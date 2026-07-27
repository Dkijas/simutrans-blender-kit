"""The sprite measuring tape, without Blender or Pillow.

    python tests/test_spritemetrics.py

spritemetrics is pure arithmetic over a flat pixel list, so every case here builds
a sheet from a literal and reads the numbers back - no render, no file. If the
measuring tape is wrong, every rule that reads it is wrong for a reason nobody will
find, so it is tested on its own first.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import spritemetrics                                    # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


TRANSPARENT = (0, 0, 0, 0)
SOLID = (200, 50, 50, 255)


def make_sheet(tile_px, cols, rows, rects):
    """A flat RGBA pixel list with an opaque rectangle in some cells.

    rects: {(row, col): (x0, y0, x1, y1)} in CELL-LOCAL pixels, inclusive corners.
    Everything else is transparent.
    """
    w, h = cols * tile_px, rows * tile_px
    px = [TRANSPARENT] * (w * h)
    for (r, c), (x0, y0, x1, y1) in rects.items():
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[(r * tile_px + y) * w + (c * tile_px + x)] = SOLID
    return px, w, h


def test_an_empty_cell_is_present_false_not_none():
    px, w, h = make_sheet(16, 1, 1, {})
    m = spritemetrics.cell_metrics(px, w, 16, 0, 0, "s")
    check("an empty cell reports present=False", m.present is False)
    check("and its code is preserved for the caller", m.code == "s")
    check("every measured field is zero", m.width == 0 and m.coverage == 0)


def test_a_known_rectangle_measures_exactly():
    # a 6-wide, 4-tall block from (3,5) to (8,8) inside a 16px cell
    px, w, h = make_sheet(16, 1, 1, {(0, 0): (3, 5, 8, 8)})
    m = spritemetrics.cell_metrics(px, w, 16, 0, 0, "s")
    check("present", m.present)
    check("width is inclusive: 8-3+1 = 6", m.width == 6, str(m.width))
    check("height is inclusive: 8-5+1 = 4", m.height == 4, str(m.height))
    check("coverage is the pixel count 6*4 = 24", m.coverage == 24, str(m.coverage))
    check("bbox edges are cell-local", (m.left, m.right, m.top, m.bottom) == (3, 8, 5, 8))
    check("centroid of a filled rect is its centre",
          abs(m.cx - 5.5) < 1e-9 and abs(m.cy - 6.5) < 1e-9,
          "%s,%s" % (m.cx, m.cy))


def test_the_centroid_follows_the_mass_not_the_box():
    """An L - a tall column plus a foot reaching right - so the mass leans LEFT of
    the bounding-box centre. A box-centre implementation of cx would report 5.5;
    the mass centroid reports 4.0. This is the property the CellMetrics docstring
    advertises, so a test has to actually distinguish the two."""
    px, w, h = make_sheet(16, 1, 1, {})
    # column x 2..3, y 2..9  (16 px)  +  foot x 2..9, y 10..11 (16 px)
    for y in range(2, 10):
        for x in (2, 3):
            px[y * w + x] = SOLID
    for y in (10, 11):
        for x in range(2, 10):
            px[y * w + x] = SOLID
    m = spritemetrics.cell_metrics(px, w, 16, 0, 0)
    box_centre_x = (m.left + m.right) / 2.0
    check("the bounding box spans x 2..9, centre 5.5", abs(box_centre_x - 5.5) < 1e-9,
          str(box_centre_x))
    check("the mass centroid leans left of it (cx=4.0, not 5.5)",
          abs(m.cx - 4.0) < 1e-9, str(m.cx))


def test_the_opaque_threshold_is_exactly_alpha_48():
    """Everything measured hangs on OPAQUE_ALPHA. A pixel at alpha 48 is body; one
    at 47 is edge feathering. If nothing pins this, a '<' vs '<=' slip goes green."""
    w = h = 16
    px = [TRANSPARENT] * (w * h)
    px[5 * w + 5] = (10, 10, 10, 48)      # exactly the threshold -> counts
    px[5 * w + 6] = (10, 10, 10, 47)      # one below -> does not
    m = spritemetrics.cell_metrics(px, w, 16, 0, 0)
    check("alpha 48 counts as opaque", m.present and m.coverage == 1, str(m.coverage))
    check("alpha 47 is below the threshold and is ignored",
          m.left == 5 and m.right == 5)


def test_bare_rgb_pixels_are_opaque():
    """sheet.read_png hands back 3-tuples for an alpha-less PNG. At the pixel level
    that is body, not transparency (there is nothing transparent about it), so the
    3-tuple branch of _alpha must read as opaque. (The CLI refuses a WHOLE alpha-less
    sheet separately - that is a different decision, made where the context is.)"""
    w = h = 16
    px = [TRANSPARENT] * (w * h)
    for y in range(4, 7):
        for x in range(4, 7):
            px[y * w + x] = (120, 30, 30)     # a bare RGB 3-tuple, no alpha
    m = spritemetrics.cell_metrics(px, w, 16, 0, 0)
    check("a 3-tuple RGB pixel is treated as opaque",
          m.present and m.coverage == 9, str(m.coverage))


def test_cell_local_coordinates_are_offset_by_the_cell_origin():
    # same rectangle, but in cell (1, 2): the numbers must be identical
    px, w, h = make_sheet(16, 4, 2, {(1, 2): (3, 5, 8, 8)})
    m = spritemetrics.cell_metrics(px, w, 16, 1, 2, "ne")
    check("a rect in a far cell measures the same as in cell 0",
          m.width == 6 and m.height == 4 and m.left == 3 and m.top == 5,
          "%s" % (m,))


def test_measure_maps_codes_to_the_same_cells_the_dat_uses():
    codes = ("s", "w", "sw", "se", "n", "e", "ne", "nw")
    # put a unique-width block in two known cells: se is cell (0,3), ne is (1,2)
    px, w, h = make_sheet(16, 4, 2, {(0, 3): (6, 6, 8, 12),     # se: 3 wide
                                     (1, 2): (2, 6, 13, 9)})     # ne: 12 wide
    got = spritemetrics.measure(px, w, h, 16, codes, cols=4)
    check("every code has a record", set(got) == set(codes))
    check("se lands in cell (0,3): width 3", got["se"].width == 3, str(got["se"].width))
    check("ne lands in cell (1,2): width 12", got["ne"].width == 12, str(got["ne"].width))
    check("an untouched cell is present=False", got["s"].present is False)


def test_measure_refuses_a_sheet_that_is_not_whole_cells():
    px, w, h = make_sheet(16, 2, 1, {})
    try:
        spritemetrics.measure(px, w + 3, h, 16, ("s", "w"), cols=2)
        check("a ragged sheet raises", False, "no error")
    except ValueError:
        check("a ragged sheet raises rather than mis-measures", True)


def test_measure_refuses_a_code_that_falls_off_the_grid():
    px, w, h = make_sheet(16, 2, 1, {})   # a 2x1 grid = 2 cells
    try:
        spritemetrics.measure(px, w, h, 16, ("s", "w", "sw"), cols=2)
        check("a code past the last cell raises", False, "no error")
    except ValueError:
        check("a code with no cell raises rather than guessing", True)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("SPRITEMETRICS_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("SPRITEMETRICS_TESTS_OK")


if __name__ == "__main__":
    main()
