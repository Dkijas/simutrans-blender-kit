"""Bundle the linter into ONE file, with the schema baked in.

    python tools/build_standalone_linter.py  ->  dist/simutrans_dat_lint.py

Why bother: the linter is the part of this kit that is useful to people who will
never open Blender, and most of the pakset world writes .dat files by hand. Asking
them to clone a repo to get a warning about a stray '#' is asking too much. One
file, standard library only, `python simutrans_dat_lint.py mypak/` - that is a
thing somebody actually tries.

The schema is generated from the engine's own writers, so the bundle carries the
engine version it was cut from and says so on every run.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from core import schema  # noqa: E402

OUT = os.path.join(ROOT, "dist", "simutrans_dat_lint.py")

HEADER = '''\
#!/usr/bin/env python
"""Simutrans .dat linter - checks a .dat against what the engine ACTUALLY reads.

    python simutrans_dat_lint.py myvehicle.dat
    python simutrans_dat_lint.py pakXXX/           (recurses)

One file. Standard library only. No Blender, no install, no dependencies.

makeobj will happily compile a .dat that the game then cannot use, and the format
has failure modes that are completely silent. This catches them:

  * END-OF-LINE COMMENTS ARE NOT COMMENTS. tabfile_t::read_line() drops a line only
    when it STARTS with '#'. So `freight=None  # a note` sets freight to the whole
    string, and the pakset loader dies with "Cannot resolve 'GOOD-None  # a note'".
    Numeric keys hide it completely, because atoi() stops at the space.

  * AN INDENTED LINE IS NOT A KEY. read_line() also drops any line starting with a
    space. Indent `power=600` to line it up prettily and the engine never sees it -
    your locomotive just quietly has no engine.

  * NO ICON, NO OBJECT. A way, wayobj, roadsign, bridge or tunnel only gets a build
    tool if its cursor skin has an icon (builder/wegbauer.cc:123 and four more like
    it). Without one it loads, appears in no list, has no button, and CANNOT BE
    BUILT BY ANYONE. makeobj does not say a word.

  * THE THIRD SEASON IMAGE IS NEVER DRAWN. obj/gebaeude.cc indexes
    effective_season[seasons-1][...], and the row for THREE images is a byte-for-byte
    copy of the row for two. Ship three and the third is thrown away. Use 2 (all-year
    + snow) or 4/5 (the real seasons).

  * UNKNOWN KEYS, with a hint. If another obj= type reads that key, it says which.

The key list is NOT hand-maintained. It is extracted from the engine's own
descriptor writers (descriptor/writer/*.cc), which is the only authority there is -
there has never been a schema document for .dat files.

Engine version: %(version)s

Public domain / Artistic License, same as Simutrans. Use it however you like.
"""

import json
import os
import re
import sys

SCHEMA = json.loads(r"""%(schema)s""")

'''

FOOTER = '''

# ------------------------------------------------------------------ command line
def dat_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for dirpath, _dirs, files in os.walk(p):
                for f in sorted(files):
                    if f.lower().endswith(".dat"):
                        yield os.path.join(dirpath, f)
        else:
            yield p


def main(argv):
    if not argv:
        print(__doc__)
        return 2

    files = list(dat_files(argv))
    if not files:
        print("no .dat files found in %s" % ", ".join(argv))
        return 2

    errors = warnings = 0
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            print("%s: cannot read: %s" % (path, e))
            errors += 1
            continue

        for f in lint(text):
            print("%s:%d: %s: %s" % (path, f.line, f.level, f.message))
            if f.level == "error":
                errors += 1
            else:
                warnings += 1

    print("\\n%d file(s), %d error(s), %d warning(s)   [engine %s]"
          % (len(files), errors, warnings, ENGINE_VERSION))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


def body_of_schema_module():
    """core/schema.py, minus its imports and its file-loading preamble."""
    with open(os.path.join(ROOT, "core", "schema.py"), encoding="utf-8") as f:
        src = f.read()

    # cut everything up to and including the SCHEMA load; the bundle supplies it
    marker = 'OBJ_TYPES = SCHEMA["obj_types"]'
    i = src.index(marker)
    return src[i + len(marker):].lstrip("\n")


def main():
    with open(os.path.join(ROOT, "core", "dat_schema.json"), encoding="utf-8") as f:
        raw = f.read()

    # the schema goes inside a raw triple-quoted string, so it must not contain one
    if '"""' in raw:
        raise SystemExit("the schema contains a triple quote; the bundler cannot "
                         "embed it as a raw string")

    text = (HEADER % {"version": schema.ENGINE_VERSION, "schema": raw}
            + 'ENGINE_VERSION = SCHEMA["engine_version"]\n'
            + 'COMMON_KEYS = SCHEMA["common_keys"]\n'
            + 'OBJ_TYPES = SCHEMA["obj_types"]\n\n'
            + body_of_schema_module()
            + FOOTER)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    print("%s  (%.0f KB, %d object types, engine %s)"
          % (OUT, os.path.getsize(OUT) / 1024.0,
             len(schema.OBJ_TYPES), schema.ENGINE_VERSION))


if __name__ == "__main__":
    main()
