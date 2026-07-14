"""A way, end to end, inside Blender.

    blender --background --python tests/blender_way.py

A way's sixteen images are six models turned on the tile, and the whole thing
rests on one claim: that turning a piece by a quarter-turn turns its RIBI by a
rotate-left. Get the sense of that rotation backwards and every curve, every
tee and every stub is wrong - while the sheet still looks perfectly plausible,
the .pak still compiles, and the road still appears in game. It just connects to
the wrong neighbours.

So this test does not look at the images and nod. It asks, for every one of the
sixteen, WHERE THE ASPHALT ACTUALLY REACHES.

The engine's projection is exact and we already prove elsewhere that our camera
reproduces it (project_camera == project_engine at z = 0). So the midpoint of the
tile's north edge lands at a known pixel, and so do east, south and west. Sample
those four pixels and the image itself tells you which directions it connects to.
That has to equal the ribi it was rendered for - all four bits, all sixteen
images, no exceptions.

Prints WAY_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                                       # noqa: E402
from core import colors, paksets, projection, schema, sheet, ways   # noqa: E402

OUT = os.path.join(_ROOT, "build", "way")
PAKSET = "pak128"
FAILED = []

ARM_HALF_WIDTH = 0.13      # tile units - the asphalt is a strip, not the whole tile
PROBE_AT = 0.40            # how far out to sample: just inside the tile edge
PROBE_RADIUS_PX = 4


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def _slab(name, x0, x1, y0, y1, tile_world, mat):
    """A flat rectangle of asphalt, given in TILE units (the tile is -0.5..+0.5)."""
    s = tile_world
    verts = [(x0 * s, y0 * s, 0.0), (x1 * s, y0 * s, 0.0),
             (x1 * s, y1 * s, 0.0), (x0 * s, y1 * s, 0.0)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    return ob


def build_road():
    """The six shapes, one per collection - exactly what an artist would model.

    Each is a strip of asphalt running from the centre of the tile out to the
    edges its base ribi names, IN BLENDER'S AXES: north is +Y, east is +X. The
    engine's own grid has y growing southward and is left-handed, so it is not a
    frame you can model in - see projection.WORLD_AZIMUTH_DEG.
    """
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)

    pak = paksets.get(PAKSET)
    tw = pak.tile_world
    w = ARM_HALF_WIDTH

    asphalt = rig.make_special_color_material(bpy, (70, 70, 76), name="asphalt")
    # a stripe down the middle in a player colour, so we also prove that a way's
    # reserved colours survive the render exactly as a vehicle's do
    paint = rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3],
                                            name="way_paint")

    # centre patch, then one arm per direction bit, in TILE units and BLENDER axes
    # (north = +Y). Each arm is a strip from the tile centre out to one edge.
    ARMS = {
        ways.NORTH: (-w, w, -w, 0.5),
        ways.EAST:  (-w, 0.5, -w, w),
        ways.SOUTH: (-w, w, -0.5, w),
        ways.WEST:  (-0.5, w, -w, w),
    }

    for piece, base in ways.PIECES:
        col = bpy.data.collections.new(rig.WAY_COLLECTION_PREFIX + piece)
        bpy.context.scene.collection.children.link(col)

        col.objects.link(_slab("%s_hub" % piece, -w, w, -w, w, tw, asphalt))
        for bit, (x0, x1, y0, y1) in ARMS.items():
            if base & bit:
                col.objects.link(
                    _slab("%s_%d" % (piece, bit), x0, x1, y0, y1, tw, asphalt))

        # the centre stripe: small, and only on the pieces that have a through road
        if base in (ways.NORTH | ways.SOUTH, 0xF):
            col.objects.link(
                _slab("%s_paint" % piece, -0.02, 0.02, -0.45, 0.45, tw, paint))


def probe_pixel(tile_px, bit):
    """Where the midpoint of the tile edge for this direction bit lands, in the cell.

    project_engine IS the engine's projection, and the tile's ground centre sits at
    TILE_CENTRE_IN_CELL of the cell - that is the whole mapping, and it is the same
    one the vehicle and the building already ride on.
    """
    dx, dy = ways.RIBI_ENGINE_VECTOR[bit]      # the ENGINE's grid: y grows south
    sx, sy = projection.project_engine(dx * PROBE_AT, dy * PROBE_AT, tile_px)
    cx = projection.TILE_CENTRE_IN_CELL[0] * tile_px + sx
    cy = projection.TILE_CENTRE_IN_CELL[1] * tile_px + sy
    return (int(round(cx)), int(round(cy)))


def connects(path, tile_px, bit):
    """Does the rendered image actually have asphalt at that tile edge?"""
    w, h, alpha, px = sheet.read_png(path)
    cx, cy = probe_pixel(tile_px, bit)
    hits = total = 0
    for dy in range(-PROBE_RADIUS_PX, PROBE_RADIUS_PX + 1):
        for dx in range(-PROBE_RADIUS_PX, PROBE_RADIUS_PX + 1):
            x, y = cx + dx, cy + dy
            if not (0 <= x < w and 0 <= y < h):
                continue
            total += 1
            p = px[y * w + x]
            if not alpha or p[3] > 0:
                hits += 1
    return total and hits * 2 > total          # majority of the probe is covered


def main():
    pak = paksets.get(PAKSET)
    tile_px = pak.tile_px
    build_road()

    plan = ways.plan()
    check("six models cover all sixteen ribis, once each",
          sorted(r for r, _n, _t in plan) == list(range(16)),
          str(sorted(r for r, _n, _t in plan)))
    check("a road with no cross piece is blind at four-way junctions",
          ways.missing(("none", "end", "straight", "curve", "tee")) == [15])

    frames = rig.render_way(bpy, OUT, PAKSET, basename="bkitroad")
    check("sixteen images rendered", len(frames) == 16, str(len(frames)))

    by_ribi = dict(frames)

    # THE ORACLE. For every image, the asphalt must reach exactly the tile edges
    # its ribi names - and no others.
    for ribi in range(16):
        path = by_ribi[ribi]
        got = 0
        for bit in (ways.NORTH, ways.EAST, ways.SOUTH, ways.WEST):
            if connects(path, tile_px, bit):
                got |= bit
        check("image[%s]: the road really connects %s (not %s)"
              % (ways.code(ribi), ways.code(ribi) or "nothing",
                 ways.code(got) or "nothing"),
              got == ribi,
              "rendered %r but the asphalt reaches %r" % (ways.code(ribi),
                                                          ways.code(got)))

    # if the rotation were a no-op we would be shipping sixteen copies of one image
    distinct = {tuple(sheet.read_png(p)[3]) for _r, p in frames}
    check("the turned images are actually different", len(distinct) == 16,
          "%d distinct images out of 16 - the model is not turning" % len(distinct))

    for ribi, path in frames:
        w, h, alpha, _px = sheet.read_png(path)
        check("image[%s] is one tile (%dx%d RGBA)"
              % (ways.code(ribi), tile_px, tile_px),
              (w, h) == (tile_px, tile_px) and alpha, "%dx%d" % (w, h))

    sheet_png, dat_path, placement = rig.build_way_sheet_and_dat(
        frames, OUT, PAKSET, basename="bkitroad", cols=4,
        name="BKit_Road", waytype="road", topspeed=80, cost=100, maintenance=10,
        author="simutrans-blender-kit")

    with open(dat_path, encoding="utf-8") as f:
        dat = f.read()

    check("dat is a way", "obj=way" in dat)
    check("dat is a road", "waytype=road" in dat)
    # way_writer.cc:95 fatals without this one, and only this one
    check("dat carries the mandatory image[-]", "image[-]=" in dat, dat)
    check("dat carries every ribi",
          all(("image[%s]=" % ways.code(r)) in dat for r in range(16)), dat)
    # and the one that makeobj will NOT tell you about (builder/wegbauer.cc:123)
    check("dat carries an icon, or the way cannot be built at all",
          "icon=" in dat, dat)

    findings = schema.lint(dat)
    for f in findings:
        print("       %s" % f)
    check("the .dat lints clean against the engine schema", not findings,
          "%d finding(s)" % len(findings))

    # and the linter must actually catch the missing icon - it is the whole point
    without_icon = "\n".join(l for l in dat.splitlines()
                             if not l.startswith("icon="))
    check("the linter catches a way with no icon",
          any(f.level == "error" and "icon" in f.message
              for f in schema.lint(without_icon)),
          "it would have shipped an unbuildable road in silence")

    _sw, _sh, salpha, spx = sheet.read_png(sheet_png)
    rgb = [(p[0], p[1], p[2]) for p in spx if not (salpha and p[3] == 0)]
    check("the player-colour centre line survived", bool(colors.scan(rgb)),
          "no reserved colour in the sheet")

    print("\nsheet: %s\ndat:   %s" % (sheet_png, dat_path))
    if FAILED:
        print("\nWAY_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nWAY_OK")


main()
