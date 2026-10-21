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

## Pole Position II VS: the two-player split-screen build

`patches/splitscreen.py` builds a two-player version of the game from your own
retail dump: player 2 on the top half of the screen, player 1 on the bottom,
the HUD between them. Each player has their own car, camera, laps, clock,
score and result; they qualify, race, collide and are tallied separately, and
the title logo reads *POLE POSITION VS*. The build is a 48K cartridge
(`$4000-$FFFF`); the retail game is 32K. A second form, a 2x48K BankSet
cartridge, adds player 2's start/finish line and smoother curves
([below](#the-bankset-build)).

[`docs/SPLITSCREEN.md`](docs/SPLITSCREEN.md) describes the current design:
screen layout, what runs when, RAM and ROM maps, features and known limits.
`docs/FINDINGS.md` is how it got there (checkpoints 1-90, then the BankSet
work).

**Controls.** Player 1 as stock. Player 2 uses a two-button 7800 controller
in port 2 with the same scheme: the buttons are gas and brake, left and right
steer, up and down shift gear.

### Getting it: the bundle

[`dist/pp2-vs.abp`](dist/pp2-vs.abp) turns your own retail dump into the VS
cartridge. It has two options:

- **`vs-split`**: the two-player build. It grows the cartridge from 32K to 48K
  and sets the `.a78` header's ROM size to match.
- **`vs-hires-car`**: the same build with KevinMos3 and Defender_2600's
  higher-detail car ([below](#a-higher-detail-car-sprite-credit-kevinmos3-and-defender_2600)).
  It brings `vs-split` along.

```
python ../a7800-toolkit/tools/patchset.py apply dist/pp2-vs.abp \
    --rom "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78" \
    --with vs-split --out pp2-vs.a78
```

Use `--with vs-hires-car` for the higher-detail car. It can also go on top of
a cartridge that already has `vs-split`. `patchset.py check` says which
options a cartridge carries. The result is signed for real hardware, and is
byte-identical to the generator's `--build --sign` below. It needs
[a7800-toolkit](https://github.com/Miasmark/a7800-toolkit)'s `patchset.py`,
`bps.py` and `sign7800.py`, at commit `f449428` or later (bundles that grow
the cartridge, and options built on each other), cloned beside this
repository as `../a7800-toolkit`.

Where the bundle keeps retail bytes in place, it stores only their CRC32s.
What it does carry:
- this project's code;
- the graphics it generates from the retail pixels: sheared copies of the
  road slices (grey road with a border each side), player 2's highlights
  and the VS logo edit. A copy's unshifted rows match the retail's, about
  2K in all;
- the car redraw's 159 bytes, with credit.

Rebuilding a bundle gives the same file, byte for byte. With the toolkit at
`0be62ea`, `pp2-vs.abp` is SHA-256
`ef3c3e42b6f49a8d218f66cd9e77e198f21b03dc3f2b5462baba581661fb73fe` and
`pp2-graphics-hack.abp` is
`96585a15328115c5240009be3606d535ca99b5f625ef7d7be9cc11bf5f2f1b07`.

### Building it

You need:

1. **The retail NTSC dump**, 32,768-byte body, CRC32 `A85FB962`, SHA-256
   `b852432108a86d003c2c7d393455b5a52eafc474209a6e7e5ed11f99366b8d5e`, with
   or without its 128-byte `.a78` header. Put it beside this README named
   `Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78`, or point
   `PP2_ROM` at it. Any other file is refused before anything is written.
2. **Python 3** (built with 3.10; nothing outside the standard library).
3. **[a7800-toolkit](https://github.com/Miasmark/a7800-toolkit)**, cloned
   beside this repository as `../a7800-toolkit`: `asm.py` and `m6502.py` for
   every build, `sign7800.py` to sign, `patchset.py` and `bps.py` for
   `--bundle`. Verified at commit `e44dca9`; `--bundle` needs `ff816b1` or
   later (`patchset.bundle_from_images`). Set `PP2_TOOLKIT` to point at
   another `tools` directory.

Then, from this directory:

```
python patches/splitscreen.py --build -o pp2-vs.a78           # unsigned: MAME, recordings
python patches/splitscreen.py --build --sign -o pp2-vs.a78    # signed: real hardware
PP2_HIRES_CAR=1 python patches/splitscreen.py --build -o pp2-vs-hires.a78
PP2_BANKSET=1 python patches/splitscreen.py --build --sign -o pp2-vs-bankset.a78
python patches/splitscreen.py --bundle                        # rewrites dist/pp2-vs.abp
```

The build is deterministic and prints the result's SHA-256. From the headered
dump:

| | unsigned | signed |
|---|---|---|
| VS | `55c178608cf625b9614b8bd0627fd8d862432dc226855e0bea7f1eadb5d1e2d8` | `60927bd2c3897b310da750a8ebedd64b6472bdf6191080c3b764ea8ccbd47e31` |
| VS, higher-detail car | `cfac95a4e278f95728140cba32e2830b0770e1c6853c9266b5936a20697f7e6f` | `d705b2c945354731a9f83b9f5c8ff5853b864c8f93002ab0e65724ee0354c9b3` |
| VS BankSet | `2b8b72e546cb8325d8f53c088334ea959764e953130f4d968e8b5e446810febb` | `73bb5f8c5a89ad52858f7fb0fc7533558ffe74dc17ebd0c43fa0fa81aae013ae` |
| VS BankSet, higher-detail car | `3f04fbf5dc4b0fef45e05813fcd8ad8da875aab046644af4e212e3d45cab7faf` | `13a4ccd28fabcd53c26149f944855e0e0b37bfe1688de7baf3cb58db831512b6` |

(A headerless dump gives a headerless 49,152-byte image with the same body.)

Every edit is checked against the bytes it expects to find. The new graphics
(player 2's highlights, the sheared road slices, the VS) are generated from
your dump's own pixels at build time.

**Signed or unsigned.** A 7800's BIOS checks a signature at boot, and the
check's running time depends on the signature bytes themselves. Every `.inp`
recording here was made against an unsigned image, and a signed build plays
them back as a different race. Use the unsigned build for MAME and for
testing, the signed one (or the bundle's output) for a real console or flash
cart. The full account is in the generator's docstring.

**Switches.** `PP2_HIRES_CAR=1` builds in the higher-detail car;
`PP2_BANKSET=1` builds the BankSet form.
`PP2_NO_SMOOTH`, `PP2_NO_NEAR`, `PP2_NO_SPLIT`, `PP2_NO_OVL` and `PP2_NO_VS`
leave out one feature each; `PP2_P2PAL=n` recolours player 2's car. They and
the test hooks are listed in the generator's docstring.

### The BankSet build

`PP2_BANKSET=1` writes a 98,432-byte cartridge: a v3 `.a78` header (type
`$2000`, BankSet) and two 48K halves, the CPU's and MARIA's. The second half
gives the build the room the 48K one ran out of, and it goes to:

- **player 2's start/finish line**, drawn on player 2's own road (the 48K
  build has player 1's only);
- **smoother curves**: more road bands draw from pre-sheared copies, the
  nearest band included, with half-pixel slopes as well as whole ones;
- **a fix** for a sliver of kerb that wraps onto the left edge of player 2's
  view when it drives off the road to its left.

It needs a player that does BankSet: the openFPGA 7800 core, or the Atari
fork of MAME ([Miasmark/mame-Atari8bit7800](https://github.com/Miasmark/mame-Atari8bit7800)).
Stock MAME 0.287 doesn't. It is not yet confirmed on hardware, and there is
no bundle for it yet: build it with the generator. `docs/SPLITSCREEN.md`
("The BankSet build") summarises the design; `docs/FINDINGS.md` has the
measurements.

On the fork an unsigned build boots the 2600 bootstrap first; run it with
`-bios skip`. The committed recordings don't drive this build there.
`tools/probe-race-tickrate.lua` (scripted races) does; give it player 2's
addresses for this build: `QA=0094 P2C=49D2 P2P=498E` (the 48K build:
`2027`, `49D0`, `498C`).

### Checking a build

```
MAME=/path/to/mame tools/check-build.sh pp2-vs.a78
```

replays the committed recordings and scripted races against the build --
game health, player 2's display lists, the halving row search against the
original, a trap for any jump into data, and the race's tick rate under
load -- and prints what to compare (the expected values are in the script's
header). It takes a couple of minutes and needs a 7800 BIOS (`BIOS`, default
`../bios`). For the higher-detail build, run it with `PP2_HIRES_CAR=1` set.

Or through the toolkit's `regress.py`, which runs the same set from
`tools/check-build.json` and compares every verdict with a saved baseline:

```
python ../a7800-toolkit/tools/regress.py tools/check-build.json --var rom=good.a78 --save good.json
python ../a7800-toolkit/tools/regress.py tools/check-build.json --var rom=pp2-vs.a78 --against good.json
```

It exits 1 if anything changed, and gives verdict for verdict what the
script does.

## A higher-detail car sprite (credit: KevinMos3 and Defender_2600)

The car-sprite redraw here is **not this project's own work**: it is **"Pole
Position II Graphics Hack"** by **KevinMos3** and **Defender_2600**, published
on the AtariAge forums on 2014-04-12. All credit for the artwork is theirs.
This project only locates exactly which bytes their release changed, so the
redraw can be applied as an option, always with their names attached. Those
bytes are two sprite objects, confirmed live against the display list rather
than guessed from the diff, and two palette values.

It comes two ways:

- **On the retail game**: `patches/graphics_hack.py` /
  [`dist/pp2-graphics-hack.abp`](dist/pp2-graphics-hack.abp), option
  `hires-car`, exactly as they released it.

  ```
  python ../a7800-toolkit/tools/patchset.py apply dist/pp2-graphics-hack.abp \
      --rom "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78" \
      --with hires-car --out pp2-hires-car.a78
  ```

- **In VS**: `dist/pp2-vs.abp`, option `vs-hires-car`, or
  `PP2_HIRES_CAR=1`. The sprite bytes go in unchanged. The two palette
  values can't: in the retail game they sit in a scanline routine that VS no
  longer runs (it reclaimed that space for its own code), so VS sets the car
  palette itself, in the hack's blue and white. Player 1's car is theirs as
  released. Player 2's is the same car with gold highlights, so the two
  players are still told apart (next section).

The retail bundle does not go on a VS cartridge, and neither does VS go on a
cartridge that already has the retail redraw. `patchset.py` recognises either
and refuses, naming the palette bytes they both need. Use `vs-hires-car`
instead.

## Player 2's highlights (design credit: Defender_2600)

In the split-screen build, player 2's car carries highlights over its top
section, in both views, so it cannot be mistaken for player 1 or for a rival.
The look follows a mock-up by **Defender_2600** on AtariAge; the pixels are
generated from the car by `p2_overlay_art()` in `patches/splitscreen.py`.
On the stock gold car they are blue and white. On the higher-detail car,
which is blue and white itself, they are gold: the same contrast the other
way round, in the yellow rival's palette. Rivals are single-colour cars
(yellow, white or blue), so neither combination is one of theirs. On the
redrawn upright frame they follow that frame's own details: its light wing
stripe becomes the bar, and its wing tips and sidepods turn gold.
`PP2_NO_OVL=1` builds without them.

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
| `tools/` | This project's own probe scripts; each says what it does in its first lines. |
| `docs/SPLITSCREEN.md` | The VS build's current design: layout, timing, RAM and ROM maps. |
| `patches/` | Scripts that build a modified ROM from your own dump; see "Pole Position II VS" above. |
| `dist/` | The `.abp` bundles: `pp2-vs.abp` (the VS build, with or without the higher-detail car) and `pp2-graphics-hack.abp` (the higher-detail car on the retail game). Retail bytes appear as CRC32s; see "Getting it: the bundle". |
| `tools/check-build.sh` | The regression set for a VS build (see "Checking a build"). |
| `Play Recording.command`, `Record Session.command` | Double-click launchers (macOS + MAME on `PATH`). |

Not committed (see `.gitignore`): the ROM, the generated `src/rom.asm` and
`build/`, and regeneratable probe output.
