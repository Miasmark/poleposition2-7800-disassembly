#!/bin/bash
# -----------------------------------------------------------------------------
#  Watch a recorded Pole Position II session play back.
#
#  Usage:   double-click, then type the recording name when asked
#           or from Terminal:  ./"Play Recording.command" run-01
#
#  While watching:  P pauses,  Esc quits,  Tab opens the MAME menu.
#  When the recording runs out the game simply carries on under your control.
# -----------------------------------------------------------------------------
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

MAME="$(command -v mame || true)"
BIOS="$DIR/../bios"
CART="$DIR/Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"

if [ -z "$MAME" ]; then
    echo "Could not find mame on PATH. Install it with: brew install mame"
    read -p "Press enter to close..."
    exit 1
fi

NAME="$1"
if [ -z "$NAME" ]; then
    echo "Recordings available:"
    for f in "$DIR"/*.inp; do
        [ -e "$f" ] && echo "   $(basename "${f%.inp}")"
    done
    echo ""
    read -p "Recording name (without .inp): " NAME
fi
if [ -z "$NAME" ] || [ ! -f "$DIR/$NAME.inp" ]; then
    echo "No such recording: $NAME.inp"
    read -p "Press enter to close..."
    exit 1
fi

echo "Recording: $NAME.inp"
echo "Cart:      $(basename "$CART")"
echo ""
echo "P pauses, Esc quits."
echo ""

"$MAME" a7800 -rompath "$BIOS" -cart "$CART" -skip_gameinfo -window \
    -input_directory "$DIR" -playback "$NAME.inp"

read -p "Press enter to close..."
