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

### The road doesn't compute a curve. It's a two-shape swap.

Raised by a question about whether a second, independent road view is
feasible at all (split-screen two-player). The first pass at this (below,
corrected rather than deleted, since the wrong turn is worth keeping visible)
tapped `$2200-$226B` for 5,000 frames and found almost every byte written
exactly 15 times, and concluded that was a periodic per-segment rebuild
"once every ~5.5 seconds". **That conclusion was wrong.** Extending the same
tap across the *entire* 17,115-frame race shows all 15 writes to a
representative byte (`$2210`) land in the first 211 frames and never
recur -- `sub_F171` (`rom:F171-F187`) copies two fixed ROM templates
(`dat_BC7E`->`$2200`, `dat_BD7E`->`$226B`, 107 and 92 bytes) once, at race
setup, and is never called again. The "15 times" was three overlapping init
passes on boot, not fifteen separate rebuilds.

That raised a real puzzle: screenshots at frames 3000, 8000 and 12000 of
`run-01` show visibly different road shapes -- a curve, then straight, then
a gentler curve -- so *something* changes. Every graphics address the zones
reference (`$8000`, `$9ED2`, `$AA00`, ...) is ROM on this linear, unbanked
cart, so it cannot be the pixels. Diffing a full `$2200-$226B` dump at frame
3000 against one at frame 8000 finds exactly one differing region:
`$2220-$222F`. Tapping that region for the whole race finds exactly two
writers, `rom:D81A` and `rom:DA91`, each stamping the **same fixed 9-byte
pattern** into `$2224-$222C` every time it fires -- not a computed value,
a constant. `DA91` writes `F6 24 00 BD 1C 07 AB 1C 07`; `D81A` writes
`15 1D 06 F6 24 02 09 1D 06`. Across the race: `DA91` at f1260 and f4367,
`D81A` at f3861, f7079, f8969, f10865, f12755, f15713, f16488 -- `D81A` wins
and holds for long stretches, which is exactly why frames 8000 and 12000
(both inside a `D81A` stretch) show a straighter road than frame 3000 (inside
the one `DA91` stretch).

So the mechanism is a **binary toggle between two pre-baked 9-byte zone
snippets** -- one shaped like TEST's one corner, one shaped like its
straights -- patched into a fixed slot in an otherwise-static, copied-once
display list. Consistent with TEST's own shape (a rounded rectangle: one
corner radius, reused four times, per the track-format section below) not
needing more than two shapes. FUJI, with corners of differing severity,
almost certainly needs more than two snippets in the equivalent table, and
that table hasn't been located yet -- the next concrete thread if the full
curve system matters later.

**Why this matters for a second camera:** building a second player's road
view does not require reverse-engineering a curvature algorithm, because
there isn't one to find. It requires a second copy of the same fixed
template (trivial -- it's one more `sub_F171`-style blit at setup) and the
same kind of small-snippet patch, driven by player 2's own track position
instead of player 1's. That is a substantially easier Phase 1 target than
"parameterize the zone generator" implied.

### The road's DMA weight, measured properly with `dmabudget.py`

The project's own `tools/dmabudget.py` (MAME-calibrated cycle costs per
zone/object/byte, not reasoned about from scratch) settles the budget
question the previous write-up in this section had flagged as open.
`tools/probe-dlgfx.lua` decodes the live zone list at frame 3000 of
`run-01`: the race DLL (`$2200`) is 17 zones / 113 scanlines / 1-9 objects
each; the HUD DLL (`$226B`) is 21 zones / 146 scanlines. Feeding both,
object-by-object, through `dmabudget.py`'s constants:

    road DLL:     4,901 cycles  (16.4% of an NTSC frame)
    HUD DLL:      4,010 cycles  (13.4%)
    combined:     8,911 cycles  (29.8%)
    left for CPU: 20,957 cycles (70.2%)

**Comfortable headroom, not a tight budget.** And the same reasoning as
before still holds, now on firmer ground: splitting the existing 113 road
scanlines between two ~56-line camera views doesn't add to this total --
same scanline count, same object density, whichever way it's apportioned.
What would add a little: a handful of extra zone-boundary transitions if
the two halves' bands don't line up (each is `PER_ZONE` = 1.7 cycles, noise
at this scale), and drawing the other player's car into each viewport via
the object-slot system documented above (a ~15-line, ~15-byte-wide sprite
costs on the order of 200 cycles by this model -- also noise against a
21,000-cycle surplus).

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
