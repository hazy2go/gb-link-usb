// Pin map per board. Select with cmake -DGBLINK_BOARD=breadboard (default) or revA.
#pragma once

#if defined(GBLINK_BOARD_REVA)
// PCB rev A (hw/rev-a, docs/PCB.md): pins go through 74LVC1T45 translators (Game Boy side at USB 5 V).
#define BOARD_NAME "rev A"
#define PIN_SCK  12  // U102 A side (SCK, both directions)
#define PIN_IN   13  // U103 A side, from GB SOUT (DIR tied low: B to A)
#define PIN_OUT  14  // U104 A side, to GB SIN (DIR tied high: A to B)
#define PIN_SCK_DIR 11  // U102 DIR: low = Game Boy drives SCK (B to A), high = we drive it. R103 pulls it low.
#define PIN_LED  21  // D101 through R109, active high
#else
// Breadboard (docs/breadboard.html): plug 5 SCK, plug 2 GB SOUT, plug 3 GB SIN, wired straight to the Pico 2 W.
#define BOARD_NAME "breadboard"
#define PIN_SCK  0
#define PIN_IN   1   // from GB SOUT
#define PIN_OUT  2   // to GB SIN
#define LED_CYW43 1  // the Pico 2 W's LED hangs off the wireless chip
#endif
