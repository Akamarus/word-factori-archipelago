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
    wf_probe_gate.context.room=string_repeat("d",64); wf_access_next_poll=0; wf_access_poll();
    record_test("quantity previous room does not grant limits",get_current_module_count("Rotate_cw")==0,"native_function");
    with(clockwise) instance_destroy(); with(counterclockwise) instance_destroy();
}
