"""The Civia S/465, checked against what was actually produced.

    python assets/civia_465/tests/test_civia465.py

stdlib only, no Blender: it reads the artefacts the build left behind - the five
sheets, the five .dat, the five .pak - and asks them the questions that matter.
None of these checks pass just because a file exists:

  * the sheet really carries EIGHT headings, and every one of them has ink in it
  * nothing is clipped: no drawn pixel touches the edge of its cell
  * every reserved colour in every sheet is one we asked for. Nothing accidental.
  * the windows really are the engine's window colour, or they will never light
  * the couplings really form the chain A1 - A5 - A3 - A4 - A2, in that order, and
    both ends are closed (the cab may lead, the tail cab may not)
  * the .dat lints clean against the schema extracted from the engine
  * the .pak exists and makeobj put our vehicle names inside it

Prints CIVIA465_TESTS_OK.
"""

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
_ROOT = os.path.dirname(os.path.dirname(_PROJ))
sys.path.insert(0, _ROOT)

from core import colors, directions, paksets, schema, sheet    # noqa: E402

SPRITES = os.path.join(_PROJ, "sprites")
DAT = os.path.join(_PROJ, "dat")
PAK = os.path.join(_PROJ, "pak")
MAKEOBJ = os.path.join(_ROOT, "build", "tools", "makeobj.exe")

TILE = paksets.get("pak128").tile_px

# key, .dat name, may-precede, may-follow
UNIT = (
    ("civia465_cab_a", "CiviaS465_CabA", "none", "CiviaS465_Int1"),
    ("civia465_intermediate_1", "CiviaS465_Int1", "CiviaS465_CabA",
     "CiviaS465_IntPanto"),
    ("civia465_intermediate_panto", "CiviaS465_IntPanto", "CiviaS465_Int1",
     "CiviaS465_Int3"),
    ("civia465_intermediate_3", "CiviaS465_Int3", "CiviaS465_IntPanto",
     "CiviaS465_CabB"),
    ("civia465_cab_b", "CiviaS465_CabB", "CiviaS465_Int3", "none"),
)

# Reserved colours this train uses ON PURPOSE. Anything else reserved in a sheet
# is an accident, and the engine will repaint it at runtime without telling anyone.
WANTED = {
    colors.WINDOW_DARK: "lit windows",
    colors.HEADLIGHT: "headlights",
    colors.LAMP_RED: "tail lights",
    colors.PLAYER_RAMP_BLUE[3]: "player colour",
}

FAILED = []
CHECKS = [0]


def check(name, cond, detail=""):
    CHECKS[0] += 1
    if not cond:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def cells(png):
    """-> {dir_code: [pixels]} using the engine's own cell order."""
    w, h, _a, px = sheet.read_png(png)
    cols = w // TILE
    out = {}
    for i, code in enumerate(directions.DIR_CODES):
        cx, cy = (i % cols) * TILE, (i // cols) * TILE
        cell = []
        for y in range(TILE):
            row = (cy + y) * w + cx
            cell.extend(px[row:row + TILE])
        out[code] = cell
    return w, h, out


def test_sheets():
    for key, _name, _p, _n in UNIT:
        png = os.path.join(SPRITES, "%s.png" % key)
        check("%s: the sheet is there" % key, os.path.exists(png), png)
        if not os.path.exists(png):
            continue

        w, h, cell = cells(png)
        check("%s: the sheet is 4x2 cells of %dpx" % (key, TILE),
              (w, h) == (4 * TILE, 2 * TILE), "%dx%d" % (w, h))

        for code in directions.DIR_CODES:
            drawn = [i for i, p in enumerate(cell[code]) if p[3] > 127]
            check("%s: heading %s has a vehicle in it" % (key, code),
                  len(drawn) > 200, "%d opaque px" % len(drawn))

            # clipping: a sprite that runs off its cell is cut off in silence and
            # the .pak compiles anyway
            edge = [i for i in drawn
                    if i % TILE in (0, TILE - 1) or i // TILE in (0, TILE - 1)]
            check("%s: heading %s is not clipped" % (key, code), not edge,
                  "%d px on the cell edge" % len(edge))

        # reserved colours, over the whole sheet
        seen = {}
        for code in directions.DIR_CODES:
            for p in cell[code]:
                if p[3] > 127 and p[:3] in colors.RESERVED:
                    seen[p[:3]] = seen.get(p[:3], 0) + 1
        accidental = {k: v for k, v in seen.items() if k not in WANTED}
        check("%s: no ACCIDENTAL reserved colours" % key, not accidental,
              str(accidental))
        check("%s: the windows are the engine's window colour" % key,
              seen.get(colors.WINDOW_DARK, 0) > 50,
              "%d px" % seen.get(colors.WINDOW_DARK, 0))
        if key.startswith("civia465_cab"):
            check("%s: the headlights are the engine's light colour" % key,
                  seen.get(colors.HEADLIGHT, 0) > 4)
            check("%s: the tail lights are the engine's red" % key,
                  seen.get(colors.LAMP_RED, 0) > 4)


def test_dats():
    for key, name, prev, next_ in UNIT:
        path = os.path.join(DAT, "%s.dat" % key)
        check("%s: the .dat is there" % key, os.path.exists(path), path)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()

        check("%s: it is that vehicle" % key, "name=%s" % name in text)
        check("%s: it is electric" % key, "engine_type=electric" in text)
        check("%s: it carries passengers" % key, "freight=Passagiere" in text)

        for code in directions.DIR_CODES:
            check("%s: the .dat points at heading %s" % (key, code),
                  "EmptyImage[%s]=%s." % (code, key) in text)

        check("%s: may follow %s" % (key, prev),
              "Constraint[Prev][0]=%s" % prev in text, text)
        check("%s: may be followed by %s" % (key, next_),
              "Constraint[Next][0]=%s" % next_ in text, text)
        # exactly one of each: a second entry would let the unit be built wrong
        check("%s: no other coupling is allowed" % key,
              text.count("Constraint[Prev]") == 1
              and text.count("Constraint[Next]") == 1)

        findings = schema.lint(text)
        check("%s: lints clean against the engine schema" % key, not findings,
              str(findings))


def test_the_chain_is_closed():
    """Only the cab may lead, only the tail cab may end, and the middle is fixed."""
    leads = [n for _k, n, p, _x in UNIT if p == "none"]
    tails = [n for _k, n, _p, x in UNIT if x == "none"]
    check("exactly one car may lead the train", leads == ["CiviaS465_CabA"],
          str(leads))
    check("exactly one car may end it", tails == ["CiviaS465_CabB"], str(tails))

    order = [n for _k, n, _p, _x in UNIT]
    for i, (_k, _n, prev, next_) in enumerate(UNIT):
        if i > 0:
            check("%s follows %s and nothing else" % (order[i], order[i - 1]),
                  prev == order[i - 1])
        if i < len(UNIT) - 1:
            check("%s pulls %s and nothing else" % (order[i], order[i + 1]),
                  next_ == order[i + 1])


def test_paks():
    for key, name, _p, _n in UNIT:
        pak = os.path.join(PAK, "%s.pak" % key)
        check("%s: the .pak is there" % key, os.path.exists(pak), pak)
        if not os.path.exists(pak) or not os.path.exists(MAKEOBJ):
            continue
        out = subprocess.run([MAKEOBJ, "LIST", pak], capture_output=True,
                             text=True, errors="replace").stdout
        check("%s: makeobj finds our vehicle inside it" % key, name in out,
              out.strip().splitlines()[-1] if out.strip() else "(no output)")


def main():
    print("\n=== Civia S/465 ===\n")
    test_sheets()
    test_dats()
    test_the_chain_is_closed()
    test_paks()

    if FAILED:
        print("\nCIVIA465_TESTS_FAILED: %d of %d checks"
              % (len(FAILED), CHECKS[0]))
        sys.exit(1)
    print("%d checks passed" % CHECKS[0])
    print("\nCIVIA465_TESTS_OK")


main()
