"""Build the figures for the forum post, out of the kit's own real output.

    blender --background --python tools/make_figures.py

Nothing here is a mock-up. Every sprite in every figure is a PNG the kit actually
rendered in examples/demo_all.py, shown at its true pixel size and scaled up with
nearest-neighbour so it stays crisp. If a figure looks wrong, the tool is wrong.

Blender is doing the compositing because it is already here and it has a font;
there is no Pillow on this machine and a hand-rolled bitmap font would look it.
"""

import math
import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core import sheet, ways                                   # noqa: E402

SRC = os.path.join(_ROOT, "build", "demo_all")
OUT = os.path.join(_ROOT, "dist", "figures")

# Colours are written the way anyone reads them - as they should LOOK - and then
# converted. Blender shader colours are linear; hand it an sRGB value straight and
# everything comes out washed out and pale, which is exactly what happened the first
# time. (Same trap as the player colours: see rig.srgb_to_linear.)
def _lin(c):
    return tuple(c[i] / 12.92 if c[i] <= 0.04045
                 else ((c[i] + 0.055) / 1.055) ** 2.4 for i in range(3))


INK = _lin((0.93, 0.94, 0.96))
DIM = _lin((0.60, 0.63, 0.68))
HOT = _lin((1.00, 0.70, 0.22))
GOOD = _lin((0.40, 0.90, 0.55))
BAD = _lin((1.00, 0.42, 0.42))
BG = _lin((0.10, 0.11, 0.13))
CARD = _lin((0.16, 0.17, 0.20))

PIECE_COLOUR = {
    "none":     _lin((0.60, 0.63, 0.68)),
    "end":      _lin((0.45, 0.72, 1.00)),
    "straight": _lin((0.40, 0.90, 0.55)),
    "curve":    _lin((1.00, 0.72, 0.30)),
    "tee":      _lin((0.95, 0.55, 0.85)),
    "cross":    _lin((1.00, 0.42, 0.42)),
}

U = 1.0            # one blender unit == one sprite


# --------------------------------------------------------------------- scene
def new_scene(view_w, view_h, px_per_unit=130):
    """A page view_w x view_h units. Nothing gets cropped, because the resolution
    and the ortho scale are derived from the SAME numbers - the first version set
    them independently and cut the title off the top."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for im in list(bpy.data.images):
        bpy.data.images.remove(im)

    scene = bpy.context.scene
    scene.render.resolution_x = int(view_w * px_per_unit)
    scene.render.resolution_y = int(view_h * px_per_unit)
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
    except (AttributeError, TypeError):
        pass

    world = bpy.data.worlds.get("FigWorld") or bpy.data.worlds.new("FigWorld")
    world.use_nodes = True

    # NEVER LOOK A NODE UP BY NAME. Blender generates a new node's name from its
    # TRANSLATED label, so on a Spanish Blender the world's background node is
    # called "Fondo" and nodes.get("Background") quietly returns None. The figure
    # then rendered on Blender's default grey and every colour in it was a lie -
    # which is how the steel mast ended up exactly the same grey as the card it
    # stood on, and the "back layer" panel looked empty.
    bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg is None:
        raise SystemExit("the world has no background node")
    bg.inputs[0].default_value = BG + (1.0,)
    bg.inputs[1].default_value = 1.0
    scene.world = world

    cam_data = bpy.data.cameras.new("FIGCAM")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(view_w, view_h)   # Blender fits the LARGER side
    cam = bpy.data.objects.new("FIGCAM", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0, 0, 20)
    cam.rotation_euler = (0, 0, 0)
    scene.camera = cam
    return scene


def _emit_image(path, name):
    """A shadeless material showing the PNG exactly, alpha and all, unfiltered."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(path)
    img.interpolation = "Closest"          # pixel art stays pixel art

    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.0
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")

    nt.links.new(img.outputs["Color"], emit.inputs["Color"])
    nt.links.new(img.outputs["Alpha"], mix.inputs[0])
    nt.links.new(clear.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emit.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])

    for attr, val in (("blend_method", "BLEND"),
                      ("surface_render_method", "BLENDED")):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    return mat


def sprite(path, x, y, w=U, h=None):
    """Put a PNG on the page, centred at (x, y), w units wide."""
    iw, ih, _a, _px = sheet.read_png(path)
    h = h if h is not None else w * ih / float(iw)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, 0))
    ob = bpy.context.active_object
    ob.scale = (w, h, 1)
    ob.data.materials.append(_emit_image(path, os.path.basename(path)))
    return ob


def text(body, x, y, size=0.18, colour=INK, align="CENTER", bold=False):
    bpy.ops.object.text_add(location=(x, y, 0.1))
    ob = bpy.context.active_object
    ob.data.body = body
    ob.data.size = size
    ob.data.align_x = align
    ob.data.align_y = "CENTER"
    if bold:
        ob.data.space_character = 1.06

    mat = bpy.data.materials.new("txt")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = colour + (1.0,)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    ob.data.materials.append(mat)
    return ob


def box(x, y, w, h, colour=CARD):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, -0.05))
    ob = bpy.context.active_object
    ob.scale = (w, h, 1)
    mat = bpy.data.materials.new("box")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = colour + (1.0,)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    ob.data.materials.append(mat)
    return ob


def save(name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    # Say it out loud rather than trust it. The first pass came out washed out
    # because the view transform was still AgX, which lifts the shadows: a
    # background asked for as 0.10 rendered at 0.25, and the steel mast came out the
    # same grey as the card it was sitting on - so the "back layer" panel of the
    # catenary figure looked EMPTY. The exact same trap as the player colours.
    vt = bpy.context.scene.view_settings.view_transform
    if vt != "Standard":
        raise SystemExit("view transform is %r, not Standard - the figure would "
                         "be tone-mapped and the colours would be a lie" % vt)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("figure: %s" % path)


# ------------------------------------------------------------------ figure 1
def fig_workflow():
    """Model -> render -> .dat -> makeobj -> the game."""
    new_scene(14.0, 3.05, 105)

    steps = [
        ("1", "Model it", "in Blender,\nlike anything else"),
        ("2", "Press a button", "the add-on renders\nevery view it needs"),
        ("3", "It writes the .dat", "and checks it against\nthe engine itself"),
        ("4", "makeobj", "one click, from\nthe same panel"),
        ("5", "Play it", "your object is\nin the game"),
    ]
    x = -5.6
    for i, (num, title, sub) in enumerate(steps):
        box(x, -0.22, 2.3, 1.9)
        text(num, x, 0.40, 0.30, HOT)
        text(title, x, -0.04, 0.26, INK)
        text(sub, x, -0.64, 0.16, DIM)
        if i < len(steps) - 1:
            text(">", x + 1.4, -0.22, 0.34, HOT)
        x += 2.8

    text("Simutrans Blender Kit", 0, 1.15, 0.30, INK)
    save("fig1-workflow.png")


# ------------------------------------------------------------------ figure 2
def fig_ways():
    """Six models, sixteen images - the actual road we generated."""
    new_scene(9.4, 9.8, 128)

    text("A road is sixteen images.", 0, 4.15, 0.32, INK)
    text("You model six of them. The kit turns them.", 0, 3.72, 0.20, DIM)

    piece_of = {}
    for ribi, name, turns in ways.plan():
        piece_of[ribi] = (name, turns)

    for ribi in range(16):
        col, row = ribi % 4, ribi // 4
        x = -3.3 + col * 2.2
        y = 2.5 - row * 1.75
        name, turns = piece_of[ribi]
        box(x, y - 0.05, 1.95, 1.5)
        sprite(os.path.join(SRC, "bkroad_%s.png" % ways.code(ribi)), x, y + 0.18, 1.3)
        text("image[%s]" % ways.code(ribi), x, y - 0.48, 0.15, INK)
        turn_txt = name if turns == 0 else "%s, turned %d" % (name, turns)
        text(turn_txt, x, y - 0.68, 0.13, PIECE_COLOUR[name])

    text("the six you model:  none - end - straight - curve - tee - cross",
         0, -3.85, 0.19, HOT)
    text("the other ten are those six, rotated. no extra work.",
         0, -4.18, 0.16, DIM)
    save("fig2-ways.png")


# ------------------------------------------------------------------ figure 3
def fig_vehicle():
    """The eight headings of the loco, straight out of the renderer."""
    new_scene(12.0, 3.8, 122)

    text("One model. Eight headings.", 0, 1.60, 0.28, INK)
    text("The add-on orbits the camera for you - and the sun with it.",
         0, 1.24, 0.17, DIM)

    codes = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
    x = -4.9
    for code in codes:
        box(x, -0.30, 1.15, 1.40)
        sprite(os.path.join(SRC, "bkloco_%s.png" % code), x, -0.10, 1.0)
        text(code.upper(), x, -0.75, 0.18, HOT)
        x += 1.4

    text("EmptyImage[s], EmptyImage[w], ... - written into the .dat for you",
         0, -1.55, 0.16, DIM)
    save("fig3-vehicle.png")


# ------------------------------------------------------------------ figure 4
def fig_building():
    """A building is a grid: four layouts, stacked height slices."""
    new_scene(8.2, 6.1, 140)

    text("A house faces its street.", 0, 2.55, 0.28, INK)
    text("Four layouts, each cut into height slices. The kit does the cutting.",
         0, 2.18, 0.17, DIM)

    where = ("street to the south", "to the east", "to the north", "to the west")
    x = -2.85
    for layout in range(4):
        box(x, -0.05, 1.7, 3.1)
        for h in (1, 0):
            p = os.path.join(SRC, "bkhouse_%d_0_0_%d_0_0.png" % (layout, h))
            if os.path.exists(p):
                sprite(p, x, -0.05 + h * 1.0, 1.35)
        text("layout %d" % layout, x, -1.15, 0.18, HOT)
        text(where[layout], x, -1.38, 0.13, DIM)
        x += 1.9

    text("the door turns with the house - that is the whole point",
         0, -2.35, 0.16, DIM)
    save("fig4-building.png")


# ------------------------------------------------------------------ figure 5
def _over(base_px, top_px, w, h):
    """Alpha-composite top over base. Plain Porter-Duff, nothing clever."""
    out = []
    for i in range(w * h):
        b = base_px[i] if len(base_px[i]) == 4 else base_px[i] + (255,)
        t = top_px[i] if len(top_px[i]) == 4 else top_px[i] + (255,)
        a = t[3] / 255.0
        out.append(tuple(int(round(t[c] * a + b[c] * (1 - a))) for c in range(3))
                   + (max(b[3], t[3]),))
    return out


def fig_catenary():
    """Why the catenary needs two layers - composited from our own sprites."""
    new_scene(10.6, 3.75, 140)

    back = os.path.join(SRC, "bkwire_back_ew.png")
    front = os.path.join(SRC, "bkwire_front_ew.png")
    train = os.path.join(SRC, "bkloco_e.png")

    w, h, _a, bpx = sheet.read_png(back)
    _w, _h, _a2, fpx = sheet.read_png(front)
    _w, _h, _a3, tpx = sheet.read_png(train)

    right = _over(_over(bpx, tpx, w, h), fpx, w, h)      # back, train, front
    wrong = _over(_over(bpx, fpx, w, h), tpx, w, h)      # everything behind

    tmp = os.path.join(OUT, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    p_right = os.path.join(tmp, "right.png")
    p_wrong = os.path.join(tmp, "wrong.png")
    sheet.write_png(p_right, w, h, right, has_alpha=True)
    sheet.write_png(p_wrong, w, h, wrong, has_alpha=True)

    text("The wire goes OVER the train.", 0, 1.55, 0.28, INK)
    text("So the kit renders it in two layers, and puts the right parts in each.",
         0, 1.20, 0.17, DIM)

    panels = ((-3.45, back, "back layer", "the poles - behind the train", INK),
              (-1.15, front, "front layer", "the contact wire", INK),
              (1.1, p_right, "together: RIGHT", "the wire crosses over it", GOOD),
              (3.5, p_wrong, "all in one layer", "the train drives over its own"
               " wire", BAD))
    for x, path, title, sub, col in panels:
        box(x, -0.32, 2.15, 2.5)
        sprite(path, x, 0.10, 1.75)
        text(title, x, -1.05, 0.17, col)
        text(sub, x, -1.30, 0.125, DIM)

    save("fig5-catenary.png")


def main():
    if not os.path.isdir(SRC):
        raise SystemExit("no sprites at %s - run examples/demo_all.py first" % SRC)
    fig_workflow()
    fig_ways()
    fig_vehicle()
    fig_building()
    fig_catenary()
    print("\nFIGURES_OK")


main()
