//
// Does the generated bridge load, and can it be built?
//
// A bridge with a span but no icon loads and lists nowhere - builder/
// brueckenbauer.cc has the way's 'no icon, no builder' rule, and makeobj does
// not warn. So the real test is the engine's own bridge list, the one the
// toolbar is built from: get_available_bridges for rail must contain ours.
//
// Which piece the engine draws on which slope (bridges.GROUP_TURNS) is a visual
// question a headless run cannot answer; that is confirmed by eye in a windowed
// game. This confirms the bridge is BUILDABLE.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: is the generated bridge buildable?"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_Bridge"

local result = "not run"


function check_bridge()
{
	local found = null
	local total = 0

	foreach (b in bridge_desc_x.get_available_bridges(wt_rail)) {
		total++
		if (b.get_name() == WANTED) {
			found = b
		}
	}

	print("BKITBRIDGE: rail bridges available = " + total)

	if (found == null) {
		result = "BKITBRIDGE_FAIL: " + WANTED + " is NOT in the bridge builder list"
	}
	else {
		result = "BKITBRIDGE_OK: " + WANTED + " is buildable (topspeed="
			+ found.get_topspeed() + ")"
	}
	print(result)
}


function start()        { check_bridge() }
function resume_game()  { check_bridge() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("none") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
