"""Does MAKEOBJ actually recognise the colours we tell the artist to paint?

    python tests/test_colours_makeobj.py

Comparing our table against the engine's source proves only that we transcribed
it correctly this time. It does not prove that a pixel painted with one of those
colours survives compilation as a SPECIAL colour rather than as an ordinary one -
and that is the thing that was broken, silently, for every signal the kit made.

So: paint the colours into a real PNG, run the real makeobj, and read the .pak it
produces. descriptor/writer/image_writer.cc:110 says an opaque pixel whose colour
is in image_t::rgbtab[] is stored as

    pix = 0x8000 + i          i = its index in rgbtab

and anything else goes down the quantising path and comes out at 0x8020 or above.
So the .pak either contains the 16-bit word 0x8000+i for our colour, or the colour
is not special and never will be.

Prints COLOURS_OK.
"""

import os
import struct
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core import colors, paksets, roadsigns, sheet     # noqa: E402
from tools import extract_colors, toolchain            # noqa: E402

OUT = os.path.join(_ROOT, "build", "colours")
SRC = os.environ.get("SIMUTRANS_SRC", os.path.join(os.path.dirname(_ROOT), "simutrans"))
TILE = 128

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def swatch_sheet(path, rgb):
    """One tile, transparent, with a solid block of `rgb` in the middle."""
    px = []
    for y in range(TILE):
        for x in range(TILE):
            inside = TILE // 4 <= x < 3 * TILE // 4 and TILE // 4 <= y < 3 * TILE // 4
            px.append(rgb + (255,) if inside else colors.TRANSPARENT + (0,))
    sheet.write_png(path, TILE, TILE, px, has_alpha=True)


def compile_pak(makeobj, name, rgb):
    """Paint rgb into a one-image sign, compile it, and hand back the .pak bytes."""
    os.makedirs(OUT, exist_ok=True)
    swatch_sheet(os.path.join(OUT, "%s.png" % name), rgb)

    # roadsign_writer wants all four headings. One tile, pointed at four times:
    # this is a colour test, not a geometry test.
    placement = {(d, 0): (0, 0) for d in roadsigns.SIGN_DIRS}
    block = roadsigns.image_block(name, placement)
    ui = roadsigns.ui_block(name, placement)
    dat = roadsigns.roadsign_dat(name, block, ui, waytype="road", is_signal=0)

    with open(os.path.join(OUT, "%s.dat" % name), "w", encoding="utf-8") as f:
        f.write(dat)

    proc = subprocess.run(
        [makeobj, paksets.get("pak128").makeobj_arg, "%s.pak" % name, "%s.dat" % name],
        cwd=OUT, capture_output=True, text=True, errors="replace")
    pak = os.path.join(OUT, "%s.pak" % name)
    if proc.returncode != 0 or not os.path.exists(pak):
        return None, (proc.stdout + proc.stderr).strip()
    with open(pak, "rb") as f:
        return f.read(), ""


def has_word(blob, word):
    """Is this 16-bit value in the file? makeobj writes pixels little-endian."""
    return struct.pack("<H", word) in blob


def main():
    makeobj = toolchain.find_makeobj(_ROOT)
    if not makeobj:
        print("COLOURS_SKIP: no makeobj (set SIMUTRANS_MAKEOBJ)")
        return 2
    if not os.path.isdir(os.path.join(SRC, "src", "simutrans")):
        print("COLOURS_SKIP: no Simutrans source at %s (set SIMUTRANS_SRC)" % SRC)
        return 2

    table = extract_colors.rgbtab(SRC)

    # Every colour we hand the artist, through the real compiler.
    wanted = [("player colour %d" % i, rgb) for i, rgb in enumerate(colors.PLAYER_COLORS)]
    wanted += [(what, paint) for paint, _night, what in colors.LIGHTS]

    for what, rgb in wanted:
        index = table.index(rgb) if rgb in table else None
        if index is None:
            check("%s is a colour makeobj knows" % what, False,
                  "#%02X%02X%02X is not in image.cc rgbtab at all" % rgb)
            continue

        blob, err = compile_pak(makeobj, "sw%02d" % index, rgb)
        if blob is None:
            check("%s compiles" % what, False, err)
            continue

        check("%s (#%02X%02X%02X) survives makeobj as special %d"
              % ((what,) + rgb + (index,)),
              has_word(blob, 0x8000 + index),
              "the .pak has no 0x%04X - the pixel was compiled as an ordinary"
              " colour and will never light up or recolour" % (0x8000 + index))

    # And the counter-example: the colour this kit USED to tell people to paint
    # for a purple signal lamp. It is not in rgbtab, so makeobj cannot see it.
    # If this ever starts passing, the bug is back.
    old_purple = (0xE1, 0x00, 0xE1)
    check("the old purple is NOT a special colour", old_purple not in table,
          "#E100E1 is in rgbtab after all - then the original code was right")

    if colors.LAMP_PURPLE not in table:
        check("LAMP_PURPLE is a colour makeobj knows", False,
              "core/colors.py offers #%02X%02X%02X as the purple signal lamp and"
              " makeobj has never heard of it" % colors.LAMP_PURPLE)
    else:
        blob, err = compile_pak(makeobj, "swold", old_purple)
        if blob is not None:
            check("a sign painted #E100E1 has no purple lamp in it",
                  not has_word(blob, 0x8000 + table.index(colors.LAMP_PURPLE)),
                  "it compiled as the purple light, so the fix was unnecessary")

    if FAILED:
        print("\nCOLOURS_FAILED: %s" % ", ".join(FAILED))
        return 1
    print("\nCOLOURS_OK: %d reserved colours, each one compiled by makeobj and found"
          " in the .pak" % len(wanted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
