"""EVARÍNYA – SPHEREx sky viewer, real data.   Run:  streamlit run app.py

Share a view:  ?ra=17h57m48.5s&dec=%2B04d41m36s&fov=12&pmra=-802.8&pmdec=10362.4
(add &embed=true to embed it in another page)
Data: NASA/IPAC Infrared Science Archive (IRSA), SPHEREx DR1 and QR3 spectral images.
"""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import spherex_data as sx
from presets import PRESETS

st.set_page_config(page_title="Evarínya – SPHEREx Sky Viewer", page_icon="🌌", layout="wide",
                   initial_sidebar_state="expanded")
def _stars(n, seed, colors=("#ffffff", "#ffffff", "#cfe3ff", "#ffe9c4")):
    """CSS box-shadow star field: n points scattered over the viewport (pure CSS, works offline)."""
    rng = np.random.default_rng(seed)
    return ",".join(f"{rng.uniform(0, 100):.1f}vw {rng.uniform(0, 100):.1f}vh 0 {colors[rng.integers(len(colors))]}"
                    for _ in range(n))


STAR_CSS = f"""
<style>
.stApp {{
  background:
    radial-gradient(ellipse 80% 55% at 78% -8%, rgba(99,102,241,.22), transparent 60%),
    radial-gradient(ellipse 70% 50% at 8% 108%, rgba(236,72,153,.14), transparent 60%),
    linear-gradient(180deg, #04060f 0%, #070b1c 55%, #0b1026 100%);
  background-attachment: fixed;
}}
.stApp::before, .stApp::after {{
  content: ""; position: fixed; top: 0; left: 0; width: 1px; height: 1px; z-index: 0; pointer-events: none;
}}
.stApp::before {{ box-shadow: {_stars(140, 1)}; opacity: .75; }}
.stApp::after  {{ width: 2px; height: 2px; border-radius: 50%; box-shadow: {_stars(34, 2)};
                  animation: twinkle 5s ease-in-out infinite alternate; }}
@keyframes twinkle {{ from {{ opacity: .25; }} to {{ opacity: 1; }} }}
[data-testid="stHeader"], [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: transparent; }}
.block-container {{ position: relative; z-index: 1; padding-top: .8rem; max-width: 1100px; }}

.hero {{ text-align: center; padding: .3rem 0 .65rem; }}
.hero .kicker {{ letter-spacing: .2em; font-size: .62rem; color: #93c5fd; text-transform: uppercase; }}
.hero h1 {{ margin: .1rem 0 .2rem; font-size: 2.15rem !important; letter-spacing: .12em; font-weight: 800;
            background: linear-gradient(90deg, #fde68a, #f59e0b 45%, #fb7185);
            -webkit-background-clip: text; background-clip: text; color: transparent;
            filter: drop-shadow(0 0 10px rgba(245,158,11,.3)); }}
.hero h1 .brand-subtitle {{ margin-left: .5rem; font-size: .48em; font-weight: 500; letter-spacing: .04em;
            color: #d5def5; -webkit-text-fill-color: #d5def5; vertical-align: middle; }}
.hero p {{ color: #aab4d4; font-size: .9rem; margin: 0 auto; max-width: 640px; }}

.stButton > button {{ border-radius: 999px; border: 1px solid rgba(147,197,253,.35);
    background: rgba(15,23,52,.55); color: #e6ecff; backdrop-filter: blur(6px); transition: all .18s; }}
.stButton > button:hover {{ border-color: #f59e0b; color: #fde68a; box-shadow: 0 0 18px rgba(245,158,11,.35);
    transform: translateY(-1px); }}
[data-testid="stAlert"] {{ background: rgba(30,58,138,.28); border: 1px solid rgba(147,197,253,.25);
    border-radius: 14px; backdrop-filter: blur(6px); }}
[data-testid="stExpander"] {{ background: rgba(13,18,36,.55); border: 1px solid rgba(147,197,253,.18);
    border-radius: 14px; backdrop-filter: blur(6px); }}
[data-testid="stSidebar"] {{ background: rgba(8,12,28,.82); backdrop-filter: blur(8px); border-right: 1px solid rgba(147,197,253,.15); }}
[data-baseweb="select"] > div {{ background: rgba(13,18,36,.65); border-radius: 10px; }}
[data-testid="stPlotlyChart"] {{ background: rgba(2,4,12,.55); border: 1px solid rgba(147,197,253,.18);
    border-radius: 16px; padding: .4rem; box-shadow: 0 10px 40px rgba(0,0,0,.45); }}
</style>
"""
st.markdown(STAR_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- cached helpers
@st.cache_data(show_spinner=False)
def get_rows(ra, dec, pmra, pmdec, epoch):
    return sx.query_rows(sx.Target(ra, dec, pmra, pmdec, epoch))


@st.cache_data(show_spinner=False, ttl=86400)
def lookup_name(ra, dec, radius_arcsec=15.0):
    """Return the nearest SIMBAD identifier, or None when no object is returned."""
    from astroquery.simbad import Simbad
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    simbad = Simbad()
    simbad.server = "simbad.harvard.edu"
    simbad.timeout = 20
    res = simbad.query_region(SkyCoord(ra * u.deg, dec * u.deg), radius=radius_arcsec * u.arcsec)
    if res is None or len(res) == 0:
        return None
    cols = {c.lower(): c for c in res.colnames}
    return str(res[cols["main_id"]][0]).strip()


@st.cache_data(show_spinner=False, ttl=86400)
def resolve_object_name(name):
    """Resolve a SIMBAD object name to J2000 coordinates and proper motion."""
    from astroquery.simbad import Simbad

    simbad = Simbad()
    simbad.server = "simbad.harvard.edu"
    simbad.timeout = 20
    simbad.add_votable_fields("pmra", "pmdec")
    result = simbad.query_object(name)
    if result is None or len(result) == 0:
        return None

    columns = {column.lower(): column for column in result.colnames}
    row = result[0]

    def value(column, default=0.0):
        item = row[columns[column]]
        return default if np.ma.is_masked(item) else float(item)

    return {
        "name": str(row[columns["main_id"]]).strip(),
        "ra": value("ra"),
        "dec": value("dec"),
        "pmra": value("pmra"),
        "pmdec": value("pmdec"),
    }


class AutoColorFailed(Exception):
    def __init__(self, info):
        super().__init__("no measurable signal in any color")
        self.info = info


@st.cache_data(show_spinner=False)
def get_auto(ra, dec, pmra, pmdec, epoch, fov):
    """Raises on failure on purpose: Streamlit does not cache exceptions, so a network hiccup is
    retried next time instead of being remembered forever."""
    t = sx.Target(ra, dec, pmra, pmdec, epoch)
    det, table, info = sx.best_detector(t, sx.query_rows(t), fov)
    if det is None:
        raise AutoColorFailed(info)
    return det, table, info


@st.cache_resource(show_spinner="Cleaning and aligning the images…")
def get_frames(ra, dec, pmra, pmdec, epoch, fov, det, n_max):
    t = sx.Target(ra, dec, pmra, pmdec, epoch)
    rows = sx.thin([r for r in sx.query_rows(t) if r["det"] == det], n_max)
    return sx.build_frames(t, rows, fov)


def to_uint8(cube, upper_pct, invert):
    lo, hi = np.nanpercentile(cube, 50), np.nanpercentile(cube, upper_pct)
    x = np.clip((cube - lo) / max(hi - lo, 1e-9), 0, 1)
    x = np.nan_to_num(np.arcsinh(10 * x) / np.arcsinh(10), nan=0.0)
    x = (255 * x).astype(np.uint8)
    return 255 - x if invert else x


CMAPS = {
    "Grayscale": [(0, (0, 0, 0)), (1, (255, 255, 255))],
    "Heat (black → red → yellow → white)": [(0, (0, 0, 0)), (.33, (190, 20, 10)),
                                            (.66, (255, 190, 30)), (1, (255, 255, 235))],
    "Ice (black → blue → white)": [(0, (0, 0, 0)), (.5, (30, 90, 200)), (1, (235, 245, 255))],
    "Rainbow (blue → green → yellow → red)": [(0, (10, 10, 90)), (.25, (30, 120, 220)),
                                              (.5, (40, 200, 120)), (.75, (250, 220, 40)),
                                              (1, (230, 40, 30))],
}


def colorize(img8, name):
    """False color: map brightness (0-255) to a color scale. Returns an RGB uint8 array."""
    stops = CMAPS[name]
    xs = [p for p, _ in stops]
    lut = np.stack([np.interp(np.arange(256) / 255, xs, [c[i] for _, c in stops]) for i in range(3)],
                   axis=1).astype(np.uint8)
    return lut[img8]


def view_box(crop, center, zoom):
    """Box (y0, y1, x0, x1) inside `crop`, `zoom` times smaller, centred on the target."""
    y0, y1, x0, x1 = crop
    hw, hh = (x1 - x0) / zoom, (y1 - y0) / zoom
    cx = x0 + (x1 - x0) / 2 if not np.isfinite(center[0]) else center[0]
    cy = y0 + (y1 - y0) / 2 if not np.isfinite(center[1]) else center[1]
    cx, cy = np.clip(cx, x0 + hw / 2, x1 - hw / 2), np.clip(cy, y0 + hh / 2, y1 - hh / 2)
    return int(round(cy - hh / 2)), int(round(cy + hh / 2)), int(round(cx - hw / 2)), int(round(cx + hw / 2))


def style_sky(fig, height=600):
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x")
    fig.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0), height=height,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", dragmode="pan")


def circle(fig, xy, r, color="#38bdf8", dash="solid"):
    x, y = float(xy[0]), float(xy[1])
    fig.add_shape(type="circle", x0=x - r, x1=x + r, y0=y - r, y1=y + r,
                  line=dict(color=color, width=1.5, dash=dash))


# ---------------------------------------------------------------- state + URL
def _set(p, tip=""):
    st.session_state.update(ra=p["ra"], dec=p["dec"], fov=float(p["fov"]), pmra=float(p["pm"][0]),
                            pmdec=float(p["pm"][1]), epoch=float(p["epoch"]), tip=tip)


def pick(name):
    _set(PRESETS[name], PRESETS[name]["tip"])
    st.session_state.name_search = ""


def use_image_candidate(ra, dec):
    st.session_state.update(ra=f"{ra:.8f}", dec=f"{dec:.8f}", pmra=0.0, pmdec=0.0,
                            epoch=sx.T_REF, tip="")


if "ra" not in st.session_state:
    st.session_state.update(ra="", dec="", fov=12.0, pmra=0.0, pmdec=0.0, epoch=2000.0, tip="")
    qp = st.query_params
    if "ra" in qp:
        try:
            st.session_state.update(
                ra=qp["ra"], dec=qp.get("dec", "0"), fov=min(max(float(qp.get("fov", 12)), 1.0), 30.0),
                pmra=float(qp.get("pmra", 0)), pmdec=float(qp.get("pmdec", 0)),
                epoch=float(qp.get("epoch", 2000)), tip="")
        except ValueError:
            pass

# ---------------------------------------------------------------- header
st.markdown(
    "<div class='hero'><div class='kicker'>NASA SPHEREx · infrared sky survey</div>"
    "<h1>EVARÍNYA&nbsp;<span class='brand-subtitle'>SPHEREx Sky Viewer</span></h1>"
    "<p>Explore real infrared images and watch the sky change.</p></div>",
    unsafe_allow_html=True)

with st.form("name_search_form"):
    search_col, button_col = st.columns([5, 1])
    search_col.text_input("Find a star or object by name", key="name_search",
                          placeholder="e.g. Teegarden's Star")
    submitted_name = button_col.form_submit_button("Find coordinates", use_container_width=True)
if submitted_name:
    object_name = st.session_state.name_search.strip()
    if not object_name:
        st.warning("Enter an object name to search SIMBAD.")
    else:
        try:
            resolved = resolve_object_name(object_name)
        except Exception as e:
            st.error(f"SIMBAD lookup failed ({type(e).__name__}): {e}")
        else:
            if resolved is None:
                st.warning(f"SIMBAD did not find an object named “{object_name}”.")
            else:
                st.session_state.ra = f"{resolved['ra']:.8f}"
                st.session_state.dec = f"{resolved['dec']:.8f}"
                st.session_state.pmra = resolved["pmra"]
                st.session_state.pmdec = resolved["pmdec"]
                st.session_state.epoch = 2000.0
                st.success(f"Found {resolved['name']}; coordinates and motion filled in.")

viewer_slot = st.empty()

with st.sidebar.expander("Example targets", expanded=False):
    for name in PRESETS:
        st.button(name, key=f"preset_{name}", on_click=pick, args=(name,), use_container_width=True)
if st.session_state.tip:
    st.info(st.session_state.tip)

st.sidebar.markdown("### Enter coordinates manually")
st.sidebar.text_input("Right ascension (RA)", key="ra",
                      help="Enter degrees (269.45) or hours (17h57m48.5s).")
st.sidebar.text_input("Declination (Dec)", key="dec",
                      help="Enter degrees (4.69) or degrees, minutes, seconds (+04d41m36s).")
with st.sidebar.expander("Advanced settings · motion and field of view"):
    st.slider("How wide an area? (arcminutes)", 1.0, 30.0, key="fov", step=0.5,
              help="Wider areas let you follow faster-moving objects, but load more slowly.")
    st.number_input("Motion in RA (mas/yr)", key="pmra", step=10.0, format="%.1f",
                    help="Optional. If you know the object's proper motion, the tool shows where it should be.")
    st.number_input("Motion in Dec (mas/yr)", key="pmdec", step=10.0, format="%.1f")
    st.number_input("Position is for year", key="epoch", step=1.0, format="%.1f",
                    help="Catalog positions are usually for the year 2000.")

ra_input = str(st.session_state.ra).strip()
dec_input = str(st.session_state.dec).strip()
if not ra_input or not dec_input:
    st.query_params.clear()
    st.info("Search for an object, choose an example, or enter both RA and Dec to load the sky viewer.")
    st.stop()

try:
    coord = sx.parse_coord(ra_input, dec_input)
except Exception:
    st.error("I couldn't read those coordinates. Try something like 269.45 and 4.69.")
    st.stop()

ra, dec, fov = float(coord.ra.deg), float(coord.dec.deg), float(st.session_state.fov)
pmra, pmdec, epoch = float(st.session_state.pmra), float(st.session_state.pmdec), float(st.session_state.epoch)
has_pm = bool(pmra or pmdec)
target = sx.Target(ra, dec, pmra, pmdec, epoch)
_c2000 = sx.propagate(coord, pmra, pmdec, epoch, 2000.0) if epoch != 2000.0 else coord
try:
    _name = lookup_name(float(_c2000.ra.deg), float(_c2000.dec.deg))
except Exception as exc:
    st.warning(f"SIMBAD lookup failed ({type(exc).__name__}: {str(exc)[:200]}). The SPHEREx view is unaffected.")
else:
    if _name:
        st.caption(f"📍 Known object here: **{_name}** (from SIMBAD)")
    else:
        st.caption("📍 No catalogued object found at this position (it may be very faint, or the position is slightly off).")
st.query_params.update(ra=st.session_state.ra, dec=st.session_state.dec, fov=str(fov),
                       pmra=str(pmra), pmdec=str(pmdec), epoch=str(epoch))

# ---------------------------------------------------------------- which images exist
try:
    with st.spinner("Asking the SPHEREx archive which images cover this spot (first time only)…"):
        rows = get_rows(ra, dec, pmra, pmdec, epoch)
except Exception as e:
    st.error(f"Couldn't search the SPHEREx archive: {type(e).__name__}: {str(e)[:300]}. "
             "If you're online, IRSA may be busy or changing its data releases, so try again in a minute. "
             "Otherwise use a target you downloaded beforehand with prefetch.py.")
    st.stop()
if not rows:
    st.warning("SPHEREx hasn't imaged this spot in the data released so far. Try another position.")
    st.stop()
counts = {d: sum(r["det"] == d for r in rows) for d in sx.BAND_UM}

# ---------------------------------------------------------------- controls
c1 = c2 = st.sidebar
choice = c1.selectbox(
    "Color of light", [None] + [d for d in sx.BAND_UM if counts[d]],
    format_func=lambda d: "Automatic: clearest view" if d is None
    else f"{sx.BAND_UM[d][0]}–{sx.BAND_UM[d][1]} µm ({counts[d]} images)",
    help="SPHEREx sees six infrared 'colors' (wavelengths in micrometres, µm). Automatic picks the "
         "one where your target stands out best; you can choose another.")
bin_days = c2.slider("Combine images taken within … days", 0, 30, 10,
                     help="Adding images together reduces noise, so faint things show up.")
c3 = c4 = c5 = st.sidebar
n_max = c3.slider("Max images per color", 10, 150, 40, help="More images: smoother but slower to download.")
upper = c4.slider("Brightness scale", 90.0, 99.99, 99.5)
invert = c5.checkbox("Dark stars on light", value=False)
cmap = c5.selectbox("Color map", list(CMAPS), index=1,
                    help="False color: brightness is shown as color, because each SPHEREx image is a single wavelength.")

if choice is None:
    with st.spinner("Finding the clearest color (downloads a few small patches)…"):
        try:
            det, table, info = get_auto(ra, dec, pmra, pmdec, epoch, fov)
        except AutoColorFailed as e:
            det, table, info = max(counts, key=counts.get), {}, e.info
            why = {"off_image": "target outside the image", "background": "not enough clean sky around it",
                   "aperture": "too many bad pixels on the target",
                   "masked_center": "every pixel at the target is flagged (a very bright star can saturate)"}
            reasons = "; ".join(f"{n}× {why.get(k, k)}" for k, n in info.get("reasons", {}).items())
            st.warning(
                f"I couldn't measure the target in any color: {info['tried']} patches tried, "
                f"{info['download_failed']} failed to download, {info['read_failed']} unreadable"
                + (f" ({reasons})" if reasons else "") + ". I'm showing the color with the most images instead. "
                + (f"Last error: {info['last_error']}. " if info["last_error"] else "")
                + "Pick a color yourself to see it.")
    if not table and info.get("note") == "saturated":
        lo, hi = sx.BAND_UM[det]
        st.caption(f"This target is very bright: the detector saturates and the core is blanked in every color, "
                   f"so I can't rank colors by signal-to-noise. Showing {lo}–{hi} µm, where the least of "
                   f"the star is blanked ({info['masked_frac'][det]:.0%} of pixels near it).")
        with st.expander("How was the color chosen?"):
            st.write("Share of pixels around the target that are blanked, per color (lower = better):")
            st.dataframe([{"Color (µm)": f"{sx.BAND_UM[d][0]}–{sx.BAND_UM[d][1]}", "Blanked": f"{v:.0%}"}
                          for d, v in sorted(info["masked_frac"].items())], hide_index=True)
    if table:
        lo, hi = sx.BAND_UM[det]
        best = table[det]
        st.caption(f"Clearest view: {lo}–{hi} µm" + ("" if best >= 3 else " (the target is faint in every color; "
                                                    "this is the best of a weak set)") + ".")
        with st.expander("How was the color chosen?"):
            st.write("Median signal-to-noise at your target, per color (higher = clearer):")
            st.dataframe([{"Color (µm)": f"{sx.BAND_UM[d][0]}–{sx.BAND_UM[d][1]}", "Signal-to-noise": round(v, 1)}
                          for d, v in sorted(table.items())], hide_index=True)
else:
    det = choice

rows_d = sx.thin([r for r in rows if r["det"] == det], n_max)
bar = st.progress(0.0, text="Downloading small image patches from IRSA (cached after the first time)…")
sx.download_rows(target, rows_d, fov, progress=bar.progress)
bar.empty()
frames, grid, scale = get_frames(ra, dec, pmra, pmdec, epoch, fov, det, n_max)
if not frames:
    st.warning("The images for this color don't cover your spot well. Try another color or position.")
    st.stop()
frames = sx.stack_frames(frames, bin_days)
labels = [f"{i + 1}. {f.date} · {f.wavelength_um:.2f} µm" + (f" · ×{f.n}" if f.n > 1 else "")
          for i, f in enumerate(frames)]

# ---------------------------------------------------------------- explore tabs

crop = sx.common_crop(frames)
cy0, cy1, cx0, cx1 = crop
p_first = np.array(grid.world_to_pixel(target.at_mjd(frames[0].mjd)), float)
p_last = np.array(grid.world_to_pixel(target.at_mjd(frames[-1].mjd)), float)
years = (frames[-1].mjd - frames[0].mjd) / 365.25
shift_as = float(np.hypot(pmra, pmdec)) / 1000 * years
wls = [f.wavelength_um for f in frames]

image_container = viewer_slot.container()
m1, m2 = image_container.columns([3, 2])
mode = m1.radio("View", ["▶ Animate", "⇄ Earliest vs latest"], horizontal=True, label_visibility="collapsed")
zoom = m2.slider("Zoom", 1.0, 4.0, 1.0, 0.5, help="Zoom in on the target.")
speed = image_container.slider("Speed", 1, 10, 3) if mode.startswith("▶") and len(frames) > 1 else None

vy0, vy1, vx0, vx1 = view_box(crop, p_first, zoom)
cube8 = to_uint8(np.stack([f.image[cy0:cy1, cx0:cx1] for f in frames]), upper, invert)
view = colorize(cube8[:, vy0 - cy0:vy1 - cy0, vx0 - cx0:vx1 - cx0], cmap)
off = np.array([vx0, vy0], float)
r_px = 15 / scale
ring = "#22d3ee" if cmap != "Grayscale" else ("#f59e0b" if not invert else "#0369a1")

if mode.startswith("▶"):
    fig = px.imshow(view, animation_frame=0, origin="lower", binary_string=True)
    if fig.layout.sliders:
        sl = fig.layout.sliders[0]
        for step, f in zip(sl.steps, frames):
            step.label = f.date
        sl.currentvalue = dict(prefix="Date: ", font=dict(size=14))
        sl.pad = dict(t=10)
        if fig.layout.updatemenus:
            btn = fig.layout.updatemenus[0].buttons[0].args[1]
            btn["frame"]["duration"] = int(1000 / speed)
            btn["transition"] = dict(duration=0)
    elif len(frames) == 1:
        image_container.caption("Only one image is available for this target, so it is shown as a still frame.")
    marks = [(p_first, "solid")] + ([(p_last, "dot")] if has_pm else [])
else:
    pick_l = image_container.radio(
        "Show", [f"Earliest · {frames[0].date}", f"Latest · {frames[-1].date}"], horizontal=True)
    latest = pick_l.startswith("Latest")
    fig = px.imshow(view[-1 if latest else 0], origin="lower", binary_string=True)
    marks = [(p_last if latest else p_first, "solid")] + \
            ([(p_first if latest else p_last, "dot")] if has_pm else [])
for xy, dash in marks:
    circle(fig, xy - off, r_px, ring, dash)
if has_pm:
    a_, b_ = p_first - off, p_last - off
    fig.add_shape(type="line", x0=float(a_[0]), y0=float(a_[1]), x1=float(b_[0]), y1=float(b_[1]),
                  line=dict(color=ring, width=1, dash="dot"))
style_sky(fig, 600)
image_container.plotly_chart(fig, use_container_width=True, config=dict(displaylogo=False, scrollZoom=True))
_st = CMAPS[cmap] if not invert else [(1 - p, c) for p, c in reversed(CMAPS[cmap])]
_grad = ", ".join(f"rgb{c} {int(p * 100)}%" for p, c in _st)
image_container.markdown(
    f"<div style='height:10px;border-radius:6px;background:linear-gradient(90deg,{_grad})'></div>"
    "<div style='display:flex;justify-content:space-between;font-size:.75rem;color:#8b96b8'>"
    "<span>faint</span><span>bright</span></div>",
    unsafe_allow_html=True,
)

tab_play, tab_cmp, tab_spec, tab_info, tab_guide = st.tabs(
    ["▶ Watch it change", "Compare two dates", "Colors of light", "About this data", "❓ Help"])

with tab_play:
    lo_b, hi_b = sx.BAND_UM[det]
    if has_pm and len(frames) > 1:
        px_move = shift_as / sx.PIXEL_ARCSEC
        st.markdown(f"**What to look for:** your target should drift about **{shift_as:.1f}″** between "
                    f"{frames[0].date} and {frames[-1].date} (≈ {px_move:.1f} SPHEREx pixels). "
                    + ("That is small, so try the *Earliest vs latest* view and zoom in." if px_move < 3 else
                       "Follow the dotted line: the star should travel along it."))
    elif not has_pm:
        st.markdown("**What to look for:** the ring marks the position you entered. Watch whether the "
                    "object there gets brighter or fainter.")
    st.caption(f"{len(frames)} frames · {lo_b}–{hi_b} µm · wavelength drifts {min(wls):.2f}–{max(wls):.2f} µm "
               f"across frames, so a star can change brightness without being variable. "
               "North is up, east is left. Background gradients are removed and every frame shares one "
               "brightness scale.")

    with st.expander("Search these images for possible sources"):
        st.caption("Looks for bright image peaks near your position. These are candidates, not confirmed objects.")
        candidate_key = (
            ra, dec, pmra, pmdec, epoch, det, fov, n_max, bin_days,
            tuple((f.mjd, f.n) for f in frames),
        )
        if st.session_state.get("image_candidates_key") != candidate_key:
            st.session_state.pop("image_candidates_key", None)
            st.session_state.pop("image_candidates", None)
        if st.button("Detect image candidates", key="detect_image_candidates"):
            with st.spinner("Searching the selected SPHEREx images for bright peaks…"):
                found = sx.image_candidates(
                    frames, grid, target, radius_arcmin=min(1.0, fov / 2))
            st.session_state.image_candidates = found
            st.session_state.image_candidates_key = candidate_key

        if st.session_state.get("image_candidates_key") == candidate_key:
            candidates = st.session_state.image_candidates
            if not candidates:
                st.info("No strong image peaks were found near this position in the selected color.")
            else:
                st.caption("Coordinates are for 2026.0. Peak significance is estimated from image noise.")
                st.dataframe(
                    [{
                        "Candidate": f"Image peak {i + 1}",
                        "RA (deg)": round(candidate["ra"], 7),
                        "Dec (deg)": round(candidate["dec"], 7),
                        "Offset (arcmin)": round(candidate["separation_arcmin"], 3),
                        "Peak significance (sigma)": round(candidate["snr"], 1),
                    } for i, candidate in enumerate(candidates)],
                    hide_index=True,
                )
                selected = st.selectbox(
                    "Candidate to inspect",
                    range(len(candidates)),
                    format_func=lambda i: (
                        f"Candidate {i + 1} · {candidates[i]['ra']:.6f}, "
                        f"{candidates[i]['dec']:.6f}"
                    ),
                    key=f"image_candidate_choice_{det}_{len(frames)}_{bin_days}",
                )
                st.button(
                    "Use selected candidate as the target",
                    key="use_image_candidate",
                    on_click=use_image_candidate,
                    args=(candidates[selected]["ra"], candidates[selected]["dec"]),
                )

with tab_cmp:
    if len(frames) < 2:
        st.info("Only one image at this color: nothing to compare.")
    else:
        a_l = st.select_slider("Earlier", labels, value=labels[0])
        b_l = st.select_slider("Later", labels, value=labels[-1])
        a, b = frames[labels.index(a_l)], frames[labels.index(b_l)]
        if abs(a.wavelength_um - b.wavelength_um) > 0.05 * a.wavelength_um:
            st.warning("These two images are at noticeably different wavelengths, so bright stars can "
                       "differ for that reason alone. Pick two with similar wavelengths if you can.")
        diff = np.nan_to_num(b.image - a.image)[cy0:cy1, cx0:cx1]
        vmax = float(np.percentile(np.abs(diff), 99.5)) or 1.0
        fig2 = px.imshow(diff, origin="lower", color_continuous_scale="RdBu_r", zmin=-vmax, zmax=vmax,
                         aspect="equal", template="plotly_dark")
        if has_pm:
            o = np.array([cx0, cy0], float)
            pa = np.array(grid.world_to_pixel(target.at_mjd(a.mjd)), float) - o
            pb = np.array(grid.world_to_pixel(target.at_mjd(b.mjd)), float) - o
            circle(fig2, pa, 15 / scale, "white", "dot")
            circle(fig2, pb, 15 / scale, "white")
            fig2.add_annotation(x=float(pb[0]), y=float(pb[1]), ax=float(pa[0]), ay=float(pa[1]),
                                xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                                arrowhead=2, arrowcolor="white")
        style_sky(fig2, 560)
        fig2.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Fixed stars cancel out. Red = brighter later, blue = brighter earlier. "
                   + ("The dotted circle is where the object should have been on the earlier date, "
                      "the solid circle where it should be on the later date." if has_pm else
                      "A moving object appears as a blue and red pair."))

with tab_spec:
    st.write("How bright this spot is at each infrared color, measured from the images.")
    key = (ra, dec, pmra, pmdec, epoch, fov, n_max)
    if st.button("Measure the spectrum (downloads all six colors: a few minutes the first time)"):
        all_rows = [r for d in sx.BAND_UM for r in sx.thin([x for x in rows if x["det"] == d], n_max)]
        bar2 = st.progress(0.0, text="Downloading…")
        pts = sx.spectrum(target, all_rows, fov, progress=bar2.progress)
        bar2.empty()
        st.session_state["spec"] = (key, pts)
    saved = st.session_state.get("spec")
    if saved and saved[0] == key:
        figs = go.Figure()
        for d in sx.BAND_UM:
            pts = [p for p in saved[1] if p["det"] == d]
            figs.add_trace(go.Scatter(x=[p["wl"] for p in pts], y=[p["flux"] for p in pts], mode="markers",
                                      name=f"{sx.BAND_UM[d][0]}–{sx.BAND_UM[d][1]} µm"))
        figs.update_layout(template="plotly_dark", xaxis_title="Wavelength (µm)",
                           yaxis_title="Brightness (mJy, approximate)", height=420,
                           margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(figs, use_container_width=True)
        st.caption("Rough aperture photometry: good for comparing colors, not for absolute brightness. "
                   "Points with no clear source scatter around zero.")

with tab_info:
    st.dataframe([{"Frame": lab, "Color (detector)": f.detector, "Wavelength (µm)": round(f.wavelength_um, 3),
                   "Exposures combined": f.n, "Possible contamination near target": ", ".join(f.flags) or "none"}
                  for lab, f in zip(labels, frames)], hide_index=True, use_container_width=True)
    st.caption("Data: NASA/IPAC Infrared Science Archive, SPHEREx DR1 and QR3 spectral images (wide survey). "
               "Zodiacal light is subtracted and flagged pixels are masked. To share this view, copy the "
               "page address; add &embed=true to embed it.")

with tab_guide:
    _e = st.expander("1. What am I looking at?", expanded=True)
    _e.markdown(
        "These are **real infrared images from NASA's SPHEREx space telescope**, launched on 11 March 2025. "
        "SPHEREx maps the whole sky in **102 infrared spectral channels**, from 0.75 to 5.0 micrometres (µm). "
        "Our eyes see only a small part of this light. The nominal 25-month mission plans four independent "
        "all-sky surveys. Each region is typically completed over a few days during a survey pass; the actual "
        "time between observations of a particular target varies.")

    _e = st.expander("2. Why is it grey (or red, yellow, blue)?")
    _e.markdown(
        "A SPHEREx image records **how much infrared light arrived at each pixel**; it does not record visible "
        "color. The image values are brightness measurements, in MJy/sr (megajanskys per steradian).\n\n"
        "- **Grayscale:** dark = faint, white = bright.\n"
        "- **Heat, Ice, or Rainbow:** the same brightness mapped to colors so differences are easier to see. "
        "This is called *false color*. Here, color represents **brightness**, not the star's real color or its "
        "temperature. The faint-to-bright bar shows the mapping; changing the selected infrared range is a "
        "separate control.")

    _e = st.expander("3. What does “Color of light” choose?")
    _e.markdown(
        "SPHEREx has six detectors, each covering 17 of the mission's 102 spectral channels. The app groups "
        "those channels into six detector ranges. Choose one to view; each exposure measures the target at a "
        "specific wavelength within that range.")
    _e.dataframe(
        [{"Detector": d, "Wavelength range (µm)": f"{lo:.2f}–{hi:.2f}"}
         for d, (lo, hi) in sx.BAND_UM.items()],
        hide_index=True,
    )
    _e.markdown(
        "**Automatic** samples a few exposures in each available detector range and chooses the one where the "
        "target has the strongest signal compared with the background noise.")

    _e = st.expander("4. Why can a star change brightness between frames?")
    _e.markdown(
        "SPHEREx uses a *linear variable filter*: wavelength changes across the field of view. As the telescope "
        "points in different directions, a target is measured at different positions on the filter and therefore "
        "at slightly different wavelengths. A star can get brighter or fainter between frames **without being a "
        "variable star**. The wavelength for each frame is listed in *About this data*.")

    _e = st.expander("5. What is moving? What are the ring and dotted line?")
    _e.markdown(
        "Most stars appear fixed, but nearby stars can have **proper motion**: a slow drift across the sky, "
        "entered in milliarcseconds per year (mas/yr). Barnard's Star moves about 10 arcseconds per year, while "
        "one SPHEREx pixel is 6.15 arcseconds wide.\n\n"
        "- The **solid ring** marks the predicted starting position in the animation, or the selected date in "
        "*Earliest vs latest*.\n"
        "- When motion is entered, the **dotted ring** marks the predicted position at the other end of the "
        "date range, and the dotted line shows the predicted path.\n"
        "- If the target does not line up, check its coordinates, proper motion, and coordinate epoch.")

    _e = st.expander("6. Compare two dates")
    _e.markdown(
        "The app subtracts the earlier image from the later one. Unchanged stars mostly cancel out. "
        "**Red** means brighter later; **blue** means brighter earlier. A moving source can appear as a blue "
        "and red pair. Wavelength differences between the two frames can also change a star's apparent "
        "brightness.")

    _e = st.expander("7. Colors of light (the spectrum)")
    _e.markdown(
        "Each exposure provides one brightness measurement at one wavelength. Together, the measurements form "
        "a rough **spectrum**: brightness versus wavelength. The app uses aperture photometry: it sums the "
        "signal in a small circle around the target and subtracts an estimate of the nearby sky. This is useful "
        "for comparing colors, not for precise or calibrated brightness.")

    _e = st.expander("8. Signal-to-noise (S/N)")
    _e.markdown(
        "S/N describes how strongly a target stands out from background noise. An S/N of 10 means the measured "
        "signal is about ten times the estimated noise. In this app, the estimate uses the scatter in nearby sky "
        "pixels and the number of pixels in the measurement aperture. As a rough rule of thumb, astronomers often "
        "look for S/N of 3–5 or more; this app labels the best result as faint when its S/N is below 3.")

    _e = st.expander("9. Why are there black patches or missing stars?")
    _e.markdown(
        "The data flags pixels that are unreliable, including pixels affected by events such as cosmic rays or "
        "saturation. The app masks flagged pixels and crops edges where the exposures do not overlap. A very "
        "bright star can saturate the detector, leaving its center blank. Very faint sources may not stand out "
        "in a single exposure; try another infrared range or combine more images.")

    _e = st.expander("10. What does this app do to the data?")
    _e.markdown(
        "1. Asks IRSA (NASA/IPAC's Infrared Science Archive) which exposures cover the target, then downloads "
        "small image cutouts.\n"
        "2. Subtracts the supplied model of **zodiacal light** (sunlight scattered by dust in our solar system).\n"
        "3. Masks flagged pixels, removes the remaining smooth background, and aligns the exposures on a "
        "common north-up grid.\n"
        "4. Crops to the region shared by the frames and uses one brightness scale so frames can be compared. "
        "The brightness-scale control changes the display stretch.\n"
        "5. Optionally combines nearby-in-time exposures using a **median**, which helps reduce noise.")

    _e = st.expander("Sources")
    _e.markdown(
        "- NASA SPHEREx mission: https://www.nasa.gov/missions/spherex/\n"
        "- SPHEREx survey and observing strategy: https://spherex.caltech.edu/page/survey\n"
        "- IRSA SPHEREx data products: "
        "https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products\n"
        "- IRSA SPHEREx tutorial: https://caltech-ipac.github.io/irsa-tutorials/spherex-intro\n"
        "- SIMBAD Astronomical Database (CDS), for object-name and nearby-object lookups: "
        "https://simbad.cds.unistra.fr/simbad/\n"
        "- SIMBAD reference: Wenger et al. (2000), A&AS, 143, 9: "
        "https://doi.org/10.1051/aas:2000332\n"
        "- Bock et al., *The SPHEREx Satellite Mission*: https://arxiv.org/abs/2511.02985")
