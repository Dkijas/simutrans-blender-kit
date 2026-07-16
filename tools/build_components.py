"""Build the shipped component catalogue, from geometry defined here.

    blender --background --factory-startup --python tools/build_components.py

WHY THE COMPONENTS ARE BUILT AND NOT COMMITTED AS ART
    We ship no third-party art, and "we modelled it ourselves" is a claim that
    should be checkable rather than asserted. Every component below is a few dozen
    lines of primitives in this file - so the provenance IS the source, the licence
    is unambiguous (this repo's), and anyone can regenerate the .blend and get the
    same thing.

    It also means a reviewer can read what a bogie is instead of opening a binary.

THE ANCHOR IS THE POINT
    Each component's anchor says where its origin should land when it is inserted,
    in TILE-relative units. A bogie that arrives under the axle rather than at the
    world origin is the entire value of a component library; getting that number
    right, once, here, is what saves the artist getting it right every time.

These are deliberately plain. They are joinery, not art: something to hang a body
on, at the right height, pointing the right way. An artist will replace them.
"""

import json
import math
import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import components, paksets                            # noqa: E402

OUT = os.path.join(_ROOT, "components")

# One tile is 2.0 Blender units in every shipped profile (paksets.py: tile_world
# is "pure convention - it only has to be consistent with ortho_scale"). A pak128
# tile is ~40 m by pak128's own convention, so a metre is about 0.05 units. Every
# size below is written in METRES and converted once, here, because a bogie is
# 2.5 m long and nobody thinks in Blender units.
TILE = paksets.get("pak128").tile_world
M = TILE / 40.0

AUTHOR = "simutrans-blender-kit"
LICENSE = "MIT"
VERSION = "1.0.0"


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def box(col, name, size, at, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=at)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    if rot:
        ob.rotation_euler = rot
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob


def cyl(col, name, radius, depth, at, rot=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=at,
                                        vertices=16)
    ob = bpy.context.active_object
    ob.name = name
    if rot:
        ob.rotation_euler = rot
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob


# --- the components ----------------------------------------------------------

def wheelset(col):
    """Two wheels on an axle. 0.92 m wheels, 1.435 m gauge - standard gauge,
    which is what pak128's track is drawn as."""
    r = 0.46 * M
    half = 0.7175 * M           # half of 1.435 m
    x = (math.pi / 2.0, 0.0, 0.0)          # a cylinder stands in Z; lay it along Y
    cyl(col, "wheel_left", r, 0.04 * M, (0, -half, r), x)
    cyl(col, "wheel_right", r, 0.04 * M, (0, half, r), x)
    cyl(col, "axle", 0.06 * M, 1.3 * M, (0, 0, r), x)
    return (0.0, 0.0, 0.0)      # anchor: the rail head, on the centreline


def bogie(col):
    """Two wheelsets in a frame. 2.5 m wheelbase - a short passenger bogie."""
    r = 0.46 * M
    half = 0.7175 * M
    wb = 1.25 * M               # half of a 2.5 m wheelbase
    x = (math.pi / 2.0, 0.0, 0.0)
    for i, dx in enumerate((-wb, wb)):
        cyl(col, "bogie_wheel_%d_l" % i, r, 0.04 * M, (dx, -half, r), x)
        cyl(col, "bogie_wheel_%d_r" % i, r, 0.04 * M, (dx, half, r), x)
        cyl(col, "bogie_axle_%d" % i, 0.06 * M, 1.3 * M, (dx, 0, r), x)
    box(col, "bogie_frame_l", (3.0 * M, 0.12 * M, 0.30 * M), (0, -half, r + 0.1 * M))
    box(col, "bogie_frame_r", (3.0 * M, 0.12 * M, 0.30 * M), (0, half, r + 0.1 * M))
    box(col, "bogie_bolster", (0.5 * M, 1.5 * M, 0.25 * M), (0, 0, r + 0.35 * M))
    return (0.0, 0.0, 0.0)


def pantograph(col):
    """A single-arm pantograph, folded to about 4 m - roughly where a pak128
    catenary's contact wire sits above the rail."""
    h = 3.9 * M
    box(col, "panto_base", (1.2 * M, 1.0 * M, 0.12 * M), (0, 0, 0.06 * M))
    box(col, "panto_lower", (1.6 * M, 0.10 * M, 0.10 * M),
        (0.2 * M, 0, h * 0.42), (0.0, math.radians(-52), 0.0))
    box(col, "panto_upper", (1.5 * M, 0.08 * M, 0.08 * M),
        (-0.35 * M, 0, h * 0.80), (0.0, math.radians(48), 0.0))
    box(col, "panto_shoe", (0.25 * M, 1.9 * M, 0.06 * M), (-0.7 * M, 0, h))
    # anchor: the roof. The artist puts it where their roof is - so it lands at
    # z=0 and gets lifted, rather than pretending we know their roof height.
    return (0.0, 0.0, 0.0)


def headlight(col):
    """A round lamp in a shallow housing. 0.25 m across."""
    r = 0.125 * M
    y = (0.0, math.radians(90), 0.0)       # face +X, the vehicle's nose
    cyl(col, "headlight_housing", r, 0.12 * M, (0, 0, 0), y)
    cyl(col, "headlight_lens", r * 0.8, 0.02 * M, (0.07 * M, 0, 0), y)
    return (0.0, 0.0, 0.0)


def coupler(col):
    """A centre buffer coupler, at 1.06 m - UIC height above the rail."""
    h = 1.06 * M
    box(col, "coupler_shank", (0.8 * M, 0.16 * M, 0.16 * M), (0, 0, h))
    box(col, "coupler_head", (0.3 * M, 0.42 * M, 0.34 * M), (0.45 * M, 0, h))
    return (0.0, 0.0, 0.0)


CATALOGUE = (
    ("wheelset", "Wheelset", "wheel", wheelset,
     "Two 0.92 m wheels on an axle at 1.435 m gauge. Origin at the rail head, "
     "on the centreline: put it where the axle goes and it sits on the rail."),
    ("bogie_2axle", "Two-axle bogie", "bogie", bogie,
     "A short passenger bogie: two wheelsets at a 2.5 m wheelbase, in a frame, "
     "with a bolster to hang a body from. Origin at the rail head."),
    ("pantograph_single", "Single-arm pantograph", "pantograph", pantograph,
     "Folded to about 4 m, which is roughly where pak128's catenary contact "
     "wire runs. Origin at its base: lift it to your roof."),
    ("headlight_round", "Round headlight", "headlight", headlight,
     "A 0.25 m lamp facing +X - the vehicle's nose. Give the lens the Headlight "
     "material and it lights up after dark."),
    ("coupler_centre", "Centre coupler", "coupler", coupler,
     "A centre buffer coupler at UIC height (1.06 m above the rail). Origin at "
     "the rail head, so it lands at the right height on its own."),
)


def build_one(key, name, category, fn, note):
    d = os.path.join(OUT, key)
    os.makedirs(d, exist_ok=True)
    clear()
    col = collection(category)
    anchor = fn(col)
    blend = os.path.join(d, "%s.blend" % key)
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    meta = {
        "schema_version": components.SCHEMA_VERSION,
        "key": key, "name": name, "category": category,
        "author": AUTHOR, "license": LICENSE, "version": VERSION,
        "blend": "%s.blend" % key,        # relative to this sidecar, always
        "collection": category,
        "anchor": list(anchor),
        "pakset": "",                     # a tile is 2.0 units everywhere
        "note": note,
    }
    with open(os.path.join(d, components.SIDECAR), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    made = []
    for key, name, category, fn, note in CATALOGUE:
        made.append(build_one(key, name, category, fn, note))
        print("  built %s" % key)

    comps = components.catalogue(OUT)
    findings = components.check_catalogue(comps)
    errors = [f for f in findings if f.level == components.ERROR]
    for f in findings:
        print("  %-11s %s" % (f.level, f.message))
    if errors:
        print("COMPONENTS_BUILD_FAILED: %d error(s)" % len(errors))
        sys.exit(1)
    if len(comps) != len(CATALOGUE):
        print("COMPONENTS_BUILD_FAILED: built %d, catalogue reads %d"
              % (len(CATALOGUE), len(comps)))
        sys.exit(1)
    print("COMPONENTS_BUILD_OK: %d components" % len(comps))


if __name__ == "__main__":
    main()
