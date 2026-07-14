"""
Pakset profiles.

tile_px      the tile edge in pixels. This is the number in the pakset name and
             the number you pass to makeobj (`makeobj pak128 ...`).

tile_world   how many Blender units one tile is modelled as. This is pure
             convention - it only has to be consistent with ortho_scale. The
             German wiki's Blender page models a tile as 2 units, so we default
             to that; anything works as long as ortho_scale matches.

height_step  the pakset's own `tile_height`, straight out of its
             config/simuconf.tab (settings.cc:1338 -> env_t::pak_tile_height_step).
             It is NOT a pixel count and it is NOT a universal constant. It is in
             64-pixel units and the engine scales it to the pakset's tile width
             (simconst.h:110), so the rise on screen is

                 tile_height * tile_px / 64

             This module used to declare 16 for every profile. pak128's own
             simuconf.tab says EIGHT, and 16 would have drawn every ramp twice as
             steep as the pakset it sits in. Nothing broke, because until the slope
             images existed nobody read the field - which is exactly the sort of
             wrong number that waits.

             MEASURED, from the paksets themselves:

                 pak (the demo pakset, 64px)   tile_height = 16   -> 16 px
                 pak128                        tile_height =  8   -> 16 px

             Both come out at sixteen screen pixels a level: the pakset authors
             keep the apparent steepness constant, and the .tab number moves to
             pay for it.

             pak192 and pak256 are NOT measured - we do not have them here. They
             carry the engine's default and are marked below.
"""

from dataclasses import dataclass

from . import projection


@dataclass(frozen=True)
class Pakset:
    name: str
    tile_px: int
    tile_world: float = 2.0
    height_step: int = 16

    @property
    def ortho_scale(self) -> float:
        """Blender ortho_scale that makes one tile span exactly tile_px."""
        return projection.ortho_scale(self.tile_world)

    @property
    def diamond_px(self) -> tuple:
        """(w, h) of the ground diamond. Always 2:1."""
        return projection.tile_diamond_px(self.tile_px)

    @property
    def height_world(self) -> float:
        """One height level in Blender units - how far a single ramp rises."""
        return projection.height_world(self.height_step, self.tile_world)

    @property
    def height_rise_px(self) -> float:
        """One height level in screen pixels, as the engine draws it."""
        return projection.height_rise_px(self.height_step, self.tile_px)

    @property
    def makeobj_arg(self) -> str:
        """The command makeobj wants: `makeobj pak128 out.pak src/`."""
        return "pak" if self.tile_px == 64 else "pak%d" % self.tile_px


PAK64 = Pakset("pak64", 64, height_step=16)     # measured: simutrans/pak/config
PAK128 = Pakset("pak128", 128, height_step=8)   # measured: pak128/config/simuconf.tab
PAK192 = Pakset("pak192", 192)                  # NOT measured - the engine default
PAK256 = Pakset("pak256", 256)                  # NOT measured - the engine default

PROFILES = {p.name: p for p in (PAK64, PAK128, PAK192, PAK256)}


def get(name: str) -> Pakset:
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(
            "unknown pakset %r (known: %s)" % (name, ", ".join(sorted(PROFILES)))
        )
