// SODAX market data for the Game Boy: price candles from the SODAX oracle, live
// swap quotes from the SODAX solver, packed into one screen frame for rom/sodax.gb.
//
// Endpoints (from @sodax/sdk 2.2.0, no API key needed):
//   GET  https://api.sodax.com/v1/be/oracle/candles?symbol=&interval=&from=&to=   USD OHLC, oldest first
//   POST https://api.sodax.com/v1/intent/quote  {token_src, token_dst, amount, quote_type}  -> {quoted_amount}
// Quote tokens are SODAX hub-chain (Sonic, 146) assets; all pairs below route to USDC (checked 2026-10-16).

const BACKEND = 'https://api.sodax.com/v1/be';
const SOLVER = 'https://api.sodax.com/v1/intent';

export const USDC = { address: '0x29219dd400f2bf60e5a23d13be72b486d4038894', decimals: 6 };

// symbol, hub asset address, decimals, amount used for the quote line
export const COINS = [
  { symbol: 'BTC',  address: '0xeb0393893b5bf98a50073d6740738b08e575058b', decimals: 8,  amount: '0.01' },
  { symbol: 'ETH',  address: '0xaeafa26e43f46cd83efe89b1e57c858eb5685a24', decimals: 18, amount: '0.1' },
  { symbol: 'SOL',  address: '0x0c09e69a4528945de6d16c7e469dea6996fdf636', decimals: 9,  amount: '1' },
  { symbol: 'SODA', address: '0x7c7d53eecda37a87ce0d5bf8e0b24512a48dc963', decimals: 18, amount: '1000' },
  { symbol: 'SUI',  address: '0x4676b2a551b25c04e235553c1c81019337384673', decimals: 9,  amount: '10' },
  { symbol: 'HYPE', address: '0x7288622bc2d39553f34d5b81c88c3f979d91dbc7', decimals: 18, amount: '1' },
  { symbol: 'AVAX', address: '0xc9e4f0b6195f389d9d2b639f2878b7674eb9d8cd', decimals: 18, amount: '1' },
  { symbol: 'XLM',  address: '0x8ac68af223907fb1b893086601a3d99e00f2fa9d', decimals: 7,  amount: '100' },
  { symbol: 'POL',  address: '0x9ee17486571917837210824b0d4cadfe3b324d12', decimals: 18, amount: '100' },
];

// label, candle interval, span in seconds
export const RANGES = [
  { label: '24H', interval: '5m', span: 86400 },
  { label: '7D',  interval: '1h', span: 7 * 86400 },
  { label: '30D', interval: '1h', span: 30 * 86400 },
];

export const CHART_W = 128, CHART_H = 48, LINE = 20;

// The API is behind Cloudflare and occasionally times out or returns 5xx (seen: 520),
// so each request gets a timeout and up to 3 tries.
async function getJson(url, init = {}) {
  let last;
  for (let attempt = 0; attempt < 3; attempt++) {
    if (attempt) await new Promise((r) => setTimeout(r, 800 * attempt));
    try {
      const r = await fetch(url, { ...init, signal: AbortSignal.timeout(10000) });
      const text = await r.text();
      if (r.ok) return JSON.parse(text);
      last = new Error(`HTTP ${r.status}`);
      if (r.status < 500) break;               // 4xx: retrying won't help
    } catch (e) {
      last = new Error(e.name === 'TimeoutError' ? 'timeout' : e.message);
    }
  }
  throw last;
}

export async function fetchCandles(symbol, range, now = Math.floor(Date.now() / 1000)) {
  const q = new URLSearchParams({ symbol, interval: range.interval, from: String(now - range.span), to: String(now) });
  const d = await getJson(`${BACKEND}/oracle/candles?${q}`);
  return d.candles.map((c) => ({ t: c.timestamp, close: Number(c.close), high: Number(c.high), low: Number(c.low) }));
}

// Decimal string -> smallest units, exactly (no float).
export function toUnits(amount, decimals) {
  const [i, f = ''] = amount.split('.');
  return (BigInt(i) * 10n ** BigInt(decimals) + BigInt((f + '0'.repeat(decimals)).slice(0, decimals) || '0')).toString();
}

export async function fetchQuote(coin) {
  const body = { token_src: coin.address, token_dst: USDC.address, amount: toUnits(coin.amount, coin.decimals), quote_type: 'exact_input' };
  const d = await getJson(`${SOLVER}/quote`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return Number(d.quoted_amount) / 10 ** USDC.decimals;   // USDC received
}

// Price text: more decimals for small prices, thousands separators.
export function fmtPrice(v) {
  const d = v >= 1000 ? 2 : v >= 1 ? 3 : v >= 0.01 ? 4 : 6;
  return v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}
// Short form for the low/high line (fits 20 columns together).
const fmtShort = (v) => v >= 1000 ? Math.round(v).toLocaleString('en-US')
  : v.toLocaleString('en-US', { maximumSignificantDigits: 4 });
const fmtUsdc = (v) => v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Resample closes to `n` points (linear interpolation over the candle index).
export function resample(values, n) {
  if (values.length === 0) return [];
  if (values.length === 1) return Array(n).fill(values[0]);
  return Array.from({ length: n }, (_, i) => {
    const x = (i * (values.length - 1)) / (n - 1), k = Math.floor(x), f = x - k;
    return k + 1 < values.length ? values[k] * (1 - f) + values[k + 1] * f : values[k];
  });
}

// Text for rom/sodax.gb: ASCII 0x20-0x5F; bit 7 set = drawn inverted (white on black).
// Glyph reuse in the ROM font: ^ up triangle, \ down triangle, [ filled dot, ] hollow dot.
const clean = (s) => s.toUpperCase().replace(/[^\x20-\x5f]/g, '?');
const inv = (s) => [...clean(s)].map((c) => String.fromCharCode(c.charCodeAt(0) | 0x80)).join('');
const visibleLen = (s) => s.length;
function row(left = '', right = '') {
  const gap = Math.max(1, LINE - visibleLen(left) - visibleLen(right));
  return (left + ' '.repeat(gap) + right).slice(0, LINE).padEnd(LINE);
}
const plain = (s) => [...s].map((c) => String.fromCharCode(c.charCodeAt(0) & 0x7f)).join('');

// Screen layout (rows of the 20x18 tile screen):
//  0  title bar (inverted)        5-10 chart (ROM)       13 quote header
//  2-3 big price                  11  low / high          14-15 quote
//  4  change + range tabs         16  coin page dots      17 footer (ROM)
export function buildScreen({ coin, range, candles, quoteUsdc, coinIndex = 0, coinCount = 1, time = new Date() }) {
  const closes = candles.map((c) => c.close);
  const last = closes.at(-1), first = closes[0];
  const lo = Math.min(...candles.map((c) => c.low)), hi = Math.max(...candles.map((c) => c.high));
  const change = ((last - first) / first) * 100;
  const hhmm = time.toTimeString().slice(0, 5);

  let price = `$${fmtPrice(last)}`;
  if (price.length > 10) price = `$${fmtShort(last)}`;
  price = price.slice(0, 10).padEnd(10);

  const tabs = RANGES.map((r) => (r === range ? inv(r.label) : clean(r.label))).join(' ');
  const arrow = change >= 0 ? '^' : '\\';
  const dots = Array.from({ length: coinCount }, (_, i) => (i === coinIndex ? '[' : ']')).join(' ');
  const pad = Math.max(0, Math.floor((LINE - dots.length) / 2));

  const rows = [
    inv(row(' SODAX', `${coin.symbol}/USD `)),
    row(`${arrow}${change >= 0 ? '+' : ''}${change.toFixed(2)}%`, tabs),
    row(clean(`L ${fmtShort(lo)}`), clean(`H ${fmtShort(hi)}`)),
    row(inv(' SOLVER QUOTE '), hhmm),
    row(clean(` PAY ${coin.amount} ${coin.symbol}`)),
    row(clean(quoteUsdc == null ? ' NO ROUTE RIGHT NOW' : ` GET ${fmtUsdc(quoteUsdc)} USDC`)),
    (' '.repeat(pad) + dots).padEnd(LINE).slice(0, LINE),
  ];
  const pts = resample(closes, CHART_W);
  const pmin = Math.min(...pts), pmax = Math.max(...pts), span = pmax - pmin || 1;
  const chart = pts.map((v) => Math.round((1 - (v - pmin) / span) * (CHART_H - 1)));
  const text = Buffer.from([rows[0], price, ...rows.slice(1)].join(''), 'latin1');
  return { lines: [plain(rows[0]), price, ...rows.slice(1).map(plain)], chart, payload: Buffer.concat([text, Buffer.from(chart)]) };
}

// Frame: 0x7E, type 0x01, length (LE16), payload, sum of payload bytes (LE16).
export function frame(payload, type = 0x01) {
  let sum = 0;
  for (const b of payload) sum = (sum + b) & 0xffff;
  return Buffer.concat([Buffer.from([0x7e, type, payload.length & 0xff, payload.length >> 8]), payload, Buffer.from([sum & 0xff, sum >> 8])]);
}

// Everything for one screen; a failing quote still shows the chart.
// If SODAX is briefly unreachable, the last good candles / quote are reused.
const lastGood = new Map();
export async function loadScreen(coinIndex, range) {
  const coin = COINS[coinIndex];
  const key = `${coin.symbol}/${range.label}`;
  const [c, q] = await Promise.allSettled([fetchCandles(coin.symbol, range), fetchQuote(coin)]);
  const prev = lastGood.get(key) || {};
  const candles = c.status === 'fulfilled' && c.value.length ? c.value : prev.candles;
  const quoteUsdc = q.status === 'fulfilled' ? q.value : prev.quoteUsdc ?? null;
  if (!candles) throw new Error(`no candles for ${coin.symbol} (${c.reason?.message || 'empty'})`);
  lastGood.set(key, { candles, quoteUsdc });
  const scr = buildScreen({ coin, range, candles, quoteUsdc, coinIndex, coinCount: COINS.length });
  scr.stale = c.status !== 'fulfilled' || q.status !== 'fulfilled';
  return scr;
}
