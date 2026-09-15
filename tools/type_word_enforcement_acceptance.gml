// Authored bounded native enforcement acceptance. No player save is loaded.
var namespace_path = string_lower(string_replace_all(game_save_id, "\\", "/"));
if (string_pos("/wf_ap_typeword_probe_20260915/", namespace_path) == 0) { game_end(); exit; }
tests=[]; snapshots={}; external_count=0;
function wf_probe_external() { external_count++; }
function record_test(name, passed, evidence_kind) { array_push(tests,{name:name,passed:passed,evidence_kind:evidence_kind}); }
function snapshot(name, value) { variable_struct_set(snapshots,name,json_parse(json_stringify(value))); }
function emit_result(value) { show_debug_message("WF_TYPEWORD_RESULT:NATIVE_NONCE:"+json_stringify(value)); }
function clone(value) { return json_parse(json_stringify(value)); }
function enter_probe() { setLevel("VV",-1,3,false); }
function limits_are_safe() {
    return get_current_module_count("Merger2")==0 && get_current_module_count("Rotate_cw")==0
        && get_current_module_count("Reflect_vert")==0 && get_current_module_count("IFactory")==-1
        && get_current_module_count("Bend")==-1;
}
try {
    global.mods={folder:"mods/word factori archipelago"};
    global.feature_flags={rotated_outputs:false};
    recipes=loadB64JsonFileAsStruct("recipes.data",true);
    levels=[{text:"VV",module_counts:{},wf_ap_caps:{}}]; word_list=[]; histograms={}; latest_score={}; prev_score={}; urls={sgg:"disabled"};
    var identity=instance_create_depth(0,0,0,oIdentity);
    full_recipe_list=[]; refreshRecipeList();
    var input=instance_create_depth(0,0,0,oInput);
    var slot=variable_struct_get(identity.save_data.slots,"0");
    wf_probe_gate={context:undefined,payload:undefined}; wf_access_last=undefined;
    global.mods.folder="";
    // Exact production marker and runtime shapes, supplied by isolated providers.
    var context=json_parse("{\"schema\":2,\"mode\":\"enhanced\",\"room\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"layout\":\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\",\"checks_contract\":\"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\",\"capability\":\"free_word_machine_enforcement_v1\"}");
    var payload=clone(context); payload.revision=1; payload.levels=[{text:"VV",module_counts:{}}];
    payload.machine_counts={Bend:-1,Rotate_cw:0,Rotate_ccw:0,Reflect_hor:0,Reflect_vert:0,Merger2:0,Merger3:0,Merger4:0,IFactory:-1};
    wf_probe_gate.context=clone(context); wf_probe_gate.payload=clone(payload);
    enter_probe();
    // Stock control: the candidate hooks delegate to the unchanged native path.
    current_module_counts=clone(payload.machine_counts);
    record_test("stock free word ignores Bender-only limits",get_current_module_count("Merger2")==-1,"native_function");
    global.mods.folder="mods/word factori archipelago"; enter_probe();
    record_test("free-word locked merger",get_current_module_count("Merger2")==0,"native_function");
    record_test("I remains available",get_current_module_count("IFactory")==-1,"native_function");
    record_test("Bender usable",get_current_module_count("Bend")==-1,"native_function");
    var locked_names=["Rotate_cw","Rotate_ccw","Reflect_hor","Reflect_vert","Merger3","Merger4"];
    for(var name_index=0;name_index<6;name_index++) {
        var locked=locked_names[name_index];
        record_test("locked family "+locked,get_current_module_count(locked)==0,"native_function");
    }
    snapshot("bender_only",current_module_counts);
    // Client JSON uses integer tokens; GameMaker's own writer uses decimals.
    wf_probe_gate.payload.machine_counts=json_parse("{\"Bend\":-1,\"Rotate_cw\":0,\"Rotate_ccw\":0,\"Reflect_hor\":0,\"Reflect_vert\":0,\"Merger2\":0,\"Merger3\":0,\"Merger4\":0,\"IFactory\":-1}");
    wf_probe_gate.payload.revision=json_parse("9000000001"); enter_probe();
    record_test("client integer JSON revision and counts accepted",limits_are_safe() && get_current_module_count("Bend")==-1 && wf_access_last.revision==9000000001,"native_function");
    snapshot("client_integer_snapshot",wf_access_last);
    var bad_names=["missing","malformed","stale","wrong room","wrong layout","old contract","old acknowledgment","missing family","unlimited locked source"];
    for(var bad=0;bad<array_length(bad_names);bad++) {
        wf_probe_gate.context=clone(context); wf_probe_gate.payload=clone(payload); wf_access_last=undefined;
        switch(bad) {
            case 0: wf_probe_gate.payload=undefined; break;
            case 1: wf_probe_gate.payload="bad JSON value"; break;
            case 2: enter_probe(); wf_probe_gate.payload.revision=0; break;
            case 3: variable_struct_set(wf_probe_gate.payload,"room",string_repeat("c",64)); break;
            case 4: wf_probe_gate.payload.layout=string_repeat("d",64); break;
            case 5: wf_probe_gate.payload.schema=1; break;
            case 6: wf_probe_gate.context.capability="enhanced"; break;
            case 7: variable_struct_remove(wf_probe_gate.payload.machine_counts,"Merger2"); break;
            case 8: wf_probe_gate.payload.machine_counts.Merger2="-1"; break;
        }
        enter_probe(); record_test("fail closed "+bad_names[bad],limits_are_safe(),"native_function");
    }
    wf_probe_gate.context=undefined; enter_probe();
    record_test("missing context fails closed",limits_are_safe(),"native_function");
    wf_probe_gate.context=clone(context); wf_probe_gate.payload=clone(payload); wf_access_last=undefined;
    wf_probe_gate.payload.machine_counts.Merger2=-1; enter_probe();
    record_test("same-room cache starts with Merger2 unlocked",get_current_module_count("Merger2")==-1,"native_function");
    wf_probe_gate.payload=undefined; enter_probe();
    record_test("validated same-room inventory retained",get_current_module_count("Merger2")==-1
        && get_current_module_count("IFactory")==-1 && get_current_module_count("Bend")==-1
        && get_current_module_count("Rotate_cw")==0,"native_function");
    snapshot("retained_same_room",current_module_counts);
    wf_probe_gate.payload=clone(payload); wf_probe_gate.payload.revision=2;
    wf_probe_gate.payload.machine_counts.Merger2=-1; enter_probe();
    record_test("previous room has Merger2 unlocked",get_current_module_count("Merger2")==-1,"native_function");
    wf_probe_gate.payload=undefined;
    variable_struct_set(wf_probe_gate.context,"room",string_repeat("e",64)); enter_probe();
    record_test("previous room inventory never reused",limits_are_safe(),"native_function");
    wf_probe_gate.context=clone(context); wf_probe_gate.payload=clone(payload); wf_access_last=undefined;
    // Invalid newer snapshots must retain a previously accepted same-context unlock.
    wf_probe_gate.context=clone(context); wf_probe_gate.payload=clone(payload); wf_access_last=undefined;
    wf_probe_gate.payload.machine_counts.Merger2=-1; enter_probe();
    var invalid_cases=["fractional revision","oversized revision","negative revision","boolean revision","same revision conflict","wrong checks contract","uppercase digest","extra family","bad level text","missing cap"];
    for(var invalid=0;invalid<array_length(invalid_cases);invalid++) {
        wf_probe_gate.payload=clone(payload); wf_probe_gate.payload.revision=2;
        switch(invalid) {
            case 0: wf_probe_gate.payload.revision=1.5; break;
            case 1: wf_probe_gate.payload.revision=9007199254740992; break;
            case 2: wf_probe_gate.payload.revision=-1; break;
            case 3: wf_probe_gate.payload.revision=true; break;
            case 4: wf_probe_gate.payload.revision=1; break;
            case 5: wf_probe_gate.payload.checks_contract=string_repeat("d",64); break;
            case 6: variable_struct_set(wf_probe_gate.payload,"room",string_repeat("A",64)); break;
            case 7: wf_probe_gate.payload.machine_counts.Extra=0; break;
            case 8: wf_probe_gate.payload.levels[0].text="XX"; break;
            case 9: levels[0].wf_ap_caps={Bend:2}; break;
        }
        enter_probe();
        // A changed native cap invalidates the entire retained snapshot as well.
        record_test("reject "+invalid_cases[invalid],get_current_module_count("Merger2")==(invalid==9 ? 0 : -1),"native_function");
    }
    levels[0].wf_ap_caps={};
    wf_probe_gate.context=clone(context); wf_probe_gate.payload=clone(payload); wf_access_last=undefined;
    wf_probe_gate.payload.machine_counts.Merger2=-1; enter_probe();
    wf_probe_gate.context.checks_contract=string_repeat("d",64);
    record_test("context change invalidates between entries",get_current_module_count("Merger2")==0,"native_function");
    wf_probe_gate.context=clone(context);
    record_test("invalidated cache cannot revive without entry",get_current_module_count("Merger2")==0,"native_function");
    wf_probe_gate.context=clone(context); wf_probe_gate.payload=clone(payload); wf_access_last=undefined;
    enter_probe();
    record_test("tagged rotation preview remains locked",getModuleRecipe(oRotate,"cw",[new Letter("I")]).toString()=="?","native_function");
    record_test("tagged reflection preview remains locked",getModuleRecipe(oReflect,"vert",[new Letter("I")]).toString()=="?","native_function");
    levels[0]={text:"VV",module_counts:{Bend:2,Merger2:3},wf_ap_caps:{Bend:2,Merger2:3}};
    wf_probe_gate.payload.levels[0].module_counts={Bend:2,Merger2:0};
    setLevel("VV",0,1,false);
    record_test("campaign finite cap retained",get_current_module_count("Bend")==2,"native_function");
    record_test("campaign native cap cannot grant locked family",get_current_module_count("Merger2")==0,"native_function");
    levels[0]={text:"VV",module_counts:{},wf_ap_caps:{}};
    wf_probe_gate.payload=clone(payload); wf_access_last=undefined;
    var replay_modes=[0,1,3,4,5,7];
    for(var mode_index=0;mode_index<array_length(replay_modes);mode_index++) {
        var replay_mode=replay_modes[mode_index]; setLevel("VV",-1,replay_mode,false);
        record_test("noncampaign replay mode "+string(replay_mode),limits_are_safe(),"native_function");
    }
    global.mods.folder=""; enter_probe();
    record_test("AP unselected keeps native behavior",get_current_module_count("Merger2")==-1,"native_function");
    global.mods.folder="mods/word factori archipelago"; global.mods.folder="mods/another mod"; enter_probe();
    record_test("other mod keeps native behavior",get_current_module_count("Merger2")==-1,"native_function");
    global.mods.folder=""; enter_probe();
    record_test("vanilla keeps native behavior",get_current_module_count("Merger2")==-1,"native_function");
    global.mods.folder="mods/word factori archipelago"; enter_probe();
    // Serialized factory graph consumed by the original native construction path.
    // Goals first, then Merger2 nodes, then four sources; no letters are injected.
    var layout={uuid:"probe-import-vv",building_count:6,output:"VV",buildings:[
        {module:"oFinalWord",tag:"V_0",topo_index:0},{module:"oFinalWord",tag:"V_1",topo_index:1},
        {module:"oMerger2",tag:"",topo_index:2},{module:"oMerger2",tag:"",topo_index:3},
        {module:"oIFactory",tag:"",topo_index:4},{module:"oIFactory",tag:"",topo_index:5},
        {module:"oIFactory",tag:"",topo_index:6},{module:"oIFactory",tag:"",topo_index:7}],pipes:[
        {from:4,to:2,dist:2},{from:5,to:2,dist:2},{from:6,to:3,dist:2},{from:7,to:3,dist:2},
        {from:2,to:0,dist:2},{from:3,to:1,dist:2}]};
    var saved_layout=json_stringify(layout);
    var graph=makeBuildingsFromTemplate(json_parse(saved_layout));
    var control=instance_create_depth(0,0,0,oControl); control.buildings=graph;
    var goal=instance_create_depth(0,0,0,oFinalWordMain);
    var toggle=instance_create_depth(0,0,0,oMenuToggle); toggle.state=3;
    if(layer_get_id("GUIElements")==-1) layer_create(0,"GUIElements");
    for(var node=2;node<array_length(graph);node++) {
        var module_inst=instance_create_depth(0,0,0,graph[node].module); module_inst.building=graph[node];
    }
    record_test("imported locked toolbar count is zero",get_current_module_count("Merger2")==0,"native_function");
    var journal_before=json_stringify(slot.recipes);
    var preview=graph[2].getRecipe([new Letter("I"),new Letter("I")]);
    var direct_preview=getModuleRecipe(oMerger2,"",[new Letter("I"),new Letter("I")]);
    record_test("locked native recipe preview blocked",preview.toString()=="?" && direct_preview.toString()=="?" && json_stringify(slot.recipes)==journal_before,"native_function");
    for(var tick=0;tick<60;tick++) { control.doTick(); control.try_win_condition(); }
    record_test("locked imported merger produces no word",goal.num_words_completed==0 && !isLevelBeaten("VV"),"native_production");
    record_test("locked imported merger records no recipe",!isRecipeFound("oMerger2","I I","V"),"native_production");
    record_test("locked graph emits no queued merger output",graph[2].queued_produce_letter==undefined && graph[3].queued_produce_letter==undefined,"native_production");
    snapshot("locked_import",{counts:current_module_counts,slot:slot,words:goal.num_words_completed,ticks:control.cycle_count});
    // Inventory refresh comes from actual setLevel -> get_level_module_counts.
    wf_probe_gate.payload.revision=2; wf_probe_gate.payload.machine_counts.Merger2=-1;
    record_test("item waits for factory entry",get_current_module_count("Merger2")==0,"native_function");
    enter_probe();
    record_test("re-entry applies Merger2 without restart",get_current_module_count("Merger2")==-1,"native_function");
    var premature=false;
    for(var tick=0;tick<100 && !control.win_already_triggered;tick++) {
        control.doTick(); control.try_win_condition();
        if(goal.num_words_completed<10 && isLevelBeaten("VV")) premature=true;
    }
    record_test("same imported layout resumes native production",goal.num_words_completed==10 && control.win_already_triggered && isLevelBeaten("VV") && !premature,"native_production");
    record_test("unlocked merger discovers native recipe",isRecipeFound("oMerger2","I I","V"),"native_production");
    record_test("import layout preserved through lock and unlock",json_stringify(layout)==saved_layout && control.buildings[2]==graph[2],"native_production");
    record_test("order win no campaign credit",variable_struct_names_count(slot.beaten_levels)==0,"native_production");
    snapshot("unlocked_import",{counts:current_module_counts,slot:slot,words:goal.num_words_completed,ticks:control.cycle_count});
    // Native custom factory tree and real timing cache, warmed while AP is off.
    var custom_template={uuid:"probe-custom-v",building_count:3,output:"V",buildings:[
        {module:"oMerger2",tag:"",topo_index:0},{module:"oIFactory",tag:"",topo_index:1},{module:"oIFactory",tag:"",topo_index:2}],
        pipes:[{from:1,to:0,dist:2},{from:2,to:0,dist:2}]};
    slot.templates=[custom_template];
    var custom_layout_before=json_stringify(slot.templates);
    global.mods.folder=""; enter_probe();
    var custom=new Building(oCustomBuilding,"probe-custom-v");
    var warm_output=undefined;
    for(var warm_tick=0;warm_tick<30 && warm_output==undefined;warm_tick++) warm_output=custom.produce(400);
    var cached_ticks=custom.getTicksTillProduce(400);
    record_test("stock custom emits native template output",warm_output!=undefined && warm_output.toString()=="V" && cached_ticks<10000,"native_production");
    // Full inventory is deliberately insufficient for unsupported custom factories.
    global.mods.folder="mods/word factori archipelago";
    wf_probe_gate.payload.revision=3;
    var family_names=variable_struct_get_names(wf_probe_gate.payload.machine_counts);
    for(var f=0;f<array_length(family_names);f++) variable_struct_set(wf_probe_gate.payload.machine_counts,family_names[f],-1);
    enter_probe();
    var any_custom_output=false;
    for(var blocked_tick=0;blocked_tick<30;blocked_tick++) if(custom.produce(400)!=undefined) any_custom_output=true;
    var custom_preview=getModuleRecipe(oCustomBuilding,"probe-custom-v",[]);
    record_test("cached custom output blocked with full inventory",!any_custom_output && custom.getTicksTillProduce(400)==10000,"native_production");
    record_test("custom preview blocked",custom_preview.toString()=="?" && custom.getRecipe([]).toString()=="?","native_function");
    record_test("unsupported custom layout remains saved",json_stringify(slot.templates)==custom_layout_before,"native_production");
    // Recipe-only rooms use the same gate; order state cannot grant machinery.
    wf_probe_gate.payload=clone(payload); wf_probe_gate.payload.revision=4; wf_probe_gate.payload.probe_orders_enabled=false; wf_probe_gate.payload.probe_recipes_enabled=true;
    enter_probe();
    record_test("recipes on orders off still restricts families",limits_are_safe(),"native_function");
    snapshot("custom",{stock_cached_ticks:cached_ticks,blocked_output:any_custom_output,layout_preserved:json_stringify(slot.templates)==custom_layout_before});
    var supported=array_all(tests,function(item) { return item.passed; });
    emit_result({schema:1,save_namespace:game_save_id,enforcement_supported:supported,tests:tests,snapshots:snapshots,
        native_hooks:NATIVE_ENFORCEMENT_HOOKS,custom_policy:"AP custom production and previews blocked even with full inventory; no per-template validation",
        external_calls_stubbed:["Task1 normal object events and service stubs","PersistentData notification UI","module presentation forwarded to native Building.produce"],native_source_sha256:NATIVE_SOURCE_HASHES});
} catch(failure) {
    emit_result({schema:1,save_namespace:game_save_id,enforcement_supported:false,tests:tests,snapshots:snapshots,failure:failure,native_hooks:NATIVE_ENFORCEMENT_HOOKS,native_source_sha256:NATIVE_SOURCE_HASHES});
}
game_end();
