"""Stadler FLIRT RABe 523 (SBB) for pak128 - shared components.

Built with the add-on's own API only - nothing here reimplements the kit. It is a
close sibling of assets/civia_465 (another 2004 low-floor EMU); the differences are
the SBB livery (white body, red doors, red cab front, grey roof, dark-grey skirt),
the four-car formation, and the per-car data. See PROJECT_PLAN.md.

    rig.build_rig / render_directions          camera, sun, the 8 headings
    rig.make_paint_material                     lit paint
    rig.new_texture / paint_rect / commit_texture  the livery, painted in code
    rig.make_livery_material                    lit bodywork + UNLIT light texels
    rig.make_special_color_material             player colour, lamps (exact, unlit)
    rig.declare_special                         "this reserved colour is on purpose"
    rig.textured_quad                           the flanks, with explicit UVs
    colors.WINDOW_DARK / HEADLIGHT / LAMP_RED   the engine's own light table

WHY A CAB CARRIES BOTH LAMPS (same as civia): a vehicle has no night image - night
is only the day->night colour swap in simgraph16.cc - so "lamps only when leading"
is not expressible. Each cab gets white headlights AND red tail lights on the same
front; whichever end leads, the picture is true.

DIMENSIONS: cross-section is ABSOLUTE and identical on every car (a FLIRT is one tube
cut into pieces); only the .dat length matters for spacing and it is 8/16 tile on
every car, as on every pak128 rail vehicle - mixing lengths opens the joints.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Prefer the INSTALLED add-on: rig.DECLARED_SPECIAL is module state, so geometry and
# validator must share one rig module or they disagree about intentional colours.
try:
    from simutrans_blender_kit.addon import rig                       # noqa: F401
    from simutrans_blender_kit.core import colors, paksets, schema, sheet
except ImportError:
    from addon import rig                                   # noqa: E402
    from core import colors, paksets, schema, sheet         # noqa: E402

PAKSET = "pak128"
PAK = paksets.get(PAKSET)
TW = PAK.tile_world

AUTHOR = "victor_18993"
METRES_PER_TILE = 25.0          # APPROXIMATION, as in civia_465

# The flat contour: one dark, cool near-black inked 1 px around the silhouette so the
# vehicle reads as a defined sprite in the depot. Far from all reserved colours.
OUTLINE = (0x16, 0x18, 0x1C)


def apply_outline(sheet_png):
    """Ink the flat contour onto a finished sheet, in place. -> the (r,g,b) inked."""
    return sheet.add_outline_file(sheet_png, PAK.tile_px, OUTLINE)


# --------------------------------------------------------------------- palette
# SBB FLIRT: white body, red doors and cab front, grey roof, dark-grey skirt. Reds
# are kept clear of the engine's reserved LAMP_RED (the validator is the gate).
BODY_HI = (0xF4, 0xF4, 0xF2)
BODY = (0xE8, 0xE9, 0xE7)
BODY_SH = (0xD2, 0xD3, 0xD1)
BODY_DEEP = (0xBC, 0xBE, 0xBC)

RED_HI = (0xE7, 0x3A, 0x40)
RED = (0xD9, 0x24, 0x2B)            # SBB-style red, clear of LAMP_RED
RED_SH = (0xA8, 0x1B, 0x21)

GLASS_HI = (0x3A, 0x46, 0x50)       # a pane that will NEVER light at night
GLASS = (0x22, 0x27, 0x2D)          # window band, not pure black on purpose
GLASS_DEEP = (0x1C, 0x21, 0x27)

ROOF = (0xC9, 0xCB, 0xCC)
ROOF_SH = (0xAF, 0xB2, 0xB5)
EQUIP = (0x9E, 0xA5, 0xAC)
EQUIP_DET = (0x7E, 0x85, 0x8D)

GREY_BAND = (0x8C, 0x90, 0x94)      # the light-grey lower band of the SBB scheme
UNDER = (0x4C, 0x50, 0x55)
BOGIE = (0x3B, 0x3F, 0x44)
DARK = (0x2A, 0x2D, 0x31)
DEEP = (0x1D, 0x20, 0x23)

PANTO_INSULATOR = (0x8A, 0x5A, 0x2B)
PANTO_METAL = (0x44, 0x48, 0x4C)

# --------------------------------------------------------- reserved / light use
LIT_PANE = rig.declare_special(colors.WINDOW_DARK)    # -> warm yellow at night
HEADLIGHT = colors.HEADLIGHT                          # -> yellow at night
TAILLIGHT = colors.LAMP_RED                           # red, day and night
PLAYER = colors.PLAYER_RAMP_BLUE[3]

TEX_W, TEX_H = 512, 128


# ------------------------------------------------------------------------ cars
REFERENCE_METRES = 18.5     # a FLIRT module ~ length_total/4; cross-section from here
PAK128_VEHICLE_LENGTH = 8   # every car; mixing lengths opens the joints (see civia_465)


class Car:
    """One car of the unit. `reversed_` turns the finished car around so a tail cab
    modelled nose-at-+X shows its nose forward while it runs at the back (Simutrans
    draws every car with the convoy-direction image; pak128 does the same with e.g.
    BR-373_FrontCar / BR-373_BackCar)."""

    def __init__(self, key, name, metres, cab, panto, doors, seats, tonnes,
                 kilowatts, reversed_=False):
        self.key = key
        self.name = name
        self.metres = metres
        self.cab = cab
        self.panto = panto
        self.doors = doors
        self.seats = seats
        self.tonnes = tonnes
        self.kilowatts = kilowatts
        self.reversed_ = reversed_

    @property
    def length(self):
        return PAK128_VEHICLE_LENGTH


# Four-car RABe 523: cab A - int B - int C (pantograph) - cab D. Traction on the two
# cab cars (1000 kW each = 2000 kW). Seats ~184 over the unit; ~120 t over the unit.
CAB_A = Car("cab_a", "SBB_FLIRT_RABe523_A", 18.5, cab=True, panto=False,
            doors=(0.40, 0.80), seats=42, tonnes=34, kilowatts=1000)
INT_B = Car("int_b", "SBB_FLIRT_RABe523_B", 18.5, cab=False, panto=False,
            doors=(0.24, 0.54, 0.82), seats=50, tonnes=26, kilowatts=0)
INT_C = Car("int_c", "SBB_FLIRT_RABe523_C", 18.5, cab=False, panto=True,
            doors=(0.24, 0.54, 0.82), seats=50, tonnes=26, kilowatts=0)
CAB_D = Car("cab_d", "SBB_FLIRT_RABe523_D", 18.5, cab=True, panto=False,
            doors=(0.40, 0.80), seats=42, tonnes=34, kilowatts=1000,
            reversed_=True)

UNIT = (CAB_A, INT_B, INT_C, CAB_D)


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
    """The proportions every component is placed against. Cross-section is ABSOLUTE,
    the same on every car (only the length varies) - deriving it from the length
    makes a train thinner in the middle, which does not exist."""

    def __init__(self, car):
        self.car = car
        self.length = car.length / 16.0 * TW           # sprite == .dat length
        self.half = self.length / 2.0
        # fattened for 128px legibility, checked against the catenary in-game (civia)
        self.width = 0.196 * TW
        self.height = 0.184 * TW
        self.floor = self.height * 0.15                # the skirt hangs below
        self.top = self.floor + self.height
        self.mid = self.floor + self.height / 2.0


# ----------------------------------------------------------------- the livery
def livery_texture(car, decals=True):
    """The flank, painted, plus the LIGHT mask. -> (image, mask). Flat colour, panel
    joints and a faint grime gradient - no photographic textures (brief)."""
    img, px = rig.new_texture(bpy, "flirt_%s" % car.key, TEX_W, TEX_H,
                              background=BODY)
    mimg, mpx = rig.new_texture(bpy, "flirt_%s_mask" % car.key, TEX_W, TEX_H,
                                background=(0, 0, 0), colorspace="Non-Color")

    def rect(x0, y0, x1, y1, rgb, light=False):
        rig.paint_rect(px, TEX_W, x0 * TEX_W, y0 * TEX_H, x1 * TEX_W, y1 * TEX_H, rgb)
        rig.paint_rect(mpx, TEX_W, x0 * TEX_W, y0 * TEX_H, x1 * TEX_W, y1 * TEX_H,
                       (255, 255, 255) if light else (0, 0, 0))

    # ---- bodywork, shaded for volume (y=0 is the BOTTOM)
    rect(0.00, 0.86, 1.00, 1.00, BODY_HI)      # top of the flank catches light
    rect(0.00, 0.30, 1.00, 0.52, BODY)
    rect(0.00, 0.47, 1.00, 0.52, BODY_HI)      # highlight up under the window band

    # ---- the light-grey lower band and the dark underframe (the SBB scheme)
    rect(0.00, 0.00, 1.00, 0.12, DEEP)
    rect(0.00, 0.12, 1.00, 0.15, DARK)
    rect(0.00, 0.15, 1.00, 0.30, GREY_BAND)
    rect(0.00, 0.29, 1.00, 0.30, BODY_SH)      # a soft edge where grey meets white

    # ---- the window band. NOT pure black. Framed and mullioned so it reads as a row
    # of windows rather than a smear.
    rect(0.00, 0.55, 1.00, 0.82, GLASS)
    rect(0.00, 0.806, 1.00, 0.82, EQUIP_DET)       # header rail
    rect(0.00, 0.55, 1.00, 0.562, DARK)            # sill rail
    rect(0.00, 0.82, 1.00, 0.835, RED)             # a thin red line along the roofline

    # ---- the panes, alternating lit/unlit so the night band is not one stripe
    x, i = 0.05, 0
    while x < 0.95:
        w = min(0.076, 0.95 - x)
        if w < 0.03:
            break
        lit = (i % 3) != 1
        rect(x, 0.585, x + w, 0.785, LIT_PANE if lit else GLASS, light=lit)
        rect(x, 0.585, x + w, 0.60, GLASS_DEEP)        # shadow under the pane
        rect(x, 0.765, x + w, 0.785, GLASS_HI)         # reflection along the top
        rect(x - 0.007, 0.585, x, 0.785, EQUIP_DET)    # mullion left of the pane
        x += 0.095
        i += 1

    # ---- the doors: RED, full height, cutting the band clean through (SBB)
    for centre in car.doors:
        rect(centre - 0.048, 0.15, centre + 0.048, 0.84, RED)
        rect(centre - 0.048, 0.15, centre + 0.048, 0.24, RED_SH)   # shadow low
        rect(centre - 0.048, 0.80, centre + 0.048, 0.84, RED_HI)   # highlight high
        rect(centre - 0.050, 0.15, centre - 0.048, 0.84, DARK)     # frames
        rect(centre + 0.048, 0.15, centre + 0.050, 0.84, DARK)
        rect(centre - 0.002, 0.15, centre + 0.002, 0.84, DARK)     # leaf split
        rect(centre - 0.038, 0.585, centre + 0.038, 0.785, GLASS_HI)
        rect(centre - 0.038, 0.585, centre + 0.038, 0.60, GLASS_DEEP)

    # ---- panel joints: what stops the flank reading as one flat slab
    for j in range(1, 9):
        jx = j / 9.0
        if any(abs(jx - c) < 0.07 for c in car.doors):
            continue
        rect(jx, 0.30, jx + 0.002, 0.52, BODY_SH)
        rect(jx, 0.86, jx + 0.002, 1.00, BODY_SH)

    # ---- a very light grime gradient along the bottom. No photographic dirt.
    for k in range(6):
        rect(k / 6.0, 0.12, (k + 1) / 6.0, 0.15 + 0.004 * (k % 3), DARK)

    if decals:
        paint_decals(rect, car)

    return rig.commit_texture(img, px), rig.commit_texture(mimg, mpx)


def paint_decals(rect, car):
    """SBB CFF FFS mark, kept SEPARATE so the livery can be relettered. At 128px the
    wordmark would be ~2px tall, so it is a legible mark of the right colour in the
    right place, not spelled out (brief allows this)."""
    rect(0.10, 0.86, 0.17, 0.885, RED)          # the SBB mark high on the side
    rect(0.05, 0.86, 0.085, 0.885, DARK)        # the unit-number strip
    if car.cab:
        rect(0.03, 0.40, 0.08, 0.43, RED)       # a small mark on the cab flank


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
    """Bajos with volume and two bogies that read as bogies, not as track."""
    box((0, 0, b.floor / 2.0), (b.length * 0.99, b.width * 0.90, b.floor),
        mats["under"], name="underframe")
    box((0, 0, b.floor * 0.30), (b.length * 0.70, b.width * 0.72, b.floor * 0.55),
        mats["dark"], name="equipment_box")
    for bx in (-0.33, 0.33):                    # standard placement (see plan)
        box((bx * b.length, 0, b.floor * 0.44),
            (b.length * 0.16, b.width * 0.80, b.floor * 0.80), mats["bogie"],
            name="bogie")
        for wx in (-0.055, 0.055):
            cyl((bx * b.length + wx * b.length, 0, b.floor * 0.16),
                b.floor * 0.30, b.width * 0.86, mats["deep"], axis="Y",
                name="wheelset")


def build_roof(b, mats, panto):
    """Roof with low visible equipment - from above (most of the 8 headings) it is
    half of what you see; anything tall on it reads as a second storey (civia lesson)."""
    box((0, 0, b.top + b.height * 0.010),
        (b.length * 0.985, b.width * 0.88, b.height * 0.04), mats["roof"],
        bevel=b.width * 0.04, name="roof")
    for ax in (-0.30, -0.05, 0.22):
        box((ax * b.length, 0, b.top + b.height * 0.035),
            (b.length * 0.12, b.width * 0.52, b.height * 0.022), mats["equip"],
            name="roof_box")
        box((ax * b.length, 0, b.top + b.height * 0.048),
            (b.length * 0.09, b.width * 0.38, b.height * 0.006),
            mats["equip_det"], name="roof_grille")
    if panto:
        px_ = 0.02
        for sy in (-1, 1):                      # the insulators
            box((px_ * b.length, sy * b.width * 0.22, b.top + b.height * 0.075),
                (b.width * 0.10, b.width * 0.10, b.height * 0.05),
                mats["insulator"], name="panto_insulator")
        box((px_ * b.length, 0, b.top + b.height * 0.10),
            (b.length * 0.28, b.width * 0.55, b.height * 0.012),
            mats["panto"], name="panto_base")
        box((px_ * b.length + b.length * 0.05, 0, b.top + b.height * 0.16),
            (b.length * 0.22, b.width * 0.06, b.height * 0.010),
            mats["panto"], name="panto_arm")     # the folded arm
        box((px_ * b.length + b.length * 0.13, 0, b.top + b.height * 0.21),
            (b.length * 0.02, b.width * 0.62, b.height * 0.012),
            mats["panto"], name="panto_bow")     # the bow, what makes it read as one


def build_cab(b, mats):
    """The nose: a red bulb with a big dark windscreen, and BOTH lamps on the front
    (the engine cannot switch lamps by convoy position)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=14, radius=0.5,
                                         location=(b.half, 0, b.mid))
    nose = bpy.context.active_object
    nose.name = "nose"
    nose.scale = (b.width * 0.82, b.width, b.height)
    nose.data.materials.append(mats["red"])

    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.5,
                                         location=(b.half + b.width * 0.04, 0,
                                                   b.mid + b.height * 0.22))
    screen = bpy.context.active_object
    screen.name = "windscreen"
    screen.scale = (b.width * 0.80, b.width * 0.88, b.height * 0.50)
    screen.data.materials.append(mats["glass"])

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
    """A coupling end: a dark gangway face and a coupler. EVERY non-cab end needs one,
    including the back of a cab car, or a bare white shell end faces the camera."""
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
    return {
        "body": rig.make_paint_material(bpy, BODY, "flirt_body"),
        "red": rig.make_paint_material(bpy, RED, "flirt_red"),
        "glass": rig.make_paint_material(bpy, GLASS, "flirt_glass"),
        "roof": rig.make_paint_material(bpy, ROOF, "flirt_roof"),
        "equip": rig.make_paint_material(bpy, EQUIP, "flirt_equip"),
        "equip_det": rig.make_paint_material(bpy, EQUIP_DET, "flirt_equip_det"),
        "under": rig.make_paint_material(bpy, UNDER, "flirt_under"),
        "bogie": rig.make_paint_material(bpy, BOGIE, "flirt_bogie"),
        "dark": rig.make_paint_material(bpy, DARK, "flirt_dark"),
        "deep": rig.make_paint_material(bpy, DEEP, "flirt_deep"),
        "panto": rig.make_paint_material(bpy, PANTO_METAL, "flirt_panto"),
        "insulator": rig.make_paint_material(bpy, PANTO_INSULATOR, "flirt_insul"),
        "headlamp": rig.make_special_color_material(bpy, HEADLIGHT, "flirt_head"),
        "taillamp": rig.make_special_color_material(bpy, TAILLIGHT, "flirt_tail"),
        "player": rig.make_special_color_material(bpy, PLAYER, "flirt_player"),
    }


def build_car(car, decals=True):
    """One complete car in the scene. Nose along +X, on z=0, at the origin."""
    clear()
    b = Body(car)
    mats = materials()

    box((0, 0, b.mid), (b.length, b.width, b.height), mats["body"],
        bevel=b.width * 0.10, name="shell")

    tex, mask = livery_texture(car, decals=decals)
    build_flanks(b, rig.make_livery_material(bpy, tex, mask,
                                             "flirt_livery_%s" % car.key))
    build_underframe(b, mats)
    build_roof(b, mats, car.panto)
    if car.cab:
        build_cab(b, mats)          # nose at +X, coupling end at -X
        build_end(b, mats, -1)
    else:
        build_end(b, mats, -1)
        build_end(b, mats, +1)

    # player colour, low on the skirt, emission/exact/unlit
    box((0, 0, b.floor + b.height * 0.028),
        (b.length * 0.995, b.width * 1.02, b.height * 0.028), mats["player"],
        name="player_stripe")

    if car.reversed_:
        turn_around()
    return b


def turn_around():
    """Spin the finished car 180 deg about z so the tail cab faces backwards. A rigid
    rotation, not a mirror."""
    import math
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        x, y, z = ob.location
        ob.location = (-x, -y, z)
        ob.rotation_euler.z += math.pi
