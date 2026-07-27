//
// SCREENSHOT DRIVER for the Stadler FLIRT RABe 523 (SBB) on pak128.
//
// Builds a real scene (electrified line + station + depot), assembles the four-car
// unit with one click, runs it, and drives the TEST-ONLY engine hooks
// debug.center_view() / debug.take_screenshot() so the game photographs itself.
// PNGs land in <user_dir>/screenshot/simscrNN.png. This scenario is scaffolding,
// not part of the delivered addon.
//

map.file = "empty-16x16.sve"

scenario.short_description = "FLIRT RABe 523 screenshot driver"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

CAB_A <- "SBB_FLIRT_RABe523_A"

local result = "not run"
local convoy = null
local polls = 0
local shots = 0
local built = false
local station_pos = null


function bad(err) { return (typeof err == "string") && err != "" }

function build_everything()
{
	if (built) { return }
	built = true

	local pl = player_x(0)
	pl.book_cash(100000000000)

	local rails = way_desc_x.get_available_ways(wt_rail, st_flat)
	rails.sort(@(a, b) b.get_topspeed() <=> a.get_topspeed())
	local rail = rails[0]

	local wire = null
	foreach (w in wayobj_desc_x.get_available_wayobjs(wt_rail)) {
		if (w.get_waytype() == wt_rail) { wire = w }
	}

	local depot_desc = null
	foreach (b in building_desc_x.get_building_list(building_desc_x.depot)) {
		if (b.get_waytype() == wt_rail) { depot_desc = b; break }
	}

	// a straight run across the map, then a diagonal - both wired
	command_x.build_way(pl, coord3d(1, 8, 0), coord3d(12, 8, 0), rail, true)
	command_x.build_way(pl, coord3d(12, 8, 0), coord3d(14, 6, 0), rail, true)
	command_x.build_wayobj(pl, coord3d(1, 8, 0), coord3d(12, 8, 0), wire)
	command_x.build_wayobj(pl, coord3d(12, 8, 0), coord3d(14, 6, 0), wire)
	command_x.build_depot(pl, coord3d(1, 8, 0), depot_desc)

	// a station on the line, so we get a "stopped at a platform" frame
	local stop = null
	foreach (b in building_desc_x.get_building_list(building_desc_x.station)) {
		if (b.get_waytype() == wt_rail) { stop = b; break }
	}
	if (stop != null) {
		command_x.build_station(pl, coord3d(8, 8, 0), stop)
		command_x.build_station(pl, coord3d(9, 8, 0), stop)
		station_pos = coord3d(8, 8, 0)
	}

	local cab = null
	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		if (v.get_name() == CAB_A) { cab = v }
	}

	local depot = depot_x(1, 8, 0)
	depot.append_vehicle(pl, convoy_x(0), cab)
	convoy = depot.get_convoy_list()[0]
	local sched = [ schedule_entry_x(coord3d(8, 8, 0), 0, 0),
	                schedule_entry_x(coord3d(14, 6, 0), 0, 0) ]
	convoy.change_schedule(pl, schedule_x(wt_rail, sched))
	depot.start_all_convoys(pl)

	result = "FLIRTSHOTS: scene built, driving the camera"
	print(result)
}


// Center on the convoy and photograph. Kept one place so every shot is framed the
// same way.
function shoot(label)
{
	if (convoy == null) { return }
	local p = convoy.get_pos()
	debug.center_view(p.x, p.y)
	debug.take_screenshot()
	shots++
	print("FLIRTSHOT " + shots + ": " + label + " at (" + p.x + "," + p.y + ")")
}


function tick()
{
	if (!built) { return }
	polls++
	if (convoy == null) { return }

	// space the shots out along the run so the train is in a different place each time
	if (polls == 12)  { shoot("leaving the depot") }
	if (polls == 40)  { shoot("on the open line") }
	if (polls == 70)  { shoot("mid-line side view") }
	if (polls == 100) { shoot("approaching the station") }
	if (polls == 130) { shoot("at / near the station") }
	if (polls == 165) { shoot("on the diagonal") }
	if (polls == 200) { shoot("far end") }
	if (polls == 240) { shoot("header candidate") }

	// keep running so the in-game clock advances toward dusk/night, then shoot again
	if (polls == 500)  { shoot("evening") }
	if (polls == 750)  { shoot("dusk") }
	if (polls == 1000) { shoot("night") }
	if (polls == 1250) { shoot("late night") }

	if (polls == 1300) {
		result = "FLIRTSHOTS_OK: took " + shots + " screenshots"
		print(result)
	}
}


function start()        { build_everything() }
function resume_game()  { build_everything() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("FLIRT screenshot driver") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { tick(); return 0 }
