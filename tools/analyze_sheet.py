"""Measure and check a rendered sprite sheet from the command line.

    python tools/analyze_sheet.py assets/civia_465/sprites/civia465_cab_a.png
    python tools/analyze_sheet.py --json sprites/*.png

What it is FOR
--------------
A sheet lints clean and compiles even when a direction came out empty, the model
was turned the wrong way, or the body was built off the tile origin. Those are
invisible to makeobj and to the .dat; they are wrong only in the picture. This runs
the same per-direction checks the panel will (core.directioncheck) against a
finished PNG, so the mistake is found at the artist's desk, not in someone's game.

It uses the kit's own stdlib PNG reader (core.sheet), NOT Pillow, so it runs
anywhere the add-on does and has no dependency to install. It takes ANY sheet,
including foreign art the kit did not render - that is what makes it a validator and
not just a post-render self-check.

Directions are auto-detected from the sheet size: an 8-cell sheet (4x2 at tile_px)
is the 8 headings s,w,sw,se / n,e,ne,nw; a 4-cell sheet is the first four. Override
with --dirs and --cols if a sheet is laid out some other way.

Exit code is non-zero if any ERROR-level finding is raised (a missing direction),
so it drops straight into a Makefile or CI step.
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import (colorcheck, directioncheck, directions, paksets, sheet,  # noqa: E402
                  spritemetrics)


def _codes_and_cols(sheet_w, sheet_h, tile_px, dirs_arg, cols_arg):
    """Work out which direction codes the cells hold, and the column count."""
    grid_cols = sheet_w // tile_px
    grid_rows = sheet_h // tile_px
    cells = grid_cols * grid_rows
    if dirs_arg:
        codes = tuple(dirs_arg)
    elif cells >= 8:
        codes = directions.codes_for(8)
    elif cells >= 4:
        codes = directions.codes_for(4)
    else:
        codes = directions.DIR_CODES[:cells]
    cols = cols_arg or grid_cols
    return codes, cols


def analyze_one(path, tile_px, dirs_arg, cols_arg, do_colours=False):
    """-> (findings, metrics, (w, h), codes) for one sheet. Raises on unreadable PNG.

    Refuses a sheet with no alpha channel: the whole measurement is the opaque
    silhouette, and without alpha every pixel reads as opaque, so a full tile is
    'measured' for every direction and the sheet passes for the wrong reason. Better
    to say why than to green-light art we cannot actually see the shape of.

    With do_colours, the special-colour check (colorcheck) is appended: dead windows
    and player-colour placement. Kept opt-in so the default run stays about shape.
    """
    w, h, has_alpha, pixels = sheet.read_png(path)
    if not has_alpha:
        raise ValueError("no alpha channel - silhouettes cannot be measured "
                         "(re-export as RGBA, or with a tRNS transparency chunk)")
    codes, cols = _codes_and_cols(w, h, tile_px, dirs_arg, cols_arg)
    metrics = spritemetrics.measure(pixels, w, h, tile_px, codes, cols)
    findings = list(directioncheck.check(metrics, tile_px, expected_codes=codes))
    if do_colours:
        findings += list(colorcheck.check(pixels, w, h, tile_px))
        # Each module sorts ERROR-first internally; concatenation breaks that, so
        # re-sort the pool (stable, so each module's intra-level order is kept).
        rank = {directioncheck.ERROR: 0, directioncheck.WARNING: 1,
                directioncheck.INFORMATION: 2}
        findings.sort(key=lambda f: rank[f.level])
    return findings, metrics, (w, h), codes


def _finding_dict(f):
    return {"level": f.level, "code": f.code, "message": f.message}


def _metric_dict(m):
    return {"present": m.present, "width": m.width, "height": m.height,
            "coverage": m.coverage, "cx": round(m.cx, 1), "cy": round(m.cy, 1)}


def main(argv=None):
    # allow_abbrev=False: otherwise '--col' is an ambiguous prefix of both --cols
    # and --colours and argparse errors out on a call that used to set cols.
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 allow_abbrev=False)
    ap.add_argument("sheets", nargs="+", help="one or more sprite-sheet PNGs")
    ap.add_argument("--pakset", default="pak128",
                    help="pakset profile for the tile size (default pak128)")
    ap.add_argument("--tile", type=int, default=None,
                    help="tile size in px; overrides --pakset")
    ap.add_argument("--dirs", default=None,
                    help="comma-separated direction codes, in cell order")
    ap.add_argument("--cols", type=int, default=None,
                    help="cells per row; default = sheet width / tile")
    ap.add_argument("--colours", "--colors", action="store_true", dest="colours",
                    help="also run the special-colour check (dead windows, player colour)")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable output")
    args = ap.parse_args(argv)

    tile_px = args.tile if args.tile else paksets.get(args.pakset).tile_px
    dirs_arg = [d.strip() for d in args.dirs.split(",")] if args.dirs else None

    report = []
    worst_error = False
    for path in args.sheets:
        try:
            findings, metrics, size, codes = analyze_one(
                path, tile_px, dirs_arg, args.cols, do_colours=args.colours)
        except Exception as e:      # noqa: BLE001 - any decode failure is per-sheet
            # read_png raises ValueError/OSError for the errors it names, but a
            # truncated or corrupt PNG surfaces as zlib.error, struct.error,
            # KeyError and friends - none of them ValueError. A batch (sprites/*.png
            # in a CI step) must report the bad file and carry on, not abort with a
            # traceback and emit no JSON for the sheets that were fine.
            worst_error = True
            report.append({"sheet": path, "error": str(e)})
            if not args.json:
                print("%s\n  ERROR could not read: %s\n" % (path, e))
            continue

        errs = [f for f in findings if f.level == directioncheck.ERROR]
        if errs:
            worst_error = True

        # A sheet that auto-detects to 4 directions is a valid SYMMETRIC vehicle -
        # but it is indistinguishable, from pixels alone, from an 8-direction one
        # whose other four headings failed to render. We cannot know which without
        # the vehicle's spec, so we say so rather than pass it silently or cry wolf.
        note = None
        if not dirs_arg and len(codes) == 4:
            note = ("detected 4 directions (a symmetric vehicle). An asymmetric or "
                    "road vehicle needs 8 - pass --dirs to assert the full set")

        entry = {
            "sheet": path,
            "size": {"width": size[0], "height": size[1]},
            "findings": [_finding_dict(f) for f in findings],
            "metrics": {c: _metric_dict(m) for c, m in metrics.items()},
        }
        if note:
            entry["note"] = note
        report.append(entry)

        if not args.json:
            print("%s  (%dx%d)" % (path, size[0], size[1]))
            for f in findings:
                print("  %-11s %-18s %s" % (f.level, f.code, f.message))
            if note:
                print("  NOTE        %s" % note)
            if not findings:
                print("  (nothing to report)")
            print()

    if args.json:
        print(json.dumps({"tile_px": tile_px, "sheets": report}, indent=2))

    return 1 if worst_error else 0


if __name__ == "__main__":
    sys.exit(main())
