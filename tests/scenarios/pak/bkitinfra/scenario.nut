//
// Does the catenary actually electrify, and can the signal actually be placed?
//
// The Blender test proved the images are in the right lists and the aspects are
// the right way round. It cannot prove the engine AGREES that this thing is
// catenary at all - that depends on own_waytype, on the icon that gives it a build
// tool, and on the type name being "way-object" and not "way_obj". None of those
// are visible in a picture.
//
// So lay a rail, hang the wire on it, and ask the way itself:
//
//     way_x::is_electrified()
//
// That single call is what an electric locomotive asks before it will move. If it
// says false, the catenary is decoration.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: hang the catenary, plant the signal"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

WIRE   <- "BKit_Catenary"
SIGNAL <- "BKit_Signal"
local result = "not run"


function find_way(wt)
{
	local list = way_desc_x.get_available_ways(wt, st_flat)
	if (list.len() == 0) {
		return null
	}
	return list[0]
}


function lay_infra()
{
	local pl = player_x(0)

	// --- a rail to hang things on ------------------------------------------
	local rail = find_way(wt_rail)
	if (rail == null) {
		result = "BKITINFRA_FAIL: the pakset has no buildable rail at all"
		print(result)
		return
	}
	local err = command_x.build_way(pl, coord3d(2, 2, 0), coord3d(9, 2, 0), rail, true)
	if (err != null && err != "") {
		result = "BKITINFRA_FAIL: could not lay the rail: " + err
		print(result)
		return
	}

	// --- the catenary ------------------------------------------------------
	local wire = wayobj_desc_x(WIRE)
	if (wire == null) {
		result = "BKITINFRA_FAIL: the engine has no wayobj called " + WIRE
		print(result)
		return
	}

	local before = tile_x(5, 2, 0).get_way(wt_rail).is_electrified()
	if (before) {
		result = "BKITINFRA_FAIL: the bare rail claims to be electrified already"
			+ " - this test would prove nothing"
		print(result)
		return
	}

	err = command_x.build_wayobj(pl, coord3d(2, 2, 0), coord3d(9, 2, 0), wire)
	if (err != null && err != "") {
		result = "BKITINFRA_FAIL: could not hang the catenary: " + err
		print(result)
		return
	}

	// THE ORACLE. This is the call an electric loco makes before it will move.
	if (!tile_x(5, 2, 0).get_way(wt_rail).is_electrified()) {
		result = "BKITINFRA_FAIL: the wire is up but the rail is NOT electrified"
			+ " - own_waytype is wrong, and the catenary is decoration"
		print(result)
		return
	}

	// --- the signal --------------------------------------------------------
	// The scripting class is sign_desc_x. The C++ class is roadsign_desc_t and the
	// .dat type is obj=roadsign - three layers, three names. Guessing does not work
	// here; reading api_obj_desc.cc:802 does.
	local mine = null
	foreach (s in sign_desc_x.get_available_signs(wt_rail)) {
		if (s.get_name() == SIGNAL) {
			mine = s
		}
	}
	if (mine == null) {
		result = "BKITINFRA_FAIL: " + SIGNAL + " is not in the engine's list of"
			+ " buildable rail signs - no icon means no build tool"
		print(result)
		return
	}

	err = command_x(tool_build_roadsign).work(pl, coord3d(5, 2, 0), SIGNAL)
	if (err != null && err != "") {
		result = "BKITINFRA_FAIL: could not plant the signal: " + err
		print(result)
		return
	}

	local sign = sign_x(5, 2, 0)
	if (sign == null || !sign.is_valid()) {
		result = "BKITINFRA_FAIL: nothing standing on (5,2) after building the signal"
		print(result)
		return
	}
	if (sign.get_desc().get_name() != SIGNAL) {
		result = "BKITINFRA_FAIL: planted " + sign.get_desc().get_name()
			+ ", expected " + SIGNAL
		print(result)
		return
	}

	result = "BKITINFRA_OK: " + WIRE + " electrifies the rail, and " + SIGNAL
		+ " is standing on (5,2)"
	print(result)
}


function start()        { lay_infra() }
function resume_game()  { lay_infra() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Look at the electrified line.") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
