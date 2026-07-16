"""The object templates, without Blender.

    python tests/test_templates.py

THE TEMPLATE MUST AGREE WITH THE RENDERER, and that is the whole of this file.

A template is a tool telling an artist "model into this collection". If it names
one the renderer does not read, the artist models into a void with the tool's
authority behind them - strictly worse than the hand-typing it replaced, because
a typo at least looks like a typo, while a tool's output looks like a fact.

So nothing below checks the template against a list of names written here. That
would be a third copy of the spelling, and a third copy is a third thing to drift.
Everything is checked against addon.rig and core.ways / core.bridges, which are
what actually look the names up when the render runs.

The checker that reads a finished scene is tests/test_scenecheck.py; core.templates
does not depend on it, and neither does this.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from addon import rig                                            # noqa: E402
from core import bridges, paksets, templates, ways                # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


# --- the template agrees with the renderer -----------------------------------

def test_the_prefixes_are_one_spelling_not_two():
    """rig's constants come FROM templates - there is one literal, not two.

    This test is the second version. The first compared the values with `is`,
    reasoning that two separate literals would be two distinct objects. They are
    not: CPython interns short string literals, so `"way_" is "way_"` is True and
    the test passed with the constants re-declared in both files - it proved
    nothing while claiming to prove exactly this. It was caught by breaking rig.py
    on purpose and watching the test stay green.

    Values cannot answer the question at all: rig binds its constant at import, so
    the two agree by construction the moment they are equal, however they got that
    way. The claim is about the SOURCE - one literal in the tree - so the source is
    what gets read.
    """
    import re
    with open(os.path.join(_ROOT, "addon", "rig.py"), encoding="utf-8") as f:
        src = f.read()

    # A prefix constant assigned a bare string literal. Deliberately not a search
    # for "way_" anywhere: rig's docstrings name the collections in prose, which
    # is documentation, not a second source of truth.
    literal = re.compile(r"^\s*(\w*(?:PREFIX|SUFFIX))\s*=\s*[\"']", re.M)
    found = literal.findall(src)
    check("addon/rig.py declares no collection prefix of its own", found == [],
          "re-declared in rig.py instead of imported: %s" % (found,))

    for label, mine, theirs in (
            ("way", rig.WAY_COLLECTION_PREFIX, templates.WAY_PREFIX),
            ("wayobj", rig.WAYOBJ_COLLECTION_PREFIX, templates.WAYOBJ_PREFIX),
            ("tunnel", rig.TUNNEL_COLLECTION_PREFIX, templates.TUNNEL_PREFIX),
            ("bridge", rig.BRIDGE_COLLECTION_PREFIX, templates.BRIDGE_PREFIX),
            ("freight", rig.FREIGHT_COLLECTION_PREFIX, templates.FREIGHT_PREFIX)):
        check("the %s prefix reaches rig with the right value" % label,
              mine == theirs, "%r vs %r" % (mine, theirs))


def test_way_collections_are_the_renderers_own_pieces():
    """Not a list retyped here - ways.PIECE_NAMES, which render_way iterates."""
    got = templates.names("way")
    for piece in ways.PIECE_NAMES:
        check("way template offers %s" % piece,
              rig.WAY_COLLECTION_PREFIX + piece in got)
    check("and the slope, without which the way is invisible on every hill",
          "way_slope" in got)
    check("and the double slope, which is the ORDINARY hill on pak128",
          "way_slope2" in got)


def test_bridge_collections_come_from_the_writers_own_groups():
    got = templates.names("bridge")
    for group, _dirs in bridges.GROUPS:
        name = rig.BRIDGE_COLLECTION_PREFIX + bridges.GROUP_COLLECTION[group]
        check("bridge template offers %s" % name, name in got)
        check("and its front layer", name + "_front" in got)
    check("the span is the one you cannot skip",
          [c.name for c in templates.required("bridge")] == ["bridge_span"])


def test_wayobj_offers_a_front_layer_for_every_piece():
    """The catenary's whole trap: put the contact wire in the back list and the
    train drives over its own overhead line, with nothing warning."""
    got = templates.names("wayobj")
    for piece in ways.PIECE_NAMES:
        check("wayobj_%s has a front layer" % piece,
              "wayobj_%s_front" % piece in got)


def test_a_vehicle_needs_no_collections_and_that_is_the_point():
    check("a plain vehicle asks for nothing", templates.names("vehicle") == ())
    check("cargo variants are the exception",
          templates.names("vehicle", freight_variants=2)
          == ("freight_0", "freight_1"))


def test_variants_are_numbered_the_way_the_renderer_reads_them():
    # Seasons and phases are ADDITIVE from 1: variant 0 is the bare model, and
    # nobody makes a season_0. Signal aspects are NOT: state_0 is the red lamp,
    # a real collection, because STATE_RED is 0.
    check("2 seasons wants season_1 only",
          templates.names("building", seasons=2) == ("season_1",))
    check("4 seasons wants 1..3",
          templates.names("building", seasons=4)
          == ("season_1", "season_2", "season_3"))
    check("2 aspects want state_0 AND state_1",
          templates.names("roadsign", states=2) == ("state_0", "state_1"))


def test_every_object_type_is_answerable():
    for obj_type in templates.OBJECT_TYPES:
        try:
            templates.collections(obj_type)
            templates.guides(obj_type)
            ok = True
        except Exception as e:                                    # noqa: BLE001
            ok = False
            print("      %s" % e)
        check("the template knows what a %s is" % obj_type, ok)


def test_an_unknown_type_is_refused_not_guessed():
    for fn in (templates.collections, templates.guides):
        try:
            fn("locomotive")
            ok = False
        except ValueError:
            ok = True
        check("%s refuses an unknown type" % fn.__name__, ok)


def test_guide_names_are_collected_not_listed():
    """guide_names() must find every guide any type makes - an orphan guide left
    in the scene is one Create Template can never clean up again."""
    listed = set(templates.guide_names())
    for obj_type in templates.OBJECT_TYPES:
        for g in templates.guides(obj_type):
            check("guide_names knows %s (from %s)" % (g.name, obj_type),
                  g.name in listed)


def test_guides_are_empties_because_scene_bounds_counts_meshes():
    """rig.scene_bounds walks every MESH and skips only the camera and sun BY
    NAME - it never looks at hide_render. A mesh guide would join the model's
    bounding box and break the framing it exists to help."""
    for obj_type in templates.OBJECT_TYPES:
        for g in templates.guides(obj_type):
            # Blender empty display types. MESH is not one of them, and that is
            # the property being relied on.
            check("%s guide %s is an empty display type"
                  % (obj_type, g.name),
                  g.display in ("PLAIN_AXES", "ARROWS", "SINGLE_ARROW", "CUBE",
                                "SPHERE", "CONE", "IMAGE"))


def test_the_length_guide_is_carunits_not_metres():
    tw = paksets.get("pak128").tile_world
    check("length 16 is a whole tile", templates.length_world(16, tw) == tw)
    check("length 8 is half a tile", templates.length_world(8, tw) == tw / 2.0)
    check("length 4 is a quarter", templates.length_world(4, tw) == tw / 4.0)
    # the guide must follow the panel's number, or it is decoration
    g8 = [g for g in templates.guides("vehicle", length=8)
          if g.name == "SIMUTRANS_length"][0]
    g16 = [g for g in templates.guides("vehicle", length=16)
           if g.name == "SIMUTRANS_length"][0]
    check("the length guide grows with the declared length",
          g16.scale[0] == 2 * g8.scale[0], "%r vs %r" % (g16.scale, g8.scale))


def test_the_tile_guide_follows_the_pakset():
    for name in ("pak64", "pak128"):
        tw = paksets.get(name).tile_world
        tile = [g for g in templates.guides("vehicle", name)
                if g.name == "SIMUTRANS_tile"][0]
        check("%s tile guide is one tile across" % name,
              tile.size * 2 == tw, "%r" % (tile.size,))


def test_a_building_footprint_is_centred_on_its_plot():
    """A layout turns the building about its footprint CENTRE, not its corner -
    the 2x1 bug. A guide drawn at the corner would teach the wrong anchor."""
    tw = paksets.get("pak128").tile_world
    g = [x for x in templates.guides("building", size_x=2, size_y=1)
         if x.name == "SIMUTRANS_footprint"][0]
    check("a 2x1 plot's centre is half a tile east", g.location[0] == tw / 2.0,
          "%r" % (g.location,))
    check("and not shifted in y for a single row", g.location[1] == 0.0)
    g11 = [x for x in templates.guides("building", size_x=1, size_y=1)
           if x.name == "SIMUTRANS_footprint"][0]
    check("a 1x1's centre IS its corner", g11.location[:2] == (0.0, 0.0))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("TEMPLATE_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("TEMPLATE_TESTS_OK")


if __name__ == "__main__":
    main()
