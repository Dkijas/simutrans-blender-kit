"""Variants, components and the preview, inside Blender.

    blender --background --factory-startup --python tests/blender_phase2.py

The pure suites (test_variants, test_package, test_components) check the rules.
This checks the things only Blender can answer, and one of them is the claim the
whole preview feature rests on:

    THE PREVIEW IS THE FINAL RENDER.

Not "matches", not "is kept in step with" - is. test_the_preview_is_the_final_
render below renders one heading through preview() and the same heading through
render_directions(), and demands the PNGs be byte-identical. If they ever differ,
the preview has become a second renderer and the feature should be deleted rather
than debugged.

Prints PHASE2_OK on success.
"""

import hashlib
import json
import os
import shutil
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from addon import library, rig, template, workflow                # noqa: E402
from core import components, package, variants                    # noqa: E402

OUT = os.path.join(_ROOT, "build", "phase2")
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


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


class _Props:
    obj_type = "vehicle"
    pakset = "pak128"
    out_dir = OUT
    dirs = "8"
    basename = "p2loco"
    align_offset = (0.0, 0.0, 0.0)
    length = 16
    size_x = size_y = 1
    seasons = phases = states = 1
    freight_goods = ""
    is_signal = False
    obj_name = "P2_Loco"
    author = "tests"
    factory_mapcolor = 1


# --- THE claim ---------------------------------------------------------------

def test_the_preview_is_the_final_render():
    """Byte-identical, or the feature is a lie.

    rig.render_directions is literally prepare_directions() + a loop of
    render_one_step(). preview() calls those same two functions. So this test is
    not checking that two implementations agree - it is checking that the one
    implementation has not been forked behind our backs.
    """
    clear()
    a_box()
    rig.build_rig(bpy, "pak128")
    p = _Props()

    prev_png, mark = workflow.preview(bpy, OUT, p)
    check("the preview rendered something", os.path.exists(prev_png))
    check("and it recorded what the scene looked like", len(mark) == 64)

    # the final render, same heading, its own basename so nothing is overwritten
    frames = rig.render_directions(bpy, OUT, "pak128", dirs=8,
                                   basename="p2loco_final")
    final = dict(frames)[workflow.PREVIEW_CODE]

    check("the preview and the final render are BYTE-IDENTICAL",
          sha(prev_png) == sha(final),
          "%s vs %s" % (sha(prev_png)[:16], sha(final)[:16]))


def test_the_preview_uses_the_same_camera_object():
    """Not a copy of the rig - the rig."""
    clear()
    a_box()
    p = _Props()
    workflow.preview(bpy, OUT, p)
    cams = [o for o in bpy.data.objects if o.type == "CAMERA"]
    check("there is exactly one camera in the file", len(cams) == 1,
          str([c.name for c in cams]))
    check("and it is the kit's own", cams[0].name == rig.CAM_NAME)


def test_a_stale_preview_is_known_to_be_stale():
    clear()
    ob = a_box()
    p = _Props()
    _png, mark = workflow.preview(bpy, OUT, p)
    check("a fresh preview is not stale", not workflow.is_stale(bpy, p, mark))

    ob.location = (0.0, 0.0, 3.0)
    bpy.context.view_layer.update()
    check("moving the model makes it stale", workflow.is_stale(bpy, p, mark))

    ob.location = (0.0, 0.0, 0.45)
    bpy.context.view_layer.update()
    check("putting it back makes it fresh again",
          not workflow.is_stale(bpy, p, mark))


def test_the_fingerprint_notices_what_matters():
    clear()
    ob = a_box()
    p = _Props()
    base = workflow.fingerprint(bpy, p)

    ob.scale = (3.0, 0.8, 0.9)
    bpy.context.view_layer.update()
    check("a resize is noticed", workflow.fingerprint(bpy, p) != base)
    ob.scale = (2.0, 0.8, 0.9)
    bpy.context.view_layer.update()

    ob.hide_render = True
    check("hiding it from the render is noticed",
          workflow.fingerprint(bpy, p) != base)
    ob.hide_render = False

    mat = rig.make_paint_material(bpy, (200, 0, 0))
    ob.data.materials.append(mat)
    check("a new material is noticed", workflow.fingerprint(bpy, p) != base)

    check("and nothing changed means nothing changed",
          workflow.fingerprint(bpy, p) == workflow.fingerprint(bpy, p))


def test_the_preview_reports_what_the_panel_cannot():
    clear()
    ob = a_box()
    ob.data.materials.append(rig.make_paint_material(bpy, (200, 30, 30)))
    p = _Props()
    png, _m = workflow.preview(bpy, OUT, p)
    lines = workflow.preview_report(bpy, png, p)
    check("it says something about the frame", len(lines) > 0, str(lines))
    check("and it mentions reserved colours either way",
          any("recoloured" in l or "player" in l.lower() or "colour" in l.lower()
              for l in lines), str(lines))


# --- variants on a real scene ------------------------------------------------

def test_a_variant_repaints_without_duplicating_geometry():
    clear()
    ob = a_box()
    mat = rig.make_paint_material(bpy, (128, 128, 128))
    mat.name = "Body"
    ob.data.materials.append(mat)

    meshes_before = len(bpy.data.meshes)
    objects_before = len(bpy.data.objects)

    vs = variants.VariantSet(obj_type="vehicle")
    vs, v = variants.add(vs, "Loco_Green", materials={"Body": (0, 120, 0)})
    changed = workflow.apply_variant(bpy, v, "pak128")

    check("the material was repainted", changed["materials"] == ["Body"])
    check("NO mesh was duplicated", len(bpy.data.meshes) == meshes_before,
          "%d -> %d" % (meshes_before, len(bpy.data.meshes)))
    check("NO object was duplicated", len(bpy.data.objects) == objects_before)
    check("the object now wears the variant's material",
          ob.data.materials[0].name.endswith(v.key),
          ob.data.materials[0].name)


def test_a_variant_shows_and_hides_collections():
    clear()
    ob = a_box("Extra")
    col = bpy.data.collections.new("extra_bits")
    bpy.context.scene.collection.children.link(col)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)

    vs = variants.VariantSet(obj_type="vehicle")
    vs, v = variants.add(vs, "Plain", hide=("extra_bits",))
    workflow.apply_variant(bpy, v, "pak128")
    check("the hidden collection is out of the render", ob.hide_render)

    vs, v2 = variants.add(vs, "Fancy", show=("extra_bits",))
    workflow.apply_variant(bpy, v2, "pak128")
    check("and showing it puts it back", not ob.hide_render)


def test_the_variant_document_survives_a_real_blend():
    """The whole reason the format is one JSON string: it is written and read by
    core/variants.py, so a .blend from an older kit is migrated by the same code
    the tests exercise."""
    clear()
    bpy.types.Scene.simutrans_test = bpy.props.StringProperty()
    try:
        vs = variants.VariantSet(obj_type="vehicle")
        vs, a = variants.add(vs, "Green", materials={"Body": (0, 120, 0)})
        vs, _b = variants.add(vs, "Red", overrides={"power": 800})
        bpy.context.scene.simutrans_test = variants.dump(vs)

        path = os.path.join(OUT, "variants.blend")
        os.makedirs(OUT, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.wm.open_mainfile(filepath=path)

        back = variants.load(bpy.context.scene.simutrans_test)
        check("the variants survived a save and reload", len(back.variants) == 2)
        check("with their keys intact", back.variants[0].key == a.key)
        check("and their overrides", back.variants[0].materials == {"Body": (0, 120, 0)})
    finally:
        del bpy.types.Scene.simutrans_test


def test_an_old_blend_without_the_property_still_opens():
    """Compatibility with a scene made before phase 2 existed."""
    clear()
    a_box()
    vs = variants.load("")
    check("no variant document means no variants", vs.variants == ())
    check("and the scene is otherwise untouched", len(bpy.data.objects) == 1)
    scene = template.describe(bpy, _Props(), rig)
    check("phase 1's own checker still reads it", scene.has_mesh)


# --- components --------------------------------------------------------------

def _make_component(root, key="test_bogie"):
    """Build a component from scratch, in code. We ship no third-party art, and
    the licence on this one is ours because the geometry is."""
    d = os.path.join(root, key)
    os.makedirs(d, exist_ok=True)
    clear()
    col = bpy.data.collections.new("bogie")
    bpy.context.scene.collection.children.link(col)
    ob = a_box("BogieFrame", size=(0.6, 0.5, 0.2), at=(0, 0, 0.1))
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    blend = os.path.join(d, "%s.blend" % key)
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    with open(os.path.join(d, components.SIDECAR), "w", encoding="utf-8") as f:
        json.dump({"schema_version": 1, "key": key, "name": "Test bogie",
                   "category": "bogie", "author": "simutrans-blender-kit tests",
                   "license": "MIT", "version": "1.0.0",
                   "blend": "%s.blend" % key, "collection": "bogie",
                   "anchor": [0.0, 0.0, 0.0], "pakset": ""}, f)
    return d


def test_a_component_is_inserted_with_its_geometry():
    root = os.path.join(OUT, "components")
    shutil.rmtree(root, ignore_errors=True)
    _make_component(root)

    clear()
    a_box()
    before = len(bpy.data.objects)
    comps = components.catalogue(root)
    check("the catalogue found it", len(comps) == 1, str([c.key for c in comps]))

    col = library.insert(bpy, comps[0], components.APPEND, pakset_name="pak128")
    check("a collection arrived", col is not None)
    check("with geometry in it", col is not None and len(col.objects) > 0)
    check("and the scene grew", len(bpy.data.objects) > before)


def test_an_unlicensed_component_is_refused_at_the_door():
    root = os.path.join(OUT, "components_bad")
    shutil.rmtree(root, ignore_errors=True)
    d = _make_component(root, "unlicensed")
    with open(os.path.join(d, components.SIDECAR), encoding="utf-8") as f:
        raw = json.load(f)
    raw["license"] = ""
    with open(os.path.join(d, components.SIDECAR), "w", encoding="utf-8") as f:
        json.dump(raw, f)

    clear()
    comp = components.catalogue(root)[0]
    before = len(bpy.data.objects)
    try:
        library.insert(bpy, comp, components.APPEND, pakset_name="pak128")
        ok = False
    except ValueError as e:
        ok = "licence" in str(e) or "license" in str(e)
    check("inserting an unlicensed component raises", ok)
    check("and nothing was added to the scene", len(bpy.data.objects) == before)


def test_a_component_whose_blend_is_gone_is_refused():
    root = os.path.join(OUT, "components_gone")
    shutil.rmtree(root, ignore_errors=True)
    d = _make_component(root, "vanishing")
    os.remove(os.path.join(d, "vanishing.blend"))
    clear()
    comp = components.catalogue(root)[0]
    try:
        library.insert(bpy, comp, components.APPEND)
        ok = False
    except ValueError:
        ok = True
    check("a component with no .blend raises rather than inserting nothing", ok)


# --- the whole way through ---------------------------------------------------

def test_template_to_package():
    """The phase-1 template, phase-2 variants, and a package at the end - the
    flow the two phases exist to make possible."""
    clear()
    template.create(bpy, "vehicle", "pak128", length=16)
    ob = a_box()
    mat = rig.make_paint_material(bpy, (128, 128, 128))
    mat.name = "Body"
    ob.data.materials.append(mat)
    rig.build_rig(bpy, "pak128")

    out = os.path.join(OUT, "family")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)

    vs = variants.VariantSet(obj_type="vehicle")
    vs, _g = variants.add(vs, "P2_Green", materials={"Body": (0, 120, 0)})
    vs, _r = variants.add(vs, "P2_Red", materials={"Body": (180, 0, 0)},
                          overrides={"power": 800})

    base = {"obj_name": "P2_Base", "author": "tests", "waytype": "track",
            "engine_type": "electric", "speed": 100, "power": 500, "weight": 20,
            "length": 16, "payload": 0, "freight": "None", "cost": 1000,
            "runningcost": 10, "intro_year": 1900}
    errs = variants.blocking(variants.check(
        vs, base, collections=workflow.scene_collections(bpy),
        materials=workflow.scene_materials(bpy)))
    check("the family validates", errs == (), str([f.message for f in errs]))

    made = []
    for v in vs.variants:
        workflow.apply_variant(bpy, v, "pak128")
        fields = variants.resolve(v, base)
        frames = rig.render_directions(bpy, out, "pak128", dirs=4,
                                       basename=v.name)
        _png, dat, _pl = rig.build_sheet_and_dat(
            frames, out, "pak128", basename=v.name, cols=4,
            name=fields["obj_name"], author=fields["author"],
            waytype=fields["waytype"], engine_type=fields["engine_type"],
            speed=fields["speed"], power=fields["power"],
            weight=fields["weight"], length=fields["length"],
            payload=fields["payload"], freight=fields["freight"],
            cost=fields["cost"], runningcost=fields["runningcost"],
            intro_year=fields["intro_year"])
        made.append(dat)

    check("two variants, two .dat files", len(made) == 2)
    from core import schema
    for dat in made:
        with open(dat, encoding="utf-8") as f:
            text = f.read()
        check("%s lints clean" % os.path.basename(dat), not schema.lint(text))
    with open(made[0], encoding="utf-8") as f:
        green = f.read()
    with open(made[1], encoding="utf-8") as f:
        red = f.read()
    check("each carries its OWN name", "name=P2_Green" in green
          and "name=P2_Red" in red)
    check("and the override reached the .dat", "power=800" in red
          and "power=500" in green)

    open(os.path.join(out, "LICENSE.md"), "w").write("CC BY 4.0\n")
    man = package.Manifest(name="P2_Family", author="tests", version="1.0.0",
                           license="CC BY 4.0", pakset="pak128",
                           objects=tuple(v.name for v in vs.variants))
    pkg = package.plan(out, man)
    errs = package.blocking(package.check(pkg))
    check("the package validates", errs == (), str([f.message for f in errs]))

    zip_path = os.path.join(OUT, "P2_Family.zip")
    package.write(pkg, zip_path)
    names, manifest = package.contents(zip_path)
    check("the zip has a manifest", package.MANIFEST_NAME in names)
    check("it lists both objects",
          set(manifest["objects"]) == {"P2_Green", "P2_Red"})
    check("both .dat files are in it",
          all(any(n.endswith(os.path.basename(d)) for n in names) for d in made))
    check("and the sprites too",
          sum(1 for n in names if n.endswith(".png")) >= 2, str(names))


def main():
    print("Blender %s" % bpy.app.version_string)
    os.makedirs(OUT, exist_ok=True)
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("PHASE2_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("PHASE2_OK")


if __name__ == "__main__":
    main()
