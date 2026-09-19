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
    zone  1         4         blank gap  (must stay blank -- a road band here
                                          hangs the machine; see below)
    zones 2-13     72         player 2's view -- twelve road bands
                                                      DLI index 8 on zone 7
    zone  14        6         blank, and the landing pad for
                                                      DLI index 9
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

Zone 14 is blank on purpose. MARIA raises a zone's display interrupt about
four scanlines before that zone has finished displaying, and palette writes
take effect immediately, so index 9's handler -- which swaps the road's
palette for the divider's -- used to repaint the bottom four lines of the
last mirror band while they were still on screen. Giving index 9 a blank zone
of its own puts that early write somewhere harmless. It costs the mirror its
farthest band, because zones 1-14 hold exactly fourteen selectors and zone 1
cannot be the one given up.

Player 2's view is currently a *mirror*: its bands point at the same RAM
sub-lists player 1's road uses, so it tracks the same curve and the same
stripe animation for free, at the cost of stair-stepping where the real road
is smooth. That last part is not a temporary limitation: the smoothness comes
from DLI_InjectRowCurveX, which is beam-synchronised -- one WSYNC per road
scanline, rewriting each band's x mid-zone -- so a second copy for the mirror
would cost another ~78 scanlines of stalled main loop. Measured headroom is
four to five scanlines (docs/FINDINGS.md, "What a second view cannot have").
See
"Phase 1" in docs/FINDINGS.md for the full trail -- including two things this
patch had to fix that are not obvious from the zone table alone: CTRL's read
mode has to follow the layout (character mode for the HUD, the road's mode
everywhere else), and BACKGRND has to carry the road's ground colour into
player 2's view or every transparent pixel in the road graphics shows sky.

It mirrors twelve of player 1's thirteen road zones -- all but the farthest,
which pays for zone 14 -- so the top view is 72 lines of road against the 78
below it, with the missing band being the most distant and least detailed. Earlier versions managed only ten, and
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
# All but the farthest. Thirteen would fit the line budget, but index 9 needs
# a blank zone to land on (see put_zone(p, 14, ...) in fix_mirror_split) and
# zones 1-14 hold exactly fourteen selectors: thirteen bands leave no room for
# it, and zone 1 cannot be the one given up -- a road band there hangs the
# machine outright a few thousand frames in, with the screen flashing as the
# interrupt chain dies (docs/FINDINGS.md). So the blank goes after the bands
# and the farthest band, the one with least on it, pays for it.
ROAD_BANDS = ALL_ROAD_BANDS[1:]

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
# Where MARIA reads the zone list from. Stock builds it at $2200, immediately
# below the results screen's own list at $226B, which leaves room for exactly
# the 35 zones stock uses and no more. $2500-$27FF is 768 bytes with no
# reference anywhere in the disassembly -- verified by scanning for both
# literal addresses and indexed bases -- and it sits clear of the last road
# band's display list, which ends at $24FA. Moving the race list there is what
# makes a finer-grained mirror possible: it needs far more than 35 zones.
DLL_BASE = 0x2500

# The mirror is drawn as thirty-six two-line zones rather than twelve six-line
# ones, each with its own short display list, so its road edge steps every two
# scanlines instead of every six. What pays for it: a band's display list is
# nine four-byte object slots and eight of them are usually empty -- address
# $0000 -- but MARIA fetches every one regardless. Pointing the mirror at a
# short list of its own instead of at the road's costs ~24 scanlines less DMA,
# measured (docs/FINDINGS.md, "Paying for the mirror with slots it never used").
FINE_LINES = int(os.environ.get("PP2_FINE_LINES", "2"))   # scanlines per mirror zone
# Bands 1..FINE_BAND_LAST are drawn with fine zones; the rest keep one
# six-line zone each on the road's own list so their objects survive.
# How many of the near bands keep their own short, road-only display lists.
# Zero by default, and that is the point: a band on its own list draws the
# road and nothing else, so cars and signs disappear at that range. With the
# injection gone the road is stepped either way, so the fine zones were buying
# smoothness that is no longer on offer while costing every distant object.
# All twelve bands now point at the road's real lists, in both views.
FINE_BAND_LAST = int(os.environ.get("PP2_FINE_LAST", "0"))
SUBS_PER_BAND = 6 // FINE_LINES
FINE_ZONES = FINE_BAND_LAST * SUBS_PER_BAND
MIRROR_ZONES = FINE_ZONES + (12 - FINE_BAND_LAST)
# Both views are built from the same plan now, so the zone list is two of them
# plus the fixed furniture: the top margin and gap, the carrier, three divider
# rows, the horizon, the decor strip and two bottom margin zones.
DLL_ZONES = MIRROR_ZONES * 2 + 10
IDX8_SUB = int(os.environ.get("PP2_IDX8", str(5 * SUBS_PER_BAND)))
MINI_DL_BASE = int(os.environ.get("PP2_MINI_BASE", "0x2600"), 16)
MINI_DL_SIZE = 6

# The blank zone index 9 lands on, between the mirror and the divider. Six
# lines is the minimum that keeps the divider's early palette write off the
# last mirror band; anything spare goes here as breathing room above the HUD.
CARRIER_LINES = int(os.environ.get("PP2_CARRIER", "12"))

# ---------------------------------------------------------------------------
# Player 2's own viewport.
#
# Until now both views pointed at the same thirteen road display lists, so they
# could not diverge however the zones were arranged -- a mirror by
# construction. Player 2 gets its own lists here, driven by its own geometry,
# which is what makes two cameras possible at all.
#
# Road surface only: ten bytes per band, the two road objects and an end
# marker. Copying player 1's lists wholesale would carry the traffic across
# too, but they are 468 bytes and rewriting them every frame costs ~3,700
# cycles -- about 33 scanlines, more than the whole budget the injection
# bypass freed. Objects in player 2's view need the engine to compute a second
# set of positions for a second camera anyway; a copy of player 1's would be
# in the wrong places by definition.
P2_DL_BASE = 0x2600
# Player 2's bands no longer share one stride. A fixed stride meant every band
# paid for a car slot only four of them use, and -- the reason this had to
# change -- the far bands had ZEROS where their second road object would go,
# which MARIA reads as end-of-list. Anything placed after that was never drawn,
# so an object slot at a fixed offset was unreachable in exactly the seven bands
# that most need one. Sized per band instead, the object slot sits immediately
# after the road objects, where MARIA always reaches it:
#
#     far  bands 1-7    road0, object, end                10 bytes
#     near bands 8-11   road0, road1, car, object, end    18
#     near band  12     road0, road1, object, end         14
#
# 156 bytes against the 216 a uniform 18 would have cost.


def p2_band_layout():
    """Each band's list address and the offsets within it.

    Returns band -> dict with 'addr', 'road1', 'car' and 'obj'. 'road1' and
    'car' are None for bands that have neither.
    """
    out, addr = {}, P2_DL_BASE
    for b in range(1, 13):
        near = b >= 8
        has_car = b in P2_CAR_BANDS
        off = 4
        road1 = None
        car = None
        if near:
            road1 = off
            off += 4
        if has_car:
            car = off
            off += 4
        obj = off
        out[b] = {"addr": addr, "road1": road1, "car": car, "obj": obj}
        addr += obj + 4 + 2          # the object slot, then the end marker
    return out


def p2_dl_bytes():
    """Total size of player 2's lists, for the copy loop and the layout check."""
    lay = p2_band_layout()
    return lay[12]["addr"] + lay[12]["obj"] + 6 - P2_DL_BASE
P2_TEMPLATE = 0xFEC0

# A constant added to player 2's road x. Zero makes the two views identical
# again, which is the regression check; anything else drives the viewports
# apart and is how the split is demonstrated before there is a second camera.
P2_X_OFFSET = int(os.environ.get("PP2_P2_OFFSET", "0"), 0)

# Player 2's lateral position, as a signed offset from player 1's, and the
# scratch the camera maths uses. Both live in the free RAM above the display
# lists so no zero page has to be found for them.
P2_LATERAL = 0x2702          # signed: how far player 2 sits from player 1
P2_SCRATCH = 0x2703          # step, step3, step6, accumulator -- 7 bytes

# Re-running the engine's geometry for a second camera is not affordable: the
# pipeline is two 78-iteration loops, about 38 scanlines, against roughly 10
# of headroom. It does not have to be re-run. The only thing a lateral move
# changes is the seed in sub_E9DA, and that seed enters as a constant step
# accumulated once per row -- dat_EA41 indexed by the offset, a straight ramp
# of ~3.55 per unit whose high byte stays zero to index 72. So the shift at
# row i is just i * step / 256, and a band sampling row 6b+3 can be walked
# with one 16-bit add per band. ~360 cycles for the whole camera.
LATERAL_RAMP = 0xEA41

# Player 2's controller. The game never touches it: every SWCHA read masks
# $F0, $20 or $10 -- all high nibble, player 1's stick -- and INPT2, INPT3 and
# INPT5 appear nowhere in the ROM at all. So player 2's directions sit in
# SWCHA's low nibble, unread, active low: bit 3 right, bit 2 left, bit 1 down,
# bit 0 up. Player 1 steers on INPT0/INPT1 with INPT4 as trigger, so the same
# shape of input is free for player 2 whenever its steering wants to be
# analogue rather than a stick.
SWCHA = 0x0280
P2_RIGHT, P2_LEFT = 0x08, 0x04
P2_LIMIT = 0x68              # how far player 2's camera may lean either way.
                             # $68 is 104, the furthest player 1 was observed to
                             # reach, which puts open grass and the scenery line
                             # inside player 2's range too. It was $3C -- one
                             # unit past the road edge -- then $47, as far as a
                             # single-byte lateral ramp allows. Reading the ramp
                             # as the 16-bit value it actually is removed that
                             # ceiling; the remaining one is the table's length.
P2_STEP_HI = 0x2710          # high byte of the per-row lateral step
P2_STAGE_TMP = 0x2715        # the stripe byte, held across the near-band write
LATERAL_RAMP_HI = 0xEADE     # dat_EA41's HIGH byte. The ramp is a 16-bit value,
                             # about 3.55 per unit, and it passes 256 at index
                             # 72 -- which is exactly why reading only the low
                             # byte capped how far player 2 could go.
LATERAL_RAMP_LEN = 120       # both halves run $EA41..$EAB8 and $EADE..$EB55
ROAD_EDGE = 0x3B             # |lateral| at or past this is off the racing line,
                             # the same threshold player 1 uses at rom:C210

# ---------------------------------------------------------------------------
# Player 2's own position along the track.
#
# This is the half of a second camera that cannot be derived from player 1's
# arrays, because it depends on the curvature of the track ahead of a
# different point. The engine's own walk (AccumulateRowCurveOffset, rom:E981)
# covers 78 rows; player 2's view samples 13 of them, one per band at row
# 6b+3, so the walk runs 13 times with the integration stepped six rows at a
# time instead of once.
#
# The stepping is done as six real single-row integrations rather than a
# closed form. The accumulate is a DOUBLE integration -- curvature into a
# velocity, velocity into a position -- so a six-row step is v += 6c and
# p += 6v + 21c, the 21c being sum(1..6) for the intermediate rows. Doing the
# six steps literally is both cheaper than those 16-bit constant multiplies
# and exactly right, which removes the question of how much the coarse step
# drifts from the engine's own answer.
P2_TRACK_SEG = 0x2750        # player 2 track state; $2730 is NOT free -- see findings
P2_TRACK_LO = 0x2751
P2_TRACK_HI = 0x2752
P2_WALK = 0x2720             # walk scratch: dist, seg, v, p, curvature
P2_SPEED = 0x2753            # player 2's own speed along the track
P2_FRAC = 0x2755             # remainder of the /12 advance, always < 12
P2_QUOT = 0x2758             # whole track units to advance this frame
# The signed track-unit gap between the two cameras, positive when player 1 is
# ahead. Everything that has to relate the two cars -- drawing one in the
# other's view, and collisions -- is built on this.
GAP_PSEG = 0x2759            # player 1's segment last frame
GAP_PLO = 0x275A             # player 1's in-segment position last frame
GAP_PHI = 0x275B
GAP_LO = 0x275C              # the gap itself, signed 16-bit
GAP_HI = 0x275D
GAP_TLO = 0x275E             # scratch for this frame's player 1 advance
GAP_THI = 0x275F
P1_SEG = 0x00CF              # player 1's segment
P1_POS_LO = 0x00D5           # player 1's DISTANCE REMAINING in that segment,
P1_POS_HI = 0x00D6           # counting down -- not distance travelled
P1_SPEED = 0x00CE            # player 1's speed byte, same scale as P2_SPEED
PLAYER_X = 0x00D1            # player 1's lateral offset, signed, 0 = centre

# Collision box between the two cars, in the units each axis already uses.
# Longitudinal: the cars advance about 21 units a frame at full speed, so $50
# is roughly a car length at racing speed. Lateral: player 1 reaches about
# +-104 at the rumble strips and the road is about 160 pixels wide there, so a
# lateral unit is roughly 0.77 pixels and the 32-pixel car is about 41 units.
# Both are deliberately single constants, and both are estimates meant to be
# tuned by feel rather than derived.
COLLIDE_Z = 0x50
COLLIDE_X = 0x28
COLLIDE_PENALTY = 0x18       # speed each car loses, ONCE, per contact
P2_HIT = 0x276D              # already touching, so the penalty is not re-paid
P2_PREV_STATE = 0x276E       # $009D last frame, to spot a race starting
# Player 2's own road-stripe phase. The stripes are the only speed cue in a
# view with no HUD of its own, and they were scrolling to PLAYER 1's speed,
# because player 2 took its width bytes straight out of player 1's arrays.
P2_PHASE = 0x270A            # 0..29, the texture phase
P2_PHASE_ACC = 0x270B        # its fractional accumulator
P2_LEAN = 0x270C             # this frame's lean for player 2, $00..$20
P2_CAR_OK = 0x270D           # (no longer used; the car reads nothing of player 1's)
P2_GEAR = 0x270E             # $00 lo, $10 hi -- the same values player 1 uses
P2_STEER_ACC = 0x270F        # steering authority accumulator, scaled by speed

# Player 2's controls now mirror player 1's exactly: the two buttons are gas and
# brake, the stick shifts gear up and down, and left/right steer.
INPT2, INPT3 = 0x000A, 0x000B    # port 2's two buttons; player 1 uses INPT0/1
ACCEL_TABLE = 0xC3C1         # dat_C3C1[(Speed>>4) + Gear], signed
RACE_CLOCK_LO = 0x00DF       # both zero during the countdown, which is how
RACE_CLOCK_HI = 0x00DE       # rom:C2DA knows the race has not started

# Band 10's car sprite comes from one of TWO sheets, and the alternation
# between them is the wheel flicker. Measured over a run, in the driving state:
#     high byte $AA -> low byte = $D8 + lean
#     high byte $91 -> low byte =       lean
# Both ascend with lean, which is why the lean delta was already right for this
# band. What was wrong is that the SHEET was copied from player 1, so player 2's
# wheels flickered in lockstep with player 1's.
TIRE_SHEET_A_HI, TIRE_SHEET_A_LO = 0xAA, 0xD8
TIRE_SHEET_B_HI, TIRE_SHEET_B_LO = 0x91, 0x00
TIRE_BAND = 10
# The other three bands' pages, constant in every driving frame measured.
P2_CAR_BASE_HI = {8: 0x9D, 9: 0x97, 11: 0x8B}
STRIPE_TEX = 0x1F00          # sub_E8AC's texture, read at phase + dat_C07E[row]
STRIPE_WIDTH = 0x1F3C        # per-row width field, ORed into the same byte
ROW_TEX_INDEX = 0xC07E       # dat_C07E: each row's offset into the texture
GAME_STATE = 0x009D          # $02 qualifying drive, $03 race drive,
                             # $10 and $11 the banner runs that precede them
GRID_LANE = 0x20             # half the gap between the two grid lanes, 32.
                             # 64 apart is outside the collision box of 40 and
                             # well inside the road edge at 59.
GRID_MIN_MIRROR = 0x10       # below this, player 1's slot is too near the
                             # centre to mirror usefully, so fall back

# The divider is shared: its top row belongs to player 2 and its lower rows to
# player 1, matching the viewport above and below it. Player 2's row needs a
# display list of its own rather than the game's, so it can be filled with
# player 2's readouts. Seeded at boot from the row it replaces, so it renders
# something recognisable before the content is rewritten.
P2_HUD_DL = 0x2770           # player 2's HUD row: one 5-byte header + end
P2_HUD_TEMPLATE = 0xFF70            # 12 bytes; moved off $FC00 to leave
                                    # P2_TEMPLATE room to grow
SWCHA = 0x0280               # player 2's stick: bit 3 right, 2 left, 1 down, 0 up
P2_HALF = 0x2756             # which half of the walk this frame runs
P2_END = 0x2757              # the sample index this half stops at
P2_BANDX = 0x2760            # 13 bytes: the walk answer per band

SEG_LEN_LO, SEG_LEN_HI, SEG_CURVE = 0x1800, 0x185A, 0x1900
ROW_CURVE_OFFSET = 0x1A31    # the walk's own output, before the per-row base
TRACK_LEN = 0x00C1
BAND_SAMPLE = int(os.environ.get("PP2_SAMPLE", "3"))
PLACEHOLDER_W = int(os.environ.get("PP2_PW", "0x1F"), 16)
PLACEHOLDER_X = int(os.environ.get("PP2_PX", "0x80"), 16)
DLL_TEMPLATE = 0xFE58          # boot image of the zone list, clear of the code blob
MINI_TEMPLATE = 0xFF7C         # boot image of the mini display lists

# Road band slot +00, the road surface itself: (address low, address high).
# Confirmed static across frames -- the injection rewrites only this slot's
# width and x, never its address -- which is what lets the mini lists bake
# their addresses in at boot and do no per-frame address work at all.
BAND_GFX = [(0x00, 0x80), (0x06, 0x80), (0x0E, 0x80), (0x00, 0xAA),
            (0x10, 0xAA), (0xBC, 0x9E), (0xD2, 0x9E), (0x1A, 0x80),
            (0x38, 0x80), (0x5A, 0x80), (0x7E, 0x80), (0xA6, 0x80),
            (0xD2, 0x80)]

# Slot +04. The five nearest bands draw the road with TWO objects, not one --
# by then it is wider than a single object can cover -- and a mirror that
# replicated only slot +00 lost the left half of its road from the eighth band
# down, a hard seam across the view. Addresses are static like slot +00's;
# width and x change per frame but NOT per scanline (the injection never
# touches this slot), so all three sub-zones of a band share one value.
# None is a band whose second slot stays empty.
BAND_SLOT1 = [None] * 8 + [(0x47, 0x80), (0x69, 0x80), (0x8D, 0x80),
                           (0xB5, 0x80), (0xE1, 0x80)]

# Slot +1C of player 1's near bands is the player's car: palette 6, 8 bytes
# wide, and -- in 5999 of the 6700 frames sampled -- x = 64. It spans bands 8
# to 11, one graphics page per band, and the page is the base plus a lean
# offset of 0, 8, $10, $18 or $20, with $10 upright.
#
# x = 64 is not a compromise for player 2, it is the right answer: the car is
# centred and the ROAD moves under it, and player 2's road already moves with
# player 2's steering. So width and x are baked into the template and only the
# graphics page is copied each frame. The lean therefore still follows player
# 1's steering, which is the one part of this that is scaffolding.
P1_CAR_SLOT = [0x244C + 0x1C, 0x246E + 0x1C, 0x2490 + 0x1C, 0x24B2 + 0x1C]
P2_CAR_BANDS = [8, 9, 10, 11]
P2_CAR_SEED = [(0x08, 0x9D), (0x08, 0x97), (0xE0, 0xAA), (0x08, 0x8B)]
P2_CAR_W = 0xD8              # palette 6, 8 bytes
P2_CAR_X = 0x40              # 64
P2_CAR_DELTA = 0x2754        # this frame's lean adjustment, L2 - L1

# The road is injected two different ways and the mirror has to follow both.
# For the eight far bands, DLI_InjectRowCurveX writes a band's slot +00 width
# and x from these two arrays, indexed by road scanline:
ROW_CURVE_X = 0x1B00           # per-scanline road x
ROW_CURVE_Y = 0x1B4E           # per-scanline road width

# From band 8 down (road scanline 48, rom:EE73 onward) it switches to writing
# FOUR bytes per scanline -- both road objects, width and x each -- from four
# separate arrays indexed by (scanline - 48). Missing this is what put a seam
# across the mirror at the eighth band: the near zones were being fed the far
# bands' arrays, which is not where those bands' geometry lives at all.
NEAR_FIRST_ROW = 48            # road scanline where the scheme changes
NEAR_SLOT0_W = 0x007E          # zero page
NEAR_SLOT0_X = 0x0060          # zero page
# These two are not separate arrays at all: $1B30 is RowCurveXStaged + 48 and
# $1B7E is RowCurveYStaged + 48 -- the ordinary per-row curve arrays, read at
# the near rows. So the near bands' RIGHT half is positioned by exactly the
# same values the far bands use, and only their LEFT half comes from the
# zero-page pair.
#
# Which is why stripping the walk's tail at rom:E9BE broke them. That strip
# stopped RowCurveXStagedSrc being written, so StageRowCurveForDLI now copies
# nothing into RowCurveXStaged. The far bands were given a replacement --
# RowCurveOffset plus the per-row base -- and the near bands' right half was
# not, so it read zero and collapsed onto the left half.
NEAR_SLOT1_W = 0x1B7E        # == RowCurveYStaged + 48, still filled by sub_E8AC
NEAR_SLOT1_X = 0x1B30        # == RowCurveXStaged + 48, NO LONGER FILLED
# Where the per-frame hook goes: sub_DC4F, called from the true vertical-blank
# handler's tail at rom:F16B. Two earlier choices inside the main loop both
# failed the same way. StageRowCurveForDLI (rom:EA2C) stages only the x array,
# $1B00-$1B4D; the width array at $1B4E is filled separately. Moving past that
# to sub_DD41 (rom:D8CF) still read a half-built frame -- probing what the
# routine actually saw returned widths of 34 30 30 30 00 00 where the live
# values were 18 38 38 14 34 34, and a width of $00 is MARIA's end-of-list
# marker, so most mirror zones terminated immediately and drew nothing.
#
# The main loop simply does not have a point where both arrays are settled.
# Vertical blank does: by then the road below has already been drawn from
# them, so the mirror is guaranteed to show exactly the values player 1's
# road used -- one frame old, which is what the coarse mirror always showed.
PER_FRAME_HOOK = int(os.environ.get("PP2_HOOKSUB", "0xDC4F"), 16)

# Zone 0, the blank gap at zone 1, the mirror, then index 9's blank carrier:
# the divider starts immediately after those. Derived rather than written
# down, because a stale constant here aims the light, the banner and
# HudReassert at whatever zone happens to sit at that index -- with a coarser
# mirror that is a road zone, and the display corrupts a few thousand frames
# in rather than immediately.
DIVIDER_ZONE = MIRROR_ZONES + 3
DIVIDER_ADDR = DLL_BASE + DIVIDER_ZONE * 3

# The three-row HUD, written into the divider by HudReassert once normal
# driving begins, sharing those zones with the start light and the
# "POLE POSITION!" banner exactly as stock already did at its own zones 12-14.
# The third selector's flags byte is $86, not $06: seven lines *plus* the
# DLI bit for index 10. Every writer of these three zones -- this table, the
# light's dat_A6CD and the banner's dat_A6BB -- has to agree on that bit, or
# whichever one runs last silently drops the interrupt.
HUD_ROWS = [0x06, P2_HUD_DL >> 8, P2_HUD_DL & 0xFF,
            0x06, 0x1D, 0x28, 0x86, 0x1D, 0x34]

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
HUD_REASSERT_ADDR = 0xF400
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
        "P2C1 = $0029", "P2C2 = $002A", "P2C3 = $002B",
        "P3C1 = $002D", "P3C2 = $002E", "P3C3 = $002F",
        "P4C1 = $0031", "P4C2 = $0032", "P4C3 = $0033",
        "P5C1 = $0035", "P5C2 = $0036", "P5C3 = $0037",
        "P6C1 = $0039", "P6C2 = $003A", "P6C3 = $003B",
        "P7C1 = $003D", "P7C2 = $003E", "P7C3 = $003F",
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
        # DLI_ECA1 sets the palettes for everything above the divider, and
        # the values it picks are the stock ones for a HUD, not for a road:
        # P2 all black, P3 set late at L_ECF8 to $0D/$0B/$09, P4 and P5 in the
        # $C0s, P0C2 a flat colour where the road wants the animated stripe
        # byte. That is why cars, signs and the lap line all came out wrong in
        # the mirror while the road surface itself looked right -- the surface
        # uses P0/P1, which an earlier round had already matched by hand, and
        # everything *on* the road uses P2-P5, which nothing had touched.
        #
        # Rather than six scattered byte-edits inside DLI_ECA1 (which is what
        # this patch used to do, and which cannot work for P3 anyway because
        # L_ECF8 overwrites it afterwards), this runs at the very end of that
        # handler and restates the same palette block DLI_ED4F installs for
        # player 1's road. Both views then draw from identical registers.
        "MirrorPalette:",
        "    LDA #$89", "    STA P2C1",
        "    LDA #$8B", "    STA P2C2",
        "    LDA #$8D", "    STA P2C3",
        "    LDA #$1E", "    STA P3C1",
        "    LDA #$17", "    STA P3C2",
        "    LDA #$0E", "    STA P4C1",
        "    LDA #$98", "    STA P4C2",
        "    LDA #$9C", "    STA P5C1",
        "    LDA #$96", "    STA P5C2",
        "    LDA #$00", "    STA P3C3", "    STA P4C3", "    STA P5C3",
        "    LDA #$0F", "    STA P0C1",
        # the stripe animation: a flat byte here is what made the lap line and
        # the road stripes hold still in the mirror while they moved below.
        "    LDA $00FC", "    STA P0C2",
        "    LDA #$34", "    STA P1C1",
        "    LDA #$04", "    STA P1C2", "    STA P1C3", "    STA P0C3",
        # the ground colour the real road uses, rather than a hardcoded guess
        # -- it is per-track, so a constant was only ever right on some of them.
        # P6 and P7 are the cars. DLI_ED4F sets them too (rom:EDC1 and
        # rom:EDE2); L_ECF8 loads this region's from ram_00F4-$F9 instead,
        # which is why the car in the mirror came out blue while the same car
        # below it was yellow.
        "    LDA #$0F", "    STA P7C1", "    STA P7C2", "    STA P7C3",
        "    LDA #$2F", "    STA P6C1",
        "    LDA #$26", "    STA P6C2",
        "    LDA #$00", "    STA P6C3",
        "    LDA $00FB", "    STA BACKGRND",
        "    JMP $EC09",
        # Copies both boot images into RAM: the zone list to DLL_BASE and the
        # mini display lists to MINI_DL_BASE. Replaces sub_F171's first loop,
        # whose DEX/BPL form could only ever move 128 bytes.
        # With the injection skipped, DLI_ED4F's own tail runs immediately
        # rather than after the road, and two of its jobs were relying on that
        # ordering: setting BACKGRND to the road's ground colour (the injection
        # did it, at rom:EDAF/EDC5) and clearing it to black for the bottom
        # margin (rom:F158, now neutered). This puts the ground colour back
        # before the road is drawn, and lets the margin share it.
        "RoadTail:",
        "    LDA $00FB",
        "    STA BACKGRND",
        "    JSR P2Frame",
        "    JMP $F143",
    ] + p2_walk_src() + [
        "P2ZLo:",   "    .byte " + ",".join("$%02X" % v for v in p2_walk_tables()["P2ZLo"]),
        "P2ZHi:",   "    .byte " + ",".join("$%02X" % v for v in p2_walk_tables()["P2ZHi"]),
        "P2Shift:", "    .byte " + ",".join("$%02X" % v for v in p2_walk_tables()["P2Shift"]),
        "P2Base:",  "    .byte " + ",".join("$%02X" % v for v in p2_walk_tables()["P2Base"]),
        "P2Band:",  "    .byte " + ",".join("$%02X" % v for v in p2_walk_tables()["P2Band"]),
        "MirrorInit:",
        "    LDX #$00",
        "MiLoop1:",
        "    LDA $%04X,X" % DLL_TEMPLATE,
        "    STA $%04X,X" % DLL_BASE,
        "    INX",
        "    CPX #$%02X" % (DLL_ZONES * 3),
        "    BNE MiLoop1",
        "    JSR P2HudInit",
    ] + ([] if os.getenv("PP2_NO_MINI_COPY") else _mini_copy_src()) + [
        "    LDX #$00",
        "P2Loop:",
        "    LDA $%04X,X" % P2_TEMPLATE,
        "    STA $%04X,X" % P2_DL_BASE,
        "    INX",
        "    CPX #$%02X" % p2_dl_bytes(),
        "    BNE P2Loop",
        "    RTS",
        # Once per frame, straight after the game stages the per-scanline road
        # curve: give each mirror zone its own width and x from the same two
        # arrays DLI_InjectRowCurveX reads. No WSYNC anywhere -- each zone is
        # only two scanlines, so the value can be written ahead of the beam
        # rather than into the middle of a zone as the road's version must.
        # Zone k stands for road scanline 6 + 2k; the mirror starts at band 1,
        # which is scanline 6.
        "MirrorStage:",
    ] + ["    STA WSYNC"] * int(os.environ.get("PP2_BURN", "0")) + [
        "    JSR $%04X" % PER_FRAME_HOOK,
    ] + _unrolled_mirror_stage() + (
        [] if os.getenv("PP2_KEEP_INJECTION") else road_stage_src()
    ) + p2_stage_src() + p2_car_src() + [
        "    RTS",
    ] + p2_stage_tables() + [
        "WrapSlot0:",
        "    CMP #$A0",
        "    BCC WrapKeep",
        "    CMP #$FD",
        "    BCS WrapKeep",
        "    LDA #$FC",          # $FC - $3C = $C0: parked at 192..255, no wrap
        "WrapKeep:",
        "    SEC",
        "    SBC #$3C",
        "    RTS",
    ] + p2_race_init_src() + [
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
        # MirrorPalette leaves P2-P5 holding the road's colours, so the divider
        # has to put back the ones DLI_ECA1 and L_ECF8 would have left, or the
        # HUD, the start light and the banner inherit the road's palette.
        "    LDA #$00", "    STA P2C1", "    STA P2C2", "    STA P2C3",
        "    LDA #$0D", "    STA P3C1",
        "    LDA #$0B", "    STA P3C2",
        "    LDA #$09", "    STA P3C3",
        "    LDA #$C8", "    STA P4C1", "    STA P5C2",
        "    LDA #$CC", "    STA P4C2",
        "    LDA #$C4", "    STA P5C1",
        # and DLI_ECA1's own start-light special case (rom:ECDC-ECF6), which
        # tinted P4 while the light was on screen. It used to reach the light
        # because the light drew in this palette region; now that the light
        # draws in the divider, the tint has to be applied here instead.
        "    LDA $009D",
        "    CMP #$13",
        "    BNE PalNoSub",
        "    LDA $0048",
        "PalNoSub:",
        "    CMP #$06",
        "    BMI PalDone",
        "    CMP #$08",
        "    BPL PalDone",
        "    LDA #$0A", "    STA P4C1",
        "    LDA #$35", "    STA P4C2",
        "    LDA #$0C", "    STA P4C3",
        # and P6/P7 back to what L_ECF8 loads for this region.
        "    LDA $00F4", "    STA P6C1",
        "    LDA $00F5", "    STA P6C2",
        "    LDA $00F6", "    STA P6C3",
        "    LDA $00F7", "    STA P7C1",
        "    LDA $00F8", "    STA P7C2",
        "    LDA $00F9", "    STA P7C3",
        "PalDone:",
    ] + (_unrolled_mirror_stage() if os.getenv("PP2_HOOK_PALETTE") else []) + [
        "    JMP $EC09",
        "P2HudInit:",
        "    LDX #$00",
        "P2HudLoop:",
        "    LDA $%04X,X" % P2_HUD_TEMPLATE,
        "    STA $%04X,X" % P2_HUD_DL,
        "    INX",
        "    CPX #$0C",
        "    BNE P2HudLoop",
        "    RTS",
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


def _mini_copy_src():
    """Copy the fine zones' display lists into RAM at boot. Sized to what
    exists: a fixed-size copy overran into live RAM at any base without that
    much free after it. Note this runs once, from a one-time init path, and
    still shifts startup enough to desync a recording -- see docs/FINDINGS.md,
    "Boot-time work desyncs the recordings".
    """
    n = FINE_ZONES * MINI_DL_SIZE
    if n == 0:
        return []                                  # no short lists to copy
    assert n <= 255, "copy needs splitting at %d bytes" % n
    return ["    LDX #$00", "MiLoop2:",
            "    LDA $%04X,X" % MINI_TEMPLATE,
            "    STA $%04X,X" % MINI_DL_BASE,
            "    INX", "    CPX #$%02X" % n, "    BNE MiLoop2"]


def road_stage_src():
    """One width and x per road band per frame, replacing the per-scanline
    injection entirely.

    DLI_InjectRowCurveX is beam-synchronised: one WSYNC per road scanline, ~78
    scanlines of stalled 6502 every frame, and it is what makes player 1's road
    smooth where the mirror steps. Driving each band from a single value
    instead makes the two views match -- which is the point -- and hands that
    time back.

    Each band takes its middle scanline's value. The far bands read the same
    two arrays the mirror's fine zones do; the near five read the four arrays
    the injection switches to at rom:EE73, indexed by (scanline - 48), and
    carry a second road object that needs its own width and x.
    """
    lines = []
    for b in range(13):
        band = ALL_ROAD_BANDS[b]
        # Which scanline of the band to sample. The road tapers across a
        # band, so one sample has to stand for six lines; on a sharp curve the
        # near bands are wide enough that the wrong choice puts the object
        # past the end of the line and MARIA wraps it round to the left edge.
        i = 6 * b + BAND_SAMPLE
        if i < NEAR_FIRST_ROW:
            # x comes from RowCurveOffset plus this band's fixed perspective
            # base, rather than from RowCurveXStagedSrc. That is the same sum
            # the engine used to compute per row at rom:E9D0 -- doing it here,
            # for the 13 rows anything actually reads, lets the whole tail of
            # its walk be stripped.
            lines += ["    LDA $%04X" % (ROW_CURVE_Y + i), "    STA $%04X" % (band + 1),
                      "    LDA $%04X" % (ROW_CURVE_OFFSET + i),
                      "    CLC",
                      "    ADC #$%02X" % band_base(i),
                      "    STA $%04X" % (band + 3)]
        else:
            # Both of the near band's halves are rebuilt here. Neither of the
            # arrays the stock injection reads survives the walk-tail strip:
            # $1B30 is RowCurveXStaged+48 and $0060 is its zero-page copy, and
            # both are now left empty, which is what collapsed the two halves
            # onto a single x. Measured off the live stock ROM across all 30
            # near rows and every sampled frame:
            #
            #   slot1 x == RowCurveOffset[row] + band_base(row)   (same rule
            #              the far bands already use, and band_base already
            #              returns the near bases $48 $44 $3C $34 $30)
            #   slot0 x == slot1 x - $3C                          (exact, never
            #              varies -- slot0 is a fixed-width piece a constant
            #              distance to the left, not a second scaled half)
            #   slot0 W == (slot1 W & $E0) | $10                  (a fixed 16
            #              byte object that only inherits the stripe palette)
            #
            # RowCurveYStaged ($1B4E, hence $1B7E at the near rows) is filled
            # by sub_E8AC and is untouched by the strip, so slot1's width is
            # still read straight out of it.
            n = i - NEAR_FIRST_ROW
            lines += ["    LDA $%04X" % (NEAR_SLOT1_W + n), "    STA $%04X" % (band + 5),
                      "    AND #$E0", "    ORA #$10", "    STA $%04X" % (band + 1),
                      "    LDA $%04X" % (ROW_CURVE_OFFSET + i),
                      "    CLC", "    ADC #$%02X" % band_base(i),
                      "    STA $%04X" % (band + 7)]
            lines += wrap_guard()
            lines += ["    STA $%04X" % (band + 3)]
    return lines


def _unrolled_mirror_stage():
    """Each fine mirror zone's road width and x, written straight rather than
    looped. Every fine zone belongs to a far band, so they all read the same
    two per-scanline arrays; the near bands keep the road's own lists and need
    no update at all. Mirror zone k stands for road scanline 6 + FINE_LINES*k.
    """
    lines = []
    if os.getenv("NOUPDATE"):
        return lines
    limit = int(os.environ.get("PP2_UPD_LIMIT", str(FINE_ZONES)))
    for k in range(min(limit, FINE_ZONES)):
        i = 6 + FINE_LINES * k
        a = MINI_DL_BASE + k * MINI_DL_SIZE
        lines += ["    LDA $%04X" % (ROW_CURVE_Y + i), "    STA $%04X" % (a + 1),
                  "    LDA $%04X" % (ROW_CURVE_X + i), "    STA $%04X" % (a + 3)]
    return lines



# An 8-bit HPOS cannot express a negative position. MARIA renders x in
# $A0..$FF correctly as a negative offset, because the head lands past column
# 159 (invisible) and only the part that runs past 255 wraps back into 0..,
# which is exactly where a negative-positioned object belongs. But once the
# intended position is far enough left that its 8-bit value drops back into
# $00..$9F, MARIA draws it as a POSITIVE position and the object reappears at
# the right-hand edge as a detached slab of road.
#
# slot0 is the half this happens to, because it sits a fixed $3C to the left of
# slot1. With slot1 at $C7 (-57) slot0 is at -117, whose byte is $8B = 139, and
# 139 is a perfectly ordinary on-screen column. Measured against the stock ROM
# at a comparable lateral offset, the road pixel runs per scanline were
#     stock  0-129                (one run)
#     ours   0-131  and  278-319  (two runs; 278-319 is 139..159 in MARIA units)
#
# slot0 is 16 bytes = 64 pixels, so it is entirely off-screen left exactly when
# slot1 is in $A0..$FC, and parking it at $C0 hides it with no wrap of its own
# ($C0 + 64 = 256, so its span ends at 255). $FC is the cutoff because at
# slot1 >= $FD a few of slot0's pixels legitimately reach column 0.
def wrap_guard():
    """Turn slot1's x, in A, into slot0's x, parking it off-screen when its true
    position is too far left to be expressed in eight bits.

    Inline this and it is ten extra bytes a band, which is a hundred bytes the
    blob does not have -- it overran the free $FF run at $F3FF-$FF7E. As a call
    it costs JSR + STA, exactly what SEC / SBC / STA cost before the guard
    existed, so the blob does not grow at all. The price is 12 cycles a band,
    about one scanline across all ten."""
    return ["    JSR WrapSlot0"]


def _blob_len():
    """Length of the generated code blob, for the layout check.

    The blob has to be measured before anything is written, because it is the
    piece that keeps outgrowing its slot -- and when it runs into a template the
    failure reads as "expected ff.. but found <template data>", which names the
    victim rather than the culprit.
    """
    return len(_assemble(hud_reassert_src(HUD_REASSERT_ADDR))[0])


def band_base(row):
    """dat_EBA4[dat_BB7E[row]] -- the fixed perspective base the engine adds to
    RowCurveOffset at rom:E9D0. Constant per row, so it need not be looked up
    at runtime."""
    import io as _io
    rom = bytearray(_io.open(load_source()[0], "rb").read())
    rom = rom[len(rom) - ROM_SIZE:]
    return rom[(0xEBA4 + rom[0xBB7E + row - BASE]) - BASE]


def p2_walk_tables():
    """Per-sample track depth, curvature scale and lateral base, in walk order
    (nearest band first). Lifted straight out of the stock tables at the 13
    rows player 2's bands actually sample."""
    import io as _io
    rom = bytearray(_io.open(load_source()[0], "rb").read())
    rom = rom[len(rom) - ROM_SIZE:]
    at = lambda a: rom[a - BASE]
    rows = [6 * b + 3 for b in range(13)][::-1]
    return {
        "P2ZLo":   [at(0xEB56 + i) for i in rows],
        "P2ZHi":   [at(0xEAB9 + i) for i in rows],
        "P2Shift": [0 if i >= 0x40 else (1 if i >= 0x20 else (2 if i >= 0x10 else 3))
                    for i in rows],
        "P2Base":  [at(0xEBA4 + at(0xBB7E + i)) for i in rows],
        "P2Band":  list(range(12, -1, -1)),
    }


def p2_walk_src():
    """Walk player 2's track position out to each band and leave the road's
    lateral offset for that band in P2_BANDX."""
    W = P2_WALK
    return [
        # Called from the MAIN LOOP, not from vblank. The walk is far too long
        # for the vblank handler's deadline -- that is why stripping ~1,900
        # cycles out of the engine's own walk bought nothing while this ran
        # there: the saving was main-loop time, and vblank is not main-loop
        # time. Here it can spend what the strip freed.
        # Called from RoadTail, i.e. from DLI_ED4F once the road's palettes are
        # set and before the frame-end work -- mid screen, every frame, with
        # the bottom margin's slack ahead of the vblank wait.
        #
        # NOT from sub_D8AC. That was the first choice and it is not a per-frame
        # routine at all: a counter incremented there reached 1 and stayed
        # there, so player 2's track position was copied once at race start,
        # from segment 0, and frozen. Every symptom followed from that -- the
        # walk integrating zero curvature, the steering doing nothing, and the
        # band output sitting at exactly the per-band base values.
        "P2Frame:",
        "    INC $2758",
    ] + p2_drive_src() + [
        "    JSR P2Geom",
        "    RTS",
        "P2Geom:",
    ] + (["    RTS"] if os.getenv("PP2_STUB_GEOM") else []) + [
        # distance starts where the engine starts it: $47 plus the player's
        # own distance into the current segment (rom:E941)
        # The parity is read here BEFORE it is toggled below, so the test is
        # against the value this frame is about to flip: a 1 now becomes the
        # second half, which must NOT reinitialise the accumulators the first
        # half left behind. Getting this the wrong way round left the two
        # halves computed from different starting states, and they failed to
        # join -- a clean step in the road right at the boundary band.
        "    LDA $%04X" % P2_HALF,
        "    BNE P2GNoInit",
        "    CLC",
        "    LDA #$47", "    ADC $%04X" % P2_TRACK_LO, "    STA $%04X" % W,
        "    LDA #$00", "    ADC $%04X" % P2_TRACK_HI, "    STA $%04X" % (W + 1),
        "    LDA $%04X" % P2_TRACK_SEG, "    STA $%04X" % (W + 2),
        "    LDA #$00",
        "    STA $%04X" % (W + 3), "    STA $%04X" % (W + 4),
        "    STA $%04X" % (W + 5), "    STA $%04X" % (W + 6),
        "P2GNoInit:",
        # Twelve samples fit in a frame here and thirteen do not, so the walk
        # runs in halves and completes every second frame. The accumulators --
        # distance, segment, velocity, position -- already live in RAM, so the
        # second half simply carries on from where the first stopped: only the
        # index and the stopping point differ.
        "    LDA $%04X" % P2_HALF,
        "    EOR #$01",
        "    STA $%04X" % P2_HALF,
        "    BEQ P2GSecond",
        "    LDX #$00",
        "    LDA #$07",
        "    STA $%04X" % P2_END,
        "    JMP P2GLoop",
        "P2GSecond:",
        "    LDX #$07",
        "    LDA #$0D",
        "    STA $%04X" % P2_END,
        "P2GLoop:",
        # The advance below walks track segments until the distance reaches
        # this sample's depth. It is the one unbounded loop in the walk, and
        # it runs inside a display interrupt -- if the track length or a
        # segment length ever reads zero the distance stops growing and it
        # spins forever, taking the machine with it. Bounded to 32 steps, far
        # more than six rows of distance can legitimately need.
        "    LDA #$20",
        "    STA $%04X" % (P2_WALK + 10),
        # advance through track segments until the distance reaches this
        # sample's depth. A loop, not a single test: six rows of distance can
        # cross more than one segment.
        "P2GAdv:",
        "    SEC",
        "    LDA $%04X" % W,       "    SBC P2ZLo,X",
        "    LDA $%04X" % (W + 1), "    SBC P2ZHi,X",
        "    BPL P2GHave",
        "    LDY $%04X" % (W + 2),
        "    INY",
        "    CPY $%04X" % TRACK_LEN,
        "    BNE P2GNoWrap",
        "    LDY #$00",
        "P2GNoWrap:",
        "    STY $%04X" % (W + 2),
        "    CLC",
        "    LDA $%04X,Y" % SEG_LEN_LO, "    ADC $%04X" % W,       "    STA $%04X" % W,
        "    LDA $%04X,Y" % SEG_LEN_HI, "    ADC $%04X" % (W + 1), "    STA $%04X" % (W + 1),
        "    DEC $%04X" % (P2_WALK + 10),
        "    BEQ P2GHave",
        "    JMP P2GAdv",
        "P2GHave:",
        # curvature for this segment, sign extended, scaled the way the stock
        # ASL chain scales it at this depth
        "    LDY $%04X" % (W + 2),
        "    LDA $%04X,Y" % SEG_CURVE,
        "    STA $%04X" % (W + 8),
        "    LDY #$00",
        "    CMP #$80",
        "    BCC P2GPos",
        "    LDY #$FF",
        "P2GPos:",
        "    STY $%04X" % (W + 9),
        "    LDY P2Shift,X",
        "    BEQ P2GNoShift",
        "P2GShift:",
        "    ASL $%04X" % (W + 8), "    ROL $%04X" % (W + 9),
        "    DEY", "    BNE P2GShift",
        "P2GNoShift:",
        # six single-row integrations -- three for the first sample, which is
        # only three rows in from where the walk starts
        "    LDY #$06",
        "    CPX #$00",
        "    BNE P2GSteps",
        "    LDY #$03",
        "P2GSteps:",
        "    CLC",
        "    LDA $%04X" % (W + 3), "    ADC $%04X" % (W + 8), "    STA $%04X" % (W + 3),
        "    LDA $%04X" % (W + 4), "    ADC $%04X" % (W + 9), "    STA $%04X" % (W + 4),
        "    CLC",
        "    LDA $%04X" % (W + 5), "    ADC $%04X" % (W + 3), "    STA $%04X" % (W + 5),
        "    LDA $%04X" % (W + 6), "    ADC $%04X" % (W + 4), "    STA $%04X" % (W + 6),
        "    DEY",
        "    BNE P2GSteps",
        # the band's lateral offset: the position's high byte plus the fixed
        # perspective base the engine adds at rom:E9D0
        "    LDA $%04X" % (W + 6),
        "    CLC",
        "    ADC P2Base,X",
        "    LDY P2Band,X",
        "    STA $%04X,Y" % P2_BANDX,
        "    INX",
        "    CPX $%04X" % P2_END,
        # inverted: the loop body is well over 128 bytes, so the way back has
        # to be a jump rather than a relative branch
        "    BEQ P2GDone",
        "    JMP P2GLoop",
        "P2GDone:",
        "    RTS",
    ]


def p2_plan():
    """Player 2's viewport: the same zone shape as player 1's, but every zone
    pointed at player 2's own display list rather than the shared road."""
    lay = p2_band_layout()
    return [(6, lay[b]["addr"], None) for b in range(1, 13)]


def p2_dl_template():
    """Boot image of player 2's lists. The graphics addresses never change --
    only width and x do -- so they are baked in and cost nothing per frame.
    Bands without a second road object get a zero width byte there, which is
    MARIA's end-of-list marker, so the list simply stops after the first."""
    lay = p2_band_layout()
    out = []
    for b in range(1, 13):
        lo, hi = BAND_GFX[b]
        e = [lo, 0x1F, hi, 0x80]
        if lay[b]["road1"] is not None:
            lo1, hi1 = BAND_SLOT1[b]
            e += [lo1, 0x1F, hi1, 0x80]
        if lay[b]["car"] is not None:
            clo, chi = P2_CAR_SEED[P2_CAR_BANDS.index(b)]
            e += [clo, P2_CAR_W, chi, P2_CAR_X]
        # the object slot, parked off-screen until something is put in it, then
        # the two-byte end marker
        e += [0x00, 0x1F, 0x00, 0xA1, 0x00, 0x00]
        out += e
    return out


def p2_car_src():
    """Draw player 2's car entirely from its own state.

    Nothing here reads player 1's sprite any more. It used to copy player 1's
    graphics page and add a lean delta, which meant player 2 inherited player
    1's CRASH: when player 1 spun, player 2's car spun with it, in a view where
    player 2 was still driving perfectly well.

    The pages are constants. Measured over 5163 frames of run-01 and 5933 of
    run-02, in every single ordinary driving frame:

        band  8   high $9D   low = lean
        band  9   high $97   low = lean
        band 11   high $8B   low = lean
        band 10   high $AA   low = $D8 + lean   <- one of two wheel sheets
                  high $91   low =       lean   <- the other

    so the whole car is a base plus this frame's lean, with band 10 also picking
    a wheel sheet. Player 2 picks that from bit 0 of its own stripe phase, which
    advances at about its own Speed/40 a frame.

    The one thing still taken from player 1 is WHETHER there is a car to draw at
    all. Before a race its slot holds $0000, and both cars come and go together,
    so player 2's is parked off-screen at x = $A1 -- the same idiom the stock
    lists use for an empty object slot -- rather than drawn over a menu.

    Player 2 therefore never shows a crash animation, because player 2 has no
    crash of its own yet. Not crashing is the right failure here: sympathetic
    crashing was the bug.
    """
    lines = ["    LDA $%04X" % (P1_CAR_SLOT[3] + 2), "    BNE P2CarDraw"]
    lay = p2_band_layout()
    for b in P2_CAR_BANDS:
        dl = lay[b]["addr"] + lay[b]["car"]
        lines += ["    LDA #$A1", "    STA $%04X" % (dl + 3)]
    lines += ["    JMP P2CarEnd", "P2CarDraw:"]

    # this frame's lean, straight off the stick: $08 right, $18 left, $10 level
    lines += [
        "    LDX #$%02X" % int(os.environ.get("PP2_FORCE_LEAN", "0x10"), 16),
        "    LDA $%04X" % SWCHA,
        "    AND #$%02X" % P2_LEFT,
        "    BNE P2LeanNotL",
        "    LDX #$18",
        "P2LeanNotL:",
        "    LDA $%04X" % SWCHA,
        "    AND #$%02X" % P2_RIGHT,
        "    BNE P2LeanNotR",
        "    LDX #$08",
        "P2LeanNotR:",
        "    STX $%04X" % P2_LEAN,
    ]

    for b in P2_CAR_BANDS:
        dl = lay[b]["addr"] + lay[b]["car"]
        lines += ["    LDA #$%02X" % P2_CAR_X, "    STA $%04X" % (dl + 3)]
        if b == TIRE_BAND:
            lines += [
                "    LDA $%04X" % P2_PHASE,
                "    AND #$01",
                "    BEQ P2TireB",
                "    LDA #$%02X" % TIRE_SHEET_A_HI, "    STA $%04X" % (dl + 2),
                "    LDA $%04X" % P2_LEAN,
                "    CLC", "    ADC #$%02X" % TIRE_SHEET_A_LO,
                "    STA $%04X" % (dl + 0),
                "    JMP P2TireDone",
                "P2TireB:",
                "    LDA #$%02X" % TIRE_SHEET_B_HI, "    STA $%04X" % (dl + 2),
                "    LDA $%04X" % P2_LEAN, "    STA $%04X" % (dl + 0),
                "P2TireDone:",
            ]
        else:
            lines += ["    LDA #$%02X" % P2_CAR_BASE_HI[b], "    STA $%04X" % (dl + 2),
                      "    LDA $%04X" % P2_LEAN, "    STA $%04X" % (dl + 0)]
    lines += ["P2CarEnd:"]
    return lines


def p2_camera_src():
    """Set up player 2's lateral camera for the frame.

    step  = LATERAL_RAMP[|offset|]        the per-row shift, 8 bits
    step3 = step * 3                      the first band samples row 9
    step6 = step * 6                      one band is six rows further on
    acc   = step3                         then += step6 before each band

    Negative offsets negate step3 and step6 once, so the per-band loop is a
    plain 16-bit add either way and the high byte of the accumulator is the
    shift to apply.
    """
    S = P2_SCRATCH
    return [
        "    LDA $%04X" % P2_LATERAL,
        "    BPL P2Mag",
        "    EOR #$FF",
        "    CLC",
        "    ADC #$01",
        "P2Mag:",
        "    TAX",
        # The ramp is 16 bits. Taking only the low byte silently wrapped past
        # index 71, which is what limited how far player 2 could travel.
        "    LDA $%04X,X" % LATERAL_RAMP,
        "    STA $%04X" % S,
        "    LDA $%04X,X" % LATERAL_RAMP_HI,
        "    STA $%04X" % P2_STEP_HI,
        # step3 = step * 3, now from a 16-bit step
        "    LDA $%04X" % S,
        "    STA $%04X" % (S + 1),
        "    LDA $%04X" % P2_STEP_HI,
        "    STA $%04X" % (S + 2),
        "    ASL $%04X" % (S + 1),
        "    ROL $%04X" % (S + 2),
        "    LDA $%04X" % (S + 1),
        "    CLC",
        "    ADC $%04X" % S,
        "    STA $%04X" % (S + 1),
        "    LDA $%04X" % (S + 2),
        "    ADC $%04X" % P2_STEP_HI,
        "    STA $%04X" % (S + 2),
        # step6 = step3 * 2
        "    LDA $%04X" % (S + 1),
        "    ASL A",
        "    STA $%04X" % (S + 3),
        "    LDA $%04X" % (S + 2),
        "    ROL A",
        "    STA $%04X" % (S + 4),
        # negate both when player 2 sits to the other side
        "    LDA $%04X" % P2_LATERAL,
        "    BPL P2NoNeg",
        "    SEC",
        "    LDA #$00", "    SBC $%04X" % (S + 1), "    STA $%04X" % (S + 1),
        "    LDA #$00", "    SBC $%04X" % (S + 2), "    STA $%04X" % (S + 2),
        "    SEC",
        "    LDA #$00", "    SBC $%04X" % (S + 3), "    STA $%04X" % (S + 3),
        "    LDA #$00", "    SBC $%04X" % (S + 4), "    STA $%04X" % (S + 4),
        "P2NoNeg:",
        # accumulator starts at step3
        "    LDA $%04X" % (S + 1), "    STA $%04X" % (S + 5),
        "    LDA $%04X" % (S + 2), "    STA $%04X" % (S + 6),
    ]


def p2_drive_src():
    """Player 2's car: throttle, steering, and its own distance along the track.

    Everything here is player 2's own state. Nothing is copied from player 1
    any more, which is what makes this two cars rather than two views of one.
    The stick is free -- the game never reads SWCHA's low nibble -- so up and
    down are throttle and brake, left and right are steering.

    Advancing the position mirrors what the engine does for player 1: add the
    speed to the distance into the current segment, then carry into the next
    segment for as long as the distance exceeds that segment's length. The
    carry is a loop because at speed one frame can cross a short segment
    entirely.
    """
    return [
        # Start a race by watching the game's own state byte rather than by
        # hooking the race-start routine. A JSR inside StartDriveHud cost
        # enough time to change how the race ran -- run-02's race ended some
        # 4000 frames early -- which is the same cycle sensitivity that already
        # forced the light and banner templates to be matched line for line.
        # Out here in RoadTail there is headroom, and the trigger is free.
        "    LDA $%04X" % GAME_STATE,
        "    CMP $%04X" % P2_PREV_STATE,
        "    BEQ P2InitSkip",
        "    STA $%04X" % P2_PREV_STATE,
        # The banner runs during $10 and $11, with the car already rolling --
        # measured, player 1 reaches speed 77 in $10 before the qualifying lap
        # state $02 even begins. Setting up at $02 therefore left both cars
        # sitting in the centre through the whole banner and snapped them apart
        # the moment driving started. Set up at the BANNER instead.
        "    CMP #$10",
        "    BEQ P2DoInit",
        "    CMP #$11",
        "    BEQ P2DoInit",
        # $03 gets one more visit, because player 1's race grid slot does not
        # exist yet during its banner: PlayerX reads 44 there, a leftover from
        # the previous lap, and only becomes the real slot as $03 begins. So the
        # race re-places player 2 alone then, without disturbing anything else.
        "    CMP #$%02X" % (0x02 if os.getenv("PP2_PLACE_ON_QUAL") else 0x03),
        "    BEQ P2DoPlace",
        "    JMP P2InitSkip",
        "P2DoInit:",
        "    JSR P2RaceInit",
        "    JMP P2InitSkip",
        "P2DoPlace:",
        "    JSR P2PlaceMirror",
        "P2InitSkip:",
        # --- is the race actually under way? --------------------------------
        # rom:C2D4 gates player 1 the same way: outside state 1, if both halves
        # of the race clock are zero the countdown is still running and speed is
        # bled off rather than driven. Player 2 was free to drive off the line
        # early because it had no such gate.
        "    LDA $%04X" % GAME_STATE,
        "    CMP #$01",
        "    BEQ P2CanDrive",
        "    LDA $%04X" % RACE_CLOCK_HI,
        "    ORA $%04X" % RACE_CLOCK_LO,
        "    BNE P2CanDrive",
        "    LDA $%04X" % P2_SPEED,
        "    SEC", "    SBC #$0F",
        "    BCS P2CdStore", "    LDA #$00",
        "P2CdStore:",
        "    STA $%04X" % P2_SPEED,
        "    JMP P2DriveDone",
        "P2CanDrive:",
        # --- gear: stick up shifts to hi, down to lo ------------------------
        "    LDA $%04X" % SWCHA,
        "    AND #$01",
        "    BNE P2NotUp",
        "    LDA #$10", "    STA $%04X" % P2_GEAR,
        "P2NotUp:",
        "    LDA $%04X" % SWCHA,
        "    AND #$02",
        "    BNE P2NotDown",
        "    LDA #$00", "    STA $%04X" % P2_GEAR,
        "P2NotDown:",
        # --- throttle: the gas button, through player 1's own accel table ----
        # dat_C3C1[(Speed>>4) + Gear] is a SIGNED step, which is what makes the
        # gears behave: lo gear pulls hard low down and turns negative past its
        # top speed, hi gear bogs off the line and holds speed up high.
        "    LDA $%04X" % INPT3,
        "    BPL P2NoGas",
        "    LDA $%04X" % P2_SPEED,
        "    LSR A", "    LSR A", "    LSR A", "    LSR A",
        "    CLC", "    ADC $%04X" % P2_GEAR,
        "    TAX",
        "    LDA $%04X,X" % ACCEL_TABLE,
        "    BMI P2GasNeg",
        "    CLC", "    ADC $%04X" % P2_SPEED,
        "    BCC P2GasStore",
        "    LDA #$FF",
        "P2GasStore:",
        "    STA $%04X" % P2_SPEED,
        "    JMP P2NoGas",
        "P2GasNeg:",
        "    CLC", "    ADC $%04X" % P2_SPEED,
        "    BCS P2GasStore2",
        "    LDA #$00",
        "P2GasStore2:",
        "    STA $%04X" % P2_SPEED,
        "P2NoGas:",
        # --- off the racing line: drag ---------------------------------------
        # rom:C200 takes |PlayerX|, and at $3B or beyond calls SkidDrag, which
        # subtracts the top two bits of Speed -- 0 to 3 a frame, so the faster
        # you are the harder the rumble strip bites. Player 2 pays the same.
        #
        # The CLC here is cosmetic. It was added on the belief that the ROM's
        # SkidDrag depended on whatever carry it was entered with, since it
        # rotates three times without clearing first. It does not: after three
        # rotations the entry carry sits in bit 2 and the AND #$03 discards it,
        # leaving bits 1 and 0 holding the original bits 7 and 6. Checked over
        # all 256 speeds against both entry carries -- identical every time. The
        # ROM is already exactly Speed >> 6, and player 1 needs no correction.
        "    LDA $%04X" % P2_LATERAL,
        "    BPL P2OffAbs",
        "    EOR #$FF", "    CLC", "    ADC #$01",
        "P2OffAbs:",
        "    CMP #$%02X" % ROAD_EDGE,
        "    BCC P2OnRoad",
        "    CLC",
        "    LDA $%04X" % P2_SPEED,
        "    ROL A", "    ROL A", "    ROL A",
        "    AND #$03",
        "    SEC", "    EOR #$FF",
        "    ADC $%04X" % P2_SPEED,
        "    BCS P2DragStore", "    LDA #$00",
        "P2DragStore:",
        "    STA $%04X" % P2_SPEED,
        "P2OnRoad:",
        # --- brake ----------------------------------------------------------
        "    LDA $%04X" % INPT2,
        "    BPL P2NoBrake",
        "    LDA $%04X" % P2_SPEED,
        "    SEC", "    SBC #$08",
        "    BCS P2BrStore", "    LDA #$00",
        "P2BrStore:",
        "    STA $%04X" % P2_SPEED,
        "P2NoBrake:",
        # --- road-stripe phase, exactly as sub_E8AC advances player 1's -----
        # AF drops by Speed/2 each frame and every time it goes negative it
        # gains 20 and the phase steps on, so the stripes scroll at about
        # Speed/40 steps a frame. Mirrored rather than reinvented so the two
        # views scroll at the same rate for the same speed.
        "    LDX #$00",
        "    LDA $%04X" % P2_SPEED,
        "    LSR A",
        "    EOR #$FF",
        "    SEC",
        "    ADC $%04X" % P2_PHASE_ACC,
        "    BPL P2PhStore",
        "P2PhLoop:",
        "    INX",
        "    ADC #$14",
        "    BMI P2PhLoop",
        "P2PhStore:",
        "    STA $%04X" % P2_PHASE_ACC,
        "    TXA",
        "    CLC",
        "    ADC $%04X" % P2_PHASE,
        "    CMP #$1E",
        "    BMI P2PhOk",
        "    SBC #$1E",
        "P2PhOk:",
        "    STA $%04X" % P2_PHASE,
        # --- steering ------------------------------------------------------
        # A RISING lateral moves the car LEFT, not right. Measured both ways:
        # holding player 2's stick right moved P2_LATERAL +1.000 a frame and
        # player 2's road x +1.018 a frame, and a road moving right is a car
        # moving left. Player 1 works the same way -- forcing PlayerX to +40
        # and -40 on alternating frames put its road at x 54.6 and 43.6, so
        # positive PlayerX is also a car to the left.
        #
        # The two therefore share a convention, which is what lets the collision
        # box compare P2_LATERAL against PlayerX directly. So the fix for
        # player 2's reversed steering belongs here and nowhere else: right
        # steers toward the negative end, left toward the positive one.
        # Steering authority scales with speed. The accumulator gains the
        # speed byte each frame and a step is taken on each carry out, so it is
        # about one unit a frame at full speed, half that at half speed, and
        # nothing at all at a standstill -- the car cannot be swung sideways
        # while stopped, which it could before.
        "    LDA $%04X" % P2_STEER_ACC,
        "    CLC", "    ADC $%04X" % P2_SPEED,
        "    STA $%04X" % P2_STEER_ACC,
        "    BCC P2NoSteer",
        "    LDA $%04X" % SWCHA,
        "    AND #$%02X" % P2_RIGHT,
        "    BNE P2NotRight",
        "    LDA $%04X" % P2_LATERAL,
        "    SEC",
        "    SBC #$01",
        "    CMP #$%02X" % ((0x100 - P2_LIMIT - 1) & 0xFF),
        "    BNE P2StoreR",
        "    LDA #$%02X" % ((0x100 - P2_LIMIT) & 0xFF),
        "P2StoreR:",
        "    STA $%04X" % P2_LATERAL,
        "P2NotRight:",
        "    LDA $%04X" % SWCHA,
        "    AND #$%02X" % P2_LEFT,
        "    BNE P2NotLeft",
        "    LDA $%04X" % P2_LATERAL,
        "    CLC",
        "    ADC #$01",
        "    CMP #$%02X" % (P2_LIMIT + 1),
        "    BNE P2StoreL",
        "    LDA #$%02X" % P2_LIMIT,
        "P2StoreL:",
        "    STA $%04X" % P2_LATERAL,
        "P2NotLeft:",
        "P2NoSteer:",
        # --- advance along the track ---------------------------------------
        # Player 1 advances by Speed/12 per frame, measured: Speed 16 -> 1.33
        # units, 106 -> 8.83, 198 -> 16.50, 210 -> 17.50. Player 2 was adding
        # its speed raw, which at its old $C0 cap was 192 units a frame against
        # player 1's 21.25 at full tilt -- about nine times too fast.
        #
        # So divide by 12, carrying the remainder between frames rather than
        # throwing it away, which would lose up to 11/12 of a unit each frame.
        # Repeated subtraction is exact and small; the count is bounded because
        # the remainder is always left below 12, so the worst case is 21 passes
        # and a carry out of the add is handled by pre-subtracting 192.
        "    LDA #$00", "    STA $%04X" % P2_QUOT,
        "    LDA $%04X" % P2_FRAC, "    CLC", "    ADC $%04X" % P2_SPEED,
        "    BCC P2DivLoop",
        "    ADC #$3F",                       # carry set, so +$40 = value - 192
        "    LDY #$10", "    STY $%04X" % P2_QUOT,
        "P2DivLoop:",
        "    CMP #$0C",
        "    BCC P2DivDone",
        "    SBC #$0C",                       # CMP left carry set
        "    INC $%04X" % P2_QUOT,
        "    BCS P2DivLoop",                  # SBC cannot borrow here
        "P2DivDone:",
        "    STA $%04X" % P2_FRAC,
        "    CLC",
        "    LDA $%04X" % P2_TRACK_LO, "    ADC $%04X" % P2_QUOT,
        "    STA $%04X" % P2_TRACK_LO,
        "    LDA $%04X" % P2_TRACK_HI, "    ADC #$00",
        "    STA $%04X" % P2_TRACK_HI,
        "P2Carry:",
        "    LDY $%04X" % P2_TRACK_SEG,
        "    SEC",
        "    LDA $%04X" % P2_TRACK_LO, "    SBC $%04X,Y" % SEG_LEN_LO,
        "    TAX",
        "    LDA $%04X" % P2_TRACK_HI, "    SBC $%04X,Y" % SEG_LEN_HI,
        "    BCC P2Rolled",
        "    STA $%04X" % P2_TRACK_HI,
        "    STX $%04X" % P2_TRACK_LO,
        "    INY",
        "    CPY $%04X" % TRACK_LEN,
        "    BNE P2NoWrap2",
        "    LDY #$00",
        "P2NoWrap2:",
        "    STY $%04X" % P2_TRACK_SEG,
        "    JMP P2Carry",
        "P2Rolled:",
        "P2DriveDone:",
    ] + p2_gap_src()


def p2_gap_src():
    """Maintain the signed track gap between the two cameras.

    Both cars advance in the same units -- segment lengths and the perspective
    Z table are one and the same scale, which is what makes this worth having:
    an object's distance from player 2 is its distance from player 1 plus this
    gap, and the ROM's own Z-to-row search at rom:E3CD then turns that into a
    row for player 2 exactly as it does for player 1.

    The gap is accumulated from what each camera ACTUALLY moved rather than
    from speed, which would drift. Player 1's position counts DOWN as distance
    remaining in its segment, so its advance is prev - now, except across a
    segment boundary where it is prev + (new segment's length - now). One
    boundary per frame is the most that can happen: the fastest advance is
    21 units and the shortest segment is far longer.
    """
    return [
        "    LDY $%04X" % P1_SEG,
        "    CPY $%04X" % GAP_PSEG,
        "    BEQ P2GapSame",
        # crossed into a new segment: advance = prev + (seglen[new] - now)
        "    SEC",
        "    LDA $%04X,Y" % SEG_LEN_LO, "    SBC $%04X" % P1_POS_LO,
        "    STA $%04X" % GAP_TLO,
        "    LDA $%04X,Y" % SEG_LEN_HI, "    SBC $%04X" % P1_POS_HI,
        "    STA $%04X" % GAP_THI,
        "    CLC",
        "    LDA $%04X" % GAP_TLO, "    ADC $%04X" % GAP_PLO,
        "    STA $%04X" % GAP_TLO,
        "    LDA $%04X" % GAP_THI, "    ADC $%04X" % GAP_PHI,
        "    STA $%04X" % GAP_THI,
        "    JMP P2GapAdd",
        "P2GapSame:",
        "    SEC",
        "    LDA $%04X" % GAP_PLO, "    SBC $%04X" % P1_POS_LO,
        "    STA $%04X" % GAP_TLO,
        "    LDA $%04X" % GAP_PHI, "    SBC $%04X" % P1_POS_HI,
        "    STA $%04X" % GAP_THI,
        "P2GapAdd:",
        # gap += player 1's advance, then -= player 2's
        "    CLC",
        "    LDA $%04X" % GAP_LO, "    ADC $%04X" % GAP_TLO,
        "    STA $%04X" % GAP_LO,
        "    LDA $%04X" % GAP_HI, "    ADC $%04X" % GAP_THI,
        "    STA $%04X" % GAP_HI,
        "    SEC",
        "    LDA $%04X" % GAP_LO, "    SBC $%04X" % P2_QUOT,
        "    STA $%04X" % GAP_LO,
        "    LDA $%04X" % GAP_HI, "    SBC #$00",
        "    STA $%04X" % GAP_HI,
        # Saturate. The gap is a running total and player 1 laps the track, so
        # left alone it overflows -- measured -32747..32689 over one run -- and
        # every wrap through zero reads as the two cars being in the same place.
        # Anything past +-$4000 means they are nowhere near each other, so
        # pinning it there costs nothing and removes the phantom contacts.
        "    LDA $%04X" % GAP_HI,
        "    BMI P2GapNeg",
        "    CMP #$40", "    BCC P2GapDone",
        "    LDA #$40", "    STA $%04X" % GAP_HI,
        "    LDA #$00", "    STA $%04X" % GAP_LO,
        "    JMP P2GapDone",
        "P2GapNeg:",
        "    CMP #$C0", "    BCS P2GapDone",
        "    LDA #$C0", "    STA $%04X" % GAP_HI,
        "    LDA #$00", "    STA $%04X" % GAP_LO,
        "P2GapDone:",
        # remember where player 1 was, for next frame
        "    LDA $%04X" % P1_SEG,  "    STA $%04X" % GAP_PSEG,
        "    LDA $%04X" % P1_POS_LO, "    STA $%04X" % GAP_PLO,
        "    LDA $%04X" % P1_POS_HI, "    STA $%04X" % GAP_PHI,
    ] + p2_collide_src()


def p2_collide_src():
    """Knock the two cars apart when they touch.

    The gap is the exact longitudinal separation, so the test is a box: |gap|
    under COLLIDE_Z and the lateral offsets within COLLIDE_X.

    Two things here are not obvious, and the first version got both wrong.

    The speed penalty is paid ONCE per contact, not every frame. Charged every
    frame it is not a collision, it is a clamp: the cars start the race on the
    same piece of track, so they touch from frame one, and player 1 could never
    accelerate off the line -- run-02 went from HEALTHY to STALLED, with player
    1's speed pinned at 0 for the first 1500 frames.

    And contact PUSHES player 2 sideways, away from player 1, so the overlap
    actually resolves instead of persisting until something else happens to
    separate them. Only player 2 is pushed; shoving player 1's lateral would be
    reaching into the game's own physics rather than alongside it.
    """
    if os.getenv("PP2_NO_COLLIDE"):
        return []
    return [
        # |gap| < COLLIDE_Z, with the gap signed 16-bit
        "    LDA $%04X" % GAP_HI,
        "    BEQ P2HitZPos",
        "    CMP #$FF",
        "    BNE P2NoHit",
        "    LDA $%04X" % GAP_LO,               # negative: -COLLIDE_Z..-1
        "    CMP #$%02X" % (0x100 - COLLIDE_Z),
        "    BCC P2NoHit",
        "    JMP P2HitX",
        "P2HitZPos:",
        "    LDA $%04X" % GAP_LO,
        "    CMP #$%02X" % COLLIDE_Z,
        "    BCS P2NoHit",
        "P2HitX:",
        # signed lateral difference, kept for the push direction
        "    LDA $%04X" % P2_LATERAL,
        "    SEC", "    SBC $%04X" % PLAYER_X,
        "    STA $%04X" % GAP_TLO,
        "    BPL P2HitAbs",
        "    EOR #$FF", "    CLC", "    ADC #$01",
        "P2HitAbs:",
        "    CMP #$%02X" % COLLIDE_X,
        "    BCS P2NoHit",
        # --- touching: push player 2 clear, respecting the camera's limits ---
        "    LDA $%04X" % GAP_TLO,
        "    BMI P2PushLeft",
        "    LDA $%04X" % P2_LATERAL, "    CLC", "    ADC #$01",
        "    CMP #$%02X" % (P2_LIMIT + 1), "    BNE P2PushStore",
        "    LDA #$%02X" % P2_LIMIT,
        "    JMP P2PushStore",
        "P2PushLeft:",
        "    LDA $%04X" % P2_LATERAL, "    SEC", "    SBC #$01",
        "    CMP #$%02X" % ((0x100 - P2_LIMIT - 1) & 0xFF), "    BNE P2PushStore",
        "    LDA #$%02X" % ((0x100 - P2_LIMIT) & 0xFF),
        "P2PushStore:",
        "    STA $%04X" % P2_LATERAL,
        # --- the speed penalty, once per contact ---
        "    LDA $%04X" % P2_HIT,
        "    BNE P2HitEnd",
        "    LDA #$01", "    STA $%04X" % P2_HIT,
        "    LDA $%04X" % P2_SPEED,
        "    SEC", "    SBC #$%02X" % COLLIDE_PENALTY,
        "    BCS P2HitP2Ok", "    LDA #$00",
        "P2HitP2Ok:",
        "    STA $%04X" % P2_SPEED,
        "    LDA $%04X" % P1_SPEED,
        "    SEC", "    SBC #$%02X" % COLLIDE_PENALTY,
        "    BCS P2HitP1Ok", "    LDA #$00",
        "P2HitP1Ok:",
        "    STA $%04X" % P1_SPEED,
        "    JMP P2HitEnd",
        "P2NoHit:",
        "    LDA #$00", "    STA $%04X" % P2_HIT,
        "P2HitEnd:",
    ]


def p2_race_init_src():
    """Put player 2 on the grid beside player 1, once, when a race starts.

    Without this, player 2's state is whatever RAM held at power-on and the gap
    starts from a garbage previous-frame reading. Player 2 lines up level with
    player 1 along the track and P2_START_LATERAL to the side, which is outside
    the collision box, so the race does not begin with the two cars inside each
    other.

    Player 1's position word is distance REMAINING in its segment and player
    2's is distance CONSUMED, hence the subtraction.
    """
    return [
        # Re-place player 2 alone, mirroring whatever grid slot the game has
        # just given player 1 from its qualifying lap. Nothing else is touched,
        # so this is safe to call after the session is already running. If
        # player 1 is too near the centre to mirror usefully, the symmetric pair
        # is used instead.
        "P2PlaceMirror:",
        "    LDA $%04X" % PLAYER_X,
        "    BPL P2GridAbs",
        "    EOR #$FF", "    CLC", "    ADC #$01",
        "P2GridAbs:",
        "    CMP #$%02X" % GRID_MIN_MIRROR,
        "    BCC P2GridSym",
        "    LDA $%04X" % PLAYER_X,
        "    EOR #$FF", "    CLC", "    ADC #$01",
        "    STA $%04X" % P2_LATERAL,
        "    RTS",
        # One car per lane. Used for the qualifying banner, where there is no
        # qualifying result to place anyone by, and as the mirror's fallback.
        "P2GridSym:",
        "    LDA #$%02X" % ((0x100 - GRID_LANE) & 0xFF),
        "    STA $%04X" % PLAYER_X,
        "    LDA #$%02X" % GRID_LANE,
        "    STA $%04X" % P2_LATERAL,
        "    RTS",
        "P2RaceInit:",
        "    JSR P2GridSym",
        "    LDA #$00",
        "    STA $%04X" % P2_SPEED, "    STA $%04X" % P2_FRAC,
        "    STA $%04X" % P2_PHASE, "    STA $%04X" % P2_PHASE_ACC,
        "    STA $%04X" % P2_GEAR, "    STA $%04X" % P2_STEER_ACC,
        "    STA $%04X" % P2_HIT,
        "    STA $%04X" % GAP_LO,  "    STA $%04X" % GAP_HI,
        "    LDY $%04X" % P1_SEG, "    STY $%04X" % P2_TRACK_SEG,
        "    SEC",
        "    LDA $%04X,Y" % SEG_LEN_LO, "    SBC $%04X" % P1_POS_LO,
        "    STA $%04X" % P2_TRACK_LO,
        "    LDA $%04X,Y" % SEG_LEN_HI, "    SBC $%04X" % P1_POS_HI,
        "    STA $%04X" % P2_TRACK_HI,
        # seed the gap's memory so the first frame's advance reads as zero
        "    STY $%04X" % GAP_PSEG,
        "    LDA $%04X" % P1_POS_LO, "    STA $%04X" % GAP_PLO,
        "    LDA $%04X" % P1_POS_HI, "    STA $%04X" % GAP_PHI,
        "    RTS",
    ]


def p2_follow_src():
    """Point player 2's track position at player 1's.

    With this in place the two cameras are at the same place on the track, so
    player 2's walk must reproduce player 1's road exactly -- which is the
    regression check for the walk itself. Replace these three copies with
    player 2's own position and the cameras come apart.
    """
    return [
        "    LDA $00CF", "    STA $%04X" % P2_TRACK_SEG,
        "    LDA $00D5", "    STA $%04X" % P2_TRACK_LO,
        "    LDA $00D6", "    STA $%04X" % P2_TRACK_HI,
    ]


def p2_stage_tables():
    """The per-band constants the staging loops index.

    Everything is a single byte, because every address involved shares a page:
    the stripe texture and the width table both sit in $1F, and all of player
    2's lists in $26. So a band is described by three bytes rather than by
    sixty of unrolled code.
    """
    import io as _io
    rom = bytearray(_io.open(load_source()[0], "rb").read())
    rom = rom[len(rom) - ROM_SIZE:]
    lay = p2_band_layout()
    tex, wid, dst = [], [], []
    for b in range(1, 13):
        i = 6 * b + BAND_SAMPLE
        off = rom[ROW_TEX_INDEX + i - BASE]
        assert off + 29 <= 0xFF, "row %d texture index overflows" % i
        tex.append(off)
        assert (STRIPE_WIDTH + i) >> 8 == STRIPE_TEX >> 8, "width table changed page"
        wid.append((STRIPE_WIDTH + i) & 0xFF)
        assert lay[b]["addr"] >> 8 == P2_DL_BASE >> 8, "band lists changed page"
        dst.append(lay[b]["addr"] & 0xFF)
    return [
        "P2StTex:", "    .byte " + ",".join("$%02X" % v for v in tex),
        "P2StWid:", "    .byte " + ",".join("$%02X" % v for v in wid),
        "P2StDst:", "    .byte " + ",".join("$%02X" % v for v in dst),
    ]


def p2_stage_src():
    """Player 2's road geometry, once per frame, from its own source.

    Two loops rather than twelve unrolled blocks -- one for the far bands,
    which draw the road with a single object, and one for the near bands, which
    need two plus the fixed $3C offset between them. Unrolled this was about
    sixty bytes a band; the loops and their tables are a fraction of that, and
    the space is needed for the object pass.

    The bands must still be walked in order, because the camera accumulator
    advances exactly once per band, so the far loop runs first and the near
    loop continues from where it left off.
    """
    S = P2_SCRATCH
    lines = p2_camera_src()

    def advance():
        return ["    CLC",
                "    LDA $%04X" % (S + 5), "    ADC $%04X" % (S + 3),
                "    STA $%04X" % (S + 5),
                "    LDA $%04X" % (S + 6), "    ADC $%04X" % (S + 4),
                "    STA $%04X" % (S + 6)]

    def stripe():
        # this band's stripe byte, at player 2's own phase
        return ["    LDA $%04X" % P2_PHASE,
                "    CLC", "    ADC P2StTex,X",
                "    TAY",
                "    LDA $%04X,Y" % STRIPE_TEX]

    def band_x():
        out = ["    LDA $%04X,X" % (P2_BANDX + 1),
               "    CLC", "    ADC $%04X" % (S + 6)]
        if P2_X_OFFSET:
            out += ["    CLC", "    ADC #$%02X" % (P2_X_OFFSET & 0xFF)]
        return out

    # --- far bands: one road object -------------------------------------
    lines += ["    LDX #$00", "P2StFar:"]
    lines += stripe()
    lines += [
        "    LDY P2StWid,X",
        "    ORA $%04X,Y" % STRIPE_TEX,
        "    LDY P2StDst,X",
        "    STA $%04X,Y" % (P2_DL_BASE + 1),
    ] + advance() + band_x() + [
        "    LDY P2StDst,X",
        "    STA $%04X,Y" % (P2_DL_BASE + 3),
        "    INX",
        "    CPX #$%02X" % (NEAR_FIRST_ROW // 6 - 1),
        "    BNE P2StFar",
    ]

    # --- near bands: two road objects, slot0 a fixed $3C to the left ------
    lines += ["P2StNear:"]
    lines += stripe()
    lines += [
        "    STA $%04X" % P2_STAGE_TMP,
        "    LDY P2StWid,X",
        "    ORA $%04X,Y" % STRIPE_TEX,
        "    LDY P2StDst,X",
        "    STA $%04X,Y" % (P2_DL_BASE + 5),
        "    LDA $%04X" % P2_STAGE_TMP,
        "    ORA #$10",
        "    STA $%04X,Y" % (P2_DL_BASE + 1),
    ] + advance() + band_x() + [
        "    LDY P2StDst,X",
        "    STA $%04X,Y" % (P2_DL_BASE + 7),
    ] + wrap_guard() + [
        "    LDY P2StDst,X",
        "    STA $%04X,Y" % (P2_DL_BASE + 3),
        "    INX",
        "    CPX #$0C",
        "    BNE P2StNear",
    ]
    return lines


def stripe_src(row):
    """Leave this row's stripe byte in A, at PLAYER 2's phase.

    sub_E8AC builds player 1's width byte as

        RowCurveYStaged[row] = $1F00[phase + dat_C07E[row]] | ram_1F3C[row]

    and its slot0 companion as the same texture byte ORed with $10 -- which is
    also where `ram_004E,X` writes, the array that looked like it had no writer
    at all because only the base $0060 was searched for. Player 2 now does the
    same with its own phase, so the stripes scroll to ITS speed.

    dat_C07E[row] is fixed per row so it is baked in, and it never exceeds 29,
    so phase + offset tops out at 54 and plain absolute-indexed addressing is
    enough -- no zero-page pointer needed, unlike the engine's own (ram_00FD),Y.
    """
    import io as _io
    rom = bytearray(_io.open(load_source()[0], "rb").read())
    rom = rom[len(rom) - ROM_SIZE:]
    off = rom[ROW_TEX_INDEX + row - BASE]
    assert off + 29 <= 0xFF, "row %d texture index would overflow" % row
    return ["    LDA $%04X" % P2_PHASE,
            "    CLC", "    ADC #$%02X" % off,
            "    TAY",
            "    LDA $%04X,Y" % STRIPE_TEX]


def mirror_plan():
    """The mirror, band by band, as (lines, dl_address, mini_index).

    Hybrid on purpose. The far bands get FINE_LINES-tall zones with short
    display lists of their own, which is what makes their road edge smooth --
    and they are where the curve actually reads, since that is where the road
    is narrow. The near bands keep one six-line zone each pointed at the
    road's OWN display list, so everything drawn on them comes along: the
    player's car and the traffic around it, which live in the last five bands.

    Replicating objects into fine zones was the alternative and it does not
    fit. They sit at different offsets in each band and move between frames,
    so there is no cheap subset to copy -- it means the whole slot area, 32
    bytes per sub-zone, over a thousand bytes a frame.
    """
    plan, k = [], 0
    for b in range(1, 13):
        if b <= FINE_BAND_LAST:
            for _ in range(SUBS_PER_BAND):
                plan.append((FINE_LINES, MINI_DL_BASE + k * MINI_DL_SIZE, k))
                k += 1
        else:
            plan.append((6, ALL_ROAD_BANDS[b], None))
    return plan


MIRROR_PLAN_LEN = None       # filled on first use by dll_template()


def dll_template():
    """The new zone list. Replaces the stock 35-zone boot template entirely."""
    plan = mirror_plan()
    z = [[0x8F, 0x24, 0xF6],                          # 0: 16 blank, DLI idx7
         [0x03, 0x24, 0xF6]]                          # 1:  4 blank, must stay blank
    # Index 8 sits partway down the mirror. Its home was expressed in fine
    # sub-zones, which silently lands past the end of a coarse plan -- and a
    # chain link that no zone carries simply never fires, taking every
    # interrupt after it with it. Clamped, so the count can change freely.
    top = p2_plan()                                   # player 2's viewport
    idx8_at = min(IDX8_SUB, len(top) - 1)
    for n, (lines, dl, mini) in enumerate(top):
        dli = 0x80 if n == idx8_at else 0x00
        z.append([(lines - 1) | dli, dl >> 8, dl & 0xFF])
    z.append([(CARRIER_LINES - 1) | 0x80, 0x24, 0xF6])  # blank, DLI idx9
    z.append([0x06, P2_HUD_DL >> 8, P2_HUD_DL & 0xFF])   # divider: player 2's row
    z.append([0x06, 0x1D, 0x28])
    z.append([0x86, 0x1D, 0x34])                      #   DLI idx10
    z.append([0x09, 0x18, 0xFA])                      # horizon, stock
    z.append([0x89, 0x1D, 0x3B])                      # decor, DLI idx11
    # Player 1's view, built from the SAME plan as player 2's -- same zone
    # heights, same display lists, same dropped far band. With the injection
    # gone neither view gets per-scanline treatment any more, so the two are
    # now identical rather than merely similar, and the bottom gives up the
    # six lines of its farthest band in the bargain.
    for lines, dl, _mini in plan:
        z.append([(lines - 1), dl >> 8, dl & 0xFF])
    z.append([0x0F, 0x24, 0xF6])                      # bottom margin
    z.append([0x0F, 0x24, 0xF6])
    total = sum((e[0] & 0x0F) + 1 for e in z)
    tl, bl = sum(p[0] for p in top), sum(p[0] for p in plan)
    if tl != bl:
        raise SystemExit("views differ: top %d lines, bottom %d" % (tl, bl))
    if total != 249:
        raise SystemExit("zone list totals %d lines, need 249 (off by %+d)"
                         % (total, total - 249))
    return [b for e in z for b in e]


def mini_dl_template():
    """One short list per fine mirror zone: a single road-surface object and
    an end marker. Six bytes -- the far bands draw the road with one object,
    so there is no second slot to carry. MARIA steps a zone's graphics one
    page per scanline counting down from height-1, so a zone standing in for
    band rows starting at j0 needs its base page shifted by 6 - FINE_LINES -
    j0 to land on the rows the band would have drawn. Static, so it is baked
    in here and costs nothing per frame."""
    out = []
    for k in range(FINE_ZONES):
        b, m = 1 + k // SUBS_PER_BAND, k % SUBS_PER_BAND
        lo, hi = BAND_GFX[b]
        shift = 6 - FINE_LINES - FINE_LINES * m
        out += [lo, PLACEHOLDER_W, (hi + shift) & 0xFF, PLACEHOLDER_X, 0x00, 0x00]
    return out


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
    # -- player 2's view, as its own zone list -------------------------------
    # The stock boot template at dat_BC7E is no longer used: sub_F171 is
    # redirected below to copy this one instead, which is larger than the 107
    # bytes that would fit between $2200 and the results screen's own list.
    # These four live in the same free $FF run as the code blob, and the blob
    # and the templates have both outgrown their slots more than once. An
    # overlap shows up as an "expected ff.. but found <our own data>" mismatch
    # on whichever put runs second, which says nothing about the real cause, so
    # check the layout first and name the pair that collides.
    _regions = [("code blob", HUD_REASSERT_ADDR, _blob_len()),
                ("DLL_TEMPLATE", DLL_TEMPLATE, DLL_ZONES * 3),
                ("P2_TEMPLATE", P2_TEMPLATE, p2_dl_bytes()),
                ("P2_HUD_TEMPLATE", P2_HUD_TEMPLATE, 12),
                ("MINI_TEMPLATE", MINI_TEMPLATE, FINE_ZONES * MINI_DL_SIZE)]
    _regions = sorted((a, n, nm) for nm, a, n in _regions if n)
    for (a1, n1, nm1), (a2, _, nm2) in zip(_regions, _regions[1:]):
        if a1 + n1 > a2:
            raise SystemExit(
                "layout overlap: %s $%04X..$%04X runs into %s at $%04X"
                % (nm1, a1, a1 + n1 - 1, nm2, a2))

    # The camera now reads the ramp as 16 bits, so the only ceiling left is the
    # table's own length -- run off the end and the lateral step comes from
    # whatever follows it in ROM.
    if P2_LIMIT >= LATERAL_RAMP_LEN:
        raise SystemExit(
            "P2_LIMIT %d runs off the lateral ramp, which has %d entries"
            % (P2_LIMIT, LATERAL_RAMP_LEN))

    p.put(DLL_TEMPLATE, dll_template(), expect=[0xFF] * (DLL_ZONES * 3))
    p.put(P2_TEMPLATE, p2_dl_template(), expect=[0xFF] * p2_dl_bytes())
    # Seed of player 2's HUD row: the same two character objects the row it
    # replaces uses, so it draws legibly from the first frame. Rewriting the
    # characters it points at is what makes it player 2's, and is not done yet.
    p.put(P2_HUD_TEMPLATE,
          [0x8A, 0x60, 0x1F, 0x4D, 0x0C, 0x9D, 0x60, 0x1F, 0x55, 0x68, 0x00, 0x00],
          expect=[0xFF] * 12)
    if FINE_ZONES:
        p.put(MINI_TEMPLATE, mini_dl_template(),
              expect=[0xFF] * (FINE_ZONES * MINI_DL_SIZE))

    # -- aim the light and banner at the new divider -------------------------
    # Both routines end with `STA ram_2224,X`, hardcoded at zone 12 -- which
    # is a mirror band now. One operand byte each sends them to zone 15
    # instead, where the HUD divider actually lives.
    p.put(0xD81B, [DIVIDER_ADDR & 0xFF, DIVIDER_ADDR >> 8],
          expect=[0x24, 0x22])                            # sub_D80D, the banner
    p.put(0xDA92, [DIVIDER_ADDR & 0xFF, DIVIDER_ADDR >> 8],
          expect=[0x24, 0x22])                            # sub_DA7C, the light

    # -- and move the zone list itself ---------------------------------------
    # Two bytes: where sub_F171 copies the boot template to, and the DPPH
    # immediate in sub_D8AC that tells MARIA where to read it from. The
    # results screen's list at $226B is untouched and keeps its own pointer
    # (rom:D89B), so only the race view moves.
    p.put(0xD8D7, [DLL_BASE >> 8], expect=[0x22])   # sub_D8AC: LDA #$22 -> DPPH

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
    # This used to be six byte-edits scattered through DLI_ECA1's palette
    # block -- BACKGRND to a hardcoded ground colour, P0 and P1 to the road's.
    # They got the road *surface* right and everything drawn on it wrong: the
    # cars, the signs and the lap line all take palettes 2-5, which none of
    # them touched, and P3 could not have been fixed that way in any case
    # because L_ECF8 writes it after that block runs. MirrorPalette replaces
    # the lot, at the end of the handler, by restating DLI_ED4F's own palette
    # block -- so the two views draw from identical registers instead of from
    # two hand-matched approximations. See the hook on rom:ED29 below.

    # -- the one piece of new code this patch needs --------------------------
    code, syms = _assemble(hud_reassert_src(HUD_REASSERT_ADDR))
    assert len(code) == _blob_len(),         "blob length moved between the layout check and the put"

    p.put(HUD_REASSERT_ADDR, code, expect=[0xFF] * len(code))
    reassert_addr = syms["HudReassert"]
    start_drive_addr = syms["StartDriveHud"]
    qual_drive_addr = syms["QualDriveHud"]
    divider_restore_addr = syms["ZoneDividerRestore"]
    palette_only_addr = syms["DividerPaletteOnly"]
    mirror_palette_addr = syms["MirrorPalette"]
    mirror_init_addr = syms["MirrorInit"]
    mirror_stage_addr = syms["MirrorStage"]
    road_tail_addr = syms["RoadTail"]

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

    # rom:ED29 -- DLI_ECA1's closing `JMP sub_EC09`, retargeted to
    # MirrorPalette, which installs the road's palettes for player 2's view
    # and then makes the same jump. It has to be here, at the very end of the
    # handler, rather than inside the palette block it supersedes: L_ECF8
    # (rom:ECF8) writes P3 on its way out, so anything set earlier is lost.
    p.put(0xED29, [mirror_palette_addr & 0xFF, mirror_palette_addr >> 8],
          expect=[0x09, 0xEC])

    # rom:F171 -- sub_F171's first loop, which copied the stock 107-byte zone
    # list to $2200, becomes a call to MirrorInit. The loop's DEX/BPL form
    # cannot move more than 128 bytes and the new list is 177, so it is
    # replaced outright rather than retargeted. The second loop, which builds
    # the results screen's own list at $226B, is left exactly as it was.
    # rom:D8CF -- the main loop's `JSR sub_DD41`, retargeted to P2Main, which
    # runs player 2's walk and then makes that same call. It sits after
    # sub_E93D (rom:D8BC) so player 1's own walk has already run, and well
    # before the vblank wait, so the walk is spending main-loop cycles.
    # rom:E9BE -- the tail of the engine's own per-row walk, stripped to just
    # the loop control. Everything between it and the DEX is dead in this
    # build: RowCurveOffsetAlt has no readers anywhere in the ROM, and
    # RowCurveXStagedSrc feeds only StageRowCurveForDLI's copy into
    # RowCurveXStaged, which nothing reads now that the injection is bypassed.
    # The 13 values that ARE read are recomputed in MirrorStage from
    # RowCurveOffset, which the walk still stores. About 1,900 cycles a frame,
    # some 17 scanlines, for no loss of accuracy at all.
    p.put(0xE9BE, [0xCA, 0x10, 0x9B, 0x60],
          expect=[0xBC, 0x7E, 0xBB, 0xE0])

    # rom:ED9D -- the head of DLI_InjectRowCurveX, replaced by a jump straight
    # to the handler's own tail at rom:F143. That skips the whole per-scanline
    # injection, ~78 scanlines of WSYNC, and leaves the palette block above it
    # untouched. The bands now carry whatever MirrorStage wrote for the frame.
    if not os.getenv("PP2_KEEP_INJECTION"):
        p.put(0xED9D, [0x4C, road_tail_addr & 0xFF, road_tail_addr >> 8],
              expect=[0xAD, 0x00, 0x1B])
        # rom:F158 -- `STA BACKGRND` with A=0. It used to run after the road
        # had been drawn; without the injection's 78 scanlines in front of it
        # it now lands mid-road and blacks the whole view out.
        p.put(0xF158, [0xEA, 0xEA], expect=[0x85, 0x20])

    p.put(0xF171, [0x20, mirror_init_addr & 0xFF, mirror_init_addr >> 8] + [0xEA] * 8,
          expect=[0xA2, 0x6A, 0xBD, 0x7E, 0xBC, 0x9D, 0x00, 0x22, 0xCA, 0x10, 0xF7])

    # rom:F16B -- the vertical-blank handler's `JSR sub_DC4F`, retargeted to
    # MirrorStage, which makes that same call and then hands each mirror zone
    # its own width and x. Registers are free here: the handler's next
    # instruction is `JMP sub_EC09`, which pops Y, X and A before its RTI.
    if not (os.getenv("PP2_NO_STAGE_HOOK") or os.getenv("PP2_HOOK_PALETTE")):
        _at = int(os.environ.get("PP2_HOOKAT", "0xF16C"), 16)
        _exp = [0x3D, 0xDF] if _at == 0xF15E else [0x4F, 0xDC]
        p.put(_at, [mirror_stage_addr & 0xFF, mirror_stage_addr >> 8], expect=_exp)
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
