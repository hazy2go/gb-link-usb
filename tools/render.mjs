// Render a printer capture (.bin raw stream or hex text) to PNG files.
// Usage: node tools/render.mjs captures/<file>.bin   -> captures/<file>-1.png, -2.png ...
import { readFileSync, writeFileSync } from 'node:fs';
import { parsePackets, assembleImages, parseHex } from '../web/gbprinter.js';
import { printToPng } from './png.mjs';

const file = process.argv[2];
if (!file) { console.error('usage: node tools/render.mjs <capture>'); process.exit(1); }
let bytes = new Uint8Array(readFileSync(file));
if (!bytes.slice(0, 4096).some((b) => b < 9 || (b > 13 && b < 32))) bytes = parseHex(new TextDecoder().decode(bytes));

const packets = parsePackets(bytes);
const { images, warnings } = assembleImages(packets);
console.log(`${bytes.length} bytes, ${packets.length} packets, ${images.length} image(s)`);
for (const w of warnings) console.log('  warning:', w);
images.forEach((img, i) => {
  const out = file.replace(/\.[^.]+$/, '') + `-${i + 1}.png`;
  writeFileSync(out, printToPng(img));
  console.log(`  ${out} (${img.width}x${img.height})`);
});
