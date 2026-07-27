//
// THE STADLER FLIRT RABe 523 (SBB), IN A RUNNING GAME, ON PAK128'S OWN TRACK.
//
// Modelled on the civia465 scenario. It asks the engine four things it cannot fake:
//   1. is the cab car in the depot catalogue?
//   2. is it really ELECTRIC (needs_electrification(), not the word in the .dat)?
//   3. does ONE click on the cab assemble the four-car unit IN ORDER (the couplings)?
//   4. and does it MOVE, on pak128 rail under pak128 catenary?
//

map.file = "empty-16x16.sve"

scenario.short_description = "Stadler FLIRT RABe 523 on pak128"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

CAB_A <- "SBB_FLIRT_RABe523_A"

// The four-car unit, in the order the couplings must produce it.
UNIT <- ["SBB_FLIRT_RABe523_A", "SBB_FLIRT_RABe523_B",
         "SBB_FLIRT_RABe523_C", "SBB_FLIRT_RABe523_D"]

local result = "not run"
local convoy = null
local start_pos = null
local polls = 0
local built_once = false
local watching = false


function bad(err) { return (typeof err == "string") && err != "" }
function fail(why) { result = "FLIRT523_FAIL: " + why; print(result); watching = false }

function names_of(cars)
{
	local out = []
	foreach (v in cars) { out.append(v.get_name()) }
	return out
}

function joined(list)
{
	local s = ""
	foreach (i, v in list) { s += (i > 0 ? " " : "") + v }
	return s
}


function build_everything()
{
	if (built_once) { return }
	built_once = true

	local pl = player_x(0)
	pl.book_cash(100000000000)          // a bankrupt player cannot start a train

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

	// a straight run and a diagonal, all wired
	if (bad(command_x.build_way(pl, coord3d(2, 8, 0), coord3d(11, 8, 0), rail, true))) {
		return fail("laying the rail")
	}
	if (bad(command_x.build_way(pl, coord3d(11, 8, 0), coord3d(14, 5, 0), rail, true))) {
		return fail("the diagonal")
	}
	if (bad(command_x.build_wayobj(pl, coord3d(2, 8, 0), coord3d(11, 8, 0), wire))) {
		return fail("hanging the catenary")
	}
	if (bad(command_x.build_wayobj(pl, coord3d(11, 8, 0), coord3d(14, 5, 0), wire))) {
		return fail("the catenary on the diagonal")
	}
	if (!tile_x(6, 8, 0).get_way(wt_rail).is_electrified()) {
		return fail("the rail is not electrified after the wire went up")
	}
	if (bad(command_x.build_depot(pl, coord3d(2, 8, 0), depot_desc))) {
		return fail("the depot")
	}

	// --- is the cab car in the depot catalogue?
	local cab = null
	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		if (v.get_name() == CAB_A) { cab = v }
	}
	if (cab == null) { return fail(CAB_A + " is NOT in the depot list") }

	// --- does the engine agree it is electric?
	if (!cab.needs_electrification()) {
		return fail(CAB_A + " does not need catenary - it did not come through as"
			+ " an electric vehicle")
	}

	// --- ONE click on the cab car; the depot follows the single-successor chain
	local depot = depot_x(2, 8, 0)
	depot.append_vehicle(pl, convoy_x(0), cab)
	convoy = depot.get_convoy_list()[0]
	convoy.change_schedule(pl, schedule_x(wt_rail, [
		schedule_entry_x(coord3d(4, 8, 0), 0, 0),
		schedule_entry_x(coord3d(10, 8, 0), 0, 0),
	]))
	depot.start_all_convoys(pl)

	start_pos = convoy.get_pos()
	watching = true
	print("FLIRT523: built; watching the unit leave the depot")
}


function watch()
{
	if (!watching || convoy == null) { return }
	polls++

	local now = convoy.get_pos()
	if (now.x != start_pos.x || now.y != start_pos.y) {
		local names = names_of(convoy.get_vehicles())

		if (names.len() != UNIT.len()) {
			return fail("one click on the cab gave " + names.len() + " car(s), not "
				+ UNIT.len() + " - the couplings do not chain: [" + joined(names) + "]")
		}
		foreach (i, want in UNIT) {
			if (names[i] != want) {
				return fail("car " + i + " is " + names[i] + ", expected " + want
					+ " - the unit assembles out of order: [" + joined(names) + "]")
			}
		}

		result = "FLIRT523_OK: one click assembled the whole " + names.len()
			+ "-car unit in order [" + joined(names) + "], the engine agrees it is"
			+ " electric, and it has moved from (" + start_pos.x + "," + start_pos.y
			+ ") to (" + now.x + "," + now.y + ") on pak128 rail under pak128 catenary"
		print(result)
		watching = false
		return
	}
	if (polls > 400) {
		result = "FLIRT523_FAIL: the unit never left the depot in " + polls + " steps"
		print(result)
		watching = false
	}
}


function start()        { build_everything() }
function resume_game()  { build_everything() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Watch the FLIRT run.") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { watch(); return 0 }
