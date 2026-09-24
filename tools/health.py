#!/usr/bin/env python3
"""Grade a statelog CSV for LIVENESS rather than for matching stock.

A recording cannot validate a build whose boot timing changed (docs/FINDINGS.md,
"Boot-time work desyncs the recordings") -- the inputs simply land at different
moments and the race legitimately differs. What a recording can still show is
whether the machine is HEALTHY: the simulation keeps advancing, the clock keeps
running, nothing freezes. That is what this measures.

    health.py <csv>

The verdict is a heuristic. On the two-player recordings "STALLED" is the
normal answer: the qualifying message holds the clock for ~500 frames, and
player 1 waits at its line while player 2 finishes a qualifying lap (the
1,926-frame runs on test-pp2-2p-0923-0205/0236). What matters is the same
numbers as the previous build's (tools/check-build.sh prints them).
"""
import sys, csv, os

COLS = ["frame","InputAccel","InputBrake","PlayerX","LatVel",
        "RoadCurve","Speed","Gear","Clock","ClockHi"]

path = sys.argv[1]
rows = [r for r in csv.reader(open(path, encoding="utf-8", errors="replace")) if len(r) == len(COLS)]

# Ignore a frozen run that reaches the end of the log: every recording ends
# on a static results screen, and stock shows a 1115-frame one on run-02.
frozen = worst = 0
worst_at = None
moved = set()
prev = None
for r in rows:
    if prev is not None:
        if r[1:] == prev[1:]:
            frozen += 1
            if frozen > worst and r is not rows[-1]:
                worst, worst_at = frozen, r[0]
        else:
            frozen = 0
            for i in range(1, len(COLS)):
                if r[i] != prev[i]:
                    moved.add(COLS[i])
    prev = r

clocks = {r[8] for r in rows}
tail = 0
for r in reversed(rows[1:]):
    if r[1:] == rows[rows.index(r) - 1][1:]:
        tail += 1
    else:
        break
verdict = "HEALTHY" if worst - tail < 120 else "STALLED"
print("%-8s frames=%d  longest frozen run=%d frames%s  distinct clock values=%d"
      % (verdict, len(rows), worst,
         (" (ends f%s)" % worst_at) if worst_at else "", len(clocks)))
print("         fields that ever move: %s" % ", ".join(sorted(moved)))
