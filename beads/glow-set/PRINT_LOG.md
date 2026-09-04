# glow-set — print log

Newest entry first. Same convention as `beads/redaphid-portrait/PRINT_LOG.md`:
each entry records the geometry, whether it printed, and the one lesson worth
propagating to the recipe.

---

## sm-* motif batch — 2026-09-04 — FOUR CONSECUTIVE GOOD BEADS. The run that worked.

First unbroken run of the night. Every one of these came off usable:

| # | bead      | job        | ticks     | result                    |
|---|-----------|------------|-----------|---------------------------|
| 1 | kikko     | `e5a68f52` | 344/344   | halves force together, hold |
| 2 | kikko     | `7bba680f` | 344/344   | same                      |
| 3 | akoma     | `3dc0433b` | 674/674   | "passable" - first with hole compensation |
| 4 | changming | `39d80737` | 645/645   | clean                     |

### What changed, in the order it mattered

1. **A real brim.** `brim_type: auto_brim` reads like a brim is on; auto DECLINES
   to brim a compact 20mm slab, so every earlier plate ran with none.
   `--force-brim` (`outer_only`) fixed the Top lifting. This is the single change
   that turned failures into beads.
2. **`xy_hole_compensation 0.05`** for the deformed bores that remained once the
   part stopped lifting. Verdict on akoma: passable. Kept for the rest.
3. **Peg 1.8mm** was already right in the sm-* sets - see the entry below. The
   fit was never the problem here.

### Do not confuse the two Top failures

They look alike and are not. **Lifting** is the whole half curling off the plate
so it will not mate at all - cured by the brim. **Deformed bores** is the part
sitting flat with squished-oval sockets - that is first-layer squeeze-in, and the
lever is hole compensation, not adhesion. Fixing the first revealed the second.

### The pipeline that made it repeatable

3MF -> `elegoo-slicer.exe --slice 0 --outputdir` -> `docker cp` into
centauri-mcp:/tmp -> `upload_file` -> `start_print`. No GUI anywhere. The two
traps are that the CLI is a GUI-subsystem binary printing nothing to a console,
and that centauri-mcp declares no volumes so the file has to be put INSIDE the
container first. Uploads are refused mid-job (HTTP 400), so stage between prints.

Unfixed: CLI slices run 11-13m against the GUI's ~6m because the CLI uses its own
stored presets, not the 3MF's. Patching the template did nothing. Costs ~6 min a
bead and is not worth chasing mid-batch.

---

## test20c02 rerun — 2026-09-04 — THE TOP WARPS. Telemetry called it a success.

Job `7b6450e6`, `test20c02.gcode`, 347/347 ticks, layer 16 of 16, zero
`exception_status`, filament detected throughout. Every number said clean. The
part says otherwise: **the Top came off the plate WARPED and would not snap
into the Bottom.** The Bottom was fine.

This is the third time a run reported `task_status: 1` / full tick count while
the physical result was unusable (see `56b63725` and `b96babb5` below). The rule
stands and should never be relaxed: **no telemetry proves a part exists, and no
telemetry proves a part is FLAT. Only hands on the plate.**

### Why the Top and not the Bottom

The Top prints mating-face-down, and that face is perforated by three 2.6mm
socket mouths plus their 45-degree funnels. Its first layer therefore has
markedly less bed contact than the solid Bottom's, and less continuous
perimeter to anchor the corners. It is the half that lifts.

### The setting that was lying

The profile read `brim_type: auto_brim`, `brim_width: 5`, which looks like a
5mm brim is on. **`auto_brim` lets the slicer decide per object, and for a
compact 20mm slab it routinely decides NO brim.** So the plate ran with none
while the profile advertised one. `tools/build_3mf.py` gained `--force-brim`
(`brim_type: outer_only`) and the six `sm-*` 3MFs were rebuilt with it.
Cooling was already gentled - fan off 3 layers, full by 5.

### Why this may be the tray failure too

A warped part stands proud at the edge. A proud edge is exactly what the nozzle
catches on. That gives a causal chain the collision theory was missing an
initiator for: warp -> lifted corner -> nozzle clips it -> part breaks loose ->
extrudate balls onto the hotend -> blob levers the cover off -> 707. It also
explains why singles survived and trays did not without needing a separate
mechanism: a single has ~6 minutes and two objects for a lift to matter in; a
tray has 15 minutes, six objects and long inter-object travels.

NOT yet demonstrated - no print has been run with the forced brim. If the next
Top comes out flat, this entry is the explanation. If it warps anyway, the next
lever is bed temp 60 -> 65, changed ALONE.

---

## tray3-byobject — 2026-09-04 — IN FLIGHT. First structurally-different tray file.

Job `56b63725`, `beads/glow-set/print/tray3-byobject.gcode` (committed at `4426e88`),
15m27s / 922 ticks. Canvas checked BEFORE sending: `active_tray_id: 0`, tray 0
`status: 2`, black. **Outcome not yet known - it was still levelling when this was
written. Do not read a result into this entry.**

### What makes it different from the five that failed

Six objects printed **sequentially**, instead of two merged blocks printed
layer-by-layer. Each bead completes before the next begins, so the nozzle never
travels over a finished part at printing height - the mechanism behind 0/5.

Verified structurally in the gcode, not from the settings panel:

    print_sequence     = by object
    downward Z resets  = 5   -> 6 objects printed one at a time
                         (3.8 -> 0.2) x3 bottoms, (4.0 -> 0.2) x2 tops
    estimated time     = 15m 27s

Reached by splitting the two merged meshes in the Elegoo Slicer GUI
(right-click -> Split -> to objects). Without that split the same setting produced
one reset and a 2-second difference.

### [!] THE RISK PROFILE INVERTS - watch WHERE it fails, not just whether

Sequential printing removes mid-layer crossings but introduces a new exposure: between
beads the nozzle drops to Z=0.2 and moves past neighbours already ~4mm tall. The slicer
computed clearance and did not object, and 4mm is far below any gantry limit.

**So if this file fails, it should fail AT A TRANSITION, not mid-bead.** That
distinction is the next piece of evidence either way - a mid-bead failure would mean
the collision theory is incomplete.

### Two prior runs tonight, for the record

    8a2d0dee  14m54s  aborted at layer 0 on purpose - carried the collision settings
    5a9e908e  14m56s  stopped - by-object was SET but the meshes were still merged

---

## tray3-lowaccel — 2026-09-03 — the diagnosis: NOZZLE COLLISION ON INTER-OBJECT TRAVEL

Job `8a2d0dee`. Canvas verified BEFORE the run for the first time: `active_tray_id: 0`,
tray 0 `status: 2`, black. The pre-flight check finally happened.

**ABORTED ON PURPOSE AT LAYER 0** (298s, all preheat + levelling, nothing extruded) once
the gcode inspection below showed it carried the collision settings. No material wasted.
This job is the diagnosis, not a test result.

### [!!] THE ANSWER TO THE QUESTION THAT OUTLIVED EVERY OTHER EXPLANATION

**Singles 7/7, trays 0/5.** The mechanism is that **the nozzle clips a printed part while
travelling between objects**, tears it off the plate, and winds it onto itself. Multiple
CC2 owners report this exact fingerprint:

    "Something about the traveling between them. It always seems to clip the top
     of one and pull it off the bed. The more objects the earlier it happens too."
    "I physically watched one get ripped off by the extrusion nozzle."
    "When I try to print only 1 at a time it works great."

**Inter-object travel only exists on a multi-part plate.** That IS the split, as a
mechanism rather than a correlation.

| observation | accounted for |
|---|---|
| isolated part survived, crowded ones died | nothing travels past the isolated one |
| ooze strand arcing between two parts | the nozzle went there, at part height |
| rebuilt in ~2 layers after a thorough clean | clipping begins once parts are tall enough - nothing accumulates |
| dense nest of CURLED filament | extrusion peeled off a part top and wound on |
| scorched amber-brown core | older peeled material cooking across several prints |
| cold pull did nothing | correct, the bore was never involved |
| blob levers the cover -> 707 | downstream, as he said |

20mm beads, 16 layers, small bed-contact area is the worst-case geometry for it.

### [x] AND THE FILE PRINTING RIGHT NOW HAD THE COLLISION SETTINGS

The printer reported `14m54s` / 888 ticks; the file built here says `29m 59s` with
`M204 S1000`. **Re-slicing in Elegoo Slicer 1.5.3.5 regenerated it with the new slicer's
own accelerations** - the low-acceleration experiment did not actually run. Little lost,
because acceleration was never the lever. What the gcode did carry:

    z_hop_types          = Auto Lift    <- conditional; only 2 Z-lift moves in 33k moves
    travel_speed         = 500 mm/s
    reduce_crossing_wall = 0            <- reverted for the accel test

No effective Z-hop, 500mm/s travel, crossing walls freely. Precisely the configuration
owners name. **Lesson: `Auto Lift` is not Z-hop.** Verify lift by counting standalone
`G1 Z` moves in the gcode, not by reading the setting name.

### [!!] GOTCHA: `make_plate.py` MERGES THE BEADS, SO "BY OBJECT" DOES NOTHING

First attempt at the fix: `print_sequence = by object` was set and **took** - the gcode
header confirms it, and standalone `G1 Z` moves went from **2 to 1081**. The estimate
moved from **14m54s to 14m56s.** Nothing gained.

**Because the 3MF holds TWO objects, not six.** `tools/make_plate.py:114-115` does
`trimesh.util.concatenate(...)`, fusing all N beads into one `Bottom` mesh and one `Top`
mesh. The gcode shows exactly one downward Z reset (3.8 -> 0.2): print the whole Bottom
object, then the whole Top object.

**So the travel between beads is INSIDE a single object, and by-object cannot touch it.**
Sequential printing sequences objects; it cannot sequence islands within one mesh.

**Workaround in the GUI (what to do now):** select each object -> right-click ->
**Split -> to objects**, then re-slice. Beads are 3.8mm tall so the sequential clearance
rule does not block it.

**Pipeline TODO (not done - deadline):** `make_plate.py` needs a no-merge mode and
`build_3mf.py` needs to emit one parent object per bead. It is currently built around
exactly two parents (a Top+Decoration assembly and a Bottom), so this is a real refactor,
not a flag. Until then **the GUI split is a REQUIRED step for any ganged plate.**

### The fixes, strongest first

1. **Print sequence -> By Object**, not By Layer. Beads are 5.5mm tall so gantry
   clearance is a non-issue, and it removes inter-object travel entirely. **It turns a
   tray into a sequence of singles, and singles are 7/7.**
2. **Z-hop type -> Normal Lift** (not Auto), and **travel speed -> 100-150 mm/s**.
3. Fewer parts, more spacing, add a brim. An owner: 9-up failed three times, 4-up in the
   corners prints every time.
4. Re-check flow ratio and Z-offset. Over-extrusion raises ridges the nozzle then catches;
   Z-offset is set separately from auto-levelling on this machine.
5. **Inspect the hotend for a bend or a crept-out bronze section** before trusting a run -
   a collision can bend it, and "just knocking into a print is enough to bend it badly."

### [!] OPERATIONAL RULE, LEARNED FROM OTHER OWNERS THE EXPENSIVE WAY

**If a blob forms mid-print, CUT POWER. Do not press Cancel.** Cancel triggers a homing
move that drags the blob into the chute and snaps nozzles off.

### Retracted by the research, not just demoted

The first research pass led with the purge/wiper system. **The tray gcode is single-colour**
(`T0` twice, one toolchange line), so there is one purge at job start and the wiper cannot
be the engine. The wiper findings remain true about the machine - real CC2 weak point,
no-warranty consumable, 150-500h life, one spare in the tool kit, not sold retail - and
they matter again when we return to two-colour beads. They are not this failure.

Bed-region was also alive and is now the weaker of the two: the tray does span X 89-167
where a single only occupies X 118-138, so parts DO stand where a single never prints.
The collision mechanism explains the strand and the curl; bed region does not. Still
separable by printing ONE bead deliberately off-centre if the collision fixes disappoint.

---

## tray3blk again — 2026-09-03 — HALTED AT LAYER 2. ErrorCode 707, toolhead cover detached.

Job `a6916306`. Run after a full nozzle clean at 240C and a bed clean. Panel:

    ErrorCode: 707
    "Toolhead front cover detached. Please check if it is loose or abnormal"

Photos: `photos/2026-09-03-error707-toolhead-cover.jpg`,
`photos/2026-09-03-blob-on-toolhead.jpg`.

### [!!] THE CAUSAL ORDER, after he corrected me TWICE

I called the loose cover the root cause. **Wrong** - he reattaches it himself, so he knows
it was ON for the earlier runs. Then I called the blob the root cause. **Also wrong**, and
this is the important one, in his words: **"that blob is a RESULT of the failure."**

    ??? THE REAL FAULT  ->  print fails  ->  nozzle extrudes into open air
                        ->  blob forms on the toolhead
                        ->  blob props/levers the magnetic cover  ->  ErrorCode 707

**Every physical thing found tonight sits at the right-hand end of that chain** - the
nozzle coating, the nest, the blob, the detached cover, 707. Cleaning the nozzle and
reseating the cover are symptom treatment, which is exactly why each one appeared to work
and then the failure returned.

**The trap for research:** Elegoo's docs and owner reports describe *"waste piles up ->
props the toolhead -> knocks the cover off -> 707"*. That reads like a root cause and is
really the same downstream chain from the machine's point of view.

### What the research did settle

- The cover is held by **three magnets** and read by a **Hall sensor** - no clips, so
  "vibrated loose" is the wrong model. A merely GAPPED cover trips 707. Elegoo's own
  diagnostic: touch a paperclip to each marked magnet position.
- **No owner or Elegoo report links speed or acceleration to 707.**
- But the stock cowling is **>120 g** and rings the head at 20,000 mm/s2. Mass x accel is
  a real force here; the community fix is a **lighter cover** (~65 g), not a slower machine.

### Acceleration, since "slow it down" came up three times

`set_print_speed("silent")` is nearly useless - 0.5%. Real control needs re-slicing:

    the file that failed twice   M204 S5000    14m42s
    tray3-lowaccel                M204 S1000    29m59s

5x less acceleration, built and staged in `out/` with its 3MF. **Untested** - the evidence
points at the waste path first, and this stays a cheap experiment, not a diagnosis.

### Still open

**Why do multi-part plates fail when single beads do not?** Singles 7/7, trays 0/5. That
question has now outlived every explanation offered for it tonight.

---

## tray3blk @ 50% — 2026-09-03 — SPEED IS RULED OUT. One isolated part survived; the crowded ones did not.

Job `38f16300`, `tray3blk.gcode` unchanged, `set_print_speed("silent")` = 50%.
Photo: `beads/glow-set/photos/2026-09-03-tray3blk-silent-38f16300.jpg`.

**His hypothesis, tested properly and cheaply.** No re-slice, no upload - the printer
takes the speed change live and `PrintSpeedPct` in `get_status` confirmed 50 for the
whole run.

### [x] SPEED DID NOT CHANGE THE OUTCOME — AND BARELY CHANGED THE SPEED

    original run   879 ticks
    "silent" run   874 ticks

`PrintSpeedPct` read 50 the entire time and ticks still advanced at ~1/second of wall
clock. **"Silent" mode does not halve a print of this shape** - it throttles some move
classes and the short perimeter moves on a 20mm part are evidently not among them. So
this is a weak test of "slower" AND a strong result: the plate failed the same way.

The arithmetic said the same thing beforehand and is worth keeping: per-layer time is
**23 s on the single that works** (366/16) versus **55 s on the tray that fails**
(882/16). The tray already gives each part MORE cooling, not less.

### [!] THE PATTERN IN THE PHOTO: THE ISOLATED PART SURVIVED

- **One clean, complete part** - a `Bottom`, three pegs and the NFC pocket crisp, good
  surface. It is the one sitting **on its own**, away from the others.
- **The wrecked parts are the ones with a NEIGHBOUR**, and two of them are **joined by a
  thin filament arc** - an ooze strand strung directly from one part to the next.
- A crumpled wad with its own trailing strand.
- The hexagon is blobbed **along one edge only**, not uniformly.

**Contamination is not needed to explain this and neither is speed.** A strand running
between two parts is material carried on the nozzle during the travel between them.

**[?] TWO READINGS STILL ALIVE, and they need different fixes:**

1. **Proximity / travel ooze.** Fits best: crowded parts fail, the isolated one does not.
   Addressed by `tray3w45` - pitch 29 -> 45mm, `reduce_crossing_wall` on, `z_hop_types`
   Normal Lift, `retract_before_wipe` 70%.
2. **Plate position / bed levelling.** The survivor is also in a different REGION of the
   bed, and a single bead always prints dead centre - which would explain the whole
   singles-vs-trays split on its own. **Not yet excluded.**

**THE TEST THAT SEPARATES THEM: print ONE bead deliberately OFF-CENTRE**, where the tray
parts died. Singles are 7/7 at centre. If a lone bead fails out there it is the bed, and
no amount of spacing or retraction will fix it.

**Blocked on the same thing both times: no way to get new gcode onto the printer.**
`upload_file` rejects every path tried - `D:\...`, `D:/...`, `/mnt/d/...`, `/projects/...`
and the `claude-code` container's `/tmp`. `centauri` and `claude-code` do not share a
filesystem. Live controls (`set_print_speed`, `set_fan_speed`, `set_temperatures`) still
work on files already on the printer, which is how this run happened at all.

---

## test20c02 (3rd run) — 2026-09-03 — **PRINTED. AND IT SNAPS.**

Job `d8a997d1`, `test20c02.gcode`, one 20mm bead, both halves, black `T0`,
16 layers, 266s, 1.64g. 20:57:58 -> 21:08:17.

**He confirmed it with his hands: the halves snapped together well.**

### THIS RETIRES THE OPEN GEOMETRY QUESTION

`PEG_CLEAR 0.01` had been built but never printed. It is now hardware-proven,
and the snap-fit ladder is closed:

| step | PEG_HEIGHT | PEG_CLEAR | engagement | hardware result |
|---|---|---|---|---|
| start | 1.2 | 0.05 | 0.50mm | plainly loose |
| depth | 1.8 | 0.05 | 1.00mm | snaps, won't hold |
| clearance | 1.8 | 0.02 | 1.00mm | "perfect", later slightly loose |
| clearance | 1.8 | **0.01** | 1.00mm | **snaps and holds. SHIP THIS.** |

Depth is maxed out - Top is 3.00mm, the socket eats 2.05mm, leaving a 0.95mm
ceiling. Gotcha #40 holds: **fix depth first, clearance second.**

---

## test20c02 (2nd run) — 2026-09-03 — bare plate. **NO FILAMENT WAS LOADED.**

Job `b96babb5`, 15:09:11 -> 15:18:48. Same file, same machine, same nozzle.

**[?] CAUSE NOT ESTABLISHED - and my first answer was wrong.** I said this was mine:
the cold pull before it unloads by design and I started without re-loading. But I
only checked `get_canvas_status` AFTER the run, and the machine reads
`active_tray_id: -1` / tray `status: 1` after ANY job finishes - **including the bead
that printed perfectly at 21:08.** That reading is what SUCCESS leaves behind, so it
cannot separate the two runs. The cold pull genuinely does unload and re-loading is
still right, but **why this plate came out bare is still open.**

### THE TWO RUNS ARE A CONTROLLED PAIR, AND THEY PROVE THE TELEMETRY IS BLIND

`b96babb5` and `d8a997d1` are **the same gcode file**. Compare what SDCP said:

| | `b96babb5` (bare plate) | `d8a997d1` (real bead) |
|---|---|---|
| `task_status` | 1 (success) | 1 (success) |
| `CurrentLayer` | climbed to 16 | climbed to 16 |
| `CurrentTicks / TotalTicks` | complete | complete |
| `filament_detected` mid-print | **1** | 1 |
| `exception_status` | empty | empty |
| **what was on the plate** | **nothing** | **a bead that snaps** |

Every field agrees. The outcomes are opposite. There is no remote check that
separates these two runs - only a human looking at the plate. See
`printer_filament_detected_gate` in memory; the sensor reports filament PRESENT,
not filament FLOWING.

Corollary worth keeping: at idle after this successful run `filament_detected`
read **0**. Idle 0 means nothing is parked at the sensor between jobs. It is not
a fault and it is not a reason to refuse to print.

---

## What the print history actually supports about red

He suspects the red filament. The history is consistent with that but does not
isolate it, and the log should say so rather than bank a win:

    test20red      17e2cd47  ok        single bead
    test20blk      5e5a8e33  ok        single bead
    test20red      c0aa169a  ok        single bead
    test20peg18    86fbb0e6  ok        single bead
    test20peg18blk 21da0e21  ok        single bead
    test20c02      f9878112  ok        single bead
    plate3         1f327292  STOPPED   multi
    tray6red       66b3d718  STOPPED   multi
    tray3          9b064b8f  STOPPED   multi   red
    tray3blk       af01d730  STOPPED   multi   black - parts DID adhere
    test20c02      b96babb5  ok*       single  (*bare plate, no filament)
    test20c02      d8a997d1  ok        single bead - SNAPS

**Two variables are still braided together: colour and parts-per-plate.** Every
single-bead run has produced a part. Every multi-bead run has been stopped. Red
runs that failed were also multi-bead; the one multi-bead BLACK run adhered
properly but smeared, which is a different failure mode.

So the honest statement is: **red is implicated in the adhesion failure and black
is not, but plate population is an unseparated confound.** The test that would
settle it is a 3-bead RED tray against the 3-bead BLACK tray already run - and
with the fest on 09-06 that test is not worth the filament. Print black singles.

---

## tray3blk — 2026-09-03 — ADHESION DID NOT REPRODUCE IN BLACK. Stopped for a different mess.

Job `af01d730`, `tray3blk.gcode`, 3 beads, black `T0`, 16 layers, 882s, 3.9g.
**A deliberate single-variable twin of the failed `tray3.gcode`**: identical layer
count, print time and filament mass, differing only in `color_map`
(`#000000` t:0 vs `#FF0000` t:1). Same geometry, same layout, same everything else.

He stopped it around layer 6-8 because it was making a mess.

### THE RESULT THAT MATTERS: the parts STUCK

Every part on the plate was firmly adhered and had built up real height. That is a
categorical difference from the red runs, where his description was *"an oozing,
undifferentiated mass stuck to the print head with nothing layed."*

- A clean, well-formed **purge line** went down and stayed down.
- **No blob formed on the nozzle.**
- `filament_detected == 1` with `CurrentLayer >= 1`, the check that actually means
  something.

**Slot tally is now black `T0` 6/6, red `T1` 1/4.** The slot correlation has survived
every test all session and nothing else has. Red / `T1` is implicated; colour is no
longer a live explanation for the ADHESION failure.

### Verify the slot from the machine, not from memory

`get_canvas_status` reports it directly and settles it before a run:

    tray 0  #000000 black  status 2  <- active_tray_id
    tray 1  #F72221 red    status 1
    tray 2/3 white / blue  status 0  (empty)

That is a 10-second check that removes the single most expensive trap in this project.
Do it instead of asking whether the right spool is loaded.

### The NEW failure, which is not adhesion

From the photograph:

- Heavy **grey-white smeared material** on two of the parts - deposited or dragged, not
  those parts' own extrusion.
- Two adjacent parts **merged at their boundary**.
- A long trailing strand whose **root is visibly REDDISH**.
- One part (the hexagon) comparatively clean.

**[!] THE RED ROOT IS THE EVIDENCE: THE MELT ZONE WAS NEVER CLEARED.** The blob was
peeled off the OUTSIDE only. The previous entry already said a cold pull belonged in
the cleanup and it was skipped. Old red plus thermally degraded PLA is still upstream
and dumping intermittently onto whatever part sits underneath - which fits damage that
is **irregular and part-specific** rather than uniform.

**[?] NOT SEPARATED YET:** edge-curl being struck by the nozzle explains edge-heavy
damage too, and the damage IS edge-heavy on the triangles. One photograph cannot
distinguish these. Contamination dumping is random across parts; curl-strike repeats in
the same places on the same edges. **Do not commit to one of these from this run** -
that is the mistake this log has now recorded three times in one day.

### Next: cold pull, then the BASELINE, not the tray

`test20c02.gcode` - one bead, 6 min, 1.64g, black `T0`, the exact file that produced the
bead he called perfect. Clean result means the melt zone was it. Same smearing means it
is mechanical - nozzle height or curl - and the new 0.6mm nozzle is the next move rather
than another print.

---

## tray3 FAILED THE SAME WAY — 2026-09-03 — it is the machine, not the batch

Job `9b064b8f`, 3 beads, centred, red `T1`, clean nozzle, no cancel in front of
it. Same outcome: *"I see it trying to print, but I don't see any plastic
layed."* Stopped at layer 4.

### Two theories I wrote down today, both wrong

1. **"The cancel before it left a blob."** Killed by this run: the nozzle was
   cleaned first and it failed identically.
2. **"The red glitter is clogging the nozzle."** Killed by the photograph of the
   removed blob - it is a large mass of plastic. **A clog starves; it does not
   produce that much material.** I asserted it with more confidence than one
   colour-correlation deserved.

Both were single-explanation guesses reached before the evidence could support
them. What has actually held up all session is the boring tally: **black on `T0`
is 5/5, red on `T1` is 1/4**, and the one red success came straight after a
hand-load.

### The failure is ADHESION, and it is self-reinforcing

Plastic extrudes normally and never sticks; it curls up onto the nozzle. The
reason it repeats after cleaning is the feedback loop: **this machine levels by
touching the nozzle tip to the bed.** Any film left on that tip makes the probe
read the bed as closer than it is, so the nozzle parks too high, so nothing
sticks, so more plastic collects on the tip. Every run since the first blob has
probed with a fouled tip, which means the stored mesh is suspect too.

So cleaning flow is not enough - **the outside flat face of the tip has to be
bare metal, and the bed must be re-levelled afterwards.**

### Reading the blob

It carried fine dark streaks marbled through the red plus a grey-brown patch.
Two different things, worth telling apart:

- **Marbled dark streaks: unpurged BLACK filament**, not burning. The `T0`->`T1`
  colour change flushes 200mm (`M6211 A1 L200 T1`), and transition material
  looks exactly like this, following the flow lines.
- **Grey-brown patch: thermally degraded PLA.** That blob sat wrapped around a
  block at 210 degC, then 240 degC during cleaning, for the better part of an hour.

In the hand: unpurged black stretches like the red does; burnt PLA is brittle,
crumbles to hard specks and smells acrid. The consequence either way is that
degraded material is probably still in the melt zone, so a **cold pull** belongs
in the cleanup, not just an external peel.

### Next step is a BASELINE, not another experiment

`test20c02.gcode` is still on the printer - the exact file that produced the
bead that fit perfectly (black, `T0`, 1.64g, 6 min). Clean the tip, re-level,
print that one file. It prints -> the machine is fine and the batch work can
resume in black. It fails -> the machine is the problem and no amount of
geometry work matters until levelling is fixed.

---

## tray6red FAILED — 2026-09-03 — nothing laid down; and the brim lesson is WRONG

Job `66b3d718`, 6 motifs in red on `T1`. Outcome, in the user's words: *"an
oozing, undifferentiated mass stuck to the print head with nothing layed down."*

**Nothing adhered at all.** That rules out the obvious story (a part detaches
mid-print and the nozzle drags it) — material was extruded, `filament_detected`
read 1, layers advanced to 2 and beyond, and none of it ever reached the plate.
This is a FIRST-LAYER failure, not a batch-size failure, and the signature is
worth naming because the two look identical in the API and opposite on the bed:

- **parts on the plate, one missing, blob** -> adhesion of one part failed
- **plate bare, everything on the nozzle** -> the first layer never took at all

### The most likely cause is the CANCEL that preceded it

The previous job (`plate3`, wrong shapes) was cancelled mid-print at the machine,
and this print was started **immediately afterwards without inspecting the
nozzle**. A cancel parks a hot nozzle carrying molten plastic; if a blob forms
there, the next print cannot lay a first layer and simply feeds the blob. Not
proven, but it fits "nothing laid down" better than anything geometric, and the
geometry had already printed fine at one bead.

**Rule: after ANY cancelled print, clean the nozzle and confirm the plate before
starting the next job.** Do not chain a start onto a cancel.

### `auto_brim` produces NO BRIM. The "brim wins" entry below is wrong.

Measured in the sliced gcode, not inferred from settings:

    brim_type = auto_brim    brim_width = 5    skirt_loops = 0
    TYPE:Brim  extrusions: 0        TYPE:Skirt extrusions: 0

And the same is true of `test20-peg18c02` — **the bead that fit perfectly and
printed cleanly also had zero brim.** So a brim has never actually been tested
on this bead family, and whatever fixed the earlier smeared print, it was not
the brim. `auto_brim` means *the slicer decides*, and here it decides none.

This matters beyond the brim: the earlier entry verified `brim_type=auto_brim`
in the 3MF and treated that as proof a brim existed. **A setting being present
in the project file is not evidence the slicer acted on it** — the same class of
error as reading `task_status: 1` as proof a part exists. Check the gcode for the
extrusions, not the config for the intent.

### Also worth recording: five variables moved at once

Against the last good print this changed part count (2 -> 12), bed spread
(centred -> x 43.6..212.8), duration (6 -> 28 min), silhouette (quatrefoil -> 6
motifs) and filament (black `T0` -> red glitter `T1`). Even with a clean result
that proves nothing, and with a failure it makes attribution impossible. The
same mistake this log already records against the funnel print, repeated while
scaling up.

Re-proving at THREE beads, centred (x 82..167, y 101..152), red, everything else
as the bead that printed perfectly.

---

## test20-peg18c02, 20 mm black — 2026-09-03 — SNAP FIT SOLVED

Job `f9878112`, `T0`, 16/16 layers, `filament_detected` 1 confirmed at layer 4.

**User's verdict: "that one was perfect!"** The snap fit is solved. The numbers
that did it, and the two-step path that found them:

| step | `PEG_HEIGHT` | `PEG_CLEAR` | engagement | result |
|---|---|---|---|---|
| start | 1.2 | 0.05 | 0.50 mm | plainly too loose |
| depth | **1.8** | 0.05 | **1.00 mm** | *snaps* audibly, still won't hold |
| clearance | **1.8** | **0.02** | 1.00 mm | **perfect** |

**Canonical constants for this bead family: `PEG_HEIGHT = 1.8`,
`PEG_CLEAR = 0.02`, with `SOCKET_LEADIN = 0.4` and `PEG_CHAMFER = 0.35`.**

The ordering is the lesson. Depth first: at 0.50 mm engagement no clearance
value would have saved it, because there was almost no length over which any
clearance applied. Clearance second, and only once the part already snapped.
Doing them in the other order — or together — would have produced a fit that
worked without anyone knowing which change earned it.

Every one of the 30 bead sets on `japanese-mon` / `chinese-glow` / `adinkra` was
built at `PEG_HEIGHT` 1.2. **None of them would have snapped.** They need
rebuilding at 1.8 / 0.02 before the fest.

---

## test20-peg18 BLACK, 20 mm — 2026-09-03 — PRINTED; the idle gate was wrong

Job `21da0e21`, `test20peg18blk.gcode`, 16 layers, 1.64 g on **T0 (black)**.
Verified the honest way: `filament_detected` read **1 at layer 1 and still 1 at
layer 4**, with layers advancing — the two phantom runs read 0 throughout.
Finished `CurrentTicks == TotalTicks` (346/346).

### The rule I wrote an hour earlier was falsified by this print

After the second phantom print I wrote "require `filament_detected == 1` while
IDLE before `start_print`". **This job sat at idle 0, loaded normally at 210 °C,
and printed.** That gate would have blocked a good print. The user said *fire it
anyway* and was right.

Re-sorted by slot, the record stops being about the flag:

| slot | runs | outcome |
|---|---|---|
| `T0` (black, FIRST slot) | `5e5a8e33`, `21da0e21` | 2/2 produced parts |
| `T1` (red, SECOND slot) | `17e2cd47`, `86fbb0e6` | printed nothing |
| `T1` (red) | `c0aa169a` | parts, but hand-loaded first |

**`T1`'s auto-load is the thing that fails.** Every `T1` failure also happened to
show idle-0, which is how the idle flag looked causal across three runs until a
fourth broke it. Worth naming as a shape of bad inference, not just deleting:
the correlation was inherited from the confound.

Surviving rule: `filament_detected` must read **1 once `CurrentLayer >= 1`**;
if layers climb with it at 0, `stop_print`. Prefer `T0` for single-colour jobs.

Second phantom print, for the record: `86fbb0e6` (red, `T1`) ran all 16 layers,
reported `task_status: 1`, and left a **completely clean plate — not even a purge
line.** "No purge line" is the question to ask, because it separates *never
loaded* from *loaded but did not stick*.

Also: a warm bed collapses the ~12 min preamble to ~3. A single sleep-until-done
sails past the abort window; poll instead.

### FIT VERDICT: it snaps. Barely too loose to hold.

User, on the printed pair: *"almost perfect! It makes the 'snapping' noise.
Barely, barely too loose for sticking together."*

**This confirms #40's diagnosis.** At 0.50 mm engagement the halves were plainly
loose; at **1.00 mm they snap** — same 0.050 mm radial clearance, so the whole
change came from depth. Engagement length was the fault, not clearance, and
reaching for `PEG_CLEAR` first would have chased the wrong number.

Now, and only now, clearance is the right knob: **`PEG_CLEAR` 0.05 -> 0.02**
(radial; 0.10 -> 0.04 mm diametral). Peg height stays 1.8 so this remains a
single-variable step. If it overshoots to too-tight that is the recoverable
direction — the funnel and the chamfered tip both help it start.

---

## test20-peg18, 20 mm red — 2026-09-03 — PEG HEIGHT 1.2 -> 1.8

### The red reprint worked, and gave the first real fit data

`test20red.gcode` reprinted once red was loaded in **tray 1** (`t:1`, the slot
the file was always keyed to — it was empty the first time). Job
`c0aa169a`, `task_status: 1`, 608 s, `filament_detected: 1` from layer 1.
Parts came out.

**Verdict from the user: close, but TOO LOOSE.**

### The funnel ate the grip — measured, not guessed

Measured off the exported STLs by cross-sectioning both halves at 0.1 mm steps
and comparing socket bore radius against peg radius at the same seated height:

| depth into socket | socket r | peg r | radial gap |
|---|---|---|---|
| 0.0 mm (mating face) | 1.749 | — | — |
| 0.2 mm | 1.549 | 1.299 | 0.250 |
| 0.4 mm | 1.349 | 1.299 | **0.050** |
| 0.8 mm | 1.349 | 1.299 | **0.050** |
| 1.0 mm | 1.349 | 1.103 | 0.246 |

Only **0.50 mm** of the peg ever sat at the design clearance. `SOCKET_LEADIN`
(0.4 mm of funnel) and `PEG_CHAMFER` (0.5 mm of tip taper) between them consume
most of a 1.2 mm peg. The funnel was added to fix ovalised socket mouths and it
worked, but it bought that by spending the grip.

**`PEG_HEIGHT` 1.2 -> 1.8** restores it: measured engagement **0.50 -> 1.00 mm**,
with the radial gap held at 0.050 mm so this is a single-variable change.
Bottom half grows 2.70 -> 3.30 mm tall; the plate goes 15 -> 16 layers.

### Fill quality on the mating face is inferior, and it is not cosmetic

The user zoomed in on the socket face and called it: the fill there is visibly
worse than on the other half, and he asked whether that makes the tolerance
imprecise. **It does.**

- The bore is **not round.** The funnel's concentric steps form cleanly on one
  side; the other side has a smooth mass of material encroaching into the
  opening. So the clearance is not uniform — a peg can be loose overall and
  still only touch on one axis.
- The face is **ridged**, with valleys between adjacent beads and small pits.
  Two halves resting on high spots never seat flush, which steals engagement
  on top of the little the geometry allowed.

**Root cause is orientation.** That face is the **first layer** — the Top half
prints mating-face-down against the plate, so the precision face is drawn in
the most-squished layers. The proof is in the same photo: the *Bottom* half's
mating face is a **top surface** and is visibly smoother. Same print, same
filament, opposite quality.

The red filament is **glitter-loaded PLA** (the sparkle is in the material),
which resolves small features worse than the black did — so the black print's
"round, open and flush" sockets did not transfer to this one.

**Candidate next lever, NOT yet done:** flip the Top half in the export so its
mating face is a top surface instead of the first layer. The Top's outer face
is the back of the bead, so nothing cosmetic is lost by putting it on the
plate, and the sockets become blind holes drilled downward from a top surface —
which also removes the reason the funnel exists. This changes shared export
orientation for all 30 bead sets, so it wants a deliberate decision.

---

## test20, 20 mm — 2026-09-02 — PRINTED ON SLOT 1; SOCKET FUNNEL WORKS

Second attempt, and the one that produced parts. Both halves, black, slot 1.

### The first attempt printed NOTHING, and reported success

`test20red.gcode` targeted **slot 2**, which had no filament in it. The job ran
all 15 layers with a dry extruder and finished with **`task_status: 1`**,
`CurrentTicks == TotalTicks`, empty `exception_status`. I reported it as a
successful print. He looked at the machine: *"looks like nothing printed at
all."*

**`task_status: 1` means the gcode ran. It is not evidence that a part
exists.** Every check available in the API is a check on the JOB, and they all
stay green when nothing is extruded.

**The tell was `filament_detected`, and it was there the whole time.** It read
**0 for the entire dry job** — including mid-print at layers 10 and 13, with
`filament_detect_enable: 1`. This log's own earlier entry says that flag reads
0 through the preamble and flips to 1 once loading completes, so a 0 at layer
13 contradicted the note outright; it got explained away instead of read. On
the successful slot-1 run it read **1** by layer 1. That is the check to watch.

Cheap prior for next time: every recent successful job draws from `t:0`
(slot 1). A job aimed at another slot is the unusual one — confirm the filament
before starting, since the API exposes no slot inventory at all.

### The socket funnel works

Before, each socket was ringed by a **raised crater of curled extrudate**
standing proud of the mating face, with the bore ovalised and partly occluded.

After, with `SOCKET_LEADIN = 0.4`: the sockets are **round, open, and flush** —
no raised rim at all, the surrounding face is flat, and the countersink shows
as clean concentric steps (the 45° chamfer stepped at 0.2 mm layers). Pegs came
out formed with their tip taper intact. Both halves lay flat; no obvious lift,
so the brim and the delayed cooling look right, though neither was isolated.

Caveat worth keeping: this print changed **four** things at once relative to
the photographed one — funnel, `seam_position=random`, brim, delayed cooling.
The old part was made from a pre-sliced gcode predating all of them. So the
funnel is not independently proven; it is only consistent with the improvement.

**Still unproven: the snap fit.** Neither half has been test-fitted and no NFC
tag has been seated. redaphid-portrait needed six iterations before the halves
gripped.

Minor: a small ooze blob with whiskers fused to the Top half's rim at one
point. Cosmetic, trims off.

---

## test20-red, 20 mm solid red — 2026-09-02 — first attempt, printed nothing

**The box has a slicer after all, and it slices from the command line.** It is
`D:\tools\elegooslicer\elegoo-slicer.exe` — *with a hyphen*. Searching for
`ElegooSlicer.exe` finds nothing, which is exactly how this log and the vault
both came to say "no slicer is installed on this box". He corrected it.

    D:\tools\elegooslicer\elegoo-slicer.exe --slice 0 \
        --outputdir <dir> <project.3mf>          # -> <dir>\plate_1.gcode

It is a GUI-subsystem binary and prints **nothing** to the console — `--help`
returns zero bytes. Judge it by whether `plate_1.gcode` appeared, never by the
log. The 3MF's embedded `project_settings` are honoured, so the brim, seam and
cooling patches survive into the gcode and can be grepped there.

**Every "cannot print without a human slicing once" note in this repo is now
stale.** The 3MF → gcode → upload → print path is autonomous.

What printed: the quatrefoil at **20 mm** (`BEAD_R=10`), single filament, on
**slot 2 (#FF0000 red)**. 20 mm is the floor — at 19 mm `place_pegs` fails, so
there is no smaller version of this shape. 15 layers, 5m57s, 1.64 g.

Outcome confirmed the documented way, not by eye: job
`17e2cd47-ef34-476a-babf-98d436df70e7` returned **`task_status: 1`** in
`print_history`, reached layer 15/15 with `CurrentTicks == TotalTicks` and an
empty `exception_status`. 591 s wall clock including preamble.

**The chamber camera cannot see the parts.** It looks across the front lip of
the plate, so a bead at the plate centre (110-146, 128) is out of frame and the
plate reads as *empty* both before and after a successful print. Do not use a
snapshot to decide whether something printed — it looks identical either way.

This is the **first print carrying the three fixes**, all confirmed present in
the gcode itself rather than assumed: `brim_type=auto_brim` / `brim_width=5`,
`seam_position=random`, and `close_fan_the_first_x_layers=3` with
`full_fan_speed_layer=5`. Filament draw was `0.00, 546.04, 0.00, 0.00` — slot 2
only, so the single-colour assignment is right.

### The socket defect this was built to fix

From the photo of the 32 mm black print: the three peg sockets came out
**ovalised, not round**, each ringed by a curled rim of extrudate standing
proud of the face, with loops of stringing around the bore.

`tz` — the plane the sockets open onto — is the **mating face, and that face
goes against the plate**. So the socket mouth is drawn in the very first
layers, the ones that get squished. A 2.7 mm bore is already the hardest thing
on the layer to trace cleanly, and first-layer squish then pushes material into
it. That is the ovalisation and the raised rim.

Fix: a **45° lead-in funnel at the socket mouth**, `SOCKET_LEADIN = 0.4`.
Measured on the exported STL — **3.49 mm at the mouth tapering to the nominal
2.69 mm bore by z=0.4** — so the two most-squished layers now trace a
noticeably larger circle and the squeeze-out has somewhere to go. It doubles as
the entry taper for the peg, the counterpart to the chamfered peg tip in
gotcha #30.

Note the old print was made from a **pre-sliced gcode that predates all three
fixes**, so its stringy socket masses are also the `seam_position=aligned`
failure this log already described. Do not read the new print as testing the
funnel alone — it changes four things at once.

---

## two-colour variants — 2026-09-02 — built + verified, NOT sliced, NOT printed

Glow-green body with a **black figure raised on the show face**. Adds a third
part, `Decoration.stl`, to the existing `Bottom`/`Top` pair. Built by
`build_talisman.py` with `BEAD_GLYPH="<theme>:<name>"` (themes from
`glyphs.py`: `star`, `groove`, `sigil`); leaving `BEAD_GLYPH` unset still
produces the single-filament bead exactly as before. The decoration itself is
built by the new `deco.py`.

**Raised, not inlaid, and the reason is print economics.** Filling a carved
groove with black means every layer from the recess floor to the show face
contains both colours — two filament swaps per layer for ~6 layers, which on
this machine is a large wipe tower and minutes of purge per bead. Standing the
figure on the show face instead makes every layer below it pure glow and every
layer above it pure black: **exactly one filament change for the whole bead**.
It looks the same — an opaque black figure on a glowing green field.

Built and verified on the 24 mm quatrefoil, all three themes: non-manifold 0 on
all three parts, string hole open, all three peg sockets correct blind floors,
`Decoration.stl` at **z 3.010–3.510** (show face 3.0 + 0.01 lift + 0.5 relief),
confirmed by reading the exported STL rather than trusting the build log.

`groove` is the best of the three by a distance — concentric rings, centred,
fills the face. `sigil` and `star` needed `deco.fit_glyph` to centre and grow
them; they were written for a 22 mm round medallion carved as a recess, and a
small off-centre mark that reads fine as a self-shadowing groove reads as a
speck when raised.

**Lessons captured** (now recipe gotchas #38 and #39):

- **Blender 5.0 headless needs `--gpu-backend opengl`.** Without it `-b` hangs
  forever on Vulkan context creation — ~0.03 s CPU, ~18 MB, zero output, never
  reaching the script. `blender --version` still works and proves nothing.
- **Never UNION decoration primitives that share a face or a tangent.** Bars
  and caps all spanning the same z are coplanar; a cap of radius exactly `w/2`
  is tangent to its bar; a connected stroke path emits duplicate caps at shared
  endpoints. All three together gave 1020 non-manifold edges. Union oversized
  in Z with jitter and let the crop cut the exact slab.
- The pipeline's usual `remove_doubles` at 0.005 **tears 0.8 mm strokes apart**.
  Use 1e-5 on decorations.

**Extended to the whole `shapes.py` family.** `BEAD_SHAPE="shape:<name>"` now
builds the 14 silhouettes in `shapes.py` (they are drawn at final size in
absolute mm, so `BEAD_R` does not apply to them). 13 of 14 built; themes are
cycled and seeded per shape so each bead is unique and reproducible.

**`heart` is excluded and it is not this work's fault** — it fails identically
with no decoration at all, `Bottom=553 Top=553` non-manifold, so the silhouette
breaks the body pipeline. Verified by building it single-colour. Worth fixing
separately; it is a good shape to have in a trade batch.

Building the whole set rather than one bead is what exposed the remaining
bugs, and two of them were design errors rather than solver quirks:

- **The 6.2 mm glyph envelope was inherited from the wrong problem.**
  `GLYPH_R_MAX` exists for *carved* glyphs, which cut 1.2 mm into the show face
  and therefore had to clear the peg sockets and the string hole underneath. A
  **raised** figure removes no material and sits entirely above the show face,
  so those features are irrelevant to it. The only real limit is the
  silhouette. Dropping the cap lets the figures be bolder.
- **Centring on the origin is wrong for a concave shape.** On `moon` the
  crescent bite reaches the origin — clearance there is 0.75 mm — so an
  origin-centred groove was sliced into fragments by the silhouette crop, which
  reads as a mistake rather than a design. The figure is now placed at the
  origin only when it has room to spare, and otherwise at the silhouette's best
  interior point, which `place_pocket` already solves for. Ring glyphs are also
  shrunk to fit (`pine` lost its rings into the branch notches for the same
  reason).

**Open — do not read this entry as "done":**

- **Never sliced, never printed.** Same wall as every other bead here: the
  printer only runs `.gcode` and no slicer is installed on this box.
- **There is no glow filament in the profile.** The saved template describes
  four Elegoo PLA slots as black / red / white / blue. The 3MF is built with
  the body on **slot 2** and the decoration on **slot 1 (black)**, and
  `build_3mf.py --body-colour "#7CFC00"` rewrites slot 2's colour so the
  slicer preview shows green. That makes a wrong slot **visible** rather than
  silent — but glow filament still has to be physically loaded into slot 2, or
  the bead prints red.
- Snap-fit and NFC seating remain unproven on this shape, as for the
  single-colour quatrefoil.

---

## quatrefoil 32mm — 2026-09-02 — printed, brim confirmed as the adhesion fix

Printed from `ECC2_0.4_quatrefoil_Elegoo PLA _0.2_8m9s.gcode` (already on the
printer, single-colour black PLA, both halves on one plate, 15 layers, 3.36 g).
Started over the MCP; job `ef3276c3-2fd7-45b5-97c9-1cb076978032` finished with
`task_status: 1` and no `exception_status`. Both halves came off cleanly formed.

This is the **single-colour diagnostic print** that Vikunja #45 asked for, and
it settles the brim conflict that task flagged: `PRINT_GUIDE.md` says no brim,
the adhesion diagnosis says use one. **The brim wins.** The profile that printed
carries `auto_brim` at 5 mm, and the shield that failed earlier carried no
printer profile at all — three files, geometry only — so the slicer fell back to
whatever was loaded and produced no brim. Geometry was never the problem.

Sequence timing, for anyone watching a future print and wondering if it hung:
about **12 minutes of preamble** before the first layer — preheat to 140 °C,
home, a long dense bed-level mesh, nozzle wipe, then a second heat to 210 °C and
a filament load/purge. During the purge the job clock ticks up while
`remaining_time_sec` stays pinned and the toolhead sits parked at (52.5, 264).
That looks exactly like a hang and is not one. `filament_detected` reads **0**
for the whole preamble and only flips to 1 when the load completes — do not read
an early 0 as "no filament loaded".

**Lessons captured**:

- **The printer only runs sliced `.gcode`.** A generated `.3mf` uploads happily
  and then sits inert; `list_files` shows it with `layer: 0`, `print_time: 0`,
  `color_map: []`, versus populated values on every file that has really
  printed. Check those fields before calling `start_print`.
- **No slicer is installed on this box**, so 3MF -> gcode cannot be done
  headlessly. An agent can rebuild geometry and bundles alone but cannot get a
  *new* design onto the plate without the GUI running once.
- `start_print` returning `Ack: 0` is not proof of printing. Confirm `state: 2`
  with a `TaskId`, then confirm the outcome in `print_history` —
  `task_status: 1` is success, `2` is failed/cancelled.

**Open follow-ups**:

- The **24 mm** quatrefoil (`print/quatrefoil24/`) is built and verified but has
  never been sliced, so it has never printed. It needs one pass through Elegoo
  Slicer. Its 3MF is correct: extruders `1/1/1/1`, `auto_brim` 5 mm,
  `seam_position` random.
- Neither half has been test-fitted, and no NFC tag has been seated in the
  pocket. Snap-fit grip at `PEG_CLEAR` and the 10.5 mm pocket are both unproven
  on this shape — redaphid-portrait needed six iterations before the halves
  gripped, so do not assume this one is done.

---

## Known intermittent contaminant — cat hair on the plate

Reported by the user 2026-09-02: he has washed the plate repeatedly and keeps
finding stray cat hairs on it, and expects some are still there.

This is worth writing down because it **mimics a geometry or calibration fault
and is not one**. A hair is a point contaminant that lands somewhere different
on every plate, so the printer "fails, gets fixed, then fails again" — a
pattern that reads like a bad Z-offset but is really a fresh hair in a new
spot. Do not re-derive a calibration theory from an intermittent first-layer
failure on this machine until the plate has been checked.

Which face gets hurt depends on the half, because the two print in opposite
orientations (`.claude/skills/bead-stl-export/export.py`: `Bottom: 180`,
Top unflipped):

- **Top** prints with its **socket / mating face against the plate**. A hair
  here lands on the surface that has to seat flat, in among the peg sockets.
  The failure presents as *the halves will not grip* — which invites blaming
  `PEG_CLEAR` and re-cutting geometry that was fine. Check the mating face
  before touching peg clearance.
- **Bottom** prints with its **silhouette / show face against the plate**, so a
  hair there is a cosmetic divot on the face that is meant to glow.

Practical notes: a solvent wipe lifts oils but not hair — hair needs tape, a
lint roller, or a rinse under running water. Re-contamination happens while the
plate air-dries or sits open, so the pass that matters is the one done
immediately before starting the print, not at cleaning time. Keeping the
enclosure shut between prints is the cheap mitigation.

Because it is random, the honest hedge for a batch is to **print spares and
inspect**, rather than trying to guarantee a clean plate.
