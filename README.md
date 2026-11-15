# Evarínya: Watch the Infrared Sky Change

![Evarínya screenshot](docs/screenshot.png)

Watch the infrared sky change over time, using *real images from NASA's SPHEREx mission*.
Pick a target, press play, and spot what moves.

> Built for the NASA Space Apps Challenge.

## What it does

SPHEREx maps the whole sky in 102 infrared spectral channels. Its nominal 25-month mission plans four
independent all-sky surveys. Evarínya turns those raw exposures into something you can look at and explore:

- *Watch it change*: an animation of selected exposures covering your target, aligned onto one north-up grid.
  Fast movers (like Barnard's Star) visibly drift across the frame.
- *Earliest vs latest*: a quick toggle between the first and last image, for motion that is only about a pixel.
- *Compare two dates*: a difference image where fixed stars cancel out and moving or changing objects stand out
  (red = brighter later, blue = brighter earlier).
- *Colors of light*: a rough infrared spectrum of your target from aperture photometry on selected exposures.
- *Automatic color choice*: SPHEREx sees six wavelength ranges (detectors). Evarínya measures the
  signal-to-noise at your target in each one and picks the clearest. For very bright stars that saturate
  the detector, it picks the color where the least of the star is blanked out, and says so.
- *Proper motion tracking*: enter a target's motion (mas/yr) and the app draws where it should be on each date.
- *Search by name*: use the search at the top of the page to look up a star or object in SIMBAD and fill in its
  coordinates and available proper motion. Example targets are stacked in a collapsible left-sidebar drawer;
  the image viewer appears immediately below the search, followed by five horizontal Explore tabs.
- *Enter coordinates*: the left sidebar has always-visible RA and Dec fields; motion and field-of-view options
  are grouped under advanced settings.
- *Image candidates*: find bright nearby peaks in the selected SPHEREx images and inspect their coordinates.
  These are possible sources, not confirmed objects.
- *Help*: a plain-language guide to the images, colors, motion markers, and data processing.
- *Shareable views*: the page address encodes the target, so you can share a link to exactly what you see.

## Example targets

One-click presets: *Barnard's Star*, *Epsilon Indi B*, *WISE 0855*, *RW Aurigae*, and *R Draconis*.
Search SIMBAD by object name or enter coordinates directly (degrees, or `17h57m48.5s` / `+04d41m36s`).

## How it works

1. Asks IRSA for its current wide-survey collections and which SPHEREx exposures cover the target, querying
   collections separately and preferring the newest copy when exposures overlap.
2. Downloads a small cutout of each selected exposure from IRSA instead of the full multi-megabyte image.
3. Removes zodiacal light, masks flagged pixels, subtracts a smooth background, and reprojects every exposure
   onto one common grid.
4. Crops to the area where all frames have data, applies one shared brightness scale, and optionally median-stacks
   exposures taken within a chosen time window to reduce noise.

Downloads are cached in `utils/cache/`, so repeat runs are fast and work offline.

## Run it

Requires Python 3.10+.

```bash
pip install -r requirements.txt
streamlit run utils/app.py
```

Then open the address Streamlit prints (usually http://localhost:8501). The first run for a new target downloads
data from IRSA and takes a little while.

*Optional: prefetch the demo targets* so the app also works without internet:

```bash
python utils/prefetch.py                      # all presets
python utils/prefetch.py "Barnard's Star"     # one preset
python utils/prefetch.py --per-color 20       # smaller download
```

Use the same `--per-color` value as the app's "Max images per color" slider (default 40).

*Quick data test without the app:*

```bash
python utils/spherex_data.py "17h57m48.5s" "+04d41m36s" 12
```

## Project layout

| File | Purpose |
| --- | --- |
| `utils/app.py` | Streamlit interface |
| `utils/spherex_data.py` | IRSA queries, downloads, cleaning, reprojection, photometry, color selection |
| `utils/presets.py` | The example targets |
| `utils/prefetch.py` | Pre-download data for offline use |
| `requirements.txt` | Python dependencies |

## Limitations

- *Bright stars saturate.* Very bright targets (Barnard's Star, for example) can have their core flagged and
  blanked, so signal-to-noise can't be measured there. The app falls back to the color with the least blanking.
- *Faint targets may not show.* Extremely faint objects like WISE 0855 can be below the detection level in a
  single exposure. Try the reddest colors and combine many images.
- *Slow movers barely move.* Motion of a few arcseconds per year is about one SPHEREx pixel (6.15″) over the
  data released so far. Use Earliest vs latest and zoom in.
- *Automatic color choice is a quick estimate.* It samples a few exposures per color, so on faint targets the
  ranking is noisy. You can always pick a color by hand.
- *Photometry is rough.* The spectrum uses simple aperture photometry with no aperture or color correction.
  It is good for comparing colors, not for absolute brightness.
- *Each frame is at a slightly different wavelength* (SPHEREx uses linear variable filters), so a star can change
  brightness between frames without being variable.

## Data and credits

- Data: [NASA/IPAC Infrared Science Archive (IRSA)](https://irsa.ipac.caltech.edu/), SPHEREx DR1 and QR3
  spectral images (wide survey).
- Mission: [NASA SPHEREx](https://spherex.caltech.edu/).
- Built with Streamlit, Plotly, NumPy, Astropy, Astroquery, PyVO, SciPy, Requests, Pillow, and Reproject.

SPHEREx acknowledgement requested by IRSA:

> “This publication makes use of data products from the Spectro-Photometer for the History of the Universe,
> Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory
> and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.”

## Future work

- Overlay Gaia and WISE catalog sources on the images.
- Cross-match the target with Gaia to confirm known sources and fill in proper motion.
- Add an AI explainer for what the user is seeing.
- Prefetch more targets for offline use.

## Team

- Benekeng a Yombo Micheline Diane
- Nde Tine Tagu Christ Junior

## AI use disclosure

Generative AI (Claude and GitHub Copilot) assisted with writing and debugging the code and documentation. The team chose the design, tested the app against real SPHEREx data, and reviewed the results. No observations were simulated or generated; all images come from the NASA/IPAC IRSA archive.
