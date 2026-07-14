"""
Exact Simutrans camera geometry.

Everything here is DERIVED FROM THE ENGINE SOURCE, not from tutorials:

  src/simutrans/display/viewport.cc :: viewport_t::get_screen_coord()
      x = (pos.x - pos.y) * (img_size / 2)
      y = (pos.x + pos.y) * (img_size / 4)

That is the whole projection. Read off it:

  * moving one tile in world +X moves the sprite (+S/2, +S/4) on screen
  * moving one tile in world +Y moves the sprite (-S/2, +S/4) on screen
  => a 1x1 ground tile draws as a diamond S wide and S/2 tall: 2:1 dimetric.

Deriving the camera that reproduces this exactly
------------------------------------------------
Take an orthographic camera at azimuth 45 deg and elevation theta above the
horizon. A ground point (X, Y) projects to:

    screen_x = (X - Y) * cos(45)
    screen_y = (X + Y) * sin(45) * sin(theta)

Divide the two coefficients and compare with the engine (which wants the ratio
(S/4) / (S/2) = 1/2):

    [cos(45) * sin(theta)] / cos(45) = sin(theta) = 1/2   =>   theta = 30 deg

So the camera elevation is EXACTLY 30 degrees. In Blender a camera with zero
rotation looks straight down, so:

    rotation_x = 90 - 30 = 60 deg
    rotation_z = azimuth
    type       = ORTHOGRAPHIC

Note the classic confusion: the tile EDGES run across the screen at
atan(1/2) = 26.565 deg, but the CAMERA sits at 30 deg. They are different
numbers and mixing them up is a common way to get subtly wrong sprites.
"""

import math

# Elevation of the camera above the horizon. Exact: asin(1/2).
ELEVATION_DEG = 30.0

# Blender's camera looks down -Z at zero rotation, so tilt it up by this much.
CAMERA_ROTATION_X_DEG = 90.0 - ELEVATION_DEG  # 60.0

# The eight headings are 45 degrees apart.
AZIMUTH_STEP_DEG = 45.0

# Angle of the tile edges on screen. NOT the camera angle - do not confuse.
TILE_EDGE_ANGLE_DEG = math.degrees(math.atan(0.5))  # 26.565...


# ------------------------------------------------------- WHICH WAY IS NORTH
#
# THE ENGINE'S WORLD IS LEFT-HANDED. Everything below is the consequence, and it
# is the single most load-bearing fact in this kit.
#
# The engine's axes are x = east, y = SOUTH, z = up. Take the cross product:
# east x south = up. In any right-handed frame it is east x NORTH that gives up.
# So (east, south, up) is left-handed - and Blender's world is right-handed.
#
# No rotation carries one onto the other. Only a reflection does. Try to model a
# tile with "+X is east and +Y is south" and there is NO camera azimuth that
# reproduces the engine's picture; we measured all four and none of them fit.
# Worse, three of them fit ALMOST - they get two of the four compass points right
# - which is exactly how you ship a pakset whose curves connect backwards.
#
# The fix is not a hack, it is a choice of labels:
#
#     IN BLENDER:  +X = EAST      +Y = NORTH      -Y = south      -X = west
#
# Blender's (east, north, up) IS right-handed, so the frames now agree, and the
# engine's tile index y (which grows southward) simply runs along Blender's -Y.
# Nothing about the artwork is mirrored - only the name we give an axis. It is
# also the convention an artist would guess: north is up the map.
#
# With those labels the camera that reproduces viewport_t::get_screen_coord
# exactly - measured, by rendering a marker on each axis and finding it again in
# the pixels - is azimuth 45:
#
#     +X (east)  -> (+25.6, +12.8) px      the engine: (+25.6, +12.8)   MATCH
#     +Y (north) -> (+25.6, -12.8) px      the engine puts SOUTH at
#                                          (-25.6, +12.8), and north is its
#                                          negation.                    MATCH
#
# And here is the check that makes it trustworthy. A vehicle is modelled nose
# along +X, and directions.BASE_AZIMUTH_DEG - the azimuth at which that nose must
# read as "heading south" - was MEASURED, independently and long before any of
# this, against a shipped pak128 bus: 135. Now derive it instead. South is -Y, so
# the nose has to turn -90 degrees, so the camera turns +90:
#
#     45 + 90 = 135.
#
# It falls out. Two separate roads to the same number, one from the engine's
# source and one from somebody else's art.
WORLD_AZIMUTH_DEG = 45.0


def world_azimuth(model_turn_deg: float = 0.0) -> float:
    """Camera azimuth that renders a world-space model turned by `model_turn_deg`.

    The rig holds the model still and orbits the camera, so turning the model by
    +t is the same picture as turning the camera by -t.
    """
    return WORLD_AZIMUTH_DEG - model_turn_deg


def ortho_scale(tile_world_size: float) -> float:
    """Blender ortho_scale so that exactly one tile spans the render width.

    A 1x1 ground square at 45 deg azimuth spans sqrt(2) world units
    horizontally on screen (its corners project to +/- sqrt(2)/2). To make that
    span the full width of a square render, the camera frame must be exactly
    sqrt(2) * tile_world_size wide.

    With the common "1 tile = 2 Blender units" convention this gives
    2 * sqrt(2) = 2.8284..., NOT the 2.800 quoted on the German wiki. That
    rounding is ~1% off and renders sprites ~1% too large.
    """
    return tile_world_size * math.sqrt(2.0)


def camera_rotation(azimuth_deg: float) -> tuple:
    """Blender camera euler (x, y, z) in DEGREES for a given azimuth."""
    return (CAMERA_ROTATION_X_DEG, 0.0, azimuth_deg)


def project_engine(world_x: float, world_y: float, tile_px: int) -> tuple:
    """The engine's own projection (viewport_t::get_screen_coord), in pixels."""
    sx = (world_x - world_y) * (tile_px / 2.0)
    sy = (world_x + world_y) * (tile_px / 4.0)
    return (sx, sy)


def project_camera(world_x: float, world_y: float, world_z: float,
                   tile_px: int, tile_world_size: float = 1.0) -> tuple:
    """The same projection expressed as a 30-degree orthographic camera.

    Used to PROVE the camera reproduces the engine exactly (see tests).
    Returns pixels, with +y pointing down the screen like the engine does.
    """
    az = math.radians(45.0)
    el = math.radians(ELEVATION_DEG)

    # world units -> screen units
    sx = (world_x - world_y) * math.cos(az)
    sy = (world_x + world_y) * math.sin(az) * math.sin(el) + world_z * math.cos(el)

    # screen units -> pixels: one tile spans sqrt(2)*tile_world_size world units
    # across a render that is tile_px wide.
    px_per_world = tile_px / (math.sqrt(2.0) * tile_world_size)
    return (sx * px_per_world, sy * px_per_world)


def tile_diamond_px(tile_px: int) -> tuple:
    """(width, height) in pixels of the ground tile diamond. Always 2:1."""
    return (tile_px, tile_px // 2)


# ---------------------------------------------------------------- alignment
#
# Where, inside the tile_px x tile_px cell, is the ground at the tile's centre?
#
# This is the "vehicle alignment" problem, and it is NOT the cell centre. It is
# a pakset convention, so it was MEASURED, from pak128's own tile cursor
# (landscape/grounds/marker.png + marker.dat). Slope 0 - a flat tile - is drawn
# from two halves, marker.0.0 (back) and marker.3.0 (front); together they are
# exactly the tile diamond at ground level. In the 128px cell they occupy
#
#     x 2..125          y 65..126          centre (63.5, 95.5)
#
# i.e. the diamond fills the full width and the BOTTOM half of the cell, and its
# centre sits at (1/2, 3/4) of the cell - not (1/2, 1/2). The top half of the
# cell is the headroom a vehicle or building grows up into. pak128's rail
# alignment template (devdocs/rail-template.png) independently agrees: its
# screen-horizontal track runs through y ~= 96.
#
# The engine draws a vehicle image from the same cell origin as the ground image
# (viewport_t::get_screen_coord is called with the same tile pos, and a vehicle
# at the tile centre has xoff = yoff = 0), so the vehicle's cell must use the
# same reference point. Get this wrong and the vehicle floats above the rail or
# sinks into it.
TILE_CENTRE_IN_CELL = (0.5, 0.75)


def camera_target_lift(tile_world_size: float = 1.0) -> float:
    """How far ABOVE the model's ground anchor the camera must aim.

    The camera's aim point always lands at the centre of the render. But the
    tile centre has to land at 3/4 height (see TILE_CENTRE_IN_CELL), i.e. a
    quarter of a cell BELOW the render centre. Aiming the camera higher pushes
    the scene down the frame by exactly that much, so:

        drop_px = (0.75 - 0.5) * tile_px

    A world +Z of dz moves the sprite up the screen by
    dz * cos(elevation) * px_per_world, with px_per_world = tile_px /
    (sqrt(2) * tile_world). Setting that equal to drop_px and solving:

        dz = 0.25 * tile_world * sqrt(2) / cos(30 deg)

    which is tile_world * sqrt(6)/6 = 0.40825 * tile_world.
    """
    drop = TILE_CENTRE_IN_CELL[1] - 0.5
    return drop * tile_world_size * math.sqrt(2.0) / math.cos(math.radians(ELEVATION_DEG))
