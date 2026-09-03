# Print Guide — Multi-color NFC Bead on Centauri Carbon 2

End-to-end workflow for printing a multi-color NFC bead (default sizing: 20 mm kandi-bracelet) on a Centauri Carbon 2 with Elegoo Slicer. Default colors are red body + black decoration; override per charm in the build script.

The Centauri Carbon 2 is **multi-filament** — auto-feeds between filaments mid-print. **Do NOT use M600 / manual filament-swap workflows on this hardware.** The slicer assigns filaments per part and the printer handles every transition automatically.

## The fast path — slicer-ready 3MF

The recommended workflow generates a single `.3mf` file with everything pre-arranged. **One drag into Elegoo Slicer and you can press slice.**

```sh
# 1. (in Blender) export STLs from the live scene
exec(open(r"<repo>/.claude/skills/bead-stl-export/export.py").read())

# 2. (host shell) verify alignment + manifold
uv run nfc-verify-stls

# 3. (host shell) build the slicer-ready 3MF
uv run nfc-build-3mf
```

That writes `tmp/latest/bead_multicolor.3mf` with:

- **`Bottom`** as one object on the plate, assigned to **Filament 2** (red body)
- **`Top` + `Decoration`** as a single multi-part object on the plate; **`Top`** on Filament 2 (red), **`Decoration`** on Filament 1 (black). Already merged — no manual "Combine into one object" step needed.
- **`brim_type=auto_brim`, `brim_width=5`, `raft_layers=0`** patched into the project settings.
  **This guide used to say `no_brim`, and that was wrong** — a 3MF that reached the plate
  without a brim smeared its first layer, and the 3MF that printed cleanly carried
  `auto_brim` at 5 mm. A missing printer profile is the usual way the brim goes absent
  (see recipe gotcha #33). Keep the brim; it is the adhesion fix, not clutter.
- **Centauri Carbon 2 printer profile** preserved from the reference 3MF in `tmp/latest/slicer_template/` — process preset, machine config, filament slots all match what's on your slicer.

Drag `tmp/latest/bead_multicolor.3mf` into Elegoo Slicer, verify the layer preview shows red body + black spiral at the right Z, and press slice.


## Printing autonomously over the MCP (no GUI)

The whole path is scriptable — this box has a **headless slicer** at
`D:	ools\elegooslicer\elegoo-slicer.exe` (note the hyphen; searching for
`ElegooSlicer.exe` finds nothing and two sessions wrongly concluded there was no
slicer here). It is a GUI-subsystem binary that prints nothing to the console,
so judge it by the artifact it writes, not by its output:

```sh
# 3MF -> gcode; emits plate_1.gcode into the output dir
/d/tools/elegooslicer/elegoo-slicer.exe --slice 0     --outputdir "D:\path	o\out" "D:\path	o\project.3mf"

# the MCP server runs in a container and cannot see host paths -
# stage the file into it first, then upload by its CONTAINER path
docker cp "D:\path	o\out\plate_1.gcode" centauri-mcp:/tmp/job.gcode
```

Then `upload_file(local_path="/tmp/job.gcode")` and `start_print(...)`.

### Pre-flight — do not skip these, each one has burned a real print

1. **`filament_detected` must read 1 while the printer is IDLE.** A dry extruder
   runs the whole job and still reports `task_status: 1`. This is recipe gotcha
   #41 and it has produced two phantom prints. Note it reads 0 *legitimately*
   during preheat, mesh, wipe and load — gate on the idle value.
2. **Check the gcode draws from the slot you think it does.**
   `grep -a "^; filament used \[g\]"` shows usage per slot *in position order*,
   and `grep -a "M6211 A1 L[0-9]* T[0-9]*"` shows which tool it loads.
   **Black is the FIRST slot (`T0`); red is the SECOND (`T1`).** Every job drawn
   from `T0` has succeeded here; `T1` has failed to auto-load twice.
3. **Confirm the uploaded file is really gcode.** `list_files` shows a real job
   with populated `layer` / `print_time` / `color_map`. A `.3mf` uploads happily
   and sits inert at `layer: 0` — see gotcha #35.
4. **`Ack: 0` from `start_print` is not proof.** Confirm `state: 2` with a
   non-empty `TaskId`.

### Judging the result

`task_status: 1` only means the gcode ran to the end. **The chamber camera
cannot see the plate centre** — it looks across the front lip, so a snapshot
reads empty both before and after a good print. A human has to look. Ask them
about the **purge line** specifically: no purge line means filament never
reached the nozzle; a purge line with no part means adhesion.

Watch the flag *during* the run too, not just at the start — poll rather than
sleeping until the end, because a warm bed collapses the ~12 minute preamble to
about 3 and it is easy to sleep straight past the window where aborting would
still have saved the filament.

## Reference 3MF template (one-time setup)

`nfc-build-3mf` reads printer/process settings from `tmp/latest/slicer_template/`. To populate that:

1. In Elegoo Slicer, set up a project the way you want it for these beads (Centauri Carbon 2, PLA filament slots in the right positions, layer height 0.12 mm, 100% infill, no supports).
2. **Save Project As** → `tmp/latest/template.3mf`.
3. Extract it: `cd tmp/latest && unzip template.3mf -d slicer_template/` (the bash way) or right-click in Explorer → 7-zip → extract to `r1_extracted\`.
4. From now on, every `nfc-build-3mf` run produces a 3MF that opens with that same printer/process profile.

You only do this once (or whenever you change printer/filament setup).

## The slow path — manual import (when you don't have a 3MF template)

If you don't have a reference 3MF set up yet, drop the three STLs in directly:

1. Drag `tmp/latest/Bottom.stl`, `Top.stl`, `Decoration.stl` onto the build plate.
2. Select `Top` and `Decoration` in the object list (Ctrl-click) → right-click → **Combine into one object** (or "Merge as parts").
3. Click each part and assign filaments:
   - `Bottom` → Filament 2 (red)
   - `Top` part → Filament 2 (red)
   - `Decoration` part → Filament 1 (black)
4. **Process** panel:
   - Layer height: **0.12 mm** (decoration is 0.5 mm tall = ~4 layers)
   - Infill: **100%**
   - Supports: **off**
   - Wipe / prime tower: **on** (default size is fine)
   - Brim: **off** (no brim — the parts have plenty of bed adhesion at this footprint)
5. Slice and verify the layer preview at Z ≈ 2.5 mm shows the spiral splitting from red to black.

## Print

Send the gcode to the printer. Total print time at 0.12 mm / 100% infill / 20 mm bead: **~20–30 minutes per half** including the wipe tower. The Centauri Carbon 2 auto-feeds the right filament at every transition — zero operator intervention.

## After printing

1. Drop the **NTAG215 sticker** (10 mm dia) into the bottom half's NFC pocket recess. It sits flush.
2. Press the top half down onto the bottom — the 3 pegs friction-fit into the matching peg holes. No glue.
3. String through the 2 mm hole in the head of the bead.

If the press-fit feels loose, increase `PEG_CLEARANCE` in `beads/<charm>/build_<charm>.py` (currently 0.1 mm); rebuild + reprint. Too tight: decrease.

## Verifying before you print

`nfc-verify-stls` is the pre-print guard:

```sh
uv run nfc-verify-stls
```

It loads the 3 STLs in `tmp/latest/` via `trimesh` and checks:

| Check | What |
|---|---|
| `geometry` | vertex/face counts > 0 |
| `watertight` | manifold (every edge has exactly 2 face uses) |
| `bed-flat` | `Bottom` and `Top` start at z=0 |
| `diameter` | within ±1.5 mm of the expected 20 mm |
| `thickness` | bottom 4 mm ±0.5, top 2.5 mm ±0.3, decoration relief 0.5 mm ±0.2 |
| `decoration on top` | gap top_max → deco_min in [-0.02, +0.10] mm |
| `decoration X/Y aligned` | top center and decoration center within 1 mm X / 2 mm Y |

Exits non-zero on any failure → safe to wire into a pre-print git hook.

## File reference

| Path | What |
|---|---|
| `tmp/latest/bead_multicolor.3mf` | **The one to drag into Elegoo Slicer** |
| `tmp/latest/Bottom.stl` `Top.stl` `Decoration.stl` | Individual STLs (manual flow) |
| `tmp/latest/manifest.txt` | Audit trail of the latest export |
| `tools/build_3mf.py` | The 3MF builder (`nfc-build-3mf`) |
| `tools/verify_stls.py` | The verifier (`nfc-verify-stls`) |
| `.claude/skills/bead-stl-export/export.py` | The Blender-side STL exporter |
| `prompts/nfc-bead/prompt.md` | Technical bead recipe (canonical) |
