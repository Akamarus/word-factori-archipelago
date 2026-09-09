// Authored isolated test harness, never installed into the user's game.
// Replaces only the test copy's initial oPersistent Create event.
var save_path = string_lower(string_replace_all(game_save_id, "\\", "/"));
if (string_pos("wf_ap_native_acceptance_20260909", save_path) == 0)
{
    show_debug_message("REFUSED: test save directory was not isolated");
    game_end();
    exit;
}
global.mods = {folder: "mods/word factori archipelago"};
directory_create("mods");
directory_create("mods/word factori archipelago");
levels = loadJsonFileAsStruct("acceptance_levels.json", true);
var payload = loadJsonFileAsStruct("acceptance_runtime.json", true);
results = [];
function record_test(name, passed)
{
    array_push(results, {name: name, passed: passed});
}
function save_payload(value)
{
    writeJsonFileFromStruct("mods/word factori archipelago/archipelago_runtime.json", value, true);
}
record_test("enhanced marker enabled", wf_ap_enabled());
var ack_path = "mods/word factori archipelago/archipelago_native_status.json";
var ack = file_exists(ack_path) ? loadJsonFileAsStruct(ack_path, true) : undefined;
record_test("native acknowledgement matches loaded room", is_struct(ack) && ack.room == levels[0].wf_ap.room && ack.layout == levels[0].wf_ap.layout);
file_delete(ack_path);
levels[0].wf_ap.announced = false;
levels[0].wf_ap.announce_retry_at = current_time + 5000;
wf_ap_enabled();
record_test("failed acknowledgement respects retry cooldown", !file_exists(ack_path));
levels[0].wf_ap.announce_retry_at = current_time - 1;
wf_ap_enabled();
record_test("failed acknowledgement retries without reload", file_exists(ack_path) && levels[0].wf_ap.announced);
record_test("four completions open page two", getPageUnlockThresh(1) == 4);
// Native button method, with only unrelated UI dependencies replaced in the
// isolated runner. No native progression condition is replaced by this test.
var ui = instance_create_depth(0, 0, 0, oUIControl);
var button = instance_create_depth(0, 0, 0, oLevelButton);
button.level_mode = 0;
for (var i = 0; i < 6; i++)
{
    button.level_index = i;
    record_test("first page button " + string(i) + " selectable", button.is_enabled());
}
button.visible = false;
record_test("hidden button guard preserved", !button.is_enabled());
button.visible = true;
ui.state = 19;
record_test("blocked UI state guard preserved", !button.is_enabled());
ui.state = 0;
global.mods.folder = "";
record_test("vanilla does not enable enhanced hooks", !wf_ap_enabled());
record_test("vanilla threshold remains six", getPageUnlockThresh(1) == 6);
global.mods.folder = "mods/word factori archipelago";
save_payload(payload);
var updated = get_level_module_counts(0);
record_test("factory entry reads newly unlocked Merger2", !variable_struct_exists(updated, "Merger2"));
record_test("loaded baseline was not rewritten", levels[0].module_counts.Merger2 == 0);
record_test("duplicate revision remains readable", is_struct(wf_ap_counts(0)));
payload.room = string_repeat("c", 64);
save_payload(payload);
record_test("wrong room ignored", is_undefined(wf_ap_counts(0)));
record_test("wrong room falls back to loaded limits", get_level_module_counts(0).Merger2 == 0);
payload.room = levels[0].wf_ap.room;
payload.layout = string_repeat("d", 64);
save_payload(payload);
record_test("wrong layout ignored", is_undefined(wf_ap_counts(0)));
payload.layout = levels[0].wf_ap.layout;
payload.revision -= 1;
save_payload(payload);
record_test("older revision ignored", is_undefined(wf_ap_counts(0)));
payload.revision += 2;
payload.levels[0].text = "WRONG";
save_payload(payload);
record_test("wrong target ignored", is_undefined(wf_ap_counts(0)));
payload.levels[0].text = levels[0].text;
payload.levels[0].module_counts = {Merger2: -1};
save_payload(payload);
record_test("negative machine count ignored", is_undefined(wf_ap_counts(0)));
payload.levels[0].module_counts = {};
levels[0].wf_ap_caps = {Merger2: 2};
save_payload(payload);
record_test("omitted challenge cap rejected", is_undefined(wf_ap_counts(0)));
payload.levels[0].module_counts = {Merger2: 3};
save_payload(payload);
record_test("increased challenge cap rejected", is_undefined(wf_ap_counts(0)));
payload.levels[0].module_counts = {Merger2: 2};
save_payload(payload);
record_test("valid challenge cap accepted", wf_ap_counts(0).Merger2 == 2);
payload.levels[0].module_counts = {Merger2: 0};
save_payload(payload);
record_test("locked machine overrides challenge cap", wf_ap_counts(0).Merger2 == 0);
record_test("out of range level ignored", is_undefined(wf_ap_counts(999)));
record_test("type a word ignored", is_undefined(wf_ap_counts(-1)));
// Preserve client JSON integer tokens: the game writer converts them to
// floating-point literals and would hide the real int64 parsing regression.
function save_raw_revision(value, revision_token)
{
    value.revision = "RAW_REVISION_TOKEN";
    var text = string_replace_all(json_stringify(value), "\"RAW_REVISION_TOKEN\"", revision_token);
    var file = file_text_open_write("mods/word factori archipelago/archipelago_runtime.json");
    file_text_write_string(file, text);
    file_text_close(file);
}
save_raw_revision(payload, "1788991728607");
record_test("client epoch revision parses as int64", is_int64(wf_ap_read_json("mods/word factori archipelago/archipelago_runtime.json").revision));
record_test("client int64 revision accepted", is_struct(wf_ap_counts(0)));
save_raw_revision(payload, "1788991728606");
record_test("older int64 revision rejected", is_undefined(wf_ap_counts(0)));
save_raw_revision(payload, "1788991728608.5");
record_test("fractional revision rejected", is_undefined(wf_ap_counts(0)));
save_raw_revision(payload, "-1");
record_test("negative revision rejected", is_undefined(wf_ap_counts(0)));
file_delete("mods/word factori archipelago/archipelago_runtime.json");
record_test("missing runtime ignored without dialog", is_undefined(wf_ap_counts(0)));
record_test("missing file read fails quietly", is_undefined(wf_ap_read_json("mods/word factori archipelago/missing.json")));
var invalid_file = file_text_open_write("mods/word factori archipelago/archipelago_runtime.json");
file_text_write_string(invalid_file, "{incomplete");
file_text_close(invalid_file);
record_test("malformed runtime ignored without dialog", is_undefined(wf_ap_counts(0)));
writeJsonFileFromStruct("acceptance_results.json", {save_directory: game_save_id, tests: results}, true);
game_end();
