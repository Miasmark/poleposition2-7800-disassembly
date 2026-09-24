#!/usr/bin/env python3
"""The address of each of player 2's road headers (bands 1-12, the width byte's
header +2 as tools/probe-p2-list-integrity.lua reads it), from the current
layout -- print them into a file and pass it as HDR. The layout moves when
bands gain slots (checkpoints 82, 83), so derive it rather than keep a copy.

    python tools/p2-road-headers.py > p2hdr.txt
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "patches"))
import splitscreen as S  # noqa: E402

lay = S.p2_band_layout()
print(" ".join("%04X" % (lay[b]["addr"] + 2) for b in range(1, 13)))
