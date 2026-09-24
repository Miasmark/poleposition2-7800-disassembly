"""Far-band road slices, sheared: sizes and a preview.
Line k (0 top .. 5 bottom) of a band is page hi+5-k at lo. A shear of s px
per line moves line k by s*(k - A) px, A = the sample line (x is the sample
row's). Each variant is trimmed to its content and padded to whole bytes."""
import sys
from PIL import Image

ROM = r"C:/Users/thuco/Documents/Atari 7800/Pole Position II/Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78"
d = open(ROM, "rb").read()
rom = lambda a: d[128 + a - 0x8000]
GFX = {1: (0x06, 0x80), 2: (0x0E, 0x80), 3: (0x00, 0xAA), 4: (0x10, 0xAA),
       5: (0xBC, 0x9E), 6: (0xD2, 0x9E), 7: (0x1A, 0x80)}
WID = {1: 8, 2: 12, 3: 16, 4: 20, 5: 22, 6: 26, 7: 30}
A = 3


def lines(b):
    lo, hi = GFX[b]
    w = WID[b]
    return [[(rom(((hi + 5 - k) << 8) + lo + i) >> (6 - 2 * j)) & 3
             for i in range(w) for j in range(4)] for k in range(6)]


def shear(b, s):
    """-> (rows of pixels, x offset in px relative to stock x, width bytes)"""
    L = lines(b)
    pts = [(k, c + s * (k - A), v) for k in range(6) for c, v in enumerate(L[k]) if v]
    lo = min(c for _, c, _ in pts)
    lo = (lo // 4) * 4 if lo >= 0 else -((-lo + 3) // 4) * 4   # whole bytes
    hi = max(c for _, c, _ in pts)
    wb = (hi - lo) // 4 + 1
    rows = [[0] * (wb * 4) for _ in range(6)]
    for k, c, v in pts:
        rows[k][c - lo] = v
    return rows, lo, wb


if __name__ == "__main__":
    total = 0
    for b in range(1, 8):
        out = []
        for s in range(-6, 7):
            rows, dx, wb = shear(b, s)
            out.append("%+d:%d%s" % (s, wb, "!" if wb > 31 else ""))
        print("band %d stock %d bytes: %s" % (b, WID[b], " ".join(out)))
    # preview: band 1-7 stock and s=-3..3
    col = {0: (30, 90, 30), 1: (200, 200, 200), 2: (120, 120, 120), 3: (160, 40, 40)}
    col = {0: (40, 110, 40), 1: (230, 230, 230), 2: (90, 90, 90), 3: (190, 50, 40)}
    S = list(range(-3, 4))
    sx, sy = 3, 6
    Wd = 60 * 4 * sx
    im = Image.new("RGB", (Wd, 7 * (6 * sy + 6) * len(S) // len(S) * len(S) // 7 * 7 + 10), (0, 0, 0))
    im = Image.new("RGB", (len(S) * (40 * 4 * sx // 3) + 20, 7 * (6 * sy + 8) + 10), (0, 0, 0))
    for j, s in enumerate(S):
        for b in range(1, 8):
            rows, dx, wb = shear(b, s)
            x0 = 10 + j * (40 * 4 * sx // 3) + 60 + dx * sx // 1
            y0 = 5 + (b - 1) * (6 * sy + 8)
            for k in range(6):
                for c, v in enumerate(rows[k]):
                    if v:
                        for yy in range(sy):
                            for xx in range(sx):
                                px, py = x0 + c * sx + xx, y0 + k * sy + yy
                                if 0 <= px < im.width:
                                    im.putpixel((px, py), col[v])
    im.save(sys.argv[1] if len(sys.argv) > 1 else "shear.png")
