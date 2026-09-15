// Authored feasibility candidate only. These explicit inputs are probe-owned.
// probe_* keys are NOT a production runtime/receipt contract.
function wf_tw_active() {
    if (!variable_global_exists("mods") || !is_struct(global.mods)
        || !variable_struct_exists(global.mods,"folder") || !is_string(global.mods.folder)) return false;
    if (string_lower(string_replace_all(global.mods.folder,"\\","/")) != "mods/word factori archipelago") return false;
    if (!variable_instance_exists(oPersistent,"wf_probe_gate")) return true;
    var gate=oPersistent.wf_probe_gate;
    return !is_struct(gate) || !variable_struct_exists(gate,"enabled") || gate.enabled != false;
}
function wf_tw_safe_counts() {
    var counts={IFactory:-1};
    var names=PROBE_MODULE_NAMES;
    for(var i=0;i<array_length(names);i++) variable_struct_set(counts,names[i],0);
    // Bender Access is guaranteed precollected equipment for this AP design.
    counts.Bend=-1;
    return counts;
}
function wf_tw_context_valid(value) {
    if (!is_struct(value)) return false;
    var required=["schema","mode","room","layout","probe_contract","probe_ack"];
    for(var i=0;i<array_length(required);i++) if(!variable_struct_exists(value,required[i])) return false;
    return value.schema==1 && value.mode=="enhanced" && is_string(value.room) && string_length(value.room)==64
        && is_string(value.layout) && string_length(value.layout)==64
        && value.probe_contract=="native-enforcement-1" && value.probe_ack=="native-enforcement-1";
}
function wf_tw_entry_counts() {
    // Safe defaults are complete: absent family keys must not mean unlimited.
    oPersistent.wf_probe_limits=wf_tw_safe_counts();
    if(!variable_instance_exists(oPersistent,"wf_probe_gate") || !is_struct(oPersistent.wf_probe_gate)) return oPersistent.wf_probe_limits;
    var gate=oPersistent.wf_probe_gate;
    if(!variable_struct_exists(gate,"context") || !wf_tw_context_valid(gate.context)) return oPersistent.wf_probe_limits;
    var context=gate.context;
    var previous=variable_struct_get(gate,"last");
    var retained=is_struct(previous) && previous.room==context.room && previous.layout==context.layout
        && previous.probe_contract==context.probe_contract && previous.probe_ack==context.probe_ack;
    if(retained) oPersistent.wf_probe_limits=json_parse(json_stringify(previous.probe_family_counts));
    var payload=variable_struct_get(gate,"payload");
    if(!wf_tw_context_valid(payload) || payload.room!=context.room || payload.layout!=context.layout) return oPersistent.wf_probe_limits;
    if(!variable_struct_exists(payload,"revision") || (!is_real(payload.revision) && !is_int64(payload.revision))
        || payload.revision<0 || payload.revision!=floor(payload.revision)
        || (retained && payload.revision<previous.revision)) return oPersistent.wf_probe_limits;
    if(!variable_struct_exists(payload,"probe_family_counts") || !is_struct(payload.probe_family_counts)) return oPersistent.wf_probe_limits;
    var counts=payload.probe_family_counts;
    var names=variable_struct_get_names(wf_tw_safe_counts());
    if(variable_struct_names_count(counts)!=array_length(names)) return oPersistent.wf_probe_limits;
    for(var i=0;i<array_length(names);i++) {
        if(!variable_struct_exists(counts,names[i])) return oPersistent.wf_probe_limits;
        var count=variable_struct_get(counts,names[i]);
        if((!is_real(count) && !is_int64(count)) || (count!=0 && count!=-1)) return oPersistent.wf_probe_limits;
    }
    if(counts.IFactory!=-1) return oPersistent.wf_probe_limits;
    gate.last=json_parse(json_stringify(payload));
    oPersistent.wf_probe_limits=json_parse(json_stringify(counts));
    return json_parse(json_stringify(counts));
}
function wf_tw_limit(name) {
    if(!is_string(name)) name=object_get_name(name);
    if(string_copy(name,1,1)=="o") name=string_delete(name,1,1);
    name=string_replace_all(name,"GUI","");
    if(name=="IFactory") return -1;
    if(!variable_instance_exists(oPersistent,"wf_probe_limits") || !is_struct(oPersistent.wf_probe_limits)
        || !variable_struct_exists(oPersistent.wf_probe_limits,name)) return 0;
    return variable_struct_get(oPersistent.wf_probe_limits,name);
}
function wf_tw_allowed(module, tag) {
    if(!wf_tw_active()) return true;
    if(module==oIFactory || module==oFinalWord) return true;
    // Conservative approved restriction: no AP custom output or recipe previews.
    if(module==oCustomBuilding) return false;
    var name=object_get_name(module);
    if(module==oRotate || module==oReflect) name+="_"+tag;
    return wf_tw_limit(name)==-1;
}
