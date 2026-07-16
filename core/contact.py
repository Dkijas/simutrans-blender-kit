"""The eight headings on one page, labelled.

A contact sheet is an EXTRA artefact made FROM the finished frames. It does not
touch them and it is not the sprite sheet: `sheet.assemble` writes the real one
that the .dat points at, and this writes a second image, elsewhere, that an artist
looks at and then throws away.

That distinction is the whole design. The frames come from the real render (see
addon/workflow.py: prepare_directions + render_one_step, which is what
render_directions itself is made of), so what you are looking at IS what the game
will get. If this module drew the frames, or scaled them, or re-lit them, the
preview would be a picture of a preview.

THE LABELS
    Four glyphs - n, s, e, w - are all eight direction codes need, so the font
    below is four 3x5 bitmaps rather than a dependency. It is drawn into the
    CONTACT SHEET only, never into a frame.

WHY THE ORDER IS NOT OURS TO CHOOSE
    directions.DIR_CODES is `s w sw se n e ne nw`, which is not compass order and
    looks like a mistake. It is the order the engine reads images in
    (vehicle_writer.cc:179), and the real sheet is laid out in it. A contact sheet
    in "sensible" compass order would show the artist a different arrangement from
    the one their .dat describes - so it uses the same grid_placement the real
    sheet does, and labels it instead of reordering it.
"""

from . import directions, sheet

# 3x5, one bit per pixel, top row first. Only four letters exist in the eight
# direction codes, which is why this is a dict and not a font file.
_GLYPHS = {
    "n": ("101", "111", "101", "101", "101"),
    "s": ("111", "100", "111", "001", "111"),
    "e": ("111", "100", "110", "100", "111"),
    "w": ("101", "101", "101", "111", "101"),
}

GLYPH_W, GLYPH_H = 3, 5
LABEL_PAD = 1

# White on black, both drawn: a label in one colour vanishes on art of that
# colour, and the sprite behind it is exactly the thing being judged.
LABEL_FG = (255, 255, 255)
LABEL_BG = (0, 0, 0)


def label_size(code, scale=2):
    w = (GLYPH_W * len(code) + (len(code) - 1)) * scale + 2 * LABEL_PAD
    h = GLYPH_H * scale + 2 * LABEL_PAD
    return w, h


def draw_label(px, width, x0, y0, code, scale=2):
    """Stamp `code` into a flat RGBA pixel list. Mutates px; returns nothing.

    px is sheet.read_png's shape: a flat list of (r,g,b,a) tuples.
    """
    w, h = label_size(code, scale)
    for y in range(y0, min(y0 + h, len(px) // width)):
        for x in range(x0, min(x0 + w, width)):
            px[y * width + x] = LABEL_BG + (255,)

    cx = x0 + LABEL_PAD
    for ch in code:
        rows = _GLYPHS.get(ch)
        if rows is None:
            continue
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit != "1":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        x = cx + rx * scale + sx
                        y = y0 + LABEL_PAD + ry * scale + sy
                        if 0 <= x < width and 0 <= y * width + x < len(px):
                            px[y * width + x] = LABEL_FG + (255,)
        cx += (GLYPH_W + 1) * scale


def placement(codes=None, cols=4):
    """Which cell each heading lands in -> {code: (row, col)}.

    sheet.grid_placement is the real sheet's own layout function. Using it means
    the contact sheet cannot disagree with the .dat about where a heading is.
    """
    return sheet.grid_placement(list(codes or directions.DIR_CODES), cols=cols)


def missing(frames, dirs=8):
    """Headings the render did not produce -> (code, ...).

    A frame that failed leaves a gap, and a contact sheet with a hole in it is the
    only place anyone would notice before the .dat points at nothing.
    """
    have = {code for code, _png in frames}
    return tuple(c for c in directions.codes_for(dirs) if c not in have)


def build(frames, tile_px, out_path, cols=4, scale=2):
    """Assemble the frames into a labelled contact sheet -> (path, placement).

    `frames`: [(code, png_path)] from the REAL render. They are read, never
    written: the sheet the .dat points at is somebody else's business.
    """
    codes = [c for c, _p in frames]
    place = sheet.assemble(frames, tile_px, cols=cols, out_path=out_path)

    width, height, alpha, px = sheet.read_png(out_path)
    if not alpha:
        px = [(r, g, b, 255) for (r, g, b) in px]
    px = list(px)

    for code in codes:
        row, col = place[code]
        draw_label(px, width, col * tile_px + 1, row * tile_px + 1, code, scale)

    sheet.write_png(out_path, width, height, px, has_alpha=True)
    return out_path, place


def report(frames, place, dirs=8):
    """What the sheet shows, in words -> (str, ...). For the panel."""
    out = []
    gaps = missing(frames, dirs)
    if gaps:
        out.append("MISSING: no frame for %s - the .dat would point at nothing"
                   % ", ".join(gaps))
    rows = max((r for r, _c in place.values()), default=0) + 1
    cols = max((c for _r, c in place.values()), default=0) + 1
    out.append("%d heading(s) in a %dx%d grid, in the engine's own order: %s"
               % (len(frames), cols, rows,
                  " ".join(c for c, _p in frames)))
    return tuple(out)
