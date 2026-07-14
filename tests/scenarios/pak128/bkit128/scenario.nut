//
// Does pak128 actually offer the commuter unit we just installed as an addon?
//
// Not "does the .pak load" - a .pak can load and still be unbuyable. This asks
// the engine's own catalogue (the list the depot dialog is built from), and then
// asks the harder question: does the engine agree the two cars COUPLE? An EMU
// whose halves cannot be joined is not an EMU, and nothing about the sprites or
// the .dat would tell you.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: the commuter unit, in pak128"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

MOTOR   <- "BKitCercaniasM"
TRAILER <- "BKitCercaniasR"

local result = "not run"


function names_of(list)
{
	local out = []
	foreach (v in list) { out.append(v.get_name()) }
	return out
}

function has(list, name)
{
	foreach (n in list) { if (n == name) return true }
	return false
}


function check()
{
	local motor = null
	local trailer = null
	local total = 0

	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		total++
		if (v.get_name() == MOTOR)   { motor = v }
		if (v.get_name() == TRAILER) { trailer = v }
	}
	print("BKIT128: rail vehicles pak128 offers = " + total)

	if (motor == null || trailer == null) {
		result = "BKIT128_FAIL: unit not in the depot list (motor="
			+ (motor != null) + " trailer=" + (trailer != null) + ")"
		print(result)
		return
	}

	local m_next = names_of(motor.get_successors())
	local r_prev = names_of(trailer.get_predecessors())

	if (!motor.can_be_first()) {
		result = "BKIT128_FAIL: the motor car cannot lead the train"
	}
	else if (trailer.can_be_first()) {
		result = "BKIT128_FAIL: the trailer would lead the train"
	}
	else if (!has(m_next, TRAILER)) {
		result = "BKIT128_FAIL: the motor car will not pull the trailer"
	}
	else if (!has(r_prev, MOTOR)) {
		result = "BKIT128_FAIL: the trailer will not follow the motor car"
	}
	else if (trailer.get_power() != 0) {
		result = "BKIT128_FAIL: the trailer has an engine"
	}
	else {
		result = "BKIT128_OK: " + MOTOR + " leads, pulls " + TRAILER
			+ ", topspeed=" + motor.get_topspeed()
			+ ", motor power_raw=" + motor.get_power()
			+ ", trailer power=" + trailer.get_power()
			+ " (of " + total + " rail vehicles in the depot)"
	}
	print(result)
}


function start()        { check() }
function resume_game()  { check() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("none") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
