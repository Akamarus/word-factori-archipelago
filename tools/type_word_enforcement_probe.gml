// Isolated native gate providers; the production enforcement core is unchanged.
function wf_access_context() { return oPersistent.wf_probe_gate.context; }
function wf_access_payload() { return oPersistent.wf_probe_gate.payload; }
function wf_access_levels() { return oPersistent.levels; }
