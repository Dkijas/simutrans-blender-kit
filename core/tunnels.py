"""Tunnel portals: four directions, two layers.

Grounded in descriptor/writer/tunnel_writer.cc and descriptor/tunnel_desc.{h,cc}:

- A portal has four direction images, keyed n|s|e|w (tunnel_writer.cc indices[]).
  The key names the heading INTO the hill, not the slope: the engine's
  slope_indices table (tunnel_desc.cc) puts the "n" image on a SOUTH-facing slope,
  "s" on north, "e" on west, "w" on east. So the four keys are, in the writer's
  own order, n, s, e, w - which is NOT the way module's slope order (n, w, e, s),
  and mixing them up points every portal at the wrong hill.

- Each direction is drawn in two layers: backimage[dir] behind the vehicle (the
  mouth cut into the hillside) and frontimage[dir] over it (the arch the train
  passes under). It is the catenary trap again - a front piece left in the back
  list is driven straight over.

- The icon (cursor image 1) is mandatory. builder/tunnelbauer.cc carries the same
  "no icon, no builder" rule as ways: a tunnel with none loads, lists nowhere, and
  cannot be built - and makeobj does not warn.

Broad portals (the l|r|m keys) and snow seasons ([1]) are the engine's optional
extras; this module emits the narrow, single-season portal.
"""

# tunnel_writer.cc indices[] - the order the engine stores and indexes them in.
DIRS = ("n", "s", "e", "w")


def image_block(basename, back, front=None):
    """backimage[dir] / frontimage[dir] lines for the four portal directions.

    back and front are {dir: (row, col)}. `back` must cover all four directions -
    it is the portal itself, and the engine indexes by slope position, so a hole
    draws nothing on that hill. `front` (the arch over the vehicle) is all four or
    none, for the same reason a partial catenary front list ships a train driving
    over its own wire.
    """
    missing_back = [d for d in DIRS if d not in back]
    if missing_back:
        raise ValueError("a tunnel needs a back portal for every direction; "
                         "missing %s" % ", ".join(missing_back))
    lines = ["backimage[%s]=%s.%d.%d" % (d, basename, back[d][0], back[d][1])
             for d in DIRS]

    if front:
        missing_front = [d for d in DIRS if d not in front]
        if missing_front:
            raise ValueError("front portals are all four or none; missing %s"
                             % ", ".join(missing_front))
        lines += ["frontimage[%s]=%s.%d.%d" % (d, basename, front[d][0], front[d][1])
                  for d in DIRS]
    return "\n".join(lines)


def icon_block(basename, placement, icon_dir="s"):
    """icon= and cursor= from one rendered portal image.

    The icon is what makes the tunnel buildable at all (builder/tunnelbauer.cc).
    A tunnel reuses a portal image for it, exactly as a way reuses a ribi image -
    a real toolbar pictogram is nicer but not what decides buildability.
    """
    if icon_dir not in placement:
        raise ValueError("no portal image for direction %r to use as the icon"
                         % (icon_dir,))
    r, c = placement[icon_dir]
    return "icon=%s.%d.%d\ncursor=%s.%d.%d" % (basename, r, c, basename, r, c)


_TUNNEL_SKELETON = """\
obj=tunnel
name={name}
copyright={author}
waytype={waytype}

# --- economy -------------------------------------------------------------
# cost and maintenance are in 1/100 credits; topspeed is km/h.
cost={cost}
maintenance={maintenance}
topspeed={topspeed}
axle_load={axle_load}
intro_year={intro_year}

# --- the build tool ------------------------------------------------------
# WITHOUT AN ICON THERE IS NO TOOL - builder/tunnelbauer.cc, the same rule as a
# way. The tunnel loads, lists nowhere, and cannot be built by anyone.
{ui}
{way}
# --- graphics (generated - do not hand-edit) -----------------------------
# backimage[dir] behind the vehicle, frontimage[dir] over it. dir is n|s|e|w and
# names the heading INTO the hill (tunnel_desc.cc slope_indices), so "n" is drawn
# on a south-facing slope. Two layers, like catenary.
{images}
"""


def tunnel_dat(name, images, ui, waytype="track", topspeed=120, cost=100,
               maintenance=100, axle_load=9999, intro_year=1900, way="",
               author=""):
    """A compilable narrow-portal tunnel .dat.

    `ui` is icon_block(); `images` is image_block(). `way` optionally names the way
    built inside the tunnel - it is written as a cross-reference and must resolve to
    a real way at game load, so leave it empty unless you have one.
    """
    way_line = ("way=%s" % way) if way else \
        "# way: none - the tunnel carries no way of its own"
    return _TUNNEL_SKELETON.format(
        name=name, author=author, waytype=waytype, cost=cost,
        maintenance=maintenance, topspeed=topspeed, axle_load=axle_load,
        intro_year=intro_year, ui=ui, way=way_line, images=images,
    )
