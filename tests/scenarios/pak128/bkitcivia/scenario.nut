//
// THE CIVIA, RUNNING NEXT TO A PAK128 TRAIN, ON PURPOSE.
//
// Scale is the one thing a render cannot tell you. A sprite that looks right on
// its own can be a head taller than everything else in the pakset, and you only
// find out when it stands next to somebody else's coach. So: two electrified
// tracks side by side, our unit on one, a pak128 train on the other, both
// running, and a screenshot decides.
//
// Two lessons are baked in here, both of them mine and both of them paid for:
//
//   * the tool calls are QUEUED, not executed where you write them. Reading a
//     convoy's car count on the next line gives you the count from before your
//     appends landed - which is how I got told a three-car unit had four cars.
//     So nothing is asserted at build time; the watcher checks later.
//
//   * a schedule whose two stops are adjacent tiles leaves the train sitting in
//     the depot forever, which looks exactly like "the vehicle is broken".
//

map.file = "empty-16x16.sve"

scenario.short_description = "Blender Kit: Civia beside a pak128 train"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

DRIVER <- "CiviaA1"
CENTRE <- "CiviaA3"

local result = "not run"
local ours = null
local theirs = null
local their_name = "?"
local polls = 0
local watching = false
local built_once = false


function bad(err) { return (typeof err == "string") && err != "" }
function fail(why) { result = "BKITCIVIA_FAIL: " + why; print(result); watching = false }


// The engine calls BOTH start() and resume_game(), and it calls them more than
// once. Without this latch the whole thing is built again and again, and every
// pass couples another set of cars onto the convoys that are already there:
// pak128's train ended up 12 cars long and ours 4, because the Civia's coupling
// constraints refused most of the extras and the ACE3, having none, accepted all
// of them. THAT is why nothing ever left the depot.
function build_everything()
{
	if (built_once) { return }
	built_once = true

	local pl = player_x(0)
	// book_cash() is in CENTS. 300000000 looked like plenty and is three million
	// euros, which a 400 km/h track, two depots and a heavy pak128 electric ate
	// whole - the account went to -2.5M, and a bankrupt player cannot start a
	// convoy. Both trains sat in their depots and neither of them was broken.
	pl.book_cash(100000000000)

	local rails = way_desc_x.get_available_ways(wt_rail, st_flat)
	if (rails.len() == 0) { return fail("no rail") }
	rails.sort(@(a, b) b.get_topspeed() <=> a.get_topspeed())
	local rail = rails[0]

	local wire = null
	foreach (w in wayobj_desc_x.get_available_wayobjs(wt_rail)) {
		if (w.get_waytype() == wt_rail) { wire = w }
	}
	if (wire == null) { return fail("no catenary") }

	local depot_desc = null
	foreach (b in building_desc_x.get_building_list(building_desc_x.depot)) {
		if (b.get_waytype() == wt_rail) { depot_desc = b; break }
	}
	if (depot_desc == null) { return fail("no rail depot") }

	// pak128's own powered passenger stock - pick one to stand next to
	// A commuter unit deserves a commuter unit to stand next to. The ACE3-407 is
	// pak128's first hit and it is a 687-tonne heavyweight that would not even
	// leave the depot, so pick something of the same kind as ours: an EMU with a
	// cab, passengers, and enough power per tonne to actually move.
	local theirs_desc = null
	local fallback = null
	foreach (v in vehicle_desc_x.get_available_vehicles(wt_rail)) {
		if (v.get_power() <= 0 || v.get_capacity() <= 0) { continue }
		local n = v.get_name()
		if (n == DRIVER || n == "BKitCercaniasM") { continue }
		if (fallback == null) { fallback = v }
		// get_weight() is in KILOGRAMS, not tonnes. A filter of "<= 60" matches
		// nothing at all and quietly leaves you comparing against a 320 km/h
		// express - which is not what a Cercanias unit should be measured beside.
		if (v.get_weight() <= 50000 && v.get_topspeed() <= 200) {
			theirs_desc = v
			break
		}
	}
	if (theirs_desc == null) { theirs_desc = fallback }
	if (theirs_desc == null) { return fail("pak128 has no powered passenger vehicle") }
	their_name = theirs_desc.get_name()
	print("BKITCIVIA: comparing against pak128's " + their_name)

	local a1 = vehicle_desc_x(DRIVER)
	local a3 = vehicle_desc_x(CENTRE)
	if (a1 == null || a3 == null) { return fail("the Civia is not in the pakset") }

	// row 7 = ours, row 9 = theirs. Same track, same wire, same depot type.
	foreach (row in [7, 9]) {
		local err = command_x.build_way(pl, coord3d(2, row, 0), coord3d(14, row, 0),
		                                rail, true)
		if (bad(err)) { return fail("rail on row " + row + ": " + err) }
		err = command_x.build_wayobj(pl, coord3d(2, row, 0), coord3d(14, row, 0), wire)
		if (bad(err)) { return fail("wire on row " + row + ": " + err) }
		err = command_x.build_depot(pl, coord3d(2, row, 0), depot_desc)
		if (bad(err)) { return fail("depot on row " + row + ": " + err) }
	}

	// THE DEPOT COMPLETES THE UNIT FOR YOU (tool/simtool.cc, case 'a'): when the
	// vehicle you append has exactly ONE possible successor, it appends that too,
	// and follows the chain to the end. So A1 + A3 is not two cars, it is the
	// whole A1-A3-A2 unit: A3's only successor is a driving car. Ask for three and
	// you get four. Everything I built on top of "one call, one car" was wrong.
	local d_ours = depot_x(2, 7, 0)
	d_ours.append_vehicle(pl, convoy_x(0), a1)
	ours = d_ours.get_convoy_list()[0]
	d_ours.append_vehicle(pl, ours, a3)
	ours.change_schedule(pl, schedule_x(wt_rail, [
		schedule_entry_x(coord3d(5, 7, 0), 0, 0),
		schedule_entry_x(coord3d(13, 7, 0), 0, 0),
	]))
	d_ours.start_all_convoys(pl)

	// pak128's ACE3-407 is a fixed unit for the same reason: one append, four cars
	local d_theirs = depot_x(2, 9, 0)
	d_theirs.append_vehicle(pl, convoy_x(0), theirs_desc)
	theirs = d_theirs.get_convoy_list()[0]
	theirs.change_schedule(pl, schedule_x(wt_rail, [
		schedule_entry_x(coord3d(5, 9, 0), 0, 0),
		schedule_entry_x(coord3d(13, 9, 0), 0, 0),
	]))
	d_theirs.start_all_convoys(pl)

	watching = true
	print("BKITCIVIA: both trains bought and started")
}


// Tool calls are QUEUED. Calling start_all_convoys() on the line after
// change_schedule() starts a convoy that does not have its schedule yet, and a
// convoy with no schedule simply stays in the depot - which reads, from the
// outside, exactly like "your vehicle is broken". So: start them a few game
// steps later, from here, once the queue has certainly drained. Both trains sat
// in their depots until I did this, pak128's own included, which is what told me
// the fault was mine and not the Civia's.
function watch()
{
	if (!watching || ours == null || theirs == null) { return }
	polls++

	if (polls == 20) {
		print("BKITCIVIA: ours = " + ours.get_vehicles().len() + " cars at speed "
		      + ours.get_speed() + " | theirs = " + theirs.get_vehicles().len()
		      + " cars at speed " + theirs.get_speed())
	}

	local a = ours.get_pos()
	local b = theirs.get_pos()
	// both have to be OUT of their depot at (2,row) and on the open track
	if (a.x > 3 && b.x > 3) {
		result = "BKITCIVIA_OK: our " + ours.get_vehicles().len() + "-car Civia at ("
			+ a.x + "," + a.y + "), pak128's " + their_name + " ("
			+ theirs.get_vehicles().len() + " cars) at (" + b.x + "," + b.y
			+ ") - both on the open track, compare them"
		print(result)
		watching = false
		return
	}
	if (polls > 400) {
		result = "BKITCIVIA_FAIL: after " + polls + " steps ours is at (" + a.x + ","
			+ a.y + ") and theirs at (" + b.x + "," + b.y + ") - somebody never"
			+ " left the depot"
		print(result)
		watching = false
	}
}


function start()        { build_everything() }
function resume_game()  { build_everything() }

function get_rule_text(pl)   { return ttext("none") }
function get_goal_text(pl)   { return ttext("Compare the two trains.") }
function get_info_text(pl)   { return ttext(result) }
function get_result_text(pl) { return ttext(result) }
function is_tool_allowed(pl, tool_id, wt, name) { return true }
function is_scenario_completed(pl) { watch(); return 0 }
