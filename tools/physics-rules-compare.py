"""Compare the two cars' per-tick rules key by key, from a drive.lua log."""
import sys, csv, collections
rows = list(csv.DictReader(open(sys.argv[1])))
# one sample per cycle, after both cars have updated (P1 at phase 2/3, P2 at 4)
ticks = [r for r in rows if r["b8"] == "5" and r["state"] in ("02", "03")]
def pedal(inp, who):
    b1, b2 = "%s Button 1" % who in inp, "%s Button 2" % who in inp
    return "brake" if b2 else ("gas" if b1 else "coast")
spd = {"P1": collections.defaultdict(set), "P2": collections.defaultdict(set)}
lat = {"P1": collections.defaultdict(set), "P2": collections.defaultdict(set)}
byf = {int(r["f"]): r for r in rows}
for a, b in zip(ticks, ticks[1:]):
    if int(b["f"]) - int(a["f"]) != 6: continue
    inp = b["inputs"]
    # inputs steady for the whole cycle, clock running at both ends
    span = [byf.get(f) for f in range(int(a["f"]) - 6, int(b["f"]) + 1)]
    if any(r is None or r["inputs"] != inp for r in span): continue
    if a["clock"] == "0" or b["clock"] == "0": continue
    for who, s, x, g, c in (("P1", "p1spd", "p1x", "p1gear", "p1curve"), ("P2", "p2spd", "p2x", "p2gear", "p2curve")):
        if who == "P1" and (a["crash"] != "0" or b["crash"] != "0"): continue
        onroad = abs(int(a[x])) < 59 and abs(int(b[x])) < 59
        straight = int(a[c]) == 0 and int(b[c]) == 0
        if onroad and straight:
            key = (int(a[s]), a[g], pedal(inp, who))
            spd[who][key].add(int(b[s]) - int(a[s]))
        if int(a[c]) == 0 and int(b[c]) == 0 and abs(int(a[x])) < 59:
            st = "R" if "%s Right" % who in inp else ("L" if "%s Left" % who in inp else "-")
            lat[who][(int(a[s]), st)].add(int(b[x]) - int(a[x]))
def compare(name, d):
    both = set(d["P1"]) & set(d["P2"])
    same = [k for k in both if d["P1"][k] == d["P2"][k]]
    diff = sorted(k for k in both if d["P1"][k] != d["P2"][k])
    print("%s: %d keys seen by both cars, %d agree, %d differ" % (name, len(both), len(same), len(diff)))
    for k in diff[:8]:
        print("   %-28s P1 %s  P2 %s" % (k, sorted(d["P1"][k]), sorted(d["P2"][k])))
compare("speed rule (speed, gear, pedal) -> change", spd)
compare("steer rule (speed, stick) on straights -> lateral change", lat)
