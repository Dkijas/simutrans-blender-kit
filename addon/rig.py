"""
The Blender side: build the rig, render the directions, emit sheet + .dat.

Kept as plain functions taking `bpy` so they can be driven headlessly from a
test script (blender --background --python ...) instead of only from the UI.

Camera placement
----------------
With Blender's default XYZ euler and rotation (rx, 0, rz), the camera looks
along R*(0,0,-1) = (-sin(rz)*cos(el'), cos(rz)*cos(el'), -sin(el')) where
el' is the elevation. To aim at the origin we simply sit on the opposite ray.

For elevation 30 and azimuth 45 this puts the camera at
(0.6124D, -0.6124D, 0.5D) - the same ray as the (10, -10, 8.2) quoted on the
German wiki, except that theirs is 30.1 degrees and this is exactly 30.
Distance only affects clipping for an ortho camera, never scale.
"""

import math
import os
import sys

try:
    # installed in Blender: we are <addon-package>.addon.rig
    from ..core import (buildings, colors, datgen, directions, paksets,
                        projection, roadsigns, sheet, ways)
except ImportError:
    # run straight from a checkout (the tests, and `blender --python ...`)
    _HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    from core import (buildings, colors, datgen, directions, paksets,
                      projection, roadsigns, sheet, ways)

CAM_NAME = "SIMUTRANS_CAM"
SUN_NAME = "SIMUTRANS_SUN"

# pak128's devdocs/128painting.txt: "sun shines from south (bottom left corner
# of screen) and it is 60 degrees above real ground in game".
SUN_ELEVATION_DEG = 60.0

# THE SUN MUST TURN WITH THE CAMERA, and this is not a stylistic choice - the
# engine forces it.
#
# In game the view is fixed and the sun is fixed; what turns is the VEHICLE. Our
# rig instead keeps the model still and orbits the camera, which is the same
# image only if the sun orbits too (rotating the model by t == rotating camera
# AND sun by -t). Leave the sun pinned to the world and it ends up pinned to the
# vehicle's body instead of to the screen.
#
# The proof that this is what the engine expects is in vehicle_desc.h: a vehicle
# may ship only 4 images, and the engine then REUSES image[dir-4] for the
# opposite heading (it does not even mirror it). Reuse is only correct if a
# symmetric vehicle looks identical heading north and heading south - i.e. if the
# lighting is fixed relative to the SCREEN. A world-pinned sun would light those
# two sprites differently and the engine's own fallback would look wrong.
#
# Where the sun sits relative to the camera: the docs say it comes from the south,
# the bottom-left corner of the screen. The bottom-left corner of the tile diamond
# is world +Y, so the sun sits at world +Y. In our azimuth convention a body at
# azimuth A sits in world direction (sin A, -cos A), so +Y is azimuth 180, and the
# base camera is at azimuth 135 (see directions.BASE_AZIMUTH_DEG). The sun therefore
# leads the camera by 45 degrees, in every frame.
SUN_OFFSET_FROM_CAMERA_DEG = 45.0

# How hard the sun burns, and how much sky fills the shadow side. These two
# numbers are the entire lighting model, and they only do anything for materials
# made with make_paint_material / make_image_material - a special-colour material
# is emission, and emission does not care about light. That is the point of it.
SUN_STRENGTH = 3.2
AMBIENT_RGB = (150, 165, 185)      # a cool sky, so shadows go blue-grey, not black
AMBIENT_STRENGTH = 0.55


def _prepare_out(out_dir):
    """Make the output directory, and make the path ABSOLUTE first.

    Blender does not resolve a relative render.filepath against the process's
    working directory - it resolves it against the .blend, and an unsaved .blend
    has nowhere to resolve against. Hand it "build/out" and the PNGs land
    somewhere like C:\\build\\out, outside the project, while os.makedirs()
    cheerfully creates the directory you meant. The renders then vanish and the
    slicer fails on a file that "was just written".

    Every test in this kit passes an absolute path, so this never showed up until
    a demo used a relative one. An artist typing a path into the panel would have
    hit it on their first try.
    """
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def clipped_edges(path):
    """Which edges of the cell the sprite runs off -> ('top', 'left', ...).

    A vehicle, a way, a sign and a wayobj are each ONE cell. Model something taller
    than the cell has headroom for and the render simply cuts it: the .pak compiles,
    the game runs, and your locomotive is missing the top of its cab. Nothing warns
    you - the sprite looks like a sprite.

    So ask the pixels. If anything opaque sits in the outermost row or column, the
    model did not fit and what you are looking at is a slice of it.
    """
    w, h, alpha, px = sheet.read_png(path)

    def opaque(x, y):
        p = px[y * w + x]
        return (not alpha) or p[3] > 0

    edges = []
    if any(opaque(x, 0) for x in range(w)):
        edges.append("top")
    if any(opaque(x, h - 1) for x in range(w)):
        edges.append("bottom")
    if any(opaque(0, y) for y in range(h)):
        edges.append("left")
    if any(opaque(w - 1, y) for y in range(h)):
        edges.append("right")
    return tuple(edges)


# WHICH EDGES ARE ALLOWED TO BE TOUCHED, and this is not fussiness.
#
# A road's asphalt REACHES the tile edge - that is the whole point of a road - and
# the ground diamond fills the cell's full width and its bottom half. So a way, a
# wayobj and a sign touch left, right and bottom BY DESIGN, and warning about it
# would be crying wolf on every correct object in the pakset.
#
# The TOP is different. Nothing on the ground has any business up there: the top of
# the cell is headroom, and anything reaching it has been cut off.
GROUND_WATCH = ("top",)
ALL_EDGES = ("top", "bottom", "left", "right")


def warn_if_clipped(frames, what="model", watch=ALL_EDGES):
    """Say so, loudly, if the renders are running off the edge of the cell."""
    bad = {}
    for key, path in frames:
        edges = tuple(e for e in clipped_edges(path) if e in watch)
        if edges:
            bad[key] = edges
    if bad:
        first = sorted(bad)[0]
        print("\n*** THE %s DOES NOT FIT THE TILE ***" % what.upper())
        print("    %d of %d images touch the edge of their cell, so they are being"
              % (len(bad), len(frames)))
        print("    CUT OFF. The .pak will compile and the game will run; your object")
        print("    will simply be missing the parts that fell outside.")
        print("    e.g. %s runs off the %s." % (first, "/".join(bad[first])))
        print("    Make the model smaller, or use a pakset with a bigger tile.\n")
    return bad


def _camera_location(distance, azimuth_deg, elevation_deg, target=(0.0, 0.0, 0.0)):
    """Sit on the ray from `target` back towards the camera.

    For an ortho camera the distance only affects clipping, never scale - what
    matters is the direction, and that the camera AIMS AT THE RIGHT POINT.
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    return (
        target[0] + math.sin(az) * math.cos(el) * distance,
        target[1] - math.cos(az) * math.cos(el) * distance,
        target[2] + math.sin(el) * distance,
    )


def aim_sun(bpy, camera_azimuth_deg):
    """Put the sun where it belongs for a camera at this azimuth.

    Always called with the camera's OWN azimuth, so the two stay locked together
    - see SUN_OFFSET_FROM_CAMERA_DEG for why that is not optional.
    """
    sun = bpy.data.objects.get(SUN_NAME)
    if sun is None:
        return
    sun.rotation_euler = tuple(math.radians(a) for a in (
        90.0 - SUN_ELEVATION_DEG,
        0.0,
        camera_azimuth_deg + SUN_OFFSET_FROM_CAMERA_DEG,
    ))


def scene_bounds(bpy, ignore=(CAM_NAME, SUN_NAME)):
    """(mins, maxs) world-space bounding box of the renderable meshes."""
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    found = False
    for ob in bpy.context.scene.objects:
        if ob.name in ignore or ob.type != "MESH":
            continue
        found = True
        for corner in ob.bound_box:
            world = ob.matrix_world @ __import__("mathutils").Vector(corner)
            for i in range(3):
                mins[i] = min(mins[i], world[i])
                maxs[i] = max(maxs[i], world[i])
    if not found:
        return ([0.0] * 3, [0.0] * 3)
    return (mins, maxs)


def scene_center(bpy, ignore=(CAM_NAME, SUN_NAME)):
    """Centre of the bounding box of the renderable objects.

    Only a convenience for previewing a model that is not yet placed. It is NOT
    the render anchor - see tile_anchor().
    """
    mins, maxs = scene_bounds(bpy, ignore)
    return tuple((mins[i] + maxs[i]) / 2.0 for i in range(3))


def tile_anchor(pakset_name="pak128", align_offset=(0.0, 0.0, 0.0)):
    """The point the camera must aim at, for a model placed on the tile.

    MODEL CONVENTION
        origin (0, 0, 0) is the CENTRE of the tile, at GROUND level;
        the model sits on z = 0 and its nose points along +X.

    Aim the camera here and the tile's ground centre lands where the engine
    expects it - (1/2, 3/4) of the cell, not the cell centre. That is the whole
    of "vehicle alignment": a model on z=0 comes out sitting on the rail.

    align_offset nudges it (world units) for the odd vehicle that does not ride
    the centreline.
    """
    pak = paksets.get(pakset_name)
    lift = projection.camera_target_lift(pak.tile_world)
    return (align_offset[0], align_offset[1], lift + align_offset[2])


def build_rig(bpy, pakset_name="pak128", distance=20.0, target=None):
    """Create/refresh the Simutrans camera, sun and render settings.

    Idempotent: re-running it just re-applies the numbers.
    `target` is the point the camera aims at; None = the tile anchor.
    """
    pak = paksets.get(pakset_name)
    scene = bpy.context.scene
    if target is None:
        target = tile_anchor(pakset_name)

    # --- camera ---
    cam_data = bpy.data.cameras.get(CAM_NAME) or bpy.data.cameras.new(CAM_NAME)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = pak.ortho_scale
    cam_data.clip_start = 0.1
    cam_data.clip_end = distance * 4

    cam = bpy.data.objects.get(CAM_NAME)
    if cam is None:
        cam = bpy.data.objects.new(CAM_NAME, cam_data)
        scene.collection.objects.link(cam)
    cam.data = cam_data

    base_az = directions.BASE_AZIMUTH_DEG
    cam.rotation_euler = tuple(
        math.radians(a) for a in (projection_rot_x(), 0.0, base_az)
    )
    cam.location = _camera_location(distance, base_az, 30.0, target)
    scene.camera = cam

    # --- sun ---
    sun_data = bpy.data.lights.get(SUN_NAME) or bpy.data.lights.new(SUN_NAME, "SUN")
    sun_data.type = "SUN"
    sun = bpy.data.objects.get(SUN_NAME)
    if sun is None:
        sun = bpy.data.objects.new(SUN_NAME, sun_data)
        scene.collection.objects.link(sun)
    sun.data = sun_data
    sun_data.energy = SUN_STRENGTH
    sun_data.angle = 0.0            # a hard sun: crisp facets, no mushy terminator
    aim_sun(bpy, base_az)

    # --- ambient ---
    # Without this the shadow side of every object is BLACK, because a sun is the
    # only light in the scene and nothing bounces off a transparent film. Real
    # pak art has a lit side, a mid side and a shaded side; that third value comes
    # from the sky, so the sky has to exist.
    #
    # Look the background node up by TYPE. Blender names nodes from their
    # TRANSLATED label, so on a Spanish Blender this node is called "Fondo" and
    # nodes.get("Background") quietly returns None.
    world = scene.world or bpy.data.worlds.new("SIMUTRANS_WORLD")
    scene.world = world
    world.use_nodes = True
    for node in world.node_tree.nodes:
        if node.type == "BACKGROUND":
            lin = tuple(srgb_to_linear(c / 255.0) for c in AMBIENT_RGB)
            node.inputs["Color"].default_value = (lin[0], lin[1], lin[2], 1.0)
            node.inputs["Strength"].default_value = AMBIENT_STRENGTH

    # --- render ---
    r = scene.render
    r.resolution_x = pak.tile_px
    r.resolution_y = pak.tile_px
    r.resolution_percentage = 100
    r.film_transparent = True          # alpha, so no magenta key needed
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "8"
    # Simutrans art is matched pixel-for-pixel; the pakset docs say AA off.
    if hasattr(r, "filter_size"):
        r.filter_size = 0.0
    # Blender dithers when it writes 8-bit. Dithering nudges pixel values by a
    # count or two - harmless for photos, fatal for exact-match reserved colours.
    if hasattr(r, "dither_intensity"):
        r.dither_intensity = 0.0

    # CRITICAL for special colours.
    #
    # Blender's default view transform (AgX/Filmic) tone-maps every pixel. A
    # player-colour blue painted as exactly (96,132,167) comes out as something
    # else entirely, and the engine - which matches reserved colours EXACTLY -
    # then fails to recolour it. This is precisely why the legacy pak128.Britain
    # script rendered special colours as separate shadeless masks.
    #
    # 'Standard' means "what you set is what you get", which is the only sane
    # basis for a palette-exact pipeline.
    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0
    except (AttributeError, TypeError):
        pass

    return pak


def srgb_to_linear(c: float) -> float:
    """Blender shader colours are LINEAR; PNG output is sRGB-encoded.

    So to land on an exact sRGB byte value in the file, the material has to be
    fed the linear pre-image of it. Skip this and your player-colour blue is
    silently off by a few counts - which, for exact-match reserved colours,
    means "not a player colour at all".
    """
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_special_color_material(bpy, rgb, name=None):
    """A shadeless material that renders to EXACTLY `rgb` in the output PNG.

    Use for player-colour areas, and for anything else that must survive to the
    pak byte-for-byte. Emission + no shading + Standard view transform = 1:1.
    """
    name = name or "sp_%02X%02X%02X" % rgb
    rgb = tuple(rgb)
    if rgb in colors.RESERVED:
        DECLARED_SPECIAL.add(rgb)      # asked for on purpose; see scan_reserved_colors
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    lin = tuple(srgb_to_linear(c / 255.0) for c in rgb)
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (lin[0], lin[1], lin[2], 1.0)
    emit.inputs["Strength"].default_value = 1.0

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


# Every reserved colour the artist has asked for ON PURPOSE. make_special_color_material
# records them here, so that scan_reserved_colors() can tell the difference between
# "I painted the player-colour stripe" and "the shading happened to land on a
# player-colour blue and the game is about to repaint half my window".
DECLARED_SPECIAL = set()


def make_paint_material(bpy, rgb, name=None, roughness=0.62, metallic=0.0):
    """Ordinary paint: a LIT surface. rgb is the colour in full sunlight.

    This is the material almost everything should use. A special-colour material
    is emission - it ignores the sun completely - which is exactly right for a
    player-colour patch and exactly wrong for a roof, because the whole reason a
    128px sprite reads as a solid object is that its top, its lit side and its
    shaded side are three different values. Paint them all the same and you get a
    sticker.
    """
    name = name or "paint_%02X%02X%02X" % rgb
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    lin = tuple(srgb_to_linear(c / 255.0) for c in rgb)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (lin[0], lin[1], lin[2], 1.0)
    _set_if_present(bsdf, "Roughness", roughness)
    _set_if_present(bsdf, "Metallic", metallic)
    # Kill the specular lobe. A white highlight on a 128px sprite is a blown-out
    # pixel, not a shine, and it is the fastest way to hit a reserved colour.
    _set_if_present(bsdf, "Specular IOR Level", 0.1)

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_image_material(bpy, image, name=None, roughness=0.62):
    """A LIT surface whose colour comes from an image.

    interpolation="Closest" is not a detail. Blender's default bilinear filter
    blends neighbouring texels, so a hard livery edge comes out as a gradient -
    and any player-colour texel gets averaged with its neighbour into a colour
    that is NOT a player colour any more, so the engine stops recolouring it.
    """
    name = name or ("tex_%s" % image.name)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Closest"
    tex.extension = "EXTEND"

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    _set_if_present(bsdf, "Roughness", roughness)
    _set_if_present(bsdf, "Metallic", 0.0)
    _set_if_present(bsdf, "Specular IOR Level", 0.1)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_livery_material(bpy, image, mask, name=None, roughness=0.62):
    """Paint that is LIT, except where the mask says the pixel is a LIGHT.

    A lit window in Simutrans is not a render effect, it is a colour swap: the
    engine keeps a day table and a night table (display/simgraph16.cc) and fades
    one into the other as it gets dark. It matches EXACTLY. So a window texel has
    to arrive in the PNG as precisely (87,101,111) - and a texel that has been
    through a sun, however gently, is not exactly anything.

    Hence two shaders on one surface: Principled for the bodywork, Emission for
    the light texels, and a hard mask to choose. Both read the SAME image, so the
    colour a light shows by day is the colour you painted.
    """
    name = name or ("livery_%s" % image.name)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Closest"
    tex.extension = "EXTEND"

    msk = nt.nodes.new("ShaderNodeTexImage")
    msk.image = mask
    msk.interpolation = "Closest"        # a soft mask would half-light a pixel,
    msk.extension = "EXTEND"             # and half a light colour is no colour

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    _set_if_present(bsdf, "Roughness", roughness)
    _set_if_present(bsdf, "Metallic", 0.0)
    _set_if_present(bsdf, "Specular IOR Level", 0.1)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])

    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(msk.outputs["Color"], mix.inputs["Fac"])
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emit.outputs["Emission"], mix.inputs[2])

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def _set_if_present(node, socket, value):
    if socket in node.inputs:
        node.inputs[socket].default_value = value


def bpy_module():
    """The functions here take `bpy` so they can be tested; the sheet builders
    were written before that mattered and do not. Fetch it where it is needed."""
    import bpy
    return bpy


def new_texture(bpy, name, width, height, background=(255, 255, 255),
                colorspace="sRGB"):
    """A blank RGBA image to paint with paint_rect(), in sRGB byte colours.

    Returns (image, pixels), pixels a flat float list, row 0 at the BOTTOM
    (Blender's convention, not an image editor's).

    The buffer holds the sRGB values AS WRITTEN, and the image is tagged sRGB so
    Blender converts them to linear when the shader samples it. The obvious
    alternative - store linear values and tag the image Non-Color - looks tidier
    and is wrong: a new image is an EIGHT BIT buffer, so the linear value gets
    quantised to a byte, and linear quantisation in the darks is brutal. The
    engine's window colour (87,101,111) came back as nothing recognisable, and
    exactly zero window pixels survived. Store sRGB, let Blender convert.

    Masks want colorspace="Non-Color": they are numbers, not colours.
    """
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, width, height, alpha=True)
    img.colorspace_settings.name = colorspace

    px = [0.0] * (width * height * 4)
    for i in range(width * height):
        px[4 * i:4 * i + 4] = [background[0] / 255.0, background[1] / 255.0,
                               background[2] / 255.0, 1.0]
    return img, px


def paint_rect(px, width, x0, y0, x1, y1, rgb, alpha=1.0):
    """Fill [x0,x1) x [y0,y1) of a pixel buffer with an sRGB byte colour.

    y counts from the BOTTOM, because that is how Blender reads an image.
    """
    val = [rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, alpha]
    for y in range(int(y0), int(y1)):
        base = (y * width + int(x0)) * 4
        for _x in range(int(x1) - int(x0)):
            px[base:base + 4] = val
            base += 4


def commit_texture(img, px):
    img.pixels = px
    img.pack()
    return img


def textured_quad(bpy, name, corners, material, uvs=((0, 0), (1, 0), (1, 1), (0, 1))):
    """A single quad with EXPLICIT uvs. Four corners, counter-clockwise.

    Explicit, because bpy.ops.uv.cube_project has an opinion about which face is
    which and it is not the same opinion as yours.
    """
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(list(corners), [], [(0, 1, 2, 3)])
    mesh.update()

    uv = mesh.uv_layers.new(name="UVMap")
    for i, co in enumerate(uvs):
        uv.data[i].uv = co

    mesh.materials.append(material)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def declare_special(rgb):
    """Say out loud: I am using this reserved colour ON PURPOSE.

    make_special_color_material() declares for you, because asking for a special
    colour by hand IS the declaration. A colour that arrives through a TEXTURE
    cannot declare itself - the window colour of a livery is painted with
    paint_rect() and nothing in the kit can tell it apart from a shading accident.
    So the artist says so, once, and the report can then answer the only question
    worth asking: which reserved pixels did I NOT ask for?
    """
    rgb = tuple(rgb)
    DECLARED_SPECIAL.add(rgb)
    return rgb


def _reserved_hits(bpy, png_path):
    """Every reserved colour actually present in the sheet -> {rgb: count}."""
    img = bpy.data.images.load(png_path, check_existing=False)
    try:
        # Non-Color, or Blender hands back the pixels converted to LINEAR and
        # every byte value we compare against the palette is wrong.
        img.colorspace_settings.name = "Non-Color"
        px = list(img.pixels)
        seen = {}
        for i in range(len(px) // 4):
            if px[4 * i + 3] < 0.5:
                continue                       # transparent: not drawn
            rgb = tuple(min(255, max(0, int(round(px[4 * i + c] * 255.0))))
                        for c in range(3))
            if rgb in colors.RESERVED:
                seen[rgb] = seen.get(rgb, 0) + 1
        return seen
    finally:
        bpy.data.images.remove(img)


def reserved_colour_report(bpy, png_path):
    """-> (intentional, accidental), each {rgb: count}.

    The distinction is the whole point. A player-colour stripe and a night-lit
    window are reserved colours the artist WANTED. A shading pixel that happens to
    land on one is a bug that no tool in the pakset world reports: the engine
    matches these EXACTLY and repaints them at runtime, so a stray pixel turns the
    company colour on somewhere it has no business being, and neither makeobj nor
    the game will ever mention it. pak128's own devdocs/128painting.txt shouts
    about this in five exclamation marks.
    """
    hits = _reserved_hits(bpy, png_path)
    intentional = {k: v for k, v in hits.items() if k in DECLARED_SPECIAL}
    accidental = {k: v for k, v in hits.items() if k not in DECLARED_SPECIAL}
    return intentional, accidental


def scan_reserved_colors(bpy, png_path):
    """The undeclared reserved colours only. See reserved_colour_report()."""
    return reserved_colour_report(bpy, png_path)[1]


def warn_if_reserved_colors(bpy, png_path, what="sheet"):
    hits = scan_reserved_colors(bpy, png_path)
    if not hits:
        return hits
    print("\n*** %s HITS A RESERVED COLOUR BY ACCIDENT ***" % what.upper())
    for line in colors.report(hits):
        print("    %s" % line)
    print("    The engine matches these EXACTLY and will repaint them at runtime.")
    print("    If you meant it, say so with rig.declare_special(rgb).")
    return hits


def projection_rot_x():
    return projection.CAMERA_ROTATION_X_DEG


def render_directions(bpy, out_dir, pakset_name="pak128", dirs=8,
                      basename="vehicle", distance=20.0, align_offset=(0.0, 0.0, 0.0)):
    """Render the 4 or 8 headings. Returns [(dir_code, png_path), ...].

    The model must be placed per the kit's convention: standing on z = 0, its
    centre over the world origin, nose along +X. The camera then aims at
    tile_anchor(), which is what puts the ground where the engine expects it -
    this IS "vehicle alignment", and it is why the loco ends up on the rail
    rather than hovering over it.

    The aim point is computed ONCE and reused for every heading. Recomputing it
    per frame (for instance from the model's own bounding box, which changes
    shape as it turns) would let the vehicle jitter between directions - the
    kind of bug that only shows up once everything is already in the pakset.
    """
    target = tile_anchor(pakset_name, align_offset)

    pak = build_rig(bpy, pakset_name, distance, target=target)
    cam = bpy.data.objects[CAM_NAME]
    scene = bpy.context.scene

    out_dir = _prepare_out(out_dir)
    frames = []
    for code in directions.codes_for(dirs):
        az = directions.azimuth_deg(code)
        cam.rotation_euler = tuple(
            math.radians(a) for a in (projection_rot_x(), 0.0, az)
        )
        cam.location = _camera_location(distance, az, 30.0, target)
        aim_sun(bpy, az)          # the sun rides with the camera, never the model

        path = os.path.join(out_dir, "%s_%s.png" % (basename, code))
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        frames.append((code, path))

    warn_if_clipped(frames, "vehicle")
    return frames


def render_building(bpy, out_dir, pakset_name="pak128", basename="building",
                    size_x=1, size_y=1, layouts=None, seasons=1, season_setup=None,
                    phases=1, phase_setup=None,
                    distance=40.0, align_offset=(0.0, 0.0, 0.0)):
    """Render a building and cut it into the cells the engine addresses.

    MODEL CONVENTION for a building: standing on z = 0, its origin tile over the
    Blender origin, growing EAST (+X) and SOUTH (-Y), with the FACADE - the side
    that should face the road - pointing along -Y, which is the side Blender's own
    Front view looks at.

    South is -Y and not +Y because the engine's world is left-handed and Blender's
    is not; projection.WORLD_AZIMUTH_DEG has the whole argument. Getting this wrong
    does not crash anything - it reflects the building, and the reflection is only
    visible once you look at where the front door ends up.

    A layout is the building turned to face the road; layout L is the model turned
    +90*L (derived in core/buildings.py from the engine's own street table). The
    rig keeps the model still and orbits camera and sun instead, which is the same
    image.

    seasons: only 1, 2, 4 and 5 are worth asking for - the engine NEVER draws a
    third one (core/buildings.SEASON_MEANING).
    phases: animation frames, cycled every animation_time ms.

    season_setup(bpy, season) and phase_setup(bpy, phase) are called before each,
    so the model can put its snow on or move its blades. Both are REQUIRED once
    their count goes above one: without them every image renders identically, the
    .pak compiles, the game runs, and nobody ever finds out that the snow and the
    animation do not exist.

    Each image is cut from ONE render, big enough for the whole building.
    Rendering each cell separately with its own camera would be the obvious thing
    and it would be wrong: the slices have to line up to the pixel, and the only
    way to guarantee that is to cut them out of the same image.

    Returns [( (layout, x, y, h, phase, season), png_path ), ...] with the empty
    top slices dropped. Heights and phases both have to be contiguous from 0 - the
    engine stops at the first one it cannot find, so a hole silently decapitates
    the building or truncates its animation.
    """
    pak = paksets.get(pakset_name)
    tile_px = pak.tile_px
    n_layouts = buildings.layouts_for(size_x, size_y, layouts)

    if seasons not in buildings.SEASON_MEANING:
        raise ValueError("seasons must be 1..5, not %r" % (seasons,))
    if seasons > 1 and season_setup is None:
        raise ValueError("seasons=%d needs a season_setup(bpy, season) callback: "
                         "something has to actually change between them" % seasons)
    if phases > 1 and phase_setup is None:
        raise ValueError("phases=%d needs a phase_setup(bpy, phase) callback: an "
                         "animation whose frames are identical is not an animation"
                         % phases)

    # how tall is the model, in height slices?
    mins, maxs = scene_bounds(bpy)
    px_per_world = tile_px / (math.sqrt(2.0) * pak.tile_world)
    up_px = max(0.0, maxs[2]) * math.cos(math.radians(30.0)) * px_per_world
    heights = max(1, int(math.ceil(up_px / tile_px)) + 1)   # +1, then trim empties

    # AIM AT THE MIDDLE OF THE BUILDING, not at its corner tile. The camera orbits
    # its aim point, so the aim point is the pivot the building turns about - and a
    # layout turns the building about its centre (buildings.footprint_centre). For
    # a 1x1 house the two are the same point, which is exactly why this could be
    # wrong for so long without anything going red.
    #
    # In Blender the footprint runs east (+X) and south (-Y) from the origin tile.
    cx = (size_x - 1) / 2.0 * pak.tile_world
    cy = -(size_y - 1) / 2.0 * pak.tile_world
    target = tile_anchor(pakset_name,
                         (align_offset[0] + cx, align_offset[1] + cy,
                          align_offset[2]))
    build_rig(bpy, pakset_name, distance, target=target)
    scene = bpy.context.scene
    cam = bpy.data.objects[CAM_NAME]
    out_dir = _prepare_out(out_dir)

    frames = []
    for season in range(seasons):
        if season_setup is not None:
            season_setup(bpy, season)

        for phase in range(phases):
            if phase_setup is not None:
                phase_setup(bpy, phase)

            for layout in range(n_layouts):
                width, height, cuts = buildings.canvas_cells(size_x, size_y, layout,
                                                             heights, tile_px)
                scene.render.resolution_x = width
                scene.render.resolution_y = height
                # keep the SAME pixels-per-world as a one-tile render: ortho_scale
                # sizes the LARGER dimension of the frame
                cam.data.ortho_scale = max(width, height) / px_per_world

                az = buildings.layout_azimuth(layout)
                cam.rotation_euler = tuple(math.radians(a)
                                           for a in (projection_rot_x(), 0.0, az))
                cam.location = _camera_location(distance, az, 30.0, target)
                aim_sun(bpy, az)   # the sun rides with the camera, never the model

                big = os.path.join(out_dir, "%s_full_%d_%d_%d.png"
                                   % (basename, layout, phase, season))
                scene.render.filepath = big
                bpy.ops.render.render(write_still=True)

                bw, bh, _alpha, px = sheet.read_png(big)
                for (x, y, h), fleft, ftop in cuts:
                    left = int(round(fleft))
                    top = int(round(ftop))

                    cell = []
                    opaque = False
                    for row in range(tile_px):
                        for col in range(tile_px):
                            sx, sy = left + col, top + row
                            if 0 <= sx < bw and 0 <= sy < bh:
                                p = px[sy * bw + sx]
                                p = p if len(p) == 4 else (p[0], p[1], p[2], 255)
                            else:
                                p = (0, 0, 0, 0)      # outside the render
                            if p[3]:
                                opaque = True
                            cell.append(p)

                    if not opaque and h > 0:
                        continue                      # empty slice above the roof
                    path = os.path.join(out_dir, "%s_%d_%d_%d_%d_%d_%d.png"
                                        % (basename, layout, x, y, h, phase, season))
                    sheet.write_png(path, tile_px, tile_px, cell, has_alpha=True)
                    frames.append(((layout, x, y, h, phase, season), path))

    # keep every height run contiguous from 0
    keep = {}
    for key, path in frames:
        keep.setdefault((key[0], key[1], key[2], key[4], key[5]), []).append(
            (key[3], path))
    out = []
    for group in sorted(keep):
        layout, x, y, phase, season = group
        for h, path in sorted(keep[group]):
            out.append(((layout, x, y, h, phase, season), path))
    return out


WAY_COLLECTION_PREFIX = "way_"


def collection_piece_setup(prefix=WAY_COLLECTION_PREFIX):
    """The default way of telling the rig which piece to render.

    Put each shape in its own collection - way_none, way_end, way_straight,
    way_curve, way_tee, way_cross - and this shows one and hides the rest. An
    artist never has to write a line of Python; a script that wants finer control
    passes its own piece_setup instead.
    """
    def setup(bpy, name):
        wanted = prefix + name
        found = False
        for col in bpy.data.collections:
            if not col.name.startswith(prefix):
                continue
            hide = col.name != wanted
            found = found or not hide
            for ob in col.objects:
                ob.hide_render = hide
        if not found:
            raise ValueError(
                "no collection named %r. A way is modelled as six shapes, one per "
                "collection: %s" % (wanted,
                                    ", ".join(prefix + p for p in ways.PIECE_NAMES)))
    return setup


def render_way(bpy, out_dir, pakset_name="pak128", basename="way",
               pieces=ways.PIECE_NAMES, piece_setup=None, distance=20.0,
               align_offset=(0.0, 0.0, 0.0)):
    """Render a way's sixteen images. Returns [(ribi, png_path), ...].

    MODEL CONVENTION for a way: the piece lies on z = 0, centred on the world
    origin, on a tile that runs from -0.5 to +0.5 in both axes. It is modelled in
    its BASE ribi (core/ways.PIECES) with north = -Y and east = +X - the axes the
    engine itself uses, derived in core/ways from ribi_t::layout_to_ribi[].

    Only SIX shapes have to be modelled. The other ten images are those six turned
    on the tile, because the engine's four direction bits are in compass order and
    a quarter-turn is therefore a rotate-left on the mask. The rig turns the camera
    (and the sun with it) rather than the model, which is the same picture.

    A missing piece is not an error - the writer stores an empty image and the
    engine simply draws nothing. So a road with no `cross` is INVISIBLE at every
    four-way junction, and nothing warns you. ways.missing() will.
    """
    if piece_setup is None:
        piece_setup = collection_piece_setup()

    target = tile_anchor(pakset_name, align_offset)
    pak = build_rig(bpy, pakset_name, distance, target=target)
    cam = bpy.data.objects[CAM_NAME]
    scene = bpy.context.scene
    out_dir = _prepare_out(out_dir)

    frames = []
    current = None
    for ribi, name, turns in ways.plan(pieces):
        if name != current:
            piece_setup(bpy, name)
            current = name

        az = ways.azimuth_for(turns)
        cam.rotation_euler = tuple(math.radians(a)
                                   for a in (projection_rot_x(), 0.0, az))
        cam.location = _camera_location(distance, az, 30.0, target)
        aim_sun(bpy, az)          # the sun rides with the camera, never the model

        path = os.path.join(out_dir, "%s_%s.png" % (basename, ways.code(ribi)))
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        frames.append((ribi, path))

    warn_if_clipped(frames, "way", GROUND_WATCH)
    return frames


def collection_variant_setup(prefix):
    """Seasons, animation phases, signal aspects - all the same shape.

    A variant is ADDITIVE. Everything outside these collections is always there;
    a collection called <prefix>1 holds only the things that appear in variant 1 -
    the snow on the roof, the lit lamp, the green aspect. Variant 0 is the model
    with none of them.

    That is the convention that lets an artist do seasons and animation from the
    panel without writing a line of Python: make a collection, put the snow in it,
    ask for two seasons. It is the same idea as the way pieces, and deliberately
    so - one convention to learn, not four.
    """
    def setup(bpy, index):
        wanted = "%s%d" % (prefix, index)
        for col in bpy.data.collections:
            if not col.name.startswith(prefix):
                continue
            hide = col.name != wanted
            for ob in col.objects:
                ob.hide_render = hide
    return setup


WAYOBJ_COLLECTION_PREFIX = "wayobj_"


def collection_wayobj_setup(prefix=WAYOBJ_COLLECTION_PREFIX):
    """Which piece, and which LAYER of it, to render.

    The same six shapes as a way - wayobj_none, wayobj_end, ... - plus, for each,
    an optional wayobj_<piece>_front holding the parts that must be drawn AFTER the
    vehicles. For catenary that is the wire that crosses over the train; leave it in
    the back collection and the train drives over its own overhead line.

    Flat names rather than a child collection called "front", because Blender's
    collection names are globally unique: six children all called "front" would
    silently become front.001, front.002, and the lookup would find whichever one
    it happened to name first.
    """
    def setup(bpy, piece, layer):
        wanted = prefix + piece + ("_front" if layer == ways.WAYOBJ_FRONT else "")
        found = False
        for col in bpy.data.collections:
            if not col.name.startswith(prefix):
                continue
            hide = col.name != wanted
            found = found or not hide
            for ob in col.objects:
                ob.hide_render = hide
        if not found and layer == ways.WAYOBJ_BACK:
            raise ValueError(
                "no collection named %r. A wayobj is modelled as six shapes, one "
                "per collection: %s" % (wanted, ", ".join(prefix + p
                                                          for p in ways.PIECE_NAMES)))
        # a missing _front collection is fine: that piece has nothing in front
    return setup


def has_front_parts(bpy, prefix=WAYOBJ_COLLECTION_PREFIX):
    """Does this wayobj have anything to draw in front of the vehicles?"""
    return any(col.name.startswith(prefix) and col.name.endswith("_front")
               and col.objects for col in bpy.data.collections)


def render_wayobj(bpy, out_dir, pakset_name="pak128", basename="wayobj",
                  pieces=ways.PIECE_NAMES, piece_setup=None, distance=20.0,
                  align_offset=(0.0, 0.0, 0.0)):
    """Render a wayobj's images. Returns [((layer, ribi), png_path), ...].

    Same sixteen ribis as a way, from the same six models - but each one twice, once
    for what goes behind the vehicles and once for what goes in front. See
    collection_wayobj_setup for how the artist says which is which.
    """
    if piece_setup is None:
        piece_setup = collection_wayobj_setup()

    layers = ways.WAYOBJ_LAYERS if has_front_parts(bpy) else (ways.WAYOBJ_BACK,)

    target = tile_anchor(pakset_name, align_offset)
    build_rig(bpy, pakset_name, distance, target=target)
    cam = bpy.data.objects[CAM_NAME]
    scene = bpy.context.scene
    out_dir = _prepare_out(out_dir)

    frames = []
    for layer in layers:
        for ribi, name, turns in ways.plan(pieces):
            piece_setup(bpy, name, layer)

            az = ways.azimuth_for(turns)
            cam.rotation_euler = tuple(math.radians(a)
                                       for a in (projection_rot_x(), 0.0, az))
            cam.location = _camera_location(distance, az, 30.0, target)
            aim_sun(bpy, az)

            path = os.path.join(out_dir, "%s_%s_%s.png"
                                % (basename, layer, ways.code(ribi)))
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            frames.append(((layer, ribi), path))

    warn_if_clipped(frames, "wayobj", GROUND_WATCH)
    return frames


def build_wayobj_sheet_and_dat(frames, out_dir, pakset_name="pak128",
                               basename="wayobj", cols=4, **dat_kwargs):
    """Assemble the wayobj's sheet and write a compilable .dat next to it."""
    pak = paksets.get(pakset_name)
    out_dir = _prepare_out(out_dir)
    sheet_png = os.path.join(out_dir, "%s.png" % basename)
    placement = sheet.assemble(frames, pak.tile_px, cols=cols, out_path=sheet_png)

    block = ways.wayobj_image_block(basename, placement)
    # the icon has to be a BACK image: the front layer of a straight run is a bare
    # wire on transparency, which makes a button nobody can see
    icon_key = (ways.WAYOBJ_BACK, ways.DEFAULT_ICON_RIBI)
    r, c = placement[icon_key]
    ui = "icon=%s.%d.%d\ncursor=%s.%d.%d" % (basename, r, c, basename, r, c)

    dat_text = ways.wayobj_dat(dat_kwargs.pop("name", basename), block, ui,
                               **dat_kwargs)
    dat_path = os.path.join(out_dir, "%s.dat" % basename)
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write(dat_text)

    return sheet_png, dat_path, placement


def render_roadsign(bpy, out_dir, pakset_name="pak128", basename="sign",
                    states=1, state_setup=None, distance=20.0,
                    align_offset=(0.0, 0.0, 0.0)):
    """Render a sign or signal. Returns [((direction, state), png_path), ...].

    MODEL CONVENTION: the sign stands at the tile's NORTH edge (Blender +Y), facing
    the traffic. The four images are that one model turned, exactly as a way's are.

    states: a plain sign has one. A block signal has TWO, and STATE 0 IS RED
    (obj/roadsign.h:63). state_setup(bpy, state) is called before each and is
    REQUIRED once there is more than one - a signal whose red and green images are
    identical is not a signal, it compiles, and the trains obey it anyway.
    """
    if states > 1 and state_setup is None:
        raise ValueError("states=%d needs a state_setup(bpy, state) callback: a "
                         "signal whose aspects look identical is not a signal "
                         "(state 0 is RED)" % states)

    target = tile_anchor(pakset_name, align_offset)
    build_rig(bpy, pakset_name, distance, target=target)
    cam = bpy.data.objects[CAM_NAME]
    scene = bpy.context.scene
    out_dir = _prepare_out(out_dir)

    frames = []
    current = None
    for direction, state in roadsigns.plan(states):
        if state != current:
            if state_setup is not None:
                state_setup(bpy, state)
            current = state

        az = roadsigns.azimuth_for(direction)
        cam.rotation_euler = tuple(math.radians(a)
                                   for a in (projection_rot_x(), 0.0, az))
        cam.location = _camera_location(distance, az, 30.0, target)
        aim_sun(bpy, az)

        path = os.path.join(out_dir, "%s_%s_%d.png" % (basename, direction, state))
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        frames.append(((direction, state), path))

    warn_if_clipped(frames, "sign", GROUND_WATCH)
    return frames


def build_roadsign_sheet_and_dat(frames, out_dir, pakset_name="pak128",
                                 basename="sign", cols=4, **dat_kwargs):
    """Assemble the sign's sheet and write a compilable .dat next to it."""
    pak = paksets.get(pakset_name)
    out_dir = _prepare_out(out_dir)
    sheet_png = os.path.join(out_dir, "%s.png" % basename)
    placement = sheet.assemble(frames, pak.tile_px, cols=cols, out_path=sheet_png)

    block = roadsigns.image_block(basename, placement)
    ui = roadsigns.ui_block(basename, placement)
    dat_text = roadsigns.roadsign_dat(dat_kwargs.pop("name", basename), block, ui,
                                      **dat_kwargs)
    dat_path = os.path.join(out_dir, "%s.dat" % basename)
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write(dat_text)

    return sheet_png, dat_path, placement


def build_way_sheet_and_dat(frames, out_dir, pakset_name="pak128",
                            basename="way", cols=4, **dat_kwargs):
    """Assemble the way's sheet and write a compilable .dat next to it."""
    pak = paksets.get(pakset_name)
    out_dir = _prepare_out(out_dir)
    sheet_png = os.path.join(out_dir, "%s.png" % basename)
    placement = sheet.assemble(frames, pak.tile_px, cols=cols, out_path=sheet_png)

    block = ways.image_block(basename, placement)
    ui = ways.ui_block(basename, placement)
    dat_text = ways.way_dat(dat_kwargs.pop("name", basename), block, ui, **dat_kwargs)
    dat_path = os.path.join(out_dir, "%s.dat" % basename)
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write(dat_text)

    return sheet_png, dat_path, placement


def build_sheet_and_dat(frames, out_dir, pakset_name="pak128",
                        basename="vehicle", cols=4, **dat_kwargs):
    """Assemble the sheet and write a compilable .dat next to it."""
    pak = paksets.get(pakset_name)
    out_dir = _prepare_out(out_dir)
    sheet_png = os.path.join(out_dir, "%s.png" % basename)
    placement = sheet.assemble(frames, pak.tile_px, cols=cols, out_path=sheet_png)

    warn_if_reserved_colors(bpy_module(), sheet_png, what="the vehicle sheet")

    block = datgen.image_block(basename, placement)
    dat_text = datgen.vehicle_dat(dat_kwargs.pop("name", basename), block,
                                 **dat_kwargs)
    dat_path = os.path.join(out_dir, "%s.dat" % basename)
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write(dat_text)

    return sheet_png, dat_path, placement
