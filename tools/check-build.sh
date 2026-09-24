#!/bin/bash
# check-build.sh -- the regression set for a split-screen build, as run for
# every checkpoint since 80. Run from the repo root:
#
#     MAME=/path/to/mame BIOS=../bios tools/check-build.sh pp2-vs.a78
#
# Needs the recordings run-02, run-03 and test-pp2-2p-0922-2037/0923-0205/
# 0923-0236 (committed), a 7800 BIOS directory (BIOS, default ../bios) and
# Python with patches/splitscreen.py importable (it reads the build's own
# symbols, so the ROM must come from the current generator; set
# PP2_HIRES_CAR=1 for the higher-detail build). Output lands in
# build/check-<rom name>/; takes a few minutes, the MAME runs in parallel.
#
# What to expect from a healthy build (checkpoints 88-89):
#   health       the same verdict line as the previous build on each recording
#                ("STALLED" is normal here -- see tools/health.py)
#   integrity    0 racing frames with a zeroed road header, on all four
#   zrowup       0 differences
#   wild         no line (no CPU fetch from $8000-$BFFF)
#   tick rate    ~100 per 600 frames on each of six starts (stress scenario)
set -u
ROM="${1:?usage: tools/check-build.sh <rom.a78>}"
MAME="${MAME:-mame}"
BIOS="${BIOS:-../bios}"
NAME="$(basename "$ROM" .a78)"
OUT="build/check-$NAME"
mkdir -p "$OUT"
run() {   # run <autoboot script> <extra mame args...>
    local s="$1"; shift
    "$MAME" a7800 -rompath "$BIOS" -cart "$ROM" -skip_gameinfo -keyboardprovider none \
        -input_directory . "$@" -autoboot_script "$s" \
        -window -nomax -nothrottle -sound none -video soft
}
read P2C P2P ZR1 ZR2 < <(python - <<'EOF'
import sys; sys.path.insert(0, "patches")
import splitscreen as S
sy = S._ext()[1]
print("%04X %04X %04X %04X" % (sy["P2CrashStart"], sy["P2Puddle"], sy["ZuDone"] + 2, sy["ZuNone"] + 2))
EOF
)
python tools/p2-road-headers.py > "$OUT/p2hdr.txt"

for r in run-02 run-03 test-pp2-2p-0923-0205 test-pp2-2p-0923-0236; do
    FRAMES=12000 run tools/probe-health-log.lua -playback "$r.inp" 2>&1 | grep "^[0-9]" > "$OUT/health-$r.csv" &
done
for r in test-pp2-2p-0922-2037 test-pp2-2p-0923-0205 test-pp2-2p-0923-0236 run-03; do
    HDR="$OUT/p2hdr.txt" FR=12000 O="$OUT/integrity-$r.txt" run tools/probe-p2-list-integrity.lua -playback "$r.inp" >/dev/null 2>&1 &
done
wait
for r in run-03 test-pp2-2p-0923-0205; do
    RTS="$ZR1 $ZR2" END=12000 O="$OUT/zrowup-$r.txt" run tools/probe-zrowup-check.lua -playback "$r.inp" >/dev/null 2>&1 &
done
for r in run-02 run-03 test-pp2-2p-0923-0205; do
    END=12000 O="$OUT/wild-$r.txt" run tools/probe-wild-fetch.lua -playback "$r.inp" >/dev/null 2>&1 &
done
wait
# the stress scenario: both cars scripted, then 240 each in traffic, ticks
# counted over frames 7000-7600, from six slightly different starts
for a in 211 213 214 216 218 220; do
    CA=7000 CB=7600 NAVN=2 P2C=$P2C P2P=$P2P FR=7602 O="$OUT/tick-$a.txt" \
    PHASES="3900:$a:210:-40:-40:1;30000:240:240:-40:-40:1" \
        run tools/probe-race-tickrate.lua >/dev/null 2>&1 &
done
wait

echo "== $ROM"
for r in run-02 run-03 test-pp2-2p-0923-0205 test-pp2-2p-0923-0236; do
    echo "health    $r: $(python tools/health.py "$OUT/health-$r.csv" | head -1)"
done
for r in test-pp2-2p-0922-2037 test-pp2-2p-0923-0205 test-pp2-2p-0923-0236 run-03; do
    echo "integrity $r: $(cat "$OUT/integrity-$r.txt" 2>/dev/null)"
done
for r in run-03 test-pp2-2p-0923-0205; do
    echo "zrowup    $r: $(tail -1 "$OUT/zrowup-$r.txt" 2>/dev/null)"
done
for r in run-02 run-03 test-pp2-2p-0923-0205; do
    echo "wild      $r: [$(cat "$OUT/wild-$r.txt" 2>/dev/null)]"
done
echo "tick rate: $(for a in 211 213 214 216 218 220; do grep -o 'CC23=[0-9]*' "$OUT/tick-$a.txt" | cut -d= -f2; done | tr '\n' ' ')"
