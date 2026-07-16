"""Variants applied to a real scene, and a preview that is the render.

core/variants.py is the bookkeeping - keys, overrides, validation, persistence.
This is where a variant meets geometry, and where the preview lives.

THE PREVIEW IS NOT A SECOND RENDERER, AND HERE IS THE PROOF
    addon/rig.py:render_directions is, in full:

        plan, codes = prepare_directions(...)
        frames = [render_one_step(bpy, plan, code) for code in codes]
        warn_if_clipped(frames, "vehicle")
        return frames

    preview() below calls prepare_directions() and render_one_step(). The same
    two functions, in the same order, with the same arguments. Not an equivalent
    path - the same one, fewer headings.

    So "does the preview match the final render?" is not a question about care or
    about keeping two things in step. There is one camera (build_rig), one aim
    point (tile_anchor), one colour management (_fix_colour_management), one
    per-heading render (_render_one_direction). A preview that differed from the
    final render would require render_directions to differ from itself.

    That is the whole reason this is worth having. A preview built by rendering
    the viewport, or with its own camera "set up the same way", would be a second
    thing to keep true - and the day it drifted it would be a preview that lies,
    which is worse than none.

WHEN IS A PREVIEW STALE?
    Anything the render depends on: the meshes, the materials, the pakset, the
    alignment, the variant. fingerprint() hashes those. It is deliberately cheap
    and deliberately conservative - it would rather say "stale" after a change
    that did not matter than say "fresh" after one that did.
"""

import hashlib
import os
import sys

try:
    from . import rig
    from ..core import (colors, contact, night, paksets, scenecheck, sheet,
                        variants)
except ImportError:
    _HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    from addon import rig
    from core import (colors, contact, night, paksets, scenecheck, sheet,
                      variants)


# --- variants on a real scene ------------------------------------------------

def scene_materials(bpy):
    return tuple(sorted(m.name for m in bpy.data.materials))


def scene_collections(bpy):
    from . import template as _t          # noqa: PLC0415 - avoids a cycle
    out = {}
    for col in bpy.data.collections:
        out[col.name] = sum(1 for ob in col.objects if ob.type == "MESH")
    return out


def apply_variant(bpy, variant, pakset_name="pak128"):
    """Make the scene look like this variant -> what was changed.

    Materials are repainted through rig.make_special_color_material, which is the
    only thing that gets a reserved colour through Blender's tone mapping intact.
    A variant that set a material's colour directly would produce a livery the
    engine refuses to recolour - the exact failure the Materials button exists to
    prevent, reintroduced by the back door.
    """
    changed = {"materials": [], "shown": [], "hidden": []}

    for name, rgb in sorted((variant.materials or {}).items()):
        mat = bpy.data.materials.get(name)
        if mat is None:
            continue
        fresh = rig.make_special_color_material(bpy, tuple(rgb),
                                                name="%s__%s" % (name, variant.key))
        for ob in bpy.context.scene.objects:
            if ob.type != "MESH" or not ob.data.materials:
                continue
            for i, slot in enumerate(ob.data.materials):
                if slot is not None and slot.name == name:
                    ob.data.materials[i] = fresh
        changed["materials"].append(name)

    for name in variant.show or ():
        col = bpy.data.collections.get(name)
        if col:
            for ob in col.objects:
                ob.hide_render = False
            changed["shown"].append(name)
    for name in variant.hide or ():
        col = bpy.data.collections.get(name)
        if col:
            for ob in col.objects:
                ob.hide_render = True
            changed["hidden"].append(name)

    return changed


# --- the preview -------------------------------------------------------------

# The heading a single-frame preview shows. `s` is the base heading - the one
# BASE_AZIMUTH_DEG was measured against - so it is the one an artist has any
# hope of comparing against a reference photo.
PREVIEW_CODE = "s"


def fingerprint(bpy, props):
    """A cheap hash of everything the render depends on -> str.

    Conservative on purpose: it would rather call a preview stale after a change
    that did not matter than call it fresh after one that did. A preview believed
    to be current, and not, is worse than no preview.
    """
    h = hashlib.sha256()
    for ob in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if ob.type != "MESH" or ob.name in (rig.CAM_NAME, rig.SUN_NAME):
            continue
        h.update(ob.name.encode("utf-8"))
        h.update(repr(tuple(round(v, 5) for v in ob.location)).encode())
        h.update(repr(tuple(round(v, 5) for v in ob.scale)).encode())
        h.update(repr(tuple(round(v, 5) for v in ob.rotation_euler)).encode())
        h.update(b"1" if ob.hide_render else b"0")
        h.update(repr(len(ob.data.vertices)).encode())
        for slot in ob.data.materials:
            h.update((slot.name if slot else "-").encode("utf-8"))
    for field in ("pakset", "obj_type", "dirs", "basename"):
        h.update(repr(getattr(props, field, "")).encode())
    h.update(repr(tuple(round(v, 5) for v in props.align_offset)).encode())
    return h.hexdigest()


def preview(bpy, out_dir, props, code=PREVIEW_CODE):
    """Render ONE heading, through the final render's own code path.

    -> (png_path, fingerprint). See the module docstring: prepare_directions and
    render_one_step are the two functions render_directions itself is made of.
    """
    plan, codes = rig.prepare_directions(
        bpy, out_dir, props.pakset, dirs=int(props.dirs),
        basename="%s_preview" % props.basename,
        align_offset=tuple(props.align_offset))
    if code not in codes:
        code = codes[0]
    _code, png = rig.render_one_step(bpy, plan, code)
    return png, fingerprint(bpy, props)


def preview_report(bpy, png, props):
    """What the preview can tell you that the panel's numbers cannot.

    Every one of these is an existing check, run against the finished frame - the
    same frame the sheet will be built from. Nothing here is a preview-only rule.
    """
    out = []
    frames = ((PREVIEW_CODE, png),)

    mark = rig.warning_mark()
    rig.warn_if_clipped(frames, "preview")
    out.extend(rig.warnings_since(mark))

    try:
        _w, _h, alpha, px = sheet.read_png(png)
    except (OSError, ValueError):
        return tuple(out)

    rgb = [(q[0], q[1], q[2]) for q in px if not (alpha and q[3] == 0)]
    if not rgb:
        out.append("The frame is empty - nothing landed in the cell")
        return tuple(out)

    hits = colors.scan(rgb)
    out.extend(colors.report(hits) if hits else
               ["No reserved colours - nothing will be recoloured or lit"])
    return tuple(out)


def is_stale(bpy, props, recorded):
    """Has anything the render depends on moved since `recorded`?"""
    return recorded is None or recorded != fingerprint(bpy, props)


def preview_sheet(bpy, out_dir, props, dirs=8):
    """All eight headings, through the final render's own path, on one page.

    -> (contact_png, frames, placement, fingerprint)

    Same two functions as preview(): prepare_directions() and render_one_step().
    The contact sheet is assembled afterwards, by core/contact.py, FROM the
    finished frames - it reads them and writes a separate image. The frames the
    .dat will point at are not touched, and no second renderer exists to drift.
    """
    plan, codes = rig.prepare_directions(
        bpy, out_dir, props.pakset, dirs=int(dirs),
        basename="%s_preview" % props.basename,
        align_offset=tuple(props.align_offset))
    frames = [rig.render_one_step(bpy, plan, code) for code in codes]

    pak = paksets.get(props.pakset)
    dest = os.path.join(out_dir, "%s_contact.png" % props.basename)
    png, place = contact.build(frames, pak.tile_px, dest, cols=4)
    return png, frames, place, fingerprint(bpy, props)


def sheet_report(bpy, frames, place, props, dirs=8):
    """What the contact sheet can tell you -> (str, ...).

    Every check here is an existing one, run against the real frames.
    """
    out = list(contact.report(frames, place, dirs))

    mark = rig.warning_mark()
    rig.warn_if_clipped(frames, "preview")
    out.extend(rig.warnings_since(mark))

    sizes = set()
    for _code, png in frames:
        try:
            w, h, _a, _px = sheet.read_png(png)
            sizes.add((w, h))
        except (OSError, ValueError):
            out.append("could not read %s" % os.path.basename(png))
    if len(sizes) > 1:
        # Every frame must be one img_size cell; image_writer.cc reads
        # image=file.row.col as exactly img_size squared.
        out.append("The headings are not all the same size (%s). The writer "
                   "reads every image as one tile-sized square"
                   % ", ".join("%dx%d" % s for s in sorted(sizes)))
    return tuple(out)


# --- doing something to every variant, and putting the scene back -------------

class SceneRestore:
    """Remember the material slots, put them back afterwards.

    Applying a variant REWRITES material slots - that is not a choice, it is how
    Blender assigns a material to a mesh, and phase 2 said so. What phase 2 did
    not do was put them back: Render All Variants left the last variant applied,
    so an artist who rendered a family found their scene painted in whichever
    livery happened to be last, with no way to tell that from a scene they had
    painted themselves.

    So: a context manager that snapshots (object, slot index) -> material and
    restores it. Used with `with`, it restores on the way out whether the body
    finished, raised, or was cancelled - which are exactly the three cases where
    leaving the scene wrong matters most.

    IT REPORTS ITS OWN FAILURES. `problems` is not empty when something could not
    be put back - an object deleted mid-run, a slot that moved. Silence there
    would be the worst outcome: the artist believes the scene is theirs and it is
    not.
    """

    def __init__(self, bpy):
        self.bpy = bpy
        self.slots = []
        self.active = None
        self.selected = ()
        self.problems = []
        self.restored = False

    def __enter__(self):
        self.snapshot()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.restore()
        return False            # never swallow the exception

    def snapshot(self):
        bpy = self.bpy
        self.slots = []
        for ob in bpy.data.objects:
            if ob.type != "MESH" or not getattr(ob.data, "materials", None):
                continue
            for i, mat in enumerate(ob.data.materials):
                self.slots.append((ob.name, i, mat.name if mat else None))
        self.active = (bpy.context.view_layer.objects.active.name
                       if bpy.context.view_layer.objects.active else None)
        self.selected = tuple(o.name for o in bpy.context.selected_objects)

    def restore(self):
        bpy = self.bpy
        self.problems = []
        for name, i, mat_name in self.slots:
            ob = bpy.data.objects.get(name)
            if ob is None:
                self.problems.append("%s is gone - its materials were not "
                                     "restored" % name)
                continue
            if not getattr(ob.data, "materials", None) or i >= len(ob.data.materials):
                self.problems.append("%s has no material slot %d any more"
                                     % (name, i))
                continue
            want = bpy.data.materials.get(mat_name) if mat_name else None
            if mat_name and want is None:
                self.problems.append("the material %r is gone, so %s slot %d "
                                     "keeps what it has" % (mat_name, name, i))
                continue
            ob.data.materials[i] = want

        for ob in bpy.context.selected_objects:
            ob.select_set(False)
        for name in self.selected:
            ob = bpy.data.objects.get(name)
            if ob is not None:
                ob.select_set(True)
        if self.active:
            ob = bpy.data.objects.get(self.active)
            if ob is not None:
                bpy.context.view_layer.objects.active = ob

        self.restored = not self.problems
        return self.problems

    def findings(self):
        """What to tell the artist -> (Finding, ...). Reuses scenecheck's."""
        if self.restored:
            return (scenecheck.Finding(
                scenecheck.INFORMATION, "restored",
                "The scene is back as it was"),)
        return tuple(scenecheck.Finding(scenecheck.WARNING, "not-restored", p)
                     for p in self.problems)

