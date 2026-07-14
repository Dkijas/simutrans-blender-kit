"""Catenary and signals, end to end, inside Blender.

    blender --background --python tests/blender_infra.py

Both ride on the ribi machinery the ways already proved, so what is actually new -
and what this test is for - is the two things that are easy to ship backwards:

  THE CATENARY'S TWO LAYERS.  A wayobj needs backimage[ribi] AND frontimage[ribi].
  The poles and the far wire go behind the train; the wire that crosses OVER it
  goes in front. Put everything in the back list and the .pak compiles, the game
  runs, the catenary appears - and the train drives straight over its own overhead
  line. Nothing warns you, because nothing is wrong: the images are simply in the
  wrong list.

  THE SIGNAL'S TWO ASPECTS.  State 0 is RED (obj/roadsign.h:63). Swap the two and
  the signal shows green for danger. That is not a rendering bug, it is a
  signalling bug, and the trains will act on it.

Prints INFRA_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                                            # noqa: E402
from core import paksets, roadsigns, schema, sheet, ways         # noqa: E402

OUT = os.path.join(_ROOT, "build", "infra")
PAKSET = "pak128"
FAILED = []

RED = (200, 20, 20)
GREEN = (20, 200, 20)
WIRE = (240, 220, 60)      # the front wire, so we can find it in the pixels
POLE = (90, 90, 100)


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


def opaque_pixels(path):
    w, h, alpha, px = sheet.read_png(path)
    if not alpha:
        return w * h
    return sum(1 for p in px if p[3] > 0)


# ------------------------------------------------------------- catenary
def build_catenary():
    """Six pieces of overhead line. The poles go behind, the wire goes in front."""
    clear()
    pak = paksets.get(PAKSET)
    tw = pak.tile_world

    pole_mat = rig.make_special_color_material(bpy, POLE, name="pole")
    wire_mat = rig.make_special_color_material(bpy, WIRE, name="wire")

    for piece, base in ways.PIECES:
        back = bpy.data.collections.new(rig.WAYOBJ_COLLECTION_PREFIX + piece)
        bpy.context.scene.collection.children.link(back)
        front = bpy.data.collections.new(
            rig.WAYOBJ_COLLECTION_PREFIX + piece + "_front")
        bpy.context.scene.collection.children.link(front)

        # a mast at the tile's north-west corner: behind the train, always
        bpy.ops.mesh.primitive_cylinder_add(radius=0.05 * tw, depth=1.4 * tw,
                                            location=(-0.4 * tw, 0.4 * tw, 0.7 * tw))
        mast = bpy.context.active_object
        mast.name = "mast_%s" % piece
        mast.data.materials.append(pole_mat)
        bpy.context.scene.collection.objects.unlink(mast)
        back.objects.link(mast)

        # the contact wire: one span per direction the ribi names, strung high over
        # the middle of the track. THIS is the part that must be drawn in front.
        for bit, (bx, by) in ways.RIBI_BLENDER_VECTOR.items():
            if not (base & bit):
                continue
            bpy.ops.mesh.primitive_cube_add(size=1, location=(
                bx * 0.25 * tw, by * 0.25 * tw, 1.3 * tw))
            span = bpy.context.active_object
            span.name = "wire_%s_%d" % (piece, bit)
            # thin across the span, long along it
            span.scale = (0.06 * tw if bx == 0 else 0.5 * tw,
                          0.06 * tw if by == 0 else 0.5 * tw,
                          0.03 * tw)
            span.data.materials.append(wire_mat)
            bpy.context.scene.collection.objects.unlink(span)
            front.objects.link(span)

    # --- the ramp. Same story as the way's: wayobj.cc:270 reaches for the slope
    # image with no guard, so a catenary without one is NOT DRAWN on a hill - the
    # rail climbs it, the wire does not, and the tile is still electrified.
    rise = pak.height_world
    back = bpy.data.collections.new(rig.WAYOBJ_COLLECTION_PREFIX + ways.SLOPE_PIECE)
    bpy.context.scene.collection.children.link(back)
    front = bpy.data.collections.new(
        rig.WAYOBJ_COLLECTION_PREFIX + ways.SLOPE_PIECE + "_front")
    bpy.context.scene.collection.children.link(front)

    # The mast stands on the raised (south, -Y) side of a north-facing ramp, and it
    # is exactly as tall as the flat ones. NOTHING in the ramp may be higher than
    # the flat model, because the flat model already sits close to the top of the
    # cell: raising the wire by a height level put it clean off the frame, and the
    # rig's own clipping warning said so before the test did.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05 * tw, depth=1.4 * tw,
                                        location=(-0.4 * tw, -0.4 * tw, 0.7 * tw))
    mast = bpy.context.active_object
    mast.name = "mast_slope"
    mast.data.materials.append(pole_mat)
    bpy.context.scene.collection.objects.unlink(mast)
    back.objects.link(mast)

    # the wire follows the ramp DOWNWARDS: level with the flat catenary over the
    # raised end, one height level below it over the other
    for sign, drop in ((-1, 0.0), (1, rise)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(
            0.0, sign * 0.25 * tw, 1.3 * tw - drop))
        span = bpy.context.active_object
        span.name = "wire_slope_%d" % sign
        span.scale = (0.06 * tw, 0.5 * tw, 0.03 * tw)
        span.data.materials.append(wire_mat)
        bpy.context.scene.collection.objects.unlink(span)
        front.objects.link(span)


def test_catenary():
    pak = paksets.get(PAKSET)
    build_catenary()

    check("the rig sees that this wayobj has front parts",
          rig.has_front_parts(bpy))

    frames = rig.render_wayobj(bpy, OUT, PAKSET, basename="bkitwire")
    check("thirty-two images: sixteen ribis, two layers", len(frames) == 32,
          str(len(frames)))

    by_key = dict(frames)

    # THE ORACLE FOR THE SPLIT. The wire is in the front layer and the mast is in
    # the back one, so each layer must contain exactly one of them and neither may
    # contain the other. Get the collections crossed and this goes red.
    for ribi in (5, 10, 15):          # ns, ew, nsew - all have wire in every span
        back = by_key[(ways.WAYOBJ_BACK, ribi)]
        front = by_key[(ways.WAYOBJ_FRONT, ribi)]

        check("image[%s]: the back layer has the mast, not the wire"
              % ways.code(ribi),
              _has(back, POLE) and not _has(back, WIRE),
              "the wire is in the BACK list - the train will drive over it")
        check("image[%s]: the front layer has the wire, not the mast"
              % ways.code(ribi),
              _has(front, WIRE) and not _has(front, POLE),
              "the mast is in the FRONT list - it will be drawn over the train")

    # the piece with no connections has no wire at all, so its front image is blank -
    # which is correct, and must not be mistaken for a broken render
    check("image[-]: nothing to draw in front of an isolated tile",
          opaque_pixels(by_key[(ways.WAYOBJ_FRONT, 0)]) == 0)

    # --- the ramp
    check("the rig sees the catenary's ramp", rig.has_wayobj_slope_model(bpy))
    slope_frames = rig.render_wayobj_slopes(bpy, OUT, PAKSET, basename="bkitwire")
    check("eight slope images: four directions, two layers",
          len(slope_frames) == 8, str(len(slope_frames)))
    check("every slope image has something in it",
          all(opaque_pixels(p) > 0 for _k, p in slope_frames))
    check("the four back ramps are four different pictures",
          len({tuple(sheet.read_png(p)[3]) for (lay, _d), p in slope_frames
               if lay == ways.WAYOBJ_BACK}) == 4)

    sheet_png, dat_path, _pl = rig.build_wayobj_sheet_and_dat(
        frames, OUT, PAKSET, basename="bkitwire", cols=8,
        slope_frames=slope_frames,
        name="BKit_Catenary", waytype="track", own_waytype="electrified_track",
        author="simutrans-blender-kit")

    with open(dat_path, encoding="utf-8") as f:
        dat = f.read()

    check("dat is a way-object (with a hyphen - way_obj_writer.h:31)",
          "obj=way-object" in dat)
    check("dat grants electrification", "own_waytype=electrified_track" in dat)
    check("dat carries both layers",
          "backimage[ns]=" in dat and "frontimage[ns]=" in dat, dat)
    check("dat carries an icon", "icon=" in dat, dat)
    # NUMERIC only: way_obj_writer.cc:78 builds the key with sprintf("...[%d]"),
    # and never looks for a lettered one. n=3, w=6, e=9, s=12.
    check("dat carries all four slope images, or the wire vanishes on hills",
          all(("backimageup[%d]=" % n) in dat and ("frontimageup[%d]=" % n) in dat
              for n in (3, 6, 9, 12)), dat)

    findings = schema.lint(dat)
    for f in findings:
        print("       %s" % f)
    check("the catenary .dat lints clean", not findings,
          "%d finding(s)" % len(findings))


def _has(path, rgb, tol=40):
    w, h, alpha, px = sheet.read_png(path)
    for p in px:
        if alpha and p[3] == 0:
            continue
        if all(abs(p[i] - rgb[i]) < tol for i in range(3)):
            return True
    return False


# --------------------------------------------------------------- signal
def build_signal():
    """A post with a lamp. The lamp's colour is what the state changes."""
    clear()
    pak = paksets.get(PAKSET)
    tw = pak.tile_world

    bpy.ops.mesh.primitive_cylinder_add(radius=0.05 * tw, depth=1.0 * tw,
                                        location=(0.3 * tw, 0.42 * tw, 0.5 * tw))
    post = bpy.context.active_object
    post.name = "POST"
    post.data.materials.append(rig.make_special_color_material(bpy, POLE,
                                                               name="pole"))

    # the lamp sits at the tile's NORTH edge (Blender +Y), which is the model
    # convention: the four images are this one sign turned.
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11 * tw,
                                         location=(0.3 * tw, 0.42 * tw, 1.05 * tw))
    lamp = bpy.context.active_object
    lamp.name = "LAMP"


def state_setup(bpy_, state):
    """State 0 is RED. obj/roadsign.h:63 - and the trains act on it."""
    lamp = bpy_.data.objects.get("LAMP")
    if lamp is None:
        return
    lamp.data.materials.clear()
    lamp.data.materials.append(
        rig.make_special_color_material(bpy, RED if state == roadsigns.STATE_RED
                                        else GREEN, name="aspect_%d" % state))


def test_signal():
    build_signal()

    frames = rig.render_roadsign(bpy, OUT, PAKSET, basename="bkitsignal",
                                 states=2, state_setup=state_setup)
    check("eight images: four directions, two aspects", len(frames) == 8,
          str(len(frames)))

    by_key = dict(frames)

    # THE ORACLE. State 0 must be RED in every direction. If the aspects are the
    # wrong way round, the signal shows green for danger.
    for d in roadsigns.SIGN_DIRS:
        check("image[%s][0] is RED, as the engine assumes" % d,
              _has(by_key[(d, 0)], RED) and not _has(by_key[(d, 0)], GREEN),
              "state 0 is STATE_RED (obj/roadsign.h:63)")
        check("image[%s][1] is GREEN" % d,
              _has(by_key[(d, 1)], GREEN) and not _has(by_key[(d, 1)], RED))

    # the four directions are the same sign turned; identical images would mean the
    # sign never turned and would face one way for all four
    distinct = {tuple(sheet.read_png(by_key[(d, 0)])[3])
                for d in roadsigns.SIGN_DIRS}
    check("the four directions are actually different images", len(distinct) == 4,
          "%d distinct out of 4" % len(distinct))

    # the engine's flat index: direction + state*4, with dir 0=n 1=s 2=w 3=e
    check("north is index 0", roadsigns.image_index("n", 0) == 0)
    check("east is index 3", roadsigns.image_index("e", 0) == 3)
    check("green north is index 4", roadsigns.image_index("n", 1) == 4)

    sheet_png, dat_path, _pl = rig.build_roadsign_sheet_and_dat(
        frames, OUT, PAKSET, basename="bkitsignal", cols=4,
        name="BKit_Signal", waytype="track", is_signal=1,
        author="simutrans-blender-kit")

    with open(dat_path, encoding="utf-8") as f:
        dat = f.read()

    check("dat is a roadsign", "obj=roadsign" in dat)
    check("dat is a signal", "is_signal=1" in dat)
    check("dat carries all four directions at state 0",
          all(("image[%s][0]=" % d) in dat for d in roadsigns.SIGN_DIRS), dat)
    check("dat carries the green aspect", "image[n][1]=" in dat, dat)
    check("dat carries an icon", "icon=" in dat, dat)

    findings = schema.lint(dat)
    for f in findings:
        print("       %s" % f)
    check("the signal .dat lints clean", not findings,
          "%d finding(s)" % len(findings))


def main():
    test_catenary()
    test_signal()
    if FAILED:
        print("\nINFRA_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nINFRA_OK")


main()
