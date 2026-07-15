//
// Does the generated station stop load, and can it be built?
//
// A stop is an obj=building with type=stop and a waytype - and, because a player
// builds it, an icon. Without the icon hausbauer.cc:235 gives it a NULL builder:
// it loads, lists nowhere, and cannot be placed, exactly the way rule. makeobj
// never warns. So the real test is the engine's own station list, the one the
// toolbar is built from: get_available_stations for rail must contain ours.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: is the generated stop buildable?"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_Stop"

local result = "not run"


function check_stop()
{
	local found = null
	local total = 0

	// building_desc_x.station is the generic stop; freight filters by what it
	// accepts, and ours enables passengers (parameter 3 may not be null)
	foreach (b in building_desc_x.get_available_stations(building_desc_x.station, wt_rail, good_desc_x.passenger)) {
		total++
		if (b.get_name() == WANTED) {
			found = b
		}
	}

	print("BKITSTOP: rail stations available = " + total)

	if (found == null) {
		result = "BKITSTOP_FAIL: " + WANTED + " is NOT in the station builder list"
			+ " - it may have loaded without an icon"
	}
	else {
		result = "BKITSTOP_OK: " + WANTED + " is buildable"
	}
	print(result)
}


function start()        { check_stop() }
function resume_game()  { check_stop() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("none") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
