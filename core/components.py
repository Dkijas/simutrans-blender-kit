"""A bogie you modelled once, in the next four vehicles.

The catalogue, the metadata and the rules - all of it pure. The Blender half
(actually pulling a collection out of a .blend) is addon/components.py.

WHAT A COMPONENT IS
    A named collection inside a .blend, plus a sidecar `component.json` that says
    what it is, who made it and under what licence. That is all. It is not a new
    file format and it is not a database: a component IS a Blender collection, so
    an artist makes one by modelling a bogie and writing six lines of JSON.

WHY THE LICENCE IS NOT OPTIONAL
    A component library is a thing that copies other people's work into other
    people's projects. That is the entire point of it, and it is exactly why an
    unlicensed component is refused rather than warned about: the moment it is
    inserted, it is in somebody's pakset, and the question "may we ship this?"
    has no answer and no owner. The kit will not be the reason that happens.

    We ship no third-party art. The example components are modelled by this
    project's tests, in code, and carry the repo's own licence.

PATHS ARE RELATIVE, ALWAYS
    A component's .blend is named relative to its own component.json. An absolute
    path is refused, not normalised: it means the catalogue only works on the
    machine that wrote it, and the failure - a component that silently vanishes on
    a colleague's checkout - looks like a bug in the tool rather than in the data.

ANCHOR
    Where the component's origin should sit when it lands. Its whole value is that
    a bogie arrives under the axle rather than at the world origin - so it is part
    of the metadata, not something the artist re-derives per project.
"""

import json
import os
import re
from typing import NamedTuple

from . import scenecheck

SCHEMA_VERSION = 1
SIDECAR = "component.json"

Finding = scenecheck.Finding
ERROR = scenecheck.ERROR
WARNING = scenecheck.WARNING
INFORMATION = scenecheck.INFORMATION
blocking = scenecheck.blocking

# How a component arrives in the scene. Blender can do all three; they are not
# interchangeable and the difference bites later, so the artist picks.
#
#   LINK      the .blend stays the master. Edit it once, every user updates.
#             But the file must still be there at render time - and it will not
#             be, for whoever you send the project to.
#   APPEND    a real copy. Yours forever, diverges forever, renders anywhere.
#   INSTANCE  one mesh, many empties pointing at it. Cheap for eight bogies.
LINK = "link"
APPEND = "append"
INSTANCE = "instance"
MODES = (APPEND, LINK, INSTANCE)

CATEGORIES = ("bogie", "wheel", "pantograph", "coupler", "headlight", "window",
              "door", "sign", "post", "way", "building", "other")

_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/][\\/]|/|//)")
_KEY_OK = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")


class Component(NamedTuple):
    """One reusable part.

    key         stable id, unique in its catalogue. Lowercase, no spaces.
    blend       path to the .blend, RELATIVE to this component.json.
    collection  the collection inside that .blend to bring over.
    anchor      where its origin lands, in tile-relative units (x, y, z).
    pakset      "" = any. Otherwise the pakset it was modelled for.
    source      the directory its component.json was read from. Not serialised.
    """
    key: str
    name: str = ""
    category: str = "other"
    author: str = ""
    license: str = ""
    version: str = "1.0.0"
    blend: str = ""
    collection: str = ""
    anchor: tuple = (0.0, 0.0, 0.0)
    pakset: str = ""
    note: str = ""
    source: str = ""

    def as_dict(self):
        return {
            "schema_version": SCHEMA_VERSION,
            "key": self.key, "name": self.name, "category": self.category,
            "author": self.author, "license": self.license,
            "version": self.version, "blend": self.blend,
            "collection": self.collection, "anchor": list(self.anchor),
            "pakset": self.pakset, "note": self.note,
        }

    def blend_path(self):
        """The .blend's real location -> path, or None if it has no source."""
        if not self.source or not self.blend:
            return None
        return os.path.normpath(os.path.join(self.source, self.blend))


def parse(raw, source=""):
    """One sidecar dict -> Component. Never raises; check() judges it."""
    if not isinstance(raw, dict):
        return None
    anchor = raw.get("anchor") or (0.0, 0.0, 0.0)
    try:
        anchor = tuple(float(v) for v in anchor)[:3]
    except (TypeError, ValueError):
        anchor = (0.0, 0.0, 0.0)
    if len(anchor) != 3:
        anchor = (0.0, 0.0, 0.0)
    return Component(
        key=str(raw.get("key", "")),
        name=str(raw.get("name", "")),
        category=str(raw.get("category", "other")),
        author=str(raw.get("author", "")),
        license=str(raw.get("license", "")),
        version=str(raw.get("version", "")),
        blend=str(raw.get("blend", "")),
        collection=str(raw.get("collection", "")),
        anchor=anchor,
        pakset=str(raw.get("pakset", "")),
        note=str(raw.get("note", "")),
        source=source,
    )


def load_dir(path):
    """Read one component directory -> Component, or None if it has no sidecar."""
    sidecar = os.path.join(path, SIDECAR)
    if not os.path.isfile(sidecar):
        return None
    try:
        with open(sidecar, encoding="utf-8") as f:
            raw = json.load(f)
    except (ValueError, OSError):
        return None
    return parse(raw, source=path)


def catalogue(*roots):
    """Every component under these roots -> (Component, ...), key order.

    Roots are searched in order and the FIRST key wins, so a project's own
    component shadows a shared one of the same key. That is the useful direction:
    a local override should not need permission from the library it overrides.
    """
    out, seen = [], set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not os.path.isdir(path):
                continue
            comp = load_dir(path)
            if comp is None or comp.key in seen:
                continue
            seen.add(comp.key)
            out.append(comp)
    return tuple(sorted(out, key=lambda c: c.key))


def by_category(comps):
    out = {}
    for c in comps:
        out.setdefault(c.category, []).append(c)
    return {k: tuple(v) for k, v in sorted(out.items())}


def check(comp, pakset=None):
    """Everything wrong with this component -> (Finding, ...), errors first."""
    return tuple(sorted(_check(comp, pakset),
                        key=lambda f: scenecheck._ORDER[f.level]))


def _check(comp, pakset):
    if not comp.key or not _KEY_OK.match(comp.key):
        yield Finding(ERROR, "bad-key",
                      "%r is not a usable component key. Lowercase letters, "
                      "digits, _ and - only" % (comp.key,))
    if not comp.name.strip():
        yield Finding(WARNING, "no-name",
                      "Component %r has no readable name" % (comp.key,))
    if comp.category not in CATEGORIES:
        yield Finding(WARNING, "unknown-category",
                      "%r is not one of the known categories - it will still "
                      "work, it just will not group" % (comp.category,))

    # The one that is an ERROR, and the module docstring says why: inserting an
    # unlicensed component puts it in somebody's pakset with no answer to "may we
    # ship this?".
    if not comp.license.strip():
        yield Finding(ERROR, "no-license",
                      "Component %r has no licence. It would be copied into "
                      "somebody's project with no answer to whether they may "
                      "ship it" % (comp.key,))
    if not comp.author.strip():
        yield Finding(ERROR, "no-author",
                      "Component %r has no author. A licence with nobody behind "
                      "it grants nothing" % (comp.key,))
    if not comp.version.strip():
        yield Finding(WARNING, "no-version",
                      "Component %r has no version" % (comp.key,))

    if not comp.blend.strip():
        yield Finding(ERROR, "no-blend",
                      "Component %r names no .blend" % (comp.key,))
    elif _ABSOLUTE.match(comp.blend):
        yield Finding(ERROR, "absolute-path",
                      "Component %r points at %r, which only exists on the "
                      "machine that wrote it" % (comp.key, comp.blend))
    elif ".." in comp.blend.replace("\\", "/").split("/"):
        yield Finding(WARNING, "climbing-path",
                      "Component %r reaches outside its own folder (%r), which "
                      "will not survive being copied elsewhere"
                      % (comp.key, comp.blend))
    else:
        path = comp.blend_path()
        if path and comp.source and not os.path.isfile(path):
            yield Finding(ERROR, "missing-blend",
                          "Component %r names %s, which is not there"
                          % (comp.key, comp.blend))

    if not comp.collection.strip():
        yield Finding(ERROR, "no-collection",
                      "Component %r does not say which collection to bring over"
                      % (comp.key,))

    if pakset and comp.pakset and comp.pakset != pakset:
        # A warning, not an error. tile_world is 2.0 in every shipped profile, so
        # a pak64 bogie is the right SIZE in pak128 - what differs is how many
        # pixels it lands on, and whether that much detail survives. That is a
        # judgement about the art, so the artist makes it.
        yield Finding(WARNING, "other-pakset",
                      "Component %r was modelled for %s and you are building "
                      "%s. It will be the right size - a tile is 2.0 units "
                      "everywhere - but the detail was drawn for a different "
                      "pixel count" % (comp.key, comp.pakset, pakset))


def check_catalogue(comps, pakset=None):
    """The whole catalogue, plus what only shows up between components."""
    out = []
    seen = {}
    for c in comps:
        out.extend(check(c, pakset))
        if c.key in seen:
            out.append(Finding(ERROR, "duplicate-key",
                               "Two components share the key %r" % (c.key,)))
        seen[c.key] = c
    return tuple(sorted(out, key=lambda f: scenecheck._ORDER[f.level]))


def usable(comps, pakset=None):
    """Only the ones that would insert cleanly. What the panel offers."""
    return tuple(c for c in comps if not blocking(check(c, pakset)))
