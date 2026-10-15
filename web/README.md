# Web

Static page, no build step.

- `gbprinter.js`: decoder (packets -> images). Pure JS, runs in browser and Node.
- `index.html`: paste a hex dump / open a log or binary capture, see prints, download PNGs. `#demo` in the URL loads a test print.
- Tests: `npm test` (Node 20+).
- Run locally: `npm run serve`, then open http://localhost:8000 (modules need http, not file://).

Still to come: live input over WebUSB from the firmware, raw console, online link.
