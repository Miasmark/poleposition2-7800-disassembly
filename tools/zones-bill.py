"""Usage: python tools/zones-bill.py <dump.bin> [...]   (dumps from probe-render-survey.lua)

Walk a RAM dump's display lists and bill them with dmabudget's measured
constants, so every game is costed by the same instrument."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "a7800-toolkit", "tools"))
import dlwalk, dmabudget as B

FRAME = 262 * 114          # NTSC CPU cycles per frame
VISIBLE = 243              # stop the walk once the zones cover this many lines

def bill(path):
    meta = open(path[:-4] + ".txt").read()
    dpph, dppl, ctrl = (int(x, 16) for x in re.findall(r"=([0-9A-F]{2})", meta))
    chars = 2 if ctrl & 0x10 else 1
    src = dlwalk.Source(open(path, "rb").read(), 0x1800)
    at, lines, zones = (dpph << 8) | dppl, 0, []
    while lines < VISIBLE and len(zones) < 80:
        z = dlwalk.decode_dll_entry(src, at); at += 3
        try:
            objs = dlwalk.walk_dl(src, z["dl"])
        except IndexError:
            objs = []                       # DL outside RAM: a ROM-resident list
        cyc = 0.0
        for o in objs:
            if o["indirect"]:
                cyc += B.PER_OBJ + B.FIVE_XTRA + o["width"] * (1 + chars) * B.PER_BYTE
            else:
                cyc += B.PER_OBJ + o["width"] * B.PER_BYTE + (B.FIVE_XTRA if o["bytes"] == 5 else 0)
        cost = z["lines"] * (B.PER_LINE + cyc) + B.PER_ZONE + (B.DLI_COST if z["dli"] else 0)
        zones.append((z, objs, cost)); lines += z["lines"]
    return zones, ctrl

def summary(name, path):
    zones, ctrl = bill(path)
    total = sum(c for _, _, c in zones)
    lines = sum(z["lines"] for z, _, _ in zones)
    hdrs = sum(len(o) for _, o, _ in zones)
    ind = sum(1 for _, o, _ in zones for e in o if e["indirect"])
    dlis = sum(1 for z, _, _ in zones if z["dli"])
    hist = {}
    for z, _, _ in zones: hist[z["lines"]] = hist.get(z["lines"], 0) + 1
    print("%-26s zones=%3d lines=%3d  headers=%3d (indirect %2d)  DLI zones=%d  "
          "DMA=%6.0f cyc = %4.1f%% of frame  -> CPU left %5.0f" % (
          name, len(zones), lines, hdrs, ind, dlis, total, 100 * total / FRAME, FRAME - total))
    print("%26s zone heights: %s" % ("", "  ".join("%dx%d" % (n, h) for h, n in sorted(hist.items()))))
    return zones

if __name__ == "__main__":
    for p in sys.argv[1:]:
        summary(os.path.basename(p)[:-4], p)
