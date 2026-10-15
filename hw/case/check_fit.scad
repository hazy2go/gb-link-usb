// Collision check: intersection of the case with the board + top parts. Must render empty.
use <case.scad>
include <parts.scad>
include <case.scad>
which = "lid";
module board_and_parts() {
    translate([BOARD_OFS[0], BOARD_OFS[1], Z_BB + 0.01]) linear_extrude(B_T - 0.02) offset(-0.05) rrect(B_W, B_L, B_R);   // board (0.05 shrink: touching is fine)
    translate([BOARD_OFS[0], BOARD_OFS[1], Z_BT + 0.01]) parts_top();
}
intersection() { if (which == "lid") lid(); else tray(); board_and_parts(); }
