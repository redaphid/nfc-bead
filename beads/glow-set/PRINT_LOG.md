# glow-set — print log

Newest entry first. Same convention as `beads/redaphid-portrait/PRINT_LOG.md`:
each entry records the geometry, whether it printed, and the one lesson worth
propagating to the recipe.

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
