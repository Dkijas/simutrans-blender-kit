//
// ONE OBJECT OF EVERY TYPE, IN ONE RUNNING GAME.
//
// Each of the five has its own test elsewhere. This one is different: it makes them
// depend on each other, so that no single piece can pass by being lucky.
//
// The locomotive is ELECTRIC. An electric loco will not move a metre on
// unelectrified track. So if the convoy covers ground, then:
//
//     the catenary really is catenary   (own_waytype, and the wayobj type name)
//     the loco really is a loco         (the vehicle desc, the depot list)
//     and the rail underneath is really electrified
//
// all at once, and none of it can be faked by an image that merely looks right.
//
// The negative control matters as much as the positive one: a SECOND stretch of
// rail is left bare, and it must come back NOT electrified. Without that, a bug
// that reported every way as electrified would sail straight through.
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: one object of every type, together"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

LOCO     <- "BKitAll_Loco"
HOUSE    <- "BKitAll_House"
ROAD     <- "BKitAll_Road"
CATENARY <- "BKitAll_Catenary"
SIGNAL   <- "BKitAll_Signal"

RIBI_NAME <- ["-", "n", "e", "ne", "s", "ns", "se", "nse",
              "w", "nw", "ew", "new", "sw", "nsw", "sew", "nsew"]

local result = "not run"
local convoy = null
local start_pos = null
local polls = 0
local built = false


function fail(why)
{
	result = "BKITALL_FAIL: " + why
	print(result)
	built = false
}


function build_everything()
{
	local pl = player_x(0)
	pl.book_cash(50000000)          // a showroom, not an economy test

	// ---------------------------------------------------------------- 1. the road
	local road = null
	foreach (w in way_desc_x.get_available_ways(wt_road, st_flat)) {
		if (w.get_name() == ROAD) { road = w }
	}
	if (road == null) { return fail(ROAD + " is not a buildable road") }

	local err = command_x.build_way(pl, coord3d(2, 2, 0), coord3d(6, 2, 0), road, true)
	if (err != null && err != "") { return fail("laying the road: " + err) }
	err = command_x.build_way(pl, coord3d(6, 2, 0), coord3d(6, 5, 0), road, true)
	if (err != null && err != "") { return fail("the second leg: " + err) }

	// the engine's own ribi, at the corner: it meets (5,2) to the west and (6,3)
	// to the south, so 8|4 = 12
	local got = tile_x(6, 2, 0).get_way_dirs(wt_road)
	if (got != 12) {
		return fail("the road corner at (6,2) has ribi " + got + " (" + RIBI_NAME[got]
		            + "), expected 12 (sw) - north/east/south/west is wrong")
	}

	// ---------------------------------------------------------------- 2. the rail
	local rails = way_desc_x.get_available_ways(wt_rail, st_flat)
	if (rails.len() == 0) { return fail("the pakset has no rail at all") }
	rails.sort(@(a, b) b.get_topspeed() <=> a.get_topspeed())
	local rail = rails[0]

	err = command_x.build_way(pl, coord3d(3, 8, 0), coord3d(13, 8, 0), rail, true)
	if (err != null && err != "") { return fail("laying the rail: " + err) }

	// THE NEGATIVE CONTROL: a second stretch that we deliberately leave bare
	err = command_x.build_way(pl, coord3d(3, 12, 0), coord3d(8, 12, 0), rail, true)
	if (err != null && err != "") { return fail("the bare rail: " + err) }

	// ------------------------------------------------------------ 3. the catenary
	local wire = wayobj_desc_x(CATENARY)
	if (wire == null) { return fail("the engine has no wayobj called " + CATENARY) }

	if (tile_x(6, 8, 0).get_way(wt_rail).is_electrified()) {
		return fail("the bare rail claims to be electrified BEFORE the wire went up"
		            + " - this test would prove nothing")
	}

	err = command_x.build_wayobj(pl, coord3d(3, 8, 0), coord3d(13, 8, 0), wire)
	if (err != null && err != "") { return fail("hanging the catenary: " + err) }

	if (!tile_x(6, 8, 0).get_way(wt_rail).is_electrified()) {
		return fail("the wire is up but the rail is NOT electrified - own_waytype is"
		            + " wrong, and the catenary is decoration")
	}
	if (tile_x(6, 12, 0).get_way(wt_rail).is_electrified()) {
		return fail("the BARE rail also reports electrified - something is saying yes"
		            + " to everything, and the positive result means nothing")
	}

	// -------------------------------------------------------------- 4. the signal
	local sign = null
	foreach (s in sign_desc_x.get_available_signs(wt_rail)) {
		if (s.get_name() == SIGNAL) { sign = s }
	}
	if (sign == null) {
		return fail(SIGNAL + " is not in the engine's list of buildable rail signs"
		            + " - no icon means no build tool")
	}
	err = command_x(tool_build_roadsign).work(pl, coord3d(11, 8, 0), SIGNAL)
	if (err != null && err != "") { return fail("planting the signal: " + err) }
	if (!sign_x(11, 8, 0).is_valid()) {
		return fail("nothing standing on (11,8) after building the signal")
	}

	// --------------------------------------------------------------- 5. the house
	local house = building_desc_x(HOUSE)
	if (house == null) { return fail("the engine has no building called " + HOUSE) }

	local public_pl = player_x(1)
	err = command_x(tool_add_city).work(public_pl, coord3d(2, 14, 0), "0")
	if (err != null && err != "") { return fail("founding a city: " + err) }
	err = command_x(tool_build_house).work(public_pl, coord3d(1, 5, 0), "11" + HOUSE)
	if (err != null && err != "") { return fail("planting the house: " + err) }
	if (building_x(1, 5, 0) == null) {
		return fail("nothing standing on (1,5) after building the house")
	}

	// ---------------------------------------------- 6. the ELECTRIC loco, running
	local loco = vehicle_desc_x(LOCO)
	if (loco == null) { return fail("the engine has no vehicle called " + LOCO) }

	local in_depot_list = false
	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		if (v.get_name() == LOCO) { in_depot_list = true }
	}
	if (!in_depot_list) { return fail(LOCO + " is not in the depot list") }

	local depot_desc = null
	foreach (b in building_desc_x.get_building_list(building_desc_x.depot)) {
		if (b.get_type() == building_desc_x.depot && b.get_waytype() == wt_rail) {
			depot_desc = b
			break
		}
	}
	if (depot_desc == null) { return fail("no rail depot in this pakset") }

	err = command_x.build_depot(pl, coord3d(3, 8, 0), depot_desc)
	if (err != null && err != "") { return fail("the depot: " + err) }

	local depot = depot_x(3, 8, 0)
	depot.append_vehicle(pl, convoy_x(0), loco)
	convoy = depot.get_convoy_list()[0]
	convoy.change_schedule(pl, schedule_x(wt_rail, [
		schedule_entry_x(coord3d(4, 8, 0), 0, 0),
		schedule_entry_x(coord3d(10, 8, 0), 0, 0),
	]))
	depot.start_all_convoys(pl)

	start_pos = convoy.get_pos()
	built = true
	print("BKITALL: everything is built; now watching the electric loco move")
}


// The convoy has to actually COVER GROUND. Starting it is not the same as moving:
// an electric loco with no power sits in the depot doing nothing at all, and a test
// that stops at start_all_convoys() would call that a pass.
function watch()
{
	if (!built || convoy == null) {
		return
	}
	polls++

	local now = convoy.get_pos()
	if (now.x != start_pos.x || now.y != start_pos.y) {
		result = "BKITALL_OK: road ribi ok, catenary electrifies (bare rail does not),"
			+ " signal planted, house standing, and the ELECTRIC " + LOCO
			+ " has moved from (" + start_pos.x + "," + start_pos.y + ") to ("
			+ now.x + "," + now.y + ") - so the wire really is carrying it"
		print(result)
		built = false
		return
	}

	if (polls > 400) {
		result = "BKITALL_FAIL: the electric loco has not moved in " + polls
			+ " steps. It is on the wire, so either the catenary does not really"
			+ " electrify or the loco has no power."
		print(result)
		built = false
	}
}


function start()        { build_everything() }
function resume_game()  { build_everything() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Watch the electric loco.") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }

function is_scenario_completed(pl) { watch(); return 0 }
