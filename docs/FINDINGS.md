# Pole Position II -- findings so far

*Reading this file:* it is chronological, and it keeps wrong turns next to
their corrections. Later sections supersede earlier ones where they say so;
the split-screen work started as a *mirror* of player 1's road
(checkpoints 1-18) and most of its early sections describe that. For the
build as it stands, read [`SPLITSCREEN.md`](SPLITSCREEN.md) first.

Day one. Almost everything below is a measurement or an explicitly-flagged
hypothesis, and the two are kept distinct: where something is read from the
code but never watched running, it says so.

## The manual, as a source of numbers to look for

The AtariAge manual scan gives concrete values, which is what makes it useful
here: they are things to find in the ROM rather than claims to repeat.

| | |
|---|---|
| tracks | four: TEST, FUJI, SEASIDE, SUZUKA |
| qualifying | 120 driving seconds; 73"00 or better to qualify |
| lap allowance | 75 seconds for the first, 60 for each after |
| race length | 5 laps |
| score | 10,000 a lap, 50 a car passed, 200 a second left at the finish |
| qualifying bonus | 4,000 at 58"50 down to 200 at 73"00 |
| hazards | signs cause a wipeout, puddles slow you considerably, skidding cuts speed |
| controls | joystick back for low gear, forward for high; left button accelerates, right brakes |

FUJI is listed as the track with billboards, puddles and other cars, which
matches `run-02` exactly.

Nothing above is a finding. Every one of those numbers is a hypothesis about
what is in the ROM until it is located there.

## The cartridge

| | |
|---|---|
| ROM | `Pole Position II (NTSC) (Atari) (1987) (A85FB962).a78` |
| Size | 32,896 bytes (128-byte header + 32,768) |
| Mapper | linear 32K, no banking, mapped `$8000-$FFFF` |
| Vectors | NMI `$EBEF`, RESET `$D205`, IRQ `$EC0E` |

Linear, so every address is unambiguous and the cross-bank reference
resolution that caused repeated errors in the banked projects simply does not
apply. This is the second 32K linear cartridge in the series after Galaga.

## Day one coverage

Tracing from the three hardware vectors alone reaches **16.8%** of the ROM
(5,494 of 32,768 bytes), leaving 27,274 bytes in 26 gaps -- the lowest opening
figure of any project in this series, where Ms. Pac-Man reached 52.4% and
Asteroids 41.9%. One gap accounts for most of it:

    $8000-$C1A4   16,805 bytes   over half the cartridge, contiguous

A block that size at the bottom of the map, in a game built around a scrolling
road and a horizon, is very likely graphics and track data. That is a
hypothesis. Nothing has been rendered or traced yet.

**Resolving two indirect jumps took it to 27.5%** -- see below.

## No missed code, and two RAM vectors

`disasm.py --check-gaps` classifies every apparent `JSR`/`JMP` whose operand
lands in a gap. On the day-one annotations there were **141 candidates and not
one real**: every one is a `$20`/`$4C`/`$6C` byte occurring inside data or in
the middle of a longer instruction. No traced code branches into any gap.

What it did flag was two indirect jumps through RAM, whose targets no static
scan can know:

    rom:D26A   JMP ($0040)
    rom:EC06   JMP ($00FD)

The toolkit's `ram_vectors` scan finds neither -- it looks for an immediate
load paired with a store, and these are not built that way. So they were
resolved live, against `run-01`, by tracing the emulator and reading the
instruction that actually followed each jump.

    JMP ($0040)  ->  $D26D, $D3A4
    JMP ($00FD)  ->  $EC10, $EC57, $EC76, $EC87, $EC8C, $ED30, $ED4A, $ED4F

Both land inside gaps the trace had reported: `$D26D-$D477` and `$EC0F-$F170`.

## The display-interrupt handler table

Reading the code around the second vector explains it, and gives more than the
recording did. The NMI entry:

    $EBEF   STA WSYNC
            ...save A/X/Y...
            LDA ram_009C
            BMI sub_EC09
            LDX ram_00FF          ; a zone index
            LDA dat_A48A,X        ; handler address, low
            STA ram_00FD
            LDA dat_A496,X        ; handler address, high
            STA ram_00FE
            JMP (ram_00FD)

Two parallel tables twelve bytes apart, indexed by `ram_00FF`, so **twelve
display-interrupt handlers**, installed one per zone. Read out of the ROM:

    index  0 -> $2456     RAM -- copied there at run time, not statically reachable
    index  1 -> $EC10     index  7 -> $ECA1
    index  2 -> $EC57     index  8 -> $ED2B
    index  3 -> $EC76     index  9 -> $ED30
    index  4 -> $EC87     index 10 -> $ED4A
    index  5 -> $EC9E     index 11 -> $ED4F
    index  6 -> $EC8C

The recording exercised eight of the eleven ROM handlers; the table gives all
of them, which is why it was worth reading the mechanism rather than stopping
at what the trace happened to visit. Those eleven are now entries, and the
table is declared as `dat_DliHandlerTable`.

**The table sits at `$A48A`, inside the 16,805-byte block** -- the first
structure identified in it, and evidence that the block is not purely graphics.

Coverage after all this: **27.5%** (9,014 bytes, 4,230 instructions), 23,730
bytes still in 24 gaps. Round-trip byte-identical throughout.

## The chain, and an entry nothing selects

Each handler installs the index for the next one, which is what makes it a
chain rather than a table lookup. Every site that writes `ram_00FF`:

    $D890  #$01     $EC78  #$04     $ED2B  #$09  (via $EC78)
    $D8D4  #$07     $EC9A  #$01     $ED30  #$0A  (guarded, see below)
    $EC52  #$02     $ECA6  #$08     $F169  #$07
    $EC5F  #$03

So indices **1, 2, 3, 4, 7, 8, 9 and 10** are installed. `$ED30` is the only
conditional one: it loads `$0A`, and only stores it when `ram_0048` is in
`4..7`, otherwise branching away -- a range check on some game-state value.

**Nothing installs index 0.** No path found writes it, and across the whole of
`run-01` the address it points at (`$2456`) is never executed. Two readings,
and the evidence does not separate them: the entry is dead, or it belongs to a
mode this recording never enters. It is written down as unselected rather than
as dead, because "no path found" is a statement about the search.

That `$2456` is in RAM is itself worth noting. The BIOS copies into `$2300`
and `$2400` during startup (`$FB2F`/`$FB35`, 256 iterations each -- BIOS code,
not the cartridge's: `$FB1C` onward in this ROM is all `$FF` padding). So
whatever index 0 would jump to is either installed by the game later, or is
BIOS leftovers.

## Two display lists, and the road

The game builds its display list pointer in exactly two places -- and neither
is the address a tap reports. `$1F84` is the BIOS's display list; write taps on
`DPPH`/`DPPL` catch the BIOS's stores and stop firing before the cartridge
makes its own, which yields a screenful of nonsense that reads like a decode
failure. The real ones come straight out of the code:

    $D89B   LDA #$22 / STA DPPH,  LDA #$6B / STA DPPL   ->  DLL $226B
    $D8D6   LDA #$22 / STA DPPH,  LDA #$00 / STA DPPL   ->  DLL $2200

Two screens. Walked live at frame 3000 of `run-01`, `$226B` draws from `$A5xx`,
`$A6xx` and `$B0xx` in small pieces -- text and panel furniture. `$2200` is the
race, and the lower half of it is the road:

    zone 20   $8000/w6      zone 28   $8038/w16  $8047/w19
    zone 21   $8006/w8      zone 29   $805A/w16  $8069/w21
    zone 22   $800E/w12     zone 30   $807E/w16  $808D/w25
    zone 27   $801A/w30     zone 31   $80A6/w16  $80B5/w29

**The bands are packed end to end by width.** `$8000`+6 = `$8006`, +8 =
`$800E`, +12 = `$801A`, +30 = `$8038`. Where a zone draws two objects the
second grows steadily -- 19, 21, 25, 29 -- and its successor follows exactly.

### The off-by-one, resolved

The paired zones looked wrong: the first object reports width 16 but the next
address is 15 bytes on. That was written down as a possible decode error. It
is not one. Reading the horizontal positions as well as the widths settles it:

    zone 28   $8038 w16 x15  ends at pixel 79  |  $8047 w19 x75
    zone 29   $805A w16 x14  ends at pixel 78  |  $8069 w21 x74
    zone 30   $807E w16 x8   ends at pixel 72  |  $808D w25 x68
    zone 31   $80A6 w16 x2   ends at pixel 66  |  $80B5 w29 x62

Each pair overlaps by exactly four pixels -- one byte in 160A -- and the
overlapping byte is **the same ROM address drawn at the same screen position
by both objects**. `$8038`'s sixteenth byte is `$8047`, which is `$8047`'s
first byte, and both land on pixels 75-78. The same is true of all four.

So the width decode is right, the packing is right, and the game deliberately
overlaps the two halves of each wide road strip by one byte. It costs nothing
and it cannot show a seam, because the shared byte is drawn twice in the same
place with the same value.

The apparent contradiction came from comparing addresses without positions.
Widths alone said 16 and 15 at once; adding x said both, consistently.

Widths increasing down the screen is a road in perspective: narrow at the
horizon, wide at the car. So **the block at `$8000` opens with the road
bands**, stored as a contiguous run of variable-width strips, and MARIA is
observed fetching from them rather than this being inferred from entropy or a
render.

The same screen also fetches from `$87xx`-`$8Bxx`, `$9Exx`, `$A3xx`, `$AAxx`
and `$B0xx`, all inside the same block. So it is graphics throughout, reached
from many display-list entries rather than one table -- which is why a static
search for references into it finds so little.

### The road surface is fixed. The curve is applied to everything drawn on it.

Raised by a question about whether a second, independent road view is
feasible at all (split-screen two-player). This took three passes to get
right, and each wrong turn is kept below rather than deleted, since the
dead ends are as informative as the answer.

**Pass 1 (wrong):** tapping `$2200-$226B` for 5,000 frames of `run-01` found
almost every byte written exactly 15 times, read as a periodic per-segment
rebuild "once every ~5.5 seconds". Extending the same tap across the full
17,115-frame race showed all 15 writes landing in the first 211 frames and
never recurring -- `sub_F171` (`rom:F171-F187`) copies two fixed ROM
templates (`dat_BC7E`->`$2200`, `dat_BD7E`->`$226B`) once, at race setup,
never again. True, but not the whole story.

**Pass 2 (wrong):** screenshots at frames 3000, 8000 and 12000 show visibly
different road shapes, so something changes. Diffing full `$2200-$226B`
dumps at frame 3000 vs. frame 8000 found exactly one differing region,
`$2220-$222F`, written by `rom:D81A`/`rom:DA91`. Read as a binary
corner/straight zone-snippet toggle. **Wrong** -- bracketing the write at
frame 3861 with screenshots immediately before and after shows the event is
the "POLE POSITION! 4000" qualifying banner appearing (with the gear
indicator flipping HI->LO and the car stopping), not a road change at all.
`$2224-$222C` is a HUD panel slot, not part of the road.

**Pass 3 (confirmed):** `RoadCurve` (`$00DA`) reads -7 at frames 3000 and
12000 (both curved) and 0 at frame 8000 (straight) -- the right signal, at
last. Tracing every reader of `RoadCurve` finds only steering/skid physics
(`SkidCheck` at `rom:C269`, a ramp-toward-target routine at `rom:C3E9`-`C43C`
easing it by 7 per step -- matching "the curvature ramps symmetrically in
and out of every corner" already documented below). None of that is
rendering. The render-side consumer turned out to be a level deeper: the
*track's* `SegCurve` table (`$1900`, per-segment curvature, not the smoothed
per-frame `RoadCurve`) is read at `rom:E981`, inside a routine
(`rom:E95C-E9D0`) that scales it by perspective -- more `ASL` doublings for
rows further from the camera (`CPX #$40`/`#$20`/`#$10`/`#$06` gate
successive doublings) -- and accumulates the result into two per-row
tables, `ram_1A31` and `ram_1C08`.

Both real consumers of that table are render-side, not gameplay:

* `rom:D1FD`: `SBC ram_1A31,Y` (`Y=$48`, the player's row) directly computes
  **`PlayerX`**. The car's on-screen lateral position *is* the curve offset
  at the player's row, subtracted from a base.
* `rom:E502`: inside the shared object-positioning code (the same system
  documented above for rival cars, signs and puddles), `ram_1A31,Y` and
  `ram_1A30,Y` are added into an object's screen-space X alongside its own
  `ObjLateral`.

So the mechanism is: **the base pavement graphic (zones 20-31, the fixed
ROM trapezoid) never moves and is never curve-specific -- it's a permanent
straight-ahead backdrop.** The curve is applied entirely to *everything
drawn on top of it* -- the player's car, every rival car, every sign and
puddle, and (almost certainly, though not directly traced) the centerline
dashes and roadside border, all repositioned every frame by the same
accumulated per-row offset. The road only *looks* like it bends because
everything on it does.

**Why this matters for a second camera:** this is better news than either
wrong pass suggested. The curve computation (`rom:E95C-E9D0`) is compact,
already perspective-scaled per row, and shares its output format with the
object-positioning system already characterized above for drawing the
other player's car. A second viewport needs its own curve-accumulation pass
fed from player 2's own track position into the same `SegCurve` stream, and
its own `PlayerX`-equivalent -- but the static pavement backdrop is generic
enough (it's not curve-specific ROM art) that it may not need duplicating
at all, only reusing from a second camera offset.

### The last piece: the curve is injected live, scanline by scanline, by a DLI chain

One gap remained even after `ram_1A31` was confirmed: diffing the *complete*
decoded zone list (all 35 zones, not the object-bearing subset) between
frame 3000 and frame 8000 shows more than `PlayerX` and other objects
moving. Zone 19 -- five small objects sitting right at the horizon line,
lines 129-139 in the layout above -- keeps the *same five graphics
addresses* at both frames but at entirely different `x` positions (e.g.
`$B04F` at `x122` when curved, `x111` when straight). That is the skybox:
noticed live in play and confirmed here in the data. The road zones
(20-32) show the same pattern, and several of their padding
`$0000/w1` slots become real small objects in one frame and not the other.

None of that lives in the RAM this doc had already tapped. `$2300-$2500`
(the *target* sub-lists the static zone selectors point to, not the
selectors themselves) turned out to be rewritten **every single frame** --
1,010 writes across 1,000 frames tapping just one representative byte,
`$2303`. The writer is `rom:EDA0` (`AccumulateRowCurveOffset`'s neighbor,
not yet named), and reading it settles the mechanism completely: it is a
**display interrupt handler** -- `STA WSYNC` between every couple of
instructions, the classic per-scanline raster-sync pattern -- that reads a
staged per-row table (`ram_1B00`, `ram_1B4E`, ...) one entry at a time and
pokes it straight into the live zone entries' `x` fields (`ram_2301`,
`ram_2303`, ...) *as MARIA is actively drawing that scanline*.

The staging table traces cleanly back to the same curvature pipeline:
`sub_EA2C` (`rom:EA2C-EA3D`) copies `ram_1B9C,X` into `ram_1B00,X`, and
`ram_1B9C` and `ram_1A31` are filled from the same accumulation -- both
read `ram_1C56,X`, and `sub_EA16` (`rom:EA16-EA27`) seeds that accumulator
from ROM tables (`dat_EA41`, `dat_EADE`), the same per-track curvature data
family as `SegCurve`.

So the complete picture, corrected one more time: the *structural* display
list (which zones exist, what graphics they reference, how many lines each
spans) really is static, copied once at boot, exactly as first found. What
is not static, and runs every frame via a chain of per-scanline display
interrupts, is the **`x` position of every object drawn** -- road strips,
horizon markers, the lot -- live-injected from a table computed once per
frame from the track's curvature. The pavement never bends; the interrupt
chain sweeps every object sideways as MARIA draws it, scanline by scanline,
and that sweep is what a human eye reads as the road curving.

This changes the DMA accounting by a small, bounded amount not yet folded
into the total above: `dmabudget.py` has a `dli=True` flag precisely for
this (`DLI_COST` = 16.6 cycles per zone that raises one), and the zones
this chain touches haven't been individually confirmed and marked. Given
the surplus already measured (23,834 cycles), even a dozen such zones adds
under 200 cycles -- not enough to change the headroom conclusion, but worth
stating as unmeasured rather than silently folded in.

**Why this matters for a second camera, revised:** duplicating curvature
for player 2 means duplicating this whole small pipeline -- the
accumulation (already scoped) *and* the per-scanline DLI injection, not
just a value computed once per frame. That is more moving parts than the
previous version of this section implied, though each part is small and
already understood in isolation.

### The road's DMA weight and the full screen layout, measured properly

Two mistakes in the same write-up, caught while double-checking before any
Phase 1 layout work rather than after: `tools/probe-dlgfx.lua`'s zone walk
was hardcoded to zones 0-31 and only printed zones with at least one object,
so the first pass here summed 113 scanlines and missed every zone that
draws nothing -- and separately treated `$226B` as if it ran *alongside*
`$2200` and added their DMA costs together. Neither is right. `$2200` and
`$226B` are the same kind of alternative this doc already established for
DPPH/DPPL (one active list at a time): `$2200` is the race view, `$226B` is
the results/qualifying screen, and the game is never driving with both DMA
costs live at once. The 113-line figure and the "29.8% combined" figure are
both wrong; corrected below rather than deleted.

Walking all 35 zone-selector slots in the (fixed-size, 107-byte) race
template and decoding every object chain, including the ones with none,
gives the real picture: **249 of 262 NTSC scanlines**, not 113. In list
order (which is screen order), the driving view is:

    lines   0- 26  sky (zones 0-1, no objects -- solid colour via a DLI)
    lines  26- 33  HUD row 1 (TOP / SCORE)
    lines  33- 56  sky + gap zones (3,5,7)
    lines  36- 43  HUD row 2 (UNIT / LAP)
    lines  46- 53  HUD row 3 (SPEED / HI-LO)
    lines  56- 83  more sky/gap zones (8,9,10,11) -- no objects
    lines  83- 99  the "POLE POSITION!" banner's two zones -- empty
                   at frame 3000, populated only around a qualifying finish
    lines  99-119  more gap zones (14,15,16,17) -- no objects
    lines 119-139  zones 18-19: small decorative objects (a marker, signs)
    lines 139-217  **the paved road** -- zones 20-32, 78 lines, this is the
                   part previously and correctly analyzed in detail above
    lines 217-249  more sky/gap zones (33,34) -- no objects

So the actual pavement is a **78-line band roughly in the vertical middle**
of a 249-line view that is otherwise sky, HUD text, and a banner slot that's
usually empty. This matters a great deal for where a second camera's view
could physically go: the ~130 empty-object lines are cheap (each still
costs `PER_LINE` per the model below, since MARIA times a scanline whether
or not it draws anything, but none of them cost real per-line object
fetches) and several are large contiguous runs (26, 27, and 32 lines) that
are exactly the kind of "quiet, mostly unused vertical space" this
investigation set out looking for.

Feeding the complete, correct 35-zone list through `tools/dmabudget.py`:

    race DLL (all 35 zones, complete): 6,034 cycles  (20.2% of an NTSC frame)
    left for CPU logic:               23,834 cycles  (79.8%)

**Even more headroom than the incomplete count suggested**, and now for
the number that's actually relevant (the results screen's `$226B` DLL was
never competing for the same frame in the first place). The reasoning
about a second camera still holds and is on firmer ground now: the same
total scanline count and object density applies whichever way it's
apportioned between two camera views, and the large empty-sky runs are
where a second player's own sky/road band has real room to live without
displacing anything the current single-player view needs.

## The race clock

`$DF` is the clock, in BCD, counting down. `$DE` extends it above 99 -- it
holds `01` through the 120-second qualifying run and borrows to `00` at the
100-to-99 boundary, which is what proves the two are coupled. For every
two-digit allowance it is `00`.

**It ticks every 36 frames**, so a driving second is about 0.6 of a real one
and the clock runs at roughly 1.67x real time. Measured at single-frame
resolution: 26 down to 00 across frames 10071 to 10971, every transition
exactly 36 frames apart.

An earlier version of this file said 30 frames, "exactly", and that was
wrong -- it came from sampling the clock every 30 frames and seeing one
change per sample, which is aliasing and will report the sampling interval
back at you whatever the truth is. The same note dismissed a ~36-frame
estimate from the qualifying phase as the less trustworthy measurement. It
was the correct one. **Never measure a period at the period you are
sampling at**, and treat a result that lands exactly on the sampling
interval as evidence of the method rather than the subject.

The clock also stops. Between phases (`$DD` = `$08`) both bytes sit at `$75`
and nothing moves for hundreds of frames. That reading is not a clock value at
all, and decoding it as a 16-bit pair produces a nonsensical 7575 -- which is
exactly what happened here before the frozen interval was recognised for what
it is.

### Laps extend the clock, they do not reset it

Watching for upward jumps found four, and calling them "resets" was wrong:

    f684     0 -> 120     qualifying allowance, set
    f3402    0 ->  75     race start allowance, set
    f6504    5 ->  65     EXTENSION: 5 remaining, 60 added
    f8814    1 ->  60     extension
    f10974        -> 0    time out, and the recording ends at f11942

`5 -> 65` is a clean sixty added to what was left, not a reset to a fixed
value, and that is how the game behaves: completing a lap extends the clock
and announces **EXTENDED TIME!**, except the last, which announces **FINAL
LAP!** and extends anyway. So the manual's "60 seconds each" is an allowance
added per lap rather than a fresh countdown -- a distinction the manual's
wording does not make and the RAM does.

Against the manual: 120 confirmed, 75 confirmed, 60 confirmed as the extension
amount, and the clock reaching zero where the recording ends.

**The 200-points-a-second rule cannot be checked from `run-02`.** The game
tallies cars passed and seconds remaining into the score before the game-over,
but this run ended *because* the clock hit zero, so the seconds component is
zero by construction. There is also no rapid drain in `$DF` anywhere in the
run -- it counts down at its normal 36 frames a tick all the way to `00` at
f10971 -- so nothing here converts time into points. Testing that rule needs a
recording that finishes a race with time left.

### The messages, found (superseded -- see above)

`EXTENDED TIME` and `FINAL LAP` appear nowhere as ASCII, and nowhere as a run
of bytes whose letter-to-letter spacing matches -- but that second search
assumes the tile codes run alphabetically and that there is no separate space
character, and neither is established. So this is a weak negative, of the kind
`pitfalls.md` warns about: text in a tile-based game is not ASCII and greps
for it come back empty. Finding the messages means finding the routine that
draws them.

## The character set, and the text

The HUD is four fields of display data in RAM, filled from ROM templates by
`rom:F204`:

    dat_C976  19 bytes -> ram_1F8A   row 1, left
    dat_C98A  19 bytes -> ram_1FA8   row 2, left
    dat_C9A2  11 bytes -> ram_1F9D   row 1, right
    dat_AE24  11 bytes -> ram_1FBA   row 2, right

Those templates are the labels on screen, and knowing what they say -- TOP,
SCORE, LAP, SPEED -- gives the encoding directly. Every shared letter agrees
across all four words, which is what makes it a solution rather than a guess:
`$A6` is the S of both SCORE and SPEED, `$A3` the P of SPEED and LAP, `$A2`
the O of TOP and SCORE, `$9A` the E of three of them.

    $8C-$95   digits 0-9
    $96-$A8   A B C D E F G H I . . L M N O P Q R S T U
    $A9 $AA   X Y
    $AB       space
    $B1-$B4   J K Z V

**The letters are not one contiguous run**, but none are missing. The common
ones are packed at `$96`, and J, K, Z and V -- the four the run skips -- are
appended at `$B1`-`$B4`. V turned up first, because `9C 96 A0 9A AB A2 B4 9A
A5` is GAME OVER and nothing else fits; the other three came from searching
for the track names with the gaps as wildcards.

This is why the earlier search failed and was right to be called a weak
negative: it assumed alphabetical codes with no gaps, and there are four.

This is why the earlier search failed and was right to be called a weak
negative: it assumed alphabetical codes with no gaps, and the encoding has
three.

### What the ROM says

    $A0A0   TEST                  $B1ED   EXTENDED PLAY
    $A0AC   SEASIDE               $B1FB   TIME
    $A372   PASSING BONUS         $B2F2   POLE POSITION
    $AC25   1984 ATARI            $C96D   GAME OVER
    $AD25   1982 NAMCO            $C9A2   ...FINAL LAP
    $BED6   QUALIFYING POSITION 1 2 3 4 5 6 7 8

`QUALIFYING POSITION 1 2 3 4 5 6 7 8` confirms the manual's eight-place bonus
table exists, and locates the text for it.

### A retraction: the track names are text after all

An earlier version of this section said FUJI and SUZUKA "cannot be spelled --
no J, K or Z in the font -- so those two track names are not text. They must
be drawn as graphics." **Wrong, and wrong for a reason worth keeping.**

The reasoning ran: the letters are missing, therefore the words are missing,
therefore they are drawn some other way. The step that failed is the first
one. The letters were never missing -- they were somewhere I had not looked,
because I had assumed the alphabet was one contiguous block and stopped
mapping at the end of it.

Searching for the names with the unknown letters as wildcards finds them at
once:

    $A0A6   9B A8 B1 9E              F U J I
    $A4A4   A6 A8 B3 A8 B2 96        S U Z U K A

and that yields J, K and Z. The prompt for it was the observation that
graphics cost more space than text, so a handful of single-use characters is
the cheaper thing to store -- which is exactly what the ROM does.

The names sit in a table with a digit and a `$B0` separator after each:

    $A0A0   TEST 2 $B0
    $A0A6   FUJI 3 $B0
    $A0AC   SEASIDE
    $A4A4   4 $B0 SUZUKA

`EXTENDED PLAY` rather than `EXTENDED TIME`: the message this game shows on a
lap completion is not quite what was described from memory, and the ROM is the
authority.

## The HUD, read off the screen

A snapshot mid-race settles what the templates say and what each field is:

    TOP    23400        UNIT      LAP   80:62
    SCORE  23400          51      SPEED 255mph
                          HI

Which confirms the decode exactly, including the odd part. **The timer is
labelled `UNIT`.** The bytes are `A8 A1 9E A7` and there is no other reading;
the screen agrees. A racing game whose clock is captioned "UNIT" is peculiar
enough to look like a decoding error, and it is not one -- worth recording
before someone "corrects" it later.

The fields, and what each confirms:

| field | template | confirms |
|---|---|---|
| TOP / SCORE | `dat_C976` / `dat_C98A` | both read 23400 -- equal, because the score IS the high score |
| UNIT | in `dat_C976` | shows 51 at frame 7000, and `$DF` measured 54 at f6900 and 45 at f7200 |
| HI | | the gear, under the timer |
| LAP | `dat_C9A2` | 80:62, the lap timer, separate from the race clock |
| SPEED | `dat_AE24` | 255mph -- and `{AC}{AD}` in that template are the "mph" glyphs |

The UNIT value cross-checking against `$DF` is the useful one: the clock was
found by a RAM search and the display was decoded from ROM templates, by
different routes, and they agree on the same number at the same frame.

A second snapshot at frame 9000 reads TOP/SCORE 31820, UNIT 55, LAP 136:14,
SPEED 255mph -- so the score rose by 8,420 between the two, and the lap timer
runs in a different format from the race clock (`136:14` rather than seconds).

## The lap timer, and the qualifying thresholds

The lap timer is three BCD bytes in zero page, found by reading two values off
a screenshot and searching for exactly those bytes:

    $BE  hundreds     $BD  seconds     $BC  hundredths

        00 80 62  ->  080:62  at frame 7000
        01 36 14  ->  136:14  at frame 9000

`rom:D9B5` clears all three. `rom:D3F7` is the qualifying check:

    LDX #$00
    LDA LapTimeHundreds
    BNE ...                  100 seconds or more: no position
    LDA LapTimeSeconds
    CMP dat_DBA0,X           thresholds, seconds
    BMI got_it
    BNE next
    LDA LapTimeHundredths
    CMP dat_DBA8,X           thresholds, hundredths
    BMI got_it
    INX / CPX #$08 / BNE     eight positions

**Two parallel tables** -- `dat_DBA0` seconds, `dat_DBA8` hundredths -- walked
until the lap beats one:

    1st  58.50      5th  66.00
    2nd  60.00      6th  68.00
    3rd  62.00      7th  70.00
    4th  64.00      8th  73.00

The manual gives the first and the last and nothing between. Both match, and
the six middle thresholds are now known -- which is the useful direction for a
reference to be checked in: it confirmed the ends and the ROM supplied the
rest.

**Why the first search for this failed.** Looking for the pair `58 50` as
adjacent bytes returns nothing, and that was reported as no qualifying table
being present. The pair is split across two tables eight bytes apart; both
bytes were there all along. The sibling Asteroids project's score table has the
same shape, two parallel BCD arrays, so a value a manual states as one number
is quite likely stored as two -- and "not found" should be read as "not found
in the layout I assumed".

The lap timer also advances at the same 1.667x rate as the race clock (80.62 at
f7000 to 136.14 at f9000 is 55.52 units in 33.3 real seconds), so the two share
one prescaler.

## Speed, and how it bleeds off

Speed is `$CE`, a single **binary** byte -- not BCD like everything else on
the HUD. Found by reading two values off screenshots (158 at frame 4200, 241
at frame 10600) and searching for exactly those bytes: one match in all of
RAM, and no match at all for the BCD encodings. That it saturates at 255 is
the confirming detail, since a BCD speedometer would cap at 199 or 999.

Its behaviour through a crash confirms it beyond the fingerprint:

    f7460  232    f7500  136    f7530   39
    f7480  215    f7510   94    f7540    0
    f7490  187    f7520   75

A car decelerating to a stop over about eighty frames.

### The decay is one eighth per update

`rom:C92F`:

    LDA Speed
    LSR / LSR / LSR      speed >> 3
    EOR #$FF
    SEC
    ADC Speed            EOR/SEC/ADC is the 6502 subtract idiom
    STA Speed            so: speed = speed - speed/8

Exponential decay, losing an eighth each time it runs. Immediately above it a
threshold gates a call:

    LDA Speed
    CMP #$5A             90
    BCC skip
    LDA #$02
    JSR sub_DEF3         only above 90

So something -- plausibly the crash effect or its sound -- happens only when
the impact is above 90.

### Events in run-02, and a retraction

An earlier reading of this recording called five of the drops "identical,
mechanical drops of exactly 31 from a saturated 255 to 224" and guessed that
224 being `$E0` pointed at a mask. That was wrong, and the arithmetic on this
very page says so: `$FF >> 3` is 31, so `255 - 255/8` is exactly 224. Each of
those five is one perfectly ordinary application of `SpeedDecay` at saturated
speed. There is no mask. The lesson is the flat one -- a number that looks
significant in hex was already explained by the formula in the paragraph above
it.

With the decay understood, the events classify themselves:

    f6537  puddle  255 -> 224       f9747  CRASH   slot 06  type 3, a car
    f7263  puddle  255 -> 224       f9753  decay   237 -> 208, during the crash
    f7479  CRASH   slot 01  type 1  f10137 -16 flat 146 -> 130
    f8379  puddle  255 -> 224       f10965 puddle  255 -> 224
    f9105  puddle  255 -> 224

    f3132 and f11007 are NOT decays -- see the ramp below.

### The scripted stop, and two false positives

Two more events first read as decays, at f3132 (136 -> 119) and f11007
(140 -> 123). They are not. Sampling every frame through those windows shows a
constant step, not a proportional one:

    f3126  153 136 119 102 85 68 51 34 17 0      -17 every 6 frames
    f10990 174 157 140 123 106 89 72 55 38 21 4 0

`153 - 153/8` is 134, not 136, so the formula does not describe the sequence.
This is a **scripted deceleration of 17 per step, every six frames, to a dead
stop** -- `153` is `9 x 17` and lands exactly on zero. A screenshot at f3185
shows the car stopped under QUALIFYING POSITION 1 2 3 4 5 6 7 8, and the
second ramp runs out the end of the recording when the clock expires. It is
the stop at the end of qualifying and at time-out.

Both were flagged only because `136 >> 3` and `140 >> 3` are both 17, the same
as the ramp's step. So the aliasing band matters more than first stated: a drop
of `speed >> 3` is a puddle **except** at speed 136-143, where it cannot be told
from the scripted ramp, and at 128-135, where it cannot be told from the flat
-16 at `SpeedPenalty16`. Outside 128-143 the classification is unambiguous, and
all five confirmed puddle hits are at a saturated 255, well clear of it.

## The collision system

`ObjectCollision` at rom:C86E walks sixteen object slots each frame, reached
through the indirection `ObjSlotList,Y`, and every slot carries:

| table | meaning |
|---|---|
| `ObjType,X` (`$19B4`) | flags; the low three bits are the type |
| `ObjZLo`/`ObjZHi` (`$19C4`/`$19D4`) | 16-bit distance up the road |
| `ObjLateral,X` (`$1A00`) | position across the road |
| `ObjLatOffset,X` (`$1A2E`) | per-object lateral correction |

A slot is in range only if the high byte of Z is `$00` with a low byte under
`$4E`, or `$FF` with a low byte of `$D3` or more -- that is, just ahead or just
behind. Then rom:C8AA walks Y down from `$4D` through the 78-entry perspective
table (`dat_PerspectiveZHi`, `dat_PerspectiveZLo`) to convert Z into the screen
row the object draws on, rom:C8D0 forms

    | scaled_x - ObjLatOffset,X - $40 - PlayerX |

and compares it against `$1E` (30) when the object is near and `$1A` (26) when
it is far. Under the threshold is a contact, and `CollisionContact` at rom:C907
dispatches on the type:

| type | stamped at | what it is | on contact |
|---|---|---|---|
| 0 | -- | empty slot | -- |
| 1 | rom:CF54, from track data at `$18B4` | roadside sign, lateral 35/36 | **crash** |
| 2 | rom:D010 (`LDA #$C2`) | **puddle**, lateral 15-18 | `SpeedDecay` |
| 3 | rom:CA0A (`LDA #$43`) | rival car | **crash** |
| 7 | rom:CB0E (`LDA #$FF`) | sentinel, always slots 7 and 8 at negative Z | -- |

Only type 2 decays. Everything else falls into `CrashStart` at rom:C93E, which
records the slot in `CrashSlot`, sets `CrashTimer` to `$20`, and fires sounds 7
and 8. The recovery is at rom:C5E8: `CrashTimer` counts down, and at zero the
speed is restored and `CrashSlot` is put back to `$FF`.

### Type 2 is the puddle, and one dodge proves it

`SpawnObjectCommon` at rom:D015 gives every object it places a lateral of
`($B9 >> 1 AND 3) + $0F` -- 15 to 18, the middle of the road, where type 1
roadside furniture sits at 35/36. Photographing a type-2 object at close range
shows a blue patch on the road surface, on a frame with no rival car nearby to
confuse it.

The timing settles it. Sampling every frame where a type-2 object is about 250
units out gives six approaches, and five produce a decay exactly 18 frames
later:

| puddle at z~250 | PlayerX | event |
|---|---|---|
| f6519 | `$00` | DECAY f6537 |
| f7245 | `$16` (22) | DECAY f7263 |
| f8361 | `$07` | DECAY f8379 |
| f9087 | `$FB` (-5) | DECAY f9105 |
| f10113 | **`$D1` (-47)** | none |
| f10947 | `$11` (17) | DECAY f10965 |

The puddle sits at lateral 17. On five approaches the player was within about
twenty of it and hit it; on the sixth the player was 47 to the left and missed.
The exception is the confirmation, not a hole in it -- the lateral threshold is
doing exactly what rom:C8E0 says it does.

### Which crash is the sign

The two crashes are different types, so the question answers itself:

* **f7479** is slot 1, **type 1** -- the sign. Every type-1 object in every
  dump sits at lateral 35 or 36 with a zero offset, at the road edge, recurring
  at regular Z spacing (1022, 2022, 4022 on one lap; 941, 3441, 8441 on
  another). That is roadside furniture, and the screenshot has the car off the
  road on the grass at 217mph.
* **f9747** is slot 6, **type 3** -- a rival car, at Z `$FFEF` (-17), right on
  top of the player. The screenshot shows the player's car overlapping the car
  ahead. A rear-end, not the sign.

### Finding the events reliably

`tools/probe-events2.lua` and `tools/probe-events3.lua` detect and classify
every event from per-frame polling of state the game itself maintains --
`Speed`, `CrashSlot`, `CrashTimer` and the object tables -- with no write taps
anywhere. A drop of precisely `speed >> 3` is a puddle by construction, since
`SpeedDecay` has exactly two xrefs and both are inside `CollisionContact`.

The one ambiguity is the band at speed 128-143, described above, where the
proportional drop collides with the flat `-16` and with the scripted ramp's
`-17`. A detector that cares about the difference should check whether the
step repeats at a constant value before calling it a puddle.


### A note on the instrument, not the game

Write taps on `$CE` reported **nothing at all** across the crash while the
value demonstrably changed every few frames. The taps are not reliable here:
the only one that ever fired was the BIOS clearing RAM at frame 1. Tapping
the mirror at `$20CE` as well as `$00CE` was necessary and still not
sufficient.

The listing found all six writers of the byte immediately. Where MAME's
instruments have been unreliable all through this project, the disassembly
has not been -- and it should be the first place looked, not the fallback.

## The physics, and 929 bytes that were hiding behind a JMP

Six routines wrote `Speed`, and not one of them accelerated the car. That was
the tell. `rom:D701` sits in the listing as a nine-byte gap, and those nine
bytes are three well-formed calls:

    D701: 20 D3 C1   JSR $C1D3     into a 442-byte gap
    D704: 20 00 C6   JSR $C600     into a 119-byte gap
    D707: 20 05 C7   JSR $C705     into a 176-byte gap

It is a gap only because `rom:D6FE` does `JMP sub_D70A` and steps straight
over it -- the penalty path skipping the normal update. Nothing reachable
calls `$D701`, so the tracer never entered, and three entire routines stayed
dark. Declaring `rom:D701`, `rom:C1D3`, `rom:C600`, `rom:C705` and `rom:C3B2`
as entries took coverage from 27.5% to **30.3%** (+929 bytes, +471
instructions) and turned six `Speed` writers into fourteen.

`--check-gaps` had listed all of this under "70 coincidences", which is
correct by its own rule and useless here: nothing inside an unreached region
can be an instruction start, so the test cannot distinguish dead data from
live code that simply has no reachable caller. What actually settled it was
the internal consistency -- `$C25A` and `$C2A4` both `JSR $C3B2`, `$C317` and
`$C333` both `JMP $C33A`. Independent references converging on the same
targets are not coincidence.

### The gear, found at last

`Gear` is `$DB`, and it is written in exactly two places, each of which also
writes the two HUD characters for it:

| routine | `Gear` | HUD at `$1FC6`/`$1FC7` |
|---|---|---|
| `SetGearLo` rom:C47A | `$00` | `$9F $A2` = LO |
| `SetGearHi` rom:C489 | `$10` | `$9D $9E` = HI |

That closes an open question that had eleven candidate bytes and no way to
choose between them. The value is not a flag, it is *an index*: rom:C2F6 forms
`(Speed >> 4) + Gear` and reads `dat_AccelCurves`, so LO uses entries 0-15 and
HI uses 16-31 of one 32-byte table.

    LO  03 05 07 08 07 06 05 04 03 02 00 00 FF FF FE FC
    HI  01 01 01 02 03 05 07 06 05 04 03 02 01 01 01 01

LO pulls hardest at 48-63mph and then goes **negative** above about 192, so it
actively brakes the car -- a top speed near 176. HI barely moves off the line
at +1 but never stops pulling, which is the only way to reach the 255 the HUD
saturates at. The whole gearbox is thirty-two bytes.

### Every way the car loses speed

| mechanism | amount | where |
|---|---|---|
| accelerator held | `+dat_AccelCurves[(Speed>>4)+Gear]` | rom:C2F6 |
| accelerator released | **-5** | rom:C340 |
| brake (`InputBrake`) | **-10** | rom:C352 |
| skidding | **-((Speed>>5) & 3)** | `SkidDrag` rom:C3B2 |
| puddle | **-Speed/8** | `SpeedDecay` rom:C92F |
| clock expired | **-15** | rom:C2E0 |
| crashing | **-25** | rom:C2C0 |
| scripted stop | **-16 or -17** | rom:D6EE |

The scripted stop is worth a note: `LDA Speed / SBC #$10` has **no `SEC`** in
front of it, so with carry clear it subtracts 17, not 16. That is exactly the
`-17` ramp measured off the qualifying and time-out stops, and it means the
routine's name is a slight lie in a way the listing makes obvious.

## Skidding, and dragging along the edge

`SteerAndLimits` at rom:C4F7 does two things. Steering is speed-scaled: rom:C515
walks an eight-entry threshold table and accumulates the input once per
threshold the current speed clears, so the car moves further sideways per frame
the faster it goes. Then rom:C537 applies the track limits:

| `PlayerX` | zone |
|---|---|
| \|x\| < 60 (`$3C`/`$C4`) | on the road |
| 60 to 103 | off the road, on the verge |
| 104 (`$68`/`$98`) | hard clamp, **and `LateralVel` is zeroed** |

In `run-02` the clamp never engages -- the furthest out is 102 -- so the outer
wall is never reached. There were eight verge excursions.

### The drag is the skid, not the verge

`SkidCheck` at rom:C269 takes `X = Speed >> 5` (0-7), and skids the car when
`|LateralVel - RoadCurve|` reaches `dat_SkidThresholds[X]`: **24, 24, 22, 20,
19, 18, 16, 14**. The wheels are pointing one way and the car is going another,
and the faster it goes the less divergence it takes. On a skid rom:C297 starts
sound 3, the screech, and sets `SkidFlag`; rom:C2A4 then calls `SkidDrag`, which
is the only caller path that costs speed. rom:C2AA is the exit, stopping sounds
3 and 4.

Measured across `run-02`: 234 frames of skidding in eight episodes, **every one
of which loses speed**.

    f5145 ..5168   24 fr  verge   0%   229 -> 223   (-6)
    f5349 ..5408   60 fr  verge  38%   239 -> 188  (-51)
    f6819 ..6842   24 fr  verge   0%   253 -> 247   (-6)
    f7227 ..7238   12 fr  verge   0%   253 -> 251   (-2)
    f7449 ..7478   30 fr  verge  77%   234 -> 217  (-17)
    f9123 ..9134   12 fr  verge   0%   224 -> 222   (-2)
    f9537 ..9560   24 fr  verge   0%   253 -> 247   (-6)
    f9723 ..9764   42 fr  verge   5%   248 -> 180  (-68)

**79% of the skidding happens on the road.** So skidding is a cornering
mechanic and the verge is where a bad one puts you, not its cause -- there is
no separate off-road drag anywhere in the speed code. The apparent one is real
but indirect: with the throttle held and crashes excluded, speed falls on 6.2%
of verge frames against 0.56% on the road, an eleven-fold difference, and the
skid accounts for it.

The episode at f7449-7478 makes the chain explicit. It is 77% on the verge and
ends **one frame before the crash at f7479** -- the slide ran the car off the
road and into the sign. The two are one event, not two.

## The game-state machine, and sixteen handlers behind an indirect jump

`sub_D253` at rom:D253 is the main loop's dispatcher. It waits for the frame
tick, then:

    LDX $9D                    ; the game state
    LDA dat_StateHandlersLo,X / STA $40
    LDA dat_StateHandlersHi,X / STA $41
    JMP ($0040)

Two parallel tables again -- low bytes at rom:A7C2, high bytes at rom:9CCF --
the same shape as the DLI handler table at rom:A48A. A tracer cannot follow
`JMP ($0040)`, so **sixteen of the twenty handlers were sitting in gaps**.

Three of the targets land exactly on a gap's start address (`$D2D3`, `$D4B6`,
`$D725`), which is what confirms the table rather than merely suggesting it --
a random 16-bit read has no reason to hit a boundary the coverage map drew
independently. Entry 11 is `$D3F7`, `QualifyingPosition`, identified months
earlier from screen behaviour and never connected to a caller until now. Entry
20 reads `$00AA`, outside ROM, so the table is exactly twenty long.

States 2/16, 3/17, 4/5 and 6/7 share handlers. Declaring all sixteen took
coverage from 30.3% to **33.5%** and emptied every dark gap in the `$D` page:
`$D4B6` (562 bytes), `$D2D3` (209), `$D9D5` (97), `$D82B` (93), `$DB40` (60)
and `$D725` (30) were all state handlers.

### What is left, and what kind of thing it is

21,412 bytes remain in 21 ranges, but they are not all the same kind of
unknown. Sorting them by whether traced code already reads into them:

**Data the code demonstrably uses** -- these are understood in role if not in
detail, and closing them is declaration work, not discovery:

| range | bytes | reads from traced code |
|---|---|---|
| `$AE2F-$C17D` | 4943 | 107 reads, 36 addresses |
| `$A7D6-$AE23` | 1614 | part of the 89-read `$A4A2` region |
| `$8000-$9CCE` | 7375 | the graphics block; the display list names `$87xx`-`$8Bxx`, `$9Exx`, `$AAxx`, `$B0xx` |
| `$DE0D-$DEC7` | 187 | 48 reads, 24 addresses -- dense, likely the sound tables around `sub_DED6`/`sub_DEF3` |
| `$DBB0-$DBDE` | 47 | 14 reads |

**Silent** -- nothing traced touches these at all, which is exactly where the
physics and the state handlers were both found:

| range | bytes | note |
|---|---|---|
| `$F281-$FFFF` | 3455 | includes the 6502 vectors at `$FFFA` |
| `$E049-$E285` | 573 | the largest silent range left |
| `$E80F-$E8AB` | 157 | |
| `$EA41-$EAB8` | 120 | |
| `$EB07-$EB55` | 79 | sits between the two perspective tables |
| `$EBA4-$EBEE` | 75 | runs up to the NMI at `$EBEF` |
| `$C955-$C964`, `$C96D-$C975` | 25 | either side of `dat_SkidThresholds` |

`--check-gaps` now reports no gap stepped over by a JMP, no real call site into
any gap, and two `JMP ($xxxx)` through RAM pointers: rom:D26A, which is the
dispatcher above and now resolved, and rom:EC06, the DLI table, whose index-0
handler at `$2456` remains the one entry nothing selects.

## The sound engine

No POKEY on this cartridge, so everything is the TIA two voices. `$2102` and
`$2103` hold the sound id playing on voice 0 and voice 1, `$FF` meaning free --
which retrospectively explains the `ram_2102,X` reads inside the collision
handler that looked unmotivated when the puddles were found. That code was
asking whether the splash was already playing before retriggering it.

Three entry points: `SoundStart` rom:DEF3 (id in A), `SoundStop` rom:DED6, and
`SoundSilenceAll` rom:DEC8. `SoundUpdate` rom:DF3D runs the sequencer each
frame and does nothing in states 1 and $13.

**Each sound has three independent byte streams**, not one -- pitch to `AUDF`,
waveform to `AUDC`, and a volume envelope to `AUDV`, each advanced by its own
per-voice index (`SndPitchIdx`, `SndAudcIdx`, `SndAudvIdx`). The pointers live
in four parallel 20-byte tables at `dat_SndStreamPtrs` rom:A558 plus two more at
`dat_SndVolPtrs` rom:E049. In a stream, `$FF` ends the sound and frees the voice,
`$FE` and `$FD` are escapes, and a byte with bit 7 set means hold rather than
advance (rom:E017 does `BPL` then `DEY`).

### Priority, and why the engine never wins

With only two voices, `SoundStart` arbitrates: when both are busy it compares
`dat_SndPriority` for the incoming sound against what is playing and takes the
voice only if it outranks it. The whole scheme reads off the table at a glance:

| sound | priority | what it is |
|---|---|---|
| `$0F` | **0** | the engine -- anything at all steals its voice |
| `$0E` | 2 | |
| `$02` | 3 | puddle splash |
| `$10` | 4 | road rumble |
| `$03`,`$04` | 5 | skid screech, two voices |
| `$08` | 6 | crash |
| `$07` | 7 | crash |
| `$0B` | 8 | |
| `$01`,`$06`,`$0D` | 9 | |
| `$00`,`$05`,`$09`,`$0A`,`$0C`,`$11`,`$12` | 10 | |
| `$13` | **20** | race-start fanfare -- nothing interrupts it |

Putting the engine at zero is the whole trick. It is the one sound that plays
continuously, so making it the weakest means every effect simply borrows a voice
and the drone resumes underneath when the effect ends -- no ducking logic
anywhere.

### The engine note is computed, not sequenced

Sounds `$0F` and `$10` do not read their streams at all; rom:DF56 special-cases
`$0F`, and both point at dummy addresses in the graphics block. They are driven
by `EngineNote` at rom:C38D instead:

    EnginePitch ($210D) = 30 - (Speed >> 4),  minus 3 more in LO gear
    EngineRate  ($210C) =  8 - (Speed >> 5)

`AUDF` is a divisor, so as speed rises the value falls and the pitch rises, and
the rate value falls too so the sound pulses faster. LO gear sits three lower --
revving higher at the same road speed, which is what a real gearbox does. The
whole engine is nine instructions.

### What actually plays in run-02

Sampling both voice slots every frame:

    $10  30 starts   road rumble
    $0F  14 starts   engine (restarted each time an effect steals its voice)
    $03  11 starts   skid screech      -- matches the eight skid episodes
    $04  10 starts   skid, second voice
    $02   7 starts   puddle splash
    $07   2 starts   crash  }  exactly the two crashes at f7479 and f9747
    $08   2 starts   crash  }
    $0C   2 starts   score tally  } both at f11061, just after the clock
    $0D   2 starts   score tally  } expired at f11055
    $13   1 start    race-start fanfare, once
    $05   1 start    } f11547, after the tally -- the game-over music
    $06   1 start    }

Four impossible ids also appeared -- `$55` at f1, `$AC` at f17, `$64` and `$E3`
at f72. All of them are before the cartridge owns that RAM: the BIOS runs about
133 frames first, so anything sampled by frame number that early is measuring
the logo screen, not the game. They are init garbage, not a twenty-first sound.

## The track format

`LoadTrack` at rom:D917 is fully parameterised by `TrackIndex` (`$C4`), and
every table it touches is indexed by it:

| table | per track |
|---|---|
| `dat_TrackStreamPtrs` rom:C955/rom:C959 | stream A pointer |
| `dat_TrackStreamPtrs` rom:C95D/rom:C961 | stream B pointer |
| `$AAD4` / `$A4AA` | length of stream A / stream B |
| `$ABD4` | initial object cursor |

Four entries in each, so **four tracks**. The sixteen bytes at `$C955` were an
unexplained gap until the loader was read.

### One byte per segment, two nibbles

Each byte of a track stream packs two fields, expanded at rom:D949:

    low nibble  -> index into dat_SegLengths, a menu of 14 lengths
    high nibble -> curvature, minus 5, so -5 to +10

The length menu is what identifies the format. Read as 16-bit pairs -- low
bytes at `$A197`, high at `$A1A5`, which the road code accumulates as a pair at
rom:C4E7 -- they come out as round decimal numbers:

    300  500  900  1000  1500  2000  2500  3000  5000  5300  10000  1200  600  800

Nothing else about the encoding is ambiguous once those are recognised. A first
reading had the nibbles the other way round; the round numbers settle it.

Stream B is a second, shorter list with its own length, using the same length
menu but packing a roadside-object descriptor into the high bits instead of a
curvature: bits 7-5 and bit 4 are recombined at rom:D97E into `SegObjDesc`
(`$18B4`), which is exactly what rom:CF54 later reads to build the type-1
roadside signs the car can crash into.

### The four tracks, decoded

| track | segments | total length | recording |
|---|---|---|---|
| 0 TEST | 27 | 42,500 | `run-01` |
| 1 FUJI | 41 | 45,000 | `run-02` |
| 2 SUZUKA | 85 | -- | |
| 3 (fourth) | 89 | -- | |

Both recordings confirm the static read exactly: sampling `TrackIndex` live gives
track 0 with lengths 26/17 for `run-01` and track 1 with 40/16 for `run-02`,
matching `dat_AAD4`/`dat_A4AA` byte for byte.

TEST decodes as a literal rounded rectangle:

    straight 5000    CORNER 2500 [-1/-2/-3/-2/-1]
    straight 5000    CORNER 2500 [-1/-2/-3/-2/-1]
    straight 10000   CORNER 2500 [-1/-2/-3/-2/-1]
    straight 5000    CORNER 2500 [-1/-2/-3/-2/-1]
    straight 5000    CORNER 2500 [-5]

Four identical corners, all turning the same way, separated by straights, and a
fifth closing corner joining back to the start. That is the track as described
from playing it, recovered from the ROM without reference to the screen.

FUJI is a real circuit by comparison -- corners of differing severity including
a nine-segment hairpin:

    straight 7500    CORNER 3500 [+1/+2/+3/+4/+3/+2/+1]
    straight 1000    CORNER 3000 [-1/-2/-1]
    straight 1000    CORNER 3500 [+1/+2/+3/+4/+3/+2/+1]
    straight 1000    CORNER 3200 [-1/-2/-3/-4/-5/-4/-3/-2/-1]
    straight 300     CORNER 13500 [+1/+2/+1/+2/+3/+2/+1]
    straight 2500    CORNER 5000 [+4]

The curvature ramps symmetrically in and out of every corner rather than
stepping, so the road eases. Each closing corner is a single unramped value,
which is the seam where the lap joins.

## Phase 1 prototyping: a second static view, and a real MARIA timing rule

Not reverse-engineering in the usual sense -- this is notes from actually
patching the ROM, in service of the two-player split-screen research -- but
a genuine hardware fact came out of it that belongs here.

**The mechanism is proven.** Repointing zone 0 and zone 1's selectors (in
`dat_BC7E`, the boot-time template) from the shared empty terminator to a
new, hand-written object list dropped into free ROM space at `$F400` gets
MARIA to draw content that didn't exist before -- confirmed by screenshot,
with the game's score and timing byte-identical to the unpatched run at the
same frame (the input recording stayed in sync; nothing about gameplay
changed). Zero new instructions were needed for this part.

**Object height must match the zone's line count, not be chosen freely.**
`docs/graphics.md` in the shared toolkit already said why: MARIA fetches
scanline *n* of an object from *page* `base + n`, not from a contiguous
block, so a zone declaring more lines than the graphic was authored for
reads into whatever ROM happens to sit at the following pages. Zones 20-32
each declare exactly as many lines as their graphic is tall (6-8); the first
prototype attempt didn't match this (16 and 10 lines against 6- and
8-line-tall graphics) and produced a plausible-but-wrong shape as a result.
Matching the line count to the graphic's real height fixed it immediately.

**A zone's display-interrupt bit fires at the *end* of that zone, not the
start.** Byte 0 bit 7 of a zone selector is documented (`docs/hardware.md`)
as "trigger a display interrupt at the end of this zone" -- easy to read
past, and easy to assume means "at the start" instead, which is what this
session did at first. The practical consequence: zone 0's own DLI
configures the palette for zone 1 onward, never for zone 0 itself.

**The DLI-index dispatch table has 12 slots, and which ones actually run
changes with game state -- confirmed by tracing it live, not by reading the
table once.** `dat_DliHandlerTable`/`dat_A496` (`rom:A48A`/`A496`) map
`ram_00FF` to a handler address; index 0 is the long-documented dead entry
(`$2456`, never installed). Tracing every write to `ram_00FF` around frame
212 (just after race setup) shows the chain looping **1->2->3->4->6->1**
(`DLI_EC10` is index 1) -- and tapping `$EC10` as an executed address
across the whole race shows it fetched 1,051 times, **last at frame 1260,
never again**. Tracing the same chain again at frame 3000 shows a
completely different loop, **7->8->9->10->11**, with `ram_00FF` forced to 7
every frame by an unrelated routine (`rom:F169`, part of the per-frame
setup that also reads the controller) -- `DLI_EC10` never enters the chain
at all once real driving starts. The first attempt at this fix spent
considerable effort editing `DLI_EC10` -- confirmed live to execute exactly
as written, every frame, right up until frame 1260 -- and correctly saw no
effect on a frame-3000 screenshot, because by then that handler is simply
not running. Not a failed patch; the wrong handler, identified before this
was traced and corrected after.

**The real handler is `DLI_ECA1` (index 7), and the fix is one byte.**
Reading it fully: it re-reads the controller, sets `ram_00FF=8` (chaining
to the next handler), sets `BACKGRND`, then does `LDA #$00 / STA P2C1 /
STA P2C2 / STA P2C3` -- all three registers zeroed from a single shared
load. Changing that one immediate (`rom:ECAD`, `$00`->`$8B`) turns a test
object drawn under palette 2 from solid black to solid grey, confirmed by
screenshot, with score and timing still untouched. A full three-tone grey
(matching the road's real `$89`/`$8B`/`$8D`) would need three separate
loads where the original has one shared load -- a small instruction-count
increase, not attempted here, since a single flat tone was enough to
confirm the mechanism.

**The design implication for a second camera:** *which* DLI actually governs
a given zone during real gameplay cannot be read off the static table or
assumed from a zone's own trigger bit -- it depends on which state the
12-slot chain is in, which itself changes with game phase (qualifying vs.
race, confirmed here as one concrete example). The only reliable way to
find the *active* handler for a specific frame is to trace `ram_00FF`
writes live at that frame, the same way this session eventually did.
Assuming zone 0's own DLI (`DLI_EC10`) governs zone 0's neighbourhood at an
arbitrary point in a race turned out to be wrong twice over: wrong end of
the zone, and -- separately -- wrong handler for that point in the game.

**A smaller correction from the same pass:** the HUD text object decoded
earlier in this document was read as palette 3, from its header byte's
upper three bits. That byte (`$60`) has bit 5 set, which `docs/hardware.md`
identifies as the indirect/character-mode flag for the 5-byte DL entry
format -- meaning those bits are not a palette at all in this format, and
the HUD text is in character mode, not direct mode as assumed. Its real
palette lives in *byte 3* instead (moved there in the 5-byte layout), and
reads as palette 2 for all three HUD rows checked -- the same palette the
road itself uses, not a separate one.

## The cartridge signature affects recording playback -- through timing, not validity

Found while moving the split-screen work from ad hoc byte edits into a proper
`.abp` bundle (`patches/splitscreen.py`), and worth recording on its own,
separately from that patch, because it applies to every recording this
project has and every patch it will ever build.

The build applied cleanly through `tools/patchset.py apply` -- correct
anchors, correct target match, and (via the manifest's `"region": "ntsc"`)
a freshly *valid* cartridge signature, exactly as it should for something
meant to run on real hardware. Replayed against `run-01.inp`, it landed on
the wrong score, gear and speed at frame 8000. Not a crash, not visibly
broken -- a complete, plausible-looking race that simply was not the one the
recording asked for.

Diffing the result against the same edits built *without* signing found
the entire discrepancy confined to exactly 120 bytes: `$FF80-$FFF7`, the
signature block itself, and nothing else. Nothing in the disassembled ROM
reads that range -- checked directly, not assumed -- so the game's own code
cannot be the cause. `sign7800.verify()` makes the shape of it clear:
the unsigned build's original, untouched signature bytes report `False`
(correctly -- this patch's edits invalidate them), yet that is the build
that reproduces the recording exactly. The freshly-signed build reports
`True` and desyncs. A third version, with the signature block simply
zeroed, gives a third result, different from both. All three are
individually deterministic -- rerunning any one of them reproduces the same
"wrong" score every time -- so this is not jitter or a race condition; it is
a function of the exact byte content of that block.

The mechanism this points to: the BIOS's signature check is a modular
squaring (`sig^2 mod N`, the scheme's own public exponent), and squaring's
running time on a 6502 plausibly depends on the operand's bit pattern --
not on whether the final comparison against the cartridge hash passes or
fails, which is a cheap step at the very end. Different signature bytes,
valid or not, cost a different number of cycles to check, and a boot
sequence timed to the cycle is exactly what a frame-perfect input recording
cannot absorb a shift in.

**Practical rule, now written down rather than rediscovered per patch:** a
build meant to replay against an existing recording must carry the
recording's *exact* signature bytes -- which for every recording in this
repo means the original cartridge's, untouched, even though that makes the
signature cryptographically invalid for edited content. A build meant for
real hardware, or for a fresh recording made against it specifically, needs
a valid signature instead. These are different requirements and satisfying
one does not satisfy the other. `patches/splitscreen.py --build` defaults to
unsigned for exactly this reason, with `--sign` (or `patchset.py apply`'s
automatic resigning) opt-in for the other case.

## Phase 1: the top display, mirroring player 1

The first working second view. Thirteen bytes, no new instructions.

**The trick is that the road's zones don't own their object lists.** Zones
20-32 point at sub-lists in RAM (`$2300`, `$2326`, `$234C`, ...) which the
per-scanline DLI chain rewrites every frame with fresh curve-driven `x`
positions (see the curve section above). Pointing a *sky* zone's selector at
one of those same RAM addresses makes it draw the same band, tracking the
same curve, for free -- no second copy of anything, no new code.

Zones 8, 9 and 10 were the candidates: 8 lines each, contiguous, empty, and
well clear of the HUD rows. Repointed at road zones 20/21/22's sub-lists,
with their line counts cut 8->6 to match the graphics' real height (the rule
recorded above), and zone 11 grown 3->9 to absorb the six freed lines so
nothing below shifts:

    zone  8   n=8 dl=$22C7  ->  n=6 dl=$2300
    zone  9   n=8 dl=$22D1  ->  n=6 dl=$2326
    zone 10   n=8 dl=$22DB  ->  n=6 dl=$234C
    zone 11   n=3           ->  n=9          (DLI bit preserved)

**Colour needed three more bytes, and the reason is worth recording.** Road
objects declare palette 1, but palette 1 holds different values at the top of
the screen than at the road: `DLI_ECA1` (governing zones 1-19) sets
`P1C1/C2/C3` = `$24`/`$28`/`$80`, while `DLI_ED4F` (governing the road at
zones 20+) sets them to `$34`/`$04`/`$04`. Same objects, same palette number,
different colours -- the `$80` is why the first mirror rendered navy blue.
Matching `DLI_ECA1`'s palette 1 to the road's fixed it: `rom:ECCB` `$24`->`$34`,
`rom:ECC7` `$28`->`$04`, and `rom:ECB5` `$80`->`$04` (that last one is a load
shared with `P0C3`/`P4C3`/`P5C3`; changing all four showed no visible harm to
the HUD, sky or hills).

Verified against `run-01` at two frames: at 3000 the mirrored band is skewed,
at 8000 it is a symmetric perspective trapezoid -- it tracks the live curve,
because it is literally reading player 1's own sub-lists. Score, lap and speed
readouts are byte-identical to the unpatched run at both frames, so nothing
about gameplay is disturbed.

Still cosmetic, and left alone deliberately: the roadside-sign objects carried
in those same sub-lists mirror too, in the wrong palette (green rather than
white), for the same class of reason as the road strips did.

## The full mirror: ten bands, and why three were not enough

Extending the three-band mirror to ten (sky zones 8-17 -> road zones 20-29)
settles a question raised looking at the short version: the mirrored bands
looked wrong during a curve -- the real road's edges both lean one way, while
the three mirrored bands seemed to slant toward the middle.

They were faithful. The road's curvature is carried entirely by the `x` byte
(see the curve section above), and **the offsets are not monotonic down the
screen.** At a left-curving frame the near bands step left going down
(zone 28-32 `x` = 15, 14, 8, 2, 253) while the far bands step *right*
(zone 20-22 `x` = 10, 19, 22). Three far bands therefore show a short
right-leaning wedge -- correct, and nothing like a curve, because a curve only
emerges once enough bands' offsets accumulate. With ten bands the mirror bends
the same way as the road below it, and the player's car, the rumble strips and
the dashed centreline all appear.

**Zone budget, for anyone extending this further.** The sky has room but it is
fragmented. Zones 8-17 are ten usable slots (63 lines) once the HUD rows
(2, 4, 6) are avoided, which is enough for ten 6-line bands with three lines
left over -- parked on blank zone 1 (`n` 10 -> 13) so the total stays at 249
and nothing below shifts. Zones 11 and 15 carry DLI bits that must be
preserved when their line counts change (`$82` -> `$85`, not `$05`).

**Zones 12, 13 and 14 are not in the boot template.** Their selectors are
rewritten at run time from two ROM tables, `dat_A6BB` (`rom:A6BB`) and
`dat_A6CD` (`rom:A6CD`), nine bytes each, by the pair of routines that drive
the "POLE POSITION!" banner -- whichever ran last wins, and both paths occur
during a normal race. Patching only `dat_BC7E` leaves those three zones
reverting. Patching both tables holds, at the cost of the banner, which shares
them.

Total: 43 bytes, no new instructions. Score, lap and speed readouts remain
byte-identical to the unpatched run at both frames checked.

## Relocating the HUD: a real two-viewport screen

With the mirror proven, the next structural step was moving the HUD out of the
top of the screen so the two views could sit above and below it. The result is
a screen that is genuinely laid out as split-screen:

    zone  0        16   blank top margin
    zones 1-11     67   player 2's view (ten bands + a gap)
    zones 12-14    21   HUD, three rows -- the centre divider
    zones 15-17    15   blank
    zones 18-19    20   horizon decoration
    zones 20-32    78   player 1's road
    zones 33-34    32   blank

**The HUD had to go to zones 12/13/14 specifically**, because those are the
three the banner tables (`dat_A6BB`/`dat_A6CD`) rewrite at run time -- anywhere
else and the banner code would stamp over it. Putting the HUD there
co-locates the two things that share those slots, which is what the layout
wanted anyway. Zones 2, 4 and 6, freed by the move, become view bands.

**Read mode has to follow the layout.** The HUD's text objects are character
mode and render under CTRL read mode 3; both road views render under mode 0.
So the mode now switches with the structure rather than against it:
`DLI_ECA1`'s tail changed from `ORA #$03` to `AND #$FC` (zones 1+ = mode 0 for
player 2's view), zone 11's DLI back to `sub_EC67` (zones 12+ = mode 3 for the
HUD band), and zone 15's DLI already returns mode 0 for everything below. Get
this wrong in either direction and the symptom is not obvious -- the HUD
garbles, or road bands decode as the sawtooth-edged wrong shape described
below.

`BACKGRND` likewise moved: `DLI_ECA1` now loads the road's ground colour
(`$1B`) rather than sky, so player 2's view sits on ground like player 1's.

Line budget is unchanged at 139 lines before the road, so player 1's view and
everything below it is untouched; score, lap and speed still read identically
to the unpatched game.

Known rough edges, all understood rather than mysterious: player 2's bands
still stair-step for the reason in the next section; the three HUD rows are
adjacent with no gaps between them (the originals were spaced by separate
zones that no longer sit between them); and the view is still a mirror, not an
independent camera.

## Why a mirror can never be smooth: the curve is injected per scanline

The ten-band mirror still rendered a sawtooth left edge where the road below
is a smooth curve. The cause is the most important structural fact found so
far for the split-screen work.

`$2303` is zone 20's x byte. Tapping it shows **six writes per frame** -- one
per scanline of that six-line band -- with values `FF 01 03 06 08 0A`, a clean
two-units-per-scanline ramp. `$2301` (its palette/width byte) is likewise
written six times. The road's DLI chain (`DLI_ED4F` onward, `rom:ED9D`-`EE60`,
unrolled and `WSYNC`-paced) is rewriting each band's sub-list *between
scanlines, while MARIA is drawing it*.

So a band's entry in RAM is not "the band's position". It is a scratch slot
that holds one scanline's position for as long as that scanline takes. Reading
it at any other point in the frame gives whatever the last injection left
there.

That is exactly what a mirror does. Sky zones 8-17 render roughly eighty
scanlines before the road, so each mirrored band reads one static x and holds
it for all six of its lines. The result is correct to band resolution and
wrong to scanline resolution: a stair-step where the original is a curve. It
shows worst on the left edge because that edge *is* the x byte; the right edge
is x plus width, and the per-band width changes partly mask the same stepping.

**Consequence, and it is a firm one.** Pointing a second view at player 1's
sub-lists gets geometry, colour and stripe animation for almost nothing --
everything above -- but it cannot get smoothness, because smoothness is not
stored anywhere. It is produced by code running in lockstep with the beam. A
faithful second view needs its own injection pass over its own scanlines,
fed from the staged row tables (`ram_1B00`/`ram_1B4E`), which is real
WSYNC-paced code rather than a table edit.

Scope, for planning: the existing injection is an unrolled run of roughly
eighty writes with `STA WSYNC` between them, and `dmabudget.py` charges a
display interrupt at 16.6 cycles plus whatever the handler itself costs.
Doubling it is well inside the measured frame surplus (~23,800 cycles), but
it is the first part of this project that has to be written rather than
repointed.

## How the road's stripes animate: palette switching, not palette cycling

Raised as a hypothesis while reviewing the mirrored top display -- that the
red/white rumble strips and the dashed centreline might be animated by cycling
palette colours. Close, and the real mechanism is worth writing down exactly.

The palette *registers* do not cycle. `DLI_ED4F` sets the road's colours from
literals, and the two it takes from RAM (`ram_00FA`/`FB` for `BACKGRND`,
`ram_00FC` for `P0C2`) are flat across thirty consecutive frames at full
speed -- measured, not assumed.

What changes is *which palette each object declares*. Logging the road
sub-lists across consecutive frames shows the palette|width byte alternating
by exactly `$20`, which is bit 5 of the palette field:

    zone 20   3A 3A 3A 3A 1A 1A 3A 3A 1A 1A 3A 3A
    zone 27   22 22 02 02 22 22 02 02 02 02 22 22
    zone 31   30 30 10 10 30 30 10 10 10 10 30 30

`$3A` is palette 1 width 6; `$1A` is palette **0**, same width. Identical
graphics, flipped between two palettes frame to frame. At the road those
palettes are deliberately dissimilar -- `DLI_ED4F` sets palette 0 bright
(`P0C1`/`P0C2` = `$0F`/`$0F`) and palette 1 dark (`P1C1`/`P1C2` = `$34`/`$04`)
-- so the strip pixels flash light/dark and read as motion. The alternation is
not a simple every-frame toggle; it holds for a frame or two at a time, which
is what makes the apparent speed of the stripes track road speed.

The x positions shift on the same frames, from the curve pipeline documented
above. The graphics addresses never change: `$8000` is the zone-20 strip on a
hard curve and on a straight alike. **All of the road's apparent curvature and
all of its apparent motion are carried by two things only -- the x byte and the
palette bit.** The pixels are constant.

**Consequence for a mirrored or second view:** faithfully reproducing the road
elsewhere on screen means matching *both* palettes 0 and 1 in whichever DLI
governs that region, not just one. Matching only palette 1 leaves every
"palette 0" frame rendering in the host region's unrelated colours, which
looks like a flicker or a wrong-coloured centreline rather than an obvious
palette bug.

## A higher-detail car sprite, from elsewhere, incorporated with credit

`patches/graphics_hack.py` / `dist/pp2-graphics-hack.abp` -- independent of
the split-screen work above, and not this project's own artwork.

**The redraw is by KevinMos3 and Defender_2600**, published on the AtariAge
forums 2014-04-12 as "Pole Position II Graphics Hack". All credit for the
sprite work is theirs; this project's contribution is narrower -- finding
exactly which bytes their release changed, so the change can be applied on
its own, combined with anything else here, and always with their names
attached, rather than only available bundled inside their standalone ROM.

**What actually changed, confirmed live rather than assumed.** Walking the
display list against `run-01.inp` (not a guess from the diff alone) finds
two objects, both width 8, palette 6: a 26-line main pose based at `$8B10`
(five road-band zones reuse it as 6-line slices, `$8B10`/`$9110`/`$9710`/
`$9D10`/`$A310` -- each exactly 6 pages, i.e. 6 scanlines, apart, the same
line-planar convention documented above) and a 6-line companion piece at
`$AAE8`. `tools/gfx.py` rendered both, before and after: same silhouette,
visibly more cockpit and shading detail in the redraw. Two more bytes,
`$EDE3`/`$EDE7`, recolour `P6C1`/`P6C2` -- the car's own palette -- to suit.
Nothing else from their release is reproduced: their build also carries its
own re-signed cartridge signature and a changed header title string, neither
of which is the sprite, and neither is included here.

**Composes cleanly with the split-screen patch, confirmed rather than
assumed.** The two touch entirely disjoint bytes (checked programmatically:
zero overlap), and `tools/patchset.py apply` accepts either bundle as a
target for the other, in either order, on the strength of the anchors
alone -- exactly the case `.abp`'s anchor design exists for. Applied
together and replayed against `run-01.inp`: score, gear and speed match the
unpatched run exactly, and the mirrored top view (Phase 1, above) shows the
redrawn car automatically, since it already reads the same live sub-lists
player 1's road does.

*Corrected later (after checkpoint 89):* this held for the mirror-era build
it was tested on, but not since the dead injection was reclaimed ("931 bytes
of the base ROM are dead", below). The hack's two palette bytes `$EDE3`/`$EDE7`
lie inside it, and the VS build no longer runs the stock code that read them.
See "The .abp bundle grows the cartridge".

One thing this option's `.abp` does that this project's own patches
deliberately avoid: its BPS necessarily carries the replacement bytes
themselves; a CRC32 can identify someone else's finished artwork but cannot
describe how to draw it. That is the deliberate, credited exception to the
policy in `patches/splitscreen.py`'s own docstring, not an oversight.

## The mirror was missing the car, and the divider was missing the light

Two follow-up requests against the working split-screen build: the player's
own car was visibly cut off at the bottom of the mirrored top view, and the
start light and "POLE POSITION! ####" banner had stopped appearing at all
since the HUD relocation (above) took over their zones. Both are fixed now;
the trail to get there is worth keeping, since two different wrong turns
were caught live rather than shipped.

**The car was cut off because the mirror simply didn't include the zones it
lives in.** `docs/FINDINGS.md`'s "a higher-detail car sprite" section had
already established that the confirmed car-sprite object spans five
consecutive zones, six lines apart ($8B10/$9110/$9710/$9D10/$A310-family
addresses). Dumping the live display list zone-by-zone (adapting
`tools/probe-dlgfx.lua`) at frame 3000 found that chain sitting in real
zones 27-31 -- but the mirror only ever pointed at real zones 20-29 (the
*first* ten of player 1's thirteen road bands), missing 30 and 31 entirely.
MARIA has no idea an object "continues" past a zone that doesn't reference
it; the bottom two-fifths of the car simply never got asked for.

The fix, once found, was one line: `ROAD_BANDS` now takes the *last* ten of
the thirteen (`ALL_ROAD_BANDS[3:13]`, real zones 23-32) instead of the first
ten. Verified by re-dumping the live DL: the car's full five-zone chain now
lands in mirror zones 6-10, and a screenshot at frame 3000 shows both cars
whole. Replayed against `run-01.inp`, byte-for-byte identical state-machine
timing to the unpatched ROM (below) -- zero cost, in other words, once the
right ten zones were chosen instead of extending to thirteen.

**The first attempt at fixing this instead tried extending the mirror to
all thirteen zones, and that is the wrong turn worth keeping.** It required
moving which zone carries the display-interrupt bit that switches character
mode on (for the HUD) and back off (for the road) -- from zones 11/15 to
14/17, to make room. Read purely from the code, this looked safe: the DLI
dispatch chain (`ENTRY_Nmi`, `dat_DliHandlerTable`) is index-driven, not
zone-number-driven -- each handler sets `ram_00FF` to whatever the *next*
handler should be before returning, and MARIA's interrupt doesn't tell the
CPU which zone raised it. So which physical zone carries a given bit
"shouldn't" matter to which handler runs, only to when.

It renders correctly in isolation (confirmed: the divider and the road both
decode in the right mode at the new positions). But replayed against
`run-01.inp`, the qualifying phase -- which should end at frame 3766, same
as the unpatched ROM -- instead ran until frame 13564: a real desync, not a
rendering bug, caught by logging the race's own state byte (`ram_009D`)
frame-by-frame rather than trusting the screenshot. Bisecting it (three
isolated test builds, changing one variable at a time against the
otherwise-untouched, proven-safe layout) placed the cause squarely on
moving those two specific DLI bits: a build that extended the mirror the
same way but left the bits at zones 11/15 (rendering wrong, HUD-mode
content where road content should be) matched the unpatched timeline almost
exactly, while the DLI-moved build didn't. Something about *which* zone
ends up carrying that interrupt measurably changes the frame's timing in a
way a recording is sensitive to, even though nothing about the bit's
*effect* should differ by the reasoning above. Not fully explained -- just
avoided, the same discipline the signature-timing bug (above) established:
when a recording disagrees with a change that looks correct, trust the
recording. `DLI_ZONES` stays exactly `{0, 7, 11, 15, 19}`, unmoved.

**The light and the banner had stopped appearing because the HUD-relocation
fix (above) overwrote the ROM tables that draw them, permanently.** Asked to
bring them back without giving up the always-on HUD, the fix needed new
code for the first time in this patch (docs/FINDINGS.md's `splitscreen.py`
docstring has the full reasoning): `dat_A6BB` and `dat_A6CD` are restored to
their original, untouched bytes, so the stock start-light and banner
routines display exactly as they always have, and a new routine
(`HudReassert`/`StartDriveHud`) reasserts the HUD in zones 12-14 once each
one finishes, sharing the divider the same way stock code already shares it
between the light and the banner ("whichever wrote last wins").

Finding *where* to hook that back-in took three live corrections in a row:

1. **The obvious hook only covered one of two places driving resumes from.**
   `rom:D848` (in `sub_D83D`, the "resume after a per-lap event" check, state
   $09 -> $03) is easy to find and works correctly there -- but instrumenting
   the new code to count its own calls into a spare, unreferenced RAM byte
   (`$1FFF`, confirmed unreferenced anywhere in the disassembly) and
   comparing that count, frame-by-frame, against exactly when zones 12-14
   changed showed it never firing at all around frame 5010, when the
   *second* start light (the real race, not qualifying) finishes. A raw
   byte-pattern search across every addressing mode 6502 supports for a
   store to `ram_009D` (not just the `STA` instances the disassembler had
   already labelled) turned up the real site: `rom:CBEB`, inside a
   completely different, periodic state check gated on `ram_00A2` vs
   `ram_00A3`, using `STY` rather than `STA` a few instructions upstream of
   it. Two genuinely different places set state $03; both needed the hook.
2. **The first version of the second hook stored the wrong value.** It
   reloaded `A` with `#$03` *before* calling the shared write routine, not
   after -- and the write routine clobbers `A` (it loads HUD bytes into it).
   So the byte that actually reached `ram_009D` was a HUD byte, not 3. Live
   symptom: the race state visibly cycled through the start-light sequence
   *again* rather than beginning to drive, easy to mistake for "the light
   fired twice" rather than "the state machine got fed the wrong number."
   Fixed by writing first and reloading `#$03` immediately before jumping
   back to rejoin the original code.
3. **Even fixed, that hook alone measurably desynced the recording.** The
   shared write routine is a loop plus a `JSR`/`RTS` round trip -- maybe 120
   cycles where the original instruction pair took 5. At `rom:D848` that
   was free; at `rom:CBEB` it was not, and the qualifying-completion frame
   drifted again, the same signature as the DLI-bit mistake above: a
   recording sensitive to a frame's exact cycle count, not to what that
   frame displays. The fix was to stop sharing code at this one call site --
   nine straight `LDA #imm`/`STA abs` pairs, inlined, no loop, no `JSR` --
   which cut the added cost enough that the recording matches the unpatched
   ROM's state-machine timing frame-for-frame again, checked by diffing the
   full transition log rather than spot-checking a few frames.

Verified end to end against both recordings in this repository: `run-01.inp`
and `run-02.inp` both land on the exact unpatched score/gear/speed at frame
8000, and `run-01.inp`'s full state-transition log (every `ram_009D` change,
all seventeen thousand-odd frames) matches the unpatched ROM's frame numbers
exactly, not approximately. Screenshots confirm the visible result: the
light and the "POLE POSITION! 4000" banner both show correctly in the
divider at their moments, and the HUD reappears there the instant each one
finishes -- not 2,200-odd frames later, which is what the version with only
the `rom:D848` hook left it doing.

## Colour, a third entry point, and a screen that bumped

Real hands-on play of the working divider (above) surfaced three more bugs,
none of them visible from a handful of scripted-recording screenshots: the
light, banner and HUD all rendered in the wrong colours; the HUD never
reasserted during qualifying at all; and the whole screen visibly bumped up
and back down around every per-lap message. All three are fixed; two of the
three took a wrong turn on the way, both caught live.

**The colours.** `DLI_ECA1` -- the interrupt that recolours zones 1+ for the
mirror -- sets a run of palette registers (`P0C1/C2`, `P1C1/C2`, the shared
`P0C3/P1C3/P4C3/P5C3` load, `BACKGRND`) that stay in effect for the rest of
the "sky" span, zones 1 through 19, until the road's own DLI at zone 20 sets
different ones. Stock never needed to reset them again in between, because
everything in that whole span -- HUD, light, banner, decorative signs -- was
designed to look right in one shared palette. This patch's mirror needs
*road* colours for zones 2-11 specifically, which the divider (12-14)
inherits too, since nothing resets it before its own scanlines render --
confirmed by comparing screenshots against the unpatched ROM at the same
frames: stock's HUD is blue-on-sky, this patch's was rendering it in the
road's tan-and-white instead, background included, not just text.

The fix needed to land inside a per-scanline interrupt handler for the first
time, which is a much tighter cycle budget than the state-machine hooks
above: `ZoneDividerRestore` (docs and full reasoning in
`patches/splitscreen.py`'s `hud_reassert_src`) replaces zone 11's own DLI
(`rom:ED47`, `JMP sub_EC67`) with a version that does the same CTRL mode
switch and then restores the original P0/P1/BACKGRND values, confirmed to
add no measurable cost (a full recording's state-transition log, diffed
frame-for-frame against the unpatched ROM, came back identical).

**The wrong turn inside the colour fix:** the first version only fixed the
banner and the HUD, not the light. A second screenshot comparison, this one
specifically at a frame where the light is on screen, showed it still
rendering against road colours even after the first fix. The reason:
`DLI_ED30` (zone 11's real handler) doesn't unconditionally switch to
character mode -- when `ram_009D` is $4-$7 (the light showing, which needs
mode 0's direct graphics), it takes a *different* path (`rom:ED42`, `STA
ram_00FF / JMP sub_EC09`) that stays in mode 0 and skips `sub_EC67`
entirely. `ZoneDividerRestore` sat on the path that path never took.
`DividerPaletteOnly` covers the second path -- same palette fix, deliberately
*without* the mode switch, since that path's whole point is staying in mode
0 for the light's own graphics.

**Qualifying never showing the HUD.** Root cause: HudReassert's two existing
hooks (rom:D848 and rom:CBEB) both work, but they cover the two ways *normal
driving* is entered -- qualifying enters its own, separate drive state ($02)
through a third path that neither hook touches, and nothing ever transitions
qualifying back out of $02 and through anywhere else before it ends. No hook
ever fired during the entire qualifying run, which is exactly the reported
symptom.

**The wrong turn inside this fix, and the more interesting one:** the first
attempt hooked `rom:D412`, a `LDA #$02 / STA ram_009D` this project's own
disassembler never showed as reached from anywhere qualifying-related, found
by grepping for the instruction shape rather than tracing execution. It
looked plausible, the bytes matched, the build succeeded -- and it never
fired. Dense per-frame sampling around the exact moment qualifying begins
(the same technique that caught the earlier register-clobber bug) showed
`ram_009D` becoming $02 right on schedule while the divider's contents never
changed at all. A raw byte-pattern search across the *whole ROM* for the
exact four-byte sequence `A9 02 85 9D` -- not just the instances the
disassembler had already labelled `STA ram_009D` -- turned up a *second*
occurrence at `rom:CBEF`, four bytes away from the already-hooked `rom:CBEB`
and falling into the very same shared `STA ram_009D` (`rom:CBF1`) that
`StartDriveHud` already rejoins at. That shared instruction can't be
overwritten (two other callers depend on it staying exactly what it is), and
`L_CBEF` itself is only two bytes -- too short for a JMP. So the real hook
sits one instruction earlier, at `rom:CBE3` (`CMP #$10 / BEQ L_CBEF`, four
bytes): `QualDriveHud` reproduces that comparison, does the state store and
the HUD write on a match, and rejoins the original code (`$CBE7`, the
`CMP #$11` check `rom:CBEB` depends on) on any other value. `rom:D412`'s
role, whatever it is, remains unpatched -- an edit that was never confirmed
to do anything live is worse than no edit, not a harmless extra.

**The screen bump.** Root cause was arithmetic, not logic: HudReassert,
StartDriveHud and QualDriveHud all write three 7-line rows (21 lines total)
into zones 12-14, but the stock light and banner templates don't match that
-- 8+8+1=17 and 7+3+7=17. Every swap between "HUD showing" and "light or
banner showing" changed how many scanlines MARIA processed before the road,
which shifted the whole screen below the divider up or down by the
difference for as long as the swap lasted. Fixed with two single-byte edits
to `dat_A6BB` and `dat_A6CD` -- not their addresses, not their visible
content, just each template's own blank filler zone's line count (3->7 and
1->5), so all three writers total 21 and the swap stops moving anything.
Confirmed by screenshot: the road and decoration sit at the same height in
frames taken during a lap message and immediately after the HUD reasserts,
where they visibly didn't before.

Verified the same way as the round before it: both recordings still land on
the exact unpatched score/gear/speed at frame 8000, and `run-01.inp`'s full
state-transition log matches the unpatched ROM frame-for-frame after every
one of the fixes above, not just the first.

## Why zone 11 specifically: the desync is directional, not budget-shaped

Follow-up to "The mirror was missing the car, and the divider was missing
the light" above, which found that moving the mode-switch DLI bit from
zone 11 to zone 14 (to make room for a full thirteen-band mirror) desyncs a
recording, without explaining why. Asked to actually find out -- partly
because the answer matters beyond this one patch, if a future independent
two-camera view needs its own equivalent of zone 11's boundary.

**It isn't about how much is drawn.** A version of the moved-DLI mirror
with zones 12-14 left completely blank -- no mirror content, next to no
DMA cost -- desyncs at the identical frame (1265) with the identical
symptom (a live controller-port tap: `InputAccel` reads $FF in the
unpatched ROM and $7F in the patched one, at the same instant the
recording's very first real accelerator press happens). The earlier
"~2,000 extra cycles" estimate for those three zones, measured properly
afterward against `dmabudget.py` using the *real* object counts and widths
from a live display-list dump rather than a guessed worst case, turned out
to be about 3.5x too high anyway (roughly 680 cycles, not 2,000) -- moot,
since even zero cost broke it identically.

**It isn't zone 15 either.** A version that moves *only* zone 11's bit (to
zone 14) and leaves zone 15's bit exactly where stock has it -- so the gap
between the two interrupts shrinks drastically, unlike the original
two-bit-move version where both shift together and the gap stays similar
to stock -- desyncs identically, same frame, same symptom. Since the gap to
the *next* interrupt varies a lot between these two variants but the
failure doesn't, the size of that particular gap isn't the mechanism.

**It's directional.** Moving zone 11's bit two zones *earlier* instead (to
zone 9, with literally nothing else changed from the shipped, safe design
-- same ten bands, same zone 1, same everything) produces no controller-port
divergence at all across a full 4,200-frame check. It isn't clean -- a
much smaller, later, different-shaped drift shows up in `PlayerX` starting
around frame 1948, almost certainly just from zones 9-11 rendering in the
wrong CTRL mode with real mirror content in them -- but the catastrophic,
immediate, input-level failure that every *later* placement produces is
simply absent.

That asymmetry points at zone 19's own DLI (`DLI_ED4F`): a long,
WSYNC-paced handler that injects fresh per-scanline curve data into all
thirteen real road bands, phase-locked to MARIA's raster for the entire
78-line road with no slack to spare (docs/FINDINGS.md, "the last piece").
Moving the mode-switch interrupt *later* -- closer to zone 19 -- is the one
change that plausibly costs that handler some of its own margin; moving it
*earlier* only gives it more. The most likely chain, not yet confirmed at
the cycle level (MAME's own write-tap API proved unreliable for tracing
this precisely -- taps stop firing a few frames after boot for reasons this
investigation didn't get to the bottom of): a late or jittered entry into
`DLI_ED4F` shifts its own internal WSYNC pacing, which delays when it
finally returns; that delay reaches the true VBLANK handler (`rom:F110`
onward -- confirmed to be where the main loop's own frame counter,
`ram_00B9`, gets incremented, and where `ram_00FF` gets re-armed to `$07`
for the next frame's race-view DLI chain), pushing it later in real time
even though every zone's *scanline* position is unchanged; and that reaches
into the next frame's read of the controller port, which is timing-
sensitive in a way ordinary digital inputs aren't (`ReadController`,
`rom:C17E`, stores the *raw* byte from `INPT1`/`INPT0`, not just a masked
bit -- consistent with these being genuinely time-charged paddle-style
inputs where a few cycles of jitter can tip a real transition to the wrong
side, exactly what a controller-value flip landing on the recording's very
first accelerator press looks like).

**The practical upshot, including for a future disconnected two-camera
view:** the failure tracks proximity to zone 19, not identity with zone 11.
A second, independent divider boundary looks safe to add as long as it
stays *earlier* in the frame than zone 11's own position, not later --
moving the existing boundary earlier still costs a little (the `PlayerX`
drift above), so it isn't free, but it is a different and much smaller
class of problem than the one moving it later produces. Fitting all
thirteen bands into the *current* mirror without moving anything past
zone 11's own position would need zone 0 and zone 1's combined margin (23
lines today) cut to about 5 -- tight, and zone 0's own requirements haven't
been audited for how far it can shrink -- but it's the direction that this
investigation's evidence says is worth trying, not the direction that was
tried and rejected.

## Correction: it's zone COUNT, not direction -- and the ceiling is exactly ten

Follow-up to "Why zone 11 specifically" above, asked to go further: could
the trigger zone shrink to one line, move even earlier, or need to stay
blank, since a future disconnected two-camera view might need to clone
whatever makes it safe. That follow-up work found the previous section's
conclusion -- "directional, proximity to zone 19" -- was the wrong
explanation for a real observation, and it's worth being precise about
which part was right.

**What holds up:** a one-line trigger zone works exactly as well as a
six-line one, and content versus blank makes no difference -- both
confirmed by moving the shipped design's zone 11 to one line (freeing five
lines elsewhere, zone 19 held fixed) with and without real mirror content
in it. Neither changes the outcome. Zone size and zone content were never
the mechanism, in either the earlier round or this one.

**What didn't hold up: "later is worse."** Extending zone 11 in place --
same zone *number*, just more lines, so still only ten zone-table entries
between zone 1 and the trigger -- stayed safe all the way out to the exact
scanline the original thirteen-band attempt used (101), and one line
short of the scanline the original *ten*-band-plus-shrunk-zone-1 attempt
used. That's a direct contradiction of "later is worse" at the same
absolute position. The actual variable, isolated by holding zone 1 fixed
and varying only how many *distinct* zones sit between it and the trigger:

    K = 10 zones (2-11):  safe, zero controller-port divergence
    K = 11 zones (2-12):  desyncs, frame 1265, identical symptom
    K = 12 zones (2-13):  desyncs, frame 1265, identical symptom
    K = 13 zones (2-14):  desyncs, frame 1265, identical symptom

Ten is safe at any tested position from zone 9 through zone 11's own
(extended) end. Eleven breaks it immediately, and stays broken the same
way regardless of how much further it's pushed. The boundary is a zone
*count*, not a scanline.

**A real, separate bug was found and ruled out along the way.** With
eleven or more mirrored zones, zone 12 becomes mirror content -- and the
stock start-light/banner routines still copy their own bytes to a
hardcoded `ram_2224` (zone 12's own slot) the moment either fires, because
nothing had retargeted them yet in these test builds. Watching zone 12
live confirmed it: real mirror data (`85 24 D4`) at frame 1250, overwritten
with HUD-triplet data at frame 1261, one frame before the controller-port
divergence starts. That looked, briefly, like the whole explanation -- a
genuine content collision, independent of the earlier DLI-position theory.
It wasn't: a version that retargets the light/banner's write destination
away from zone 12 entirely (to zone 15, the real new divider, using the
same `STA ram_2224,X` -> `STA ram_222D,X` operand patch this project's
shipped patch already uses elsewhere) desyncs identically. The collision
is real and worth avoiding on its own merits, but it isn't why the
recording breaks.

**So the mechanism is still not fully known** -- only its shape. Ten zone
selectors between zone 1 and the mode-switch trigger is safe; eleven or
more isn't, regardless of trigger position, zone size, content, or whether
the light/banner collision is separately fixed. The precision of the
boundary (exactly ten, not nine or twelve) suggests something in the ROM
assumes a fixed-size structure here rather than a soft cycle budget --
matching the "ten usable slots" already documented for this same sky
region in "Phase 1 prototyping" above -- but what specifically enforces it
hasn't been traced to an instruction. MAME's write-tap API remains
unreliable for chasing it further (stops firing a few frames after boot,
as before); anyone continuing this would likely need real breakpoints or
cycle-exact tracing this investigation didn't have reliable access to.

**Practical answer to the three questions asked:** the trigger zone can be
one line, doesn't need to be blank, and can sit anywhere from zone 9
through zone 11 safely -- but none of that lifts the real ceiling. Ten
zone-table entries between zone 1 and the trigger is the hard limit this
technique (mirroring the live road sub-lists directly) runs into, and nothing
tested moves that number. A thirteen-band mirror isn't reachable this way.
For a future independent second camera, the same limit likely applies to
whatever its own equivalent boundary is -- at most ten zone entries in
that view's own "before the divider" span, regardless of where in the
frame it sits.

## Solved: the start light was erasing display-interrupt bits

The two sections above both got this wrong, in different ways -- "proximity to
zone 19", then "at most ten zone entries". Neither survives. The actual cause
is mundane once seen, explains every result from all three rounds, and lifts
the limit entirely: a **full thirteen-band mirror works**.

**The start light and banner overwrite whole zone selectors, DLI bit
included.** `sub_D80D` and `sub_DA7C` each copy *nine* bytes -- three
complete three-byte zone selectors -- to wherever `STA ram_2224,X` points
(zones 12, 13 and 14 by default). The first byte of a selector is its flags
byte, and bit 7 of the flags byte is the display-interrupt bit. So the moment
the light first appears, any DLI bit sitting on zone 12, 13 or 14 is
**erased**. That link of the interrupt chain never fires again, the chain
stalls, and everything downstream of it -- including the next frame's
controller read -- goes wrong from that frame onward. Frame 1261 is when the
light first writes; frame 1265 is where the controller value first diverges.

A pure-position test settles it: with **every** zone blank and no content
anywhere, moving index 10's bit to zone 13 desyncs, while leaving it at 15 or
moving it to 5 or 17 stays clean. Nothing is drawn differently in any of
those -- the only thing that changes is whether the bit sits inside the
nine-byte overwrite window.

Every earlier result fits:

| build | DLI bits | light writes | verdict |
|---|---|---|---|
| shipped / `ext15` / `ext18` | 11, 15 | 12-14 | clean |
| trigger moved earlier (zone 9) | 9, 15 | 12-14 | clean |
| `K=11` / `K=12` / `K=13` | 12 / 13 / 14 | 12-14 | **wiped** |
| 13 bands, DLI at 14/17 | 14, 17 | 12-14 | **wiped** |
| same, retargeted to `$222D` | 14, 17 | 15-17 | **wiped** (17) |
| HUD above mirror, retargeted to `$2209` | 2, 5 | 3-5 | **wiped** (5) |
| same positions, all zones blank, no retarget | 2, 5 | 12-14 | clean |

The retargeted builds are the giveaway: retargeting moves the *window*, so a
bit that was safe at 17 becomes the one that gets erased. That is why "move
the divider somewhere else" kept failing no matter where it went -- the
divider and the interrupt were always moving together, so the bit stayed
inside the window by construction.

**The rule, stated usefully:** no DLI bit may sit on any of the three zones
the light/banner routines write to. Everything else this investigation
blamed -- zone count, scanline position, DMA cost, content, direction of
travel -- is irrelevant on its own.

**What it unlocks.** Park index 10 on a one-line spacer zone *outside* the
window and the mirror can have all thirteen bands:

    zone  0      16   sky                       DLI idx7
    zone  1      13   sky
    zones 2-14   78   full 13-band mirror       DLI idx8 on z7, idx9 on z14
    zones 15-17  21   HUD divider               <- light/banner retargeted here
    zone  18      1   spacer                    DLI idx10  (outside 15-17)
    zone  19     10   decor                     DLI idx11
    zones 20-32  78   player 1's road, unmoved

Verified against `run-01.inp`: zero controller-port divergence across 4,200
frames, and score/gear/speed at frame 8000 identical to the unpatched ROM
(`028900` / `$10` / 255mph). The top view is now the same 78 lines as the
road below it rather than 60 -- the two views are finally the same size.

## The mirror was free; the interrupt positions were not

The previous section ends with a full thirteen-band mirror that renders
correctly and matches stock exactly across `run-01`. It was wrong to stop
there. Replayed against `run-02` the same build scores 011040 where stock
scores 026770, ends in gear `$00` instead of `$10`, and -- as the person
testing it put it -- is "outright crashing."

The harness is why that got through. `cmp.py` graded a build by counting
frames where `InputAccel` or `InputBrake` differed from stock, on the theory
that the controller read is the timing-sensitive thing and everything else
follows from it. The full-mirror build reads the pad **perfectly**: zero input
diffs across 4,200 frames, on both recordings. What it does is fall behind on
physics. Stock accelerates `$46` -> `$4D` at frame 774 of `run-02`; the patched
build does it at 776, and does the next step two frames late as well. The
verdict said CLEAN because the thing it measured was genuinely fine. `cmp.py`
now grades on the whole state vector, and `run.sh` takes a recording name
instead of hardcoding `run-01`.

Worth recording precisely because it is easy to over-correct: **no patched
build has ever been bit-identical to stock, and that was never the bar.** The
shipped ten-band patch drifts too -- 37 frames of `PlayerX` on `run-01`, 5 on
`run-02` -- and lands on stock's exact final score. Drift in `PlayerX` that
converges is normal. A two-frame lag in `Speed` that compounds is not.

### Three things that were not the cause

Bisecting the production build against `run-02`, each suspect removed alone:

| build                                    | f8000 `run-02`      |
|------------------------------------------|---------------------|
| stock / shipped                          | 026770 `$10` 198    |
| full mirror, production                  | 011040 `$00` 158    |
| ...minus the `$A6BE`/`$A6D3` line fix    | 011040 `$00` 158    |
| ...minus the `rom:CBE3` qualifying hook  | 011040 `$00` 158    |
| layout only, every hook removed          | 026770 `$10` 198 ✅ |

So the thirteen-band layout is innocent and the hooks are implicated. Adding
them back one at a time separates them cleanly: `rom:CBE3`, `rom:ED48` and
`rom:ED42` are each harmless; `rom:D848`, `rom:CBEB` and the line fix each
break it on their own.

That pattern has an obvious reading, and the obvious reading is wrong. The
three harmful edits are exactly the three that keep the divider at its full
21 lines, and the three harmless ones never touch a line count -- so the
layout-only build "passes" only because the start light shrinks the divider
to 17 and nothing ever puts it back, quietly running the frame at 135 active
lines instead of 139. That reads as a DMA ceiling: the mirror costs too much,
139 lines is over budget, shrink the mirror.

It is not. Sweeping the band count against the full hook set, **8, 9, 10, 11
and 12 bands all fail exactly like 13** -- including ten, which is what the
shipped patch runs at 139 lines without trouble. Cost is not the variable.

### What it actually was

Dumping the zone tables side by side makes it visible in one line:

| build   | DLI zones        | zone 18            |
|---------|------------------|--------------------|
| stock   | 0, 7, 11, 15, 19 | 10 lines, `$18FA`  |
| shipped | 0, 7, 11, 15, 19 | 10 lines, `$18FA`  |
| broken  | 0, **1**, 14, **18**, 19 | **1 line, blank** |

The shipped patch never moved a display interrupt. The full-mirror layout
moved two, and did it for a reason that seemed forced: the light and banner
overwrite zones 15-17 wholesale, flags bytes included, so index 10 could not
live there -- it went out to zone 18, which meant shrinking zone 18 to a
single line and discarding its stock `$18FA` content, which meant moving
index 8 down to zone 1 to rebalance the 139 lines.

Every one of those was a real consequence of the first choice, and together
they are what starves the 6502. The interrupt handlers are not free: each ends
in `sub_EC67` or `sub_EC78`, both of which burn a `WSYNC`, and `DLI_ED4F` at
zone 19 spends **six** `WSYNC`s on palette setup before it even reaches the
road-curve injection at rom:ED9D. Where those handlers fire, and how much
scanline is left between one and the next, is the budget that matters -- not
how many bands the mirror draws.

### The fix: let the templates carry the bit

The premise was wrong. The light's nine-byte write is not destructive, it is
just a *copy* -- so put the display-interrupt bit in the thing being copied.
Setting bit 7 on the third selector of both templates makes the light and
banner **preserve** index 10 rather than erase it:

    dat_A6BB  06 1D 09  06 24 F6  86 1D 15     7+7+7 = 21, DLI on slot 3
    dat_A6CD  07 1C AB  07 1C BD  84 24 F6     8+8+5 = 21, DLI on slot 3

`HUD_ROWS` in the patch carries the same `$86`, because all three writers of
those zones have to agree: whichever runs last is the one that decides whether
the interrupt survives. With that in place index 10 stays on zone 17, the end
of the divider group -- the same shape stock uses -- and zone 18 keeps its ten
lines of `$18FA` untouched. Index 8 goes back to zone 7. The final layout:

    zone  0       16   blank                        DLI index 7
    zone  1        4   blank
    zones 2-14    78   all thirteen mirror bands    DLI index 8 (z7), 9 (z14)
    zones 15-17   21   HUD divider                  DLI index 10 (z17)
    zone  18      10   $18FA, stock
    zone  19      10   decoration                   DLI index 11
    zones 20-32   78   player 1's road, unmoved

139 lines in every divider state, DLIs at 0, 7, 14, 17, 19. Verified at frame
8000 against both recordings: `run-01` 028900 `$10` 255 and `run-02` 026770
`$10` 198, both matching stock exactly, with residual drift of 37 and 24
frames of `PlayerX` -- the same class as the shipped patch's own.

The general rule, which cost three wrong theories to reach: **a DLI bit inside
the overwrite window is fine as long as every routine that writes that window
carries it.** Moving the interrupt out is the expensive answer, and the cost
does not show up where you would look for it.

## What a second view cannot have: the smoothing is beam-synchronised

The mirror stair-steps where the real road is smooth. The obvious question is
whether the smoothing can simply be run twice. It cannot, and the reason is
worth having on the record with a number attached.

`DLI_InjectRowCurveX` (rom:EDA0) is not a per-frame setup routine. It is
beam-synchronised: one `WSYNC` per road scanline, rewriting each band's x and
y bytes *mid-zone* -- MARIA re-reads a zone's display list on every scanline,
so changing `$2303` between lines is what bends the band. Thirteen bands at
six lines each means ~78 `WSYNC`s, and for all of them the 6502 is stopped.
A second copy for the mirror costs another ~78 scanlines of main loop.

Measuring the headroom directly settles it. Index 8's handler was replaced
with one that burns N scanlines and then does index 9's job, so the chain
still lands on index 10, with no DLI anywhere in the mirror (a MARIA display
interrupt is an NMI and would re-enter the handler):

| extra scanlines | f8000 `run-02`   |
|-----------------|------------------|
| 1               | 026770 ✅        |
| 2               | 026770 ✅        |
| 4               | 026770 ✅        |
| 6               | 000390 ❌        |
| 20              | 010800 ❌        |
| 77              | 005080 ❌        |

**The budget is four to five scanlines.** The feature needs seventy-eight.
It is not a matter of writing it more tightly -- `WSYNC` is the mechanism, not
the implementation. Freeing that much CPU would mean cutting elsewhere, which
is what the smaller Atari signs and a lower enemy-car count were proposed for.

## The mirror's colours: everything on the road, not the road itself

Cars, signs and the lap line came out wrong in the mirror while the road
surface looked right. That split is the whole diagnosis. `DLI_ECA1` sets the
palettes for everything above the divider, and an earlier round had matched
P0 and P1 -- the road surface -- by hand, with six byte-edits inside its
palette block. Everything *drawn on* the road uses P2-P7, which nothing had
touched:

| palette | `DLI_ECA1` (top) | `DLI_ED4F` (bottom) | what it carries |
|---------|------------------|---------------------|-----------------|
| P0C2    | `$3C`            | `ram_00FC`          | stripe animation, lap line |
| P2      | `$00 $00 $00`    | `$89 $8B $8D`       | road furniture |
| P3      | `$0D $0B $09`    | `$1E $17 $00`       | signs |
| P4      | `$C8 $CC $80`    | `$0E $98 $00`       | |
| P5      | `$C4 $C8 $80`    | `$9C $96 $00`       | |
| P6      | `ram_00F4-$F6`   | `$2F $26 $00`       | **cars** |
| P7      | `ram_00F7-$F9`   | `$0F $0F $0F`       | cars |

P0C2 is why the stripes and the lap line held still in the mirror while they
animated below: a flat byte where the road reads a per-frame one. P6 is why
the car was blue on top and gold below.

Six scattered byte-edits could never have fixed this, and not only because
they missed P2-P7: `L_ECF8` (rom:ECF8) writes P3 on its way out of the very
same handler, so anything set earlier in the block is overwritten. The fix
hooks `DLI_ECA1`'s closing `JMP sub_EC09` at rom:ED29 instead and restates
`DLI_ED4F`'s whole palette block, so both views draw from identical registers
rather than from two hand-matched approximations. `BACKGRND` comes from
`ram_00FB`, the road's own ground colour, rather than the hardcoded `$1B` it
used to use -- that value is per-track, so a constant was only right on some.
`PaletteRestore` grew the matching restores, or the HUD and the start light
would have inherited the road's palette.

### The interrupt fires before the zone finishes

With the palettes matched, the mirror's bottom four scanlines rendered solid
`$38` tan with the grass behind them `$89` blue -- the road's *shape* intact,
every colour wrong. MARIA raises a zone's display interrupt about four
scanlines before that zone has finished displaying, and palette writes land
the instant they are made, so index 9's handler repainted the last mirror band
while it was still on screen.

Delaying the handler works, exactly linearly -- one `STA WSYNC` at the head of
`PaletteRestore` recovers one scanline:

| `WSYNC`s | tan rows remaining | f8000 `run-02` |
|----------|--------------------|----------------|
| 1        | 3                  | 026770 ✅      |
| 2        | 2                  | 000000 ❌      |
| 3        | 1                  | 000000 ❌      |
| 4        | 0                  | 000000 ❌      |

Clearing it needs four; the budget from the table above allows one. So the
interrupt got a blank zone to land on instead, where the early write repaints
nothing: the divider simply reads as a few lines taller.

That costs a band. Zones 1-14 hold exactly fourteen selectors, thirteen bands
leave no room for a blank, and **zone 1 cannot be the one given up** -- moving
the bands up to zones 1-13 to free zone 14 hangs the machine outright at frame
6500 of `run-01`, everything frozen and the screen flashing as the interrupt
chain stops being serviced. Confirmed both ways: with index 9 on zone 14 and
on zone 13, a road band in zone 1 hangs it either way, and the same build with
the bands back at zones 2-14 runs clean to 12,200 frames. So the blank goes
after the bands and the farthest band pays for it. The mirror is twelve bands,
72 lines, against the road's 78.

One more trap in that neighbourhood, found the hard way: with zone 1 at six
lines and the blank at four, `run-01` diverges for 2,725 straight frames from
f9475. At zone 1 = four and the blank = six -- the same 139 total -- it tracks
stock to 13,000 frames on both recordings. Zone 1's length is load-bearing and
nothing about the line budget says so.

A method note, since it nearly shipped a broken build: the first read of that
2,725-frame divergence called it benign, because the scan printed the first
twelve divergent stretches and they were all one frame long. The sustained one
was the sixty-fifth. Sort by length, not by position.

## Paying for the mirror with slots it never used

The earlier section concluded that smoothing the mirror was impossible: the
injection is beam-synchronised, a second copy costs ~78 scanlines, and the
budget is four to five. That conclusion was right about the injection and
wrong about the budget, because the budget is not fixed. It is mostly being
spent on nothing.

A road band's display list is nine four-byte object slots. At any moment one
or two hold a car or a sign; the rest are `00 1F 00 A1` -- width set, address
`$0000`. MARIA fetches all nine regardless. The mirror, pointing at the road's
own band lists, pays for eight objects that draw nothing.

Re-running the burn sweep with the mirror pointed at a six-byte list holding
only the road surface:

| mirror configuration      | burn scanlines tolerated |
|---------------------------|--------------------------|
| the road's own band lists | 4-5                      |
| road surface only         | 28+                      |
| blank, nothing drawn      | 28-40                    |

A road-only mirror costs almost exactly what a blank one does. **Roughly 24
scanlines of headroom are recoverable** -- enough to hand each mirror zone its
own width and x once per frame, with no `WSYNC` anywhere, because a zone that
is only two scanlines tall does not need its list rewritten mid-zone.

### What makes it possible

* `$2500-$27FF` is 768 bytes with no reference anywhere in the disassembly --
  checked for indexed bases as well as literal addresses, and clear of the
  last band list, which ends at `$24FA`. Note the scan reports `$24DC-$27FF`
  as unreferenced, which is wrong below `$2500`: those bytes belong to band 12
  and are only ever written through an index.
* The race zone list is placed by two bytes: `sub_F171`'s copy target and the
  DPPH immediate at rom:D8D6. The results screen keeps its own list at
  `$226B` and its own pointer at rom:D89B, so only the race view moves.
  **Verified: relocated to `$2500`, both recordings match stock exactly.**
* Slot +00's *address* never changes -- the injection rewrites only its width
  and x. Confirmed identical across frames 2600, 2601, 2640, 3000 and 4000. So
  every address in the mirror's lists can be baked in at boot.
* MARIA steps a zone's graphics one page per scanline, counting down from
  height-1, and the road graphics encode the taper *within* a band that way.
  A two-line zone standing in for band rows j and j+1 needs its base page
  shifted by `4 - j`, which is also static and also bakeable.

### Where the prototype got to

Working: the relocated 59-zone list, the boot-time copy of both images, and
thirty-six two-line mirror zones fed once per frame from the vertical-blank
handler. The mirror's road edge is genuinely smooth and tracks the road's own
profile closely over the far two thirds -- widths of 34, 52, 68, 80, 104, 116,
132, 152, 162, 180, 204 against the road's 12, 28, 44, 58, 76, 92, 112, 124,
144, 154, 170.

Not working: a seam at the eighth band. The five nearest bands draw the road
with **two** objects, slot +00 and slot +04, because by then it is wider than
one object can cover. Slot +04's address is static and its width and x change
per frame but not per scanline, so it is cheap to replicate -- but with it
added the near zones still render only their right half.

Three traps worth keeping, all of which cost a build:

* **The main loop has no point where both curve arrays are settled.**
  `StageRowCurveForDLI` (rom:EA2C) fills only x, `$1B00-$1B4D`; the width array
  at `$1B4E` is filled separately by sub_E8AC at rom:D8CC. Hooking either one
  read a half-built frame. Probing what the routine actually saw returned
  widths of `34 30 30 30 00 00` where the live values were `18 38 38 14 34 34`,
  and **a width byte of `$00` is MARIA's end-of-list marker**, so most zones
  terminated immediately and the mirror drew nothing at all. Vertical blank
  (rom:F16B) is the answer: by then the road below has been drawn from those
  arrays, so the mirror shows exactly what player 1's road used.
* **Two separate 8-bit index overflows.** Thirty-six ten-byte lists is 360
  bytes; neither the per-frame update nor the boot copy can walk that with one
  8-bit register. The update is unrolled (faster anyway, ~576 cycles with no
  loop overhead); the copy is split in half.
* **The code blob outgrew its templates.** Unrolling pushed it from 322 to 949
  bytes, straight over a template parked at `$FC00`. `expect=` caught it.

A sentinel is what untangled the first of those: writing `$AA`/`$BB` instead
of the array values proved the writes were landing in exactly the right
places, which moved the search from the loop to its inputs.

## Boot-time work desyncs the recordings, and it cost hours

This one belongs at the front of anyone's mind before the rest of this
section, because it invalidated several hours of apparently careful bisecting.

Building a finer-grained mirror meant adding a boot-time copy: a new zone list
into RAM, and a set of short display lists beside it. Every build carrying it
failed the recordings with the *same* numbers -- `026770` becomes `000670` on
`run-02`, every time, regardless of what else changed. That consistency was
read, wrongly, as evidence of a single structural bug, and the hunt went
through the zone list, the display lists, the display-list addresses, RAM
versus ROM, granularity, and interrupt positions, ruling each out.

The control that settled it: **mirror pointed at the road's own display lists,
no per-frame hook, the only change a 120-iteration copy loop at boot writing
to RAM the mirror never reads.** Identical failure. It cannot be corruption --
nothing reads those bytes -- and it cannot be per-frame cost, because the loop
runs once, from a one-time init path (rom:D241). It is boot timing: the extra
work shifts startup past a frame boundary, every subsequent input in the
recording lands at a different moment, and the race diverges from the top.

This is the same effect already documented here for cartridge signing, which
is why `--build` is unsigned. It generalises: **a recording cannot validate
any build that changes how much work happens before the race starts.** When
bisecting, hold the boot cost constant across every variant, or the comparison
is meaningless. Two things follow from that:

* Identical failure values across structurally different builds are a *signal*,
  not a coincidence -- they mean the variable you are changing is not the one
  that matters.
* A build that fails a recording has not necessarily failed. It may simply be
  unmeasurable this way, and needs a different check.

## The per-frame budget, measured properly

With boot cost held constant and the mirror on the road's own display lists,
sweeping how many mirror zones get their width and x rewritten each frame from
the hook at rom:F16B:

| zones updated | approx cycles | result |
|---------------|---------------|--------|
| 1, 2, 3, 4, 6, 9 | 16 - 144   | pass   |
| 12               | ~234       | fail   |

**Roughly 150-230 cycles per frame.** A thirty-six zone, two-line mirror needs
about 786. Two other homes were tried and did worse: rom:F15D, ahead of the
handler's own vblank wait -- the reasoning that time before a wait is free
turns out not to hold -- and the divider's own display interrupt, mid-screen,
where the burn sweep had suggested there was room.

That last one is worth stating plainly, because it contradicts the earlier
section: the ~24 scanlines of headroom the burn sweep found are **not**
spendable on per-frame work at frame end. They were measured by stalling a
mid-screen interrupt while MARIA was already starving the 6502. Time taken
once the display is done comes out of the main loop's actual compute window,
and that window is far tighter.

### Where the prototype reached

It works, visually. Thirty-six two-line zones, each with its own six- or
ten-byte display list, fed from the same arrays the road's own injection
reads. The mirror's road edge is smooth and its width profile tracks the road
one band ahead: 34, 52, 68, 80, 104, 116, 132, 152, 162, 180, 204, 220, 226,
242, 268, 282, 290, 296 against the road's 12 through 292. The seam that first
appeared at the eighth band is gone.

Getting there turned up two facts about the road worth keeping:

* **The near bands are injected completely differently.** For the eight far
  bands, the injection writes slot +00's width and x from `$1B4E`/`$1B00`
  indexed by scanline. From band 8 down -- road scanline 48, rom:EE73 -- it
  writes *four* bytes per scanline, both road objects' width and x, from
  `$007E`, `$0060`, `$1B7E` and `$1B30`, indexed by `scanline - 48`. The road
  needs two objects there because it is wider than one can cover.
* **Every address in those lists is static.** Slot +00's and slot +04's
  graphics addresses never change across frames; only width and x do. So a
  mirror's lists can bake their addresses in at boot and do no address work at
  all -- including the page shift MARIA needs, since it counts the graphics
  page down from the zone height and a shorter zone must start higher.

What is not solved is paying for it. The rendering is right; the update is
about four times the per-frame budget. Freeing that much would mean cutting
elsewhere -- which is what the smaller Atari signs and a lower enemy-car count
were proposed for, and remains the honest next step rather than a cleverer
loop. The prototype and every build behind it are kept outside the tree so
none of this has to be rediscovered.

## Making both views identical, by making the road worse

The mirror could never match player 1's road while the road had something the
mirror could not afford. `DLI_InjectRowCurveX` is that something: beam
synchronised, one `WSYNC` per road scanline, roughly **78 scanlines of stalled
6502 every frame**, and the single largest consumer in the frame. It is why
the road is smooth and the mirror steps.

Giving it up makes the two views the same and hands the time back.

`JMP` at rom:ED9D, the head of the injection, straight to that handler's own
tail at rom:F143. The palette block above it is untouched; the whole
per-scanline pass is skipped. Each band then carries one width and x for the
frame, written by the same routine that feeds the mirror -- the far bands from
`$1B4E`/`$1B00` at the band's middle scanline, the near five from the four
arrays the injection switched to at rom:EE73, plus their second road object.
Thirteen bands cost about 290 cycles a frame against the 78 scanlines saved.

Two jobs were relying on the injection's length and had to be put back:

* **BACKGRND.** The injection set it mid-road from `ram_00FA`/`ram_00FB`
  (rom:EDAF, rom:EDC5). Without it the road drew on whatever the divider's
  palette restore had left. `RoadTail` sets it from `ram_00FB` before jumping
  to the tail.
* **The black-out at rom:F158.** `STA BACKGRND` with A=0, meant for the bottom
  margin *after* the road. With 78 scanlines no longer in front of it, it
  landed mid-road and blacked the whole view out. NOPped; the margin now
  shares the ground colour.

### Both views from one plan

With neither view getting per-scanline treatment, player 1's road can be built
from exactly the same description as the mirror: same zone heights, same
display lists, same dropped farthest band. 26 zones and 72 lines each.
Measured on two frames, **0 of 11,520 sampled pixels differ between the two
views.**

The bottom giving up its farthest band frees six lines, which went to the
blank carrier zone between the mirror and the divider -- breathing room above
the HUD, at no cost.

What this bought, measured by the same burn probe used before: the frame
tolerated **under 2 stalled scanlines** at the frame-end hook before, and
**10 to 30** after. That is the budget the next stage needs.

A trap worth recording: the zone list is two views now, 62 zones, and the
boot-time copy still had the old one-view length baked in. The list simply
stopped at zone 48 and the bottom view rendered half a road. Derive the count.

### Per-view skyboxes: free on lines, not yet on palette

Putting the horizon (`$18FA`) and the decor strip (`$1D3B`) above the top view
costs exactly the twenty lines zone 0 and the blank gap already spend, so the
line budget does not object. It still does not render: zone 0's own display
interrupt is what installs the road palettes, and it fires at the *end* of
that zone, so the strip draws in whatever the previous frame left behind. The
fix is to move that palette work earlier -- the vblank handler is the obvious
home -- and is not done.

## Correction: the "wraparound fix" below is wrong, and so were two detectors

Live testing killed it. The hide both **eats visible road on ordinary frames**
and **does not fix the wraparound**. The build is reverted; what follows is
kept because the reasoning failure is the useful part.

Two detectors said it worked, and both were measuring the wrong shape:

* The first only flagged rows where road touched `x=0`. The artifact is a
  *detached* chunk that can start a few pixels in, so it scored 0 of 8 while
  the artifact was plainly on screen.
* The replacement looked for two road runs with grass between on one row. That
  misses it too: at the near rows the true road is off screen entirely, so the
  wrapped fragment is the ONLY road run on that line.

A third approach -- comparing the coarse build against an injection-kept build
frame for frame -- was invalid, because the two builds desync and the
"mismatch" was mostly different game state rather than different rendering.

What a live screenshot actually shows: the car far off the road with no road
beneath it, the true road as a chunk in the FAR rows, and a fragment at the
far RIGHT edge on NEAR rows where the road has gone off screen to the left.

That reading changes the diagnosis. For x in 160..255 the game is using
**negative positioning** -- the object is meant to wrap in from the left edge,
and MARIA's 255/0 wrap is the mechanism it relies on, not a bug. Hiding
everything at x >= 160 therefore deletes road that is supposed to be drawn,
which is exactly the road-eating. And the stray fragment is not a clamp
failure at all: it is one x per band being correct for one scanline out of six.

If that is right, only finer x granularity on the near bands fixes it -- which
costs the objects again, because finer zones need their own display lists.
Unverified either way: no frame in run-01 or run-02 reproduces the situation
(searched for speed 140-152 with |PlayerX| >= 55; no matches), so there is
nothing to test a fix against yet.

## Superseded: hiding a road half has to shrink it, not just move it

With the injection gone and both views coarse, sharp-curve off-road frames
showed the road reappearing at the opposite screen edge. It was tempting to
read that as a new bug. It was not: probed over eight frames chosen for
|curve| >= 6, |PlayerX| >= 40 and speed > 60, **pp2-full13's mirror already
wrapped 4 of 8** while its own road view wrapped 0 of 8. The per-scanline
injection had been suppressing it in the bottom half all along; making the
views identical made the existing mirror bug symmetrical.

The mechanism, once the 7800 software guide settled that MARIA wraps at the
255/0 boundary rather than at the line width:

HPOS is eight bits and the line is 160 wide, so the game hides a road half
that has curved off screen by parking it above 160. That is safe only while
`x + width` stays under 256. The near bands' road objects are wide -- up to 25
bytes -- so a half parked at, say, 206 runs past 255 and comes back round at
the left edge. Per-scanline injection never held a value there long enough to
show. One sample per band does.

**The fix has to shrink the object as well as move it.** When x is at or above
160 the object is meant to be invisible, so its width goes to the minimum (low
five bits set, palette bits kept) and x to 161 -- the value the game itself
uses for unused slots. It then ends at 165, clear of the boundary.

A wrong turn worth keeping: moving x alone, without touching width, changed
nothing at all -- still 4 of 8. The object was still wide enough to reach past
255 from its new home. Checkpoint 10 keeps that version so the idea is not
retried.

Reading the result also needed care. The hide drops about 15% of the road
pixels on ordinary frames, which looks like it is eating legitimate road until
you read a row: without the hide, row +68 is `road:0-109  kerb:110-123
road:124-275  kerb:276-295  grass`. That first stretch is road *outside* the
left kerb -- the wrapped copy. The hide replaces it with grass. The pixels it
removes are the artifact.

With it in place: wrap 0 of 8, the two views still identical, and the build
matches stock at run-01 f8000 and f11000 and at run-02 f1500, f2600, f8000 and
f11000 -- so the whole coarse rewrite, injection bypass included, now comes
back recording-clean rather than merely healthy.

## Disconnecting the viewports

Until now the two views could not diverge however the zones were arranged,
because both pointed at the same thirteen road display lists. They were a
mirror by construction, not by choice.

Player 2 now draws from its own lists at `$2600` -- twelve bands, ten bytes
each, the two road objects and an end marker -- fed by its own geometry. The
addresses in them never change, only width and x, so they are baked in at boot
and cost nothing per frame. `P2_X_OFFSET` adds a constant to player 2's road
x, which is how the split is demonstrated before there is a second camera:

* offset 0 reproduces player 1's road exactly. Road edges at rows +20, +40 and
  +60 read (124,243), (54,257), (0,281) in **both** views.
* offset `$18` shifts player 2's road 48 pixels while player 1's is untouched,
  from the same frame.

Cost: 120 bytes of RAM and about 384 cycles a frame.

### Why player 2's viewport carries no traffic

Copying player 1's lists wholesale would bring the objects along, and it is not
affordable: they are 468 bytes, and rewriting them every frame is ~3,700
cycles, roughly 33 scanlines -- more than the entire budget the injection
bypass freed.

It would also be wrong. Player 2's traffic has to be computed for player 2's
camera. A copy of player 1's sits at player 1's positions, which is only
correct while the two views agree -- precisely the property being removed.
Objects for the second view wait on the engine producing a second set of
positions, which is engine work rather than a rendering problem.

### On the recordings

This build desyncs them (`run-01` f8000 gives 021710 against stock's 028900).
That is the boot-timing artifact recorded earlier in this document, not
breakage: player 2's lists need a copy loop at startup, and any change to
startup work moves every later input relative to the game. Liveness is
unaffected -- every state field still moves and the clock still shows its
usual 101 distinct values. The same caveat applies to anything added from here
until the second camera exists, since each addition changes boot work again.

## Player 2's camera is derived, not recomputed

Two cameras looked like it needed the engine's geometry run twice. It does not
fit. The pipeline is `sub_E9DA` seeding an accumulator from `PlayerX`, then a
78-iteration loop building `RowCurveXStagedSrc` -- two passes of ~78
iterations, about **38 scanlines**, against roughly **10** of headroom. Adding
cartridge RAM does not help: the constraint here is cycles, not memory.

It does not need recomputing. A lateral move changes exactly one thing in that
pipeline -- the seed -- and the seed enters as a constant step accumulated once
per row. That step is `dat_EA41` indexed by the offset, and the table is a
straight ramp of about 3.55 per unit whose high byte stays zero to index 72. So
the shift at row i is `i * step / 256`, and a band sampling row `6b+3` needs
one 16-bit add:

    step  = dat_EA41[|offset|]
    step3 = step * 3            the first band samples row 9
    step6 = step * 6            each band is six rows further on
    acc   = step3 ; per band: acc += step6 ; shift = acc >> 8

Negative offsets negate `step3`/`step6` once, so the per-band path is a plain
add either way. **About 360 cycles for the whole camera**, against ~38
scanlines to recompute it.

Verified by driving the offset at `$2702`: at 0 player 2 reproduces player 1's
road exactly; at +16 the road shifts 8 pixels at the far band, ~20 mid and
~20-30 near; at -16 it mirrors. The growth with proximity is the point -- a
flat slide would be the wrong shape.

### What full two-player still needs

* **An independent track position.** The lateral camera still shares player 1's
  point on the track. A second Z needs curve data for a different position,
  and that is the part that genuinely cannot be derived from player 1's arrays.
* **Controller 2**, which `$2702` stands in for at the moment.
* **Player 2's car and traffic.** Its viewport is road-only, and objects need
  positions computed for its own camera.
* **Player 2's HUD**, currently player 1's.

## A 39-byte table buys the second track position

The lateral half of a second camera turned out to be derivable. The other
half -- an independent position along the track -- is the part that genuinely
cannot be, because it depends on the curvature of the track ahead of a
different point.

That work is `AccumulateRowCurveOffset` (rom:E981-E9D9). It walks 78 rows from
nearest to farthest, advancing through track segments as the accumulated
distance passes each row's perspective depth (`dat_EB56` low, `dat_EAB9` high),
and double-integrates `SegCurve` into `$0044-$0047`. A second pass is about
2,340 cycles -- roughly 20 scanlines against the ~10 available.

Player 2's view samples only **13** of those rows, one per band at row `6b+3`,
so the walk can be done in 13 steps rather than 78. The stock tables give the
depth and the curvature scale at exactly those rows:

| band | row | Z (hi:lo) | curvature scale |
|------|-----|-----------|-----------------|
| 0    | 3   | 04:6A     | x8 |
| 3    | 21  | 02:1D     | x4 |
| 6    | 39  | 00:E0     | x2 |
| 12   | 75  | 00:02     | x1 |

    BandZLo   6A 7F BC 1D A0 37 E0 9B 66 3D 20 0C 02
    BandZHi   04 03 02 02 01 01 00 00 00 00 00 00 00
    BandShift 03 03 03 02 02 01 01 01 01 01 01 00 00

The scale is the stock ASL chain made explicit: X >= $40 is x1, $20-$3F x2,
$10-$1F x4, below $10 x8.

**39 bytes of ROM, and 13 iterations instead of 78 -- about 390 cycles, some 3
scanlines against 20.** That is the difference between fitting in the frame and
not, and it is the place a table earns its keep: not a multiply lookup, but
skipping 65 iterations of a walk whose intermediate results nothing reads.

### The part to get right

The accumulate is a *double* integration: `$0044/45` accumulates curvature into
a velocity, `$0046/47` accumulates that into a position. A coarse step cannot
simply scale the per-row increment by six:

    per row  (78 steps):   v += c        p += v
    per band (13 steps):   v += 6c       p += 6v + 21c

The `21c` is sum(1..6) -- the position also gains the partial velocities from
the five intermediate rows. Checked against the exact loop for c = 1, 5 and -3;
both terms match. Dropping the second one makes the road bend too little on
curves, which looks plausible and is wrong, so it is worth stating before
someone simplifies it away. Neither term needs a multiply: 6c is 4c+2c and 21c
is 16c+4c+c.

One more difference from the stock loop: the segment advance becomes a loop
rather than a single test, because six rows of distance can cross more than one
track segment.

## Measured: interpolation is accurate enough, and both views can share the walk

The section below says player 1 cannot share the coarse walk, because object
placement reads `RowCurveOffset` at arbitrary depths. That stands as a fact
about the code -- but the conclusion drawn from it was too cautious. The
question is not whether thirteen samples can be indexed at row 37; it is how
wrong reconstructing row 37 from them actually is. That is measurable.

Dumping the live 78-byte array across six frames, including sharp curves and
far-off-centre ones, and comparing each row against linear interpolation
between the samples:

| samples | ROM | mean error | worst | worst in near rows 60-77 |
|---------|-----|------------|-------|--------------------------|
| 13 band rows           | 39 B | 0.51 | 9 | 4 |
| + row 0                | 42 B | 0.38 | 4 | 4 |
| **+ rows 0 and 77**    | 45 B | **0.34** | **2** | **1** |
| + more near rows       | 51 B | 0.34 | 2 | 1 |

Both **edges** are what matter, not more samples in the middle: the 13-row
worst case of 9 was at row 0, where interpolation had nothing to its outside
and was clamping. Adding the two ends takes the worst case to 2 units, and 1
unit through the near rows where collisions are decided -- on a road some 150
units wide at the nearest band. Adding further samples buys nothing.

So a fifteen-sample walk serves object placement too, and **both views can use
it**, which is the requirement that matters: the two viewports have to behave
the same, and they cannot if one is walking 78 rows and the other 15.

    SampleRow   00 03 09 0F 15 1B 21 27 2D 33 39 3F 45 4B 4D
    SampleZLo   14 6A 7F BC 1D A0 37 E0 9B 66 3D 20 0C 02 00
    SampleZHi   05 04 03 02 02 01 01 00 00 00 00 00 00 00 00
    SampleShift 03 03 03 03 02 02 01 01 01 01 01 01 00 00 00

60 bytes of ROM. Fifteen iterations rather than 78 is ~450 cycles against
~2,340 -- about 3 scanlines against 20. **Both** views then cost ~7 scanlines
where player 1 alone costs 20 today: a net saving of ~12 scanlines *and* a
second camera.

A level-of-detail scheme -- coarse placement far out, exact when an object
comes close enough to collide -- was the plan before this was measured, and it
is not needed. The near rows are the accurate ones already. Worth recording as
a case where measuring first removed the complicated half of the design.

## Why player 1 cannot share the coarse walk -- as originally reasoned

The obvious follow-on to the 13-step table is to give player 1 the same
treatment and bank the saving twice: player 1's view is coarse too, one x per
band, so the 78-row walk is computing 65 values its own road never reads.

It does not hold, and the reason is worth recording before someone tries it.
`RowCurveOffset` (`$1A31`) has two consumers outside the curve pipeline:

* **rom:D1FD** reads it at a single fixed row (`LDY #$48`) and the result
  becomes `PlayerX`. One row, and a coarse walk could carry it.
* **rom:E502** reads it at `LDY ram_0048` -- a *variable* index -- inside the
  object placement maths, right after `ObjLateral,Y` and before a compare that
  decides whether the object is on screen. That is where a car or a sign gets
  its lateral position, and the index is the object's distance.

So the array is not private to the road renderer. It is the road's shape at
arbitrary depth, and object placement samples it wherever an object happens to
be. Thirteen band samples cannot answer that question; the walk is a sequential
double integration, so there is no way to get row 37 without having walked
rows 0-37.

**Player 2 can still use the coarse walk, because its viewport has no objects.**
That is what makes the second camera affordable: ~3 scanlines rather than ~20,
paid on top of player 1's existing full walk rather than instead of it.

Two ways the saving could still be had, neither taken:

* Interpolate `RowCurveOffset` between band samples for object placement. The
  double integral is smooth so the error would be small -- but it would be an
  error in where cars are drawn and where they are hit, which is a poor place
  to approximate.
* Walk fully only as far as the furthest live object, coarsely beyond. The
  saving then depends on traffic, which is exactly when the frame is busiest.

And a consequence worth noting for later: when player 2 does get objects, it
needs a full-resolution offset array of its own, and this saving disappears
with it.

## Player 2's track walk: built, correct, and over budget

The 13-sample walk is implemented -- tables lifted from the stock ROM at the
rows player 2's bands sample, segment advance as a loop since six rows of
distance can cross more than one segment, and the integration done as six real
single-row steps rather than a closed form so there is no approximation to
justify. It follows player 1's track position, so the two views must agree,
which is the check the walk exists to pass.

It does not fit. Shortening the walk separates cost from correctness cleanly:

| samples | result |
|---------|--------|
| 1, 3    | runs normally |
| 6, 9, 13| does not run |

Each sample is roughly 250-270 cycles, mostly the six integrations at ~30
each, so thirteen is about 3,400 cycles -- some 30 scanlines against the ~10
available.

### An estimate that was wrong for several turns

The engine's own per-row body is about **85** cycles, not the 30 assumed
earlier: a segment compare, a curvature fetch with sign extension and a
variable shift, four 16-bit adds, a seed add, two table lookups and two
stores. Its 78-row walk is therefore nearer **6,600 cycles (~58 scanlines)**
than the 2,340 quoted before.

That makes converting player 1 a much bigger prize than advertised -- and
changes the order of work. It is not a follow-up optimisation; it is the thing
that has to happen first, because it is what pays for player 2:

    player 1 today             ~6,600 cycles    78 rows, full array
    player 1 on a 13-walk      ~3,400           plus an interpolation fill
    player 2 on a 13-walk      ~3,400
    ----------------------------------------------------------------
    both                       ~6,800 + fill    against 6,600 today

Roughly break-even before the fill, which is too tight. So the closed-form step
is worth having after all: `v += 6c` and `p += 6v + 21c` replaces ~180 cycles
of integration per sample with about 100, taking each walk to ~2,200 and both
to ~4,400 -- comfortably under what player 1 costs alone today, with room for
the fill. It is exact for constant curvature across the step, which is the
normal case; the literal six steps only matter when a segment boundary falls
inside a step.

## Which budget? The vblank deadline is not the frame budget

Player 2's 13-sample walk would not run: six samples was already too many. The
engine's own walk was then stripped of ~1,900 cycles of work that is dead in
this build, and it made **no difference at all** -- three samples still ran,
six still did not.

The reason is that the walk was being called from `MirrorStage`, which runs in
the vertical-blank handler. Vblank has a hard deadline of its own, and the
cycles freed were main-loop cycles. Moving the call to rom:D8CF -- in
`sub_D8AC`, after `sub_E93D` has run player 1's walk and well before the vblank
wait -- ran all thirteen samples immediately.

Worth stating plainly because it invalidates the way cost has been discussed
for several turns here: "about 10 scanlines of headroom" was never one number.
There is main-loop time and there is interrupt time, and work has to be costed
against the one it will actually spend.

### The engine's walk tail is dead weight here

rom:E9BE-E9D8 computes two things this build never reads. `RowCurveOffsetAlt`
has **zero** readers anywhere in the ROM. `RowCurveXStagedSrc` feeds only
`StageRowCurveForDLI`'s copy into `RowCurveXStaged`, which nothing reads now
that the injection is bypassed.

Stripped to `DEX / BPL / RTS`. The thirteen values that *are* read are
recomputed in `MirrorStage` as `RowCurveOffset[row]` plus a per-band constant
-- `dat_EBA4[dat_BB7E[row]]`, fixed per row, so it need not be looked up at
runtime. About 1,900 cycles a frame with no loss of accuracy, and it is the
same sum the engine was computing at rom:E9D0 anyway.

### Open: player 2's track state is not being copied

`P2Main` is verified in the built ROM -- rom:D8CF jumps to it, and its bytes
are the three copies followed by the call and the tail jump. `P2Geom`
demonstrably runs, because `P2_BANDX` comes back holding exactly the per-band
base values, which is what it writes when the position accumulator is zero.
But the segment byte reads 00 at end of frame while player 1's reads 09, so the
walk is integrating zero curvature from segment zero -- which is precisely the
output observed.

RAM aliasing is ruled out: writing distinct bytes to `$2500`, `$2600`, `$2700`,
`$2730`, `$2750`, `$2760`, `$27F0`, `$2000` and `$2400` returns every one
intact. Moving player 2's state from `$2730` to `$2750` changed nothing.

## Correction: sub_D8AC is not the main loop

It has been called that here for several turns. It is not. A counter
incremented at the top of a routine hooked into it read **01 at frame 900 and
still 01 at frame 1500** -- it runs once, at race start.

That single fact explains everything that was wrong with player 2's walk.
Its track position was copied from player 1's once, at segment 0, and frozen
there. So the walk integrated zero curvature from a straight starting segment,
the steering appeared dead, and `P2_BANDX` came back holding exactly the
per-band base values -- which is precisely what the walk writes when the
position accumulator is zero. Three symptoms, one cause, and the cause was an
assumption about where per-frame work happens rather than anything in the new
code.

The game's per-frame work lives in the NMI and display-interrupt chain. That
is worth stating plainly because it reframes every cost measured in this
document: they have all been *interrupt* time, which is why the budget has
felt so unreasonably tight against a frame of some 29,000 cycles.

Moving the call to `RoadTail` -- inside `DLI_ED4F`, and genuinely per frame --
stopped the game outright: player 1's own `RowCurveOffset` came back all
zeros. About 3,400 cycles is far beyond what that handler can hold.

So player 2's walk has no home. It needs somewhere that runs every frame and
can afford roughly 30 scanlines, and no such place has been found yet. Two
directions worth trying, in order:

* **Split it across frames.** Four or five samples per frame, completing every
  third frame. Player 2's camera would lag through curves, but the per-frame
  cost falls to something an interrupt can absorb.
* **Find the game's own per-frame physics and hook beside it**, instead of
  picking a routine that looks like a loop. Doing the latter is what cost this
  turn.

### Player 2's controller is free

Established while looking for somewhere to put the input: the game never reads
it. Every `SWCHA` read masks `$F0`, `$20` or `$10` -- all high nibble, player
1's stick -- and `INPT2`, `INPT3` and `INPT5` appear nowhere in the ROM.
Player 2's directions sit in SWCHA's low nibble, active low: bit 3 right, bit
2 left, bit 1 down, bit 0 up. Player 1 steers on `INPT0`/`INPT1` with `INPT4`
as trigger, so the identical shape of input is available for player 2 when its
steering wants to be analogue rather than a stick.

## What actually runs each frame: a sampling profiler

Two probes in this project read numbers off builds that had already stopped
running, so the tool for this question had to satisfy two conditions: change
nothing in the ROM, and report liveness in the same run as the measurement.

`mirror-lab/checkpoints/profile.lua` samples the program counter and buckets it
by 256-byte page, alongside a speed/position check. On a healthy build over a
hundred frames:

    LIVENESS speed=A0 playerx=00 -> RUNNING
    SAMPLES 101
    PAGE $DB00   101  100.0%

**Every sample lands in the vblank wait.** `$DB00` is `BIT MSTAT / BPL`,
reached from rom:F160 inside the NMI handler. The game finishes its frame work
and spins there. That confirms what the `sub_D8AC` sentinel implied from the
other direction -- the per-frame work lives in the interrupt chain, and there
is genuine idle time before vblank rather than a frame that is merely full.

The sampler fires once per frame rather than continuously, so this answers
"which routines tick every frame" and not "where do the cycles go". A real
cycle profile would need a finer timer than the lua API offers here.

### Liveness of every prototype, same probe

| build | frames 1400-1450 |
|-------|------------------|
| lateral camera (13) | RUNNING |
| first track walk (14) | **DEAD** |
| walk in sub_D8AC (15) | RUNNING |
| steering (16, the .a78) | RUNNING |

Worth running before trusting any of them. It also caught a bookkeeping error:
the `.a78` and the `.py` saved as checkpoint 16 are different builds.

### Still open, and narrowed

Calling player 2's per-frame work from `RoadTail` -- inside `DLI_ED4F`,
genuinely per frame, with roughly 110 scanlines of idle ahead of the vblank
wait -- kills the game at every frame range tested. Bounding the
segment-advance loop to 32 steps does **not** fix it, so it is not a spin
inside an interrupt, which was the obvious suspect.

The next test is one build and separates the two remaining explanations:
call `P2Frame` from `RoadTail` with the walk stubbed to an immediate `RTS`. If
that runs, the problem is the walk's cost or contents; if it dies, the problem
is calling anything from that point at all.

## Player 2's track walk, split across frames

It was never the call site and never the contents. Bisected against the
profiler's liveness check:

| test | result |
|------|--------|
| `RoadTail` calls `P2Frame`, which returns immediately | runs |
| `P2Frame` runs steering and follow, walk stubbed | runs |
| full walk, 1 sample | runs |
| 2, 3, 4, 5, 6, 8, 10, 11, 12 samples | runs |
| **13 samples** | **dead** |

Cost, and the ceiling is twelve where thirteen are needed. One sample short --
which is why every earlier attempt died without a hint as to why.

So the walk runs in halves: samples 0-6 on one frame, 7-12 on the next,
completing every second frame. Nothing needs saving to make that work; the
accumulators -- distance, segment index, velocity, position -- already live in
RAM, so the second half simply carries on from where the first stopped. Only
the index and the stopping point differ between the two.

### The bug the split introduced

The parity byte is read at the top of the routine and toggled further down, so
the "should I initialise" test was reading the value *before* the flip. The two
halves were therefore computed from different starting states and did not join.

It showed as a clean step in the position accumulator at exactly the boundary
band -- `...10 0C | 0F 0D...` where the sequence should have been smooth. That
is the useful part: a discontinuity precisely at a split boundary is a
statement about the split, not about the arithmetic either side of it.
Inverted, the accumulator reads `21 1D 18 14 10 0C 09 06 04 02 01 00 00` --
continuous, and decreasing from far to near as the geometry requires.

Player 2's viewport is now drawn from its own track walk, its own lateral
camera, and its own display lists, every frame.

## Player 2 drives

Player 2 now has its own car rather than its own view of player 1's. The stick
is free -- the game never reads SWCHA's low nibble -- so up and down are
throttle and brake, left and right steer. Its position along the track is its
own: speed added to the distance into the current segment each frame, carried
into the next segment for as long as the distance exceeds that segment's
length, the same shape the engine uses for player 1. Nothing is copied across
any more.

Verified live: speed climbs 00 to C0, the segment index advances through the
track, the distance accumulates, and the lateral offset runs 00 to 3C under
steering. The two viewports show different parts of the track.

### Two traps, and they cost most of the session

**`-playback` overrides the input ports.** Every attempt to test player 2's
stick under a recording silently discarded the presses. The steering looked
dead when it was simply unreachable. SWCHA was correct throughout -- probed
without playback it reads `$FE` for P2 Up, `$F7` for P2 Right and `$EF` for P1
Up, exactly as documented. Input has to be tested without `-playback`, which
means driving Select, Reset and player 1's button from lua to get into a race
first.

**Duplicate labels assemble silently.** An older steering block was still
inside `P2Frame` when the new drive routine added its own, so two
`P2NotRight:` labels existed. The build succeeded. Branches resolved to the
first definition, so the new code jumped backwards into the old block -- which
is why the steering appeared to work while the throttle never ran at all. One
symptom present, one absent, from a single cause.

The rule worth keeping: after replacing a generated block, grep for its labels
and assert the count. The assembler will not do it, and the failure looks like
a logic bug in whichever half you did not write most recently.

### What two-player still lacks

* Player 2 has no car sprite in its own view, and no traffic -- its viewport is
  road only.
* No HUD of its own: speed and lap are player 1's.
* Its speed scale is uncalibrated. Adding the speed byte straight to the
  distance is not the engine's own scale, so `$C0` is far faster than player
  1's equivalent.
* No collision, and no interaction between the two cars.

## A shared divider, and the bands that turned out not to be clipped

The divider now belongs to both players: its top row is player 2's, matching
the viewport above it, and the lower two rows stay player 1's, matching the
viewport below. Player 2's row is a display list of its own at `$2770`, seeded
at boot from the row it replaces so it draws legibly from the first frame.
Both the boot template and the triplet `HudReassert` rewrites point at it, so
it survives the start light and the per-lap banner.

What it does not yet have is player 2's *content*. The HUD rows are five-byte
extended headers pointing at character buffers in RAM -- the top row is two
objects, `$1F8A` at x `$0C` and `$1F9D` at x `$68`. Saying something about
player 2 means writing those character codes, which needs the game's character
encoding established first: which code is which digit, and where the game
writes its own. That is a reading job rather than a building one.

### The bands are not clipped

Measured rather than assumed: both views render all twelve bands at full
six-line height. The top runs y=11 to 82 and the bottom y=136 to 207, 72 rows
each, with band boundaries landing exactly every six rows.

What happens at the nearest band is horizontal, not vertical. Its road spans
96..319 in the top view and 0..227 in the bottom -- it is simply wider than the
320-pixel line at that depth and runs off both sides. The total display is 249
lines, which is what stock uses, so the bottom view ends exactly where stock's
road ends and any remaining loss is overscan that affects stock equally.

## The near bands' road is drawn in two halves, and they have collapsed

The five near bands draw the road as two objects -- a left half at slot +00 and
a right half at slot +04. Probed at runtime, slot 1's x minus slot 0's x reads
**00 on every near band in every frame**, so the halves sit on top of one
another. That is both reported faults from one cause: player 2's left half is
not missing but hidden behind the right one, and player 1's near bands look
stuck in a turn because the road being drawn is half its proper width.

The generated code is right and reads two different sources, `$0060+n` for the
left half's x and `$1B30+n` for the right's. Both read zero at runtime, where
the original dumps had them `$3C` apart. So an array upstream is not being
filled, and *that* is the bug.

Two workarounds were tried on the assumption it could be derived instead.
Neither works, and both are worth recording:

* **A constant gap.** It is not constant -- the offset is the left half's own
  width, which varies per band and per frame. `$3A` closed the seam on the four
  rows sampled, and left 47 rows split across three frames once measured
  across the whole near region. Four rows is not a measurement, and it briefly
  looked like a fix.
* **Derived from the width**, `bytes*4 - 4`, from MARIA's width field holding
  32 minus the byte count. This matches the original dump exactly -- 16 bytes
  wide, `$3C` apart -- and still leaves 47 rows split.

A derivation that matches the recorded data and still fails means the premise
is wrong somewhere: most likely the HPOS-per-byte figure, or the right half's
width being independent rather than the remainder of the left's.

The next step is not a third formula. It is finding why `$1B30+n` reads zero,
because with that array intact the original arrangement needs no derivation at
all. `sub_E8AC` fills those near-band arrays, and the walk-tail strip at
rom:E9BE is the only change this project has made anywhere near them.

## What's open

Corrections to earlier versions of this list are noted where they apply, since
two items on it turned out to be wrong rather than merely unfinished.

* **The score and the cars-passed tally: located.** `run-01` (TEST, driven to
  completion) is the recording that settles it, and a live tap confirms it
  against the number that actually appears on the results screen: 23 cars
  passed, 2 collided, 0 signs hit.

  `ram_009E`/`009F` (a 2-byte BCD pair, zero-page) is the live cars-passed
  counter. `rom:D08F`/`D091` zeroes both at race setup. `sub_CA90` (`rom:CA90`)
  is the only place either byte is written during the race, and it is a plain
  BCD `+1`. Tapping it across all 17,115 frames of `run-01` gives exactly 26
  increments -- three of them boot-time noise before the cartridge owns that
  RAM (matching the same init-garbage pattern documented for the sound IDs
  above), 23 real ones, landing on `$23` (BCD 23) at the frame the race ends.
  That is not a coincidence checked against a guess; it is the actual byte
  read back at the moment the game itself consumes it.

  What consumes it, read straight from the code: `sub_D31C` (`rom:D31C`) is
  the end-of-race check -- clock expired or car stopped, then `LDA ram_009F /
  ORA ram_009E`, and only if that is nonzero does it call `sub_D802` (draw the
  results screen) and `sub_DB40` (draw the track name). `sub_DB40`'s tail
  (`rom:DB5E-DB79`) is the handoff: `LDA ram_009F / STA ram_00AB`, `LDA
  ram_009E / STA ram_00AC`, start sounds `$0C`/`$0D` ("score tally" in the
  audio survey above), and fall into `sub_D253`'s state machine at mode `$08`.
  That mode is `sub_D582`: every 18 frames, decrement `ram_00AC` by 1 (BCD)
  and call `sub_D684` once, which adds `$50` (BCD 50) to a 3-byte accumulator
  at `ram_1CA5-1CA7` -- **50 points a car**, exactly the manual's number, and
  `ram_1CA5-1CA7` is therefore the score's real storage, found as a side
  effect of chasing the counter rather than by any of the three approaches
  that had failed against it directly (monotonic scanning defeated by BCD
  carries, packed-BCD adjacency defeated by parallel tables, alphabetical
  text defeated by relocated letters).

  `ram_00AC` is reused, not dedicated: earlier in the same results sequence
  (mode `$0E`, `sub_D69E`/`rom:D6B1`) it holds **seconds remaining** instead,
  counted down the same way but calling `sub_D684` four times per decrement --
  200 points a second, also exactly the manual's number. `run-01`'s log shows
  this stage first (18 down to 0, frames 15713-16037), then the reload to 23
  and the cars-passed stage (frames 16055-16469), back to back -- which is
  why `run-02` (clock hit zero, no seconds bonus) only ever exercises the
  second stage and looked like a smaller mystery than it was.

  One thing about the trigger is understood in effect but not yet in full
  mechanism: `sub_CA90` is reached from a type-independent check (`rom:CA76`,
  gated on a slot being empty -- `ObjType,X AND $07 == 0` -- with its Z having
  just gone negative, itself gated on an earlier flag set only when that same
  empty slot's Z was small and positive). A direct lifecycle trace of every
  slot in `run-01` finds only **two** genuine type-3 (rival car) events in the
  whole race, and both are immediate crashes (`CrashSlot`/`CrashTimer` set on
  the same frame) -- matching "2 collided" exactly, but meaning a *passed* car
  never shows up in the object table as type 3 at all by the time this check
  sees it. Something reclassifies a successfully-avoided car to empty before
  it reaches this test; what does that, and where, is the next thread if the
  full picture matters later. It does not change anything above: the counter,
  its value, and its consumption are confirmed against the game's own results
  screen, not inferred from the object-type theory.
* **The fourth track.** Tracks 2 and 3 are 85 and 89 segments; only TEST and
  FUJI have been decoded and driven. SUZUKA is track 2 by name order, but the
  fourth name has not been read out of the ROM.
* **The RAM handler at `$2456`.** Nothing selects DLI index 0 and nothing
  writes that address during `run-01`. Settle whether any mode does.
* **`$8000-$9CCE`, 7,375 bytes.** The graphics block. The display list names
  `$87xx`-`$8Bxx`, `$9Exx`, `$AAxx`, `$B0xx`; nothing yet says what they draw.
* **`$AE2F-$C17D`, 4,943 bytes**, which traced code reads from 36 distinct
  addresses. Understood in role, undeclared in detail.
* **The silent ranges**, where nothing traced reads at all -- `$F281-$FFFF`
  (which includes the 6502 vectors), `$E085-$E1CA`, `$DE0D-$DEC7`. Both the
  physics and the state handlers were found in ranges that looked exactly like
  these, so they are the place to look next, not the place to assume is data.

Two entries that used to sit here have been resolved and should not be
reintroduced:

* `SpeedPenalty16` at rom:D6E8 was "not established". It is the scripted stop,
  and its `SBC #$10` has no `SEC`, so it subtracts 17 rather than 16 -- which
  is exactly the ramp measured at the end of qualifying and at time-out.
* This list used to say the game is "nearly silent without input, so the audio
  tooling that dominated the sibling projects will contribute little here."
  That was wrong on both counts: there are twenty sounds, each driving three
  independent streams, under a priority scheme worth the read on its own.

## The recordings

* `run-01` (17,115 frames): the TEST track, driven to completion. It includes a
  crash and a stretch where a system dialog took the controls, so input during
  that window is not the player's and should not be read as intent.
* `run-02` (11,942 frames): the FUJI track -- puddles, a sign struck, a lot of
  skidding, and the run ends when the clock runs out rather than at a finish
  line. It exercises every hazard the manual names, which is why most of the
  live findings here cite it.

## The near bands' "second array" does not exist ($1B30 / $1B7E)

**Confirmed live.** The near-row injection (rom:EE73, scanline >= 48) writes four
bytes per row, and the two it takes from `$1B7E+n` and `$1B30+n` were treated
throughout this project as a *separate pair of near-band arrays*. They are not.

    $1B00 = RowCurveXStaged (78 bytes, $1B00-$1B4D)   ->  $1B30 = +48
    $1B4E = RowCurveYStaged (78 bytes, $1B4E-$1B9B)   ->  $1B7E = +48

and `n = row - 48`, so `$1B30+n` is simply `RowCurveXStaged[row]` and `$1B7E+n`
is `RowCurveYStaged[row]`. The near bands' right half is positioned by exactly
the same per-row curve array the far bands use. The left half comes from the
zero-page pair `$007E`/`$0060`, which `StageRowCurveForDLI` copies out of
`ram_1C38`.

What gave this away: grepping the whole disassembly for writers of `$1B30` and
`$1B7E` returned *nothing*, direct or indexed. The only indexed stores anywhere
near them use base `ram_1BEA`/`ram_1BEB` (rom:E360, E5FC, E60B), which start
*above* `$1B30` and so can never reach it. An array with no writer is not an
array.

### Why this broke the split-screen build

The walk-tail strip at rom:E9BE stopped `RowCurveXStagedSrc` being written, so
`StageRowCurveForDLI` copies nothing into `RowCurveXStaged` *or* into its
zero-page mirror `$0060`. The far bands were given a replacement for this
(`RowCurveOffset + band_base`); the near bands never were. Both of their halves
therefore read zero, landed on the same x, and the road collapsed -- which the
user saw as "the bottom view's nearest bands look stuck in a left turn" and
"the top view's left half is outright missing in the nearest bands".

### The relationship, measured off the stock ROM

Dumping `$0060[0..29]`, `$1B00[48..77]`, `$007E[0..29]`, `$1B4E[48..77]` and
`RowCurveOffset[48..77]` from the *unpatched* ROM under run-02, at three frames:

    slot1 x - slot0 x == $3C on all 30 rows at every frame, without exception
    slot1 x == RowCurveOffset[row] + base, base flat within each 6-row band
               and equal to $48 $44 $3C $34 $30 for bands 8..12
    slot0 W == (slot1 W & $20) | $10

The base table is not new: `band_base(row)` (`dat_EBA4[dat_BB7E[row]]`) already
returns those five values. slot0 is a fixed-width 16-byte object sitting a
constant $3C to the left, not a second perspective-scaled half -- which is why
every attempt to *derive* the gap from the width failed.

So each near band is rebuilt from two arrays that do survive the strip:

    LDA $1B7E+n   STA slot1W          ; RowCurveYStaged, filled by sub_E8AC
    AND #$20  ORA #$10  STA slot0W
    LDA RowCurveOffset+i  CLC  ADC #base  STA slot1x
    SEC  SBC #$3C  STA slot0x

### Corrections this supersedes

* **Wrong:** "`$1B30` is the near bands' slot1 x array." It is `RowCurveXStaged`
  at the near rows.
* **Wrong:** "only slot1 is broken; `$0060` is intact." `$0060` is the zero-page
  copy of the same dead array and reads zero as well. Checking only the *gap*
  hid this, because with both halves zero the gap is a plausible-looking number.
* **Wrong (checkpoint 22):** deriving the gap from the width (`bytes*4 - 4`) or
  pinning it to a constant added to a broken slot0. The constant $3C was right;
  adding it to zero was not.

### Method note

Cross-build frame numbers are still not comparable -- builds desync, so the
stock ROM at f1500 is not this build's f1500. The stock dump was used only for
the *relationships between arrays within one frame*, which are frame-invariant,
never to compare absolute values against the patched build.

### The mirror needed the same fix, separately

Player 2's road is staged by `p2_stage_src`, not by the road's own routine, and
it collapsed for a second, independent reason: its `emit()` helper *discards*
the x source it is passed and writes `P2_BANDX[band] + accumulator` into both
slots, and it read slot0's width from `$007E` -- the dead zero-page copy of
`RowCurveXStaged`'s partner. So fixing player 1 left the top view exactly as it
was, which is what the user saw ("Missing the left half on the top view still").

The mirror now applies the same rule, with one wrinkle: the walk accumulator
must advance exactly once per band, so that step is inlined rather than being
run once per slot as `emit()` did.

Lesson worth keeping: this project has **two** road-staging paths, and a fix to
the shared geometry has to be applied to both. Verifying only player 1's DL
addresses ($244C..$24D4) says nothing about player 2's ($2646..$266E).

## The rumble-strip wraparound: an 8-bit HPOS cannot hold a negative position

**Confirmed live, and fixed.** The user reported that the wraparound "starts when
the player car starts hitting the rumble strips" -- that is, at large lateral
offsets. Reproduced at f2079 of run-02 (PlayerX = 104) and measured objectively
by counting road-coloured pixel runs per scanline:

    stock, PlayerX = 92    0-129                 one run
    ours,  PlayerX = 104   0-131  and  278-319   two runs

The second run is columns 139..159 in MARIA units, which is exactly where
`near band 12 slot0` sat. So this is ours, not an inherited artifact.

### Mechanism

MARIA's HPOS is eight bits against a 160-wide line, and wraps at the 255/0
boundary. That makes x in `$A0..$FF` render *correctly* as a negative position:
the head lands past column 159 and is invisible, and only the part that runs
past 255 comes back at 0.., which is precisely where a negative-positioned
object belongs. The road relies on this constantly -- at f2079 every band had x
between 199 and 250.

The failure is when the intended position is so far left that its byte drops
back into `$00..$9F`. With slot1 at `$C7` (= -57) slot0 is at -117, whose byte is
`$8B` = 139 -- an ordinary on-screen column. MARIA draws it there, as a detached
slab of road at the right-hand edge.

slot0 is the half this happens to because it sits a fixed `$3C` to the left of
slot1, so it crosses the boundary first. It is 16 bytes = 64 pixels wide, so it
is entirely off-screen exactly when slot1 is in `$A0..$FC`, and parking it at
`$C0` hides it with no wrap of its own (`$C0` + 64 = 256, so its span ends at
255). `$FC` is the correct cutoff: at slot1 >= `$FD` a few of slot0's pixels
legitimately reach column 0, and those still render correctly unaided.

This is why the earlier clamp (checkpoint 10) failed. It clamped x directly and
ate visible road on ordinary frames, because on ordinary frames the large x
values are *correct*. The fix has to distinguish "large x meaning negative,
which works" from "small x meaning very negative, which does not", and only the
second is repairable.

### Also corrected here

`slot0 W == (slot1 W & $20) | $10` from checkpoints 23/24 was wrong: it keeps
only one of the three palette bits. Over 7300 frames x 30 rows on the stock ROM
it fails 201 times, because the road uses palette 7 as well as 0 and 1. The
correct mask is `& $E0`, which holds everywhere.

And `slot0 x == slot1 x - $3C` is no longer just a measurement. `dat_EBA4` and
`dat_EBA9` are one contiguous table that the disassembler split in two:

    EBA4: 44 40 38 30 28 24 1C 14 48 44 3C 34 30 0C 08 00 F8 F4
    dat_EBA4[8..12] = 48 44 3C 34 30     slot1's perspective base
    dat_EBA9[8..12] = 0C 08 00 F8 F4     slot0's

Every pair differs by exactly `$3C`, which is why the constant is exact.

### Cost

Inline, the guard was 10 bytes a band over 10 bands -- 100 bytes the blob does
not have, and it overran the free `$FF` run at `$F3FF-$FF7E`. As a `JSR` it costs
`JSR` + `STA`, exactly what `SEC` / `SBC` / `STA` cost before, so the blob does
not grow. The price is 12 cycles a band, about one scanline over all ten.

### Not fixed: the opposite edge

The mirror-image case is an object whose x is on-screen but whose span runs past
255, spilling its tail onto the far edge. A detector over run-01 and run-02
found **zero** occurrences in either view -- but both recordings keep the car to
the right of centre, so that case is unexercised rather than shown absent. It
would need x in roughly 133..159 on a 29-31 byte band, which is what a hard left
excursion should produce. Left unfixed pending a case that actually reproduces
it; clamping the width would be the repair, since only invisible and spurious
pixels lie beyond 256.

## Player 2's car

**Confirmed live.** The top view drew road and nothing else. The player's car is
slot `+1C` of player 1's near-band display lists -- palette 6, 8 bytes wide, and
x = 64 in 5999 of 6700 frames sampled -- spanning bands 8 to 11 with one
graphics page per band. The page is a base plus a lean offset of 0, 8, `$10`,
`$18` or `$20`, with `$10` upright. Empty object slots in those lists are parked
at x = 161 with a 1-byte width, the same off-screen idiom the wrap guard uses.

x = 64 is the correct value for player 2 as well, not an approximation: the car
is centred and the *road* moves under it, and player 2's road already moves with
player 2's steering. So width and x are baked into player 2's template and only
the graphics page is copied each frame -- two byte copies a band over four
bands.

Placement checks out against the live zone list: player 2's road occupies
scanlines 20..91 and its car lines 62..85; player 1's road occupies 145..216 and
its car 187..210. Both are 58%..90% of their own view.

`P2_DL_SIZE` went from 10 to 14 to fit the third object.

### A layout trap worth naming

Growing `P2_TEMPLATE` to 168 bytes ran it from `$FB80` into `P2_HUD_TEMPLATE` at
`$FC00`. The failure surfaced as `at $FC00 expected ffffff.. but found
80808d1f8080e0d8aa40..` -- that is, the patch found *its own* data and reported
it as "this is not the ROM this patch was written for", which points at the
wrong thing entirely. The blob and these templates share one free `$FF` run and
have both outgrown their slots several times now, so there is a layout
assertion up front that sorts the four regions and names the colliding pair.

### Still scaffolding

The lean follows player 1's steering, since the page is copied rather than
selected from player 2's own state. Driving it from `P2_LATERAL` means decoding
which bases are the car and which are the crash and spin sprites -- band 11
alone showed `$8B00`/`$08`/`$10`/`$18`/`$20` for the car but also `$8660`,
`$86BA` and `$98EF` in other states -- so substituting lean bits blindly would
corrupt those.

## Player 2's car lean

**Confirmed live.** The lean is not worth decoding from `dat_E83E` -- that table
is indexed by object type at rom:E577, not by lean. There is a far simpler
handle: all four car bands carry the same lean, and band 11's base is `$8B00`,
so **band 11's low byte is player 1's lean** -- one of `$00 $08 $10 $18 $20`,
with `$10` upright.

Every band's page is base + lean, so adding `(L2 - L1)` to player 1's low byte
turns his car into player 2's with no knowledge of any band's base. Band 10's
base moves between `$AAE0` and `$9100` with the wheel animation at rom:E7D3, and
the delta absorbs that for free.

Guarded on band 11 being the ordinary driving sprite: high byte `$8B`, low byte
no greater than `$20`. The crash, spin and start sprites are on other pages --
`$8660`, `$86BA`, `$98EF` and friends were all observed -- and offsetting into
those would draw garbage, so in those states the page copies through unchanged
and player 2's car shares player 1's animation.

Player 2's lean is three-state, straight off the stick, where player 1's is a
five-state gradual one. Matching the easing would mean reproducing whatever
drives player 1's, and **no single RAM byte determines it**: every zero-page
address was checked for a consistent value-to-lean mapping over 5933 frames and
none held.

### Two method notes

**A same-frame comparison of the two cars is not a valid check.** The copy
happens during MirrorStage and player 1's slot can be rewritten later in the
same frame, so an end-of-frame sample compares a value written at one moment
against one written at another. That produced 56 "wrong" copies and 4 impossible
lean values, all of which were sampling artifacts. The invariant that actually
holds is time-independent: *every page player 2's car shows must be one player
1's car also uses*. Over run-02 that holds on all four bands, with no extras.

**And the stick cannot be tested under `-playback`**, which overrides the input
ports -- the first attempt appeared to show the left lean doing nothing, when in
fact the race had not started and player 2's list still held its template seed.

### Layout, again

The blob overran `DLL_TEMPLATE`. The checkpoint 26 assertion missed it because
it only covered the four templates, not the blob; it now measures the blob first
and includes it in the check. `FINE_ZONES` is 0, so `MINI_TEMPLATE` is unused
and everything above `$FD0C` was free -- the templates moved up and the blob has
`$F400..$FCFF`, currently 1858 bytes with 446 spare.

## Player 2's speed, put on player 1's scale

**Confirmed live.** Player 1's track advance is **exactly Speed/12** per frame:

    Speed  16 -> 1.33 units    Speed 143 -> 11.83
    Speed 106 -> 8.83          Speed 198 -> 16.50
    Speed 123 -> 10.17         Speed 210 -> 17.50

and its speed byte tops out at 255, rising by 1 on 52% of rising frames and
falling by 2 on 47% of falling ones (the larger drops are crashes and
off-road). Player 2 was adding its speed byte to its position raw and capping at
`$C0` -- 192 units a frame against player 1's 21.25, about nine times too fast.

Player 2 now uses the same cap (`$FF`), the same ramp (+1 / -2) and divides its
advance by 12, **carrying the remainder between frames** rather than discarding
it, which would lose up to 11/12 of a unit every frame. Repeated subtraction is
exact and small, and the loop is bounded: the remainder is always left below 12,
so the worst case is 21 passes, and a carry out of the add is handled by
pre-subtracting 192 (`ADC #$3F` with carry set adds `$40`). No division table
was needed after all.

Verified: the quotient cycles 22, 21, 21, 21 at full speed, a mean of 21.25 over
949 advancing frames -- exactly 255/12.

### Two measurement traps, both mine

**A signed delta.** The first attempt to measure player 1's rate reported 0.00
units/frame at *every* speed, because the probe filtered on `delta >= 0` and
player 1's `$00D5/$00D6` counts **down** -- it is distance remaining in the
segment. A filter that excludes the sign the counter actually moves in produces
a clean, entirely wrong table of zeros.

**Averaging in frames that are not racing.** An aggregate over a frame window
then reported player 2 advancing 12.76 units/frame instead of 21.25. 467 of the
1416 frames at speed 255 were before the race began, where the speed byte is
already pinned at 255 but the walk is not running, so they contributed zero.
21.25 x (949/1416) = 14.2, and over the wider window 12.76. Counting advancing
and non-advancing frames *separately* settled it. A mean over "frames at speed
255" is not a mean over "frames where the car was moving".

## The track gap between the two cameras

**Confirmed live.** Everything that has to relate the two cars -- drawing one in
the other's view, collisions, and traffic -- rests on one number: the signed
track-unit gap between the cameras.

It is worth having because **segment lengths and the perspective Z table are the
same units**. `AccumulateRowCurveOffset` adds `SegLenLo/Hi` into the very
accumulator it then compares against `dat_EB56`/`dat_EAB9`, so an object's
distance from player 2 is simply its distance from player 1 plus the gap. That
means the ROM's own Z-to-row search, `sub_E3CD` (a linear walk from row `$4D`
down, comparing a 16-bit Z against the perspective table), can place objects for
player 2 exactly as it does for player 1. Traffic does not need a new
projection, only the gap.

The gap is accumulated from what each camera **actually moved**, not from speed,
which would drift. Player 1's `$00D5/$00D6` is **distance remaining** in its
segment and counts DOWN (measured: 127 units per 6 frames at full speed, i.e.
21.2/frame), while player 2's counts up from the segment start -- hence the
subtraction, and the separate branch for a segment boundary. Only one boundary
can be crossed per frame: the fastest advance is 21 units and segments are
thousands long.

Verified against a gap computed independently from both (segment, position)
pairs: **1500 frames, 0 disagreements, worst error 0 units.**

It is saturated at +-`$4000`. It is a running total and player 1 laps the track,
so left alone it overflows -- measured `-32747..32689` over one run -- and every
wrap through zero reads as the two cars occupying the same place.

## Car-to-car collision, and three ways it went wrong

**Confirmed live.** The test is a box: `|gap|` under `COLLIDE_Z` and the two
lateral offsets within `COLLIDE_X`. The constants are estimates meant to be
tuned by feel -- about a car length at racing speed, and about a car width given
that player 1 reaches +-104 across a road roughly 160 pixels wide.

**The penalty must be paid once per contact, not per frame.** Charged every
frame it is not a collision, it is a clamp. The cars start the race on the same
piece of track, so they touch from frame one, and player 1 could never
accelerate off the line: run-02 went from HEALTHY to STALLED with player 1's
speed pinned at 0 for the first 1500 frames, 1566 of 6700 frames inside the box.
Contact now also pushes player 2 sideways so the overlap resolves rather than
persisting until something else separates them. Only player 2 is pushed --
shoving player 1's lateral would be reaching into the game's physics rather than
working alongside it.

**There was no race initialisation at all.** Player 2 began from whatever RAM
held at power-on and the gap from a garbage previous-frame reading. `P2RaceInit`
now lines player 2 up level with player 1 along the track and `P2_START_LATERAL`
to the side, outside the collision box, so the grid is not an overlap.

**And that init must not be hooked into the race-start routine.** A `JSR
P2RaceInit` inside `StartDriveHud` cost enough time to change how the race ran
-- run-02's race ended some 4000 frames early. This is the same cycle
sensitivity that already forced the light and banner templates to be matched
line for line. It now triggers off a transition of the game's own state byte
`$009D` into `$02` (qualifying drive) or `$03` (race drive), read out in
`RoadTail` where there is headroom. The trigger costs nothing in the hot path.

Isolated with `PP2_NO_COLLIDE`:

    baseline (checkpoint 28)      HEALTHY  296 @ f592   101 clock values
    gap + init, collision off     HEALTHY  296 @ f592   101 clock values
    gap + init, collision on      STALLED  395 @ f5959  101 clock values

The gap and init are byte-identical to baseline. The remaining difference is the
collision working as intended: under these recordings player 2 sits parked on
the racing line forever, so player 1 laps into it, loses time, and the race ends
earlier, leaving an idle stretch inside the 7000-frame window. The game recovers
after f5959, so it is not a hang -- but a recording with two cars actually being
driven is the only honest test of this, which is what `Record a test run.bat`
is for.

## Traffic: not done, and what it needs

Player 2 still has no traffic. The projection is solved -- gap plus `sub_E3CD`,
above -- but the **display list has no room**. Player 2's bands are 14 bytes:
two road objects, the car, and the end marker. Player 1's are 34, with six
object slots at `+08`..`+1C` (empties parked at x = 161 with a 1-byte width, the
same off-screen idiom the wrap guard uses) and the car at `+1C`.

Giving player 2 the same six slots means `P2_DL_SIZE` 34, so 12 x 34 = 408 bytes
from `$2600`, which runs to `$2797` and straight through player 2's own
variables at `$2702`..`$276E`. So traffic needs those variables relocated first,
and `$2730` is already known not to be free. One extra slot (`P2_DL_SIZE` 18,
ending at `$26D7`) would fit without moving anything, which is enough to draw
player 1's car in player 2's view and vice versa -- arguably the more valuable
half of "traffic" for a two-player mod, and the next thing to do.

Objects are 21-entry parallel arrays at `$1A7F`, `$1A94` (row), `$1AA9`,
`$1ABE`, `$1AD3`, `$1AE8`, with `ObjZLo`/`ObjZHi` at `$19C4`/`$19D4` holding each
object's Z **relative to player 1** -- which is exactly the quantity the gap
converts.

## Lateral sign: a rising lateral moves the car LEFT, for both players

**Confirmed live.** Player 2's steering was reversed. Measured on a two-player
recording: holding right moved `P2_LATERAL` **+1.000 a frame** and player 2's
road x **+1.018 a frame** -- and a road moving right is a car moving left.

Player 1 uses the same convention. Correlating `PlayerX` deltas against road x
did **not** settle it -- 45 usable samples averaging exactly 0.00, no
correlation -- because player 1's road x also moves with the curve, which
swamps the lateral contribution. What settled it was forcing `PlayerX` to `+40`
and `-40` on alternating four-frame blocks, so both samples see the same stretch
of track: mean road x was **54.6** and **43.6** respectively. Positive `PlayerX`
puts the road further right, so **positive `PlayerX` is a car to the LEFT**.

This matters beyond the bug. Because both laterals rise leftward, the collision
box comparing `P2_LATERAL` against `PlayerX` is comparing like with like and
needed no change. Only the steering was wrong, so only the steering was
touched: right now steers toward the negative end, left toward the positive.

The lean was already right and was left alone. Averaging player 1's lean byte
over frames where it was moving each way gave `$11` moving right against `$0B`
moving left, with `$10` upright -- so a higher value is a lean to the right,
which is what the `$18`/`$08` mapping already produced.

### Method note

A recording made on one build cannot validate the build that fixes it: changing
the ROM desyncs it, and `-playback` overrides the input ports, so the stick
cannot be exercised under playback at all. Both directions were checked by
driving the ports live.

## The road stripes, and the writer of $007E

**Confirmed live.** The top view's stripes scrolled to *player 1's* speed,
because player 2 took its width bytes out of player 1's arrays and the stripe
palette rides in the same byte. With no HUD of its own, the stripes are player
2's only speed cue, so they were actively misleading.

Reading the rest of `sub_E8AC` gives the whole mechanism:

    ram_00AF -= Speed/2 each frame; every time it goes negative it gains $14
    and the phase steps on -- so roughly Speed/40 steps a frame
    ram_00CD = phase, 0..29
    ram_00FD/FE = $1F00 + ram_00CD

    RowCurveYStaged[row] = $1F00[phase + dat_C07E[row]] | ram_1F3C[row]
    ram_004E[row]        = $1F00[phase + dat_C07E[row]] | $10

**That last line is the missing writer of `$007E`.** It is `STA ram_004E,X` at
rom:E8F8 -- base `$004E`, and `$004E + 48 = $007E`. Earlier this array was
recorded as having no writer anywhere in the disassembly, which was wrong: the
search was for base `$0060`, the array's *other* half. The lesson is the same
one `$1B30` taught -- these are not separate arrays, they are offsets into
longer ones, and searching for the offset finds nothing.

It also explains why `slot0 W == (slot1 W & $E0) | $10` held over every frame
tested: both are the same texture byte, one ORed with the row's width field and
the other with `$10`.

Player 2 now keeps its own phase and accumulator, advanced by `P2_SPEED` using
`sub_E8AC`'s own arithmetic, and builds its width bytes rather than copying.
`dat_C07E[row]` is fixed per row so it is baked in, and it never exceeds 29, so
`phase + offset` tops out at 54 -- absolute-indexed addressing is enough, where
the engine needs a zero-page pointer because its index is a variable row.

Verified three ways: **decoupled** (under playback with player 2 parked, player
1's phase takes all 30 values across 3089 frames and player 2's never moves);
**correct rate** (traced at speed 255 the phase runs 28, 4, 10, 17, 23, 29,
6... = 6.375 steps a frame, exactly Speed/40); and **sane output** (all twelve
bands' width fields match the value player 1 uses for the same row, with only
the palette bits moving).

### The same measurement trap, twice

An aggregate over a frame window reported 2.749 steps/frame against a
theoretical 6.375 -- because the window included frames before the race started,
where `P2_SPEED` is already pinned at 255 but the walk is not running. This is
exactly the trap that made the speed work read 12.76 instead of 21.25. **A mean
over "frames at speed 255" is not a mean over "frames where the car was
moving."** Trace frame by frame, or separate advancing from non-advancing
frames, before believing an averaged rate.

## The car lean is $08 right, $18 left -- correcting an earlier finding

**Confirmed live, and this reverses what was recorded before.** Checkpoint 27
concluded that a higher lean value meant leaning right. That was wrong.

The original evidence was a correlation of player 1's lean byte against
`PlayerX` deltas, resting on **42 and 24 samples** -- `PlayerX` only updates
every few frames, so almost every frame was discarded. Repeating the measurement
against `LatVel`, which moves every frame, made it worse rather than better:
run-01 gave `+0.173` and run-02 `-1.206` for the same correlation, i.e.
**contradictory signs**, and `LatVel` is almost never negative (240 and 0 frames
across two runs), so there was nothing to correlate against.

What settled it was not a correlation at all. Two ROMs were built with the lean
pinned to `$08` and to `$18`, and each photographed: `$08` carries the car's
body mass to the right, `$18` to the left. **When a correlation keeps giving
weak or contradictory answers, force the variable and look at the result.**

It only surfaced after the steering fix because the two errors cancelled: before
that, right steered left *and* leaned left, which is self-consistent, so only
the steering looked wrong.

## The wheel flicker, and making it player 2's own

**Confirmed live.** Band 10's car sprite comes from one of two sheets, and the
alternation between them is the wheel flicker. In the ordinary driving state:

    high byte $AA  ->  low byte = $D8 + lean
    high byte $91  ->  low byte =       lean

Both **ascend** with lean, which is why the lean delta was already correct for
this band -- the thing being copied from player 1 was the *sheet*, so player 2's
wheels flickered in lockstep with player 1's.

The sheet is chosen at rom:E7D3, which overwrites band 10 with
`dat_B2ED[ram_00E1/2]` and high byte `$AA` only when `ram_00E1` is below `$0A`
and even; otherwise the generic object emitter's `$91` sprite stands. `$00E1` is
seeded to `$05` at rom:D0D5 and set from the crash timer at rom:C5FD.

Rather than reproduce `$00E1`, player 2 picks its sheet from bit 0 of its own
stripe phase, which already advances at about its `Speed/40` a frame -- so the
wheels flicker faster the faster player 2 goes, and never in step with player 1.
Outside the driving state band 10 still copies player 1's page, so crash and
spin sprites keep animating.

Verified: under playback with player 2 parked, player 1's sheet changes 486
times and player 2's 18 -- and those 18 are frames where player 1 enters or
leaves a crash state and band 10 takes the copy path, which is intended. Band
10's low byte matched its sheet's mapping on every frame of the run.

## Disconnecting player 2's crash

**Confirmed live.** Player 2's car was built by copying player 1's graphics page
and adding a lean delta, so it inherited player 1's *state* as well as its lean:
when player 1 spun or crashed, player 2's car spun with it, in a view where
player 2 was still driving normally.

Fixed by removing the dependency rather than widening the guard. The car's pages
are constants -- measured over 5163 driving frames of run-01 and 5933 of run-02,
with zero exceptions:

    band  8   high $9D   low = lean
    band  9   high $97   low = lean
    band 11   high $8B   low = lean
    band 10   high $AA   low = $D8 + lean      (wheel sheet A)
              high $91   low =       lean      (wheel sheet B)

so player 2's car is a base plus its own lean, with band 10 picking a wheel
sheet from its own stripe phase. This deleted the lean delta, the guard flag and
every read of player 1's slots -- the routine is shorter than the one it
replaced. A dependency that has to be guarded in three places is usually a
dependency that should not exist.

The one thing still read from player 1 is *whether there is a car to draw at
all*: its slot holds `$0000` before a race, and both cars come and go together,
so player 2's is parked at x = `$A1`, the idiom the stock lists use for an empty
object slot.

Verified over run-02, restricted to frames where a race is actually running:
**player 1 crashing or spinning on 768 frames, player 2 still driving on all
768**, and player 1 driving on 4407 with player 2 driving on all of them.

Player 2 now never shows a crash animation, since it has no crash of its own
yet. That is the right failure mode here -- crashing in sympathy was the bug.

### Unverified

The "no car to draw" parking path never runs in these recordings: player 1
always has a car once a race is under way, and the frames where it does not are
before the mirror code runs at all, where player 2's list still holds its
template. That path is defensive only and has not been exercised.

## Player 2's controls, mirroring player 1's

**Confirmed live.** Player 2 had invented its own scheme -- stick up and down
for throttle -- where player 1 uses the two buttons for gas and brake and the
stick to shift gear. Player 2 now mirrors player 1 exactly.

**Buttons.** Port 2's two buttons land on `INPT3` and `INPT2`, mirroring player
1's `INPT1` (gas) and `INPT0` (brake) read at rom:C188. Verified by pressing
each in turn: P2 Button 1 gives `INPT3 = $80`, P2 Button 2 gives `INPT2 = $80`,
and player 1's give `INPT1`/`INPT0` the same way -- bit 7 set when pressed.

**Gear.** Player 2 now has one, and it uses player 1's own table:
`dat_C3C1[(Speed>>4) + Gear]`, a **signed** step, which is what makes a gear
mean anything:

    lo gear   3  5  7  8  7  6  5  4  3  2  0  0 -1 -1 -2 -4
    hi gear   1  1  1  2  3  5  7  6  5  4  3  2  1  1  1  1

Held from a standstill, lo gear rockets to 160 and stalls exactly where its
table reaches zero, and hi gear bogs to 42 before climbing 176, 224, 255.

**The race gate** is player 1's own, at rom:C2D4: outside state `$01`, if both
halves of the race clock (`$00DE`/`$00DF`) are zero then the countdown is still
running and speed is bled off rather than driven. Player 2 had no such gate and
could drive off the line early. Verified by forcing 200 into player 2's speed
during a real countdown: it bled off at exactly `$0F` a frame, the rate rom:C2EB
uses for player 1.

**Steering authority now scales with speed.** An accumulator gains the speed
byte each frame and one unit is steered per carry out, so it is about one unit a
frame at full speed and nothing at all at a standstill:

    speed   0 ->  0.000 units/frame        speed 128 ->  0.506
    speed  32 ->  0.124                    speed 255 ->  1.000
    speed  64 ->  0.247

### Measurement note

The first two steering sweeps reported **0.000 at both 128 and 255** -- for two
different reasons at once. The sweep ran past the end of the attract demo, where
the mirror code stops running entirely; and at the higher rates the lateral
reached its +-60 clamp inside the sampling window and sat on it, dragging the
average down. Compressing the sweep into the drivable window and reversing
direction every 20 frames fixed both. Two independent artifacts producing the
same wrong number is a good argument for sweeping a parameter rather than
trusting a single measurement.

## Player 2 and the rumble strips

**Confirmed live.** Leaving the racing line now costs player 2 speed, on player
1's own terms. rom:C200 computes `|PlayerX|` and, at `$3B` or beyond, calls
`SkidDrag`:

    SkidDrag:  Speed -= (Speed >> 6)     ; 0..3 a frame

so the faster the car is going the harder the strip bites. Player 2 runs the
same test against its own lateral.

**The real obstacle was that player 2 could not reach the rumble strips at
all.** Its camera limit was `$3C` -- exactly one unit past the `$3B` road edge.
Raised to `$47`, which is as far as the camera can go: `p2_camera_src` reads
only the **low** byte of the lateral ramp, and `dat_EADE`, the ramp's high byte,
is zero only up to index 71. A build-time check now fails loudly by name if the
limit is ever pushed past that.

That leaves player 2 with a rumble band of 59..71 against player 1's 59..82, so
player 2 still cannot reach open grass. Widening it means handling the camera's
lateral ramp as a 16-bit value.

Verified: in hi gear player 2 reaches 255 on the road, and steering off the line
drops it to **189**, where it holds -- exactly the equilibrium where hi-gear
acceleration (+2 at that speed) cancels the drag (189 >> 6 = 2). The same test
in lo gear moves 160 to 158, which looks like almost nothing until you notice lo
gear already plateaus at 160 where its table reaches zero, so 2 is the whole
margin available.

### A detail worth copying deliberately

The ROM's `SkidDrag` performs its three `ROL`s **without a preceding `CLC`**, so
the value it subtracts depends on whatever carry the routine happens to be
entered with. Player 2's copy adds the `CLC`, making it exactly `Speed >> 6`.
That is a deliberate divergence, not an oversight.

## The lateral ramp is 16-bit, and that was the range ceiling

**Confirmed live, and this supersedes the previous entry's limit.** `dat_EA41`
is not an 8-bit table with a separate companion: it is the **low half of a
16-bit ramp**, about 3.55 per unit, and `dat_EADE` is its high byte. The value
passes 256 at index 72, which is precisely why reading only the low byte capped
player 2's travel -- past that index the step wrapped and the road would have
jumped backwards.

Reading both halves removes the ceiling entirely. `P2_LIMIT` is now `$68` (104),
matching the furthest player 1 was observed to reach, which puts the rumble
strip and **open grass** inside player 2's range. The only limit left is the
table's 120 entries, and the build-time check tests that instead.

Verified by forcing the lateral across 8..104 in steps of 8 and watching player
2's road: the per-band shift ran 0, 8, 16, 24, 33, 41, 50, 59, 67, 76, 84, 92,
101 with **zero backward steps** -- the wrap at index 72 is gone. Under stick
control the car crosses the road edge at 59, the rumble strip, and out onto
grass at 104, speed falling 255 to 189.

Grass costs the same drag as the rumble strip, which is faithful rather than
incomplete: player 1 applies the same `SkidDrag` anywhere past `$3B` and makes
grass worse through **scenery collisions**, not a deeper drag. The signs are
what is still missing.

## Correction: SkidDrag has no carry dependency

The previous entry recorded that the ROM's `SkidDrag` depended on whatever carry
it was entered with -- it rotates three times without clearing first -- and
described player 2's added `CLC` as a deliberate divergence. **That was wrong.**

After three rotations the entry carry sits in **bit 2**, and the `AND #$03`
discards it; bits 1 and 0 hold the original bits 7 and 6 either way. Checked
exhaustively over all 256 speeds against both entry carries: **identical every
time**. The ROM is already exactly `Speed >> 6`.

So there is nothing to bring into line -- player 1 needs no change at all. The
`CLC` stays as a harmless no-op with the reasoning written beside it, because a
reader will otherwise wonder the same thing and re-derive it.

The general lesson: three `ROL`s look carry-dependent and a masked result often
is not. Work out where the injected bit lands before calling something a bug.

## Objects for player 2: projection solved, blocked on the list layout

**The projection is solved**, and it needs none of the object arrays. Player 1's
near band lists already carry each drawn object's graphics, width and x, and the
band it sits in gives its row -- hence its distance from player 1, straight out
of the perspective table:

    band  8  row 51  Z = $0066        band 11  row 69  Z = $000C
    band  9  row 57  Z = $003D        band 12  row 75  Z = $0002
    band 10  row 63  Z = $0020

Add the camera gap and that is the object's distance from **player 2**, and
`sub_E3CD` turns it back into a row. Three rejections fall out for free: the
search leaves `X = $FF` past the far plane, a negative Z means the object is
behind player 2, and row 0-5 maps to band 0, which player 2 has no list for. x
transfers as the object's offset from the road **centre**, since that is what is
fixed to the track.

It was written, and then **backed out** for two reasons.

**Space.** The build came to 3070 bytes against the 2945 the only free `$FF` run
holds. A whole-ROM scan found no other run over 96 bytes except two ~100-byte
`$00` runs at `$A12F` and `$A22F`, which sit inside tables and are probably real
data. The object pass itself is only 140 bytes; most of the growth was
`P2_DL_SIZE` going 14 to 18.

**And the far bands cannot hold an object at all.** Bands 1-7 have no second
road object, so their list has **zeros at offset +04**, and MARIA reads a zero
width byte as end-of-list. Anything placed after it is never reached. Objects
would have appeared only in the five nearest bands -- and near-objects-only has
already been rejected once in this project, for the road.

### Both point at the same fix

Make the per-band lists **variable length**, laid out by what each band actually
needs, with the object slot immediately after the road objects rather than after
a car slot the far bands never use:

    far  bands 1-7     road0, object, end                10 bytes
    near bands 8-11    road0, road1, car, object, end    18
    near band  12      road0, road1, object, end         14

156 bytes against 216 -- it saves 60 **and** puts the object where MARIA will
reach it. The cost is that band addresses stop being `base + n * size`, so
`mirror_plan`, `p2_stage_src`, `p2_car_src` and the object pass all have to take
them from one table. That refactor is worth doing on its own, before objects go
back in.

### Object collision is not blocked by any of this

It needs only the gap and the two laterals, which already exist and are exact --
the same box test the car-to-car collision uses. It was held back only because
colliding with objects player 2 cannot see would be worse than not colliding.

## How objects reach the track: a rolling 16-slot window

**Measured live.** Objects do not spawn at a distance. There are **16 slots**,
each holding an object's distance from player 1, counting down as the car
advances; an object becomes visible when that distance falls below the horizon.

    visible depth              Z = 0 (bumper) .. 1300 (horizon, row 0)
    objects visible at once    7..13, usually 9 or 10

Where the 16 slots sit, as a share of all slot-frames over one run:

    already passed (Z < 0)        5.9%
    visible (0..1300)            58.7%
    ahead 1301..5000             12.1%
    ahead 5001..20000            21.8%
    over 20000                    1.6%

So a third of the list is tracked *beyond* what can be seen. Slots are recycled
-- about 30 times in 6400 frames -- but at a median Z of **6421**, five times
past the horizon, so recycling is invisible in normal play.

### Why this matters for player 2, and what it forces

The list is keyed to **player 1's** position. One reload was observed at Z =
256, well inside the visible depth. That is harmless for player 1, but player 2
sits at `Z1 + gap`, so with player 2 running ahead, a slot recycling anywhere in
1300..6000 lands inside player 2's visible range and the object **pops in
close**.

This rules out the approach the backed-out attempt used. Reading objects out of
player 1's *display list* carries no object identity, so there is no way to tell
"this slot just recycled" from "this object has been approaching for seconds".

Reading the **16-slot object array** instead makes the slot index an identity,
so player 2 can hold one byte per slot meaning *"I have seen this object beyond
my own horizon"* and refuse to materialise anything that did not arrive from the
far plane. That fixes the pop-in and makes player 2's object set derive from
world positions rather than from whatever player 1 is drawing -- genuinely
independent views, which is the requirement.

The cost is that sprite selection is type-dispatched (`sub_E475` and the paths
around it), so fetching graphics for an object player 1 cannot currently see
needs that dispatch understood. That is the remaining unknown.

### Order of work

1. Variable-length per-band lists (needed regardless, and stands alone).
2. Object array read, with the per-slot "seen beyond the horizon" flag.
3. Object collision -- which needs only the gap and the two laterals, both of
   which already exist and are exact.

## What is in the object list, and where it comes from

**Measured live.** Three classes are visible (`ObjType & 7`, the value the
pipeline dispatches on at rom:E434):

    class 0   56188 slot-frames   mean |lateral|  1.5, max 32   traffic
    class 1    3573 slot-frames   mean |lateral| 35.4, max 36   SIGNS
    class 2     306 slot-frames   mean |lateral| 16.0, max 16   fixed marker

**Signs are in the same list as the traffic**, as class 1, pinned to +-35/36
every time, with their own path at `L_E4A1` that applies a height adjustment --
what a tall roadside object needs. One implementation therefore covers both.

**And the track's objects are data, not spawns.** `ram_00A8`/`ram_00A9` is a
16-bit **cursor** that advances through `ObjSegLenLo`/`ObjSegLenHi` -- per-object
spacings laid along the track -- at rom:CF8A, and retreats at rom:CC0F. The 16
slots are a sliding window over that list. Nothing is created at the horizon;
objects are read in as the cursor reaches them.

## The right fix for pop-in: widen the window to cover both cars

Because the window is driven by one cursor, and that cursor follows player 1, a
slot can recycle inside player 2's visible range. The fix is to make the window
span **both** cars rather than to hide the symptom: load an object when the car
FURTHEST AHEAD is a horizon away from it, and release it only once the car
FURTHEST BEHIND has passed.

In player-1-relative Z, with `gap = P1global - P2global`:

    load when     Z1 <= 1300 + max(0, -gap)      ; the leader's horizon
    release when  Z1 <  min(0, -gap)             ; the trailer's zero

When player 1 leads (`gap > 0`) the load threshold is unchanged and slots are
held further into negative Z1 until player 2 has passed. When player 2 leads
(`gap < 0`) objects load earlier by exactly player 2's lead, so they enter from
player 2's horizon rather than appearing mid-view.

This removes the need for the per-slot "seen beyond my own horizon" flag
described earlier: with the window widened at the source, nothing can appear
inside either car's visible range in the first place. It needs the cursor's
advance and retreat thresholds hooked, at rom:CF8A and rom:CC0F.

## Reserve a slot for the other car

Each car should appear in the other's view, and that is better done as a
reserved slot than as a general object. Player 1's near band lists have six
object slots and at most three were ever in use, so there is room without
touching the layout. More importantly the other car needs no projection
guesswork and cannot pop in: its distance is the gap, exactly, and its lateral
is a variable already held -- both are known every frame rather than inferred
from a display list.

## The object window CANNOT be widened: the 16 slots are already full

**Measured live, and this overturns the plan in the previous entry.**

    spacing between distinct object distances   median 122 units, 25th pct 16
    objects sharing a single distance           often 7 to 9 (a row across the track)
    slots not tracking anything                 0 free 78% of the time
                                                1 free 18%, 2 free 4%

The list runs at capacity. Widening it to span both cars would need slots that
do not exist, so the load/release threshold change described above is not
implementable as written -- there is nothing to load the next object into.

### What replaces it: player 2 gets its own window

Rather than share player 1's 16 slots, player 2 keeps **its own smaller set of
slots with its own cursor** over the same track object data (`ObjSegLenLo/Hi`).
This is better on every count that matters here:

* **No exhaustion.** Player 1's list is untouched and player 2's is sized to
  what is left.
* **No pop-in, with no extra machinery.** Player 2's window loads from player
  2's OWN horizon, so objects always enter from the far plane. Neither the
  per-slot "seen beyond my horizon" flag nor the widened thresholds are needed.
* **Genuinely independent views**, which was the requirement all along.
* **The gap is not even needed for this.** Player 2's track position is already
  maintained exactly, so its cursor is driven directly from it.

The remaining unknown is where a slot's `ObjType` and `ObjLateral` come from
when the cursor loads one -- the code around rom:CC23 and rom:CF9C -- since
player 2's cursor must read the same source data.

## The two cars start on top of each other

**Measured live.** At the start of each session:

    qualifying (state $02)   PlayerX = 0  (centre)   P2_LATERAL = 48 (left)
    race       (state $03)   PlayerX = 35 (left)     P2_LATERAL = 49 (left)

In the race they are both left of centre and **14 apart**, well inside the
COLLIDE_X box of 40 -- so they begin the race already touching, which the
one-penalty-per-contact rule then charges them both for.

They need placing symmetrically at init, one either side: `PlayerX` negative and
`P2_LATERAL` positive, around +-32, which is 64 apart (outside the collision
box) and comfortably inside the road edge at 59. Note that `P2RaceInit` runs off
the `$009D` transition in RoadTail, while the game sets `PlayerX = 35` itself,
so the ordering of the two writes has to be checked rather than assumed.

This has to be fixed **before** the other car is drawn as an object, or the
first thing either player will see is the other car inside their own.

## Grid placement: the race already had the mechanism

**Confirmed live.** The two cars were starting on top of each other -- in the
race both left of centre and 14 apart, inside the collision box of 40, so they
began in contact and were both charged a collision penalty for it.

The **race** needed nothing new. It already places player 1 from the qualifying
lap, and `PlayerX` reads 35 a full frame *before* the state changes to `$03`, so
player 2 can simply mirror it into the other lane and inherit the same
mechanism. Verified at three slots: 35 gives -35 (70 apart), 60 gives -60 (120),
and 4 -- too near the centre to mirror usefully -- falls back to the symmetric
pair (64 apart).

**Qualifying** has no result to go on, and the stock game just centres the car,
which with two cars means both in the same place. It is now placed
symmetrically, one car per lane at +-32: 64 apart, outside the collision box,
well inside the road edge at 59.

Verified: **0 frames inside the collision box in the first 300 frames of a
session**, where before they started in contact.

### Both recordings are now stale

This moves *player 1's* start position, so run-01 and run-02 no longer replay
the race they recorded. run-01 still grades as baseline and run-02 diverges --
the documented desync rule, not a regression. They remain useful as liveness
checks and nothing more. `PP2_GRID_FORCE_RACE` is kept as a test switch, since
neither recording reaches a real race any more and the mirror branch would
otherwise be unexercisable.

## Correction: the lap starts at the banner, not at the driving state

**Confirmed live.** The previous entry placed the cars on entry to state `$02`.
That is where *driving* starts, not where the lap starts. The banner run is
state `$10`, and the car is **already rolling through it**:

    f685  state $04 -> $10   PlayerX=0    P1spd=0     banner begins
    f775  state $10          PlayerX=0    P1spd=77    still centred, rolling
    f781  state $10 -> $02   PlayerX=-32  P2=32       snapped apart here

So both cars sat in the centre for the whole banner and jumped apart the instant
`$02` arrived. Setup now happens on entry to `$10` or `$11`, before player 1 has
moved at all.

### And a claim from the previous entry was wrong

It said player 1's race grid slot "reads 35 a full frame before the state
changes", and concluded the slot could be read early. That was true only of the
single frame immediately before `$03`. Measured across the whole of state `$11`,
`PlayerX` reads **44** -- a leftover from the previous lap -- and only becomes
the real slot `35` as `$03` begins. Sampling one frame either side of a
transition says nothing about the period leading up to it.

Placement is therefore split in two:

* `P2RaceInit` sets everything up at the banner, using the symmetric pair.
* `P2PlaceMirror` re-places **player 2 alone** at `$03`, once the slot exists,
  touching nothing else -- so it is safe to call into a running session.

Verified with `PP2_PLACE_ON_QUAL`, which fires the mirror at `$02` so it can be
exercised at all: slot 35 gives -35 (70 apart), -40 gives +40 (80 apart,
correctly crossing to the other side), and 6 -- too central -- falls back to
+-32. Zero frames inside the collision box in the first 300 of a session.

No recording reaches a race any longer, so that switch is the only way to test
the mirror branch and is kept deliberately.

## The race grid: qualifying position picks a row and a lane

**Decoded from rom:D1AD-D204.** The race start is not a fixed position. It is a
grid of rows of two, indexed by the qualifying position in `ram_00A6` (1-based):

    L_D1AD:
      LDY ram_00A6          qualifying position
      DEY / TYA / LSR A     (pos-1)/2  =  the grid ROW
      STA ram_00D6          -> player 1's track position high byte, i.e. how
      LDA #$64 / STA ram_00D5   far back down the grid the car starts
      LDY ObjSlotList,X
      JSR sub_CF47          x3 -- the enemy cars placed around it
    ...
      LDA ram_00A6 / AND #$01   (pos-1)&1  =  the LANE
      -> lateral $02 or $20, projected through sub_E676 at row $48 and
         turned into PlayerX by SBC RowCurveOffset,Y / SBC #$3F

So the qualifying position determines **both** how far back the car starts and
which of the two lanes it occupies, and the enemy cars fill the other slots.

### What this means for player 2

`P2PlaceMirror` mirrors player 1's lateral, which -- by accident rather than
design -- lands player 2 in **the other lane of player 1's own row**. That is a
legitimate grid slot and the two players cannot collide there, so it is closer
to correct than it looks. What it does *not* do is stop the enemy car that was
assigned to that slot from also being there.

A proper implementation needs, in order:

1. **Player 2 needs a qualifying time at all.** It has no lap timing today, so
   there is nothing to rank it by. This is the prerequisite for everything else.
2. A rank for player 2, and a rule that the two players cannot be given the same
   position -- otherwise both resolve to one slot.
3. Player 2 placed from its own position with the same row/lane arithmetic,
   setting its track position as well as its lateral, rather than mirroring.
4. **Suppression of the enemy car occupying player 2's slot**, which is the part
   that is actually missing right now rather than merely approximate.

Step 4 is worth doing on its own even before 1 to 3, since it removes a visible
overlap under the placement that already exists.

### Note on state $10

It is the rolling section BEFORE the starting line, which is why placing there
is right: the lap does not begin, or end, until the line is crossed.

## Variable-length band lists, and why the bytes were not the point

Player 2's bands no longer share one stride. Each list is sized to what that
band holds, with the object slot immediately after the road objects:

    band  1-7    $2600..$2645   road0, object, end                10 bytes
    band  8-11   $2646..$268D   road0, road1, car, object, end    18
    band  12     $268E..$269B   road0, road1, object, end         14

156 bytes against the 216 a uniform 18 would have cost, leaving 102 bytes of
headroom before player 2's variables at `$2702`.

**The saving was the lesser reason.** With a fixed stride the far bands had
**zeros** where their second road object would go, and MARIA reads a zero width
byte as end-of-list -- so an object slot at a fixed offset was unreachable in
exactly the seven bands that most need one. Verified by walking the lists as the
hardware does, header by header until the end marker: **all twelve object slots
are now reached, where seven were not.**

### Space is still the constraint

    blob 2618 + templates 270 = 2888 of the 2945 the free $FF run holds

57 bytes spare, and the object pass needs more than that. The obvious next
saving is `DLL_TEMPLATE`'s 102 bytes: it is a boot image copied once to $2500,
so it could be built by a loop rather than stored whole.

## Unrolled staging became two loops: 427 bytes back

Player 2's twelve unrolled band-staging blocks are now two loops -- one for the
far bands, one for the near -- over three one-byte tables.

They fit in one byte each because **every address involved shares a page**: the
stripe texture and the width table both sit in `$1F`, and all of player 2's
lists in `$26`. So a band costs three bytes of table rather than about sixty of
code. The order still matters, since the camera accumulator advances exactly
once per band, so the far loop runs first and the near loop continues from it.

    blob 2618 -> 2191, saving 427 bytes
    spare in the free run: 57 -> 484

Verified byte for byte: player 2's whole 156-byte list was dumped at six frames
from both builds and compared. **Identical throughout** -- which is the right
check for a refactor that must change nothing.

The same treatment is available for `road_stage_src` (~260 bytes unrolled) and
`p2_drive_src` if more room is needed.

## Audio for player 2: the allocator already exists

**Decoded from rom:DEF3.** `SoundStart` is not a two-channel poke -- it is a
**priority-based two-voice allocator**:

    scan voices 1 then 0 for a free one (SndVoiceId, $FF means free)
    if none is free:
        compare dat_E1CB[new sound] against dat_E1CB[voice 1's current]
        steal voice 1 if the new sound ranks at least as high
        otherwise compare against voice 0 and steal that
        otherwise drop the new sound entirely

So the game already arbitrates more logical sounds than it has voices, through a
priority table indexed by sound id. Player 2's engine would be another sound id
with a chosen priority rather than a new mixer.

That does not remove the hard limit -- two voices between two engines and the
effects -- but it does mean the work is choosing priorities, not building
arbitration. The likely shape is that each engine outranks the other player's
effects but yields to its own, so a crash still cuts through.

## Curve drift for player 2

Player 2 tracked the road as though on rails -- curves did not push it at all,
while player 1 drifts outward.

Player 1's rule, at rom:C1D3 and rom:C4FE:

    rate = driftTable[SegCurve + 5][Speed >> 5]     negated when index >= 6
    accumulate that rate ONCE PER SPEED THRESHOLD in dat_B4F8 it exceeds
    divide by four with sign extension, and add to PlayerX

The per-threshold accumulation is the part that matters: it is what makes the
push grow with speed rather than being a fixed amount per curve.

The engine keeps the table as eleven pointers (`dat_AA24`/`dat_AB24`) to rows of
eight. Following one needs a zero-page pair, and the engine's `$40`/`$41` belong
to the object emitter, which RoadTail has no business borrowing -- so the rows
are dereferenced **at build time** and laid out flat, 88 bytes indexed by
`(curve index * 8) + (Speed >> 5)`. Curve index 5, a straight, is all zeros; the
rows grow with curvature and speed band and are symmetric about the straight.

Omitted deliberately: player 1 adds `RoadCurve` to the rate before scaling, and
that is its smoothed visual curvature, which player 2 has no equivalent of. Only
the segment term is used -- the dominant one, and the same source player 1's own
`LateralVel` comes from.

Verified with the throttle held and the stick untouched: **493 straight frames
with zero lateral movement, 2506 curve frames with 904 units of movement, and
zero frames pushed the wrong way.**

## Player 1's far band lists, and a second object attempt

**Mapped for the first time.** Player 1's far band lists are uniform: the road
at +00, then **eight object slots at +04..+20**, then the end marker at +24. The
near bands run +08..+1C, because their second road object sits at +04 -- so
reading a near band as though it were far would take road1 for an object.

    $2300 $2326 $234C $2372 $2398 $23BE | $2400 $2426 $244C $246E $2490 $24B2 $24D4

Thirteen bands across **two pages**, unevenly spaced. Absolute-indexed
addressing therefore needs one pass per page, with each band carrying its offset
within its page.

**There is no free zero-page pair** to avoid that with an indirect pointer.
`$02..$1F` are hardware registers rather than RAM, and scanning the disassembly
for unreferenced zero page is misleading in any case: it cannot see indexed
arrays, such as the one `STA ram_004E,X` fills across `$7E..$9B`.

**And the loop-back branch does not reach.** A band's body is far longer than
128 bytes, so each pass has to close with a jump, with the branch only skipping
it.

The pass assembles and is believed correct, but:

    blob 2401 -> 2824, so the object pass costs 423 bytes
    total 3094 against the 2945 available: 149 OVER

`patches/splitscreen.py` is restored to checkpoint 42 and verified to rebuild
byte-identical. Two savings are identified and are sufficient together:

1. `road_stage_src` -- 13 unrolled bands, about 260 bytes -- to loops, the same
   treatment that took 427 bytes off `p2_stage_src`. Worth about 126, and it
   needs three loops rather than two because player 1's band addresses straddle
   `$23` and `$24` in the same way.
2. The object pass duplicates its entire copy and x arithmetic once per page.
   Fetching the four object bytes and player 1's road x into scratch in the
   page-specific part, then sharing the map, arithmetic and write, is worth
   about 80.

## The DLI path has about two scanlines of slack, and loops are not free there

`road_stage_src` was converted to three loops to free space for the object pass.
It saves 87 bytes, the code is correct, **and it hangs the machine.**

The conversion checks out every way it can be checked short of running: the
generated assembly was printed and read instruction by instruction; the band
addresses and page split were dumped and are right ($2300 for bands 0-5, $2400
for 6-12, every offset within $00..$DF); and measured against the formula the
road headers must satisfy, the loop version matched **better** than the build it
replaces -- 140 mismatches against 3744, the residue in both being within-frame
drift between when staging runs and when the sample is taken.

But from f1500 the clock sits at 261, speed 160, segment 4, position 461 and
never moves again, while the display keeps drawing. That is the 6502 stuck
inside the DLI chain, not a desynced recording.

**Headroom, measured.** `PP2_BURN` adds WSYNCs to MirrorStage. One or two extra
scanlines still reach state `$10` at f6000 exactly as the shipped build does;
four changes behaviour. So there are roughly two scanlines of slack, and three
loops at about 15 cycles a band over 13 bands is about 1.8 -- right on the edge.

**Not proven.** The burn test degrades gracefully where this freezes hard, so
the cause may be something else entirely. Bisecting one loop at a time is the
next step, and worth doing before trusting the cycle explanation.

### What this changes about the space hunt

`MirrorStage` runs inside a beam-synchronised interrupt, so **trading code size
for cycles is not free there**, the way it appeared to be when `p2_stage_src`
was converted. That conversion added loop overhead too and survived -- which now
looks like it spent most of the remaining slack rather than being free. Further
savings should come from data, or from code outside the DLI, not from turning
more unrolled DLI code into loops.

## 931 bytes of the base ROM are dead, and provably so

The bypassed injection is reclaimable. `RoadTail` is entered at rom:ED9D and
leaves with `JMP $F143`, so the whole of `DLI_InjectRowCurveX` and its thirty
unrolled per-row writes -- **$EDA0..$F142, 931 bytes** -- is unreachable.

Two independent checks. Every label inside the range is referenced only from
within it, nothing external. And filling all 931 bytes with `$FF` left the state
log **byte-identical over 7000 frames of both recordings**. That is proof rather
than inference, which matters, because a scan for *other* dead code found ten
subroutines with no recorded xref that are almost certainly reached through the
game's state dispatch -- "no xref" only means the disassembler could not trace
it. Those were left alone.

The four templates now live there, handing their 270 bytes in the `$F3FF` run
back to the code blob, and verified neutral: state logs byte-identical to the
previous build on both recordings. Their expect lists are the real stock bytes
rather than `$FF`, so a ROM whose injection differs still fails loudly.

    code:      $F400..$FD60, 543 bytes spare before $FF7F
    templates: 270 of the reclaimed 931, 661 spare there

## Objects: the constraint was never space, it was cycles

With the space problem solved the object pass fits -- and still fails. The game
stalls and **zero objects are drawn**.

`sub_E3CD` is a **linear search of up to 78 iterations**, run once per object,
inside a DLI with about two scanlines of slack -- roughly 250 cycles. Scanning
thirteen bands for their first non-empty slot costs about a thousand more on its
own. The pass is an order of magnitude over budget, and no amount of reclaimed
ROM changes that.

Two fixes, and the next attempt probably wants both:

* **Replace the search with a lookup.** Z runs 0..1300, so a table indexed
  directly below 256 and by `(Z-256)>>3` above is 387 bytes -- which the
  reclaimed region has room for -- and turns hundreds of cycles per object into
  about ten.
* **Split the pass across frames**, as the walk already is, a few bands each,
  cutting the per-frame cost four or five times.

This also reframes the earlier `road_stage_src` hang: that was read as *possibly*
cycles, and this makes the cycle explanation much more likely, since the same
DLI path is demonstrably running with almost no margin.

## Objects reach player 2's view, and still stall the game

Two fixes since the last attempt, both of which worked:

* **The Z-to-row search became a lookup.** `sub_E3CD` walks up to 78 rows per
  object. The table is 416 bytes -- indexed by Z directly below 256 and by
  `(Z-256)>>3` above, since distances are a unit or two apart at the bumper and
  fifty apart at the horizon, so one stride cannot serve both. It lives in the
  reclaimed injection at `$EED0`/`$EFD0` rather than the code blob.
* **The pass moved from `MirrorStage` to the `RoadTail` path.** MirrorStage has
  about two scanlines of slack; RoadTail carries the walk, which alone costs
  thousands of cycles. Putting the pass in MirrorStage is why the previous
  attempt drew nothing at all -- it never had time to run.

Objects now appear in player 2's view. The game still stalls. Isolated with
`PP2_NO_OBJECTS` on the same build: **objects off gives the usual 101 distinct
clock values, objects on gives 3.** So the fault is in the pass itself, not the
lookup, the relocation, or the reclaimed space.

### The clue to follow next

**All twelve destination slots are occupied on 100% of frames.** Player 1 draws
only four to nine objects at a time, so most source bands should find nothing
and most destinations should stay parked. Either the empty test is not matching,
or the mapping returns a destination where it should reject.

The first thing to check is the start offset: a far band's first object slot is
`+04`, a near band's is `+08`, because the near bands have their second road
object at `+04`. If that start is ever taken from the wrong entry, a near band's
road1 reads as an object and *every* band finds a hit -- which would produce
exactly the 12 of 12 observed.

## Why copying objects corrupts: graphics pages are band-relative

The object pass's fault is structural, not a coding slip, and it was narrowed in
three steps.

**The per-band end offset was wrong.** Near bands end at `+20` and far bands at
`+24`, measured live -- so scanning every band to `+24` read the byte past a near
band's end marker, which is the next band's road width and never `$A1`. All five
near bands reported a spurious object every frame. That took 12 destinations of
12 down to 11, and the game still stalled.

**Bounding the destination index changed nothing**, ruling out an out-of-range
table read.

**Disabling only the WRITES, keeping the scan and mapping, restored the camera
gap** -- 5015, 11879, 14048 where it had collapsed to 0. So the copy is the
corrupter.

### The reason

rom:E7A9 writes an object's graphics **high byte from `ram_0046`, then adds 6**:

    LDA ram_0046 / STA (ptr),Y / CLC / ADC #$06 / STA ram_0046

The page is allocated as objects are emitted, stepping **six pages per band**,
because MARIA advances a zone's graphics one page per scanline and a band is six
lines. A sprite tall enough to cross bands is therefore written into *several*
of player 1's bands, with pages `P`, `P+6`, `P+12`.

Copying one such entry into one of player 2's bands draws a **six-line slice of
the sprite** with nothing above or below it -- the graphical corruption seen in
play -- and a garbage-width object overruns DMA, starving the CPU and stopping
the clock.

### What that means for the design

**Player 2's one-object-slot-per-band layout cannot represent a multi-band
sprite.** Two ways forward:

* Write a placed object into as many consecutive destination bands as it spans,
  stepping the page by 6 each time. That needs the sprite's height, which player
  1's emitter knows through its band loop but does not record anywhere the pass
  can read -- so it would have to be derived, or the source bands scanned for
  runs of the same object.
* Or place only single-band objects and leave the tall ones out, which for
  signs -- the class that is always tall -- means leaving out most of them.

The first is the real answer. It also explains why the earlier
read-from-the-object-arrays design was the better one: an object's height is a
property of the object, not of a display list entry.

### Correction: the band-span claim is not established

The entry above explains the copy corruption by objects being sliced across
bands with pages P, P+6, P+12. **That is not yet established.**

rom:E751 does loop an object across bands -- `LDY ram_0044 / DEY /
CPY ram_0045 / BPL L_E751` walks from one band index down to another, writing a
slice each time and stepping the page by 6. But a measurement of how many bands
objects actually span came back **100% single-band**, which contradicts it.

That measurement is the unreliable one: it identified a run by the object being
at the *same slot index* in consecutive bands, and the emitter advances each
band's write pointer independently through `(ram_0040),Y`, so one object can
occupy different slot indices in different bands. The run detection would miss
every real multi-band sprite.

So what is **proven** is narrower than the entry above claims:

* near bands end at `+20`, far bands at `+24` -- measured directly, and the
  scan must use a per-band end or it reads a phantom object in every near band;
* the **copy** is what corrupts, not the scan or the mapping -- disabling only
  the writes restored the camera gap;
* the destination index is not out of range -- bounding it changed nothing.

The *why* behind the copy is still open. Before building on the page theory it
needs a measurement that identifies an object across bands by something other
than slot index -- its graphics low byte and width, say, or by instrumenting
ram_0044/ram_0045 at rom:E751 directly.

## The other player's car, and why it worked where objects did not

Player 1's car now draws in player 2's view, and **run-01 and run-02 grade
exactly as baseline** -- no stall, no corruption, where every general-object
attempt broke something.

The reason is that **nothing is copied**. The distance *is* the camera gap,
exactly, and the lateral is a variable already held, so there are no
pre-rasterised slices to reproject and none of the band-relative page trouble
applies. That is what made it the right thing to build first.

* distance -> row -> band via the Z-to-row lookup (416 bytes in the reclaimed
  injection, since `sub_E3CD` is a search of up to 78 rows);
* the sprite from a **measured** per-band table -- sampling palette-6 objects
  across a run gave `$A3 $9D $97 $91 $8B` for bands 7-11 at eight bytes wide and
  `$91`/`$8B` at two bytes further out, all sharing the lean offsets, which is
  one car sliced across five bands plus a distant sprite;
* x is player 2's road at that band plus the lateral difference scaled by the
  camera's own ramp, reduced to a byte a band as `(3 + 6*band) * 1.775`;
* lean taken from player 1's own, guarded on its driving sprite.

Verified: at gap 91 it draws in band 8 -- Z is 102 there -- at x 33, page
`$9D10`, ahead and to the left of player 2's car. At gap 30 it moves to band 10,
Z 32. At a saturated gap, and at negative gaps, nothing is drawn.

### What this suggests for the general objects

The difference is not the projection, which was already solved. It is the
**source**: world state reprojected cleanly, where a display list entry carries
a band-relative page that does not survive being moved. That is the argument for
reading the 16-slot object arrays rather than player 1's lists -- an object's
position and type are properties of the object, its page is not.

## Both cars now appear in both views

The mirror of the previous entry is in: player 2's car draws in player 1's view.
run-01 and run-02 grade exactly as baseline.

It needed a slot in player 1's lists, and there is a free one. **The first object
slot of every band** -- `+04` on the far ones, `+08` on the near, which have
their second road object at `+04` -- **was never once filled by the game across
6800 frames**, while `+08`/`+0C` onwards and `+18` are in constant use. Being
first, it also draws behind the game's own objects, which is the right order for
a car further away.

Only one band is written per frame, so instead of parking all thirteen the band
used last frame is remembered and parked. Player 1's lists straddle two pages,
so that write branches rather than indexes.

Verified: drawn on 385 frames and **never once while the gap was positive** --
never while player 2 was behind, where player 1 could not see it. At gap -80 it
lands in band 8, where Z is 102, at x 85 with page `$9D10`: band 8's page plus
an upright lean.

**Not seen mid-race.** Under both recordings player 2 is parked, so the gap is
almost always positive and no racing frame has player 2 ahead. This direction is
verified by its numbers rather than by a picture, and a two-player recording
would settle it.

## Two faults from play: a RAM collision and the band slicing

**The corruption was a RAM collision, and a blunt one.** `P1_OC_LAST` was placed
at `$2720`, which is `P2_WALK` -- the other car's state was written directly on
top of the walk's scratch every frame. Moved to `$2740`, and a
`_check_p2_ram()` guard now sorts every one of player 2's regions and refuses to
build if any two overlap. That guard is the real fix; the address was only the
symptom.

**"A single wheel" was the band slicing, and it confirms the earlier theory.** A
car is five bands tall close up -- pages `$A3 $9D $97 $91 $8B` across bands 7 to
11, which is exactly how player 1's own car is drawn -- so writing one slice
drew a single six-line strip of it. Player 2's view now writes a slice into
every band from the base upward toward the horizon, each taking its own band's
page, stopping at band 7 so they stay inside the eight-byte sprite's range.

run-01 and run-02 grade at baseline, and the two-player recording grades
**HEALTHY** at 101 clock values.

### Still single-slice: player 1's view

The same change applied to player 1's view broke run-01 and run-02 down to 3
distinct clock values while leaving the two-player recording untouched, and
`PP2_NO_OTHERCAR` isolates it to the other-car code rather than to the staging
tables that moved in the same round. Not diagnosed. So **player 2's car will
still look like a wheel in player 1's view** until that is solved.

What is odd about it, and worth starting from: in run-01 and run-02 player 2 is
parked, so the gap is positive and player 1's pass should reject before drawing
anything at all. Something in that pass costs or corrupts even on the path where
it draws nothing.

## "Always on the left" was three bugs in one calculation

1. **The origin.** The offset was added to the road object's x, which is the
   road's **left edge**, so the car sat at the edge whatever the lateral said.
   Player 2's own car is drawn at x `$40`, dead centre, so the other car belongs
   at `$40` plus the difference between them.
2. **The multiply.** The shift-and-add used an **8-bit multiplicand**. It
   doubles every step, so it overflowed on the first shift and every scaled
   offset was wrong. Widened to 16 bits.
3. **The sign.** A positive lateral is a car to the **left**, while screen x
   grows to the right, so the offset must be applied *against* the difference.
   Applied with it, two cars on opposite sides of the road both drew to the
   left, one of them off the edge entirely -- at a difference of -64 the car
   landed at x 254.

Only the first was visible from the symptom; the other two were found by
checking the arithmetic against measured values rather than by looking again.

After all three, from the recording with the players on opposite sides:

    difference -64, band 7  ->  x 130    right of centre, correct
    difference -77, band 5  ->  x  99    further away, so nearer centre
    x over 665 drawn frames: 98..137, all on screen

All four recordings grade clean: run-01 and run-02 at baseline, both two-player
recordings HEALTHY at 101 clock values.

## Correction: a positive lateral is a car to the RIGHT

The note above saying a positive lateral puts the car to the LEFT is wrong, and
it inverted the other car in both views. The measurement that settles it:
player 1's own car sits at x 64 in every frame of a run -- it never moves. It is
the ROAD that moves, and the road goes LEFT as the lateral goes POSITIVE.

    lat   0 -> road x  12        lat +31 -> road x 246
    lat -63 -> road x  58        lat +45 -> road x 234
    lat -72 -> road x  64

A road to the left of a car fixed at centre means the car is to the RIGHT. So a
positive lateral is a car to the RIGHT, and a screen offset derived from a
lateral difference runs WITH that difference, not against it.

Worth stating why the earlier reading survived as long as it did: the origin and
the multiply were both wrong at the same time, and between them they pinned the
car to one side whatever the sign said. Fixing those two exposed the sign, and
only then could it be measured.

## Two more ways the other car landed on the wrong side

Neither is the sign, and both outlive a sign fix.

**An 8-bit HPOS cannot say "off the right edge."** The car is drawn from x 64,
so an offset of 121 gives 185, which MARIA renders as NEGATIVE and draws at the
LEFT. Both extremes come out on the left. The scaled offset is now clamped to
90, keeping x within -26..154: the low end lands in $A0..$FF and reads as the
negative it is, the high end stays on screen. Clamped rather than parked, so a
distant car pins to the edge of the view instead of vanishing from it.

**The difference itself overflowed.** Two signed laterals can be 208 apart --
one car in the left grass, the other in the right -- and that does not fit a
signed byte. `SBC` wrapped it and the sign flipped: a true -136 came back as
+120, and the car drew on the far side of the road from where it actually was.
Six frames of run-02, from f5180. On signed overflow the carry says which way
the true value went (set means it went negative), so the difference is pinned to
-127 or +127 and the clamp takes it to the edge from there.

This one matters more than its six frames suggest: it needs the two cars on
opposite sides of the road, which is exactly what a real two-player game does
and what a single-player recording almost never produces.

Both fixes were paid for out of dead weight rather than new space: `P2RoadOfs`
and `P1OcRoad`, 25 bytes of table holding each band's road-object offset, had
had no reader since the car was anchored to x 64; and player 1's pass stored the
finished offset and read it back twice when A already carried it, 9 bytes.

    verified: wrongside=0 and offscreen=0 in both views on all four recordings.
    run-02's player-1 view went from x 235, which wraps to the left, to x 154,
    pinned to the right edge.
    health: all four at 101 clock values, with run-01 at 1047@f1259 and run-02
    at 394@f5958 -- both exactly baseline.

## RoadTail has less slack than assumed: two JSRs break it

The two other-car passes carry an identical copy of the lateral-to-screen
multiply. Folding them into one `OcScale` subroutine is obviously right -- it
frees about 40 bytes and removes the duplication that let the sign be wrong in
two places at once. It also drops run-01 to 3 distinct clock values, with player
1's speed pinned at 0 by the collision penalty.

Disabling either pass restores it; inlining both restores it; so the two `JSR`s
together, about 24 cycles, are enough to break it. That contradicts the earlier
note that RoadTail "has far more" slack than MirrorStage's two scanlines -- at
this point in the path it does not. Not merged; the generator is kept in the
scratchpad as `with-ocscale.py`. Worth revisiting only alongside a real
measurement of what the path actually costs.

## Where the frame actually goes -- and how Motor Psycho and Fatal Run differ

Asked whether Motor Psycho or Fatal Run use a better structure for the same
kind of road. The answer turned out to be less about them than about this
game: PP2 is not short of CPU. About a quarter of every frame is spent
waiting, and it feels cramped because the idle time and the work are in
different places.

### Same instrument on all four

`tools/probe-render-survey.lua` counts per frame the display interrupts (reads
of the NMI vector), `WSYNC` writes, and the last `DPPH`/`DPPL`/`CTRL` written,
and dumps RAM for `tools/zones-bill.py`, which walks the lists and bills them
with `dmabudget.py`'s measured constants.

| | DLIs | WSYNCs | CTRL | DLL | zones | MARIA DMA |
|---|---|---|---|---|---|---|
| PP2 stock | 5 | 97 | `$40` | fixed `$2200` | 35, mostly 6-line | 21.7% |
| PP2 two-player | 5 | 17 | `$40` | fixed `$2500` | 34, mostly 6-line | 28.9% |
| Motor Psycho | 4-5 | 5 | `$50` | flips `$226C`/`$2383` | 57-80, mostly **2-line** | 18-31% |
| Fatal Run | 5 | 11 | `$50` | flips `$1F3F`/`$1E4C` | 51-60, mostly **2-line** | 27-30% |

MARIA's bill is about the same everywhere, so DMA is not the difference.

**The two 1990 games share one design.** Each road zone is two scanlines
holding one road object, drawn from a **pre-drawn road image in ROM**: the
graphics page steps down the screen while the width grows (Motor Psycho
`$9E66`->`$7B5E`, 1->20 bytes; Fatal Run `$5E00`->`$5A..`, 1->26 bytes), so a
zone's whole contribution is its x -- which is the curve. Stripes appear to be
the palette flipped 0/1 per zone, not different graphics. The sky and
mountains are character mode (`CTRL` bit 4, two-byte characters) whose
character strings point straight into ROM, so the backdrop costs the CPU
nothing to compose.

**And both double-buffer, at a variable rate.** The DLL flips between two
buffers when the back one is finished:

    Motor Psycho  frames between flips: 3:95 4:192 5:112 6:94 7:17  -> 13.4 updates/s
    Fatal Run     frames between flips: 2:193 3:171                  -> 24.3 updates/s

The spread is the tell: they flip when the CPU finishes, so their frame rate
falls wherever the work lands. They are not more efficient than PP2 -- PP2
redraws its road at 60 -- they simply have no deadline.

### PP2 is already a two-rate engine

`tools/probe-pcprof.lua` is a sampling profiler that needs no timer: MARIA
reads the DLL at every zone boundary, so a read tap there fires about 35 times
a frame at even beam positions with the 6502 halted, and its PC is a fair
sample. The hottest code in both builds is not work:

    $EA28  LDA $B8 / BNE $EA28     stock 34.8% of samples, two-player 24.1%
    $E709  LDA $E5 / BNE $E709     two-player 6.4%

Both run at SP `$1FD`, one call below the main loop's `$1FF` -- **main-loop
code, not interrupt code** (the vblank spin, by contrast, sits at `$1F1-$1F5`).

* `$B8` is a **six-frame counter**, written 0..5 by the NMI at rom:F14A.
  `$EA28` is the true entry of `StageRowCurveForDLI` and holds until it wraps
  to 0. That is why the main loop kept "finding the tick six ahead".
* `$E5` is set to `$FF` by a display interrupt at rom:ED26 and cleared at
  rom:F150 in vblank, so `$E709` waits for vblank before rebuilding the
  object display lists at `$E6D7`.

`tools/probe-mainloop-rates.lua` confirms the rate: the row staging and the
object rebuild each run **once every 6.00 frames** in the two-player build
(6.42 in stock, which occasionally misses a cycle). So the road and physics
tick at 60 in the interrupt chain, and everything in the main loop -- objects
included -- ticks at 10.

`tools/probe-spins.lua` puts cycles on every wait (6 cycles an iteration, 9
for the tick spin):

| mean cycles/frame | stage wait | object wait | vblank spin | tick spin | **idle** |
|---|---|---|---|---|---|
| PP2 stock, run-01 | 8,026 | 1 | 1,116 | 821 | **~10,000 (33%)** |
| two-player, 0922-2037 | 4,244 | 1,086 | 1,832 | 1 | **~7,200 (24%)** |
| two-player, run-01 | 2,367 | 2,731 | 2,221 | 642 | **~8,000 (27%)** |

The two-player build has *less* idle than stock but not by much, because
bypassing the 97-`WSYNC` row injection freed more than player 2 has added.
None of the zero-idle frames that would signal an overrun appear in either.

### Why it felt cramped anyway

Everything added for player 2 so far lives in the interrupt chain --
`MirrorStage` with its two scanlines, `RoadTail` inside `DLI_ED4F` -- where a
deadline is a scanline, not a frame. The two failures that looked like "out of
CPU" were both that: the general object pass drew nothing from `MirrorStage`,
and two `JSR`s in `RoadTail` (checkpoint 54's dead end) stopped player 1. The
main loop sat beside both with roughly **25,000 cycles of slack per 10 Hz
cycle** and no scanline deadline.

### The tear constraint that comes with the main loop

`tools/probe-beam.lua` derives the beam from emulated time, anchored to the
instant the `$DB8E` spin falls through (VBLANK going high): the game's own
object rebuild starts **17.5 lines after vblank begins and runs 42.8 lines**,
finishing about 40 lines into the next visible frame. That is safe for player
1's view at the bottom. It is not automatically safe for player 2's view on
top: a player-2 rebuild appended after it would race the beam through player
2's own bands. It needs either to run while the beam is in player 1's half, or
a second copy of player 2's lists to write into.

### ROM: the blob is full, and the zeros are mostly not free

The code blob ends at `$FF74` against a free run ending `$FF7F`: **11 bytes**.
Of 2,316 bytes in zero runs of 16+, a read tap (`tools/probe-zero-reads.lua`)
first reported every one read -- the 7800 BIOS reads the whole cartridge at
boot to check its signature. Counting only from frame 300, **1,056 are never
read over four recordings**, 486 of them in 19 stretches of 16+ (largest 41,
at page edges in `$86xx-$8Axx`). Those recordings never show attract mode, the
other tracks, results or every crash frame, so these are candidates to prove,
not space to spend.

## The attract demo, and what cutting it would free

With no input the game alternates the title and track map (state `$00`,
~1,400 frames) with a computer-driven race (state `$01`, ~1,414 frames), on
whichever track is selected. State `$01` appears in no real game -- real play
runs `00 06 04 10 02` (qualifying) `0B .. 11 03` (the race) `0C 09` -- so
"what the demo uses" is exactly "what is read in state `$01`".

### How it is built: the real race, with the stick replaced

* **Launch**, rom:D272-D298, inside the title handler: when the idle timer
  (`sub_DA5C`, a countdown in `$BF/$C0`) expires it sets state 1, loads the
  track, picks a grid slot from the frame counter, and calls the ordinary race
  start `$D0B9` and race init `$D8AC`.
* **Handler**, rom:D2D3: stick moved -> `$D888` (back to title, shared by four
  callers); otherwise the race tick. Its last three bytes, `$D302: JMP $D701`,
  are the race-tick jump that states `$02` and `$03` branch to as well.
* **The autopilot is 28 bytes.** rom:C3E1 is the player's steering-input
  routine, called once, from `$C1D3`. In the demo it decides direction from the
  car's lateral position (`$D1`, a +/-10 dead band) at `$C3E7-$C3FC`; in play
  it reads the stick at `$C447`. Both then share the steering application at
  `$C3FD-$C43D` -- the stick path branches back into it at `$C460`, `$C465` and
  `$C478`. An earlier reading here took all of `$C3E1-$C446` for the
  autopilot; those branches show it is not.
* Six small `CMP #$01` tests elsewhere (`$C2D4` countdown skip, `$C43E` clock,
  `$C705`, `$CBDD`, `$DF3D` sound, and our own `$F50C`).

### What it would free

| where | bytes | how |
|---|---|---|
| `$D275-$D298` launch | 36 | `$D272: JMP $D299`, so an expired timer keeps the title up |
| `$D2D3-$D301` handler | 47 | never entered; keep `$D302` |
| `$C3E1-$C3FC` demo steering | 28 | retarget `$C1D3`'s `JSR` to `$C447` |
| `$C43F-$C446` demo clock test | 8 | `RTS` at `$C43E` |
| our blob, `$F50C` test | 6 | drop from `splitscreen.py` |

**About 120 bytes of original ROM in four pieces (8-47), and 6 in the code
blob.** Small, because the demo is the race engine; the other `CMP #$01` tests
save three to six bytes each and need re-routing, so they are not worth it.

### What the coverage said, and why most of it is not demo code

`tools/probe-state-coverage.lua` taps every read of the cart (CPU and MARIA
alike), armed only once the cart's reset code at `$D205` runs so the BIOS's
signature scan is excluded, and tags each byte with `$9D` **at the moment of
the read**. Tagging by the state at frame end, the first version, filed the
demo's launch code under the title. `tools/state-coverage-diff.py` subtracts.

Over sixteen runs -- every recording plus the demo on all four tracks (held by
writing `TrackIndex`, `$C4`, during the title) -- **2,108 bytes are read only
in the demo**: 747 in code, 1,361 in graphics and tables. Almost none of it is
demo logic:

* `$D0C1-$D204`, ~300 bytes, is the race start, `$D0B9`. Its other caller,
  `$D655`, is the real race start after qualifying -- which **no recording
  reaches on the two-player build**: they all go `02 0D 0A 00` and never see
  state `$03`. That gap hides every race-only path.
* `$CAEE-$CB4F` and the like are object and traffic paths (kind-2 markers,
  respawning) that the demo reaches by driving further, on more tracks.
* The graphics -- one 8-byte, ~30-line sprite in pages `$8A-$A3` among them --
  are objects no recording happened to draw.

A four-track recording that qualifies and reaches the race on each track would
shrink the list to what is genuinely the demo's.

### Confirmed with a four-track recording: ~120 bytes, and nothing else

`run-03.inp` (retail ROM, 413 s) qualifies on all four tracks and races on
tracks 0 and 1. Re-running the comparison on retail -- the demo on all four
tracks against `run-01`, `run-02` and `run-03`, with real play on the
two-player build added to "used elsewhere" -- takes the demo-only set from
2,108 bytes to **235**, and every remaining piece is identified:

| range | bytes | what | cut? |
|---|---|---|---|
| `$D276-$D298` | 35 | demo launch | yes |
| `$D2D3-$D2F9` (two pieces) | 31 | demo handler | yes, whole `$D2D3-$D301` |
| `$C3E8-$C3FC`, `$C41C-$C41F`, `$C445` | 26 | autopilot decision, demo clock store | yes, as `$C3E1-$C3FC` and `$C43F-$C446` |
| `$D0E0-$D0E6`, `$D10E` | 8 | grid-slot parity in the shared race start | no -- real play with an even grid slot |
| `$E5B8-$E5BF`, `$C31C`, `$E1CB` | 10 | object offset path, speed clamp, one sound-table byte | no -- shared |
| pages `$87-$95`, `$A2`, offsets `$59-$5F` | 125 | the **water splash** beside the car on a puddle (caught being drawn at f5375, track 2) | no -- real play hits puddles |

So the earlier estimate stands: **~120 bytes of original ROM in four pieces
(36, 47, 28, 8), plus 6 in the code blob.** The coverage gap was the whole of
the difference.

### Qualifying cut-offs are shared by every track -- as the manual says

On tracks 2 and 3 of `run-03` the line appeared not to register. It did: the
game entered state `$0B` (`QualifyingPosition`, rom:D3F7) and six frames later
returned to `$02`. The handler compares the lap timer `$BE:$BD:$BC` (BCD)
against eight thresholds at `$DBA0`/`$DBA8` -- 58.50 for pole, then 60, 62,
64, 66, 68, 70 and 73.00 for eighth -- **indexed by position only, not by
track**. A lap that beats none of them does not count, and qualifying runs on
until its clock expires. `run-03`'s laps: 57.45 (track 0, pole), 68.00
(track 1, 6th), 79.79 and 82.62 (tracks 2 and 3, over the cut-off). This is
the manual's rule -- 120 seconds to drive, 73 to qualify -- not a bug.

The game's timer runs about 1.6x real time: track 2's 79.79 took ~49 real
seconds (2,946 frames), track 0's 57.45 about 36. So 73.00 is roughly 45 real
seconds a lap, which is what makes the longer tracks hard.

### Correction: the zero runs are not free space

The survey above counted 1,056 zero bytes never read after boot, 486 of them in
19 stretches of 16+, and called them candidates. With the coverage from the
attract work -- 39 runs, including `run-03` on all four tracks and the demo on
all four -- **68 of the 2,316 zero bytes are never read, and none lie in a
stretch of 16 or more** (94 if the demo is cut). The earlier figure was four
recordings not showing enough of the game.

These files arm at the cart's reset code rather than at frame 300, so a boot
pass could in principle inflate them; none does -- no zero byte is read only
during boot (state `$55`). The zeros are read in play: qualifying (42 bytes
read there and nowhere else), race start (14), the demo (26), the race (4).
They are transparent pixels and zero table entries, as they looked.

So there is no hidden space in the fill. Freeing ROM means removing or moving
something that is used: the attract demo (~120 bytes in four pieces), or the
work-relocation options above that retire the 416-byte Z-to-row tables and
duplicated code.

## Player 2's walk and other-car passes move to the main loop

Checkpoint 55. Player 1's physics turns out to run in the main loop, once per
six-frame cycle -- measured by the phase of the `$B8` counter on which each
byte changes: speed and track position only ever change at phase 2, lateral
position only at phase 3. Everything built for player 2 ran every frame inside
display interrupts instead. This is stage A of putting it beside player 1's.

* **The walk** now runs from the race tick at rom:D713, which called player
  1's walk (`sub_E93D`) and now calls `P2Tick`: that walk, then player 2's
  in full. The race tick runs in states `$02`/`$10` and `$03`/`$11` (they
  share handlers), exactly where player 1's walk runs. Its input is a copy of
  `P2_TRACK_*` taken with a re-read check, because the drive that moves those
  bytes still runs in an interrupt that can land between two reads.
* **The other-car passes** run at the object rebuild, rom:E70D, once vblank
  has begun. Player 2's view is written first, while the beam draws nothing,
  because that view is on top. Player 1's is written *after* the game's
  rebuild (`$E6D7`), which rewrites player 1's lists: the first build wrote
  it before, the rebuild wiped it every cycle, and player 2's car vanished
  from player 1's view. After, it is still long before the beam reaches the
  bottom view.
* **One multiply.** With both passes out of the interrupt, a `JSR` is free,
  and the duplicated multiply became one routine -- the change that stopped
  player 1 when tried at checkpoint 54.

Verified:

    walk        1,197 walks recomputed independently from their snapshots
                (tools/walk-check.py): 0 mismatches
    other car   wrongside=0, offscreen=0 in both views; the player-1-view
                slot never found wiped between updates
    health      run-01 and run-02 exactly baseline; both two-player runs
                HEALTHY at 101 clock values
    main loop   still one pass every 6.00 frames

And what it bought, on `test-pp2-2p-0922-2037`:

    player 2's work inside RoadTail, per frame    63.7 -> 5.7 scanlines (median)
    spare time in the interrupt chain, p10        774 -> 3,906 cycles
    spare time in the interrupt chain, median     1,116 -> 4,380 cycles
    code blob spare                               11 -> 37 bytes

Player 2's walk had been taking about a quarter of every frame inside an
interrupt. It now costs the main loop about 1,150 cycles a frame, averaged,
out of the idle it was already spending in the stage wait.

A wrong turn worth recording: the first independent check reported 28 and 49
mismatched walks, each wrong output equal to the right one for the previous
snapshot. The fault was the checker -- it added the low byte's carry into the
starting distance twice -- not the ROM. A trace of every walk's entry, snapshot
and output showed the ROM's outputs changing exactly when a sample crossed into
a new segment, which is all the walk depends on.

Still in the interrupt: the drive, drift, gap and collision. They move next,
onto player 1's tick and player 1's rules -- player 2 currently applies the
accel-table step, braking and drag every frame where player 1 applies its
step once per cycle, which is a real difference in how the two cars respond.

## Correction: the two laterals run in opposite directions

Measured with `tools/probe-lateral-sign.lua`, each view's road x against its
own lateral, over `test-pp2-2p-0922-2037`:

    player 1   PlayerX  -80..-65 -> road x  60     player 2   P2_LATERAL -48..-33 -> road x -48
               PlayerX   48.. 63 -> road x -26                P2_LATERAL  96..111 -> road x  97

Player 1's road moves left as `PlayerX` rises, so positive is right of centre
(as found at checkpoint 54). **Player 2's road moves right as `P2_LATERAL`
rises, so for player 2 positive is LEFT.** Player 2's steering, lean and camera
agree with each other, which is why it drives correctly in its own view; the
trouble was every place the two were combined.

* **Collision** tested `|P2_LATERAL - PlayerX|`, firing when the cars were at
  mirror-image positions and missing real overlaps away from the centre line.
  It now tests `|P2_LATERAL + PlayerX|`; the sum's sign still picks the push.
* **The other car**, in both views, was placed from `P1 - P2` where the real
  separation is `P1 + P2`, so cars on opposite sides collapsed toward the
  middle of each other's view. Both passes now difference against `-P2`,
  still by subtraction so the overflow saturation holds.
* **Player 2's curve drift** added player 1's rate in player 1's sign, which
  pushed player 2 into curves; it is now subtracted.

**The earlier checks of the other car were circular.** Checkpoints 53-55
reported `wrongside=0`, but the probe computed the expected side with the same
`P1 - P2` the code used, so it could only ever agree. This time the check is
the screen: `tools/probe-sign-shots.lua` picks frames where the cars are close
on opposite sides of the road and frames of collision, and screenshots them.
Every one reads right -- player 2's car left of player 1's when it should be,
player 1's car at the left edge of player 2's view when it is left of it, and
a collision with the two cars visibly side by side.

Health unchanged: run-01 and run-02 at baseline, both two-player runs HEALTHY.

## Player 2's drive runs on player 1's tick, by player 1's rules

Checkpoint 57, stage B. Player 1's per-tick physics, read from the ROM:

| | per tick | where |
|---|---|---|
| gas held | + `dat_C3C1[(Speed>>4)+Gear]`, saturating at 0 and 255 | rom:C2F6 |
| gas released | -5, to 0 below 10 | rom:C340 |
| brake | -10, to 0 below 20 | rom:C352 |
| off the road | -Speed>>6 at \|x\| >= `$3B` | rom:C20D, `SkidDrag` |
| steering | ((stick +-7 + drift rate) x speed thresholds cleared) / 4 | rom:C4F7 |
| advance | Speed>>1, low bit dropped | rom:C498 |

`$DA` is the stick term, -7/0/+7, stepping 7 a tick toward the held side and
straight back to 0 when centred; its only writers are the stick routine and two
race-start clears. Earlier notes here called it `RoadCurve` and `LatVel`; it is
neither. The eight speed thresholds at `dat_B4F8` are 128 112 96 80 60 40 15 1.

The earlier "every way the car loses speed" table gave these amounts per frame.
They are per tick -- once per six frames -- which is also why the old per-frame
player 2 could match player 1's top speed and advance and still handle
differently: it applied the accel step six times as often, braked about five
times as hard, never coasted down, and steered at a fixed 1 unit a frame
against player 1's 14 a tick at full speed.

Player 2's drive now runs from `P2Tick`, straight after player 1's walk, and
applies these rules to its own state. Two departures, both deliberate: the
start gate keeps player 2's bleed-and-hold rather than player 1's clock-zero
path (which below speed 30 zeroes speed and then subtracts 15, giving 241);
and the collision push is 6 a tick where it was 1 a frame. `P2Frame` in
`RoadTail` keeps only the stripe scroll, which is per-frame for player 1 too.

### Verified by driving both cars identically

`tools/probe-drive-script.lua` drives both players from a script -- no
recording, both given the same inputs -- and `tools/physics-rules-compare.py`
compares the two cars' per-tick rules key by key: speed change keyed by
(speed, gear, pedal), lateral change keyed by (speed, stick), only on cycles
where the inputs held, both cars were on tarmac on a straight, and the race
clock ran. Collision off for the comparison, so neither car shoves the other.

    checkpoint 56 (per-frame player 2)   1 of 30 speed keys agree
    checkpoint 57                        23 of 23 speed keys, 23 of 23 steering keys

The unfiltered first pass also showed the drift now matches: both cars carried
to -72 on the same curve, where the old player 2 went to +136.

Also: walk 1,197/1,197 exact; health at baseline; player 2's work inside
`RoadTail` 1.0 scanline a frame (63.7 before stage A); interrupt-side spare in
the worst 10% of frames 4,632 cycles (774 before).

Not yet ported: player 1's cornering skid (`SkidCheck`, rom:C269), its crash,
and its sign collisions. Existing two-player recordings desync on this build
-- their player-2 inputs were made for the old steering -- so it needs driving
live.

## Each player's car drawn as the game draws a rival

Checkpoint 58. The other player's car used to be one six-line slice at a scale
of our own -- a black blob or a lone wheel, placed without the road's curve
between the cars. It is now drawn by the game's own rival-car rules.

### How the game draws a rival car

* `sub_E286` (called from the race tick at rom:D716, straight after player 1's
  walk) builds a **drawable list**: entry 0 is the player's car (`sub_E364`),
  then one entry per visible world object (`sub_E3E0` row, `sub_E475` height,
  `sub_E461` slot class, `sub_E54B`/`sub_E676` x, `sub_E4F1` viewing-angle
  sprite, `sub_E5C7` palette/width, `sub_E60F` hide rules). The count is `$DD`;
  the per-entry arrays are `$1A94` nearest row, `$1AA9` farthest row, `$1AD3`
  sprite low byte, `$1ABE` sprite page, `$1BEA` palette/width, `$1AE8` x,
  `$1A7F` slot class.
* After vblank `sub_E6D7` parks six slots in every band and the emitter
  (rom:E713-E7C9) writes each entry into **every band it spans**, one header a
  band, the sprite page starting at `page - $9DC3[band] + row` and stepping 6 a
  band. Cars are slot class 4, which takes the slots at +4..+20: five a band.
* **x** = hi(|c| x (row+4)) with c's sign, + `RowCurveOffset[row]` + `$4F`,
  carry kept between the two adds. c is a lateral coefficient, `$E80F`/`$A8A1`,
  linear at about 9.6 per lane index about lane `$16`; `$23`/`$24` are the
  roadside positions signs use. The multiplier is row + 4 -- `INC $4B` before
  the loop -- which the first model had as row + 3.
* **Sprite**: size class `dat_BA7E[row]` (0-9); height `dat_ACCA`, width
  `dat_ABCA`; for sizes 0-5 one of **five viewing angles**, chosen from
  (x + lane + $1F)/8 - $0E plus the road's slope at the row, through the
  pointer tables at `$A295`/`$A29F`.

`tools/rival-car-model.py` reproduces all of that from state captured by
`tools/probe-object-list.lua`: rows, x, sprite, palette/width and slot class
match on **144 of 146** rival cars in run-03 (the two misses are the checker
mis-indexing the list past a sign, not the maths).

### Calibration: lateral units against the coefficient

Solving, at each of 600 list builds, for the c that would put an object exactly
under player 1's car (drawn at x 64): **c = 3.38 x PlayerX - 46** at the
nearest rows, residual under 2 px. The slope is the camera's (the lateral ramp
is ~3.59 a unit); the -46 is the fixed offset between the two sprites' anchors.
So a car at lateral w (player 1's terms) has coefficient 3.38w - 46, kept as a
128-byte table of round(3.38n/2).

### What the ROM now does

* **Player 1's view**: `RivalCars` replaces the race tick's call to `sub_E286`,
  makes it, then appends player 2's car: distance -GAP, lateral -P2_LATERAL,
  class 4. The game's own emitter draws it.
* **Player 2's view**: player 1's car is projected the same way, with player
  2's road in place of `RowCurveOffset` -- the walk's `P2_BANDX[b]` less its
  per-band base, plus player 2's camera shift at that band -- staged in
  `P2E_*`, and emitted by `P2ObjCommit` at vblank band by band, as the game's
  emitter does.
* The row search is the game's own `sub_E3CD`, so the 416 bytes of Z-to-row
  tables are gone. The old passes, their multiply and their tables are gone.
  `OcCoef`, `OcRow` and `OcSprite` are assembled on their own in the reclaimed
  injection; `RivalCars` and `OcMul` stay in the blob.

`tools/rival-entries-check.py` recomputes both staged cars from state captured
by `tools/probe-rival-entries.lua`: **165/165** entries for player 2's car in
player 1's view, **167, 116 and 19 of 19** for player 1's car in player 2's
view over three recordings, all matching the model.

ROM: blob spare 14 -> 56 bytes; the reclaimed injection holds 141 bytes of
tables and 233 of code where the 416-byte tables were, 42 spare.

### The mangling that the first build caused

The first build (RC1) shredded player 2's whole view. Bisection showed the
emit code's *presence*, not its execution, correlated with it -- which pointed
at layout, and was wrong: `MirrorStage` took the same time in both builds. The
answer was in the data: the first header of every band had its graphics page
zeroed. `P2ObjCommit` can run before anything has been staged -- the reset
switch's path (rom:D7A9) runs the object rebuild without passing the list hook,
and so, in run-01, did the start of qualifying -- with `P2E_TOP` still 0 from
the RAM clear rather than the `$FF` that means nothing. Row 0 put the emit in
band 0, its index wrapped to `$FF`, and the loop zeroed player 2's lists; the
per-frame stage rewrites only some of each header's bytes, so the damage stayed.
Fixed twice over: `P2E_TOP` is set to `$FF` in `MirrorInit`, and the emit
refuses any row >= `$4E` or a start in band 0.

`tools/probe-p2-list-integrity.lua` checks every racing frame for a zeroed road
header in player 2's lists: RC1 failed on 4,122-4,284 frames per recording,
the fix and checkpoint 57 on none.

### Slot capacity

Adding a car to the game's list could, in a crowded band, make it the sixth
class-4 object, which the emitter would write past the band's slots. In run-03's
races the game never put more than one rival in a band, so the extra car makes
two of five; the append is also refused outright once five cars are listed.

## The grid is the stress case -- and a crash the original game can have

Checkpoint 59. Prompted by the observation that track 1's grid in run-03 starts
with rows of two cars ahead.

### Correction: rival cars per band

The previous entry said the game never put more than one rival in a band. That
came from captures that stopped around f5100, before run-03's second race, and
only counted state `$03`. **The grid is drawn during state `$11`**, the rolling
start, and counting that too, retail run-03 puts **four rival cars in one band
at f10300** -- track 1's grid, player 1 having qualified 6th.

### A band's object slots

`sub_E6D7` parks six slots per band (+0..+20); `sub_E320` two more at +24/+28
in bands 0-7. The emitter hands them out by slot class:

| offset | used by |
|---|---|
| +0 | class 0, fixed (kind-2 objects) |
| +4, +8, +12, +16, ... | cars, class 4, from a per-band counter `$1997` (starts at 4) |
| +16 (bands 7-12) / +20 (0-6) onward | class `$10`, signs, from `$198A` |
| **+20** | **player 1's own car**, class `$14`, fixed, in bands 7-11 |
| +24, +28 | crash pieces, classes `$18`/`$1C` |

So a near band holds **four** cars before the fifth lands on player 1's car. The
grid fills that exactly. There is no spare slot to reserve.

### What "reserving a slot" became

The emitter walks the list from the **last** entry down (rom:E729: `LDX $DD /
DEX`), so the entry appended last is the first to take a car slot in every band
it spans. Player 2's car is appended last -- it already has first claim, which
is the reservation. What was missing was a limit: `CarSlot` replaces the car
allocation at rom:E79C and leaves a car out of any band where its slot would be
+20 or beyond, stepping the sprite page as the write would have so the car's
next band still lines up. No car can now be written over player 1's; in an
overfull band the rival emitted last loses that band's slice. Retail never
reached +20 with a car in any recording, so this changes nothing there.

The guard added at checkpoint 58 -- refuse player 2's car once five cars were
listed -- is gone. It would have hidden the car on exactly this grid.

### Stress test

`tools/probe-grid-stress.lua` starts player 1 at grid position 6 or 8 (by
setting `$A6`, which the race start at rom:D0B9 builds the grid from) and holds
player 2 ahead of it among the rivals, sweeping the distance and lane. Checked
after every emitter pass:

    grid 6th: 243 passes, player 2's car listed on 243, player 1's slot intact
    grid 8th: 224 passes, player 2's car listed on 224, player 1's slot intact

The fullest band held four cars with player 2's included, so the cap was not
needed there. To prove its skip path, a test build with the cap at one car a
band (`PP2_CARCAP=0x08`) dropped 523 rival slices: rivals lose slices cleanly,
player 2's car -- emitted first -- stays whole, player 1's slot is untouched.
The default build is byte-identical with or without the hook.

(The integrity check compares only palette/width and x in player 1's slot: the
game's own wheel flicker, rom:E7D3-E7E7, rewrites band 10's sprite bytes every
frame.)

### A crash in the original game, exposed by timing

Run on the rival-car build, run-03 reset to the title at f9321, mid-qualifying
on track 1: game state, track, speed and clock all `$F0`. The write came from
rom:E935, inside `sub_E8AC` (stripe staging, called from vblank at rom:F15A),
whose last loop runs X from `$E6` down until it equals `$E7`, writing `$F0` to
`$4E,X` when X >= `$30`. `$E6/$E7` are a row range for the nearest sign-type
object, set by `sub_CC23` in the main loop in two halves -- `STA $E7` at rom:CC5E,
`STY $E6` at rom:CC60. The interrupt's return address on the stack was
**`$CC60`**: vblank had landed between the two stores, the loop got the new `$E7`
with the old `$E6`, started on the wrong side of its end, wrapped through zero,
and sprayed `$F0` across zero page.

The window is three cycles a tick, so retail can in principle hit it too; our
added main-loop work moved run-03 onto it. `E6E7Safe` now stores `$E6 = $FF`
first ("no range", which rom:E925 skips), then `$E7`, then `$E6`, so every
intermediate state is safe. run-03 now reaches both races on this build.

    health: identical to checkpoint 57/58 on five recordings
    run-03: both races reached, no reset
    player 2's lists: no zeroed road header on four recordings incl. run-03
    rival entries vs model: 167/167 both views
    walk: exact

## Player 2 sees the world's objects

Checkpoint 60. Player 2's view used to show the road and player 1's car only.
It now shows the signs, the marker and the rival cars, each at the size, sprite
and palette player 1 would see from player 2's distance, placed on player 2's
road. Getting there needed three things: room in player 2's lists, room in the
ROM, and CPU time.

### Three object slots a band, built at boot

Player 2's bands had one object slot, for the other car. Each band now has
`P2_OBJ_SLOTS` = 3: the headers, three parked slots, and the end marker. The
whole block still fits the 256 bytes a one-byte offset from `P2_DL_BASE` can
reach, ending at `$26FC`, clear of `P2_LATERAL` at `$2702`. The boot template
now holds only the headers plus each band's header length. `P2BuildLists`
(MirrorInit) writes the parked slots and end markers itself, so a bigger layout
did not cost a bigger template.

Slots are handed out in list order, and player 1's car is listed first, so it
always gets the first slot in its bands. That is the reserved slot, and it
leaves two for world objects. A full band skips that entry's slice there, the
way the game's own emitter does.

### The ROM is now 48K

The object code did not fit: the `$F400` blob came up 183 bytes short. As
agreed earlier ("expand the ROM to 48KB if we ever run out of space
altogether"), the build is now a 48K cart:
- header size 49152, type `$0000`, mapped at `$4000-$FFFF` with no banking,
  like Karateka;
- the 32K source sits unchanged at `$8000-$FFFF`;
- `$4000-$7FFF` starts as `$FF` and holds new code (`EXT_ADDR`), written with
  `expect` = `$FF` like every other put.

Checked before relying on it:
- RC6 padded to 48K gives identical 7,000-frame state logs to the 32K RC6 on
  run-01 and test-pp2-2p-0923-0205;
- bytes placed at `$4000` and `$7FF0` read back through the CPU;
- a `--sign` build passes `sign7800.verify` and boots through the BIOS to the
  title screen. `$FFF9` is `$87`, so the BIOS hashes from `$8000` and the new
  area is not covered, which does not stop it booting.

RivalCars, player 2's objects, `P2X`, the emitter and FastZRow moved to
`$4000`: 808 bytes, 15,576 free. The blob has 543 spare.

**`--bundle` now refuses.** A `.abp` section is a fixed extent of the source
body and the format cannot grow it (patchset-format.md, "Length changes"). The
committed `dist/pp2-splitscreen.abp` dates from d05d31f and was already stale.

### FastZRow: the row search by halving

`sub_E3CD` finds an object's row by walking from `$4D` down until a row's
distance exceeds Z: up to 78 passes, and it now runs twice per object, once
per view. The distance table (`$EB56`/`$EAB9`) falls strictly from 1300 at
the horizon to 0 at the bumper, so the answer is the largest row whose
distance exceeds Z, which halving finds in seven steps. rom:E3CD now jumps to
`FastZRow`. The build asserts it matches the linear search for every Z from 0
to `$7FFF`; both ROM callers and OcRow test for a negative Z first.

Confirmed live with `tools/probe-fastzrow-check.lua`, which recomputes the
original search on every return: **0 differences in 11,320 searches (run-03)
and 3,722 (test-pp2-2p-0923-0205).**

*Wrong turn:* the first run of that probe reported 2,594 and 1,975
differences. The probe had read the distance table when the script loaded,
before the cart was mapped, so its "expected" rows were all `$FF`. Reading
the table on first use fixed it; FastZRow was never wrong.

RivalCars per call, in scanlines (`tools/probe-rivalcars-cost.lua`):

| build | run-03 median / p90 / max | 0923-0205 median / p90 / max |
|---|---|---|
| RC6 (no player 2 objects) | 69.5 / 207.9 / 250.0 | 181.0 / 212.3 / 247.8 |
| OB4 linear search, with objects | 190.8 / 269.1 / 659.2 | 180.4 / 225.3 / 300.1 |
| OB5 FastZRow, with objects | 49.9 / 167.9 / 274.0 | 61.2 / 168.5 / 204.7 |

Player 2's objects cost less than nothing overall: the halving search saves
more than they add. The main loop holds its 6-frame cycle (6.00, from 6.05 on
OB3).

### How player 2's objects are built

After player 1's list and player 2's car entry, `P2Objects` walks the same
object window (`$B0` down to `$B1`) and, for each object, runs the game's own
routines with the object's distance moved by the camera gap:
- `sub_E3E0` for the row, kind (`$4A`) and height index (`$49`);
- `sub_E475` for the height;
- `sub_E55B` for the sprite by kind;
- `sub_E5C7` for the palette and width.

The distance is restored straight after `sub_E3E0`. Entries go into the
game's own arrays straight after player 1's list (`P2L_START`..`P2L_END`):
the game's emitter stops at `$DD` and never sees them, and `P2Emit` writes
them into player 2's bands in the same main-loop pass.

Only x is our own. `P2X` takes the object's lane coefficient (`$E80F`/`$A8A1`
by `$1A00`) and computes hi(c x (row+4)), plus player 2's camera at the row's
band, plus that band's road offset, plus `$4F`. It is the same projection as
player 1's car in player 2's view. Signs keep their second entry and its x
offset (`$BFF6`), as rom:E665 does. Kind 3 (player 1's crash) is skipped, and
so is band 0, which player 2's view does not have. `sub_E461` (slot class) and
`sub_E60F` (player 1's hide-by-lateral rules) are not called.

### The kind byte, clobbered: found by forcing the gap to 0

With the gap at 0, player 2 looks at the same objects from the same distance,
so its entries must be player 1's except for x. `tools/probe-p2-objects-gap0.lua`
forces the gap to 0 for player 2's object pass only, restoring it when the
pass returns, and logs both lists. `tools/p2-objects-gap0-check.py` then
matches the two lists in both directions.

The first build (OB4) failed. Signs came out as one entry instead of two, and
palettes were `$5E` where player 1 had `$9E`/`$9F` for signs and `$BF` for
cars. The cause: `P2X` calls `OcMul`, which uses `$4A`/`$4B` as its product
(and `$40`/`$41`/`$43`/`$4C` as scratch), and `$4A` is the kind that
`sub_E55B` and `sub_E5C7` branch on. The kind is now kept in `P2L_KIND`
(`$2790`) across the call.

`$2790` was checked first: a write watch on the retail ROM over all of run-03
saw no write anywhere in `$2700-$27FF` after frame 300. Every byte there is
written during the first 300 frames, presumably by the boot RAM clear.

After the fix (OB5), with the gap forced to 0:

    0923-0205: 430 lists; player 2's entries: 659 exact, 3 sprite-only
    run-03:   1874 lists; player 2's entries: 2114 exact, 74 sprite-only
    player 1's entries player 2 lacks: all in band 0, crash debris
      (class 18/1C, sub_E2CA), or player 2's own car (the last entry)

OB4, by the same check on 0923-0205: 343 of player 2's entries were not in
player 1's list, and 636 of player 1's sign entries were missing from player
2's.

The sprite-only differences are all cars (class 04). A car's viewing-angle
sprite (rom:E4F1) depends on x, which is player 2's own, and on player 1's
road slope at the row (`RowCurveOffset[row] - [row-1]`). Player 2 has no
per-row road of its own. **Known approximation:** a rival car in player 2's
view can show a neighbouring angle frame when the two players are on
differently curved road. Player 1's car in player 2's view takes the level
angle instead (OcSprite with `OC_S0/S1` = 0).

A trace confirmed one case that looked like a bug and is correct: at f2741 of
0923-0205 player 1 has a sign in view and player 2's list is empty. The sign
was at Z = `$007A` with player 2 182 units ahead, so player 2 had already
passed it.

### Checks on OB5 (promoted, `patches/pp2-2p.a78`)

    health: identical to OB3/OB4 on four recordings (the 0923-0205 frozen
      run ends at f6955, 18 frames before OB3's -- the faster loop)
    main loop: once every 6.00 frames (0923-0205 and 0923-0236)
    player 2's lists: no zeroed road header on 0923-0205, 0923-0236, run-03
    rival entries vs model (tools/rival-entries-check.py, now reading player
      1's car from player 2's list): 146/146, 346/346, 117/117 in player 2's
      view; 199/199, 140/140 in player 1's
    FastZRow vs linear: 0 differences
    slots: no band of player 2's needed more than 3 on 0923-0205 or 0923-0236
      (the busiest held 2)
    screenshots: signs and rival cars in player 2's view, in the track's own
      palette (desert yellow, the other course white/blue)

### Limits, for later

- **Player 1's window.** The object window is player 1's. With player 2 far
  ahead, objects past player 1's horizon are not in it yet, so player 2 sees
  them appear late, nearer than the horizon. Fix: widen the window to cover
  the leader, the leader/trailer idea from earlier.
- **Two world objects a band** in player 2's view. Neither 2-player recording
  reaches a race grid with player 2 among the rivals, so the grid stress case
  (run-03's track 2 start) is not measured for player 2's view yet.
- **Player 1's hide rules are not applied.** `sub_E60F` hides signs by player
  1's lateral; player 2 shows every sign in view.
- The pre-race visual issues on player 2's view (reported earlier) are still
  deferred to cleanup.

## Player 2's own world: its own signs, one field of traffic for both

Checkpoint 61. Until now player 2 saw the world through player 1's object
window, so objects appeared late in player 2's view when player 2 led, and
vanished before player 2 reached them when it trailed. Asked to have "the
leading player control what comes into view, or make it independent
completely except for overlap". It is now both:
- **Signs and the marker are independent.** Player 2 computes its own from the
  track data.
- **Cars are one shared field.** A car is kept while either player still needs
  it and re-placed ahead of whichever player needs cars, so where the views
  overlap they show the same cars.

### Correction: the object table is not full

An earlier entry here ("The object window CANNOT be widened: the 16 slots are
already full") was wrong. Only `$AE`+1 slots are live; the entries past `$AE`
are stale copies, and that count included them. Measured live on run-03:

    qualifying track 0   2 cars + 3 signs            ($AE = 4)
    qualifying track 1   4 cars + 3 signs
    tracks 2, 3          5 cars + 3 signs, + player 1's crashed car at times
    race                 + the marker (class 2)
    largest $AE while racing, all four tracks, retail: 9

Car counts are capped per track by `dat_ABD4`: 4, 6, 7, 7.

### How the game feeds the window

- **Signs are track data.** One sign stands at every object-segment boundary.
  `$A0/$A1` is the distance to the next boundary and `$A2` the segment index,
  both stepped by player 1's advance at rom:C4CB, the same Speed/2 that moves
  the road walk and every object. So the three signs are `$A0` ahead, then
  `+ObjSegLen[$A2+1]`, then `+ObjSegLen[$A2+2]`, each looking as rom:CF47
  builds it from `SegObjDesc` (type `((d & $70) << 1) | 1`, lane `$23`/`$24` by
  bit 0). Checked against the live slots: 3,801 of 3,804 samples on run-03 and
  0923-0236. The three misses are single transition samples: the tick where
  `$A2` has stepped but the slot is not yet recycled, and a lap reset.
- **Cars are a simulation.** Each has its own speed (`$1A10`, steered toward
  `$1CCF`), and the lane-change and overtaking AI (rom:CC77) works only on
  distances between cars. Only the recycle pass (rom:CAA0) refers to player 1:
  - a car more than 120 behind player 1 is retired;
  - it is re-placed `(2*$ED + 1 + dat_AFBE[track]) * 256` ahead (rom:CB1B), or
    deleted if there are more cars than the cap.
- **The marker** is re-placed `dat_AFC2/AFC6` ahead (15,000 / 15,000 /
  10,000 / 6,000 by track) once it is 120 behind.

### What was built (all in the `$4000` area)

- **Player 2's object segment.** `P2_OA0`/`P2_OA2` are the counter as
  rom:C4CB keeps it, stepped by player 2's advance in its drive (`P2ObjSeg`)
  and copied from player 1's at P2RaceInit.
- **Player 2's signs.** `P2Objects` computes the next three from that counter
  and draws them through object slot 15. The game never uses slot 15: a
  write watch over all of run-03 on retail saw no write to any of its arrays
  after boot. The sign loop stops at the first sign past the horizon.
- **The marker for player 2** is player 1's plus the gap, folded into
  -120..L, so player 2 sees the instance nearest ahead of it.
- **Cars:** `P2Objects` now walks **every live slot**, not player 1's visible
  window, since player 2 can see what player 1 cannot. Each car's distance is
  player 1's plus the gap.
- **One field of traffic: `CarTick` / `CarRetire`.** rom:D70D, the race
  tick's call of the object tick, now goes to `CarTick`: the same calls, with
  the recycle pass wrapped. A car is *needed* by a player while it is between
  120 behind and `CAR_REACH` (`$2400`) ahead of them. For the pass, each car is
  put in the frame of the player who needs it:
  - both need it: the frame in which it is further ahead, so it lasts until
    the trailing player has passed it;
  - one needs it: that player's frame;
  - neither: if it is more than 120 behind one of them, it is retired now
    (distance set to -128).

  The game's own code then retires and re-places. Afterwards, `CpFix` gives
  each re-placed car to whichever player has fewer cars coming (the leader on
  a tie), at the stock distance ahead of that player. If that would put it
  inside the other player's view (-300..1600), it goes to 1,600 ahead of the
  other player instead. Distances then go back to player 1's frame.
- **Stock when alone.** Until player 2 has moved (`P2_ACTIVE`), or while the
  gap is pinned at +-`$4000`, `CarRetire` is a jump to rom:CAA0.
  `PP2_STOCK_TRAFFIC=1` builds without the hook.

### Results

Signs, player 2's counter against player 1's plus the gap
(`tools/world-check.py`):

    0923-0205          717 of 717 race ticks exact
    0923-0236          706 of 706
    run-03             1,704 qualifying + 160 race ticks exact (until the gap pins)
    traffic scenario   1,201 of 1,201

Cars, on a controlled scenario (`tools/probe-traffic-scenario.lua`): track 3,
speeds scripted so player 2 falls 3,000 behind, leads by 7,900, and falls back.

| | stock traffic (W3-stock) | shared traffic (W4) |
|---|---|---|
| car re-placed inside player 2's view | 5 | 0 |
| car vanished inside either view | 0 | 0 |
| player 1 hit a car | 7 | 7 |
| cars in view per tick, player 1 / player 2 | 1.32 / 0.38 | 0.89 / 0.66 |

On an earlier, lighter run (track 1), stock traffic also retired cars inside
player 2's view three times, at 553-1,113 ahead of player 2. W3 did not.

Cost on that scenario, RivalCars in scanlines, and how often the main loop
needed more than its 6 frames:

| build | RivalCars median / p90 / max | 6-frame passes | 8 / 10 / 12 frames |
|---|---|---|---|
| OB5 (checkpoint 60) | 91.5 / 246.9 / 443.9 | 977 | 43 / 43 / 120 |
| W3 (no filter) | 261.1 / 323.9 / 504.7 | 798 | 49 / 49 / 199 |
| W4 (promoted) | 96.8 / 264.9 / 469.9 | 993 | 33 / 33 / 127 |

Track 3's traffic already made the stock-object build miss passes; that is
not new. W3 ran the full per-object pipeline about 8 times a call (every live
slot and all three signs), most of it on objects behind player 2 or past its
horizon. `P2Near`, a distance test before the pipeline (-128..1300, the most
rom:E3E0 can put on screen), brought it to 1.5 calls.

Also on W4:
- player 2's list integrity: 0 zeroed road headers on three recordings;
- rival-car model: 146/146, 344/344, 117/117 in player 2's view; 199/199,
  140/140 in player 1's;
- health: unchanged;
- screenshots: player 2 leading sees cars and signs player 1 has not reached;
  with the two close, both views show the same cars.

### Wrong turns

- **First hook site: the recycle call inside the object tick (rom:C9B9), plus
  the re-placement store (rom:CB38).** With player 2 inactive the logic was
  stock, yet run-01 shifted by a frame at the 00 -> 06 state change: that
  path runs the object tick from the setup code, and even a do-nothing loop
  there moved a main-loop pass over a frame edge. A fast path did not help.
  Hooking only the race tick's call (rom:D70D) and fixing re-placements after
  the pass instead of at rom:CB38 did: run-01 then matched the build without
  the hook for 12,000 frames.
- **One-player recordings are no longer frame-exact references.** Player 2's
  view now has content even when player 2 is idle (its signs), which costs
  time and moves passes. Against the build without the traffic hook:
  - run-01: identical;
  - run-03: 2 isolated sample frames differ;
  - run-02: diverges at f8972, after a main-loop pass slips at f7855.

  Player 2 was never active in any of them, so that is timing, not traffic
  logic.
- **The scenario's first runs** held the race clock at 0 to stop it running
  out, and player 2's drive does not run with the clock at 0, so the gap only
  grew. Held at a nonzero value instead. Poking TrackIndex did not choose the
  track; pressing Select on the title (after it appears, around f300) does.

### Limits, for later

- **Player 2 has no collisions** with cars or signs; it drives through them.
  The pieces exist: the gap, both laterals, and every object's distance.
- **Player 1's crash** (a car that becomes class 3) is not shown in player 2's
  view.
- **Viewing angles:** a rival car in player 2's view still takes its angle
  sprite from player 1's road slope (see checkpoint 60).
- **Pinned gap:** with the gap pinned (the players more than 16,384 apart),
  traffic reverts to player 1's alone. Player 2 still sees its own signs, but
  no cars.
- **`tools/p2-objects-gap0-check.py`** now stands for cars only; signs are
  checked by `tools/world-check.py`.

## Player 2 collides: puddles, cars and signs by player 1's rules

Checkpoint 62. Two reports: when the cars touched, player 1 bumped player 2
but nothing came back the other way; and player 2 drove straight through the
world. Asked, too, whether player 2 sees puddles.

### Correction: class 2 is the puddle, not a marker

Checkpoint 61 called object class 2 "the marker" and built a fold for it
(`P2Marker`, now `P2PdFold`). It is the **puddle**, found long ago in this file
("Type 2 is the puddle, and one dodge proves it"): type `$C2`, lateral 15-18,
laid for the race by rom:D1DF (`dat_ACD4` per track; qualifying is set up with
none at rom:CFD1) and re-placed `dat_AFC2/AFC6` ahead once passed. So player 2
has been *drawing* puddles since checkpoint 61, through that fold. It had no
effect until now.

### Player 1's rules (rom:C86E, rom:C1D3, rom:C93E)

- **Cars and puddles, by position.** Every slot within -45..77 of the player:
  - the row it would draw on (rom:C8AA);
  - its x there from rom:E676 (the lane coefficient times row+4, plus the road
    curve at the row, plus `$4F`);
  - then `- curve - $40 - PlayerX` in one borrow chain.

  Under 30 is a contact, or under 26 when the stale `$4E` is 75 or more. A
  puddle costs Speed/8, with the splash (sound 2) if none is playing and speed
  is 90 or more. Anything else is a crash.
- **Signs, not by position.** rom:C1D3 arms `$EB` while the car is deep on
  the verge (x <= -82, or >= 86) on the same side as the next sign (lane `$23`
  left, `$24` right). rom:C8F9 crashes it once the object segment steps while
  armed: the car went past the sign out there.
- **The crash** (rom:C93E), measured: `CrashTimer` 32, counted down once a
  tick. On run-02 it lasted 187 frames, 31 main-loop passes.
  - Each tick costs 25 speed, down to 0 (rom:C2C0).
  - No steering (rom:C500) and no further tests (rom:C866).
  - Sounds 7 and 8; low gear.
  - The car's sprite index `$E1` = timer + 10 (rom:C5F8): spin frames through
    `A797` -> `B3FA` height, `C0F4`/`C0FA` sprite, `AF29` x offset, `ADB6`
    palette/width while the index is 30 or more. After that the car is hidden,
    and two pieces of debris (rom:E2CA) fly out for the whole crash.
  - `PlayerX` is not reset.

### What was built

- **`P2Collide`** (the `$4000` area), once a tick after the gap is updated,
  applies the same rules with player 2's lateral in player 1's terms
  (`-P2_LATERAL`), its distances (player 1's plus the gap, puddles folded to
  the nearest instance), and its own object segment for the sign. The contact
  arithmetic is rom:E6D0/C8CD's instruction for instruction, road curve and
  borrow chain included.
- **The sign crash** fires in `P2ObjSeg` when player 2's segment steps while
  `P2_ARM` is set.
- **`P2CrashStart` / `P2CrashTick`:** player 2's own 32-tick crash, with the
  same speed loss, no gas, brake or steering, low gear, and sounds 7 and 8.
  At the end, speed 0.
- **`P2CrashDraw`** puts player 2's crash into its own list, first after
  player 1's car: the spin frames, then rom:E2CA's two pieces of debris (via
  rom:E344). `P2Car` parks player 2's four car headers meanwhile.
- **Car to car:** contact now shoves **both** cars apart, `COLLIDE_PUSH` (4)
  each a tick. Before, only player 2 was pushed, which is what "player 1 bumps
  player 2, and nothing comes back" was.
- The cars player 2 hits are the shared ones (checkpoint 61), so a car either
  player hits is a real car in both views.

### How it was checked

**The contact test is the same arithmetic as player 1's, exactly.**
`tools/contact-model-check.py` models rom:C8C1-C8EC with rom:E676 byte for
byte:
- the model against every player 1 test logged live
  (`tools/probe-contact-tests.lua`, `tools/probe-collide-scenario.lua`): 180 of
  180 values and decisions, on run-03 and two scripted races;
- player 2's code against the model: 134 of 134;
- exhaustively, player 2's arithmetic at the same place as player 1's: every
  car and puddle lane, every row a contact can be on, every road-curve value,
  every lateral. **0 of 23,969,792 differ.**

The one deliberate difference: for an object already behind the player,
player 1's 30-or-26 choice reads `$4E`, which then holds a stale value. Player 2
uses 30.

Races on tracks 1 and 3 with both players held level and in the same lane
(`probe-collide-scenario.lua`):
- player 2 crashes into the same cars as player 1, at the same gap when level
  (car slot 10, gap -1: f4785 and f4790), and first when it leads;
- both crash at the signs while deep on either verge;
- both take puddle slowdowns.

Screenshots: player 2's view shows its spin frames and debris, while player 1's
view carries on.

Car to car, the same start with laterals left free: on checkpoint 61 player 1
stayed at -10 while player 2 went to -52. Now player 1 goes to +10 and player 2
to -30, 40 apart (the contact box), then both drift with the road.

Also on checkpoint 62:
- player 2's list integrity: 0 zeroed road headers on three recordings;
- rival-car model: 103/103, 335/335 (player 2's car in player 1's view) and
  166/166, 132/132, 125/125 (player 1's in player 2's);
- signs exact on every tick;
- health: unchanged.

Cost: player 2's tick (rom:D713-D716) averages 516 scanlines against 506
before, peaking at 691 when a crash starts. RivalCars averages 161 lines while
player 2 is not crashing (152 before) and 207 while it is, for the crash's
entries. The traffic scenario's pass spacing got worse (12-frame passes 187
against 127), but that run now plays differently, with both cars crashing, so
it does not compare like for like.

### Wrong turns

- **The first player 2 formula**, `hi(c * (row+4)) + $0F - x`, looked like
  the ROM's once the curve cancels. It differs by one in **38%** of cases,
  because the curve goes in with a carry and comes out with a borrow. Replaced
  by the ROM's own sequence, which the exhaustive check then settled.
- **Probe artifacts, not code:**
  - the curve byte was read after the computation (the display interrupt
    rewrites that table);
  - `P2_LATERAL` was read after a per-frame poke had changed it mid-test;
  - a player 1 test and its hit were logged either side of a frame boundary.

  Each probe now reads the value at the moment it is used (a `P2ClCurve`
  label, `CL_PX`), and the checker matches the hit on the same frame or the
  next.
- **The first scripted runs** found no puddles: qualifying is set up with
  none. The scenario now drives on into the race.

### Limits, for later

- **Player 2's crash is not shown in player 1's view.** Player 2's car keeps
  its ordinary sprite there. The game's own rival-crash frames (kind 3, rom:E4B7
  / E59D / E5E8, driven by `CrashTimer`) are the way to do it.
- **Player 1's crash is not shown in player 2's view** (the car it hit, class
  3, is skipped there, and player 1's car keeps its ordinary sprite).
- **A car player 2 hits carries on.** For player 1 it becomes the crash kind
  and is moved behind player 1 when the crash ends (rom:D037). Player 2's
  crash leaves the shared car alone, so it drives on ahead.
- The splash and crash sounds share the TIA's two voices with player 1's, by
  the game's own priorities.

## Each player's crash, seen from the other car

Checkpoint 63. After checkpoint 62 each player saw only their own crash; the
other car went on looking normal while it spun and stopped.

**How the game draws a crashed rival** (the car player 1 hit): kind 3 through
the same per-object routines -- the row snapped to its band's base row
(rom:E443), height `B3FA`, sprite `C0F4`/`C0FA`, palette `ADB6`, all indexed by
`A7A1[CrashTimer]` (rom:E4B7, E59D, E5E8) -- and hidden once the count is under
20 (rom:E60F, x = `$A1`). `A7A1[t]` is `A797[t + 10]`: the same six spin frames
the player's own car uses, over the same part of the crash.

**What was built.** `OcCrash`, called in RivalCars on each other-car entry
(player 2's car in player 1's view with `P2_CRASH`, player 1's in player 2's with
`CrashTimer`), gives it that look: spin frames while the count is 20 or more,
then left out of the list until the crash ends, as the game does. The frames
are full size -- the game only ever draws them right in front of the player --
so a car further off (its own sprite under 16 rows tall) keeps its ordinary
sprite for the whole crash rather than a full-size explosion at the horizon.

Player 2's view also now draws **the car player 1 crashed into** (kind 3),
through the same routines with player 1's count, hidden under 20 as rom:E60F
does. It was skipped before.

Checked by screenshot (`tools/probe-collide-shots.lua`, screenshots at set
delays after every crash): player 1 crashing 245 ahead of player 2 appears in
player 2's view as the spin frames growing and shrinking, then nothing, then
player 1's car again; player 2 crashing 644 ahead of player 1 is too far for
the frames and stays an ordinary small car in player 1's view. Unchanged:
list integrity (0 zeroed headers, three recordings), the rival-car model
(103/103, 335/335; 174/174, 130/130, 117/117), health.

Still open: **a car player 2 hits carries on driving.** For player 1 the car it
hits becomes the crash kind and is moved behind at the end (rom:C9F2, rom:D037),
but that machinery is keyed to player 1's one `CrashSlot` and `CrashTimer`.

## The car player 2 hits behaves as the car player 1 hits

Checkpoint 64. After checkpoint 62 a car player 2 crashed into drove on as if
nothing had happened.

**Player 1's sequence, for reference.** CrashStart (rom:C93E) records the car
in `CrashSlot`; the next object tick (rom:C9F2) makes it the crash kind (type
`$43`) and takes 25 off its speed every tick of the crash; it is drawn from
`CrashTimer` (rom:E4B7 height, rom:E59D sprite, rom:E5E8 palette) and hidden
below 20 (rom:E617); when the crash ends rom:D037 makes it a fresh car
(rom:CF3B look), 119 behind the player at its own target speed (`$1CCF`), in
lane 1 or `$22`, whichever is away from the player.

**Player 2's, now the same.** `P2CrashCar` records the car in `P2_CRSLOT`
and makes it the crash kind at once; `P2CrashTick` slows it 25 a tick;
`P2Wreck` gives it back -- fresh look, 119 behind player 2, own speed, lane
away from player 2 -- on the tick the crash ends. Wrinkles:

- **The drawing reads one crash count.** The four `CrashTimer` reads above now
  go through `CrTimerOf`, which gives the count of the crash that car belongs
  to: player 1's for `CrashSlot`, player 2's for `P2_CRSLOT`. Both views use
  the same routines, so player 2's wreck animates by player 2's crash in both.
- **Invisible wrecks.** Player 1 never tests its own wreck (no tests while
  crashing), but it can reach player 2's. rom:C87E now skips a wreck whose
  crash has it hidden, so neither player hits what it cannot see; player 2
  tests wrecks under the same rule.
- **One car, two crashes.** A car player 1 is already crashing into stays
  player 1's; if player 1 hits player 2's wreck, player 1's crash end resets it
  and player 2's leaves it alone.
- **Player 2's wreck lives in player 2's frame** for the recycle pass while the
  crash lasts (CarRetire), or the stock rule would park it beside player 1.

Checked tick by tick (`tools/probe-wreck.lua`), one crash each:

    player 1, slot 9: type 43 at once, speed 42 -> 0, parks at -112, then
                      type 80, z -119, speed 67, lane 34 (player 1 left)
    player 2, slot 8: type 43 at once, speed 48 -> 0, parks at -112, then
                      type 80, z -119, speed 67, lane 1 (player 2 right)

and on all nine crash ends of that run, both players' cars came back at exactly
-119 from the player that hit them. Screenshots: player 2 crashing 240 and 31
ahead of player 1 shows as explosions in player 1's view; player 1 then drove
into player 2's wreck and crashed on it, as it would on any wreck. Unchanged:
contact arithmetic (0 of 23,969,792; 65/65 live), integrity, rival-car model,
signs, health.

*Wrong turn:* the first version gave the car back inside the drive, as the
count ran out -- before this tick's gap update, so it landed up to a tick's
advance (about 100) short of -119. It now happens at the top of `P2Collide`,
after the gap is updated.

**Saved for last** (cleanup, per the standing rule): the visual glitches in
player 2's view before a race starts.

## Found: both cars are placed on the same spot at every start

**Confirmed live** on test-pp2-2p-0923-0236 and -0205: one frame into the
qualifying banner (state `$10`), player 1 is at x -28 and player 2 at -36 --
both were put at -32 and the car-to-car push has already started separating
them; 30 frames later they are at -12 and -52.

Cause: `P2GridSym` sets `PlayerX = -GRID_LANE` and `P2_LATERAL = +GRID_LANE`,
and `P2PlaceMirror` sets `P2_LATERAL = -PlayerX`. Both were written before
"Correction: the two laterals run in opposite directions" -- player 2's position
in player 1's terms is **-P2_LATERAL** -- so both now put player 2 exactly on
player 1 instead of in the other lane. The correction fixed collision, drift
and the other-car drawing but not these two.

Consequences, now that the cars collide:
- every qualifying start begins with the two cars inside each other, a bump
  and a speed penalty for both (quite possibly the "player 1 bumps player 2"
  seen in play);
- every race start puts both cars in player 1's grid lane. In the scripted
  race runs both then crashed into the grid car there (slot 10, 1 ahead) at
  the rolling start, on track 1 and track 3 alike.

Fixing the sign will put player 2 in the other lane of player 1's grid row --
where an enemy car was placed (see "The race grid", step 4), so that car will
also have to go.

## Starts fixed: side by side, and the car in the way moved

Checkpoint 65, fixing the bug found just above.

- **Qualifying (the `$10` banner): side by side.** `P2GridSym` now puts player 1
  at -32 and player 2 at +32 (`P2_LATERAL` -32), level on the track. On both
  recordings: -32 and +32 one frame in, still there 30 frames later, no bump.
- **Race: player 2 in the other lane of player 1's grid row.** `P2PlaceMirror`
  sets `P2_LATERAL = PlayerX`, i.e. x2 = -x1, at the `$11` banner and again at
  `$03` when the game sets player 1's lane. A slot closer than 20 to the centre
  (the mirror would be inside the contact box) sends player 2 64 away on the
  other side instead; `GRID_MIN_MIRROR` went from 16 to 20 for that reason.
- **Player 1 is no longer moved at the race banner.** `P2RaceInit` used to call
  `P2GridSym` at `$11` too, which set `PlayerX` to -32 -- straight into the grid
  car sharing player 1's row, which player 1 then crashed into. The game leaves
  `PlayerX` alone there (a leftover, measured 44) and sets the real lane at `$03`;
  so does this now.
- **`P2Clear` moves a car out of player 2's way.** Any car level with player 2
  (-128..160) and within 40 of its lateral is sent 128 behind both players,
  where the recycle pass retires it at once and it rejoins as traffic ahead --
  what the game already does with every grid car that starts behind player 1.
  Run at every placement. On the race grid it is exactly the car the game put
  in player 2's new lane.

What the grid looks like (track 3 and track 1 alike): rows of two, 272 apart,
lanes `$02` and `$20`, the `$20` car 16 further ahead. Player 1's row holds one
enemy car. After the fix: player 1 at 44 (its own), player 2 at -44, the car
that was in lane `$02` beside player 1 moved to -128 and recycled, and no crash
at the start on either track with nothing held during the race.

### And the other car was missing from player 2's view at the start

With the two level, the gap is typically -1: player 2 one unit ahead, so in
player 2's view player 1 is one unit *behind*. `OcRow` rejected any negative
distance, but rom:E3E6 adds 6 first and only then looks at the sign, so the
game draws a car up to 6 behind on the bottom rows. `OcRow` now does the same
(and so does `tools/rival-entries-check.py`'s model); player 1's car now shows
beside player 2's at both starts. Rival-car model on the recordings: 69/69,
79/79 and 46/46, 93/93, 117/117 (fewer entries than before -- the recordings
now play differently, since the cars no longer start inside each other).
Integrity and health unchanged.

`tools/probe-start-positions.lua` reads both positions at each start.

## The HUD: one line per player

Checkpoint 66. The divider's text rows now read

    2UP  score  clock  gear  lap  speed MPH     <- player 2, top row
    1UP  score  clock  gear  lap  speed MPH     <- player 1, under it

each one 31-character text object, the clock shared (there is one race clock),
the lap to a tenth rather than a hundredth.

**Where the game keeps each value** (read from the code, all confirmed on
screen):

| field | value | HUD characters | writer |
|---|---|---|---|
| score | `$1CA5-$1CA7` BCD | `$1FAE` (5) | rom:C69A, leading zeros blank |
| top score | `$1CA8-$1CAA` | `$1F90` | same |
| clock | `$DE/$DF` BCD, -1 every 6 ticks | `$1FB7` (3) | rom:C705 |
| lap | `$BC/$BD/$BE` BCD | `$1FA2` (6, colon `$B0`) | rom:C772 |
| speed | `$CE` binary | `$1FC0` (3) + mph `$AC $AD` | rom:C7B5 |
| gear | `$DB` | `$1FC6` (2) | SetGearLo/Hi |

The score is distance: Speed/2 a tick into `$AD`, 10 points per 40 of it
(rom:C600), called only from the driving paths. The lap's seconds step when
the tick phase `$E0` comes round to 0 and its hundredths are that phase's
entry in `dat_9CE3` (00 14 37 45 62 79); it does not run in states 05 07 10 11
08 0E 0F 01 (`dat_ADD0`).

**Built.** The 1UP line copies player 1's fields out of the game's own HUD
characters every tick. The 2UP line is built from player 2's own values:
- **score** (`P2_SCORE`), by rom:C600's rule on player 2's speed, in states
  $02 and $03, reset at the qualifying banner;
- **lap time** (`P2_LAPS`/`P2_LAPH`), by rom:C74E's rule on the same tick phase,
  started and restarted when player 2 crosses the start line -- its object
  segment stepping out of segment 0, the boundary whose crossing starts player
  1's lap (rom:CBD1) -- so it counts from player 2's own crossing;
- gear and speed from player 2's (rom:C7B5's conversion), the clock copied.

The rows' display lists are in ROM at `$7FE0`/`$7FE8`/`$7FF0` (the new code
area stops at `$7FDF`), so `HUD_ROWS` -- written by HudReassert, StartDriveHud,
QualDriveHud and the boot zone list -- is a constant as before. The HUD
appears and disappears exactly as stock's does: blank on the banners, the
start light and "PREPARE TO RACE" in their places, back when driving starts.

Checked with both players driven identically (`tools/probe-hud-values.lua`):
through the qualifying lap the two scores agree to within the 10 points of one
tick either side of a sample, and player 2's lap seconds equal player 1's whole
seconds at every sample, both starting on the frame of the line.

### Wrong turns

- **1UP on the third row** drew bold with the "h" of mph a solid block: that
  row renders in read mode 0 (it only ever held the gear, which is why "HI" /
  "LO" always looked bold). 1UP is on the second row; the third is empty.
- **8-line rows** (8+8+5, keeping the divider's 21 lines) to show the glyphs'
  last line: the font is seven lines tall, and the eighth reads past it and
  draws stray dots under every space. Back to 7+7+7, as stock.
- **Player 2 scored between races**: its score ran in every state not on
  rom:C600's skip list, but C600 itself only runs while driving -- player 2
  gained 1,020 points in the intermission after qualifying. Now $02/$03 only.

### Seen, for the next step (player 2's laps)

- **Player 2 keeps driving after qualifying ends**: the gap moves through the
  states after `$0B`, while player 1 is stopped by the game.
- **Player 2 gets none of the bonuses** player 1 does at the end of
  qualifying (player 1 went 8,570 -> 10,000 -> 10,400) -- no qualifying
  position, no lap bonus yet.
- Player 2's lap clock already restarts at each crossing, so its lap times --
  the input to a qualifying position -- are there to be used.

## Player against player: a rear-end is a crash, alongside is a bump

Checkpoint 67. The two players now meet by the game's rule for a rival car
(rom:C86E: in reach ahead, within 30 across -- the laterals are on one scale):

- **the other car 31..77 ahead and within 30 across: the car behind crashes.**
  Player 2's is its own crash; player 1's is the game's CrashStart (rom:C93E),
  handed slot 15 -- the spare slot player 2's signs are drawn through -- with a
  sign's type put there first, so the crash has no car to wreck and rom:D037
  returns at once when it ends (it leaves a sign's slot alone);
- **nearer than 31 (alongside): the bump**, both shoved apart and a speed
  penalty once per contact, as before.

The car in front is not wrecked (unlike a rival, which becomes the crash kind):
it is a player, and it drives on.

Checked (scripted, qualifying lap): player 2 driven into player 1's lane from
behind crashed at 76 and 69 behind; player 1 driven into player 2 crashed at 72
behind, through slot 15, with the explosion in its view and player 2's car
driving on ahead of it. Integrity, rival-car model, health unchanged.

The far-edge 26 of rom:C8EA (for 75..77) is not reproduced -- 30 throughout.

## Player 2's engine: one voice each

Checkpoint 68. The TIA has two voices, and the game shares them between the
engine (sound `$0F`, priority 0 -- the lowest) and its effects.

**How the engine sound works** (rom:C36C-C3B1, rom:DF3D-E03B): EngineNote sets
`EnginePitch` ($210D) = 30 - Speed/16 (3 lower in LO) and `EngineRate` ($210C);
SoundUpdate gives the voice playing `$0F` that pitch on AUDF, the volume
`$210B` (8, toggled by 8 each update on the verge, the off-road pulse), and
the rate as its duration. It is started on a free voice -- SoundStart takes
voice 1 first -- when no voice is playing it, and stopped with SoundStop($0F),
which would silence every voice playing it.

**Built:** voice 0 is player 1's engine and voice 1 player 2's, whenever an
effect is not using it; effects still take a voice by the game's priorities
(SoundStart unchanged, so they take voice 1 first). Four hooks:
- rom:DF5A `LDA EnginePitch` -> `EngPitchX`, the voice's owner's pitch;
- rom:DFDA, the engine's volume and rate -> `EngVolRate` (player 2's verge
  pulse on its own lateral and volume byte);
- rom:C372 player 1's `SoundStop($0F)` -> voice 0 only;
- rom:C378 player 1's start -> voice 0 when free.

`P2Engine`, once a race tick, computes player 2's note with EngineNote's own
arithmetic and starts or stops $0F on voice 1. `PP2_STOCK_AUDIO=1` builds without.

Checked from the TIA registers (`tools/probe-engine-voices.lua`), players at
200 and 120: voice 0 AUDF 15, voice 1 AUDF 20 -- EngineNote's values for each --
swapping when the speeds swap; both volume 8; after player 2's crash voice 1
briefly carried an effect and then its engine again. Health unchanged. A
recording of the run (a1.wav) was kept for listening.

## The end of qualifying, and player 2's place on the race grid

Checkpoint 69.

**Player 1's end of qualifying** (rom:D3F7, state `$0B`, entered at the line):
the lap is ranked against `dat_DBA0`/`DBA8`. Worse than 73.00 (or 100 s and
over) and it is state `$02` again -- another lap while the clock lasts.
Qualified, the car is stopped 16 a pass (SpeedPenalty16, rom:D6E8: the score
rounded by rom:D478, then rom:D6EB, which runs the race tick). Once stopped:
`$A6` = position, the POLE POSITION / QUALIFYING POSITION message,
`dat_A6C4[pos]` hundreds of bonus to the tally (40 20 14 10 08 06 04 02),
speed and clock zeroed, state `$12`. **The race grid** (rom:D1AD): row
(pos-1)/2, row*256+$64 short of the line (both the walk, `$D5/$D6`, and the
object segment, `$A0/$A1`); lane `$20` for odd positions, `$02` for even,
projected at row `$48` for `PlayerX` (rom:D1E5-D202).

**Player 2, built:**
- `P2Line`, at player 2's line: a completed lap in `$02`/`$0B` is ranked the
  same way (rom:D3F7's compares, player 2's seconds and its hundredths).
  Qualified: position kept, the score rounded as rom:D478 does, the car
  stopped 16 a tick and parked (`P2_PARK` 1). Not: another lap.
- `QualHold` at rom:D422 (`INX / STX $A6`, reached once player 1 has
  stopped): while player 2 is still on a lap that could qualify (under 73 s),
  player 1 waits -- back into the race tick through rom:D6EB, speed held at
  0, the clock still (C705 is not on that path). Then: player 2 out if it did
  not make it; a tie on position goes to the better lap, the other one place
  back (9th is out); player 2's `dat_A6C4` bonus added; `$A6` stored.
- `P2RaceSlot` at the race banner: a qualified player 2 onto its own slot --
  row and lane from its position as rom:D1AD does, its walk, object segment
  and the gap all from the row, its x by rom:D1E5's projection -- and the car
  the game put there cleared (P2Clear). One that did not qualify sits out:
  parked behind the grid (a 9th slot), not drawn, no collisions (`P2_PARK` 2).
- **Cars right behind a player start from rest.** Grid cars leave at full
  speed and a player from 0, so a car behind a player in its lane rammed it
  within a few ticks (seen: player 2 on row 1, crashed 47 frames into the
  banner by the row-2 car behind it). Stock never meets this: every car
  behind player 1 at the start is behind the only player and is recycled at
  once. Now, at the grid, a car within 1,280 behind either player in that
  player's lane gets speed 0; rom:CA32 brings it back up one a tick.

Player 2's lap clock now has **its own tick phase** (`P2_LAPPH`, stepped as
rom:C705 steps `$E0`). *Wrong turn:* on `$E0` it froze during the hold --
C705 is not on the hold's path -- so a player 2 lap never reached 73 and the
hold never ended (seen: player 1 held in `$0B` indefinitely).

Checked (scripted, track 3):

    A  p1 200, p2 190   p1 7th at 69.14; p2's lap went past 73 in the hold
                        (it crashed on the way): out, sits the race out
    B  p1 190, p2 200   p2 qualified first (7th, +400), parked; p1 8th, no
                        hold; grid: p1 lane $02 x -41, p2 lane $20 x 44
    D  p2 not driving   hold released as p2's lap passed 73: out
    F  p1 200, p2 215   p2 4th (+1000), p1 7th: p2 two rows ahead, gap -513
                        at placement, its slot's car moved to -128, and no
                        crash at the start (before the rest start: rammed)

Health identical to checkpoint 68 on run-02, run-03 and both 2-player
recordings (a player 2 that never crossed the line releases the hold at once);
integrity 0 on all.

**Not yet**: player 2's qualifying position is not shown on screen (player 1's
message is the game's), and "player 1 does not qualify, player 2 races alone"
waits on player 2's own race logic (next).

## Player 2's race: its own clock, laps and finish

Checkpoint 70.

**Player 1's race** (for reference): `$A7` is 1 when the race starts, and the
race ends at the crossing where it equals `$C3` (5 on track 3), so four laps
after the start line. Each other crossing adds 60 to the clock (BCD, rom:D504)
with jingle `$0B`. The clock goes −1 every 6 ticks (rom:C705, skipped in
states `$01`/`$0E`). When the clock reaches 0 (rom:D324) or player 1 finishes
(rom:D4BC), the game waits, running the race tick, until `CrashTimer | Speed`
is 0. It then tallies 200 a second left (`$0F`, 4 × 50) and cars passed
(`$08`).

**Player 2, built** (`P2_CLOCK` `P2_CPH` `P2_LAPN` `P2_RST` `P2_RACE`, $2730-$2735):
- `P2RaceGo`, from `P2RaceSlot` when player 2 qualified: its own clock from
  player 1's starting clock, its lap count from `$A7`.
- `P2RaceTick`, once a tick from HudTick: the clock, as rom:C705 runs it. At 0,
  player 2 is out of time: parked, slowing 16 a tick.
- `P2RaceLap`, at player 2's line during the race: +60 and the jingle, or on
  the last lap the finish: parked, and 200 a second left added to its score.
  The lap clock is no longer restarted at each crossing in the race, so it
  runs on as the race total, as player 1's does.
- `RaceWait`, at rom:D324 and rom:D4BC (`LDA $D4 / ORA $CE`): reports
  "not stopped" while player 2 is still racing. Player 1 waits, held at speed 0
  through the race tick, until player 2 finishes or runs out of time.
- A finished or timed-out player 2, once stopped, is taken off the track
  (`P2_PARK` 2): no longer drawn in player 1's view, and nothing to hit.
  Before this, it sat stopped just past the line in its lane, in player 1's
  path on every later lap.
- 2UP shows player 2's own clock once it is racing.

### Wrong turns

- **Lap count off by one.** `P2_LAPN` started at 0 while `$A7` starts at 1, so
  player 2 needed a fifth lap. Seen: player 1 finished, and player 2 ran out
  of time a lap short while the game held player 1. It now starts from `$A7`.
- **Player 2 frozen when player 1 timed out.** Player 2's drive was gated on
  player 1's race clock ("is the race under way?"). With player 1 out of time
  and held by RaceWait, player 2 kept speed and score but did not move, while
  its own clock ran down. Seen: the gap stuck at −16008 through the hold. In
  the race, player 2's own state now decides this.
- **Probe artifacts, not bugs.** The race probe wrote player 1's clock (60)
  every frame and forced both speeds. So player 1 could never time out, and a
  player past its time kept driving and earned another +60 at the line. The
  probe now leaves player 1's clock alone (`FREECLK`), stops driving player 1
  once its clock is 0, and stops driving player 2 once `P2_RST` is set.

### A crash when player 2 falls far behind (pre-existing, fixed)

Player 1 at 240 and player 2 at 120 reset the machine at player 1's first lap
crossing: state, track and clock all `$F0`. The same happens on the committed
checkpoint 69 build. The stock ROM makes about 12 crossings at each of 230,
240, 250 and 255 without it.

Traced:
- **The write:** rom:E935, the stripe loop (`X` from `$E6` down to `$E7`), with
  `$E6` = `$E7` = `$4D`. An empty range runs the loop all the way round,
  across zero page.
- **Where `$E6/$E7` come from:** rom:CC23 takes the first type-1 object (the
  start line and the signs), `$E6` from its Z+6 and `$E7` from its Z+106,
  through rom:CC63's row table. That table ends at 0 for row `$4D`, so any
  type-1 object at Z ≤ −107 gives `$4D`/`$4D`. In stock the start line's Z
  always equals `$D5` (the distance to the segment end), and the line leaves
  the list at the crossing, so this never happens.
- **Why the line was elsewhere:** slot 3, the line, was 2,124 short of `$D5`
  and drifting further. A write tap showed it moved twice a tick. The first
  move is rom:C9F0's; the second comes from rom:CAA0, the stock recycle pass.
  For an object more than 256 behind (Z hi negative and not `$FF`), CAA0 resets
  it to −96. If player 1 is left of centre, it then leaves through rom:CACA
  `JMP sub_CA89`, which lands in C9F0's movement loop and moves every object
  after it in the list again. Stock never has an object that far behind.
- **Why objects were that far behind:** cars kept for a trailing player 2
  (CarRetire) sit behind player 1. Once player 2 is more than `$4000` behind,
  the gap pins and CarRetire goes back to the stock pass, which then meets
  those cars. One such object a tick is enough to double-move the rest.

Fixed twice:
- On the pinned path (`CrPin`), any object more than 256 behind is first set
  to 256 behind (`$FF00`), so the stock pass retires it the ordinary way
  (rom:CAD4).
- `E6E7Safe` also refuses an empty range: if `$E7` ≠ `$FF` and `$E6` ≤ `$E7`,
  `$E6` stays `$FF` ("no range"). `$E7` = `$FF` is a real range (up to the
  top). Stock never produces an empty range, or it would reset itself.

Still true: a pinned gap no longer tracks the real separation, and cars all
stay in player 1's frame while it is pinned. Player 2 that far behind sees no
cars until the gap unpins. The long-term answer is probably to wrap the gap
modulo the track length; noted for later.

### Checked (scripted, track 3, both at −40/+40)

    p1 215/p2 210 then 240/240, clock pinned  p2 laps 1→5 with p1's; p1
        finishes; the game holds; p2 finishes (+200/s); release, $0F, game over
    p1 160, p2 240 (pinned)   p2 finishes first, stops, leaves the track; p1
        races to its own finish
    p1 150, p2 240 (free)     p1 out of time at 71 s, held at 0; p2 races on,
        laps 2..5, finishes with 25 s (+5,000); release, $08, game over
    p1 150, p2 150 (free)     both out of time; game over at once
    p1 240, p2 240 (free)     p2 crashes into a car 3 frames after p1 finishes,
        4,557 behind; recovers; out of time 1,622 short; release
    p1 240, p2 120 (free)     the crash case: no reset. p2 out of time and off
        the track, p1 finishes the race

Health identical to checkpoint 69 on run-02, run-03 and both 2-player
recordings (the recordings drift a frame from f698 on, the known boot-timing
desync). Integrity 0 on four recordings.

### Measured, for the optimization pass

Race-tick rate in a racing window (f7000-7600, both cars at 240, traffic):

    stock 100 ticks / 600 frames   ck60 82   ck62 57   ck65 51   ck69 54   ck70 53

Two-player racing therefore runs at a little over half stock speed once both
views have traffic. Qualifying (f1400-3600 of 0923-0205) is still at a full
6.00 frames a tick. Both clocks count ticks, so the race stays fair; it just
plays slowly. The drop arrived with player 2's world objects and collisions
(checkpoints 60-62), not with this round.

**Not yet:** player 2 has no cars-passed tally (`$08` counts player 1's
only). "Player 1 does not qualify, player 2 races alone" is next.

## Player 1 does not qualify, player 2 does: player 2 races alone

Checkpoint 71.

**Stock:** the qualifying clock runs out in state `$02` (rom:D305). Once player
1 has stopped (rom:D30D, `LDA CrashTimer / ORA Speed`), rom:D316 ends the
game. The race setup that follows a qualifier's stop (rom:D422-D476, then
states `$12 $0E $07 $05 $11 $03`) depends on `$A6` throughout: the object count
(rom:D0D9), the parity adjustment on track 0 (rom:D102), the grid (rom:D1AD),
the lane (rom:D1E9), and the blinking digit in the message (rom:DA03). So
player 1 gets a real grid position rather than an invented 9th.

**Built:**
- `QualOut` at rom:D30D: if player 1 has stopped and player 2 qualified, set
  `P1_OUT` and go on as rom:D422-D476 would, using player 2's position. That
  gives the pole message, or QUALIFYING POSITION with player 2's place
  blinking. Player 2 gets its `dat_A6C4` bonus; player 1 gets none
  (TallyValueHi 0); then state `$12`. `$A6` is player 2's position, so player
  1's grid slot is player 2's own and no rival is displaced for it.
- `P1OutRace` at rom:D31C (`LDA RaceClockHi / BNE`), in state `$03` only:
  player 1 stays on the stopped path (rom:D6EB, held at 0; its clock does not
  run there) until player 2 is done. Then it takes the end of a stopped
  player 1's race (rom:D32D: the cars tally if any, then game over).
- `P1Coll` at rom:D70A (`JSR sub_C866`): no contacts for player 1 while it
  sits out. `PvpCrash` and the players' contact box skip too, since the two
  cars start on the same spot.
- `P1_OUT` ($2736) is cleared with the rest at a new session (`$10`).

### Wrong turn

- **The banner never ended.** rom:D31C is the handler for state `$11` as well
  as `$03`. Held there, the start countdown never finished, while player 2,
  its race flag set, drove off and ran out its clock under the banner (seen:
  `$11` from f5971 to game over). The hold is now for `$03` only.
- **Probe:** it forced player 1's speed whenever player 1's clock was not 0.
  A sitting-out player 1's clock stays at 72, so the probe drove it round to
  a lap crossing. The probe now leaves player 1 alone once `P1_OUT` is set
  (and with `FREECLK=2` leaves the qualifying clock alone too).

### Checked (scripted, track 3)

    p1 100, p2 215   p2 4th, p1 out at f5220: message with 4 blinking, tally
                     0000, race at f6182; p1 held at 0 on p2's slot, no
                     contacts; p2 out of time on lap 3; game over
    p1 100, p2 240   p2 laps 1..5 alone, finishes with 28 s (+5,600); game over
    p1 100, p2 100   neither qualifies: game over as stock
    p1 215, p2 210   both qualify: the checkpoint 70 race, unchanged

Health identical to checkpoint 70 on four recordings (run-02: 7 single-frame
`PlayerX` samples differ, same values a frame apart). Integrity 0 on four.

**Seen, for cleanup:** while player 1 sits out, 1UP shows its frozen clock,
and its view shows its car standing on the grid. One car-tally point (50)
was credited to player 1 at the end of a race it sat out.

## Two-player racing back at full speed: the vblank wait, split

Checkpoint 72. Race-tick rate in a racing window (f7000-7600, both cars at
240, traffic):

    stock 100 ticks / 600 frames    checkpoint 71: 53    now: 100

### Where the time went

A sampling profile (`tools/probe-race-profile.lua`, taps on the DLL reads)
put 28% of the two-player race's visible-frame samples in `sub_DB8E`, the
vblank spin, at SP `$F1-$F5`: interrupt code. Stock had about 1% there.
Tapped by caller and beam line (`tools/probe-race-spin.lua`), all of it was
DLI idx11's tail waiting at rom:F160:
- **stock** spins from line ~248: its 97-`WSYNC` road injection fills the
  lines before;
- **this build** spins from line ~176: RoadTail bypasses the injection and
  jumps straight to rom:F143, so the handler reached the wait about 70 lines
  early and held the main loop for about a quarter of every frame.

The spin was not new cost; the injection used to spend those lines. But it
is reclaimable time, and the main loop was missing its six-frame slot
(rom:EA28) for lack of it.

### The split

- `VbSplit` at rom:F160: clears `$9C` (DLIs allowed again), sets `$FF` = 12,
  returns from the interrupt.
- DLI index 12, `VbTail`, on the first bottom-margin zone (DLL line 232):
  releases `$E5` (moved there from rom:F150, `STA` -> `BIT`), stages
  MirrorStage's inputs, and goes on into the stock tail at rom:F163.
- The NMI's handler tables are relocated to the code area (`DliLo`/`DliHi`,
  rom:EBFC and rom:EC01 retargeted) to carry the 13th entry.
- **No wait for vblank in VbTail.** The tail's real deadlines are only "after
  the view it writes": player 1's road (ends line 217), player 2's (ends 104),
  and `sub_DC4F`'s decor list (zone 19, lines 135-144, rewritten every other
  frame; that is why the tail alternates in length).
- **MirrorStage's inputs are staged.** The main loop now runs between lines
  176 and 232 too, so VbTail can fire mid-P2Tick. MirrorStage read the curve
  (rom:E93D's `RowCurveOffset`) and player 2's `P2_BANDX` live. Stock never
  met this: the spin kept the main loop out until MirrorStage had run. P2Tick
  now raises `TICK_BUSY` while it writes. VbTail copies the 13 sampled rows
  and `P2_BANDX` into `$1C38-$1C52` when it is clear; mid-tick, the last
  complete values stand. `$1C38-$1C55` was `RowCurveOffsetAlt`'s tail, written
  only by the walk tail this build strips (rom:E9BE) and read only by
  rom:EA38's copy into zero page, which nothing reads. A write tap over a
  whole two-player race saw no writes after boot.

### Wrong turns

- **V1: no road at all.** VbTail called `sub_DC4F` itself, as stock's tail
  does, but this build retargets that `JSR` (rom:F16B) to MirrorStage, which
  draws the road for both views. The palettes and DLI chain were fine; the
  chain trace (idx 7-12 every frame) ruled them out. VbTail now jumps into the
  stock tail rather than copying it.
- **V2: a torn player 2 view** about one frame in 24 (bands broken into
  slabs). The first guess was the timing of the object rebuild; the 12/40-line
  alternation of player 2's staging writes turned out to be the same in
  checkpoint 71, so it was not new.
- **V4 moved the six-frame counter** (`$B8`, rom:F145) into VbTail so the
  stock curve copy (rom:EA2C) could not straddle it. That halved the overlaps
  (37 -> 17 of 2,000), but `$B8` stays 0 for a whole frame, so a late copy
  still met VbTail. V5 gated the copy with a "late" flag instead. Then it
  emerged that the copy moves nothing live any more (the strip stopped its
  source being written), and the real race was P2Tick's own output. V6 gated
  P2Tick's start: no better, because it starts before 176 and runs past 232,
  and the waits cost 26 ticks. Both gates were removed for the staging above.
- **V3-V8: `ObjWait`**, a vblank requirement added at rom:E709 (the rebuild's
  `$E5` wait). It livelocked qualifying on 0923-0205 from f4656: the tail
  ends after vblank, the next frame's first DLI sets `$E5` again, and the
  main loop never saw both conditions at once. Removed; `$E5` alone gives
  checkpoint 71's rebuild timing. V8 still locked with VbTail waiting for
  vblank: the tail, now a little longer, always ran past idx7 (line 16),
  which re-set `$E5` before the main loop resumed. Checkpoint 71 got through
  on every other frame only because its tail alternated between ending at
  line 12 and line 40. Dropping the wait (V9) fixed it: the rebuild now runs
  on every tick (102 rebuilds in 600 frames, against 53).

### Checked

- tick rate 100/600 (stock 100, checkpoint 71 53); rebuild every tick;
- no tearing in 24-frame bursts at qualifying, the race start and two race
  points, including a crash and the start line under player 1;
- state flow on all four recordings. They drift (the game now runs at a
  different speed from the recordings) but play through qualifying, races,
  game over and the attract demo, with health the same shape as checkpoint 71;
  0923-0205, which locked on V3-V8, now plays through;
- integrity 0 on four recordings;
- scripted flows: player 1 out of time with player 2 finishing, and player 2
  racing alone, unchanged.

Still on the table for speed: `sub_E8AC` stages all 78 rows of
`RowCurveYStaged` in the interrupt (~8% of samples) where this build reads a
few, and the stock object pass (rom:CE40, 8.5%).

## Player 2's cars-passed bonus

Checkpoint 73.

**Stock** (rom:C9F0-CA90, once a tick in the object move): a rival car (type 0),
not the crash slot, whose distance was `$0000-$1FFF` ahead before the move
and is negative after, adds one (BCD) to `$9E/$9F`. rom:D08F clears the count
at race start. At the end of the race, rom:D32D/DB40 tally 50 points a car
(state `$08`), after a clock-out as well as after the finish.

**Player 2** (`P2Pass`, from `P2RaceTick`, once a racing tick): the same
rule in player 2's frame, a car's distance plus the gap. A 16-bit mask holds
"ahead within `$2000`" per slot; a car whose bit was set and is now behind
counts. Not while the gap is pinned (it no longer says where the cars are),
and not player 2's own crash car. At its finish or time-out (`P2PayCars`),
50 a car goes straight onto its score, as its time bonus does. The count and
mask are cleared in `P2RaceGo`, as rom:D08F clears player 1's.

*Wrong turn:* C1 walked all 16 slots. Unused slots keep stale distances, and
since player 2's distance includes the gap, a stale slot drifts across 0 as
the gap moves: a false pass (seen: mask bits for slots 9-14 set all race).
C2 walks the object list from `$AE`, as rom:C9F0 does, and rebuilds the mask
each tick, so a slot off the list always starts clear.

Checked (scripted race, both at 240): player 2 29 passes to player 1's 38
(player 2 3,000-4,000 behind and crashing more); at its time-out the score
rose by exactly 1,450 (29 × 50). Race tick rate unchanged at 100/600.

## Cleanup: the pre-race views, player 1's car colour, sitting out

Checkpoint 74. Compared frame for frame with the stock ROM through the
pre-race states (`tools/probe-state-snaps.lua`: snapshots 2, 20 and 60 frames
into every state):

**Player 2's view before the banners.** Stock draws each scene once, on
entering state `$06` (rom:D994, qualifying) and `$07` (rom:D64E, the race
grid), through rom:D8AC. Player 2 was placed only at the banners (`$10`,
`$11`), and its view is built by P2Tick on the race tick, which those states
do not run. So through `$06`, `$07` and `$05` player 2's view showed whatever
it last showed: a curve from the attract demo, or where it parked after
qualifying. Now:
- rom:D8BC, sub_D8AC's `JSR sub_E93D`, calls P2Tick, which makes that call
  first and then runs player 2's drive and geometry;
- the state watch sets player 2 up at `$06` (as at `$10`) and `$07` (as at
  `$11`) as well. The banners set it up again, as before.

Player 2's view now shows the start at `$06`, the two cars side by side
through `$04`, and the race grid with its cars through `$07` and `$05`.
Player 2's score now clears at `$06`, as rom:D9BB clears player 1's.

**Player 1's car went green** in `$06` and `$07`, while the PREPARE banner
scrolls; stock keeps it yellow. The cars' palettes (P6 `$2F $26 $00`, P7
`$0F`) were set for the road by the injection itself (rom:EDC1-EDCB,
rom:EDE2-EDEC). With the injection bypassed, player 1's car had been relying
on the values MirrorPalette sets for the top view lasting all frame. The
divider's copy of stock's start-light code (rom:ECDC-ED1A) loads L_ECF8's
P6/P7 in `$06`/`$07`: in stock that runs every frame at the top, in the copy
only in those two states, just above player 1's road. RoadTail, which stands
in for the injection, now sets P6/P7 as the injection did.

**Player 1 sitting out** (checkpoint 71's notes): the 1UP line shows no clock
(it was frozen at the race-start value), and player 1's cars-passed count is
cleared before rom:D32D, so a race player 1 sat out ends straight in game
over with no `$08` tally (it had been credited one car, 50 points).

Checked: the pre-race states against stock; the sit-out race (1UP clock
blank, player 1's score unchanged at the end, game over without `$08`);
health, state flow, integrity (0 on four) and race tick rate (100/600) the
same as checkpoint 72.

## Headroom, after checkpoint 74

**CPU** (race profile, both cars at 240 with traffic, two windows): the main
loop spends about 20% of its visible-frame samples waiting, at rom:EA28 (the
six-frame slot, 9-14%) and rom:E709 (the rebuild's `$E5`, 5-10%). A tick
finishes with roughly a frame of its six to spare. The biggest real costs:

| where | share | what |
|---|---|---|
| rom:CE40 | 15-18% | stock object pass (inside rom:C9AD) |
| rom:E8AC (E8E6, E8FF, E915) | ~8% | stripe staging, all 78 rows of `RowCurveYStaged`, in the interrupt; this build reads only the sampled rows |
| P2Geom (P2GSteps) | ~5% | player 2's road walk |
| rom:E93D (E9A2, E9E6, ...) | ~7% | player 1's road walk |
| rom:EA2C | ~1.5% | the stock curve copy, now pure waste (below) |

**ROM:** the new code area (`$4000-$7FDF`) has 11,060 bytes free (5,292
used); the `$F400` blob has 359 free; the reclaimed injection (`$EDA0-$F142`)
holds the templates.

**RAM:** the mod's own area (`$2600-$27FF`) is full to the byte. What can be
had:
- `$1B00-$1B4D` (`RowCurveXStaged`, 78 bytes), `$1B9C-$1BE9`
  (`RowCurveXStagedSrc`, 78) and zero page `$60-$7D` (30). Their only users are
  now the walk tail this build strips (rom:E9D3), the stock copy rom:EA2C-EA3C
  (which copies the never-written source into the other two), and the dead
  injection. Retiring the copy frees all three and its CPU.
- `$1C53-$1C55`, the rest of the stripped `RowCurveOffsetAlt` tail past the
  staging copies.

## Cleanup: player 1's skyline in the track's colours

Checkpoint 75. Compared with the stock ROM on all four tracks, row by row
through the horizon (dominant colours per scanline):

- **The decor drew in the cars' colours.** The horizon decor (zone 19:
  mountains, hills, trees) draws in P6/P7, which stock's L_ECF8 (rom:ECF8)
  loads every frame from the track's `$F4-$F9`. The divider's copy of that
  code had the load inside the start-light tint's `$06/$07` branch. So outside
  those states the decor kept whatever P6/P7 held, the cars' colours from
  MirrorPalette: white trees on track 3, white snow on track 1's mountains.
  The load now runs every frame, as stock's does.
- **The horizon's last lines.** RoadTail stands in for the injection, whose
  first lines stock times after DLI_ED4F's palette block: two lines on,
  `BACKGRND` = `$FA` (the track's horizon colour: the water line on track 2);
  two more, `BACKGRND` = `$FB` (the ground) and the cars' P7 (rom:EDAD-EDCB);
  then P6. RoadTail wrote the ground and the cars' palettes at once, so the
  water line never showed. After checkpoint 74 the early P7 also turned the
  decor's bottom three rows white; they still draw in the track's P7. RoadTail
  now keeps stock's line timing (four `WSYNC`s).

Checked: all four tracks' horizon rows match stock (differences only where
the decor has scrolled to a different heading); player 1's car stays yellow
under the PREPARE banner; race tick rate still 100/600.

## RAM: a coverage map, and 530 bytes freed

Checkpoint 76. `tools/probe-ram-coverage.lua` counts every read and write per
address after frame 600, over `$1800-$27FF` plus the zero-page and stack
mirrors (`$0040-$00FF` = `$2040-$20FF`, `$0140-$01FF` = `$2140-$21FF`). Taps
see MARIA's DMA reads (the DLL at `$2500`: about 88,000 reads over 30,000
frames), so display lists count as used. Runs: a two-player scripted game
(qualifying, race, game over, attract) and three recordings (run-03 covers
all four tracks, 0923-0205 the attract demo).

1,013 bytes were never read. One trap: the 6502's indexed stores (`STA
abs,X`, `STA zp,X`) make a dummy read of their target, so an array written
by one and never read shows exactly as many "reads" as writes. That is how
`RowCurveXStaged` and zero page `$60-$7D` looked read.

**Freed by patching out the injection's last feeders**, whose outputs only
the bypassed injection read:
- rom:EA2C `StageRowCurveForDLI` copied `RowCurveXStagedSrc` (never written
  since the walk-tail strip) into `RowCurveXStaged` and zero page `$60-$7D`:
  now `RTS`. That also saves its time on every tick.
- sub_E8AC's `STA $4E,X` for X ≥ `$30` (rom:E8F8, the odd-frame copy;
  rom:E90E; rom:E935, the stripe fill): per-row colours for zero page
  `$7E-$9B`, now `NOP`s. The first attempt missed rom:E8F8; a write tap on
  the range found it (zero writers after).

**Free, as `FREE_RAM` in the patch** (the build refuses any region that
overlaps one):

| range | bytes | |
|---|---|---|
| `$0060-$009B` | 60 | zero page, freed above |
| `$1B00-$1B4D` | 78 | `RowCurveXStaged`, freed above |
| `$1B9C-$1BE9` | 78 | `RowCurveXStagedSrc`, freed above |
| `$1FF3-$203F` | 77 | never touched |
| `$210F-$213F` | 49 | never touched, below the stack's reach |
| `$2200-$2233` | 52 | stock's race DLL, replaced by `DLL_BASE`; never touched |
| `$2566-$25FF` | 154 | past `DLL_BASE`'s 34 zones; never touched |

That is 548 bytes, 60 of them zero page. Smaller scraps not listed: the stack
page's unused depth (`$2140-$21D6`, keep a margin); pieces of the stock race
DLL at `$2239-$226A`; and a few 10-30 byte tails in the object and decor
arrays (`$18CD`, `$18F0`, `$1973`, `$19E4-$19FF`, `$1CE7`, `$1D1C`, `$1D59`).

Checked: health identical to checkpoint 75 on four recordings (run-02 differs
in 6 single-frame samples); integrity 0 on four; race tick rate 100/600; no
writes to the freed ranges.

## Evaluated: back to 32K, and a skybox for player 2

### 32K

What the build occupies now: the new code area holds 5,292 bytes of code
(`$4000-$54AB`) plus the HUD row lists (`$7FE0-$7FF1`). Inside the original
32K it uses the reclaimed injection (about 108 bytes still free there), the
code blob (`$F400-$FE24`, 359 free) and 32 small patch sites.

What the original 32K could still give (`tools/probe-rom-coverage.lua`: every
cart byte read by CPU or MARIA once the cart's reset code runs; scripted
two-player games on all four tracks and six recordings): **1,602 bytes are
never read**, 1,079 of them in stretches of 16 or more, and 107 of those are
code. They are mostly sound pitch tables for sounds these runs never
triggered (`$E099-$E152`), 33-byte graphics page tails, a 112-byte table at
`$BC79`, and 108 bytes before the vectors (`$FF8E-$FFF9`). Some are surely
read in situations these runs do not reach, so this is an upper bound. With
the attract demo cut (~120 bytes) and the free space above, the original ROM
tops out at about **1.7K for 5.3K of code**.

Where the mod's 7.9K of code goes (new code area, then blob):

    qualifying + race 1,236   hazards/crashes 1,184   rival cars (p2 view) 918
    shared traffic      803   HUD               565   audio 229   vblank 138
    player 2 emitter    151   FastZRow           56   blob 2,597 (MirrorStage 273, ...)

Getting to 32K needs about 3.6K of this removed: 45%. Local tightening
(loops for unrolled blocks, shared helpers) might find 10-20%. The only route
that could reach 32K is structural: run player 2 through the stock routines
(physics, collision, crash, walk) by swapping its state into player 1's
variables and back, instead of keeping re-implementations. That is large,
touches everything, and costs a swap each way per tick. Recommendation: stay
at 48K; take local savings only when space is wanted.

### A skybox for player 2

MAME shows DLL lines 8-231 (the decor at DLL 135-144 lands at image rows
127-136); stock draws its content in 16-215. The current top:

    z0   0-15  blank, DLI idx7 (stock ECA1: sky palettes, decor P6/P7)
    z1  16-19  blank
    z2-13  20-91  player 2's road (12 x 6)
    z14 92-103  blank carrier, DLI idx9
    z15-17 104-124  HUD ...   (player 1's half unchanged below)

A 12-line sky (10-line decor, 2-line horizon) fits in the top slack, with
nothing below the HUD moving: z1's 4 lines and 8 of the carrier's 12. Player
2's sky at 16-27, its road at 28-99, the carrier at 100-103.

What it needs:
- **Palettes.** idx7 (stock ECA1) already loads the sky colours and the
  track's decor P6/P7 for the region below it, which is exactly the sky's
  need. A new DLI at the foot of the sky then switches to player 2's road:
  its horizon line (`$FA`), ground (`$FB`) and the cars' P6/P7, with
  MirrorPalette's road colours. The handler table now has room (checkpoint
  72 relocated it).
- **A second decor list**, built like `sub_DC4F`/`sub_DC89` build player 1's
  (zone 19's list at `$1D3B`) from the track's decor objects, but offset by
  player 2's heading. Player 2 needs its own heading accumulator, driven from
  its segment curvature and advance the way player 1's is. RAM: a list of
  about 40 bytes plus the accumulator, from `FREE_RAM`.
- **The carrier's DLI (idx9)** has to be checked for how many lines it
  needs before it can shrink to 4.
- **Risk:** the top of the sky (DLL 16) is where stock's own HUD started, so
  it is inside the area stock relies on being visible.

*Tabled (user's call):* the return to 32K stays at 48K for now; the
evaluation above is the reference for picking it up later.

## Player 2's skybox, turning with player 2

Checkpoint 77. Player 2's view now has its own horizon decor (mountains,
hills and water, trees, desert) above its road, turning with its own heading.

**How player 1's works** (stock):
- **Heading.** `$C9` (coarse, 0-`$77`, 120 units a turn), `$CA` (fine, 0-3) and
  `$CB` (accumulator). rom:DBDF, every other frame from `sub_DC4F`, adds
  Speed/2 × (|curvature|+3), signed by the curve of player 1's segment.
- **Lists.** rom:DC60 places the base object of zone 19's list (`$1D3B`) and
  the horizon object of zone 18's (`$18FA`) from per-track tables
  (`dat_A8C6/CA/D2`). rom:DC89 writes one 4-byte header per decor object in
  view (`$1C0E/$1C1C/$1C2A` per object, `$CC` the last), ending with a zero
  width. rom:DD0B gives each object's x (or `$A0`, out of view) from
  `$F0/$F1` and the heading alone. `$F0-$F2` and `$C9-$CB` are used by
  nothing else.

**Player 2's:**
- **Heading** `P2_HEAD`/`P2_HEADF`/`P2_HEADA` (zero page `$60-$62`, freed at
  checkpoint 76), advanced as rom:DBDF does from player 2's speed and segment.
  Before a start (`$04-$07`, `$10`, `$11`) it follows player 1's: rom:D8AC
  clears player 1's heading after player 2's set-up copied it, which left
  player 2's sky turned through `$07`/`$05`.
- **Lists** in freed RAM. The decor at `$1B00`, and a copy for the decor's
  top 8 lines at `$1B9C` with the graphics two pages up: MARIA counts a zone's
  graphics offset down from its height, so an 8-line zone needs the page 2
  higher to show the same rows. The horizon object's list is at `$1B30`. They
  are built with player 2's heading swapped into `$C9/$CA` for rom:DD0B, by
  `P2Sky` from VbSplit (line ~176): after player 2's sky has been drawn, and
  before VbTail's stock tail uses the same scratch.
- **Screen.** Three zones under zone 1: the horizon's bottom 2 lines (the
  tallest decor's tops, as zone 18 carries them for player 1), the decor's
  top 8, and its bottom 2. The 12 lines came from the carrier (12 → 6, its
  minimum) and the first bottom margin (16 → 10). Player 2's road starts 12
  lines lower, and the HUD and player 1's half 6 lines lower.
- **Palettes.** DLI_ECA1 (index 7) already leaves the sky's palettes: `$89`,
  and L_ECF8's track decor P6/P7, exactly what the sky needs. Its closing
  jump (rom:ED29) now goes to `SkyHold`, which points the chain at a new
  index 13. `P2SkyEnd`, on the decor's last 2 lines, sets the horizon colour
  (`$FA`, the water line on track 2) and goes on into MirrorPalette (the road,
  the cars, the ground `$FB`), handing the chain back to index 8. The DLI
  handler tables moved into the blob to reach it.

### Wrong turns

- **One 10-line decor zone** with the DLI on it needed nine `WSYNC` lines to
  reach the horizon line. Together with P2Sky that tipped the race tick to 74
  of 100: each alone left it at 97-100, so the main loop was right at its
  six-frame edge. Splitting the decor (8 + 2) puts the DLI where the horizon
  line starts; one `WSYNC`, and the rate is back to 98-101.
- **Calibration:** the horizon line landed two rows early (7 lines), then
  covered the right rows but spilled two rows into the road (9 + 2), before
  matching (9 + 0, then 1 + 0 on the split zone).

Checked: player 2's sky matches player 1's row for row on all four tracks
(both dominant colours per scanline; the one exception, a row on track 1, is
the mountains scrolled to a different point). The headings match before the
start and turn independently in the race; the decor visibly shifts through a
turn. Banner, start light, HUD and the qualifying message are all in place in
the moved divider. Health and state flow are identical in shape to
checkpoint 76 on four recordings; integrity 0 on four; race tick rate
98-101/600.

*Decided (user):* thinner traffic for a player far behind stays as it is,
as a feature: with the gap pinned past `$4000`, the trailing player 2 sees no
rival cars until it closes up.

## Player 2's qualifying result on screen

Checkpoint 78. While the game shows its qualifying message (states `$12`,
`$0E`), the divider's three rows are the message (`$1D09`, text at `$1FC8`,
player 1's place blinked in by rom:DA03), a blank middle row (`$24F6`) and the
bonus tally (`$1D15`). The middle row now says where the other player stands:

    2UP POSITION n       both qualified (n is player 2's place)
    2UP NOT QUALIFIED    player 2 sits the race out
    1UP NOT QUALIFIED    player 1 sits it out (the message above is player 2's)

`QMsg`, once a frame from VbSplit (after the divider has been drawn), points
the middle zone at its own 31-character line (`QM_BUF`/`QM_DL`, in the
never-touched RAM at `$1FF3`). It saves the zone's own entry on the way in and
puts it back once the state moves on. The text uses the game's font; its
letters decode from the message itself (Q = `$A4`, R = `$A5`, Y = `$AA`).

Checked: all three cases on screen; the banner at `$07` and the HUD in the
race are back afterwards.

*Wrong turn, reported in play:* the race banner and the start lights showed
only their top halves after checkpoint 78. The race's set-up (`$07`) points
the divider's middle row at the banner's lower half before QMsg sees the
state change, and QMsg then put its saved blank back over it. It now restores
the row only while the row still points at its own line. Checked against the
build before (whole) and Q1 (top halves): Q2 shows both whole.

## The two-player result at game over

Checkpoint 79. At game over (`$0D`, `$0A`) the divider shows the game's
message on its top row and nothing below (the bonus screens `$0F`/`$08` use
the same layout: text, then an 8-cell tally row in the bold read mode). The
middle row now carries both final scores:

    1UP  75550           2UP  40110

The higher score's label and digits blink, on `$B9` bit 3 as rom:DA0B blinks
a qualifying place; a tie blinks neither. The font has no W (it has V `$B4`
and X `$A9`), so blinking replaces a "WINS". The line is rebuilt every
frame by `QMsg` (the same row and save/restore as the qualifying result),
from `$1CA5-$1CA7` and `P2_SCORE`, six BCD digits each with leading zeros
blanked. The winner is the higher final score, bonuses included.

*Not a bug, recorded because it cost a run:* a test run sat in state `$13`,
the game's pause (rom:D743: a falling edge on SWCHB bit 3), from qualifying
to the end. Re-running the same script on six builds never paused. MAME's
window had keyboard focus while chat was being typed. Test runs now pass
`-keyboardprovider none`.

Checked: player 1 winning (its block blinks) and player 2 winning (a race
player 1 sat out; its block blinks), in both blink phases.

## Qualifying ties, tested live, and the one for 8th fixed

Checkpoint 80 (asked: does the faster player get a shared slot?). QualHold
(rom:D422) has always settled a shared slot by lap time: the faster keeps it,
the slower goes one place back, and a dead heat goes to player 1. What
checkpoint 69 did not test live, and got wrong: both 8th with player 2 faster.
Player 1 cannot go to 9th on that path, so the code put player 2 out instead,
the faster player losing the place. Since checkpoint 71 a player 1 that does
not qualify can sit out, so QualHold now hands that case to the same path
(QualOut's body, `QoAloneGo`): player 2 keeps 8th, player 1 sits out, player
2 races alone.

Checked, scripted pairs on track 3 (slots: under 58.50, 60, 62, 64, 66, 68,
70, 73):

| p1, p2 speed | laps (p1 / p2) | slot | result |
|---|---|---|---|
| 201, 200 | 68.00 / 69.00 | both 7 | p1 7th, p2 8th |
| 198, 200 | 69.37 / 68.79 | both 7 | p2 7th, p1 8th |
| 195, 198 | 70.00 / 72.37 | both 8 | p1 8th, p2 out (sits out) |
| 189, 190 | 72.37 / 70.79 | both 8 | p2 8th, p1 out: the race starts with player 2 alone. Before this, p2 was out. |

## Race position on the HUD, and sub_E8AC down to the rows anything reads

Checkpoint 81.

**1ST / 2ND.** Each HUD line was 31 characters, the most one text object can
hold. The row lists (still in ROM, `$7FE0`/`$7FEC`/`$7FF8`) now carry a second
3-character object per line (`HUD_POS2`/`HUD_POS1`, RAM `$2021-$2026`), and
the pair is re-centred (x 10, 35 characters). HudFill writes the positions
while both players are racing (`$03`, `$0C`, `$09`; not when one sits out):
more laps first (`$A7` against player 2's count, which start equal), then the
gap's sign (positive: player 1 ahead). Blank otherwise. Checked: player 1
ahead ("2ND" on 2UP, "1ST" on 1UP) and player 2 ahead; nothing in
qualifying.

**The tick rate slipped to 89**, in the build after checkpoint 78, whose new
code never runs in a race. What changed was ~200 bytes of layout in the code
area (page crossings in hot loops). With both cars at 240 and traffic, the
main loop had almost nothing left of its six-frame slot, so shuffling code
tipped ticks over. Real headroom was needed, not cycle-chasing.

**sub_E8AC, trimmed.** On odd frames it rebuilds all 78 rows of
`RowCurveYStaged` (about 2,000 cycles, inside DLI idx11): rows `$4D-$3C` as
texture `$1F00[CD + dat_C07E[row]] + $B6` ORed with `$1F3C[row]`, the rest
without `$B6`, then `$E0` into rows between `$E6` and `$E7` (the sign stripe;
`$E7` = `$FF` meaning down to row 0). The bypassed injection read them all;
this build reads 13, each band's sample row (road_stage_src). rom:E8E6 now
jumps to `E8Lite`, which computes exactly those 13 with the same arithmetic.
The header (the texture phase `$AF`/`$CD` and the pointer) stays stock.
`E8Lite` has its own scratch (zero page `$65-$66`): it runs in the
interrupt, and borrowing the main loop's scratch would corrupt it.

*Checked exact:* a probe recomputes the 13 rows from the same inputs each
time the routine returns (rom:F15D): 74,087 rows over two 12,000-frame
races, with 3-5 rare disagreements. The full stock routine, run under the
same probe, shows the same kind (0 and 3), so they are the probe's timing,
not E8Lite. Race tick rate back to 97/600; health and state flow as before
on four recordings; integrity 0 on four.

*Test harness:* MAME now runs with `-keyboardprovider none` everywhere,
including `run.sh` (see checkpoint 79's pause).

## Player 2's car: the top slice, and a colour experiment that hit the start line

Checkpoint 82. *Reported:* player 2's car was clipped at the top in its view.
Player 1's car spans five bands: its top slice (the roll hoop and helmet,
graphics page `$A3` + lean) sits in band 7, above the four bands (8-11)
copied into player 2's lists. *Correction to "Player 2's car":* that
section found the car in bands 8 to 11 by sampling slot `+1C` of the near
bands, the slot band 7 does not use. The later section on the other
player's car had the five pages `$A3 $9D $97 $91 $8B` across bands 7 to
11, but player 2's own car was never revisited. Player 2's car now takes
a slot in band 7 too (`P2_CAR_BANDS` 7-11, seed `$10`/`$A3`, base page `$A3`),
and the lean moves it like the others. On screen the two cars now match.

The extra slot pushes bands 7-12 of player 2's lists 4 bytes on, and the block
(now `$2600-$26FF`, all 256 bytes the one-byte offsets reach) ran over player
2's qualifying bytes at `$26FC-$2701`. Those six moved to free RAM at
`$2027-$202C` (`FREE_RAM`'s "untouched" run now starts at `$202D`).

*Wrong turn, caught by the test:* the list integrity probe first reported
thousands of frames with a zeroed road header. Its header list was the
old one; regenerated from `p2_band_layout()` (bands 8-12 at `$2684`,
`$269E`, `$26B8`, `$26D2`, `$26EC`) it reports 0 on four recordings.
Health and state flow unchanged; qualifying ties as checkpoint 80; player 2
alone finishes; race tick rate 99-101/100.

**Player colours: tried, reverted.** The idea was for each player's car to
get its own colour. The cars use palette 6 (`$2F $26 $00`, the gold car;
crash frames too, rom:ADB6). The experiment gave player 2's car palette 7,
which looked free in the race. It is not: palette 7 is white (`$0F` x3) and
draws the start/finish line and the sign stripes (sub_E8AC's `$E0` ORs the
row to palette 7) and the crash smoke. The user saw the start line change
with the car. No palette is spare in the road regions: 0-1 road, 2 road
pieces and wrecks, 3-5 rivals and signs, 6 the cars, 7 white. Any per-player
colour has to share palette 6, by view or by band (a decision for the
user).

### Player colours through 160B (evaluated, not built)

Asked: would converting the car to 160B help? Yes. It is the one route that
needs no palette register. In 160B each pixel carries two palette bits of
its own. The header picks the group (palettes 0-3 or 4-7), the pixel picks
one of the four. A 160B car in the 4-7 group can use any colour already
loaded there. A write tap on the palette registers over two recordings found
the road region's palettes constant in the race:

    P4 $0E $98 $00   P5 $9C $96 $00   P6 $2F $26 $00 (car)   P7 $0F x3

So a blue car (`$9C` for the car's `$2F`, `$96` or `$98` for its `$26`,
black kept) changes nothing else on screen. Group 0-3 offers `$89/$8B/$8D`
and `$1E/$17`, but palettes 0-1 are the road's.

What it takes:

- **Graphics.** 160B is 2 pixels a byte, so the 8-byte car slice becomes 16
  bytes. There are 5 leans x 6 band sheets (bands 7, 8, 9, 11 and band 10's
  two wheel frames) x 6 lines x 16 bytes = 2,880 bytes. That fits in the free
  new code area (`$4000-$7FDF`). The lean offsets double (0, `$10` ... `$40`).
- **Headers.** 160B needs the write-mode bit, so each band's car slot gets a
  5-byte header. Player 2's lists are exactly 256 bytes, so the extra bytes
  need room.
- **Player 1's view.** Player 1's lists need the same 5-byte slot where
  player 2's car appears (the other-car slot and its distant sprite).
- **DMA.** About 8 more bytes a line over roughly 30 lines: a few hundred CPU
  cycles a frame, on a race loop close to its limit, so measure it.
- **Not covered.** The crash and spin frames stay gold unless those are
  converted too.

### Player colours: borrowing a rival palette (built as a switch)

The simpler answer came from the user's overlay idea. The car's three
colours are light, mid and black (`$2F $26 $00`). Palettes 4 and 5 have the
same shape: `$0E $98 $00` and `$9C $96 $00`. Drawing the stock 160A car with
one of them recolours it, shading kept, with no new graphics and no palette
register touched. `PP2_P2PAL` (default 6, stock) sets player 2's car
palette in both places it is drawn: its own lists (`P2_CAR_W`) and player
1's view (`OC_PW` after the first `OcSprite`). Crash frames keep palette 6.
Checked on screen in a two-player race: palette 5 gives a light blue and blue
car, palette 4 white and blue, in both views. The start line, signs and
rivals are unchanged.

*The catch:* the rival cars use the same sprite in palettes 3 (yellow `$1E
$17`), 4 (white) and 5 (blue). A borrowed palette makes player 2 look like
one colour of rival. In its own view that does not matter, since the car at
the bottom centre is always the player's. In player 1's view it does.

**Overlay (the user's idea), costed.** Draw a second 160A object over the
gold car, in palette 4 or 5, carrying only highlight pixels: a stripe, a
number. Gold with blue is a combination no rival has.

- **Graphics.** Overlay pages for each lean and band that has highlights:
  8 bytes x 6 lines per lean per band. That is 1,440 bytes for all 5 leans x
  6 sheets, or about 480 for a stripe on bands 8-9 only.
- **Display lists.** A 4-byte header per overlaid band in player 2's lists,
  which are full at 256 bytes. In player 1's view the other car goes through
  the rival emitter at 10+ sizes, so an overlay there needs its own slot and
  graphics per size. Near sizes only is practical.
- **DMA.** 8 bytes a line on each overlaid band, plus the header.

## Player 2's highlights: a second sprite over the car

Checkpoint 83. The user's idea: overlay another 160A sprite on player 2's car
in another palette, highlights only, on the top section. **Design credit:
Defender_2600 (AtariAge)**, whose mock-up set the look: blue wing and
sidepods, a white bar across the wing with white ends and centre, a yellow
helmet. The helmet is the car's own light gold (`$2F`) showing through; the
overlay is palette 4 (`$0E` white, `$98` blue), constant in both views'
road regions, so no palette register changes.

**The sprite is one column.** The player car (and a rival at size 0) is a
single 30-page column, `$8B-$A8`: line L up from the bottom of band 11 is
page `$8B + L`, six a band, and the lean or viewing angle picks the low byte
(`$00-$20`, eight apart). The highlights sit on lines 14-19 only: band 9's
top four lines and band 8's bottom two. The highlight column is built the
same way. Pages `$75-$7A` hold lines 14-19, with five zero pages either side
(`$70-$7F`, low bytes `$00-$27`). Whichever six lines a band shows, the rows
past the highlights then read blank; the new code area's `$FF` fill would
not. `EXT_END` moves to `$6FFF`.

**Player 2's view.** Bands 8 and 9 of player 2's lists get a header after
the car (drawn over it): page `$79` for band 8 and `$73` for band 9, which
lines their bottom lines up with car lines 18 and 12. The low byte is
player 2's lean. They park with the car (a crash, or out of the race). The
8 bytes come from the object slots: over four recordings, no near band ever
held three objects, and bands 9-12 held two in under 0.1% of frames. Those
bands now have two slots, so the lists are 248 bytes (headers at `$2684`,
`$26A2`, `$26BC`, `$26D2`, `$26E8` for bands 8-12). Parking, the list
build and the emitter's cap take per-band counts (`P2ObjCap`, and
`P2BuildLists` computes the count inline: it assembles apart from the
table).

**Player 1's view.** Player 2's car is an entry in the game's own object
list, sliced into bands by the stock emitter. The highlights are a second
entry: rows `ROW-14` to `ROW-19`, page `$75`, the car's angle as the low
byte, palette 4. They are added only at size 0 (the car's own pages) and
not while player 2 crashes. The entry goes in *before* the car's, because
the emitter works from the last entry and hands out slots in order. The car
takes the earlier slot and the highlights the next, so they draw on top.

*Checked:* on screen in both views, including player 2 alongside player 1
at an angle, where the highlights follow the angled frame. The green seen
inside the helmet in one shot is the grass behind the car: the roll hoop's
inside is transparent in the stock sprite too. Health matches checkpoint 82
on four recordings, list integrity is 0 on four, qualifying ties are as
before, and player 2 alone finishes. Race tick rate is 99, 101, 99, 94, 98
and 100 over six starts against 96, 99, 99, 98, 98 and 100 without the
highlights. That is the same within the test's noise (one early reading of
94 alone looked like a cost).

*Not covered:* sizes 1-5 (player 2 further ahead of player 1) have no
highlights, and there player 2 still looks like a gold rival. Combined with
the higher-detail car (graphics hack), which redraws the upright frame
`$8B10`, the highlights are derived from the stock car and misalign on that
frame. (*Corrected later:* this was inferred, not tested. The two builds do
not stack at all, because the hack's palette bytes are in the reclaimed
injection. See "The .abp bundle grows the cartridge".) `PP2_NO_OVL=1` builds without them. `PP2_NO_OVL_P1` (test hook)
leaves out player 1's view only.

## Player 2's bonuses, tallied with player 1's

Checkpoint 84. Until now player 2's time bonus and cars-passed bonus went
straight onto its score at its finish. Player 1's are tallied on screen.

**Stock tally.** At the finish, rom:D4C5 puts the message up, takes the
seconds left (`$DF`, the clock's low byte) into `$AC` and enters state `$0F`.
Every 18 passes (`$C5`, reset by rom:DB7C), rom:D69E takes one off `$AC`
and adds 4 x 50. The bold row shows `200 x SS` (`$1FEB-$1FF2`). At zero
(rom:D6DF), rom:DB40 puts up PASSING BONUS. If there are cars (`$9E/$9F`,
rom:DB55), state `$08` counts `$AB/$AC` down, 50 a step, showing `50 x NNN`.
Then game over (rom:D5CD, rom:D316). Player 1 out of time goes through
rom:D32D: the cars tally or game over, with no time bonus. The finish also
rounds the score (rom:D478); the time-out path does not.

**Built.**
- **Kept, not paid.** Player 2's finish stores its seconds in `P2_TBS`
  (`$202D`, the clock's low byte, as rom:D4E7 takes player 1's). Its time-out
  no longer pays the cars; they stay in `P2_PASSN`. Both are cleared at a
  new session.
- **Counted together.** `TallyT` at rom:D6A9 and `TallyC` at rom:D58D run
  player 2's step in the same beat, 200 or 50 onto `P2_SCORE`, and player
  1's step only while it has any left. The state lasts until both are empty.
- **Reached from every end.** `TallyCars` at rom:DB55 also checks player
  2's cars. `TallyEnd` at rom:D32D (player 1 out of time, or sat out) goes
  to the `$0F` tally when player 2 has seconds. It sets that up as rom:D4C5
  does, but without rom:D478's rounding, and with player 1's seconds at 0.
  Otherwise it goes to the cars tally if either player has cars, else game
  over.
- **A fallback.** `TallyFlush` at rom:D316 (game over) pays anything still
  pending outright. No path found leaves any.
- **On screen.** The divider's middle row shows both counts: `1UP 200x07` at
  the left edge, `2UP 200x00` at the right, with the game's message and bold
  row centred between them. Player 1's block is left out when it sat out, and
  the row is only taken when player 2 raced. The first version was one
  31-cell line; its 2UP block butted against TIME BONUS and PASSING BONUS in
  the row above. The row is now two ten-cell objects (`QmSplit`, a constant
  list in ROM), and the game-over result uses the same split.

*Checked* (scripted, both player 2 and player 1 end cases):

    race                    tally                      paid
    both race, p2 out of time  1UP 9 s, 59 cars; 2UP 29 cars   +1,800 +2,950; +1,450
    p1 out of time, p2 done    2UP 23 s; 1UP 3, 2UP 4 cars     +4,600; +150, +200
    p1 sat out, p2 done        2UP 29 s, 1 car                 +5,800, +50; 1UP unchanged
    p2 out of time, p1 done    1UP 5 s, 83 cars; 2UP 2 cars    +1,000 +4,150; +100

Each state lasted as long as the longer count needed (e.g. `$08` ran on past
player 1's 3 cars for player 2's 4). Health matches checkpoint 83 on four
recordings, list integrity is 0 on four, qualifying ties are as before, and
race tick rate is 100, 98, 98, 99, 97 and 100.

*A behaviour change:* player 2's time bonus used to be 200 x the whole clock,
hundreds included. It is now the seconds byte, as player 1's has always been.

*Wrong turn:* the first build failed with a branch 322 bytes out of range.
A new label `QmT2` matched an existing text label of the same name. The
toolkit's assembler takes a label defined twice without complaint, so the
branch resolved to the other one. `_assemble` now refuses duplicate labels.

## Curve smoothing, re-evaluated: a cheaper way back (not built)

Asked: the stock smoothing came out for its cost. Is there a cheaper one that
spends the free ROM instead?

**What was removed.** `DLI_InjectRowCurveX` rewrote each road band's x (and
width) on every scanline, one `WSYNC` a line: 78-97 stalled lines a frame,
the frame's largest consumer. Since checkpoint 6 (`06-no-injection`) each band has
one x and one width for its six lines, in both views, so an edge that slopes
steps once a band.

**How big the steps are** (`tools/probe-band-slopes.lua`: player 1's
`RowCurveOffset` over a band's six rows, every 6th frame of three recordings,
3,647 samples):

    band            1   2   3   4   5   6   7   8   9  10  11  12
    median (5 rows) 3   3   2   2   3   3   3   3   3   3   3   3
    90th pct       13  11  10   9   8   8   8   7   7   7   7   7
    max            27  21  19  16  14  13  12  10  10   9   9   9

Units are 160-mode pixels over five rows. Perspective contributes as well
as curves: an edge slopes whenever the car is off-centre, so the stair shows
on straights too. A typical step is about 4 px at a band edge, 8-10 on a
bend, and up to 20 near the horizon.

**Options.**

1. **Pre-sheared road slices (recommended to try).** Keep one x per band, and
   draw the band from a variant of its road graphics whose six lines are
   already offset by s pixels a line (s = the band's slope, rounded and
   clamped). The x is adjusted for the variant's padding. The CPU cost is a
   lookup per band per view. It changes only with the track walk (10 Hz), so
   it can live in the main loop, with no `WSYNC` and no extra zones. Both
   views share the graphics.
   - *ROM.* One set of slices is 339 bytes a line (bands 1-7: 8, 12, 16, 20,
     22, 26, 30; bands 8-12: 16 + 19, 21, 25, 29, 31), about 2K. With s = +/-1
     each object needs a byte of padding each side, so 375 bytes a line. Two
     variants (+1, -1) are 750 bytes a line in 6-page columns, about 4.5K.
     The free ROM holds that: 5,443 bytes after the code ($5ABD-$6FFF, 21 whole
     pages, three columns), plus the low bytes $28-$FF of the highlight pages
     $70-$7F (two more 216-byte columns). The narrow far bands (1-4) could
     take +/-2 and +/-3 as well for a few hundred bytes more.
   - *What it buys.* Residual step = 6 x |slope - s|. On a typical band it
     drops from ~4 px to ~1; on the 90th percentile of a bend, from 8-10 to
     about 2-4. The horizon's worst bends (up to 6 px a row) stay stepped.
   - *Costs to measure.* MARIA reads two more bytes per road object per line
     on a sheared band, a few hundred CPU cycles a frame. Crowded near lines
     could hit MARIA's per-line DMA limit. Band 12's right piece is already
     31 bytes, the maximum width, so its shear would have to clip a byte at
     its outer end.
   - *Player 2.* Its walk samples one row per band, so its slope is the
     difference between neighbouring bands' samples, divided by 6. The
     double-integrated curve is smooth enough for that.
2. **Half-height zones (3-line bands).** This halves the step exactly. But
   every object in a band (cars, signs) must then be in both halves' lists,
   the top half's with its page raised by 3. That is about 780 more bytes of
   display list RAM across both views, against about 500 free and in pieces.
   Rejected on RAM, not CPU.
3. **Per-scanline writes by display interrupt instead of `WSYNC`.** A zone's
   graphics page counts down from its own height. So sub-zones of a band
   cannot share one list without every header's page being rewritten.
   Rejected.
4. **Stock injection on a few bands only.** The cost is per scanline
   stalled, so any useful share of the 78 lines is back to what was removed.
   Rejected.

**Suggested first step, if wanted:** a prototype of option 1 for player 1's
near bands (7-12), s = +/-1 only, about 1.7K of ROM. Measure the tick rate
and look for DMA overruns before committing the rest.

## The title logo: II becomes VS

Checkpoint 85. The title's logo is palette 0 (1 black letters, 2 grey
pennants, 3 blue stripe) in objects of a title list at `$226B`. The II is
one 4-byte (16 px) object at x 136 in four zones: `$A5D6` (5 lines), `$B00E`
(10), `$B00A` (10) and `$A5DA` (5). Its pennant is larger than the other
letters' and runs lower. The II is serif bars top and bottom with two 2-pixel
stems.

The pennant is kept. The II's black is filled back in grey, or blue on the
stripe's diagonal, and V (7 px) and S (5 px) are drawn in black with 2-pixel
strokes, as the logo's own letters are. There are 20 rows of 4 bytes in
`TITLE_VS`, each put with its stock bytes as the expected value;
`PP2_NO_VS=1` leaves the II. It shows in both of the logo's colour phases.

*Only the title reads them.* A read tap over those 80 bytes through two
whole recordings saw reads in state `$00`, plus a few frames of `$01` and
`$06` while the title was still on screen. X1 differs from checkpoint 84's
build in 68 bytes, all in pages `$A5` and `$B0-$B9`.

*Probe trap:* the first run of that tap logged nothing at all. The taps were
held in a Lua local that nothing referenced after set-up, so they were
garbage-collected. Keep tap handles in a global, as
`tools/probe-rom-coverage.lua` does.

## Far-band smoothing: sheared road slices, bands 1-5

Checkpoint 86. The user's call: the far bands looked worst ("outright
disconnected" on sharp turns), and their slices are narrow, so start there.

**What each band draws.** Band b's six lines are pages `hi+5` (top) to `hi`
at `BAND_GFX[b]`. Its width field is constant per band in `$1F3C` (`$18
$14 $10 $0C $0A $06 $02` for bands 1-7: 8, 12, 16, 20, 22, 26, 30 bytes),
ORed with the stripe texture (`$00`/`$20`, palette 0 or 1). Its x is the
curve at the sample row plus a fixed perspective base, which is the same in
both views (`band_base` = `OC_BASE` by band).

**The slices.** `smooth_art()` builds, for each band and each shear s, a
copy whose line k moves s*(k-3) px, so the sample row stays put. Each copy
is trimmed to its content, and its start (dx) is kept for x. The taper
helps: a +/-1 shear of band 7 is 29 bytes, narrower than stock. The ranges
cover each band's measured worst slope: +/-5, 4, 4, 3, 3 px a line for bands
1-5. That is 38 copies, 630 bytes a line, first-fit packed into three
6-page columns: `$70-$75` and `$76-$7B` at low bytes `$28-$FF` (beside the
highlight art), and `$6A-$6F`. `EXT_END` is now `$69FF`.

**Choosing and applying.**
- `SmSelect`, at the end of each tick (`P2Tick`, main loop, 10 Hz), picks
  each band's slice. The slope is the curve's change over twelve rows,
  either side of the band. For player 1 that is `RowCurveOffset` at the
  neighbouring sample rows. For player 2 it is `P2_BANDX` less the bases,
  plus the camera's lateral term (12 x step, signed as the camera signs it).
  `SmDiv` divides by 12 and rounds, and each band's range clamps it.
- `SmApply`, in `VbTail` once the tick's values are whole (both views
  drawn), writes the slice's address into the header, and its width field
  and dx into zero page (`SM_W1/SM_DX1`, `SM_W2/SM_DX2`; `$67-$91`).
- Every frame, the stage code ORs the width field into the band's width byte
  and adds dx to its x. Player 2's far loop got shorter: `ORA zp,X` replaces
  a two-table lookup.

*Wrong turn, measured:* the first form chose and applied every frame at the
end of `MirrorStage`, about 60 cycles a band for ten bands. That cost the
race 69-99 ticks in 100 over six starts (97-100 without). Split as above:
98-100.

*Checked:* on screen, a hard bend's far road goes from disconnected slabs to
one continuous edge, with lane marks and kerb edges following it, in both
views. List integrity is 0 on four recordings. Health has the same shape;
the timing shift moves the recorded inputs a little (run-03's qualifying
message ends 380 frames earlier). `PP2_NO_SMOOTH=1` builds without it.
Bands 6-7 are still stepped where they meet band 5.

### The far stripes are per band, and always have been since checkpoint 6

Raised by the user: "the palette cycling is not reaching the far bands".
The kerb stripes and the centre dashes are the stripe texture choosing each
road line's palette: 0 (`$0F` white kerb, `P0C2` dash) or 1 (`$34` red kerb,
dash the road's `$04`). The stock injection set it line by line. Since the
injection was dropped (checkpoint 6), each band has one palette for all six
lines. `dat_C07E` falls about 6 a row in band 1 and 2 a row in band 7,
against a texture half-period of 15. So a far stripe is 2.5-7.5 rows long,
shorter than a band. The stock game shows fine red/white kerbs and dashes
to the horizon; this build shows each far band in one colour, and a band on
palette 1 has no centre dash. It is aliasing from the band sample. The
smoothing did not cause it; with the edges now continuous it is easier to
see.

Options, none built:
- **A mid-band change by display interrupt.** Split each far band into two
  3-line zones sharing one list, with an interrupt between them rewriting
  the page and palette of every header in the band (road and objects). It
  needs no `WSYNC`, but costs about 14 interrupts a frame plus one write per
  object, and the interrupt chain is where the budget is tight.
- **Stripe patterns baked into the slices.** A band's six-line pattern
  depends on the texture phase (up to about 30 patterns a band) and would
  multiply the sheared copies. It needs far more ROM than there is.
- **Palette cycling proper.** Kerb classes as colour indices, with the
  palette registers rotated each frame. There are not enough spare colours:
  palettes 2-5 are the road pieces, rivals and signs.

## The far bands split in two, for the stripes

Checkpoint 87. The user's suggestion, after the stripe finding above: cycle
each far band separately, with one or two splits more.

*What the log showed first:* player 1's far bands did cycle separately
(patterns like `RRwwRwR`, `wRRwwRR`). But at speed the texture phase
(`$CD`) moves about 6 a frame, and band 1 spans about 33 texture steps
against a period of 30. One sample per band strobes, which reads as the far
road flipping as a block.

**Built.** Far bands 1-7 in both views are two 3-line zones:
- **The halves.** The bottom half is the band's own list: MARIA counts a
  3-line zone's page from +2 down, so it draws the band's lines 3-5 as
  before. The top half has a 14-byte list of its own (road header, two
  object slots, end) whose pages are 3 higher. Player 1's are at
  `$2599-$25FA`, after the zone list, which is now 51 zones and 153 bytes.
  Player 2's are at `$2200`, `$220E`, `$221C`, `$210F`, `$211D`, `$212B`
  and `$1BCA`.
- **Stripes.** Each half takes its own stripe, from row 6b+1 (top) and
  6b+3 (bottom). Player 1's top rows are extra rows in `E8Lite`, so the
  start line's palette-7 override covers them too. Player 2's are sampled
  in `P2TopStage` at its own phase.
- **The road slice.** Width field, x and the sheared slice are shared:
  `SmApply` writes the slice into both headers, the top one 3 pages up.
- **Objects.** At each object rebuild (10 Hz), `TopCopy2` (after `P2Emit`)
  and `TopCopy1` (after the game's rebuild at rom:E6D7) copy the band's
  first two objects into its top list with their page raised by 3. Unused
  slots are parked as the game parks them (x `$A1`, width 1; a wide object
  parked at 161 would wrap onto the left edge). Player 2's emitter fills
  in order. Player 1's objects sit in fixed slots by kind, so the copy
  searches the slots each band was seen to use: +4/+8 cars, +24 signs,
  +28/+32 others, and +20 in band 7, player 1's own car's top. Measured
  over three recordings, a far band never held more than three objects,
  and rarely more than two. A third object, or one in an unexpected slot,
  draws in the band's bottom half only.
- **Layout.** Display interrupt index 8 was placed by zone count (clamped
  to the view's last zone); it is now pinned to the last zone. The zone
  list's boot template grew 42 bytes, so `P2_TEMPLATE` moved to `$EE3A`.

*The cost, measured* (race tick rate, six starts, both cars at 240 in
traffic):

    no split (checkpoint 86)          98-100
    split, pointer search, all slots  83-95
    split, copies off (test hook)     93-100
    split, unrolled copies (kept)     94-100

The first copy was a generic loop through a zero-page pointer over all
eight slots, and it cost about 9 ticks. Unrolled over each band's known
slots, with player 2's empty slots just parked, it costs about 2-3.
`TopInit`, first unrolled at about 980 bytes, overran the code area; it is
a template table and a loop now. The code area ends at `$6942`, against
`$69FF`.

*Checked:* on screen, the far kerbs alternate red and white within each band
and the centre dashes reach the far road, in both views. The far car draws
whole across the seam. List integrity is 0 on four recordings, and health
has the normal shape. `PP2_NO_SPLIT=1` builds without it.
`PP2_NO_TOPCOPY` (test hook) leaves the top halves without objects.

## Near-band shearing: sized, and not yet built

Asked for after checkpoint 87 (bands 8-11 chosen). Findings from sizing it:

- **Near lines are two objects:** a fixed 16-byte left piece at x-60 and a
  right piece of 19-31 bytes. Sheared together as one line and split back
  into two objects of at most 31 bytes (band 12's right piece is already 31),
  a +/-1 shear costs 33, 37, 41, 43 and 47 bytes a line per shear for bands
  8-12. Bands 8-11 at +/-1 total 308 bytes a line, about 1.85K. Near lines
  have no interior gaps, so the split can go anywhere.
- **The width byte varies:** for bands 10-12 the game sometimes takes 8 bytes
  off the right piece's width (field `$07` -> `$0F`, etc.). A sheared slice
  therefore has to carry a width delta, not an absolute field.
- **Slot use in player 1's near lists** (object slots from +8; three
  recordings): +8 is used in 6-12 frames out of about 14,000, +12 by cars,
  +16 rarely, +20 never, +24 sometimes, and +28 (`$1C`) is player 1's car,
  always. A three-piece layout (the stock pieces with their kerbs clipped,
  plus small sheared edge pieces) would need +8, and a car there would lose
  that band's slice in those frames. It would cost about 200 bytes a line.
- **Why it does not fit:** a slice needs a column of six consecutive pages
  at one low-byte range. Free space is about 2.2K in all, but mostly
  fragments: the code area's tail after `$64xx`, 58 bytes a line in the
  `$6A` column, and the `$7C-$7F` windows. A new column needs the code to
  end by `$63FF` (or by `$6437` for a 200-byte-wide one). The code ends at
  `$6942`.
- **Compaction measured:** tables into `$7C28-$7FDF`, `SmDiv` on |d|
  (85 entries), and `TopCopy1`'s copies through a shared routine. The code
  end moved to `$64AD`. It cost race ticks: 91-100 against 94-100.
  Reverted.

What it would take: move more routines into the `$7C-$7F` windows
(`TopInit`, `SmInit`, `SmQ`), compact `TopCopy2`, and then add the near
bands' own selection and apply code. Each step costs some speed, and the
near bands' per-frame adjustments (four per band per view) come on top.
Estimated at about 90-93 in the stress test. Or, in scope order, spend less:
near bands 8-10 only, or reduce the far bands' extreme shears.

## Speed: the object pass's row search, by halving

Checkpoint 88. Asked (before near-band shearing): find speed first.

**The profile.** `tools/probe-pcprof.lua` samples the CPU's PC at each zone
boundary (MARIA's zone-list reads). It was run in the stress scenario, both
cars at 240 in traffic, frames 7000-7600, three starts (550,000 samples),
alongside the scripted race. Two probes loaded together must not share a
global tap table: the profiler's `TAPS={}` dropped the race probe's taps
until it was loaded with its table renamed.

    13.8%  rom:CE3E-CE51, the object pass's row search
    13.4%  the blob, mostly just after STA WSYNC (lines waited out)
    12.7%  rom:E709, the main loop waiting for vblank before the rebuild
     4.4%  rom:EA28, the six-frame staging wait

**rom:CE3E** walks rows up from 0 and returns the first whose distance
(`$EB56`/`$EAB9`) the object's Z (`$47`/`$48`) reaches, by the sign of
Z - T[row], or `$4E`: up to 78 passes of about 15 cycles, called up to
twice per object (rom:CDF2, CE0F, CE72, CE8B). `FastZRow` (checkpoint
60) had replaced rom:E3CD, a different search walking the other
way; this one was untouched. `ZRowUp` is the same search by halving: seven
steps, X kept, the answer in Y as before. The test is monotone in the row
for Z below `$8000`, and Z at or above `$8600` never meets it (`$4E` at once,
the objects behind). The band between wraps the signed difference and falls
back to the stock routine. Checked at build time for all 65,536 Z, and live
(a probe recomputing the stock search at each return): 0 differences in
66,750 searches over four recordings.

Race tick rate in the stress scenario, six starts: **100, 100, 102, 100,
100, 100**, against 94-100 at checkpoint 87. Health is identical to
checkpoint 87 on four recordings, list integrity is 0 on four, and the
tallies pay as before (a scripted race: 60 s, 36 cars, player 2's 31).

*Wrong turn, a crash:* the first build wrote `JMP ZRowUp` over rom:CE3E.
Three bytes: CE3E, CE3F and CE40, and CE40 is the stock loop's own start,
the branch target and the fallback's entry. The patch's expected bytes
covered only what it overwrote, so the build check could not see that the
third byte was a branch target. Any fallback then ran a broken
instruction. On test-0236 the CPU fetched from `$85EC`, road graphics, at
f1661; the variant with the stock search (every call a fallback) crashed at
f271. Found with a tap on CPU fetches in `$8000-$BFFF`, which dumped the
stack (the chain from rom:D710, the race tick). A code-area shift alone was
ruled out: checkpoint 87's build with 5 bytes of padding ran clean. Fixed by
retargeting the four callers and leaving CE3E intact.
`PP2_LINEAR_CE3E=1` builds with the stock search.

*Also seen:* in the scripted qualifying pairs, lap times now differ from
checkpoint 80's table, because the race no longer loses ticks. Player 2
meets traffic in the same lane, 7 contacts in the 198/200 pair. Each
result is right for its times (e.g. 189/190: player 2 faster for 8th,
player 1 out).

## Documentation pass after checkpoint 88

Asked: make sure everything is documented, annotated and current, with a
clear build path from the retail ROM. What changed, and what was found
stale:

- **`annotations.json`** had not moved since the early disassembly. It gains
  30 labels (the state dispatcher and handlers, the tally helpers, the object
  pass and both row searches, the emitter, the stripe-row builder, the track
  walk, the decor builders), 31 RAM names and 9 data tables, each noted. The
  wait at rom:EA28 is labelled apart from `StageRowCurveForDLI` (rom:EA2C),
  which this file already names. Disassembly and `verify.py`: ROUND-TRIP
  PASSED; coverage unchanged at 33.5%.
- **The generator's docstring** described the mirror-era patch. It now
  covers the build, its requirements, the switches, and why `--bundle` cannot
  express a 48K image. Stale comments were fixed: player 2's lean has come
  from its own stick since checkpoint 27; its crash is drawn by `P2CrashDraw`;
  the car is five bands; the fine zones are inactive.
- **The build path:** the dump is checked by its body's SHA-256 (CRC32
  A85FB962) before anything is written. A named `PP2_ROM` that is not a dump
  is an error; before, it silently fell back to another copy. A missing
  toolkit says so. `PP2_TOOLKIT` overrides the toolkit's location. Each build
  prints its SHA-256; the README lists checkpoint 88's (unsigned and signed,
  both deterministic; the signed one boots).
- **`dist/pp2-splitscreen.abp`** was the mirror-era patch and cannot be
  rebuilt (the format cannot grow 32K to 48K). Removed; the README says why.
- **Tools:** fourteen probes printed player 2's qualifying bytes from their
  pre-checkpoint-82 addresses (`$26FC-$2701`, now `$2027-$202C`); fixed. The
  first pass of that fix also moved `probe-rival-entries.lua`'s dump of
  player 2's RAM block from `$2700` to `$202B`, reading that base as the old
  `P2_PARK`; caught while writing the tool headers and put back. Five tools
  gained headers; `race-profile-map.py` no longer assumes this machine's path.
- **Verification in the repo:** `tools/check-build.sh` runs the regression
  set used since checkpoint 80, against any build, with the build's own
  symbols. `tools/health.py` and its logger came in from the lab.
  `tools/p2-road-headers.py` derives the integrity probe's header list; a
  hand-kept copy went stale at checkpoint 82. The four recordings the findings
  cite (run-03 and three two-player tests) are committed. `.gitattributes`
  keeps shell scripts LF.
- **`docs/SPLITSCREEN.md`** is new: the current design, with its maps (zone
  list, RAM claimed and free, ROM layout, the 73 changed ranges of the retail
  32K) generated by `tools/splitscreen-maps.py` from the generator itself.
  `ram_claims()` now exposes the list the build checks, so the document
  cannot drift from it.

The build's bytes did not change in any of this: SHA-256 `eb488ab7...` before
and after.

## Near-band smoothing, bands 8-11

Checkpoint 89. Asked for after the speed work (checkpoint 88) gave the
headroom back. Bands 8-11, +/-1 px a line, in both views.

**The design, cheap per frame.** A near line is two objects: a 16-byte left
piece at the right piece's x - 60 (the stage's wrap guard computes it) and a
right piece whose width comes from the game (the stripe texture, plus `$B6`
from row 60, ORed with the `$1F3C` width field). The texture's `$08` bit takes
8 bytes off the right piece on some rows, for bands 10-11, whose field has bit
3 clear.
- **The slices.** Each line is composed as drawn (the right piece over the
  left, clear pixels showing through), sheared, and split again: the left
  piece still 16 bytes starting 60 px left of the right piece, the right
  piece the rest (18-28 bytes). So the wrap guard places the left piece
  unchanged.
- **Width.** The right piece's width goes in as a delta subtracted from what
  the game computed (`SEC / SBC NEAR_DB+e`), which keeps the `$08` rows
  exact. Writing absolute fields into `$1F3C` was considered: that table is
  written only in state `$00` (a write tap over two recordings), but a field
  write would lose the `$08` behaviour.
- **x.** Player 1's `ADC #base` became `ADC NEAR_NX+e`, a RAM copy of base +
  offset. Player 2's near loop adds `NEAR_NX-3,X`. Per frame this is a few
  cycles a band.
- **Choosing and applying.** `SmSelect` picks 0-2 per band (`SmPick1`: the
  slope over twelve rows, rounded and clamped) from the same differences as
  the far bands. `SmApply` (`SnLoop`, 10 Hz) writes both headers' graphics
  through `E8L_T`, which is free in index 12 since E8Lite runs in index 11,
  and the delta and offset.

**The ROM.** It did not fit at first (FINDINGS above, "Near-band shearing:
sized"). Making room:
- the smoothing's tables into the low bytes `$28-$DF` of pages `$7C`, `$7D`
  and `$7F`, `SmDiv` shrunk to 85 entries on |d| (`SmQ`);
- `TopCopy1`/`TopCopy2` through shared copy routines;
- `TopInit`, `SmQ` and `SmPick1` into a separately assembled block at `$7E28`
  (206 of 216 bytes).

The code area ends at `$63AA`, so pages `$64-$69` became a fourth slice
column. Far and near slices together needed 942 bytes a line against 944, and
first-fit packing failed on the fragments. Band 1's range went from +/-5 to
+/-4 (its 90th-percentile slope is 2.6 px a line), freeing 28 bytes a line.

*Checked:*
- `tools/check-build.sh`: health as checkpoint 88 on four recordings,
  integrity 0 on four, `ZRowUp` 0 differences, no wild fetch, stress tick
  rate 100 on all six starts.
- On screen, on bends, the near kerbs' 6-line sawtooth becomes a continuous
  edge in both views.
- Choices over a two-player recording: player 1's near bands mostly s = 0,
  player 2's mostly s = -1. That looked like a bias, and it is geometry:
  player 2 drove offset to one side. A probe comparing each choice with the
  slope of what player 2's view actually draws agreed 2,803 times in 2,820;
  the 17 were all d = -7, the rounding boundary, with staging a tick apart.
  With both cars scripted to the same lateral, the two views chose alike.

*Pitfalls on the way:*
- the first composite let the right piece's clear pixels erase the left
  piece's (MARIA does not draw clear pixels); caught reading the script;
- a probe add-on spliced in with `awk -v` had its `\n` escapes turned into
  line breaks: `string.char(10)` instead, as the other add-ons do.

*Not covered:* band 12 (its right piece is already 31 bytes and there was no
ROM left); +/-2 px a line on the near bands.

## The .abp bundle grows the cartridge

After checkpoint 89. The toolkit's anchored bundle could only patch fixed
extents of the dump, so the 48K build had no bundle and `--bundle` refused.
Toolkit commit `2ad23b3` adds `patchset/3`. With it, an option can say
`"grow": {"size": 49152, "at": "front", "fill": "0xFF"}`:

- A linear 7800 cartridge ends at `$FFFF`, so it grows at the front, and the
  body's base moves from `$8000` to `$4000`.
- Sections are CPU addresses in the grown body. Those in the new 16K describe
  the `$FF` fill.
- The `.a78` header's ROM size (bytes 49-52) is set to the grown size.
- A header whose cartridge type puts anything at `$4000`, or banks the image,
  refuses to grow.
- The toolkit's `docs/patchset-format.md`, "Growing the cartridge", has the
  rules.

**The VS bundle.** It has one option (`vs-split`): 476 sections covering
16,880 bytes, one BPS spanning them (16,994 bytes), and anchors at `$A415`,
`$B912`, `$D000` and `$F17C`. On the retail dump, `patchset.py apply`:

- grows the body to 48K and sets the header to 49,152;
- signs the result, which is **byte-identical to `--build --sign`**
  (`8eb5dab8...`);
- is recognised afterwards: `check` on the result says "applied", and a
  second `apply` changes nothing;
- gives the same body from a headerless dump.

The self-test pins all of these on an invented cartridge ("patch sets that
grow"). The bundle goes to `build/`, not `dist/`, because of the generated
graphics (README).

**A wrong turn in recognising a grown cartridge.** The patcher tries every
layout the bundle can produce: the dump's 32K at `$8000`, and 48K at
`$4000`. On a 48K file, the 32K layout also fits, at the file's last 32K
(the offset `len(file) - body_size` it always tries for trailing bodies). The
anchors all sit in `$8000`-`$FFFF`, so both layouts scored 4 of 4, and the
first one won. The cartridge was then read as a 32K body with a 16K
"header", which is wrong. Ties now go to the offset the bundle declares
(0 or 128), then to the larger size.

**The graphics hack and VS do not stack. This corrects two earlier claims.**
Checkpoint 83 and the mirror-era test both said they touch disjoint bytes.
Stacking the two bundles showed otherwise:

- The hack's section `s_EDE3` (`$EDE3`-`$EDE7`, the car's palette `P6C1`/`P6C2`
  as the stock injection loads it) lies inside VS's `s_ED9D` (265 bytes). That
  is the injection VS reclaimed at `$EDA0`-`$F142`.
- VS no longer runs that code. `RoadTail` and `MirrorPalette` set `P6C1`/`P6C2`
  with their own `LDA #$2F`/`#$26`.

So the combination is a real clash, not an artefact of the tool. A VS-aware
redraw would change those two immediates to `$93`/`$0D` instead, and rederive
the highlights from the new upright frame. It is not built.

The first stacking attempt reported "not the cartridge" in both orders. That
was the wrong error:

- The hack's anchors `$B000` and `$F000` contained bytes VS changes (4 and 234).
- A VS anchor lay on hack-changed bytes.

Each generator now keeps its anchors off the other's bytes:

- `splitscreen.py` avoids `graphics_hack.CAR_SPRITE_EDITS`.
- `graphics_hack.py` avoids every retail byte the VS edits change, plus the
  signature at `$FF80`-`$FFF7`. Its anchors moved to `$A415`, `$B912`,
  `$D000` and `$F17C`.
- `dist/pp2-graphics-hack.abp` was regenerated. Applied to the retail dump,
  its output is unchanged.

Now each bundle recognises the other's cartridge, and the refusal names the
clashing bytes:

    hires-car cannot apply: the bytes it covers (33 sections, s_8B13..s_EDE3)
    hold neither what it expects nor what it would write. Something else has
    changed them: s_EDE3 ($EDE3, 5 bytes).

That message needed a toolkit change too. A span is judged as a whole, so the
refusal used to list all 33 of the hack's sections. It now picks out the
sections that no longer hold the dump's bytes. That is sound because an
option refused this way is known not to be on the cartridge.

The standalone reader (`Anchored-Bundle-of-Patches/abp.py`) refuses a `/3`
bundle by name, as intended: "is 'patchset/3', not patchset/2".

## The higher-detail car in VS, and the bundle published

After checkpoint 89. The request was to make KevinMos3 and Defender_2600's
car redraw work in VS, and to publish the VS bundle.

**What carries over.**
- The 38 sprite edits (the upright frame at `$8B10`, 26 lines, and its
  6-line companion at `$AAE8`) touch nothing VS changes. They go in as they
  are, checked against the retail bytes.
- The two palette values, `P6C1 $2F -> $93` and `P6C2 $26 -> $0D`, do not
  carry over. In the retail game they are operands in the scanline
  injection at rom:EDE3/EDE7, which VS no longer runs. VS sets palette 6 in
  two places, `RoadTail` (player 1's view) and `MirrorPalette` (player 2's),
  so the hack's values go there instead.
- `PP2_HIRES_CAR=1` builds it in. `car_colours()`, `car_rom()` and
  `ovl_pw()` are what change. `car_rom()` is the retail body with the redraw,
  and the highlight art is now derived from it.

**First look: every car blue and white.** A first build used the hack's
colours in both views, and MAME showed four identical-looking cars:

- Each car in the other player's view is drawn from the same pages at the
  nearest size, also in palette 6.
- Player 2's blue and white highlights all but vanished on a blue body.
- Rivals use palettes 3 (yellow `$1E $17`), 4 (white `$0E $98`) and 5
  (blue `$9C $96`). A blue and white car sits close to two of them.

**The fix inverts the contrast.**
- Player 1 keeps the redraw as released.
- Player 2 has the same car with **gold** highlights, in palette 3, the
  yellow rival's (`$1E` light, `$17` gold).
- On the stock car, player 2 was gold with blue; now it is blue with gold.
  Rivals are single-colour cars, so neither combination is one of theirs.
- Palette 3 holds the same values in both views (`MirrorPalette` writes
  `$1E/$17`, and stock does the same in player 1's view). The header byte
  changes from `$98` to `$78` in both views.

**The highlight rule, on a frame it was not written for.** The rule finds
the wing's centre as the longest black run in band 9's second line. The
redrawn upright frame has no such gap: the wing is solid, with a light
stripe across it and light endplate lines. On it, the rule coloured the
whole wing and drew no bar. The frame now takes a second branch, used when
the run is under 4 pixels:
- light pixels in band 9's top four lines become the bar;
- body pixels outside columns 9-22 (the wing tips) become gold;
- the sidepods (band 8's bottom two lines, outside the roll hoop) become
  gold, as before.

The other four leans are still the stock drawing, and keep the stock rule.
The stock build is unchanged (`0c5b6488...`).

**Checked.**
- *Screenshots in MAME* (`test-pp2-2p-0923-0205`): player 2's car in its
  own view and in player 1's view, upright and leaning, with the highlights
  on their frames. `tools/probe-overlay-shots.lua` takes `PW=0x78` for this
  build.
- *`tools/check-build.sh`* on the unsigned hires build:
  - health identical to the stock build on all four recordings;
  - integrity 0; `ZRowUp` 0 differences; no wild fetch;
  - tick rate 100 on all six starts.

The change is data and immediates of the same length, so none of that was
expected to move, and none of it did.

| hires build | SHA-256 |
|---|---|
| unsigned | `1dde56ea0fc864d52fc2e3500decd72d05139dcbbb2bda022da03d59d21ab660` |
| signed | `7990630e12dba759673718cf1307d097ef775d94342b0a5a85b4fcbe887b21a5` |

**The bundle: `dist/pp2-vs.abp`, two options.**
- `vs-split`, and `vs-hires-car` on top of it.
- 508 sections: 467 VS only, 9 shared, 32 the redraw. 17,307 bytes of BPS.
- The shared sections are where both options change bytes (palette 6's
  operands, the highlight column, the highlight header's palette). Each
  option has a patch over exactly that span: `vs-split` from retail to VS,
  `vs-hires-car` from VS to hires. That is how the toolkit reads the
  dependency (`derived: vs-hires-car needs vs-split`).

Tested:
1. Each option on the retail dump gives the generator's `--build --sign`
   image of its variant, byte for byte.
2. `vs-hires-car` applied to a VS cartridge gives the same image as in one go.
3. Applying either option again changes nothing.
4. `check` reports:
   - retail: both applicable;
   - VS: one on, one applicable;
   - VS + hires: both on;
   - the retail-hacked cartridge: both refused, naming `s_ED9D`.
5. A headerless dump gives the same body.

**Two bugs on the way.**
- *Ours.* The first bundle's hires image differed from the generator's at
  one byte: `$4100`, `RcP1Show`'s `LDA #` of the highlight header (`$98`
  where `$78` belonged). `_ext()`, `_hi_code()`, the slices and the rival
  code are assembled once per process and cached, and the bundle builds both
  variants in one process. `_patched()` now empties the four caches going in
  and coming out.
- *The toolkit's* (commit `064514a`). This was the first real chain: two
  options sharing sections, one rewriting the other's bytes. It broke in
  three places, each now in the self-test and the format doc:
  - a span's pristine state was taken from the last patch's `before`, so
    `vs-split` looked built on nothing;
  - once `vs-hires-car` was on, `vs-split` read as blocked;
  - on retail, `vs-hires-car` read as blocked, though `apply` runs
    `vs-split` first.

**Publishing, and what the bundle carries.** The generated graphics were
the reason the bundle stayed in `build/`. The user's call: they are
transformative, and mostly grey road with a border each side, so it is
published. For the record, a byte audit of the new 16K on the hires image
(runs of 16 or more bytes, not flat, that also occur in the retail ROM):
- 2,162 bytes in the graphics area, the sheared road slices' unshifted rows;
- 224 bytes in the code area, fragments of the game's own routines that
  player 2's copies mirror (from pages `$C9`, `$D4`, `$DB`, `$DC`, `$DF`).

Retail bytes kept in place are CRC32s only, as before.

**Also fixed:** the README's bundle command from the previous commit had
lost its line continuations. It was written through a non-raw Python
string, which turned `\` plus newline into nothing. This time the text was
written from a file.

**Toolkit, since.** The toolkit work above went forward to the public
repository, [a7800-toolkit](https://github.com/Miasmark/a7800-toolkit), as PR
#2 (merged, `f449428`). The generators, README and tools now look for it
cloned beside this repository as `../a7800-toolkit`, not at the Karateka
fork (`../a7800-toolkit-local`). With it, all four builds (VS and
higher-detail car, unsigned and signed) give the same SHA-256 as before, and
both bundles apply identically.

## What this mod gave back to the toolkit

After checkpoint 89. The lessons of the mod that are not about Pole Position
II went into [a7800-toolkit](https://github.com/Miasmark/a7800-toolkit)
(PR #3), and the generators now use them.

**Fixed in the toolkit.**
- *`asm.py` accepted a name defined twice.* The later definition won
  silently: checkpoint 84's branch went 322 bytes astray this way. It now
  refuses a name redefined with a different value. The same value twice is
  allowed, because older listings repeat labels.
- *`disasm.py` wrote every named byte block's label twice.* This is why
  older listings repeat them: `emit_block` labelled a block, then
  `emit_bytes` labelled its first run again. It came to light because the
  new check first refused this game's own listing (`dat_StateHandlersHi`).
  The listing lost 27 repeated labels and still round-trips.
- *Bundles were a new file every rebuild.* The zip stamped the time and the
  OS into every entry. Entries are now fixed, so the same inputs give the
  same bytes.

**Built from this mod's code.**
- *`patchset.bundle_from_images`.* It builds a bundle from the dump and each
  option's finished image: sections, spans grouped by which options change
  them, anchors clear of other bundles' bytes, and growth. It refuses to
  write a bundle whose options do not reproduce their images. Both
  generators now call it, and their hand-written bundle code (about 150
  lines, and `pick_anchors` twice) is gone. The regenerated
  `pp2-vs.abp` and `pp2-graphics-hack.abp` have the same sections and
  anchors as before, apply to the same bytes, and rebuild byte-identical:
  - `pp2-vs.abp` is `a631bace...`;
  - `pp2-graphics-hack.abp` is `96585a15...`.
- *Probes, made game-agnostic.*
  - `probes/wildfetch.lua`
  - `probes/romcoverage.lua`
  - `probes/rendersurvey.lua` with `tools/zonebill.py`
  - `probes/snapwhen.lua`
- *`tools/modmap.py`,* the general `vs-rom-map.py`. On this build it
  reproduces the published retail and overwritten figures (26,830 read,
  1,952 unread, 3,986 overwritten).
- *`tools/regress.py`,* the general `check-build.sh`. This project's set is
  now also in `tools/check-build.json`. On the hires build it gave the
  script's verdicts, line for line.

**Measured on the way.**
- *Where coverage should start.* The coverage probe has to skip the BIOS,
  which reads the whole cartridge to hash it. A game-agnostic start is the
  cartridge's first INPTCTRL write with the lock bit set. This game writes
  it at `$D207`, Karateka at `$4061`, Midnight Mutants at `$FF02`, all just
  after the hand-over. The old probe started at `$D205`, a PC this game
  alone has.
- *The signature timing, seen once more.* The unsigned build locks at
  frame 209 and the signed one at 203. That shift is why recordings desync
  on a signed build. It is now a toolkit pitfall ("Re-signing a cartridge
  moves the start of the game").
- *MAME's palette.* `palette.py` gained MAME's own table: every colour in
  four MAME screenshots is in it. `$17` is (145,126,9), the gold chosen for
  player 2's highlights, where the old approximation gave olive.

## Checkpoint 90: player 2's sky, and player 1's far objects in blinds

Reported in play:
1. The top of player 2's skybox was mostly cut off.
2. Objects in player 1's view were drawn partly, "with blinds or broken
   up". The user named one: "that's a flying tire", from player 1's crash.

Both were reproduced from the user's recording (`test-pp2-vs-0924-1733.inp`,
made against a checkpoint-88 build) by replaying it on that exact cartridge.

### The sky: the horizon zone was given two lines of ten

Checkpoint 77 gave player 2 a 2-line horizon zone, "the horizon's bottom
two lines (the tops of the tallest decor, as zone 18 carries them for player
1)". Player 1's horizon zone has all ten lines, and it carries the tall
features, such as Fuji's peak, from its top line down. The checkpoint-77
check compared the two skies by each row's dominant colours, over rows
player 2 actually had. So player 2's view drew only Fuji's lowest rows: a
flat-topped sliver under 11 rows of empty sky.

The lines were there to take. Mapping a screenshot to the zone list gives
row = zone line − 9: the picture starts at line 9. The frame's first 20
lines are blank zones, and lines 9-19 were on screen as plain sky.

**Fix.** Zone 0 goes from 16 lines to 8, and player 2's horizon zone from 2
to 10. Everything from line 22 down is where it was:
- player 2's decor, road and horizon line;
- the divider;
- player 1's half.

The DLI on zone 0 (index 7, the sky's palettes) fires eight lines earlier.
Zone 1, the 4 blank lines it writes the palettes during, is unchanged. The
horizon zone's list is player 2's own copy of the stock one, and it now
reads the object's ten pages exactly as player 1's zone does.

### The objects: TopCopy1 copied before the game had placed anything

Since checkpoint 87, each far band (1-7) is two 3-line zones. The top half
has its own list, and `TopCopy1` fills it from the band's main list once a
tick. An object missing from the top list draws in the band's bottom three
lines only, three lines on and three off down the object, which is the
blinds.

A list dump during player 1's crash showed the tire and car pieces
(palette 6) in the main lists, with the top lists parked or holding stale
copies. A write trap on band 4 gave the order within a tick:

1. rom:E6D7 parks slots 0-5 of every band.
2. `TopCopy1` copies.
3. rom:E320 parks slots 6-7.
4. Only then, from rom:E713, does the game emit this tick's objects
   (writes at rom:E7AC-E7C2).

`P2ObjCommit`, hooked at rom:E70D, had run `TopCopy1` straight after
rom:E6D7. The annotations named rom:E6D7 `EmitObjectLists`, and it emits
nothing: it only parks. So `TopCopy1` never saw a rival or a sign in slots
0-5, because they were always parked when it ran. The debris in slots 6-7
it copied from the previous tick, six frames stale. Every object in player
1's far bands had drawn in blinds since checkpoint 87. The known limit in
SPLITSCREEN ("a far band's third object... draws in the band's bottom half
only (rare)") was this bug, and it was not rare at all.

Player 2's view was never affected. `TopCopy2` runs after player 2's own
emitter, `P2Emit`.

**Fix.**
- `P2ObjCommit` ends in the game's slot parking.
- The rebuild's three callers go through two wrappers that make the same
  call, then run `TopCopy1`:
  - rom:D71F (`JSR ObjectRebuild`) and rom:D7BE (`JMP ObjectRebuild`) go to
    `RbAfter`;
  - rom:D8C5 (`JSR sub_E70D`) goes to `RbAfterE70D`.
- The copy now runs after rom:E713's emission, on the same tick, still ahead
  of the beam reaching player 1's half.

It costs 12 bytes of the code area, which now ends at `$63B6` (73 bytes
spare). No work was added, so the tick rate is unaffected.

Annotations: rom:E6D7 is now `ParkObjectSlots`, rom:E320
`ParkObjectSlotsHigh`, and rom:E70D `RebuildObjectLists`, with comments on
where emission really starts.

**Checked.**
- *Screenshots from the user's recording.* Player 2's Fuji has its peak and
  matches player 1's. Through the crash (frames 7400-7480), the flying tire
  is solid where the old build drew it in stripes.
- *Player 1's far rivals.* At frames 17040-17160 of the same recording,
  the current build draws them in stripes and the fixed build draws them
  solid. The two builds stay in step frame for frame.

### Fuji's top portion misaligned: a second bug in player 2's sky

With the whole horizon zone showing, the user saw Fuji's top drawn off its
base in player 2's view. Zoomed, the top eight lines of player 2's decor
sat to the left of its last two.

`P2Sky` builds three lists: the horizon object's, the decor's, and a copy of
the decor's for its top eight lines. The copy is needed because MARIA counts
a zone's page down from its height, and this zone is 8 lines where the list
serves 10. Stock rom:DC60 gives:
- the base object an x from the heading (`$1D3E`);
- the horizon object that x plus `($A8C6 - $A8CA) * 4` (`$18FD`).

`P2Sky` stored the horizon's x into the horizon list and also into the
decor copy, where the base object's own x belongs. So since checkpoint 77,
the decor's top eight lines were shifted by the per-track offset against
its bottom two. The flat sliver the old 2-line zone left was offset the
same way.

**Fix:** the copy takes the base object's x, as `P2_DECOR_DL` does. At frame
1200, player 2's Fuji is now identical to player 1's, pixel for pixel.

### Regression

The regression set (`tools/check-build.json` with the toolkit's
`regress.py`) was run on the checkpoint-89 build as the baseline, and on
checkpoint 90. 17 of 19 verdicts were identical:
- health on all four recordings, so the game state is the same frame by
  frame;
- integrity 0 on four;
- no wild fetch;
- tick rate 100 on all six starts.

The two that changed are the `ZRowUp` check, still with 0 differences but
with fewer searches in its 12,000-frame window: 18,030 → 18,016 and
13,793 → 13,769. Split by fix (the old sky zones patched back into a copy
of the build), the object fix alone accounts for 6 and 4 of those, and the
sky change for the rest. That is the main loop fitting a few fewer object
passes into the window, not a change in what the game does.

*Wrong turn in the harness, first run:* the integrity probes found no header
file on either build. `regress.py` filled in `vars_cmd` before `--var`, so
`check-vars.py` wrote the headers to the default `build/regress` while the
jobs, given `--var out=...`, looked elsewhere. `regress.py` now applies
`--var` before `vars_cmd` as well as after, and `check-build.json` passes
`{out}` to `check-vars.py`.

| checkpoint 90 | unsigned | signed |
|---|---|---|
| VS | `45ca22aa...` | `b2ce96ea...` |
| higher-detail car | `07a28034...` | `825fee12...` |

`dist/pp2-vs.abp` was regenerated (`3fe22035...`). Both options apply to
their signed builds, and to each other stacked. `pp2-graphics-hack.abp`
came out byte-identical.
