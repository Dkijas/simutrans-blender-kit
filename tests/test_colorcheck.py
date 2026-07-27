"""Special-colour location + near-miss, tripped and not.

    python tests/test_colorcheck.py

The one rule that judges (near-glow-miss) is tested three ways: it fires on a
window painted a hair off the glow colour, it stays silent on the EXACT glow colour
(that is a working light, not a bug), and - the false positive that would have this
turned off within a day - it stays silent on ordinary grey bodywork that sits near
the non-darkening greys. The last test demands total silence on real shipped art.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import colorcheck, colors, sheet                          # noqa: E402

FAILED = []
TRANSPARENT = (0, 0, 0, 0)


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def codes(findings):
    return [f.code for f in findings]


def _sheet(tile_px, cols, rows, blocks):
    """blocks: {(row,col): (rgb_or_rgba, (x0,y0,x1,y1))} - fill a cell rectangle."""
    w, h = cols * tile_px, rows * tile_px
    px = [TRANSPARENT] * (w * h)
    for (r, c), (colour, (x0, y0, x1, y1)) in blocks.items():
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[(r * tile_px + y) * w + (c * tile_px + x)] = colour
    return px, w, h


def test_a_window_painted_a_hair_off_is_caught():
    near = (colors.WINDOW_DARK[0] + 1, colors.WINDOW_DARK[1], colors.WINDOW_DARK[2])
    px, w, h = _sheet(16, 1, 1, {(0, 0): (near, (4, 4, 8, 8))})
    f = colorcheck.check(px, w, h, 16)
    check("a near-miss to the window glow colour is reported",
          "near-glow-miss" in codes(f))
    check("it is a warning, not a block",
          "near-glow-miss" not in codes(colorcheck.blocking(f)))


def test_the_exact_glow_colour_is_not_a_finding():
    """An exactly-right window IS a working light. Flagging it would punish correct
    art for doing the thing the colour exists to do."""
    px, w, h = _sheet(16, 1, 1, {(0, 0): (colors.WINDOW_DARK, (4, 4, 8, 8))})
    f = colorcheck.check(px, w, h, 16)
    check("the exact glow colour raises no near-miss", "near-glow-miss" not in codes(f))


def test_grey_bodywork_near_a_non_darkening_grey_is_silent():
    """The false positive that matters: a grey vehicle is full of pixels a count or
    two off the non-darkening greys, and none of it is a bug. Near-miss must target
    only the glow surfaces, never the greys."""
    grey_light = colors.LIGHTS[6][0]              # 0x9B9B9B, a non-darkening grey
    near_grey = (grey_light[0] + 1, grey_light[1] - 1, grey_light[2])
    px, w, h = _sheet(16, 1, 1, {(0, 0): (near_grey, (2, 2, 13, 13))})
    f = colorcheck.check(px, w, h, 16)
    check("grey bodywork near a grey light is NOT a near-glow-miss",
          "near-glow-miss" not in codes(f), str(codes(f)))


def test_an_exact_player_colour_is_reported_as_information():
    blue = colors.PLAYER_RAMP_BLUE[3]
    px, w, h = _sheet(16, 1, 1, {(0, 0): (blue, (4, 4, 6, 6))})
    f = colorcheck.check(px, w, h, 16)
    check("an exact player colour is reported", "player-colour" in codes(f))
    check("as INFORMATION, never a warning - a livery is a feature",
          all(x.level == colorcheck.INFORMATION
              for x in f if x.code == "player-colour"))


def test_findings_locate_the_offending_cell():
    near = (colors.WINDOW_DARK[0], colors.WINDOW_DARK[1] + 2, colors.WINDOW_DARK[2])
    px, w, h = _sheet(16, 4, 2, {(1, 2): (near, (4, 4, 8, 8))})   # cell (1,2)
    f = colorcheck.check(px, w, h, 16)
    msg = [x.message for x in f if x.code == "near-glow-miss"]
    check("the finding names the cell it is in", msg and "(1,2)" in msg[0],
          msg[0] if msg else "no finding")


def test_transparent_pixels_are_not_counted():
    # a fully transparent pixel that happens to carry a glow-ish RGB must be ignored
    ghost = (colors.WINDOW_DARK[0] + 1, colors.WINDOW_DARK[1], colors.WINDOW_DARK[2], 0)
    px, w, h = _sheet(16, 1, 1, {(0, 0): (ghost, (4, 4, 8, 8))})
    f = colorcheck.check(px, w, h, 16)
    check("a transparent near-miss is not a finding", "near-glow-miss" not in codes(f))


def test_distance_three_is_out_of_range():
    """Pins the exclusion edge of NEARMISS_MAX_DIST=2. A pixel 3 off the glow colour
    is a different colour, not a slip, and must NOT fire - otherwise widening the
    cutoff would ship green."""
    far = (colors.WINDOW_DARK[0] + 3, colors.WINDOW_DARK[1], colors.WINDOW_DARK[2])
    px, w, h = _sheet(16, 1, 1, {(0, 0): (far, (4, 4, 8, 8))})
    f = colorcheck.check(px, w, h, 16)
    check("a pixel 3 counts off a glow colour is NOT a near-miss",
          "near-glow-miss" not in codes(f), str(codes(f)))


def test_a_correct_windows_antialiased_fringe_is_not_flagged():
    """The zero-false-positive guard, made deterministic (no reliance on a rendered
    asset). A correctly-painted window is a patch of the EXACT glow colour with a
    one-off anti-aliased fringe; a DEAD window is the fringe with no exact core. The
    per-cell suppression must spare the first and still catch the second."""
    tile, cols = 16, 2
    w, h = tile * cols, tile
    px = [TRANSPARENT] * (w * h)
    exact = colors.WINDOW_DARK
    fringe = (exact[0] + 1, exact[1], exact[2])         # one count off -> would-be near-miss
    # cell (0,0): a WORKING window - exact core inside a one-off fringe ring
    for y in range(3, 12):
        for x in range(3, 12):
            px[y * w + x] = fringe
    for y in range(5, 10):
        for x in range(5, 10):
            px[y * w + x] = exact
    # cell (0,1): a DEAD window - the fringe colour only, no exact core
    for y in range(3, 12):
        for x in range(tile + 3, tile + 12):
            px[y * w + x] = fringe
    f = colorcheck.check(px, w, h, tile)
    msgs = [x.message for x in f if x.code == "near-glow-miss"]
    check("exactly one near-glow-miss (the dead window only)", len(msgs) == 1,
          str(len(msgs)))
    check("it names the dead cell (0,1), not the working window's fringe (0,0)",
          msgs and "(0,1)" in msgs[0] and "(0,0)" not in msgs[0],
          msgs[0] if msgs else "no finding")


def test_the_real_civia_cab_sheet_has_no_near_miss():
    """Zero false positives on shipped, in-game-correct art with real windows."""
    p = os.path.join(_ROOT, "assets", "civia_465", "sprites", "civia465_cab_a.png")
    if not os.path.exists(p):
        print("  note skipping real-sheet check: %s not rendered" % os.path.basename(p))
        return
    w, h, _a, px = sheet.read_png(p)
    f = colorcheck.check(px, w, h, 128)
    warns = [x for x in f if x.level == colorcheck.WARNING]
    check("the real Civia cab sheet raises no near-glow-miss warning",
          warns == [], "; ".join(x.message[:80] for x in warns))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("COLORCHECK_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("COLORCHECK_TESTS_OK")


if __name__ == "__main__":
    main()
