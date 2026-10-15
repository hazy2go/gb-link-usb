#!/bin/zsh
# Double-click to start: live SODAX prices and quotes on the Game Boy (run rom/sodax.gb).
cd "$(dirname "$0")"
NODE=$(command -v node || echo /opt/homebrew/bin/node)
exec "$NODE" tools/sodax-bridge.mjs
