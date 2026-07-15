"""Factories: a building, plus the economics that drive it.

Grounded in descriptor/writer/factory_writer.cc:

- obj=factory EMBEDS a building: factory_writer forces type=fac (line 222) and
  then calls building_writer on the same object (line 225). So one obj=factory
  block carries the ordinary building keys - dims and the BackImage list the kit
  already renders - AND the economics.
- mapcolor is MANDATORY. The writer fatals without it (line 171): every factory
  needs a colour to show on the minimap.
- A producer names its goods with outputgood[i] / outputcapacity[i] /
  outputfactor[i]; a consumer with inputgood[i] / inputsupplier[i] /
  inputcapacity[i] / inputfactor[i]. Every good is a cross-reference that must
  resolve to a real pakset good at game load. outputcapacity must be > 10, or
  makeobj errors (line 267).

location: land | water | city | river | shore | forest (default land).
"""


def output_block(products):
    """outputgood/outputcapacity/outputfactor for each (good, capacity, factor).

    capacity MUST be > 10 - factory_writer.cc:267 errors otherwise, and a factory
    that errors does not pack.
    """
    lines = []
    for i, (good, capacity, factor) in enumerate(products):
        lines.append("outputgood[%d]=%s" % (i, good))
        lines.append("outputcapacity[%d]=%d" % (i, capacity))
        lines.append("outputfactor[%d]=%d" % (i, factor))
    return "\n".join(lines)


def input_block(supplies):
    """inputgood/inputsupplier/inputcapacity/inputfactor for each
    (good, suppliers, capacity, factor)."""
    lines = []
    for i, (good, suppliers, capacity, factor) in enumerate(supplies):
        lines.append("inputgood[%d]=%s" % (i, good))
        lines.append("inputsupplier[%d]=%d" % (i, suppliers))
        lines.append("inputcapacity[%d]=%d" % (i, capacity))
        lines.append("inputfactor[%d]=%d" % (i, factor))
    return "\n".join(lines)


_FACTORY_SKELETON = """\
obj=factory
name={name}
copyright={author}

# --- identity ------------------------------------------------------------
# mapcolor is MANDATORY - the writer fatals without it (factory_writer.cc:171).
# It is the colour the factory shows on the minimap, 0..254.
mapcolor={mapcolor}
location={location}
productivity={productivity}
distributionweight={chance}

# --- footprint (this is the embedded building) ---------------------------
dims={dims}
level={level}

# --- goods ---------------------------------------------------------------
# A producer has outputs, a consumer has inputs; each good must resolve at load.
{goods}

# --- graphics (generated - do not hand-edit) -----------------------------
{images}
"""


def factory_dat(name, images, mapcolor=1, dims="1,1", level=1, location="Land",
                productivity=10, chance=1, outputs=(), inputs=(), author=""):
    """A compilable factory .dat. `images` is buildings.image_block(...).

    outputs: (good, capacity, factor) tuples - capacity must be > 10.
    inputs:  (good, suppliers, capacity, factor) tuples.
    A factory with neither compiles but does nothing useful; give it at least one.
    """
    goods = "\n".join(b for b in (output_block(outputs), input_block(inputs)) if b)
    return _FACTORY_SKELETON.format(
        name=name, author=author, mapcolor=mapcolor, location=location,
        productivity=productivity, chance=chance, dims=dims, level=level,
        goods=goods or "# no inputs or outputs yet", images=images,
    )
