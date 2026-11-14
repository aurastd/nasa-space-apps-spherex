"""Real SPHEREx data access for Evarínya.

Flow: IRSA SIA2 query (which exposures cover this spot?) -> IRSA cutout service (download a
small patch of each exposure) -> clean + reproject each patch onto one north-up grid -> Frames.
Everything downloaded is cached in ./cache, so a second run (or a run without wifi) is instant.

Quick test (needs internet the first time):
    python spherex_data.py 17h57m48.5s +04d41m36s 12

Sources: IRSA SPHEREx data-access guide and the IRSA tutorial notebooks (SIA2 collections
spherex_dr1 / spherex_qr3, cutouts via ?center=..&size=.., spectral WCS key "W").
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import re
import sys
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import requests
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS

warnings.filterwarnings("ignore", module="astropy")

COLLECTIONS = ["spherex_dr1", "spherex_qr3"]        # wide survey (QR2 is no longer searchable)
CACHE = Path(__file__).parent / "cache"
BAND_UM = {1: (0.75, 1.09), 2: (1.10, 1.62), 3: (1.63, 2.41),
           4: (2.42, 3.82), 5: (3.83, 4.41), 6: (4.42, 5.00)}      # one range per detector
T_REF = 2026.0                                      # reference epoch for cutout and grid centers
PIXEL_ARCSEC = 6.15
MJYSR_TO_MJY_PER_PIX = (PIXEL_ARCSEC / 206265.0) ** 2 * 1e9   # MJy/sr in one pixel -> mJy

# FLAGS bits (names from the FLAGS extension header)
BAD_MASK = sum(1 << b for b in (0, 1, 2, 6, 7, 9, 10, 11, 15))   # unusable pixels -> NaN
CONTAM = {17: "persistence", 20: "crosstalk", 22: "ghost", 23: "ghost", 24: "ghost",
          25: "streak", 26: "bloom", 27: "snowball", 28: "halo"}


# ------------------------------------------------------------------ small types
@dataclass(frozen=True)
class Target:
    ra: float                  # degrees, at `epoch`
    dec: float
    pm_ra: float = 0.0         # mas/yr, already multiplied by cos(dec)
    pm_dec: float = 0.0
    epoch: float = 2000.0

    def at(self, year: float) -> SkyCoord:
        return propagate(SkyCoord(self.ra * u.deg, self.dec * u.deg), self.pm_ra, self.pm_dec, self.epoch, year)

    def at_mjd(self, mjd: float) -> SkyCoord:
        return self.at(Time(mjd, format="mjd").jyear)


@dataclass
class Frame:
    mjd: float
    detector: int
    wavelength_um: float
    image: np.ndarray                                   # float32, north up, MJy/sr, background removed
    flags: list = field(default_factory=list)           # contamination near the target
    n: int = 1                                          # exposures stacked into this frame

    @property
    def date(self) -> str:
        return Time(self.mjd, format="mjd").iso[:10]


def parse_coord(ra: str, dec: str) -> SkyCoord:
    """Degrees ('269.45', '4.69') or sexagesimal ('17h57m48.5s', '+04d41m36s')."""
    ra, dec = ra.strip(), dec.strip()
    try:
        return SkyCoord(float(ra) * u.deg, float(dec) * u.deg)
    except ValueError:
        return SkyCoord(ra, dec, unit=(u.hourangle, u.deg))


def propagate(coord, pm_ra, pm_dec, epoch0, year):
    """Linear proper-motion shift from epoch0 to `year` (fine for a few decades)."""
    dt = year - epoch0
    dec = coord.dec.deg + pm_dec * dt / 3.6e6
    ra = coord.ra.deg + pm_ra * dt / 3.6e6 / np.cos(np.radians((coord.dec.deg + dec) / 2))
    return SkyCoord(ra * u.deg, dec * u.deg)


def _key(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


def detector_of(url: str, name: str = "") -> int:
    for pattern, text in ((r"/(\d)/level2_", url), (r"_\dD(\d)_spx", url), (r"D(\d)", name)):
        m = re.search(pattern, text)
        if m:
            return int(m.group(1))
    return 0


def thin(rows, n):
    """At most n rows, evenly spread over time (rows are sorted by date)."""
    if not n or len(rows) <= n:
        return rows
    idx = sorted(set(np.linspace(0, len(rows) - 1, n).round().astype(int)))
    return [rows[i] for i in idx]


# ------------------------------------------------------------------ query + download
def _sia_query(target: Target, radius_arcmin: float):
    from astroquery.ipac.irsa import Irsa
    res = Irsa.query_sia(pos=(target.at(T_REF), radius_arcmin * u.arcmin), collection=COLLECTIONS)
    names, rows, seen = res.colnames, [], set()
    for r in res:
        url = str(r["access_url"])
        det = detector_of(url, str(r["energy_bandpassname"]) if "energy_bandpassname" in names else "")
        try:
            mjd = float(r["t_min"])
        except Exception:
            continue
        key = (round(mjd, 4), det)
        if det and np.isfinite(mjd) and key not in seen:
            seen.add(key)
            rows.append(dict(url=url, mjd=mjd, det=det))
    rows.sort(key=lambda r: r["mjd"])
    return rows


def query_rows(target: Target, radius_arcmin: float = 1.0, max_age_days: float = 7.0):
    """Every exposure covering the target: [{url, mjd, det}, ...]. Cached as JSON (new data
    arrives weekly, so the cache is refreshed after a week; an old cache still works offline)."""
    f = CACHE / "queries" / f"{_key(round(target.ra, 5), round(target.dec, 5), target.pm_ra, target.pm_dec, target.epoch)}.json"
    if f.exists() and time.time() - f.stat().st_mtime < max_age_days * 86400:
        return json.loads(f.read_text())
    try:
        rows = _sia_query(target, radius_arcmin)
    except Exception:
        if f.exists():
            return json.loads(f.read_text())
        raise
    if rows:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rows))
    return rows


def cutout_size_deg(fov_arcmin: float) -> float:
    """Cutout side in degrees: 1.5 x the field of view (exposures are rotated), in a few fixed
    sizes so different slider values share the same cached downloads."""
    need = fov_arcmin * 1.5 / 60
    return next((s for s in (0.1, 0.2, 0.3, 0.5, 0.75) if s >= need), need)


def cutout_url(url: str, center: SkyCoord, size_deg: float) -> str:
    return f"{url}?center={center.ra.deg:.6f},{center.dec.deg:.6f}d&size={size_deg:.4f}"


def fetch(url: str, retries: int = 3) -> Path:
    path = CACHE / "cutouts" / f"{_key(url)}.fits"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    for k in range(retries):
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            tmp = path.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(path)
            return path
        except requests.RequestException:
            if k == retries - 1:
                raise
            time.sleep(2 * (k + 1))


def download_all(urls, progress=None, workers: int = 8):
    paths = [None] * len(urls)
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch, u_): i for i, u_ in enumerate(urls)}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            try:
                paths[futs[fut]] = fut.result()
            except Exception:
                pass
            if progress:
                progress(k / len(urls))
    return paths


def download_rows(target: Target, rows, fov_arcmin: float, progress=None):
    center, size = target.at(T_REF), cutout_size_deg(fov_arcmin)
    return download_all([cutout_url(r["url"], center, size) for r in rows], progress)


# ------------------------------------------------------------------ reading one cutout
def read_cutout(path, center: SkyCoord):
    """One cutout -> dict(img, wcs, flg, x, y, wl, det). The zodiacal light is removed and
    unusable pixels are NaN. (x, y) and the wavelength are those of `center` in this exposure."""
    with fits.open(path, memmap=False) as hdul:
        hdr = hdul["IMAGE"].header
        img = np.array(hdul["IMAGE"].data, dtype=float)
        zodi = np.array(hdul["ZODI"].data, dtype=float) if "ZODI" in hdul else 0.0
        flg = np.array(hdul["FLAGS"].data, dtype=np.int64) if "FLAGS" in hdul else np.zeros(img.shape, np.int64)
        wcs = WCS(hdr)
        x, y = wcs.world_to_pixel(center)
        try:                                    # per-pixel wavelength (linear variable filter)
            swcs = WCS(hdr, fobj=hdul, key="W")
            swcs.sip = None
            wl = float(swcs.pixel_to_world(x, y)[0].to(u.um).value)
        except Exception:
            wl = float("nan")
        det = int(hdr.get("DETECTOR", 0) or 0)
    img = img - zodi
    img[(flg & BAD_MASK) != 0] = np.nan
    return dict(img=img, wcs=wcs, flg=flg, x=float(x), y=float(y), wl=wl, det=det)


def contamination_near(flg, x, y, r: int = 3):
    h, w = flg.shape
    x0, x1, y0, y1 = int(max(x - r, 0)), int(min(x + r + 1, w)), int(max(y - r, 0)), int(min(y + r + 1, h))
    if x1 <= x0 or y1 <= y0:
        return []
    patch = int(np.bitwise_or.reduce(flg[y0:y1, x0:x1].ravel()))
    return sorted({name for bit, name in CONTAM.items() if (patch >> bit) & 1})


def photometry(img, x, y, ap=2.0, r_in=5.0, r_out=9.0, search=1.5):
    """Rough aperture photometry at (x, y) on a native-pixel image: returns (flux in mJy, S/N).
    The aperture is nudged to the brightest pixel within `search` pixels. No aperture or color
    correction: good for comparing colors, not for absolute fluxes."""
    yy, xx = np.indices(img.shape)
    ok = np.isfinite(img)
    cand = np.where(ok & (np.hypot(xx - x, yy - y) <= search), img, -np.inf)
    if not np.isfinite(cand).any():
        return np.nan, np.nan
    iy, ix = np.unravel_index(cand.argmax(), cand.shape)
    d = np.hypot(xx - ix, yy - iy)
    in_ap, bg = ok & (d <= ap), ok & (d >= r_in) & (d <= r_out)
    if in_ap.sum() < 3 or bg.sum() < 10:
        return np.nan, np.nan
    b = np.median(img[bg])
    sigma = 1.4826 * np.median(np.abs(img[bg] - b))
    flux = float(np.sum(img[in_ap] - b))
    noise = max(sigma * np.sqrt(in_ap.sum()), 1e-12)
    return flux * MJYSR_TO_MJY_PER_PIX, flux / noise


def measure(path, center: SkyCoord):
    c = read_cutout(path, center)
    flux, snr = photometry(c["img"], c["x"], c["y"])
    return dict(det=c["det"], wl=c["wl"], flux=flux, snr=snr)


# ------------------------------------------------------------------ frames
def make_grid(center: SkyCoord, fov_arcmin: float, max_px: int = 300):
    scale = max(3.0, fov_arcmin * 60 / max_px)          # arcsec per output pixel (oversampled 2x)
    n = int(round(fov_arcmin * 60 / scale))
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [center.ra.deg, center.dec.deg]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-scale / 3600, scale / 3600]
    return w, (n, n), scale


def smooth_background(img, block: int = 30, pct: float = 30.0):
    """Slowly varying background (leftover zodiacal light, detector gradients): a low percentile
    in coarse blocks (so stars barely bias it), interpolated back up to full size."""
    from scipy import ndimage as ndi
    h, w = img.shape
    ny, nx = max(int(np.ceil(h / block)), 1), max(int(np.ceil(w / block)), 1)
    coarse = np.full((ny, nx), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for j in range(ny):
            for i in range(nx):
                blk = img[j * block:(j + 1) * block, i * block:(i + 1) * block]
                if np.isfinite(blk).sum() >= 0.3 * blk.size:
                    coarse[j, i] = np.nanpercentile(blk, pct)
    good = np.isfinite(coarse)
    if not good.any():
        return np.zeros_like(img)
    coarse[~good] = np.median(coarse[good])
    yy, xx = np.indices(img.shape)
    bg = ndi.map_coordinates(coarse, [(yy + 0.5) / block - 0.5, (xx + 0.5) / block - 0.5],
                             order=1, mode="nearest")
    return bg


def common_crop(frames, edge_ok: float = 0.97):
    """Largest box (y0, y1, x0, x1) with solid data in every frame, so the ragged black edges where
    exposures don't overlap are cut away. Isolated masked pixels are tolerated."""
    from scipy import ndimage as ndi
    ok = np.ones(frames[0].image.shape, bool)
    for f in frames:                     # a pixel is solid if >=80% of its 5x5 neighbourhood has data
        ok &= ndi.uniform_filter(np.isfinite(f.image).astype(float), size=5) >= 0.8
    y0, x0 = 0, 0
    y1, x1 = ok.shape
    while y1 - y0 > 20 and x1 - x0 > 20:
        edges = {"t": ok[y0, x0:x1].mean(), "b": ok[y1 - 1, x0:x1].mean(),
                 "l": ok[y0:y1, x0].mean(), "r": ok[y0:y1, x1 - 1].mean()}
        worst = min(edges, key=edges.get)
        if edges[worst] >= edge_ok:
            break
        if worst == "t":
            y0 += 1
        elif worst == "b":
            y1 -= 1
        elif worst == "l":
            x0 += 1
        else:
            x1 -= 1
    return y0, y1, x0, x1


def build_frames(target: Target, rows, fov_arcmin: float, progress=None):
    """Download (cached), clean and reproject every exposure in `rows` onto one north-up grid.
    Returns (frames, grid_wcs, arcsec_per_pixel)."""
    from reproject import reproject_interp
    center = target.at(T_REF)
    paths = download_rows(target, rows, fov_arcmin, progress)
    grid, shape, scale = make_grid(center, fov_arcmin)
    frames = []
    for r, p in zip(rows, paths):
        if p is None:
            continue
        try:
            c = read_cutout(p, target.at_mjd(r["mjd"]))
            out = reproject_interp((c["img"], c["wcs"]), grid, shape_out=shape,
                                   order="bilinear", return_footprint=False)
        except Exception:
            continue
        if np.isfinite(out).mean() < 0.5:               # target too close to the detector edge
            continue
        out = out.astype(np.float32)
        out -= smooth_background(out)
        det = c["det"] or r["det"]
        wl = c["wl"] if np.isfinite(c["wl"]) else float(np.mean(BAND_UM[det]))
        frames.append(Frame(r["mjd"], det, wl, out, contamination_near(c["flg"], c["x"], c["y"])))
    return frames, grid, scale


def stack_frames(frames, bin_days: float):
    """Co-add (median) exposures taken within `bin_days` of each other, to cut the noise."""
    if bin_days <= 0 or len(frames) < 2:
        return frames
    frames = sorted(frames, key=lambda f: f.mjd)
    groups, cur = [], [frames[0]]
    for f in frames[1:]:
        if f.mjd - cur[0].mjd <= bin_days:
            cur.append(f)
        else:
            groups.append(cur)
            cur = [f]
    groups.append(cur)
    out = []
    for g in groups:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            img = np.nanmedian(np.stack([f.image for f in g]), axis=0).astype(np.float32)
            wl = float(np.nanmean([f.wavelength_um for f in g]))
        out.append(Frame(float(np.mean([f.mjd for f in g])), g[0].detector, wl, img,
                         sorted({x for f in g for x in f.flags}), len(g)))
    return out


# ------------------------------------------------------------------ colors and spectrum
def best_detector(target: Target, rows, fov_arcmin: float, per_det: int = 4, progress=None):
    """Sample a few exposures per color, measure the signal-to-noise at the target, and return
    (best detector, {detector: median S/N}, info). Colors with 3+ images are preferred; if none
    qualifies, any measured color is used. `info` says how many downloads/measurements failed
    and why, so the app can explain itself instead of silently guessing."""
    by_det = {}
    for r in rows:
        by_det.setdefault(r["det"], []).append(r)
    chosen = [r for rs in by_det.values() for r in thin(rs, per_det)]
    paths = download_rows(target, chosen, fov_arcmin, progress)
    info = dict(tried=len(chosen), download_failed=0, read_failed=0, no_signal=0, last_error="")
    snrs = {}
    for r, p in zip(chosen, paths):
        if p is None:
            info["download_failed"] += 1
            continue
        try:
            m = measure(p, target.at_mjd(r["mjd"]))
        except Exception as e:
            info["read_failed"] += 1
            info["last_error"] = f"{type(e).__name__}: {e}"
            continue
        if np.isfinite(m["snr"]):
            snrs.setdefault(r["det"], []).append(m["snr"])
        else:
            info["no_signal"] += 1
    table = {d: float(np.median(v)) for d, v in snrs.items()}
    if not table:
        return None, {}, info
    ok = [d for d in table if len(by_det[d]) >= 3] or list(table)
    return max(ok, key=table.get), table, info


def spectrum(target: Target, rows, fov_arcmin: float, progress=None):
    """Photometry of every exposure in `rows` (any colors): [{det, wl, flux, snr, mjd}, ...]."""
    paths = download_rows(target, rows, fov_arcmin, progress)
    out = []
    for r, p in zip(rows, paths):
        if p is None:
            continue
        try:
            m = measure(p, target.at_mjd(r["mjd"]))
        except Exception:
            continue
        if np.isfinite(m["flux"]) and np.isfinite(m["wl"]):
            out.append(dict(m, mjd=r["mjd"]))
    return out


# ------------------------------------------------------------------ command-line test
def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return
    c = parse_coord(argv[1], argv[2])
    fov = float(argv[3]) if len(argv) > 3 else 12.0
    t = Target(c.ra.deg, c.dec.deg)
    print("Querying IRSA...")
    rows = query_rows(t)
    print(f"{len(rows)} exposures cover this spot")
    for d, (lo, hi) in BAND_UM.items():
        print(f"  detector {d} ({lo}-{hi} um): {sum(r['det'] == d for r in rows)} images")
    if not rows:
        return
    print("Measuring a few exposures per detector...")
    best, table, info = best_detector(t, rows, fov, progress=lambda f: print(f"\r  {f:4.0%}", end=""))
    print("\nS/N by detector:", {d: round(v, 1) for d, v in table.items()}, "-> best:", best, info)
    if best:
        sel = thin([r for r in rows if r["det"] == best], 10)
        frames, grid, scale = build_frames(t, sel, fov)
        print(f"Built {len(frames)} frames of {frames[0].image.shape} px at {scale:.1f} arcsec/px; "
              f"dates {frames[0].date} to {frames[-1].date}")


if __name__ == "__main__":
    main(sys.argv)
