"""Alignment and lighting, checked inside Blender against the engine's own rules.

    blender --background --python tests/blender_alignment.py

Two things no unit test can prove, because they only exist once pixels are on
disk:

  1. ALIGNMENT. The ground at the tile centre must land at (1/2, 3/4) of the
     cell - measured from pak128's marker.png, see core/projection.py. So render
     an actual tile-sized quad at z=0 and check where its diamond falls. Get this
     wrong and every vehicle floats above the rail or sinks into it.

  2. LIGHTING. The engine lets a vehicle ship only 4 images and REUSES
     image[dir-4] for the opposite heading (vehicle_desc.h) - it does not mirror
     it. That is only correct if a 180-degree-symmetric vehicle renders
     IDENTICALLY in opposite headings, which in turn is only true if the sun is
     fixed to the screen, not to the world. So render a plain box and demand the
     four opposite pairs come out pixel-for-pixel equal.

Prints ALIGN_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                              # noqa: E402
from core import directions, paksets, projection, sheet   # noqa: E402

OUT = os.path.join(_ROOT, "build", "align")
PAKSET = "pak128"
FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def opaque_bbox(path):
    w, h, alpha, px = sheet.read_png(path)
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            p = px[y * w + x]
            if alpha and p[3] == 0:
                continue
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return (min(xs), max(xs), min(ys), max(ys))


def test_alignment(pak):
    """Render THE TILE ITSELF and see where it lands in the cell."""
    clear()
    rig.build_rig(bpy, PAKSET)

    # a quad exactly one tile across, lying on the ground
    bpy.ops.mesh.primitive_plane_add(size=pak.tile_world, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.data.materials.append(rig.make_special_color_material(bpy, (255, 0, 0)))

    path = os.path.join(OUT, "tile.png")
    os.makedirs(OUT, exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

    bb = opaque_bbox(path)
    check("the tile quad rendered at all", bb is not None)
    if bb is None:
        return
    x1, x2, y1, y2 = bb
    t = pak.tile_px
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0

    print("       diamond: x %d..%d  y %d..%d   centre (%.1f, %.1f)"
          % (x1, x2, y1, y2, cx, cy))

    # 2:1 diamond, one tile wide and half a tile tall
    check("diamond spans the full cell width", x1 <= 1 and x2 >= t - 2,
          "x %d..%d of %d" % (x1, x2, t))
    check("diamond is half a tile tall", abs((y2 - y1 + 1) - t // 2) <= 2,
          "height %d, expected %d" % (y2 - y1 + 1, t // 2))

    # THE point of the whole exercise
    want_x, want_y = (projection.TILE_CENTRE_IN_CELL[0] * t,
                      projection.TILE_CENTRE_IN_CELL[1] * t)
    check("tile centre is at x = tile_px/2", abs(cx - want_x) <= 1.0,
          "%.1f vs %.1f" % (cx, want_x))
    check("tile centre is at y = 3/4 tile_px (NOT the cell centre)",
          abs(cy - want_y) <= 1.0, "%.1f vs %.1f (cell centre is %.1f)"
          % (cy, want_y, t / 2.0))
    check("the ground really is BELOW the cell centre", cy > t / 2.0 + 4)


def test_opposite_headings_are_identical(pak):
    """The engine reuses image[dir-4]; so opposite headings must MATCH."""
    clear()
    rig.build_rig(bpy, PAKSET)

    # A box has 180-degree rotational symmetry about z whatever its proportions.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.3))
    box = bpy.context.active_object
    box.scale = (0.8, 0.4, 0.3)

    frames = dict(rig.render_directions(bpy, OUT, PAKSET, dirs=8, basename="sym"))

    # What this test is really asking is "does the sun ride with the camera": a
    # sun pinned to the MODEL lights the far heading from the wrong side and the
    # two images come out visibly different.
    #
    # It used to demand the two files be identical BYTE FOR BYTE, and that held
    # only because every material in the kit was emission - a flat colour does not
    # care where the camera is. Now that surfaces are lit, cos(135) and cos(315)
    # are not exact negatives of each other in binary, so the shading lands a
    # single count apart on a few hundred pixels. That is float rounding, not a
    # rig fault. So: the SILHOUETTE must still match exactly (that would catch a
    # camera that moved), and the shading is allowed to differ by one count.
    for near, far in directions.FALLBACK.items():   # n->s, e->w, ne->sw, nw->se
        a = sheet.read_png(frames[near])[3]
        b = sheet.read_png(frames[far])[3]

        cutout = sum(1 for p, q in zip(a, b) if (p[3] > 127) != (q[3] > 127))
        check("%s and %s have the same silhouette" % (far, near), cutout == 0,
              "%d pixels are opaque in one and not the other - the camera moved"
              % cutout)

        worst = 0
        for p, q in zip(a, b):
            for x, y in zip(p, q):
                worst = max(worst, abs(x - y))
        check("%s and %s are shaded the same (the sun rides with the camera)"
              % (far, near), worst <= 1,
              "channels differ by up to %d - the sun is pinned to the model, not "
              "the screen" % worst)


def main():
    pak = paksets.get(PAKSET)
    print("\ntest_alignment")
    test_alignment(pak)
    print("\ntest_opposite_headings_are_identical")
    test_opposite_headings_are_identical(pak)

    if FAILED:
        print("\nALIGN_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nALIGN_OK")


main()
