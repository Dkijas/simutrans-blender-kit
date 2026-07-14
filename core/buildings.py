"""Buildings: how a model gets cut into the images the engine expects.

A vehicle is one sprite per heading. A building is not a sprite at all - it is a
GRID, and the engine addresses it like this (descriptor/writer/building_writer.cc):

    BackImage[layout][y][x][height][phase][season]
    FrontImage[layout][y][x][height][phase][season]

    layout   the building rotated: dims=x,y[,layouts]; the writer defaults to
             1 layout for a square footprint and 2 otherwise. For an ODD layout
             the footprint is TRANSPOSED (the writer does
             `h = l&1 ? size.x : size.y`).
    y, x     which tile of the footprint
    height   vertical slice: a building taller than one cell is stacked
    phase    animation frame
    season   summer, winter, ...

    A five-index form (no season) is accepted when there is only one season.
    FrontImage MUST be height 0 - the writer errors out otherwise
    ("Frontimage height MUST be one tile only!").

THE STACKING GEOMETRY, taken from the engine, not guessed
---------------------------------------------------------
obj/gebaeude.cc, drawing the background images of one tile:

        ypos -= raster_width;                     // then draw the next height

So consecutive height slices sit exactly ONE FULL TILE WIDTH apart vertically -
tile_px, not tile_px/2. (Easy to get wrong: the tile DIAMOND is tile_px/2 tall,
but the stacking step is the full tile_px.)

Everything else follows from what we already know: a tile's ground centre lands
at (1/2, 3/4) of its cell (see projection.TILE_CENTRE_IN_CELL), and tile (x, y)
of the footprint sits at project_engine(x, y) relative to the origin tile.
"""

from . import projection

# The engine reads these in order; emit them the same way so a .dat diffs cleanly
# against a hand-written one.
BACK, FRONT = "Back", "Front"

# WHICH WAY A LAYOUT TURNS
#
# A layout is the building rotated to face the road. world/simcity.cc holds the
# table that decides it:
#
#     static int const building_layout[] = { ..., 0, 1, 4, 2, ... };
#     static koord const neighbors[] = { (0,1), (1,0), (0,-1), (-1,0) };
#
# Read off the single-road cases: a road at neighbors[L] gives layout L. In the
# ENGINE's grid (x east, y south) that is
#
#     layout 0 -> the road, and so the facade, is SOUTH
#     layout 1 -> EAST        layout 2 -> NORTH        layout 3 -> WEST
#
# Now put it in Blender's axes, where north is +Y (projection.WORLD_AZIMUTH_DEG
# explains why it has to be, and it is not optional):
#
#     layout 0 -> -Y     layout 1 -> +X     layout 2 -> +Y     layout 3 -> -X
#
# Measured counter-clockwise from +X that is -90, 0, +90, 180 degrees: each layout
# turns the model by a further +90.
#
#     MODEL CONVENTION: the facade faces -Y - which is the side you are looking at
#     in Blender's own Front view - and layout L is the model turned +90*L about Z.
#
# THE SIGN OF THAT +90 IS A TRAP. An earlier version of this file had -90, from a
# measurement against a shipped pak128 house (tracking its chimney across the four
# layouts). The measurement was right; the frame it was expressed in was the
# ENGINE's, which is LEFT-handed. Conjugating a rotation by a reflection reverses
# it, so the engine's -90 per layout is Blender's +90. Two rights made a wrong,
# and every house would have faced away from its road.
def layout_azimuth(layout):
    """Camera azimuth for a layout.

    The rig keeps the model still and orbits the camera, so turning the model by
    +90*L is the same image as turning the camera (and the sun with it) by -90*L.
    """
    return projection.world_azimuth(90.0 * layout)


def layouts_for(size_x, size_y, requested=None):
    """How many layouts to render.

    The engine's default, from building_writer.cc: 1 for a square footprint, 2
    otherwise - because a non-square building has to be able to lie the other way
    round.
    """
    if requested:
        return requested
    return 1 if size_x == size_y else 2


def footprint(size_x, size_y, layout):
    """(width, height) of the footprint for this layout. Odd layouts transpose."""
    if layout & 1:
        return (size_y, size_x)
    return (size_x, size_y)


def footprint_centre(size_x, size_y, layout):
    """The middle of the footprint, in engine tile coordinates.

    THE PIVOT, and for anything bigger than one tile it is not the origin tile.
    A layout is the building turned round - but the engine still anchors it at
    tile (0,0) and grows it into +x/+y, so the turn is about the footprint's
    CENTRE, not its corner. Turn a 2x1 house about its corner tile and it swings
    off its own plot: the slices then come out of the wrong part of the render and
    the house is quietly scrambled.

    A 1x1 building has its centre AT the origin tile, which is why none of this
    showed up until the first two-tile one.
    """
    w, h = footprint(size_x, size_y, layout)
    return ((w - 1) / 2.0, (h - 1) / 2.0)


def cell_topleft(x, y, h, tile_px, origin=(0.0, 0.0)):
    """Top-left of the cell for footprint tile (x, y), height slice h.

    In pixels, relative to the ground point the camera aims at - `origin`, in
    engine tile coordinates. That is the one point the rig can place exactly.
    """
    gx, gy = projection.project_engine(x - origin[0], y - origin[1], tile_px)
    cx = gx - tile_px * projection.TILE_CENTRE_IN_CELL[0]
    cy = gy - tile_px * projection.TILE_CENTRE_IN_CELL[1]
    return (cx, cy - h * tile_px)                          # gebaeude.cc: ypos -= raster


def cells(size_x, size_y, layout, heights):
    """Every (x, y, h) the engine will look for, in the engine's own order."""
    w, h_tiles = footprint(size_x, size_y, layout)
    return [(x, y, h)
            for y in range(h_tiles)
            for x in range(w)
            for h in range(heights)]


def canvas(size_x, size_y, layout, heights, tile_px):
    """(width, height, ground_centre) of a render big enough for every cell.

    ground_centre is where the FOOTPRINT CENTRE's ground point must land, in canvas
    pixels. The rig aims the camera so that it does.

    The canvas is padded symmetrically around that point, because that is the one
    thing the camera can place exactly: the aim point always lands at the centre
    of the frame, and the tile anchor puts the ground a fixed tile_px/4 below it.
    """
    fc = footprint_centre(size_x, size_y, layout)
    rects = [cell_topleft(x, y, h, tile_px, fc)
             for (x, y, h) in cells(size_x, size_y, layout, heights)]
    x1 = min(r[0] for r in rects)
    x2 = max(r[0] for r in rects) + tile_px
    y1 = min(r[1] for r in rects)
    y2 = max(r[1] for r in rects) + tile_px

    # the aim point lands at the frame centre; the ground sits tile_px/4 below it
    drop = tile_px * (projection.TILE_CENTRE_IN_CELL[1] - 0.5)

    width = 2 * max(-x1, x2)
    height = max(-2 * y1 - 2 * drop, 2 * drop + 2 * y2)

    width = int(-(-width // 2) * 2)                        # round up to even
    height = int(-(-height // 2) * 2)
    return width, height, (width / 2.0, height / 2.0 + drop)


def canvas_cells(size_x, size_y, layout, heights, tile_px):
    """Every cell and where to cut it: -> (width, height, [((x,y,h), left, top)]).

    THE ONLY WAY TO ASK. canvas() measures from the footprint centre and
    cell_topleft() will happily measure from anywhere you tell it to, so pairing
    the two by hand means passing the same origin to both, every time, or getting
    a building that is quietly sliced from the wrong part of the render. That is
    not a thing to remember - it is a thing to not be able to get wrong.
    """
    fc = footprint_centre(size_x, size_y, layout)
    width, height, ground = canvas(size_x, size_y, layout, heights, tile_px)
    out = []
    for (x, y, h) in cells(size_x, size_y, layout, heights):
        ox, oy = cell_topleft(x, y, h, tile_px, fc)
        out.append(((x, y, h), ground[0] + ox, ground[1] + oy))
    return width, height, out


# SEASONS - and the trap in them.
#
# obj/gebaeude.cc picks which season image to draw through this table:
#
#     effective_season[seasons-1][actual] = {
#         {0,0,0,0,0},      # 1 image
#         {0,0,0,0,1},      # 2 images
#         {0,0,0,0,1},      # 3 images   <-- IDENTICAL to the row above
#         {0,1,2,3,2},      # 4 images
#         {0,1,2,3,4},      # 5 images
#     }
#
# The column is the world's season, and world/simworld.cc maps months to it with
#     month_to_season[12] = { 2,2,2, 3,3, 0,0,0,0, 1,1, 2 }   // "summer always zero"
# so 0=summer, 1=autumn, 2=winter, 3=spring - and column 4 is SNOW (above the
# snowline, or arctic climate).
#
# Read the table and two things fall out that no tutorial mentions:
#
#   * With TWO images the second one is the SNOW image, not "winter". It appears
#     above the snowline and nowhere else; in a temperate December the engine
#     still draws image 0.
#   * With THREE images the third is NEVER DRAWN. The row for 3 images is a copy
#     of the row for 2. An artist can spend a day on a third season image and the
#     game will not show it once, and nothing warns them.
#
# So the counts worth using are 1, 2, 4 and 5.
SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER, SEASON_SPRING, SEASON_SNOW = range(5)

SEASON_NAMES = ("summer", "autumn", "winter", "spring", "snow")

# how the engine reads a given number of images
SEASON_MEANING = {
    1: ("all year",),
    2: ("all year", "snow"),
    3: ("all year", "snow", "NEVER DRAWN"),
    4: ("summer", "autumn", "winter", "spring"),   # snow reuses winter
    5: ("summer", "autumn", "winter", "spring", "snow"),
}

USEFUL_SEASON_COUNTS = (1, 2, 4, 5)


# ANIMATION
#
# A tile may have several phases; the engine cycles them every animation_time
# milliseconds. It walks phase upward and stops at the first one that is missing,
# so the phases have to be contiguous from 0 - exactly like the height slices.
#
# One nice detail from obj/gebaeude.cc:275 - each building starts on a RANDOM
# phase (`anim_frame = sim_async_rand(phases)`), so a street of identical houses
# does not blink in unison. Nothing for us to do; just do not expect frame 0 to
# be the one on screen.
DEFAULT_ANIMATION_TIME_MS = 300


def _key(k):
    """Canonical image key: (layout, x, y, h, phase, season).

    A 4-tuple (no animation, one season) is accepted and padded, because that is
    what most objects are.
    """
    if len(k) == 4:
        return tuple(k) + (0, 0)
    if len(k) == 6:
        return tuple(k)
    raise ValueError("image key must be (layout,x,y,h) or "
                     "(layout,x,y,h,phase,season), got %r" % (k,))


def image_block(basename, placement, kind=BACK):
    """BackImage[layout][y][x][h][phase][season] lines, in the engine's own order.

    placement: {(layout, x, y, h, phase, season): (row, col)} - what
    sheet.assemble() gives back.

    The six-index form is emitted only when there is more than one season; with a
    single season the engine also accepts the five-index form, and that is what
    hand-written .dats look like, so ours diff cleanly against them.
    """
    keys = {_key(k): v for k, v in placement.items()}
    seasoned = any(k[5] for k in keys)

    lines = []
    for k in sorted(keys, key=lambda k: (k[0], k[2], k[1], k[3], k[4], k[5])):
        row, col = keys[k]
        layout, x, y, h, phase, season = k
        text = "%sImage[%d][%d][%d][%d][%d]" % (kind, layout, y, x, h, phase)
        if seasoned:
            text += "[%d]" % season
        lines.append("%s=%s.%d.%d" % (text, basename, row, col))
    return "\n".join(lines)


# See core/datgen.py for why no comment ever shares a line with a value.
_BUILDING_SKELETON = """\
obj=building
name={name}
copyright={author}
type={type}

# --- footprint -----------------------------------------------------------
# dims = tiles in x, tiles in y [, layouts]. The engine defaults to 1 layout
# for a square footprint and 2 otherwise; odd layouts transpose the footprint.
dims={dims}

# --- economy / placement -------------------------------------------------
# level drives passenger and mail demand, and the default capacity (level*32).
# chance is the relative likelihood the city picks this house (0 = never).
level={level}
chance={chance}
intro_year={intro_year}
retire_year={retire_year}

# --- graphics (generated - do not hand-edit) -----------------------------
{images}
"""


def building_dat(name, images, btype="res", dims="1,1", level=1, chance=100,
                 author="", intro_year=1900, retire_year=2999,
                 animation_time=None):
    """A compilable city-building .dat.

    btype: res | com | ind | cur (attraction) | tow (townhall) | ... - the value
    the engine reads from `type=`.
    animation_time: milliseconds per phase; only meaningful with >1 phase.
    """
    dat = _BUILDING_SKELETON.format(
        name=name, author=author, type=btype, dims=dims, level=level,
        chance=chance, intro_year=intro_year, retire_year=retire_year,
        images=images,
    )
    if animation_time is not None:
        dat = dat.replace("# --- graphics",
                          "# --- animation ----------------------------------"
                          "-------------------------\n"
                          "# milliseconds per phase\n"
                          "animation_time=%d\n\n# --- graphics" % animation_time)
    return dat
