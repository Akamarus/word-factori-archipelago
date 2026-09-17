// A real Python transport/adapter runs concurrently; no AP network is involved.
function wf_mail_live_step() {
    if(wf_live_done) return;
    if(wf_live_phase==0) {
        global.wf_live_context=json_parse("{\"room\":\"LIVE_ROOM_TOKEN\",\"checks_contract\":\"test-contract\"}");
        wf_mail_bridge_clear("Waiting for real client transport.");
        global.wf_mail_bridge.next_poll=0;
        wf_live_phase=1;
    }
    wf_mail_bridge_step(current_time);
    var b=global.wf_mail_bridge;
    if(wf_frames mod 120==0) show_debug_message("WF_MAIL_LIVE_STATE:"+json_stringify({
        enabled:b.enabled,valid:b.valid,hello:b.hello,reads:b.reads,next_poll:b.next_poll,
        now_ms:current_time,next_hello:b.next_hello,active:wf_access_active(),
        marker:wf_mail_read("enabled.json",4096),message:b.message,
        snapshot:wf_mail_read("snapshot.json",262144),
        snapshot_valid:wf_mail_snapshot_valid(wf_mail_read("snapshot.json",262144))}));
    if(wf_live_phase==1 && wf_mail_bridge_ready() && is_struct(b.snapshot)
        && array_length(b.snapshot.words)==1 && b.snapshot.words[0].word=="TEST") {
        wf_expect("live bridge displays Python authoritative target",true);
        wf_expect("live bridge submits native chat",wf_mail_submit("submit-text",{text:"native-roundtrip"}));
        wf_live_phase=2;
    }
    if(wf_live_phase==2 && is_undefined(b.pending) && string_pos("forwarded",b.message)>0) {
        wf_expect("live bridge receives Python acknowledgment",true);
        wf_live_done=true;
    }
    if(wf_frames>900 && !wf_live_done) {
        wf_expect("live bridge timed out: "+b.message,false);
        wf_live_done=true;
    }
}
