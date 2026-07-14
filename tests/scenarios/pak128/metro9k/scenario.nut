//
// THE METRO DE MADRID SERIE 9000, IN A RUNNING GAME, ON PAK128'S OWN TRACK.
//
// Not "does the .pak load" - a pak can load and still be unbuyable, or buyable and
// unable to move. This asks the engine four things it cannot fake:
//
//   1. is the car in the depot catalogue (the very list the depot dialog is built
//      from)?
//   2. is it really ELECTRIC? Not "does the .dat say so" - does the engine, having
//      loaded the .pak, agree that this vehicle needs catenary?
//   3. does the DEPOT assemble the unit the constraints describe? Each car has
//      exactly one possible successor, so one click on the cab must produce six
//      cars IN ORDER.
//   4. and does it MOVE?
//
// Checks 2 and 3 exist because they did not. The success line reported the car
// count and called the unit "electric" - the first was never compared and the
// second was a string literal. Both a diesel build and a build with no couplings
// at all (one click, one car) passed.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Metro de Madrid serie 9000 on pak128"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

CAB_A <- "MadridMetro_S9000_CabA"

// The real six-car unit, in the order the couplings must produce it.
UNIT <- ["MadridMetro_S9000_CabA", "MadridMetro_S9000_R1", "MadridMetro_S9000_S1",
         "MadridMetro_S9000_S2", "MadridMetro_S9000_R2", "MadridMetro_S9000_CabB"]

local result = "not run"
local convoy = null
local start_pos = null
local polls = 0
local built_once = false
local watching = false


function bad(err) { return (typeof err == "string") && err != "" }
function fail(why) { result = "METRO9K_FAIL: " + why; print(result); watching = false }

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
	pl.book_cash(100000000000)          // cents. A bankrupt player cannot start a train.

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

	// a straight run, a diagonal and a curve - the shapes a vehicle sprite has to
	// survive - all of it wired
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

	// --- is the cab car in the catalogue the depot dialog is built from?
	local cab = null
	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		if (v.get_name() == CAB_A) { cab = v }
	}
	if (cab == null) { return fail(CAB_A + " is NOT in the depot list") }

	// --- is it electric? Ask the ENGINE, which has read the compiled .pak, rather
	//     than trusting the word in our own success message. needs_electrification()
	//     is true only for a vehicle whose engine_type really came through as
	//     electric, so this is the check that a diesel .dat cannot survive.
	if (!cab.needs_electrification()) {
		return fail(CAB_A + " does not need catenary - it did not come through as"
			+ " an electric vehicle")
	}

	// --- ONE click on the cab car. The depot follows the chain of single
	//     successors, so this is also the test of the couplings.
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
	print("METRO9K: built; watching the unit leave the depot")
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

		result = "METRO9K_OK: one click assembled the whole " + names.len()
			+ "-car unit in order [" + joined(names) + "], the engine agrees it is"
			+ " electric, and it has moved from (" + start_pos.x + "," + start_pos.y
			+ ") to (" + now.x + "," + now.y + ") on pak128 rail under pak128 catenary"
		print(result)
		watching = false
		return
	}
	if (polls > 400) {
		result = "METRO9K_FAIL: the unit never left the depot in " + polls + " steps"
		print(result)
		watching = false
	}
}


function start()        { build_everything() }
function resume_game()  { build_everything() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Watch the Metro9000 run.") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { watch(); return 0 }
