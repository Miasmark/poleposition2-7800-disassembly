import sys, re, os, collections
os.chdir(r"C:\Users\thuco\Documents\Atari 7800\Pole Position II")
sys.path.insert(0, "patches")
syms = []
cur = None
for ln in open("src/rom.asm", encoding="utf-8", errors="replace"):
    m = re.match(r"^([A-Za-z_][\w]*):", ln)
    if m: cur = m.group(1); continue
    m = re.search(r";\s*([0-9A-F]{4}):", ln)
    if m and cur:
        syms.append((int(m.group(1), 16), "rom:" + cur)); cur = None
patched = len(sys.argv) > 2
if patched:
    import splitscreen as S
    for tab in (S._ext()[1], S._rival_helpers()[1], S._assemble(S.hud_reassert_src(S.HUD_REASSERT_ADDR))[1]):
        for k, v in tab.items():
            if isinstance(v, int) and 0x4000 <= v <= 0xFFFF and not re.match(r"^[A-Z0-9_]+$", k):
                syms.append((v, k))
syms.sort()
import bisect
addrs = [a for a, _ in syms]
def name(pc):
    i = bisect.bisect_right(addrs, pc) - 1
    return syms[i][1] if i >= 0 else "?%04X" % pc
tot = 0; by = collections.Counter(); main = collections.Counter()
for ln in open(sys.argv[1]):
    pc, sp, c = map(int, ln.split(","))
    n = name(pc); by[n] += c; tot += c
    main["main" if sp >= 0xF6 else "irq"] += c
print("samples", tot, dict(main))
for n, c in by.most_common(int(os.environ.get("TOP", "30"))):
    print("%6.2f%%  %s" % (100.0 * c / tot, n))
