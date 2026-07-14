//
// The final proof: put the generated loco on an actual rail and drive it.
//
// The depot check (scenario "bkitcheck") proves the vehicle is BUYABLE. It
// cannot prove it is ALIGNED - a loco can be in the catalogue and still float
// above the rail or sink into it. So build a track, buy the thing, and run it.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: the generated loco, running"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_Switcher"

local result = "not started"


function build_demo()
{
	local pl = player_x(0)
	pl.book_cash(50000000)          // this is a showroom, not an economy test

	local loco = vehicle_desc_x(WANTED)
	if (loco == null) {
		result = "BKITDEMO_FAIL: no such vehicle: " + WANTED
		print(result)
		return
	}

	local rails = way_desc_x.get_available_ways(wt_rail, st_flat)
	rails.sort(@(a, b) b.get_topspeed() <=> a.get_topspeed())
	local rail = rails[0]

	// One long straight. The depot goes ON the last tile of it: the engine wants
	// depots on a flat DEAD-END way tile, not on bare ground beside the track.
	local err = command_x.build_way(pl, coord3d(4, 2, 0), coord3d(4, 14, 0), rail, true)
	if (err != null) {
		result = "BKITDEMO_FAIL: track: " + err
		print(result)
		return
	}

	// there is no get_available_depots(); filter the building list, as the
	// engine's own test helpers do (tests/test_helpers.nut get_depot_by_wt)
	local depot_desc = null
	foreach (b in building_desc_x.get_building_list(building_desc_x.depot)) {
		if (b.get_type() == building_desc_x.depot && b.get_waytype() == wt_rail) {
			depot_desc = b
			break
		}
	}
	if (depot_desc == null) {
		result = "BKITDEMO_FAIL: no rail depot in this pakset"
		print(result)
		return
	}

	err = command_x.build_depot(pl, coord3d(4, 14, 0), depot_desc)
	if (err != null) {
		result = "BKITDEMO_FAIL: depot: " + err
		print(result)
		return
	}

	local depot = depot_x(4, 14, 0)
	depot.append_vehicle(pl, convoy_x(0), loco)
	local cnv = depot.get_convoy_list()[0]
	// create_simple_schedule() is a test-harness helper, not part of the API -
	// build the schedule directly (schedule_entry_x is pos, min load, wait)
	cnv.change_schedule(pl, schedule_x(wt_rail, [
		schedule_entry_x(coord3d(4, 2, 0), 0, 0),
		schedule_entry_x(coord3d(4, 13, 0), 0, 0),
	]))
	depot.start_all_convoys(pl)

	result = "BKITDEMO_OK: " + WANTED + " is running between (4,2) and (4,13)"
	print(result)
	print("BKITDEMO: track = " + rail.get_name() + ", depot = " + depot_desc.get_name())
}


function start()        { build_demo() }
function resume_game()  { build_demo() }

function get_rule_text(pl)   { return ttext("Watch the loco.") }
function get_goal_text(pl)   { return ttext("Does it sit on the rail?") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
