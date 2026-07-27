"""The after-render, per-direction check: every rule, tripped and not tripped.

    python tests/test_directioncheck.py

Same discipline as test_scenecheck: a validator is only worth its button if it can
say no, so each rule is tested once on a sheet that must trip it and once on a sheet
that must not. The "must not" halves are the ones that keep the tool switched on -
this kit's linters earn their keep by being clean on correct art, and a
direction check that cried wolf on a cab car would be turned off within a day.

The last test loads a REAL shipped, in-game-correct sheet (the Civia 465 cab) and
demands total silence. That is the zero-false-positives bar, on art that was not
built to please this checker.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import directioncheck, directions, sheet, spritemetrics   # noqa: E402

FAILED = []

TRANSPARENT = (0, 0, 0, 0)
SOLID = (200, 50, 50, 255)
CODES = ("s", "w", "sw", "se", "n", "e", "ne", "nw")


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def codes(findings):
    return [f.code for f in findings]


def _centred_rect(tile_px, w, h):
    """A w x h rectangle centred in a tile_px cell -> inclusive (x0,y0,x1,y1)."""
    x0 = (tile_px - w) // 2
    y0 = (tile_px - h) // 2
    return (x0, y0, x0 + w - 1, y0 + h - 1)


# The silhouette shape of a CORRECT vehicle, in the measured family pattern:
# broadside (sw/ne) widest, end-on (se/nw) narrowest, cardinals in between, every
# opposite pair equal, all centred. Real 128-px cells and the sizes actually
# measured off the shipped Civia cab, so the thresholds are tested at the scale
# they are calibrated for - a 16-px toy sheet would trip the absolute slack floor.
_TILE = 128
_GOOD = {
    "s": (52, 42), "n": (52, 42),
    "w": (52, 42), "e": (52, 42),
    "sw": (57, 28), "ne": (57, 28),
    "se": (20, 46), "nw": (20, 46),
}


def _build(shape, tile_px=_TILE, overrides=None):
    """A sheet from {code: (w, h)} centred rectangles, cols=4, 8 cells.

    overrides: {code: (x0,y0,x1,y1)} to place a cell by hand (for off-centre tests).
    """
    cols = 4
    rows = 2
    W, H = cols * tile_px, rows * tile_px
    px = [TRANSPARENT] * (W * H)
    placement = sheet.grid_placement(CODES, cols)
    for code, (w, h) in shape.items():
        r, c = placement[code]
        if overrides and code in overrides:
            x0, y0, x1, y1 = overrides[code]
        else:
            x0, y0, x1, y1 = _centred_rect(tile_px, w, h)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[(r * tile_px + y) * W + (c * tile_px + x)] = SOLID
    metrics = spritemetrics.measure(px, W, H, tile_px, CODES, cols)
    return metrics


def test_a_correct_sheet_is_silent_but_for_the_measurement():
    f = directioncheck.check(_build(_GOOD), _TILE)
    errs = [x for x in f if x.level == directioncheck.ERROR]
    warns = [x for x in f if x.level == directioncheck.WARNING]
    check("a correct sheet raises no error", errs == [], str(codes(f)))
    check("and no warning", warns == [], str(codes(f)))
    check("but it does report the silhouettes", "coverage" in codes(f))


def test_an_empty_direction_is_an_error_that_blocks():
    shape = dict(_GOOD)
    del shape["ne"]                       # render dropped one heading
    f = directioncheck.check(_build(shape), _TILE, expected_codes=CODES)
    check("a missing direction is an error", "missing-direction" in codes(f))
    check("and it blocks",
          "missing-direction" in codes(directioncheck.blocking(f)))
    check("a full sheet has none",
          "missing-direction" not in codes(directioncheck.check(_build(_GOOD), _TILE)))


def test_a_model_turned_the_wrong_way_is_caught():
    # swap the families: end-on wide, broadside narrow -> the classic 90-degree error
    bad = dict(_GOOD)
    bad["sw"] = bad["ne"] = (20, 46)
    bad["se"] = bad["nw"] = (57, 28)
    f = directioncheck.check(_build(bad), _TILE)
    check("broadside narrower than end-on is reported", "facing-order" in codes(f))
    check("the correct sheet is not",
          "facing-order" not in codes(directioncheck.check(_build(_GOOD), _TILE)))
    check("it is a warning, not a block",
          "facing-order" not in codes(directioncheck.blocking(
              directioncheck.check(_build(bad), _TILE))))


def test_an_opposite_pair_that_disagrees_in_size_is_caught():
    bad = dict(_GOOD)
    bad["n"] = (30, 42)                   # north came out far narrower than south
    f = directioncheck.check(_build(bad), _TILE)
    check("a mismatched opposite pair is reported", "opposite-mismatch" in codes(f))
    check("a matched one is not",
          "opposite-mismatch" not in codes(directioncheck.check(_build(_GOOD), _TILE)))
    check("a few px rounding difference does NOT trip it",
          "opposite-mismatch" not in codes(directioncheck.check(
              _build(dict(_GOOD, n=(49, 42))), _TILE)))


def test_a_body_built_off_the_origin_is_caught():
    # shove the s-cell blob hard to the right: cx far from the centre (64)
    over = {"s": (95, 60, 118, 100)}      # x 95..118, cx=106.5, off ~42 px
    f = directioncheck.check(_build(_GOOD, overrides=over), _TILE)
    check("an off-centre body is reported", "sprite-off-centre" in codes(f))
    check("its code is distinct from scenecheck's 'off-centre'",
          "off-centre" not in codes(f))
    check("a centred one is not",
          "sprite-off-centre" not in codes(directioncheck.check(_build(_GOOD), _TILE)))
    check("a nose a few px off centre does NOT trip it",
          "sprite-off-centre" not in codes(directioncheck.check(
              _build(_GOOD, overrides={"s": (40, 60, 95, 100)}), _TILE)))


def test_a_near_square_vehicle_does_not_trip_facing_order():
    """A short wagon whose end-on view is a pixel or two wider than its broadside
    one is correct art, not a 90-degree error. The slack spares it; the dramatic
    real swap (tested above) still fires."""
    square = {c: (44, 40) for c in ("s", "w", "n", "e")}
    square["sw"] = square["ne"] = (42, 30)   # broadside barely the wider family
    square["se"] = square["nw"] = (44, 34)   # end-on a touch wider - within slack
    f = directioncheck.check(_build(square), _TILE)
    check("a near-square footprint is not called mis-facing",
          "facing-order" not in codes(f), str(codes(f)))


def test_a_four_direction_sheet_checks_what_it_can():
    """A symmetric vehicle ships 4 images (s,w,sw,se); the opposite checks simply
    have nothing to compare and must stay quiet rather than invent a finding."""
    four = {k: _GOOD[k] for k in ("s", "w", "sw", "se")}
    metrics = _build(four)               # the other four cells are empty
    f = directioncheck.check(metrics, _TILE,
                             expected_codes=("s", "w", "sw", "se"))
    check("no opposite-mismatch when the opposite side was never rendered",
          "opposite-mismatch" not in codes(f), str(codes(f)))
    check("facing-order still works from one broadside and one end-on",
          "facing-order" not in codes(f))
    # and if the four-dir set is asked to include a heading it did not draw:
    f2 = directioncheck.check(metrics, _TILE, expected_codes=CODES)
    check("expecting 8 from a 4-dir sheet flags the 4 that are missing",
          codes(f2).count("missing-direction") == 4)


def test_the_real_civia_cab_sheet_is_clean():
    """Zero false positives on shipped, in-game-correct art. If the render output is
    not present (Blender never ran here), this is a soft skip, NOT a pass - the
    synthetic 'good' sheet above already carries the rule coverage."""
    p = os.path.join(_ROOT, "assets", "civia_465", "sprites", "civia465_cab_a.png")
    if not os.path.exists(p):
        print("  note skipping real-sheet check: %s not rendered" % os.path.basename(p))
        return
    w, h, _a, px = sheet.read_png(p)
    metrics = spritemetrics.measure(px, w, h, 128, CODES, cols=4)
    f = directioncheck.check(metrics, 128, expected_codes=CODES)
    bad = [x for x in f if x.level != directioncheck.INFORMATION]
    check("the real Civia cab sheet raises no error or warning",
          bad == [], "; ".join("%s:%s" % (x.code, x.message) for x in bad))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("DIRECTIONCHECK_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("DIRECTIONCHECK_TESTS_OK")


if __name__ == "__main__":
    main()
