# Pole Position II (Atari 7800) disassembly

A byte-identical disassembly and memory-map investigation of *Pole Position II*
(NTSC, Atari, 1987), built with
[a7800-toolkit](https://github.com/Miasmark/a7800-toolkit) and MAME as a
live-verification instrument, not just a static reader.

**This repo does not contain the ROM.** Supply your own legally-owned dump
(`Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78`, alongside a 7800
BIOS) to reproduce anything here. The disassembly listing itself
(`src/rom.asm`) isn't committed either -- it's fully generated from
[`annotations.json`](annotations.json) plus the ROM, and regenerating it is one
command (below).

## Start here

[`docs/FINDINGS.md`](docs/FINDINGS.md) is the real deliverable: a narrative of
what has been confirmed live in MAME, what is still a hint, and what was
actively distrusted, tested, and in several cases retracted rather than
assumed. [`annotations.json`](annotations.json) is the machine-readable form of
the same knowledge.

**This is a partial disassembly, and the number is the honest one: 33.5% of the
cartridge is reached as code.** Around 21,000 bytes remain unclassified, most
of it the graphics block at `$8000` and a large data region at `$AE2F` that
traced code demonstrably reads from but which is not broken down here. What is
mapped is the machinery rather than the artwork.

Solved and live-verified on the gameplay side:

* **The driving model.** Two 16-entry acceleration curves selected by gear --
  LO goes negative above about 192 and tops out near 176, HI pulls +1 forever
  and is the only way to reach 255. Coast, brake, crash and clock-expiry
  deceleration; the skid test against eight speed-banded traction thresholds,
  and the drag it applies.
* **The collision system.** Sixteen object slots, a 78-entry perspective table
  turning distance into a screen row, lateral thresholds of 30 near and 26 far,
  and a type dispatch that separates puddles (which slow you) from signs and
  rival cars (which end your run).
* **The track format.** Four courses stored as nibble-packed segment lists --
  low nibble indexes a menu of fourteen lengths, high nibble is curvature. TEST
  decodes to a literal rounded rectangle of four identical eased corners.
* **The sound engine.** Twenty sounds, each driving three independent byte
  streams into the TIA's two voices, arbitrated by a priority table that puts
  the engine at the bottom so every effect simply borrows a voice.
* **The state machine**, the display-interrupt chain, the race clock, the lap
  timer, the qualifying thresholds, the character set and the HUD.

The wrong turns are deliberately left next to the corrections, because several
were the most instructive part of the work: five speed drops called
"mechanical" that were one ordinary application of a formula printed in the
paragraph above the guess; a puddle detector built from that formula that
aliased against a scripted ramp and produced two false positives; and a
coverage tool reporting "no missed code" about a region it had no way to enter.

**No reference source was used.** Unlike some of the sibling projects, no
private or unlicensed historical source was consulted for this game at any
point -- every finding here comes from the ROM, the recordings, and MAME.

Working discipline, same as the sibling projects: every claim about what a byte
range does should be checked live before it is trusted, not pattern-matched
from a probe script carried over from a previous project. Every
`annotations.json` change is followed by JSON validation, `disasm.py`
regeneration, and a `verify.py` byte-identical round-trip check.

![ROM coverage map](docs/img/coverage-map.png)

## Reproducing it

```
# from this directory, with the toolkit checked out as a sibling and your own
# ROM copy dropped in:

python3 ../a7800-toolkit/tools/disasm.py "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78" -c annotations.json -o src
python3 ../a7800-toolkit/tools/verify.py "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78" -d src
# -> ROUND-TRIP PASSED
```

Add `--gaps` for a report of every byte reached as neither code nor a declared
block, `--check-gaps` to have each apparent call into one classified as real or
coincidental, and `--map` for a heatmap (needs Pillow).

## The split-screen patch

`patches/splitscreen.py` rearranges the display list into a two-viewport
layout -- player 2's view on top, the HUD moved to the centre as a divider,
player 1's road below, unmoved. It ships no cartridge data: it's a list of
addresses and the bytes to check for and replace, verified against your own
dump before anything is written.

```
python patches/splitscreen.py "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78" -o pp2-split.a78
```

Player 2's view is currently a *mirror* of player 1's road, not an independent
camera -- see "Phase 1" in `docs/FINDINGS.md` for what that buys for free
(geometry, colour, the stripe animation) and why it can't yet be smooth (the
real road's curve is injected scanline-by-scanline by a display interrupt,
which a mirror rendered elsewhere on screen can't borrow). The patch script's
own docstring has the zone-by-zone layout and the reasoning behind each edit.

## Recording a session

Live findings come from replaying a MAME input recording -- a deterministic
button-press log, not video, and not copyrighted content -- against a
PC/frame-tagged Lua probe. Recordings are committed here as they are made, so
the findings that cite them stay reproducible.

```
./"Record Session.command"        # play, Esc to stop -> next free run-NN.inp
./"Play Recording.command" run-01 # watch a recording play back
```

Probe runs go through MAME directly, and **`-skip_gameinfo` is not optional**:
without it MAME holds on its information screen waiting for a keypress, so an
unattended or backgrounded probe simply sits there until somebody notices and
presses a button. The launcher scripts above already pass it; anything invoked
by hand needs it too.

```
mame a7800 -rompath ../bios -cart "<rom>" -skip_gameinfo \
     -input_directory "$(pwd)" -playback run-02.inp \
     -autoboot_script tools/<probe>.lua \
     -window -nomax -nothrottle -sound none -video soft
```

## Layout

| | |
|---|---|
| `annotations.json` | The recipe. Feed it to `disasm.py` to get the listing. |
| `docs/FINDINGS.md` | The narrative -- read this first. |
| `tools/` | This project's own probe scripts. |
| `patches/` | Byte-patch scripts that build a modified ROM from your own dump; see "The split-screen patch" above. |
| `Play Recording.command`, `Record Session.command` | Double-click launchers (macOS + MAME on `PATH`). |

Not committed (see `.gitignore`): the ROM, the generated `src/rom.asm` and
`build/`, and regeneratable probe output.
