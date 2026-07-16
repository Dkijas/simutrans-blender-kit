"""Create Template and Validate, inside Blender, the way the panel calls them.

    blender --background --factory-startup --python tests/blender_template.py

tests/test_templates.py checks the rules without Blender. This checks the things
only Blender can answer:

  * the collections really appear in the file, under the names the renderer reads;
  * the guides do NOT change the model's bounding box - the one that would break
    the render it exists to help;
  * pressing the button twice changes nothing and destroys nothing;
  * a scene built from the template renders, all the way to a .dat.

Prints TEMPLATE_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from addon import rig, template                          # noqa: E402
from core import scenecheck, templates                   # noqa: E402

OUT = os.path.join(_ROOT, "build", "template")
FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def a_box(name="Body", size=(2.0, 0.8, 0.9), at=(0.0, 0.0, 0.45)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=at)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.context.view_layer.update()
    return ob


def collection_names():
    return {c.name for c in bpy.data.collections}


# --- the collections ---------------------------------------------------------

def test_a_way_template_makes_the_renderers_own_collections():
    clear()
    made, kept, _guides = template.create(bpy, "way", "pak128")
    have = collection_names()
    for name in templates.names("way"):
        check("way template made %s" % name, name in have)
    check("and said so", set(made) >= set(templates.names("way")))
    check("nothing was already there", kept == ())


def test_a_tunnel_template_satisfies_the_renderers_own_guard():
    """render_tunnel_portals refuses without a portal. The template must be the
    thing that stops that refusal - checked by asking the guard itself."""
    clear()
    check("no portal before the template", not rig.has_tunnel_model(bpy))
    template.create(bpy, "tunnel", "pak128")
    # the collection exists but is empty; put a mesh in it as an artist would
    ob = a_box("Portal")
    for col in list(ob.users_collection):
        col.objects.unlink(ob)
    bpy.data.collections["tunnel_portal"].objects.link(ob)
    check("with the template and a mesh, the renderer's own guard is satisfied",
          rig.has_tunnel_model(bpy))


def test_a_vehicle_template_makes_no_collections_and_says_so():
    clear()
    made, kept, guides = template.create(bpy, "vehicle", "pak128")
    check("a vehicle needs no collections", made == () and kept == ())
    check("but it does get guides", len(guides) >= 2)


def test_freight_variants_appear_only_when_asked_for():
    clear()
    template.create(bpy, "vehicle", "pak128")
    check("no freight collections by default",
          not any(n.startswith("freight_") for n in collection_names()))
    clear()
    template.create(bpy, "vehicle", "pak128", freight_variants=2)
    check("two asked for, two made",
          {"freight_0", "freight_1"} <= collection_names())
    check("and rig counts them the way render_freight_variants will",
          rig.freight_variant_count(bpy) == 2)


# --- the guides do not disturb the model -------------------------------------

def test_the_guides_do_not_move_the_bounding_box():
    """THE point of making them empties. rig.scene_bounds walks every MESH and
    skips only the camera and the sun BY NAME - it never looks at hide_render. A
    mesh guide would join the box and the framing and clipping checks would then
    measure the guide instead of the model."""
    clear()
    a_box()
    before = rig.scene_bounds(bpy)
    template.create(bpy, "vehicle", "pak128", length=8)
    after = rig.scene_bounds(bpy)
    check("scene_bounds is identical before and after the guides",
          before == after, "%r -> %r" % (before, after))

    # and the same for the biggest guide set there is
    clear()
    a_box()
    before = rig.scene_bounds(bpy)
    template.create(bpy, "building", "pak128", size_x=4, size_y=4, seasons=4)
    after = rig.scene_bounds(bpy)
    check("a 4x4 building's footprint guide does not enter the box either",
          before == after, "%r -> %r" % (before, after))


def test_every_guide_is_an_empty_in_the_file():
    clear()
    template.create(bpy, "vehicle", "pak128")
    holder = bpy.data.collections[templates.GUIDE_COLLECTION]
    check("the guides have their own collection", len(holder.objects) > 0)
    for ob in holder.objects:
        check("%s is an EMPTY, so nothing renders it" % ob.name,
              ob.type == "EMPTY")
        check("%s cannot be clicked and dragged by accident" % ob.name,
              ob.hide_select)


def test_the_guides_follow_the_object_not_the_pakset():
    """A tile is 2.0 Blender units in every shipped pakset - tile_world is pure
    convention and only has to match ortho_scale, which is the camera's business.
    So the tile guide does NOT resize between pak64 and pak128, and an earlier
    version of this test asserted that it did. The code was right; the test (and
    the docstring it was written from) were wrong."""
    clear()
    template.create(bpy, "vehicle", "pak64")
    small = bpy.data.objects["SIMUTRANS_tile"].empty_display_size
    template.create(bpy, "vehicle", "pak128")
    big = bpy.data.objects["SIMUTRANS_tile"].empty_display_size
    check("a tile is the same size in world units in both paksets", small == big,
          "%r vs %r" % (small, big))
    check("and pressing again does not add a second tile guide",
          len([o for o in bpy.data.objects if o.name == "SIMUTRANS_tile"]) == 1)

    # what DOES move a guide is the object's own numbers
    template.create(bpy, "vehicle", "pak128", length=4)
    short = tuple(bpy.data.objects["SIMUTRANS_length"].scale)
    template.create(bpy, "vehicle", "pak128", length=16)
    long_ = tuple(bpy.data.objects["SIMUTRANS_length"].scale)
    check("the length guide follows the declared length", short[0] < long_[0],
          "%r vs %r" % (short, long_))

    # a nose arrow left over from a vehicle would tell a building to face +X
    template.create(bpy, "building", "pak128")
    check("switching to a building removes the vehicle's nose arrow",
          "SIMUTRANS_nose_+X" not in bpy.data.objects)
    check("and gives it a facade marker instead",
          "SIMUTRANS_facade_-Y" in bpy.data.objects)


def test_an_empty_slope_collection_is_not_a_modelled_ramp():
    """The regression this template would have caused, pinned down.

    The template makes way_slope for every way. has_slope_model used to ask only
    whether the collection EXISTED - fine while the only way to have one was to
    make it and fill it, fatal once the kit creates empty ones: ui._render would
    call render_way_slopes on nothing, write blank slope images into the .dat, and
    leave the way invisible on every hill. Silently. Which is the exact thing the
    slope image exists to prevent."""
    clear()
    template.create(bpy, "way", "pak128")
    check("an empty way_slope is NOT a modelled ramp",
          rig.has_slope_model(bpy) is False)
    check("nor is an empty way_slope2",
          rig.has_slope_model(bpy, double=True) is False)

    ob = a_box("Ramp")
    for col in list(ob.users_collection):
        col.objects.unlink(ob)
    bpy.data.collections["way_slope"].objects.link(ob)
    check("put a mesh in it and it is", rig.has_slope_model(bpy) is True)

    clear()
    template.create(bpy, "wayobj", "pak128")
    check("the same for an empty wayobj_slope",
          rig.has_wayobj_slope_model(bpy) is False)


# --- twice is the same as once -----------------------------------------------

def test_pressing_it_twice_changes_nothing():
    clear()
    template.create(bpy, "way", "pak128")
    ob = a_box("MyCurve")
    for col in list(ob.users_collection):
        col.objects.unlink(ob)
    bpy.data.collections["way_curve"].objects.link(ob)

    cols_before = collection_names()
    objs_before = {o.name for o in bpy.data.objects}
    bounds_before = rig.scene_bounds(bpy)

    made, kept, _g = template.create(bpy, "way", "pak128")

    check("the second press makes nothing new", made == ())
    check("it reports what was already there", len(kept) == len(templates.names("way")))
    check("no collection was added or removed", collection_names() == cols_before)
    check("no object was added or removed",
          {o.name for o in bpy.data.objects} == objs_before)
    check("the artist's model is untouched", rig.scene_bounds(bpy) == bounds_before)
    check("and it is still in the collection they put it in",
          "MyCurve" in bpy.data.collections["way_curve"].objects)


def test_it_refuses_to_overwrite_an_artists_object():
    """A guide name collision must not cost anyone their mesh."""
    clear()
    mine = a_box("SIMUTRANS_tile")           # somebody's real, modelled object
    template.create(bpy, "vehicle", "pak128")
    still = bpy.data.objects.get("SIMUTRANS_tile")
    check("an artist's mesh with a guide's name survives",
          still is not None and still.type == "MESH")
    check("and it is the same object", still is mine)


# --- validate ----------------------------------------------------------------

class _Props:
    """The panel's properties, as the operator would pass them."""
    obj_type = "vehicle"
    pakset = "pak128"
    out_dir = "//simutrans"
    length = 16
    size_x = size_y = 1
    seasons = phases = states = 1
    freight_goods = ""
    is_signal = False
    obj_name = "Test_Loco"
    author = "tests"
    factory_mapcolor = 1


def test_validate_reads_a_real_scene():
    clear()
    a_box()
    scene = template.describe(bpy, _Props(), rig)
    check("it sees the mesh", scene.has_mesh)
    check("it measures the box", abs(scene.maxs[0] - scene.mins[0] - 2.0) < 1e-6,
          "%r %r" % (scene.mins, scene.maxs))
    check("it knows the .blend is unsaved", not scene.saved)
    check("it knows the output path is relative", scene.out_relative)

    findings = scenecheck.check(scene)
    codes = [f.code for f in findings]
    check("an unsaved .blend with a '//' path is caught", "unsaved-blend" in codes)


def test_validate_does_not_count_the_guides_as_the_artists_collections():
    clear()
    a_box()
    template.create(bpy, "vehicle", "pak128")
    scene = template.describe(bpy, _Props(), rig)
    check("the guide collection is not offered to the checker",
          templates.GUIDE_COLLECTION not in (scene.collections or {}))


def test_validate_catches_a_bad_scene_and_passes_a_good_one():
    clear()
    a_box(at=(0.0, 0.0, 5.0))                       # floating
    scene = template.describe(bpy, _Props(), rig)._replace(
        saved=True, out_relative=False)
    codes = [f.code for f in scenecheck.check(scene)]
    check("a floating model is caught", "floating" in codes)

    clear()
    a_box()                                          # on the ground, 1 tile long
    scene = template.describe(bpy, _Props(), rig)._replace(
        saved=True, out_relative=False)
    findings = scenecheck.check(scene)
    check("a good scene raises no error", scenecheck.blocking(findings) == (),
          str([f.code for f in findings]))


# --- and the whole thing still renders ---------------------------------------

def test_a_scene_built_from_the_template_renders_to_a_dat():
    """The end of the argument. A template that produces a scene the existing
    pipeline cannot render would be a new way to fail, not a shortcut."""
    clear()
    template.create(bpy, "vehicle", "pak128", length=16)
    a_box()
    rig.build_rig(bpy, "pak128")

    frames = rig.render_directions(bpy, OUT, "pak128", dirs=4,
                                   basename="tmpl_loco")
    check("it rendered the four headings", len(frames) == 4, str(frames))
    png, dat, _pl = rig.build_sheet_and_dat(
        frames, OUT, "pak128", basename="tmpl_loco", cols=4,
        name="Tmpl_Loco", author="tests", waytype="track",
        engine_type="electric", speed=100, power=500, weight=20, length=16,
        payload=0, freight="None", cost=1000, runningcost=10, intro_year=1900)
    check("it wrote a sheet", os.path.exists(png))
    check("it wrote a .dat", os.path.exists(dat))

    from core import schema
    with open(dat, encoding="utf-8") as f:
        findings = schema.lint(f.read())
    check("and the .dat lints clean against the engine schema", not findings,
          str(findings))


def main():
    print("Blender %s" % bpy.app.version_string)
    os.makedirs(OUT, exist_ok=True)
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("TEMPLATE_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("TEMPLATE_OK")


if __name__ == "__main__":
    main()
