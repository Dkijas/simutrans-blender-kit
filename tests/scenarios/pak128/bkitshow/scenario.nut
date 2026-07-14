//
// THE COMMUTER UNIT, RUNNING, ON PAK128 TRACK.
//
// Everything under the train belongs to pak128: the rails, the overhead line, the
// depot. Only the train is ours. That is the point - an addon is not a diorama,
// it has to sit inside somebody else's pakset and work.
//
// The unit is ELECTRIC, so it cannot move a metre unless pak128's own catenary is
// really feeding pak128's own rails. If it covers ground, it is not pretending.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: Cercanias on pak128"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

MOTOR   <- "BKitCercaniasM"
TRAILER <- "BKitCercaniasR"

local result = "not run"
local convoy = null
local start_pos = null
local polls = 0
local built = false


function fail(why)
{
	result = "BKITSHOW_FAIL: " + why
	print(result)
	built = false
}


// The tool calls do NOT report success the same way. build_way() gives back null
// or "" when it worked; append_vehicle() gives back true. Compare a bool against
// "" and every successful coupling reads as an error, which is exactly the false
// alarm this cost me. Only a non-empty STRING is a complaint.
function bad(err)
{
	return (typeof err == "string") && err != ""
}


function build_everything()
{
	local pl = player_x(0)
	pl.book_cash(200000000)

	// ------------------------------------------------- pak128's own rail
	local rails = way_desc_x.get_available_ways(wt_rail, st_flat)
	if (rails.len() == 0) { return fail("pak128 offers no rail") }
	rails.sort(@(a, b) b.get_topspeed() <=> a.get_topspeed())
	local rail = rails[0]
	print("BKITSHOW: rail = " + rail.get_name() + " (" + rail.get_topspeed() + " km/h)")

	local err = command_x.build_way(pl, coord3d(2, 8, 0), coord3d(14, 8, 0), rail, true)
	if (bad(err)) { return fail("laying pak128 rail: " + err) }

	// ------------------------------------------- pak128's own overhead line
	local wires = wayobj_desc_x.get_available_wayobjs(wt_rail)
	local wire = null
	foreach (w in wires) {
		if (w.get_waytype() == wt_rail) { wire = w }
	}
	if (wire == null) { return fail("pak128 offers no rail wayobj") }
	print("BKITSHOW: catenary = " + wire.get_name())

	err = command_x.build_wayobj(pl, coord3d(2, 8, 0), coord3d(14, 8, 0), wire)
	if (bad(err)) { return fail("hanging pak128 catenary: " + err) }

	if (!tile_x(8, 8, 0).get_way(wt_rail).is_electrified()) {
		return fail("pak128 rail is not electrified after the wire went up")
	}

	// ------------------------------------------------ pak128's own depot
	local depot_desc = null
	foreach (b in building_desc_x.get_building_list(building_desc_x.depot)) {
		if (b.get_waytype() == wt_rail) { depot_desc = b; break }
	}
	if (depot_desc == null) { return fail("pak128 has no rail depot") }

	err = command_x.build_depot(pl, coord3d(2, 8, 0), depot_desc)
	if (bad(err)) { return fail("the depot: " + err) }

	// ----------------------------------------------------- OUR train
	local motor = vehicle_desc_x(MOTOR)
	local trailer = vehicle_desc_x(TRAILER)
	if (motor == null)   { return fail("no vehicle called " + MOTOR) }
	if (trailer == null) { return fail("no vehicle called " + TRAILER) }

	local depot = depot_x(2, 8, 0)
	local c = convoy_x(0)
	// M - R - R - M: the engine will simply refuse this if the constraints are wrong
	err = depot.append_vehicle(pl, c, motor)
	if (bad(err)) { return fail("the leading motor car: " + err) }
	convoy = depot.get_convoy_list()[0]
	err = depot.append_vehicle(pl, convoy, trailer)
	if (bad(err)) { return fail("coupling the first trailer: " + err) }
	err = depot.append_vehicle(pl, convoy, trailer)
	if (bad(err)) { return fail("coupling the second trailer: " + err) }
	err = depot.append_vehicle(pl, convoy, motor)
	if (bad(err)) { return fail("the rear motor car: " + err) }

	local cars = convoy.get_vehicles().len()
	if (cars != 4) {
		return fail("the unit has " + cars + " cars, not 4 - the constraints refused"
		            + " a coupling the depot should have allowed")
	}
	print("BKITSHOW: the depot assembled a " + cars + "-car unit")

	convoy.change_schedule(pl, schedule_x(wt_rail, [
		schedule_entry_x(coord3d(4, 8, 0), 0, 0),
		schedule_entry_x(coord3d(13, 8, 0), 0, 0),
	]))
	depot.start_all_convoys(pl)

	start_pos = convoy.get_pos()
	built = true
	print("BKITSHOW: four cars on pak128 rail; now watching them move")
}


function watch()
{
	if (!built || convoy == null) { return }
	polls++

	local now = convoy.get_pos()
	if (now.x != start_pos.x || now.y != start_pos.y) {
		result = "BKITSHOW_OK: the 4-car unit (M-R-R-M) is running on pak128 rail"
			+ " under pak128 catenary - moved from (" + start_pos.x + ","
			+ start_pos.y + ") to (" + now.x + "," + now.y + ")"
		print(result)
		built = false
		return
	}
	if (polls > 400) {
		result = "BKITSHOW_FAIL: the unit has not moved in " + polls + " steps"
		print(result)
		built = false
	}
}


function start()        { build_everything() }
function resume_game()  { build_everything() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Watch the Cercanias unit run on pak128 track.") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { watch(); return 0 }
