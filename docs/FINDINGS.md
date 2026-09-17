# Pole Position II -- findings so far

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
