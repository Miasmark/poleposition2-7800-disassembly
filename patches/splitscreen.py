#!/usr/bin/env python3
"""
Pole Position II split-screen: build a patched cartridge and an .abp bundle.

    python patches/splitscreen.py --list
    python patches/splitscreen.py --build -o pp2-split.a78     (playable, for testing)
    python patches/splitscreen.py --bundle                     (writes dist/pp2-splitscreen.abp)

Every edit is checked against the bytes it expects to find, so building
against the wrong dump fails by name instead of producing a corrupt ROM.

## What this is

Rearranges the display list into a two-viewport layout -- player 2's view on
top, the HUD relocated to the centre as a divider, player 1's road below,
untouched:

    zone  0        16 lines   blank top margin        DLI index 7
    zone  1         4         blank gap
    zones 2-14     78         player 2's view -- all thirteen road bands
                                                      DLI index 8 on zone 7,
                                                      index 9 on zone 14
    zones 15-17    21         HUD, three rows -- the centre divider
                                                      DLI index 10 on zone 17
    zone  18       10         horizon decoration ($18FA, stock)
    zone  19       10         decoration              DLI index 11
    zones 20-32    78         player 1's road (unmoved)
    zones 33-34    32         blank

Zones 0-19 total exactly 139 lines in every state the divider can be in --
HUD showing, start light showing, or per-lap banner showing. They have to:
a mismatch there shifts everything below the divider for the mismatch's
duration, which is what used to make the whole screen bump up for a lap
message and drop back when it cleared.

Player 2's view is currently a *mirror*: its bands point at the same RAM
sub-lists player 1's road uses, so it tracks the same curve and the same
stripe animation for free, at the cost of stair-stepping where the real road
is smooth (the smoothness is injected scanline-by-scanline by a display
interrupt, which a view rendered ~80 scanlines earlier cannot borrow). See
"Phase 1" in docs/FINDINGS.md for the full trail -- including two things this
patch had to fix that are not obvious from the zone table alone: CTRL's read
mode has to follow the layout (character mode for the HUD, the road's mode
everywhere else), and BACKGRND has to carry the road's ground colour into
player 2's view or every transparent pixel in the road graphics shows sky.

It mirrors all thirteen of player 1's road zones, so the top view is the
same 78 lines as the road below it. Earlier versions managed only ten, and
two separate rounds of investigation blamed that on the wrong thing -- first
on which zone the mirror sat next to, then on a supposed ten-zone ceiling.
Both were wrong, and docs/FINDINGS.md keeps them on the record next to what
actually turned out to be true: the start light was erasing display-interrupt
bits, and the interrupts' *positions*, not the mirror's size, are what the
6502's frame budget is sensitive to.

## Why .abp and not a single BPS or a bare byte-patcher

A BPS is a delta between two *whole* files, with a CRC32 of the whole source
and the whole target -- exactly right for "here is my hack" and wrong for
"here is a set of options, and here is how to check whether a dump can even
take them." The .abp format (`docs/patchset-format.md` in the toolkit) checks
a named byte range at a time instead, which is what lets an option apply
cleanly to a dump that already has *another* option on it, and what lets
`tools/patchset.py list`/`check`/`apply` reason about this patch the same way
they already reason about Karateka's.

It also means this file ships less of the ROM than a naive "expected bytes"
check would: a section's identity in the bundle is a CRC32 of its pre-image,
never the pre-image itself. The one exception is real: `bps.create()` below
necessarily encodes the *new* bytes an edit writes, because those bytes are
this project's own work, not a copy of anything.

## HudReassert: the one piece of new code this patch needs

Everything above is a pure data edit -- existing bytes, replaced. The HUD's
divider (zones 12-14) is different: those three zones are not in the boot
template at all. They are rewritten at *run time*, from two ROM tables
(`dat_A6BB`, `dat_A6CD`), by the stock routines that drive the start light
and the "POLE POSITION! ####" qualifying banner -- whichever ran last wins,
and both happen during a normal race. That sharing is stock behaviour, not
something this patch introduced; the ORIGINAL always-on HUD lives at zones
2/4/6, untouched by any of it. This patch's mirror needs zones 2-11 for the
ten road bands, which is where that original HUD used to live, so the HUD
has to move to the one place already wired to be a shared, overwritable
divider: zones 12-14.

Sharing it, though, means something has to give the HUD back once the light
or the banner is done showing -- stock never needs to, because stock's real
HUD lives elsewhere. Nothing else ever will on its own (confirmed live: the
light's and banner's zone-selector writes are one-shot, and once the second
light finishes, zones 12-14 sit on its leftover graphic for the rest of the
race). So a tiny new routine (`hud_reassert_src` below) writes the HUD's
three zone-selectors back in -- hooked in at *two* places, not one, which
took counting to find: the obvious spot (rom:D848, in sub_D83D, reached
whenever driving resumes after a per-lap event) turned out to only be one
of two places the game enters normal driving from. The other, reached right
as the start light itself finishes, is a completely different routine
(rom:CBEB, a periodic state check unrelated to sub_D83D). Hooking only the
first left the HUD not returning after the start light specifically --
confirmed by having the new code count its own calls into a spare RAM byte
across a full recording and comparing against exactly when zones 12-14
changed. See docs/FINDINGS.md, "The mirror was missing the car, and the divider was missing the light".
dat_A6BB and dat_A6CD themselves are NOT touched -- the light and the
banner still display exactly as they always have; this only adds the "and
now put the HUD back" step stock never needed.

An earlier version of this patch instead overwrote dat_A6BB/dat_A6CD's own
bytes to force the HUD into zones 12-14 permanently -- simpler, no new code,
but it meant the light and the banner could never display again. That
tradeoff turned out not to be worth it once asked to reconsider it; this is
the fix. A second earlier version fixed that by also *relocating* zones
12-14's role to zones 15-17 and moving the pair of DLI (display-interrupt)
bits that switch character mode on and off to match -- which renders fine,
but measurably desyncs an existing recording (see docs/FINDINGS.md, "The
mirror was missing the car, and the divider was missing the light"): moving
either of those two specific DLI bits shifts something in the frame's
timing that a recorded race is
sensitive to, even though the two zones the bits move *to* render correctly
in isolation. HudReassert exists because it gets the same visible behaviour
(HUD normally, light and banner over it at their moments) without moving
either bit.

Two more mistakes surfaced getting the CBEB hook right, both caught live
rather than assumed correct: the first version called the shared HudWrite
subroutine and then reloaded `A` with `#$03` *before* the call instead of
after, so the value HudWrite left in `A` (a HUD byte, not 3) is what ended
up in `ram_009D` -- a wrong-but-plausible race state that happened to look
like a second start-light sequence on screen, which is what gave it away.
Fixed by writing first and reloading `#$03` right before the jump back.
The second: even fixed, a JSR to the shared subroutine plus its loop
was enough alone to desync the recording from that point on -- rom:CBEB has
far less cycle budget to spare than rom:D848 did. `_unrolled_hud_write()`
replaces the loop with nine straight `LDA #imm`/`STA abs` pairs and drops
the JSR, for this one call site only; rom:D848 still uses the shared,
looped HudWrite, since that one was never the problem.

## Signing this and testing against a recording are two different needs

`--build` does not sign by default, and that is deliberate, not an oversight.

An NTSC 7800's BIOS checks a cartridge signature at boot, and the check's
*running time* turns out to depend on the signature bytes' own bit pattern --
not on whether the check ultimately passes. Measured directly: a build with
this patch's edits but the ORIGINAL, now cryptographically-invalid signature
(untouched, since nothing here writes near it) replays `run-01.inp` and lands
on exactly the expected score, gear and speed at frame 8000. The same build
freshly re-signed -- a real, valid signature -- desyncs from the very same
recording by frame 8000, landing on a different score entirely. Zeroing the
signature block instead gives a *third*, still different, result. All three
are individually deterministic; they differ from each other only in the
120 signature bytes.

So: unsigned is what every recording in this repo was made against, and what
another one should be made against if you need one for a new build. `--sign`
(or `tools/patchset.py apply`, which signs automatically via the bundle's
`region` field) is what a copy meant for real hardware, or a fresh MAME
session with no recording riding on it, actually needs. Conflating the two --
signing a build and then testing it against an existing recording -- produces
a playable, plausible-looking race that is quietly not the one being asked
for, which is a worse failure mode than an obvious crash.
"""
import argparse
import hashlib
import io
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLKIT_TOOLS = os.path.join(ROOT, "..", "a7800-toolkit-local", "tools")
sys.path.insert(0, TOOLKIT_TOOLS)

HDR = 128
BASE = 0x8000                    # linear, unbanked cart: $8000-$FFFF is all of it
ROM_SIZE = 32768

ROM_NAME = "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"
SOURCES = [
    os.environ.get("PP2_ROM", ""),
    os.path.join(ROOT, ROM_NAME),
    os.path.expanduser(os.path.join("~", "Documents", "Atari 7800",
                                    "Rom Library", ROM_NAME)),
]
OUTDIR = os.environ.get("PP2_OUT", ROOT)
DISTDIR = os.path.join(ROOT, "dist")


class Patcher(object):
    """Byte edits against a headerless ROM, each checked before it is made."""

    def __init__(self, rom, base=BASE):
        self.rom = bytearray(rom)
        self.base = base
        self.writes = []          # what this patcher wrote, in order

    def off(self, addr):
        return addr - self.base

    def peek(self, addr, n):
        o = self.off(addr)
        return bytes(self.rom[o:o + n])

    def put(self, addr, data, expect=None):
        o = self.off(addr)
        if expect is not None:
            found = bytes(self.rom[o:o + len(expect)])
            if found != bytes(expect):
                raise SystemExit(
                    "at $%04X expected %s but found %s -- this is not the ROM "
                    "this patch was written for"
                    % (addr, bytes(expect).hex(), found.hex()))
        self.rom[o:o + len(data)] = bytes(data)
        self.writes.append((addr, bytes(data)))
        return self


# ---------------------------------------------------------------- the fix

ZONE_TABLE = 0xBC7E               # boot-time display-list template, copied to $2200 by sub_F171


def zone(n):
    return ZONE_TABLE + n * 3


# Road band sub-lists in RAM, far-to-near, for all thirteen of player 1's
# own bands (real zones 20-32). The curve pipeline (docs/FINDINGS.md, "the
# last piece") rewrites these every frame, which is why pointing a second
# view at them tracks the road's curve at no extra cost.
ALL_ROAD_BANDS = [0x2300, 0x2326, 0x234C, 0x2372, 0x2398, 0x23BE, 0x2400,
                  0x2426, 0x244C, 0x246E, 0x2490, 0x24B2, 0x24D4]

# All thirteen get mirrored, so player 2's view is the same 78 lines as
# player 1's road rather than a shortened 60. Earlier versions of this patch
# could only manage ten, and three rounds of investigation blamed that on the
# wrong thing twice (docs/FINDINGS.md, "Solved: the start light was erasing
# display-interrupt bits" supersedes both). The real constraint turned out to
# have nothing to do with how many zones the mirror uses -- see DLI_ZONES.
ROAD_BANDS = ALL_ROAD_BANDS

# Zones carrying a display-interrupt bit, and the one rule that governs where
# they may go: **no DLI bit may sit on a zone the start light or the banner
# writes to.** Those routines (sub_D80D, sub_DA7C) copy nine bytes -- three
# whole zone selectors, flags byte included -- to wherever `STA ram_2224,X`
# points. Bit 7 of a flags byte *is* the display-interrupt bit, so a bit
# inside that window is simply erased the first time the light appears, that
# link of the chain stops firing, and everything downstream of it (the next
# frame's controller read included) breaks.
#
# There are two ways out of that, and only one of them is cheap. Parking the
# bit outside the window works -- an earlier version put index 10 on a
# one-line zone 18 -- but it costs zone 18's stock ten lines of $18FA, forces
# index 8 down to zone 1 to rebalance, and the resulting DLI spacing starves
# the 6502: speed falls behind stock from frame ~774 of run-02, the deficit
# compounds, and the race ends early (docs/FINDINGS.md, "The mirror was free;
# the interrupt positions were not"). The cheap way is to stop treating the
# overwrite as destructive and make the templates *carry* the bit: set bit 7
# on the third selector of dat_A6BB and dat_A6CD and the light and banner
# preserve index 10 instead of erasing it. It then stays on zone 17, the end
# of the divider group, which is the same shape stock uses -- and zone 18
# keeps its stock content untouched.
DLI_ZONES = {0, 7, 14, 17, 19}

# Where the light and banner's nine bytes land, as a zone number and as the
# low byte of the `STA ram_2224,X` operand that aims them. Zone 15 = $2200 +
# 15*3 = $222D. The three zones from here are the divider, and must stay
# clear of DLI_ZONES above.
DIVIDER_ZONE = 15
DIVIDER_ADDR = 0x2200 + DIVIDER_ZONE * 3

# The three-row HUD, written into the divider by HudReassert once normal
# driving begins, sharing those zones with the start light and the
# "POLE POSITION!" banner exactly as stock already did at its own zones 12-14.
# The third selector's flags byte is $86, not $06: seven lines *plus* the
# DLI bit for index 10. Every writer of these three zones -- this table, the
# light's dat_A6CD and the banner's dat_A6BB -- has to agree on that bit, or
# whichever one runs last silently drops the interrupt.
HUD_ROWS = [0x06, 0x1D, 0x1C, 0x06, 0x1D, 0x28, 0x86, 0x1D, 0x34]

# HudReassert lives here: $F3FF-$FF7E (2,945 bytes) is a run of untouched $FF
# filler, confirmed via the toolkit's own --gaps report (disasm.py) and by
# entropy (a real table wouldn't be one repeated byte for that long) -- well
# clear of $FF80, where the cartridge signature starts. This is the first
# code this project has ever added rather than edited in place, so it gets a
# fixed, checked address rather than the bundle's dynamic float search:
# there is exactly one of it, nothing else competes for the space, and
# `expect=` on the write already proves the space is genuinely free on the
# ROM being patched -- the property a float's auto-placement exists to give
# when several options might collide over the same room.
HUD_REASSERT_ADDR = 0xF900
SOUNDSTOP = 0xDED6


def hud_reassert_src(addr):
    """Four routines sharing one write.

    HudWrite is the 9-byte copy into the divider (DIVIDER_ADDR). HudReassert
    wraps it for rom:D848, where it replaces `LDA #$0B / JSR SoundStop` at
    the end of sub_D83D -- the "resume driving after a per-lap event" path
    (state $09 -> $03) -- and still makes that same SoundStop call itself
    afterward, A restored to $0B first.

    StartDriveHud wraps it (inlined, not a call -- see `_unrolled_hud_write`)
    for rom:CBEB, where it replaces `LDA #$03 / BNE L_CBF1` -- state $11 ->
    $03, reached from a periodic ram_00A2/ram_00A3-gated state check
    unrelated to sub_D83D. This is normal driving's *other* entry point;
    hooking only rom:D848 left the HUD not returning after the start light.

    QualDriveHud does the same for rom:CBE3 (`CMP #$10 / BEQ L_CBEF`), the
    third and last entry into normal driving -- qualifying's own, never
    revisited afterward (qualifying just stays in state $02 until it ends),
    which is why the divider previously never showed anything but the start
    light for all of qualifying. It shares tight quarters with the rom:CBEB
    hook above (see the comment at its call site in fix_mirror_split for
    why it hooks one instruction earlier than the other two), which is also
    why it reproduces a comparison rather than just a state store.

    ZoneDividerRestore and DividerPaletteOnly are different in kind: not a
    state-machine hook but a replacement for the two paths DLI_ED30 (zone
    11's own interrupt) can take. Stock's DLI_ED30 already has to decide
    between them -- CTRL read mode 3 for the divider's own text (`JMP
    sub_EC67` at rom:ED47) *unless* ram_009D is $4-$7 (the start light is
    showing, which needs mode 0's direct graphics, not character mode), in
    which case it stays mode 0 (`STA ram_00FF / JMP sub_EC09` at rom:ED42).
    Neither path ever touched palette -- stock never needed either to,
    since in stock the whole zones-1-19 span uses one shared palette that
    DLI_ECA1 sets once, appropriate for banner, HUD and light alike. This
    patch's mirror repoints that same palette at the road's colours instead
    (below), which the divider inherits too since nothing resets it on
    either path -- confirmed live (screenshot comparison against the
    unpatched ROM at the same frames caught the text-and-background case;
    a second comparison, specifically at a frame where the light is showing,
    caught that the mode-0 path needed the identical fix -- an easy one to
    miss, since it only shows up while the light itself is on screen).
    ZoneDividerRestore handles the mode-3 path (reproducing sub_EC67's mode
    switch first, so results-screen callers elsewhere, which still call
    sub_EC67 directly, are untouched); DividerPaletteOnly handles the mode-0
    path (reproducing only its `STA ram_00FF`, since that path's whole point
    is *not* switching mode). Both then fall into the same palette/BACKGRND
    restore before jumping back to $EC09."""
    return [
        ".org $%04X" % addr,
        "SoundStop = $%04X" % SOUNDSTOP,
        "WSYNC = $0024", "CTRL = $003C", "BACKGRND = $0020",
        "P0C1 = $0021", "P0C2 = $0022", "P0C3 = $0023",
        "P1C1 = $0025", "P1C2 = $0026", "P1C3 = $0027",
        "P4C3 = $0033", "P5C3 = $0037",
        "HudWrite:",
        "    LDX #$08",
        "Loop:",
        "    LDA HudTriplet,X",
        "    STA $%04X,X" % DIVIDER_ADDR,
        "    DEX",
        "    BPL Loop",
        "    RTS",
        "HudReassert:",
        "    JSR HudWrite",
        "    LDA #$0B",
        "    JSR SoundStop",
        "    RTS",
        "StartDriveHud:",
    ] + _unrolled_hud_write() + [
        "    LDA #$03",
        "    JMP $CBF1",
        "QualDriveHud:",
        "    CMP #$10",
        "    BNE QualDriveSkip",
        "    LDA #$02",
        "    STA $009D",
    ] + _unrolled_hud_write() + [
        "    JMP $CC08",
        "QualDriveSkip:",
        "    JMP $CBE7",
        "DividerPaletteOnly:",
        "    STA $00FF",
        "    JMP PaletteRestore",
        "ZoneDividerRestore:",
        "    STA $00FF",
        "    LDA $005F",
        "    ORA #$03",
        "    STA WSYNC",
        "    STA $005F",
        "    STA CTRL",
        "PaletteRestore:",
        "    LDA #$80",
        "    STA P0C3",
        "    STA P1C3",
        "    STA P4C3",
        "    STA P5C3",
        "    LDA #$38",
        "    STA P0C1",
        "    LDA #$3C",
        "    STA P0C2",
        "    LDA #$28",
        "    STA P1C2",
        "    LDA #$24",
        "    STA P1C1",
        "    LDA #$89",
        "    STA BACKGRND",
        "    JMP $EC09",
        "HudTriplet:",
        "    .byte $%02X,$%02X,$%02X,$%02X,$%02X,$%02X,$%02X,$%02X,$%02X"
        % tuple(HUD_ROWS),
    ]


def _unrolled_hud_write():
    """StartDriveHud's write, inlined rather than a JSR to HudWrite: rom:CBEB
    (docs/FINDINGS.md, "The mirror was missing the car, and the divider was missing the light") turned out
    to have far less cycle budget to spare than rom:D848 -- the loop-based
    write plus a JSR/RTS round trip was enough alone to desync a recording,
    confirmed live the same way the signature-timing bug was (a recording
    sensitive to a frame's exact cycle count, not merely to what the frame
    displays). Nine straight LDA #imm/STA abs pairs, no loop, no call."""
    lines = []
    for i, b in enumerate(HUD_ROWS):
        lines.append("    LDA #$%02X" % b)
        lines.append("    STA $%04X" % (DIVIDER_ADDR + i))
    return lines


def _assemble(lines):
    """Assemble `lines`; return (code, symbols) -- symbols is the label ->
    address table the assembler built while resolving it, so a caller that
    needs to JSR to one of several labels in the same blob (HudReassert
    below has three) doesn't have to hand-compute offsets."""
    import asm
    a = asm.Assembler()
    code = bytes(a.assemble(lines))
    return code, dict(a.sym)


# Stock boot-template zone selectors, zones 1-18, so every edit below can
# state what it expects to find without repeating it inline.
STOCK_ZONES = {
    1:  [0x09, 0x24, 0xF6], 2:  [0x06, 0x1D, 0x1C], 3:  [0x02, 0x24, 0xF6],
    4:  [0x06, 0x1D, 0x28], 5:  [0x02, 0x24, 0xF6], 6:  [0x06, 0x1D, 0x34],
    7:  [0x82, 0x24, 0xF6], 8:  [0x07, 0x22, 0xC7], 9:  [0x07, 0x22, 0xD1],
    10: [0x07, 0x22, 0xDB], 11: [0x82, 0x24, 0xF6], 12: [0x06, 0x24, 0xF6],
    13: [0x02, 0x24, 0xF6], 14: [0x06, 0x24, 0xF6], 15: [0x82, 0x24, 0xF6],
    16: [0x07, 0x22, 0xE1], 17: [0x07, 0x22, 0xEB], 18: [0x09, 0x18, 0xFA],
}


def put_zone(p, z, lines, dl):
    """One zone selector: line count, DL address, DLI bit from DLI_ZONES."""
    flags = (lines - 1) | (0x80 if z in DLI_ZONES else 0x00)
    p.put(zone(z), [flags, dl >> 8, dl & 0xFF], expect=STOCK_ZONES[z])


def fix_mirror_split(p):
    """Give player 2's view all thirteen road bands across zones 2-14; put
    the HUD divider at zones 15-17 where the start light and banner are
    retargeted to draw; bring the HUD back there once driving begins.

    Ported from the hand-verified edits built up over several live sessions
    (docs/FINDINGS.md, "Phase 1" onward). One piece *is* new code --
    HudReassert -- and the module docstring explains what forced that.
    """
    # -- player 2's view: a gap, then all thirteen bands across zones 2..14 --
    # Thirteen, not ten, so the top view is the same 78 lines as the road
    # below it. What used to cap this at ten had nothing to do with the
    # mirror at all -- see DLI_ZONES above and docs/FINDINGS.md, "Solved:
    # the start light was erasing display-interrupt bits".
    put_zone(p, 1, 4, 0x24F6)
    for i, dl in enumerate(ROAD_BANDS):
        put_zone(p, 2 + i, 6, dl)

    # -- the divider: zones 15-17, three HUD rows ----------------------------
    for i in range(3):
        put_zone(p, DIVIDER_ZONE + i, 7,
                 (HUD_ROWS[i * 3 + 1] << 8) | HUD_ROWS[i * 3 + 2])

    # Zone 18 is deliberately absent from this function: it keeps its stock
    # ten lines of $18FA. An earlier version spent it as a one-line perch for
    # index 10; the templates carry that bit now, so it isn't needed.

    # -- aim the light and banner at the new divider -------------------------
    # Both routines end with `STA ram_2224,X`, hardcoded at zone 12 -- which
    # is a mirror band now. One operand byte each sends them to zone 15
    # instead, where the HUD divider actually lives.
    p.put(0xD81B, [DIVIDER_ADDR & 0xFF], expect=[0x24])   # sub_D80D, the banner
    p.put(0xDA92, [DIVIDER_ADDR & 0xFF], expect=[0x24])   # sub_DA7C, the light

    # -- the divider's own three writers need to agree on a total ------------
    # HudReassert/StartDriveHud/QualDriveHud all write 7+7+7=21 lines across
    # zones 12-14. The stock light and banner templates don't match that --
    # 8+8+1=17 and 7+3+7=17 -- so every swap between "HUD showing" and
    # "light or banner showing" changed how many scanlines MARIA processed
    # before the road, visibly shifting the whole screen below the divider
    # for the swap's duration (confirmed live: it bumps up when a per-lap
    # message appears, and back down when it clears). Both edits below are
    # to a *blank filler zone's line count only* -- not the address, not the
    # visible content -- so the light and banner still show exactly the
    # graphics they always have, just with four more scanlines of the same
    # blank padding they already had some of.
    p.put(0xA6BE, [0x06], expect=[0x02])   # dat_A6BB's blank middle slot: 3 lines -> 7
    p.put(0xA6D3, [0x04], expect=[0x00])   # dat_A6CD's blank last slot:   1 line  -> 5

    # -- and both templates must preserve index 10 ---------------------------
    # Bit 7 on each template's third selector. Without it the first appearance
    # of the light or banner erases the interrupt that restores read mode 0
    # before the road, and the chain never recovers. With it, the divider can
    # hold a DLI at all -- which is what lets index 10 stay on zone 17 and
    # zone 18 keep its stock content. Line counts only otherwise; neither
    # edit touches an address or any visible graphics.
    p.put(0xA6C1, [0x86], expect=[0x06])   # dat_A6BB 3rd selector: +DLI
    p.put(0xA6D3, [0x84], expect=[0x04])   # dat_A6CD 3rd selector: +DLI (5 lines)

    # -- read mode has to follow the layout ----------------------------------
    # The HUD's text objects are character mode and need CTRL read mode 3;
    # both road views need mode 0. Wrong either way and the failure is not
    # obvious: the HUD garbles, or road bands decode into a sawtooth-edged
    # wrong shape. DLI_ECA1's tail governs zones 1+, so it flips to mode 0 for
    # player 2. Zone 11's DLI still routes to mode 3 for the divider (below,
    # ZoneDividerRestore takes over from sub_EC67 to add a palette fix at the
    # same spot), and zone 15's already restores mode 0 below -- untouched,
    # and load-bearing.
    p.put(0xED1E, [0x29, 0xFC], expect=[0x09, 0x03],
          )  # DLI_ECA1 tail: ORA #$03 -> AND #$FC

    # -- colour ---------------------------------------------------------------
    # Pixel value 0 is transparent and shows BACKGRND, so player 2's view
    # needs the road's ground colour behind it, not sky.
    p.put(0xECA9, [0x1B], expect=[0x89])                    # BACKGRND: sky -> ground

    # Road objects declare palettes 0 and 1, alternating every frame or two --
    # that flip is what animates the rumble strips and the centreline. Both
    # palettes must match the road's, or every other frame renders in
    # whatever colours this region used to use.
    p.put(0xECBF, [0x0F], expect=[0x38])                    # P0C1
    p.put(0xECC3, [0x0F], expect=[0x3C])                    # P0C2
    p.put(0xECCB, [0x34], expect=[0x24])                    # P1C1
    p.put(0xECC7, [0x04], expect=[0x28])                    # P1C2
    p.put(0xECB5, [0x04], expect=[0x80])                    # shared C3 load

    # -- the one piece of new code this patch needs --------------------------
    code, syms = _assemble(hud_reassert_src(HUD_REASSERT_ADDR))
    p.put(HUD_REASSERT_ADDR, code, expect=[0xFF] * len(code))
    reassert_addr = syms["HudReassert"]
    start_drive_addr = syms["StartDriveHud"]
    qual_drive_addr = syms["QualDriveHud"]
    divider_restore_addr = syms["ZoneDividerRestore"]
    palette_only_addr = syms["DividerPaletteOnly"]

    # -- and bring the HUD back once normal driving begins -------------------
    # Two different places turn out to do that, not one (docs/FINDINGS.md,
    # "The mirror was missing the car, and the divider was missing the light" -- found by counting how many
    # times each hook actually ran across a full recording, after the first
    # version of this fix left the HUD not returning after the start light).
    #
    # rom:D848 -- sub_D83D's "resume after a per-lap event" path (state $09
    # -> $03): `LDA #$0B / JSR SoundStop` becomes a JSR to HudReassert, which
    # does the HUD write and then makes the same SoundStop call itself (A
    # restored to $0B first), so nothing about the original behaviour
    # changes beyond adding the write.
    p.put(0xD848, [0x20, reassert_addr & 0xFF, reassert_addr >> 8],
          expect=[0x20, 0xD6, 0xDE])

    # rom:CBEB -- the *other* path, state $11 -> $03 right as the start
    # light finishes, reached from an entirely different routine (a
    # periodic ram_00A2/ram_00A3-gated state check). `LDA #$03 / BNE
    # L_CBF1` becomes a JMP to StartDriveHud, which does the HUD write
    # *first* and only then reloads A with #$03 (HudWrite clobbers A and X
    # -- reloading has to come after) before jumping back to $CBF1 to
    # rejoin the original code -- the shared `STA ram_009D` that three
    # different transitions funnel through, so the actual state store still
    # happens exactly where the game always put it.
    p.put(0xCBEB, [0x4C, start_drive_addr & 0xFF, start_drive_addr >> 8, 0xEA],
          expect=[0xA9, 0x03, 0xD0, 0x02])

    # rom:CBE3 -- a *third* entry point, state $10 -> $02, qualifying's own
    # (and only) transition into its drive state. Unlike the other two,
    # nothing ever transitions qualifying back out of $02 and through here
    # again, which is exactly why the divider previously showed only the
    # start light for the entire qualifying run: no hook ever fired during
    # it. This one shares tight quarters with the rom:CBEB hook above --
    # the unique code for it is only two bytes (`L_CBEF: LDA #$02`) before
    # falling into the same three-way-shared `STA ram_009D` at $CBF1 that
    # StartDriveHud already rejoins at, too little room for a JMP without
    # also overwriting that shared instruction and breaking its other two
    # callers. So the hook goes one step earlier, at the branch's own
    # `CMP #$10 / BEQ L_CBEF` (rom:CBE3, 4 bytes): QualDriveHud reproduces
    # that comparison, and on state $10 does the state store, the HUD write,
    # then a JMP to $CC08 (the same place the original code's `BNE L_CC08`
    # would have landed, given the value it just stored is nonzero). On any
    # other state it jumps to $CBE7 to rejoin the original code exactly
    # where the replaced instructions left off -- the `CMP #$11` check,
    # untouched, still deciding rom:CBEB's own case. L_CBEF and the shared
    # $CBF1 it used to fall into are unreached now, not overwritten -- just
    # four orphaned bytes, harmless. Found only after the first attempt (a
    # hook at rom:D412, a second, unrelated occurrence of the same
    # `LDA #$02 / STA ram_009D` byte pattern this project's own disassembly
    # never labelled as reached from qualifying) was built, live-tested, and
    # shown -- by dense per-frame sampling, not by assumption -- to never
    # actually fire during qualifying at all.
    p.put(0xCBE3, [0x4C, qual_drive_addr & 0xFF, qual_drive_addr >> 8, 0xEA],
          expect=[0xC9, 0x10, 0xF0, 0x08])

    # rom:ED47 -- zone 11's own DLI, `JMP sub_EC67`, retargeted to
    # ZoneDividerRestore (same mode switch, plus the palette fix). Only this
    # one JMP's operand changes; sub_EC67 itself, and DLI_EC87's own,
    # separate call to it, are untouched.
    p.put(0xED48, [divider_restore_addr & 0xFF, divider_restore_addr >> 8],
          expect=[0x67, 0xEC])

    # rom:ED42 -- the *other* path out of the same DLI_ED30 check (ram_009D
    # in $4-$7, the start light showing, so mode stays 0): `STA ram_00FF /
    # JMP sub_EC09` becomes a JMP to DividerPaletteOnly, which reproduces
    # the STA and then applies the same palette/BACKGRND fix, without
    # touching CTRL -- this path's whole point is staying in mode 0 for the
    # light's own graphics, confirmed live at a frame where the light is on
    # screen: without this hook specifically, the light still rendered
    # against the road's colours even after the mode-3 case above was fixed.
    p.put(0xED42, [0x4C, palette_only_addr & 0xFF, palette_only_addr >> 8, 0xEA, 0xEA],
          expect=[0x85, 0xFF, 0x4C, 0x09, 0xEC])
    return p


FIXES = [
    {"id": "mirror-split", "fn": fix_mirror_split,
     "title": "Split screen: player 2's view mirrors player 1's road",
     "note": "Experimental. Player 2's view is a mirror of player 1's road, "
             "not yet an independent camera -- see docs/FINDINGS.md."},
]


# --------------------------------------------------------------------- I/O

def load_source():
    for c in SOURCES:
        if not c or not os.path.isfile(c):
            continue
        blob = open(c, "rb").read()
        header = len(blob) - ROM_SIZE
        if header not in (0, HDR):
            continue
        return c, header, bytearray(blob[header:])
    raise SystemExit(
        "Pole Position II ROM not found. Set PP2_ROM, or drop a copy named\n"
        "  %s\nbeside this script." % ROM_NAME)


def _runs(addrs, gap=1):
    """Sorted addresses -> a list of (start, length), merging gaps <= `gap`."""
    addrs = sorted(addrs)
    out = []
    i = 0
    while i < len(addrs):
        j = i
        while j + 1 < len(addrs) and addrs[j + 1] - addrs[j] <= gap:
            j += 1
        out.append((addrs[i], addrs[j] - addrs[i] + 1))
        i = j + 1
    return out


def pick_anchors(rom, sections, n=4, size=256):
    """Extents no option touches, to identify the cartridge by.

    A hash of the whole file is true of exactly one dump -- the pristine one
    -- and false of every ROM this bundle produces, so it cannot answer "is
    this the right game" about a cartridge that already has an option on it.
    Anchors can: ground no option stands on, as true after patching as before.
    """
    busy = [(int(s["addr"], 16) - BASE, int(s["addr"], 16) - BASE + s["length"])
            for s in sections.values()]
    out = []
    for i in range(n):
        start = (len(rom) * (2 * i + 1)) // (2 * n)
        for at in range(start, len(rom) - size):
            if any(not (at + size <= a or b <= at) for a, b in busy):
                continue
            if any(not (at + size <= a or b <= at) for a, b in
                   [(int(x["addr"], 16) - BASE, int(x["addr"], 16) - BASE + x["length"])
                    for x in out]):
                continue
            chunk = rom[at:at + size]
            if len(set(chunk)) < 32:          # a run of one value proves nothing
                continue
            out.append({"addr": "0x%04X" % (at + BASE), "length": size,
                        "crc32": "0x%08X" % (zlib.crc32(chunk) & 0xFFFFFFFF)})
            break
    if len(out) < n:
        raise SystemExit("could not find %d usable anchors" % n)
    return out


def build(out_path, sign=False):
    """Apply the fix directly. Unsigned by default -- see the docstring above
    on why: a recording made against the pristine ROM depends on the
    signature block's *exact bytes*, not merely on whether they verify."""
    src, header, rom = load_source()
    p = Patcher(bytes(rom))
    for fix in FIXES:
        fix["fn"](p)
    body = bytes(p.rom)

    if sign:
        sys.path.insert(0, TOOLKIT_TOOLS)
        import sign7800
        try:
            body = sign7800.signed(body)
        except sign7800.SignError as e:
            raise SystemExit("could not sign the patched image: %s" % e)

    out = (b"\x00" * header if header == 0 else
           io.open(src, "rb").read()[:header]) + body
    io.open(out_path, "wb").write(out)
    print("wrote %s (%d bytes changed)%s"
          % (out_path, len(p.writes), "" if sign else " -- unsigned"))
    return 0


def build_bundle(out_path=None):
    """Write dist/pp2-splitscreen.abp: sections, the one option, its BPS."""
    sys.path.insert(0, TOOLKIT_TOOLS)
    import patchset
    import bps

    src, header, rom = load_source()
    p = Patcher(bytes(rom))
    for fix in FIXES:
        fix["fn"](p)

    touched = set()
    for addr, data in p.writes:
        touched.update(range(addr, addr + len(data)))

    sections = {}
    for at, n in _runs(touched, gap=4):
        sections["s_%04X" % at] = {
            "addr": "0x%04X" % at, "length": n,
            "crc32": "0x%08X" % patchset.crc32(bytes(rom[at - BASE:at - BASE + n])),
        }
    anchors = pick_anchors(rom, sections)

    touched_ids = sorted(sections, key=lambda sid: int(sections[sid]["addr"], 16))
    before, after = bytearray(), bytearray()
    for sid in touched_ids:
        at, n = int(sections[sid]["addr"], 16), sections[sid]["length"]
        before += rom[at - BASE:at - BASE + n]
        after += p.rom[at - BASE:at - BASE + n]

    member = "p/mirror-split.bps"
    files = {member: bps.create(bytes(before), bytes(after))}
    option = {
        "id": "mirror-split",
        "title": FIXES[0]["title"],
        "note": FIXES[0]["note"],
        "patches": [{"sections": touched_ids, "bps": member,
                     "before": "0x%08X" % patchset.crc32(bytes(before))}],
    }

    manifest = {
        "format": patchset.FORMAT,
        "name": "Pole Position II split-screen (experimental)",
        "what": "Two-viewport layout: player 2's view (a mirror of player "
                "1's road, not yet an independent camera) on top, the HUD "
                "relocated to the centre as a divider, player 1's road "
                "unmoved below. The start light and the qualifying banner "
                "still display at that same divider, as stock; a small new "
                "routine (HudReassert) brings the HUD back once each one "
                "finishes.",
        "target": {
            "what": os.path.basename(src),
            "body_size": len(rom),
            "body_sha256": hashlib.sha256(bytes(rom)).hexdigest(),
            "headers": [0, HDR],
            "region": "ntsc",
            "base": "0x%04X" % BASE,
            "anchors": anchors,
        },
        "sections": sections,
        "options": [option],
    }
    out_path = out_path or os.path.join(DISTDIR, "pp2-splitscreen.abp")
    if not os.path.isdir(DISTDIR):
        os.makedirs(DISTDIR)
    patchset.write_bundle(out_path, manifest, files)
    print(out_path)
    print("  1 option, %d sections, %d bytes covered"
          % (len(sections), sum(s["length"] for s in sections.values())))
    print("  %d bps file(s), %d bytes"
          % (len(files), sum(len(v) for v in files.values())))
    print("")
    print("  python ../a7800-toolkit-local/tools/patchset.py list %s" % out_path)
    print("  python ../a7800-toolkit-local/tools/patchset.py apply %s "
          "--rom \"%s\" --with mirror-split --out pp2-split.a78" % (out_path, ROM_NAME))
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.strip().split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--build", action="store_true",
                    help="apply the fix directly and write a playable .a78 "
                         "(unsigned by default -- add --sign for a real-hardware copy)")
    ap.add_argument("--sign", action="store_true",
                    help="with --build: sign the result. Do NOT use this for a "
                         "build you intend to test against an existing .inp "
                         "recording -- see the docstring's note on why")
    ap.add_argument("--bundle", nargs="?", const="", metavar="OUT",
                    help="write the .abp (default: dist/pp2-splitscreen.abp)")
    ap.add_argument("-o", "--out", help="output path for --build")
    args = ap.parse_args()

    if args.bundle is not None:
        return build_bundle(args.bundle or None)
    if args.build:
        if not args.out:
            raise SystemExit("--build needs -o (where to write the playable ROM)")
        return build(args.out, sign=args.sign)
    for f in FIXES:
        print("  %-14s %s" % (f["id"], f["title"]))
        print("                 %s" % f["note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
