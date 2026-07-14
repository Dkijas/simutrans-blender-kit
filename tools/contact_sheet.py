"""A contact sheet: the eight headings, magnified and LABELLED, for a human.

    python tools/contact_sheet.py <dir> <basename> [-o out.png] [--scale 3]

The sprite sheet that goes into the .pak is packed for the ENGINE: the cells are
in the engine's order (s w sw se n e ne nw), untouched and unlabelled, and you
cannot tell at a glance which cell is which. That is correct, and it is useless
for reviewing the art. This makes the other thing: every heading blown up on a
flat background with its name written next to it, so a person can see that the
nose points where it should and that nothing is clipped.

It never touches the sheet that ships. stdlib only, like the rest of core.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import directions, sheet          # noqa: E402

BG = (118, 138, 108, 255)       # a grass-ish green: pak art is never seen on white
INK = (255, 255, 255, 255)

# A 3x5 dot font. Five glyphs is all this needs: the heading codes are made of
# n, s, e, w only. Anything fancier would be a dependency.
GLYPHS = {
    "n": ("101", "111", "111", "101", "101"),
    "s": ("111", "100", "111", "001", "111"),
    "e": ("111", "100", "110", "100", "111"),
    "w": ("101", "101", "111", "111", "101"),
}


def _blit(dst, dw, src, sw, sh, x0, y0, scale):
    for y in range(sh):
        for x in range(sw):
            px = src[y * sw + x]
            if px[3] == 0:
                continue
            for sy in range(scale):
                for sx in range(scale):
                    dx, dy = x0 + x * scale + sx, y0 + y * scale + sy
                    dst[dy * dw + dx] = px


def _text(dst, dw, code, x0, y0, size=3):
    x = x0
    for ch in code:
        glyph = GLYPHS[ch]
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit != "1":
                    continue
                for sy in range(size):
                    for sx in range(size):
                        dst[(y0 + gy * size + sy) * dw + x + gx * size + sx] = INK
        x += 4 * size
    return x


def contact_sheet(frame_dir, basename, out_path, scale=3, cols=4):
    """One cell per heading, in the ENGINE's order, each one labelled."""
    codes = [c for c in directions.DIR_CODES
             if os.path.exists(os.path.join(frame_dir, "%s_%s.png"
                                            % (basename, c)))]
    if not codes:
        raise SystemExit("no frames like %s_<dir>.png in %s" % (basename, frame_dir))

    first = sheet.read_png(os.path.join(frame_dir, "%s_%s.png"
                                        % (basename, codes[0])))
    tile = first[0]
    cell = tile * scale
    label = 8 * scale
    rows = (len(codes) + cols - 1) // cols
    w, h = cell * cols, (cell + label) * rows

    px = [BG] * (w * h)
    for i, code in enumerate(codes):
        fw, fh, _a, pixels = sheet.read_png(
            os.path.join(frame_dir, "%s_%s.png" % (basename, code)))
        cx = (i % cols) * cell
        cy = (i // cols) * (cell + label)
        _text(px, w, code, cx + scale, cy + scale, size=scale)
        _blit(px, w, pixels, fw, fh, cx, cy + label, scale)

    sheet.write_png(out_path, w, h, px)
    return out_path, codes


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dir")
    ap.add_argument("basename")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args(argv)

    out = args.out or os.path.join(args.dir, "%s_contact.png" % args.basename)
    path, codes = contact_sheet(args.dir, args.basename, out, scale=args.scale)
    print("%s  (%d headings: %s)" % (path, len(codes), " ".join(codes)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
