//
// Is the generated building REAL?
//
// Not "did the .pak compile" - makeobj compiles broken .dats happily. And not
// "is it in a list" either: city houses are not in the scripted catalogue at all.
// hausbauer_t::get_list() returns NULL for city_res (builder/hausbauer.cc:1006);
// they live in a separate get_citybuilding_list() that the API never exposes. Ask
// it that way and you get an empty list even for pak64's own houses - which is
// exactly the false negative that sent us looking.
//
// So do the strongest thing the engine allows: BUILD IT ON THE MAP with the
// engine's own tool, then ask the tile what is standing there.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: plant the generated house"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WANTED <- "BKit_House"
local result = "not run"


function plant_house()
{
	local public_pl = player_x(1)

	local desc = building_desc_x(WANTED)
	if (desc == null) {
		result = "BKITHOUSE_FAIL: the engine has no building called " + WANTED
		print(result)
		return
	}

	// a city house needs a city to belong to
	local err = command_x(tool_add_city).work(public_pl, coord3d(8, 8, 0), "0")
	if (err != null) {
		result = "BKITHOUSE_FAIL: could not found a city: " + err
		print(result)
		return
	}

	// "11" is the rotation/layout prefix the tool expects - same as the engine's
	// own tests do it (tests/tests/test_building.nut)
	err = command_x(tool_build_house).work(public_pl, coord3d(2, 2, 0),
	                                       "11" + desc.get_name())
	if (err != null) {
		result = "BKITHOUSE_FAIL: could not build it: " + err
		print(result)
		return
	}

	local b = building_x(2, 2, 0)
	if (b == null) {
		result = "BKITHOUSE_FAIL: nothing is standing on (2,2)"
		print(result)
		return
	}

	local got = b.get_desc()
	if (got.get_name() != WANTED) {
		result = "BKITHOUSE_FAIL: built " + got.get_name() + ", expected " + WANTED
		print(result)
		return
	}

	local size = desc.get_size(0)
	result = "BKITHOUSE_OK: " + got.get_name() + " is standing at (2,2)"
		+ " size=" + size.x + "x" + size.y
		+ " capacity=" + desc.get_capacity()
	print(result)
}


function start()        { plant_house() }
function resume_game()  { plant_house() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Look at the house on (2,2).") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
