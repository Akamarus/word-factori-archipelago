// Appended to the isolated native enforcement gate. Reuses real VV factory.
var qcontext=clone(context); qcontext.schema=3; qcontext.capability="progressive_machine_enforcement_v1";
record_test("quantity context supported",wf_access_context_valid(qcontext),"native_function");
if(wf_access_context_valid(qcontext)) {
    wf_probe_gate.context=clone(qcontext); wf_probe_gate.payload=clone(qcontext);
    wf_probe_gate.payload.revision=100;
    wf_probe_gate.payload.levels=[{text:"VV",module_counts:{}}];
    wf_probe_gate.payload.machine_counts={Bend:1,Rotate_cw:2,Rotate_ccw:2,Reflect_hor:1,Reflect_vert:1,Merger2:1,Merger3:0,Merger4:0,IFactory:-1};
    wf_access_last=undefined; enter_probe();
    record_test("quantity source always unlimited",get_current_module_count("IFactory")==-1,"native_function");
    record_test("import over allowance blocks placement",get_current_module_count("Merger2")==0,"native_function");
    var qslot={}; variable_struct_set(identity.save_data.slots,"0",qslot);
    goal.counts=[0,0]; goal.num_words_completed=0; control.win_stats=undefined; control.win_already_triggered=false;
    for(var qt=0;qt<50;qt++) {control.doTick();control.try_win_condition();}
    record_test("over-limit imported factory cannot produce",goal.num_words_completed==0 && !isLevelBeaten("VV"),"native_production");
    record_test("over-limit explains family and placed counts",variable_instance_exists(oPersistent,"wf_probe_notice") && string_pos("Merger2 2/1",wf_probe_notice)>0,"native_function");
    record_test("over-limit imported layout preserved",control.buildings[2]==graph[2] && instance_number(oMerger2)==2,"native_production");
    wf_probe_gate.payload.revision=101; wf_probe_gate.payload.machine_counts.Merger2=2;
    wf_access_next_poll=0;
    for(var qt=0;qt<150 && !control.win_already_triggered;qt++) {control.doTick();control.try_win_condition();}
    record_test("live tier applies without setLevel",wf_access_last.revision==101 && goal.num_words_completed==10 && isLevelBeaten("VV"),"native_production");
    // A ready-to-award buffered win must not bypass a reduced allowance.
    variable_struct_set(identity.save_data.slots,"0",{}); control.win_already_triggered=false;
    wf_probe_gate.payload.revision=102; wf_probe_gate.payload.machine_counts.Merger2=1; wf_access_next_poll=0;
    control.try_win_condition();
    record_test("over-limit buffered win blocked",!isLevelBeaten("VV") && !control.win_already_triggered,"native_production");
    wf_probe_gate.payload.revision=103; wf_probe_gate.payload.machine_counts.Merger2=2; wf_access_next_poll=0;
    wf_access_poll();
    var clockwise=instance_create_depth(0,0,0,oRotate); clockwise.is_temp_initial=false; clockwise.state=1; clockwise.building=new Building(oRotate,"cw");
    var counterclockwise=instance_create_depth(0,0,0,oRotate); counterclockwise.is_temp_initial=false; counterclockwise.state=0; counterclockwise.building=new Building(oRotate,"ccw");
    record_test("two directions share two rotation slots",get_current_module_count("Rotate_cw")==0 && get_current_module_count("Rotate_ccw")==0,"native_function");
    var third=instance_create_depth(0,0,0,oRotate); third.is_temp_initial=false; third.state=1; third.building=new Building(oRotate,"cw");
    record_test("third rotation makes imported scene invalid",!wf_access_factory_allowed(),"native_function");
    with(third) instance_destroy();
    record_test("deleting excess machine restores allowance",wf_access_factory_allowed(),"native_function");
    counterclockwise.is_temp_initial=true;
    record_test("placement ghost does not consume allowance",get_current_module_count("Rotate_cw")==1,"native_function");
    counterclockwise.is_temp_initial=false;
    levels[0].wf_ap_caps={Rotate_cw:0}; wf_probe_gate.payload.levels[0].module_counts={Rotate_cw:0};
    wf_probe_gate.payload.revision=104; wf_access_next_poll=0; setLevel("VV",0,1,false);
    record_test("challenge direction cap restricts scene",get_current_module_count("Rotate_cw")==0 && !wf_access_factory_allowed(),"native_function");
    levels[0].wf_ap_caps={}; wf_probe_gate.payload.levels[0].module_counts={};
    wf_probe_gate.payload.revision=105; enter_probe();
    wf_probe_gate.payload.revision=106; wf_probe_gate.payload.machine_counts.Rotate_cw=3; wf_access_next_poll=0; wf_access_poll();
    record_test("mismatched direction snapshot rejected",wf_access_last.revision==105,"native_function");
    wf_probe_gate.payload=undefined; wf_access_next_poll=0; wf_access_poll();
    record_test("quantity reconnect retains same-room snapshot",wf_access_last.revision==105,"native_function");
    var bad_counts=clone(wf_access_last.machine_counts);
    bad_counts.Bend=2.5;
    record_test("fractional quantity rejected",!wf_access_counts_valid(bad_counts,qcontext),"native_function");
    bad_counts.Bend=true;
    record_test("boolean quantity rejected",!wf_access_counts_valid(bad_counts,qcontext),"native_function");
    bad_counts.Bend=5;
    record_test("five must use unlimited sentinel",!wf_access_counts_valid(bad_counts,qcontext),"native_function");
    bad_counts.Bend=-1;
    record_test("unlimited sentinel accepted",wf_access_counts_valid(bad_counts,qcontext),"native_function");
    var horizontal=instance_create_depth(0,0,0,oReflect); horizontal.is_temp_initial=false; horizontal.state=0; horizontal.building=new Building(oReflect,"hor");
    var vertical=instance_create_depth(0,0,0,oReflect); vertical.is_temp_initial=false; vertical.state=1; vertical.building=new Building(oReflect,"vert");
    record_test("reflection directions share one allowance",!wf_access_factory_allowed() && get_current_module_count("Reflect_hor")==0 && get_current_module_count("Reflect_vert")==0,"native_function");
    wf_probe_gate.payload=clone(wf_access_last);
    wf_probe_gate.payload.revision=106;
    wf_probe_gate.payload.machine_counts.Reflect_hor=-1; wf_probe_gate.payload.machine_counts.Reflect_vert=-1;
    wf_access_next_poll=0; wf_access_poll();
    record_test("unlimited reflection accepts both directions",wf_access_factory_allowed() && get_current_module_count("Reflect_hor")==-1,"native_function");
    with(horizontal) instance_destroy(); with(vertical) instance_destroy();
    with(clockwise) instance_destroy(); with(counterclockwise) instance_destroy();
    // Real native ticks must audit once, regardless of the number of buildings
    // or production callbacks. Counter instrumentation exists only in this probe.
    var profile=[]; var profile_sizes=[16,64,128];
    for(var size_index=0;size_index<3;size_index++) {
        var size=profile_sizes[size_index];
        while(instance_number(oModule)<size) {
            var extra=instance_create_depth(0,0,0,oIFactory);
            extra.is_temp_initial=false; extra.building=new Building(oIFactory,"");
        }
        global.wf_probe_tick_scans=0;
        var tick_started=get_timer(); control.doTick();
        var tick_elapsed=get_timer()-tick_started;
        array_push(profile,{modules:instance_number(oModule),scans:global.wf_probe_tick_scans,microseconds:tick_elapsed});
        record_test("one scene audit for native tick with "+string(size)+" modules",global.wf_probe_tick_scans==1,"native_production");
        record_test("tick permissions cleared after production "+string(size),is_undefined(global.wf_access_tick_grants),"native_production");
    }
    snapshot("tick_scope_profile",profile);
    var actual_tick=control.wf_access_native_tick;
    control.wf_access_native_tick=method(control,function() {
        if(!wf_access_allowed(oIFactory,"") || wf_access_allowed(oMerger4,"") || wf_access_allowed(oCustomBuilding,"")) throw "incorrect tick grants";
        return 7;
    });
    record_test("native early return preserved and scope cleared",control.doTick()==7 && is_undefined(global.wf_access_tick_grants),"native_function");
    control.wf_access_native_tick=method(control,function() { throw "intentional tick failure"; });
    var caught_tick=false;
    try {control.doTick();} catch(tick_error) { caught_tick=tick_error=="intentional tick failure"; }
    record_test("native error rethrown and scope cleared",caught_tick && is_undefined(global.wf_access_tick_grants),"native_function");
    control.wf_access_native_tick=actual_tick;
    // A new placement is checked immediately outside the scope and next tick.
    var excess=instance_create_depth(0,0,0,oMerger2); excess.is_temp_initial=false; excess.building=new Building(oMerger2,"");
    var before_cycle=control.cycle_count;
    control.doTick();
    record_test("placement after tick invalidates production and preview",control.cycle_count==before_cycle && !wf_access_allowed(oIFactory,"") && is_undefined(global.wf_access_tick_grants),"native_production");
    with(excess) instance_destroy();
    wf_probe_gate.payload.revision=107; wf_probe_gate.payload.machine_counts.Merger2=1; wf_access_next_poll=0;
    control.doTick();
    record_test("next tick honors changed received allowances",control.cycle_count==before_cycle && is_undefined(global.wf_access_tick_grants),"native_production");
    wf_probe_gate.payload.revision=108; wf_probe_gate.payload.machine_counts.Merger2=2; wf_access_next_poll=0;
    control.doTick();
    record_test("later upgrade resumes production without reload",control.cycle_count==before_cycle+1,"native_production");
    wf_probe_gate.context.room=string_repeat("d",64); wf_access_next_poll=0; wf_access_poll();
    record_test("quantity previous room does not grant limits",get_current_module_count("Rotate_cw")==0,"native_function");
}
