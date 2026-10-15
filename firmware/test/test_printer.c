// Host test for src/printer.c. Run: make -C firmware/test
// Simulates the link hardware: replies are queued two bytes ahead, exactly as
// the PIO TX FIFO does on the Pico (two zeros primed at start).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../src/printer.h"

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { fails++; printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static printer_t P;
static uint8_t q[4]; static int qn;   // reply queue (models PIO OSR + TX FIFO)

static void link_reset(void) { printer_init(&P); q[0] = q[1] = 0; qn = 2; }

// One byte exchange: the GB sends b, gets back the queued reply.
static uint8_t xfer(uint8_t b) {
    uint8_t out = q[0];
    memmove(q, q + 1, --qn);
    q[qn++] = printer_rx(&P, b);
    return out;
}

// Send a packet, return the status byte the GB sees; check the reply to every byte.
static int send_packet(uint8_t cmd, const uint8_t *data, int len, int corrupt_sum) {
    uint8_t pkt[8 + PRINTER_MAX_DATA + 2];
    int n = 0;
    pkt[n++] = 0x88; pkt[n++] = 0x33; pkt[n++] = cmd; pkt[n++] = 0;
    pkt[n++] = len & 0xff; pkt[n++] = len >> 8;
    uint16_t sum = cmd + (len & 0xff) + (len >> 8);
    for (int i = 0; i < len; i++) { pkt[n++] = data[i]; sum += data[i]; }
    if (corrupt_sum) sum ^= 1;
    pkt[n++] = sum & 0xff; pkt[n++] = sum >> 8; pkt[n++] = 0; pkt[n++] = 0;

    uint8_t r[sizeof pkt];
    for (int i = 0; i < n; i++) r[i] = xfer(pkt[i]);
    for (int i = 0; i < n - 2; i++) CHECK(r[i] == 0, "cmd %02X byte %d reply %02X, want 00", cmd, i, r[i]);
    CHECK(r[n - 2] == PRINTER_ID, "cmd %02X first dummy reply %02X, want 81", cmd, r[n - 2]);
    return r[n - 1];
}

int main(void) {
    uint8_t tiles[PRINTER_MAX_DATA];
    for (int i = 0; i < PRINTER_MAX_DATA; i++) tiles[i] = (uint8_t)(i * 7);
    uint8_t print_args[4] = {1, 0x13, 0xE4, 0x40};
    int st;

    // A typical print job (GB Camera style: INIT, 9 DATA, empty DATA, PRINT, then STATUS polls).
    link_reset();
    st = send_packet(PRINTER_CMD_INIT, NULL, 0, 0);       CHECK(st == 0x00, "INIT status %02X", st);
    st = send_packet(PRINTER_CMD_STATUS, NULL, 0, 0);     CHECK(st == 0x00, "STATUS after INIT %02X", st);
    for (int i = 0; i < 9; i++) {
        st = send_packet(PRINTER_CMD_DATA, tiles, PRINTER_MAX_DATA, 0);
        CHECK(st == 0x00, "DATA %d status %02X", i, st);
    }
    st = send_packet(PRINTER_CMD_DATA, NULL, 0, 0);       CHECK(st == 0x00, "end DATA status %02X", st);
    st = send_packet(PRINTER_CMD_PRINT, print_args, 4, 0); CHECK(st == PRINTER_ST_FULL, "PRINT status %02X", st);

    // Poll: full, then busy+full for a while, then full, then idle.
    int saw_busy = 0, polls = 0, last = -1;
    printf("status after PRINT:");
    while (polls < 100) {
        st = send_packet(PRINTER_CMD_STATUS, NULL, 0, 0);
        polls++;
        if (st != last) { printf(" %02X@%d", st, polls); last = st; }
        if (st & PRINTER_ST_BUSY) saw_busy = 1;
        if (saw_busy && st == 0x00) break;
    }
    printf("\n");
    CHECK(saw_busy, "never reported busy after PRINT");
    CHECK(st == 0x00, "never returned to idle (last %02X)", st);
    CHECK(polls > PRINTER_BUSY_POLLS && polls < PRINTER_BUSY_POLLS + 10, "busy for %d polls", polls);

    // Bad checksum is reported, and the next good packet clears it.
    st = send_packet(PRINTER_CMD_DATA, tiles, 16, 1);     CHECK(st & PRINTER_ST_CHECKSUM, "bad checksum not flagged %02X", st);
    st = send_packet(PRINTER_CMD_DATA, tiles, 16, 0);     CHECK(!(st & PRINTER_ST_CHECKSUM), "checksum flag stuck %02X", st);
    CHECK(P.bad_checksums == 1, "bad_checksums %u", (unsigned)P.bad_checksums);

    // Garbage before a packet and 0x88 0x33 inside data must not confuse framing.
    link_reset();
    xfer(0x12); xfer(0x88); xfer(0x00);
    uint8_t tricky[6] = {0x88, 0x33, 0x01, 0x00, 0x00, 0x00};
    st = send_packet(PRINTER_CMD_DATA, tricky, 6, 0);     CHECK(st == 0x00, "tricky DATA status %02X", st);
    st = send_packet(PRINTER_CMD_INIT, NULL, 0, 0);       CHECK(st == 0x00, "INIT after tricky %02X", st);

    // Absurd length aborts the packet instead of swallowing the link.
    link_reset();
    xfer(0x88); xfer(0x33); xfer(0x04); xfer(0x00); xfer(0xff); xfer(0xff);
    CHECK(P.pos == -1, "absurd length not aborted (pos %d)", P.pos);
    st = send_packet(PRINTER_CMD_INIT, NULL, 0, 0);       CHECK(st == 0x00, "INIT after abort %02X", st);

    CHECK(P.packets > 0, "no packets counted");
    printf(fails ? "%d FAILED\n" : "all printer tests passed\n", fails);
    return fails ? 1 : 0;
}
