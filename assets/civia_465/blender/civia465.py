"""Renfe Civia S/465 for pak128 - shared components.

Everything here is built with the add-on's own API. Nothing is reimplemented:

    rig.build_rig / rig.render_directions          camera, sun, the 8 headings
    rig.make_paint_material                        lit paint
    rig.new_texture / paint_rect / commit_texture  the livery, painted in code
    rig.make_livery_material                       lit bodywork + UNLIT light texels
    rig.make_special_color_material                player colour, lamps (exact)
    rig.declare_special                            "this reserved colour is on purpose"
    rig.textured_quad                              the flanks, with explicit UVs
    rig.build_sheet_and_dat                        sheet + .dat (+ its own lint)
    colors.WINDOW_DARK / HEADLIGHT / LAMP_RED      the engine's own light table

WHAT THE ENGINE CANNOT DO, and I am not going to pretend otherwise
------------------------------------------------------------------
A vehicle has NO night image. Checked: there is not one light or night key in
descriptor/vehicle_desc.h or descriptor/writer/vehicle_writer.cc. Night lighting
is ONLY the day->night colour swap in display/simgraph16.cc. Therefore:

  * "headlights only on the car that is leading" is not expressible. The sprite is
    fixed; a cab car shows its lamps whether it leads or trails.
  * So each cab gets what a real cab has: white headlights AND red tail lights on
    the same front (look at references/civia-side1.jpg). Whichever end leads, the
    picture is true.
  * The interior glow is per-window: some panes are painted the engine's window
    colour (they light up), some are painted a plain dark grey that is NOT in the
    light table (they never do). That is what stops the band becoming one uniform
    glowing stripe.

DIMENSIONS - what is measured and what is not
---------------------------------------------
Measured (es.wikipedia.org/wiki/Civia, and the works drawing in references/):
    465 = A1-A5-A3-A4-A2, 98.05 m over five cars
    driving car 22.4 m (the two-car 462 is 44.8 m)
    A3 20.75 m (the three-car 463 is 65.55 m, minus the two driving cars)
    A4 14.75 m, A5 17.75 m (from the 464 = 80.30 m and the 465 = 98.05 m)
    width 2.94 m, height 4.265 m, 120 km/h, 2200 kW, 157.3 t, 997 seats/standing
APPROXIMATED (say so, do not dress it up):
    * a tile is taken as 25 m. Simutrans Standard has no metres-per-tile; what
      MUST hold is sprite length == length/16 of a tile, or the cars gap/overlap.
    * bogie positions: the works drawing is not dimensioned. Standard placement.
    * the two "fat" factors below: true scale reads as a stick at 128 px, so pak
      art is drawn wide - but overdo it and the roof fouls the catenary. These
      were set by standing the train next to pak128's own 620 railcar in a
      running game and looking at where the contact wire falls.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Prefer the INSTALLED add-on when there is one. It matters: rig.DECLARED_SPECIAL
# is module state, so if the geometry is built against the checkout's rig and the
# operator validates with the installed rig, the two disagree about which reserved
# colours were on purpose - and the report accuses the artist of their own windows.
try:
    from simutrans_blender_kit.addon import rig                       # noqa: F401
    from simutrans_blender_kit.core import colors, paksets, schema, sheet
except ImportError:
    from addon import rig                                   # noqa: E402
    from core import colors, paksets, schema, sheet         # noqa: E402

PAKSET = "pak128"
PAK = paksets.get(PAKSET)
TW = PAK.tile_world

# The person who modelled this, not the tool that rendered it. copyright= in a
# .dat is the ARTIST's credit; signing it "simutrans-blender-kit" put the kit's
# name on somebody's work. The geometry here is victor_18993's.
AUTHOR = "victor_18993"
METRES_PER_TILE = 25.0          # APPROXIMATION. See the module docstring.

# --------------------------------------------------------------------- palette
# The brief's palette, checked against references/civia-elevation.png and the
# photographs. The purple band and the red pinstripes are in the drawing and are
# not in the brief's list, so they are added here rather than left out.
BODY_HI = (0xF2, 0xF2, 0xF0)
BODY = (0xE4, 0xE5, 0xE3)
BODY_SH = (0xCF, 0xCF, 0xCD)
BODY_DEEP = (0xB9, 0xBB, 0xB9)

RED_HI = (0xE9, 0x4A, 0x50)
RED = (0xD7, 0x26, 0x2E)
RED_SH = (0xA6, 0x1C, 0x21)

GLASS_HI = (0x3A, 0x46, 0x50)       # a pane that will NEVER light at night
GLASS = (0x23, 0x28, 0x2E)          # the window band. Not pure black, on purpose.
GLASS_DEEP = (0x1F, 0x25, 0x2C)

ROOF = (0xD7, 0xD9, 0xDA)
ROOF_SH = (0xB9, 0xBD, 0xC1)
EQUIP = (0x9E, 0xA5, 0xAC)
EQUIP_DET = (0x7E, 0x85, 0x8D)

UNDER = (0x52, 0x56, 0x5B)
BOGIE = (0x3F, 0x43, 0x48)
DARK = (0x2C, 0x2F, 0x33)
DEEP = (0x1F, 0x22, 0x25)

PURPLE = (0x6E, 0x1F, 0x6E)         # off the works drawing
PANTO_INSULATOR = (0x8A, 0x5A, 0x2B)
PANTO_METAL = (0x44, 0x48, 0x4C)

# --------------------------------------------------------- reserved / light use
# Declared ON PURPOSE, so the validator can tell these from an accident.
LIT_PANE = rig.declare_special(colors.WINDOW_DARK)    # -> warm yellow at night
HEADLIGHT = colors.HEADLIGHT                          # -> yellow at night
TAILLIGHT = colors.LAMP_RED                           # red, day and night
PLAYER = colors.PLAYER_RAMP_BLUE[3]

TEX_W, TEX_H = 512, 128


# ------------------------------------------------------------------------ cars
REFERENCE_METRES = 22.4     # the driving car. EVERY car takes its cross-section
                            # from this one.

# EVERY CAR IS length=8. This is not laziness and it is not a guess: I asked the
# pakset. Every single rail vehicle pak128 ships - all four cars of the ACE3-407,
# the Thunder, the BR-373 Eurostar, the 2000 Class, the 620 railcar - reports
# get_length() == 8. Not one of them is anything else.
#
# It matters because of how a convoy is laid out. simconvoi.cc trails each car
# behind the one in front by the length OF THE ONE IN FRONT (finish_rd():
# `step_pos -= v->get_desc()->get_length_in_steps()`, and the depot releases car i
# once the head has driven the summed length of the cars before it). The art,
# meanwhile, sits centred in its cell. Those two only agree when the cars are the
# same length: give them different ones and every joint opens by exactly
# (L_previous - L_this)/2.
#
# I first used the real metres - 22.4, 17.75, 20.75, 14.75 - which gave lengths of
# 14, 11, 13, 9 and joints of +6.7 px, -4.5, +8.9, -11.2: a hole behind every long
# car, an overlap behind every short one. It is plainly visible in the game and it
# is exactly what the arithmetic predicts.
#
# So: one length for all five, the pakset's own. The cost is honest and it is
# recorded in reports/TODO_BALANCE.md - the cars no longer differ in length the way
# the real modules do.
PAK128_VEHICLE_LENGTH = 8


class Car:
    """One car of the unit. metres is measured; length is what the .dat says.

    `reversed_` turns the finished car around. It is not decoration and it is not
    optional: Simutrans draws EVERY vehicle of a convoy with the image for the
    convoy's direction of travel, so a rear cab car modelled with its nose at +X
    shows that nose pointing FORWARDS while it is running at the back of the
    train. The fix is the one pak128 itself uses - look at BR-373_FrontCar and
    BR-373_BackCar, or Thunder_(front_engine) and Thunder_(rear_engine): the tail
    car is a separate object, modelled facing the other way.
    """

    def __init__(self, key, name, metres, cab, panto, doors, seats, tonnes,
                 kilowatts, reversed_=False):
        self.key = key
        self.name = name
        self.metres = metres
        self.cab = cab
        self.panto = panto
        self.doors = doors            # door centres, 0..1 along the car
        self.seats = seats
        self.tonnes = tonnes
        self.kilowatts = kilowatts
        self.reversed_ = reversed_

    @property
    def length(self):
        """Simutrans length, in 1/16 of a tile. The sprite is built to match.

        The same for every car, and the same as every rail vehicle in pak128. See
        PAK128_VEHICLE_LENGTH: mixing lengths inside one convoy is what opens the
        joints, and no pak128 train does it.
        """
        return PAK128_VEHICLE_LENGTH


# The 465 is A1-A5-A3-A4-A2. The pantographs sit on the centre car in the works
# drawing, which is the car the brief calls "intermediate with the electrics".
CAB_A = Car("civia465_cab_a", "CiviaS465_CabA", 22.4, cab=True, panto=False,
            doors=(0.36, 0.78), seats=52, tonnes=34, kilowatts=550)
INT_1 = Car("civia465_intermediate_1", "CiviaS465_Int1", 17.75, cab=False,
            panto=False, doors=(0.22, 0.50, 0.78), seats=64, tonnes=26,
            kilowatts=0)
INT_PANTO = Car("civia465_intermediate_panto", "CiviaS465_IntPanto", 20.75,
                cab=False, panto=True, doors=(0.22, 0.50, 0.78), seats=45,
                tonnes=37, kilowatts=550)
INT_3 = Car("civia465_intermediate_3", "CiviaS465_Int3", 14.75, cab=False,
            panto=False, doors=(0.28, 0.72), seats=64, tonnes=26, kilowatts=0)
CAB_B = Car("civia465_cab_b", "CiviaS465_CabB", 22.4, cab=True, panto=False,
            doors=(0.36, 0.78), seats=52, tonnes=34, kilowatts=550,
            reversed_=True)          # the tail cab faces the other way. See Car.

UNIT = (CAB_A, INT_1, INT_PANTO, INT_3, CAB_B)


# ------------------------------------------------------------------- utilities
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


def cyl(loc, radius, depth, material, axis="Y", name="part"):
    rot = {"X": (0, 1.5708, 0), "Y": (1.5708, 0, 0), "Z": (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=depth,
                                        location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(material)
    return ob


class Body:
    """The proportions every component is placed against. One car, one Body.

    The cross-section comes from the REFERENCE car, never from this one. The first
    build derived width and height from each car's own length, so the short 14.75 m
    module came out narrower and lower than the cab car - a train whose middle is
    thinner than its ends, which does not exist. Only the LENGTH varies from car to
    car; a Civia is one tube, cut into pieces of different lengths.
    """

    def __init__(self, car):
        self.car = car
        self.length = car.length / 16.0 * TW           # sprite == .dat length
        self.half = self.length / 2.0

        # The cross-section is ABSOLUTE: the same on every car, and not derived
        # from the length. It comes from the catenary - these numbers were set by
        # standing the train next to pak128's own 620 railcar in a running game and
        # watching where the contact wire falls. Tie them to the length (which is
        # what I did first) and the short cars come out narrow and low, which is a
        # train whose middle is thinner than its ends.
        self.width = 0.198 * TW
        self.height = 0.187 * TW
        self.floor = self.height * 0.16                # the skirt hangs below
        self.top = self.floor + self.height
        self.mid = self.floor + self.height / 2.0


# ----------------------------------------------------------------- the livery
def livery_texture(car, decals=True):
    """The flank, painted, plus the LIGHT mask. -> (image, mask)

    The zones are the ones in the brief: bodywork, window band, doors, stripes,
    underframe, roof edge. Panel joints and a very light dirt gradient are painted
    in too - flat colour is what makes a 128px sprite look like a sticker.

    decals=False leaves the logos and the unit number off, so the livery can be
    reused or relettered. That is why they are a separate pass and not baked in.
    """
    img, px = rig.new_texture(bpy, "civia_%s" % car.key, TEX_W, TEX_H,
                              background=BODY)
    mimg, mpx = rig.new_texture(bpy, "civia_%s_mask" % car.key, TEX_W, TEX_H,
                                background=(0, 0, 0), colorspace="Non-Color")

    def rect(x0, y0, x1, y1, rgb, light=False):
        rig.paint_rect(px, TEX_W, x0 * TEX_W, y0 * TEX_H, x1 * TEX_W, y1 * TEX_H,
                       rgb)
        rig.paint_rect(mpx, TEX_W, x0 * TEX_W, y0 * TEX_H, x1 * TEX_W, y1 * TEX_H,
                       (255, 255, 255) if light else (0, 0, 0))

    # ---- bodywork, with tonal variation. y=0 is the BOTTOM of the car.
    rect(0.00, 0.86, 1.00, 1.00, BODY_HI)      # the top of the flank catches light
    rect(0.00, 0.21, 1.00, 0.50, BODY)
    rect(0.00, 0.21, 1.00, 0.26, BODY_SH)      # ...and it darkens towards the skirt

    # ---- the underframe
    rect(0.00, 0.00, 1.00, 0.13, DEEP)
    rect(0.00, 0.13, 1.00, 0.15, DARK)

    # ---- the stripes, off the works drawing: purple band between two red lines
    rect(0.00, 0.15, 1.00, 0.20, PURPLE)
    rect(0.00, 0.20, 1.00, 0.215, RED)
    rect(0.00, 0.50, 1.00, 0.515, RED)         # the red line under the windows
    rect(0.00, 0.845, 1.00, 0.86, RED)         # and the one along the roofline

    # ---- the window band. NOT pure black: the brief is right, and so is the art.
    rect(0.00, 0.55, 1.00, 0.82, GLASS)

    # ---- the panes. Alternate lit and unlit so the night band is not a stripe.
    x, i = 0.05, 0
    while x < 0.95:
        w = min(0.076, 0.95 - x)
        if w < 0.03:
            break
        lit = (i % 3) != 1                     # two lit, one dark, repeating
        rect(x, 0.585, x + w, 0.785, LIT_PANE if lit else GLASS_HI, light=lit)
        rect(x, 0.585, x + w, 0.60, GLASS_DEEP)        # a shadow under the pane
        x += 0.095
        i += 1

    # ---- the doors: white, full height, and they cut the band clean through
    for centre in car.doors:
        rect(centre - 0.048, 0.15, centre + 0.048, 0.84, BODY_HI)
        rect(centre - 0.050, 0.15, centre - 0.048, 0.84, DARK)     # frames
        rect(centre + 0.048, 0.15, centre + 0.050, 0.84, DARK)
        rect(centre - 0.002, 0.15, centre + 0.002, 0.84, DARK)     # leaf split
        rect(centre - 0.038, 0.585, centre + 0.038, 0.785, GLASS_HI)
        rect(centre - 0.038, 0.585, centre + 0.038, 0.60, GLASS_DEEP)
        rect(centre - 0.010, 0.44, centre + 0.010, 0.46, RED)      # the door dot

    # ---- panel joints: the thing that stops the flank reading as one flat slab
    for j in range(1, 9):
        jx = j / 9.0
        if any(abs(jx - c) < 0.07 for c in car.doors):
            continue
        rect(jx, 0.215, jx + 0.002, 0.50, BODY_SH)
        rect(jx, 0.86, jx + 0.002, 1.00, BODY_SH)

    # ---- a very light grime gradient along the bottom. No photographic dirt.
    for k in range(6):
        rect(k / 6.0, 0.13, (k + 1) / 6.0, 0.15 + 0.004 * (k % 3), DARK)

    if decals:
        paint_decals(rect, car)

    return rig.commit_texture(img, px), rig.commit_texture(mimg, mpx)


def paint_decals(rect, car):
    """Logos and lettering, kept SEPARATE so they can be switched off.

    At 128 px a car is about 100 px long and the renfe wordmark would be two
    pixels tall. So it is simplified to a mark, not spelled out: a legible smudge
    of the right colour in the right place beats unreadable text, and the brief
    says so.
    """
    rect(0.10, 0.815, 0.16, 0.835, PURPLE)      # the renfe mark, high on the side
    rect(0.05, 0.815, 0.09, 0.835, RED)         # the unit number strip
    if car.cab:
        rect(0.02, 0.52, 0.07, 0.545, PURPLE)   # the wordmark on the cab flank


# -------------------------------------------------------------------- assembly
def build_flanks(b, tex_mat):
    """The two sides. Counter-clockwise from outside, or the livery is mirrored."""
    y = b.width / 2.0 + 0.004 * TW
    for sign in (1, -1):
        if sign > 0:
            corners = [(-b.half, y, b.floor), (b.half, y, b.floor),
                       (b.half, y, b.top), (-b.half, y, b.top)]
        else:
            corners = [(b.half, -y, b.floor), (-b.half, -y, b.floor),
                       (-b.half, -y, b.top), (b.half, -y, b.top)]
        rig.textured_quad(bpy, "flank_%d" % sign, corners, tex_mat,
                          ((0, 0), (1, 0), (1, 1), (0, 1)))


def build_underframe(b, mats):
    """Bajos with volume, and two bogies that read as bogies, not as track."""
    box((0, 0, b.floor / 2.0), (b.length * 0.99, b.width * 0.90, b.floor),
        mats["under"], name="underframe")
    box((0, 0, b.floor * 0.30), (b.length * 0.70, b.width * 0.72, b.floor * 0.55),
        mats["dark"], name="equipment_box")

    for bx in (-0.33, 0.33):                    # APPROXIMATE: see the docstring
        box((bx * b.length, 0, b.floor * 0.44),
            (b.length * 0.16, b.width * 0.80, b.floor * 0.80), mats["bogie"],
            name="bogie")
        for wx in (-0.055, 0.055):              # the wheels, visible below it
            cyl((bx * b.length + wx * b.length, 0, b.floor * 0.16),
                b.floor * 0.30, b.width * 0.86, mats["deep"], axis="Y",
                name="wheelset")


def build_roof(b, mats, panto):
    """Roof with volume and visible equipment - the brief asks for it, and from
    above (which is most of the eight headings) it is half of what you see."""
    box((0, 0, b.top + b.height * 0.010),
        (b.length * 0.985, b.width * 0.88, b.height * 0.04), mats["roof"],
        bevel=b.width * 0.04, name="roof")

    # LOW boxes. The first attempt used height*0.05 and the car came out looking
    # like a double-decker: at this camera angle the roof is most of what you see,
    # so anything standing on it is read as another storey. The reference roof
    # equipment is barely proud of the roof line, and so is this.
    for ax in (-0.30, -0.05, 0.22):
        box((ax * b.length, 0, b.top + b.height * 0.035),
            (b.length * 0.12, b.width * 0.52, b.height * 0.022), mats["equip"],
            name="roof_box")
        box((ax * b.length, 0, b.top + b.height * 0.048),
            (b.length * 0.09, b.width * 0.38, b.height * 0.006),
            mats["equip_det"], name="roof_grille")

    if panto:
        for px_ in (-0.16, 0.16):
            for sy in (-1, 1):                  # the insulators
                box((px_ * b.length, sy * b.width * 0.22,
                     b.top + b.height * 0.075),
                    (b.width * 0.10, b.width * 0.10, b.height * 0.05),
                    mats["insulator"], name="panto_insulator")
            box((px_ * b.length, 0, b.top + b.height * 0.10),
                (b.length * 0.18, b.width * 0.55, b.height * 0.012),
                mats["panto"], name="panto_base")
            # the folded arm and the bow, which is what makes it read as a panto
            box((px_ * b.length + b.length * 0.03, 0, b.top + b.height * 0.16),
                (b.length * 0.14, b.width * 0.06, b.height * 0.010),
                mats["panto"], name="panto_arm")
            box((px_ * b.length + b.length * 0.08, 0, b.top + b.height * 0.21),
                (b.length * 0.02, b.width * 0.62, b.height * 0.012),
                mats["panto"], name="panto_bow")


def build_cab(b, mats):
    """The nose. A bulb, not a wedge - and the cap must be exactly as wide and as
    tall as the body it caps, or it reads as a ball stuck on the front."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=14, radius=0.5,
                                         location=(b.half, 0, b.mid))
    nose = bpy.context.active_object
    nose.name = "nose"
    nose.scale = (b.width * 0.80, b.width, b.height)
    nose.data.materials.append(mats["red"])

    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.5,
                                         location=(b.half + b.width * 0.04, 0,
                                                   b.mid + b.height * 0.20))
    screen = bpy.context.active_object
    screen.name = "windscreen"
    screen.scale = (b.width * 0.78, b.width * 0.86, b.height * 0.52)
    screen.data.materials.append(mats["glass"])

    # A real cab carries BOTH lamps. The engine has no way to switch them by
    # convoy position, so painting both is the only honest picture - and it is
    # what the reference photograph shows.
    for sy in (-1, 1):
        box((b.half + b.width * 0.30, sy * b.width * 0.30,
             b.floor + b.height * 0.34),
            (b.width * 0.11, b.width * 0.15, b.height * 0.08), mats["headlamp"],
            name="headlight")
        box((b.half + b.width * 0.30, sy * b.width * 0.30,
             b.floor + b.height * 0.22),
            (b.width * 0.10, b.width * 0.12, b.height * 0.05), mats["taillamp"],
            name="taillight")

    box((b.half + b.width * 0.10, 0, b.floor * 0.55),
        (b.width * 0.60, b.width * 0.88, b.floor * 1.05), mats["deep"],
        name="nose_skirt")
    box((b.half + b.width * 0.26, 0, b.floor * 0.30),
        (b.width * 0.16, b.width * 0.30, b.floor * 0.55), mats["dark"],
        name="coupler")


def build_end(b, mats, sx):
    """A coupling end: a dark gangway face and a coupler under it.

    EVERY end that is not a cab needs one, INCLUDING the back of a cab car. The
    first build gave the cab car a cab at the front and nothing at all at the back,
    so the bare white end of the shell was left facing the camera - and in the w
    and n headings the car had a blank slab for a tail. It is the sort of thing you
    only see on a contact sheet, which is what the contact sheet is for.
    """
    box((sx * (b.half + 0.002 * TW), 0, b.mid),
        (b.width * 0.05, b.width * 0.86, b.height * 0.90), mats["dark"],
        name="end_wall")
    box((sx * (b.half + b.width * 0.03), 0, b.mid - b.height * 0.05),
        (b.width * 0.10, b.width * 0.46, b.height * 0.55), mats["deep"],
        name="gangway")
    box((sx * (b.half + b.width * 0.06), 0, b.floor * 0.45),
        (b.width * 0.12, b.width * 0.30, b.floor * 0.60), mats["dark"],
        name="coupler")


def materials():
    m = {
        "body": rig.make_paint_material(bpy, BODY, "civia_body"),
        "red": rig.make_paint_material(bpy, RED, "civia_red"),
        "glass": rig.make_paint_material(bpy, GLASS, "civia_glass"),
        "roof": rig.make_paint_material(bpy, ROOF, "civia_roof"),
        "equip": rig.make_paint_material(bpy, EQUIP, "civia_equip"),
        "equip_det": rig.make_paint_material(bpy, EQUIP_DET, "civia_equip_det"),
        "under": rig.make_paint_material(bpy, UNDER, "civia_under"),
        "bogie": rig.make_paint_material(bpy, BOGIE, "civia_bogie"),
        "dark": rig.make_paint_material(bpy, DARK, "civia_dark"),
        "deep": rig.make_paint_material(bpy, DEEP, "civia_deep"),
        "panto": rig.make_paint_material(bpy, PANTO_METAL, "civia_panto"),
        "insulator": rig.make_paint_material(bpy, PANTO_INSULATOR, "civia_insul"),
        # exact, unlit, or the engine will not recognise them
        "headlamp": rig.make_special_color_material(bpy, HEADLIGHT, "civia_head"),
        "taillamp": rig.make_special_color_material(bpy, TAILLIGHT, "civia_tail"),
        "player": rig.make_special_color_material(bpy, PLAYER, "civia_player"),
    }
    return m


def build_car(car, decals=True):
    """One complete car in the scene. Nose along +X, on z=0, at the origin."""
    clear()
    b = Body(car)
    mats = materials()

    box((0, 0, b.mid), (b.length, b.width, b.height), mats["body"],
        bevel=b.width * 0.10, name="shell")

    tex, mask = livery_texture(car, decals=decals)
    build_flanks(b, rig.make_livery_material(bpy, tex, mask,
                                             "civia_livery_%s" % car.key))
    build_underframe(b, mats)
    build_roof(b, mats, car.panto)
    if car.cab:
        build_cab(b, mats)          # the nose is at +X, the coupling end at -X
        build_end(b, mats, -1)
    else:
        build_end(b, mats, -1)
        build_end(b, mats, +1)

    # The player colour. Emission, exact, unlit - low on the skirt, where Renfe
    # puts nothing, so a company colour does not fight the livery.
    box((0, 0, b.floor + b.height * 0.030),
        (b.length * 0.995, b.width * 1.02, b.height * 0.030), mats["player"],
        name="player_stripe")

    if car.reversed_:
        turn_around()
    return b


def turn_around():
    """Spin the finished car 180 degrees about z: the tail cab faces backwards.

    A rigid rotation, not a mirror - so the left flank really does become the right
    flank, which is what happens when you turn a coach round. Doing it here, once,
    beats writing every component twice.
    """
    import math
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        x, y, z = ob.location
        ob.location = (-x, -y, z)
        ob.rotation_euler.z += math.pi
