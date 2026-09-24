#!/usr/bin/env python3
"""The split-screen build's maps, as markdown tables, from the generator itself:
the zone list (screen layout), the RAM it claims and leaves free, the ROM
layout, and every range it changes in the retail 32K. docs/SPLITSCREEN.md's
tables are this script's output; rerun it after a change to the layout.

    python tools/splitscreen-maps.py > build/maps.md

Needs the retail dump and the toolkit, like a build (patches/splitscreen.py).
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "patches"))
import splitscreen as S  # noqa: E402

SRC = open(os.path.join(ROOT, "patches", "splitscreen.py"), encoding="utf-8").read().split("\n")


def zones():
    t = S.dll_template()
    out, line = [], 0
    for i in range(0, len(t), 3):
        b0, hi, lo = t[i:i + 3]
        h = (b0 & 0x0F) + 1
        out.append((i // 3, line, h, bool(b0 & 0x80), (hi << 8) | lo))
        line += h
    return out


def described(addr):
    """First generator line that names this address (rom:XXXX or 0xXXXX)."""
    pats = ("rom:%04X" % addr, "0x%04X" % addr)
    for n, ln in enumerate(SRC, 1):
        if any(p in ln for p in pats):
            return n
    return None


def main():
    lay = S.p2_band_layout()
    names = {S.P2_HOR_DL: "player 2's horizon", S.P2_DECOR_TOP: "player 2's decor (top 8 lines)",
             S.P2_DECOR_DL: "player 2's decor (last 2)", 0x24F6: "blank",
             0x18FA: "player 1's horizon (stock)", 0x1D3B: "player 1's decor (stock)"}
    for b in range(1, 13):
        names[lay[b]["addr"]] = "player 2, band %d" % b
        names[S.ALL_ROAD_BANDS[b]] = "player 1, band %d" % b
    for b in S.SPLIT_BANDS:
        names[S.P1_TOP[b]] = "player 1, band %d top half" % b
        names[S.P2_TOP[b]] = "player 2, band %d top half" % b
    hud = [(S.HUD_ROWS[i + 1] << 8) | S.HUD_ROWS[i + 2] for i in (0, 3, 6)]
    for n, a in zip(("divider row 1 (2UP)", "divider row 2 (1UP)", "divider row 3"), hud):
        names.setdefault(a, n)
    print("### Zone list (%d zones at $%04X, %d lines)\n" % (S.DLL_ZONES, S.DLL_BASE, 249))
    print("| zone | first line | lines | DLI | list | draws |")
    print("|---:|---:|---:|:-:|---|---|")
    for z, line, h, dli, dl in zones():
        print("| %d | %d | %d | %s | $%04X | %s |" % (z, line, h, "x" if dli else "", dl, names.get(dl, "")))

    print("\n### RAM the build claims\n")
    print("| name | from | to | bytes |")
    print("|---|---|---|---:|")
    for n, a, sz in sorted(S.ram_claims() + S.ram_claims_other(), key=lambda r: r[1]):
        print("| %s | $%04X | $%04X | %d |" % (n, a, a + sz - 1, sz))
    print("\n### RAM still free\n")
    print("| from | to | note |")
    print("|---|---|---|")
    for lo, hi, why in S.FREE_RAM:
        print("| $%04X | $%04X | %s |" % (lo, hi, why))

    code = S._ext()[0]
    print("\n### ROM layout (48K, $4000-$FFFF)\n")
    print("| from | to | what |")
    print("|---|---|---|")
    print("| $%04X | $%04X | new code area (`_ext()`), %d bytes; limit $%04X |"
          % (S.EXT_ADDR, S.EXT_ADDR + len(code) - 1, len(code), S.EXT_END))
    for page, lo in S.SMOOTH_COLS:
        print("| $%02X%02X | $%02X%02X | sheared road slices: pages $%02X-$%02X, low bytes $%02X-$FF |"
              % (page, lo, page + 5, 0xFF, page, page + 5, lo))
    print("| $%04X | $%04X | player 2's highlight column: 16 pages, low bytes $00-$27 |"
          % (S.OVL_COL, S.OVL_COL + 0xF27))
    hc = S._hi_code()[0]
    print("| $%04X | $%04X | code kept in the $7E window (TopInit, SmQ, SmPick1), %d of 216 bytes |"
          % (S.HI_CODE, S.HI_CODE + len(hc) - 1, len(hc)))
    hd, ha = S.hi_data(), S.hi_data_addrs()
    for n in sorted(ha, key=lambda k: ha[k]):
        print("| $%04X | $%04X | table %s |" % (ha[n], ha[n] + len(hd[n]) - 1, n))
    print("| $%04X | $%04X | the divider's row lists |" % (S.HUD_DL2, S.HUD_DLB + 1))
    print("| $8000 | $FFFF | the retail 32K, changed in the ranges below |")

    p = S.Patcher(bytes(S.load_source()[2]))
    for fix in S.FIXES:
        fix["fn"](p)
    touched = set()
    for addr, data in p.writes:
        if addr >= 0x8000:
            touched.update(range(addr, addr + len(data)))
    runs = S._runs(touched, gap=1)
    print("\n### Ranges changed in the retail 32K (%d ranges, %d bytes)\n"
          % (len(runs), sum(n for _, n in runs)))
    print("| from | bytes | first described at (patches/splitscreen.py line) |")
    print("|---|---:|---|")
    for at, n in runs:
        ln = described(at)
        print("| $%04X | %d | %s |" % (at, n, ln if ln else ""))


if __name__ == "__main__":
    main()
