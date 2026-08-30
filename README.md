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
what's been confirmed live in MAME, what's still just a hint, and what was
actively distrusted rather than assumed. **This is day one**, so read it as a
starting map: most of the cartridge is currently one very large unexplained
block.

Working discipline, same as the sibling projects: every claim about what a byte
range does should be checked live before it's trusted, not pattern-matched from
a probe script carried over from a previous project. Every `annotations.json`
change is followed by JSON validation, `disasm.py` regeneration, and a
`verify.py` byte-identical round-trip check.

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
| `Play Recording.command`, `Record Session.command` | Double-click launchers (macOS + MAME on `PATH`). |

Not committed (see `.gitignore`): the ROM, the generated `src/rom.asm` and
`build/`, and regeneratable probe output.
