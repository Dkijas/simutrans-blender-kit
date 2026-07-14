"""Ways: roads, rails, canals - and the symmetry that makes them cheap to draw.

A way is not one sprite. The engine picks a different image depending on which
NEIGHBOURS the tile connects to, and it addresses that image by a four-bit mask
called the RIBI (dataobj/ribi.h:170):

        1 = North      2 = East      4 = South      8 = West

descriptor/way_desc.h:113 then does, with no indirection whatsoever:

        get_image_id(ribi) -> get_child<image_list_t>(n)->get_image_id(ribi)

so THE IMAGE LIST IS INDEXED BY THE BITMASK ITSELF. The writer builds that list
by walking ribi_codes[] in order (writer/way_writer.cc:25), and the array index
is the mask: ribi_codes[3] == "ne" == 1|2. Sixteen entries, one per combination.

WHICH WAY IS NORTH
------------------
The bits are named, not drawn, so the names have to be tied to world axes. The
engine does it for us in dataobj/ribi.cc:17 -

        const ribi_t::ribi ribi_t::layout_to_ribi[4] = { south, east, north, west };
        // "same like the layouts of buildings"

and world/simcity.cc:2914 gives the layouts their coordinates -

        static koord const neighbors[] = { (0,1), (1,0), (0,-1), (-1,0) };

Line them up and there is nothing left to guess. In the ENGINE's tile grid:

        north = -y        east = +x        south = +y        west = -x

Careful: that grid is LEFT-HANDED (east x south = up), so it is NOT the frame you
model in. In Blender, north is +Y. projection.WORLD_AZIMUTH_DEG carries the whole
argument, and it matters: the first cut of this module modelled the pieces with
the engine's own axes, and every image came out REFLECTED - n swapped with w, e
with s. It compiled. It looked fine. Half the road connected backwards.

SIXTEEN IMAGES FROM SIX MODELS
------------------------------
The camera never moves, but the way can be turned on the tile. Rotating a piece
by +90 degrees maps north->east->south->west->north, which on the bitmask is just
a rotate-left. So each modelled piece sweeps out a whole orbit of ribis:

        piece       base ribi        turns      covers
        none        0    "-"         1          0
        end         1    "n"         4          n e s w
        straight    5    "ns"        2          ns ew
        curve       3    "ne"        4          ne se sw nw
        tee         7    "nse"       4          nse sew nsw new
        cross       15   "nsew"      1          nsew
                                    ---
                                     16         every ribi, exactly once

Six models, sixteen images, no gaps and no duplicates. That is the whole of a
flat way - and it is not a coincidence, it is the orbit decomposition of the
rotate-left action on the four bits.
"""

from . import projection

# --- the bits, from dataobj/ribi.h:170 ---------------------------------------
NORTH, EAST, SOUTH, WEST = 1, 2, 4, 8

# The bit as a step in the ENGINE's tile grid (x east, y SOUTH). This is what
# project_engine() wants, so it is what the tests probe with.
RIBI_ENGINE_VECTOR = {
    NORTH: (0, -1),
    EAST:  (1, 0),
    SOUTH: (0, 1),
    WEST:  (-1, 0),
}

# The same bit as a direction IN BLENDER, where +Y is north - because the engine's
# frame is left-handed and Blender's is not, so the two can only be reconciled by
# calling the engine's -y "north" (projection.WORLD_AZIMUTH_DEG has the whole
# argument). This is the one an artist models against.
RIBI_BLENDER_VECTOR = {
    NORTH: (0, 1),
    EAST:  (1, 0),
    SOUTH: (0, -1),
    WEST:  (-1, 0),
}

# writer/way_writer.cc:25, verbatim and in order. The first 16 are indexed BY the
# mask; the last 10 are the extended switch images (a crossing drawn two ways),
# which is why the writer only reads them when image[new2] exists.
RIBI_CODES = (
    "-", "n",  "e",  "ne",  "s",  "ns",  "se",  "nse",
    "w", "nw", "ew", "new", "sw", "nsw", "sew", "nsew",
    "nse1", "new1", "nsw1", "sew1", "nsew1",
    "nse2", "new2", "nsw2", "sew2", "nsew2",
)

BASIC_RIBI_COUNT = 16


def code(ribi):
    """Bitmask -> the .dat key spelling. code(5) == 'ns'."""
    if not 0 <= ribi < BASIC_RIBI_COUNT:
        raise ValueError("ribi must be a 4-bit mask, got %r" % (ribi,))
    return RIBI_CODES[ribi]


def rotate(ribi, turns):
    """Turn a ribi by `turns` quarter-turns clockwise on screen (n->e->s->w).

    On the bitmask that is a rotate-left, because the bits are in compass order.
    """
    turns %= 4
    return ((ribi << turns) | (ribi >> (4 - turns))) & 0xF


# --- the six pieces ----------------------------------------------------------
#
# MODEL CONVENTION: a piece is modelled in its BASE ribi, on a flat tile centred
# on the Blender origin, with NORTH = +Y and EAST = +X (see RIBI_BLENDER_VECTOR).
# "end" is a stub that only meets the tile's north edge; "curve" joins the north
# and east edges; and so on.
PIECES = (
    ("none",     0),
    ("end",      NORTH),
    ("straight", NORTH | SOUTH),
    ("curve",    NORTH | EAST),
    ("tee",      NORTH | SOUTH | EAST),
    ("cross",    NORTH | SOUTH | EAST | WEST),
)

PIECE_BASE = dict(PIECES)
PIECE_NAMES = tuple(name for name, _ in PIECES)


def orbit(base):
    """The distinct ribis a piece reaches by turning, and the turn that gets there.

    -> [(ribi, turns)], turns ascending. A straight only has two: turning it twice
    gives back the same mask, and rendering that image again would be waste.
    """
    out, seen = [], set()
    for turns in range(4):
        r = rotate(base, turns)
        if r not in seen:
            seen.add(r)
            out.append((r, turns))
    return out


def plan(pieces=PIECE_NAMES):
    """Every image a flat way needs -> [(ribi, piece_name, turns)], ribi ascending.

    `pieces` is which pieces the artist actually modelled. With all six the plan
    covers all sixteen ribis; with fewer, missing() says what the way will be
    blind to.
    """
    out = []
    for name in pieces:
        if name not in PIECE_BASE:
            raise ValueError("unknown way piece %r; the engine's shapes are: %s"
                             % (name, ", ".join(PIECE_NAMES)))
        for ribi, turns in orbit(PIECE_BASE[name]):
            out.append((ribi, name, turns))
    out.sort()
    return out


def missing(pieces):
    """Ribis with no image, given these pieces -> [ribi].

    Not fatal: the writer stores an empty entry and the engine draws nothing, so
    a road missing its `cross` piece is simply INVISIBLE at every four-way
    junction. Nobody warns you. We do.
    """
    covered = {ribi for ribi, _, _ in plan(pieces)}
    return [r for r in range(BASIC_RIBI_COUNT) if r not in covered]


def azimuth_for(turns):
    """Camera azimuth that renders a piece turned by `turns` quarter-turns.

    A turn steps the ribi n -> e -> s -> w. In Blender that is +Y -> +X -> -Y ->
    -X, which is a rotation of MINUS 90 degrees each time (Blender measures
    positive counter-clockwise, and the compass runs the other way round). The rig
    holds the model still and orbits the camera instead, so the camera goes the
    opposite way again:

        model turn = -90*t     =>     camera azimuth = 45 + 90*t

    The two sign flips cancel, which is exactly the sort of thing that is easier
    to get right by asking the pixels than by staring at it - see tests/blender_way.
    """
    return projection.world_azimuth(-90.0 * turns)


# --- slopes ------------------------------------------------------------------
#
# A way climbing a hill needs its own image. writer/way_writer.cc:115 reads
#
#     imageup[n|w|e|s]     single-height slope
#     imageup2[n|w|e|s]    double-height slope
#
# and accepts a numeric spelling that looks arbitrary until you decode it:
#
#     imageup[3] imageup[6] imageup[9] imageup[12]
#
# Those are slope4_t corner bits (dataobj/ribi.h:119) - SW=1, SE=2, NE=4, NW=8 -
# and a slope is named after the direction it FACES, so its far corners are the
# raised ones. A north slope has its south corners up: SW|SE = 1|2 = 3. West: 6.
# East: 9. South: 12. The numbers line up with slope_names[] = {n, w, e, s}
# exactly, which is the proof the old and new spellings are the same key.
SLOPE_NAMES = ("n", "w", "e", "s")
SLOPE_LEGACY_CODE = {"n": 3, "w": 6, "e": 9, "s": 12}

# A way on a slope runs ALONG the slope, so the piece to model is the straight
# one, sitting on a ramp. The name is the direction the ramp faces.
SLOPE_TURNS = {"n": 0, "e": 1, "s": 2, "w": 3}

# way_desc.h:176 - "hack for old ways without double height images to use single
# slope images for both". Skipping imageup2 is therefore legal and merely ugly:
# the way stretches over a double slope instead of climbing it.
DOUBLE_SLOPE_OPTIONAL = True


def slope_plan(double=False):
    """-> [(key, name, turns)] for the slope images, in the writer's own order."""
    prefix = "imageup2" if double else "imageup"
    return [("%s[%s]" % (prefix, name), name, SLOPE_TURNS[name])
            for name in SLOPE_NAMES]


# --- diagonals ---------------------------------------------------------------
#
# When a road runs corner-to-corner the engine draws a dedicated diagonal image
# instead of two curves. writer/way_writer.cc:135 loops ribi 3, 6, 9, 12 - the
# four curves - so a diagonal is keyed by the curve it replaces.
DIAGONAL_RIBIS = (3, 6, 9, 12)   # ne, se, nw, sw - the writer's order


def diagonal_plan():
    """-> [(key, turns)] for diagonal[ne|se|nw|sw]."""
    base = NORTH | EAST
    turn_of = {rotate(base, t): t for t in range(4)}
    return [("diagonal[%s]" % code(r), turn_of[r]) for r in DIAGONAL_RIBIS]


# NO ICON, NO ROAD.
#
# builder/wegbauer.cc:123, when the pakset is loaded:
#
#     if( desc->get_cursor()->get_image_id(1) != IMG_EMPTY ) {
#         tool_build_way_t *tool = new tool_build_way_t();   // ... and register it
#     }
#     else {
#         desc->set_builder( NULL );
#     }
#
# Image 1 of the cursor skin is the ICON. Ship a way without one and the engine
# loads it perfectly, lists it nowhere, gives it no toolbar button, and hands the
# scripting API a way with no builder - so it cannot be built AT ALL. makeobj does
# not warn. The pakset does not warn. It is simply not in the game.
#
# The same line appears, verbatim, in obj/wayobj.cc:558, obj/roadsign.cc:753,
# builder/brueckenbauer.cc, builder/tunnelbauer.cc and builder/hausbauer.cc: it is
# the rule for EVERYTHING the player builds. core/schema.py lints for it.
#
# We found it the only way anyone ever finds it - by laying the road in a running
# game and being told there was no such road.
DEFAULT_ICON_RIBI = EAST | WEST      # a straight run reads best as a button


# See core/datgen.py for why no comment ever shares a line with a value: in a
# .dat, '#' only opens a comment at the START of a line.
_WAY_SKELETON = """\
obj=way
name={name}
copyright={author}
waytype={waytype}
system_type={system_type}

# --- economy -------------------------------------------------------------
# cost and maintenance are in 1/100 credits; topspeed is km/h.
cost={cost}
maintenance={maintenance}
topspeed={topspeed}
axle_load={axle_load}
intro_year={intro_year}
retire_year={retire_year}

# --- the build tool ------------------------------------------------------
# WITHOUT AN ICON THERE IS NO TOOL, and without a tool the way cannot be built
# by anyone - see builder/wegbauer.cc:123. It is not optional.
{ui}

# --- graphics (generated - do not hand-edit) -----------------------------
# image[<ribi>] where the ribi is n|e|s|w: north=1 east=2 south=4 west=8, and
# the engine indexes this list by that mask directly.
{images}
"""


def way_dat(name, images, ui, waytype="road", system_type=0, cost=100,
            maintenance=100, topspeed=50, axle_load=9999, author="",
            intro_year=1900, retire_year=2999):
    """A compilable way .dat. `ui` is the icon/cursor block - see ui_block()."""
    return _WAY_SKELETON.format(
        name=name, author=author, waytype=waytype, system_type=system_type,
        cost=cost, maintenance=maintenance, topspeed=topspeed,
        axle_load=axle_load, intro_year=intro_year, retire_year=retire_year,
        ui=ui, images=images,
    )


def image_block(basename, placement, prefix="image"):
    """image[<ribi>]=sheet.row.col lines, in the engine's own list order.

    placement: {ribi: (row, col)} - what sheet.assemble() gives back.
    """
    lines = []
    for ribi in sorted(placement):
        row, col = placement[ribi]
        lines.append("%s[%s]=%s.%d.%d" % (prefix, code(ribi), basename, row, col))
    return "\n".join(lines)


# --- wayobj: catenary, and anything else that rides ON a way -----------------
#
# A wayobj (obj=way_obj) is indexed by the same ribi as the way it sits on, so the
# same six models give the same sixteen images. What is new is that it needs TWO of
# them per ribi:
#
#     backimage[<ribi>]     drawn BEFORE the vehicles
#     frontimage[<ribi>]    drawn AFTER them
#
# That split is the whole reason catenary looks right: the poles and the far wire
# belong behind the train, and the wire that crosses over it belongs in front. Put
# everything in the back list and the train drives OVER its own overhead line.
#
# The engine does not decide the split for you and cannot: it is a modelling
# decision about which parts of the mesh are nearer the camera than a vehicle in
# the middle of the tile. So the artist makes it, by putting the front parts in a
# child collection (see addon/rig.collection_wayobj_setup).
WAYOBJ_BACK, WAYOBJ_FRONT = "back", "front"
WAYOBJ_LAYERS = (WAYOBJ_BACK, WAYOBJ_FRONT)

# The declared type is "way-object", with a HYPHEN - way_obj_writer.h:31, and the
# class is way_obj_writer_t, and the file is way_obj_writer.cc. Every name around it
# says way_obj; the one the .dat has to use does not. We wrote obj=way_obj, makeobj
# would have refused it, and the linter caught it first because it knows the type
# names by reading get_type_name() rather than by guessing from the filenames.
WAYOBJ_TYPE = "way-object"


_WAYOBJ_SKELETON = """\
obj=way-object
name={name}
copyright={author}

# --- what it rides on, and what it IS --------------------------------------
# waytype is the way it may be built on; own_waytype is what it grants. Catenary
# is own_waytype=electrified_track, which is what makes an electric loco run.
waytype={waytype}
own_waytype={own_waytype}
cost={cost}
maintenance={maintenance}
topspeed={topspeed}
intro_year={intro_year}
retire_year={retire_year}

# --- the build tool --------------------------------------------------------
# No icon, no tool, no catenary - obj/wayobj.cc:558, the same line as the way's.
{ui}

# --- graphics (generated - do not hand-edit) -------------------------------
# Two layers per ribi: back is drawn before the vehicles, front after. The wire
# that crosses over the train belongs in FRONT, or the train drives over it.
{images}
"""


def wayobj_dat(name, images, ui, waytype="track",
               own_waytype="electrified_track", cost=100, maintenance=100,
               topspeed=999, author="", intro_year=1900, retire_year=2999):
    """A compilable wayobj .dat - catenary, third rail, street lamps."""
    return _WAYOBJ_SKELETON.format(
        name=name, author=author, waytype=waytype, own_waytype=own_waytype,
        cost=cost, maintenance=maintenance, topspeed=topspeed,
        intro_year=intro_year, retire_year=retire_year, ui=ui, images=images,
    )


def wayobj_image_block(basename, placement):
    """backimage[<ribi>] / frontimage[<ribi>] lines.

    placement: {(layer, ribi): (row, col)}, layer in WAYOBJ_LAYERS.
    """
    lines = []
    for layer in WAYOBJ_LAYERS:
        for (lay, ribi) in sorted(placement, key=lambda k: k[1]):
            if lay != layer:
                continue
            row, col = placement[(lay, ribi)]
            lines.append("%simage[%s]=%s.%d.%d"
                         % (layer, code(ribi), basename, row, col))
    return "\n".join(lines)


def ui_block(basename, placement, icon_ribi=DEFAULT_ICON_RIBI, cursor_ribi=None):
    """icon= and cursor= lines. The icon is what makes the way buildable at all.

    Both are ordinary image references, so by default we simply point them at one
    of the sixteen images the way already has: nothing extra to model, and an
    artist who wants a hand-drawn button just passes their own.
    """
    if icon_ribi not in placement:
        raise ValueError("no image for ribi %r to use as the icon" % (icon_ribi,))
    cursor_ribi = icon_ribi if cursor_ribi is None else cursor_ribi

    ir, ic = placement[icon_ribi]
    cr, cc = placement[cursor_ribi]
    return ("icon=%s.%d.%d\ncursor=%s.%d.%d"
            % (basename, ir, ic, basename, cr, cc))
