"""Translations for the panel.

This is plain data - no bpy - so the completeness test can run without Blender.

We use Blender's OWN translation machinery (bpy.app.translations), not a
home-made one. That means the panel follows the language the user already picked
in Preferences > Interface > Translation; there is no separate setting to find,
and a user running Blender in Spanish gets a Spanish panel for free.

TO ADD A LANGUAGE
    Copy the "es" block, change the key to Blender's locale code (de_DE, fr_FR,
    ja_JP, pl_PL, ...), and translate the values. tests/test_core.py fails if a
    language is missing a string or invents one that the UI never uses, so a
    half-finished translation cannot slip through unnoticed.

WHAT IS DELIBERATELY NOT TRANSLATED
    The waytype and engine_type values (track, road, diesel, ...). They are not
    prose: they are the literal keywords written into the .dat and read by
    makeobj. Translating them would produce a file the game cannot load.

WHY WE USE OUR OWN MESSAGE CONTEXT
    Blender's message catalogue is keyed by (context, string), and it already
    translates plenty of ordinary words. Register "Engine" in the default context
    and Blender happily shows you "Motor de procesamiento" - its RENDER engine -
    where you meant the locomotive's. Worse, operator button labels are not
    looked up in the default context at all but in "Operator", so bl_label
    translations in the default context are silently ignored and the buttons stay
    English while everything around them turns Spanish.

    Both problems vanish if we stop sharing a namespace with Blender: every
    string of ours lives in the CONTEXT below, and every place that shows one
    says so (bl_translation_context on the classes, translation_context on the
    properties, text_ctxt on the labels, and _() for the strings we format
    ourselves).
"""

# Our own corner of Blender's message catalogue.
CONTEXT = "SimutransKit"

# Every English string the UI shows. The test checks this list against what the
# code actually uses, so it cannot drift.
SOURCE_STRINGS = (
    # panels
    "Rig",
    "Output",
    "Object (.dat)",
    "%d px, ortho_scale %.4f",
    "Save the .blend, or use an",
    "absolute Output path",
    # operators
    "Build Rig",
    "Create the Simutrans camera and sun and set the render options this pakset needs",
    "Render Sheet",
    "Render every heading, assemble the sprite sheet, write the .dat",
    "Check Colours",
    "Scan the sheet for Simutrans' reserved colours - the ones the engine repaints "
    "in the company colour",
    "Night Preview",
    "Show the sheet as the game will draw it after dark - the engine's own "
    "day-to-night colour swap, not a filter",
    "Night",
    "How dark. The game's clock runs 0 (noon) to 4 (deep night) - "
    "display/simview.cc hours2night[]",
    "%s - %d px will light up",
    "%s - but NOTHING lights up: no pixel carries one of the engine's light "
    "colours, so this runs dark all night",
    # properties
    "Pakset",
    "tile is %d px",
    "Dirs",
    "8 (asymmetric)",
    "every heading rendered",
    "4 (symmetric)",
    "the engine reuses each for its opposite",
    "Where the sheet and the .dat go. '//' is relative to the .blend, so save the "
    ".blend first or give an absolute path",
    "Sheet",
    "Name",
    "Author",
    "Waytype",
    "Engine",
    "Speed (km/h)",
    "Power (kW)",
    "0 makes it an unpowered wagon or trailer",
    "Weight (t)",
    "Length",
    "in 1/16 of a tile; 8 is half a tile",
    "Payload",
    "Freight",
    "Cargo variants",
    "Comma-separated goods for a wagon that looks different loaded (e.g. 'Kohle, "
    "Oel'). Put each load in a collection freight_0, freight_1, ... in the same "
    "order. Leave EMPTY for a wagon that looks the same whatever it carries",
    "Cost (cents)",
    "Running cost",
    "Intro year",
    "In front",
    "Comma-separated vehicle names that may go IN FRONT of this one. Use 'none' to "
    "allow it at the head of the train. Leave EMPTY to couple behind anything - an "
    "empty field is not the same as 'none'",
    "Behind",
    "Comma-separated vehicle names that may go BEHIND this one. Use 'none' to allow "
    "it at the tail. Leave EMPTY to couple to anything",
    "Align offset",
    "Nudge the vehicle inside its cell. Leave at zero unless it does not ride the "
    "centre of the way",
    "Write .dat",
    # compile
    "Compile",
    "Compile .pak",
    "Run makeobj on the .dat and produce a .pak the game can load",
    "makeobj",
    "Path to the makeobj executable. It is not shipped with Blender: build it from "
    "the Simutrans source with 'cmake --build <dir> --target makeobj'",
    "Install to",
    "Optional. Copy the compiled .pak here - normally a pakset's addons folder, so "
    "the game picks it up",
    "Set the path to makeobj first",
    "makeobj not found: %s",
    "No .dat yet - render the sheet first",
    "makeobj failed: %s",
    "Compiled %s (%d bytes)",
    "Could not install the .pak: %s",
    "Compiled %s and installed it to %s",
    # messages
    "%s rig: %d px, ortho_scale %.4f",
    "Set an Output directory",
    "Save your .blend first, or set an absolute Output path ('//' means 'next to "
    "the .blend', and there isn't one yet)",
    "Nothing to render - the scene has no mesh",
    "You listed %d cargo variant(s) but there are %d freight_ collection(s). "
    "Make one collection freight_0..freight_%d, one per good, in order",
    "Rendered %d frames to %s",
    "Rendering %d headings - Esc to cancel",
    "Rendering heading %d/%d - Esc to cancel",
    "Render cancelled at heading %d/%d",
    "No sheet yet - render one first",
    "No reserved colours - nothing will be recoloured",
    # This used to end with "- see the console", and that WAS the bug: the artist
    # has no console open. Every finding is reported into the panel itself now.
    ".dat: %d error(s), %d warning(s)",
    ".dat line %d: %s",
    "%s + %s, with %d warning(s) above",
    # Write .dat: rebuild the .dat from the last render, no re-rendering
    "Rewrite the .dat from the last render, with the current numbers - no "
    "re-rendering. Change power, cost, couplings and press this instead of "
    "rendering every heading again",
    "No render to build from - press Render Sheet first",
    "The last render of %r was a %s, not a %s",
    "Wrote %s (no re-render)",
    # --- materials: the reserved colours the kit exists to make reachable
    "Materials",
    "Material",
    "Paint",
    "Apply to selected",
    "Give the selected objects a Simutrans material - a player colour, a night "
    "light, or plain paint",
    "Select a mesh object first",
    "%s -> %d object(s)",
    "The colour for Plain paint. The reserved materials above ignore it - their "
    "colour is fixed by the engine",
    "Player colour",
    "Window (warm)",
    "Window (blue)",
    "Headlight",
    "Red lamp",
    "Green lamp",
    "Yellow lamp",
    "Signal (purple)",
    "Plain paint",
    # --- what kind of object
    "Object",
    "Vehicle",
    "Building",
    "Way",
    "Catenary",
    "Sign / Signal",
    "Tunnel",
    "Bridge",
    "Factory",
    "a train, a bus, a ship - 4 or 8 headings",
    "a house, a factory - turned to face its street",
    "a road, a rail - six models, sixteen images",
    "overhead line and the like, in two layers",
    "four directions, one aspect each",
    "a portal, four directions, two layers",
    "span, ramps, pillars - in two layers",
    "a building that makes or consumes goods",
    "Map colour",
    "The colour the factory shows on the minimap (0-254). The engine refuses a "
    "factory without one",
    "Productivity",
    "How much the factory makes per step",
    "Location",
    "Where the industry generator may place it",
    "Makes",
    "The good this factory PRODUCES (e.g. 'Kohle'). Must be a real pakset good. "
    "Empty for a pure consumer",
    "Output store",
    "Storage for the produced good. Must be more than 10",
    "Consumes",
    "A good this factory CONSUMES (e.g. 'Eisenerz'). Must be a real pakset good. "
    "Empty for a pure producer",
    "Max length",
    "Longest span the bridge may cross, in tiles. 0 = unlimited",
    "Max height",
    "How high above the ground the bridge may be built",
    "Pillar every",
    "Place a pillar every N tiles. 0 = no pillars",
    # --- building
    "Tiles east",
    "Tiles south",
    "Accepts passengers",
    "Accepts mail",
    "Accepts goods",
    "Layouts",
    "How many ways round it can be built. 0 lets the engine decide: 1 for a square "
    "footprint, 2 otherwise",
    "Kind",
    "Level",
    "drives demand, and the default capacity (level x 32)",
    "Chance",
    "how often a city picks this house; 0 = never",
    "Seasons",
    "1, 2, 4 or 5 - never 3, the engine NEVER draws the third image. Put each "
    "season's extras in a collection 'season_1', 'season_2', ...",
    "Phases",
    "animation frames. Put each frame's extras in a collection 'phase_1', "
    "'phase_2', ...",
    # --- way / wayobj
    "Top speed",
    "Maintenance",
    "Grants",
    "what the wayobj gives the way underneath. Catenary is electrified_track - that "
    "is what lets an electric loco run",
    # --- roadsign
    "Block signal",
    "a signal rather than a sign. It then needs two aspects, and STATE 0 IS RED",
    "Aspects",
    "1 for a plain sign, 2 for a signal. State 0 is RED. Put each aspect's extras in "
    "a collection 'state_0', 'state_1', ...",
    # --- the model hints, drawn in the panel, one short line each
    "Model: nose along +X,",
    "on z=0, at the origin",
    "Model: facade toward -Y",
    "(Blender's Front view),",
    "growing east (+X) and south (-Y)",
    "Six collections:",
    "way_none, way_end, way_straight,",
    "way_curve, way_tee, way_cross",
    "Six collections wayobj_none ...",
    "wayobj_cross, and for each, a",
    "wayobj_<piece>_front for the parts",
    "drawn OVER the vehicles",
    "Model it at the tile's NORTH",
    "edge (+Y). For a signal, put each",
    "aspect's lamp in state_0 / state_1;",
    "STATE 0 IS RED",
    "Collection tunnel_portal on a",
    "ramp facing NORTH, and",
    "tunnel_portal_front for the parts",
    "Collections bridge_span,",
    "bridge_start, bridge_ramp,",
    "bridge_pillar, and a _front for",
    "the parts drawn OVER the vehicles",
    "No bridge_span collection - model the pieces in bridge_span, bridge_start, "
    "bridge_ramp, bridge_pillar",
    "Model it like a building:",
    "facade toward -Y, growing",
    "east (+X) and south (-Y).",
    "Give it a Map colour",
    "Inner way",
    "Optional: the name of the way built inside the tunnel. It is written as a "
    "cross-reference and must resolve to a real way at game load, so leave it "
    "EMPTY unless you have one",
    "No tunnel_portal collection - model the portal on a north-facing ramp and "
    "put it in tunnel_portal",
    # --- warnings shown BEFORE the mistake is made
    "3 seasons: the engine NEVER",
    "draws the third. Use 2, 4 or 5.",
    "A signal needs 2 aspects.",
    "State 0 is RED.",
)


SPANISH = {
    # panels
    "Rig": "Rig",
    "Output": "Salida",
    "Object (.dat)": "Objeto (.dat)",
    "%d px, ortho_scale %.4f": "%d px, ortho_scale %.4f",
    "Save the .blend, or use an": "Guarda el .blend, o usa una",
    "absolute Output path": "ruta de salida absoluta",
    # operators
    "Build Rig": "Montar rig",
    "Create the Simutrans camera and sun and set the render options this pakset needs":
        "Crea la cámara y el sol de Simutrans y ajusta las opciones de render que "
        "necesita este pakset",
    "Render Sheet": "Renderizar hoja",
    "Render every heading, assemble the sprite sheet, write the .dat":
        "Renderiza todas las direcciones, monta la hoja de sprites y escribe el .dat",
    "Check Colours": "Comprobar colores",
    "Scan the sheet for Simutrans' reserved colours - the ones the engine repaints "
    "in the company colour":
        "Busca en la hoja los colores reservados de Simutrans: los que el motor "
        "repinta con el color de la empresa",
    "Night Preview": "Vista nocturna",
    "Show the sheet as the game will draw it after dark - the engine's own "
    "day-to-night colour swap, not a filter":
        "Enseña la hoja tal como la dibujará el juego de noche: el cambio de color "
        "día-noche del propio motor, no un filtro",
    "Night": "Noche",
    "How dark. The game's clock runs 0 (noon) to 4 (deep night) - "
    "display/simview.cc hours2night[]":
        "Cuánta oscuridad. El reloj del juego va de 0 (mediodía) a 4 (noche "
        "cerrada) - display/simview.cc hours2night[]",
    "%s - %d px will light up": "%s - %d px se encenderán",
    "%s - but NOTHING lights up: no pixel carries one of the engine's light "
    "colours, so this runs dark all night":
        "%s - pero NO se enciende NADA: ningún píxel lleva un color-luz del motor, "
        "así que esto circulará a oscuras toda la noche",
    # properties
    "Pakset": "Pakset",
    "tile is %d px": "la casilla mide %d px",
    "Dirs": "Direcciones",
    "8 (asymmetric)": "8 (asimétrico)",
    "every heading rendered": "se renderizan todas las direcciones",
    "4 (symmetric)": "4 (simétrico)",
    "the engine reuses each for its opposite":
        "el motor reutiliza cada una para su opuesta",
    "Where the sheet and the .dat go. '//' is relative to the .blend, so save the "
    ".blend first or give an absolute path":
        "Dónde van la hoja y el .dat. '//' es relativo al .blend, así que guarda "
        "antes el .blend o pon una ruta absoluta",
    "Sheet": "Hoja",
    "Name": "Nombre",
    "Author": "Autor",
    "Waytype": "Vía",
    "Engine": "Motor",
    "Speed (km/h)": "Velocidad (km/h)",
    "Power (kW)": "Potencia (kW)",
    "0 makes it an unpowered wagon or trailer":
        "0 lo convierte en vagón o remolque sin motor",
    "Weight (t)": "Peso (t)",
    "Length": "Longitud",
    "in 1/16 of a tile; 8 is half a tile":
        "en 1/16 de casilla; 8 es media casilla",
    "Payload": "Capacidad",
    "Freight": "Carga",
    "Cargo variants": "Variantes de carga",
    "Comma-separated goods for a wagon that looks different loaded (e.g. 'Kohle, "
    "Oel'). Put each load in a collection freight_0, freight_1, ... in the same "
    "order. Leave EMPTY for a wagon that looks the same whatever it carries":
        "Mercancías separadas por coma para un vagón que se ve distinto cargado "
        "(p. ej. 'Kohle, Oel'). Pon cada carga en una colección freight_0, "
        "freight_1, ... en el mismo orden. Déjalo VACÍO para un vagón que se ve "
        "igual lleve lo que lleve",
    "Cost (cents)": "Precio (céntimos)",
    "Running cost": "Coste por km",
    "Intro year": "Año de aparición",
    "In front": "Delante de",
    "Comma-separated vehicle names that may go IN FRONT of this one. Use 'none' to "
    "allow it at the head of the train. Leave EMPTY to couple behind anything - an "
    "empty field is not the same as 'none'":
        "Nombres de vehículos, separados por comas, que pueden ir DELANTE de éste. "
        "Pon 'none' para permitir que encabece el tren. Déjalo VACÍO para que se "
        "enganche detrás de cualquier cosa: vacío no es lo mismo que 'none'",
    "Behind": "Detrás de",
    "Comma-separated vehicle names that may go BEHIND this one. Use 'none' to allow "
    "it at the tail. Leave EMPTY to couple to anything":
        "Nombres de vehículos, separados por comas, que pueden ir DETRÁS de éste. "
        "Pon 'none' para permitir que vaya en cola. Déjalo VACÍO para que se "
        "enganche a cualquier cosa",
    "Align offset": "Ajuste de alineación",
    "Nudge the vehicle inside its cell. Leave at zero unless it does not ride the "
    "centre of the way":
        "Mueve el vehículo dentro de su celda. Déjalo a cero salvo que el vehículo "
        "no vaya por el centro de la vía",
    "Write .dat": "Escribir .dat",
    # compile
    "Compile": "Compilar",
    "Compile .pak": "Compilar .pak",
    "Run makeobj on the .dat and produce a .pak the game can load":
        "Ejecuta makeobj sobre el .dat y produce un .pak que el juego puede cargar",
    "makeobj": "makeobj",
    "Path to the makeobj executable. It is not shipped with Blender: build it from "
    "the Simutrans source with 'cmake --build <dir> --target makeobj'":
        "Ruta al ejecutable makeobj. No viene con Blender: se compila desde el "
        "código de Simutrans con 'cmake --build <dir> --target makeobj'",
    "Install to": "Instalar en",
    "Optional. Copy the compiled .pak here - normally a pakset's addons folder, so "
    "the game picks it up":
        "Opcional. Copia aquí el .pak compilado; normalmente la carpeta addons de "
        "un pakset, para que el juego lo cargue",
    "Set the path to makeobj first": "Indica antes la ruta a makeobj",
    "makeobj not found: %s": "no se encuentra makeobj: %s",
    "No .dat yet - render the sheet first":
        "Todavía no hay .dat: renderiza antes la hoja",
    "makeobj failed: %s": "makeobj ha fallado: %s",
    "Compiled %s (%d bytes)": "%s compilado (%d bytes)",
    "Could not install the .pak: %s": "No se ha podido instalar el .pak: %s",
    "Compiled %s and installed it to %s": "%s compilado e instalado en %s",
    # messages
    "%s rig: %d px, ortho_scale %.4f": "rig %s: %d px, ortho_scale %.4f",
    "Set an Output directory": "Indica una carpeta de salida",
    "Save your .blend first, or set an absolute Output path ('//' means 'next to "
    "the .blend', and there isn't one yet)":
        "Guarda antes el .blend, o pon una ruta de salida absoluta ('//' significa "
        "'junto al .blend', y todavía no hay ninguno)",
    "Nothing to render - the scene has no mesh":
        "No hay nada que renderizar: la escena no tiene ninguna malla",
    "You listed %d cargo variant(s) but there are %d freight_ collection(s). "
    "Make one collection freight_0..freight_%d, one per good, in order":
        "Indicaste %d variante(s) de carga pero hay %d colección(es) freight_. "
        "Crea una colección freight_0..freight_%d, una por mercancía, en orden",
    "Rendered %d frames to %s": "%d fotogramas renderizados en %s",
    "Rendering %d headings - Esc to cancel":
        "Renderizando %d orientaciones - Esc para cancelar",
    "Rendering heading %d/%d - Esc to cancel":
        "Renderizando orientación %d/%d - Esc para cancelar",
    "Render cancelled at heading %d/%d":
        "Render cancelado en la orientación %d/%d",
    "No sheet yet - render one first": "Todavía no hay hoja: renderiza una primero",
    "No reserved colours - nothing will be recoloured":
        "Sin colores reservados: no se repintará nada",
    ".dat: %d error(s), %d warning(s)": ".dat: %d error(es), %d aviso(s)",
    ".dat line %d: %s": ".dat línea %d: %s",
    "%s + %s, with %d warning(s) above": "%s + %s, con %d aviso(s) arriba",
    "Rewrite the .dat from the last render, with the current numbers - no "
    "re-rendering. Change power, cost, couplings and press this instead of "
    "rendering every heading again":
        "Reescribe el .dat desde el último render, con los números actuales, sin "
        "volver a renderizar. Cambia potencia, coste o enganches y pulsa esto en "
        "vez de renderizar otra vez cada dirección",
    "No render to build from - press Render Sheet first":
        "No hay render del que partir: pulsa antes Renderizar hoja",
    "The last render of %r was a %s, not a %s":
        "El último render de %r fue un %s, no un %s",
    "Wrote %s (no re-render)": "Escrito %s (sin re-renderizar)",

    # --- materials
    "Materials": "Materiales",
    "Material": "Material",
    "Paint": "Pintura",
    "Apply to selected": "Aplicar a lo seleccionado",
    "Give the selected objects a Simutrans material - a player colour, a night "
    "light, or plain paint":
        "Da a los objetos seleccionados un material de Simutrans: color de jugador, "
        "una luz nocturna o pintura normal",
    "Select a mesh object first": "Selecciona antes un objeto de malla",
    "%s -> %d object(s)": "%s -> %d objeto(s)",
    "The colour for Plain paint. The reserved materials above ignore it - their "
    "colour is fixed by the engine":
        "El color de la pintura normal. Los materiales reservados de arriba lo "
        "ignoran: su color lo fija el motor",
    "Player colour": "Color de jugador",
    "Window (warm)": "Ventana (cálida)",
    "Window (blue)": "Ventana (azul)",
    "Headlight": "Faro",
    "Red lamp": "Luz roja",
    "Green lamp": "Luz verde",
    "Yellow lamp": "Luz amarilla",
    "Signal (purple)": "Señal (morada)",
    "Plain paint": "Pintura normal",

    # --- what kind of object, and everything that hangs off it
    "Object": "Objeto",
    "Vehicle": "Vehículo",
    "Building": "Edificio",
    "Way": "Vía",
    "Catenary": "Catenaria",
    "Sign / Signal": "Señal",
    "Tunnel": "Túnel",
    "Bridge": "Puente",
    "Factory": "Fábrica",
    "a train, a bus, a ship - 4 or 8 headings":
        "un tren, un autobús, un barco: 4 u 8 rumbos",
    "a house, a factory - turned to face its street":
        "una casa, una fábrica: girada para mirar a su calle",
    "a road, a rail - six models, sixteen images":
        "una carretera, un raíl: seis modelos, dieciséis imágenes",
    "overhead line and the like, in two layers":
        "línea aérea y similares, en dos capas",
    "four directions, one aspect each": "cuatro direcciones, un aspecto cada una",
    "a portal, four directions, two layers":
        "un portal, cuatro direcciones, dos capas",
    "span, ramps, pillars - in two layers":
        "vano, rampas, pilares: en dos capas",
    "a building that makes or consumes goods":
        "un edificio que produce o consume mercancías",
    "Map colour": "Color en el mapa",
    "The colour the factory shows on the minimap (0-254). The engine refuses a "
    "factory without one":
        "El color con que la fábrica aparece en el minimapa (0-254). El motor "
        "rechaza una fábrica sin él",
    "Productivity": "Productividad",
    "How much the factory makes per step": "Cuánto produce la fábrica por paso",
    "Location": "Ubicación",
    "Where the industry generator may place it":
        "Dónde puede colocarla el generador de industrias",
    "Makes": "Produce",
    "The good this factory PRODUCES (e.g. 'Kohle'). Must be a real pakset good. "
    "Empty for a pure consumer":
        "La mercancía que esta fábrica PRODUCE (p. ej. 'Kohle'). Debe ser una "
        "mercancía real del pakset. Vacío para una consumidora pura",
    "Output store": "Almacén de salida",
    "Storage for the produced good. Must be more than 10":
        "Almacenamiento de la mercancía producida. Debe ser mayor que 10",
    "Consumes": "Consume",
    "A good this factory CONSUMES (e.g. 'Eisenerz'). Must be a real pakset good. "
    "Empty for a pure producer":
        "Una mercancía que esta fábrica CONSUME (p. ej. 'Eisenerz'). Debe ser una "
        "mercancía real del pakset. Vacío para una productora pura",
    "Max length": "Longitud máx.",
    "Longest span the bridge may cross, in tiles. 0 = unlimited":
        "El vano más largo que el puente puede cruzar, en casillas. 0 = sin límite",
    "Max height": "Altura máx.",
    "How high above the ground the bridge may be built":
        "A qué altura sobre el suelo puede construirse el puente",
    "Pillar every": "Pilar cada",
    "Place a pillar every N tiles. 0 = no pillars":
        "Coloca un pilar cada N casillas. 0 = sin pilares",


    # --- building
    "Tiles east": "Casillas al este",
    "Tiles south": "Casillas al sur",
    "Accepts passengers": "Acepta pasajeros",
    "Accepts mail": "Acepta correo",
    "Accepts goods": "Acepta mercancías",
    "Layouts": "Orientaciones",
    "How many ways round it can be built. 0 lets the engine decide: 1 for a square "
    "footprint, 2 otherwise":
        "De cuántas formas se puede colocar. 0 deja que lo decida el motor: 1 si la "
        "huella es cuadrada, 2 si no",
    "Kind": "Tipo",
    "Level": "Nivel",
    "drives demand, and the default capacity (level x 32)":
        "determina la demanda, y la capacidad por defecto (nivel x 32)",
    "Chance": "Probabilidad",
    "how often a city picks this house; 0 = never":
        "con qué frecuencia la ciudad elige esta casa; 0 = nunca",
    "Seasons": "Temporadas",
    "1, 2, 4 or 5 - never 3, the engine NEVER draws the third image. Put each "
    "season's extras in a collection 'season_1', 'season_2', ...":
        "1, 2, 4 o 5 - nunca 3: el motor NO dibuja jamás la tercera imagen. Pon los "
        "añadidos de cada temporada en una colección 'season_1', 'season_2', ...",
    "Phases": "Fases",
    "animation frames. Put each frame's extras in a collection 'phase_1', "
    "'phase_2', ...":
        "fotogramas de animación. Pon los añadidos de cada uno en una colección "
        "'phase_1', 'phase_2', ...",

    # --- way / wayobj
    "Top speed": "Velocidad máx.",
    "Maintenance": "Mantenimiento",
    "Grants": "Concede",
    "what the wayobj gives the way underneath. Catenary is electrified_track - that "
    "is what lets an electric loco run":
        "lo que el wayobj le da a la vía de debajo. La catenaria es "
        "electrified_track, que es lo que permite circular a una loco eléctrica",

    # --- roadsign
    "Block signal": "Señal de bloqueo",
    "a signal rather than a sign. It then needs two aspects, and STATE 0 IS RED":
        "una señal, no un cartel. Entonces necesita dos aspectos, y EL ESTADO 0 ES "
        "ROJO",
    "Aspects": "Aspectos",
    "1 for a plain sign, 2 for a signal. State 0 is RED. Put each aspect's extras in "
    "a collection 'state_0', 'state_1', ...":
        "1 para un cartel, 2 para una señal. El estado 0 es ROJO. Pon los añadidos "
        "de cada aspecto en una colección 'state_0', 'state_1', ...",

    # --- the model hints, drawn in the panel
    "Model: nose along +X,": "Modela: morro hacia +X,",
    "on z=0, at the origin": "sobre z=0, en el origen",
    "Model: facade toward -Y": "Modela: fachada hacia -Y",
    "(Blender's Front view),": "(la vista Frontal de Blender),",
    "growing east (+X) and south (-Y)": "creciendo al este (+X) y al sur (-Y)",
    "Six collections:": "Seis colecciones:",
    "way_none, way_end, way_straight,": "way_none, way_end, way_straight,",
    "way_curve, way_tee, way_cross": "way_curve, way_tee, way_cross",
    "Six collections wayobj_none ...": "Seis colecciones wayobj_none ...",
    "wayobj_cross, and for each, a": "wayobj_cross, y para cada una, una",
    "wayobj_<piece>_front for the parts": "wayobj_<pieza>_front con las partes",
    "drawn OVER the vehicles": "que se dibujan POR ENCIMA de los vehículos",
    "Model it at the tile's NORTH": "Modélala en el borde NORTE de la",
    "edge (+Y). For a signal, put each": "casilla (+Y). Si es señal, pon el foco",
    "aspect's lamp in state_0 / state_1;": "de cada aspecto en state_0 / state_1;",
    "STATE 0 IS RED": "EL ESTADO 0 ES ROJO",
    "Collection tunnel_portal on a": "Colección tunnel_portal en una",
    "ramp facing NORTH, and": "rampa que mira al NORTE, y",
    "tunnel_portal_front for the parts": "tunnel_portal_front para las partes",
    "Collections bridge_span,": "Colecciones bridge_span,",
    "bridge_start, bridge_ramp,": "bridge_start, bridge_ramp,",
    "bridge_pillar, and a _front for": "bridge_pillar, y un _front para",
    "the parts drawn OVER the vehicles": "las partes dibujadas SOBRE los vehículos",
    "No bridge_span collection - model the pieces in bridge_span, bridge_start, "
    "bridge_ramp, bridge_pillar":
        "No hay colección bridge_span: modela las piezas en bridge_span, "
        "bridge_start, bridge_ramp, bridge_pillar",
    "Model it like a building:": "Modélala como un edificio:",
    "facade toward -Y, growing": "fachada hacia -Y, creciendo",
    "east (+X) and south (-Y).": "al este (+X) y al sur (-Y).",
    "Give it a Map colour": "Dale un Color en el mapa",
    "Inner way": "Vía interior",
    "Optional: the name of the way built inside the tunnel. It is written as a "
    "cross-reference and must resolve to a real way at game load, so leave it "
    "EMPTY unless you have one":
        "Opcional: el nombre de la vía construida dentro del túnel. Se escribe como "
        "referencia cruzada y debe resolver a una vía real al cargar el juego, así "
        "que déjalo VACÍO salvo que tengas una",
    "No tunnel_portal collection - model the portal on a north-facing ramp and "
    "put it in tunnel_portal":
        "No hay colección tunnel_portal: modela el portal en una rampa que mira al "
        "norte y ponlo en tunnel_portal",

    # --- the warnings the panel shows before you make the mistake
    "3 seasons: the engine NEVER": "3 temporadas: el motor NO dibuja",
    "draws the third. Use 2, 4 or 5.": "jamás la tercera. Usa 2, 4 o 5.",
    "A signal needs 2 aspects.": "Una señal necesita 2 aspectos.",
    "State 0 is RED.": "El estado 0 es ROJO.",
}


LANGUAGES = {
    "es": SPANISH,
}


def as_blender_dict():
    """Shape it the way bpy.app.translations.register() wants.

    {locale: {(context, source): translation}} - all of ours under CONTEXT, so
    Blender's own catalogue can neither shadow us nor be shadowed by us.
    """
    return {
        locale: {(CONTEXT, src): dst for src, dst in table.items()}
        for locale, table in LANGUAGES.items()
    }
