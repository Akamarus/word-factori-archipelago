// Integration-authored presentation transport. No AP networking or game-save writes.
function wf_mail_fields(value, names) {
    if(!is_struct(value) || variable_struct_names_count(value)!=array_length(names)) return false;
    for(var i=0;i<array_length(names);i++) if(!variable_struct_exists(value,names[i])) return false;
    return true;
}
function wf_mail_integer(value) {
    return (is_real(value)||is_int64(value)) && !is_bool(value) && value>=0
        && value<=9007199254740991 && value==floor(value);
}
function wf_mail_text(value, bound) {
    // The runner represents chr(0) as an empty string; checking string_pos
    // against it would incorrectly reject every ordinary display value.
    return is_string(value) && string_length(value)<=bound;
}
function wf_mail_boolean(value) {
    // The verified runner's json_parse decodes JSON booleans as real 0/1.
    // Python enforces wire boolean types before publishing; accept only these
    // two decoded values here, never arbitrary truthy strings or numbers.
    return is_bool(value) || (is_real(value) && (value==0 || value==1));
}
function wf_mail_id(value) { return wf_mail_text(value,128) && string_length(value)>0; }
function wf_mail_null(value) { return is_undefined(value) || (is_ptr(value) && value==pointer_null); }
function wf_mail_uuid(value) {
    if(!wf_mail_text(value,32) || string_length(value)!=32) return false;
    for(var i=1;i<=32;i++) if(string_pos(string_char_at(value,i),"0123456789abcdef")==0) return false;
    return true;
}
function wf_mail_choice(value, choices) {
    if(!is_string(value)) return false;
    for(var i=0;i<array_length(choices);i++) if(value==choices[i]) return true;
    return false;
}
function wf_mail_item_valid(row) {
    return wf_mail_fields(row,["key","direction","item","player","location","historical","unread"])
        && wf_mail_id(row.key) && wf_mail_choice(row.direction,["received","sent","self"])
        && wf_mail_text(row.item,512) && wf_mail_text(row.player,512)
        && wf_mail_text(row.location,512) && wf_mail_boolean(row.historical) && wf_mail_boolean(row.unread);
}
function wf_mail_manifest_valid(value) {
    return wf_mail_fields(value,["version","session","renderer","revision","heartbeat"])
        && wf_mail_integer(value.version) && value.version==1 && wf_mail_uuid(value.session)
        && wf_mail_uuid(value.renderer) && wf_mail_integer(value.revision) && wf_mail_integer(value.heartbeat);
}
function wf_mail_snapshot_valid(value) {
    if(!wf_mail_fields(value,["version","session","renderer","revision","room","contract","connection",
        "items","chat","words","notifications","unread","acks","history"])) return false;
    if(!wf_mail_integer(value.version) || value.version!=1 || !wf_mail_uuid(value.session)
        || !wf_mail_uuid(value.renderer) || !wf_mail_integer(value.revision) || !wf_mail_integer(value.unread)) return false;
    if(!(wf_mail_null(value.room) && wf_mail_null(value.contract))
        && !(wf_mail_id(value.room) && wf_mail_id(value.contract))) return false;
    if(!wf_mail_choice(value.connection,["disconnected","connecting","connected","reconnecting","authenticating","error"])) return false;
    var groups=[value.items,value.chat,value.words,value.notifications,value.acks], limits=[50,50,20,3,32];
    for(var g=0;g<5;g++) if(!is_array(groups[g]) || array_length(groups[g])>limits[g]) return false;
    for(var i=0;i<array_length(value.items);i++) if(!wf_mail_item_valid(value.items[i])) return false;
    for(var i=0;i<array_length(value.notifications);i++) if(!wf_mail_item_valid(value.notifications[i])) return false;
    for(var i=0;i<array_length(value.chat);i++) {
        var row=value.chat[i];
        if(!wf_mail_fields(row,["key","kind","text"]) || !wf_mail_id(row.key)
            || !wf_mail_choice(row.kind,["chat","hint","command","error"]) || !wf_mail_text(row.text,512)) return false;
    }
    for(var i=0;i<array_length(value.words);i++) {
        var row=value.words[i];
        if(!wf_mail_fields(row,["name","word","status"]) || !wf_mail_text(row.name,512) || row.name==""
            || !wf_mail_text(row.word,12) || row.word==""
            || !wf_mail_choice(row.status,["Not completed","Sending","Completed"])) return false;
    }
    for(var i=0;i<array_length(value.acks);i++) {
        var row=value.acks[i];
        if(!wf_mail_fields(row,["sequence","status","message"]) || !wf_mail_integer(row.sequence)
            || !wf_mail_choice(row.status,["queued","forwarded","rejected","uncertain"])
            || !wf_mail_text(row.message,512)) return false;
    }
    if(!wf_mail_fields(value.history,["items","chat"])) return false;
    return (wf_mail_null(value.history.items)||wf_mail_id(value.history.items))
        && (wf_mail_null(value.history.chat)||wf_mail_id(value.history.chat));
}
function wf_mail_path(name) { return "mods/word factori archipelago/archipelago_mail/"+name; }
function wf_mail_read(name, limit) {
    var handle=-1, bytes=-1;
    try {
        var path=wf_mail_path(name);
        if(!file_exists(path)) return undefined;
        handle=file_bin_open(path,0);
        if(handle<0) return undefined;
        var count=file_bin_size(handle);
        if(count<=0 || count>limit) { file_bin_close(handle); return undefined; }
        // Read a bounded immutable copy from the same opened file. No unbounded
        // line allocation; UTF-8 decoding belongs to the engine buffer reader.
        bytes=buffer_create(count+1,buffer_fixed,1);
        for(var i=0;i<count;i++) buffer_poke(bytes,i,buffer_u8,file_bin_read_byte(handle));
        file_bin_close(handle); handle=-1;
        buffer_poke(bytes,count,buffer_u8,0);
        var text=buffer_read(bytes,buffer_string);
        buffer_delete(bytes); bytes=-1;
        return json_parse(text);
    } catch(error) {
        if(handle>=0) file_bin_close(handle);
        if(bytes>=0) buffer_delete(bytes);
        return undefined;
    }
}
function wf_mail_write(name, value, limit) {
    var handle=-1;
    var temp=wf_mail_path("."+global.wf_mail_bridge.renderer+"-"+name+".tmp");
    try {
        // This runner emits real numbers as 1.0; wire counters must be JSON
        // integers. Only numeric headers are formatted here; strings/payloads
        // always use the engine's JSON escaping.
        var text="";
        if(name=="hello.json") {
            text="{\"version\":1,\"renderer\":"+json_stringify(value.renderer)
                +",\"heartbeat\":"+string_format(value.heartbeat,0,0)+"}";
        } else if(name=="request.json") {
            text="{\"version\":1,\"session\":"+json_stringify(value.session)
                +",\"renderer\":"+json_stringify(value.renderer)+",\"room\":"+json_stringify(value.room)
                +",\"sequence\":"+string_format(value.sequence,0,0)+",\"action\":"+json_stringify(value.action)
                +",\"payload\":"+json_stringify(value.payload)+"}";
        } else return false;
        if(string_byte_length(text)>limit) return false;
        handle=file_text_open_write(temp);
        if(handle<0) return false;
        file_text_write_string(handle,text); file_text_close(handle); handle=-1;
        var destination=wf_mail_path(name);
        // The verified runner refuses rename-over-existing. Remove only this
        // fixed, ephemeral owned record, then rename the complete temp file.
        // A concurrent reader can see "missing", never a partly written record.
        // Readers fail closed/retry; this is not a filesystem-atomic overwrite.
        if(file_exists(destination)) file_delete(destination);
        if(!file_rename(temp,destination)) {
            if(file_exists(temp)) file_delete(temp);
            return false;
        }
        return true;
    } catch(error) {
        if(handle>=0) file_text_close(handle);
        if(file_exists(temp)) file_delete(temp);
        return false;
    }
}
function wf_mail_bridge_init() {
    if(variable_global_exists("wf_mail_bridge") && is_struct(global.wf_mail_bridge)) return;
    // Local process identity, not an authentication token. Do not disturb game RNG.
    var token=md5_string_utf8(string(get_timer())+"|"+string(date_current_datetime())+"|"+string(window_handle()));
    global.wf_mail_bridge={renderer:token,session:undefined,room_id:undefined,contract:undefined,
        revision:-1,heartbeat:-1,advanced:-1,next_poll:0,next_hello:0,hello:0,
        sequence:0,pending:undefined,snapshot:undefined,valid:false,enabled:false,
        message:"Start the Word Factori client to connect.",reads:0,snapshot_reads:0,epoch:0};
}
function wf_mail_bridge_clear(message) {
    var b=global.wf_mail_bridge;
    b.snapshot=undefined; b.revision=-1; b.heartbeat=-1; b.advanced=-1; b.valid=false;
    b.pending=undefined; b.message=message; b.epoch++;
}
function wf_mail_bridge_accept(manifest, value, now_ms, context) {
    var b=global.wf_mail_bridge;
    if(!wf_mail_manifest_valid(manifest) || manifest.renderer!=b.renderer) { b.valid=false; return false; }
    if(manifest.session!=b.session) {
        var uncertain=!is_undefined(b.pending);
        wf_mail_bridge_clear(uncertain ? "Delivery uncertain. Check chat before resending." : "Connecting to the client...");
        b.session=manifest.session; b.sequence=0;
    }
    if(manifest.revision<b.revision || manifest.heartbeat<b.heartbeat) { b.valid=false; return false; }
    if(manifest.heartbeat>b.heartbeat) {
        if(b.heartbeat>=0) b.advanced=now_ms;
        b.heartbeat=manifest.heartbeat;
    }
    if(manifest.revision!=b.revision) {
        if(!wf_mail_snapshot_valid(value) || value.session!=b.session || value.renderer!=b.renderer
            || value.revision!=manifest.revision) { b.valid=false; return false; }
        // json_parse uses pointer_null for wire null; internal state uses undefined.
        if(wf_mail_null(value.room)) variable_struct_set(value,"room",undefined);
        if(wf_mail_null(value.contract)) value.contract=undefined;
        if(wf_mail_null(value.history.items)) value.history.items=undefined;
        if(wf_mail_null(value.history.chat)) value.history.chat=undefined;
        if(!is_undefined(value.room) && (!is_struct(context) || value.room!=context.room || value.contract!=context.checks_contract)) {
            wf_mail_bridge_clear("Room changed. Load the campaign selected by your client.");
            return false;
        }
        if(value.room!=b.room_id || value.contract!=b.contract) {
            b.epoch++; b.pending=undefined; b.room_id=value.room; b.contract=value.contract;
        }
        if(is_struct(b.snapshot) && b.snapshot.connection=="connected" && value.connection!="connected") b.epoch++;
        b.snapshot=value; b.revision=value.revision;
        if(is_struct(b.pending)) {
            for(var i=0;i<array_length(value.acks);i++) {
                var ack=value.acks[i];
                if(ack.sequence==b.pending.sequence) {
                    b.message=ack.status+": "+ack.message;
                    if(ack.status!="queued") b.pending=undefined;
                }
            }
        }
    }
    b.valid=is_struct(b.snapshot);
    return b.valid;
}
function wf_mail_bridge_step(now_ms) {
    wf_mail_bridge_init();
    var b=global.wf_mail_bridge;
    if(now_ms<b.next_poll) return;
    b.next_poll=now_ms+250;
    if(!wf_access_active()) {
        if(b.enabled) wf_mail_bridge_clear("AP Mail is disabled outside the Archipelago mod.");
        b.enabled=false; return;
    }
    try {
        // A Linux-only installer marker gates the UI. Windows keeps its overlay.
        var enabled=wf_mail_read("enabled.json",4096);
        b.enabled=wf_mail_fields(enabled,["version","enabled"]) && wf_mail_integer(enabled.version)
            && enabled.version==1 && wf_mail_boolean(enabled.enabled) && enabled.enabled;
        if(!b.enabled) { b.valid=false; return; }
        var context=wf_access_context();
        if(is_struct(b.snapshot) && !is_undefined(b.snapshot.room)
            && (!is_struct(context) || context.room!=b.room_id || context.checks_contract!=b.contract)) {
            wf_mail_bridge_clear("Room changed. Reconnecting presentation...");
        }
        if(now_ms>=b.next_hello) {
            b.next_hello=now_ms+1000; b.hello++;
            if(!wf_mail_write("hello.json",{version:1,renderer:b.renderer,heartbeat:b.hello},4096)) {
                b.valid=false; b.message="Mail files unavailable. Use the regular client."; return;
            }
        }
        b.reads++;
        var manifest=wf_mail_read("manifest.json",4096);
        var value=undefined;
        if(wf_mail_manifest_valid(manifest) && (manifest.session!=b.session || manifest.revision!=b.revision)) {
            b.snapshot_reads++;
            value=wf_mail_read("snapshot.json",262144);
        }
        wf_mail_bridge_accept(manifest,value,now_ms,context);
    } catch(error) { b.valid=false; b.message="Mail unavailable. Use the regular client."; }
}
function wf_mail_bridge_ready() {
    if(!variable_global_exists("wf_mail_bridge") || !is_struct(global.wf_mail_bridge)) return false;
    var b=global.wf_mail_bridge;
    return b.enabled && b.valid && b.advanced>=0 && current_time>=b.advanced && current_time-b.advanced<5000;
}
function wf_mail_submit(action, payload) {
    var b=global.wf_mail_bridge;
    if(!wf_mail_bridge_ready() || !is_undefined(b.pending)) return false;
    if(!wf_mail_choice(action,["submit-text","mark-read","history","disconnect","reconnect"])) return false;
    if(action=="submit-text") {
        if(!wf_mail_fields(payload,["text"]) || !wf_mail_text(payload.text,1024)
            || string_length(string_trim(payload.text))==0 || b.snapshot.connection!="connected") return false;
    } else if(action=="mark-read") {
        if(!wf_mail_fields(payload,["through_key"]) || !wf_mail_id(payload.through_key)) return false;
    } else if(action=="history") {
        if(!wf_mail_fields(payload,["view","filter","cursor"]) || !wf_mail_choice(payload.view,["items","chat"])
            || !wf_mail_choice(payload.filter,payload.view=="items" ? ["all","received","sent"] : ["all"])
            || !wf_mail_id(payload.cursor)) return false;
    } else if(!wf_mail_fields(payload,[])) return false;
    if(is_undefined(b.room_id) && action!="disconnect" && action!="reconnect") return false;
    var request={version:1,session:b.session,renderer:b.renderer,
        sequence:b.sequence+1,action:action,payload:payload};
    variable_struct_set(request,"room",b.room_id);
    if(!wf_mail_write("request.json",request,8192)) {
        b.valid=false; b.message="Mail could not save the request. Use the regular client."; return false;
    }
    b.sequence++; b.pending=request; b.message="Queued for the client.";
    return true;
}
function wf_mail_bridge_shutdown() {
    if(!variable_global_exists("wf_mail_bridge") || !is_struct(global.wf_mail_bridge)) return;
    wf_mail_bridge_clear("Mail closed."); global.wf_mail_bridge.enabled=false;
}
