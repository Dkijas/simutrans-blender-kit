"""The publication package, without Blender.

    python tests/test_package.py

The package is the last thing that happens before somebody else has your work, so
the tests are about what must NOT be in it as much as what must: a .blend1 backup,
a __pycache__, an absolute path, a zip entry that climbs out of its own folder.

Reproducibility is checked by building the same package twice and comparing the
bytes. A zip stamps every entry with the clock by default, so the naive version of
this module produces a different archive every run - and then nobody can tell a
rebuild from a change, and the sha256 in the manifest means nothing.
"""

import os
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import package as P                                   # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def codes(findings):
    return [f.code for f in findings]


GOOD = dict(name="MyLoco", author="victor_18993", version="1.0.0",
            license="CC BY 4.0", pakset="pak128", objects=("Loco",))


def _project(**extra):
    """A believable project on disk. The caller cleans it up."""
    d = tempfile.mkdtemp(prefix="bkitpkg")
    open(os.path.join(d, "loco.dat"), "w").write("obj=vehicle\nname=Loco\n")
    open(os.path.join(d, "loco.png"), "wb").write(b"\x89PNG" + b"\0" * 40)
    open(os.path.join(d, "LICENSE.md"), "w").write("CC BY 4.0\n")
    open(os.path.join(d, "README.md"), "w").write("# My Loco\n")
    for rel, content in extra.items():
        full = os.path.join(d, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w").write(content)
    return d


# --- what goes in ------------------------------------------------------------

def test_a_plain_project_is_gathered():
    d = _project()
    try:
        pkg = P.plan(d, P.Manifest(**GOOD))
        names = sorted(f.arcname for f in pkg.files)
        check("everything real is in",
              names == ["LICENSE.md", "README.md", "loco.dat", "loco.png"],
              str(names))
        check("a good package has no error", P.blocking(P.check(pkg)) == (),
              str(codes(P.check(pkg))))
    finally:
        shutil.rmtree(d)


def test_the_droppings_are_left_out_and_said_out_loud():
    """The .blend1 is the one that catches people: it sits next to the .blend, it
    is the same size, and it looks like an asset."""
    d = _project(**{"loco.blend1": "BACKUP", "notes.txt~": "junk",
                    "build.log": "spam", "__pycache__/x.pyc": "junk",
                    ".git/config": "[core]"})
    try:
        pkg = P.plan(d, P.Manifest(**GOOD))
        names = [f.arcname for f in pkg.files]
        for bad in ("loco.blend1", "notes.txt~", "build.log"):
            check("%s is left out" % bad, bad not in names)
        check("__pycache__ is not walked into",
              not any("__pycache__" in n for n in names))
        check(".git is not walked into", not any(".git" in n for n in names))
        check("the real files are still there",
              "loco.dat" in names and "loco.png" in names)

        dropped = [a for a, _w in pkg.excluded]
        check("and every exclusion is reported, not silent",
              any("blend1" in a for a in dropped) and any(".git" in a for a in dropped),
              str(dropped))
        check("check() lists them as INFORMATION",
              "excluded" in codes(P.check(pkg)))
    finally:
        shutil.rmtree(d)


def test_provenance_is_recorded():
    d = _project()
    try:
        pkg = P.plan(d, P.Manifest(**GOOD))
        prov = {f.arcname: f.provenance for f in pkg.files}
        check("the .dat is generated", prov["loco.dat"] == P.GENERATED)
        check("the sprite is AUTHORED - it is what the licence covers",
              prov["loco.png"] == P.AUTHORED)
        check("so is the licence", prov["LICENSE.md"] == P.AUTHORED)
    finally:
        shutil.rmtree(d)


def test_include_filters_and_says_what_it_dropped():
    d = _project()
    try:
        pkg = P.plan(d, P.Manifest(**GOOD), include=("*.dat", "*.png"))
        names = sorted(f.arcname for f in pkg.files)
        check("only what was asked for", names == ["loco.dat", "loco.png"], str(names))
        check("and the rest is reported",
              any("README.md" in a for a, _w in pkg.excluded))
    finally:
        shutil.rmtree(d)


def test_a_prefix_puts_it_in_a_folder():
    d = _project()
    try:
        pkg = P.plan(d, P.Manifest(**GOOD), prefix="myloco")
        check("every entry is under the prefix",
              all(f.arcname.startswith("myloco/") for f in pkg.files))
        check("with posix separators, on every OS",
              all("\\" not in f.arcname for f in pkg.files))
    finally:
        shutil.rmtree(d)


# --- what is refused ---------------------------------------------------------

def test_a_package_with_no_licence_is_refused():
    d = _project()
    try:
        m = dict(GOOD); m["license"] = ""
        f = P.check(P.plan(d, P.Manifest(**m)))
        check("no licence is an error", "no-license" in codes(f))
        check("and it blocks", "no-license" in codes(P.blocking(f)))
        check("with a licence it does not",
              "no-license" not in codes(P.check(P.plan(d, P.Manifest(**GOOD)))))
    finally:
        shutil.rmtree(d)


def test_the_four_a_maintainer_will_ask_for():
    d = _project()
    try:
        for field, code, blocks in (("name", "no-name", True),
                                    ("author", "no-author", True),
                                    ("license", "no-license", True),
                                    ("version", "no-version", False),
                                    ("pakset", "no-pakset", False)):
            m = dict(GOOD); m[field] = ""
            f = P.check(P.plan(d, P.Manifest(**m)))
            check("a missing %s is reported" % field, code in codes(f))
            check("a missing %s %s block" % (field, "does" if blocks else "does NOT"),
                  (code in codes(P.blocking(f))) == blocks)
    finally:
        shutil.rmtree(d)


def test_a_package_with_no_dat_is_not_a_simutrans_object():
    d = tempfile.mkdtemp(prefix="bkitpkg")
    try:
        open(os.path.join(d, "readme.md"), "w").write("hi")
        f = P.check(P.plan(d, P.Manifest(**GOOD)))
        check("no .dat is an error", "missing-required" in codes(f))
        check("and it blocks", "missing-required" in codes(P.blocking(f)))
    finally:
        shutil.rmtree(d)


def test_an_empty_package_is_refused():
    d = tempfile.mkdtemp(prefix="bkitpkg")
    try:
        f = P.check(P.plan(d, P.Manifest(**GOOD)))
        check("nothing at all is an error", "empty-package" in codes(f))
    finally:
        shutil.rmtree(d)


def test_absolute_and_escaping_paths_are_refused():
    """plan() cannot produce these; a hand-built Package can. A package we hand
    someone must not be able to write outside the folder they unpack it into."""
    m = P.Manifest(**GOOD)
    for arc in ("/etc/passwd", "C:/Windows/x.dat", "//server/share/x.dat"):
        pkg = P.Package(manifest=m,
                        files=(P.File(arc, "x", P.AUTHORED, 1),
                               P.File("loco.dat", "x", P.GENERATED, 1)))
        check("%r is refused" % arc, "absolute-path" in codes(P.check(pkg)))
    pkg = P.Package(manifest=m,
                    files=(P.File("../../secrets.dat", "x", P.GENERATED, 1),))
    check("a path that climbs out is refused", "escaping-path" in codes(P.check(pkg)))
    check("a normal path is not",
          "absolute-path" not in codes(P.check(P.Package(
              manifest=m, files=(P.File("loco.dat", "x", P.GENERATED, 1),)))))


def test_an_absolute_preview_is_refused():
    m = dict(GOOD); m["preview"] = "C:/Users/somebody/shot.png"
    check("an absolute preview path is an error",
          "absolute-preview" in codes(P.check(P.Package(
              manifest=P.Manifest(**m),
              files=(P.File("loco.dat", "x", P.GENERATED, 1),)))))


def test_a_hand_built_package_carrying_a_dropping_is_refused():
    m = P.Manifest(**GOOD)
    pkg = P.Package(manifest=m, files=(P.File("loco.dat", "x", P.GENERATED, 1),
                                       P.File("loco.blend1", "x", P.AUTHORED, 1)))
    check("a .blend1 in a hand-built package is an error",
          "excluded-file" in codes(P.check(pkg)))


def test_a_package_of_pure_output_is_a_warning():
    m = P.Manifest(**GOOD)
    pkg = P.Package(manifest=m, files=(P.File("loco.dat", "x", P.GENERATED, 1),
                                       P.File("loco.pak", "x", P.GENERATED, 1)))
    f = P.check(pkg)
    check("all-generated is reported", "nothing-authored" in codes(f))
    check("but not refused - it may be exactly what was wanted",
          "nothing-authored" not in codes(P.blocking(f)))


# --- writing -----------------------------------------------------------------

def test_the_package_is_byte_reproducible():
    """A zip stamps each entry with the clock. Same inputs must give the same
    archive, or the sha256 in the manifest is decoration.

    The two-build comparison below is the CLAIM, and on its own it is nearly
    useless: two builds a millisecond apart get the same wall-clock second, so it
    passes even with the clock stamped into every entry. That was not a guess -
    the module was broken on purpose to use time.localtime() and this test stayed
    green, reporting reproducibility while the archive carried today's date.

    So the timestamp itself is checked. That is the mechanism the claim rests on,
    and it fails the moment anyone reaches for the clock - which is the only
    version of this test worth having, because the failure it guards against
    (a package rebuilt next week differing from this one) cannot be reproduced
    inside a test run at all.
    """
    d = _project()
    try:
        pkg = P.plan(d, P.Manifest(**GOOD))
        a = os.path.join(d, "a.zip")
        b = os.path.join(d, "b.zip")
        P.write(pkg, a)
        P.write(pkg, b)
        check("two builds of one package are byte-identical",
              P.sha256_of(a) == P.sha256_of(b))

        import zipfile
        with zipfile.ZipFile(a) as z:
            stamps = {i.filename: i.date_time for i in z.infolist()}
        check("every entry carries a fixed timestamp, not the clock",
              set(stamps.values()) == {P._FIXED_TIME},
              str(sorted(set(stamps.values()))))
        check("including the manifest", stamps[P.MANIFEST_NAME] == P._FIXED_TIME)

        # entry ORDER is the other half: a dict iteration or a filesystem walk
        # that reordered would give a different archive from the same files.
        with zipfile.ZipFile(a) as z:
            names = z.namelist()
        check("entries are written in sorted order",
              names[1:] == sorted(names[1:]), str(names))
    finally:
        shutil.rmtree(d)


def test_the_archive_does_not_depend_on_where_the_project_sits():
    """Same files, different temp directory - the package must not notice. A
    source path leaking into the archive is how a build becomes unrepeatable on
    anyone else's machine."""
    a_dir = _project()
    b_dir = _project()
    try:
        pa = os.path.join(a_dir, "p.zip")
        pb = os.path.join(b_dir, "p.zip")
        P.write(P.plan(a_dir, P.Manifest(**GOOD)), pa)
        P.write(P.plan(b_dir, P.Manifest(**GOOD)), pb)
        check("two projects with identical contents give identical archives",
              P.sha256_of(pa) == P.sha256_of(pb))
    finally:
        shutil.rmtree(a_dir)
        shutil.rmtree(b_dir)


def test_write_refuses_a_package_that_would_not_pass():
    d = _project()
    try:
        m = dict(GOOD); m["license"] = ""
        pkg = P.plan(d, P.Manifest(**m))
        try:
            P.write(pkg, os.path.join(d, "x.zip"))
            ok = False
        except ValueError as e:
            ok = "licence" in str(e) or "license" in str(e)
        check("writing an unlicensed package raises", ok)
        check("and no file was made", not os.path.exists(os.path.join(d, "x.zip")))
    finally:
        shutil.rmtree(d)


def test_the_manifest_lists_every_file_with_its_hash():
    d = _project()
    try:
        pkg = P.plan(d, P.Manifest(**GOOD))
        out = P.write(pkg, os.path.join(d, "p.zip"))
        names, man = P.contents(out)
        check("the manifest is in the archive", P.MANIFEST_NAME in names)
        check("it is versioned", man["manifest_version"] == P.MANIFEST_VERSION)
        check("it lists every file", len(man["files"]) == len(pkg.files))
        check("each with a sha256",
              all(len(f["sha256"]) == 64 for f in man["files"]))
        check("each with its provenance",
              {f["path"]: f["provenance"] for f in man["files"]}["loco.dat"]
              == P.GENERATED)
        check("the archive holds what the manifest promises",
              sorted(f["path"] for f in man["files"])
              == sorted(n for n in names if n != P.MANIFEST_NAME))
    finally:
        shutil.rmtree(d)


def test_the_manifest_carries_what_a_maintainer_needs():
    d = _project()
    try:
        m = dict(GOOD); m["dependencies"] = ("pak128.something",)
        pkg = P.plan(d, P.Manifest(**m))
        _names, man = P.contents(P.write(pkg, os.path.join(d, "p.zip")))
        for field in ("name", "author", "version", "license", "pakset",
                      "objects", "dependencies"):
            check("the manifest carries %r" % field, field in man)
        check("dependencies survive", man["dependencies"] == ["pak128.something"])
    finally:
        shutil.rmtree(d)


def test_nothing_is_written_by_planning():
    """plan() is separate from write() so the artist can look first."""
    d = _project()
    try:
        before = sorted(os.listdir(d))
        P.plan(d, P.Manifest(**GOOD))
        check("planning a package writes nothing", sorted(os.listdir(d)) == before)
    finally:
        shutil.rmtree(d)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("PACKAGE_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("PACKAGE_TESTS_OK")


if __name__ == "__main__":
    main()
