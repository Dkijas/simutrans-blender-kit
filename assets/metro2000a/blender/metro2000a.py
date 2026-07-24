"""Metro de Madrid Serie 2000A (1985) for pak128 - the narrow-gauge one.

WHY THIS TRAIN, AND WHY IT IS NOT ANOTHER 7000

The 7000 and the 9000 in this collection are the same geometry. Not similar - the
same: 578 of metro7k.py's 654 lines are byte-identical to metro9k.py's, every
geometry function among them, and the only thing that differs in the rendered
output is a red stripe painted on the doors. Their carefully sourced car lengths -
17.09 m against 18.425 m - reach a print() and no pixel, because REFERENCE_METRES
is assigned in both files and read in neither, and the cross-section is a pair of
absolute constants.

So this asset is not another livery. It is the first one that had to make the
geometry mean something, and every difference below is a fact from a source:

    galibo estrecho     2,30 m wide and 3,34 m tall, against the 7000's 2,808
                        and 3,65. Half a metre narrower. You cannot repaint that.
    14,72 m cars        against 16,88. length=7, not 8 - the first vehicle in this
                        collection that is not 8, and the reason is arithmetic.
    M+R married pairs   BOTH cars have a cab. In a six-car train that puts cabs in
                        the MIDDLE, facing each other. The 7000 is one continuous
                        "boa" with a cab only at each end. At 128 px this is the
                        difference you actually see.
    a flat nose         chamfered, not the Pininfarina wedge.
    three doors         against the 7000's four.
    red on white        the 1980s scheme, drawn by the CRTM.

REFERENCE_METRES IS LOAD-BEARING HERE

The cross-section is computed from spec.json's width_m and height_m. That is the
whole reason this file exists as something other than a copy - see Body.

WHERE IT COMES FROM

Two sources, and for once neither is a photograph of a train in a tunnel:

  * the CRTM's own history of Metro de Madrid's trains, which carries a side
    elevation of M-2004 in the red-white scheme, drawn by Miguel Angel Delgado with
    technical commentary by an engineer of Metro's Material Movil department. The
    door centres and the stripe heights below are MEASURED off it, at 1200 dpi.
  * Via Libre's April 2001 ficha, which is where every number in spec.json's
    `facts` that is not from the drawing comes from.

A drawing has no lamps in it, which is the point. Every photograph of this train is
underground, and station light is not neutral: the same Serie 7000 bodywork samples
R-B = -2 in daylight and warm cream under a platform lamp, and in one 9000 photo the
platform FLOOR - which is grey - reads warmer than the train does. The 7000's own
palette notes say this, and then set an "ivory" anyway. This body is WHITE, because
the drawing draws it white and the drawing is not standing in a tunnel.
"""

import os
import sys

import bpy

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # assets/metro2000a
_ROOT = os.path.dirname(os.path.dirname(_PROJ))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# The brief, validated. Loaded HERE, at import, because the numbers below come out
# of it - and on this asset that is not a formality: the CROSS-SECTION comes out of
# it too, which is the one thing its two published sisters do not do.
from tools import spec as _spec                       # noqa: E402
SPEC = _spec.load(os.path.join(_PROJ, "spec.json"))

# Prefer the INSTALLED add-on when there is one: rig.DECLARED_SPECIAL is module
# state, so building against the checkout's rig while the operator validates with
# the installed one makes the two disagree about which reserved colours were on
# purpose - and the report then accuses the artist of their own windows.
try:
    from simutrans_blender_kit.addon import rig                       # noqa: F401
    from simutrans_blender_kit.core import colors, paksets, sheet
except ImportError:
    from addon import rig                                   # noqa: E402
    from core import colors, paksets, sheet                 # noqa: E402

PAKSET = "pak128"
PAK = paksets.get(PAKSET)
TW = PAK.tile_world

AUTHOR = "victor_18993"

# --------------------------------------------------------------------- palette
#
# Sampled off the CRTM elevation at 1200 dpi, not off a photograph. See the module
# docstring for why that is the better source and not the lazier one.
BODY_HI = (0xFF, 0xFF, 0xFF)        # the drawing's bodywork: pure white
BODY = (0xF4, 0xF4, 0xF2)           # a hair off white, so panel joints can show
BODY_SH = (0xD8, 0xD9, 0xDA)
BODY_DEEP = (0xB4, 0xB6, 0xB8)

RED_HI = (0xE8, 0x2A, 0x40)
RED = (0xCE, 0x11, 0x26)            # REFERENCE: the door bays and the waist stripes
RED_SH = (0x9A, 0x0C, 0x1C)

GLASS_HI = (0x3A, 0x46, 0x50)
GLASS = (0x23, 0x28, 0x2E)
GLASS_DEEP = (0x1F, 0x25, 0x2C)

# The roof is most of what the iso camera sees, so a dark roof makes the whole
# vehicle read heavy and grey in-game - the first build did exactly that (#74797E).
# pak128's own EMU roofs are a light metallic grey. Lightened to match, with the
# shadow kept dark enough to still model the curve.
ROOF = (0x9C, 0xA2, 0xA8)
ROOF_SH = (0x80, 0x86, 0x8C)
ROOF_HI = (0xB6, 0xBB, 0xC0)        # a highlight along the crown
EQUIP = (0x6E, 0x74, 0x7A)
EQUIP_DET = (0x55, 0x5B, 0x61)

UNDER = (0x4A, 0x4E, 0x52)
BOGIE = (0x35, 0x4A, 0x74)          # the drawing's bogies are BLUE, and visibly so
BOGIE_DK = (0x25, 0x33, 0x50)
GANGWAY = (0x4E, 0x53, 0x58)        # grey. NOT the bogie blue - see build_end.
DARK = (0x2C, 0x2F, 0x33)
DEEP = (0x1C, 0x1E, 0x21)

PANTO_INSULATOR = (0x8A, 0x5A, 0x2B)
PANTO_METAL = (0x44, 0x48, 0x4C)

# The FLAT CONTOUR. A single dark, cool near-black inked 1 px around the silhouette
# after the render, so the white body stops dissolving into the depot behind it and
# reads as a defined sprite the way pak128's own hand-drawn stock does. ONE colour,
# chosen here on purpose: it is far from all four reserved colours (window #57656F,
# headlight #E3E3FF, tail #FF211D, player #6084A7), so the contour can never be
# mistaken for one and repainted. This is the deliberate answer to Freestyle, whose
# antialiased line introduced 181 colours and collided with the window colour. See
# apply_outline and core.sheet.outline_cells.
OUTLINE = (0x16, 0x18, 0x1C)

# --------------------------------------------------------- reserved / light use
# Declared ON PURPOSE, so the validator can tell these from an accident.
LIT_PANE = rig.declare_special(colors.WINDOW_DARK)    # -> warm yellow at night
HEADLIGHT = colors.HEADLIGHT
TAILLIGHT = colors.LAMP_RED
PLAYER = colors.PLAYER_RAMP_BLUE[3]

TEX_W, TEX_H = 512, 128


# ------------------------------------------------------------------------ cars
#
# LENGTH 7, AND WHY THAT IS SAFE HERE AND NOWHERE ELSE.
#
# The engine trails each car behind the one in front by the length OF THE ONE IN
# FRONT (simconvoi.cc:428) while the art sits centred in its cell, so mixing lengths
# inside one convoy opens every joint by (L_previous - L_this)/2. That is why the
# 7000 and the 9000 are 8 throughout.
#
# This unit is 7 throughout. Both its cars are 14,72 m, so the joints close for
# exactly the same reason the 7000's do - because the cars agree with each other,
# not because 8 is a magic number. And a 2000A cannot couple to a 7000 (different
# loading gauge, different voltage, forty years apart), so the two units never have
# to agree with one another.
#
# 7 rather than 8 because 14,72 / 2,11 = 6,98, where 2,11 m per carunit is the scale
# the 7000 already fixed (16,88 m at length 8). Rounding that to 8 would draw this
# train the same size as a 7000, which is the exact failure this asset exists to
# avoid. See spec.json length_carunits, which carries the working.
PAK128_VEHICLE_LENGTH = 7

# Every car of this unit is the reference car: they are the same body. Unlike the
# 7000, where this constant is set and never read, it IS read here - see Body.
REFERENCE_METRES = 14.72

# The catenary is where it is regardless of how tall the train is.
#
# The 7000's cross-section was tuned by standing it next to pak128's own 620 railcar
# and watching where the contact wire falls, and its pantograph bow ends up at
# 0.2562 of a tile: floor (0.187*0.16) + height (0.187) + height*0.21. A 2000A is
# LOWER, so a pantograph drawn to this car's own proportions would stop short of the
# wire and read as broken. A real pantograph does not care how tall its train is: it
# extends until it touches. So this one is built to reach the same absolute height.
WIRE_TW = 0.2562


class Car:
    """One car of the pair. Every figure is looked up in spec.json by key.

    Nothing numeric is typed in this file. The 9000 shipped a payload split summing
    to 186 against a measured 178 because its numbers lived in the module where
    nothing added them up; they live in the spec now, and car_totals refuses to load
    a split that does not meet its sourced total.

    What stays here is geometry: which door centres, and which length fact.
    """

    def __init__(self, key, name):
        entry = SPEC.car(key)          # raises if the spec has never heard of it
        self.key = key
        self.name = name
        self.metres = SPEC.value("length_car_m")
        self.doors = tuple(SPEC.value("door_centres"))
        self.role = entry["role"]
        self.cab = entry["cab"]
        self.panto = entry["panto"]
        self.reversed_ = entry["reversed"]
        self.seats = entry["seats"]
        self.tonnes = entry["tonnes"]
        self.kilowatts = entry["kilowatts"]

    @property
    def length(self):
        return PAK128_VEHICLE_LENGTH


# The unit is Mc-Rc: two cars, a cab on each, coupled at their inner ends. This is
# the whole shape of the train and it is the thing that makes it look like a 2000A -
# see the module docstring. Both cars carry the same door layout because they are the
# same carbody; the CRTM only draws the M, and that is stated in the spec.
#
# TWO cars, not six, and the unit is REPEATABLE - which is new here. The 7000 and the
# 9000 are indeformable six-car sets: one click on the cab and the depot walks a chain
# of single successors to the end. A 2000A ran as 2, 4 or 6 cars because a pair
# couples to a pair, so its chain BRANCHES, and the player really does choose. See
# build.py's couplings(), which is where that lives and where the one thing Simutrans
# cannot express is written down.
MOT = Car("s2ka_mot", "MadridMetro_S2000A_M")
REM = Car("s2ka_rem", "MadridMetro_S2000A_R")

UNIT = (MOT, REM)


# EXPERIMENTAL, and OFF by default so the published asset is byte-for-byte unchanged
# until this is approved. When True, the body gets its real profile instead of a
# chamfered prism: rounded vertical corners (the 3/4 "tube" read) and a CAMBERED
# roof. The roof camber has NO end-view source - there is no frontal drawing, only
# the weak Wikipedia width/height - so it is MODELLED, not measured, exactly the
# distinction spec.py exists to keep. The flat nose is kept: that is the 2000A
# signature against the 7000's bubble, and it is sourced from the CRTM elevation.
SHAPED_FORM = False

# ADOPTED. The second lever after the contour: MARK the big features so a 2000A reads
# AS a 2000A at 128 px, not as a generic box. Three foci: a defined nose (a brow over
# the windscreen), bolder roof equipment, and higher-contrast punched windows.
# Geometry + texture, no new source needed - these are the features the CRTM elevation
# already draws, made legible at game scale. The `if MARKED`/`else` branches below keep
# the plain version alongside, as the documented base this improved on.
MARKED = True


# ------------------------------------------------------------------- utilities
def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def box(loc, scale, material, bevel=0.0, segments=2, name="part"):
    """A cube. segments=1 gives a hard CHAMFER; 2 rounds the edge.

    The chamfer is not a detail on this train - it is the nose. See build_cab.
    """
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(material)
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segments
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
    """The proportions every component is placed against.

    THIS IS THE PART THAT IS NOT A COPY.

    The 7000 and the 9000 hardcode

        self.width  = 0.198 * TW
        self.height = 0.187 * TW

    for every car of both series, so their sourced metres change nothing. Here the
    cross-section is COMPUTED from spec.json, and the two scale factors below are
    the only thing inherited from them.

    Why two factors and not one: 0.198/2.808 = 0.0705 TW per metre of width, and
    0.187/3.65 = 0.0512 per metre of height. They disagree by 38%, because they were
    never a scale - they were set by eye against pak128's catenary and its 620
    railcar, one axis at a time. Inventing a single uniform factor now would be
    tidier and would move both published trains, so each axis keeps its own. What
    this asset fixes is that the metres are READ; it does not pretend the pakset is
    dimensionally honest, because it is not.

    The result: 2,30 m -> 0.162 TW wide (the 7000 is 0.198) and 3,34 m -> 0.171 TW
    tall (0.187). Narrower and lower, from the source, automatically.
    """

    WIDTH_TW_PER_M = 0.198 / 2.808      # the 7000's tuned width, per its metres
    HEIGHT_TW_PER_M = 0.187 / 3.65      # the 7000's tuned height, per its metres

    def __init__(self, car):
        self.car = car
        self.length = car.length / 16.0 * TW           # sprite == .dat length
        self.half = self.length / 2.0

        self.width = self.WIDTH_TW_PER_M * SPEC.value("width_m") * TW
        self.height = self.HEIGHT_TW_PER_M * SPEC.value("height_m") * TW
        self.floor = self.height * 0.16
        self.top = self.floor + self.height
        self.mid = self.floor + self.height / 2.0


# ----------------------------------------------------------------- the livery
def livery_texture(car, decals=True):
    """The flank, painted, plus the LIGHT mask. -> (image, mask)

    The red-white scheme, read off the CRTM elevation. Its shape is not the 7000's
    and not a recolour of it:

        the 7000     ivory body, one BLUE BAND high under the roof, a red stripe
                     on the door panel only.
        the 2000A    white body, each door in a FULL-HEIGHT RED BAY from skirt to
                     roof line, and TWO thin red waist stripes running the whole
                     length and crossing every bay in white.

    At 128 px the 7000 reads as a pale car with a dark line along the top. This one
    reads as a white car with three red blocks in it. That is a different train from
    a hundred metres away, which is the only distance Simutrans ever shows you.
    """
    img, px = rig.new_texture(bpy, car.key, TEX_W, TEX_H, background=BODY)
    mimg, mpx = rig.new_texture(bpy, "%s_mask" % car.key, TEX_W, TEX_H,
                                background=(0, 0, 0), colorspace="Non-Color")

    def rect(x0, y0, x1, y1, rgb, light=False):
        rig.paint_rect(px, TEX_W, x0 * TEX_W, y0 * TEX_H, x1 * TEX_W, y1 * TEX_H,
                       rgb)
        rig.paint_rect(mpx, TEX_W, x0 * TEX_W, y0 * TEX_H, x1 * TEX_W, y1 * TEX_H,
                       (255, 255, 255) if light else (0, 0, 0))

    # ---- bodywork. y=0 is the BOTTOM of the car. White, all the way up: this
    # train has no band under the roof, which is half of why it is not a 7000.
    #
    # Shaded for VOLUME, not painted flat. Flat white read as a cardboard slab
    # in-game; a real steel side has a highlight up where the sun catches it and a
    # shadow down in the shade, and that top-to-bottom gradient is most of what
    # makes pak128's own stock look rounded rather than boxy. Painted as bands from
    # the sill up: shadow, mid, body, highlight.
    rect(0.00, 0.21, 1.00, 0.97, BODY)
    rect(0.00, 0.21, 1.00, 0.28, BODY_SH)       # shadow along the sill
    rect(0.00, 0.86, 1.00, 0.955, BODY_HI)      # highlight up under the roof
    rect(0.00, 0.955, 1.00, 1.00, ROOF_SH)      # the grey roof edge

    # ---- the underframe
    rect(0.00, 0.00, 1.00, 0.13, DEEP)
    rect(0.00, 0.13, 1.00, 0.15, DARK)
    rect(0.00, 0.15, 1.00, 0.21, BODY_DEEP)

    # ---- THE WINDOWS: PUNCHED, IN PAIRS, ON WHITE BODYWORK.
    #
    # This is the second thing the drawing settles, and the first draft got it wrong
    # by copying the 7000. That train has a continuous dark ribbon with panes cut
    # into it - the flank of a 2002 aluminium boa. The CRTM's elevation of M-2004 is
    # a different object entirely: individual windows PUNCHED into a steel flank, two
    # between each pair of doors, with white bodywork above them, below them, and in
    # the pillar between them.
    #
    # It matters more than it sounds. Take the red off both trains and the ribbon is
    # what still says "modern"; a row of holes is what says 1985. At 128 px it is
    # nearly all you have left.
    #
    # The gaps are derived from the measured door bays rather than typed: whatever
    # door_centres says, the windows land between them.
    edges = [0.0]
    for c in car.doors:
        edges += [c - 0.061, c + 0.061]
    edges.append(1.0)
    gaps = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]

    pane = 0
    for gi, (g0, g1) in enumerate(gaps):
        span = g1 - g0
        if span < 0.05:
            continue
        # The last gap on a cab car IS the cab: it gets a driver's door and a
        # driver's window, painted below, and no saloon windows at all. The first
        # draft let the loop put one here and then painted the cab door straight over
        # it - the window was in the texture and invisible, which is the sort of bug
        # that survives a green build.
        if car.cab and gi == len(gaps) - 1:
            continue
        n = 2
        margin = span * 0.14
        inner = span - 2 * margin
        w = (inner - (n - 1) * span * 0.10) / n
        for k in range(n):
            x = g0 + margin + k * (w + span * 0.10)
            lit = (pane % 3) != 1              # two lit, one dark, repeating
            dark_pane = GLASS_DEEP if MARKED else GLASS_HI  # deepest hole when marked
            rect(x, 0.60, x + w, 0.845, LIT_PANE if lit else dark_pane, light=lit)
            rect(x, 0.60, x + w, 0.615, GLASS_DEEP)       # a shadow on the sill
            # The frame: a hairline on the base train, a bold near-black surround
            # when marked - which is what turns "two lit patches" into a punched
            # hole. Wide enough that adjacent frames nearly meet and the strip left
            # between a pair reads as a body pillar.
            fcol = DEEP if MARKED else BODY_SH
            fw = 0.007 if MARKED else 0.003
            rect(x - fw, 0.597, x, 0.848, fcol)           # the frame, both sides
            rect(x + w, 0.597, x + w + fw, 0.848, fcol)
            if MARKED:
                rect(x - fw, 0.845, x + w + fw, 0.852, fcol)   # top rail
                rect(x - fw, 0.593, x + w + fw, 0.600, fcol)   # bottom rail
            pane += 1

    # ---- the cab side, in the order the drawing draws it: the driver's DOOR, then
    # the signal cluster, then the driver's WINDOW, then the nose. The 7000 has none
    # of this - its cab is a bulb, and a bulb has no flank.
    if car.cab:
        rect(0.868, 0.17, 0.918, 0.895, BODY_HI)         # the cab door, white
        rect(0.866, 0.17, 0.868, 0.895, BODY_SH)         # its frame
        rect(0.918, 0.17, 0.920, 0.895, BODY_SH)
        rect(0.912, 0.50, 0.916, 0.545, EQUIP_DET)       # the handle
        # the signal cluster beside the door: two red lamps over a green one. Small,
        # exact, and the reason it is here is that it is the only spot of colour on
        # this end of the car other than the number.
        rect(0.926, 0.83, 0.933, 0.855, TAILLIGHT)
        rect(0.926, 0.795, 0.933, 0.820, TAILLIGHT)
        # the driver's window: one pane, taller than the saloon's and set higher
        rect(0.940, 0.60, 0.982, 0.855, LIT_PANE, light=True)
        rect(0.940, 0.60, 0.982, 0.615, GLASS_DEEP)
        rect(0.937, 0.597, 0.940, 0.858, BODY_SH)

    # ---- THE DOOR BAYS: full height, red, from the skirt to the roof line.
    #
    # MEASURED, not styled. The centres are spec.json's door_centres, read off the
    # CRTM elevation at 1200 dpi: the three bays span x=621-947, 1406-1732 and
    # 2173-2499 against a body of 147-2912, giving 0.230 / 0.514 / 0.791. The bay is
    # 0.118 of the car long, from the same measurement.
    for centre in car.doors:
        rect(centre - 0.059, 0.15, centre + 0.059, 0.955, RED)
        rect(centre - 0.059, 0.15, centre + 0.059, 0.17, RED_SH)
        rect(centre - 0.061, 0.15, centre - 0.059, 0.955, DARK)      # bay edges
        rect(centre + 0.059, 0.15, centre + 0.061, 0.955, DARK)
        # the two leaves, and the split between them
        rect(centre - 0.002, 0.15, centre + 0.002, 0.955, RED_SH)
        # the door windows, inset in the leaves
        for lf in (-0.030, 0.030):
            rect(centre + lf - 0.021, 0.585, centre + lf + 0.021, 0.83, GLASS_HI)
            rect(centre + lf - 0.021, 0.585, centre + lf + 0.021, 0.60, GLASS_DEEP)

    # ---- THE TWO WAIST STRIPES, and they run the WHOLE length.
    #
    # The drawing is unambiguous: two thin red lines at waist height, unbroken from
    # end to end, crossing every door bay - and where they cross, the DOOR is white,
    # not the stripe red. That inversion is the signature of the scheme and it is
    # why the stripes are painted after the bays and the breaks after the stripes.
    for y0, y1 in ((0.470, 0.500), (0.520, 0.548)):
        rect(0.00, y0, 1.00, y1, RED)
    for centre in car.doors:
        for y0, y1 in ((0.470, 0.500), (0.520, 0.548)):
            rect(centre - 0.059, y0, centre + 0.059, y1, BODY_HI)

    # ---- panel joints
    for j in range(1, 8):
        jx = j / 8.0
        if any(abs(jx - c) < 0.075 for c in car.doors):
            continue
        rect(jx, 0.215, jx + 0.002, 0.55, BODY_SH)

    for k in range(6):
        rect(k / 6.0, 0.13, (k + 1) / 6.0, 0.15 + 0.004 * (k % 3), DARK)

    if decals:
        paint_decals(rect, car)

    return rig.commit_texture(img, px), rig.commit_texture(mimg, mpx)


def paint_decals(rect, car):
    """The car number, in red, high on the cab end - where the drawing puts it.

    The M-2004 in the elevation carries its number in red capitals on the white
    bodywork above the cab side window, and nothing else: no lozenge on the flank.
    This train predates the corporate mark the 7000 wears, and painting one on would
    be inventing forty years of livery history to fill a gap.
    """
    if car.cab:
        rect(0.86, 0.885, 0.94, 0.925, RED)


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
    """Bajos, and the drawing's BLUE bogies.

    The 7000's bogies are near-black and vanish into the shadow under the car. The
    CRTM draws this one's in a distinct blue with the wheels picked out - and on a
    white car with a high floor, they show. Painting them black here would be
    copying the 7000's answer to a question this train asks differently.
    """
    box((0, 0, b.floor / 2.0), (b.length * 0.99, b.width * 0.90, b.floor),
        mats["under"], name="underframe")
    box((0, 0, b.floor * 0.30), (b.length * 0.66, b.width * 0.72, b.floor * 0.55),
        mats["dark"], name="equipment_box")

    for bx in (-0.33, 0.33):
        box((bx * b.length, 0, b.floor * 0.44),
            (b.length * 0.17, b.width * 0.80, b.floor * 0.80), mats["bogie"],
            name="bogie")
        for wx in (-0.058, 0.058):
            cyl((bx * b.length + wx * b.length, 0, b.floor * 0.16),
                b.floor * 0.30, b.width * 0.86, mats["deep"], axis="Y",
                name="wheelset")


def build_roof(b, mats, panto):
    if SHAPED_FORM:
        # A CAMBERED roof, not a flat lid. A big multi-segment bevel on a low, wide
        # box arches the top from side to side - the single change that reads most as
        # "train" rather than "box" in the 3/4 view. Sits low enough to overlap the
        # shell shoulders so there is no seam. MODELLED camber, see SHAPED_FORM.
        box((0, 0, b.top - b.height * 0.09),
            (b.length * 0.985, b.width * 0.98, b.height * 0.26),
            mats["roof"], bevel=b.width * 0.46, segments=5, name="roof")
    else:
        box((0, 0, b.top + b.height * 0.010),
            (b.length * 0.985, b.width * 0.88, b.height * 0.04), mats["roof"],
            bevel=b.width * 0.04, name="roof")
    # a highlight strip along the crown, so the roof reads as a curved metal skin
    # catching the light rather than a flat grey lid
    box((0, 0, b.top + b.height * 0.032),
        (b.length * 0.97, b.width * 0.40, b.height * 0.006), mats["roof_hi"],
        name="roof_crown")

    # The drawing shows a run of low, evenly spaced vents the whole length - more of
    # them and smaller than the 7000's three blocks.
    if MARKED:
        # Bolder, taller units with a darker cap: at 128 px a flat low vent is one
        # grey pixel, but a block with a lid reads as equipment sitting ON the roof.
        for ax in (-0.34, -0.16, 0.02, 0.20):
            box((ax * b.length, 0, b.top + b.height * 0.05),
                (b.length * 0.10, b.width * 0.56, b.height * 0.05), mats["equip"],
                name="roof_box")
            box((ax * b.length, 0, b.top + b.height * 0.078),
                (b.length * 0.086, b.width * 0.44, b.height * 0.014),
                mats["equip_det"], name="roof_box_cap")
    else:
        for ax in (-0.36, -0.20, -0.04, 0.12, 0.28):
            box((ax * b.length, 0, b.top + b.height * 0.035),
                (b.length * 0.075, b.width * 0.50, b.height * 0.022), mats["equip"],
                name="roof_box")

    if panto:
        # ONE pantograph, not the 7000's two: the drawing shows a single arm on the
        # motor car, near the coupling end. The R has none, which is what
        # spec.json's `panto` says and what the axle arrangement implies.
        #
        # It is built to reach WIRE_TW, not to this car's own proportions. See the
        # constant: a lower train raises its pantograph further, and drawing it
        # short would read as broken rather than as narrow-gauge.
        px_ = -0.22
        reach = WIRE_TW * TW - b.top
        for sy in (-1, 1):
            box((px_ * b.length, sy * b.width * 0.22, b.top + reach * 0.18),
                (b.width * 0.10, b.width * 0.10, reach * 0.30),
                mats["insulator"], name="panto_insulator")
        box((px_ * b.length, 0, b.top + reach * 0.36),
            (b.length * 0.20, b.width * 0.55, reach * 0.06),
            mats["panto"], name="panto_base")
        box((px_ * b.length + b.length * 0.04, 0, b.top + reach * 0.64),
            (b.length * 0.16, b.width * 0.06, reach * 0.05),
            mats["panto"], name="panto_arm")
        box((px_ * b.length + b.length * 0.09, 0, b.top + reach * 0.95),
            (b.length * 0.02, b.width * 0.62, reach * 0.06),
            mats["panto"], name="panto_bow")


def build_cab(b, mats):
    """The nose: FLAT. This is the shape difference, and it is the point.

    The 7000's build_cab adds a UV sphere and calls it a bulb. This one is a slab:
    a vertical front face, chamfered at the top corner and again at the skirt, which
    is what the CRTM elevation of M-2004 draws and what the CRTM's own text says by
    contrast - the Serie B (1997) "se diferencia de la primera serie por la luna
    frontal que le da un aspecto de burbuja". The bubble is the OTHER train. This
    one is the flat one it was an evolution of.

    segments=1 on the bevel, not 2: a chamfer, not a fillet. At 128 px the
    difference between a cut corner and a rounded one is one pixel of shading, and
    it is the pixel that says which of the two series you are looking at.
    """
    # the front face, as wide and as tall as the body it caps
    box((b.half + b.width * 0.05, 0, b.mid),
        (b.width * 0.10, b.width * 0.99, b.height * 0.97), mats["body"],
        bevel=b.width * 0.16, segments=1, name="nose")

    # the windscreen: a flat pane, raked slightly back. Not a sphere.
    box((b.half + b.width * 0.09, 0, b.mid + b.height * 0.22),
        (b.width * 0.06, b.width * 0.80, b.height * 0.34), mats["glass"],
        bevel=b.width * 0.05, segments=1, name="windscreen")

    if MARKED:
        # A BROW over the windscreen: a roof-coloured visor that overhangs the glass
        # and projects forward. This is the single feature that turns the flat front
        # into a face at 128 px - the drawing shows the roof carried out over the cab
        # windows, and without it the nose is just a pale rectangle.
        box((b.half + b.width * 0.17, 0, b.floor + b.height * 0.885),
            (b.width * 0.28, b.width * 0.98, b.height * 0.075), mats["roof"],
            bevel=b.width * 0.05, segments=1, name="nose_brow")
        # a shadow line tucked just under the visor, so the overhang reads as depth
        # and not as a painted band.
        box((b.half + b.width * 0.22, 0, b.floor + b.height * 0.842),
            (b.width * 0.12, b.width * 0.92, b.height * 0.022), mats["dark"],
            name="nose_brow_shadow")

    # the two waist stripes wrap onto the front face. On the drawing they run right
    # to the corner and stop; carrying them across is what keeps the nose part of
    # the same train as the flank.
    for z in (0.40, 0.47):
        box((b.half + b.width * 0.10, 0, b.floor + b.height * z),
            (b.width * 0.02, b.width * 0.95, b.height * 0.022), mats["red"],
            name="nose_stripe")

    for sy in (-1, 1):
        box((b.half + b.width * 0.09, sy * b.width * 0.31,
             b.floor + b.height * 0.30),
            (b.width * 0.09, b.width * 0.14, b.height * 0.075), mats["headlamp"],
            name="headlight")
        box((b.half + b.width * 0.09, sy * b.width * 0.31,
             b.floor + b.height * 0.19),
            (b.width * 0.08, b.width * 0.11, b.height * 0.05), mats["taillamp"],
            name="taillight")

    # the skirt chamfer: the drawing cuts the bottom front corner away at a slant,
    # and the coupler sits in the notch it leaves.
    box((b.half + b.width * 0.06, 0, b.floor * 0.55),
        (b.width * 0.50, b.width * 0.86, b.floor * 1.05), mats["deep"],
        bevel=b.width * 0.10, segments=1, name="nose_skirt")
    box((b.half + b.width * 0.20, 0, b.floor * 0.30),
        (b.width * 0.16, b.width * 0.30, b.floor * 0.55), mats["dark"],
        name="coupler")


def build_end(b, mats, sx):
    """A coupling end. A mid grey, never black - see the 7000's note: at 128 px a
    black rectangle on a white car reads as a hole punched through the coach, not as
    a bellows.

    And never BLUE either, which is a trap this train sets and the 7000 does not.
    The bogies here are blue because the CRTM draws them blue, so the first build
    reached for the bogie colour for the gangway too - the way the 7000 does, where
    its bogies are grey and nothing shows. On a white car with a blue gangway, the w
    and e headings came out with a bright blue slab hanging off the coupling end.
    Right colour, wrong part.
    """
    box((sx * (b.half + 0.002 * TW), 0, b.mid),
        (b.width * 0.05, b.width * 0.86, b.height * 0.90), mats["equip_det"],
        name="end_wall")
    box((sx * (b.half + b.width * 0.03), 0, b.mid - b.height * 0.05),
        (b.width * 0.10, b.width * 0.46, b.height * 0.55), mats["gangway"],
        name="gangway")
    box((sx * (b.half + b.width * 0.06), 0, b.floor * 0.45),
        (b.width * 0.12, b.width * 0.30, b.floor * 0.60), mats["dark"],
        name="coupler")


def materials():
    return {
        "body": rig.make_paint_material(bpy, BODY, "s2ka_body"),
        "red": rig.make_paint_material(bpy, RED, "s2ka_red"),
        "glass": rig.make_paint_material(bpy, GLASS, "s2ka_glass"),
        "roof": rig.make_paint_material(bpy, ROOF, "s2ka_roof"),
        "roof_hi": rig.make_paint_material(bpy, ROOF_HI, "s2ka_roof_hi"),
        "equip": rig.make_paint_material(bpy, EQUIP, "s2ka_equip"),
        "equip_det": rig.make_paint_material(bpy, EQUIP_DET, "s2ka_equip_det"),
        "under": rig.make_paint_material(bpy, UNDER, "s2ka_under"),
        "bogie": rig.make_paint_material(bpy, BOGIE, "s2ka_bogie"),
        "bogie_dk": rig.make_paint_material(bpy, BOGIE_DK, "s2ka_bogie_dk"),
        "gangway": rig.make_paint_material(bpy, GANGWAY, "s2ka_gangway"),
        "dark": rig.make_paint_material(bpy, DARK, "s2ka_dark"),
        "deep": rig.make_paint_material(bpy, DEEP, "s2ka_deep"),
        "panto": rig.make_paint_material(bpy, PANTO_METAL, "s2ka_panto"),
        "insulator": rig.make_paint_material(bpy, PANTO_INSULATOR, "s2ka_insul"),
        # exact, unlit, or the engine will not recognise them
        "headlamp": rig.make_special_color_material(bpy, HEADLIGHT, "s2ka_head"),
        "taillamp": rig.make_special_color_material(bpy, TAILLIGHT, "s2ka_tail"),
        "player": rig.make_special_color_material(bpy, PLAYER, "s2ka_player"),
    }


def build_car(car, decals=True):
    """One complete car in the scene. Nose along +X, on z=0, at the origin."""
    clear()
    b = Body(car)
    mats = materials()

    if SHAPED_FORM:
        # Rounded vertical corners: the 3/4 view then reads as a rounded carbody,
        # not a slab. Bigger bevel, multi-segment. The nose stays flat (build_cab),
        # so the 2000A signature survives the rounding. See SHAPED_FORM.
        box((0, 0, b.mid), (b.length, b.width, b.height), mats["body"],
            bevel=b.width * 0.18, segments=3, name="shell")
    else:
        # segments=1: the body's own corners are chamfered too, not rounded. This is
        # a 1985 welded steel box and it looks like one.
        box((0, 0, b.mid), (b.length, b.width, b.height), mats["body"],
            bevel=b.width * 0.07, segments=1, name="shell")

    tex, mask = livery_texture(car, decals=decals)
    build_flanks(b, rig.make_livery_material(bpy, tex, mask,
                                             "s2ka_livery_%s" % car.key))
    build_underframe(b, mats)
    build_roof(b, mats, car.panto)

    # EVERY car here has a cab, which no unit in this collection has had before. The
    # cab goes at +X and the coupling end at -X; the R is then turned around, so in
    # a train the two cabs of a pair sit at the OUTER ends and the couplings meet in
    # the middle. String three pairs together and you get cabs at 1, 2, 3, 4, 5 and
    # 6 - the real thing, and unmistakable at any zoom.
    build_cab(b, mats)
    build_end(b, mats, -1)

    # The company colour, as a THIN accent low on the skirt - not the bold band the
    # first build wrapped around the whole car, which read as "this is a blue train"
    # in-game and buried the white-and-red identity. pak128 uses player colour as a
    # small flash, not a livery. Half the height, tucked at the very bottom.
    box((0, 0, b.floor + b.height * 0.012),
        (b.length * 0.995, b.width * 1.02, b.height * 0.014), mats["player"],
        name="player_stripe")

    if car.reversed_:
        turn_around()
    return b


def apply_outline(sheet_png):
    """Ink the flat contour onto a finished sheet, in place. -> the (r,g,b) inked.

    Called from build.py AFTER Render Sheet and BEFORE Compile .pak, so makeobj
    reads the outlined sheet and the .pak carries the contour. Per-cell, 1 px,
    grown outward - see core.sheet.outline_cells for why that keeps the palette
    exact. This is the only place the contour is applied; the geometry never sees
    it, which is why it cannot disturb the reserved-colour report on the body.
    """
    return sheet.add_outline_file(sheet_png, PAK.tile_px, OUTLINE)


def turn_around():
    """Spin the finished car 180 degrees about z. A rigid rotation, not a mirror."""
    import math
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        x, y, z = ob.location
        ob.location = (-x, -y, z)
        ob.rotation_euler.z += math.pi
