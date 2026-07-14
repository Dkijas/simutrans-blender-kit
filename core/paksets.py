"""
Pakset profiles.

tile_px      the tile edge in pixels. This is the number in the pakset name and
             the number you pass to makeobj (`makeobj pak128 ...`).

tile_world   how many Blender units one tile is modelled as. This is pure
             convention - it only has to be consistent with ortho_scale. The
             German wiki's Blender page models a tile as 2 units, so we default
             to that; anything works as long as ortho_scale matches.

height_step  vertical pixels per height level. NOT a universal constant: the
             engine reads it per pakset (environment.h:22 -
             `#define TILE_HEIGHT_STEP (env_t::pak_tile_height_step)`), so it
             comes from the pakset's simuconf.tab. Only affects terrain/height,
             not flat-ground vehicles, but the rig exposes it for buildings.
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
    def makeobj_arg(self) -> str:
        """The command makeobj wants: `makeobj pak128 out.pak src/`."""
        return "pak" if self.tile_px == 64 else "pak%d" % self.tile_px


PAK64 = Pakset("pak64", 64)
PAK128 = Pakset("pak128", 128)
PAK192 = Pakset("pak192", 192)
PAK256 = Pakset("pak256", 256)

PROFILES = {p.name: p for p in (PAK64, PAK128, PAK192, PAK256)}


def get(name: str) -> Pakset:
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(
            "unknown pakset %r (known: %s)" % (name, ", ".join(sorted(PROFILES)))
        )
