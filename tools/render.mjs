// Render a printer capture (.bin raw stream or hex text) to PNG files.
// Usage: node tools/render.mjs captures/<file>.bin   -> captures/<file>-1.png, -2.png ...
import { readFileSync, writeFileSync } from 'node:fs';
import { deflateSync, crc32 } from 'node:zlib';
import { parsePackets, assembleImages, parseHex } from '../web/gbprinter.js';

const file = process.argv[2];
if (!file) { console.error('usage: node tools/render.mjs <capture>'); process.exit(1); }
let bytes = new Uint8Array(readFileSync(file));
if (!bytes.slice(0, 4096).some((b) => b < 9 || (b > 13 && b < 32))) bytes = parseHex(new TextDecoder().decode(bytes));

const SHADE = [0xff, 0xaa, 0x55, 0x00];
function png(img) {   // 8-bit greyscale PNG
  const raw = Buffer.alloc((img.width + 1) * img.height);
  for (let y = 0; y < img.height; y++)
    for (let x = 0; x < img.width; x++) raw[y * (img.width + 1) + 1 + x] = SHADE[img.shades[y * img.width + x]];
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(img.width, 0); ihdr.writeUInt32BE(img.height, 4); ihdr[8] = 8; ihdr[9] = 0;
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}

const packets = parsePackets(bytes);
const { images, warnings } = assembleImages(packets);
console.log(`${bytes.length} bytes, ${packets.length} packets, ${images.length} image(s)`);
for (const w of warnings) console.log('  warning:', w);
images.forEach((img, i) => {
  const out = file.replace(/\.[^.]+$/, '') + `-${i + 1}.png`;
  writeFileSync(out, png(img));
  console.log(`  ${out} (${img.width}x${img.height})`);
});
