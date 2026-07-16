"""Make the scene the artist would otherwise have to make by hand.

core/templates.py says WHAT an object needs. This puts it in a Blender file: the
collections, named the way the renderer reads them, and the guides that show the
three conventions no panel field can express - which way is forward, where the
ground is, and how big a tile is.

Like rig.py, every function takes `bpy` rather than importing it, so the whole
module is drivable from `blender --background --python tests/blender_template.py`.

EVERYTHING HERE IS IDEMPOTENT
    Press Create Template twice and you get the same scene, not two of it. That
    is not politeness; it is the difference between a button an artist trusts
    mid-project and one they only dare press on an empty file. A collection that
    exists is left exactly as it is - with the artist's models still in it - and
    only the guides are refreshed, because the guides are ours and the models are
    theirs.

    So the rule is: we never delete anything we did not make, and we never touch
    the contents of a collection at all.
"""

import math
import os
import sys

try:
    from ..core import paksets, scenecheck, templates
except ImportError:
    _HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    from core import paksets, scenecheck, templates


def _scene_collection(bpy):
    return bpy.context.scene.collection


def _ensure_collection(bpy, name, parent=None):
    """Get or make a collection, linked into the scene -> (collection, made?).

    bpy.data.collections is FILE-wide while scene.collection is what the outliner
    shows, and the two come apart: a collection that exists but is linked nowhere
    is invisible to the artist and still found by name. So this checks both.
    """
    made = False
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        made = True
    holder = parent if parent is not None else _scene_collection(bpy)
    if col.name not in holder.children:
        # A collection can only be linked to one parent at a time in a scene's
        # tree; if it is already somewhere else, leave it there - the artist may
        # have organised it deliberately.
        if not _is_linked_anywhere(bpy, col):
            holder.children.link(col)
    return col, made


def _is_linked_anywhere(bpy, col):
    if col.name in _scene_collection(bpy).children:
        return True
    for other in bpy.data.collections:
        if col.name in other.children:
            return True
    return False


def create_collections(bpy, obj_type, **opts):
    """Make every collection this object needs -> (made, kept).

    Names come from core.templates, which reads them from the same constants the
    renderers do. Nothing is emptied, nothing is deleted.
    """
    made, kept = [], []
    for spec in templates.collections(obj_type, **opts):
        _col, was_new = _ensure_collection(bpy, spec.name)
        (made if was_new else kept).append(spec.name)
    return tuple(made), tuple(kept)


def _ensure_empty(bpy, guide, parent):
    """Get or make ONE guide empty, and set it to the spec.

    An empty, not a mesh, and that is load-bearing: rig.scene_bounds() walks
    every MESH and skips only the camera and sun BY NAME, without looking at
    hide_render. A mesh guide would join the model's bounding box and the framing
    and clipping checks would then measure the guide. `ob.type != "MESH"` already
    excludes an empty, from the bounds and from the render both.
    """
    ob = bpy.data.objects.get(guide.name)
    if ob is None:
        ob = bpy.data.objects.new(guide.name, None)
    elif ob.type != "EMPTY":
        # Someone made a real object with our name. Do not touch it - deleting an
        # artist's mesh to put a guide there is exactly the destructive surprise
        # this module refuses to be.
        return None, False
    made = ob.name not in {o.name for o in parent.objects}

    ob.empty_display_type = guide.display
    ob.empty_display_size = guide.size
    ob.location = guide.location
    ob.rotation_euler = guide.rotation_euler
    ob.scale = guide.scale
    ob.hide_select = True          # a guide you can click is a guide you move
    ob.hide_render = True          # belt and braces; the type already does it

    if made:
        parent.objects.link(ob)
    return ob, made


def create_guides(bpy, obj_type, pakset_name="pak128", **opts):
    """Make (or refresh) the visual guides -> (names, ...).

    Guides ARE ours, so unlike collections they are rewritten every time rather
    than left alone. What actually moves them is the OBJECT and its numbers: a
    vehicle's length guide follows the `length` field, a building's footprint
    follows size_x/size_y, and switching object type swaps the whole set.

    Not the pakset, though - `tile_world` is 2.0 in every shipped profile, on
    purpose (paksets.py: it is "pure convention - it only has to be consistent
    with ortho_scale"). What a pakset changes is tile_px and ortho_scale, which
    are the camera's business, not the model's. So a tile is two Blender units in
    pak64 and in pak128 alike, and the guide is the same size in both. An earlier
    version of this docstring claimed the opposite; the test that was written to
    prove it failed, and the docstring was the thing that was wrong.
    """
    holder, _new = _ensure_collection(bpy, templates.GUIDE_COLLECTION)
    out = []
    for guide in templates.guides(obj_type, pakset_name, **opts):
        ob, _made = _ensure_empty(bpy, guide, holder)
        if ob is not None:
            out.append(ob.name)

    # Guides from a previous object type are stale, not sacred: a nose arrow left
    # over from a vehicle would tell a building's artist to face +X, which is
    # wrong. Ours to make, ours to remove - but only ours, and only from our own
    # collection.
    wanted = set(out)
    for ob in list(holder.objects):
        if ob.name in templates.guide_names() and ob.name not in wanted:
            holder.objects.unlink(ob)
            if not ob.users:
                bpy.data.objects.remove(ob)
    return tuple(out)


def create(bpy, obj_type, pakset_name="pak128", *, seasons=1, phases=1, states=1,
           freight_variants=0, length=8, size_x=1, size_y=1):
    """The whole template: collections + guides. -> (made, kept, guides)."""
    made, kept = create_collections(
        bpy, obj_type, seasons=seasons, phases=phases, states=states,
        freight_variants=freight_variants)
    guides = create_guides(bpy, obj_type, pakset_name, length=length,
                           size_x=size_x, size_y=size_y)
    return made, kept, guides


# --- reference images --------------------------------------------------------

REFERENCE_COLLECTION = "SIMUTRANS_REFERENCES"

# side -> (rotation, which axis the image's width runs along, and its height)
#
# A Blender IMAGE empty faces +Z with its width on +X and height on +Y. Turn it
# to stand up and the photo stands where the real thing would.
_REF_SIDES = {
    # a side elevation seen from -Y: the vehicle's length runs +X, height +Z
    "side": ((math.pi / 2.0, 0.0, 0.0), "x", "z"),
    # a front elevation seen from +X: width runs +Y, height +Z
    "front": ((math.pi / 2.0, 0.0, math.pi / 2.0), "y", "z"),
    # a plan seen from above: length +X, width +Y
    "top": ((0.0, 0.0, 0.0), "x", "y"),
}


def setup_reference(bpy, side, image_path, *, length_m, width_m, height_m,
                    pakset_name="pak128", metres_per_tile=None):
    """Put one reference photo where the model will be -> the empty, or None.

    The photo is scaled from the REAL dimensions the artist types, so a model
    traced over it is the right size in the game without anyone doing the sum.
    That sum is the whole feature: metres -> tiles -> Blender units is the step
    where an artist who has never read the pakset docs goes wrong, and it does
    not announce itself - a bus modelled 20% large is just a slightly wrong bus.

    Nothing is downloaded and nothing is fetched: image_path is a file the artist
    already has.
    """
    if side not in _REF_SIDES:
        raise ValueError("unknown reference side %r; use: %s"
                         % (side, ", ".join(sorted(_REF_SIDES))))
    if not os.path.isfile(image_path):
        raise ValueError("no such image: %s" % image_path)

    pak = paksets.get(pakset_name)
    mpt = metres_per_tile if metres_per_tile else default_metres_per_tile()
    scale = pak.tile_world / float(mpt)          # world units per metre

    rotation, w_axis, h_axis = _REF_SIDES[side]
    dims = {"x": length_m, "y": width_m, "z": height_m}
    w = dims[w_axis] * scale
    h = dims[h_axis] * scale

    name = "SIMUTRANS_ref_%s" % side
    img = bpy.data.images.load(image_path, check_existing=True)

    ob = bpy.data.objects.get(name)
    if ob is not None and ob.type != "EMPTY":
        return None
    if ob is None:
        ob = bpy.data.objects.new(name, None)
        holder, _new = _ensure_collection(bpy, REFERENCE_COLLECTION)
        holder.objects.link(ob)

    ob.empty_display_type = "IMAGE"
    ob.data = img
    ob.rotation_euler = rotation
    # empty_display_size is the width; the height follows the image's aspect, so
    # the offset is what centres it rather than a second scale.
    ob.empty_display_size = w
    aspect = (img.size[1] / img.size[0]) if img.size[0] else 1.0
    ob.empty_image_offset = (-0.5, 0.0 if side != "top" else -0.5)
    ob.location = _reference_location(side, w, h, aspect)
    ob.hide_select = True
    ob.hide_render = True
    ob.show_empty_image_perspective = False
    return ob


def _reference_location(side, w, h, aspect):
    """Sit the photo on the ground, behind the model, centred on the origin."""
    if side == "top":
        return (0.0, 0.0, 0.0)
    # Standing up: the empty's origin is its centre once the offset above has
    # moved it, so lift it by half its drawn height to put its bottom on z=0.
    return (0.0, 0.0, w * aspect / 2.0)


# The metres a tile is worth. NOT an engine constant - the engine has no metres
# at all, and nothing in the source fixes one. It is a pakset's own convention,
# and pak128's is roughly this: its `length=8` rail cars (425 of its 505, per
# convoy.py) are ~20 m coaches at half a tile.
#
# Which is why this is a DEFAULT the artist can override in the panel, not a fact
# in paksets.py. A number nobody measured does not belong beside the ones we did.
DEFAULT_METRES_PER_TILE = 40.0


def default_metres_per_tile():
    return DEFAULT_METRES_PER_TILE


# --- describing a scene for the checker --------------------------------------

def describe(bpy, props, rig_module):
    """Build a scenecheck.Scene from the live Blender file.

    The only place bpy meets the checker. Everything the rules act on is read
    here, in one pass, so core/scenecheck.py can stay pure and be tested from a
    literal.
    """
    mins, maxs = rig_module.scene_bounds(bpy)
    has_mesh = any(ob.type == "MESH" and ob.name not in (rig_module.CAM_NAME,
                                                         rig_module.SUN_NAME)
                   for ob in bpy.context.scene.objects)

    counts = {}
    for col in bpy.data.collections:
        if col.name in (templates.GUIDE_COLLECTION, REFERENCE_COLLECTION):
            continue
        counts[col.name] = sum(1 for ob in col.objects if ob.type == "MESH")

    return scenecheck.Scene(
        obj_type=props.obj_type,
        pakset=props.pakset,
        collections=counts,
        mins=tuple(mins), maxs=tuple(maxs),
        has_mesh=has_mesh,
        saved=bool(bpy.data.filepath),
        out_relative=props.out_dir.startswith("//"),
        length=props.length,
        size_x=props.size_x, size_y=props.size_y,
        seasons=props.seasons, phases=props.phases, states=props.states,
        freight_variants=len(
            [g for g in props.freight_goods.split(",") if g.strip()]),
        is_signal=props.is_signal,
        obj_name=props.obj_name,
        author=props.author,
        factory_mapcolor=props.factory_mapcolor,
    )
