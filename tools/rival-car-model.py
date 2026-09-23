"""Reproduce the game's drawable-entry list for traffic cars (kind 0).

Each captured line holds, at the moment sub_E286 returns: zero page $40-$FF,
RAM $1900-$1BFF and $1C00-$1CFF. For every world object the list builder
visits, this replays sub_E3E0, sub_E475, sub_E461, sub_E54B/E676/E4F1,
sub_E5C7 and sub_E60F in Python, and compares the car entries with what the
game itself wrote.
"""
import sys

import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROM = open(os.path.join(HERE, "..", "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"), "rb").read()[128:]
rom = lambda a: ROM[a - 0x8000]
s8 = lambda v: v - 256 if v >= 128 else v


class Snap:
    def __init__(self, line):
        f, zp, ram, ram2 = line.split()
        self.f = int(f)
        self.zp = bytes.fromhex(zp)            # $40-$FF
        self.ram = bytes.fromhex(ram)          # $1900-$1BFF
        self.ram2 = bytes.fromhex(ram2)        # $1C00-$1CFF

    def __call__(self, a):
        if 0x40 <= a <= 0xFF: return self.zp[a - 0x40]
        if 0x1900 <= a <= 0x1BFF: return self.ram[a - 0x1900]
        if 0x1C00 <= a <= 0x1CFF: return self.ram2[a - 0x1C00]
        if a >= 0x8000: return rom(a)
        raise KeyError(hex(a))


def zrow(z):
    """sub_E3CD: first row from $4D down whose tabled distance exceeds z."""
    for x in range(0x4D, -1, -1):
        t = rom(0xEB56 + x) | rom(0xEAB9 + x) << 8
        if (z - t) & 0x8000:
            return x
    return 0xFF


def e676(m, lat, row):
    """sub_E676: screen x of lateral index `lat` at `row`."""
    c = rom(0xE80F + lat) | rom(0xA8A1 + lat) << 8
    neg = c & 0x8000
    if neg:
        c = (-c) & 0xFFFF
    mult = row + 4                           # INC $4B before the loop
    prod = (c * mult) & 0xFFFF
    hi = prod >> 8
    if neg:
        hi = (-hi) & 0xFF
    t = hi + m(0x1A2E + row + 3)             # CLC / ADC road
    return ((t & 0xFF) + 0x4F + (t >> 8)) & 0xFF   # ADC #$4F keeps that carry


def car_entry(m, slot):
    """Replay the list builder's calls for one kind-0 object. Returns a dict
    of what it writes, or None if the object is not projected."""
    z = (m(0x19C4 + slot) | m(0x19D4 + slot) << 8) + 6
    z &= 0xFFFF
    if z & 0x8000:
        return None                           # behind: the $4F path, not cars ahead
    row = zrow(z)
    if row == 0xFF:
        return None
    size = rom(0xBA7E + row)
    kind = m(0x19B4 + slot) & 7
    if kind != 0:
        return None
    top = row
    bottom = top - rom(0xACCA + size)         # E493, $4F zero
    if bottom < 0:
        bottom = 0
    lat = m(0x1A00 + slot)
    x = e676(m, lat, row)                     # E54B -> $4D
    lo, hi, pw, cls = sprite(m, slot, x, lat, row, size)
    return dict(top=top, bottom=bottom, size=size, lat=lat, x=x, row=row, lo=lo, hi=hi, pw=pw, cls=cls)


def sprite(m, slot, x, lat, row, size):
    """sub_E4F1 (viewing angle -> sprite), sub_E5C7 (palette/width) and
    sub_E461 (slot class) for a kind-0 object, carries and all."""
    t = x + lat                                # CLC / ADC $1A00,Y
    c = t >> 8; t &= 0xFF
    t = t + 0x1F + c                           # ADC #$1F
    c = t >> 8; t &= 0xFF
    for _ in range(3):                         # LSR x3, carry = bit out
        c = t & 1; t >>= 1
    t = t - 0x0E - (1 - c)                     # SBC #$0E
    c = 0 if t < 0 else 1; t &= 0xFF
    t = t + m(0x1A31 + row) + c                # ADC $1A31,Y
    c = t >> 8; t &= 0xFF
    t = t - m(0x1A30 + row) - (1 - c)          # SBC $1A30,Y
    t &= 0xFF
    st = t - 256 if t >= 128 else t            # the CMP/BMI chain is signed
    y = 0 if st < -8 else 1 if st < -2 else 2 if st < 2 else 3 if st < 8 else 4
    ptr = rom(0xA295 + size) | rom(0xA29F + size) << 8
    rd = lambda a: rom(a) if a >= 0x8000 else m(a)
    lo = rd(ptr + 2 * y)
    hi = rd(ptr + 2 * y + 1)
    pw = (m(0x19B4 + slot) & 0xE0) | rom(0xABCA + size)
    cls = rom(0xB0ED + 0)
    return lo, hi, pw, cls


SP = [0, 0]; SPB = []


def main(path):
    tot = ok_rows = ok_x = 0
    bad = []
    for line in open(path):
        m = Snap(line)
        B0, B1 = s8(m(0xB0)), s8(m(0xB1))
        k = 1
        X = B0
        while X >= B1 and X >= 0:
            slot = m(0x19A4 + X)
            e = car_entry(m, slot)
            kind = m(0x19B4 + slot) & 7
            if e is not None:
                tot += 1
                got = dict(top=m(0x1A94 + k), bottom=m(0x1AA9 + k), x=m(0x1AE8 + k),
                           lo=m(0x1AD3 + k), hi=m(0x1ABE + k), pw=m(0x1BEA + k), cls=m(0x1A7F + k))
                SP[0] += 1
                SP[1] += all(got[q] == e[q] for q in ("lo", "hi", "pw", "cls"))
                if not all(got[q] == e[q] for q in ("lo", "hi", "pw", "cls")) and len(SPB) < 4:
                    SPB.append((m.f, slot, {q: e[q] for q in ("lo","hi","pw","cls","x","lat","row")},
                                {q: got[q] for q in ("lo","hi","pw","cls")}))
                r = (got["top"] == e["top"] and got["bottom"] == e["bottom"])
                ok_rows += r
                ok_x += got["x"] == e["x"] or got["x"] == 0xA1
                if not r or not (got["x"] == e["x"] or got["x"] == 0xA1):
                    bad.append((m.f, slot, e, got))
            # entry count advance: projected objects take one entry, signs two
            z = ((m(0x19C4 + slot) | m(0x19D4 + slot) << 8) + 6) & 0xFFFF
            if not (z & 0x8000) and zrow(z) != 0xFF:
                k += 2 if kind == 1 else 1
            X -= 1
    print("car entries %d: rows match %d, x match %d" % (tot, ok_rows, ok_x))
    print("sprite/palette/class match %d of %d" % (SP[1], SP[0]))
    for b in SPB: print("  f%d slot %d model %s game %s" % b)


main(sys.argv[1])
