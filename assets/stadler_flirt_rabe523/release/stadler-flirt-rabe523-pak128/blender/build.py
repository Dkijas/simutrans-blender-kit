"""Build the Stadler FLIRT RABe 523 (SBB) THROUGH THE ADD-ON, not around it.

    blender --background --factory-startup --python assets/stadler_flirt_rabe523/blender/build.py -- cab_a   # one car (the prototype)
    blender ... -- all               # the whole four-car unit, with couplings

Installs the add-on zip, enables it, fills in the panel's own properties, and presses
its own buttons: build_rig() -> render_sheet() -> compile_pak(). The only thing this
file does itself is MODEL (flirt.py); everything downstream is the add-on's code,
called the way a person would.  Prints FLIRT_OK.
"""

import os
import shutil
import subprocess
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)                       # assets/stadler_flirt_rabe523
_ROOT = os.path.dirname(os.path.dirname(_PROJ))      # the kit

ZIP = os.path.join(_ROOT, "build", "simutrans_blender_kit.zip")
sys.path.insert(0, _ROOT)
from tools import toolchain                   # noqa: E402  (harness, not the add-on)

MAKEOBJ = toolchain.find_makeobj(_ROOT) or ""
ADDONS = os.path.join(_ROOT, "build", "sim-userdir128", "addons", "pak128")

RENDERS = os.path.join(_PROJ, "renders")
SPRITES = os.path.join(_PROJ, "sprites")     # sheet + .dat live together for makeobj
DAT = os.path.join(_PROJ, "dat")
PAK = os.path.join(_PROJ, "pak")
TEXTURES = os.path.join(_PROJ, "textures")
BLEND = os.path.join(_PROJ, "blender")
REPORTS = os.path.join(_PROJ, "reports")

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def install_addon():
    """Build the add-on zip from source, then install THAT one (a stale zip in build/
    is exactly how a fix in the tree fails to reach the sprites)."""
    subprocess.run([sys.executable, os.path.join(_ROOT, "tools", "build_addon_zip.py")],
                   check=True)
    if not os.path.exists(ZIP):
        raise SystemExit("tools/build_addon_zip.py produced no %s" % ZIP)
    bpy.ops.preferences.addon_install(filepath=ZIP, overwrite=True)
    bpy.ops.preferences.addon_enable(module="simutrans_blender_kit")


def couplings(cars):
    """Who may go in front of whom. Each car has exactly ONE possible successor, so
    the depot assembles the whole unit from a single click on the cab car
    (tool/simtool.cc case 'a' walks the chain of single successors)."""
    out = {}
    for i, car in enumerate(cars):
        prev = ("none",) if i == 0 else (cars[i - 1].name,)
        next_ = ("none",) if i == len(cars) - 1 else (cars[i + 1].name,)
        out[car.key] = (prev, next_)
    return out


def build_one(flirt, car, constraints, install=True):
    from simutrans_blender_kit.addon import rig      # the INSTALLED copy

    flirt.build_car(car)

    p = bpy.context.scene.simutrans
    p.pakset = "pak128"
    p.obj_type = "vehicle"
    p.dirs = "8"
    # centred, no nudge: every car is the same length, so centred art butts exactly
    p.align_offset = (0.0, 0.0, 0.0)
    p.basename = car.key
    p.obj_name = car.name
    p.author = flirt.AUTHOR
    p.out_dir = SPRITES

    # --- the numbers (spec.json says which are measured / derived / provisional)
    p.waytype = "track"
    p.engine_type = "electric"
    p.speed = 160                     # measured: SBB FLIRT page
    p.power = car.kilowatts           # 2000 kW over the unit, on the two cab cars
    p.weight = car.tonnes             # ~120 t over the unit
    p.length = car.length             # 8/16 tile, every car
    p.freight = "Passagiere"
    p.payload = car.seats             # ~184 over the unit
    p.intro_year = 2004               # measured: in service since 2004
    p.cost = 600000 if car.cab else 400000          # PROVISIONAL (sum 2,000,000)
    p.runningcost = 60 if car.cab else 40           # PROVISIONAL (sum 200)

    prev, next_ = constraints.get(car.key, ((), ()))
    p.constraint_prev = ", ".join(prev)
    p.constraint_next = ", ".join(next_)

    p.makeobj_path = MAKEOBJ
    p.install_dir = ADDONS if install else ""

    # --- the add-on's own buttons, in panel order
    check("%s: Build Rig" % car.key, bpy.ops.simutrans.build_rig() == {"FINISHED"})
    check("%s: Render Sheet" % car.key,
          bpy.ops.simutrans.render_sheet() == {"FINISHED"})

    sheet_png = os.path.join(SPRITES, "%s.png" % car.key)
    dat_path = os.path.join(SPRITES, "%s.dat" % car.key)
    check("%s: the sheet exists" % car.key, os.path.exists(sheet_png))
    check("%s: the .dat exists" % car.key, os.path.exists(dat_path))

    # --- flat contour inked before makeobj sees the sheet, so the colour report below
    # validates the sheet the .pak will carry
    inked = flirt.apply_outline(sheet_png)
    check("%s: the flat contour was inked" % car.key,
          inked == flirt.OUTLINE, str(inked))

    # --- the reserved-colour report
    wanted, accidental = rig.reserved_colour_report(bpy, sheet_png)
    print("       intentional reserved colours: %s"
          % {("#%02X%02X%02X" % k): v for k, v in wanted.items()})
    check("%s: no ACCIDENTAL reserved colours" % car.key, not accidental,
          str(accidental))
    check("%s: the windows really are the engine's window colour" % car.key,
          wanted.get(flirt.LIT_PANE, 0) > 30,
          "%d px" % wanted.get(flirt.LIT_PANE, 0))
    if car.cab:
        check("%s: the headlights are the engine's light colour" % car.key,
              wanted.get(flirt.HEADLIGHT, 0) > 4,
              "%d px" % wanted.get(flirt.HEADLIGHT, 0))
        check("%s: the tail lights are the engine's red" % car.key,
              wanted.get(flirt.TAILLIGHT, 0) > 4,
              "%d px" % wanted.get(flirt.TAILLIGHT, 0))

    # --- makeobj, through the panel's button
    check("%s: Compile .pak" % car.key,
          bpy.ops.simutrans.compile_pak() == {"FINISHED"})
    pak = os.path.join(SPRITES, "%s.pak" % car.key)
    check("%s: the .pak exists" % car.key, os.path.exists(pak))

    # --- keep the deliverables where the brief wants them
    shutil.copy(dat_path, os.path.join(DAT, "%s.dat" % car.key))
    if os.path.exists(pak):
        shutil.copy(pak, os.path.join(PAK, "%s.pak" % car.key))
    for img in bpy.data.images:
        if img.name.startswith("flirt_%s" % car.key):
            img.filepath_raw = os.path.join(TEXTURES, "%s.png" % img.name)
            img.file_format = "PNG"
            img.save()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "%s.blend" % car.key))

    return wanted


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    which = argv[0] if argv else "cab_a"

    for d in (RENDERS, SPRITES, DAT, PAK, TEXTURES, BLEND, REPORTS):
        os.makedirs(d, exist_ok=True)

    install_addon()
    sys.path.insert(0, _HERE)
    import flirt                                 # noqa: E402  (after the install)

    if which == "all":
        cars = list(flirt.UNIT)
        cons = couplings(cars)
    else:
        # the PROTOTYPE runs without couplings: a Constraint pointing at a car that
        # does not exist yet is a dangling reference the pakset fails to resolve
        cars = [c for c in flirt.UNIT if c.key == which]
        if not cars:
            raise SystemExit("unknown car: %s" % which)
        cons = {}

    print("\n=== Stadler FLIRT RABe 523 (SBB) for pak128: %s ===\n"
          % ", ".join(c.key for c in cars))
    for car in cars:
        print("--- %s (%s, %.1f m -> length %d)"
              % (car.key, car.name, car.metres, car.length))
        build_one(flirt, car, cons)

    print("\nout: %s" % _PROJ)
    if FAILED:
        print("\nFLIRT_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nFLIRT_OK")


main()
