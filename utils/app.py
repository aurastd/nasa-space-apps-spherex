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
from presets import DEFAULT, PRESETS

st.set_page_config(page_title="Evarínya – SPHEREx Sky Viewer", page_icon="🌌", layout="wide")
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
.block-container {{ position: relative; z-index: 1; padding-top: 2.2rem; max-width: 1100px; }}

.hero {{ text-align: center; padding: 1.2rem 0 1.4rem; }}
.hero .kicker {{ letter-spacing: .35em; font-size: .72rem; color: #93c5fd; text-transform: uppercase; }}
.hero h1 {{ margin: .25rem 0 .2rem; font-size: 3.1rem !important; letter-spacing: .22em; font-weight: 800;
            background: linear-gradient(90deg, #fde68a, #f59e0b 45%, #fb7185);
            -webkit-background-clip: text; background-clip: text; color: transparent;
            filter: drop-shadow(0 0 18px rgba(245,158,11,.35)); }}
.hero p {{ color: #aab4d4; font-size: 1.05rem; margin: 0 auto; max-width: 640px; }}
.hero .steps {{ margin-top: .9rem; color: #7f8bb3; font-size: .85rem; letter-spacing: .04em; }}

.stButton > button {{ border-radius: 999px; border: 1px solid rgba(147,197,253,.35);
    background: rgba(15,23,52,.55); color: #e6ecff; backdrop-filter: blur(6px); transition: all .18s; }}
.stButton > button:hover {{ border-color: #f59e0b; color: #fde68a; box-shadow: 0 0 18px rgba(245,158,11,.35);
    transform: translateY(-1px); }}
[data-testid="stAlert"] {{ background: rgba(30,58,138,.28); border: 1px solid rgba(147,197,253,.25);
    border-radius: 14px; backdrop-filter: blur(6px); }}
[data-testid="stExpander"] {{ background: rgba(13,18,36,.55); border: 1px solid rgba(147,197,253,.18);
    border-radius: 14px; backdrop-filter: blur(6px); }}
[data-baseweb="select"] > div {{ background: rgba(13,18,36,.65); border-radius: 10px; }}
[data-baseweb="tab-list"] {{ gap: .4rem; }}
button[data-baseweb="tab"] {{ border-radius: 10px 10px 0 0; }}
[data-testid="stPlotlyChart"] {{ background: rgba(2,4,12,.55); border: 1px solid rgba(147,197,253,.18);
    border-radius: 16px; padding: .4rem; box-shadow: 0 10px 40px rgba(0,0,0,.45); }}
</style>
"""
st.markdown(STAR_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- cached helpers
@st.cache_data(show_spinner=False)
def get_rows(ra, dec, pmra, pmdec, epoch):
    return sx.query_rows(sx.Target(ra, dec, pmra, pmdec, epoch))


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


if "ra" not in st.session_state:
    _set(PRESETS[DEFAULT], PRESETS[DEFAULT]["tip"])
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
    "<h1>EVARÍNYA</h1>"
    "<p>Watch the infrared sky change over time, using real SPHEREx images.</p>"
    "<div class='steps'>① pick a target &nbsp;·&nbsp; ② press play &nbsp;·&nbsp; ③ spot what moves</div></div>",
    unsafe_allow_html=True)
st.caption("✦ Try an example")
for col, name in zip(st.columns(len(PRESETS)), PRESETS):
    col.button(name, on_click=pick, args=(name,), use_container_width=True)
if st.session_state.tip:
    st.info(st.session_state.tip)

with st.expander("Or enter your own coordinates"):
    c1, c2, c3 = st.columns(3)
    c1.text_input("Right ascension", key="ra", help="Degrees (269.45) or hours (17h57m48.5s)")
    c2.text_input("Declination", key="dec", help="Degrees (4.69) or d m s (+04d41m36s)")
    c3.slider("How wide an area? (arcminutes)", 1.0, 30.0, key="fov", step=0.5,
              help="Wider areas let you follow faster-moving objects, but load more slowly.")
    d1, d2, d3 = st.columns(3)
    d1.number_input("Motion in RA (mas/yr)", key="pmra", step=10.0, format="%.1f",
                    help="Optional. If you know the object's proper motion, the tool shows where it should be.")
    d2.number_input("Motion in Dec (mas/yr)", key="pmdec", step=10.0, format="%.1f")
    d3.number_input("Position is for year", key="epoch", step=1.0, format="%.1f",
                    help="Catalog positions are usually for the year 2000.")

try:
    coord = sx.parse_coord(st.session_state.ra, st.session_state.dec)
except Exception:
    st.error("I couldn't read those coordinates. Try something like 269.45 and 4.69.")
    st.stop()

ra, dec, fov = float(coord.ra.deg), float(coord.dec.deg), float(st.session_state.fov)
pmra, pmdec, epoch = float(st.session_state.pmra), float(st.session_state.pmdec), float(st.session_state.epoch)
has_pm = bool(pmra or pmdec)
target = sx.Target(ra, dec, pmra, pmdec, epoch)
st.query_params.update(ra=st.session_state.ra, dec=st.session_state.dec, fov=str(fov),
                       pmra=str(pmra), pmdec=str(pmdec), epoch=str(epoch))

# ---------------------------------------------------------------- which images exist
try:
    with st.spinner("Asking the SPHEREx archive which images cover this spot (first time only)…"):
        rows = get_rows(ra, dec, pmra, pmdec, epoch)
except Exception as e:
    st.error(f"Couldn't reach the archive ({type(e).__name__}). Offline? Use a target you "
             "downloaded beforehand with prefetch.py.")
    st.stop()
if not rows:
    st.warning("SPHEREx hasn't imaged this spot in the data released so far. Try another position.")
    st.stop()
counts = {d: sum(r["det"] == d for r in rows) for d in sx.BAND_UM}

# ---------------------------------------------------------------- controls
c1, c2 = st.columns(2)
choice = c1.selectbox(
    "Color of light", [None] + [d for d in sx.BAND_UM if counts[d]],
    format_func=lambda d: "Automatic: clearest view" if d is None
    else f"{sx.BAND_UM[d][0]}–{sx.BAND_UM[d][1]} µm ({counts[d]} images)",
    help="SPHEREx sees six infrared 'colors' (wavelengths in micrometres, µm). Automatic picks the "
         "one where your target stands out best; you can choose another.")
bin_days = c2.slider("Combine images taken within … days", 0, 30, 10,
                     help="Adding images together reduces noise, so faint things show up.")
c3, c4, c5 = st.columns(3)
n_max = c3.slider("Max images per color", 10, 150, 40, help="More images: smoother but slower to download.")
upper = c4.slider("Brightness scale", 90.0, 99.99, 99.5)
invert = c5.checkbox("Dark stars on light", value=False)

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

# ---------------------------------------------------------------- tabs
tab_play, tab_cmp, tab_spec, tab_info = st.tabs(
    ["▶ Watch it change", "Compare two dates", "Colors of light", "About this data"])

crop = sx.common_crop(frames)
cy0, cy1, cx0, cx1 = crop
p_first = np.array(grid.world_to_pixel(target.at_mjd(frames[0].mjd)), float)
p_last = np.array(grid.world_to_pixel(target.at_mjd(frames[-1].mjd)), float)
years = (frames[-1].mjd - frames[0].mjd) / 365.25
shift_as = float(np.hypot(pmra, pmdec)) / 1000 * years
wls = [f.wavelength_um for f in frames]

with tab_play:
    m1, m2 = st.columns([3, 2])
    mode = m1.radio("View", ["▶ Animate", "⇄ Earliest vs latest"], horizontal=True, label_visibility="collapsed")
    zoom = m2.slider("Zoom", 1.0, 4.0, 1.0, 0.5, help="Zoom in on the target.")
    speed = st.slider("Speed", 1, 10, 3) if mode.startswith("▶") else None

    vy0, vy1, vx0, vx1 = view_box(crop, p_first, zoom)
    cube8 = to_uint8(np.stack([f.image[cy0:cy1, cx0:cx1] for f in frames]), upper, invert)   # one shared scale
    view = cube8[:, vy0 - cy0:vy1 - cy0, vx0 - cx0:vx1 - cx0]
    off = np.array([vx0, vy0], float)
    r_px = 15 / scale
    ring = "#f59e0b" if not invert else "#0369a1"

    if mode.startswith("▶"):
        fig = px.imshow(view, animation_frame=0, origin="lower", binary_string=True)
        sl = fig.layout.sliders[0]
        for step, f in zip(sl.steps, frames):
            step.label = f.date
        sl.currentvalue = dict(prefix="Date: ", font=dict(size=14))
        sl.pad = dict(t=10)
        if fig.layout.updatemenus:
            btn = fig.layout.updatemenus[0].buttons[0].args[1]
            btn["frame"]["duration"] = int(1000 / speed)
            btn["transition"] = dict(duration=0)
        marks = [(p_first, "solid")] + ([(p_last, "dot")] if has_pm else [])
    else:
        pick_l = st.radio("Show", [f"Earliest · {frames[0].date}", f"Latest · {frames[-1].date}"], horizontal=True)
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
    st.plotly_chart(fig, use_container_width=True, config=dict(displaylogo=False, scrollZoom=True))

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
