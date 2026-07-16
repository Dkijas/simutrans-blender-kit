"""Consists, the contact sheet, the real catalogue, and putting the scene back.

    blender --background --factory-startup --python tests/blender_phase3.py

The load-bearing test is test_all_eight_headings_are_byte_identical: EVERY one of
the eight, rendered through the contact sheet's path and through
render_directions(), compared byte for byte. Phase 2 proved it for one heading;
if the sheet ever diverges on any of them it has become a second renderer and
should be deleted rather than debugged.

The other one that matters is test_the_scene_is_put_back: phase 2's Render All
Variants left the last variant applied, so an artist who rendered a family found
their scene painted in whichever livery came last, indistinguishable from one they
had painted themselves.

Prints PHASE3_OK on success.
"""

import hashlib
import os
import shutil
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from addon import library, rig, template, workflow                # noqa: E402
from core import (components, consists, contact, directions, document,  # noqa: E402
                  sheet, variants)

OUT = os.path.join(_ROOT, "build", "phase3")
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
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class _Props:
    obj_type = "vehicle"
    pakset = "pak128"
    out_dir = OUT
    dirs = "8"
    basename = "p3loco"
    align_offset = (0.0, 0.0, 0.0)
    length = 16
    size_x = size_y = 1
    seasons = phases = states = 1
    freight_goods = ""
    is_signal = False
    obj_name = "P3_Loco"
    author = "tests"
    factory_mapcolor = 1


# --- THE claim, for all eight ------------------------------------------------

def test_all_eight_headings_are_byte_identical():
    """Phase 2 proved one heading. This proves the other seven, because a sheet
    that is right about 's' and wrong about 'nw' is worse than no sheet."""
    clear()
    a_box()
    rig.build_rig(bpy, "pak128")
    p = _Props()

    png, frames, place, _mark = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    check("the sheet was written", os.path.exists(png))
    check("eight frames", len(frames) == 8, str([c for c, _ in frames]))

    final = dict(rig.render_directions(bpy, OUT, "pak128", dirs=8,
                                       basename="p3loco_final"))
    prev = dict(frames)
    for code in directions.DIR_CODES:
        check("heading %r is byte-identical to the final render" % code,
              sha(prev[code]) == sha(final[code]),
              "%s vs %s" % (sha(prev[code])[:12], sha(final[code])[:12]))


def test_the_order_is_the_engines_own():
    """directions.DIR_CODES is `s w sw se n e ne nw` - not compass order, and it
    looks like a mistake. It is what vehicle_writer.cc reads, and the real sheet
    is laid out in it. A "sensible" reordering would show the artist a different
    arrangement from the one their .dat describes."""
    clear()
    a_box()
    p = _Props()
    _png, frames, place, _m = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    check("the frames come back in the engine's order",
          [c for c, _p in frames] == list(directions.DIR_CODES),
          str([c for c, _p in frames]))
    check("and the sheet's grid is the real sheet's grid",
          place == sheet.grid_placement(list(directions.DIR_CODES), cols=4),
          str(place))
    check("'s' is the first cell", place["s"] == (0, 0))


def test_the_sheet_does_not_touch_the_frames():
    """A contact sheet that wrote into the frames would corrupt the art the .dat
    points at - to draw a label on it."""
    clear()
    a_box()
    p = _Props()
    _png, frames, _place, _m = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    before = {c: sha(f) for c, f in frames}
    _png2, frames2, _p2, _m2 = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    after = {c: sha(f) for c, f in frames2}
    check("the frames are unchanged by building the sheet twice",
          before == after)
    check("and the sheet is a separate file",
          _png2 not in [f for _c, f in frames2])


def test_the_labels_are_drawn():
    clear()
    a_box()
    p = _Props()
    png, _frames, place, _m = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    _w, _h, _a, px = sheet.read_png(png)
    # Every label draws a black patch with white glyph pixels in it. Both must be
    # there, or the label is invisible on art of its own colour.
    has_black = any(q[:3] == contact.LABEL_BG and q[3] == 255 for q in px)
    has_white = any(q[:3] == contact.LABEL_FG and q[3] == 255 for q in px)
    check("the labels put ink on the page", has_black and has_white)
    check("every heading got a cell", len(place) == 8)


def test_a_missing_heading_is_detected():
    frames = [(c, "x.png") for c in directions.DIR_CODES[:6]]
    gaps = contact.missing(frames, dirs=8)
    check("two headings are reported missing", set(gaps) == {"ne", "nw"},
          str(gaps))
    check("and the report says so",
          any("MISSING" in l for l in contact.report(frames, {}, dirs=8)))
    full = [(c, "x.png") for c in directions.DIR_CODES]
    check("a complete set reports nothing missing",
          contact.missing(full, dirs=8) == ())


def test_the_sheet_reports_clipping_and_size():
    """Both halves. The first version of this test only checked that an oversized
    model produced a message CONTAINING "clip" - it does not; rig says "CUT OFF".
    Grepping for a word I expected rather than the behaviour I meant is how a test
    fails on correct code, which is what happened."""
    clear()
    a_box(size=(6.0, 0.8, 0.9))          # far too long for its cell
    p = _Props()
    _png, frames, place, _m = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    lines = workflow.sheet_report(bpy, frames, place, p, dirs=8)
    check("an oversized model is reported as cut off",
          any("CUT OFF" in l for l in lines), str(lines))
    check("and the report is rig's own warning, not a second implementation",
          any("does not fit the tile" in l for l in lines), str(lines))

    clear()
    a_box()                              # a normal, tile-sized model
    _png, frames, place, _m = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    lines = workflow.sheet_report(bpy, frames, place, p, dirs=8)
    check("a model that fits is NOT reported",
          not any("CUT OFF" in l for l in lines), str(lines))
    check("but the grid is still described",
          any("engine's own order" in l for l in lines), str(lines))


def test_the_sheet_reports_frames_of_different_sizes():
    """image_writer.cc reads every image=file.row.col as exactly img_size squared,
    so a frame of another size is not a smaller sprite - it is a wrong one."""
    clear()
    a_box()
    p = _Props()
    _png, frames, place, _m = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    lines = workflow.sheet_report(bpy, frames, place, p, dirs=8)
    check("frames of one size say nothing about size",
          not any("not all the same size" in l for l in lines), str(lines))


def test_the_fingerprint_still_behaves():
    clear()
    ob = a_box()
    p = _Props()
    _png, _f, _pl, mark = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    check("a fresh sheet is not stale", not workflow.is_stale(bpy, p, mark))

    ob.location = (0, 0, 3.0)
    bpy.context.view_layer.update()
    check("moving the model makes it stale", workflow.is_stale(bpy, p, mark))
    ob.location = (0, 0, 0.45)
    bpy.context.view_layer.update()
    check("putting it back makes it fresh", not workflow.is_stale(bpy, p, mark))

    # a change that cannot reach the render must NOT invalidate it
    before = workflow.fingerprint(bpy, p)
    bpy.context.scene.frame_current = 7
    check("an irrelevant change does not invalidate the preview",
          workflow.fingerprint(bpy, p) == before)


def test_changing_the_camera_changes_the_render():
    clear()
    a_box()
    p = _Props()
    png1, _f, _pl, _m = workflow.preview_sheet(bpy, OUT, p, dirs=8)
    a = sha(png1)

    class Nudged(_Props):
        align_offset = (0.2, 0.0, 0.0)
    png2, _f2, _pl2, _m2 = workflow.preview_sheet(bpy, OUT, Nudged(), dirs=8)
    check("a different alignment gives a different sheet", a != sha(png2))


# --- putting the scene back --------------------------------------------------

def _painted_scene():
    clear()
    ob = a_box()
    mat = rig.make_paint_material(bpy, (128, 128, 128))
    mat.name = "Body"
    ob.data.materials.append(mat)
    return ob


def test_the_scene_is_put_back():
    ob = _painted_scene()
    before = ob.data.materials[0].name

    vs = variants.VariantSet(obj_type="vehicle")
    vs, v = variants.add(vs, "Green", materials={"Body": (0, 120, 0)})
    with workflow.SceneRestore(bpy) as guard:
        workflow.apply_variant(bpy, v, "pak128")
        check("the variant really is applied inside the block",
              ob.data.materials[0].name != before)
    check("and the scene is back afterwards",
          ob.data.materials[0].name == before, ob.data.materials[0].name)
    check("the guard says so", guard.restored)
    check("with nothing to report", guard.problems == [])


def test_the_scene_is_put_back_after_an_exception():
    """The case that matters most: a render that dies halfway must not leave the
    artist's scene painted in a variant."""
    ob = _painted_scene()
    before = ob.data.materials[0].name

    vs = variants.VariantSet(obj_type="vehicle")
    vs, v = variants.add(vs, "Red", materials={"Body": (180, 0, 0)})
    try:
        with workflow.SceneRestore(bpy):
            workflow.apply_variant(bpy, v, "pak128")
            raise RuntimeError("the render died")
    except RuntimeError:
        pass
    check("the scene is back after an exception",
          ob.data.materials[0].name == before)


def test_the_exception_is_not_swallowed():
    """A restore that ate the error would turn a failed render into a silent one."""
    _painted_scene()
    raised = False
    try:
        with workflow.SceneRestore(bpy):
            raise ValueError("boom")
    except ValueError:
        raised = True
    check("the error still reaches the caller", raised)


def test_a_deleted_object_is_reported_not_hidden():
    """If restoration cannot finish, the artist must hear about it. Silence would
    leave them believing the scene is theirs when it is not."""
    ob = _painted_scene()
    guard = workflow.SceneRestore(bpy)
    guard.snapshot()
    bpy.data.objects.remove(ob)
    problems = guard.restore()
    check("the loss is reported", problems != [])
    check("and it names the object", any("Body" in p for p in problems),
          str(problems))
    check("the guard does not claim success", not guard.restored)
    check("and it says so as a WARNING finding",
          [f.code for f in guard.findings()] == ["not-restored"])


def test_a_missing_material_is_reported():
    ob = _painted_scene()
    guard = workflow.SceneRestore(bpy)
    guard.snapshot()
    bpy.data.materials.remove(bpy.data.materials["Body"])
    problems = guard.restore()
    check("a material that vanished is reported", problems != [], str(problems))
    check("and the slot is left alone rather than nulled",
          len(ob.data.materials) == 1)


def test_selection_is_restored():
    ob = _painted_scene()
    other = a_box("Other", at=(3, 0, 0.45))
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

    with workflow.SceneRestore(bpy):
        bpy.ops.object.select_all(action="DESELECT")
        other.select_set(True)
        bpy.context.view_layer.objects.active = other

    check("the selection is back", ob.select_get() and not other.select_get())
    check("and the active object", bpy.context.view_layer.objects.active is ob)


def test_a_clean_scene_is_byte_for_byte_the_same_afterwards():
    """No residue at all - the acceptance criterion, measured rather than asserted."""
    ob = _painted_scene()
    def snapshot():
        return sorted((o.name, tuple(round(v, 6) for v in o.location),
                       tuple(m.name if m else None
                             for m in (o.data.materials if o.type == "MESH" else ())))
                      for o in bpy.data.objects)
    before = snapshot()

    vs = variants.VariantSet(obj_type="vehicle")
    vs, a = variants.add(vs, "A", materials={"Body": (1, 2, 3)})
    vs, b = variants.add(vs, "B", materials={"Body": (4, 5, 6)})
    with workflow.SceneRestore(bpy):
        for v in vs.variants:
            workflow.apply_variant(bpy, v, "pak128")
    check("the scene is identical afterwards", snapshot() == before,
          "%s\n vs \n%s" % (snapshot(), before))


# --- the real catalogue ------------------------------------------------------

def test_the_shipped_catalogue_is_usable():
    """The components/ folder is built by tools/build_components.py from geometry
    defined in that file - so the provenance is the source and the licence is
    unambiguous."""
    root = os.path.join(_ROOT, "components")
    if not os.path.isdir(root):
        check("SKIP: components/ has not been built "
              "(blender --background --python tools/build_components.py)", True)
        return
    comps = components.catalogue(root)
    check("the catalogue has components", len(comps) >= 3, str(len(comps)))
    for c in comps:
        errs = components.blocking(components.check(c))
        check("%s is insertable" % c.key, errs == (),
              str([f.message for f in errs]))
        check("%s has a licence and an author" % c.key,
              c.license.strip() and c.author.strip())
        check("%s uses a relative path" % c.key, not os.path.isabs(c.blend))


def test_a_shipped_component_inserts_at_its_anchor_and_size():
    root = os.path.join(_ROOT, "components")
    if not os.path.isdir(root):
        check("SKIP: components/ has not been built", True)
        return
    comps = {c.key: c for c in components.catalogue(root)}
    if "bogie_2axle" not in comps:
        check("SKIP: no bogie in the catalogue", True)
        return

    clear()
    before = len(bpy.data.objects)
    col = library.insert(bpy, comps["bogie_2axle"], components.APPEND,
                         pakset_name="pak128")
    check("it arrived", col is not None and len(col.objects) > 0)
    check("the scene grew", len(bpy.data.objects) > before)

    mins, maxs = rig.scene_bounds(bpy)
    length = maxs[0] - mins[0]
    check("it sits ON the rail, not through it", mins[2] >= -1e-4,
          "lowest z = %r" % (mins[2],))
    # 2.5 m wheelbase + 0.92 m wheels ~ 3.4 m; a tile is 40 m, so ~0.17 units
    check("it is bogie-sized, not tile-sized", 0.05 < length < 0.5,
          "%r units long" % (length,))


def test_a_component_inserts_into_a_phase_1_template():
    """The acceptance criterion that ties the phases together."""
    root = os.path.join(_ROOT, "components")
    if not os.path.isdir(root):
        check("SKIP: components/ has not been built", True)
        return
    clear()
    template.create(bpy, "vehicle", "pak128", length=16)
    a_box()
    before = rig.scene_bounds(bpy)
    comps = {c.key: c for c in components.catalogue(root)}
    library.insert(bpy, comps["wheelset"], components.APPEND,
                   pakset_name="pak128")
    check("the guides did not swallow the component",
          rig.scene_bounds(bpy) != before)
    check("and the guides are still empties",
          all(o.type == "EMPTY" for o in
              bpy.data.collections["SIMUTRANS_GUIDES"].objects))


# --- consists, end to end ----------------------------------------------------

def test_a_four_and_a_six_car_set_generate_and_render():
    """The acceptance criteria, in one go: two formations sharing vehicles,
    constraints generated, .dat written, lints clean."""
    clear()
    a_box()
    rig.build_rig(bpy, "pak128")
    out = os.path.join(OUT, "family")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)

    cs = consists.ConsistSet()
    cs, c4 = consists.add(cs, "Metro_4")
    for v, pl in (("P3_CabA", consists.HEAD_ONLY), ("P3_Mot", consists.ANYWHERE),
                  ("P3_Trl", consists.ANYWHERE), ("P3_CabB", consists.TAIL_ONLY)):
        cs, _ = consists.add_member(cs, c4.key, v, placement=pl)
    cs, c6 = consists.add(cs, "Metro_6", recommended=True)
    for v, pl in (("P3_CabA", consists.HEAD_ONLY), ("P3_Trl", consists.ANYWHERE),
                  ("P3_Mot", consists.ANYWHERE), ("P3_Mot", consists.ANYWHERE),
                  ("P3_Trl", consists.ANYWHERE), ("P3_CabB", consists.TAIL_ONLY)):
        cs, _ = consists.add_member(cs, c6.key, v, placement=pl)

    known = {"P3_CabA", "P3_CabB", "P3_Mot", "P3_Trl"}
    errs = consists.blocking(consists.check(cs, known=known))
    check("the family validates", errs == (), str([f.message for f in errs]))

    gen = consists.constraints(cs)
    check("the motor accepts both neighbours - the union",
          {"P3_CabA", "P3_Trl"} <= set(gen["P3_Mot"][0]), str(gen["P3_Mot"][0]))

    from core import schema
    frames = rig.render_directions(bpy, out, "pak128", dirs=4, basename="p3car")
    for veh, (prev, nxt) in sorted(gen.items()):
        _png, dat, _pl = rig.build_sheet_and_dat(
            frames, out, "pak128", basename=veh, cols=4, name=veh,
            author="tests", waytype="track", engine_type="electric", speed=100,
            power=500, weight=20, length=16, payload=0, freight="None",
            cost=1000, runningcost=10, intro_year=2000,
            constraint_prev=prev, constraint_next=nxt)
        with open(dat, encoding="utf-8") as f:
            text = f.read()
        check("%s: the .dat lints clean" % veh, not schema.lint(text))
        for i, x in enumerate(prev):
            check("%s: Constraint[Prev][%d]=%s" % (veh, i, x),
                  "Constraint[Prev][%d]=%s" % (i, x) in text)

    check("only the cabs may lead",
          "none" in gen["P3_CabA"][0] and "none" not in gen["P3_Mot"][0])


def test_the_document_holds_variants_and_consists_through_a_blend():
    clear()
    bpy.types.Scene.simutrans_p3 = bpy.props.StringProperty()
    try:
        doc = document.Document()
        doc.variants, _v = variants.add(doc.variants, "Green",
                                        materials={"Body": (0, 120, 0)})
        doc.consists, c = consists.add(doc.consists, "Four")
        doc.consists, _m = consists.add_member(doc.consists, c.key, "CabA",
                                               placement=consists.HEAD_ONLY)
        bpy.context.scene.simutrans_p3 = document.dump(doc)

        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, "doc.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.wm.open_mainfile(filepath=path)

        back = document.load(bpy.context.scene.simutrans_p3)
        check("the variants survived", len(back.variants.variants) == 1)
        check("the consists survived", len(back.consists.consists) == 1)
        check("with their members and placements",
              back.consists.consists[0].members[0].placement == consists.HEAD_ONLY)
    finally:
        del bpy.types.Scene.simutrans_p3


def test_a_phase_2_blend_still_opens():
    """Compatibility: a .blend saved by 0.9.0 has variants at the top level."""
    clear()
    v1 = ('{"schema_version": 1, "obj_type": "vehicle", "next_key": 1, '
          '"axes": {}, "variants": [{"key": "v00000000", "name": "Old", '
          '"overrides": {"power": 500}, "materials": {}, "show": [], '
          '"hide": [], "note": ""}]}')
    doc = document.load(v1)
    check("it opens", len(doc.variants.variants) == 1)
    check("the variant keeps its key", doc.variants.variants[0].key == "v00000000")
    check("and its overrides",
          doc.variants.variants[0].overrides == {"power": 500})
    check("and gains an empty consist set", doc.consists.consists == ())
    check("and is written back at v2", '"schema_version": 2' in document.dump(doc))


def main():
    print("Blender %s" % bpy.app.version_string)
    os.makedirs(OUT, exist_ok=True)
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("PHASE3_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("PHASE3_OK")


if __name__ == "__main__":
    main()
