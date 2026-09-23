"""Check the ROM's rival-car entries for the two player cars against the model.

Input lines (from implcheck.lua, captured as RivalCars returns to rom:D719):
frame, zero page $40-$FF, RAM $1900-$1BFF, RAM $2700-$27FF.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "patches"))
import splitscreen as S

import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROM = open(os.path.join(HERE, "..", "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"), "rb").read()[128:]
rom = lambda a: ROM[a - 0x8000]
s8 = lambda v: v - 256 if v >= 128 else v
C8 = S.rival_car_tables()[:128]
BASE = S.rival_car_tables()[128:]


def zrow(z):
    for x in range(0x4D, -1, -1):
        t = rom(0xEB56 + x) | rom(0xEAB9 + x) << 8
        if (z - t) & 0x8000:
            return x
    return 0xFF


def coef(w):
    c = 2 * C8[abs(w)]
    c = -c if w < 0 else c
    c = (c - 46) & 0xFFFF
    l8 = (((c >> 8) << 5) & 0xFF) | ((c & 0xFF) >> 3)
    t = (l8 + 0x16) & 0xFF
    lane = 0 if t >= 0x80 else (0x22 if t >= 0x23 else t)
    return c, lane


def mul(c, m):
    neg = c & 0x8000
    mag = (-c) & 0xFFFF if neg else c
    hi = ((mag * m) & 0xFFFF) >> 8
    return (-hi) & 0xFF if neg else hi


def row_of(z):
    if z & 0x8000:
        return None
    z = (z + 6) & 0xFFFF
    if z & 0x8000:
        return None
    r = zrow(z)
    if r == 0xFF:
        return None
    size = rom(0xBA7E + r)
    bot = r - rom(0xACCA + size)
    return r, size, max(bot, 0)


def sprite(x, lane, s1, s0, size):
    t = x + lane; c = t >> 8; t &= 0xFF
    t = t + 0x1F + c; c = t >> 8; t &= 0xFF
    for _ in range(3):
        c = t & 1; t >>= 1
    t = t - 0x0E - (1 - c); c = 0 if t < 0 else 1; t &= 0xFF
    t = t + s1 + c; c = t >> 8; t &= 0xFF
    t = (t - s0 - (1 - c)) & 0xFF
    st = s8(t)
    y = 0 if st < -8 else 1 if st < -2 else 2 if st < 2 else 3 if st < 8 else 4
    ptr = rom(0xA295 + size) | rom(0xA29F + size) << 8
    return rom(ptr + 2 * y), rom(ptr + 2 * y + 1), 0xC0 | rom(0xABCA + size)


tot = [0, 0]; ok = [0, 0]; bad = []
for line in open(sys.argv[1]):
    f, zp, ram, p2 = line.split()
    zp, ram, p2 = bytes.fromhex(zp), bytes.fromhex(ram), bytes.fromhex(p2)
    Z = lambda a: zp[a - 0x40]
    R = lambda a: ram[a - 0x1900]
    Q = lambda a: p2[a - 0x2700]
    gap = Q(0x275C) | Q(0x275D) << 8
    rco = lambda r: R(S.ROW_CURVE_OFFSET + r)
    # player 2's car in player 1's view: the last entry, if it was appended
    w = -s8(Q(0x2702))
    c, lane = coef(w)
    ro = row_of((-gap) & 0xFFFF)
    if ro:
        r, size, bot = ro
        t = mul(c, r + 4) + rco(r)
        x = ((t & 0xFF) + 0x4F + (t >> 8)) & 0xFF
        lo, hi, pw = sprite(x, lane, rco(r), rco(r - 1) if r else R(S.ROW_CURVE_OFFSET - 1), size)
        k = Z(0xDD) - 1
        got = (R(0x1A94 + k), R(0x1AA9 + k), R(0x1AE8 + k), R(0x1AD3 + k), R(0x1ABE + k), R(0x1BEA + k), R(0x1A7F + k))
        exp = (r, bot, x, lo, hi, pw, 4)
        tot[0] += 1; ok[0] += got == exp
        if got != exp and len(bad) < 5: bad.append(("P1 view", f, exp, got))
    # player 1's car in player 2's view: P2E_*
    c, lane = coef(s8(Z(0xD1)))
    ro = row_of(gap)
    if ro and rom(S.ROW_TO_BAND + ro[0]) != 0:
        r, size, bot = ro
        b = rom(S.ROW_TO_BAND + r)
        obj = mul(c, r + 4)
        p2l = s8(Q(0x2702))
        ramp = rom(S.LATERAL_RAMP + abs(p2l)) | rom(S.LATERAL_RAMP_HI + abs(p2l)) << 8
        cam = mul((-ramp) & 0xFFFF if p2l < 0 else ramp, rom(0x9DC3 + b) - 2)
        x = (obj + cam) & 0xFF
        x = (x + ((Q(0x2760 + b) - BASE[b]) & 0xFF)) & 0xFF
        x = (x + 0x4F + S.P2_X_OFFSET) & 0xFF
        lo, hi, pw = sprite(x, lane, 0, 0, size)
        got = tuple(Q(a) for a in (0x2749, 0x274A, 0x274E, 0x274B, 0x274C, 0x274D))
        exp = (r, bot, x, lo, hi, pw)
        tot[1] += 1; ok[1] += got == exp
        if got != exp and len(bad) < 10: bad.append(("P2 view", f, exp, got))
print("player 2's car in player 1's view: %d of %d entries match the model" % (ok[0], tot[0]))
print("player 1's car in player 2's view: %d of %d staged entries match the model" % (ok[1], tot[1]))
for b in bad:
    print("  %s f%s expected %s got %s" % b)
