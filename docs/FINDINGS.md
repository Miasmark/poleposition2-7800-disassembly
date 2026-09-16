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
