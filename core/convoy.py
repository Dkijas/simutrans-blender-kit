"""Where the engine puts each car of a train, and what that does to the joints.

THE RULE (one rule, and it is not the one you would guess)

The engine trails each car behind the one in front by the length OF THE ONE IN
FRONT. Not by its own length - by its predecessor's:

    simconvoi.cc:428   step_pos -= v->get_desc()->get_length_in_steps();
    simconvoi.cc:2153  the same, when the depot lets the convoy out

and the sprite is then drawn at that position, with no reference to length at all:

    vehicle_base.cc:338  get_screen_offset() reads `steps`, and nothing else.

So the position of a car is fixed by the cars in FRONT of it, while the picture of
it is whatever the artist drew inside the cell. Those two agree only if the artist
drew the body centred AND consecutive cars share a length. Otherwise every joint
opens by exactly

    (L_previous - L_this) / 2        in carunits (1/16 of a tile)

positive is a hole, negative an overlap. There is no waytype branch anywhere in
this: convoi_t and vehicle_base_t do it the same way for road, rail, tram,
monorail, ship and aircraft alike.

WHAT PAK128 ACTUALLY DOES, MEASURED

Not what we assumed. pak128's rail vehicles are NOT all length 8 - 425 of 505 are,
but 80 are not, and its trams run from 2 to 8. Mixed-length units are everywhere:
every steam engine and its tender, every articulated bus, most trams.

They do not gap, because the artists draw the body OFF-CENTRE by exactly the amount
above. Measured, in the Skoda 19 Tr trolleybus (front 8, middle 4, rear 4), heading
`e`, ink centre of each cell:

    front   45.0 px          predicted shift to the next car:  +2 carunits = +8 px
    middle  53.5 px          measured                                       +8.5 px
    rear    53.0 px          predicted 0 (4 -> 4)              measured    -0.5 px

Half a pixel out, over two joints. That is not a coincidence - it is the formula,
in someone else's art, drawn years before we wrote this.

WHICH IS WHY THIS IS NOT A LINTER RULE. A .dat says nothing about where the ink
sits in the cell, so "these two cars have different lengths" is not a defect - it
is a question the .dat cannot answer. Ask it as a warning and it accuses 56 pieces
of correct, shipped pak128 art. What a tool can honestly do is COMPUTE the offset,
which is what this module is for.
"""

import math

# simunits.h:95
CARUNITS_PER_TILE = 16


def joint_gap(length_prev, length_this):
    """The joint between two coupled cars, in carunits. + is a hole, - an overlap."""
    return (length_prev - length_this) / 2.0


def joint_gaps(lengths):
    """Every joint of a unit, front to back. -> [carunits], one per joint."""
    return [joint_gap(lengths[i - 1], lengths[i]) for i in range(1, len(lengths))]


def art_offsets(lengths):
    """How far FORWARD each car's art must sit in its cell, in carunits.

    -> [carunits], one per car, starting at 0 for the leading car (which has
    nothing in front of it to line up with, so it defines the datum).

    Each car inherits its predecessor's offset and adds its own joint:

        a[i] = a[i-1] + (L[i-1] - L[i]) / 2

    Feed it [8, 8, 8, 8, 8] and you get zeros - which is why a unit of equal-length
    cars needs no offsets at all, and why that is the easy way out.
    """
    out = [0.0]
    for gap in joint_gaps(lengths):
        out.append(out[-1] + gap)
    return out


def carunits_to_tiles(carunits):
    return carunits / float(CARUNITS_PER_TILE)


def along_track_px(carunits, tile_px):
    """Screen distance along a straight (cardinal) way, in pixels.

    One tile of travel moves a vehicle (tile_px/2, tile_px/4) on screen - the 2:1
    diamond - so the distance along the rail is tile_px * sqrt(5) / 4, which is
    71.55 px in pak128, NOT 128. Get this wrong and every gap you predict is out by
    a factor of nearly two.
    """
    return carunits_to_tiles(carunits) * tile_px * math.sqrt(5) / 4.0


def screen_dx_px(carunits, tile_px):
    """The horizontal component of that, which is what you measure on a sprite sheet.

    tile_px/2 per tile: the x half of the same step.
    """
    return carunits_to_tiles(carunits) * tile_px / 2.0


def world_offset(carunits, tile_world):
    """The same offset in Blender units, along the model's own +X (its nose)."""
    return carunits_to_tiles(carunits) * tile_world


def describe(names, lengths, tile_px=128):
    """A plain-language report for one unit. -> [str], one line per car."""
    offsets = art_offsets(lengths)
    lines = []
    for i, (name, length, off) in enumerate(zip(names, lengths, offsets)):
        if i == 0:
            lines.append("%-28s length %-3d datum" % (name, length))
            continue
        gap = joint_gap(lengths[i - 1], lengths[i])
        lines.append(
            "%-28s length %-3d joint %+.1f carunits (%+.1f px along the way); "
            "draw its art %+.1f carunits forward (%+.1f px) of centre"
            % (name, length, gap, along_track_px(gap, tile_px),
               off, screen_dx_px(off, tile_px)))
    return lines
