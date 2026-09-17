// Authored boundaries for the full locally extracted native editor Step body.
// No original startup/save events execute. Objects exist only in this probe.
mode=7; edit_theta=0; game_max_tick_factor=30; tick_factor=30;
drag_with_middle=false; continue_was_pressed=false;
selected_modules=[]; dangling_nodes=[]; hold_circle_t=0;
mb_right_held=false; prev_mouse_x=0; prev_mouse_y=0;
col_list=ds_list_create(); deleted=0; wf_ticks=0; wf_snapshots=0;
steps_till_next_tick=30; sample_index=0;
wf_target={x:100,y:200};
wf_rotation_widget={image_index:0};
function get_instance_under_mouse() { return [-4,undefined]; }
function move_pos() { return wf_target; }
function dangling_placement_is_valid(inst) { return true; }
function update_dangling_positions() { }
function selectionHovered() { return false; }
function updateLineHover(inst,obj) { }
function try_win_condition() { return false; }
function doTick() { wf_ticks++; }
