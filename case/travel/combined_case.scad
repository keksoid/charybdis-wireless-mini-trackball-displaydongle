// Combined flat travel case for Charybdis Mini (both halves + display dongle + 1 m cable)
// Keyboard pockets are taken from f3rn4nd0d's Charybdis Mini Travel Case
// (CC BY-NC-SA 4.0, @CASLArt3D), so this remix uses the same licence.
//
// Version 2: hollow construction. Every surface is a `skin` mm thick shell; the space
// between the skins is empty and opens at the base/lid split face, so nothing is
// trapped inside when printed in resin (SLA) or nylon (MJF). Ribs keep the shell stiff.
include <case_data.scad>

part      = "closed";  // "base", "lid", "test_frame", "closed", "open", "section"
z_split   = 15;        // height of the base/lid split (pocket floor is at z_pocket)
corner_r  = 12;
skin      = 2.5;       // wall thickness everywhere
rib_t     = 1.6;       // rib thickness
rib_step  = 40;        // rib spacing
mag_d     = 6.3;       // 6 x 3 mm magnets + clearance
mag_h     = 3.3;
boss_d    = 11;        // solid post around each magnet
$fn = 40;

module outer_2d(inset = 0) translate([outer[0], outer[1]]) offset(corner_r - inset) offset(-corner_r)
    square([outer[2] - outer[0], outer[3] - outer[1]]);
module shell() translate([0, 0, z_floor]) linear_extrude(z_top - z_floor) outer_2d();

// all cavities; g > 0 grows them by g (used to keep a skin around them)
module cavities(g = 0) {
    intersection() {
        translate([0, 0, z_pocket - g]) linear_extrude(z_top) offset(g) outline_left();
        translate([0, 0, clear + g]) ceiling_left();
    }
    intersection() {
        translate([0, 0, z_pocket - g]) linear_extrude(z_top) offset(g) outline_right();
        translate([0, 0, clear + g]) ceiling_right();
    }
    // dongle stands on its rear cap (USB-C down)
    translate([dongle_pocket[0] - g, dongle_pocket[1] - g, z_pocket - g])
        cube([dongle_pocket[2] + 2 * g, dongle_pocket[3] + 2 * g, dongle_h + 2 * g]);
    // cable compartment across the far end
    translate([cable_pocket[0] - g, cable_pocket[1] - g, z_pocket - g])
        cube([cable_pocket[2] + 2 * g, cable_pocket[3] + 2 * g, z_top - skin - z_pocket + 2 * g]);
}

// the hollow space between the skins
module hollow() difference() {
    translate([0, 0, z_floor + skin]) linear_extrude(z_top - z_floor - 2 * skin) outer_2d(skin);
    cavities(skin);
    for (m = magnets) translate([m[0], m[1], z_floor]) cylinder(d = boss_d, h = z_top - z_floor);
    // ribs
    for (x = [outer[0] + rib_step : rib_step : outer[2]])
        translate([x - rib_t / 2, outer[1], z_floor]) cube([rib_t, outer[3] - outer[1], z_top - z_floor]);
    for (y = [outer[1] + rib_step : rib_step : outer[3]])
        translate([outer[0], y - rib_t / 2, z_floor]) cube([outer[2] - outer[0], rib_t, z_top - z_floor]);
}

module magnet_holes(dir) for (m = magnets)
    translate([m[0], m[1], dir > 0 ? z_split - 0.01 : z_split - mag_h]) cylinder(d = mag_d, h = mag_h + 0.01);
module finger_notches() for (x = [outer[0], outer[2]])
    translate([x, (outer[1] + outer[3]) / 2, z_split]) scale([1, 2.2, 1]) sphere(r = 9);
module below_split() translate([outer[0] - 1, outer[1] - 1, z_floor - 1]) cube([500, 500, z_split - z_floor + 1]);
module above_split() translate([outer[0] - 1, outer[1] - 1, z_split]) cube([500, 500, 200]);

module body() difference() { shell(); cavities(); hollow(); finger_notches(); }
module base() difference() { intersection() { body(); below_split(); } magnet_holes(-1); }
module lid()  difference() { intersection() { body(); above_split(); } magnet_holes(1); }

// Cheap fit test: the walls of the base just above the floor, without the floor.
// Put the keyboard halves and the dongle into it to check the outlines before
// ordering the full case.
test_h = 6;
module test_frame() intersection() {
    base();
    translate([outer[0] - 1, outer[1] - 1, z_pocket]) cube([500, 500, test_h]);
}

if (part == "base") base();
if (part == "lid")  lid();
if (part == "test_frame") test_frame();
if (part == "closed") { color("SteelBlue") base(); color("Orange") lid(); }
if (part == "open") {
    color("SteelBlue") base();
    color("Orange") translate([outer[2] - outer[0] + 25, 0, z_top + z_split]) mirror([0, 0, 1]) lid();
}
// cut across the case to show the skins, ribs and hollows
if (part == "section") intersection() {
    union() { color("SteelBlue") base(); color("Orange") lid(); }
    translate([outer[0] - 1, 55, z_floor - 1]) cube([500, 3, 200]);
}
