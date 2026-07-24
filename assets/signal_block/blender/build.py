"""Build a two-aspect rail block signal for pak128, twice.

    blender --background --factory-startup --python assets/signal_block/blender/build.py \
            -- static           # 4 dirs x 2 states  =  8 images  (what a pakset ships today)
    blender ... -- animated     # 4 dirs x 2 states x 4 phases = 32 images
    blender ... -- both         # both, and report the size difference

WHY THIS ASSET EXISTS

Forum thread 22546 asked for animated signals and prissi objected on the
"amount of images needed". A separate measurement settled the RUNTIME cost of
animating signals and found it negligible (0.0036% of a frame with every signal
animating). That measured the cost nobody was arguing about.

The cost that WAS argued about is this one: an animated signal needs a whole
extra copy of its image layout per phase. Read off pak128 2.10.1's own
infrastructure.rail_signals.all.pak:

    25 signals, 260 game images, 207,842 bytes, 799 bytes/image average

so four phases on every signal takes that set from 296 KB to about 900 KB. On a
407 MB pakset that is +0.15%, which is not the real cost either.

THE REAL COST IS THAT SOMEBODY HAS TO DRAW 1,040 SPRITES WHERE THERE WERE 260.

That is the objection, it is a fair one, and no engine change answers it. What
answers it is not drawing them by hand: from a 3D model, the fourth phase costs
one more render, and this file is the demonstration. The two variants below come
from ONE model and differ by a loop bound.

The static variant compiles with any makeobj. The animated one uses
image[dir][state][phase], which only a makeobj carrying the node-version-7
writer accepts - see the spike branch. Nothing here is upstream.

Prints SIGNAL_BLOCK_OK.
"""

import math
import os
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)                       # assets/signal_block
_ROOT = os.path.dirname(os.path.dirname(_PROJ))      # the kit

sys.path.insert(0, _ROOT)
from addon import rig                          # noqa: E402
from core import roadsigns, sheet, paksets     # noqa: E402
from tools import toolchain                    # noqa: E402

RENDERS = os.path.join(_PROJ, "renders")
SPRITES = os.path.join(_PROJ, "sprites")
PAK = os.path.join(_PROJ, "pak")
REPORTS = os.path.join(_PROJ, "reports")

# obj/roadsign.h:63 - STATE_RED = 0, STATE_GREEN = 1. Getting this backwards is
# not a rendering bug, it is a signalling one: the trains obey the index.
STATE_RED, STATE_GREEN = 0, 1

# How many animation phases the animated variant renders. Four is the smallest
# count that reads as a blink rather than a toggle.
PHASES = 4

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        FAILED.append(name)
        print("  FAIL %s %s" % (name, detail))


# --------------------------------------------------------------------------
# The model. This is the artist's job, not the add-on's, so it lives here.
# Dimensions are provisional - my design decision - and spec.json says so.
# --------------------------------------------------------------------------

#
# SCALE. Metres are not Blender units. A tile is `tile_world` units (2.0), and
# the kit's assets take a tile as 25 m - an approximation, stated as one on the
# Civia and inherited here so the signal stands correctly next to that stock.
#
# Getting this wrong is not subtle and it is not silent either: the first run
# modelled the post as 4.2 UNITS instead of 4.2 metres, twice the width of the
# whole tile, and every one of the 8 images was clipped away to nothing. The
# .pak still compiled - at 69 bytes, all-empty images - and reported a tidy
# "4.0x more images" against a .pak that contained no artwork at all. The kit's
# own clipping linter is what said so.
#
# Note also that `distance` does NOT scale an ortho camera (rig.py:188): it only
# moves the clip planes. Size comes from here and nowhere else.
PAKSET = "pak128"
_PAK = paksets.get(PAKSET)

# Blender units per rendered pixel. DERIVED: tile_world units span tile_px
# pixels, so 2.0 units = 128 px and one unit is 64 px.
PX = _PAK.tile_world / _PAK.tile_px

# TARGET SPRITE SIZE. REFERENCE, measured off pak128 2.10.1's own
# infrastructure.rail_signals.all.pak by reading the stored w/h out of every IMG
# node: the game images run 20-38 px wide and 36-46 px tall. 40 px is the middle
# of that.
#
# This deliberately does NOT inherit the Civia's METRES_PER_TILE of 25. That
# number exists to satisfy a VEHICLE constraint - sprite length must be
# length/16 of a tile or cars gap - and it is not a world scale. Applied to a
# signal it gives a 4.2 m post 0.9 px wide, which antialiases to nothing: the
# first corrected run rendered SEVEN opaque pixels and still produced a .pak and
# a tidy 4x ratio. Simutrans art is not drawn to one scale and pretending it is
# produces a speck.
SPRITE_H_PX = 40.0

POST_HEIGHT = SPRITE_H_PX * PX
# Real posts read about 3 px across in the reference sprites - wider than true
# scale, which is the same deliberate fattening the Civia documents. Below about
# 1.5 px a vertical edge disappears into the antialiasing.
POST_RADIUS = 1.5 * PX
HEAD_RADIUS = 4.0 * PX
HEAD_DEPTH = 9.0 * PX
LAMP_RADIUS = 2.2 * PX


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials):
        for item in list(block):
            block.remove(item)


def emissive(name, rgb, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Emission Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def build_model():
    """Post, head, and two lamps. The lamps are named so state_setup can find them."""
    clear_scene()

    body = emissive("signal_body", (0.16, 0.17, 0.18))
    mats = {
        "lamp_red":   emissive("lamp_red",   (0.85, 0.06, 0.06)),
        "lamp_green": emissive("lamp_green", (0.06, 0.75, 0.20)),
    }

    bpy.ops.mesh.primitive_cylinder_add(
        radius=POST_RADIUS, depth=POST_HEIGHT,
        location=(0.0, 0.0, POST_HEIGHT / 2.0))
    post = bpy.context.object
    post.name = "post"
    post.data.materials.append(body)

    # The head sits at the top and faces SOUTH (-Y), towards the traffic: the
    # model stands at the tile's north edge, which is the convention
    # render_roadsign documents and every direction is that model turned.
    head_z = POST_HEIGHT - HEAD_DEPTH / 2.0
    bpy.ops.mesh.primitive_cylinder_add(
        radius=HEAD_RADIUS, depth=HEAD_DEPTH,
        location=(0.0, 0.0, head_z))
    head = bpy.context.object
    head.name = "head"
    head.data.materials.append(body)

    lamps = {}
    for key, dz in (("lamp_red", +2.2 * PX), ("lamp_green", -2.2 * PX)):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=LAMP_RADIUS,
            location=(0.0, -HEAD_RADIUS * 0.8, head_z + dz))
        lamp = bpy.context.object
        lamp.name = key
        lamp.data.materials.append(mats[key])
        lamps[key] = mats[key]

    return lamps


def lamp_strength(mat, value):
    mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = value


# --------------------------------------------------------------------------
# The two variants
# --------------------------------------------------------------------------

ON, OFF = 6.0, 0.0


def make_state_setup(lamps, phase_level=None):
    """Light the aspect's lamp. phase_level dims it, which is the animation."""
    def state_setup(_bpy, state):
        lit = ON if phase_level is None else phase_level
        lamp_strength(lamps["lamp_red"], lit if state == STATE_RED else OFF)
        lamp_strength(lamps["lamp_green"], lit if state == STATE_GREEN else OFF)
    return state_setup


def build_static(lamps):
    """What a pakset ships today: 4 directions x 2 states."""
    out = os.path.join(RENDERS, "static")
    frames = rig.render_roadsign(
        bpy, out, pakset_name="pak128", basename="signal_static",
        states=2, state_setup=make_state_setup(lamps), distance=17.0)

    sheet_png, dat_path, placement = rig.build_roadsign_sheet_and_dat(
        frames, os.path.join(SPRITES, "static"), pakset_name="pak128",
        basename="signal_static", cols=4,
        name="SpikeBlockSignalStatic", waytype="track", is_signal=1,
        cost=800, author="simutrans-blender-kit spike",
        intro_year=1900, retire_year=2999)
    return frames, sheet_png, dat_path, placement


def build_animated(lamps):
    """The same model, one more loop: 4 directions x 2 states x PHASES.

    The kit's roadsigns module writes image[dir][state]. The third index is not
    its business yet - it is a spike-only DAT syntax - so it is written here.
    """
    out = os.path.join(RENDERS, "animated")
    frames = []
    # A blink: full, dim, out, dim. The lamp is the only thing that changes, so
    # the extra 24 images cost exactly 24 renders and no drawing at all.
    levels = [ON, ON * 0.45, OFF, ON * 0.45][:PHASES]

    for phase, level in enumerate(levels):
        got = rig.render_roadsign(
            bpy, os.path.join(out, "phase%d" % phase), pakset_name="pak128",
            basename="signal_anim_p%d" % phase,
            states=2, state_setup=make_state_setup(lamps, phase_level=level),
            distance=17.0)
        # re-key so the sheet keeps the phase
        frames.extend((((d, s, phase)), p) for (d, s), p in got)

    pak = paksets.get("pak128")
    out_dir = os.path.join(SPRITES, "animated")
    os.makedirs(out_dir, exist_ok=True)
    sheet_png = os.path.join(out_dir, "signal_anim.png")
    placement = sheet.assemble(frames, pak.tile_px, cols=8, out_path=sheet_png)

    # image[dir][state][phase]. The engine flattens to
    # dir + state*4 + phase*stride, and phase_stride = count/phases, which is
    # why the phase must be the SLOWEST index - a whole copy of the layout.
    lines = []
    for phase in range(PHASES):
        for state in (STATE_RED, STATE_GREEN):
            for d in roadsigns.SIGN_DIRS:
                r, c = placement[(d, state, phase)]
                lines.append("image[%s][%d][%d]=signal_anim.%d.%d"
                             % (d, state, phase, r, c))
    r, c = placement[(roadsigns.SIGN_DIRS[0], STATE_RED, 0)]
    ui = "icon=signal_anim.%d.%d\ncursor=signal_anim.%d.%d" % (r, c, r, c)

    dat = roadsigns.roadsign_dat(
        "SpikeBlockSignalAnimated", "\n".join(lines), ui,
        waytype="track", is_signal=1, cost=800,
        author="simutrans-blender-kit spike", intro_year=1900, retire_year=2999)
    # the two spike-only keys the node-version-7 writer reads
    dat += "\nphases=%d\nanimation_time=300\n" % PHASES

    dat_path = os.path.join(out_dir, "signal_anim.dat")
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write(dat)
    return frames, sheet_png, dat_path, placement


def compile_pak(dat_path, makeobj, tag):
    import subprocess
    os.makedirs(PAK, exist_ok=True)
    out = os.path.join(PAK, "%s.pak" % tag)
    if os.path.exists(out):
        os.remove(out)
    # Exactly how the add-on's own Compile .pak does it (ui.py:1264): run IN the
    # directory holding the .dat, because the .dat's image references are
    # relative to it, and hand makeobj THE .DAT, not the directory. Passing the
    # directory produced a .pak containing only a ROOT node - 69 bytes, exit 0,
    # no diagnostic - which is indistinguishable from a successful build unless
    # you look inside it.
    src = os.path.dirname(dat_path)
    res = subprocess.run(
        [makeobj, _PAK.makeobj_arg, os.path.basename(out),
         os.path.basename(dat_path)],
        cwd=src, capture_output=True, text=True)
    produced = os.path.join(src, os.path.basename(out))
    if os.path.exists(produced) and produced != out:
        import shutil
        shutil.move(produced, out)
    ok = os.path.exists(out)
    if not ok:
        print(res.stdout[-2000:])
        print(res.stderr[-2000:])
    return out if ok else None


# A 128px signal image is on the order of 800 bytes in pak128's own signal file
# (measured: 260 game images, 799 bytes average). An image makeobj found to be
# entirely transparent is written as a 10-byte stub, so an all-clipped object
# compiles to a .pak of a few dozen bytes and reports whatever ratio you asked
# for. That happened here on the first run. Refuse it explicitly rather than
# trusting the eye on a number.
MIN_BYTES_PER_IMAGE = 100


def check_pak_has_artwork(pak_path, n_images):
    if pak_path is None:
        return False
    per = os.path.getsize(pak_path) / float(n_images)
    return per >= MIN_BYTES_PER_IMAGE


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["both"]
    what = argv[0] if argv else "both"

    # toolchain.find_makeobj honours SIMUTRANS_MAKEOBJ, which is how the
    # node-version-7 makeobj from the spike branch gets used for the animated
    # variant. Stock makeobj compiles the static one and rejects the other.
    makeobj = toolchain.find_makeobj(_ROOT) or ""
    check("makeobj found", bool(makeobj) and os.path.exists(makeobj), makeobj)

    lamps = build_model()
    check("model built", "post" in bpy.data.objects and "lamp_red" in bpy.data.objects)

    os.makedirs(REPORTS, exist_ok=True)
    report = []

    if what in ("static", "both"):
        frames, png, dat, placement = build_static(lamps)
        check("static: 8 images", len(frames) == 8, "got %d" % len(frames))
        pak = compile_pak(dat, makeobj, "signal_static")
        check("static: pak compiled", pak is not None)
        check("static: pak actually contains artwork",
              check_pak_has_artwork(pak, len(frames)),
              "all-transparent images compile to a stub .pak")
        if pak:
            report.append(("static", len(frames), os.path.getsize(png),
                           os.path.getsize(pak)))

    if what in ("animated", "both"):
        frames, png, dat, placement = build_animated(lamps)
        check("animated: %d images" % (8 * PHASES),
              len(frames) == 8 * PHASES, "got %d" % len(frames))
        pak = compile_pak(dat, makeobj, "signal_anim")
        check("animated: pak compiled (needs the node-v7 makeobj)", pak is not None)
        check("animated: pak actually contains artwork",
              check_pak_has_artwork(pak, len(frames)),
              "all-transparent images compile to a stub .pak")
        if pak:
            report.append(("animated", len(frames), os.path.getsize(png),
                           os.path.getsize(pak)))

    print("")
    print("  variant     images   sheet png      .pak")
    for tag, n, png_b, pak_b in report:
        print("  %-10s %6d  %10d  %8d" % (tag, n, png_b, pak_b))
    if len(report) == 2:
        s, a = report[0], report[1]
        print("  ratio      %6.1fx %10.1fx  %8.1fx"
              % (a[1] / s[1], a[2] / s[2], a[3] / s[3]))

    with open(os.path.join(REPORTS, "sizes.txt"), "w", encoding="utf-8") as f:
        for tag, n, png_b, pak_b in report:
            f.write("%s\timages=%d\tpng=%d\tpak=%d\n" % (tag, n, png_b, pak_b))

    if FAILED:
        print("\nFAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nSIGNAL_BLOCK_OK")


main()
