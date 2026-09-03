# glow-set — print log

Newest entry first. Same convention as `beads/redaphid-portrait/PRINT_LOG.md`:
each entry records the geometry, whether it printed, and the one lesson worth
propagating to the recipe.

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
