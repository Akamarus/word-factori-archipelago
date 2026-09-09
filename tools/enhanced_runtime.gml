// Integration-authored enhanced hook. Compiled against a user's verified copy.
// An enhanced campaign must carry a room/layout marker in its first level.
function wf_ap_read_json(path)
{
    // The game's general loader opens a fatal dialog for missing files.
    // Runtime sidecars can disappear during replacement; fail quietly instead.
    var handle = -1;
    try
    {
        handle = file_text_open_read(path);
        if (handle == -1) return undefined;
        var content = "";
        while (!file_text_eof(handle)) content += file_text_readln(handle);
        file_text_close(handle);
        handle = -1;
        return json_parse(content);
    }
    catch (error)
    {
        if (handle != -1) file_text_close(handle);
        return undefined;
    }
}

function wf_ap_context()
{
    if (!variable_global_exists("mods") || !is_struct(global.mods)) return undefined;
    if (!variable_struct_exists(global.mods, "folder")) return undefined;
    if (!is_string(global.mods.folder)) return undefined;
    var folder = string_lower(string_replace_all(global.mods.folder, "\\", "/"));
    var expected = "mods/word factori archipelago";
    var absolute = string_lower(string_replace_all(environment_get_variable("LOCALAPPDATA"), "\\", "/") + "/factori/" + expected);
    if (folder != expected && folder != "word factori archipelago" && folder != absolute) return undefined;
    if (!instance_exists(oPersistent)) return undefined;
    if (!variable_instance_exists(oPersistent, "levels")) return undefined;
    if (!is_array(oPersistent.levels) || array_length(oPersistent.levels) < 6) return undefined;
    var first = oPersistent.levels[0];
    if (!is_struct(first) || !variable_struct_exists(first, "wf_ap")) return undefined;
    var marker = first.wf_ap;
    if (!is_struct(marker)) return undefined;
    var fields = ["schema", "mode", "room", "layout"];
    for (var i = 0; i < array_length(fields); i++)
        if (!variable_struct_exists(marker, fields[i])) return undefined;
    if (marker.schema != 1 || marker.mode != "enhanced") return undefined;
    if (!is_string(marker.room) || string_length(marker.room) != 64) return undefined;
    if (!is_string(marker.layout) || string_length(marker.layout) != 64) return undefined;
    var needs_announcement = !variable_struct_exists(marker, "announced") || !marker.announced;
    var retry_due = !variable_struct_exists(marker, "announce_retry_at") || current_time >= marker.announce_retry_at;
    if (needs_announcement && retry_due)
    {
        // Menu availability can be checked every frame. Bound failed-write
        // retries without requiring the player to reload the campaign.
        marker.announce_retry_at = current_time + 5000;
        try
        {
            // "room" is a GameMaker built-in: assign JSON keys explicitly,
            // rather than compiling it as a struct-literal member setter.
            var status = json_parse("{}");
            variable_struct_set(status, "schema", 1);
            variable_struct_set(status, "mode", "enhanced");
            variable_struct_set(status, "room", marker.room);
            variable_struct_set(status, "layout", marker.layout);
            writeJsonFileFromStruct("mods/word factori archipelago/archipelago_native_status.json", status, true);
            marker.announced = true;
        }
        catch (error)
        {
            marker.announced = false;
            show_debug_message("AP native status write failed: " + string(error));
        }
    }
    return marker;
}

function wf_ap_enabled()
{
    return is_struct(wf_ap_context());
}

function wf_ap_counts(index)
{
    var marker = wf_ap_context();
    if (!is_struct(marker)) return undefined;
    if (index < 0 || index != floor(index) || index >= array_length(oPersistent.levels)) return undefined;
    var path = "mods/word factori archipelago/archipelago_runtime.json";
    if (!file_exists(path)) return undefined;
    try
    {
        var payload = wf_ap_read_json(path);
        if (!is_struct(payload)) return undefined;
        var fields = ["schema", "mode", "room", "layout", "revision", "levels"];
        for (var i = 0; i < array_length(fields); i++)
            if (!variable_struct_exists(payload, fields[i])) return undefined;
        if (payload.schema != 1 || payload.mode != "enhanced") return undefined;
        if (payload.room != marker.room || payload.layout != marker.layout) return undefined;
        // Client JSON epoch counters parse as int64, unlike GameMaker's own
        // writer, which emits floating-point literals. Accept both numeric
        // representations while retaining the nonnegative-integer guard.
        if ((!is_real(payload.revision) && !is_int64(payload.revision)) || payload.revision < 0 || payload.revision != floor(payload.revision)) return undefined;
        if (variable_struct_exists(marker, "revision") && payload.revision < marker.revision) return undefined;
        if (!is_array(payload.levels) || array_length(payload.levels) != array_length(oPersistent.levels)) return undefined;
        var entry = payload.levels[index];
        if (!is_struct(entry)) return undefined;
        if (!variable_struct_exists(entry, "text") || !variable_struct_exists(entry, "module_counts")) return undefined;
        if (entry.text != oPersistent.levels[index].text || !is_struct(entry.module_counts)) return undefined;
        var counts = entry.module_counts;
        var names = variable_struct_get_names(counts);
        var allowed = ["Bend", "Rotate_cw", "Rotate_ccw", "Reflect_hor", "Reflect_vert", "Merger2", "Merger3", "Merger4", "IFactory"];
        for (var i = 0; i < array_length(names); i++)
        {
            var known = false;
            for (var j = 0; j < array_length(allowed); j++)
                if (names[i] == allowed[j]) known = true;
            if (!known) return undefined;
            var count = variable_struct_get(counts, names[i]);
            if (!is_real(count) || count < 0 || count > 10000 || count != floor(count)) return undefined;
        }
        // Immutable per-level caps come from the loaded campaign, not the
        // mutable item snapshot. Omission must not bypass a challenge limit.
        var native_entry = oPersistent.levels[index];
        if (!variable_struct_exists(native_entry, "wf_ap_caps") || !is_struct(native_entry.wf_ap_caps)) return undefined;
        var caps = native_entry.wf_ap_caps;
        var cap_names = variable_struct_get_names(caps);
        for (var i = 0; i < array_length(cap_names); i++)
        {
            var name = cap_names[i];
            if (!variable_struct_exists(counts, name)) return undefined;
            var cap = variable_struct_get(caps, name);
            if (!is_real(cap) || cap < 0 || cap > 10000 || cap != floor(cap)) return undefined;
            if (variable_struct_get(counts, name) > cap) return undefined;
        }
        marker.revision = payload.revision;
        return counts;
    }
    catch (error)
    {
        return undefined;
    }
}
