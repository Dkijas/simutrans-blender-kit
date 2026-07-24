"""What the built Serie 2000A must be, checked against the artefacts on disk.

Modelled on assets/civia_465/tests/test_civia465.py, with two of its bugs fixed
rather than inherited:

  * it hardcodes build/tools/makeobj.exe, bypassing tools/toolchain.find_makeobj()
    which the rest of the harness uses precisely so paths are not Windows literals;
  * and when that path is missing it `continue`s in SILENCE, so its one check that
    the .pak really contains the vehicle passes vacuously on any machine that is
    not the author's. The harness's own rule is that a skip is not a pass. Here a
    missing makeobj FAILS, and says what to do about it.

What this asset needs that the Civia's test does not:

  * the cross-section must come from the spec. Every other test in this repo would
    still pass if Body went back to hardcoded constants - and this train would
    silently become a 7000 again, which is the only reason it exists.
  * the couplings BRANCH. Every other unit here is an indeformable chain of single
    successors; this one has to buy as 2, 4 or 6 cars, and the check that says so
    is that R may be followed by M *and* may end the train.

Prints METRO2000A_TESTS_OK.
"""

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
_ROOT = os.path.dirname(os.path.dirname(_PROJ))
sys.path.insert(0, _ROOT)

from core import colors, directions, schema, sheet     # noqa: E402
from tools import spec as spec_mod, toolchain          # noqa: E402

TILE = 128

SPRITES = os.path.join(_PROJ, "sprites")
DAT = os.path.join(_PROJ, "dat")
PAK = os.path.join(_PROJ, "pak")

CARS = ("s2ka_mot", "s2ka_rem")

# The reserved colours this train uses ON PURPOSE. Anything else reserved in a sheet
# is an accident, and the engine repaints it at runtime without telling anyone.
WANTED = {
    colors.WINDOW_DARK: "lit windows",
    colors.HEADLIGHT: "headlights",
    colors.LAMP_RED: "tail lights and the cab signal cluster",
    colors.PLAYER_RAMP_BLUE[3]: "the player colour stripe",
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


def read_dat(key):
    out = {}
    with open(os.path.join(DAT, "%s.dat" % key), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out.setdefault(k.strip(), []).append(v.strip())
    return out


def main():
    spec = spec_mod.load(os.path.join(_PROJ, "spec.json"))
    print("=== Serie 2000A: the built unit, checked ===")

    # ---- the spec's own arithmetic already held or it would not have loaded. What
    # it cannot see is whether the .dat that shipped carries those numbers.
    for key in CARS:
        d = read_dat(key)
        car = spec.car(key)
        check("%s: the .dat's payload is the spec's seats" % key,
              d["payload"] == [str(car["seats"])],
              "%s vs %s" % (d.get("payload"), car["seats"]))
        check("%s: the .dat's power is the spec's kilowatts" % key,
              d["power"] == [str(car["kilowatts"])],
              "%s vs %s" % (d.get("power"), car["kilowatts"]))
        check("%s: the .dat's weight is the spec's tonnes" % key,
              d["weight"] == [str(car["tonnes"])])
        check("%s: the .dat's speed is the sourced 65 km/h" % key,
              d["speed"] == [str(spec.value("speed"))])
        check("%s: intro_year is the sourced 1985" % key,
              d["intro_year"] == [str(spec.value("intro_year"))])

        # LENGTH 7. The single number that says this is not a 7000, and nothing else
        # in the build would complain if it went back to 8.
        check("%s: length is 7, not pak128's usual 8" % key,
              d["length"] == ["7"], str(d.get("length")))

        # electric on both, including the unpowered trailer: see build.py, this is
        # what keeps the two halves of one train in one depot tab.
        check("%s: engine_type is electric" % key, d["engine_type"] == ["electric"])

    # ---- THE COUPLINGS BRANCH. This is the shape of the train.
    mot, rem = (read_dat(k) for k in CARS)
    M, R = "MadridMetro_S2000A_M", "MadridMetro_S2000A_R"

    check("M may lead a train", mot.get("Constraint[Prev][0]") == ["none"],
          str(mot.get("Constraint[Prev][0]")))
    check("M may also follow an R - this is what makes 4 and 6 cars buildable",
          mot.get("Constraint[Prev][1]") == [R],
          str(mot.get("Constraint[Prev][1]")))
    check("M is followed by R, and only R",
          mot.get("Constraint[Next][0]") == [R]
          and "Constraint[Next][1]" not in mot,
          str(mot.get("Constraint[Next][0]")))
    check("R follows M, and only M",
          rem.get("Constraint[Prev][0]") == [M]
          and "Constraint[Prev][1]" not in rem,
          str(rem.get("Constraint[Prev][0]")))
    check("the train may end after R", rem.get("Constraint[Next][0]") == ["none"],
          str(rem.get("Constraint[Next][0]")))
    check("or carry on with another M - the pair repeats",
          rem.get("Constraint[Next][1]") == [M],
          str(rem.get("Constraint[Next][1]")))

    # ---- the joints. Every car is 7, so every joint is zero: the engine trails
    # each car by the length of the one in FRONT while the art sits centred, and
    # equal lengths are what closes that. This is the check the Civia learned the
    # hard way, with real metres of 22.4/17.75/20.75/14.75 opening a hole behind
    # every long car.
    from core import convoy
    gaps = convoy.joint_gaps([7] * 6)
    check("a six-car train has no gaps between vehicles",
          all(g == 0.0 for g in gaps), str(gaps))

    # ---- the sheets
    for key in CARS:
        png = os.path.join(SPRITES, "%s.png" % key)
        check("%s: the sheet exists" % key, os.path.exists(png), png)
        if not os.path.exists(png):
            continue

        w, h, cell = cells(png)
        check("%s: the sheet is 4x2 cells of %d px" % (key, TILE),
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

        seen = {}
        for code in directions.DIR_CODES:
            for p in cell[code]:
                if p[3] > 127 and p[:3] in colors.RESERVED:
                    seen[p[:3]] = seen.get(p[:3], 0) + 1
        accidental = {k: v for k, v in seen.items() if k not in WANTED}
        check("%s: no ACCIDENTAL reserved colours" % key, not accidental,
              str(accidental))
        check("%s: the windows really are the engine's window colour, or they will "
              "never light" % key, seen.get(colors.WINDOW_DARK, 0) > 30,
              "%d px" % seen.get(colors.WINDOW_DARK, 0))
        # BOTH cars are cab cars here, which no unit in this collection has been
        # before. Both must carry both lamps.
        check("%s: it has headlights (every car of this unit has a cab)" % key,
              seen.get(colors.HEADLIGHT, 0) > 4,
              "%d px" % seen.get(colors.HEADLIGHT, 0))
        check("%s: it has tail lights" % key, seen.get(colors.LAMP_RED, 0) > 4,
              "%d px" % seen.get(colors.LAMP_RED, 0))

    # ---- the .dat lints clean against the schema extracted from the engine
    files = []
    for k in CARS:
        p = os.path.join(DAT, "%s.dat" % k)
        with open(p, encoding="utf-8") as f:
            files.append((p, f.read()))
    findings = schema.lint_files(files)
    check("both .dats lint clean against the schema extracted from the engine",
          not findings, "; ".join(str(f) for f in findings[:3]))

    # ---- and the .pak really has our vehicle inside it.
    #
    # NOT skipped when makeobj is absent. The Civia's version does `continue` here
    # and prints nothing, so on any machine without build/tools/makeobj.exe its
    # headline check silently passes without running. A skip is not a pass.
    makeobj = toolchain.find_makeobj(_ROOT)
    check("makeobj was found, so the .pak can actually be inspected",
          bool(makeobj),
          "set SIMUTRANS_MAKEOBJ, or build it: cmake --build build --target makeobj")
    if makeobj:
        for key, name in zip(CARS, (M, R)):
            pak = os.path.join(PAK, "%s.pak" % key)
            check("%s: the .pak exists" % key, os.path.exists(pak))
            if not os.path.exists(pak):
                continue
            out = subprocess.run([makeobj, "LIST", pak], capture_output=True,
                                 text=True).stdout
            check("%s: makeobj finds %s inside the .pak" % (key, name),
                  name in out, out[:200])

    print("  %d checks" % CHECKS[0])
    if FAILED:
        print("METRO2000A_TESTS_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("METRO2000A_TESTS_OK")


main()
