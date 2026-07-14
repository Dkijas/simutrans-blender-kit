map.file = "empty-16x16.sve"
scenario.short_description = "what lengths do pak128's own multiple units use?"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"
local result = "not run"
function report()
{
	local out = ""
	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		local n = v.get_name()
		if (n.find("ACE3") != null || n.find("Thunder") != null
		    || n.find("BR-373") != null || n.find("2000_Class") != null
		    || n.find("620_Railcar") != null) {
			out += n + "=" + v.get_length() + "  "
		}
	}
	result = "PAKLEN: " + out
	print(result)
}
function start()        { report() }
function resume_game()  { report() }
function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("none") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { return 100 }
