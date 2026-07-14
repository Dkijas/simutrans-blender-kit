"""The Renfe Civia (series 463), modelled and liveried with the kit.

    blender --background --python examples/civia.py -- [pakset] [outdir]

A three-car unit, A1 - A3 - A2: two driving cars around one intermediate. Real
figures, from the Spanish Wikipedia article and the works drawing in
assets/refs/civia-elevation.png:

    driving car      22.4 m      (the 462, A1+A2, is 44.8 m over two cars)
    intermediate A3  20.75 m     (the 463 is 65.55 m, so 65.55 - 44.8)
    width            2.94 m
    height           4.265 m
    top speed        120 km/h
    power (463)      1400 kW
    capacity (463)   607, of which 169 seated

Two things here are new, and both of them are the reason the old demo train
looked like a cardboard cut-out:

1. THE TRAIN IS LIT. Everything except the player-colour stripe is painted with
   make_paint_material, which is a real surface that the sun falls on. Roof, lit
   flank and shaded flank come out as three different values, which is what makes
   128 pixels read as a solid object instead of a decal.

2. THE LIVERY IS A TEXTURE, painted here in code: white body, black window band,
   the red pinstripe, the purple lower band, the black skirt. Doors and windows
   are texels, not geometry - at 128px a modelled door frame is one pixel wide and
   costs a hundred faces.

Prints CIVIA_OK.
"""

import math
import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                              # noqa: E402
from core import colors, paksets, schema, sheet    # noqa: E402

_argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PAKSET = _argv[0] if _argv else "pak128"
OUT = _argv[1] if len(_argv) > 1 else os.path.join(_ROOT, "build", "civia")

PAK = paksets.get(PAKSET)
TW = PAK.tile_world
FAILED = []

DRIVER = "CiviaA1"
CENTRE = "CiviaA3"
AUTHOR = "simutrans-blender-kit"

# A tile is taken as 25 m, which is the usual pak128 reading. What actually has
# to hold is that the SPRITE is as long as the `length` says, or the cars stand
# apart / overlap in the convoy: body_world = length/16 * tile_world.
METRES_PER_TILE = 25.0
LEN_DRIVER = 14          # 22.4 m -> 14.3/16 of a tile
LEN_CENTRE = 13          # 20.75 m -> 13.3/16

# Renfe Cercanias, off the works drawing.
WHITE = (226, 226, 228)
BAND = (26, 26, 30)          # the black window band
# NOT a colour I chose. This is the engine's "dark window" (simgraph16.cc), and
# painting the glass EXACTLY this makes it glow warm yellow after dark, all by
# itself, because the engine swaps day colours for night ones. My first guess was
# (86,92,100) - one count out, and the train would have run at night with its
# lights off and nothing would ever have told me.
GLASS = colors.WINDOW_DARK
HEADLIGHT = colors.HEADLIGHT      # near-white by day, yellow by night
RED = (206, 32, 44)
PURPLE = (118, 34, 118)
ROOF = (128, 132, 138)
SKIRT = (32, 33, 36)
BOGIE = (44, 45, 48)
METAL = (168, 172, 178)

TEX_W, TEX_H = 512, 128


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def box(loc, scale, material, bevel=0.0, name="part"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(material)
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return ob


def side_texture(name, doors):
    """The flank, painted, plus the mask that says which texels are LIGHTS.

    Returns (livery, mask). Every window goes into both: into the livery as the
    engine's exact day colour, and into the mask so it is rendered unlit and
    reaches the .pak byte for byte. Shade a window even slightly and it stops
    being a window and starts being a dark grey rectangle that never lights up.
    """
    img, px = rig.new_texture(bpy, name, TEX_W, TEX_H, background=WHITE)
    mimg, mpx = rig.new_texture(bpy, name + "_mask", TEX_W, TEX_H,
                                background=(0, 0, 0), colorspace="Non-Color")

    def rect(x0, y0, x1, y1, rgb, light=False):
        rig.paint_rect(px, TEX_W, x0 * TEX_W, y0 * TEX_H,
                       x1 * TEX_W, y1 * TEX_H, rgb)
        rig.paint_rect(mpx, TEX_W, x0 * TEX_W, y0 * TEX_H,
                       x1 * TEX_W, y1 * TEX_H,
                       (255, 255, 255) if light else (0, 0, 0))

    # bottom of the image is the bottom of the car
    rect(0.0, 0.00, 1.0, 0.13, SKIRT)        # the black underframe
    rect(0.0, 0.13, 1.0, 0.19, PURPLE)       # the purple band
    rect(0.0, 0.19, 1.0, 0.21, RED)          # the red pinstripe above it
    rect(0.0, 0.55, 1.0, 0.78, BAND)         # the black window band
    rect(0.0, 0.50, 1.0, 0.53, RED)          # the red line under the windows

    # windows, inside the black band. These are LIGHTS.
    x = 0.06
    while x < 0.94:
        rect(x, 0.58, min(x + 0.075, 0.94), 0.75, GLASS, light=True)
        x += 0.095

    # the doors: white, full height, and they cut the black band clean through
    for centre in doors:
        rect(centre - 0.045, 0.13, centre + 0.045, 0.80, WHITE)
        rect(centre - 0.047, 0.13, centre - 0.045, 0.80, BAND)   # the frames
        rect(centre + 0.045, 0.13, centre + 0.047, 0.80, BAND)
        rect(centre - 0.001, 0.13, centre + 0.001, 0.80, BAND)   # the leaf split
        rect(centre - 0.035, 0.58, centre + 0.035, 0.75, GLASS, light=True)

    return rig.commit_texture(img, px), rig.commit_texture(mimg, mpx)


def car(length_units, cab, doors):
    """One car, nose along +X. cab=True gives it a driver's end at the nose."""
    clear()
    body_len = length_units / 16.0 * TW
    half = body_len / 2.0
    # To scale off the real thing: 2.94 m wide and 4.265 m tall on a 22.4 m car.
    # The two fudge factors are NOT decoration. True scale reads as a stick at
    # 128px, so pak art is drawn fat - but overdo it and the roof fouls the
    # catenary. These numbers come from standing the train next to pak128's own
    # 620 railcar in a running game and looking at where the contact wire falls;
    # at 1.9 / 1.35 our roof was up in the wire and theirs was well clear of it.
    width = body_len * (2.94 / 22.4) * 1.72
    height = body_len * (4.265 / 22.4) * 1.12
    floor = height * 0.16                        # the skirt hangs below the body

    white = rig.make_paint_material(bpy, WHITE, "white")
    roof_mat = rig.make_paint_material(bpy, ROOF, "roof")
    skirt = rig.make_paint_material(bpy, SKIRT, "skirt")
    bogie = rig.make_paint_material(bpy, BOGIE, "bogie")
    metal = rig.make_paint_material(bpy, METAL, "metal")
    red = rig.make_paint_material(bpy, RED, "red")
    band = rig.make_paint_material(bpy, BAND, "band")

    body_z = floor + height / 2.0

    # the shell, bevelled: a hard cube edge is what makes a model look like a box
    box((0, 0, body_z), (body_len, width, height), white,
        bevel=width * 0.10, name="body")

    # the flanks: the livery lives here
    tex, mask = side_texture("civia_side", doors)
    tex_mat = rig.make_livery_material(bpy, tex, mask, "civia_side")
    y = width / 2.0 + 0.004 * TW
    for sign in (1, -1):
        # counter-clockwise seen from outside, so the texture is not mirrored
        c = [(-half, sign * y, floor), (half, sign * y, floor),
             (half, sign * y, floor + height), (-half, sign * y, floor + height)]
        uvs = ((0, 0), (1, 0), (1, 1), (0, 1))
        if sign < 0:
            c = [(half, sign * y, floor), (-half, sign * y, floor),
                 (-half, sign * y, floor + height), (half, sign * y, floor + height)]
        rig.textured_quad(bpy, "flank_%d" % sign, c, tex_mat, uvs)

    # roof, skirt, bogies
    box((0, 0, floor + height + 0.005 * TW),
        (body_len * 0.985, width * 0.86, height * 0.06), roof_mat,
        bevel=width * 0.03, name="roof")
    box((0, 0, floor / 2.0), (body_len * 0.99, width * 0.92, floor), skirt,
        name="skirt")
    for bx in (-0.32, 0.32):
        box((bx * body_len, 0, floor * 0.42),
            (body_len * 0.17, width * 0.80, floor * 0.85), bogie, name="bogie")

    if cab:
        # The Civia's nose is a BULB. The trick is that the cap must be exactly as
        # wide and as tall as the body it caps - a sphere any larger reads as a
        # ball stuck on the front, which is precisely what the first attempt was.
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=14, radius=0.5,
                                             location=(half, 0, body_z))
        nose = bpy.context.active_object
        nose.name = "nose"
        nose.scale = (width * 0.80, width, height)
        nose.data.materials.append(red)

        # the windscreen: a dark cap on the upper front, following the bulb
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.5,
                                             location=(half + width * 0.04, 0,
                                                       body_z + height * 0.20))
        screen = bpy.context.active_object
        screen.name = "screen"
        screen.scale = (width * 0.78, width * 0.86, height * 0.52)
        screen.data.materials.append(band)

        # Headlights. Emission, and EXACTLY the engine's near-white light colour,
        # so that after dark the engine turns them yellow for us. Two pixels each,
        # and they are what tells a player at a glance which end is the front.
        lamp = rig.make_special_color_material(bpy, HEADLIGHT, "headlight")
        for sy in (-1, 1):
            box((half + width * 0.30, sy * width * 0.28, floor + height * 0.30),
                (width * 0.12, width * 0.16, height * 0.09), lamp,
                name="light_%d" % sy)

        # the skirt continues round the nose
        box((half + width * 0.10, 0, floor * 0.55),
            (width * 0.60, width * 0.88, floor * 1.05), skirt, name="nose_skirt")

        # pantograph, folded, over the far end
        box((-0.30 * body_len, 0, floor + height + height * 0.10),
            (body_len * 0.20, width * 0.62, height * 0.02), metal, name="pan_base")
        box((-0.30 * body_len, 0, floor + height + height * 0.17),
            (body_len * 0.03, width * 0.70, height * 0.015), metal, name="pan_bow")
    else:
        # roof air conditioning, so the intermediate is not a blank slab
        for ax in (-0.22, 0.22):
            box((ax * body_len, 0, floor + height + height * 0.055),
                (body_len * 0.16, width * 0.55, height * 0.05), roof_mat,
                name="ac")

    # THE PLAYER COLOUR. Emission, exact, unlit - it has to survive to the byte or
    # the engine will not recolour it. Kept small and low, where Renfe puts nothing.
    box((0, 0, floor + height * 0.035),
        (body_len * 0.995, width * 1.02, height * 0.035),
        rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3]),
        name="player_stripe")


def count_colour(png_path, rgb):
    """How many opaque pixels landed EXACTLY on this colour."""
    _w, _h, _a, pixels = sheet.read_png(png_path)
    return sum(1 for p in pixels if p[3] > 127 and p[:3] == tuple(rgb))


def build(basename, name, length_units, cab, doors, **dat):
    car(length_units, cab, doors)
    frames = rig.render_directions(bpy, OUT, PAKSET, dirs=8, basename=basename)
    check("%s rendered eight headings" % name, len(frames) == 8, str(len(frames)))

    png, dat_path, _pl = rig.build_sheet_and_dat(
        frames, OUT, PAKSET, basename=basename, cols=4,
        name=name, waytype="track", engine_type="electric",
        freight="Passagiere", length=length_units, speed=120,
        author=AUTHOR, **dat)

    # THE NIGHT CHECK. The windows only light up if the sheet carries the engine's
    # exact day colour; one count out and they stay black after dark, silently.
    # Counting them here is the only way to know before the sun goes down.
    lit = count_colour(png, GLASS)
    check("%s's windows survived to the sheet as the engine's window colour"
          % name, lit > 40, "%d exact pixels of %s" % (lit, GLASS))
    if cab:
        lamps = count_colour(png, HEADLIGHT)
        check("%s's headlights are the engine's light colour" % name, lamps > 8,
              "%d exact pixels of %s" % (lamps, HEADLIGHT))

    with open(dat_path, encoding="utf-8") as f:
        text = f.read()
    findings = schema.lint(text)
    for finding in findings:
        print("       %s: %s" % (name, finding))
    check("%s lints clean" % name, not findings, "%d finding(s)" % len(findings))
    return text


def main():
    os.makedirs(OUT, exist_ok=True)
    print("\n=== %s: Renfe Civia, series 463 ===\n" % PAKSET)

    print("--- A1/A2, the driving car")
    a1 = build("civia_a1", DRIVER, LEN_DRIVER, cab=True,
               doors=(0.30, 0.72),
               power=700, weight=42, payload=190,
               cost=1900000, runningcost=210, intro_year=2004,
               constraint_prev=("none", CENTRE),
               constraint_next=("none", CENTRE))

    print("--- A3, the low-floor intermediate")
    a3 = build("civia_a3", CENTRE, LEN_CENTRE, cab=False,
               doors=(0.22, 0.50, 0.78),
               power=0, weight=22, payload=227,
               cost=800000, runningcost=95, intro_year=2004,
               constraint_prev=(DRIVER,),
               constraint_next=(DRIVER,))

    check("the driving car leads", "Constraint[Prev][0]=none" in a1)
    check("the intermediate can only sit between driving cars",
          "Constraint[Prev][0]=%s" % DRIVER in a3
          and "Constraint[Next][0]=%s" % DRIVER in a3, a3)
    check("the unit is 1400 kW, like the real 463",
          "power=700" in a1, a1)          # two driving cars, 700 kW each
    check("the sprite is as long as the .dat says it is",
          "length=%d" % LEN_DRIVER in a1, a1)

    print("\nout: %s" % OUT)
    if FAILED:
        print("\nCIVIA_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nCIVIA_OK")


main()
