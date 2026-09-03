# glow-set — print log

Newest entry first. Same convention as `beads/redaphid-portrait/PRINT_LOG.md`:
each entry records the geometry, whether it printed, and the one lesson worth
propagating to the recipe.

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
