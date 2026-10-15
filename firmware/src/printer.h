// Game Boy Printer emulation: protocol state machine.
// Plain C, no Pico SDK, so it builds and is tested on the host (firmware/test).
// Protocol notes and sources: docs/PROTOCOL.md.
#pragma once
#include <stdbool.h>
#include <stdint.h>

// Commands (Pan Docs "Game Boy Printer").
#define PRINTER_CMD_INIT   0x01
#define PRINTER_CMD_PRINT  0x02
#define PRINTER_CMD_DATA   0x04
#define PRINTER_CMD_BREAK  0x08
#define PRINTER_CMD_STATUS 0x0F

// Status bits (Pan Docs).
#define PRINTER_ST_CHECKSUM 0x01
#define PRINTER_ST_BUSY     0x02
#define PRINTER_ST_FULL     0x04
#define PRINTER_ST_UNPROC   0x08

#define PRINTER_ID         0x81   // sent in the first of the two dummy bytes
#define PRINTER_MAX_DATA   0x280  // 640 bytes, Pan Docs max per DATA packet

typedef struct {
    // packet parser
    int pos;              // index in the packet of the byte just received, -1 = not in a packet
    uint8_t prev;         // previous byte (to spot 0x88 0x33)
    uint8_t cmd;
    uint16_t len;
    uint16_t sum;         // running checksum of cmd..data
    uint16_t sum_rx;      // checksum as sent by the GB
    // status emulation
    uint8_t status;
    uint8_t data_wait;    // STATUS polls until the "data taken" state settles
    uint8_t busy_wait;    // STATUS polls the printer stays busy after PRINT
    // stats
    uint32_t packets;     // complete packets seen
    uint32_t bad_checksums;
} printer_t;

void printer_init(printer_t *p);

// Feed one byte received from the Game Boy. Returns the byte the printer must
// send two bytes later: the link hardware has already queued the reply for the
// next byte by the time this one is processed (see firmware/README.md).
uint8_t printer_rx(printer_t *p, uint8_t b);

// Drop a half-received packet (e.g. after a long pause on the link).
void printer_abort_packet(printer_t *p);

// Number of STATUS polls the emulated printer reports "busy" after PRINT.
#define PRINTER_BUSY_POLLS 20
