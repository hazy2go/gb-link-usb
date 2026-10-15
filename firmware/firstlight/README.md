# First light: stacksmashing/gb-link-firmware on the Pico 2 W

Upstream firmware (GPL-3, commit 36aac15, last push 2022) used only to prove the wiring. Not our firmware.

It no longer builds on Pico SDK 2.3.1 (TinyUSB renamed the vendor control callback), so `tinyusb-api.patch` makes the one needed change.

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
