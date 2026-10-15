# SODAX on the Game Boy

Live crypto prices and real swap quotes from [SODAX](https://sodax.com) on an original Game Boy, through the gb-link-usb Pico.

<p align="center">
  <img src="img/sodax-splash.png" width="240" alt="Splash screen with the SODAX logo">
  <img src="img/sodax-btc.png" width="240" alt="BTC 24H chart, price and solver quote">
  <img src="img/sodax-eth.png" width="240" alt="ETH 30D chart, price and solver quote">
</p>
<p align="center"><sub>Emulator screenshots (PyBoy) with live SODAX data, 3x.</sub></p>

## Use it
1. Pico with the gb-link-usb firmware (v0.2+), wired as in the main README.
2. Put `rom/sodax.gb` on a flash cart (EverDrive etc.).
3. Pico on USB, then double-click **`SODAX Bridge.command`** (or `node tools/sodax-bridge.mjs`). Close the GB Printer tool first: one program at a time.
4. Switch the Game Boy on and start sodax.gb.

| Button | Action |
|---|---|
| Left / Right (or Up / Down) | previous / next coin |
| B | range: 24H, 7D, 30D |
| A or Start | load fresh data now (the footer says A:LOAD) |

The screen also refreshes every 30 s. Coins: BTC, ETH, SOL, SODA, SUI, HYPE, AVAX, XLM, POL.

## Where the data comes from
- **Chart, price, change, low/high:** SODAX oracle candles, `GET https://api.sodax.com/v1/be/oracle/candles` (USD OHLC; 5 min candles for 24H, 1 h for 7D and 30D).
- **Quote:** SODAX solver, `POST https://api.sodax.com/v1/intent/quote` with hub-chain (Sonic) asset addresses, exact input into USDC. A real, live route quote, not an oracle price.
- No API key needed. Endpoints and token addresses taken from `@sodax/sdk` 2.2.0 and the solver oracle.

## How it works
```
Game Boy (sodax.gb, clock master) --polls 1 byte/ms--> Pico (bridge mode) <--USB serial--> sodax-bridge.mjs --HTTPS--> SODAX API
```
- The Game Boy polls continuously; each poll sends a button command (or 0) and receives the next byte the PC has queued.
- The PC sends one **screen frame** per update: `$7E, $01, length 278 (LE16), payload, sum (LE16)`. Payload: 8 text rows (20 chars; bit 7 = inverted) plus 128 chart points (0 top .. 47 bottom). About 0.3 s per frame at the DMG's 8192 Hz link clock.
- The ROM draws the chart (shaded area, grid, 2 px line, end marker) off screen and copies it to VRAM a slice per VBlank, so updates never blank the screen.
- Pico bridge mode starts when the PC sends `ESC GBBRIDGE` and ends when the PC closes the port (back to printer mode).

## Screen
```
row 0      title bar (inverted)          rows 5-10  chart, 128x48
rows 2-3   price, bold 8x16 digits       row 11     low / high
row 4      change ▲/▼ + range tabs       rows 13-15 solver quote
row 16     coin page dots                row 17     controls (inverted)
```
Logo: the official SODAX lockup from `icon-project/sodax-sdks` (MIT), converted to 4 shades.
