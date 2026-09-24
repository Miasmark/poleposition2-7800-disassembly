#!/usr/bin/env python3
"""
Pole Position II: incorporate KevinMos3 and Defender_2600's car-sprite redraw.

    python patches/graphics_hack.py --list
    python patches/graphics_hack.py --build -o pp2-hires-car.a78
    python patches/graphics_hack.py --bundle          (writes dist/pp2-graphics-hack.abp)

## Credit

The sprite redraw this applies is not this project's work. It is
**"Pole Position II Graphics Hack"** by **KevinMos3** and **Defender_2600**,
published 2014-04-12 on the AtariAge forums, which redraws the player car
with more shading and detail than the original two-colour sprite. All credit
for the artwork is theirs; nothing here claims otherwise.

What this file contributes is narrower: it locates exactly which bytes their
release changed (two sprite objects -- a 26-line main pose at $8B10 and a
6-line companion piece at $AAE8, both width 8, palette 6 -- plus two palette
registers recolouring that same palette, $EDE3/$EDE7), so that the change can
be applied on its own, as a normal `.abp` option, independent of anything
else in their release (their build also carries its own new cartridge
signature and a changed header title, neither of which is this option's
concern -- see `docs/FINDINGS.md`, "the cartridge signature", for why
signing is deliberately out of scope for a build meant to replay against an
existing recording).

## Ships their new bytes, not a copy of the original hack

`bps.create()` below necessarily encodes the *replacement* bytes as literals
-- there is no CRC32-only way to describe "draw these specific new pixels"
-- so this option's BPS carries someone else's creative work verbatim. That
is the point of asking to include it with credit, not an oversight.

The 159 bytes below were extracted by diffing the hack's own release against
a pristine dump, header and cartridge signature excluded (both differ for
reasons that have nothing to do with the sprite -- their build re-signed the
cartridge, and changed the header's title string). Nothing else from their
release is reproduced here: not their signature, not their header, not any
byte outside what actually draws the car.

## In the VS build

This file's bundle is for the retail game, and does not stack with Pole
Position II VS: $EDE3/$EDE7 sit in the scanline injection VS reclaims. VS
carries the redraw itself (patches/splitscreen.py, HIRES_CAR;
dist/pp2-vs.abp, option vs-hires-car). It takes CAR_SPRITE_EDITS from here
and sets the two palette values where VS sets palette 6. Player 2's car gets
gold highlights, so the two players are still told apart.
"""
import argparse
import hashlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLKIT_TOOLS = os.path.join(ROOT, "..", "a7800-toolkit-local", "tools")
sys.path.insert(0, TOOLKIT_TOOLS)

HDR = 128
BASE = 0x8000
ROM_SIZE = 32768

ROM_NAME = "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"
SOURCES = [
    os.environ.get("PP2_ROM", ""),
    os.path.join(ROOT, ROM_NAME),
    os.path.expanduser(os.path.join("~", "Documents", "Atari 7800",
                                    "Rom Library", ROM_NAME)),
]
DISTDIR = os.path.join(ROOT, "dist")


class Patcher(object):
    """Byte edits against a headerless ROM, each checked before it is made."""

    def __init__(self, rom, base=BASE):
        self.rom = bytearray(rom)
        self.base = base
        self.writes = []

    def off(self, addr):
        return addr - self.base

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


# Extracted from KevinMos3 and Defender_2600's "Pole Position II Graphics
# Hack" (AtariAge forums, 2014-04-12), by diffing their release against a
# pristine dump and keeping only what actually draws the car -- their
# release's own re-signed cartridge signature and changed header title are
# excluded, as neither is this sprite. (address, original bytes, their bytes).
CAR_SPRITE_EDITS = [
    (0x8B13, bytes.fromhex('3ff8'), bytes.fromhex('0000')),
    (0x8C12, bytes.fromhex('0ffaa7f0'), bytes.fromhex('03c003c0')),
    (0x8D13, bytes.fromhex('f9e7'), bytes.fromhex('daa7')),
    (0x8E11, bytes.fromhex('fffefae7'), bytes.fromhex('fcffd967')),
    (0x8E16, bytes.fromhex('ff'), bytes.fromhex('3f')),
    (0x8F12, bytes.fromhex('fffbe6bf'), bytes.fromhex('dfd967f7')),
    (0x9012, bytes.fromhex('fffbe6ff'), bytes.fromhex('dfdbe7f7')),
    (0x9111, bytes.fromhex('feaffaa7eb'), bytes.fromhex('ffd7dbe7d7')),
    (0x9212, bytes.fromhex('ffb557bf'), bytes.fromhex('d5d96757')),
    (0x9311, bytes.fromhex('feaabfaaaabf'), bytes.fromhex('ffffdaa7ffff')),
    (0x9411, bytes.fromhex('fe96aa5556bf'), bytes.fromhex('ffffdaa7ffff')),
    (0x9511, bytes.fromhex('ed556a95557fec'), bytes.fromhex('ffd5dff757fffc')),
    (0x9610, bytes.fromhex('3a9d9557d5567a9c'), bytes.fromhex('3bafb5deb75efaec')),
    (0x9711, bytes.fromhex('fd'), bytes.fromhex('ff')),
    (0x9713, bytes.fromhex('ffff'), bytes.fromhex('febf')),
    (0x9716, bytes.fromhex('7f'), bytes.fromhex('ff')),
    (0x9811, bytes.fromhex('f5bffffffe5f'), bytes.fromhex('f1955695564f')),
    (0x9911, bytes.fromhex('a5bffffffe55'), bytes.fromhex('059555555650')),
    (0x9A11, bytes.fromhex('a5aaaaaaaa'), bytes.fromhex('5595555556')),
    (0x9B11, bytes.fromhex('2997ffffd654'), bytes.fromhex('35aaaaaaaa5c')),
    (0x9C11, bytes.fromhex('3957bebf95'), bytes.fromhex('3595d55756')),
    (0x9D11, bytes.fromhex('3f01fa'), bytes.fromhex('3d55b5')),
    (0x9D15, bytes.fromhex('40fc'), bytes.fromhex('557c')),
    (0x9E11, bytes.fromhex('2f00d95700f8'), bytes.fromhex('3f55baae55fc')),
    (0x9F11, bytes.fromhex('0000c9530000'), bytes.fromhex('3ff5baae5ffc')),
    (0xA011, bytes.fromhex('0000c9530000'), bytes.fromhex('3b0f9eb6f0ec')),
    (0xA111, bytes.fromhex('00'), bytes.fromhex('3f')),
    (0xA113, bytes.fromhex('c143'), bytes.fromhex('6eb9')),
    (0xA116, bytes.fromhex('00'), bytes.fromhex('fc')),
    (0xA213, bytes.fromhex('b00d'), bytes.fromhex('0d70')),
    (0xA313, bytes.fromhex('2ff4'), bytes.fromhex('0ff0')),
    (0xA413, bytes.fromhex('0a90'), bytes.fromhex('03c0')),
    (0xAAE9, bytes.fromhex('feaffaa7eb'), bytes.fromhex('ffd7dbe7d7')),
    (0xABEA, bytes.fromhex('ffb557bf'), bytes.fromhex('d5d96757')),
    (0xACE9, bytes.fromhex('feaabfaaaabf'), bytes.fromhex('ffffdaa7ffff')),
    (0xADE9, bytes.fromhex('fe96aa5556bf'), bytes.fromhex('ffffdaa7ffff')),
    (0xAEE8, bytes.fromhex('3fed556a95557f'), bytes.fromhex('3bafd5dff757fa')),
    (0xAFE9, bytes.fromhex('ed9557d5567fec'), bytes.fromhex('ffb5deb75efffc')),
    # P6C1 / P6C2: the car's palette, recoloured for the redrawn shading.
    (0xEDE3, bytes.fromhex('2f'), bytes.fromhex('93')),
    (0xEDE7, bytes.fromhex('26'), bytes.fromhex('0d')),
]


def fix_hires_car(p):
    """Apply KevinMos3 and Defender_2600's car-sprite redraw.

    Two objects, both width 8, palette 6, confirmed live (not guessed) by
    walking the display list against run-01.inp: a 26-line main pose based
    at $8B10 (zones use it as five 6-line bands, $8B10/$9110/.../$9D10/$A310,
    each 6 pages -- i.e. 6 scanlines -- apart) and a 6-line companion piece
    at $AAE8. Rendered with `a7800-toolkit`'s gfx.py before and after: same
    silhouette, visibly more shading and cockpit detail in the redraw.
    """
    for addr, expect, new in CAR_SPRITE_EDITS:
        p.put(addr, new, expect=expect)
    return p


FIXES = [
    {"id": "hires-car", "fn": fix_hires_car,
     "title": "Higher-detail player car sprite",
     "note": "Sprite redraw by KevinMos3 and Defender_2600 (AtariAge "
             "forums, \"Pole Position II Graphics Hack\", 2014-04-12). "
             "Incorporated here with credit; the artwork is theirs."},
]


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
    import zlib
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
            if len(set(chunk)) < 32:
                continue
            out.append({"addr": "0x%04X" % (at + BASE), "length": size,
                        "crc32": "0x%08X" % (zlib.crc32(chunk) & 0xFFFFFFFF)})
            break
    if len(out) < n:
        raise SystemExit("could not find %d usable anchors" % n)
    return out


def vs_split_ranges():
    """The retail bytes the VS build (patches/splitscreen.py) changes, as
    sections for pick_anchors to avoid: so this bundle still recognises a VS
    cartridge, and a clash between the two is reported as the section it is
    rather than as "not the cartridge". The signature bytes are included, as
    any signed build rewrites them. Empty if the VS generator is not there."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import splitscreen as S
    except ImportError:
        return {}
    _src, _hdr, rom = S.load_source()
    p = S.Patcher(bytes(rom))
    pristine = bytes(p.rom)
    for fix in S.FIXES:
        fix["fn"](p)
    changed = {a for addr, data in p.writes for a in range(addr, addr + len(data))
               if a >= BASE and pristine[a - S.OUT_BASE] != p.rom[a - S.OUT_BASE]}
    changed.update(range(0xFF80, 0xFFF8))               # the signature
    return {"vs_%04X" % at: {"addr": "0x%04X" % at, "length": n}
            for at, n in _runs(changed, gap=4)}


def build(out_path, sign=False):
    """Apply the fix directly. Unsigned by default -- see
    docs/FINDINGS.md, "the cartridge signature", for why that matters if
    you intend to test the result against an existing .inp recording."""
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
    anchors = pick_anchors(rom, dict(sections, **vs_split_ranges()))

    touched_ids = sorted(sections, key=lambda sid: int(sections[sid]["addr"], 16))
    before, after = bytearray(), bytearray()
    for sid in touched_ids:
        at, n = int(sections[sid]["addr"], 16), sections[sid]["length"]
        before += rom[at - BASE:at - BASE + n]
        after += p.rom[at - BASE:at - BASE + n]

    member = "p/hires-car.bps"
    files = {member: bps.create(bytes(before), bytes(after))}
    option = {
        "id": "hires-car",
        "title": FIXES[0]["title"],
        "note": FIXES[0]["note"],
        "patches": [{"sections": touched_ids, "bps": member,
                     "before": "0x%08X" % patchset.crc32(bytes(before))}],
    }

    manifest = {
        "format": patchset.FORMAT,
        "name": "Pole Position II: higher-detail car sprite",
        "what": "Incorporates KevinMos3 and Defender_2600's car-sprite "
                "redraw (AtariAge forums, \"Pole Position II Graphics "
                "Hack\", 2014-04-12) as a standalone, combinable option. "
                "Credit for the artwork is theirs; see patches/"
                "graphics_hack.py for how it was extracted.",
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
    out_path = out_path or os.path.join(DISTDIR, "pp2-graphics-hack.abp")
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
          "--rom \"%s\" --with hires-car --out pp2-hires-car.a78" % (out_path, ROM_NAME))
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.strip().split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--sign", action="store_true",
                    help="with --build: sign the result (not for testing "
                         "against an existing .inp recording)")
    ap.add_argument("--bundle", nargs="?", const="", metavar="OUT")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    if args.bundle is not None:
        return build_bundle(args.bundle or None)
    if args.build:
        if not args.out:
            raise SystemExit("--build needs -o (where to write the playable ROM)")
        return build(args.out, sign=args.sign)
    for f in FIXES:
        print("  %-12s %s" % (f["id"], f["title"]))
        print("               %s" % f["note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
