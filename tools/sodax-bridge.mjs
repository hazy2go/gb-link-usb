// SODAX on the Game Boy: the PC side.
// Puts the Pico into bridge mode, answers the Game Boy's button commands with
// screens built from live SODAX data (oracle candles + solver quotes), and
// refreshes every 30 s. Run rom/sodax.gb on the Game Boy.
//
// Usage: node tools/sodax-bridge.mjs          (needs the Pico with gb-link-usb firmware)
//        node tools/sodax-bridge.mjs --dry    (no Pico: fetch and print screens)
import { closeSync, existsSync, read, writeSync } from 'node:fs';
import { COINS, RANGES, frame, loadScreen } from './sodax.mjs';
import { findPort, openRaw } from './pico.mjs';

const REFRESH_MS = 30000;
const MAGIC = Buffer.from('\x1bGBBRIDGE', 'latin1');
const log = (s) => console.log(`${new Date().toLocaleTimeString('en-GB')}  ${s}`);

let coin = 0, range = 0;

function printScreen(scr) {
  console.log(scr.lines.map((l) => `    | ${l.padEnd(20)} |`).join('\n'));
}

if (process.argv.includes('--dry')) {
  for (let i = 0; i < COINS.length; i++) {
    const scr = await loadScreen(i, RANGES[0]);
    printScreen(scr);
    console.log();
  }
  process.exit(0);
}

let fd = null, port = null, busy = false, pending = null, timer = null;

function writeAll(buf) {
  let off = 0;
  while (off < buf.length) {
    try { off += writeSync(fd, buf, off, buf.length - off); }
    catch (e) {
      if (e.code !== 'EAGAIN') throw e;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 5);   // port busy: wait 5 ms
    }
  }
}

async function sendScreen(why) {
  if (busy) { pending = why; return; }
  busy = true;
  try {
    const scr = await loadScreen(coin, RANGES[range]);
    if (fd !== null) writeAll(frame(scr.payload));
    log(`${COINS[coin].symbol} ${RANGES[range].label} sent (${why}): ${scr.lines[1].trim()}  ${scr.lines[2].slice(0, 9).trim()}  ${scr.lines[6].trim()}`);
  } catch (e) {
    log(`SODAX request failed: ${e.message}`);
  }
  busy = false;
  clearTimeout(timer);
  timer = setTimeout(() => sendScreen('refresh'), REFRESH_MS);
  if (pending) { const w = pending; pending = null; sendScreen(w); }
}

function onCommand(c) {
  switch (c) {
    case 0x48: return sendScreen('Game Boy said hello');                      // H
    case 0x52: coin = (coin + 1) % COINS.length; return sendScreen('next coin'); // R
    case 0x4c: coin = (coin + COINS.length - 1) % COINS.length; return sendScreen('previous coin'); // L
    case 0x42: range = (range + 1) % RANGES.length; return sendScreen('range');  // B
    case 0x41: return sendScreen('refresh button');                           // A
  }
}

function connect() {
  port = findPort();
  if (!port) { setTimeout(connect, 1000); return; }
  try { fd = openRaw(port, 'rw'); } catch { fd = null; setTimeout(connect, 1000); return; }
  writeAll(MAGIC);
  log(`Pico connected (${port}), bridge mode on. Start sodax.gb on the Game Boy.`);
  setTimeout(() => sendScreen('connected'), 200);
  const chunk = Buffer.alloc(1024);
  let lastCheck = Date.now();
  const lost = (why) => {
    try { closeSync(fd); } catch { /* gone */ }
    fd = null;
    log(`Pico disconnected (${why}). Waiting...`);
    setTimeout(connect, 1000);
  };
  const poll = () => {
    read(fd, chunk, 0, chunk.length, null, (err, n) => {
      if (fd === null) return;
      if (err && err.code !== 'EAGAIN') return lost(err.code || err.message);
      if (n > 0) {
        for (let i = 0; i < n; i++) if (chunk[i]) onCommand(chunk[i]);   // 0 = idle poll
        return setImmediate(poll);
      }
      if (Date.now() - lastCheck > 1000) {
        lastCheck = Date.now();
        if (!existsSync(port)) return lost('unplugged');
      }
      setTimeout(poll, 10);
    });
  };
  poll();
}

console.log('SODAX on Game Boy: bridge\nCoins: ' + COINS.map((c) => c.symbol).join(' ') + '\n');
log('Waiting for the Pico...');
connect();
