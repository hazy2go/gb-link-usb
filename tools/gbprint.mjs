// Game Boy Printer -> PNG, hands-free.
// Waits for the Pico (printer firmware), saves every finished print as a PNG in
// ~/Pictures/GameBoy Prints (1x and 4x), plays a sound, and keeps running.
// Unplug/replug is fine. Ctrl+C or close the window to stop.
//
// Usage: node tools/gbprint.mjs [--out <folder>] [--file <capture.bin>]
//   --file decodes a saved capture instead of the Pico (for testing).
import { execFileSync, spawn } from 'node:child_process';
import { createReadStream, existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { parsePackets, assembleImages } from '../web/gbprinter.js';
import { printToPng } from './png.mjs';

const arg = (name) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : null; };
const OUT = arg('--out') || join(homedir(), 'Pictures', 'GameBoy Prints');
const IDLE_MS = 30000;   // after this long without data, an unfinished print is saved as is
mkdirSync(join(OUT, 'raw'), { recursive: true });

const stamp = () => new Date().toLocaleTimeString('en-GB');
const log = (s) => console.log(`${stamp()}  ${s}`);
const fileStamp = () => { const d = new Date(), p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`; };

let buf = [], saved = 0, idleTimer = null, rawFile = null;

function save(img) {
  let name = `print-${fileStamp()}`, n = 2;
  while (existsSync(join(OUT, `${name}.png`))) name = `print-${fileStamp()}-${n++}`;
  writeFileSync(join(OUT, `${name}.png`), printToPng(img, 1));
  writeFileSync(join(OUT, `${name}-4x.png`), printToPng(img, 4));
  log(`saved ${name}.png (${img.width}x${img.height})`);
  if (process.platform === 'darwin') spawn('afplay', ['/System/Library/Sounds/Glass.aiff'], { stdio: 'ignore' }).unref();
}

function process_(final) {
  const packets = parsePackets(Uint8Array.from(buf));
  const { images } = assembleImages(packets);
  for (; saved < images.length; saved++) {
    if (images[saved].open && !final) break;      // multi-part print still coming
    save(images[saved]);
  }
}

function onData(chunk) {
  for (const b of chunk) buf.push(b);
  if (rawFile) appendFileSync(rawFile, chunk);
  process_(false);
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {                  // quiet: finish any open print, start fresh
    process_(true);
    buf = []; saved = 0; rawFile = null;
  }, IDLE_MS);
}

// --file: decode a capture and exit
const file = arg('--file');
if (file) {
  buf = [...readFileSync(file)];
  process_(true);
  log(`${saved} print(s) from ${file}`);
  process.exit(0);
}

// Only ever open the Pico (Raspberry Pi USB vendor ID 0x2E8A), never another serial device.
const PICO_VID = 0x2e8a;
function findPort() {
  try {
    const tree = execFileSync('ioreg', ['-r', '-c', 'IOUSBHostDevice', '-l', '-w0'], { encoding: 'utf8' });
    for (const dev of tree.split(/^\+-o /m)) {
      if (!dev.includes(`"idVendor" = ${PICO_VID}`)) continue;
      const m = dev.match(/"IOCalloutDevice" = "([^"]+)"/);
      if (m) return m[1];
    }
  } catch { /* ioreg missing: no port */ }
  return null;
}

function connect() {
  const port = findPort();
  if (!port) { setTimeout(connect, 1000); return; }
  try {
    execFileSync('stty', ['-f', port, 'raw', '-echo']);   // binary, no line editing
  } catch { setTimeout(connect, 1000); return; }
  log(`Pico connected (${port}). Print from the Game Boy.`);
  const s = createReadStream(port, { highWaterMark: 1024 });
  s.on('data', (chunk) => {
    if (!rawFile) rawFile = join(OUT, 'raw', `capture-${fileStamp()}.bin`);
    onData(chunk);
  });
  const retry = (why) => { log(`Pico disconnected (${why}). Waiting...`); s.destroy(); setTimeout(connect, 1000); };
  s.on('error', (e) => retry(e.code || e.message));
  s.on('end', () => retry('end'));
}

console.log(`Game Boy Printer -> PNG\nSaving to: ${OUT}\n`);
log('Waiting for the Pico...');
connect();
