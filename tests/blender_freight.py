"""Cargo variants (freight images), end to end, inside Blender.

    blender --background --python tests/blender_freight.py

A wagon can show a different sprite depending on what it carries: empty, or
loaded with coal, or loaded with oil. The engine keeps them in
emptyimage[dir] and freightimage[i][dir], picks the empty one when the vehicle
is unloaded and the matching freight one when it is not (vehicle_desc.h
get_image_id), and demands a freightimagetype[i]=<good> for each - it FATALs in
makeobj without them.

The kit renders these the same additive way it does seasons: the base vehicle
is whatever sits outside the freight_ collections, and freight_0, freight_1, ...
each hold one cargo's load. This test does not trust that arrangement - it
renders the set and PROVES the load is really there, by demanding the empty
sprite and each loaded sprite differ pixel for pixel, and that the two loads
differ from each other. A freight_setup that quietly did nothing would ship
three identical sheets, the .pak would compile, and every wagon would look empty
however much coal it carried.

Prints FREIGHT_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                                        # noqa: E402
from core import paksets, schema, sheet                      # noqa: E402

OUT = os.path.join(_ROOT, "build", "freight")
PAKSET = "pak128"
GOODS = ["Kohle", "Oel"]      # real pak128 goods, so this data also drives the game test
FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def _box(name, sx, sy, sz, z0, mat):
    """An axis-aligned box, sx*sy*sz Blender units, sitting with its base at z0."""
    x, y, z = sx / 2.0, sy / 2.0, sz / 2.0
    verts = [(-x, -y, z0), (x, -y, z0), (x, y, z0), (-x, y, z0),
             (-x, -y, z0 + sz), (x, -y, z0 + sz), (x, y, z0 + sz), (-x, y, z0 + sz)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    return bpy.data.objects.new(name, mesh)


def build_wagon():
    """A flatbed (always there) plus one load per freight_ collection.

    The base wagon sits outside every freight_ collection so it is in every
    render. freight_0 heaps a low, wide load (coal); freight_1 stacks a tall,
    narrow one (oil drums) - deliberately different silhouettes so a rendered
    difference cannot be a fluke of colour alone.
    """
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)

    body = rig.make_special_color_material(bpy, (60, 60, 66), name="wagon_body")
    coal = rig.make_special_color_material(bpy, (30, 30, 30), name="coal")
    oil = rig.make_special_color_material(bpy, (120, 90, 40), name="oil")

    # the flatbed: nose along +X, centred, standing on z = 0
    bpy.context.scene.collection.objects.link(
        _box("flatbed", 2.4, 1.2, 0.5, 0.0, body))

    c0 = bpy.data.collections.new("%s0" % rig.FREIGHT_COLLECTION_PREFIX)
    bpy.context.scene.collection.children.link(c0)
    c0.objects.link(_box("coal_load", 2.0, 1.0, 0.4, 0.5, coal))   # low, wide

    c1 = bpy.data.collections.new("%s1" % rig.FREIGHT_COLLECTION_PREFIX)
    bpy.context.scene.collection.children.link(c1)
    c1.objects.link(_box("oil_load", 0.8, 0.8, 1.3, 0.5, oil))     # tall, narrow


def alpha_of(path):
    _w, _h, _a, px = sheet.read_png(path)
    return [p[3] for p in px]


def pixels_of(path):
    _w, _h, _a, px = sheet.read_png(path)
    return px


def differ(a_path, b_path):
    """Do two rendered sprites differ at all? (silhouette or colour.)"""
    return pixels_of(a_path) != pixels_of(b_path)


def main():
    build_wagon()

    check("two freight_ collections found",
          rig.freight_variant_count(bpy) == 2,
          str(rig.freight_variant_count(bpy)))

    empty, variants = rig.render_freight_variants(
        bpy, OUT, PAKSET, dirs=8, basename="bkithopper")
    check("empty rendered in 8 headings", len(empty) == 8, str(len(empty)))
    check("two freight variants rendered", len(variants) == 2, str(len(variants)))
    for i, v in enumerate(variants):
        check("freight %d rendered in 8 headings" % i, len(v) == 8, str(len(v)))

    # THE ORACLE: the load must actually show. Compare the same heading across the
    # empty and loaded renders - if freight_setup did nothing they would be equal.
    empty_by_dir = dict(empty)
    for i, v in enumerate(variants):
        v_by_dir = dict(v)
        diffs = sum(1 for d in empty_by_dir
                    if differ(empty_by_dir[d], v_by_dir[d]))
        check("freight %d (%s) looks different from empty in every heading"
              % (i, GOODS[i]), diffs == 8,
              "only %d/8 headings changed - the load is not being rendered" % diffs)

    # and the two loads must differ from each other, not just from empty
    coal_by_dir, oil_by_dir = dict(variants[0]), dict(variants[1])
    both = sum(1 for d in coal_by_dir if differ(coal_by_dir[d], oil_by_dir[d]))
    check("the two loads are different pictures", both == 8,
          "coal and oil render the same in %d/8 headings" % (8 - both))

    sheet_png, dat_path, _place = rig.build_freight_sheet_and_dat(
        empty, variants, GOODS, OUT, PAKSET, basename="bkithopper", cols=4,
        name="BKit_Hopper", waytype="track", freight="Kohle", payload=40,
        power=0, weight=18, length=8, cost=50000, runningcost=80,
        author="simutrans-blender-kit")

    with open(dat_path, encoding="utf-8") as f:
        dat = f.read()

    check("dat is a vehicle", "obj=vehicle" in dat)
    check("dat carries the empty images", "EmptyImage[s]=" in dat, dat)
    for i in range(2):
        check("dat carries freightimage[%d]" % i,
              "FreightImage[%d][s]=" % i in dat, dat)
        check("dat maps freightimagetype[%d]=%s" % (i, GOODS[i]),
              "\nfreightimagetype[%d]=%s\n" % (i, GOODS[i]) in dat, dat)
    # the engine numbers freight images 0..N-1 with no holes and demands exactly
    # one type per image; a spare or a gap is a makeobj fatal
    check("exactly one freightimagetype per freight image",
          dat.count("freightimagetype[") == 2, dat)

    findings = schema.lint(dat)
    for f in findings:
        print("       %s" % f)
    check("the .dat lints clean against the engine schema", not findings,
          "%d finding(s)" % len(findings))

    print("\nsheet: %s\ndat:   %s" % (sheet_png, dat_path))
    if FAILED:
        print("\nFREIGHT_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nFREIGHT_OK")


main()
