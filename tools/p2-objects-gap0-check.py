"""Check player 2's world objects against player 1's, with the camera gap at 0.

Input: the log of tools/probe-p2-objects-gap0.lua, which forces the gap to 0
for player 2's object pass only. Each line holds player 1's entries 1..$DD-1
(row/bottom row/sprite page+low/palette-width:class) and player 2's world
entries. With no gap, player 2 is looking at the same objects from the same
distance, so every one of its entries must be one of player 1's -- the same
row, height, sprite and palette -- except that a car's viewing-angle sprite
depends on x, which is player 2's own. Then the other way round: each of
player 1's entries player 2 lacks has to be one player 2 cannot have.

    python tools/p2-objects-gap0-check.py LOG [LOG...]
"""
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "patches"))
import splitscreen as S

HERE = os.path.dirname(os.path.abspath(__file__))
ROM = open(os.path.join(HERE, "..", "Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"), "rb").read()[128:]
band = lambda row: ROM[S.ROW_TO_BAND - 0x8000 + row]
REASON = {"18": "crash debris (sub_E2CA), player 1's own",
          "1C": "crash debris (sub_E2CA), player 1's own"}


def near(a, b):
    """Same rows and palette/width; the sprite may differ."""
    a, b = a.split("/"), b.split("/")
    return a[0:2] == b[0:2] and a[3] == b[3]


bad = 0
for fn in sys.argv[1:]:
    frames = unmatched = 0
    p2k, p1k = collections.Counter(), collections.Counter()
    examples = []
    for line in open(fn):
        if "|" not in line:
            continue
        a, b = line.split("|")
        p1 = [x.split(":") for x in a.split()[3:]]
        p2 = b.split()[1:]
        if not p1 and not p2:
            continue
        frames += 1
        # player 2's entries, each claimed from player 1's
        pool = collections.Counter(e for e, _ in p1)
        for e in p2:
            if pool[e]:
                pool[e] -= 1; p2k["exact"] += 1; continue
            m = [k for k in pool if pool[k] and near(k, e)]
            if m:
                pool[m[0]] -= 1; p2k["sprite differs"] += 1; continue
            p2k["NOT in player 1's list"] += 1; unmatched += 1
            if len(examples) < 5:
                examples.append(line.strip())
        # what player 1 has that player 2 did not take
        for i, (e, c) in enumerate(p1):
            if not pool[e]:
                continue
            pool[e] -= 1
            last = i == len(p1) - 1
            row = int(e.split("/")[0], 16)
            if row < 0x4E and band(row) == 0:
                p1k["band 0 (player 2 has none)"] += 1
            elif c in REASON:
                p1k[REASON[c]] += 1
            elif c == "04" and last:
                # RivalCars appends player 2's car after sub_E286, so it is
                # always last; a world car there that player 2 missed would be
                # excused too -- the one case this check cannot tell apart
                p1k["last entry, class 04: player 2's own car"] += 1
            else:
                p1k["class %s UNEXPLAINED" % c] += 1; unmatched += 1
                if len(examples) < 5:
                    examples.append(line.strip())
    print(os.path.basename(fn))
    print("  frames with entries: %d" % frames)
    print("  player 2's entries:", dict(p2k))
    print("  player 1's entries player 2 lacks:", dict(p1k))
    for e in examples:
        print("    " + e)
    bad += unmatched
sys.exit(1 if bad else 0)
