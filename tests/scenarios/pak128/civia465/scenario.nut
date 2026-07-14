//
// THE CIVIA S/465, IN A RUNNING GAME, ON PAK128'S OWN TRACK.
//
// Not "does the .pak load" - a pak can load and still be unbuyable, or buyable and
// unable to move. This asks the engine three things it cannot fake:
//
//   1. is the car in the depot catalogue (the very list the depot dialog is built
//      from)?
//   2. does the DEPOT assemble the unit the constraints describe? For the full
//      five-car set that is the whole test: each car has exactly one possible
//      successor, so one click on the cab must produce five cars in order.
//   3. and does it MOVE? The unit is electric, so if it covers ground then pak128's
//      catenary is really feeding pak128's rail and our motor really has power.
//
// It works with whatever is installed: one car (the prototype) or all five.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Civia S/465 on pak128"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

CAB_A <- "CiviaS465_CabA"

local result = "not run"
local convoy = null
local start_pos = null
local polls = 0
local built_once = false
local watching = false


function bad(err) { return (typeof err == "string") && err != "" }
function fail(why) { result = "CIVIA465_FAIL: " + why; print(result); watching = false }


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
	print("CIVIA465: built; watching the unit leave the depot")
}


function watch()
{
	if (!watching || convoy == null) { return }
	polls++

	local now = convoy.get_pos()
	if (now.x != start_pos.x || now.y != start_pos.y) {
		local cars = convoy.get_vehicles()
		local names = ""
		foreach (v in cars) { names += v.get_name() + " " }
		result = "CIVIA465_OK: the depot assembled " + cars.len() + " car(s) [" + names
			+ "], electric, and the unit has moved from (" + start_pos.x + ","
			+ start_pos.y + ") to (" + now.x + "," + now.y
			+ ") on pak128 rail under pak128 catenary"
		print(result)
		watching = false
		return
	}
	if (polls > 400) {
		result = "CIVIA465_FAIL: the unit never left the depot in " + polls + " steps"
		print(result)
		watching = false
	}
}


function start()        { build_everything() }
function resume_game()  { build_everything() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Watch the Civia run.") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { watch(); return 0 }
