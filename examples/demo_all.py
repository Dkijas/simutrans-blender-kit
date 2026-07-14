"""One object of EVERY type the kit can make, in a single Blender run.

    blender --background --python examples/demo_all.py -- [pakset] [outdir]

Five objects, five .dat files, five sheets:

    BKitAll_Loco        obj=vehicle     an ELECTRIC locomotive
    BKitAll_House       obj=building    a city house
    BKitAll_Road        obj=way         a road
    BKitAll_Catenary    obj=way-object  overhead line, in two layers
    BKitAll_Signal      obj=roadsign    a two-aspect block signal

The locomotive is electric ON PURPOSE. An electric loco will not move a metre on
unelectrified track, so the moment the game drives it we have proved the catenary
too - not that it renders, not that it compiles, but that the engine agrees it is
catenary. The pieces check each other.

Prints DEMO_ALL_OK. tests/../build/<outdir> then holds everything makeobj needs.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                                              # noqa: E402
from core import (buildings, colors, paksets, roadsigns, schema,   # noqa: E402
                  sheet, ways)

_argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PAKSET = _argv[0] if _argv else "pak64"
OUT = _argv[1] if len(_argv) > 1 else os.path.join(_ROOT, "build", "demo_all")

PAK = paksets.get(PAKSET)
TW = PAK.tile_world
FAILED = []

STEEL = (105, 110, 120)
BRICK = (170, 90, 70)
ROOF = (70, 75, 85)
ASPHALT = (68, 68, 74)
CAB = (58, 62, 72)
WIRE = (215, 190, 90)
RED = (200, 25, 25)
GREEN = (25, 190, 60)


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


def lint(dat_path, label):
    with open(dat_path, encoding="utf-8") as f:
        dat = f.read()
    findings = schema.lint(dat)
    for f in findings:
        print("       %s: %s" % (label, f))
    check("%s lints clean against the engine schema" % label, not findings,
          "%d finding(s)" % len(findings))
    return dat


# --------------------------------------------------------------- 1. vehicle
def make_loco():
    """An electric switcher. Nose along +X; that is the whole convention."""
    clear()
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.24 * TW))
    body = bpy.context.active_object
    body.scale = (1.00 * TW, 0.36 * TW, 0.24 * TW)
    body.data.materials.append(mat(STEEL, "steel"))

    # a cab, off-centre toward the nose, so the eight headings are distinguishable
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.26 * TW, 0, 0.62 * TW))
    cab = bpy.context.active_object
    cab.scale = (0.34 * TW, 0.30 * TW, 0.18 * TW)
    cab.data.materials.append(mat(CAB, "cab"))

    # a player-colour stripe: it must survive the render byte for byte
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.14 * TW))
    band = bpy.context.active_object
    band.scale = (1.02 * TW, 0.38 * TW, 0.06 * TW)
    band.data.materials.append(
        rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3]))

    # a pantograph, because it is an electric loco and it should look like one
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.20 * TW, 0, 0.80 * TW))
    pan = bpy.context.active_object
    pan.scale = (0.24 * TW, 0.28 * TW, 0.025 * TW)
    pan.data.materials.append(mat(WIRE, "wire"))

    frames = rig.render_directions(bpy, OUT, PAKSET, dirs=8, basename="bkloco")
    check("the loco rendered all eight headings", len(frames) == 8, str(len(frames)))

    _png, dat_path, _pl = rig.build_sheet_and_dat(
        frames, OUT, PAKSET, basename="bkloco", cols=4,
        name="BKitAll_Loco", waytype="track", engine_type="electric",
        power=900, speed=110, weight=70, length=16,
        cost=900000, runningcost=700, author="simutrans-blender-kit")

    dat = lint(dat_path, "loco")
    check("the loco is electric", "engine_type=electric" in dat, dat)


# -------------------------------------------------------------- 2. building
def make_house():
    """A 1x1 house. Facade toward -Y - the side Blender's Front view looks at."""
    clear()
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.65 * TW))
    body = bpy.context.active_object
    body.scale = (0.82 * TW, 0.82 * TW, 1.3 * TW)
    body.data.materials.append(mat(BRICK, "brick"))

    bpy.ops.mesh.primitive_cone_add(radius1=0.65 * TW, depth=0.55 * TW,
                                    location=(0, 0, 1.55 * TW))
    bpy.context.active_object.data.materials.append(mat(ROOF, "roof"))

    # the door, on the facade, so the house has a front and the layouts mean something
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.42 * TW, 0.35 * TW))
    door = bpy.context.active_object
    door.scale = (0.22 * TW, 0.03 * TW, 0.7 * TW)
    door.data.materials.append(mat(ROOF, "roof"))

    frames = rig.render_building(bpy, OUT, PAKSET, basename="bkhouse",
                                 size_x=1, size_y=1, layouts=4)
    keys = [k for k, _p in frames]
    check("the house rendered all four layouts",
          sorted({k[0] for k in keys}) == [0, 1, 2, 3])
    check("and stacked into more than one height slice",
          len([k for k in keys if k[0] == 0]) > 1, "the roof is missing")

    png = os.path.join(OUT, "bkhouse.png")
    placement = sheet.assemble(frames, PAK.tile_px, cols=4, out_path=png)
    dat = buildings.building_dat("BKitAll_House",
                                 buildings.image_block("bkhouse", placement),
                                 btype="res", dims="1,1,4", level=3,
                                 author="simutrans-blender-kit")
    dat_path = os.path.join(OUT, "bkhouse.dat")
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write(dat)
    lint(dat_path, "house")


# ------------------------------------------------------------------ 3. way
def _arms(base, collection, half, material, tag):
    """The tile centre plus one arm per direction the ribi names. Blender axes."""
    edges = {ways.NORTH: (0.0, 0.5), ways.EAST: (0.5, 0.0),
             ways.SOUTH: (0.0, -0.5), ways.WEST: (-0.5, 0.0)}
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.01 * TW))
    hub = bpy.context.active_object
    hub.name = "%s_hub" % tag
    hub.scale = (2 * half * TW, 2 * half * TW, 0.02 * TW)
    hub.data.materials.append(material)
    bpy.context.scene.collection.objects.unlink(hub)
    collection.objects.link(hub)

    for bit, (ex, ey) in edges.items():
        if not (base & bit):
            continue
        bpy.ops.mesh.primitive_cube_add(
            size=1, location=(ex / 2 * TW, ey / 2 * TW, 0.01 * TW))
        arm = bpy.context.active_object
        arm.name = "%s_arm_%d" % (tag, bit)
        arm.scale = ((0.5 + half) * TW if ex else 2 * half * TW,
                     (0.5 + half) * TW if ey else 2 * half * TW,
                     0.02 * TW)
        arm.data.materials.append(material)
        bpy.context.scene.collection.objects.unlink(arm)
        collection.objects.link(arm)


def make_road():
    clear()
    asphalt = mat(ASPHALT, "asphalt")
    paint = rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3])

    for piece, base in ways.PIECES:
        col = bpy.data.collections.new(rig.WAY_COLLECTION_PREFIX + piece)
        bpy.context.scene.collection.children.link(col)
        _arms(base, col, 0.14, asphalt, piece)
        if base in (ways.NORTH | ways.SOUTH, 0xF):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.02 * TW))
            line = bpy.context.active_object
            line.scale = (0.04 * TW, 0.9 * TW, 0.02 * TW)
            line.data.materials.append(paint)
            bpy.context.scene.collection.objects.unlink(line)
            col.objects.link(line)

    frames = rig.render_way(bpy, OUT, PAKSET, basename="bkroad")
    check("the road rendered all sixteen ribis", len(frames) == 16, str(len(frames)))
    check("six models covered every ribi, once", not ways.missing(ways.PIECE_NAMES))

    _png, dat_path, _pl = rig.build_way_sheet_and_dat(
        frames, OUT, PAKSET, basename="bkroad", cols=4,
        name="BKitAll_Road", waytype="road", topspeed=80,
        cost=100, maintenance=10, author="simutrans-blender-kit")
    dat = lint(dat_path, "road")
    check("the road has an icon, or nobody could build it", "icon=" in dat)


# -------------------------------------------------------------- 4. wayobj
def make_catenary():
    clear()
    pole = mat(STEEL, "steel")
    wire = mat(WIRE, "wire")

    for piece, base in ways.PIECES:
        back = bpy.data.collections.new(rig.WAYOBJ_COLLECTION_PREFIX + piece)
        bpy.context.scene.collection.children.link(back)
        front = bpy.data.collections.new(
            rig.WAYOBJ_COLLECTION_PREFIX + piece + "_front")
        bpy.context.scene.collection.children.link(front)

        # the mast stands beside the track: it belongs BEHIND the train
        bpy.ops.mesh.primitive_cylinder_add(radius=0.035 * TW, depth=0.86 * TW,
                                            location=(-0.34 * TW, 0.30 * TW,
                                                      0.43 * TW))
        mast = bpy.context.active_object
        mast.name = "mast_%s" % piece
        mast.data.materials.append(pole)
        bpy.context.scene.collection.objects.unlink(mast)
        back.objects.link(mast)

        # the contact wire crosses OVER the train: it belongs in FRONT
        for bit, (bx, by) in ways.RIBI_BLENDER_VECTOR.items():
            if not (base & bit):
                continue
            bpy.ops.mesh.primitive_cube_add(
                size=1, location=(bx * 0.25 * TW, by * 0.25 * TW, 0.83 * TW))
            span = bpy.context.active_object
            span.name = "wire_%s_%d" % (piece, bit)
            span.scale = (0.045 * TW if bx == 0 else 0.5 * TW,
                          0.045 * TW if by == 0 else 0.5 * TW,
                          0.03 * TW)
            span.data.materials.append(wire)
            bpy.context.scene.collection.objects.unlink(span)
            front.objects.link(span)

    check("the rig sees the front layer", rig.has_front_parts(bpy))
    frames = rig.render_wayobj(bpy, OUT, PAKSET, basename="bkwire")
    check("the catenary rendered both layers of all sixteen ribis",
          len(frames) == 32, str(len(frames)))

    _png, dat_path, _pl = rig.build_wayobj_sheet_and_dat(
        frames, OUT, PAKSET, basename="bkwire", cols=8,
        name="BKitAll_Catenary", waytype="track",
        own_waytype="electrified_track", author="simutrans-blender-kit")
    dat = lint(dat_path, "catenary")
    check("it is a way-object, with the hyphen", "obj=way-object" in dat)
    check("and it grants electrification",
          "own_waytype=electrified_track" in dat)


# -------------------------------------------------------------- 5. roadsign
def make_signal():
    clear()
    bpy.ops.mesh.primitive_cylinder_add(radius=0.035 * TW, depth=0.55 * TW,
                                        location=(0.28 * TW, 0.36 * TW, 0.275 * TW))
    post = bpy.context.active_object
    post.data.materials.append(mat(STEEL, "steel"))

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.085 * TW,
                                         location=(0.28 * TW, 0.36 * TW, 0.60 * TW))
    bpy.context.active_object.name = "LAMP"

    def state_setup(bpy_, state):
        lamp = bpy_.data.objects["LAMP"]
        lamp.data.materials.clear()
        lamp.data.materials.append(
            mat(RED if state == roadsigns.STATE_RED else GREEN,
                "aspect_%d" % state))

    frames = rig.render_roadsign(bpy, OUT, PAKSET, basename="bksignal",
                                 states=2, state_setup=state_setup)
    check("the signal rendered four directions x two aspects", len(frames) == 8,
          str(len(frames)))

    _png, dat_path, _pl = rig.build_roadsign_sheet_and_dat(
        frames, OUT, PAKSET, basename="bksignal", cols=4,
        name="BKitAll_Signal", waytype="track", is_signal=1,
        author="simutrans-blender-kit")
    dat = lint(dat_path, "signal")
    check("state 0 exists for every direction",
          all(("image[%s][0]=" % d) in dat for d in roadsigns.SIGN_DIRS), dat)


def main():
    os.makedirs(OUT, exist_ok=True)
    print("\n=== %s, one object of every type ===\n" % PAKSET)
    for label, fn in (("vehicle", make_loco), ("building", make_house),
                      ("way", make_road), ("way-object", make_catenary),
                      ("roadsign", make_signal)):
        print("--- %s" % label)
        fn()

    print("\nout: %s" % OUT)
    if FAILED:
        print("\nDEMO_ALL_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nDEMO_ALL_OK")


main()
