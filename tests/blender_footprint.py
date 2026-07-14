"""Does a building face its road, and does a big one sit on its own plot?

    blender --background --python tests/blender_footprint.py

Two questions that the existing building test cannot answer, because it only ever
builds a 1x1 house and only ever asks whether the four layouts came out DIFFERENT.
Different is easy. Right is not.

  A. WHICH WAY DOES IT FACE?  A layout is the building turned to face the road,
     and the road for layout L is at simcity's neighbors[L]: south, east, north,
     west. If our turn goes the wrong way round, layouts 1 and 3 swap - every
     house still renders, still compiles, still plants, and stands with its back
     to the street.

     Probe: a post offset toward the facade. Its screen position must move exactly
     as the engine's own projection of neighbors[L] says it should. The post's
     HEIGHT shifts it up the screen by the same amount in every layout, so that
     term cancels the moment we compare layouts against each other - which is
     what makes this a clean measurement rather than an argument.

  B. DOES A 2x1 STAY ON ITS PLOT?  The engine anchors a building at tile (0,0)
     and grows it into +x/+y, so turning it is a turn about the footprint's
     CENTRE. Turn it about the corner tile instead and it swings off the plot;
     the slicer then cuts the cells out of the wrong part of the render. A 1x1
     building's centre IS its corner, which is why this hid for so long.

     Probe: paint the building's EAST half. Follow that paint through the four
     layouts and it must land in the cell the engine would look for it in.

Prints FOOTPRINT_OK on success.
"""

import math
import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                                   # noqa: E402
from core import buildings, paksets, projection, sheet  # noqa: E402

OUT = os.path.join(_ROOT, "build", "footprint")
PAKSET = "pak128"
FAILED = []

# world/simcity.cc:2914 - the road for layout L, in ENGINE tile steps (y is south)
NEIGHBORS = ((0, 1), (1, 0), (0, -1), (-1, 0))

POST_AT = 0.30          # tiles from the building centre, toward the facade
MARK = (250, 140, 20)   # the post, and the painted half: a colour nothing else uses


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def _pixels_of(path, rgb, tol=30):
    """-> [(x, y)] of every pixel of that colour."""
    w, h, alpha, px = sheet.read_png(path)
    out = []
    for y in range(h):
        for x in range(w):
            p = px[y * w + x]
            if alpha and p[3] == 0:
                continue
            if all(abs(p[i] - rgb[i]) < tol for i in range(3)):
                out.append((x, y))
    return out


def centroid(path, rgb, tol=30):
    hits = _pixels_of(path, rgb, tol)
    if not hits:
        return None
    return (sum(p[0] for p in hits) / float(len(hits)),
            sum(p[1] for p in hits) / float(len(hits)))


def count(path, rgb, tol=30):
    """How much of that colour is in this cell.

    Not "is any of it here": a building is TALL, so it projects up the screen and
    a tile's image always catches a little of its neighbour. Ask which cell holds
    MOST of the paint, or you end up measuring the order you happened to search in
    - which is how two of these checks passed while being wrong.
    """
    return len(_pixels_of(path, rgb, tol))


# --------------------------------------------------------------- A. facing
def build_facing_scene(tw):
    """A squat house with a tall post toward the FACADE, which is -Y in Blender.

    The post has to clear the roof: a marker down at ground level would be hidden
    behind the house in the two layouts where the facade points away from the
    camera, and we would be measuring occlusion instead of orientation. (The
    building test already learned that lesson the hard way, with a lamp.)
    """
    clear()
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
    body = bpy.context.active_object
    body.scale = (1.5, 1.5, 1.0)

    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.12 * tw, depth=0.5,
        location=(0.0, -POST_AT * tw, 1.6))       # -Y = south = the facade side
    post = bpy.context.active_object
    post.name = "FACADE_POST"
    post.data.materials.append(rig.make_special_color_material(bpy, MARK, name="mark"))


def test_facing():
    pak = paksets.get(PAKSET)
    t = pak.tile_px
    build_facing_scene(pak.tile_world)

    rig.render_building(bpy, OUT, PAKSET, basename="facing",
                        size_x=1, size_y=1, layouts=4)

    # where the engine says the post should be, relative to the building centre
    want = {}
    for L in range(4):
        vx, vy = NEIGHBORS[L]
        want[L] = projection.project_engine(vx * POST_AT, vy * POST_AT, t)

    got = {}
    for L in range(4):
        big = os.path.join(OUT, "facing_full_%d_0_0.png" % L)
        c = centroid(big, MARK)
        if c is None:
            check("layout %d: the post is visible" % L, False, "not found in %s" % big)
            return
        _w, _h, ground = buildings.canvas(1, 1, L, 1, t)
        got[L] = (c[0] - ground[0], c[1] - ground[1])

    # The post's height lifts it up the screen by the same amount in every layout,
    # so subtract the mean and the height term is gone - no need to know it.
    def centred(d):
        mx = sum(v[0] for v in d.values()) / 4.0
        my = sum(v[1] for v in d.values()) / 4.0
        return {k: (v[0] - mx, v[1] - my) for k, v in d.items()}

    cw, cg = centred(want), centred(got)
    for L in range(4):
        err = math.hypot(cg[L][0] - cw[L][0], cg[L][1] - cw[L][1])
        check("layout %d faces its road (%s)" % (L, ("south", "east", "north",
                                                     "west")[L]),
              err < 6.0,
              "the post is %.1f px from where neighbors[%d] puts it; "
              "measured %s, the engine wants %s"
              % (err, L, tuple(round(v, 1) for v in cg[L]),
                 tuple(round(v, 1) for v in cw[L])))


# ------------------------------------------------------------ B. footprint
def build_wide_scene(tw):
    """A 2x1 house: two tiles east-west, with the EAST tile painted."""
    clear()
    # tile (0,0) is at the Blender origin; tile (1,0) is one tile EAST (+X)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, 0.0, 0.6))
    west = bpy.context.active_object
    west.scale = (0.85 * tw, 0.85 * tw, 1.2)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(tw, 0.0, 0.6))
    east = bpy.context.active_object
    east.scale = (0.85 * tw, 0.85 * tw, 1.2)
    east.data.materials.append(
        rig.make_special_color_material(bpy, MARK, name="mark"))


def test_footprint():
    pak = paksets.get(PAKSET)
    build_wide_scene(pak.tile_world)

    frames = rig.render_building(bpy, OUT, PAKSET, basename="wide",
                                 size_x=2, size_y=1, layouts=4)
    by_key = dict(frames)

    for L in range(4):
        w, h = buildings.footprint(2, 1, L)
        want = (1, 2) if L & 1 else (2, 1)
        check("layout %d: the footprint transposes to %dx%d" % (L, want[0], want[1]),
              (w, h) == want, "%dx%d" % (w, h))

    # Follow the painted EAST half round the four turns. The model turns +90 per
    # layout (Blender, where +Y is north), so east -> north -> west -> south, and
    # the engine's y grows SOUTHWARD:
    #
    #   L0  the paint is still east          -> tile (1,0) of a 2x1
    #   L1  it has turned to the north       -> the SMALLER y of a 1x2: (0,0)
    #   L2  it has turned to the west        -> tile (0,0) of a 2x1
    #   L3  it has turned to the south       -> the LARGER y of a 1x2:  (0,1)
    painted = {0: (1, 0), 1: (0, 0), 2: (0, 0), 3: (0, 1)}

    for L in range(4):
        w, h = buildings.footprint(2, 1, L)
        tally = {}
        for y in range(h):
            for x in range(w):
                key = (L, x, y, 0, 0, 0)
                if key in by_key:
                    tally[(x, y)] = count(by_key[key], MARK)
        found = max(tally, key=tally.get) if any(tally.values()) else None
        check("layout %d: the painted half lands on tile %s" % (L, painted[L]),
              found == painted[L],
              "most of the paint is on %s (counts %s) - the building has swung off "
              "its own plot" % (found, tally))


def main():
    test_facing()
    test_footprint()
    if FAILED:
        print("\nFOOTPRINT_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nFOOTPRINT_OK")


main()
