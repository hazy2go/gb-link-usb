// Game Boy Printer -> PNG, hands-free.
// Waits for the Pico (printer firmware), saves every finished print as a PNG in
// ~/Pictures/GameBoy Prints (1x and 4x), plays a sound, and keeps running.
// Unplug/replug is fine. Ctrl+C or close the window to stop.
//
// Usage: node tools/gbprint.mjs [--out <folder>] [--file <capture.bin>]
//   --file decodes a saved capture instead of the Pico (for testing).
import { spawn } from 'node:child_process';
import { closeSync, existsSync, mkdirSync, read, readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { parsePackets, assembleImages } from '../web/gbprinter.js';
import { printToPng } from './png.mjs';
import { findPort, openRaw } from './pico.mjs';

const arg = (name) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : null; };
const OUT = arg('--out') || join(homedir(), 'Pictures', 'GameBoy Prints');
const IDLE_MS = 30000;   // after this long without data, an unfinished print is saved as is
mkdirSync(join(OUT, 'raw'), { recursive: true });

const stamp = () => new Date().toLocaleTimeString('en-GB');
const log = (s) => { const line = `${stamp()}  ${s}`; console.log(line); try { appendFileSync(join(OUT, 'gbprint.log'), line + '\n'); } catch { /* ignore */ } };
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

// Read the port ourselves: open it first and keep it open (so the raw mode set by
// stty sticks), non-blocking, and treat "no data right now" as waiting, not as
// end of stream. Unplugging shows up as a read error or the device vanishing.
function connect() {
  const port = findPort();
  if (!port) { setTimeout(connect, 1000); return; }
  let fd;
  try {
    fd = openRaw(port, 'r');
  } catch {
    setTimeout(connect, 1000); return;
  }
  log(`Pico connected (${port}). Print from the Game Boy.`);
  const chunk = Buffer.alloc(4096);
  let lastCheck = Date.now();
  const lost = (why) => {
    try { closeSync(fd); } catch { /* already gone */ }
    log(`Pico disconnected (${why}). Waiting...`);
    setTimeout(connect, 1000);
  };
  const poll = () => {
    readFile_(fd, chunk, (err, n) => {
      if (err && err.code !== 'EAGAIN') return lost(err.code || err.message);
      if (n > 0) {
        if (!rawFile) rawFile = join(OUT, 'raw', `capture-${fileStamp()}.bin`);
        onData(chunk.subarray(0, n));
        return setImmediate(poll);
      }
      if (Date.now() - lastCheck > 1000) {        // quiet: is the Pico still there?
        lastCheck = Date.now();
        if (!existsSync(port)) return lost('unplugged');
      }
      setTimeout(poll, 10);
    });
  };
  poll();
}
const readFile_ = (fd, b, cb) => read(fd, b, 0, b.length, null, cb);

console.log(`Game Boy Printer -> PNG\nSaving to: ${OUT}\n`);
log('Waiting for the Pico...');
connect();
