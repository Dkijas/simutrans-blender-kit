"""Measure a reference photo or works drawing. Give back numbers, never pixels.

    blender --background --factory-startup --python tools/refmeasure.py -- \
            assets/civia_465/references/civia-elevation.png --out ref.json

WHAT IT IS FOR

A reference image is a RULER, not a material. At 128 px a vehicle's body is about
40 px long and the lettering on its flank is two pixels high - there is nothing in
a photograph that can be resampled down to that and survive, and the resampling
destroys the exact colours the engine matches on (player colour, and the light
colours that make windows glow). So the photo is not the texture. The photo is
where you find out that the window band starts at 41% of the body height and ends
at 63%, and THAT is what goes into the code that paints the livery.

Everything it prints is a `reference` fact for core/spec.py: a number, plus the
image's sha256, so the claim can be re-run against the same file and nobody has to
take anyone's word for it.

WHY IT RUNS IN BLENDER

Because Blender ships numpy and reads JPEG, and the kit already needs Blender. That
is the whole reason: no new dependency, on a project whose whole selling point is
that you install one zip and it works. core/ stays stdlib-only, as it must - it has
to run inside Blender's own Python.

WHAT IT DOES NOT DO

It does not tell you what a band IS. It finds the dark bands and gives you their
edges; whether the one at 41-63% is the glazing or a livery stripe is a judgement,
and it stays with the human. A tool that guesses that and is wrong is worse than
one that says nothing, because you would believe it.
"""

import hashlib
import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import colors        # noqa: E402


def load_rgba(path):
    """-> (h, w, 4) uint8, row 0 at the TOP, in the file's own sRGB bytes.

    Blender hands back float pixels and, if it thinks the image is sRGB, converts
    them to linear on the way out - which would quietly change every number below.
    Non-Color turns that off, so what we measure is what is in the file. And its
    buffer starts at the BOTTOM row, so it gets flipped.
    """
    img = bpy.data.images.load(os.path.abspath(path))
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    a = (px.reshape(h, w, 4) * 255.0 + 0.5).astype(np.uint8)
    return np.flipud(a)


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def body_box(rgba, tol=18):
    """The subject, minus the background. -> (box, ink mask, what the background was)

    IF THE IMAGE HAS TRANSPARENCY, THE BACKGROUND IS THE TRANSPARENCY. Nothing else.
    The first version of this also matched the background COLOUR, took the RGB of the
    transparent corners - (0,0,0), because that is what a transparent pixel stores -
    and would have deleted every black outline in the drawing as "background". It got
    away with it here only because the drawing is tightly cropped. A colour match is
    for photographs, which have no alpha and do have a sky.
    """
    h, w, _ = rgba.shape
    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3].astype(np.int16)

    if (alpha == 0).any():
        ink = alpha > 0
        what = "transparency"
    else:
        corners = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
        bg = np.median(corners, axis=0)
        ink = np.abs(rgb - bg).max(axis=2) > tol
        what = "colour %s (the four corners agreed)" % [int(v) for v in bg]

    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    if not len(rows) or not len(cols):
        raise SystemExit("the whole image is background - crop it by hand, or its "
                         "background is not flat")
    return (int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])), ink, what


def _bands(profile, threshold, min_run):
    """Contiguous runs where the profile is above the threshold. -> [(a, b)]"""
    hot = profile >= threshold
    out, start = [], None
    for i, on in enumerate(hot):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= min_run:
                out.append((start, i - 1))
            start = None
    if start is not None and len(hot) - start >= min_run:
        out.append((start, len(hot) - 1))
    return out


def dark_bands(rgba, box, ink, axis="rows", share=0.45, min_run=3):
    """Where the dark stuff is, as a fraction of the body. -> [(from, to), ...]

    Dark relative to the BODY, not to some absolute grey: a white train and a blue
    train both have windows darker than their own flank. The threshold is the
    midpoint between the body's median luma and its darkest decile, which is crude,
    stated here, and works on a clean elevation.
    """
    x0, y0, x1, y1 = box
    sub = rgba[y0:y1 + 1, x0:x1 + 1, :3].astype(np.float32)
    sub_ink = ink[y0:y1 + 1, x0:x1 + 1]

    luma = sub @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    body = luma[sub_ink]
    if not body.size:
        return []
    cut = (np.median(body) + np.percentile(body, 10)) / 2.0

    dark = (luma <= cut) & sub_ink
    axis_n = 1 if axis == "rows" else 0
    counts = dark.sum(axis=axis_n).astype(np.float32)
    total = np.maximum(sub_ink.sum(axis=axis_n), 1).astype(np.float32)
    profile = counts / total

    n = len(profile)
    return [(round(a / (n - 1), 4), round(b / (n - 1), 4))
            for a, b in _bands(profile, share, min_run)]


def palette(rgba, box, ink, k=6, iterations=12):
    """The body's own colours, by k-means. -> [{rgb, share, reserved}]

    The `reserved` field is the point of it. Sample a photograph and you will sooner
    or later land on one of the engine's reserved colours - and then the game repaints
    that patch of the train in the company colour, or lights it up at night, and
    nothing tells you why. Better to hear it here.
    """
    x0, y0, x1, y1 = box
    sub = rgba[y0:y1 + 1, x0:x1 + 1, :3].astype(np.float32)
    pts = sub[ink[y0:y1 + 1, x0:x1 + 1]]
    if len(pts) > 60000:                       # plenty, and keeps it instant
        pts = pts[:: len(pts) // 60000 + 1]

    lo, hi = pts.min(axis=0), pts.max(axis=0)
    rng = np.random.default_rng(0)             # seeded: the same photo, the same answer
    cent = lo + rng.random((k, 3), dtype=np.float32) * np.maximum(hi - lo, 1)

    for _ in range(iterations):
        d = ((pts[:, None, :] - cent[None, :, :]) ** 2).sum(axis=2)
        who = d.argmin(axis=1)
        for i in range(k):
            hit = pts[who == i]
            if len(hit):
                cent[i] = hit.mean(axis=0)

    out = []
    for i in range(k):
        n = int((who == i).sum())
        if not n:
            continue
        rgb = tuple(int(round(v)) for v in cent[i])
        out.append({
            "rgb": list(rgb),
            "hex": "#%02X%02X%02X" % rgb,
            "share": round(n / len(pts), 4),
            "reserved": colors.classify(rgb),
        })
    return sorted(out, key=lambda c: -c["share"])


def profiles(rgba, box, ink):
    """Two numbers per row of the body: how much of it is THERE, and how much is DARK.

    Coverage is the one that finds the body. A raised pantograph is five pixels wide
    and two metres tall, so it stretches the bounding box without being any part of
    the vehicle's height - and on this drawing it inflates the "height" from 4.3 m to
    5.4 m. Coverage sees straight through it: the pantograph rows are 2% full, the
    roof is 95% full, and the step between them is the roofline.
    """
    x0, y0, x1, y1 = box
    sub = rgba[y0:y1 + 1, x0:x1 + 1, :3].astype(np.float32)
    sub_ink = ink[y0:y1 + 1, x0:x1 + 1]
    width = sub_ink.shape[1]

    luma = sub @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    body = luma[sub_ink]
    cut = (np.median(body) + np.percentile(body, 10)) / 2.0
    dark = (luma <= cut) & sub_ink

    coverage = sub_ink.sum(axis=1) / float(width)
    darkness = dark.sum(axis=1) / np.maximum(sub_ink.sum(axis=1), 1)
    return coverage.tolist(), darkness.tolist()


def solid_body(coverage, threshold=0.5):
    """The rows that are really the vehicle. -> (first, last) row index, or None."""
    runs = _bands(np.array(coverage), threshold, min_run=3)
    return max(runs, key=lambda r: r[1] - r[0]) if runs else None


def chart(coverage, darkness, metres_per_px=None, width=34):
    """SHOW the profiles. A number you cannot see is a number you cannot argue with.

    The bands are found with a threshold, and a threshold is a judgement. So the tool
    prints its evidence beside its answer, and you can see for yourself whether the
    band it drew round the glazing is the glazing.
    """
    n = len(darkness)
    lines = ["       %-*s %s" % (width, "coverage (where the body IS)", "dark")]
    for i, (cov, dk) in enumerate(zip(coverage, darkness)):
        frac = i / float(n - 1)
        label = ("%5.2f m" % ((n - 1 - i) * metres_per_px)) if metres_per_px \
                else ("%4.0f%%" % (100 * frac))
        lines.append("  %s |%-*s|%s" % (label, width, "=" * int(round(cov * width)),
                                        "#" * int(round(dk * width))))
    return lines


def measure(path, length_m=None):
    rgba = load_rgba(path)
    box, ink, what = body_box(rgba)
    x0, y0, x1, y1 = box
    width, height = x1 - x0 + 1, y1 - y0 + 1

    data = {
        "source": {
            "kind": "reference",
            "image": os.path.basename(path),
            "sha256": sha256(path),
            "pixels": [int(rgba.shape[1]), int(rgba.shape[0])],
            "background": what,
        },
        "body": {
            "box": [x0, y0, x1, y1],
            "pixels": [width, height],
            "aspect": round(width / float(height), 4),
        },
        # fractions of the body, measured from its TOP and its FRONT
        "dark_bands_vertical": dark_bands(rgba, box, ink, axis="rows"),
        "dark_bands_horizontal": dark_bands(rgba, box, ink, axis="cols"),
        "palette": palette(rgba, box, ink),
    }

    coverage, darkness = profiles(rgba, box, ink)
    data["profile_coverage"] = [round(v, 3) for v in coverage]
    data["profile_dark"] = [round(v, 3) for v in darkness]

    solid = solid_body(coverage)
    if solid:
        top, bottom = solid
        data["body"]["solid_rows"] = [int(top), int(bottom)]
        data["body"]["solid_height_px"] = int(bottom - top + 1)
        # The wheels stand on the rail, so the bottom of the box IS the rail: the
        # vehicle's height is the roofline down to there. The roofline is the first
        # row that is at least half full - which cuts the crown off a curved roof,
        # and is why this reads a few per cent under the published figure. Use the
        # drawing for PROPORTIONS; cite a source for absolute size.
        data["body"]["roofline_row"] = int(top)
        data["body"]["height_to_rail_px"] = int(height - top)

    # ONE measured length turns every pixel in the image into metres. That is the
    # whole trick, and it is why a drawing is worth more than a photograph: give it
    # the overall length from a source you can cite, and the tool hands back the
    # height, the window band and the door spacing in metres - each of them now a
    # `reference` fact resting on that one citation plus this file's sha256.
    if length_m:
        scale = length_m / float(width)
        data["scale"] = {
            "metres_per_pixel": round(scale, 6),
            "from_length_m": length_m,
            "box_height_m": round(height * scale, 3),
            "note": "box_height includes anything sticking up - a raised pantograph, "
                    "a horn. body_height is the solid part, and is the one you want",
        }
        if solid:
            data["scale"]["flank_height_m"] = round(
                data["body"]["solid_height_px"] * scale, 3)
            data["scale"]["height_to_rail_m"] = round(
                data["body"]["height_to_rail_px"] * scale, 3)
        data["dark_bands_vertical_m"] = [
            [round(a * height * scale, 3), round(b * height * scale, 3)]
            for a, b in data["dark_bands_vertical"]]
    return data


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    length = float(argv[argv.index("--length") + 1]) if "--length" in argv else None

    data = measure(path, length)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2) + "\n")

    print("\n%s  %dx%d, background: %s"
          % (data["source"]["image"], data["source"]["pixels"][0],
             data["source"]["pixels"][1], data["source"]["background"]))
    print("body %dx%d px, aspect %.2f"
          % (data["body"]["pixels"][0], data["body"]["pixels"][1],
             data["body"]["aspect"]))
    if "scale" in data:
        s = data["scale"]
        print("scale %.4f m/px from a length of %s m"
              % (s["metres_per_pixel"], s["from_length_m"]))
        print("   bounding box   %.2f m   (includes the raised pantograph)"
              % s["box_height_m"])
        if "height_to_rail_m" in s:
            print("   roof to rail   %.2f m   (the vehicle's height)"
                  % s["height_to_rail_m"])
            print("   flank          %.2f m   (the solid sides, no roof crown, no "
                  "bogies)" % s["flank_height_m"])

    print("\ntop of the body to the bottom:")
    mpp = data.get("scale", {}).get("metres_per_pixel")
    for line in chart(data["profile_coverage"], data["profile_dark"], mpp):
        print(line)

    print("\ndark bands (of the body height, from the top):")
    for i, (a, b) in enumerate(data["dark_bands_vertical"]):
        extra = ""
        if "dark_bands_vertical_m" in data:
            lo, hi = data["dark_bands_vertical_m"][i]
            extra = "   = %.2f .. %.2f m from the top" % (lo, hi)
        print("    %.1f%% .. %.1f%%%s" % (100 * a, 100 * b, extra))

    print("\npalette of the body:")
    for c in data["palette"]:
        print("    %s  %4.1f%%  %s" % (c["hex"], 100 * c["share"],
                                       c["reserved"] or ""))

    hits = [c for c in data["palette"] if c["reserved"]]
    if hits:
        print("\nWARNING: this reference lands on %d of the engine's RESERVED colours."
              % len(hits))
        print("Sample one into a livery and the game will repaint or light that area,\n"
              "and nothing will tell you why. Move the colour by one count.")
    if out:
        print("\nwrote %s" % out)
    return 0


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    sys.exit(main(args))
