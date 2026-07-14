"""Read Simutrans' reserved-colour tables straight out of the engine source.

    python tools/extract_colors.py [path-to-simutrans]

There are TWO tables and they are not interchangeable:

    descriptor/image.cc     image_t::rgbtab[SPECIAL]   31 entries, 0xRRGGBB
                            what MAKEOBJ matches a pixel against
                            (image_writer.cc: `if (image_t::rgbtab[i] == rgb)`)

    display/simgraph16.cc   display_night_lights[]     15 entries, {R, G, B}
                            what the engine DRAWS after dark

rgbtab is 16 player colours followed by the same 15 lights, in the same order, so
the two line up: rgbtab[16 + i] is the colour to paint for the light that
display_night_lights[i] describes.

They agree on fourteen of those fifteen and disagree on the purple - rgbtab wants
0xFF017F painted, the display table shows 0xE100E1 - and core/colors.py was built
from the wrong one. Hence this: the tables are read, not transcribed.
"""

import os
import re
import sys

SPECIAL = 31          # descriptor/image.h
PLAYERS = 16          # two ramps of eight
LIGHTS = SPECIAL - PLAYERS


def _read(src, *parts):
    with open(os.path.join(src, "src", "simutrans", *parts), encoding="utf-8",
              errors="replace") as f:
        return f.read()


def _body(text, opening):
    """The text between `opening` ... `{` and the matching `};`."""
    start = text.index(opening)
    start = text.index("{", start) + 1
    return text[start:text.index("};", start)]


def rgbtab(src):
    """The 31 colours makeobj compares against, as (r, g, b)."""
    body = _body(_read(src, "descriptor", "image.cc"), "image_t::rgbtab[SPECIAL]")
    out = [(v >> 16 & 0xFF, v >> 8 & 0xFF, v & 0xFF)
           for v in (int(h, 16) for h in re.findall(r"0x([0-9A-Fa-f]{6})\s*,", body))]
    if len(out) != SPECIAL:
        raise ValueError("rgbtab has %d entries, expected %d" % (len(out), SPECIAL))
    return out


def night_lights(src):
    """The 15 colours the engine draws after dark, as (r, g, b)."""
    body = _body(_read(src, "display", "simgraph16.cc"), "display_night_lights[")
    out = [tuple(int(c, 16) for c in triple)
           for triple in re.findall(
               r"\{\s*0x([0-9A-Fa-f]{2})\s*,\s*0x([0-9A-Fa-f]{2})\s*,"
               r"\s*0x([0-9A-Fa-f]{2})\s*\}", body)]
    if len(out) != LIGHTS:
        raise ValueError("display_night_lights has %d entries, expected %d"
                         % (len(out), LIGHTS))
    return out


def extract(src):
    """(player colours, [(paint, night)]) - exactly what core/colors.py declares."""
    table = rgbtab(src)
    return table[:PLAYERS], list(zip(table[PLAYERS:], night_lights(src)))


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the kit
    src = (sys.argv[1] if len(sys.argv) > 1
           else os.environ.get("SIMUTRANS_SRC",
                               os.path.join(os.path.dirname(root), "simutrans")))
    players, lights = extract(src)
    print("player colours (%d):" % len(players))
    for rgb in players:
        print("    #%02X%02X%02X" % rgb)
    print("lights (%d): paint -> shown at night" % len(lights))
    for paint, night in lights:
        mark = "" if paint == night else "   (changes)"
        print("    #%02X%02X%02X -> #%02X%02X%02X%s" % (paint + night + (mark,)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
