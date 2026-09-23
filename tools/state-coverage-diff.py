"""Bytes read in one game state and in no other, across coverage runs.

    python tools/state-coverage-diff.py <dir of probe-state-coverage outputs> [state] [list]

Default state is 1, the attract demo. Inputs are the C_OUT files written by
tools/probe-state-coverage.lua (state lo hi per line, # lines ignored)."""
import sys, os, glob
sv = sys.argv[1]
WANT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 1
demo, other = set(), set()
files = sorted(glob.glob(os.path.join(sv, "cov-*.txt")))
for f in files:
    for line in open(f):
        if line.startswith("#") or not line.strip():
            continue
        s, lo, hi = map(int, line.split())
        (demo if s == WANT else other).update(range(lo, hi + 1))
only = sorted(demo - other)
runs, i = [], 0
while i < len(only):
    j = i
    while j + 1 < len(only) and only[j + 1] == only[j] + 1:
        j += 1
    runs.append((only[i], only[j])); i = j + 1
print("runs used: %d files" % len(files))
print("bytes read in the demo: %d; also read elsewhere: %d; demo-only: %d in %d ranges"
      % (len(demo), len(demo & other), len(only), len(runs)))
if "list" in sys.argv[2:]:
    for lo, hi in runs:
        print("  $%04X..$%04X %5d" % (lo, hi, hi - lo + 1))
