# glow-set — print log

Newest entry first. Same convention as `beads/redaphid-portrait/PRINT_LOG.md`:
each entry records the geometry, whether it printed, and the one lesson worth
propagating to the recipe.

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

**Still unproven: the snap fit.** This is the first part carrying `PEG_HEIGHT`
1.8 (engagement 0.50 -> 1.00 mm measured, clearance held at 0.050).

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
