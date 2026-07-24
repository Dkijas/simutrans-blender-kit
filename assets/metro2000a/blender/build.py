"""Build the Metro de Madrid Serie 2000A THROUGH THE ADD-ON, not around it.

    blender --background --factory-startup --python assets/metro2000a/blender/build.py \
            -- mot                   # one car (the prototype)
    blender ... -- all               # the M+R pair, with couplings

Same shape as the 7000's build: install the add-on zip, fill in the panel's own
properties, press the panel's own buttons. The only thing this file does itself is
MODEL. Everything downstream of the geometry is the add-on's code, called the way a
person would call it.

Prints METRO2000A_OK.
"""

import os
import shutil
import subprocess
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)                       # assets/metro2000a
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
    """Build the add-on zip from source, then install THAT one."""
    subprocess.run([sys.executable, os.path.join(_ROOT, "tools", "build_addon_zip.py")],
                   check=True)
    if not os.path.exists(ZIP):
        raise SystemExit("tools/build_addon_zip.py produced no %s" % ZIP)
    bpy.ops.preferences.addon_install(filepath=ZIP, overwrite=True)
    bpy.ops.preferences.addon_enable(module="simutrans_blender_kit")


_SPEC = None


def load_spec():
    global _SPEC
    if _SPEC is None:
        sys.path.insert(0, _ROOT)
        from tools import spec
        _SPEC = spec.load(os.path.join(_PROJ, "spec.json"))
        guesses = ", ".join(f.key for f in _SPEC.provisional())
        print("  spec: %s - %d facts, and the guesses are: %s"
              % (_SPEC.name, len(_SPEC.facts), guesses or "none"))
    return _SPEC


def couplings(cars):
    """Who may go in front of whom - and this is where the 2000A stops being a 7000.

    The 7000 and the 9000 are INDEFORMABLE: six cars, each with exactly one possible
    successor, so the depot walks the chain from a single click and there is nothing
    to decide. A 2000A is not that train. It is a married M+R pair, and pairs couple
    to pairs: it ran as 2, 4 and 6 cars. So the chain BRANCHES -

        M   prev: none, R      next: R
        R   prev: M            next: none, M

    - and every one of those four entries is doing work. `none` on M's prev is what
    lets it lead (vehicle_desc.h:218: leader_count==1 with get_leader(0)==NULL matches
    only prev_veh==NULL). `R` on M's prev is what lets a second pair follow a first.
    `none` on R's next lets the train end; `M` lets it go on.

    THE ONE THING THIS CANNOT SAY, AND IT MATTERS.

    It permits 2, 4, 6 - and also 8, 10, 12. Simutrans Standard has no way to cap a
    convoy from the .dat: get_max_convoi_length() (depot.cc:638) counts VEHICLES and
    is a global setting of the game, not a property of a vehicle. Checked, not
    assumed. Real 2000As ran to six cars because the platforms are 90 m, and the
    engine does not know what a platform is when you are standing in a depot.

    So this is a real over-permission and it is deliberate: the alternative is to
    hard-wire a six-car chain that CANNOT be bought as a two-car unit, and a
    two-car 2000A is the more common prototype, not a corner case. Say it in the
    post rather than paper over it.
    """
    mot, rem = cars
    return {
        mot.key: (("none", rem.name), (rem.name,)),
        rem.key: ((mot.name,), ("none", mot.name)),
    }


def build_one(metro2000a, car, constraints, install=True):
    from simutrans_blender_kit.addon import rig      # the INSTALLED copy

    metro2000a.build_car(car)

    p = bpy.context.scene.simutrans
    p.pakset = "pak128"
    p.obj_type = "vehicle"
    p.dirs = "8"

    # Centred, and no nudge: both cars are the same length, and centred art of equal
    # length butts exactly. It is MIXED lengths that open the joints.
    p.align_offset = (0.0, 0.0, 0.0)
    p.basename = car.key
    p.obj_name = car.name
    p.author = metro2000a.AUTHOR
    p.out_dir = SPRITES

    spec = load_spec()
    p.waytype = "track"

    # electric on BOTH cars, including the unpowered trailer, and on purpose.
    # Electrification itself is guarded by power != 0 (simconvoi.cc:1697), so this
    # does not make the trailer demand catenary. What it does is put both cars in
    # the same depot tab: depot_frame.cc:531 sorts by engine_type WITHOUT looking at
    # power, so a non-electric trailer would sit under "passengers" while its motor
    # car sits under "electrics", and the player would have to find the two halves of
    # one train in two different tabs. (Omitting engine_type would be worse still:
    # vehicle_writer.cc:28 defaults it to DIESEL, not to unknown.)
    p.engine_type = "electric"

    p.speed = spec.value("speed")                  # measured: Via Libre ficha
    p.power = car.kilowatts                        # spec: cars[].kilowatts
    p.weight = car.tonnes                          # spec: cars[].tonnes - see the note
    p.length = car.length                          # 7, not 8. See spec length_carunits
    p.freight = "Passagiere"
    p.payload = car.seats                          # SEATED only, as the 9000 shipped
    p.intro_year = spec.value("intro_year")        # measured
    p.retire_year = spec.value("retire_year")      # measured: still in service

    # PROVISIONAL, both. The motor car carries the price; the trailer costs less
    # because it has no traction equipment in it, which is the same shape of guess
    # the 7000 makes and no better founded.
    p.cost = spec.value("cost") if car.panto else spec.value("cost") // 2
    p.runningcost = (spec.value("runningcost") if car.panto
                     else spec.value("runningcost") // 2)

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

    # --- the FLAT CONTOUR, inked onto the rendered sheet before makeobj sees it.
    # Done here, in place, so the reserved-colour report below validates the sheet
    # the .pak will actually carry - contour included. One colour, non-reserved.
    inked = metro2000a.apply_outline(sheet_png)
    check("%s: the flat contour was inked" % car.key,
          inked == metro2000a.OUTLINE, str(inked))

    # --- the reserved-colour report, split the way the brief asks
    wanted, accidental = rig.reserved_colour_report(bpy, sheet_png)
    print("       intentional reserved colours: %s"
          % {("#%02X%02X%02X" % k): v for k, v in wanted.items()})
    check("%s: no ACCIDENTAL reserved colours" % car.key, not accidental,
          str(accidental))
    check("%s: the windows really are the engine's window colour" % car.key,
          wanted.get(metro2000a.LIT_PANE, 0) > 30,
          "%d px" % wanted.get(metro2000a.LIT_PANE, 0))
    # EVERY car of this unit has a cab, unlike any unit built here before, so both
    # of them must carry both lamps.
    check("%s: the headlights are the engine's light colour" % car.key,
          wanted.get(metro2000a.HEADLIGHT, 0) > 4,
          "%d px" % wanted.get(metro2000a.HEADLIGHT, 0))
    check("%s: the tail lights are the engine's red" % car.key,
          wanted.get(metro2000a.TAILLIGHT, 0) > 4,
          "%d px" % wanted.get(metro2000a.TAILLIGHT, 0))

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
        if img.name.startswith(car.key):
            img.filepath_raw = os.path.join(TEXTURES, "%s.png" % img.name)
            img.file_format = "PNG"
            img.save()
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.join(BLEND, "%s.blend" % car.key))

    return wanted


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    which = argv[0] if argv else "mot"

    for d in (RENDERS, SPRITES, DAT, PAK, TEXTURES, BLEND, REPORTS):
        os.makedirs(d, exist_ok=True)

    install_addon()
    sys.path.insert(0, _HERE)
    import metro2000a                           # noqa: E402  (after the install)

    if which == "all":
        cars = list(metro2000a.UNIT)
        cons = couplings(cars)
    else:
        # The PROTOTYPE runs without couplings on purpose: a Constraint pointing at a
        # car that does not exist yet is a dangling reference the pakset cannot
        # resolve at load.
        cars = [c for c in metro2000a.UNIT if c.key.endswith(which)]
        if not cars:
            raise SystemExit("unknown car: %s" % which)
        cons = {}

    print("\n=== Metro de Madrid Serie 2000A for pak128: %s ===\n"
          % ", ".join(c.key for c in cars))
    for car in cars:
        print("--- %s (%s, %.2f m -> length %d)"
              % (car.key, car.name, car.metres, car.length))
        build_one(metro2000a, car, cons)

    if which == "all":
        spec = load_spec()

        # The spec cannot see this module: it could hold a valid two-car spec while
        # the module builds one. That seam is what is checked here.
        want = [c["key"] for c in spec.cars]
        got = [c.key for c in metro2000a.UNIT]
        check("the module builds exactly the unit the spec describes, in order",
              got == want, "spec: %s\n         module: %s" % (want, got))

        check("and their roles spell the declared formation",
              "-".join(c.role for c in metro2000a.UNIT) == spec.formation,
              "%s vs %s" % ("-".join(c.role for c in metro2000a.UNIT),
                            spec.formation))

        # THE CROSS-SECTION IS READ, and this is the check that says so.
        #
        # The 7000 and the 9000 hardcode width and height, so their sourced metres
        # change nothing and no test can tell. Here they are computed from the spec,
        # and the failure this guards against is silent: if Body ever went back to
        # constants, everything would still build, still lint, still compile - and
        # the 2000A would quietly be a 7000 again, which is the whole reason it
        # exists. So: change the spec, and the geometry must move.
        # A MUTATION, because asserting "width == WIDTH_TW_PER_M * spec.width * TW"
        # would be tautological: it computes the expected value exactly the way Body
        # does, so it would sail through against a hardcoded constant that happened
        # to agree. The only check with teeth is to CHANGE the spec and insist the
        # geometry moves - and then put it back.
        b = metro2000a.Body(metro2000a.MOT)
        before_w, before_h = b.width, b.height
        was_w = metro2000a.SPEC.facts["width_m"].value
        was_h = metro2000a.SPEC.facts["height_m"].value
        try:
            metro2000a.SPEC.facts["width_m"].value = was_w * 2.0
            metro2000a.SPEC.facts["height_m"].value = was_h * 2.0
            moved = metro2000a.Body(metro2000a.MOT)
            check("double the spec's width and the body really doubles",
                  abs(moved.width - before_w * 2.0) < 1e-9,
                  "%.4f -> %.4f, expected %.4f"
                  % (before_w, moved.width, before_w * 2.0))
            check("double the spec's height and the body really doubles",
                  abs(moved.height - before_h * 2.0) < 1e-9,
                  "%.4f -> %.4f" % (before_h, moved.height))
        finally:
            metro2000a.SPEC.facts["width_m"].value = was_w
            metro2000a.SPEC.facts["height_m"].value = was_h

        b = metro2000a.Body(metro2000a.MOT)
        check("and the spec goes back where it was",
              abs(b.width - before_w) < 1e-9)
        check("it really is narrower than the 7000's 0.198 tiles",
              b.width < 0.198 * metro2000a.TW,
              "%.4f tiles" % (b.width / metro2000a.TW))
        check("and lower than the 7000's 0.187 tiles",
              b.height < 0.187 * metro2000a.TW,
              "%.4f tiles" % (b.height / metro2000a.TW))

        # length 7 is the other half of "this is not a 7000". If it ever rounds back
        # to 8 the train is the wrong size and nothing else complains.
        check("every car is length 7, not pak128's usual 8",
              all(c.length == 7 for c in metro2000a.UNIT),
              str([c.length for c in metro2000a.UNIT]))

        # Both cars have a cab: that is the silhouette, and it is what a six-car
        # train shows in the middle.
        check("both cars have a cab - the thing a 7000 does not have",
              all(c.cab for c in metro2000a.UNIT))
        check("exactly one car has the pantograph",
              sum(1 for c in metro2000a.UNIT if c.panto) == 1)

        # The couplings BRANCH, unlike every other unit here. If R's next ever loses
        # its "M", six-car trains stop being buildable and only the pair is left -
        # and the build would still be green.
        cons = couplings(list(metro2000a.UNIT))
        mot, rem = metro2000a.UNIT
        check("the pair repeats: R may be followed by another M",
              mot.name in cons[rem.key][1],
              str(cons[rem.key]))
        check("and the train may still end after R",
              "none" in cons[rem.key][1], str(cons[rem.key]))
        check("M may lead a train",
              "none" in cons[mot.key][0], str(cons[mot.key]))
        check("and M may also follow an R, which is what makes 4 and 6 cars work",
              rem.name in cons[mot.key][0], str(cons[mot.key]))

        check("every car credits the artist, not the tool",
              metro2000a.AUTHOR == "victor_18993",
              "AUTHOR is %r" % metro2000a.AUTHOR)

    print("\nout: %s" % _PROJ)
    if FAILED:
        print("\nMETRO2000A_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nMETRO2000A_OK")


main()
