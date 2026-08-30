# Pole Position II -- findings so far

Day one. Almost everything below is a measurement or an explicitly-flagged
hypothesis, and the two are kept distinct: where something is read from the
code but never watched running, it says so.

## The cartridge

| | |
|---|---|
| ROM | `Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78` |
| Size | 32,896 bytes (128-byte header + 32,768) |
| Mapper | linear 32K, no banking, mapped `$8000-$FFFF` |
| Vectors | NMI `$EBEF`, RESET `$D205`, IRQ `$EC0E` |

Linear, so every address is unambiguous and the cross-bank reference
resolution that caused repeated errors in the banked projects simply does not
apply. This is the second 32K linear cartridge in the series after Galaga.

## Day one coverage

Tracing from the three hardware vectors alone reaches **16.8%** of the ROM
(5,494 of 32,768 bytes), leaving 27,274 bytes in 26 gaps -- the lowest opening
figure of any project in this series, where Ms. Pac-Man reached 52.4% and
Asteroids 41.9%. One gap accounts for most of it:

    $8000-$C1A4   16,805 bytes   over half the cartridge, contiguous

A block that size at the bottom of the map, in a game built around a scrolling
road and a horizon, is very likely graphics and track data. That is a
hypothesis. Nothing has been rendered or traced yet.

**Resolving two indirect jumps took it to 27.5%** -- see below.

## No missed code, and two RAM vectors

`disasm.py --check-gaps` classifies every apparent `JSR`/`JMP` whose operand
lands in a gap. On the day-one annotations there were **141 candidates and not
one real**: every one is a `$20`/`$4C`/`$6C` byte occurring inside data or in
the middle of a longer instruction. No traced code branches into any gap.

What it did flag was two indirect jumps through RAM, whose targets no static
scan can know:

    rom:D26A   JMP ($0040)
    rom:EC06   JMP ($00FD)

The toolkit's `ram_vectors` scan finds neither -- it looks for an immediate
load paired with a store, and these are not built that way. So they were
resolved live, against `run-01`, by tracing the emulator and reading the
instruction that actually followed each jump.

    JMP ($0040)  ->  $D26D, $D3A4
    JMP ($00FD)  ->  $EC10, $EC57, $EC76, $EC87, $EC8C, $ED30, $ED4A, $ED4F

Both land inside gaps the trace had reported: `$D26D-$D477` and `$EC0F-$F170`.

## The display-interrupt handler table

Reading the code around the second vector explains it, and gives more than the
recording did. The NMI entry:

    $EBEF   STA WSYNC
            ...save A/X/Y...
            LDA ram_009C
            BMI sub_EC09
            LDX ram_00FF          ; a zone index
            LDA dat_A48A,X        ; handler address, low
            STA ram_00FD
            LDA dat_A496,X        ; handler address, high
            STA ram_00FE
            JMP (ram_00FD)

Two parallel tables twelve bytes apart, indexed by `ram_00FF`, so **twelve
display-interrupt handlers**, installed one per zone. Read out of the ROM:

    index  0 -> $2456     RAM -- copied there at run time, not statically reachable
    index  1 -> $EC10     index  7 -> $ECA1
    index  2 -> $EC57     index  8 -> $ED2B
    index  3 -> $EC76     index  9 -> $ED30
    index  4 -> $EC87     index 10 -> $ED4A
    index  5 -> $EC9E     index 11 -> $ED4F
    index  6 -> $EC8C

The recording exercised eight of the eleven ROM handlers; the table gives all
of them, which is why it was worth reading the mechanism rather than stopping
at what the trace happened to visit. Those eleven are now entries, and the
table is declared as `dat_DliHandlerTable`.

**The table sits at `$A48A`, inside the 16,805-byte block** -- the first
structure identified in it, and evidence that the block is not purely graphics.

Coverage after all this: **27.5%** (9,014 bytes, 4,230 instructions), 23,730
bytes still in 24 gaps. Round-trip byte-identical throughout.

## The chain, and an entry nothing selects

Each handler installs the index for the next one, which is what makes it a
chain rather than a table lookup. Every site that writes `ram_00FF`:

    $D890  #$01     $EC78  #$04     $ED2B  #$09  (via $EC78)
    $D8D4  #$07     $EC9A  #$01     $ED30  #$0A  (guarded, see below)
    $EC52  #$02     $ECA6  #$08     $F169  #$07
    $EC5F  #$03

So indices **1, 2, 3, 4, 7, 8, 9 and 10** are installed. `$ED30` is the only
conditional one: it loads `$0A`, and only stores it when `ram_0048` is in
`4..7`, otherwise branching away -- a range check on some game-state value.

**Nothing installs index 0.** No path found writes it, and across the whole of
`run-01` the address it points at (`$2456`) is never executed. Two readings,
and the evidence does not separate them: the entry is dead, or it belongs to a
mode this recording never enters. It is written down as unselected rather than
as dead, because "no path found" is a statement about the search.

That `$2456` is in RAM is itself worth noting. The BIOS copies into `$2300`
and `$2400` during startup (`$FB2F`/`$FB35`, 256 iterations each -- BIOS code,
not the cartridge's: `$FB1C` onward in this ROM is all `$FF` padding). So
whatever index 0 would jump to is either installed by the game later, or is
BIOS leftovers.

## What's open

* The remaining 23,730 bytes, dominated by `$8000-$C1A4` less the handler
  table now carved out of it. Render it; find what points into it.
* The RAM handler at `$2456`: nothing selects index 0 and nothing writes
  that address during `run-01`. Settle whether any mode does.
* `run-01` (17,115 frames) is the only recording: the "Test" track, a rounded
  rectangle, driven to completion. It includes a crash and a stretch where a
  system dialog took the controls, so input during that window is not the
  player's and should not be read as intent.
* The game is nearly silent without input, so the audio tooling that dominated
  the sibling projects will contribute little here.
