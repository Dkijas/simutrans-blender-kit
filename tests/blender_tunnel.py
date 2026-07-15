"""A tunnel portal, end to end, inside Blender.

    blender --background --python tests/blender_tunnel.py

A tunnel is a portal drawn in four directions and two layers: backimage[dir]
behind the vehicle (the mouth in the hillside) and frontimage[dir] over it (the
arch it passes under). This renders both and proves the machinery works:

- four back images, and they are FOUR DIFFERENT pictures (the model is really
  turned, not copied),
- a front image per direction, each DIFFERENT from its back (the two layers are
  genuinely separate - a front piece left in the back list is the catenary trap,
  a train driving over its own portal),
- a .dat that names all four back and all four front portals plus the mandatory
  icon, and lints clean.

Which physical hill each portal key lands on (tunnels.PORTAL_TURNS) is DERIVED
from the engine's slope_indices but is a reflection the way slopes taught us to
confirm in game, not in Blender - that check lives in the game scenario. This
test is about the rendering, not the mapping.

Prints TUNNEL_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                                        # noqa: E402
from core import paksets, schema, sheet, tunnels             # noqa: E402

OUT = os.path.join(_ROOT, "build", "tunnel")
PAKSET = "pak128"
FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def _box(name, sx, sy, sz, x0, y0, z0, mat, col):
    x, y = sx / 2.0, sy / 2.0
    verts = [(x0 - x, y0 - y, z0), (x0 + x, y0 - y, z0),
             (x0 + x, y0 + y, z0), (x0 - x, y0 + y, z0),
             (x0 - x, y0 - y, z0 + sz), (x0 + x, y0 - y, z0 + sz),
             (x0 + x, y0 + y, z0 + sz), (x0 - x, y0 + y, z0 + sz)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    col.objects.link(bpy.data.objects.new(name, mesh))


def build_portal():
    """A portal modelled on a north-facing hill: back = the mouth walls, front =
    the lintel over the opening. Deliberately asymmetric (offset toward +Y, the
    north / open side) so the four camera turns give four different pictures."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)

    pak = paksets.get(PAKSET)
    tw = pak.tile_world
    stone = rig.make_special_color_material(bpy, (95, 88, 80), name="portal_stone")
    arch = rig.make_special_color_material(bpy, (60, 55, 50), name="portal_arch")

    back = bpy.data.collections.new(rig.TUNNEL_COLLECTION_PREFIX + "portal")
    bpy.context.scene.collection.children.link(back)
    # two jambs either side of the mouth, on the north (open, +Y) half of the tile
    _box("jamb_l", 0.12 * tw, 0.5 * tw, 0.5 * tw, -0.22 * tw, 0.15 * tw, 0.0,
         stone, back)
    _box("jamb_r", 0.12 * tw, 0.5 * tw, 0.5 * tw, 0.22 * tw, 0.15 * tw, 0.0,
         stone, back)
    # the hillside behind, filling the south half and rising
    _box("hill", 0.9 * tw, 0.4 * tw, 0.8 * tw, 0.0, -0.3 * tw, 0.0, stone, back)

    front = bpy.data.collections.new(rig.TUNNEL_COLLECTION_PREFIX + "portal_front")
    bpy.context.scene.collection.children.link(front)
    # the lintel across the top of the opening - the part that occludes the train
    _box("lintel", 0.6 * tw, 0.16 * tw, 0.14 * tw, 0.0, 0.30 * tw, 0.42 * tw,
         arch, front)


def alpha_of(path):
    _w, _h, _a, px = sheet.read_png(path)
    return [p[3] for p in px]


def main():
    build_portal()

    check("the portal collection is there", rig.has_tunnel_model(bpy))

    portals = rig.render_tunnel_portals(bpy, OUT, PAKSET, basename="bkittunnel")
    check("four back portals rendered", len(portals["back"]) == 4,
          str(len(portals["back"])))
    check("four front portals rendered", len(portals["front"]) == 4,
          str(len(portals["front"])))

    # THE ORACLE (for the rendering): the four turns must be four DIFFERENT images,
    # or the model is not really being turned.
    back_pics = {tuple(alpha_of(p)) for _d, p in portals["back"]}
    check("the four back portals are four different pictures", len(back_pics) == 4,
          "%d distinct of 4 - the portal is not turning" % len(back_pics))

    # and each direction's front layer must differ from its back, or the split did
    # nothing and the arch is buried behind the vehicle
    back_by_dir = dict(portals["back"])
    front_by_dir = dict(portals["front"])
    diffs = sum(1 for d in tunnels.DIRS
                if sheet.read_png(back_by_dir[d])[3]
                != sheet.read_png(front_by_dir[d])[3])
    check("front and back differ in every direction", diffs == 4,
          "only %d/4 directions have a distinct front layer" % diffs)

    sheet_png, dat_path, _back = rig.build_tunnel_sheet_and_dat(
        portals, OUT, PAKSET, basename="bkittunnel", icon_dir="s",
        name="BKit_Tunnel", waytype="track", topspeed=120, cost=50000,
        maintenance=500, author="simutrans-blender-kit")

    with open(dat_path, encoding="utf-8") as f:
        dat = f.read()

    check("dat is a tunnel", "obj=tunnel" in dat)
    check("dat carries all four back portals",
          all(("backimage[%s]=" % d) in dat for d in tunnels.DIRS), dat)
    check("dat carries all four front portals",
          all(("frontimage[%s]=" % d) in dat for d in tunnels.DIRS), dat)
    check("dat carries an icon, or the tunnel cannot be built",
          "\nicon=" in dat, dat)

    findings = schema.lint(dat)
    for f in findings:
        print("       %s" % f)
    check("the tunnel .dat lints clean", not findings, "%d finding(s)" % len(findings))

    print("\nsheet: %s\ndat:   %s" % (sheet_png, dat_path))
    if FAILED:
        print("\nTUNNEL_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nTUNNEL_OK")


main()
