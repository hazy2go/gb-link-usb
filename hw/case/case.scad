// gb-link-usb rev A case: a tray and a lid, printed separately (OpenSCAD).
// The board is clamped between a ledge in the tray (under its long edges) and a lip on the lid (on its top
// edges). The link cable's jacket is pinched between the two halves at the far end. BOOTSEL and RUN are pressed
// through flex tabs in the lid; the LED shows through a hole.
//
// Board data from hw/rev-a (pcb_build.py outline, footprint positions) and hw/case/heights.json
// (tallest part: USB-C 3.25 mm). Build: openscad -D 'part="tray"' -o tray.stl case.scad (or "lid", "both").
// Units mm. Case coordinates: x across the board, y along it (USB-C end at the top, y = max), z up.

part = "both";          // "tray", "lid", "both" (print layout) or "assembly" (preview)

// ---- board (hw/tools/pcb_build.py: X0..X1 83.3..117.5, Y0..Y1 67.0..129.2, corner 1.5) ----
B_X0 = 83.3; B_Y0 = 67.0;
B_W = 34.2; B_L = 62.2; B_T = 1.6; B_R = 1.5;
// KiCad (x, y down) -> board-local case coordinates (x, y up, USB-C end at y = B_L)
function bx(x) = x - B_X0;
function by(y) = B_L - (y - B_Y0);

SW1 = [bx(91.2), by(75.2)];      // BOOTSEL (Alps SKRPABE010, 2.5 mm tall, actuator Ø ~1.6)
SW2 = [bx(111.8), by(107.475)];  // RUN
LED = [bx(114.2), by(102.0)];    // D101
USB_X = bx(100.0);               // USB-C centre (J101)
CABLE_X = bx(93.0);              // middle of the five cable pads (x 85..101)

// ---- case parameters ----
CABLE_D  = 4.0;    // link cable jacket diameter (verify on the cable; set before printing)
GAP      = 0.3;    // board edge to wall, long sides and cable end
GAP_USB  = 0.2;    // board edge (receptacle front) to the USB end wall
WALL     = 1.6;
WALL_USB = 1.2;    // thinner at the USB end: the plug's overmold sits close to the receptacle
FLOOR    = 1.2;
ROOF     = 1.2;
UNDER    = 2.5;    // under the board: USB-C legs (0.85 mm) and the cable wires through the relief holes
OVER     = 4.6;    // above the board: tallest part 3.25 mm (height_check.py budget 4.0); also leaves ~0.9 mm of roof over the USB opening
EXT      = 7.0;    // extra length beyond the board's cable end: wires fan out from the jacket to the pads
LIP      = 0.8;    // lid lip thickness
FIT      = 0.15;   // lip-to-wall clearance (press fit; 0.2 for a looser printer)
LIP_UP   = 1.5;    // tray walls rise this far above the board top; the lid lip fills it
LEDGE    = 0.8;    // ledge width under the board's long edges

OUT_W = B_W + 2 * GAP + 2 * WALL;
OUT_L = WALL_USB + GAP_USB + B_L + GAP + EXT + WALL;
OUT_H = FLOOR + UNDER + B_T + OVER + ROOF;
Z_BB = FLOOR + UNDER;            // board bottom
Z_BT = Z_BB + B_T;               // board top
Z_SPLIT = Z_BT + LIP_UP;         // tray / lid split
OUT_R = 2.5;

// board-local -> case coordinates
BOARD_OFS = [WALL + GAP, WALL + EXT + GAP];   // board corner (bx 0, by 0) in case coordinates
function c(p) = [p[0] + BOARD_OFS[0], p[1] + BOARD_OFS[1]];

$fn = 48;

module rrect(w, l, r) { offset(r) offset(-r) square([w, l]); }
module rbox(w, l, h, r) { linear_extrude(h) rrect(w, l, r); }

module shell_outer() { rbox(OUT_W, OUT_L, OUT_H, OUT_R); }
module cavity() {
    translate([WALL, WALL, FLOOR])
        rbox(OUT_W - 2 * WALL, OUT_L - WALL - WALL_USB, OUT_H - FLOOR - ROOF, 1.0);
}

// USB-C opening 12.6 x 6.6 mm: overmold of common plugs ~12 x 6.5 mm (verify with your cable), centred on the receptacle (centre ~1.63 mm above board)
module usb_cut() {
    translate([BOARD_OFS[0] + USB_X, OUT_L + 1, Z_BT + 1.63]) rotate([90, 0, 0])
        linear_extrude(WALL_USB + 2) offset(2) offset(-2) square([12.6, 6.6], center = true);
}

// cable: centred on the split so each half holds half of it; the wall and an inner rib pinch it
CABLE_Z = Z_SPLIT;
module cable_cut(d) {
    translate([BOARD_OFS[0] + CABLE_X, -1, CABLE_Z]) rotate([-90, 0, 0]) cylinder(d = d, h = WALL + 4.5);
}
module cable_rib() {   // inner rib 3 mm inside the end wall, full cavity height
    translate([BOARD_OFS[0] + CABLE_X - 4, WALL + 2.2, FLOOR]) cube([8, 1.6, OUT_H - FLOOR - ROOF]);
}

// flex button in the roof: U-slot around a tab, a nub under the tab reaches down to the switch
NUB_GAP = 0.3;   // tab nub to the switch actuator at rest
module button_slot(p, flip = false) {   // flip: hinge towards -y
    translate([c(p)[0], c(p)[1], OUT_H - ROOF - 1]) mirror([0, flip ? 1 : 0, 0]) linear_extrude(ROOF + 2)
        difference() {
            translate([-3, -3]) square([6, 9.5]);     // tab 5 x 8.5, hinge at the far end
            translate([-2.5, -2.5]) square([5, 9.5]);
        }
}
module button_nub(p) {
    top_of_switch = Z_BT + 2.5;
    translate([c(p)[0], c(p)[1], top_of_switch + NUB_GAP]) cylinder(d = 2.2, h = OUT_H - ROOF - top_of_switch - NUB_GAP + 0.01);
}

module led_hole() { translate([c(LED)[0], c(LED)[1], OUT_H - ROOF - 1]) cylinder(d = 1.8, h = ROOF + 2); }

module label(t, p, s) {
    translate([p[0], p[1], OUT_H - 0.4]) linear_extrude(1) text(t, size = s, halign = "center", valign = "center",
        font = "Liberation Sans:style=Bold");
}

// ---- board clamps ----
// ledge under the long edges (left side stops above the cable pads: wires pass through relief holes there),
// plus short pieces along the USB end, clear of the receptacle's legs
module ledges() {
    h = Z_BB - FLOOR;
    in = GAP + LEDGE;
    // right side, full length
    translate([OUT_W - WALL - in, BOARD_OFS[1], FLOOR]) cube([in, B_L, h]);
    // left side, from the USB end down to by 13 (the cable pads sit at by 10.6, relief holes at by 1.6)
    translate([WALL, BOARD_OFS[1] + 13, FLOOR]) cube([in, B_L - 13, h]);
    // USB end, both sides of the receptacle legs (bx 13.8 / 19.6)
    for (x0 = [0, 23]) translate([BOARD_OFS[0] + x0, OUT_L - WALL_USB - GAP_USB - LEDGE, FLOOR]) cube([11, LEDGE + GAP_USB, h]);
}
// floor posts under the two buttons, so pressing them does not bend the board
module posts() {
    for (p = [SW1, SW2]) translate([c(p)[0], c(p)[1], FLOOR]) cylinder(d = 3, h = Z_BB - FLOOR);
}
// lid lip: rests on the outer 0.65 mm of the board's long edges and fills the tray wall above the board
module lip() {
    in0 = WALL + FIT;
    translate([0, 0, Z_BT]) difference() {
        translate([in0, BOARD_OFS[1], 0]) cube([OUT_W - 2 * in0, B_L, LIP_UP]);
        translate([in0 + LIP, BOARD_OFS[1] - 1, -1]) cube([OUT_W - 2 * in0 - 2 * LIP, B_L + 2, LIP_UP + 2]);
        // left side: stop above the cable pads (as the ledge)
        translate([in0 - 1, BOARD_OFS[1] - 1, -1]) cube([LIP + 2, 14, LIP_UP + 2]);
    }
}

module tray() {
    difference() {
        intersection() { shell_outer(); translate([-1, -1, -1]) cube([OUT_W + 2, OUT_L + 2, Z_SPLIT + 1]); }
        cavity();
        usb_cut();
        cable_cut(CABLE_D - 0.6);              // 0.3 mm squeeze per side
    }
    difference() {
        union() { ledges(); posts(); intersection() { cable_rib(); translate([0, 0, 0]) cube([OUT_W, OUT_L, Z_SPLIT]); } }
        cable_cut(CABLE_D - 0.6);
    }
}

module lid() {
    difference() {
        union() {
            difference() {
                intersection() { shell_outer(); translate([-1, -1, Z_SPLIT]) cube([OUT_W + 2, OUT_L + 2, OUT_H]); }
                cavity();
            }
            lip();
            intersection() { cable_rib(); translate([0, 0, Z_SPLIT]) cube([OUT_W, OUT_L, OUT_H]); }
            for (p = [SW1, SW2]) button_nub(p);
        }
        usb_cut();
        cable_cut(CABLE_D - 0.6);
        button_slot(SW1); button_slot(SW2, flip = true);   // SW2 hinges away from the LED
        led_hole();
        label("gb-link-usb", [OUT_W / 2, OUT_L * 0.25], 3.2);
        label("BOOT", [c(SW1)[0] + 7.5, c(SW1)[1] + 1], 2.2);
        label("RST", [c(SW2)[0] - 7.5, c(SW2)[1] + 1], 2.2);
    }
}

module board_ghost() {
    color("green", 0.6) translate([BOARD_OFS[0], BOARD_OFS[1], Z_BB]) rbox(B_W, B_L, B_T, B_R);
}

if (part == "none") {}
else if (part == "tray") tray();
else if (part == "lid") translate([0, OUT_L, OUT_H]) rotate([180, 0, 0]) lid();   // print roof down
else if (part == "assembly") { tray(); board_ghost(); color("white", 0.5) lid(); }
else { tray(); translate([OUT_W + 6, OUT_L, OUT_H]) rotate([180, 0, 0]) lid(); }
