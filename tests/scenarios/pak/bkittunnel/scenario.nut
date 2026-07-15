//
// Does the generated tunnel load, and can it be built?
//
// A tunnel with a portal image but no icon loads and lists nowhere - the same
// 'no icon, no builder' rule as a way (builder/tunnelbauer.cc). So the real test
// is not "did the .pak load" but "is it in the tunnel builder's list", which is
// the list the toolbar is built from. This asks the engine for the available
// rail tunnels and looks for ours.
//
// This confirms the tunnel is BUILDABLE. Which portal image the engine draws on
// which hill (tunnels.PORTAL_TURNS) is a visual question a headless run cannot
// answer - that is confirmed by eye in a windowed game.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: is the generated tunnel buildable?"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_Tunnel"

local result = "not run"


function check_tunnel()
{
	local found = null
	local total = 0

	foreach (t in tunnel_desc_x.get_available_tunnels(wt_rail)) {
		total++
		if (t.get_name() == WANTED) {
			found = t
		}
	}

	print("BKITTUNNEL: rail tunnels available = " + total)

	if (found == null) {
		result = "BKITTUNNEL_FAIL: " + WANTED + " is NOT in the tunnel builder list"
	}
	else {
		result = "BKITTUNNEL_OK: " + WANTED + " is buildable (topspeed="
			+ found.get_topspeed() + ")"
	}
	print(result)
}


function start()        { check_tunnel() }
function resume_game()  { check_tunnel() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("none") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
