// Minimal greyscale PNG encoder for decoded prints (no dependencies).
import { deflateSync, crc32 } from 'node:zlib';

const SHADE = [0xff, 0xaa, 0x55, 0x00];

// img = { width, height, shades } from web/gbprinter.js; scale = whole-number pixel size.
export function printToPng(img, scale = 1) {
  const w = img.width * scale, h = img.height * scale;
  const raw = Buffer.alloc((w + 1) * h);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++)
      raw[y * (w + 1) + 1 + x] = SHADE[img.shades[Math.floor(y / scale) * img.width + Math.floor(x / scale)]];
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 0;
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
