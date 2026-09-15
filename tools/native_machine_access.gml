// Shared production enforcement. Providers supply loaded marker/levels and entry-time JSON.
// This file never opens a file, and has no externally supplied enable switch.
function wf_access_active() {
    if (!variable_global_exists("mods") || !is_struct(global.mods)
        || !variable_struct_exists(global.mods,"folder") || !is_string(global.mods.folder)) return false;
    var folder=string_lower(string_replace_all(global.mods.folder,"\\","/"));
    var expected="mods/word factori archipelago";
    var absolute=string_lower(string_replace_all(environment_get_variable("LOCALAPPDATA"),"\\","/")+"/factori/"+expected);
    return folder==expected || folder=="word factori archipelago" || folder==absolute;
}
function wf_access_digest(value) {
    if(!is_string(value) || string_length(value)!=64) return false;
    for(var i=1;i<=64;i++) if(string_pos(string_char_at(value,i),"0123456789abcdef")==0) return false;
    return true;
}
function wf_access_context_valid(value) {
    if(!is_struct(value)) return false;
    var fields=["schema","mode","room","layout","checks_contract","capability"];
    for(var i=0;i<array_length(fields);i++) if(!variable_struct_exists(value,fields[i])) return false;
    return ((value.schema==2 && value.capability=="free_word_machine_enforcement_v1")
        || (value.schema==3 && value.capability=="progressive_machine_enforcement_v1")) && value.mode=="enhanced"
        && wf_access_digest(value.room) && wf_access_digest(value.layout) && wf_access_digest(value.checks_contract);
}
function wf_access_same_context(a,b) {
    return wf_access_context_valid(a) && wf_access_context_valid(b)
        && a.schema==b.schema && a.capability==b.capability
        && a.room==b.room && a.layout==b.layout && a.checks_contract==b.checks_contract;
}
function wf_access_quantity() {
    if(!wf_access_active()) return false;
    var context=wf_access_context();
    return wf_access_context_valid(context) && context.schema==3;
}
function wf_access_safe_counts() {
    return {IFactory:-1,Bend:wf_access_quantity() ? 1 : -1,Rotate_cw:0,Rotate_ccw:0,Reflect_hor:0,Reflect_vert:0,Merger2:0,Merger3:0,Merger4:0};
}
function wf_access_integer(value) {
    return (is_real(value) || is_int64(value)) && !is_bool(value)
        && value>=0 && value<=9007199254740991 && value==floor(value);
}
function wf_access_counts_valid(counts,context) {
    if(!is_struct(counts)) return false;
    var names=variable_struct_get_names(wf_access_safe_counts());
    if(variable_struct_names_count(counts)!=array_length(names)) return false;
    for(var i=0;i<array_length(names);i++) {
        if(!variable_struct_exists(counts,names[i])) return false;
        var count=variable_struct_get(counts,names[i]);
        if((!is_real(count) && !is_int64(count)) || is_bool(count)) return false;
        if(context.schema==3) { if(count!=-1 && (!wf_access_integer(count) || count>4)) return false; }
        else if(count!=0 && count!=-1) return false;
    }
    return counts.IFactory==-1 && (context.schema!=3 || (counts.Rotate_cw==counts.Rotate_ccw && counts.Reflect_hor==counts.Reflect_vert));
}
function wf_access_levels_valid(entries) {
    var native_levels=wf_access_levels();
    if(!is_array(entries) || !is_array(native_levels) || array_length(entries)!=array_length(native_levels)) return false;
    var families=wf_access_safe_counts();
    for(var index=0;index<array_length(entries);index++) {
        var entry=entries[index]; var native_entry=native_levels[index];
        if(!is_struct(entry) || !variable_struct_exists(entry,"text") || !is_string(entry.text)
            || !variable_struct_exists(entry,"module_counts") || !is_struct(entry.module_counts)
            || !is_struct(native_entry) || !variable_struct_exists(native_entry,"text") || entry.text!=native_entry.text
            || !variable_struct_exists(native_entry,"wf_ap_caps") || !is_struct(native_entry.wf_ap_caps)) return false;
        var counts=entry.module_counts; var names=variable_struct_get_names(counts);
        for(var i=0;i<array_length(names);i++) {
            var count=variable_struct_get(counts,names[i]);
            if(!variable_struct_exists(families,names[i]) || !wf_access_integer(count) || count>10000) return false;
        }
        var caps=native_entry.wf_ap_caps; names=variable_struct_get_names(caps);
        for(var i=0;i<array_length(names);i++) {
            var cap=variable_struct_get(caps,names[i]);
            if(!variable_struct_exists(families,names[i]) || !wf_access_integer(cap) || cap>10000
                || !variable_struct_exists(counts,names[i]) || variable_struct_get(counts,names[i])>cap) return false;
        }
    }
    return true;
}
function wf_access_snapshot_valid(value,context) {
    return wf_access_same_context(value,context) && variable_struct_exists(value,"revision")
        && wf_access_integer(value.revision) && variable_struct_exists(value,"machine_counts")
        && wf_access_counts_valid(value.machine_counts,context) && variable_struct_exists(value,"levels")
        && wf_access_levels_valid(value.levels);
}
function wf_access_snapshot_equal(a,b) {
    // Semantic comparison ignores JSON object key order.
    var names=variable_struct_get_names(wf_access_safe_counts());
    for(var i=0;i<array_length(names);i++)
        if(variable_struct_get(a.machine_counts,names[i])!=variable_struct_get(b.machine_counts,names[i])) return false;
    for(var index=0;index<array_length(a.levels);index++) {
        var left=a.levels[index].module_counts; var right=b.levels[index].module_counts;
        names=variable_struct_get_names(left);
        if(array_length(names)!=variable_struct_names_count(right)) return false;
        for(var i=0;i<array_length(names);i++)
            if(!variable_struct_exists(right,names[i]) || variable_struct_get(left,names[i])!=variable_struct_get(right,names[i])) return false;
    }
    return true;
}
function wf_access_entry_counts() {
    var context=wf_access_context();
    var previous=undefined;
    if(variable_instance_exists(oPersistent,"wf_access_last")) previous=oPersistent.wf_access_last;
    oPersistent.wf_access_limits=wf_access_safe_counts();
    oPersistent.wf_access_last=undefined;
    if(!wf_access_active() || !wf_access_context_valid(context)) return oPersistent.wf_access_limits;
    var retained=wf_access_snapshot_valid(previous,context);
    if(retained) {
        oPersistent.wf_access_last=previous;
        oPersistent.wf_access_limits=json_parse(json_stringify(previous.machine_counts));
    }
    var payload=wf_access_payload();
    if(!wf_access_snapshot_valid(payload,context)) return oPersistent.wf_access_limits;
    if(retained && (payload.revision<previous.revision
        || (payload.revision==previous.revision && !wf_access_snapshot_equal(payload,previous)))) return oPersistent.wf_access_limits;
    oPersistent.wf_access_last=json_parse(json_stringify(payload));
    oPersistent.wf_access_limits=json_parse(json_stringify(payload.machine_counts));
    return json_parse(json_stringify(oPersistent.wf_access_limits));
}
function wf_access_limit(name) {
    if(!is_string(name)) name=object_get_name(name);
    if(string_copy(name,1,1)=="o") name=string_delete(name,1,1);
    name=string_replace_all(name,"GUI","");
    var counts=wf_access_safe_counts();
    if(variable_instance_exists(oPersistent,"wf_access_last")) {
        if(wf_access_same_context(oPersistent.wf_access_last,wf_access_context())
            && variable_instance_exists(oPersistent,"wf_access_limits")) counts=oPersistent.wf_access_limits;
        else {
            oPersistent.wf_access_last=undefined;
            oPersistent.wf_access_limits=wf_access_safe_counts();
        }
    }
    if(!variable_struct_exists(counts,name)) return 0;
    return variable_struct_get(counts,name);
}
function wf_access_allowed(module,tag) {
    if(!wf_access_active()) return true;
    if(wf_access_quantity() && !wf_access_factory_allowed()) return false;
    if(module==oIFactory || module==oFinalWord) return true;
    // Preserve saved layouts; unsupported native custom output/previews stay blocked.
    if(module==oCustomBuilding) return false;
    var name=object_get_name(module);
    if(module==oRotate || module==oReflect) name+="_"+tag;
    return wf_access_limit(name)!=0;
}
function wf_ap_counts(index) {
    if(!wf_access_active() || !wf_access_integer(index)) return undefined;
    if(!variable_instance_exists(oPersistent,"wf_access_last")) return undefined;
    var payload=oPersistent.wf_access_last;
    if(!wf_access_same_context(payload,wf_access_context()) || index>=array_length(payload.levels)) return undefined;
    return json_parse(json_stringify(payload.levels[index].module_counts));
}

function wf_access_poll() {
    if(!wf_access_quantity()) return;
    if(variable_instance_exists(oPersistent,"wf_access_next_poll") && current_time<oPersistent.wf_access_next_poll) return;
    oPersistent.wf_access_next_poll=current_time+250;
    wf_access_entry_counts();
}
function wf_access_name(module,tag) {
    var name=object_get_name(module);
    if(module==oRotate || module==oReflect) name+="_"+tag;
    return string_delete(name,1,1);
}
function wf_access_family(name) {
    if(name=="Bend") return 0;
    if(name=="Rotate_cw" || name=="Rotate_ccw") return 1;
    if(name=="Reflect_hor" || name=="Reflect_vert") return 2;
    if(name=="Merger2") return 3;
    if(name=="Merger3") return 4;
    if(name=="Merger4") return 5;
    return -1;
}
function wf_access_caps() {
    if(!variable_instance_exists(oPersistent,"current_level_index") || oPersistent.current_level_index<0) return {};
    var entries=wf_access_levels(); var index=oPersistent.current_level_index;
    if(!is_array(entries) || index>=array_length(entries)) return {Bend:0,Merger2:0,Merger3:0,Merger4:0,Rotate_cw:0,Rotate_ccw:0,Reflect_hor:0,Reflect_vert:0};
    // Loaded, room-bound challenge restrictions survive missing/corrupt snapshots.
    return entries[index].wf_ap_caps;
}
function wf_access_add_count(counts,name) {
    if(name=="IFactory" || name=="FinalWord") return;
    var family=wf_access_family(name);
    if(family<0) { counts.invalid=true; return; }
    counts.families[family]++;
    var value=variable_struct_exists(counts.modules,name) ? variable_struct_get(counts.modules,name) : 0;
    variable_struct_set(counts.modules,name,value+1);
}
function wf_access_scene_counts() {
    var counts={families:[0,0,0,0,0,0],modules:{},invalid:false};
    for(var i=0;i<instance_number(oModule);i++) {
        var inst=instance_find(oModule,i);
        if(variable_instance_exists(inst,"is_temp_initial") && inst.is_temp_initial) continue;
        if(!variable_instance_exists(inst,"building") || !is_struct(inst.building)) continue;
        var machine=inst.building.module; var tag=inst.building.tag;
        // Native UI direction changes precede rebuilding the simulation graph.
        if(variable_instance_exists(inst,"state")) {
            if(machine==oRotate) tag=inst.state==1 ? "cw" : "ccw";
            if(machine==oReflect) tag=inst.state==1 ? "vert" : "hor";
        }
        wf_access_add_count(counts,wf_access_name(machine,tag));
    }
    return counts;
}
function wf_access_counts_allowed(counts) {
    if(counts.invalid) return false;
    var names=["Bend","Rotate_cw","Reflect_hor","Merger2","Merger3","Merger4"];
    for(var i=0;i<6;i++) {
        var limit=wf_access_limit(names[i]);
        if(limit!=-1 && counts.families[i]>limit) return false;
    }
    var caps=wf_access_caps(); names=variable_struct_get_names(caps);
    for(var i=0;i<array_length(names);i++) {
        var name=names[i]; var used=variable_struct_exists(counts.modules,name) ? variable_struct_get(counts.modules,name) : 0;
        if(used>variable_struct_get(caps,name)) return false;
    }
    return true;
}
function wf_access_factory_allowed(graph=undefined) {
    if(!wf_access_quantity()) return true;
    if(!wf_access_counts_allowed(wf_access_scene_counts())) return false;
    if(is_array(graph)) {
        var counts={families:[0,0,0,0,0,0],modules:{},invalid:false};
        for(var i=0;i<array_length(graph);i++) wf_access_add_count(counts,wf_access_name(graph[i].module,graph[i].tag));
        if(!wf_access_counts_allowed(counts)) return false;
    }
    return true;
}
function wf_access_remaining(name) {
    wf_access_poll();
    if(!is_string(name)) name=object_get_name(name);
    if(string_copy(name,1,1)=="o") name=string_delete(name,1,1);
    name=string_replace_all(name,"GUI","");
    if(name=="IFactory") return -1;
    var family=wf_access_family(name); if(family<0) return 0;
    var counts=wf_access_scene_counts(); var remaining=wf_access_limit(name);
    if(remaining!=-1) remaining=max(0,remaining-counts.families[family]);
    var caps=wf_access_caps();
    if(variable_struct_exists(caps,name)) {
        var used=variable_struct_exists(counts.modules,name) ? variable_struct_get(counts.modules,name) : 0;
        var cap_remaining=max(0,variable_struct_get(caps,name)-used);
        remaining=remaining==-1 ? cap_remaining : min(remaining,cap_remaining);
    }
    return remaining;
}
function wf_access_explain(graph) {
    var counts=wf_access_scene_counts();
    var simulated={families:[0,0,0,0,0,0],modules:{},invalid:false};
    for(var i=0;i<array_length(graph);i++) wf_access_add_count(simulated,wf_access_name(graph[i].module,graph[i].tag));
    var labels=["Bender","Rotation","Reflection","Merger2","Merger3","Merger4"];
    var names=["Bend","Rotate_cw","Reflect_hor","Merger2","Merger3","Merger4"];
    var message="AP: factory exceeds allowances";
    for(var i=0;i<6;i++) {
        var used=max(counts.families[i],simulated.families[i]); var limit=wf_access_limit(names[i]);
        if(limit!=-1 && used>limit) message+="; "+labels[i]+" "+string(used)+"/"+string(limit);
    }
    var caps=wf_access_caps(); names=variable_struct_get_names(caps);
    for(var i=0;i<array_length(names);i++) {
        var name=names[i]; var used=0;
        if(variable_struct_exists(counts.modules,name)) used=variable_struct_get(counts.modules,name);
        if(variable_struct_exists(simulated.modules,name)) used=max(used,variable_struct_get(simulated.modules,name));
        var cap=variable_struct_get(caps,name);
        if(used>cap) message+="; level "+name+" "+string(used)+"/"+string(cap);
    }
    if(counts.invalid || simulated.invalid) message+="; custom factories are unsupported";
    message+=". Remove excess machines or wait for upgrades.";
    if(!variable_instance_exists(oPersistent,"wf_access_notice_at") || current_time>=oPersistent.wf_access_notice_at) {
        oPersistent.wf_access_notice_at=current_time+5000;
        wf_access_notice(message);
    }
}
