// Game Boy Printer data decoding: packets -> print jobs -> pixels.
// Pure functions, no DOM, so the same code runs in the browser and in Node tests.
// Protocol notes and sources: docs/PROTOCOL.md.

export const CMD = { INIT: 0x01, PRINT: 0x02, DATA: 0x04, BREAK: 0x08, STATUS: 0x0f };
const CMD_NAME = Object.fromEntries(Object.entries(CMD).map(([k, v]) => [v, k]));

export const WIDTH = 160; // 20 tiles
const TILES_PER_ROW = 20;
const TILE_BYTES = 16;

// Find packets in a raw byte stream (what the Game Boy sends on SOUT).
// Layout (Pan Docs): 0x88 0x33, cmd, compression, len lo, len hi, data[len], sum lo, sum hi.
// The checksum is the 16-bit sum of every byte except the magic and the checksum itself.
// The two trailing dummy bytes (printer answers 0x81 + status) are skipped if present.
export function parsePackets(bytes) {
  const packets = [];
  let i = 0;
  while (i + 8 <= bytes.length) {
    if (bytes[i] !== 0x88 || bytes[i + 1] !== 0x33) { i++; continue; }
    const command = bytes[i + 2];
    const compressed = bytes[i + 3] !== 0;
    const length = bytes[i + 4] | (bytes[i + 5] << 8);
    const end = i + 6 + length;
    if (end + 2 > bytes.length) break; // truncated
    const data = bytes.slice(i + 6, end);
    let sum = command + bytes[i + 3] + bytes[i + 4] + bytes[i + 5];
    for (const b of data) sum += b;
    const checksum = bytes[end] | (bytes[end + 1] << 8);
    packets.push({
      command,
      name: CMD_NAME[command] ?? `0x${command.toString(16)}`,
      compressed,
      data,
      checksumOk: (sum & 0xffff) === checksum,
    });
    i = end + 2;
  }
  return packets;
}

// RLE used by some games (e.g. Pokémon Trading Card Game); the GB Camera sends raw data.
// Scheme from mofosyne's decoder (Pan Docs leaves it undocumented):
//   control < 0x80: copy the next control+1 bytes as they are
//   control >= 0x80: repeat the next byte (control - 0x80) + 2 times
export function decompress(data) {
  const out = [];
  let i = 0;
  while (i < data.length) {
    const c = data[i++];
    if (c < 0x80) {
      for (let n = 0; n <= c && i < data.length; n++) out.push(data[i++]);
    } else if (i < data.length) {
      const b = data[i++];
      for (let n = 0; n < c - 0x80 + 2; n++) out.push(b);
    }
  }
  return Uint8Array.from(out);
}

// Decode 2 bpp tiles (20 per row, in send order) into one color index (0-3) per pixel.
// Pan Docs tile format: 2 bytes per pixel row, first byte = low bit of the color index,
// second = high bit, bit 7 = leftmost pixel.
export function decodeTiles(tileData) {
  const tileRows = Math.floor(tileData.length / (TILE_BYTES * TILES_PER_ROW));
  const height = tileRows * 8;
  const pixels = new Uint8Array(WIDTH * height);
  for (let t = 0; t < tileRows * TILES_PER_ROW; t++) {
    const tx = (t % TILES_PER_ROW) * 8;
    const ty = Math.floor(t / TILES_PER_ROW) * 8;
    for (let y = 0; y < 8; y++) {
      const lo = tileData[t * TILE_BYTES + y * 2];
      const hi = tileData[t * TILE_BYTES + y * 2 + 1];
      for (let x = 0; x < 8; x++) {
        const bit = 7 - x;
        pixels[(ty + y) * WIDTH + tx + x] = (((hi >> bit) & 1) << 1) | ((lo >> bit) & 1);
      }
    }
  }
  return { width: WIDTH, height, pixels };
}

// Map color indices to shades (0 = white .. 3 = black) with the PRINT palette byte.
// Assumed layout (verify): bits 1-0 = shade of index 0, ..., bits 7-6 = shade of index 3,
// so the usual 0xE4 is the identity. 0x00 is treated as 0xE4 (verify: some games send 0).
export function applyPalette(pixels, palette) {
  const p = palette === 0 ? 0xe4 : palette;
  const map = [0, 1, 2, 3].map((c) => (p >> (c * 2)) & 3);
  return pixels.map((c) => map[c]);
}

// Turn a packet list into finished images.
// DATA packets fill the buffer; each PRINT turns the buffer into a strip.
// Strips are joined into one image until a PRINT has a non-zero feed after (verify:
// matches how multi-part prints like Pokémon Pikachu look, not checked on hardware).
export function assembleImages(packets) {
  const images = [];
  const warnings = [];
  let buffer = [];
  let strips = [];

  const flush = () => {
    if (!strips.length) return;
    const height = strips.reduce((h, s) => h + s.height, 0);
    const shades = new Uint8Array(WIDTH * height);
    let off = 0;
    for (const s of strips) { shades.set(s.shades, off); off += s.shades.length; }
    images.push({ width: WIDTH, height, shades });
    strips = [];
  };

  for (const p of packets) {
    if (!p.checksumOk) warnings.push(`${p.name} packet with bad checksum (used anyway)`);
    if (p.command === CMD.INIT) {
      buffer = [];
    } else if (p.command === CMD.DATA) {
      const d = p.compressed ? decompress(p.data) : p.data;
      for (const b of d) buffer.push(b);
    } else if (p.command === CMD.PRINT) {
      const [sheets = 1, margins = 0, palette = 0xe4] = p.data;
      const tiles = decodeTiles(Uint8Array.from(buffer));
      buffer = [];
      if (sheets > 0 && tiles.height > 0) {
        strips.push({ height: tiles.height, shades: applyPalette(tiles.pixels, palette) });
      }
      if ((margins & 0x0f) !== 0) flush();
    }
  }
  flush();
  if (buffer.length) warnings.push(`${buffer.length} bytes of DATA never printed`);
  return { images, warnings };
}

// Shades -> RGBA (for a canvas ImageData). Default: plain grey scale.
export const GREYS = [[0xff, 0xff, 0xff], [0xaa, 0xaa, 0xaa], [0x55, 0x55, 0x55], [0x00, 0x00, 0x00]];
export function toRGBA(image, colors = GREYS) {
  const rgba = new Uint8ClampedArray(image.width * image.height * 4);
  image.shades.forEach((s, i) => {
    rgba.set(colors[s], i * 4);
    rgba[i * 4 + 3] = 0xff;
  });
  return rgba;
}

// Build a packet (used by tests and the demo; also handy for a future GB-side test ROM).
export function makePacket(command, data = [], compressed = false) {
  const len = data.length;
  const body = [command, compressed ? 1 : 0, len & 0xff, len >> 8, ...data];
  const sum = body.reduce((a, b) => a + b, 0) & 0xffff;
  return [0x88, 0x33, ...body, sum & 0xff, sum >> 8, 0x00, 0x00];
}

// Parse a hex dump ("88 33 01 00 ..." with any separators; ignores lines starting with # or //
// and anything that is not a pair of hex digits, such as JSON lines in emulator logs).
export function parseHex(text) {
  const bytes = [];
  for (const line of text.split(/\r?\n/)) {
    const l = line.trim();
    if (!l || l.startsWith('#') || l.startsWith('//') || l.startsWith('{')) continue;
    for (const m of l.matchAll(/\b[0-9a-fA-F]{2}\b/g)) bytes.push(parseInt(m[0], 16));
  }
  return Uint8Array.from(bytes);
}
