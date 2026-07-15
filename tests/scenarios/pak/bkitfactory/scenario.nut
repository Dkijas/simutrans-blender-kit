//
// Does the generated factory load, with its good resolved?
//
// A factory is a building plus economics, and each good it makes or consumes is
// a cross-reference: makeobj compiles it unresolved and the GAME fatals at load
// on a good it cannot find (Kohle must be a real pakset good). The engine's own
// factory table, keyed by name, is the proof it loaded - the industry generator
// builds the toolbar and the maps from that list.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: does the generated factory load?"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_Mine"

local result = "not run"


function check_factory()
{
	local list = factory_desc_x.get_list()
	local total = 0
	local found = false

	foreach (name, desc in list) {
		total++
		if (name == WANTED) {
			found = true
		}
	}

	print("BKITFACTORY: factory types = " + total)

	if (!found) {
		result = "BKITFACTORY_FAIL: " + WANTED + " is NOT in the factory list"
			+ " - a good may not have resolved"
	}
	else {
		result = "BKITFACTORY_OK: " + WANTED + " loaded"
	}
	print(result)
}


function start()        { check_factory() }
function resume_game()  { check_factory() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("none") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
