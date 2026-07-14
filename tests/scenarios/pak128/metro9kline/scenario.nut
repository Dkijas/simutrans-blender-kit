//
// THE SERIE 9000 WORKING A LINE, ON A REAL MAP, WITH REAL PLATFORMS.
//
// The other scenario (metro9k) asks the smallest question that cannot be faked:
// does the depot assemble the unit, and does it cover ground under catenary.
//
// This one asks what a PLAYER would ask, and the first version of it got two things
// wrong that a player would have spotted in a second:
//
//   * THE PLATFORMS WERE ONE TILE LONG. The unit is six cars of 8 carunits = 48
//     carunits = THREE TILES. A one-tile halt cannot hold it: the train hangs out of
//     the station at both ends. Platforms here are three tiles, which is the length
//     of the train, because that is what a platform is FOR.
//   * THE STATIONS WERE THREE TILES APART. With a three-tile train, the tail is
//     still in one station while the nose enters the next. There are ten tiles of
//     open running between them now.
//
// Neither fits on the 16x16 test map, so this one runs on a real one - pak128's own
// New York, 1024x1024 - and FINDS its own corridor rather than trusting a hardcoded
// coordinate that the next map would break.
//

map.file = "map.sve"          // 16x16, and no timeline - see the note below

scenario.short_description = "Serie 9000 working a four-station metro line"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

CAB_A <- "MadridMetro_S9000_CabA"

PLATFORM <- 3        // tiles. The train is 3 tiles long (6 cars x 8 carunits / 16),
                     // and a platform shorter than the train is not a platform.
GAP <- 8             // tiles of open running between the two platforms
STATIONS <- 2
NEED <- PLATFORM * STATIONS + GAP * (STATIONS - 1) + 2      // = 16, the whole map

// TWO STOPS, AND THEY ARE PROPERLY APART. That is the trade the map forces, and it
// is the right way round: the point of the test is that a six-car unit LEAVES a
// platform, RUNS, and ARRIVES at another one - and for that, the running matters
// more than the number of platforms. Eight tiles of open track between them is
// nearly three train lengths.
//
// The map is 16x16, and it is the only map the train can be bought on: every map
// pak128 ships starts before 2006 (New York 1957, tramadness 2000, the tutorial
// 1961), so a 2006 metro unit is correctly not for sale on any of them. Ours has no
// timeline at all. A saved game carries its own settings, so neither `-timeline 0`
// nor the scenario API can switch the calendar off after the fact.
//
// Three stops fitted, but only two tiles apart - which is less than one train
// length, and a train that is still leaving one station as it enters the next is
// not testing anything. Two stops, eight tiles apart, tests more.

local result = "not run"
local convoy = null
local stops = []             // the middle tile of each platform
local visited = []
local polls = 0
local built_once = false
local watching = false
local last_stop = -1


function bad(err) { return (typeof err == "string") && err != "" }
function fail(why) { result = "METRO9KLINE_FAIL: " + why; print(result); watching = false }


function find_corridor()
{
	// A straight, flat, empty run wide enough for the whole line. Scanning a
	// 1024x1024 map tile by tile from Squirrel takes minutes, so this steps through
	// rows and stops at the first one that fits - which is all we need.
	local sz = world.get_size()
	for (local y = 0; y < sz.y; y += 3) {
		local run = 0
		local start = 0
		for (local x = 0; x < sz.x; x++) {
			local t = square_x(x, y).get_ground_tile()
			if (t.is_empty() && !t.is_water() && t.get_slope() == 0) {
				if (run == 0) { start = x }
				run++
				if (run >= NEED) { return [start, y, t.z] }
			}
			else { run = 0 }
		}
	}
	return null
}


function build_everything()
{
	if (built_once) { return }
	built_once = true

	local pl = player_x(0)
	pl.book_cash(100000000000)          // cents. A bankrupt player cannot start a train.

	local site = find_corridor()
	if (site == null) { return fail("no flat empty run of " + NEED + " tiles anywhere") }
	local x0 = site[0]
	local y  = site[1]
	local z  = site[2]
	print("METRO9KLINE: corridor at y=" + y + ", x=" + x0 + ".." + (x0 + NEED - 1))

	local rails = way_desc_x.get_available_ways(wt_rail, st_flat)
	if (rails.len() == 0) { return fail("pak128 offers no rail") }
	rails.sort(@(a, b) b.get_topspeed() <=> a.get_topspeed())
	local rail = rails[0]

	local wire = null
	foreach (w in wayobj_desc_x.get_available_wayobjs(wt_rail)) {
		if (w.get_waytype() == wt_rail) { wire = w }
	}
	if (wire == null) { return fail("pak128 offers no catenary") }

	local depot_desc = null
	foreach (b in building_desc_x.get_building_list(building_desc_x.depot)) {
		if (b.get_waytype() == wt_rail) { depot_desc = b; break }
	}
	if (depot_desc == null) { return fail("pak128 has no rail depot") }

	// PICK A PLATFORM, NOT A SHED. building_desc_x.station hands back the station
	// EXTENSIONS and, first in the list, the DEPOTS - so taking the first rail entry
	// gives you Depot_train_1936 and the engine replies "Illegal station tool", which
	// is a perfectly fair thing to say about building a depot with the station tool.
	// pak128 has proper metro platforms, which is what a Serie 9000 calls at.

	// --- the line
	local x1 = x0 + NEED - 1
	if (bad(command_x.build_way(pl, coord3d(x0, y, z), coord3d(x1, y, z), rail, true))) {
		return fail("laying the rail")
	}
	if (bad(command_x.build_wayobj(pl, coord3d(x0, y, z), coord3d(x1, y, z), wire))) {
		return fail("hanging the catenary")
	}
	if (!tile_x(x0 + 5, y, z).get_way(wt_rail).is_electrified()) {
		return fail("the rail is not electrified after the wire went up")
	}
	if (bad(command_x.build_depot(pl, coord3d(x0, y, z), depot_desc))) {
		return fail("the depot")
	}

	//
	// AND IT MUST EXIST IN THIS YEAR. The map is somebody else's, and it starts when
	// it starts: asking for subway_single_modern_station on a 1930s map gets you
	// "Object not available (retired or future)", which is the engine being right.
	// So instead of asserting which platform to use, we TRY them, oldest fallback
	// last, and let the engine say which one it will accept. It is the only party
	// here that knows.
	//
	local wanted = ["train_flat_station_modern", "train_flat_station_early", "train_platform_modern", "train_platform_med", "train_platform_early", "subway_single_modern_station", "subway_single_station",
	                "subway_single_old_station", "train_station_modern",
	                "train_small_station_modern", "train_station_med",
	                "train_small_station_med", "train_station_early",
	                "train_small_station_early", "train_platform_early"]
	local by_name = {}
	foreach (b in building_desc_x.get_building_list(building_desc_x.station)) {
		if (b.get_waytype() == wt_rail) { by_name[b.get_name()] <- b }
	}

	local x_probe = x0 + 2
	local stat_desc = null
	foreach (n in wanted) {
		if (!(n in by_name)) { continue }
		local err = command_x.build_station(pl, coord3d(x_probe, y, z), by_name[n])
		if (!bad(err)) { stat_desc = by_name[n]; break }
		print("METRO9KLINE: " + n + " refused (" + err + ")")
	}
	if (stat_desc == null) { return fail("pak128 has no rail platform this map's year accepts") }

	// --- four platforms, each THREE TILES long, ten tiles apart
	local x = x0 + 2
	for (local s = 0; s < STATIONS; s++) {
		for (local t = 0; t < PLATFORM; t++) {
			local err = command_x.build_station(pl, coord3d(x + t, y, z), stat_desc)
			if (bad(err)) { return fail("platform " + (s + 1) + " tile " + (t + 1)
				+ " at " + (x + t) + "," + y + ": " + err) }
		}
		stops.append([x + 1, y])            // the middle of the platform
		x += PLATFORM + GAP
	}
	print("METRO9KLINE: " + STATIONS + " platforms of " + PLATFORM
		+ " tiles (" + stat_desc.get_name() + "), " + GAP + " tiles apart")

	// --- is the cab car in the catalogue the depot dialog is built from?
	local cab = null
	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		if (v.get_name() == CAB_A) { cab = v }
	}
	if (cab == null) { return fail(CAB_A + " is NOT in the depot list") }

	// --- ONE click on the cab. The depot follows the chain of single successors.
	local depot = depot_x(x0, y, z)
	depot.append_vehicle(pl, convoy_x(0), cab)
	convoy = depot.get_convoy_list()[0]

	local entries = []
	foreach (s in stops) { entries.append(schedule_entry_x(coord3d(s[0], s[1], z), 0, 0)) }
	convoy.change_schedule(pl, schedule_x(wt_rail, entries))
	depot.start_all_convoys(pl)

	watching = true
	print("METRO9KLINE: " + convoy.get_vehicles().len()
		+ " cars out of the depot, timetable of " + entries.len() + " stops")
}


function watch()
{
	if (!watching || convoy == null) { return }
	polls++

	// Which platform is it at? Position, not hope. A three-tile train stopped at a
	// three-tile platform can have its NOSE on any of the three tiles, so a call
	// counts if the convoy is anywhere in the platform, not only on the middle tile.
	local now = convoy.get_pos()
	local here = -1
	for (local i = 0; i < stops.len(); i++) {
		if (now.y == stops[i][1] && now.x >= stops[i][0] - 1 && now.x <= stops[i][0] + 1) {
			here = i
		}
	}

	if (here >= 0 && here != last_stop) {
		last_stop = here
		visited.append(here)
		print("METRO9KLINE: calling at station " + (here + 1))
	}

	local seen = {}
	foreach (v in visited) { seen[v] <- true }
	if (seen.len() == stops.len() && visited.len() > stops.len()) {
		local cars = convoy.get_vehicles()
		local order = ""
		foreach (v in visited) { order += (v + 1) + " " }
		result = "METRO9KLINE_OK: the " + cars.len() + "-car unit (" + (cars.len() * 8 / 16)
			+ " tiles long) worked the line under pak128 catenary: " + stops.len()
			+ " platforms of " + PLATFORM + " tiles, " + GAP
			+ " tiles apart, all called at, and it turned back. Order: " + order
		print(result)
		watching = false
		return
	}

	if (polls > 60000) {
		local order = ""
		foreach (v in visited) { order += (v + 1) + " " }
		result = "METRO9KLINE_FAIL: in " + polls + " steps it only called at: ["
			+ order + "] of " + stops.len() + " stations"
		print(result)
		watching = false
	}
}


function start()        { build_everything() }
function resume_game()  { build_everything() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Work the line, calling at every station.") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { watch(); return 0 }
