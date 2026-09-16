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
this project's own work, not a copy of anything. If a future edit ever needs
to relocate or repeat existing ROM code verbatim rather than write new bytes
next to it, that is the case to stop and ask about before bundling it -- nothing
here does that yet.

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


# Road band sub-lists in RAM, far-to-near. The curve pipeline (docs/FINDINGS.md,
# "the last piece") rewrites these every frame, which is why pointing a second
# view at them tracks the road's curve at no extra cost.
ROAD_BANDS = [0x2300, 0x2326, 0x234C, 0x2372, 0x2398,
              0x23BE, 0x2400, 0x2426, 0x244C, 0x246E]

# Zones carrying a display-interrupt bit. The DLI chain is positional -- which
# handler fires depends on which zone ended -- so bit 7 must survive even when
# a zone's contents change.
DLI_ZONES = {0, 7, 11, 15, 19}


def fix_mirror_split(p):
    """Relocate the HUD to the centre; give player 2's view zones 1-11.

    Ported from the hand-verified edits built up over several live sessions
    (docs/FINDINGS.md, "Phase 1"). Nothing here is new code -- every edit
    replaces existing bytes at a fixed address; nothing is relocated and
    nothing needs a float.
    """
    # -- HUD moves to zones 12/13/14 -----------------------------------------
    # Those three are not served by the boot template at all: they are
    # rewritten at run time from these two tables, by the routines that drive
    # the "POLE POSITION!" banner, whichever ran last. Patching the template
    # alone leaves them reverting mid-race, so the HUD has to live here --
    # which co-locates banner and HUD, as the layout wants anyway.
    hud_rows = [0x06, 0x1D, 0x1C,     # row 1: TOP / SCORE
                0x06, 0x1D, 0x28,     # row 2: UNIT / LAP
                0x06, 0x1D, 0x34]     # row 3: SPEED / HI-LO
    p.put(0xA6BB, hud_rows,
          expect=[0x06, 0x1D, 0x09, 0x02, 0x24, 0xF6, 0x06, 0x1D, 0x15])
    p.put(0xA6CD, hud_rows,
          expect=[0x07, 0x1C, 0xAB, 0x07, 0x1C, 0xBD, 0x00, 0x24, 0xF6])

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
                "unmoved below.",
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
