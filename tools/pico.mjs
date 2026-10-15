// Find and open the Pico's USB serial port on macOS (only the Pico, by USB vendor ID).
import { execFileSync } from 'node:child_process';
import { constants, openSync, closeSync } from 'node:fs';

export const VID_RASPBERRY_PI = 0x2e8a;   // our firmware (Pico SDK stdio USB)

export function findPort(vid = VID_RASPBERRY_PI) {
  try {
    const tree = execFileSync('ioreg', ['-r', '-c', 'IOUSBHostDevice', '-l', '-w0'], { encoding: 'utf8', maxBuffer: 64 << 20 });
    for (const dev of tree.split(/^\+-o /m)) {
      if (!dev.includes(`"idVendor" = ${vid}`)) continue;
      const m = dev.match(/"IOCalloutDevice" = "([^"]+)"/);
      if (m) return m[1];
    }
  } catch { /* ioreg missing */ }
  return null;
}

// Open first and keep open (so stty raw sticks), non-blocking. mode: 'r' or 'rw'.
export function openRaw(port, mode = 'r') {
  const flags = (mode === 'rw' ? constants.O_RDWR : constants.O_RDONLY) | constants.O_NOCTTY | constants.O_NONBLOCK;
  const fd = openSync(port, flags);
  try {
    execFileSync('stty', ['-f', port, 'raw', '-echo']);
  } catch (e) { closeSync(fd); throw e; }
  return fd;
}
