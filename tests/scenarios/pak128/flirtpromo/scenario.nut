//
// PROMO + CURVE-ARTICULATION driver for the FLIRT RABe 523 (SBB), pak128.
// Builds a compact scene (station with platforms, catenary, a straight, a diagonal
// and a 90-degree L-curve), zooms in, and photographs the unit via the TEST-ONLY
// hooks debug.center_view/zoom_in/take_screenshot (take_screenshot uses the display
// writer, so NO "screenshot saved" popup). Scaffolding, not part of the addon.
//

map.file = "empty-16x16.sve"
scenario.short_description = "FLIRT RABe 523 promo/curve driver"
scenario.author = "simutrans-blender-kit"
scenario.version = "1"

CAB_A <- "SBB_FLIRT_RABe523_A"

local result="not run"; local convoy=null; local polls=0; local shots=0; local built=false

function bad(e){ return (typeof e=="string") && e!="" }
function shoot(label){
    if(convoy==null) return
    local p=convoy.get_pos()
    debug.center_view(p.x,p.y); debug.take_screenshot(); shots++
    print("FLIRTPROMO "+shots+": "+label+" at ("+p.x+","+p.y+")")
}

function build_everything(){
    if(built) return
    built=true
    local pl=player_x(0); pl.book_cash(100000000000)
    local rails=way_desc_x.get_available_ways(wt_rail,st_flat)
    rails.sort(@(a,b) b.get_topspeed()<=>a.get_topspeed()); local rail=rails[0]
    local wire=null
    foreach(w in wayobj_desc_x.get_available_wayobjs(wt_rail)) if(w.get_waytype()==wt_rail) wire=w
    local depot_desc=null
    foreach(b in building_desc_x.get_building_list(building_desc_x.depot)) if(b.get_waytype()==wt_rail){ depot_desc=b; break }

    // straight (E-W), a diagonal, then a 90-degree L to the north-> exercises curves
    command_x.build_way(pl, coord3d(2,8,0), coord3d(10,8,0), rail, true)
    command_x.build_way(pl, coord3d(10,8,0), coord3d(13,5,0), rail, true)   // diagonal
    command_x.build_way(pl, coord3d(13,5,0), coord3d(13,2,0), rail, true)   // N-S (two 45 curves at the diagonal ends)
    command_x.build_way(pl, coord3d(2,8,0),  coord3d(2,12,0), rail, true)   // 90-degree L at (2,8)
    foreach(seg in [[coord3d(2,8,0),coord3d(10,8,0)],[coord3d(10,8,0),coord3d(13,5,0)],
                    [coord3d(13,5,0),coord3d(13,2,0)],[coord3d(2,8,0),coord3d(2,12,0)]])
        command_x.build_wayobj(pl, seg[0], seg[1], wire)

    // station platforms on the straight
    local stop=null
    foreach(b in building_desc_x.get_building_list(building_desc_x.station)) if(b.get_waytype()==wt_rail){ stop=b; break }
    if(stop!=null){ command_x.build_station(pl,coord3d(5,8,0),stop); command_x.build_station(pl,coord3d(6,8,0),stop); command_x.build_station(pl,coord3d(7,8,0),stop) }

    command_x.build_depot(pl, coord3d(2,12,0), depot_desc)
    local cab=null
    foreach(v in vehicle_desc_x.get_available_vehicles(wt_rail)) if(v.get_name()==CAB_A) cab=v
    local depot=depot_x(2,12,0)
    depot.append_vehicle(pl, convoy_x(0), cab)
    convoy=depot.get_convoy_list()[0]
    convoy.change_schedule(pl, schedule_x(wt_rail, [
        schedule_entry_x(coord3d(6,8,0),0,0), schedule_entry_x(coord3d(13,2,0),0,0) ]))
    depot.start_all_convoys(pl)
    debug.zoom_in(2)     // closer framing than v0.1
    result="FLIRTPROMO: scene built"; print(result)
}

function tick(){
    if(!built) return
    polls++
    if(convoy==null) return
    if(polls==18)  shoot("leaving depot / L-curve")
    if(polls==45)  shoot("on the straight (line)")
    if(polls==70)  shoot("at the station")
    if(polls==110) shoot("straight side view")
    if(polls==150) shoot("on the diagonal")
    if(polls==185) shoot("on the curve (articulation)")
    if(polls==220) shoot("curve exit")
    if(polls==260) shoot("header candidate")
    if(polls==650) shoot("evening")
    if(polls==1000) shoot("dusk/night")
    if(polls==1050){ result="FLIRTPROMO_OK: "+shots+" shots"; print(result) }
}

function start(){ build_everything() }
function resume_game(){ build_everything() }
function get_rule_text(pl){ return ttext("none") }
function get_goal_text(pl){ return ttext("FLIRT promo driver") }
function get_info_text(pl){ return ttext(result) }
function get_result_text(pl){ return ttext(result) }
function is_tool_allowed(pl,tool_id,wt,name){ return true }
function is_scenario_completed(pl){ tick(); return 0 }
