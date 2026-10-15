#!/bin/zsh
# Double-click to start: saves every Game Boy print to ~/Pictures/GameBoy Prints.
cd "$(dirname "$0")"
open "$HOME/Pictures/GameBoy Prints" 2>/dev/null || { mkdir -p "$HOME/Pictures/GameBoy Prints"; open "$HOME/Pictures/GameBoy Prints"; }
NODE=$(command -v node || echo /opt/homebrew/bin/node)
exec "$NODE" tools/gbprint.mjs
