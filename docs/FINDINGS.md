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

Tracing from the three hardware vectors reaches **16.8%** of the ROM (5,494 of
32,768 bytes, 2,617 instructions), leaving 27,274 bytes in 26 gaps.

That is the lowest opening figure of any project in this series -- Ms. Pac-Man
reached 52.4%, Asteroids 41.9% -- and one gap accounts for most of it:

    $8000-$C1A4   16,805 bytes   over half the cartridge, contiguous

A block that size, contiguous, at the bottom of the address space, in a game
built around a scrolling road and a horizon, is almost certainly graphics and
track data. That is a hypothesis, not a finding: nothing has been rendered or
traced yet.

## No missed code, and two RAM vectors

`disasm.py --check-gaps` classifies every apparent `JSR`/`JMP` whose operand
lands in a gap. Here there are **141 candidates and not one is real** -- every
one is the `$20`/`$4C`/`$6C` byte occurring inside data or mid-instruction. So
no traced code branches into any gap.

That is not the same as "the gaps hold no code", because of these:

    rom:D26A   JMP ($0040)
    rom:EC06   JMP ($00FD)

Two indirect jumps through RAM. Their targets cannot be known statically, and
in a sibling project exactly this construct hid a handler from the tracer for
a long time. Resolving them -- with a live probe, or a `ram_vectors` entry once
the values are known -- is the first job.

## What's open

Everything. Specifically, and in the order they look worth doing:

* The two RAM vectors above.
* The 16,805-byte block at `$8000`: render it, and find what points at it.
* The remaining 25 gaps, none larger than 3,455 bytes.
* The game is nearly silent without input (a passive MAME capture yields one
  row; driving the fire button yields 50 in twenty seconds), so the audio
  tooling will contribute little here compared with the sound-led projects.
