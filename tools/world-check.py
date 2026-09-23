"""Checks on world.lua logs (one line per race tick, at RivalCars' return).

signs: player 2's object segment (B0 distance, B2 index) must agree with
       player 1's (A0, A2) through the gap: the same boundary, measured from
       each, differs by exactly the gap.
cars:  every car that vanishes (recycled or deleted) or appears, and where it
       was / is: inside player 1's view (0..1300 ahead of player 1), inside
       player 2's (0..1300 ahead of player 2), or neither.
"""
import collections
import sys

VIEW = (0, 1300)


def s16(v):
    return v - 65536 if v >= 32768 else v


def parse(fn):
    T = {}; rows = []
    for l in open(fn):
        l = l.rstrip("\n")
        if l.startswith("T "):
            p = l.split()
            T[int(p[1])] = [(int(a.split(":")[0], 16), int(a.split(":")[1])) for a in p[2:]]
            continue
        if not l.startswith("f"):
            continue
        h, s = l.split("|")
        p = h.split()
        d = dict(kv.split("=") for kv in p[3:])
        slots = {}
        for e in s.split():
            i, t, z = e.split(":")
            slots[int(i)] = (int(t, 16), s16(int(z)))
        rows.append(dict(f=int(p[0][1:]), st=p[1], trk=int(p[2]), gap=int(d["gap"]),
                         A0=int(d["A0"]), A2=int(d["A2"]), B0=int(d["B0"]), B2=int(d["B2"]),
                         act=int(d["act"]), slots=slots))
    return T, rows


def boundary_gap(r, tab):
    """Distance from player 2's next boundary to player 1's, via the table;
    None if they are more than half a lap apart in segments."""
    n = len(tab)
    a2, b2 = r["A2"], r["B2"]
    k = (a2 - b2) % n
    if k <= n // 2:          # player 1 at or past player 2's segment
        z1 = r["A0"]
        z2 = r["B0"] + sum(tab[(b2 + j) % n][1] for j in range(1, k + 1))
    else:
        k = n - k
        z2 = r["B0"]
        z1 = r["A0"] + sum(tab[(a2 + j) % n][1] for j in range(1, k + 1))
    return z2 - z1


def inview(z):
    return VIEW[0] <= z <= VIEW[1]


for fn in sys.argv[1:]:
    T, rows = parse(fn)
    sg = collections.Counter(); bad = []
    for r in rows:
        if abs(r["gap"]) >= 0x4000:
            sg["gap pinned"] += 1; continue
        d = boundary_gap(r, T[r["trk"]])
        if d == r["gap"]:
            sg["exact"] += 1
        else:
            sg["off"] += 1
            if len(bad) < 5:
                bad.append((r["f"], r["st"], "gap", r["gap"], "via signs", d, "A0/A2", r["A0"], r["A2"], "B0/B2", r["B0"], r["B2"]))
    ev = collections.Counter(); exs = collections.defaultdict(list)
    for a, b in zip(rows, rows[1:]):
        if a["trk"] != b["trk"] or a["st"] != b["st"] or b["f"] - a["f"] > 12:
            continue
        for i, (t, z) in a["slots"].items():
            if t & 7:
                continue
            nb = b["slots"].get(i)
            gone = nb is None or nb[0] == 0xFF or (nb[0] & 7) != 0 or nb[1] - z > 1000
            if not gone:
                continue
            if nb is not None and (nb[0] & 7) == 3:
                ev["hit by player 1 (crash kind)"] += 1
                continue
            key = []
            if inview(z):
                key.append("P1")
            if inview(z + a["gap"]):
                key.append("P2")
            ev["vanished in " + ("+".join(key) or "neither view")] += 1
            if key and len(exs["out"]) < 6:
                exs["out"].append((a["f"], "slot", i, "Z1", z, "Z2", z + a["gap"], "gap", a["gap"], "->", "%02X" % nb[0] if nb else None, nb[1] if nb else None))
            if nb is not None and nb[0] != 0xFF and (nb[0] & 7) == 0:
                z2 = nb[1]
                key = []
                if inview(z2):
                    key.append("P1")
                if inview(z2 + b["gap"]):
                    key.append("P2")
                ev["re-placed in " + ("+".join(key) or "neither view")] += 1
                if key and len(exs["in"]) < 6:
                    exs["in"].append((b["f"], "slot", i, "Z1", z2, "Z2", z2 + b["gap"], "gap", b["gap"]))
    cars = collections.Counter()
    for r in rows:
        if abs(r["gap"]) >= 0x4000:
            continue
        v1 = sum(1 for t, z in r["slots"].values() if t & 7 == 0 and t != 0xFF and inview(z))
        v2 = sum(1 for t, z in r["slots"].values() if t & 7 == 0 and t != 0xFF and inview(z + r["gap"]))
        cars["P1 sees"] += v1; cars["P2 sees"] += v2; cars["ticks"] += 1
    print(fn.split("/")[-1])
    print("  signs, player 2's counter vs player 1's + gap:", dict(sg))
    for x in bad:
        print("    ", x)
    print("  cars:", dict(sorted(ev.items())))
    for k in ("out", "in"):
        for x in exs[k]:
            print("    ", k, x)
    if cars["ticks"]:
        print("  cars in view per tick: P1 %.2f  P2 %.2f  (%d ticks)" % (cars["P1 sees"] / cars["ticks"], cars["P2 sees"] / cars["ticks"], cars["ticks"]))
