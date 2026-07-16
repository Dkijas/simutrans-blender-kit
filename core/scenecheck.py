"""Tell the artist what is wrong BEFORE the render, not after it.

The kit already refuses plenty of mistakes. Every one of those refusals happens
during or after the render:

    rig.warn_if_clipped        reads the finished PNGs
    rig.warn_if_double_slope_missing   fires while render_way runs
    render_building            raises when a season has no callback
    schema.lint                reads the finished .dat
    ui.SIMUTRANS_OT_check_colors       needs a sheet on disk

So the artist finds out after paying for the render - and a vehicle's eight
headings on a slow machine is not a cheap thing to pay twice. Worse, the two
mistakes that cost the most (a model facing the wrong way, a model that is not
standing on the ground) survive the render perfectly: the sheet is fine, the .dat
lints clean, the pak compiles, and the vehicle is wrong in the game.

This module answers the question the panel could not ask: given a scene, is it
worth rendering?

PURE ON PURPOSE
    It takes a Scene - a plain description of what is in the file - not a bpy
    context. addon/scenecheck_blender.py builds one from bpy in about thirty
    lines; tests/test_core.py builds one from a literal and checks every rule
    without Blender in the loop. A rule that needs Blender to test is a rule that
    gets tested once.

THE THREE LEVELS, AND WHY A WARNING MUST NOT BLOCK
    ERROR        the render cannot produce a correct object. Refuse.
    WARNING      the render works and the result is probably not what you meant.
    INFORMATION  a measurement worth seeing. Never a judgement.

    The bar for ERROR is deliberately high. This kit's own linter earns its keep
    by having zero false positives on pak128's shipped art (README), and the same
    logic applies here with more force: an artist whose correct scene is refused
    turns the check off, and then it protects nobody. When a rule cannot tell
    "wrong" from "unusual", it is a WARNING. Aesthetics are never either - a model
    the checker finds ugly is none of its business.
"""

from typing import NamedTuple

from . import buildings, paksets, templates

ERROR = "ERROR"
WARNING = "WARNING"
INFORMATION = "INFORMATION"

_ORDER = {ERROR: 0, WARNING: 1, INFORMATION: 2}


class Finding(NamedTuple):
    """One thing to say. `code` is stable; the message is for a human."""
    level: str
    code: str
    message: str


class Scene(NamedTuple):
    """What the checker needs to know about a Blender file.

    Deliberately small and deliberately dumb: every field is something the addon
    can read in one line, and nothing here is a bpy object.

    collections   name -> how many mesh objects are in it
    mins/maxs     the renderable bounding box, world units (rig.scene_bounds)
    saved         has the .blend been saved? ('//' paths mean nothing until it is)
    out_relative  does the output path start with '//'?

    `collections` defaults to None, not to {}. A NamedTuple's defaults are
    evaluated once at class creation, so an empty-dict default would be ONE dict
    shared by every Scene built without one - the mutable-default trap, with a
    tuple's immutability hiding it. Readers use `scene.collections or {}`.
    """
    obj_type: str
    pakset: str = "pak128"
    collections: dict = None
    mins: tuple = (0.0, 0.0, 0.0)
    maxs: tuple = (0.0, 0.0, 0.0)
    has_mesh: bool = False
    saved: bool = True
    out_relative: bool = False
    # the panel's numbers, so the check can compare what was declared against
    # what was modelled
    length: int = 8
    size_x: int = 1
    size_y: int = 1
    seasons: int = 1
    phases: int = 1
    states: int = 1
    freight_variants: int = 0
    is_signal: bool = False
    obj_name: str = ""
    author: str = ""
    factory_mapcolor: int = 1


# How far off the ground we let a model sit before saying so, as a fraction of a
# tile. Not zero: a bogie modelled with its wheel rims a hair below z=0, or a
# body floated a whisker to avoid z-fighting, is normal art, and a checker that
# fires on it is a checker nobody reads.
GROUND_TOLERANCE_TILES = 0.02

# How much bigger than its tile a model may be before we mention it. A vehicle
# legitimately overhangs - pak128's own art does - but a model several tiles wide
# is not a vehicle, it is a unit that needs splitting into coupled cars.
OVERSIZE_TILES = 1.5


def check(scene):
    """Everything worth saying about this scene -> (Finding, ...).

    Sorted ERROR first. The caller blocks on ERROR and shows the rest.
    """
    out = []
    out.extend(_check_output(scene))
    out.extend(_check_geometry(scene))
    out.extend(_check_collections(scene))
    out.extend(_check_fields(scene))
    return tuple(sorted(out, key=lambda f: _ORDER[f.level]))


def blocking(findings):
    """The ones that must stop the render."""
    return tuple(f for f in findings if f.level == ERROR)


def _check_output(scene):
    if scene.out_relative and not scene.saved:
        # '//' is relative to the .blend, and Blender resolves it against the
        # current working directory when there is no .blend - which is wherever
        # Blender was launched from. ui._out_dir refuses this too; saying it here
        # means the artist hears it from Validate rather than from a failed render.
        yield Finding(ERROR, "unsaved-blend",
                      "Save the .blend first, or set an absolute Output path. "
                      "'//' means 'next to the .blend', and there isn't one yet")


def _check_geometry(scene):
    if not scene.has_mesh:
        yield Finding(ERROR, "no-mesh",
                      "Nothing to render - the scene has no mesh")
        return

    pak = paksets.get(scene.pakset)
    tw = pak.tile_world
    lo, hi = scene.mins, scene.maxs
    tol = GROUND_TOLERANCE_TILES * tw

    # --- the ground.
    #
    # tile_anchor() aims the camera at a point above z=0 and NOTHING re-centres
    # the model: "a model on z=0 comes out sitting on the rail" is the whole of
    # vehicle alignment. A model built 3 units up renders perfectly and floats in
    # the game, and no later check catches it, because the sheet is not wrong -
    # the model is.
    if lo[2] > tol:
        yield Finding(WARNING, "floating",
                      "The model floats %.2f above the ground. It stands on "
                      "z=0, or it flies in the game" % lo[2])
    elif lo[2] < -tol:
        yield Finding(WARNING, "sunk",
                      "The model sinks %.2f below the ground. It stands on "
                      "z=0, or it is buried in the game" % (-lo[2],))

    # --- the origin.
    if scene.obj_type in ("vehicle", "roadsign", "way", "wayobj", "tunnel",
                          "bridge"):
        cx = (lo[0] + hi[0]) / 2.0
        cy = (lo[1] + hi[1]) / 2.0
        off = max(abs(cx), abs(cy))
        if off > tw / 4.0:
            yield Finding(WARNING, "off-centre",
                          "The model sits %.2f off the origin. It is centred on "
                          "the world origin, which is the tile's centre" % off)

    # --- the size.
    span_x = hi[0] - lo[0]
    span_y = hi[1] - lo[1]
    big = max(span_x, span_y) / tw
    if big > OVERSIZE_TILES:
        yield Finding(WARNING, "oversize",
                      "The model is %.1f tiles across. One sprite is capped at "
                      "ONE tile - a longer vehicle is built as coupled cars, "
                      "each its own pak" % big)

    # --- the declared length, against the modelled one.
    #
    # This is the one an artist cannot see alone. `length` does not scale the
    # sprite; it is what the engine trails the NEXT car by (convoy.py). Declare 8
    # and model 16 and each sprite is drawn full size, overlapping its neighbour
    # by half a tile - in the depot, not in Blender.
    if scene.obj_type == "vehicle":
        want = templates.length_world(scene.length, tw)
        if want > 0 and span_x > 0:
            ratio = span_x / want
            if ratio > 1.25 or ratio < 0.75:
                yield Finding(
                    WARNING, "length-mismatch",
                    "You declared length=%d (%.2f units) but modelled %.2f along "
                    "X. The engine spaces the next car by what you DECLARED, so "
                    "the train will gap or overlap" % (scene.length, want, span_x))

    yield Finding(INFORMATION, "size",
                  "%.2f x %.2f x %.2f units - %.2f tiles long, %.2f wide"
                  % (span_x, span_y, hi[2] - lo[2], span_x / tw, span_y / tw))


def _check_collections(scene):
    opts = dict(seasons=scene.seasons, phases=scene.phases, states=scene.states,
                freight_variants=scene.freight_variants)
    try:
        wanted = templates.collections(scene.obj_type, **opts)
    except ValueError as e:
        yield Finding(ERROR, "unknown-type", str(e))
        return

    have = scene.collections or {}

    for col in wanted:
        n = have.get(col.name)
        if n is None:
            if col.required:
                yield Finding(ERROR, "missing-collection",
                              "No collection '%s' - %s" % (col.name, col.what))
            continue
        if n == 0:
            # Worse than absent, and the reason this is a rule of its own: an
            # empty collection looks done in the outliner. The renderer finds it,
            # renders nothing into it, and reports nothing.
            yield Finding(ERROR if col.required else WARNING, "empty-collection",
                          "Collection '%s' is empty - %s" % (col.name, col.what))

    # A way with no pieces at all has nothing to render. With SOME pieces it has
    # holes, and ways.missing() is the module that names them - but it is a
    # warning there and stays one here: the engine draws nothing at that ribi and
    # carries on, and the README's own line is that a missing cross is invisible,
    # not fatal.
    if scene.obj_type in ("way", "wayobj"):
        prefix = (templates.WAY_PREFIX if scene.obj_type == "way"
                  else templates.WAYOBJ_PREFIX)
        modelled = [c.name[len(prefix):] for c in wanted
                    if have.get(c.name)
                    and not c.name.endswith(templates.FRONT_SUFFIX)
                    and c.name[len(prefix):] not in (templates.SLOPE_NAME,
                                                     templates.SLOPE2_NAME)]
        if not modelled:
            yield Finding(ERROR, "no-pieces",
                          "No %s piece is modelled - there is nothing to render"
                          % scene.obj_type)

    # The names we did NOT ask for. A collection called `way_curved` or `season1`
    # is invisible to the renderer, and the artist who typed it believes it works.
    # This is precisely the typo the template exists to prevent, so it is worth
    # catching for the scenes that predate it.
    known = {c.name for c in wanted}
    for prefix in (templates.WAY_PREFIX, templates.WAYOBJ_PREFIX,
                   templates.TUNNEL_PREFIX, templates.BRIDGE_PREFIX,
                   templates.FREIGHT_PREFIX, templates.SEASON_PREFIX,
                   templates.PHASE_PREFIX, templates.STATE_PREFIX):
        for name in sorted(have):
            if name.startswith(prefix) and name not in known:
                yield Finding(WARNING, "unread-collection",
                              "Nothing reads collection '%s'. Check the spelling "
                              "- the renderer looks for exact names" % name)


def _check_fields(scene):
    if not scene.obj_name.strip():
        yield Finding(ERROR, "no-name", "The object has no Name")
    if not scene.author.strip():
        yield Finding(WARNING, "no-author",
                      "No Author. It goes in the .pak and it is how anyone knows "
                      "whose work it is")

    # Both of these already warn in the panel at the moment the number is typed
    # (ui.SIMUTRANS_PT_dat). Repeated here because Validate is the one button an
    # artist presses before rendering, and a check that is only in a tooltip is a
    # check for people who already know.
    if scene.obj_type in ("building", "factory"):
        if scene.seasons not in buildings.USEFUL_SEASON_COUNTS:
            yield Finding(WARNING, "dead-season",
                          "%d seasons: the engine NEVER draws the third image "
                          "(gebaeude.cc effective_season). Use 1, 2, 4 or 5"
                          % scene.seasons)

    if scene.obj_type == "roadsign" and scene.is_signal and scene.states < 2:
        yield Finding(ERROR, "signal-needs-two",
                      "A signal needs 2 aspects. State 0 is RED, and the trains "
                      "act on it")

    if scene.obj_type == "factory" and not (0 <= scene.factory_mapcolor <= 254):
        # factory_writer.cc calls dbg->fatal() without a usable one.
        yield Finding(ERROR, "no-mapcolor",
                      "A factory needs a Map colour (0-254). The engine refuses "
                      "one without it")
