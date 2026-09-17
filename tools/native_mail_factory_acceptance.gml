// Authored scratch host; actual Building, LetterPipe, doTick and win methods.
// Runs one native production tick per engine Step, comparing identical graphs.
function wf_factory_external() { wf_factory_external_count++; }
function wf_factory_begin(opened) {
    wf_mail_reset();
    global.wf_mail.open=opened;
    global.wf_mail.consume=opened;
    wf_factory_open=opened;
    wf_factory_age=0;
    wf_factory_kept_open=true;
    wf_factory_premature=false;
    wf_factory_external_count=0;
    global.mods={folder:""};
    global.feature_flags={rotated_outputs:false};
    recipes=loadB64JsonFileAsStruct("recipes.data",true);
    levels=["II"]; word_list=[]; histograms={}; latest_score={}; prev_score={};
    urls={sgg:"disabled"};
    var identity=instance_create_depth(0,0,0,oIdentity);
    full_recipe_list=[];
    refreshRecipeList();
    setLevel("II",-1,3,false);
    var control=instance_create_depth(0,0,0,oControl);
    instance_create_depth(0,0,0,oFinalWordMain);
    var toggle=instance_create_depth(0,0,0,oMenuToggle); toggle.state=3;
    if(layer_get_id("GUIElements")==-1) layer_create(0,"GUIElements");
    for(var n=0;n<2;n++) {
        var source=instance_create_depth(0,0,0,oIFactory);
        source.building=new Building(oIFactory,"");
        var sink=new Building(oFinalWord,"I_"+string(n));
        var pipe=new LetterPipe(2,source.building,sink);
        array_push(control.buildings,sink,source.building);
    }
}
function wf_factory_step() {
    wf_factory_age++;
    var control=oControl;
    control.doTick();
    control.try_win_condition();
    if(oFinalWordMain.num_words_completed<10 && isLevelBeaten("II")) wf_factory_premature=true;
    if(wf_factory_open && !global.wf_mail.open) wf_factory_kept_open=false;
    if(!control.win_already_triggered && wf_factory_age<100) return;
    var slot=variable_struct_get(oIdentity.save_data.slots,"0");
    var outcome={ticks:control.cycle_count,frames:wf_factory_age,words:oFinalWordMain.num_words_completed,
        journal:json_stringify(slot),won:control.win_already_triggered && isLevelBeaten("II") && !wf_factory_premature};
    var repeat_unchanged=!control.try_win_condition() && outcome.journal==json_stringify(slot);
    outcome.idempotent=repeat_unchanged;
    outcome.kept_open=wf_factory_kept_open;
    if(!wf_factory_open) {
        wf_factory_closed=outcome;
        wf_expect("closed Mail factory completes ten words",outcome.won && outcome.words==10);
    } else {
        wf_factory_open_result=outcome;
        wf_expect("open Mail factory completes ten words",outcome.won && outcome.words==10);
        wf_expect("Mail stays open throughout native production",wf_factory_kept_open);
        wf_expect("native production completion is idempotent with Mail open",repeat_unchanged);
    }
    // Each mode uses a fresh process; no test-authored instance teardown/reset.
    wf_factory_done=true;
}
