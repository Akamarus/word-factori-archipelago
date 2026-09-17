// Authored test events exercise the same frame function as production Step.
function wf_ui_event() {
    return {x:0,y:0,press:false,held:false,keys:false,toggle:false,escape:false,enter:false,
        shift:false,backspace:false,wheel:0,text:"",focus:true,width:1280,height:720};
}
function wf_ui_tests() {
    wf_mail_bridge_init();
    directory_create("mods"); directory_create("mods/word factori archipelago");
    directory_create("mods/word factori archipelago/archipelago_mail");
    var b=global.wf_mail_bridge;
    b.enabled=true; b.valid=true; b.advanced=current_time; b.session=string_repeat("a",32);
    b.room_id="test-room"; b.contract="test-contract"; b.snapshot=wf_bridge_snapshot(); b.pending=undefined;
    b.revision=1; b.sequence=0;
    wf_mail_reset();
    var s=global.wf_mail;
    var ev=wf_ui_event(); ev.x=40; ev.y=360; ev.press=true; ev.held=true;
    wf_mail_ui_frame(ev);
    wf_expect("UI first click opens and captures native controls",s.open && wf_mail_blocks_input() && !checkPressed(65));
    var l=wf_mail_layout(), k=l.scale;
    ev=wf_ui_event(); ev.press=true; ev.x=l.left+l.wide*.38; ev.y=l.top+75*k;
    wf_mail_ui_frame(ev);
    wf_expect("UI Chat switch keeps panel open",s.open && s.tab==1 && !s.typing);
    ev=wf_ui_event(); ev.text="ignored"; wf_mail_ui_frame(ev);
    wf_expect("UI unfocused chat does not collect text",s.draft=="");
    ev=wf_ui_event(); ev.press=true; ev.x=l.left+40*k; ev.y=l.bottom-80*k; wf_mail_ui_frame(ev);
    ev=wf_ui_event(); ev.text="hello"; wf_mail_ui_frame(ev);
    wf_expect("UI focused chat receives text only",s.draft=="hello" && wf_mail_blocks_input());
    ev=wf_ui_event(); ev.enter=true; ev.shift=true; wf_mail_ui_frame(ev);
    wf_expect("UI Shift Enter inserts newline without sending",s.draft=="hello\n" && is_undefined(b.pending));
    ev.shift=false; wf_mail_ui_frame(ev);
    wf_expect("UI Enter sends one bounded request",is_struct(b.pending) && b.pending.sequence==1 && s.draft=="");
    ev=wf_ui_event(); ev.keys=true; wf_mail_ui_frame(ev);
    wf_expect("UI held Enter does not repeat send",b.sequence==1);
    b.pending=undefined;
    ev=wf_ui_event(); ev.press=true; ev.x=l.left+40*k; ev.y=l.top+75*k; wf_mail_ui_frame(ev);
    wf_expect("UI Items from Chat stays open",s.open && s.tab==0);
    ev.x=l.left+l.wide*.5; ev.y=l.top+130*k; wf_mail_ui_frame(ev);
    wf_expect("UI filters update locally",s.filter==1 && is_undefined(b.pending));
    ev=wf_ui_event(); ev.press=true; ev.x=l.left+145*k; ev.y=l.bottom-30*k; wf_mail_ui_frame(ev);
    wf_expect("UI Latest requests current history",is_struct(b.pending) && b.pending.action=="history" && b.pending.payload.cursor=="latest");
    b.pending=undefined;
    ev=wf_ui_event(); ev.press=true; ev.x=l.left+l.wide*.63; ev.y=l.top+75*k; wf_mail_ui_frame(ev);
    wf_expect("UI words tab lists authoritative selected target",s.tab==2 && string_pos("CAT",s.lines[0])>0 && string_pos("Not completed",s.lines[0])>0);
    wf_expect("UI key and door have readable labels",wf_mail_display("🔑🚪")=="[KEY][DOOR]");
    ev=wf_ui_event(); ev.press=true; ev.x=l.left+l.wide*.88; ev.y=l.top+75*k; wf_mail_ui_frame(ev);
    wf_expect("UI status tab is present",s.tab==3 && string_pos("Connection",s.lines[0])>0);
    b.message="rejected: Use the regular client";
    wf_expect("UI rejected action has visible status",string_pos("rejected",wf_mail_status_text())>0);
    ev=wf_ui_event(); ev.press=true; ev.held=true; ev.x=5; ev.y=5; wf_mail_ui_frame(ev);
    wf_expect("UI outside dismissal retains click capture",!s.open && wf_mail_blocks_input());
    ev=wf_ui_event(); wf_mail_ui_frame(ev); wf_mail_ui_frame(ev);
    wf_expect("UI controls resume after dismissal release",!wf_mail_blocks_input());
    ev.toggle=true; wf_mail_ui_frame(ev); s.draft="unsent";
    ev=wf_ui_event(); ev.focus=false; wf_mail_ui_frame(ev);
    wf_expect("UI focus loss clears draft and capture",s.draft=="" && !s.open && !wf_mail_blocks_input());
    ev=wf_ui_event(); ev.width=640; ev.height=360; wf_mail_ui_frame(ev);
    l=wf_mail_layout();
    wf_expect("UI minimum viewport layout stays bounded",l.left>=0 && l.right<=640 && l.top>=0 && l.bottom<=360);
    ev.toggle=true; wf_mail_ui_frame(ev);
    s.draft="old room"; b.epoch++; ev.toggle=false; wf_mail_ui_frame(ev);
    wf_expect("UI room epoch clears old draft and popup state",s.draft=="" && array_length(s.popups)==0);
    var started=get_timer();
    for(var i=0;i<1000;i++) {
        ev=wf_ui_event(); ev.toggle=true; wf_mail_ui_frame(ev);
        if(i mod 10==0) { b.epoch++; ev.toggle=false; wf_mail_ui_frame(ev); }
    }
    wf_expect("UI thousand toggles and hundred transitions stay bounded",array_length(s.lines)<=2500
        && array_length(s.seen)<=512 && array_length(s.popups)<=3 && string_length(s.draft)<=1024);
    show_debug_message("WF_MAIL_UI_STRESS_MICROSECONDS:"+string(get_timer()-started));
    b.enabled=false; ev=wf_ui_event(); wf_mail_ui_frame(ev);
    wf_expect("UI disabled capability leaves gameplay input alone",!s.open && !wf_mail_blocks_input());
}
