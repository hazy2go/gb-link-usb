#!/usr/bin/env python3
"""Capture the printer firmware's byte stream to a file and show packets live.

Usage: python3 tools/printcap.py [port]     (Ctrl+C to stop)
Writes captures/<time>.bin. Render it: node tools/render.mjs captures/<file>.bin
"""
import glob, os, select, sys, time, tty

NAMES = {0x01: 'INIT', 0x02: 'PRINT', 0x04: 'DATA', 0x08: 'BREAK', 0x0F: 'STATUS'}
port = sys.argv[1] if len(sys.argv) > 1 else (sorted(glob.glob('/dev/cu.usbmodem*')) or [None])[0]
if not port:
    sys.exit('no /dev/cu.usbmodem* port: is the Pico plugged in?')
os.makedirs('captures', exist_ok=True)
path = time.strftime('captures/%Y%m%d-%H%M%S.bin')
fd = os.open(port, os.O_RDONLY | os.O_NOCTTY)
tty.setraw(fd)
buf = bytearray()
scan = 0
print(f'capturing {port} -> {path} (Ctrl+C to stop)')
try:
    with open(path, 'wb') as f:
        while True:
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                continue
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            f.write(chunk); f.flush()
            buf += chunk
            while True:  # print each complete packet header once
                i = buf.find(b'\x88\x33', scan)
                if i < 0 or i + 6 > len(buf):
                    break
                n = buf[i + 4] | (buf[i + 5] << 8)
                if i + 10 + n > len(buf):
                    break
                cmd = buf[i + 2]
                print(f'{time.strftime("%H:%M:%S")} {NAMES.get(cmd, hex(cmd)):6} len {n}{"  (compressed)" if buf[i + 3] else ""}')
                scan = i + 10 + n
except KeyboardInterrupt:
    pass
print(f'\n{len(buf)} bytes saved to {path}')
