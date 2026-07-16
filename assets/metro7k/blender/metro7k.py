"""Metro de Madrid Serie 7000 for pak128 - shared components.

Cloned from the Serie 9000 asset, which is its near-identical sibling (same
AnsaldoBreda/Pininfarina carbody). What differs and why is in spec.json and in the
RED DOOR BAND note in livery_texture() - that stripe is the one exterior feature
that tells a 7000 from a 9000.

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
    the same front (the 7000 shares the 9000's Pininfarina panoramic cab, no front
    door). Whichever end leads, the picture is true.
  * The interior glow is per-window: some panes are painted the engine's window
    colour (they light up), some are painted a plain dark grey that is NOT in the
    light table (they never do). That is what stops the band becoming one uniform
    glowing stripe.

DIMENSIONS - what is measured and what is not
---------------------------------------------
Measured (es.wikipedia.org/wiki/Series_7000_y_9000 and vialibre-ffe.com's 7000
ficha). The full sourcing, figure by figure, is in spec.json:
    7000 = Mc-R-M-M-R-Mc, 107 m over six cars
    cab car (Mc) 17.090 m; the four intermediates (R, M) 16.880 m
    width 2.8 m, height 3.65 m, 110 km/h; 198 kW x 16 = 3168 kW (see note)
    capacity 1260 total (payload = ~178 seated); 1500 Vcc; in service 2002
PROVISIONAL / APPROXIMATED / CONTESTED (say so, do not dress it up):
    * weight 200 t is a GUESS - AnsaldoBreda never published the mass. spec.json
      marks it provisional; balance it before anyone plays with it.
    * motor count: sources give "8 o 16" motors. We use 16 (3168 kW) to match the
      9000; spec.json records the conflict. Pantograph position is unconfirmed and
      placed on the cab cars, as on the 9000 - confirm against a photo.
    * a tile is taken as 25 m. Simutrans Standard has no metres-per-tile; what
      MUST hold is sprite length == length/16 of a tile, or the cars gap/overlap.
    * bogie positions: not dimensioned anywhere. Standard placement.
    * the two "fat" factors below: true scale reads as a stick at 128 px, so pak
      art is drawn wide - but overdo it and the roof fouls the catenary. These
      were set by standing the train next to pak128's own 620 railcar in a
      running game and looking at where the contact wire falls.
"""

import os
import sys

import bpy

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # assets/metro7k
_ROOT = os.path.dirname(os.path.dirname(_PROJ))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# The brief, validated. Not the add-on's - see tools/spec.py, and note that the
# zip builder refuses to ship anything that imports it: this is a fact about how WE
# work, not a feature a stranger downloading a sprite tool should inherit.
#
# Loaded HERE, at import, because the numbers below come out of it. They used to be
# literals in this file, where spec.py could not see them, and the split shipped
# wrong once already. A number you cannot type twice cannot drift.
from tools import spec as _spec                       # noqa: E402
SPEC = _spec.load(os.path.join(_PROJ, "spec.json"))

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

# The artist who modelled it, not the tool. See civia465.py for the reasoning:
# copyright= is the modeller's credit and this geometry is victor_18993's.
AUTHOR = "victor_18993"
METRES_PER_TILE = 25.0          # APPROXIMATION. See the module docstring.

# --------------------------------------------------------------------- palette
#
# WHERE THESE COME FROM, AND WHAT THAT IS WORTH.
#
# The blue is measured, off the nose of the real thing in
# references/real_serie9000_1.jpg (Wikimedia Commons, CC BY-SA 4.0): #2748B6.
# The rest of the flank could NOT be measured, and here is the honest reason:
# station light contaminates every photograph of an underground train. The same
# ivory bodywork sampled #C2C3A4 - a greenish khaki - under one station's lamps,
# and the same blue came out #2748B6 in one photo and #1A2267 in another. Two
# photographs of one train disagreeing by that much are not measuring the train,
# they are measuring the bulb.
#
# So: the blue is taken from the best-lit surface in the sharpest photo, and the
# ivory is set to what an ivory IS, not to what a yellow lamp made of it. Both are
# `provisional` in spec.json, and they say so.
#
# The LAYOUT, though, is not a judgement call and is not from the generated
# elevation: it is read straight off the photographs. Metro de Madrid's corporate
# livery is ivory with a BLUE BAND HIGH on the flank, right under the roof - see
# the close-up of car S-9004, where the band sits above the ivory and below the
# dark roof. The generated drawing put its blue stripe down at the skirt. That is
# the one thing it got wrong, and it is the one thing that would have been visible
# in the game.
BODY_HI = (0xF4, 0xF3, 0xEC)        # ivory, catching the light
BODY = (0xE9, 0xE7, 0xDD)           # Metro de Madrid ivory
BODY_SH = (0xD2, 0xD0, 0xC6)
BODY_DEEP = (0xB8, 0xB6, 0xAC)

BLUE_HI = (0x3A, 0x5C, 0xCE)
BLUE = (0x27, 0x48, 0xB6)           # MEASURED: the nose, real_serie9000_1.jpg
BLUE_SH = (0x1C, 0x33, 0x80)

RED_HI = (0xD8, 0x4A, 0x35)
RED = (0xB2, 0x31, 0x1C)            # MEASURED: the lamp panels, same photograph
RED_SH = (0x86, 0x23, 0x14)

GLASS_HI = (0x3A, 0x46, 0x50)       # a pane that will NEVER light at night
GLASS = (0x23, 0x28, 0x2E)          # the window band. Not pure black, on purpose.
GLASS_DEEP = (0x1F, 0x25, 0x2C)

# THE ROOF IS DARKER THAN YOU THINK IT SHOULD BE, and that is deliberate. It is
# LIT: a mid grey that looks right in a swatch renders almost white under the sun,
# and at this camera angle the roof is most of what you see - so the first build
# came out as a silver slab with a train underneath it. These values are chosen for
# what they look like AFTER the sun hits them, not for what they look like here.
ROOF = (0x74, 0x79, 0x7E)
ROOF_SH = (0x5C, 0x61, 0x66)
EQUIP = (0x6E, 0x74, 0x7A)
EQUIP_DET = (0x55, 0x5B, 0x61)

UNDER = (0x4A, 0x4E, 0x52)
BOGIE = (0x3A, 0x3D, 0x41)
DARK = (0x2C, 0x2F, 0x33)
DEEP = (0x1C, 0x1E, 0x21)

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
REFERENCE_METRES = 17.09    # the driving car. EVERY car takes its cross-section
                            # from this one. MEASURED: vialibre-ffe.com ficha 7000,
                            # cab car body 17.090 mm (the 9000's is 18.425 - a
                            # different length, but the cross-section is the same).

# EVERY CAR IS length=8, and on THIS train that is not a compromise - it is right.
#
# The engine trails each car behind the one in front by the length OF THE ONE IN
# FRONT (simconvoi.cc:428), while the art sits centred in its cell, so unequal
# lengths open every joint by exactly (L_previous - L_this)/2. On the Civia that
# cost an afternoon: real metres of 22.4 / 17.75 / 20.75 / 14.75 gave lengths of
# 14, 11, 13, 9 and a hole behind every long car, predicted and observed.
#
# The 7000 makes this even easier than the 9000 did. Its cars are 17.090 m (the two
# with cabs) and 16.880 m (the other four) - a difference of barely ONE PER CENT, far
# below the size of one carunit. They round to the same length whatever you do. So
# here, equal lengths are what the prototype actually has, the joints close, and
# nothing is being papered over.
#
# (And a correction to what the Civia's notes used to say: it is NOT true that
# every rail vehicle in pak128 is length 8. 425 of its 505 are; 80 are not, and its
# trams run from 2 to 8. Mixed-length units close their joints by drawing the art
# off-centre - see core/convoy.py, which computes the offset, and which predicts
# pak128's own Skoda trolleybus to within half a pixel.)
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

    Every figure a car carries into the .dat is looked up in spec.json by this
    car's key - seats, tonnes, kilowatts, its role, whether it has a cab, a
    pantograph, or faces backwards. None of them is typed here, because a number
    typed in two places is a number that will disagree with itself: this unit's
    sibling shipped a payload split summing to 186 against a measured 178 while
    spec.json plainly said 178, and nothing compared them.

    What stays here is GEOMETRY - the door centres, and which length fact applies -
    because that is what this file models. The lengths themselves are facts too, so
    only their KEY is written here; the metres come from the spec.
    """

    def __init__(self, key, name, metres_fact, doors):
        entry = SPEC.car(key)         # raises if the spec has never heard of it
        self.key = key
        self.name = name
        self.metres = SPEC.value(metres_fact)
        self.doors = doors            # door centres, 0..1 along the car
        self.role = entry["role"]
        self.cab = entry["cab"]
        self.panto = entry["panto"]
        self.reversed_ = entry["reversed"]
        self.seats = entry["seats"]
        self.tonnes = entry["tonnes"]
        self.kilowatts = entry["kilowatts"]

    @property
    def length(self):
        """Simutrans length, in 1/16 of a tile. The sprite is built to match.

        The same for every car, and the same as every rail vehicle in pak128. See
        PAK128_VEHICLE_LENGTH: mixing lengths inside one convoy is what opens the
        joints, and no pak128 train does it.
        """
        return PAK128_VEHICLE_LENGTH


# The 7000 is Mc-R-M-M-R-Mc: six cars, a cab at each end. This is the documented
# 7000 formation (listadotren, vialibre) and it differs from the 9000 in WHERE the
# trailers sit - here at positions 2 and 5, with the motored cars at the ends and in
# the middle. Externally all four intermediates are identical; only the .dat tells a
# motor (M, powered) from a trailer (R, unpowered).
#
# The figures are NOT here. Every one of them - seats, tonnes, kilowatts, the
# lengths, which cars have cabs and which faces backwards - is in spec.json, where
# each carries its source and where car_totals makes the splits add up to the
# sourced totals or refuses to load. What is left below is the modelling: the door
# centres, and which length fact each car is built to.
#
# Four double doors per car, per side, which is what the photographs show.
DOORS_6 = (0.16, 0.38, 0.62, 0.84)
DOORS_CAB = (0.30, 0.50, 0.70, 0.88)     # the nose eats the first door bay

CAB_A = Car("s7k_cab_a", "MadridMetro_S7000_CabA", "length_cab_car_m", DOORS_CAB)
REM_A = Car("s7k_rem_a", "MadridMetro_S7000_R1", "length_intermediate_m", DOORS_6)
MOT_A = Car("s7k_mot_a", "MadridMetro_S7000_M1", "length_intermediate_m", DOORS_6)
MOT_B = Car("s7k_mot_b", "MadridMetro_S7000_M2", "length_intermediate_m", DOORS_6)
REM_B = Car("s7k_rem_b", "MadridMetro_S7000_R2", "length_intermediate_m", DOORS_6)
CAB_B = Car("s7k_cab_b", "MadridMetro_S7000_CabB", "length_cab_car_m", DOORS_CAB)

UNIT = (CAB_A, REM_A, MOT_A, MOT_B, REM_B, CAB_B)


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
    # car.key already carries the "s7k_" prefix, so name the images by it directly:
    # "s7k_%s" % car.key would double it ("s7k_s7k_cab_a"), which leaks into the
    # saved texture filenames. build.py's save filter matches on car.key to match.
    img, px = rig.new_texture(bpy, car.key, TEX_W, TEX_H,
                              background=BODY)
    mimg, mpx = rig.new_texture(bpy, "%s_mask" % car.key, TEX_W, TEX_H,
                                background=(0, 0, 0), colorspace="Non-Color")

    def rect(x0, y0, x1, y1, rgb, light=False):
        rig.paint_rect(px, TEX_W, x0 * TEX_W, y0 * TEX_H, x1 * TEX_W, y1 * TEX_H,
                       rgb)
        rig.paint_rect(mpx, TEX_W, x0 * TEX_W, y0 * TEX_H, x1 * TEX_W, y1 * TEX_H,
                       (255, 255, 255) if light else (0, 0, 0))

    # ---- bodywork. y=0 is the BOTTOM of the car. Ivory, all the way up.
    rect(0.00, 0.21, 1.00, 0.86, BODY)
    rect(0.00, 0.21, 1.00, 0.27, BODY_SH)      # darkens towards the skirt

    # ---- the underframe
    rect(0.00, 0.00, 1.00, 0.13, DEEP)
    rect(0.00, 0.13, 1.00, 0.15, DARK)
    rect(0.00, 0.15, 1.00, 0.21, BODY_DEEP)    # the skirt, in shadow under the sill

    # ---- THE BLUE BAND, AND IT GOES HIGH.
    #
    # Metro de Madrid's corporate livery is ivory with the blue band up under the
    # roof - it is unmistakable in the close-up of car S-9004, where the order from
    # the top down is: dark roof, blue band, ivory, glass. The generated elevation
    # we were working from put its blue stripe at the SKIRT, and that is the one
    # thing about it that was actually wrong. Everything below this line is the
    # photograph's, not the drawing's.
    # The ivory gap between the glass and the blue is not decoration: on the real
    # car there is a clear band of bodywork between the top of the window and the
    # bottom of the blue, and without it the two darks merge into one smear at
    # 128 px and the livery stops being recognisable.
    rect(0.00, 0.865, 1.00, 0.965, BLUE)
    rect(0.00, 0.945, 1.00, 0.965, BLUE_SH)    # the band turns under the roof edge
    rect(0.00, 0.860, 1.00, 0.868, BLUE_HI)    # a highlight along its lower lip
    rect(0.00, 0.965, 1.00, 1.00, ROOF_SH)     # and the grey roof above it

    # ---- the window band, stopping short of the blue
    rect(0.00, 0.55, 1.00, 0.815, GLASS)

    # ---- the panes. Alternate lit and unlit so the night band is not one stripe.
    x, i = 0.05, 0
    while x < 0.95:
        w = min(0.076, 0.95 - x)
        if w < 0.03:
            break
        lit = (i % 3) != 1                     # two lit, one dark, repeating
        rect(x, 0.585, x + w, 0.78, LIT_PANE if lit else GLASS_HI, light=lit)
        rect(x, 0.585, x + w, 0.60, GLASS_DEEP)        # a shadow under the pane
        x += 0.095
        i += 1

    # ---- the doors: ivory, full height, cutting the window band clean through
    for centre in car.doors:
        rect(centre - 0.044, 0.15, centre + 0.044, 0.855, BODY_HI)
        rect(centre - 0.046, 0.15, centre - 0.044, 0.855, DARK)    # frames
        rect(centre + 0.044, 0.15, centre + 0.046, 0.855, DARK)
        rect(centre - 0.002, 0.15, centre + 0.002, 0.855, DARK)    # leaf split
        rect(centre - 0.034, 0.585, centre + 0.034, 0.78, GLASS_HI)
        rect(centre - 0.034, 0.585, centre + 0.034, 0.60, GLASS_DEEP)
        # ---- THE RED DOOR BAND: the 7000's signature.
        #
        # It is the ONE exterior thing that tells a 7000 from a 9000. The sources
        # describe the difference exactly: the 9000 "cambio la franja superior roja
        # de las puertas a azul" - so on the 7000 that upper door stripe is RED. It
        # sits on the panel above the window and below the top of the leaf, in the
        # ivory gap under the body's blue band, where the two never merge at 128 px.
        rect(centre - 0.044, 0.792, centre + 0.044, 0.850, RED)
        rect(centre - 0.044, 0.792, centre + 0.044, 0.800, RED_SH)  # shadow at its foot

    # ---- panel joints: the thing that stops the flank reading as one flat slab
    for j in range(1, 9):
        jx = j / 9.0
        if any(abs(jx - c) < 0.07 for c in car.doors):
            continue
        rect(jx, 0.215, jx + 0.002, 0.55, BODY_SH)

    # ---- a very light grime gradient along the bottom. No photographic dirt.
    for k in range(6):
        rect(k / 6.0, 0.13, (k + 1) / 6.0, 0.15 + 0.004 * (k % 3), DARK)

    if decals:
        paint_decals(rect, car)

    return rig.commit_texture(img, px), rig.commit_texture(mimg, mpx)


def paint_decals(rect, car):
    """The Metro diamond and the car number, kept SEPARATE so they switch off.

    At 128 px a car is about 100 px long, so the Metro de Madrid lozenge - a red
    diamond with a blue bar across it - is four pixels of red with one of blue in
    the middle. That is not a compromise, it is the honest resolution of the thing:
    a legible mark of the right colour in the right place beats unreadable text.
    The car number ('S-9004' in the photograph) is a smudge of turquoise, and would
    be a smudge in any pakset that has ever shipped.
    """
    rect(0.11, 0.885, 0.14, 0.935, RED)         # the Metro lozenge, on the blue band
    rect(0.11, 0.905, 0.14, 0.915, BLUE_HI)     # its blue bar
    rect(0.04, 0.895, 0.09, 0.925, (0x3F, 0xB5, 0xC4))   # the car number, turquoise


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
    nose.data.materials.append(mats["blue"])       # BLUE nose (as on the 9000;
                                                    # front colour assumed, see spec)

    # the white swoosh across the front, under the windscreen - the most
    # recognisable thing about this cab after its colour
    box((b.half + b.width * 0.28, 0, b.floor + b.height * 0.30),
        (b.width * 0.10, b.width * 0.92, b.height * 0.10), mats["body"],
        name="swoosh")

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
    # NOT near-black. A real bellows IS black, and painting it black is exactly what
    # the first build of this train did - and at 128 px, on an ivory car, a black
    # rectangle does not read as a bellows, it reads as a HOLE punched through the
    # coach. The contact sheet showed a tail with a void in it. So the gangway is a
    # mid grey with darker ribs: less true to the object, far truer to the picture.
    box((sx * (b.half + 0.002 * TW), 0, b.mid),
        (b.width * 0.05, b.width * 0.86, b.height * 0.90), mats["equip_det"],
        name="end_wall")
    box((sx * (b.half + b.width * 0.03), 0, b.mid - b.height * 0.05),
        (b.width * 0.10, b.width * 0.46, b.height * 0.55), mats["bogie"],
        name="gangway")
    box((sx * (b.half + b.width * 0.06), 0, b.floor * 0.45),
        (b.width * 0.12, b.width * 0.30, b.floor * 0.60), mats["dark"],
        name="coupler")


def materials():
    m = {
        "body": rig.make_paint_material(bpy, BODY, "s7k_body"),
        "blue": rig.make_paint_material(bpy, BLUE, "s7k_blue"),
        "red": rig.make_paint_material(bpy, RED, "s7k_red"),
        "glass": rig.make_paint_material(bpy, GLASS, "s7k_glass"),
        "roof": rig.make_paint_material(bpy, ROOF, "s7k_roof"),
        "equip": rig.make_paint_material(bpy, EQUIP, "s7k_equip"),
        "equip_det": rig.make_paint_material(bpy, EQUIP_DET, "s7k_equip_det"),
        "under": rig.make_paint_material(bpy, UNDER, "s7k_under"),
        "bogie": rig.make_paint_material(bpy, BOGIE, "s7k_bogie"),
        "dark": rig.make_paint_material(bpy, DARK, "s7k_dark"),
        "deep": rig.make_paint_material(bpy, DEEP, "s7k_deep"),
        "panto": rig.make_paint_material(bpy, PANTO_METAL, "s7k_panto"),
        "insulator": rig.make_paint_material(bpy, PANTO_INSULATOR, "s7k_insul"),
        # exact, unlit, or the engine will not recognise them
        "headlamp": rig.make_special_color_material(bpy, HEADLIGHT, "s7k_head"),
        "taillamp": rig.make_special_color_material(bpy, TAILLIGHT, "s7k_tail"),
        "player": rig.make_special_color_material(bpy, PLAYER, "s7k_player"),
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
                                             "s7k_livery_%s" % car.key))
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
