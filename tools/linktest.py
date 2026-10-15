#!/usr/bin/env python3
"""First-light check: PC -> Pico (first-light firmware, CDC) -> Game Boy running rom/linktest.gb.

The Pico clocks out each byte we send and returns the byte the Game Boy sent at the same time.
linktest.gb answers with (previous byte it received + 1), starting with 0x42.
Usage: python3 tools/linktest.py [/dev/cu.usbmodemXXXX]   (no extra packages needed)
"""
import glob, os, select, sys, termios, time, tty

# Avoid any byte whose reply would be 0x0D: upstream CDC echo adds 0x0A after 0x0D.
SEND = [0x01, 0x10, 0x20, 0x7F, 0xA0, 0xFE]
EXPECT = [0x42] + [(b + 1) & 0xFF for b in SEND[:-1]]

port = sys.argv[1] if len(sys.argv) > 1 else (sorted(glob.glob('/dev/cu.usbmodem*')) or [None])[0]
if not port:
    sys.exit('no /dev/cu.usbmodem* port: is the Pico plugged in and running the first-light firmware?')
fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
tty.setraw(fd)
termios.tcflush(fd, termios.TCIOFLUSH)
time.sleep(0.2)

got = []
for b in SEND:
    os.write(fd, bytes([b]))
    r, _, _ = select.select([fd], [], [], 1.0)
    got.append(os.read(fd, 1)[0] if r else None)
    time.sleep(0.05)  # give the GB time to redraw and re-arm
os.close(fd)

fmt = lambda v: '--' if v is None else f'{v:02X}'
print('sent    ', ' '.join(fmt(v) for v in SEND))
print('expected', ' '.join(fmt(v) for v in EXPECT))
print('got     ', ' '.join(fmt(v) for v in got))
if got == EXPECT:
    print('PASS: both directions work')
elif all(v is None for v in got):
    print('FAIL: no reply from the Pico (firmware? port?)')
elif all(v == 0xFF for v in got):
    print('FAIL: all FF: nothing driving the Pico input. Check red wire / GB running the ROM / cable plugged in.')
else:
    print('FAIL: replies arrive but are wrong. Try swapping red/orange, check the clock (green).')
