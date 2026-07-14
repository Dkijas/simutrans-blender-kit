"""
Emit .dat image references from a sheet layout.

This is where the pipeline closes: assemble() knows exactly which cell each
direction landed in, so the image references can be written mechanically
instead of by a human counting rows and columns. Getting `EmptyImage[nw]` to
point at the wrong cell is the classic way to end up with a vehicle that drives
sideways, and it is invisible until you look at it in game.

makeobj's syntax is `<sheet_basename>.<row>.<col>` (.Y.X, zero-based) - see
image_writer / the DEBUG output of makeobj, which prints exactly this mapping.
"""

from . import directions


def image_block(sheet_basename: str, placement: dict, freight: bool = False,
                freight_index: int = 0) -> str:
    """Lines of EmptyImage[dir]= / FreightImage[n][dir]= for one sheet.

    placement: {dir_code: (row, col)} as returned by sheet.assemble().
    Emitted in the engine's own key order (vehicle_writer.cc dir_codes), which
    keeps diffs stable and matches what pakset maintainers expect to read.
    """
    keyword = "FreightImage" if freight else "EmptyImage"
    lines = []
    for code in directions.DIR_CODES:
        if code not in placement:
            continue
        row, col = placement[code]
        if freight:
            key = "%s[%d][%s]" % (keyword, freight_index, code)
        else:
            key = "%s[%s]" % (keyword, code)
        lines.append("%s=%s.%d.%d" % (key, sheet_basename, row, col))
    return "\n".join(lines)


# Minimal, honest skeleton. Every value here is one the engine actually reads
# (extracted from descriptor/writer/vehicle_writer.cc), documented so nobody has
# to guess or trawl the forum for the parameter list.
#
# BEWARE, and this is not in any tutorial: a .dat has NO end-of-line comments.
# tabfile_t::read_line() (dataobj/tabfile.cc) skips a line only when it STARTS
# with '#' (or with a space); it never strips a '#' that appears after a value.
# So `freight=None   # a note` sets freight to the whole string
# "None   # a note", and the engine then dies with
#     FATAL ERROR: Cannot resolve 'GOOD-None   # a note'
# Numeric keys hide the bug, because atoi() stops at the space. Every comment
# below therefore sits on its OWN line, in column 0.
_VEHICLE_SKELETON = """\
obj=vehicle
name={name}
copyright={author}
waytype={waytype}

# --- economy -------------------------------------------------------------
# cost/runningcost are in cents; runningcost is per km.
# Omit intro_year and you silently get the engine default.
cost={cost}
runningcost={runningcost}
intro_year={intro_year}
retire_year={retire_year}

# --- physics -------------------------------------------------------------
# engine_type: steam|diesel|electric|bio|sail|hydrogene|fuel_cell|battery
# speed km/h, power kW (0 = unpowered wagon), gear % (100 = neutral),
# weight tonnes (empty), length in 1/16 of a tile (OBJECT_OFFSET_STEPS=16).
engine_type={engine_type}
speed={speed}
power={power}
gear={gear}
weight={weight}
length={length}

# --- payload -------------------------------------------------------------
# freight: None|Passagiere|Post|<goods name>
freight={freight}
payload={payload}

# --- coupling ------------------------------------------------------------
{coupling}
# --- graphics (generated - do not hand-edit) -----------------------------
{images}
"""


# Coupling is the one place where saying nothing and saying "none" are opposites,
# and the engine is unforgiving about it (descriptor/vehicle_desc.h:219):
#
#     if (leader_count == 0) return true;      // no Constraint[Prev] at all
#                                              //   -> couples behind ANYTHING
#
# and a listed constraint of `none` writes a NULL child, which means "the only
# thing allowed in front of me is nothing" - i.e. I may ONLY run at the head of
# the convoy. Write both `none`s and the vehicle can only ever run ALONE, which
# is right for a lone shunter and wrong for every carriage ever built.
#
# So: no constraints unless asked for. Pass a list of vehicle names to restrict,
# using "none" for "may be at the end" and "any" for "anything at all".
def _coupling_block(prev, next_) -> str:
    lines = []
    for side, names in (("Prev", prev), ("Next", next_)):
        if not names:
            continue
        for i, other in enumerate(names):
            lines.append("Constraint[%s][%d]=%s" % (side, i, other))
    if not lines:
        lines.append("# unconstrained: this vehicle couples to anything")
    return "\n".join(lines) + "\n"


def vehicle_dat(name, images, waytype="track", author="", freight="None",
                payload=0, speed=100, power=0, gear=100, weight=20, length=8,
                cost=1000000, runningcost=100, intro_year=1900, retire_year=2999,
                engine_type="diesel", constraint_prev=(),
                constraint_next=()) -> str:
    """A complete, compilable vehicle .dat with the image block filled in."""
    return _VEHICLE_SKELETON.format(
        name=name, author=author, waytype=waytype, cost=cost,
        runningcost=runningcost, intro_year=intro_year, retire_year=retire_year,
        engine_type=engine_type, speed=speed, power=power, gear=gear,
        weight=weight, length=length, freight=freight, payload=payload,
        coupling=_coupling_block(constraint_prev, constraint_next),
        images=images,
    )
