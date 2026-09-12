#!/usr/bin/env python3
"""
Build a two-viewport (split-screen) Pole Position II from your own cartridge.

    python patches/splitscreen.py "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78" -o pp2-split.a78

This ships no cartridge data. It is a list of addresses and replacement bytes,
every one of which is checked against the byte it expects to find first, so a
different dump fails loudly instead of producing a quietly broken ROM.

## What it does

Rearranges the display list so the screen reads as split-screen:

    zone  0        16 lines   blank top margin
    zones 1-11     67         player 2's view (ten road bands + a gap)
    zones 12-14    21         HUD, three rows -- the centre divider
    zones 15-17    15         blank
    zones 18-19    20         horizon decoration
    zones 20-32    78         player 1's road (untouched)
    zones 33-34    32         blank

The line total before the road is unchanged at 139, so player 1's half and
everything below it renders exactly as it always did.

## What it is not, yet

Player 2's view is a *mirror*: its bands point at the same RAM sub-lists that
player 1's road uses, so it shows player 1's road, tracking the same curve and
the same stripe animation for free. It is not an independent camera, and it
stair-steps where the real road is smooth. The road's smoothness comes from a
display interrupt rewriting each band's x byte between scanlines as the beam
draws it, which a view rendered 80 scanlines earlier cannot borrow -- see the
"per scanline" section of docs/FINDINGS.md. Giving player 2 a real camera means
writing its own injection pass; that is the next piece of work, and the first
that has to be written rather than repointed.

Known rough edges: the three HUD rows sit flush against each other (their
original spacing came from gap zones that no longer sit between them), and
anything else drawing into the old top-of-screen layout -- the qualifying
banner, the results screen -- has not been re-placed yet.
"""
import argparse
import sys

ZONE_TABLE = 0xBC7E           # boot-time display-list template, copied to $2200 by sub_F171


def zone(n):                  # each zone selector is three bytes: flags/lines, dl hi, dl lo
    return ZONE_TABLE + n * 3


# Road band sub-lists in RAM, far-to-near. The curve pipeline rewrites these
# every frame, which is why pointing a second view at them is nearly free.
ROAD_BANDS = [0x2300, 0x2326, 0x234C, 0x2372, 0x2398,
              0x23BE, 0x2400, 0x2426, 0x244C, 0x246E]

# Zones carrying a display-interrupt bit. The DLI chain is positional -- which
# handler fires depends on which zone ended -- so bit 7 must stay put even when
# a zone's contents change.
DLI_ZONES = {0, 7, 11, 15, 19}

# Lines per zone in the new layout, for the budget check below.
LINE_BUDGET = {0: 16, 1: 7, 12: 7, 13: 7, 14: 7, 15: 3, 16: 6, 17: 6, 18: 10, 19: 10}
for _z in range(2, 12):
    LINE_BUDGET[_z] = 6


def build_edits():
    """(address, expected_original_bytes, replacement_bytes, why)."""
    e = []

    # -- HUD moves to zones 12/13/14 -----------------------------------------
    # Those three are not served by the boot template at all: they are rewritten
    # at run time from these two tables, by the routines that drive the
    # "POLE POSITION!" banner, whichever ran last. Patching the template alone
    # leaves them reverting mid-race, so the HUD has to live here -- which
    # co-locates banner and HUD, as the layout wants anyway.
    hud_rows = [0x06, 0x1D, 0x1C,     # row 1: TOP / SCORE
                0x06, 0x1D, 0x28,     # row 2: UNIT / LAP
                0x06, 0x1D, 0x34]     # row 3: SPEED / HI-LO
    e.append((0xA6BB,
              [0x06, 0x1D, 0x09, 0x02, 0x24, 0xF6, 0x06, 0x1D, 0x15],
              hud_rows, "banner table A -> HUD rows"))
    e.append((0xA6CD,
              [0x07, 0x1C, 0xAB, 0x07, 0x1C, 0xBD, 0x00, 0x24, 0xF6],
              hud_rows, "banner table B -> HUD rows"))

    # -- player 2's view: a gap, then ten bands across zones 2..11 ------------
    e.append((zone(1), [0x09, 0x24, 0xF6], [0x06, 0x24, 0xF6],
              "zone 1: blank gap, 7 lines"))

    originals = {2: [0x06, 0x1D, 0x1C], 3: [0x02, 0x24, 0xF6],
                 4: [0x06, 0x1D, 0x28], 5: [0x02, 0x24, 0xF6],
                 6: [0x06, 0x1D, 0x34], 7: [0x82, 0x24, 0xF6],
                 8: [0x07, 0x22, 0xC7], 9: [0x07, 0x22, 0xD1],
                 10: [0x07, 0x22, 0xDB], 11: [0x82, 0x24, 0xF6]}
    for i, dl in enumerate(ROAD_BANDS):
        z = 2 + i
        flags = 0x05 | (0x80 if z in DLI_ZONES else 0x00)   # 6 lines, DLI bit preserved
        e.append((zone(z), originals[z], [flags, dl >> 8, dl & 0xFF],
                  "zone %d: view band -> road sub-list $%04X" % (z, dl)))

    # -- below the HUD: blank, sized to keep the road starting at line 139 ----
    e.append((zone(16), [0x07, 0x22, 0xE1], [0x05, 0x24, 0xF6], "zone 16: blank, 6 lines"))
    e.append((zone(17), [0x07, 0x22, 0xEB], [0x05, 0x24, 0xF6], "zone 17: blank, 6 lines"))

    # -- read mode has to follow the layout ----------------------------------
    # The HUD's text objects are character mode and need CTRL read mode 3; both
    # road views need mode 0. Wrong either way and the failure is not obvious:
    # the HUD garbles, or road bands decode into a sawtooth-edged wrong shape.
    # DLI_ECA1's tail governs zones 1+, so it flips to mode 0 for player 2.
    # Zone 11's DLI already routes through sub_EC67 (mode 3) for the HUD band,
    # and zone 15's already restores mode 0 below -- both left exactly as they
    # are, and both load-bearing.
    e.append((0xED1E, [0x09, 0x03], [0x29, 0xFC],
              "DLI_ECA1 tail: ORA #$03 -> AND #$FC (zones 1+ read mode 0)"))

    # -- colour ---------------------------------------------------------------
    # Pixel value 0 is transparent and shows BACKGRND, so player 2's view needs
    # the road's ground colour behind it. On sky, every transparent pixel in the
    # road graphics shows blue and the edges read completely wrong.
    e.append((0xECA9, [0x89], [0x1B], "BACKGRND: sky -> road ground"))

    # Road objects declare palettes 0 and 1, alternating per frame -- that flip
    # is what animates the rumble strips and centreline. Both palettes must
    # match the road's, or every other frame renders in unrelated colours.
    e.append((0xECBF, [0x38], [0x0F], "P0C1 -> road value"))
    e.append((0xECC3, [0x3C], [0x0F], "P0C2 -> road value"))
    e.append((0xECCB, [0x24], [0x34], "P1C1 -> road value"))
    e.append((0xECC7, [0x28], [0x04], "P1C2 -> road value"))
    e.append((0xECB5, [0x80], [0x04], "shared C3 load -> road value"))
    return e


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.strip().split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("rom", help="your own Pole Position II dump (.a78 or headerless)")
    ap.add_argument("-o", "--out", help="where to write the patched ROM")
    ap.add_argument("--check", action="store_true",
                    help="verify the dump matches and report, without writing")
    args = ap.parse_args()

    data = bytearray(open(args.rom, "rb").read())
    header = len(data) % 1024        # .a78 carries a 128-byte header; a raw dump does not
    if header not in (0, 128) or len(data) - header != 32768:
        raise SystemExit("unexpected size %d: not a 32K Pole Position II dump" % len(data))

    def off(addr):
        return header + (addr - 0x8000)

    edits = build_edits()

    bad = []
    for addr, want, _new, why in edits:
        got = list(data[off(addr):off(addr) + len(want)])
        if got != want:
            bad.append("  $%04X  expected %s  found %s   (%s)"
                       % (addr, bytes(want).hex(), bytes(got).hex(), why))
    if bad:
        sys.stderr.write("This dump is not the one these edits were derived from:\n")
        sys.stderr.write("\n".join(bad) + "\n")
        return 1

    total = sum(LINE_BUDGET.values())
    if total != 139:
        raise SystemExit("internal error: zones 0-19 total %d lines, must be 139 "
                         "or player 1's view shifts" % total)

    changed = 0
    for addr, _want, new, _why in edits:
        for i, b in enumerate(new):
            if data[off(addr) + i] != b:
                changed += 1
            data[off(addr) + i] = b

    print("source verified; zones 0-19 total %d lines (player 1's view unmoved)" % total)
    print("%d edits, %d bytes changed" % (len(edits), changed))
    if args.check:
        print("--check given, nothing written")
        return 0
    if not args.out:
        raise SystemExit("give -o to write the patched ROM (or --check to just verify)")
    open(args.out, "wb").write(data)
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
