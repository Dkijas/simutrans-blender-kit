"""What an artist must build, said before they build it.

Every other module in core/ READS a finished scene: rig.render_way looks for a
collection called `way_curve`, rig.has_tunnel_model looks for `tunnel_portal`,
collection_variant_setup looks for `season_1`. Nothing anywhere WRITES them, so
the artist types those names by hand, from a three-line hint in the panel, and a
typo is not an error - it is a piece that silently never renders.

This module is the inverse of the readers: given a kind of object, it says which
collections that object needs and what each one is for. The panel then makes them.

THE NAMES ARE DERIVED, NEVER RE-TYPED
    `way_curve` is not spelled out below. It is WAY_PREFIX + a name from
    ways.PIECE_NAMES, which is the same tuple render_way iterates. The bridge
    collections come from bridges.GROUP_COLLECTION, which is the dict the bridge
    renderer looks them up in. If someone renames a piece, the template follows,
    because there is one spelling and both sides read it.

    That is not tidiness. A template that agrees with the renderer today and
    drifts tomorrow is worse than no template: it would confidently create a
    collection the renderer stopped looking at, and the artist would model into
    a collection nothing renders - which is exactly the failure the template
    exists to prevent, with a tool's authority behind it.

    The five prefixes live HERE, and addon/rig.py imports them, so this module is
    the single source. The three variant prefixes (season_, phase_, state_) had no
    home at all before: they were string literals in addon/ui.py, matched only by
    a docstring in rig.py and a line of prose in the panel. Now they have one.

GUIDES ARE EMPTIES, AND THAT IS LOAD-BEARING
    rig.scene_bounds() walks every MESH in the scene and skips only the camera and
    the sun, BY NAME. It does not look at hide_render. So a guide modelled as a
    mesh would enter the bounding box, and the model's own framing and clipping
    checks would then be measured against the guide instead of the model - a guide
    that silently breaks the render it exists to help.

    Blender empties are not meshes and are never rendered, so `ob.type != "MESH"`
    already excludes them, from both the render and the bounds. The guides below
    are therefore empties by construction, not by remembering to hide them.
    tests/blender_template.py holds the line: it asserts scene_bounds is
    byte-identical before and after the guides are made.
"""

from typing import NamedTuple

from . import bridges, buildings, convoy, paksets, roadsigns, ways

# --- the collection prefixes -------------------------------------------------
#
# The single source. addon/rig.py aliases these; addon/ui.py uses them directly.
WAY_PREFIX = "way_"
WAYOBJ_PREFIX = "wayobj_"
TUNNEL_PREFIX = "tunnel_"
BRIDGE_PREFIX = "bridge_"
FREIGHT_PREFIX = "freight_"

# The additive variants - all the same shape, deliberately (see
# rig.collection_variant_setup): one convention to learn, not three.
SEASON_PREFIX = "season_"
PHASE_PREFIX = "phase_"
STATE_PREFIX = "state_"

# The parts drawn OVER the vehicle rather than behind it. A wayobj, a tunnel and
# a bridge each split into two layers, and each spells the split the same way.
FRONT_SUFFIX = "_front"

# The ramp models. Not a piece - the way's slope image is a separate render.
SLOPE_NAME = "slope"
SLOPE2_NAME = "slope2"

# Where the guides go. One collection so an artist can hide the lot with one
# click, and so a second Create Template can find and refresh them.
GUIDE_COLLECTION = "SIMUTRANS_GUIDES"


class Collection(NamedTuple):
    """One collection the artist must fill.

    required=False means the object renders without it, and something is merely
    missing from the result - a slope image, the parts in front of the vehicle.
    required=True means there is nothing to render at all without it.
    """
    name: str
    what: str
    required: bool


class Guide(NamedTuple):
    """One visual guide, as a Blender empty.

    display is Blender's empty_display_type. Carrying a Blender word in core/ is
    the same bargain paksets.makeobj_arg already makes with makeobj: it is a
    string, it needs no import, and core stays runnable without Blender.
    """
    name: str
    display: str
    location: tuple
    rotation_euler: tuple
    size: float
    scale: tuple
    what: str


OBJECT_TYPES = ("vehicle", "building", "way", "wayobj", "roadsign", "tunnel",
                "bridge", "factory")


def _pieces(prefix):
    """The six way-shaped collections, from the tuple the renderer iterates."""
    return tuple(prefix + name for name in ways.PIECE_NAMES)


def _numbered(prefix, count, what, first=0):
    return tuple(Collection("%s%d" % (prefix, i), what % i, False)
                 for i in range(first, count))


def collections(obj_type, *, seasons=1, phases=1, states=1, freight_variants=0,
                btype="res"):
    """The collections this object needs -> (Collection, ...).

    Everything here is keyed off the same constants the renderers read, so the
    list cannot promise a collection the renderer does not look for.
    """
    if obj_type not in OBJECT_TYPES:
        raise ValueError("unknown object type %r; the kit builds: %s"
                         % (obj_type, ", ".join(OBJECT_TYPES)))

    out = []

    if obj_type == "vehicle":
        # A vehicle needs NO collections. render_directions photographs whatever
        # is in the scene, so the body, the bogies and the pantograph can sit
        # loose or in collections of the artist's own naming - the renderer never
        # looks. Only cargo variants are read, and only if asked for.
        #
        # This is why the vehicle template's value is its GUIDES, not its
        # collections: what an artist gets wrong on a vehicle is the orientation,
        # the origin and the length, none of which a collection would fix.
        out.extend(_numbered(
            FREIGHT_PREFIX, freight_variants,
            "the load itself for cargo variant %d - the coal heaped in the wagon"))

    elif obj_type in ("building", "factory"):
        out.extend(_numbered(
            SEASON_PREFIX, seasons,
            "what APPEARS in season %d and not otherwise - the snow on the roof",
            first=1))
        out.extend(_numbered(
            PHASE_PREFIX, phases,
            "what appears in animation frame %d - the lit window, the turning fan",
            first=1))

    elif obj_type == "way":
        for name in ways.PIECE_NAMES:
            out.append(Collection(
                WAY_PREFIX + name, _WAY_PIECE_WHAT[name], False))
        out.append(Collection(WAY_PREFIX + SLOPE_NAME,
                              "the way running up a hill. Without it the way is "
                              "INVISIBLE on every slope", False))
        out.append(Collection(WAY_PREFIX + SLOPE2_NAME,
                              "the ramp up a DOUBLE hill - the ordinary hill on "
                              "pak128", False))

    elif obj_type == "wayobj":
        for name in ways.PIECE_NAMES:
            out.append(Collection(WAYOBJ_PREFIX + name,
                                  _WAY_PIECE_WHAT[name], False))
            out.append(Collection(
                WAYOBJ_PREFIX + name + FRONT_SUFFIX,
                "the parts of %s drawn OVER the vehicle - the contact wire that "
                "crosses above it" % name, False))
        out.append(Collection(WAYOBJ_PREFIX + SLOPE_NAME,
                              "the line running up a hill. Without it the "
                              "catenary is not drawn on a slope at all", False))

    elif obj_type == "tunnel":
        out.append(Collection(TUNNEL_PREFIX + "portal",
                              "the portal, modelled on a NORTH-facing ramp. The "
                              "rig turns it for the other three", True))
        out.append(Collection(TUNNEL_PREFIX + "portal" + FRONT_SUFFIX,
                              "the parts of the portal drawn OVER the vehicle",
                              False))

    elif obj_type == "bridge":
        # bridges.GROUPS is the writer's own order, and GROUP_COLLECTION is the
        # dict the renderer looks each one up in.
        for group, _dirs in bridges.GROUPS:
            name = BRIDGE_PREFIX + bridges.GROUP_COLLECTION[group]
            out.append(Collection(name, _BRIDGE_GROUP_WHAT[group],
                                  group == "image"))
            out.append(Collection(name + FRONT_SUFFIX,
                                  "the parts of the %s drawn OVER the vehicle"
                                  % bridges.GROUP_COLLECTION[group], False))

    elif obj_type == "roadsign":
        out.extend(_numbered(
            STATE_PREFIX, states,
            "the lamp lit in aspect %d. ASPECT 0 IS RED - the engine's "
            "STATE_RED is 0, and the trains act on it"))

    return tuple(out)


_WAY_PIECE_WHAT = {
    "none": "the tile with no connection at all - bare ground",
    "end": "a stub, meeting the NORTH edge only",
    "straight": "north to south. The rig turns it for east-west",
    "curve": "north to east. The rig turns it for the other three corners",
    "tee": "north, south and east. The rig turns it for the other three",
    "cross": "the four-way junction. Skip it and every crossroads is INVISIBLE",
}

_BRIDGE_GROUP_WHAT = {
    "image": "the span itself, modelled north-south. The rig turns it",
    "start": "where the bridge leaves the ground, facing north",
    "ramp": "the sloped approach, facing north",
    "pillar": "the pier that holds it up",
}


def required(obj_type, **opts):
    """Just the collections without which there is nothing to render."""
    return tuple(c for c in collections(obj_type, **opts) if c.required)


def names(obj_type, **opts):
    return tuple(c.name for c in collections(obj_type, **opts))


# --- the guides --------------------------------------------------------------

def _tile_guide(tile_world):
    # A CUBE empty draws a wireframe box of side 2*size, so half the tile edge
    # gives a box exactly one tile across. Flattened in z: this marks the GROUND,
    # and a cube standing a tile tall would just be in the way.
    return Guide(
        "SIMUTRANS_tile", "CUBE", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
        tile_world / 2.0, (1.0, 1.0, 0.0),
        "one tile at ground level. The model stands ON this, not in it")


def _nose_guide(tile_world):
    # SINGLE_ARROW points along the empty's +Z, so rotating +90 deg about Y aims
    # it down +X - the direction the engine reads as the vehicle's nose.
    return Guide(
        "SIMUTRANS_nose_+X", "SINGLE_ARROW", (0.0, 0.0, 0.0),
        (0.0, 1.5707963267948966, 0.0), tile_world * 0.75, (1.0, 1.0, 1.0),
        "the nose points +X. This is the convention the whole kit is built on")


def guides(obj_type, pakset_name="pak128", *, length=8, size_x=1, size_y=1):
    """The visual guides for this object -> (Guide, ...).

    Empties, every one - see the module docstring. They tell the artist the three
    things the panel cannot: which way is forward, how big a tile is, and how much
    of it this object is entitled to.
    """
    if obj_type not in OBJECT_TYPES:
        raise ValueError("unknown object type %r" % (obj_type,))

    pak = paksets.get(pakset_name)
    tw = pak.tile_world
    out = [_tile_guide(tw)]

    if obj_type == "vehicle":
        out.append(_nose_guide(tw))
        # The declared length, drawn. `length` is in carunits (1/16 of a tile),
        # and it is what the engine trails the NEXT car by - not what it scales
        # the sprite to. So a body that does not fill this box does not shrink
        # the car, it opens a gap in the train (convoy.py has the measurement).
        # An artist cannot see that mistake until the unit is coupled in a depot.
        half = length_world(length, tw) / 2.0
        out.append(Guide(
            "SIMUTRANS_length", "CUBE", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
            1.0, (half, tw / 2.0, 0.0),
            "the length you declared, in tiles. Fill it, or the train gaps"))

    elif obj_type in ("building", "factory"):
        # The footprint grows east (+X) and south (-Y) from the origin tile, the
        # way the engine grows it from (0,0). Marked at the CENTRE of the plot,
        # because a layout turns the building about its footprint centre, not its
        # corner - the 2x1 bug the README records.
        out.append(Guide(
            "SIMUTRANS_footprint", "CUBE",
            ((size_x - 1) * tw / 2.0, -(size_y - 1) * tw / 2.0, 0.0),
            (0.0, 0.0, 0.0), tw / 2.0, (float(size_x), float(size_y), 0.0),
            "the plot: %d east by %d south" % (size_x, size_y)))
        # The facade faces -Y. That is Blender's own Front view, so an artist who
        # models "facing the viewer" in the default view is already right.
        out.append(Guide(
            "SIMUTRANS_facade_-Y", "SINGLE_ARROW",
            ((size_x - 1) * tw / 2.0, -size_y * tw / 2.0, 0.0),
            (1.5707963267948966, 0.0, 0.0), tw * 0.5, (1.0, 1.0, 1.0),
            "the facade faces -Y, toward the street"))

    elif obj_type in ("way", "wayobj"):
        # Every piece is modelled in its BASE ribi, and every base ribi touches
        # north. Showing +Y is showing where `end`, `straight`, `curve` and `tee`
        # all begin.
        out.append(Guide(
            "SIMUTRANS_north_+Y", "SINGLE_ARROW", (0.0, 0.0, 0.0),
            (-1.5707963267948966, 0.0, 0.0), tw * 0.75, (1.0, 1.0, 1.0),
            "north is +Y. Every piece is modelled touching THIS edge"))

    elif obj_type == "tunnel":
        out.append(Guide(
            "SIMUTRANS_north_+Y", "SINGLE_ARROW", (0.0, 0.0, 0.0),
            (-1.5707963267948966, 0.0, 0.0), tw * 0.75, (1.0, 1.0, 1.0),
            "model the portal facing north (+Y). The rig turns it"))

    elif obj_type == "bridge":
        out.append(Guide(
            "SIMUTRANS_north_+Y", "SINGLE_ARROW", (0.0, 0.0, 0.0),
            (-1.5707963267948966, 0.0, 0.0), tw * 0.75, (1.0, 1.0, 1.0),
            "the span is modelled north-south. The rig turns it"))

    elif obj_type == "roadsign":
        out.append(Guide(
            "SIMUTRANS_north_+Y", "SINGLE_ARROW", (0.0, tw / 2.0, 0.0),
            (-1.5707963267948966, 0.0, 0.0), tw * 0.4, (1.0, 1.0, 1.0),
            "model the sign at the tile's north (+Y) edge"))

    return tuple(out)


def length_world(length, tile_world):
    """A vehicle's declared `length` in Blender units.

    length is in carunits - 1/16 of a tile (simconst.h OBJECT_OFFSET_STEPS), the
    same unit convoy.py does its joint arithmetic in.
    """
    return float(length) / convoy.CARUNITS_PER_TILE * tile_world


def guide_names():
    """Every name this module ever gives a guide, for finding and refreshing them.

    Collected by asking, not by listing: a guide added above and forgotten here
    would leave an orphan in the scene that Create Template never cleans up.
    """
    seen = []
    for obj_type in OBJECT_TYPES:
        for g in guides(obj_type):
            if g.name not in seen:
                seen.append(g.name)
    return tuple(seen)
