// Authored isolated regression harness; no player save or live network.
var namespace_path=string_lower(string_replace_all(game_save_id,"\\","/"));
if(string_pos("/wf_ap_typeword_probe_20260915/",namespace_path)==0) { game_end(); exit; }
tests=[]; snapshots={}; external_count=0;
function wf_probe_external() { external_count++; }
function record_test(name,passed) { array_push(tests,{name:name,passed:passed,evidence_kind:"native_recipe_loading"}); }
function emit_result(value) { show_debug_message("WF_TYPEWORD_RESULT:NATIVE_NONCE:"+json_stringify(value)); }
try {
    global.mods={folder:""}; global.feature_flags={rotated_outputs:false};
    var identity=instance_create_depth(0,0,0,oIdentity);
    levels=["II"]; full_recipe_list=[]; word_list=[];
    var bundled=loadB64JsonFileAsStruct("recipes.data",true);
    var online=variable_clone(bundled);
    // Same canonical duplicate shape as the reported online table.
    variable_struct_set(online.oMerger2,"I N","__M");
    variable_struct_set(online.oMerger2,"N I","__M");
    variable_struct_set(online.oMerger2,"I I","X");
    recipes=variable_clone(online);
    for(var pass=0;pass<3;pass++) {
        refreshRecipeList();
        var all_normal=true;
        var groups=["aliases","oBend","oMerger2","oMerger3","oMerger4"];
        for(var g=0;g<array_length(groups);g++) {
            var group=variable_struct_get(recipes,groups[g]);
            var names=variable_struct_get_names(group);
            for(var k=0;k<array_length(names);k++) {
                if(!is_struct(variable_struct_get(group,names[k]))) all_normal=false;
            }
        }
        record_test("duplicate refresh "+string(pass),all_normal);
    }
    request_ids={}; variable_struct_set(request_ids,"42","get_recipes");
    var response={id:42,url:"isolated",status:0,http_status:"200",result:json_stringify(online)};
    base_recipes=variable_clone(bundled);
    wf_probe_receive(response);
    record_test("vanilla still accepts recipe updates",variable_struct_exists(base_recipes.oMerger2,"N I"));
    directory_create("mods"); directory_create("mods/word factori archipelago");
    writeJsonFileFromStruct("mods/word factori archipelago/recipes.json",{include_vanilla:true},true);
    global.mods.folder="mods/word factori archipelago";
    applyModRecipes(); refreshRecipeList();
    record_test("entering AP restores bundled recipes",variable_struct_get(recipes.oMerger2,"I I").char=="V");
    var before=json_stringify(base_recipes);
    var active_before=json_stringify(recipes);
    wf_probe_receive(response);
    record_test("AP rejects online base replacement",json_stringify(base_recipes)==before);
    record_test("AP rejects active recipe replacement",json_stringify(recipes)==active_before);
    global.mods.folder="";
    applyModRecipes(); refreshRecipeList();
    record_test("leaving AP preserves vanilla base table",variable_struct_get(recipes.oMerger2,"I I").char=="X");
    emit_result({schema:1,tests:tests,snapshots:snapshots,save_namespace:game_save_id,native_source_sha256:NATIVE_SOURCE_HASHES});
} catch(failure) { emit_result({schema:1,tests:tests,snapshots:snapshots,failure:failure}); }
game_end();
