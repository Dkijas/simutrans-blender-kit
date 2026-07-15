"""Bridges: spans, ramps, starts and pillars, each in two layers.

Grounded in descriptor/writer/bridge_writer.cc (write_bridge_images):

- Four image GROUPS, each with its own set of directions:
    image  (the span/deck)  ns, ew
    start  (deck meets ramp) n, s, e, w
    ramp   (the sloped end)  n, s, e, w
    pillar (the leg)         s, w
  and each key exists in a back and a front layer (backimage[ns], frontimage[ns]),
  the catenary split - the far side of the deck behind the vehicle, the near
  railing in front.

- The icon (cursor image 1) is mandatory, as for a way: builder/brueckenbauer.cc
  carries the same 'no icon, no builder' rule. makeobj does not warn.

Double-height variants (image2/start2/ramp2/pillar2) and snow seasons are the
engine's optional extras; this emits the single-height, single-season bridge.
"""

# bridge_writer.cc names[] - the groups and their directions, in the writer's
# own order (the engine reads the list back by position).
GROUPS = (
    ("image",  ("ns", "ew")),
    ("start",  ("n", "s", "e", "w")),
    ("ramp",   ("n", "s", "e", "w")),
    ("pillar", ("s", "w")),
)


def image_block(basename, back, front=None):
    """back<group>[dir] / front<group>[dir] lines, in the writer's order.

    back and front are {group: {dir: (row, col)}}. `back` must cover every
    direction of every group - the engine reads the list by position, so a hole
    shifts every image after it onto the wrong piece, the way trap. `front` is all
    of a group or none of it, per group.
    """
    lines = []
    for group, dirs in GROUPS:
        group_back = back.get(group, {})
        missing = [d for d in dirs if d not in group_back]
        if missing:
            raise ValueError("bridge back%s needs every direction; missing %s"
                             % (group, ", ".join(missing)))
        for d in dirs:
            r, c = group_back[d]
            lines.append("back%s[%s]=%s.%d.%d" % (group, d, basename, r, c))

    if front:
        for group, dirs in GROUPS:
            group_front = front.get(group)
            if not group_front:
                continue
            missing = [d for d in dirs if d not in group_front]
            if missing:
                raise ValueError("bridge front%s is all directions or none; "
                                 "missing %s" % (group, ", ".join(missing)))
            for d in dirs:
                r, c = group_front[d]
                lines.append("front%s[%s]=%s.%d.%d" % (group, d, basename, r, c))
    return "\n".join(lines)


def icon_block(basename, back, icon_group="ramp", icon_dir="n"):
    """icon= and cursor= from one rendered bridge image (a ramp end reads well as
    a toolbar picture). The icon is what makes the bridge buildable at all -
    builder/brueckenbauer.cc, the way's 'no icon, no builder' rule."""
    group = back.get(icon_group, {})
    if icon_dir not in group:
        raise ValueError("no %s image for direction %r to use as the icon"
                         % (icon_group, icon_dir))
    r, c = group[icon_dir]
    return "icon=%s.%d.%d\ncursor=%s.%d.%d" % (basename, r, c, basename, r, c)


_BRIDGE_SKELETON = """\
obj=bridge
name={name}
copyright={author}
waytype={waytype}

# --- economy / limits ----------------------------------------------------
# cost and maintenance are in 1/100 credits; topspeed is km/h.
cost={cost}
maintenance={maintenance}
topspeed={topspeed}
axle_load={axle_load}
intro_year={intro_year}
# max_length 0 = unlimited; max_height is how far the bridge may clear the ground.
max_length={max_length}
max_height={max_height}
# pillar_distance 0 = no pillars; otherwise one every N tiles.
pillar_distance={pillar_distance}

# --- the build tool ------------------------------------------------------
# WITHOUT AN ICON THERE IS NO TOOL - builder/brueckenbauer.cc, the way's rule.
{ui}

# --- graphics (generated - do not hand-edit) -----------------------------
# back<group>[dir] behind the vehicle, front<group>[dir] over it. Groups:
# image (span) ns/ew, start & ramp n/s/e/w, pillar s/w. Two layers, like catenary.
{images}
"""


def bridge_dat(name, images, ui, waytype="track", topspeed=120, cost=100,
               maintenance=100, axle_load=9999, intro_year=1900, max_length=0,
               max_height=4, pillar_distance=0, author=""):
    """A compilable single-height bridge .dat.

    `ui` is icon_block(); `images` is image_block(). max_length 0 is unlimited;
    pillar_distance 0 turns pillars off (and then the pillar images are unused).
    """
    return _BRIDGE_SKELETON.format(
        name=name, author=author, waytype=waytype, cost=cost,
        maintenance=maintenance, topspeed=topspeed, axle_load=axle_load,
        intro_year=intro_year, max_length=max_length, max_height=max_height,
        pillar_distance=pillar_distance, ui=ui, images=images,
    )
