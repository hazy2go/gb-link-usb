# Link port, timing and the printer protocol

Sources: Pan Docs (gbdev.io/pandocs: "Serial Data Transfer (Link Cable)" and "Game Boy Printer"), and the prior-art repos listed in the README. **Anything marked (verify) has not been checked against hardware or the source yet.**

## DMG link port
- Signals are **5 V logic** on the original Game Boy (DMG).
- Pins (Pan Docs): **1 VCC (5 V)**, **2 SOUT** (serial out), **3 SIN** (serial in), **4 SD** (unused in normal play), **5 SCK** (clock), **6 GND**. Physical layout of the socket, flat side up: 2, 4, 6 on the top row and 1, 3, 5 on the bottom (verify on our plug).
- The link cable **crosses SOUT and SIN**, so one side's SOUT goes to the other side's SIN.
- Don't power anything from the link-port VCC; the Pico is powered from USB.
- **Our cut cable:** wire colors are not standard between cables. Map each wire to a plug pin before wiring (continuity check, multimeter or a Pico test script). Record the mapping in LOGBOOK.

## Serial transfer
- Byte-wide, MSB first, SPI-like. Each transfer shifts one byte out on SOUT while shifting one byte in on SIN, 8 clock pulses on SCK.
- **Clock master:** whichever side uses the internal clock. On the DMG the internal clock is **8192 Hz** (1 KB/s). The other side runs on the external clock it receives.
- Data changes on the falling edge and is sampled on the rising edge of SCK (verify; stacksmashing's PIO program uses an SPI "cpha1" mode).
- With an external clock the DMG accepts much faster rates than 8 kHz; the safe maximum is to be measured (verify).
- Registers on the Game Boy side: `SB` (FF01, data) and `SC` (FF02: bit 7 start, bit 0 clock select).

## Game Boy Printer protocol (printer = clock slave)
The Game Boy is the master (internal clock), the printer (our emulator) answers.

Packet sent by the Game Boy:

| bytes | meaning |
|---|---|
| `0x88 0x33` | magic |
| 1 | command: `0x01` INIT, `0x02` PRINT, `0x04` DATA, `0x08` BREAK, `0x0F` STATUS |
| 1 | compression flag (0 or 1, RLE) |
| 2 | data length, little-endian |
| n | data |
| 2 | checksum, little-endian (sum of command..data) |
| 2 | two dummy bytes: the printer answers `0x81` (alive) and then its status byte |

- **DATA** carries image tiles: 2 bpp Game Boy tiles, 160 px wide (20 tiles). A full DATA packet is 640 bytes (2 tile rows); an empty DATA packet marks the end of data.
- **PRINT** carries 4 bytes: sheets, margins, palette, exposure.
- **STATUS** is polled; the status bits tell the game "printing", "done", errors. The emulator has to report realistic status values or some games stall.
- Exact status values and timing per game: follow mofosyne's emulator, which is tested against every official printer game (verify against Pan Docs).

## PC side
- **WebUSB** (vendor interface, TinyUSB) lets a Chrome/Edge page talk to the device with no driver. stacksmashing's firmware also exposes a CDC serial port for apps.
- Printer milestone: firmware forwards raw packets (or decoded tiles) to the PC; the page renders 2 bpp tiles to a PNG.
