#!/usr/bin/env python3
"""What the VS build is made of: every byte of the 48K image classified --
retail and unchanged (read in play or not), retail but overwritten (by what),
or new (code, generated graphics, tables, empty) -- with a PNG map.

    python tools/vs-rom-map.py build/vs.a78 build/cov/*.txt [--png docs/img/vs-rom-map.png]

The coverage files are tools/probe-rom-coverage.lua's output (a 0/1 string,
one character per byte $4000-$FFFF: read by the CPU or MARIA after reset)
from runs of that same build; their union is taken. "Read" is a lower bound
on what the game uses: code for situations no run reached shows as unread.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "patches"))
import splitscreen as S  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
png = sys.argv[sys.argv.index("--png") + 1] if "--png" in sys.argv else None
if png in args:
    args.remove(png)
build = open(args[0], "rb").read()
build = build[len(build) - 0xC000:]                     # the 48K body, $4000-$FFFF
retail = bytes(S.load_source()[2])                      # the 32K body, $8000-$FFFF
read = [False] * 0xC000
for fn in args[1:]:
    s = open(fn).read().strip()
    assert len(s) == 0xC000, fn
    for i, ch in enumerate(s):
        if ch == "1":
            read[i] = True

cat = [None] * 0xC000
def at(a):
    return a - 0x4000

# the new 16K
code_end = S.EXT_ADDR + len(S._ext()[0])
for a in range(S.EXT_ADDR, code_end):
    cat[at(a)] = "new code"
hc = S._hi_code()[0]
for a in range(S.HI_CODE, S.HI_CODE + len(hc)):
    cat[at(a)] = "new code"
for a in S.smooth_art()[0]:
    cat[at(a)] = "generated graphics"
if S.P2_OVL:
    for a in S.p2_overlay_art():
        cat[at(a)] = "generated graphics"
hd, ha = S.hi_data(), S.hi_data_addrs()
for n in hd:
    for i in range(len(hd[n])):
        cat[at(ha[n] + i)] = "new tables"
for a in range(S.HUD_DL2, S.HUD_DLB + 2):
    cat[at(a)] = "new tables"
for a in range(0x4000, 0x8000):
    if cat[at(a)] is None:
        cat[at(a)] = "new, unused" if build[at(a)] == 0xFF else "new tables"

# the retail 32K
blob = (S.HUD_REASSERT_ADDR, S.HUD_REASSERT_ADDR + S._blob_len())
logo = set()
for a0, _old, new in S.TITLE_VS:
    logo.update(range(a0, a0 + len(new)))
for a in range(0x8000, 0x10000):
    if build[at(a)] == retail[a - 0x8000]:
        cat[at(a)] = "retail, read" if read[at(a)] else "retail, not read"
    elif blob[0] <= a < blob[1]:
        cat[at(a)] = "overwritten: new code (blob)"
    elif S.RECLAIMED_LO <= a <= S.RECLAIMED_HI:
        cat[at(a)] = "overwritten: new code and tables (the dead injection)"
    elif a in logo:
        cat[at(a)] = "overwritten: VS logo"
    else:
        cat[at(a)] = "overwritten: hooks and edits"

from collections import Counter
order = ["retail, read", "retail, not read",
         "overwritten: hooks and edits", "overwritten: VS logo",
         "overwritten: new code (blob)", "overwritten: new code and tables (the dead injection)",
         "new code", "generated graphics", "new tables", "new, unused"]
cnt = Counter(cat)
readc = Counter(c for c, r in zip(cat, read) if r)
tot = 0xC000
print("| bytes | % of 48K | read in play | what |")
print("|---:|---:|---:|---|")
for c in order:
    print("| %d | %.1f%% | %d | %s |" % (cnt[c], 100.0 * cnt[c] / tot, readc[c], c))
orig = cnt["retail, read"] + cnt["retail, not read"]
print("\nretail bytes kept unchanged: %d of 32,768 (%.1f%%); still read in play: %d"
      % (orig, 100.0 * orig / 32768, cnt["retail, read"]))
added = tot - orig - cnt["new, unused"]
print("the mod's own bytes (overwritten + new, not counting empty): %d (%.1f%% of 48K)"
      % (added, 100.0 * added / tot))

if png:
    from PIL import Image, ImageDraw
    col = {"retail, read": (120, 170, 120), "retail, not read": (60, 90, 60),
           "overwritten: hooks and edits": (230, 60, 60), "overwritten: VS logo": (240, 140, 200),
           "overwritten: new code (blob)": (250, 160, 40),
           "overwritten: new code and tables (the dead injection)": (250, 210, 60),
           "new code": (60, 130, 240), "generated graphics": (160, 110, 240),
           "new tables": (80, 210, 230), "new, unused": (40, 40, 48)}
    sx, sy = 3, 3
    W, H = 256 * sx, 192 * sy
    im = Image.new("RGB", (W + 470, H + 20), (24, 24, 28))
    for i, c in enumerate(cat):
        x, y = (i & 0xFF) * sx, (i >> 8) * sy + 10
        im.paste(col[c], (x, y, x + sx, y + sy))
    d = ImageDraw.Draw(im)
    for pg in range(0x40, 0x100, 0x10):
        y = (pg - 0x40) * sy + 10
        d.text((W + 6, y - 4), "$%02X00" % pg, fill=(200, 200, 200))
    ly = 20
    for c in order:
        d.rectangle((W + 60, ly, W + 72, ly + 12), fill=col[c])
        d.text((W + 80, ly), "%s  %d" % (c, cnt[c]), fill=(230, 230, 230))
        ly += 22
    d.text((W + 60, ly + 10), "one pixel column per byte, one row per 256-byte page", fill=(180, 180, 180))
    d.text((W + 60, ly + 26), "$4000-$7FFF new 16K; $8000-$FFFF the retail 32K", fill=(180, 180, 180))
    im.save(png)
    print("\nwrote", png)
