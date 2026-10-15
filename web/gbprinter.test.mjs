// Run: node --test web/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  CMD, parsePackets, decompress, decodeTiles, applyPalette, assembleImages, makePacket, parseHex,
} from './gbprinter.js';

test('packet parse + checksum', () => {
  const raw = Uint8Array.from([0xff, ...makePacket(CMD.INIT), ...makePacket(CMD.PRINT, [1, 0x13, 0xe4, 0x40])]);
  const p = parsePackets(raw);
  assert.equal(p.length, 2);
  assert.equal(p[0].name, 'INIT');
  assert.deepEqual([...p[1].data], [1, 0x13, 0xe4, 0x40]);
  assert.ok(p.every((x) => x.checksumOk));

  const bad = makePacket(CMD.DATA, [1, 2, 3]);
  bad[9] ^= 1; // corrupt a data byte
  assert.equal(parsePackets(Uint8Array.from(bad))[0].checksumOk, false);
});

test('RLE: literal and repeat runs', () => {
  // 0x02 -> 3 literal bytes; 0x81 -> repeat next byte 3 times
  assert.deepEqual([...decompress([0x02, 0xaa, 0xbb, 0xcc, 0x81, 0x11])], [0xaa, 0xbb, 0xcc, 0x11, 0x11, 0x11]);
  assert.equal(decompress([0xff, 0x00]).length, 0x7f + 2);
});

test('2bpp tile decode', () => {
  // first tile, row 0: lo=0b10100000, hi=0b11000000 -> pixels 3,2,1,0,0...
  const data = new Uint8Array(640);
  data[0] = 0b10100000;
  data[1] = 0b11000000;
  const { width, height, pixels } = decodeTiles(data);
  assert.equal(width, 160);
  assert.equal(height, 16);
  assert.deepEqual([...pixels.slice(0, 4)], [3, 2, 1, 0]);
});

test('palette', () => {
  assert.deepEqual([...applyPalette(Uint8Array.from([0, 1, 2, 3]), 0xe4)], [0, 1, 2, 3]);
  assert.deepEqual([...applyPalette(Uint8Array.from([0, 1, 2, 3]), 0x1b)], [3, 2, 1, 0]);
  assert.deepEqual([...applyPalette(Uint8Array.from([0, 1, 2, 3]), 0x00)], [0, 1, 2, 3]);
});

test('full job: 9 DATA packets + PRINT = 160x144 image (camera-style)', () => {
  const raw = [...makePacket(CMD.INIT)];
  for (let i = 0; i < 9; i++) raw.push(...makePacket(CMD.DATA, new Array(640).fill(0xff)));
  raw.push(...makePacket(CMD.DATA)); // empty DATA = end of data
  raw.push(...makePacket(CMD.PRINT, [1, 0x13, 0xe4, 0x40]));
  const { images, warnings } = assembleImages(parsePackets(Uint8Array.from(raw)));
  assert.equal(images.length, 1);
  assert.equal(images[0].height, 144);
  assert.ok(images[0].shades.every((s) => s === 3));
  assert.deepEqual(warnings, []);
});

test('strips join until a PRINT with feed after; compressed DATA works', () => {
  // 0xff -> 129 zeros (x4 = 516), 0xf8 -> 122 zeros, 0x01 -> 2 literal bytes: 640 total
  const comp640 = [0xff, 0, 0xff, 0, 0xff, 0, 0xff, 0, 0xf8, 0, 0x01, 0, 0];
  assert.equal(decompress(comp640).length, 640);
  const raw = [
    ...makePacket(CMD.DATA, comp640, true), ...makePacket(CMD.PRINT, [1, 0x10, 0xe4, 0x40]),
    ...makePacket(CMD.DATA, comp640, true), ...makePacket(CMD.PRINT, [1, 0x03, 0xe4, 0x40]),
    ...makePacket(CMD.DATA, comp640, true), ...makePacket(CMD.PRINT, [1, 0x03, 0xe4, 0x40]),
  ];
  const { images } = assembleImages(parsePackets(Uint8Array.from(raw)));
  assert.deepEqual(images.map((i) => i.height), [32, 16]);
});

test('bad-checksum DATA is skipped, the resent copy is used', () => {
  const tile = new Array(640).fill(0xff);
  const bad = makePacket(CMD.DATA, tile);
  bad[10] ^= 0x01;
  const raw = [...makePacket(CMD.INIT), ...bad, ...makePacket(CMD.DATA, tile), ...makePacket(CMD.PRINT, [1, 0x13, 0xe4, 0x40])];
  const { images, warnings } = assembleImages(parsePackets(Uint8Array.from(raw)));
  assert.equal(images[0].height, 16);
  assert.equal(warnings.length, 1);
});

test('hex dump parse skips comments and JSON lines', () => {
  assert.deepEqual([...parseHex('# log\n{"command":"INIT"}\n88 33 01\n00,00:00\n')], [0x88, 0x33, 0x01, 0x00, 0x00, 0x00]);
});
