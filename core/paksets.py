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

height_conversion_factor
             the pakset's `height_conversion_factor`, from the same simuconf.tab
             (settings.cc:1342 -> env_t::pak_height_conversion_factor, clamped to
             1..2). The engine multiplies terrain heights by it and, crucially,
             feeds it to slope_from_slope4() (grund.cc:240, tunnelboden.cc:110,
             brueckenboden.cc:82): with factor 2 a single terrain step becomes a
             DOUBLE-height slope, so the pakset's hills are double by default.

             It does not change any pixel of a given image - a double-slope image
             always spans two height levels. What it changes is WHICH image is the
             common case. ways.py calls the double-slope image (imageup2 / the
             way_slope2 model) "optional" and "merely ugly to skip", and for a
             factor-1 pakset that is true. For pak128 it is NOT: factor 2 makes
             the double slope the ordinary hill, so a pak128 way that omits its
             way_slope2 stretches a single-height image over every normal hill.

             MEASURED, from the paksets themselves:

                 pak (the demo pakset, 64px)   factor = 1   single-height hills
                 pak128                        factor = 2   double-height hills

             Default is 1 (environment.cc:43); pak192/pak256 are unmeasured and
             carry it.
"""

from dataclasses import dataclass

from . import projection


@dataclass(frozen=True)
class Pakset:
    name: str
    tile_px: int
    tile_world: float = 2.0
    height_step: int = 16
    height_conversion_factor: int = 1

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
    def double_slope_default(self) -> bool:
        """Are this pakset's hills double-height by default? (factor == 2).

        When true, the double-slope way/wayobj images (imageup2, the way_slope2
        model) are the ORDINARY case, not optional decoration - an artist who
        skips them stretches a single-height image over every normal hill.
        """
        return self.height_conversion_factor == 2

    @property
    def double_slope_rise_px(self) -> float:
        """Screen pixels a DOUBLE-height slope rises: two height levels."""
        return 2.0 * self.height_rise_px

    @property
    def double_slope_rise_world(self) -> float:
        """Blender units a double-slope ramp (way_slope2) must rise: 2x single."""
        return 2.0 * self.height_world

    @property
    def makeobj_arg(self) -> str:
        """The command makeobj wants: `makeobj pak128 out.pak src/`."""
        return "pak" if self.tile_px == 64 else "pak%d" % self.tile_px


# measured: simutrans/pak/config/simuconf.tab   -> tile_height 16, factor 1
PAK64 = Pakset("pak64", 64, height_step=16, height_conversion_factor=1)
# measured: pak128/config/simuconf.tab          -> tile_height  8, factor 2
PAK128 = Pakset("pak128", 128, height_step=8, height_conversion_factor=2)
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
