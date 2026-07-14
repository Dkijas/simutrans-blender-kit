//
// Does the engine actually OFFER the vehicle we generated?
//
// A .pak that loads without a fatal error is not the same thing as a vehicle a
// player can buy. This asks the engine's own catalogue - the very list the
// depot dialog is built from - and prints the answer to the log.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: is the generated vehicle available?"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_Switcher"

local result = "not run"


function check_vehicle()
{
	local found = null
	local total = 0

	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		total++
		if (v.get_name() == WANTED) {
			found = v
		}
	}

	print("BKITCHECK: rail vehicles available = " + total)

	if (found == null) {
		result = "BKITCHECK_FAIL: " + WANTED + " is NOT in the depot list"
	}
	else {
		// get_power() is power*gear*64, so undo the gear/64 to print real kW
		result = "BKITCHECK_OK: " + WANTED
			+ " topspeed=" + found.get_topspeed()
			+ " power_raw=" + found.get_power()
	}
	print(result)
}


function start()        { check_vehicle() }
function resume_game()  { check_vehicle() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("none") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
