"""Recompute player 2's walk from each recorded snapshot and compare.

    python tools/walk-check.py <output of tools/probe-walk-check.lua>

The probe needs W_DONE (P2GDone's address in the build) and W_OUT."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "patches"))
import splitscreen as S
T = S.p2_walk_tables()
def walk(seg, lo, hi, tlen, mem):
    rd = lambda a: mem[a - 0x1800]
    W = (0x47 + lo + (hi << 8)) & 0xFFFF   # CLC / ADC lo, then ADC hi with the carry
    v = p = 0
    out = [None] * 13
    for X in range(13):
        count = 32
        while True:
            lo_ = (W & 0xFF) - T["P2ZLo"][X]
            borrow = 1 if lo_ < 0 else 0
            h = ((W >> 8) - T["P2ZHi"][X] - borrow) & 0xFF
            if not (h & 0x80):
                break
            seg = (seg + 1) & 0xFF
            if seg == tlen: seg = 0
            W = (W + (rd(0x185A + seg) << 8 | rd(0x1800 + seg))) & 0xFFFF
            count -= 1
            if count == 0: break
        c = rd(0x1900 + seg); c = (c - 256) if c >= 128 else c
        c = (c << T["P2Shift"][X]) & 0xFFFF
        for _ in range(3 if X == 0 else 6):
            v = (v + c) & 0xFFFF
            p = (p + v) & 0xFFFF
        out[T["P2Band"][X]] = ((p >> 8) + T["P2Base"][X]) & 0xFF
    return out
bad = tot = 0
for line in open(sys.argv[1]):
    if line.startswith('1 '): continue   # frame 1: RAM before any race, not a walk of real state
    f, snap, band, tl, m = line.split()
    b = bytes.fromhex
    sn = b(snap); got = list(b(band))
    exp = walk(sn[0], sn[1], sn[2], int(tl, 16), b(m))
    tot += 1
    if exp != got:
        bad += 1
        if bad <= 3: print("f%s snap %s\n  got %s\n  exp %s" % (f, snap, got, exp))
print("%d walks checked, %d mismatched" % (tot, bad))
