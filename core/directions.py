"""
Vehicle facing directions.

The direction codes and their ORDER are taken verbatim from the engine:

  src/simutrans/descriptor/writer/vehicle_writer.cc:179
      static const char* const dir_codes[] = {
          "s", "w", "sw", "se", "n", "e", "ne", "nw"
      };

Two engine facts that decide how many images an artist must produce
(src/simutrans/descriptor/vehicle_desc.h):

  * get_dirs() returns 8 if image[4] exists, otherwise 4.
  * a direction > 3 with no image falls back to image[dir - 4].

So the first FOUR codes (s, w, sw, se) are a complete set for a SYMMETRIC
vehicle: the engine simply reuses the same bitmap for the opposite heading -
it does NOT mirror it. An asymmetric vehicle (and, by pak128.Britain's own
guidelines, any road vehicle) needs all eight.
"""

# Engine order. The .dat keys are EmptyImage[<code>] / FreightImage[n][<code>].
DIR_CODES = ("s", "w", "sw", "se", "n", "e", "ne", "nw")

# The opposite heading each code falls back to when only 4 images exist.
FALLBACK = {"n": "s", "e": "w", "ne": "sw", "nw": "se"}

# Compass heading -> camera azimuth, in 45-degree steps.
#
# MODEL CONVENTION: the vehicle's nose points along +X.
#
# BASE_AZIMUTH_DEG was not guessed - it was measured against real pakset art.
# Downloading a shipped pak128 vehicle (vehicles/road-psg+mail/aec_aclo_regent_iii,
# by Zeno) and reading its .dat against its sheet gives three hard constraints:
#
#     EmptyImage[nw] and EmptyImage[se]  are END-ON views (narrow silhouettes)
#     EmptyImage[ne] and EmptyImage[sw]  are BROADSIDE views (long silhouettes)
#     EmptyImage[n/s/e/w]                are three-quarter views
#
# That is not arbitrary: a vehicle running along a world diagonal travels straight
# up/down the screen, i.e. along the camera axis, so it really is seen end-on.
#
# With the camera at azimuth az, the model's +X axis lands on screen at
# (cos az, -0.5 sin az). Solving the three constraints leaves az = 135 for "s"
# (and the residual 180-degree flip is settled by the real bus, whose nose sits
# at the lower-LEFT in its S frame - which is where +X points when az = 135).
#
# An earlier value of 45 was wrong by exactly 90 degrees: it put the end-on views
# on sw/ne instead of nw/se, so every diagonal heading would have been rendered
# with the vehicle facing the wrong way.
BASE_AZIMUTH_DEG = 135.0

_AZIMUTH_ORDER = ("s", "sw", "w", "nw", "n", "ne", "e", "se")


def azimuth_deg(code: str) -> float:
    """Camera azimuth (degrees) for a facing code."""
    code = code.lower()
    if code not in _AZIMUTH_ORDER:
        raise ValueError("unknown direction code: %r" % (code,))
    return BASE_AZIMUTH_DEG + 45.0 * _AZIMUTH_ORDER.index(code)


def codes_for(count: int) -> tuple:
    """The dat keys to emit for a 4- or 8-direction vehicle, in engine order."""
    if count not in (4, 8):
        # makeobj is strict here: vehicle_writer.cc fatals with
        # "Missing images (must be either 4 or 8 directions...)"
        raise ValueError("Simutrans accepts only 4 or 8 directions, not %r" % (count,))
    return DIR_CODES[:count]
