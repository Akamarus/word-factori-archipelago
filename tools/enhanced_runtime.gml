// Integration-authored production providers. Reads only on native factory entry.
function wf_ap_read_json(path) {
    var handle=-1;
    try {
        if(!file_exists(path)) return undefined;
        handle=file_text_open_read(path);
        if(handle==-1) return undefined;
        var content="";
        while(!file_text_eof(handle)) content+=file_text_readln(handle);
        file_text_close(handle); handle=-1;
        return json_parse(content);
    } catch(error) {
        if(handle!=-1) file_text_close(handle);
        return undefined;
    }
}
function wf_access_levels() {
    if(!instance_exists(oPersistent) || !variable_instance_exists(oPersistent,"levels")) return undefined;
    return oPersistent.levels;
}
function wf_access_context() {
    if(!wf_access_active()) return undefined;
    var levels=wf_access_levels();
    if(!is_array(levels) || array_length(levels)<6 || !is_struct(levels[0])
        || !variable_struct_exists(levels[0],"wf_ap")) return undefined;
    return levels[0].wf_ap;
}
function wf_ap_context() {
    var marker=wf_access_context();
    if(!wf_access_context_valid(marker)) return undefined;
    var needs=!variable_struct_exists(marker,"announced") || !marker.announced;
    var due=!variable_struct_exists(marker,"announce_retry_at") || current_time>=marker.announce_retry_at;
    if(needs && due) {
        marker.announce_retry_at=current_time+5000;
        try {
            var status=json_parse("{}");
            var names=["schema","mode","room","layout","checks_contract","capability"];
            for(var i=0;i<array_length(names);i++) variable_struct_set(status,names[i],variable_struct_get(marker,names[i]));
            writeJsonFileFromStruct("mods/word factori archipelago/archipelago_native_status.json",status,true);
            marker.announced=true;
        } catch(error) {
            marker.announced=false;
            show_debug_message("AP native status write failed: "+string(error));
        }
    }
    return marker;
}
function wf_ap_enabled() { return wf_access_context_valid(wf_ap_context()); }
function wf_access_payload() {
    wf_ap_context();
    return wf_ap_read_json("mods/word factori archipelago/archipelago_runtime.json");
}
