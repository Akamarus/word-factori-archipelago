// Authored isolated test: native production, goal consumption and win journal.
var namespace_path=string_lower(string_replace_all(game_save_id,"\\","/"));
if(string_pos("/wf_ap_typeword_probe_20260915/",namespace_path)==0) { game_end(); exit; }
tests=[]; snapshots={}; external_count=0;
function wf_probe_external() { external_count++; }
function emit_result(value) { show_debug_message("WF_TYPEWORD_RESULT:NATIVE_NONCE:"+json_stringify(value)); }
try {
    global.mods={folder:""}; global.feature_flags={rotated_outputs:false};
    recipes=loadB64JsonFileAsStruct("recipes.data",true);
    levels=["II"]; word_list=[]; histograms={}; latest_score={}; prev_score={}; urls={sgg:"disabled"};
    var identity=instance_create_depth(0,0,0,oIdentity);
    full_recipe_list=[]; refreshRecipeList();
    var input=instance_create_depth(0,0,0,oInput);
    var control=instance_create_depth(0,0,0,oControl);
    var goal=instance_create_depth(0,0,0,oFinalWordMain);
    var toggle=instance_create_depth(0,0,0,oMenuToggle); toggle.state=3;
    if(layer_get_id("GUIElements")==-1) layer_create(0,"GUIElements");
    var cases=json_parse(QUANTITY_CASES);
    var rows=[];
    for(var c=0;c<array_length(cases);c++) {
        with(oModule) instance_destroy();
        var spec=cases[c]; var nodes=spec.nodes; var graph=[];
        identity.current_save_slot=c+10;
        variable_struct_set(identity.save_data.slots,string(c+10),{});
        setLevel(spec.word,-1,3,false);
        control.buildings=[]; control.cycle_count=0; control.floater_count=0;
        control.win_stats=undefined; control.win_already_triggered=false;
        goal.counts=array_create(string_length(spec.word),0); goal.num_words_completed=0;
        for(var n=0;n<array_length(nodes);n++) {
            var parts=string_split(nodes[n].machine,"_");
            var building=new Building(asset_get_index(parts[0]),array_length(parts)>1 ? parts[1] : "",n);
            array_push(graph,building); array_push(control.buildings,building);
            // A nonvisual module dispatches native Building.produce during native doTick.
            // It is not a claim about screen placement or efficiency scoring.
            var proxy=instance_create_depth(0,0,0,oIFactory); proxy.building=building;
        }
        for(var n=0;n<array_length(nodes);n++) for(var p=0;p<array_length(nodes[n].inputs);p++) {
            var pipe=new LetterPipe(2,graph[nodes[n].inputs[p]],graph[n]);
        }
        for(var p=0;p<array_length(spec.roots);p++) {
            var sink=new Building(oFinalWord,string_char_at(spec.word,p+1)+"_"+string(p));
            var pipe=new LetterPipe(2,graph[spec.roots[p]],sink);
            array_push(control.buildings,sink);
        }
        var premature=false;
        for(var tick=0;tick<20000 && !control.win_already_triggered;tick++) {
            control.doTick(); control.try_win_condition();
            if(goal.num_words_completed<10 && isLevelBeaten(spec.word)) premature=true;
        }
        var passed=control.win_already_triggered && goal.num_words_completed==10 && isLevelBeaten(spec.word) && !premature;
        array_push(tests,{name:spec.name,passed:passed,evidence_kind:"native_word_goal_and_journal"});
        array_push(rows,{name:spec.name,passed:passed,words:goal.num_words_completed,ticks:tick,budget:spec.budget});
    }
    snapshots={rows:rows,pipe_length:2,required_words:10};
    emit_result({schema:1,tests:tests,snapshots:snapshots,save_namespace:game_save_id,native_source_sha256:NATIVE_SOURCE_HASHES});
} catch(failure) { emit_result({schema:1,tests:tests,snapshots:snapshots,failure:failure}); }
game_end();
