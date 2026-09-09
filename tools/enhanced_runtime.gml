// Integration-authored development probe. Not bundled with player builds.
// An enhanced campaign must carry a room/layout marker in its first level.
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
        var payload = loadJsonFileAsStruct(path, true);
        if (!is_struct(payload)) return undefined;
        var fields = ["schema", "mode", "room", "layout", "revision", "levels"];
        for (var i = 0; i < array_length(fields); i++)
            if (!variable_struct_exists(payload, fields[i])) return undefined;
        if (payload.schema != 1 || payload.mode != "enhanced") return undefined;
        if (payload.room != marker.room || payload.layout != marker.layout) return undefined;
        if (!is_real(payload.revision) || payload.revision < 0 || payload.revision != floor(payload.revision)) return undefined;
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
        marker.revision = payload.revision;
        return counts;
    }
    catch (error)
    {
        return undefined;
    }
}
