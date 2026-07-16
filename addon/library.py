"""Pulling a component out of its .blend and putting it where it belongs.

core/components.py is the catalogue, the metadata and the rules. This is the six
lines of bpy that actually move geometry, plus the care around them.

Like rig.py and template.py, every function takes `bpy` rather than importing it,
so tests/blender_components.py can drive the whole thing headlessly.

THE THREE MODES ARE NOT INTERCHANGEABLE
    APPEND    a real copy. Yours forever, diverges forever, renders anywhere -
              including on the machine of whoever you send the project to.
    LINK      the .blend stays the master: fix the bogie once, every user gets
              it. And it must still be on disk at render time, which it will not
              be for anyone you send the project to. That is not a bug, it is the
              trade, and the artist is the one who knows which they want.
    INSTANCE  one mesh, many empties pointing at it. Eight bogies, one bogie's
              worth of memory.

    The panel offers all three because Blender has all three and the difference
    only shows up later - when the file moves, or when the render is due.

WHAT THIS WILL NOT DO
    It will not insert a component that core/components.py refuses. An unlicensed
    or unattributed component is the one case where the tool overrides the
    artist's click, because the click is what would put it in somebody's pakset.
"""

import os
import sys

try:
    from ..core import components, paksets
except ImportError:
    _HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    from core import components, paksets

# Where a project keeps its own components, and where the kit's shipped ones
# live. Relative, always - see the components module docstring.
PROJECT_DIRNAME = "components"
SHIPPED_DIRNAME = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "components")


def roots(blend_path=None):
    """Where to look for components -> (local, shipped). Local wins.

    A project's own components/ directory sits next to its .blend. Until the
    .blend is saved there is no "next to", so there is no local root - not a
    guess at one relative to wherever Blender was launched from.
    """
    out = []
    if blend_path:
        local = os.path.join(os.path.dirname(blend_path), PROJECT_DIRNAME)
        if os.path.isdir(local):
            out.append(local)
    if os.path.isdir(SHIPPED_DIRNAME):
        out.append(SHIPPED_DIRNAME)
    return tuple(out)


def catalogue(bpy=None, blend_path=None):
    """Every component available here -> (Component, ...)."""
    if blend_path is None and bpy is not None:
        blend_path = bpy.data.filepath or None
    return components.catalogue(*roots(blend_path))


def find(key, bpy=None, blend_path=None):
    for c in catalogue(bpy, blend_path):
        if c.key == key:
            return c
    return None


def insert(bpy, comp, mode=components.APPEND, location=None, pakset_name=None,
           name=None):
    """Bring a component into the current scene -> the new object/collection.

    Raises ValueError if the component is one core/components.py refuses, or if
    its .blend or collection is not actually there. Refusing loudly beats
    inserting an empty collection that renders as nothing.
    """
    errors = components.blocking(components.check(comp, pakset_name))
    if errors:
        raise ValueError("; ".join(f.message for f in errors))
    if mode not in components.MODES:
        raise ValueError("unknown mode %r; use: %s"
                         % (mode, ", ".join(components.MODES)))

    path = comp.blend_path()
    if not path or not os.path.isfile(path):
        raise ValueError("the component's .blend is not there: %s" % (comp.blend,))

    before = set(bpy.data.collections.keys())
    inner = "%s/Collection/" % path
    try:
        bpy.ops.wm.append(
            filepath=os.path.join(inner, comp.collection),
            directory=inner, filename=comp.collection,
            link=(mode == components.LINK),
            instance_collections=(mode == components.INSTANCE),
        )
    except RuntimeError as e:
        raise ValueError("Blender would not read %s: %s" % (comp.blend, e))

    made = [n for n in bpy.data.collections.keys() if n not in before]
    if not made and mode != components.INSTANCE:
        raise ValueError("%s has no collection called %r"
                         % (comp.blend, comp.collection))

    col = bpy.data.collections.get(made[0]) if made else None
    _place(bpy, col, comp, location, pakset_name, name)
    return col


def _place(bpy, col, comp, location, pakset_name, name):
    """Put it at its anchor, in world units.

    The anchor is stored in TILE-relative units, so a bogie sits at the same
    fraction of a tile whatever the pakset. It is multiplied by tile_world here -
    which is 2.0 in every shipped profile, so today this is a no-op; it is written
    this way because the anchor's meaning is "a fraction of a tile", and storing
    the multiplication rather than the meaning is how a number goes wrong the day
    somebody defines a profile with a different tile_world.
    """
    if col is None:
        return
    if name:
        col.name = name
    tw = paksets.get(pakset_name).tile_world if pakset_name else 1.0
    at = location if location is not None else tuple(
        v * tw for v in comp.anchor)
    for ob in col.objects:
        if ob.parent is None:
            ob.location = (ob.location[0] + at[0],
                           ob.location[1] + at[1],
                           ob.location[2] + at[2])


def missing(bpy, blend_path=None):
    """Components this file refers to that are not in the catalogue.

    A linked component whose .blend has gone is a collection with no objects: it
    renders as nothing, and Blender says so only in a console nobody has open.
    """
    have = {c.key for c in catalogue(bpy, blend_path)}
    out = []
    for lib in bpy.data.libraries:
        if not os.path.isfile(bpy.path.abspath(lib.filepath)):
            out.append(lib.filepath)
    return tuple(out), tuple(sorted(have))
