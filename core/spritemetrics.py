"""Measure a rendered sprite sheet, one direction at a time - pure, no Pillow, no bpy.

This is the measuring tape; `directioncheck` is what reads it and says whether
something is wrong. Splitting the two keeps every judgement in one place and lets
a test feed a hand-built grid instead of a render.

PURE, LIKE `colors.scan`
    The caller decodes the PNG - `sheet.read_png` returns (w, h, has_alpha, pixels)
    with `pixels` a flat list of RGB/RGBA tuples - and hands the pixels in. Nothing
    here opens a file or imports bpy, so it runs inside Blender's bundled Python and
    is unit-tested from a literal.

WHAT A "CELL" IS
    makeobj addresses a sheet as `file.row.col` on a grid of tile_px x tile_px
    cells (see sheet.py). One direction = one cell. `measure` is told the direction
    codes and the column count - exactly what `sheet.grid_placement` is told - so
    the mapping from code to cell is the same one the .dat was written against, not
    a guess.

WHAT "OPAQUE" MEANS
    A pixel counts as body when its alpha is >= OPAQUE_ALPHA. The threshold is the
    one `sheet.outline_cells` and the scene check already use (48): a soft
    anti-aliased edge is not silhouette, and counting it makes every width a few
    pixels too big in a way that changes between renders.
"""

from typing import NamedTuple

# Same cut-off as sheet.outline_cells / the render clip check. Below this, a pixel
# is edge feathering, not the shape.
OPAQUE_ALPHA = 48


class CellMetrics(NamedTuple):
    """Everything measured about one direction's cell.

    All pixel figures are CELL-LOCAL: (0, 0) is the cell's top-left corner, not the
    sheet's. `present` is False for an empty cell and then every other field is 0 -
    a reader checks `present` first.

    cx/cy are the centroid of the opaque MASS (sum of coordinates / count), not the
    bounding box centre: a nose sticking out one side moves the mass but not the
    box, and left/right balance is exactly what we want to see.
    """
    code: str
    present: bool
    width: int          # opaque bounding-box width, px
    height: int         # opaque bounding-box height, px
    coverage: int       # number of opaque pixels
    cx: float           # centroid x, cell-local px
    cy: float           # centroid y, cell-local px
    left: int           # opaque bbox min x, cell-local px
    right: int          # opaque bbox max x, cell-local px
    top: int            # opaque bbox min y, cell-local px
    bottom: int         # opaque bbox max y, cell-local px


_EMPTY_FIELDS = dict(present=False, width=0, height=0, coverage=0,
                     cx=0.0, cy=0.0, left=0, right=0, top=0, bottom=0)


def _alpha(px):
    return px[3] if len(px) >= 4 else 255


def cell_metrics(pixels, sheet_w, tile_px, row, col, code="",
                 alpha_on=OPAQUE_ALPHA):
    """Measure one cell -> CellMetrics. An empty cell is `present=False`, not None,
    so callers get a uniform record to key off `code`."""
    x0, y0 = col * tile_px, row * tile_px
    minx = miny = 10 ** 9
    maxx = maxy = -1
    sx = sy = 0
    n = 0
    for y in range(y0, y0 + tile_px):
        rowbase = y * sheet_w
        for x in range(x0, x0 + tile_px):
            if _alpha(pixels[rowbase + x]) < alpha_on:
                continue
            lx, ly = x - x0, y - y0
            n += 1
            sx += lx
            sy += ly
            if lx < minx:
                minx = lx
            if lx > maxx:
                maxx = lx
            if ly < miny:
                miny = ly
            if ly > maxy:
                maxy = ly
    if n == 0:
        return CellMetrics(code=code, **_EMPTY_FIELDS)
    return CellMetrics(
        code=code, present=True,
        width=maxx - minx + 1, height=maxy - miny + 1, coverage=n,
        cx=sx / n, cy=sy / n,
        left=minx, right=maxx, top=miny, bottom=maxy)


def measure(pixels, sheet_w, sheet_h, tile_px, codes, cols=None,
            alpha_on=OPAQUE_ALPHA):
    """Every direction's cell -> {code: CellMetrics}, in the given code order.

    `codes` and `cols` are the SAME arguments sheet.grid_placement is given, so the
    code->cell mapping matches the one the .dat uses. Raises if the sheet is not a
    whole number of tile_px cells, because then the addressing is undefined and a
    silent mis-measure is worse than a stop.
    """
    if tile_px <= 0:
        raise ValueError("tile_px must be positive")
    if sheet_w % tile_px or sheet_h % tile_px:
        raise ValueError("sheet %dx%d is not a whole number of %d-px cells"
                         % (sheet_w, sheet_h, tile_px))
    if cols is None:
        # The grid's own width, NOT len(codes): defaulting to the code count puts
        # every cell on one row, so the standard 4-column, 8-direction sheet - the
        # exact layout this module documents - would map code 5 to a column that
        # does not exist and raise below. sheet.grid_placement makes the same
        # choice (cols = the real column count) for the same reason.
        cols = sheet_w // tile_px
    grid_cols = sheet_w // tile_px
    grid_rows = sheet_h // tile_px

    out = {}
    for idx, code in enumerate(codes):
        row, col = divmod(idx, cols)
        if row >= grid_rows or col >= grid_cols:
            raise ValueError("code %r maps to cell (%d,%d) outside a %dx%d grid"
                             % (code, row, col, grid_rows, grid_cols))
        out[code] = cell_metrics(pixels, sheet_w, tile_px, row, col, code,
                                 alpha_on)
    return out
