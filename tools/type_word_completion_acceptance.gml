// Authored acceptance harness for an isolated copy. Never installed.
var namespace_path = string_lower(string_replace_all(game_save_id, "\\", "/"));
show_debug_message("Probe save namespace: " + namespace_path);
if (string_pos("/wf_ap_typeword_probe_20260915/", namespace_path) == 0)
{
    game_end();
    exit;
}
tests = [];
snapshots = {};
external_count = 0;
function wf_probe_external() { external_count++; }
function record_test(name, passed, evidence_kind) {
    array_push(tests, {name:name, passed:passed, evidence_kind:evidence_kind});
}
function snapshot(name, value) { variable_struct_set(snapshots, name, json_parse(json_stringify(value))); }
function emit_result(value) { show_debug_message("WF_TYPEWORD_RESULT:NATIVE_NONCE:" + json_stringify(value)); }
try {
    global.mods = {folder:""};
    global.feature_flags = {rotated_outputs:false};
    recipes = loadB64JsonFileAsStruct("recipes.data", true);
    levels = ["II"];
    word_list = [];
    histograms = {};
    latest_score = {};
    prev_score = {};
    urls = {sgg:"disabled"};
    var identity = instance_create_depth(0,0,0,oIdentity);
    full_recipe_list=[];
    refreshRecipeList();
    var input = instance_create_depth(0,0,0,oInput);
    var slot = variable_struct_get(identity.save_data.slots,"0");
    record_test("fresh journal empty", !isLevelBeaten("II") && variable_struct_names_count(slot.words)==0, "native_function");
    snapshot("fresh", slot);
    setLevel("II",-1,3,false);
    record_test("entry is not completion", !isLevelBeaten("II"), "native_function");
    snapshot("opened",slot);
    beatLevel(2,8,0);
    record_test("word recorded", isLevelBeaten("II"), "native_function");
    record_test("no campaign slot", !variable_struct_exists(slot.beaten_levels,"-1"), "native_function");
    snapshot("first_literal_win",slot);
    beatLevel(1,6,0);
    record_test("improved scores", slot.words.II.buildings==1 && slot.words.II.cycles==6 && slot.words.II.extra_letters==0, "native_function");
    record_test("repeat single identity", variable_struct_names_count(slot.words)==1, "native_function");
    snapshot("improved_literal_win",slot);
    var persisted = json_parse(json_stringify(identity.save_data));
    record_test("native JSON score serialization roundtrip", json_stringify(persisted)==json_stringify(identity.save_data), "native_function");
    setLevel("II",0,0,false);
    beatLevel(3,9,1);
    record_test("campaign same target shares word", variable_struct_names_count(slot.words)==1 && variable_struct_exists(slot.beaten_levels,"0") && slot.words.II.cycles==6, "native_function");
    snapshot("campaign_win",slot);
    setLevel("II",0,1,false);
    beatLevel(4,10,2);
    record_test("hard score identity distinct", variable_struct_exists(slot.words,"II_hard") && slot.words.II_hard.buildings==4 && slot.words.II.buildings==1, "native_function");
    snapshot("hard_win",slot);
    setLevel("III",-1,3,false);
    beatLevel(3,12,0);
    record_test("another target distinct", isLevelBeaten("III") && variable_struct_names_count(slot.words)==3, "native_function");
    snapshot("another_target",slot);
    var box = instance_create_depth(0,0,0,oInputBox);
    var cases = [" ii ","abcdefghijkl","A1 B!", "abcdefghijklmnopq"];
    var expected = ["II","ABCDEFGHIJKL","A1B","ABCDEFGHIJKLMNOP"];
    snapshots.input_cases=[];
    for (var c=0;c<array_length(cases);c++) {
        input.full_keyboard_string=cases[c]; input.keyboard_string_index=0;
        with(box) { event_perform(ev_step,ev_step_normal); event_perform(ev_step,ev_step_normal); }
        record_test("native input case " + string(c),box.text==expected[c],"native_function");
        array_push(snapshots.input_cases,{input:cases[c],accepted:box.text});
    }
    // Fresh identity slot: completion below can only come from production.
    variable_struct_set(identity.save_data.slots,"1",{});
    identity.current_save_slot=1;
    slot=variable_struct_get(identity.save_data.slots,"1");
    setLevel("II",-1,3,false);
    record_test("production starts unfinished",!isLevelBeaten("II"),"native_production");
    var control=instance_create_depth(0,0,0,oControl);
    var goal=instance_create_depth(0,0,0,oFinalWordMain);
    var toggle=instance_create_depth(0,0,0,oMenuToggle); toggle.state=3;
    if (layer_get_id("GUIElements")==-1) layer_create(0,"GUIElements");
    for (var n=0;n<2;n++) {
        var source=instance_create_depth(0,0,0,oIFactory);
        source.building=new Building(oIFactory,"");
        var sink=new Building(oFinalWord,"I_"+string(n));
        var pipe=new LetterPipe(2,source.building,sink);
        array_push(control.buildings,sink,source.building);
    }
    var premature_completion=false;
    for (var tick=0;tick<100 && !control.win_already_triggered;tick++) {
        control.doTick();
        control.try_win_condition();
        if (goal.num_words_completed<10 && isLevelBeaten("II")) premature_completion=true;
    }
    record_test("native goal requires ten words",!premature_completion,"native_production");
    record_test("native goal ten words",goal.num_words_completed==10,"native_production");
    record_test("native goal win journal",control.win_already_triggered && isLevelBeaten("II"),"native_production");
    record_test("native goal no campaign credit",variable_struct_names_count(slot.beaten_levels)==0,"native_production");
    var completed_journal=json_stringify(slot);
    record_test("native win caller repeats idempotently",!control.try_win_condition() && json_stringify(slot)==completed_journal,"native_production");
    snapshot("production",{slot:slot,ticks:control.cycle_count,words:goal.num_words_completed,win_stats:control.win_stats});
    // Native entry queues a room transition; run it last, after the bounded graph.
    box.text="ABCDEFGHIJKL";
    EnterInputBoxGame();
    record_test("native entry accepts twelve letters without completion",current_level=="ABCDEFGHIJKL" && current_level_index==-1 && current_level_mode==3 && !isLevelBeaten("ABCDEFGHIJKL"),"native_function");
    snapshots.external_call_count=external_count;
    emit_result({schema:1,save_namespace:game_save_id,tests:tests,snapshots:snapshots,external_calls_stubbed:["all normal object events","__GoogSystem initialization","extension init/cleanup callbacks","identity initialization and sync/cloud achievements","LevelFuncs analyticsEvent/doHTTPRequest/AWSLog","tryStampUnlockAnim/google_analytics_screenview","I module visual spawn"],native_source_sha256:NATIVE_SOURCE_HASHES});
} catch (failure) {
    show_debug_message(json_stringify(failure));
    emit_result({schema:1,save_namespace:game_save_id,tests:tests,snapshots:snapshots,failure:failure,external_calls_stubbed:true,native_source_sha256:NATIVE_SOURCE_HASHES});
}
game_end();
