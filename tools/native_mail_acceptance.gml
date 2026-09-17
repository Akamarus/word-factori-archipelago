// Integration-authored development fixture. Not a production UI or release asset.
function wf_mail_reset() {
    global.wf_mail = {enabled:true, open:false, consume:false, latch:false,
        tab:0, draft:"", scroll:0, focused:true, width:960, height:540};
}
function wf_mail_button_hit(xx, yy) {
    var s=global.wf_mail;
    return point_in_rectangle(xx,yy,12,s.height/2-30,82,s.height/2+30);
}
function wf_mail_blocks_input() {
    if(!variable_global_exists("wf_mail") || !global.wf_mail.enabled) return false;
    var s=global.wf_mail;
    // Protect early Begin Step readers before oInput has sampled this frame.
    var opening=window_has_focus() && (keyboard_check_pressed(vk_f8) ||
        (mouse_check_button_pressed(mb_left) && wf_mail_button_hit(device_mouse_x_to_gui(0),device_mouse_y_to_gui(0))));
    return s.open || s.consume || s.latch || opening;
}
function wf_mail_editor_should_yield() {
    // Called only in the verified oControl Step context. Preserve its native
    // mode and pending objects; never commit/cancel a drag through a UI click.
    if(!variable_instance_exists(id,"wf_mail_editor_wait")) wf_mail_editor_wait=false;
    if(!variable_global_exists("wf_mail") || !global.wf_mail.enabled) {
        wf_mail_editor_wait=false;
        return false;
    }
    var captured=wf_mail_blocks_input() || !global.wf_mail.focused;
    if(captured) mb_right_held=false;
    // Verified playing, paused, completed and completion-animation modes.
    // Production and win processing must still execute their original Step.
    if(mode==4 || mode==5 || mode==6 || mode==9) return false;
    var gesture=mode==1 || mode==2 || mode==3 || mode==7 || mode==8 || mode==10;
    if(captured) {
        if(gesture) wf_mail_editor_wait=true;
        return true;
    }
    if(!gesture) wf_mail_editor_wait=false;
    if(wf_mail_editor_wait) {
        // Release edges swallowed by Mail cannot complete an old drag. A new
        // desktop press (left or the original middle-drag button) re-arms it.
        var fresh=(mode==7 && drag_with_middle) ? mouse_check_button_pressed(mb_middle) : mousePressed(1);
        if(!fresh) return true;
        wf_mail_editor_wait=false;
    }
    return false;
}
function wf_mail_frame(ev) {
    var s=global.wf_mail;
    s.width=ev.width; s.height=ev.height; s.focused=ev.focus;
    if(!ev.focus || !s.enabled) {
        s.open=false; s.consume=false; s.latch=false; s.draft="";
        return;
    }
    var was_open=s.open;
    s.consume=s.open || s.latch;
    if(s.latch && !ev.held && !ev.keys) s.latch=false;
    if(ev.toggle || (ev.press && wf_mail_button_hit(ev.x,ev.y))) {
        s.open=!s.open; s.consume=true; s.latch=true;
    } else if(s.open && ev.escape) {
        s.open=false; s.consume=true; s.latch=true;
    } else if(s.open && ev.press) {
        if(!point_in_rectangle(ev.x,ev.y,120,60,s.width-40,s.height-50)) {
            s.open=false; s.latch=true;
        } else if(ev.y>=115 && ev.y<165) {
            s.tab=(ev.x<(s.width+80)/2) ? 0 : 1;
        }
    }
    if(s.open) {
        s.scroll=max(0,s.scroll+ev.wheel);
        if(s.tab==1 && !ev.toggle) s.draft=string_copy(s.draft+ev.text,1,1024);
    }
    if(was_open || s.open || s.consume) {
        with(oInput) { keyboard_string_index=string_length(full_keyboard_string)+1; }
    }
}
function wf_mail_probe_step() {
    if(!variable_global_exists("wf_mail")) return;
    try {
        wf_mail_frame({x:device_mouse_x_to_gui(0),y:device_mouse_y_to_gui(0),
            press:mouse_check_button_pressed(mb_left), held:mouse_check_button(mb_any),
            keys:keyboard_check(vk_anykey), toggle:keyboard_check_pressed(vk_f8),
            escape:keyboard_check_pressed(vk_escape), wheel:mouse_wheel_down()-mouse_wheel_up(),
            text:keyboard_string, focus:window_has_focus(),
            width:display_get_gui_width(),height:display_get_gui_height()});
        if(global.wf_mail.open || global.wf_mail.consume) keyboard_string="";
    } catch(e) {
        wf_mail_reset(); global.wf_mail.enabled=false;
    }
}
function wf_mail_probe_draw() {
    if(!variable_global_exists("wf_mail") || !global.wf_mail.enabled) return;
    var old_font=draw_get_font(), old_color=draw_get_color(), old_alpha=draw_get_alpha();
    var old_h=draw_get_halign(),old_v=draw_get_valign();
    try {
        var s=global.wf_mail;
        draw_set_alpha(1); draw_set_font(fFredokaOne); draw_set_halign(fa_left); draw_set_valign(fa_top);
        draw_set_color(make_color_rgb(190,9,36));
        draw_roundrect(12,s.height/2-30,82,s.height/2+30,false);
        draw_set_color(c_white); draw_text(18,s.height/2-22,"AP\nMAIL");
        if(s.open) {
            draw_set_color(make_color_rgb(15,21,29)); draw_roundrect(120,60,s.width-40,s.height-50,false);
            draw_set_color(make_color_rgb(83,80,178)); draw_roundrect(120,60,s.width-40,108,false);
            draw_set_color(c_white); draw_text(144,70,"Archipelago - native input probe");
            draw_set_color(s.tab==0 ? make_color_rgb(83,80,178) : make_color_rgb(40,50,65));
            draw_rectangle(130,115,(s.width+80)/2-5,165,false);
            draw_set_color(s.tab==1 ? make_color_rgb(83,80,178) : make_color_rgb(40,50,65));
            draw_rectangle((s.width+80)/2,115,s.width-50,165,false);
            draw_set_color(c_white); draw_text(150,128,"Items"); draw_text((s.width+80)/2+20,128,"Chat");
            draw_text_ext(144,190,s.tab==0 ? "Scratch test only. No AP connection.\nClick tabs; click outside to close." : "Type here: "+s.draft,28,s.width-205);
            draw_text(144,s.height-105,"Scroll: "+string(s.scroll));
        }
        draw_set_color(c_white);
        if(instance_exists(oPersistent)) draw_text(100,5,"Native consumers: "+string(oPersistent.wf_consumers)+" | F8 Mail | F10 finish");
    } catch(e) { wf_mail_reset(); global.wf_mail.enabled=false; }
    draw_set_font(old_font); draw_set_color(old_color); draw_set_alpha(old_alpha);
    draw_set_halign(old_h); draw_set_valign(old_v);
}

// PROBE HARNESS BOUNDARY
var wf_namespace=string_lower(string_replace_all(game_save_id,"\\","/"));
if(string_pos("/wf_mail_probe_NATIVE_NONCE/",wf_namespace)==0) {
    show_debug_message("WF_MAIL_RESULT:NATIVE_NONCE:"+json_stringify({supported:false,tests:[{name:"isolated save namespace",passed:false}]}));
    game_end(); exit;
}
window_set_caption("Word Factori - isolated AP Mail probe");
window_set_size(960,540);
display_set_gui_size(960,540);
wf_tests=[];
wf_frames=0;
wf_consumers=0;
wf_raw_keys=0;
wf_raw_leaks=0;
wf_raw_presses=0;
wf_raw_releases=0;
wf_interactive=PROBE_INTERACTIVE;
wf_factory=PROBE_FACTORY;
wf_factory_done=false;
wf_finishing=false;
wf_factory_closed=undefined;
wf_factory_open_result=undefined;
global.wf_mail = undefined;
wf_mail_reset();
instance_create_depth(0,0,0,oInput);
var mouse=instance_create_depth(0,0,0,oInputMouse);
mouse.mouse_type=0; mouse.pressed=false; mouse.held=false; mouse.released=false;
instance_create_depth(0,0,-10000,oCursor);

function wf_expect(label, yes) { array_push(wf_tests,{name:label,passed:yes}); }
function wf_ev() { return {x:300,y:300,press:false,held:false,keys:false,toggle:false,escape:false,wheel:0,text:"",focus:true,width:960,height:540}; }
function wf_run_tests() {
    wf_mail_reset();
    oInput.pressed={}; variable_struct_set(oInput.pressed,65,true);
    oInput.held={}; variable_struct_set(oInput.held,65,true);
    oInput.released={}; variable_struct_set(oInput.released,65,true);
    with(oInputMouse) { pressed=true; held=true; released=true; }
    wf_expect("unblocked native mapped key",checkPressed(65));
    wf_expect("unblocked native mouse consumer",mousePressed(1));
    var ev=wf_ev(); ev.x=40; ev.y=270; ev.press=true; ev.held=true;
    wf_mail_frame(ev);
    wf_expect("button opens in same frame",global.wf_mail.open);
    wf_expect("native key press suppressed",!checkPressed(65));
    wf_expect("native held key suppressed",!checkHeld(65));
    wf_expect("native key release suppressed",!checkReleased(65));
    wf_expect("native mouse press suppressed",!mousePressed(1));
    wf_expect("native mouse hold suppressed",!mouseHeld(1));
    wf_expect("native mouse release suppressed",!mouseReleased(1));
    // Engine key injection does not take effect synchronously. Real raw-key
    // coverage is recorded across frames in the interactive run below.
    oInput.full_keyboard_string="factory text";
    wf_expect("native text buffer suppressed",keyboardString()=="");
    var widget=instance_create_depth(0,0,0,oInputClickable);
    widget.pressed=true; widget.held=true; widget.released=true; widget.hover=true; widget.hold_started_with_press=true;
    with(widget) inputClickableUpdateState();
    wf_expect("real clickable dispatcher clears all edge flags",!widget.pressed && !widget.held && !widget.released && !widget.hover && !widget.hold_started_with_press);
    instance_destroy(widget);
    ev=wf_ev(); ev.press=true; ev.x=700; ev.y=140;
    wf_mail_frame(ev);
    wf_expect("Chat tab does not close panel",global.wf_mail.open && global.wf_mail.tab==1);
    ev=wf_ev(); ev.text="hi"; ev.keys=true;
    wf_mail_frame(ev);
    wf_expect("typing belongs to Chat",global.wf_mail.draft=="hi" && keyboardString()=="");
    ev=wf_ev(); ev.wheel=1; wf_mail_frame(ev);
    wf_expect("wheel belongs to panel",global.wf_mail.scroll==1 && wf_mail_blocks_input());
    ev=wf_ev(); ev.press=true; ev.x=200; ev.y=140; wf_mail_frame(ev);
    wf_expect("Items tab does not close panel",global.wf_mail.open && global.wf_mail.tab==0);
    ev=wf_ev(); ev.press=true; ev.held=true; ev.x=940; ev.y=500; wf_mail_frame(ev);
    wf_expect("outside dismiss consumes click",!global.wf_mail.open && !mousePressed(1));
    ev.press=false; wf_mail_frame(ev);
    wf_expect("dismiss hold cannot reach factory",!mouseHeld(1));
    ev.held=false; wf_mail_frame(ev);
    wf_expect("dismiss release cannot reach factory",!mouseReleased(1));
    wf_mail_frame(wf_ev());
    wf_expect("native input resumes after release",mousePressed(1) && checkPressed(65));
    ev=wf_ev(); ev.toggle=true; wf_mail_frame(ev);
    wf_expect("F8 opens immediately",global.wf_mail.open);
    ev=wf_ev(); ev.escape=true; wf_mail_frame(ev);
    wf_expect("Escape closes without key leak",!global.wf_mail.open && !checkPressed(65));
    ev=wf_ev(); ev.toggle=true; wf_mail_frame(ev);
    ev=wf_ev(); ev.focus=false; wf_mail_frame(ev);
    wf_expect("focus loss releases capture and draft",!global.wf_mail.open && !global.wf_mail.latch && global.wf_mail.draft=="" && !wf_mail_blocks_input());
    global.wf_mail.open=true; global.wf_mail.draft="unsent";
    with(oInput) event_perform(ev_other,ev_room_start);
    wf_expect("native room event resets state",!global.wf_mail.open && global.wf_mail.draft=="");
    draw_set_font(fFredokaOne);
    wf_expect("installed native font measures text",font_exists(fFredokaOne) && string_width("Archipelago")>0);
    global.wf_mail.enabled=false;
    wf_expect("disabled UI leaves native controls unchanged",checkPressed(65) && mousePressed(1));
    wf_mail_reset();
    with(oInputMouse) { pressed=false; held=false; released=false; }
    oInput.pressed={}; oInput.held={}; oInput.released={};
    keyboard_string="";
}
function wf_finish() {
    if(wf_finishing) return;
    wf_finishing=true;
    if(wf_interactive) {
        wf_expect("real raw key press exercised while Mail open",wf_raw_presses>0);
        wf_expect("real raw key release exercised while Mail open",wf_raw_releases>0);
        wf_expect("real raw key held while Mail open",wf_raw_keys>0);
        wf_expect("real raw keyboard did not reach native consumer",wf_raw_leaks==0);
    }
    // Scratch fixture only: every other instance was created by this host and
    // its original lifecycle is disabled. Let normal instance cleanup finish
    // before the runner frees room/object resources at process shutdown.
    // Calling game_end directly with these bound-method instances still alive
    // reproduced intermittent freed-memory access during native teardown.
    var host=id;
    with(all) if(id!=host) instance_destroy();
    alarm[0]=3;
}
function wf_finish_report() {
    wf_expect("scratch objects released before native shutdown",wf_finishing && instance_number(all)==1);
    var supported=array_all(wf_tests,function(t) { return t.passed; });
    show_debug_message("WF_MAIL_RESULT:NATIVE_NONCE:"+json_stringify({supported:supported,tests:wf_tests,manual_input_validated:false,gate_passed:false,native_consumers:wf_consumers,raw_key_frames:wf_raw_keys,raw_presses:wf_raw_presses,raw_releases:wf_raw_releases,factory_closed:wf_factory_closed,factory_open:wf_factory_open_result}));
    game_end();
}
function wf_probe_frame() {
    if(wf_finishing) return;
    wf_frames++;
    if(wf_frames==2) {
        try { wf_run_tests(); } catch(e) { wf_expect("native exception: "+string(e),false); }
    }
    if(wf_factory && !wf_factory_done && wf_frames>=3) {
        try {
            if(wf_frames==3) wf_factory_begin(PROBE_FACTORY_OPEN);
            else wf_factory_step();
        } catch(e) { wf_expect("factory exception: "+string(e),false); wf_factory_done=true; }
    }
    // Held-key evidence must come from actual input. Do not synthesize engine
    // key presses here: on Windows they can target a different focused window.
    // This consumer uses the same guards as native factory/widgets. It is not
    // a substitute for a populated-factory acceptance test.
    if(wf_mail_mouse_check_button_pressed(mb_left) || wf_mail_keyboard_check_pressed(65)) wf_consumers++;
    if(wf_frames>6 && global.wf_mail.open && keyboard_check(65)) {
        wf_raw_keys++;
        if(wf_mail_keyboard_check(65)) wf_raw_leaks++;
    }
    if(wf_frames>6 && global.wf_mail.open && keyboard_check_pressed(65)) {
        wf_raw_presses++;
        if(wf_mail_keyboard_check_pressed(65)) wf_raw_leaks++;
    }
    if(wf_frames>6 && global.wf_mail.open && keyboard_check_released(65)) {
        wf_raw_releases++;
        if(wf_mail_keyboard_check_released(65)) wf_raw_leaks++;
    }
    if((!wf_interactive && wf_frames>8 && (!wf_factory || wf_factory_done)) || keyboard_check_pressed(vk_f10)) wf_finish();
}
