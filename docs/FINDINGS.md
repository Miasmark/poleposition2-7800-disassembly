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

## What's open

* The road bands: how many there are, and where the run ends.
* The rest of `$8000-$C1A4`. The display list names `$87xx`-`$8Bxx`, `$9Exx`,
  `$A3xx`, `$AAxx`, `$B0xx`; nothing yet says what they draw.
* The RAM handler at `$2456`: nothing selects index 0 and nothing writes
  that address during `run-01`. Settle whether any mode does.
* `run-01` (17,115 frames): the TEST track, a rounded
  rectangle, driven to completion. It includes a crash and a stretch where a
  system dialog took the controls, so input during that window is not the
  player's and should not be read as intent.
* `run-02` (11,942 frames): the FUJI track -- puddles, a sign struck, a lot of
  skidding, and the run ends when the clock runs out rather than at a finish
  line. So it exercises every hazard the manual names, and ends on the timer,
  which makes it the recording to find the clock in.
* The game is nearly silent without input, so the audio tooling that dominated
  the sibling projects will contribute little here.
