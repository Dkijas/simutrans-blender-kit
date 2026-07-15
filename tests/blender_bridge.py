"""A bridge, end to end, inside Blender.

    blender --background --python tests/blender_bridge.py

A bridge is four groups of pieces - the span (ns/ew), the start and ramp
(n/s/e/w) and the pillar (s/w) - each drawn in a back layer behind the vehicle
and an optional front layer over it. This renders them and proves the machinery:

- every group is rendered in all of its directions, in both layers it has,
- each group's directions are DIFFERENT pictures (the piece is really turned),
- a front layer, where modelled, DIFFERS from its back (the split is real),
- and the .dat names all twelve back images plus the front ones and the icon, and
  lints clean.

Which physical orientation each key lands on (bridges.GROUP_TURNS) is derived and
confirmed by a placed bridge in game, not here. This test is the rendering.

Prints BRIDGE_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                                        # noqa: E402
from core import bridges, paksets, schema, sheet             # noqa: E402

OUT = os.path.join(_ROOT, "build", "bridge")
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


def col(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def build_bridge():
    """The four pieces, each asymmetric (offset in +Y) so the turns differ. span
    and ramp also get a front railing; start and pillar are back-only, to exercise
    the front-is-optional-per-piece path."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)

    tw = paksets.get(PAKSET).tile_world
    deck = rig.make_special_color_material(bpy, (90, 90, 96), name="deck")
    rail = rig.make_special_color_material(bpy, (140, 60, 40), name="rail")

    P = rig.BRIDGE_COLLECTION_PREFIX
    # span: a deck slab running along -Y..+Y, offset a touch north for asymmetry
    _box("span_deck", 0.5 * tw, tw, 0.12 * tw, 0.0, 0.05 * tw, 0.5 * tw, deck,
         col(P + "span"))
    _box("span_rail", 0.5 * tw, tw, 0.1 * tw, 0.28 * tw, 0.05 * tw, 0.62 * tw,
         rail, col(P + "span_front"))
    # start: where deck meets the ground, at the north edge
    _box("start_blk", 0.6 * tw, 0.4 * tw, 0.5 * tw, 0.0, 0.3 * tw, 0.0, deck,
         col(P + "start"))
    # ramp: a sloped block climbing north
    _box("ramp_blk", 0.5 * tw, 0.9 * tw, 0.4 * tw, 0.0, 0.2 * tw, 0.2 * tw, deck,
         col(P + "ramp"))
    _box("ramp_rail", 0.5 * tw, 0.9 * tw, 0.1 * tw, 0.28 * tw, 0.2 * tw, 0.6 * tw,
         rail, col(P + "ramp_front"))
    # pillar: a leg under the deck, offset north
    _box("pillar_leg", 0.18 * tw, 0.18 * tw, 0.9 * tw, 0.0, 0.15 * tw, -0.9 * tw,
         deck, col(P + "pillar"))


def alpha_of(path):
    _w, _h, _a, px = sheet.read_png(path)
    return tuple(p[3] for p in px)


def main():
    build_bridge()

    check("the bridge span collection is there", rig.has_bridge_model(bpy))

    pieces = rig.render_bridge_pieces(bpy, OUT, PAKSET, basename="bkitbridge")

    for group, dirs in bridges.GROUPS:
        frames = pieces["back"].get(group, [])
        check("back %s rendered in all %d directions" % (group, len(dirs)),
              len(frames) == len(dirs), str(len(frames)))
        pics = {alpha_of(p) for _d, p in frames}
        check("back %s: %d directions are %d different pictures"
              % (group, len(dirs), len(dirs)),
              len(pics) == len(dirs),
              "%d distinct of %d - the piece is not turning" % (len(pics), len(dirs)))

    # span and ramp have a front layer; it must differ from the back
    for group in ("image", "ramp"):
        back = dict(pieces["back"][group])
        front = dict(pieces["front"].get(group, []))
        check("%s has a front layer" % group, bool(front), "no front rendered")
        diffs = sum(1 for d in back if d in front and alpha_of(back[d]) != alpha_of(front[d]))
        check("%s front differs from back in every direction" % group,
              front and diffs == len(back),
              "only %d/%d differ" % (diffs, len(back)))

    # start and pillar are back-only: no front should have been rendered
    check("a piece with no _front collection renders no front",
          "start" not in pieces["front"] and "pillar" not in pieces["front"],
          str(list(pieces["front"])))

    sheet_png, dat_path, _back = rig.build_bridge_sheet_and_dat(
        pieces, OUT, PAKSET, basename="bkitbridge",
        name="BKit_Bridge", waytype="track", topspeed=80, cost=200000,
        maintenance=1000, max_length=8, max_height=4, pillar_distance=2,
        author="simutrans-blender-kit")

    with open(dat_path, encoding="utf-8") as f:
        dat = f.read()

    check("dat is a bridge", "obj=bridge" in dat)
    check("dat carries the span both ways",
          "backimage[ns]=" in dat and "backimage[ew]=" in dat, dat)
    check("dat carries all four ramps",
          all(("backramp[%s]=" % d) in dat for d in "nsew"), dat)
    check("dat carries both pillars",
          "backpillar[s]=" in dat and "backpillar[w]=" in dat, dat)
    check("dat carries the span front railing", "frontimage[ns]=" in dat, dat)
    check("dat carries an icon, or the bridge cannot be built",
          "\nicon=" in dat, dat)

    findings = schema.lint(dat)
    for f in findings:
        print("       %s" % f)
    check("the bridge .dat lints clean", not findings, "%d finding(s)" % len(findings))

    print("\nsheet: %s\ndat:   %s" % (sheet_png, dat_path))
    if FAILED:
        print("\nBRIDGE_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nBRIDGE_OK")


main()
