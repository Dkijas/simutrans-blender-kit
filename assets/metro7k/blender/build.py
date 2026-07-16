"""Build the Metro de Madrid Serie 7000 THROUGH THE ADD-ON, not around it.

    blender --background --factory-startup --python assets/metro7k/blender/build.py \
            -- cab_a                 # one car (the prototype)
    blender ... -- all               # the whole six-car unit, with couplings

This script installs the add-on zip, enables it, fills in the panel's own
properties, and presses the panel's own buttons:

    bpy.ops.simutrans.build_rig()      camera + sun, pak128 profile
    bpy.ops.simutrans.render_sheet()   8 headings, sheet, .dat, and its own lint
    bpy.ops.simutrans.compile_pak()    makeobj, and the copy into the addons dir

The only thing this file does itself is MODEL, which is the artist's job and not
the add-on's. Everything downstream of the geometry is the add-on's code, called
the way a person would call it.

Prints METRO7K_OK.
"""

import os
import shutil
import subprocess
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)                       # assets/metro7k
_ROOT = os.path.dirname(os.path.dirname(_PROJ))      # the kit

ZIP = os.path.join(_ROOT, "build", "simutrans_blender_kit.zip")
sys.path.insert(0, _ROOT)
from tools import toolchain                   # noqa: E402  (harness, not the add-on)

MAKEOBJ = toolchain.find_makeobj(_ROOT) or ""
ADDONS = os.path.join(_ROOT, "build", "sim-userdir128", "addons", "pak128")

RENDERS = os.path.join(_PROJ, "renders")
SPRITES = os.path.join(_PROJ, "sprites")     # sheet + .dat live together: makeobj
DAT = os.path.join(_PROJ, "dat")             # resolves image refs beside the .dat
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
    """Build the add-on zip from source, then install THAT one.

    It used to install whatever zip happened to be lying in build/. So a fix could
    be made in addon/, the test suite could go green against it, and the sprites
    would still come out of an add-on built days earlier - which is exactly what
    happened: the fix that stops Blender writing the author's home directory into
    every PNG was in the tree, and the sprites kept leaking it. The zip is derived.
    Derive it.
    """
    subprocess.run([sys.executable, os.path.join(_ROOT, "tools", "build_addon_zip.py")],
                   check=True)
    if not os.path.exists(ZIP):
        raise SystemExit("tools/build_addon_zip.py produced no %s" % ZIP)
    bpy.ops.preferences.addon_install(filepath=ZIP, overwrite=True)
    bpy.ops.preferences.addon_enable(module="simutrans_blender_kit")


_SPEC = None


def load_spec():
    """The brief, validated. Every number in it can be defended or is named a guess."""
    global _SPEC
    if _SPEC is None:
        sys.path.insert(0, _ROOT)
        from tools import spec        # ours, not the artist's - see tools/spec.py
        _SPEC = spec.load(os.path.join(_PROJ, "spec.json"))
        guesses = ", ".join(f.key for f in _SPEC.provisional())
        print("  spec: %s - %d facts, and the guesses are: %s"
              % (_SPEC.name, len(_SPEC.facts), guesses or "none"))
    return _SPEC


def couplings(cars):
    """Who may go in front of whom. Only where the real unit demands it.

    CabA - R1 - M1 - M2 - R2 - CabB, and nothing else. Because each car has
    exactly ONE possible successor, the depot will assemble the whole six-car unit
    from a single click on the cab car: tool/simtool.cc case 'a' walks the chain of
    single successors and appends them all. That is not a trick, it is how the
    paksets' own fixed units work.
    """
    out = {}
    for i, car in enumerate(cars):
        prev = ("none",) if i == 0 else (cars[i - 1].name,)
        next_ = ("none",) if i == len(cars) - 1 else (cars[i + 1].name,)
        out[car.key] = (prev, next_)
    return out


def build_one(metro7k, car, constraints, install=True):
    from simutrans_blender_kit.addon import rig      # the INSTALLED copy

    body = metro7k.build_car(car)

    p = bpy.context.scene.simutrans
    p.pakset = "pak128"
    p.obj_type = "vehicle"
    p.dirs = "8"

    # Centred, and no nudge. Every car is the same length (pak128's own convention,
    # see PAK128_VEHICLE_LENGTH), and centred art of equal length butts exactly.
    # It is MIXED lengths that open the joints, because the engine trails each car
    # behind the one in front by the length OF THE ONE IN FRONT while the art sits
    # in the middle of its cell. Aiming the camera half a body forward would fix
    # the joints too - and push the sprite off the edge of its cell, which the
    # kit's own clipping warning says out loud.
    p.align_offset = (0.0, 0.0, 0.0)
    p.basename = car.key
    p.obj_name = car.name
    p.author = metro7k.AUTHOR
    p.out_dir = SPRITES

    # --- WHERE THE NUMBERS COME FROM, HONESTLY.
    #
    # The unit-level figures below come from spec.load(), which has already refused
    # anything without a source: that is why the table captioned "valor recomendado",
    # whose capacity (1260) and per-car length (17.83 m, which is just 107/6) were
    # wrong, could not reach the .dat through them.
    #
    # The PER-CAR splits (power, weight, payload) do NOT come through the spec yet -
    # they are literals in metro7k.py that spec.py never sees. That gap is real and
    # it has already cost us: the 9000 shipped a payload split summing to 186 against
    # a measured 178 and nothing caught it. build_all() now sums the split and checks
    # it against the spec, which is the guard that would have caught it; routing the
    # splits through spec.json per car is the proper fix and is still to do.
    spec = load_spec()
    p.waytype = "track"
    p.engine_type = "electric"
    p.speed = spec.value("speed")                  # measured
    p.power = car.kilowatts                        # per-car split, NOT spec-gated
    p.weight = car.tonnes                          # per-car split, NOT spec-gated
    p.length = car.length
    p.freight = "Passagiere"
    p.payload = car.seats                          # the SEATED figure only: 178 of 1260
    p.intro_year = spec.value("intro_year")        # measured
    p.cost = spec.value("cost") if car.cab else spec.value("cost") // 2   # PROVISIONAL
    p.runningcost = (spec.value("runningcost") if car.cab
                     else spec.value("runningcost") // 2)                 # PROVISIONAL

    prev, next_ = constraints.get(car.key, ((), ()))
    p.constraint_prev = ", ".join(prev)
    p.constraint_next = ", ".join(next_)

    p.makeobj_path = MAKEOBJ
    p.install_dir = ADDONS if install else ""

    # --- the add-on's own buttons, in the order the panel offers them
    check("%s: Build Rig" % car.key,
          bpy.ops.simutrans.build_rig() == {"FINISHED"})
    check("%s: Render Sheet" % car.key,
          bpy.ops.simutrans.render_sheet() == {"FINISHED"})

    sheet_png = os.path.join(SPRITES, "%s.png" % car.key)
    dat_path = os.path.join(SPRITES, "%s.dat" % car.key)
    check("%s: the sheet exists" % car.key, os.path.exists(sheet_png))
    check("%s: the .dat exists" % car.key, os.path.exists(dat_path))

    # --- the reserved-colour report, split the way the brief asks
    wanted, accidental = rig.reserved_colour_report(bpy, sheet_png)
    print("       intentional reserved colours: %s"
          % {("#%02X%02X%02X" % k): v for k, v in wanted.items()})
    check("%s: no ACCIDENTAL reserved colours" % car.key, not accidental,
          str(accidental))
    check("%s: the windows really are the engine's window colour" % car.key,
          wanted.get(metro7k.LIT_PANE, 0) > 30,
          "%d px" % wanted.get(metro7k.LIT_PANE, 0))
    if car.cab:
        check("%s: the headlights are the engine's light colour" % car.key,
              wanted.get(metro7k.HEADLIGHT, 0) > 4,
              "%d px" % wanted.get(metro7k.HEADLIGHT, 0))
        check("%s: the tail lights are the engine's red" % car.key,
              wanted.get(metro7k.TAILLIGHT, 0) > 4,
              "%d px" % wanted.get(metro7k.TAILLIGHT, 0))

    # --- makeobj, through the panel's button
    check("%s: Compile .pak" % car.key,
          bpy.ops.simutrans.compile_pak() == {"FINISHED"})
    pak = os.path.join(SPRITES, "%s.pak" % car.key)
    check("%s: the .pak exists" % car.key, os.path.exists(pak))

    # --- keep the deliverables where the brief wants them
    shutil.copy(dat_path, os.path.join(DAT, "%s.dat" % car.key))
    if os.path.exists(pak):
        shutil.copy(pak, os.path.join(PAK, "%s.pak" % car.key))
    # Save the painted flank and its light mask. The match MUST mirror the names
    # livery_texture() gives them (metro7k.py names them car.key and car.key+"_mask").
    # Keep this in step with that file, or textures/ silently stays empty.
    for img in bpy.data.images:
        if img.name.startswith(car.key):
            img.filepath_raw = os.path.join(TEXTURES, "%s.png" % img.name)
            img.file_format = "PNG"
            img.save()
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.join(BLEND, "%s.blend" % car.key))

    return body, wanted


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    which = argv[0] if argv else "cab_a"

    for d in (RENDERS, SPRITES, DAT, PAK, TEXTURES, BLEND, REPORTS):
        os.makedirs(d, exist_ok=True)

    install_addon()
    sys.path.insert(0, _HERE)
    import metro7k                              # noqa: E402  (after the install)

    if which == "all":
        cars = list(metro7k.UNIT)
        cons = couplings(cars)
    else:
        # The PROTOTYPE runs without couplings on purpose: a Constraint pointing at
        # a car that does not exist yet is a dangling reference, and the pakset
        # would fail to resolve it at load.
        cars = [c for c in metro7k.UNIT if c.key.endswith(which)]
        if not cars:
            raise SystemExit("unknown car: %s" % which)
        cons = {}

    print("\n=== Metro de Madrid Serie 7000 for pak128: %s ===\n"
          % ", ".join(c.key for c in cars))
    for car in cars:
        print("--- %s (%s, %.2f m -> length %d)"
              % (car.key, car.name, car.metres, car.length))
        build_one(metro7k, car, cons)

    if which == "all":
        # The per-car splits are literals in metro7k.py that spec.py never sees, so
        # this is where they meet the sourced totals. The 9000 once shipped a payload
        # summing to 186 against a measured 178 and nothing noticed, because nothing
        # added them up. Now something does, on both units.
        spec = load_spec()
        seated = spec.value("payload_seated")
        got = sum(c.seats for c in metro7k.UNIT)
        check("the payload split sums to the declared seated figure", got == seated,
              "spec says %d, the six cars carry %d" % (seated, got))

        watts = spec.value("power_total_kw")
        got_kw = sum(c.kilowatts for c in metro7k.UNIT)
        check("the power split sums to the derived total", got_kw == watts,
              "spec says %d kW, the six cars carry %d kW" % (watts, got_kw))

        tonnes = spec.value("weight_total_t")
        got_t = sum(c.tonnes for c in metro7k.UNIT)
        check("the weight split sums to the declared total", got_t == tonnes,
              "spec says %d t, the six cars carry %d t" % (tonnes, got_t))

        # The art is victor_18993's. The kit used to write its own name here.
        check("every car credits the artist, not the tool",
              metro7k.AUTHOR == "victor_18993",
              "AUTHOR is %r" % metro7k.AUTHOR)

    print("\nout: %s" % _PROJ)
    if FAILED:
        print("\nMETRO7K_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nMETRO7K_OK")


main()
