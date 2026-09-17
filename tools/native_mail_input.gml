// Verified shared dispatcher guards, used by the native panel and input probe.
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
