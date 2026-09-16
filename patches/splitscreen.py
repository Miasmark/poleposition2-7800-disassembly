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

    zone  0        16 lines   blank top margin
    zones 1-11     67         player 2's view (ten road bands + a gap)
    zones 12-14    21         HUD, three rows -- the centre divider
    zones 15-17    15         blank
    zones 18-19    20         horizon decoration
    zones 20-32    78         player 1's road (unmoved)
    zones 33-34    32         blank

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

It mirrors the *last* ten of player 1's thirteen road zones (real zones
23-32), not the first ten -- the player's own car sprite lives in the last
five of those (docs/FINDINGS.md, "a higher-detail car sprite"), so mirroring
the first ten cut its bottom off. The three farthest bands go unmirrored
instead; nothing important is out there to miss.

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

# Only ten zones are safe to give player 2's view (docs/FINDINGS.md, "Two
# zones safe to touch, two that are not") -- zones 2-11, ending right where
# the stock display-interrupt chain already switches character mode on for
# the HUD at zone 11. So this mirrors the *last* ten of the thirteen bands
# (real zones 23-32) rather than the first ten: the player's own car sprite
# lives across the last five of them ($8B10-family, docs/FINDINGS.md "a
# higher-detail car sprite"), and mirroring the first ten cut its bottom two
# zones' worth of lines off -- MARIA has no idea the object continues onto a
# zone this mirror didn't include. The three farthest bands go unmirrored
# instead, which costs nothing anyone would miss (docs/FINDINGS.md).
ROAD_BANDS = ALL_ROAD_BANDS[3:13]

# Zones carrying a display-interrupt bit. The DLI chain is positional in
# effect even though it's index-driven in code (docs/FINDINGS.md): moving
# either of these two specific bits to a later zone renders correctly on its
# own but measurably desyncs an existing recording, so they stay exactly
# where the stock game put them.
DLI_ZONES = {0, 7, 11, 15, 19}

# The three-row HUD. Written into zones 12-14 (see the module docstring) by
# HudReassert once normal driving begins, sharing that divider with the
# start light and the "POLE POSITION!" banner exactly as stock already did.
HUD_ROWS = [0x06, 0x1D, 0x1C, 0x06, 0x1D, 0x28, 0x06, 0x1D, 0x34]

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
    """Two hooks, one shared write, because there turned out to be two
    places normal driving begins from, not one.

    HudWrite is the 9-byte copy into zones 12-14 (ram $2224), shared by
    both. HudReassert wraps it for rom:D848, where it replaces `LDA #$0B /
    JSR SoundStop` at the end of sub_D83D -- the "resume driving after a
    per-lap event" path (state $09 -> $03) -- and still makes that same
    SoundStop call itself afterward, A restored to $0B first, so nothing
    about the original behaviour changes beyond adding the HUD write.

    StartDriveHud wraps it for rom:CBEB, where it replaces `LDA #$03 / BNE
    L_CBF1` -- state $11 -> $03, the *other* path into normal driving, right
    as the start light finishes, reached from a completely different
    routine (a periodic ram_00A2/ram_00A3-gated state check, not sub_D83D
    at all). Both were needed: hooking only rom:D848 (this patch's first
    attempt) left the HUD not returning after the start light specifically,
    confirmed live by counting how many times each actually ran across a
    full recording -- see docs/FINDINGS.md, "Two places normal driving
    begins from"."""
    return [
        ".org $%04X" % addr,
        "SoundStop = $%04X" % SOUNDSTOP,
        "HudWrite:",
        "    LDX #$08",
        "Loop:",
        "    LDA HudTriplet,X",
        "    STA $2224,X",
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
        lines.append("    STA $%04X" % (0x2224 + i))
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


def fix_mirror_split(p):
    """Give player 2's view zones 1-11; let the start light and the banner
    keep displaying at zones 12-14 as stock always has; bring the HUD back
    there once normal driving begins.

    Ported from the hand-verified edits built up over several live sessions
    (docs/FINDINGS.md, "Phase 1" onward). One piece *is* new code --
    HudReassert -- and the module docstring explains what forced that.
    """
    # -- player 2's view: a gap, then ten bands across zones 2..11 -----------
    p.put(zone(1), [0x06, 0x24, 0xF6], expect=[0x09, 0x24, 0xF6])

    originals = {2: [0x06, 0x1D, 0x1C], 3: [0x02, 0x24, 0xF6],
                 4: [0x06, 0x1D, 0x28], 5: [0x02, 0x24, 0xF6],
                 6: [0x06, 0x1D, 0x34], 7: [0x82, 0x24, 0xF6],
                 8: [0x07, 0x22, 0xC7], 9: [0x07, 0x22, 0xD1],
                 10: [0x07, 0x22, 0xDB], 11: [0x82, 0x24, 0xF6]}
    for i, dl in enumerate(ROAD_BANDS):
        z = 2 + i
        flags = 0x05 | (0x80 if z in DLI_ZONES else 0x00)   # 6 lines, DLI bit preserved
        p.put(zone(z), [flags, dl >> 8, dl & 0xFF], expect=originals[z])

    # -- below the HUD: blank, sized so player 1's road still starts on time -
    p.put(zone(16), [0x05, 0x24, 0xF6], expect=[0x07, 0x22, 0xE1])
    p.put(zone(17), [0x05, 0x24, 0xF6], expect=[0x07, 0x22, 0xEB])

    # -- read mode has to follow the layout ----------------------------------
    # The HUD's text objects are character mode and need CTRL read mode 3;
    # both road views need mode 0. Wrong either way and the failure is not
    # obvious: the HUD garbles, or road bands decode into a sawtooth-edged
    # wrong shape. DLI_ECA1's tail governs zones 1+, so it flips to mode 0 for
    # player 2. Zone 11's DLI already routes through sub_EC67 (mode 3) for the
    # HUD band, and zone 15's already restores mode 0 below -- both untouched,
    # and both load-bearing.
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
