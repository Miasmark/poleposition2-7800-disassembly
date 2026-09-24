#!/usr/bin/env python3
"""The values tools/check-build.json needs from the current generator, as
KEY=VALUE lines for the toolkit's regress.py (its `vars_cmd`).

    python tools/check-vars.py build/regress

Prints the symbol addresses the scripted races and the ZRowUp check use,
and writes <dir>/p2hdr.txt, the road headers player 2's lists must hold
(tools/p2-road-headers.py), for the integrity probe. PP2_HIRES_CAR and the
other build switches apply as they do to the build itself, so set the same
ones for both.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "patches"))

if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0 if len(sys.argv) == 2 else 2)

import splitscreen as S  # noqa: E402

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
hdr = subprocess.run([sys.executable, os.path.join(HERE, "p2-road-headers.py")],
                     stdout=subprocess.PIPE, check=True).stdout
with open(os.path.join(out, "p2hdr.txt"), "wb") as f:
    f.write(hdr)
sy = S._ext()[1]
print("p2c=%04X" % sy["P2CrashStart"])
print("p2p=%04X" % sy["P2Puddle"])
print("zr1=%04X" % (sy["ZuDone"] + 2))
print("zr2=%04X" % (sy["ZuNone"] + 2))
