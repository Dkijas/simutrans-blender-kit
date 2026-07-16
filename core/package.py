"""Everything a pakset needs from you, gathered and checked - and nothing else.

Publishing a Simutrans object is not hard, it is fiddly, and the fiddliness is
where things go wrong: the .pak goes out without its .dat, or with a `.blend1`
backup, or with somebody's `C:\\Users\\...` baked into a path, or with no licence
at all - which makes it unusable to anyone who cares, and most paksets care.

WHAT THIS DOES NOT DO
    It does not upload. It does not post. It does not touch the network. It makes
    a folder and a zip on your disk, and then you look at them.

    `plan()` is separate from `write()` for exactly that reason: you can see the
    whole package - every file, where it came from, and what is wrong with it -
    before a byte is written.

PROVENANCE IS RECORDED, NOT GUESSED
    Every file is GENERATED or AUTHORED. It matters downstream: a pakset
    maintainer reviewing a contribution needs to know which files are output (and
    can be rebuilt, and need not be read) and which are somebody's work (and carry
    a licence, and must be). Nothing else in the pipeline records it, so it is
    recorded here, at the point where it is still known.

REPRODUCIBLE MEANS BYTE-IDENTICAL
    Same inputs, same zip, every time. Zip files carry a timestamp per entry, and
    the default is "now" - so the same package built twice differs, and nobody can
    tell a rebuild from a change. Entries are written in sorted order with a fixed
    timestamp, which makes the archive a function of its contents.

    That is what makes `sha256` in the manifest worth printing.

PURE
    No bpy. `plan()` takes a directory and a manifest; the tests build a package
    from a temp folder and read it back without Blender anywhere near it.
"""

import fnmatch
import hashlib
import json
import os
import posixpath
import re
import zipfile
from typing import NamedTuple

from . import scenecheck

MANIFEST_VERSION = 1
MANIFEST_NAME = "manifest.json"

Finding = scenecheck.Finding
ERROR = scenecheck.ERROR
WARNING = scenecheck.WARNING
INFORMATION = scenecheck.INFORMATION
blocking = scenecheck.blocking

GENERATED = "generated"
AUTHORED = "authored"

# Never ship these. Editor droppings, OS droppings, build caches and Blender's
# own backup file - which is the one that actually catches people out, because
# `.blend1` sits next to the .blend, is the same size, and looks like an asset.
EXCLUDE = (
    "*.blend1", "*.blend2", "*.blend[0-9]",
    "__pycache__", "*.pyc", "*.pyo",
    ".DS_Store", "Thumbs.db", "desktop.ini",
    "*.tmp", "*.temp", "*.bak", "*~", "*.swp", "*.orig", "*.rej",
    ".git", ".gitignore", ".gitattributes", ".svn", ".hg",
    "*.log",
)

# Which extensions are OUTPUT of this kit rather than somebody's work.
_GENERATED_EXT = (".dat", ".pak")

# A path that would only work on the machine that made it. Windows drive letters,
# POSIX absolutes, UNC shares, and Blender's own '//' - which is relative to a
# .blend that the person unpacking this does not have.
_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/][\\/]|/|//)")


class File(NamedTuple):
    """One file, and where it came from."""
    arcname: str          # its path INSIDE the package, always posix
    source: str           # where it is now, on this disk
    provenance: str       # GENERATED or AUTHORED
    size: int = 0


class Manifest(NamedTuple):
    """What the package says about itself.

    Deliberately the shape a pakset maintainer would ask for, not the shape our
    panel happens to have.
    """
    name: str = ""
    author: str = ""
    version: str = ""
    license: str = ""
    pakset: str = ""
    simutrans_min_version: str = ""
    category: str = ""
    objects: tuple = ()
    dependencies: tuple = ()
    preview: str = ""
    description: str = ""

    def as_dict(self):
        return {
            "manifest_version": MANIFEST_VERSION,
            "name": self.name,
            "author": self.author,
            "version": self.version,
            "license": self.license,
            "pakset": self.pakset,
            "simutrans_min_version": self.simutrans_min_version,
            "category": self.category,
            "description": self.description,
            "objects": list(self.objects),
            "dependencies": list(self.dependencies),
            "preview": self.preview,
        }


class Package(NamedTuple):
    manifest: Manifest
    files: tuple = ()
    excluded: tuple = ()          # (arcname, why) - reported, not hidden


def excluded_by(name):
    """Which EXCLUDE pattern rejects this basename, or None."""
    for pat in EXCLUDE:
        if fnmatch.fnmatch(name, pat):
            return pat
    return None


def provenance_of(path):
    """GENERATED for our output, AUTHORED for everything else.

    Sprites are the interesting case and they are AUTHORED on purpose. A .png IS
    generated - we rendered it - but it is generated FROM somebody's modelling,
    it is what the licence actually covers, and a maintainer who is told "this is
    just output, no need to look" would be misled. The .dat and the .pak are
    machine output in the sense that matters: throw them away and one command
    brings them back identical.
    """
    return GENERATED if os.path.splitext(path)[1].lower() in _GENERATED_EXT \
        else AUTHORED


def plan(root, manifest, include=None, prefix=""):
    """Walk `root` and decide what goes in -> Package. Writes nothing.

    include: basename globs to keep (None = everything not excluded).
    prefix:  a folder to put it all under inside the archive.
    """
    files, dropped = [], []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories in place, so we do not walk into .git
        for d in list(dirnames):
            pat = excluded_by(d)
            if pat:
                dirnames.remove(d)
                rel = os.path.relpath(os.path.join(dirpath, d), root)
                dropped.append((_arc(rel, prefix) + "/", pat))
        dirnames.sort()
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            arc = _arc(rel, prefix)
            pat = excluded_by(fn)
            if pat:
                dropped.append((arc, pat))
                continue
            if include and not any(fnmatch.fnmatch(fn, p) for p in include):
                dropped.append((arc, "not in include list"))
                continue
            files.append(File(arcname=arc, source=full,
                              provenance=provenance_of(fn),
                              size=os.path.getsize(full)))
    return Package(manifest=manifest, files=tuple(files),
                   excluded=tuple(dropped))


def _arc(rel, prefix):
    arc = rel.replace(os.sep, "/")
    return posixpath.join(prefix, arc) if prefix else arc


# --- validation --------------------------------------------------------------

def check(package, required=("*.dat",)):
    """Everything wrong with this package -> (Finding, ...), errors first.

    `required`: basename globs at least one file must match. The default is the
    honest minimum - a package with no .dat is not a Simutrans object.
    """
    out = []
    out.extend(_check_manifest(package.manifest))
    out.extend(_check_files(package, required))
    return tuple(sorted(out, key=lambda f: scenecheck._ORDER[f.level]))


def _check_manifest(m):
    # The four a pakset maintainer will ask for, and their absence is the reason
    # a contribution sits unmerged.
    if not m.name.strip():
        yield Finding(ERROR, "no-name", "The package has no name")
    if not m.license.strip():
        yield Finding(ERROR, "no-license",
                      "No licence. Nobody can legally ship this, and most "
                      "paksets will not take it")
    if not m.author.strip():
        yield Finding(ERROR, "no-author", "No author")
    if not m.version.strip():
        yield Finding(WARNING, "no-version",
                      "No version. The next release cannot be told from this one")
    if not m.pakset.strip():
        yield Finding(WARNING, "no-pakset",
                      "No pakset named. Sprite size is a pakset's business - "
                      "128px art in a pak64 game is simply wrong")
    if not m.objects:
        yield Finding(WARNING, "no-objects",
                      "The manifest lists no objects")
    for dep in m.dependencies:
        if not str(dep).strip():
            yield Finding(WARNING, "empty-dependency",
                          "An empty entry in dependencies")
    if m.preview and _ABSOLUTE.match(m.preview):
        yield Finding(ERROR, "absolute-preview",
                      "The preview path %r is absolute - it only exists on this "
                      "machine" % (m.preview,))


def _check_files(package, required):
    if not package.files:
        yield Finding(ERROR, "empty-package", "There are no files in it")
        return

    names = [f.arcname for f in package.files]
    for pat in required:
        if not any(fnmatch.fnmatch(posixpath.basename(n), pat) for n in names):
            yield Finding(ERROR, "missing-required",
                          "No file matching %r. A Simutrans object without its "
                          ".dat is not one" % (pat,))

    for f in package.files:
        base = posixpath.basename(f.arcname)
        pat = excluded_by(base)
        if pat:
            # plan() drops these, so reaching here means the package was built by
            # hand. Still refuse: shipping a .blend1 is how a half-saved scene
            # ends up in somebody else's pakset.
            yield Finding(ERROR, "excluded-file",
                          "%s should not be shipped (matches %r)"
                          % (f.arcname, pat))
        if _ABSOLUTE.match(f.arcname):
            yield Finding(ERROR, "absolute-path",
                          "%s is an absolute path inside the archive"
                          % (f.arcname,))
        if ".." in f.arcname.split("/"):
            # A zip entry that escapes its own directory. Not our artist's doing,
            # but a package we hand someone must not be able to write outside the
            # folder they unpack it into.
            yield Finding(ERROR, "escaping-path",
                          "%s climbs out of the package" % (f.arcname,))
        if f.size == 0:
            yield Finding(WARNING, "empty-file", "%s is empty" % (f.arcname,))

    if not any(f.provenance == AUTHORED for f in package.files):
        yield Finding(WARNING, "nothing-authored",
                      "Every file is generated output. The sprites are what the "
                      "licence covers - check they are in")

    for arc, why in package.excluded:
        # Said out loud, always. A tool that silently drops files is a tool you
        # cannot trust with the one file that mattered.
        yield Finding(INFORMATION, "excluded", "left out: %s (%s)" % (arc, why))

    yield Finding(INFORMATION, "contents",
                  "%d file(s): %d authored, %d generated"
                  % (len(package.files),
                     sum(1 for f in package.files if f.provenance == AUTHORED),
                     sum(1 for f in package.files if f.provenance == GENERATED)))


# --- writing -----------------------------------------------------------------

# The zip epoch. Every entry gets this, so the archive is a function of its
# contents and not of the clock.
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def manifest_json(package):
    """The manifest, with the file list and their hashes, as text."""
    d = package.manifest.as_dict()
    d["files"] = [
        {"path": f.arcname, "provenance": f.provenance,
         "sha256": sha256_of(f.source), "size": f.size}
        for f in sorted(package.files, key=lambda f: f.arcname)
    ]
    return json.dumps(d, indent=2, sort_keys=False) + "\n"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write(package, dest, prefix=""):
    """Build the zip -> its path. Refuses if check() found an error.

    Refusing is the point. A package that is missing its licence is not a package
    you want to discover is missing its licence after you have sent it.
    """
    errors = blocking(check(package))
    if errors:
        raise ValueError("the package has %d error(s): %s"
                         % (len(errors), "; ".join(f.message for f in errors)))

    man = manifest_json(package)
    entries = [(f.arcname, f.source) for f in package.files]
    entries.sort()

    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        _writestr(z, posixpath.join(prefix, MANIFEST_NAME) if prefix
                  else MANIFEST_NAME, man)
        for arc, src in entries:
            with open(src, "rb") as fh:
                _writestr(z, arc, fh.read())
    return dest


def _writestr(z, arc, data):
    """One entry, with a fixed timestamp so the archive is reproducible."""
    info = zipfile.ZipInfo(arc, date_time=_FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    z.writestr(info, data)


def contents(path):
    """Read a built package back -> (names, manifest dict). For the tests, and
    for anyone who wants to know what they actually sent."""
    with zipfile.ZipFile(path) as z:
        names = sorted(z.namelist())
        man = None
        for n in names:
            if posixpath.basename(n) == MANIFEST_NAME:
                man = json.loads(z.read(n).decode("utf-8"))
                break
    return names, man
