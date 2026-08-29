#!/bin/bash
# -----------------------------------------------------------------------------
#  Record a Pole Position II session to an .inp file.
#
#  MAME's a7800 driver reports savestate="unsupported", so .sta files cannot
#  be restored. Input recording works instead: it replays your exact session
#  deterministically from power-on.
#
#  Usage:   double-click for the next free run-NN.inp
#           or from Terminal:  ./"Record Session.command" my-name  ->  my-name.inp
#
#  With no name it picks the next unused run-NN.inp, so a new recording can
#  never overwrite an old one. Play to the point you want captured, then
#  press Esc to stop.
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
if [ ! -f "$CART" ]; then
    echo "Could not find the cartridge at: $CART"
    read -p "Press enter to close..."
    exit 1
fi

NAME="$1"
if [ -z "$NAME" ]; then
    N=1
    while :; do
        NN=$(printf "%02d" "$N")
        [ -f "$DIR/run-$NN.inp" ] || break
        N=$((N + 1))
    done
    NAME="run-$NN"
fi

echo "Recording to \"$DIR/$NAME.inp\""
echo "Play to the point you want captured, then press Esc to stop."
echo ""

"$MAME" a7800 -rompath "$BIOS" -cart "$CART" -skip_gameinfo -window \
    -input_directory "$DIR" -record "$NAME.inp"

echo ""
if [ -f "$DIR/$NAME.inp" ]; then
    SIZE=$(stat -f%z "$DIR/$NAME.inp")
    echo "Saved: $NAME.inp  ($SIZE bytes)"
else
    echo "WARNING: no recording was written."
fi
read -p "Press enter to close..."
