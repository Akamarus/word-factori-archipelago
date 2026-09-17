// Real editor Step dispatch + native move/erase methods; deterministic inputs.
// doTick is a counter here, not proof of production output (see --factory).
function wf_editor_tests() {
    wf_mail_reset();
    physics_world_create(0.1);
    oInput.input_method_override=0;
    var identity=instance_create_depth(0,0,0,oIdentity);
    identity.current_save_slot=0; identity.save_data={slots:{}};
    variable_struct_set(identity.save_data.slots,"0",{dev_mode:false,laptop_mode:false});
    var toggle=instance_create_depth(0,0,0,oMenuToggle); toggle.state=3;
    var play=instance_create_depth(0,0,0,oPlay); play.input_name=65;
    var trash=instance_create_depth(0,0,0,oTrash); trash.hover=false;
    var pen=instance_create_depth(0,0,0,oPenWeight); pen.toss_mode=false;
    var control=instance_create_depth(0,0,0,oControl);
    var part=instance_create_depth(10,20,0,oIFactory);
    with(part) {
        move=function(xx,yy) { x=xx; y=yy; };
        getAnchorArray=function() { return []; };
        start_x=x; start_y=y;
        spawnPlaceAnim=function() { };
        isMini=function() { return false; };
    }
    control.dangling_insts=[{inst:part,offset_x:0,offset_y:0}];
    global.graph={refreshTiles:function() { },makeSnapshot:function() { oControl.wf_snapshots++; }};
    global.collision_table={getTiles:function(xx,yy) { return [{line:{
        highlight:function() { return true; },
        destroy:function() { oControl.deleted++; }
    }}]; }};
    with(oInputMouse) { room_x=-1000; room_y=-1000; pressed=false; released=false; held=false; }
    control.wf_editor_step();
    wf_expect("native drag moves before Mail capture",part.x==100 && part.y==200);
    global.wf_mail.open=true;
    control.wf_target={x:300,y:400};
    control.wf_editor_step();
    wf_expect("Mail freezes an existing native drag",part.x==100 && part.y==200);
    var ev=wf_ev(); ev.press=true; ev.held=true; ev.x=940; ev.y=500;
    wf_mail_frame(ev);
    with(oInputMouse) { pressed=true; held=true; }
    control.wf_editor_step();
    wf_expect("dismiss click does not resume native drag",part.x==100 && part.y==200);
    with(oInputMouse) { pressed=false; held=false; released=true; }
    wf_mail_frame(wf_ev()); control.wf_editor_step();
    with(oInputMouse) released=false;
    wf_mail_frame(wf_ev()); control.wf_editor_step();
    wf_expect("dismiss release does not resume native drag",part.x==100 && part.y==200);
    with(oInputMouse) { pressed=true; held=true; }
    control.wf_editor_step();
    wf_expect("fresh press resumes suspended native drag",part.x==300 && part.y==400);
    with(oInputMouse) { pressed=false; held=false; released=true; }
    control.wf_editor_step();
    with(oInputMouse) released=false;
    control.wf_editor_step();
    wf_expect("fresh release commits resumed native drag exactly once",control.mode==0 && control.wf_snapshots==1 && part.x==300 && part.y==400);
    with(oInputMouse) { pressed=false; held=false; released=false; }
    control.mode=0; control.mb_right_held=true;
    control.wf_editor_step();
    wf_expect("native eraser can delete the fixture line",control.deleted==1);
    global.wf_mail.open=true; control.mb_right_held=true;
    control.wf_editor_step();
    wf_expect("Mail prevents retained eraser deletion",control.deleted==1);
    wf_expect("Mail clears retained eraser state",!control.mb_right_held);
    control.mode=4;
    control.wf_editor_step();
    wf_expect("native Step advances production with Mail open",control.wf_ticks==1);
    control.mode=5; control.wf_editor_step();
    wf_expect("native paused Step remains paused with Mail open",control.wf_ticks==1);
    control.mode=7; control.wf_target={x:500,y:600};
    control.dangling_insts=[{inst:part,offset_x:0,offset_y:0}];
    control.wf_editor_step();
    ev=wf_ev(); ev.focus=false; wf_mail_frame(ev);
    control.wf_editor_step();
    wf_expect("focus loss keeps suspended native drag frozen",part.x==300 && part.y==400);
    wf_mail_frame(wf_ev()); control.wf_editor_step();
    wf_expect("focus return alone cannot resume native drag",part.x==300 && part.y==400);
    with(oInputMouse) pressed=true;
    control.wf_editor_step();
    wf_expect("fresh press after focus return resumes native drag",part.x==500 && part.y==600);
    with(oInputMouse) pressed=false;
    global.wf_mail.open=true; control.wf_target={x:700,y:800};
    control.wf_editor_step();
    global.wf_mail.enabled=false;
    control.wf_editor_step();
    wf_expect("disabled Mail restores native editor behavior",part.x==700 && part.y==800);
    ds_list_destroy(control.col_list);
    wf_mail_reset();
}
