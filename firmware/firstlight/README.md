# First light: stacksmashing/gb-link-firmware on the Pico 2 W

Upstream firmware (GPL-3, commit 36aac15, last push 2022) used only to prove the wiring. Not our firmware.

`tinyusb-api.patch` makes four small changes for Pico SDK 2.3.1 / current TinyUSB:
1. Vendor control callback renamed (`tud_vendor_control_xfer_cb`), else it doesn't compile.
2. `tud_vendor_write_flush()` after each write: current TinyUSB buffers vendor TX until 64 bytes or a flush, so 1-byte replies would never reach the PC.
3. Upstream bug: the CDC handler read from the vendor stream (`tud_vendor_read`) instead of `tud_cdc_read`, so the serial port never worked. Fixed so we can test from a terminal without libusb.

4. `gpio_pull_up(PIN_SIN)` after PIO init. On the RP2350 the input pad's default pull-down, together with the RP2350-E9 leakage erratum (verify against the datasheet errata), held GP1 near 2 V against the shifter's 10k pull-up, so the Pico read 0. Measured: LV2 ~2 V, replies all 00. With the pull-up: replies FF (idle high), as expected.

Quirk left as is: the CDC echo adds 0x0A after any 0x0D byte (`tools/linktest.py` avoids it).

```sh
git clone https://github.com/stacksmashing/gb-link-firmware.git && cd gb-link-firmware
git apply ../path/to/tinyusb-api.patch
cmake -S . -B build -G Ninja -DPICO_BOARD=pico2_w && ninja -C build   # -> build/gbusb.uf2
```

Pins (from upstream main.c / pio/spi.pio): the Pico is clock **master**.
- GPIO0 = SCK out -> GB SCK
- GPIO1 = data in  <- GB SOUT
- GPIO2 = data out -> GB SIN

Each byte the PC sends (WebUSB or CDC) is clocked out to the Game Boy, and the byte received at the same time is sent back. Clock: clkdiv 4058.838, 4 PIO cycles per bit; at the RP2350's 150 MHz that is about 9.2 kHz (upstream tuned it for 125 MHz, about 7.7 kHz) (verify with a scope or by GB behaviour).

## Test
1. `rom/linktest.gb` on the EverDrive (`cd rom && make`). The GB is the clock slave and answers each byte with (last byte received + 1), first answer 0x42. Screen: last byte and a counter.
2. Flash `gbusb.uf2`, run `python3 tools/linktest.py`. PASS = both directions and the clock work.
