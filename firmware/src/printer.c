// Game Boy Printer emulation. See printer.h.
//
// Packet (Pan Docs): 0x88 0x33, cmd, compression, len lo, len hi, data[len],
// sum lo, sum hi, then two dummy bytes. The printer replies 0x00 to every byte
// except the dummies: PRINTER_ID, then its status byte.
//
// Status sequence: behaves like mofosyne's emulator, which is tested against
// the official printer games (our own code, same observable behaviour):
//   INIT clears busy/full. DATA and a later end-of-data (empty DATA) set
//   "full". After PRINT a few STATUS polls report data still settling, then
//   busy+full for PRINTER_BUSY_POLLS polls, then busy clears, then full clears.
#include "printer.h"

void printer_init(printer_t *p) {
    *p = (printer_t){0};
    p->pos = -1;
}

void printer_abort_packet(printer_t *p) {
    p->pos = -1;
    p->prev = 0;
}

// Status for this packet, decided once the checksum has arrived.
static void on_checksum(printer_t *p) {
    if (p->sum == p->sum_rx) p->status &= ~PRINTER_ST_CHECKSUM;
    else { p->status |= PRINTER_ST_CHECKSUM; p->bad_checksums++; }

    switch (p->cmd) {
    case PRINTER_CMD_INIT:
        p->data_wait = 0;
        p->busy_wait = 0;
        p->status &= ~(PRINTER_ST_FULL | PRINTER_ST_BUSY);
        break;
    case PRINTER_CMD_PRINT:
        p->busy_wait = PRINTER_BUSY_POLLS;
        break;
    case PRINTER_CMD_DATA:
        p->data_wait = 3;
        break;
    case PRINTER_CMD_BREAK:
        p->status = PRINTER_ST_FULL | PRINTER_ST_BUSY;
        break;
    case PRINTER_CMD_STATUS:
        if (p->data_wait) {
            if (--p->data_wait == 0) {
                p->status &= ~PRINTER_ST_UNPROC;
                if (p->busy_wait) p->status |= PRINTER_ST_BUSY | PRINTER_ST_FULL;
            }
        } else if (p->busy_wait) {
            if (--p->busy_wait == 0) p->status &= ~PRINTER_ST_BUSY;
        }
        break;
    }
}

// Changes that apply from the next packet on, after the status was sent.
static void on_packet_done(printer_t *p) {
    p->packets++;
    switch (p->cmd) {
    case PRINTER_CMD_DATA:
        p->status &= ~(PRINTER_ST_FULL | PRINTER_ST_UNPROC);
        if (p->len == 0) p->status |= PRINTER_ST_FULL;  // end of data
        break;
    case PRINTER_CMD_STATUS:
        p->status &= ~PRINTER_ST_UNPROC;
        if (!p->data_wait && !p->busy_wait) p->status &= ~PRINTER_ST_FULL;
        break;
    }
}

// Reply for packet index j, given what is known so far.
static uint8_t reply_for(const printer_t *p, int j) {
    if (p->pos < 5) return 0x00;              // length not known yet; j <= 6 anyway
    if (j == 8 + p->len) return PRINTER_ID;
    if (j == 9 + p->len) return p->status;
    return 0x00;
}

uint8_t printer_rx(printer_t *p, uint8_t b) {
    if (p->pos < 0) {
        if (p->prev == 0x88 && b == 0x33) p->pos = 1;
        p->prev = b;
        return 0x00;                          // reply for index 3 (or for idle bytes)
    }

    int i = ++p->pos;
    if (i == 2) { p->cmd = b; p->sum = b; }
    else if (i == 3) { p->sum += b; }
    else if (i == 4) { p->len = b; p->sum += b; }
    else if (i == 5) {
        p->len |= (uint16_t)b << 8;
        p->sum += b;
        if (p->len > PRINTER_MAX_DATA) { printer_abort_packet(p); return 0x00; }
    }
    else if (i < 6 + p->len) { p->sum += b; }
    else if (i == 6 + p->len) { p->sum_rx = b; }
    else if (i == 7 + p->len) { p->sum_rx |= (uint16_t)b << 8; on_checksum(p); }

    uint8_t reply = reply_for(p, i + 2);

    if (i == 9 + p->len) {                    // second dummy byte: packet complete
        on_packet_done(p);
        printer_abort_packet(p);
    }
    return reply;
}
