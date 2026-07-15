//
// Does the cargo-variant wagon really load, and is it buyable?
//
// A vehicle with freight images only loads if every freightimagetype[i]=<good>
// resolves to a real pakset good - the game reads them as cross-references and
// FATALs on one it cannot find (makeobj does not: it compiles the xref
// unresolved and leaves the failure for load time). So a BKit_Hopper that turns
// up in the depot list is proof that Kohle and Oel both resolved and the freight
// images came with it. It also reads back the wagon's own freight, which must be
// the Kohle we asked for.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: does the cargo-variant wagon load?"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_Hopper"

local result = "not run"


function check_hopper()
{
	local found = null
	local total = 0

	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		total++
		if (v.get_name() == WANTED) {
			found = v
		}
	}

	print("BKITHOPPER: rail vehicles available = " + total)

	if (found == null) {
		result = "BKITHOPPER_FAIL: " + WANTED + " is NOT in the depot list"
		print(result)
		return
	}

	local good = found.get_freight()
	local goodname = "none"
	if (good != null) {
		goodname = good.get_name()
	}

	if (goodname != "Kohle") {
		result = "BKITHOPPER_FAIL: " + WANTED + " carries " + goodname
	}
	else {
		result = "BKITHOPPER_OK: " + WANTED + " is buyable, freight=" + goodname
	}
	print(result)
}


function start()        { check_hopper() }
function resume_game()  { check_hopper() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("none") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
