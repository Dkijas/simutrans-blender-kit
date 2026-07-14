"""Package the kit as an installable Blender add-on.

    python tools/build_addon_zip.py

The zip's top-level folder becomes the Python module name Blender imports, so it
must be a valid identifier - which is why it is `simutrans_blender_kit` and not
the repo's own (hyphenated) folder name.
"""

import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = "simutrans_blender_kit"
OUT = os.path.join(ROOT, "build", "%s.zip" % MODULE)

# What Blender needs. Tests and examples are for us, not for the artist.
INCLUDE = ["__init__.py", "README.md", "addon", "core"]
SKIP_DIRS = {"__pycache__"}

# WHAT MAY NOT LEAVE THE HOUSE.
#
# INCLUDE packs `core` wholesale, so anything dropped in there ships to every artist
# who installs the add-on - which is right for the geometry, and wrong for the notes
# we keep on how WE work. tools/spec.py refuses a number whose source is a language
# model, and it does so by naming them; that list is ours, and it stays here.
#
# This is a build-time refusal and not a code review, because a code review is a
# person remembering, and a person will not remember in six months. Put such a file
# under core/ and the zip does not get written at all.
_NO_TRACE = ("chatgpt", "gpt", "llm", "claude", "copilot", "gemini", "midjourney",
             "dall-e", "stable diffusion", "openai", "anthropic", "prompt",
             "language model", "image model")
_TRACE = re.compile(r"\b(%s)\b" % "|".join(re.escape(w) for w in _NO_TRACE), re.I)


def frisk(full, rel):
    """Read a file on its way into the zip. Raise rather than ship a trace."""
    if not rel.endswith((".py", ".md", ".txt", ".json")):
        return
    with open(full, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            hit = _TRACE.search(line)
            if hit:
                raise SystemExit(
                    "REFUSING TO BUILD: %s:%d says %r, and this file ships to every\n"
                    "artist who installs the add-on:\n\n    %s\n\n"
                    "Either keep the file out of INCLUDE (tools/ is our side of the\n"
                    "line - see tools/spec.py) or reword the line."
                    % (rel, n, hit.group(0), line.strip()))


def files():
    for entry in INCLUDE:
        path = os.path.join(ROOT, entry)
        if os.path.isfile(path):
            yield path, entry
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".pyc"):
                    continue
                full = os.path.join(dirpath, fn)
                yield full, os.path.relpath(full, ROOT).replace("\\", "/")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    n = 0
    packed = list(files())
    for full, rel in packed:            # every one of them, BEFORE anything is written
        frisk(full, rel)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in packed:
            z.write(full, "%s/%s" % (MODULE, rel))
            n += 1
    print("%s  (%d files, %d bytes)" % (OUT, n, os.path.getsize(OUT)))
    return OUT


if __name__ == "__main__":
    main()
    sys.exit(0)
