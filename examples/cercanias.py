"""A commuter EMU for pak128, made entirely with the kit.

    blender --background --python examples/cercanias.py -- [pakset] [outdir]

Two vehicles, because that is what a commuter train IS:

    BKitCercaniasM   the driving motor car - cab, pantograph, electric
    BKitCercaniasR   the trailer coach - no engine, more seats

and they are coupled by constraints, so the depot will let you build
M - R - M (or M - R - R - M) and nothing silly. That is the whole point of an
EMU: the unit, not the vehicle.

Livery is the Spanish Cercanias one - white body, red doors, dark window band -
with a player-colour stripe along the skirt so the company colour still lands.

Prints CERCANIAS_OK.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                              # noqa: E402
from core import colors, paksets, schema           # noqa: E402

_argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PAKSET = _argv[0] if _argv else "pak128"
OUT = _argv[1] if len(_argv) > 1 else os.path.join(_ROOT, "build", "cercanias")

PAK = paksets.get(PAKSET)
TW = PAK.tile_world
FAILED = []

MOTOR = "BKitCercaniasM"
TRAILER = "BKitCercaniasR"
AUTHOR = "simutrans-blender-kit"

WHITE = (231, 231, 234)
RED = (196, 30, 42)
GLASS = (38, 42, 52)
ROOF = (122, 127, 134)
SKIRT = (58, 62, 68)
METAL = (150, 155, 162)


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def mat(rgb, name):
    return rig.make_special_color_material(bpy, rgb, name=name)


def box(loc, scale, material, rot_y=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.scale = scale
    if rot_y:
        ob.rotation_euler[1] = rot_y
    ob.data.materials.append(material)
    return ob


def coach(cab):
    """One car. Nose along +X. cab=True puts the driver's end at the nose."""
    clear()
    white = mat(WHITE, "white")
    red = mat(RED, "red")
    glass = mat(GLASS, "glass")
    roof = mat(ROOF, "roof")
    skirt = mat(SKIRT, "skirt")
    metal = mat(METAL, "metal")

    # body
    box((0, 0, 0.30 * TW), (0.98 * TW, 0.34 * TW, 0.34 * TW), white)
    # the window band, a hair proud of the body so it reads at 128px
    box((0, 0, 0.38 * TW), (0.80 * TW, 0.355 * TW, 0.10 * TW), glass)
    # roof and skirt
    box((0, 0, 0.475 * TW), (0.94 * TW, 0.30 * TW, 0.05 * TW), roof)
    box((0, 0, 0.10 * TW), (0.90 * TW, 0.30 * TW, 0.12 * TW), skirt)

    # doors: two per side, red, the Cercanias signature
    for sx in (-0.30, 0.24):
        for sy in (-1, 1):
            box((sx * TW, sy * 0.176 * TW, 0.29 * TW),
                (0.10 * TW, 0.02 * TW, 0.28 * TW), red)

    # the player-colour stripe. It has to survive the render byte for byte, or
    # the company colour silently turns into "some blue".
    box((0, 0, 0.175 * TW), (0.99 * TW, 0.355 * TW, 0.035 * TW),
        rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3]))

    if cab:
        # the driver's end: a raked nose and a red windscreen surround
        box((0.47 * TW, 0, 0.36 * TW), (0.16 * TW, 0.33 * TW, 0.30 * TW),
            white, rot_y=-0.22)
        box((0.505 * TW, 0, 0.40 * TW), (0.09 * TW, 0.30 * TW, 0.12 * TW),
            glass, rot_y=-0.22)
        box((0.52 * TW, 0, 0.20 * TW), (0.06 * TW, 0.32 * TW, 0.10 * TW), red)
        # pantograph, folded, over the far end
        box((-0.30 * TW, 0, 0.52 * TW), (0.30 * TW, 0.24 * TW, 0.02 * TW), metal)
        box((-0.30 * TW, 0, 0.55 * TW), (0.05 * TW, 0.26 * TW, 0.02 * TW), metal)
    else:
        # a plain gangway end, so the trailer is visibly not a driving car
        box((0.47 * TW, 0, 0.32 * TW), (0.06 * TW, 0.24 * TW, 0.26 * TW), skirt)


def build(basename, name, cab, **dat):
    coach(cab)
    frames = rig.render_directions(bpy, OUT, PAKSET, dirs=8, basename=basename)
    check("%s rendered eight headings" % name, len(frames) == 8, str(len(frames)))

    _png, dat_path, _pl = rig.build_sheet_and_dat(
        frames, OUT, PAKSET, basename=basename, cols=4,
        name=name, waytype="track", engine_type="electric",
        freight="Passagiere", author=AUTHOR, **dat)

    with open(dat_path, encoding="utf-8") as f:
        text = f.read()
    findings = schema.lint(text)
    for finding in findings:
        print("       %s: %s" % (name, finding))
    check("%s lints clean against the engine schema" % name, not findings,
          "%d finding(s)" % len(findings))
    return text


def main():
    os.makedirs(OUT, exist_ok=True)
    print("\n=== %s: a commuter unit ===\n" % PAKSET)

    print("--- motor car")
    m = build("cercanias_m", MOTOR, cab=True,
              power=1200, speed=120, weight=52, length=16, payload=86,
              cost=1400000, runningcost=180, intro_year=1990,
              constraint_prev=("none", TRAILER),
              constraint_next=("none", TRAILER))

    print("--- trailer")
    r = build("cercanias_r", TRAILER, cab=False,
              power=0, speed=120, weight=40, length=16, payload=118,
              cost=600000, runningcost=90, intro_year=1990,
              constraint_prev=(MOTOR, TRAILER),
              constraint_next=(MOTOR, TRAILER))

    check("the motor car may lead the train",
          "Constraint[Prev][0]=none" in m, m)
    check("the trailer may NOT lead it",
          "Constraint[Prev][0]=%s" % MOTOR in r, r)
    check("the two are coupled to each other",
          TRAILER in m and MOTOR in r)
    check("the trailer has no engine of its own", "power=0" in r, r)
    check("both carry passengers",
          "freight=Passagiere" in m and "freight=Passagiere" in r)

    print("\nout: %s" % OUT)
    if FAILED:
        print("\nCERCANIAS_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nCERCANIAS_OK")


main()
