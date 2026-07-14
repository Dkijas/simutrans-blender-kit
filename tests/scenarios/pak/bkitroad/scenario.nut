//
// Does the engine agree with us about which way is north?
//
// The whole way pipeline stands on one derivation: the four RIBI bits are
// 1=north 2=east 4=south 8=west (dataobj/ribi.h:170), and they point at
// north=-Y east=+X south=+Y west=-X - which we read off ribi_t::layout_to_ribi[]
// against simcity's neighbors[]. Everything else - the rotate-left, the six
// models, the sixteen images - follows from that. If it is wrong, every curve
// in the pakset is wrong, and it all still compiles.
//
// A pixel test in Blender cannot settle it: it only proves our renderer agrees
// with our own maths. So ask the ENGINE. Lay an L-shaped road and make it tell
// us, through tile_x::get_way_dirs, what ribi it thinks each tile has.
//
//     (2,2) ---- (4,2) ---- (6,2)        x grows east
//                              |
//                            (6,6)       y grows south
//
// (4,2) is a straight run, so it must be east|west.
// (6,2) is the corner: it meets (5,2) to its west and (6,3) to its south.
// (6,6) is the far end: it only meets (6,5), which lies to its north.
//
// Those three numbers are 10, 12 and 1. Nothing else is consistent with them.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: lay the generated road"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_Road"
local result = "not run"

// north=1 east=2 south=4 west=8
RIBI_NAME <- ["-", "n", "e", "ne", "s", "ns", "se", "nse",
              "w", "nw", "ew", "new", "sw", "nsw", "sew", "nsew"]


function lay_road()
{
	local pl = player_x(0)

	// 1. is it in the engine's own catalogue of buildable roads?
	local mine = null
	foreach (candidate in way_desc_x.get_available_ways(wt_road, st_flat)) {
		if (candidate.get_name() == WANTED) {
			mine = candidate
		}
	}
	if (mine == null) {
		result = "BKITROAD_FAIL: the engine has no buildable road called " + WANTED
		print(result)
		return
	}

	// 2. lay it: one leg east, one leg south
	local err = command_x.build_way(pl, coord3d(2, 2, 0), coord3d(6, 2, 0), mine, true)
	if (err != null && err != "") {
		result = "BKITROAD_FAIL: could not lay the east leg: " + err
		print(result)
		return
	}
	err = command_x.build_way(pl, coord3d(6, 2, 0), coord3d(6, 6, 0), mine, true)
	if (err != null && err != "") {
		result = "BKITROAD_FAIL: could not lay the south leg: " + err
		print(result)
		return
	}

	// 3. is it really OUR road that is lying there?
	local laid = tile_x(4, 2, 0).get_way(wt_road)
	if (laid == null) {
		result = "BKITROAD_FAIL: no road on (4,2) after building one"
		print(result)
		return
	}
	if (laid.get_desc().get_name() != WANTED) {
		result = "BKITROAD_FAIL: laid " + laid.get_desc().get_name()
			+ ", expected " + WANTED
		print(result)
		return
	}

	// 4. THE ORACLE: the engine's own ribi for each tile.
	local probes = [
		[4, 2, 10, "a straight run: east|west"],
		[6, 2, 12, "the corner: west|south"],
		[6, 6,  1, "the far end: north only"]
	]
	foreach (p in probes) {
		local got = tile_x(p[0], p[1], 0).get_way_dirs(wt_road)
		if (got != p[2]) {
			result = "BKITROAD_FAIL: (" + p[0] + "," + p[1] + ") " + p[3]
				+ " - the engine says ribi " + got + " (" + RIBI_NAME[got] + "),"
				+ " we expected " + p[2] + " (" + RIBI_NAME[p[2]] + ")."
				+ " The north/east/south/west mapping is wrong."
			print(result)
			return
		}
	}

	result = "BKITROAD_OK: " + WANTED + " laid; the engine's ribis are"
		+ " (4,2)=ew (6,2)=sw (6,6)=n, exactly as the six models assume"
	print(result)
}


function start()        { lay_road() }
function resume_game()  { lay_road() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Look at the road from (2,2).") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
