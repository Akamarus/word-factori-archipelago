// Authored scratch-only acceptance, executed by the isolated Mail runner.
function wf_access_active() { return true; }
function wf_access_context() {
    if(variable_global_exists("wf_live_context")) return global.wf_live_context;
    return json_parse("{\"room\":\"test-room\",\"checks_contract\":\"test-contract\"}");
}
function wf_bridge_snapshot() {
    var value={version:1,session:string_repeat("a",32),renderer:global.wf_mail_bridge.renderer,
        revision:1,contract:"test-contract",connection:"connected",
        items:[],chat:[],words:[{name:"Order 1",word:"CAT",status:"Not completed"}],
        notifications:[],unread:0,acks:[],history:{items:undefined,chat:undefined}};
    variable_struct_set(value,"room","test-room");
    return value;
}
function wf_bridge_tests() {
    wf_mail_bridge_init();
    var b=global.wf_mail_bridge;
    var value=wf_bridge_snapshot();
    wf_expect("bridge valid bounded snapshot",wf_mail_snapshot_valid(value));
    wf_expect("bridge JSON snapshot round trip",wf_mail_snapshot_valid(json_parse(json_stringify(value))));
    var null_probe=json_parse("{\"empty\":null}");
    wf_expect("bridge wire null uses native null pointer",is_ptr(null_probe.empty) && null_probe.empty==pointer_null);
    var wire_item=json_parse("{\"key\":\"k\",\"direction\":\"received\",\"item\":\"Bender\",\"player\":\"Tester\",\"location\":\"C\",\"historical\":false,\"unread\":true}");
    wf_expect("bridge decoded JSON booleans accepted",wf_mail_item_valid(wire_item));
    wire_item.unread=2;
    wf_expect("bridge arbitrary truthy flags refused",!wf_mail_item_valid(wire_item));
    value.words[0].status="invented";
    wf_expect("bridge invalid word status refused",!wf_mail_snapshot_valid(value));
    value=wf_bridge_snapshot(); value.secret="not allowed";
    wf_expect("bridge unknown fields refused",!wf_mail_snapshot_valid(value));
    value=wf_bridge_snapshot(); value.items=array_create(51,{});
    wf_expect("bridge excess rows refused",!wf_mail_snapshot_valid(value));
    value=wf_bridge_snapshot(); value.unread=true;
    wf_expect("bridge boolean counters refused",!wf_mail_snapshot_valid(value));
    directory_create("mods"); directory_create("mods/word factori archipelago");
    directory_create("mods/word factori archipelago/archipelago_mail");
    b.enabled=true;
    var hello={version:1,renderer:b.renderer,heartbeat:1};
    wf_expect("bridge native first replacement succeeds",wf_mail_write("hello.json",hello,4096));
    hello.heartbeat=2;
    wf_expect("bridge native existing replacement succeeds",wf_mail_write("hello.json",hello,4096));
    var loaded=wf_mail_read("hello.json",4096);
    wf_expect("bridge native bounded read round trip",is_struct(loaded) && loaded.heartbeat==2);
    wf_expect("bridge oversize file refused before parse",is_undefined(wf_mail_read("hello.json",8)));
    value=wf_bridge_snapshot();
    var manifest={version:1,session:value.session,renderer:b.renderer,revision:1,heartbeat:1};
    var now=current_time;
    wf_expect("bridge accepts matching manifest snapshot",wf_mail_bridge_accept(manifest,value,now,wf_access_context()));
    wf_expect("bridge persisted heartbeat cannot authorize actions",!wf_mail_bridge_ready());
    manifest.heartbeat=2;
    wf_mail_bridge_accept(manifest,undefined,now,wf_access_context());
    wf_expect("bridge observed advance authorizes actions",wf_mail_bridge_ready());
    wf_expect("bridge unsupported action refused",!wf_mail_submit("grant-item",{}));
    wf_expect("bridge submitted chat queued once",wf_mail_submit("submit-text",{text:"hello"}));
    wf_expect("bridge full queue blocks another send",!wf_mail_submit("submit-text",{text:"again"}) && b.sequence==1);
    value=wf_bridge_snapshot(); value.revision=2;
    value.acks=[{sequence:1,status:"forwarded",message:"Handled"}]; manifest.revision=2;
    wf_mail_bridge_accept(manifest,value,now,wf_access_context());
    wf_expect("bridge matching acknowledgment frees queue",is_undefined(b.pending));
    manifest.revision=1;
    wf_expect("bridge backward revision disables sending",!wf_mail_bridge_accept(manifest,value,now,wf_access_context()) && !wf_mail_bridge_ready());
    manifest.revision=2; wf_mail_bridge_accept(manifest,undefined,now,wf_access_context());
    b.advanced=current_time-5000;
    wf_expect("bridge five second stale heartbeat refused",!wf_mail_bridge_ready());
    b.advanced=current_time; b.pending={sequence:2};
    manifest.session=string_repeat("c",32); manifest.revision=1;
    value=wf_bridge_snapshot(); value.session=manifest.session;
    wf_mail_bridge_accept(manifest,value,now,wf_access_context());
    wf_expect("bridge restart clears pending without resend",is_undefined(b.pending) && b.sequence==0 && string_pos("uncertain",b.message)>0);
    manifest.revision=2; value.revision=2; variable_struct_set(value,"room","wrong-room");
    wf_expect("bridge wrong room clears cached history",!wf_mail_bridge_accept(manifest,value,now,wf_access_context()) && is_undefined(b.snapshot));
    wf_mail_bridge_shutdown();
    wf_expect("bridge shutdown disables transport",!b.enabled && !wf_mail_bridge_ready());
}
