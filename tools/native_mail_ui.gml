// Native presentation only. Cached rows are prepared in Step, never in Draw.
function wf_mail_reset() {
    var active=variable_global_exists("wf_mail_bridge") && is_struct(global.wf_mail_bridge)
        && global.wf_mail_bridge.enabled;
    global.wf_mail={enabled:active,open:false,consume:false,latch:false,focused:true,
        width:960,height:540,tab:0,filter:0,scroll:0,draft:"",typing:false,
        lines:[],cache:"",epoch:-1,read_key:undefined,seen:[],popups:[],notice:""};
}
function wf_mail_layout() {
    var s=global.wf_mail;
    var scale=clamp(min(s.width/1280,s.height/720),0.5,1.5);
    var wide=min(860*scale,s.width-190*scale), tall=min(740*scale,s.height-40*scale);
    var left=max(100*scale,(s.width-wide)/2), top=(s.height-tall)/2;
    return {left:left,top:top,right:left+wide,bottom:top+tall,scale:scale,wide:wide,tall:tall,
        text_scale:0.8*scale,line:25*scale};
}
function wf_mail_button_hit(xx,yy) {
    var s=global.wf_mail;
    return point_in_rectangle(xx,yy,12,s.height/2-34,82,s.height/2+34);
}
function wf_mail_display(text) {
    text=string_replace_all(string_replace_all(text,"🔑","[KEY]"),"🚪","[DOOR]");
    var out="";
    for(var i=1;i<=string_length(text);i++) {
        var ch=string_char_at(text,i), code=ord(ch);
        out+=(code==10 || (code>=32 && code<=126)) ? ch : "?";
    }
    return out;
}
function wf_mail_add_lines(text,wide,scale) {
    var s=global.wf_mail;
    text=wf_mail_display(text);
    var line="";
    for(var i=1;i<=string_length(text);i++) {
        var ch=string_char_at(text,i);
        if(ch=="\n" || (line!="" && string_width(line+ch)*scale>wide)) {
            if(array_length(s.lines)<2500) array_push(s.lines,line);
            line="";
        }
        if(ch!="\n") line+=ch;
    }
    if(array_length(s.lines)<2500) array_push(s.lines,line);
}
function wf_mail_cache() {
    var s=global.wf_mail, b=global.wf_mail_bridge, l=wf_mail_layout();
    var key=string(b.epoch)+":"+string(b.revision)+":"+string(s.tab)+":"+string(s.filter)+":"+string(s.width)+":"+string(s.height)+":"+b.message;
    if(s.cache==key) return;
    s.cache=key; s.lines=[];
    var previous=draw_get_font(); draw_set_font(fFredokaOne);
    try {
        var value=b.snapshot, wide=l.wide-40*l.scale;
        if(!is_struct(value)) wf_mail_add_lines("Start the Word Factori client and connect to your room. Mail does not control progression.",wide,l.text_scale);
        else if(s.tab==0) {
            if(array_length(value.items)==0) wf_mail_add_lines("No item deliveries yet.",wide,l.text_scale);
            for(var i=array_length(value.items)-1;i>=0;i--) {
                var row=value.items[i];
                if(s.filter==1 && row.direction=="sent") continue;
                if(s.filter==2 && row.direction=="received") continue;
                var label=row.direction=="sent" ? "Sent: " : (row.direction=="self" ? "Found: " : "Received: ");
                wf_mail_add_lines((row.unread ? "* " : "")+label+row.item,wide,l.text_scale);
                wf_mail_add_lines((row.direction=="sent" ? "To " : "From ")+row.player+" - "+row.location,wide,l.text_scale);
                array_push(s.lines,"");
            }
        } else if(s.tab==1) {
            if(array_length(value.chat)==0) wf_mail_add_lines("No messages yet. Click the input below to chat.",wide,l.text_scale);
            for(var i=array_length(value.chat)-1;i>=0;i--) {
                wf_mail_add_lines(value.chat[i].text,wide,l.text_scale);
                array_push(s.lines,"");
            }
        } else if(s.tab==2) {
            if(array_length(value.words)==0) wf_mail_add_lines("This room has no Type-a-Word targets.",wide,l.text_scale);
            for(var i=0;i<array_length(value.words);i++) {
                var row=value.words[i];
                wf_mail_add_lines(row.name+": "+row.word+" - "+row.status,wide,l.text_scale);
                array_push(s.lines,"");
            }
            wf_mail_add_lines("Complete these targets in Type-a-Word. Completed means the server confirmed the check. [KEY] and [DOOR] represent the game's symbols.",wide,l.text_scale);
        } else {
            wf_mail_add_lines("Connection: "+value.connection,wide,l.text_scale);
            wf_mail_add_lines(b.message,wide,l.text_scale);
            wf_mail_add_lines("Use the regular client for server, slot and password settings. Reconnect uses its existing configuration.",wide,l.text_scale);
            wf_mail_add_lines("Mail is presentation only: factory checks and received upgrades continue if this panel is closed.",wide,l.text_scale);
        }
    } catch(error) { s.lines=["Mail display unavailable. Use the regular client."]; }
    draw_set_font(previous);
    s.scroll=clamp(s.scroll,0,max(0,array_length(s.lines)-1));
}
function wf_mail_view_boundary() {
    var s=global.wf_mail, value=global.wf_mail_bridge.snapshot;
    s.read_key=undefined;
    if(s.tab==0 && is_struct(value) && array_length(value.items)>0) s.read_key=value.items[array_length(value.items)-1].key;
}
function wf_mail_ui_frame(ev) {
    var s=global.wf_mail,b=global.wf_mail_bridge;
    s.width=max(320,ev.width); s.height=max(240,ev.height); s.focused=ev.focus;
    s.enabled=b.enabled;
    if(s.epoch!=b.epoch) {
        s.epoch=b.epoch; s.draft=""; s.typing=false; s.scroll=0; s.cache="";
        s.read_key=undefined; s.seen=[]; s.popups=[];
    }
    if(!s.enabled || !ev.focus) {
        s.open=false; s.consume=false; s.latch=false; s.draft=""; s.typing=false; return;
    }
    var was_open=s.open, l=wf_mail_layout(), k=l.scale;
    s.consume=s.open || s.latch;
    if(s.latch && !ev.held && !ev.keys) s.latch=false;
    if(ev.toggle || (ev.press && wf_mail_button_hit(ev.x,ev.y))) {
        s.open=!s.open; s.consume=true; s.latch=true; s.typing=false;
        if(s.open) { s.scroll=0; wf_mail_view_boundary(); }
    } else if(s.open && (ev.escape || (ev.press && (!point_in_rectangle(ev.x,ev.y,l.left,l.top,l.right,l.bottom)
        || point_in_rectangle(ev.x,ev.y,l.right-48*k,l.top,l.right,l.top+48*k))))) {
        s.open=false; s.typing=false; s.latch=true;
    } else if(s.open && ev.press) {
        if(ev.y>=l.top+58*k && ev.y<l.top+104*k) {
            s.tab=clamp(floor((ev.x-l.left)/(l.wide/4)),0,3);
            s.scroll=0; s.typing=false; wf_mail_view_boundary();
        } else if(s.tab==0 && ev.y>=l.top+112*k && ev.y<l.top+150*k) {
            s.filter=clamp(floor((ev.x-l.left)/(l.wide/3)),0,2); s.scroll=0;
        } else if(s.tab==1 && point_in_rectangle(ev.x,ev.y,l.left+12*k,l.bottom-112*k,l.right-105*k,l.bottom-48*k)) {
            s.typing=true; keyboard_string="";
        } else if(s.tab==1 && point_in_rectangle(ev.x,ev.y,l.right-98*k,l.bottom-112*k,l.right-12*k,l.bottom-48*k)) {
            if(wf_mail_submit("submit-text",{text:s.draft})) { s.draft=""; keyboard_string=""; }
        } else if(s.tab==3 && ev.y>=l.bottom-104*k && ev.y<l.bottom-56*k) {
            wf_mail_submit(ev.x<(l.left+l.right)/2 ? "reconnect" : "disconnect",{});
        } else if((s.tab==0 || s.tab==1) && ev.y>=l.bottom-44*k && ev.y<l.bottom-16*k && ev.x<l.left+210*k) {
            var value=b.snapshot;
            var view=s.tab==0 ? "items" : "chat";
            if(is_struct(value)) {
                var cursor=ev.x>=l.left+115*k ? "latest" : variable_struct_get(value.history,view);
                if(!is_undefined(cursor) && wf_mail_submit("history",{view:view,filter:"all",cursor:cursor})) s.scroll=0;
            }
        } else s.typing=false;
    }
    if(s.open) {
        s.scroll=max(0,s.scroll+ev.wheel*3);
        if(s.tab==1 && s.typing && !ev.toggle) {
            // The step wrapper supplies only newly accumulated keyboard text.
            s.draft=string_copy(s.draft+ev.text,1,1024);
            if(ev.backspace && string_length(s.draft)>0) s.draft=string_delete(s.draft,string_length(s.draft),1);
            if(ev.enter) {
                if(ev.shift) s.draft=string_copy(s.draft+"\n",1,1024);
                else if(wf_mail_submit("submit-text",{text:s.draft})) s.draft="";
            }
        }
        if(s.tab==0 && !is_undefined(s.read_key) && wf_mail_submit("mark-read",{through_key:s.read_key})) s.read_key=undefined;
    }
    if(was_open || s.open || s.consume) {
        with(oInput) { keyboard_string_index=string_length(full_keyboard_string)+1; }
    }
    wf_mail_cache();
}
function wf_mail_ui_step() {
    try {
        wf_mail_bridge_step(current_time);
        if(!variable_global_exists("wf_mail") || !is_struct(global.wf_mail)) wf_mail_reset();
        var captured=global.wf_mail.open || global.wf_mail.consume;
        var typed=captured ? keyboard_string : "";
        typed=string_replace_all(string_replace_all(typed,"\r",""),"\n","");
        wf_mail_ui_frame({x:device_mouse_x_to_gui(0),y:device_mouse_y_to_gui(0),
            press:mouse_check_button_pressed(mb_left),held:mouse_check_button(mb_any),keys:keyboard_check(vk_anykey),
            toggle:keyboard_check_pressed(vk_f8),escape:keyboard_check_pressed(vk_escape),
            enter:keyboard_check_pressed(vk_enter),shift:keyboard_check(vk_shift),
            backspace:keyboard_check_pressed(vk_backspace),wheel:mouse_wheel_down()-mouse_wheel_up(),
            text:typed,focus:window_has_focus(),width:display_get_gui_width(),height:display_get_gui_height()});
        if(captured || global.wf_mail.open || global.wf_mail.consume) keyboard_string="";
        wf_mail_popup_step();
    } catch(error) {
        wf_mail_reset(); global.wf_mail.enabled=false;
    }
}
function wf_mail_popup_step() {
    var s=global.wf_mail,b=global.wf_mail_bridge;
    for(var i=array_length(s.popups)-1;i>=0;i--) if(current_time>=s.popups[i].expires) array_delete(s.popups,i,1);
    if(!wf_mail_bridge_ready() || !is_struct(b.snapshot)) return;
    for(var i=0;i<array_length(b.snapshot.notifications);i++) {
        var row=b.snapshot.notifications[i], seen=false;
        for(var n=0;n<array_length(s.seen);n++) if(s.seen[n]==row.key) { seen=true; break; }
        if(seen || row.historical || array_length(s.popups)>=3) continue;
        array_push(s.seen,row.key);
        if(array_length(s.seen)>512) array_delete(s.seen,0,1);
        if(array_length(s.popups)<3) array_push(s.popups,{text:wf_mail_display(string_copy(row.item,1,55)),expires:current_time+6000});
    }
}
function wf_mail_label(text,xx,yy,scale) { draw_text_transformed(xx,yy,text,scale,scale,0); }
function wf_mail_status_text() {
    var b=global.wf_mail_bridge;
    if(!wf_mail_bridge_ready()) return "Offline - use the regular client";
    if(is_struct(b.pending)) return "Request pending...";
    return b.message;
}
function wf_mail_ui_draw() {
    if(!variable_global_exists("wf_mail") || !global.wf_mail.enabled) return;
    var font=draw_get_font(), color=draw_get_color(), alpha=draw_get_alpha(), ha=draw_get_halign(), va=draw_get_valign();
    try {
        var s=global.wf_mail,b=global.wf_mail_bridge,l=wf_mail_layout(),k=l.scale,ts=l.text_scale;
        draw_set_alpha(1); draw_set_font(fFredokaOne); draw_set_halign(fa_left); draw_set_valign(fa_top);
        draw_set_color(make_color_rgb(190,9,36)); draw_roundrect(12,s.height/2-34,82,s.height/2+34,false);
        draw_set_color(c_white); wf_mail_label("AP\nMAIL",20,s.height/2-27,.75);
        if(is_struct(b.snapshot) && b.snapshot.unread>0) wf_mail_label(string(b.snapshot.unread),34,s.height/2+13,.6);
        if(s.open) {
            draw_set_color(make_color_rgb(15,21,29)); draw_roundrect(l.left,l.top,l.right,l.bottom,false);
            draw_set_color(make_color_rgb(83,80,178)); draw_roundrect(l.left,l.top,l.right,l.top+48*k,false);
            draw_set_color(c_white); wf_mail_label("Archipelago",l.left+22*k,l.top+10*k,ts);
            wf_mail_label("X",l.right-32*k,l.top+10*k,ts);
            var tabs=["Items","Chat","Type-a-Word","Status"], tabwide=l.wide/4;
            for(var i=0;i<4;i++) {
                draw_set_color(i==s.tab ? make_color_rgb(83,80,178) : make_color_rgb(40,50,65));
                draw_rectangle(l.left+i*tabwide+4*k,l.top+58*k,l.left+(i+1)*tabwide-4*k,l.top+104*k,false);
                draw_set_color(c_white); wf_mail_label(tabs[i],l.left+i*tabwide+12*k,l.top+70*k,ts*.82);
            }
            var content_top=l.top+118*k, content_bottom=l.bottom-(s.tab==1 ? 125 : (s.tab==3 ? 118 : 64))*k;
            if(s.tab==0) {
                var filters=["All","Received","Sent"];
                for(var i=0;i<3;i++) {
                    draw_set_color(i==s.filter ? make_color_rgb(83,80,178) : make_color_rgb(40,50,65));
                    draw_rectangle(l.left+i*l.wide/3+4*k,l.top+112*k,l.left+(i+1)*l.wide/3-4*k,l.top+150*k,false);
                    draw_set_color(c_white); wf_mail_label(filters[i],l.left+i*l.wide/3+12*k,l.top+121*k,ts*.85);
                }
                content_top=l.top+164*k;
            }
            draw_set_color(c_white);
            var capacity=max(1,floor((content_bottom-content_top)/l.line));
            var start=clamp(s.scroll,0,max(0,array_length(s.lines)-capacity));
            for(var i=0;i<capacity && start+i<array_length(s.lines);i++)
                wf_mail_label(s.lines[start+i],l.left+20*k,content_top+i*l.line,ts);
            if(s.tab==1) {
                draw_set_color(s.typing ? make_color_rgb(48,61,83) : make_color_rgb(30,40,56));
                draw_rectangle(l.left+12*k,l.bottom-112*k,l.right-105*k,l.bottom-48*k,false);
                draw_set_color(make_color_rgb(83,80,178)); draw_rectangle(l.right-98*k,l.bottom-112*k,l.right-12*k,l.bottom-48*k,false);
                draw_set_color(c_white); wf_mail_label("Send",l.right-88*k,l.bottom-95*k,ts);
                var draft=string_replace_all(wf_mail_display(s.draft),"\n"," / ");
                var chars=max(10,floor((l.wide-155*k)/(14*ts)));
                if(string_length(draft)>chars) draft="..."+string_copy(draft,string_length(draft)-chars+4,chars);
                wf_mail_label(draft=="" ? "Click here to chat - Enter sends" : draft,l.left+20*k,l.bottom-95*k,ts*.85);
            }
            if(s.tab==3) {
                draw_set_color(make_color_rgb(83,80,178));
                draw_rectangle(l.left+12*k,l.bottom-104*k,(l.left+l.right)/2-4*k,l.bottom-56*k,false);
                draw_rectangle((l.left+l.right)/2+4*k,l.bottom-104*k,l.right-12*k,l.bottom-56*k,false);
                draw_set_color(c_white); wf_mail_label("Reconnect",l.left+24*k,l.bottom-94*k,ts);
                wf_mail_label("Disconnect",(l.left+l.right)/2+16*k,l.bottom-94*k,ts);
            }
            if(s.tab==0 || s.tab==1) {
                wf_mail_label("Older",l.left+18*k,l.bottom-42*k,ts*.75);
                wf_mail_label("Latest",l.left+120*k,l.bottom-42*k,ts*.75);
            }
            var status=wf_mail_status_text();
            draw_set_color(make_color_rgb(172,200,226));
            wf_mail_label(wf_mail_display(string_copy(status,1,55)),l.left+l.wide*.4,l.bottom-40*k,ts*.6);
        } else {
            for(var i=0;i<array_length(s.popups);i++) {
                var yy=max(20,s.height/2-140-i*82);
                draw_set_color(make_color_rgb(45,153,205)); draw_roundrect(12,yy,390,yy+72,false);
                draw_set_color(c_white); wf_mail_label(string_copy(s.popups[i].text,1,40),24,yy+22,.65);
            }
        }
    } catch(error) { wf_mail_reset(); global.wf_mail.enabled=false; }
    draw_set_font(font); draw_set_color(color); draw_set_alpha(alpha); draw_set_halign(ha); draw_set_valign(va);
}
// Existing exact input hooks call these names; no development harness is included.
function wf_mail_probe_step() { wf_mail_ui_step(); }
function wf_mail_probe_draw() { wf_mail_ui_draw(); }
