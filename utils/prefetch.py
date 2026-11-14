"""Download everything the demo needs for the preset targets, so the app also works offline.

    python prefetch.py                         # all presets
    python prefetch.py "Barnard's Star"        # one preset
    python prefetch.py --per-color 20          # fewer images per color (smaller download)

Use the same --per-color as the app slider ("Max images per color", default 40).
"""
import argparse

import spherex_data as sx
from presets import PRESETS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="preset names (default: all)")
    ap.add_argument("--per-color", type=int, default=40)
    args = ap.parse_args()
    for name in args.names or PRESETS:
        p = PRESETS[name]
        c = sx.parse_coord(p["ra"], p["dec"])
        t = sx.Target(c.ra.deg, c.dec.deg, p["pm"][0], p["pm"][1], p["epoch"])
        print(f"\n== {name}")
        rows = sx.query_rows(t)
        print(f"{len(rows)} exposures cover it")
        for d in sx.BAND_UM:
            sel = sx.thin([r for r in rows if r["det"] == d], args.per_color)
            if sel:
                sx.download_rows(t, sel, p["fov"], progress=lambda f, d=d: print(f"\r  color {d}: {f:4.0%}", end=""))
                print()
    print("\nDone. Files are in ./cache")


if __name__ == "__main__":
    main()
