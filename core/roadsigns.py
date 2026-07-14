"""Road signs and railway signals.

A sign is not a way, and it is not indexed by a ribi. It has ONE image per
direction it faces, and - if it is a signal - one set of those per aspect it can
show. descriptor/writer/roadsign_writer.cc reads them as

        image[<direction>][<state>]

and flattens them into a single list, so the engine addresses them by number:

        obj/signal.cc:111    desc->get_image_id( 3 + state*4 + offset )   // east
        obj/signal.cc:123    desc->get_image_id( 0 + state*4 + offset )   // north
        obj/signal.cc:163    desc->get_image_id( 2 + state*4 + offset )   // west
        obj/signal.cc:137    desc->get_image_id( 1 + state*4 + offset )   // south

Read the numbers straight off those four lines and the order is fixed:

        index = direction + state * (number of directions)
        direction:  0 = n    1 = s    2 = w    3 = e

which is exactly roadsign_writer's general_sign_directions[] = { n, s, w, e }.
Note it is NOT compass order - n, s, w, e - and the temptation to "fix" it into
n, e, s, w is a good way to make every sign point the wrong way.

THE STATES
----------
obj/roadsign.h:63:      STATE_RED = 0,  STATE_GREEN = 1

So state 0 is the STOP aspect. A plain sign (a give-way, a one-way arrow) has one
state and four images. A block signal has two and eight. Get the order backwards
and your signals show green for red - which is not a rendering bug, it is a
signalling bug, and the trains will act on it.

`offset` in those lines is the engine reaching for an ELECTRIFIED variant of the
signal when the track underneath has catenary and the sign ships more than eight
images (signal.cc: `if (sch->is_electrified() && (desc->get_count()/8) > 1)`).
That is a nicety; we do not emit it, and the engine simply never looks for it.
"""

from . import projection

# roadsign_writer.cc:20 - and the index IS the position in this tuple.
SIGN_DIRS = ("n", "s", "w", "e")

# roadsign_writer.cc:19 - used instead, automatically, if image[ne][0] exists.
TRAFFIC_LIGHT_DIRS = ("n", "s", "w", "e", "nw", "se", "sw", "ne")

# roadsign_writer.cc:18 - for a private-road barrier.
PRIVATE_DIRS = ("ns", "ew")

# obj/roadsign.h:63
STATE_RED, STATE_GREEN = 0, 1
STATE_NAMES = ("red", "green")

# The sign is modelled once, at the tile's NORTH edge, and turned. The turn is the
# same rotate-as-the-camera-orbits trick the ways use, so it lands here too: a
# quarter-turn steps north -> east -> south -> west, which in Blender (+Y north) is
# minus 90 degrees, so the camera goes plus 90.
DIR_TURNS = {"n": 0, "e": 1, "s": 2, "w": 3}


def dir_index(direction, dirs=SIGN_DIRS):
    """Where the engine will look for this direction's image."""
    return dirs.index(direction)


def image_index(direction, state=0, dirs=SIGN_DIRS):
    """The flat index the engine computes: direction + state * len(dirs)."""
    return dir_index(direction, dirs) + state * len(dirs)


def azimuth_for(direction):
    """Camera azimuth that renders the sign facing `direction`."""
    return projection.world_azimuth(-90.0 * DIR_TURNS[direction])


def plan(states=1, dirs=SIGN_DIRS):
    """Every image a sign needs -> [(direction, state)], in the engine's own order.

    A signal needs two states, and state 0 is RED. One state is a plain sign.
    """
    return [(d, s) for s in range(states) for d in dirs]


def image_block(basename, placement):
    """image[<dir>][<state>]=sheet.row.col lines.

    placement: {(direction, state): (row, col)} - what sheet.assemble() gives back.
    """
    lines = []
    for (d, s) in sorted(placement, key=lambda k: (k[1], SIGN_DIRS.index(k[0])
                                                   if k[0] in SIGN_DIRS else 99)):
        row, col = placement[(d, s)]
        lines.append("image[%s][%d]=%s.%d.%d" % (d, s, basename, row, col))
    return "\n".join(lines)


# See core/ways.py: builder-registered objects with no icon= are loaded, listed
# nowhere, and cannot be built. obj/roadsign.cc:753 is the same line as
# builder/wegbauer.cc:123.
_SIGN_SKELETON = """\
obj=roadsign
name={name}
copyright={author}
waytype={waytype}

# --- what kind of sign -----------------------------------------------------
# is_signal turns it into a block signal: it then needs TWO states, and state 0
# is RED (obj/roadsign.h). min_speed is the speed below which it applies.
is_signal={is_signal}
cost={cost}
min_speed={min_speed}
intro_year={intro_year}
retire_year={retire_year}

# --- the build tool --------------------------------------------------------
# No icon, no tool, no sign - obj/roadsign.cc:753.
{ui}

# --- graphics (generated - do not hand-edit) -------------------------------
# image[<dir>][<state>]; the engine flattens these to dir + state*4, with
# dir 0=n 1=s 2=w 3=e.
{images}
"""


def roadsign_dat(name, images, ui, waytype="road", is_signal=0, cost=500,
                 min_speed=0, author="", intro_year=1900, retire_year=2999):
    """A compilable road sign / signal .dat."""
    return _SIGN_SKELETON.format(
        name=name, author=author, waytype=waytype, is_signal=int(is_signal),
        cost=cost, min_speed=min_speed, intro_year=intro_year,
        retire_year=retire_year, ui=ui, images=images,
    )


def ui_block(basename, placement, icon_key=None):
    """icon= and cursor=. Without the icon the sign cannot be placed at all."""
    if icon_key is None:
        icon_key = (SIGN_DIRS[0], 0)
    if icon_key not in placement:
        raise ValueError("no image at %r to use as the icon" % (icon_key,))
    r, c = placement[icon_key]
    return "icon=%s.%d.%d\ncursor=%s.%d.%d" % (basename, r, c, basename, r, c)
