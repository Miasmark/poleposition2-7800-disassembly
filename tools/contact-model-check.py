"""contact-model-check.py -- player 1's lateral contact test (rom:C8C1-C8EC, with rom:E676) modelled
byte for byte, player 2's (P2ClOne) as written, and:

1. the model against every player 1 test logged live (model.lua): same |value|
   and same contact decision;
2. player 2's formula against every player 2 test logged live;
3. exhaustively, player 1's arithmetic against player 2's formula for the same
   position (player 2's lateral = -PlayerX): every car and puddle lane, every
   row a contact can be on, every road-curve value, every lateral.
"""
import sys

import os
ROM = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"), "rb").read()[128:]
r = lambda a: ROM[a - 0x8000]
COEF = [r(0xE80F + l) | r(0xA8A1 + l) << 8 for l in range(0x30)]


def hi_proj(lane, m):
    c = COEF[lane]
    neg = c & 0x8000
    if neg:
        c = (-c) & 0xFFFF
    h = ((c * m) & 0xFFFF) >> 8
    return (-h) & 0xFF if neg else h


def p1_abs(lane, row, curve, px):
    h = hi_proj(lane, row + 4)
    s = h + curve                       # CLC; ADC curve
    c1 = s >> 8
    a = (s & 0xFF) + 0x4F + c1          # ADC #$4F (carry kept)
    a &= 0xFF
    # SEC; SBC curve; SBC #$40; SBC PlayerX -- one borrow chain
    carry = 1
    for sub in (curve, 0x40, px & 0xFF):
        v = a - sub - (1 - carry)
        carry = 1 if v >= 0 else 0
        a = v & 0xFF
    if a & 0x80:
        a = (-a) & 0xFF
    return a


def p1_hit(absv, m4e):
    thr = 0x1A if m4e >= 0x4B else 0x1E
    return ((absv - thr) & 0x80) != 0


def p2_abs(lane, m, lat, curve):
    # player 2 runs rom:E6D0/C8CD's own sequence with -P2_LATERAL for PlayerX
    s8 = lat - 256 if lat >= 128 else lat
    return p1_abs(lane, m - 4, curve, (-s8) & 0xFF)


def p2_hit(absv, zl, zh):
    thr = 0x1A if (zh == 0 and zl >= 0x4B) else 0x1E
    return absv < thr


def kv(line):
    return dict(x.split("=") for x in line.split()[2:])


for fn in sys.argv[1:]:
    lines = [l.strip() for l in open(fn)]
    hits1 = {}; hits2 = {}
    for l in lines:
        if l.startswith("P1HIT") or l.startswith("P2HIT"):
            f = int(l.split()[1][1:]); d = kv(l)
            (hits1 if l.startswith("P1") else hits2).setdefault(f, set()).add(int(d["slot"]))
    n1 = ok1 = d1 = 0; n2 = ok2 = d2 = 0; bad = []
    for l in lines:
        if l.startswith("P1 "):
            d = kv(l); f = int(l.split()[1][1:])
            a = p1_abs(int(d["lane"]), int(d["row"]), int(d["curve"]), int(d["px"]))
            n1 += 1; ok1 += a == int(d["abs"])
            hit = p1_hit(int(d["abs"]), int(d["m4e"]))
            live = any(int(d["slot"]) in hits1.get(g, ()) for g in (f, f + 1))   # a frame can end between the test and its hit
            d1 += hit == live
            if a != int(d["abs"]) and len(bad) < 4:
                bad.append(("P1", l, "model", a))
        elif l.startswith("P2 "):
            d = kv(l); f = int(l.split()[1][1:])
            a = p2_abs(int(d["lane"]), int(d["m"]), int(d["lat"]), int(d["curve"]))
            n2 += 1; ok2 += a == int(d["abs"])
            hit = p2_hit(int(d["abs"]), int(d["zl"]), int(d["zh"]))
            live = any(int(d["slot"]) in hits2.get(g, ()) for g in (f, f + 1))
            d2 += hit == live
            if a != int(d["abs"]) and len(bad) < 8:
                bad.append(("P2", l, "model", a))
    print(fn.split("/")[-1], ": player 1 %d tests, |value| %d match, decision %d match; player 2 %d tests, |value| %d match, decision %d match" % (n1, ok1, d1, n2, ok2, d2))
    for b in bad:
        print("   ", b)

# exhaustive: player 1's arithmetic vs player 2's formula at the same place
lanes = list(range(0x01, 0x21))              # cars 1..$20 (puddles 15..18 among them)
rows = range(0x40, 0x4E)
tot = diff = 0; ex = {}
for lane in lanes:
    for row in rows:
        m = row + 4
        for px in range(-104, 105):
            for curve in range(256):
                b2 = p2_abs(lane, m, (-px) & 0xFF, curve)
                b1 = p1_abs(lane, row, curve, px & 0xFF)
                tot += 1
                if b1 != b2:
                    diff += 1
                    k = (b1 - b2) & 0xFF
                    ex.setdefault(k, (lane, row, px, curve, b1, b2))
print("exhaustive |value|: %d cases, %d differ" % (tot, diff))
for k, v in sorted(ex.items()):
    print("   differ by %d, e.g. lane %d row %d x %d curve %d: rom %d, player 2 %d" % (((k if k < 128 else k - 256),) + v))
