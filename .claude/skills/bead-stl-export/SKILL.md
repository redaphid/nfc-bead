---
name: bead-stl-export
description: Export the printable bead halves to STL files in a known-good state — strips any architect aesthetic, debug overlays, or visualization-only objects first so the export contains ONLY the geometry the slicer should see. Use when the user wants to "export the STL", "send it to the slicer", "make it printable", "check it's printable", or similar. Verifies dimensions and basic mesh sanity. Requires the Blender MCP to be connected.
---

# Bead STL Export

## Project-wide naming convention

Canonical Blender object names: `Bottom`, `Top`, `Decoration`. The scene must contain meshes with exactly these names — no fallback. STL filenames mirror the live object name, so the export produces `Bottom.stl`, `Top.stl`, `Decoration.stl`. Rename in-scene first if you want the on-disk filenames to be different (e.g. bead-prefixed for organizing across charms).

A defensive STL export skill that guarantees the exported geometry is the **pure printable form**, not the cinematic / debug-decorated version of the scene.

## What it does

Single script: `export.py`. When invoked it:

1. **Strips the architect aesthetic** — runs the equivalent of `bead-architect-mode/architect_off.py` to remove `MA_*` objects (line-art GP, lights, optional plate) and `MA_*` materials.
2. **Strips debug overlays** — removes any `DBG_*` overlay objects (peg cylinders, peg-hole wireframes, NFC pocket viz, string hole viz) so they can never sneak into an export.
3. **Validates the printable cohort** — confirms `Bottom`, `Top`, and the active decoration object exist as MESH objects with non-degenerate geometry.
4. **Applies a deterministic per-part print-orientation flip** — see "Print-orientation flip" below. The flip is a temporary rotation around each part's bbox center; the live scene is restored after the export.
5. **Exports each as its own STL** — uses `bpy.ops.wm.stl_export` with `export_selected_objects=True` so each STL contains ONLY that one object, in print orientation.
6. **Verifies dimensions** — checks each STL's bounding box against the expected ranges (per `prompts/nfc-bead/prompt.md`: ~25mm diameter, ~5–6mm thick total, etc.) and reports any deviation.
7. **Reports** — prints a manifest listing each output STL, its byte size, and whether it was print-flipped.

## Print-orientation flip (the contract)

`prompts/nfc-bead/prompt.md` specifies the print-orientation contract:

- **`Bottom`** — silhouette face on the build plate, **pegs point up**. Prints flat, no supports. (Achieved by rotating 180° around X relative to build orientation.)
- **`Top`** — peg-hole face on the build plate, outer face (with the decoration) pointing up.
- **`Decoration`** — flat side on the build plate (it's a thin ribbon, ~0.5 mm tall).

Build pipelines (`build_<charm>.py`) typically produce the geometry in *build orientation* — convenient for boolean ops, not necessarily ready for the slicer. `export.py` enforces print orientation deterministically via the `EXPORT_FLIP_X_DEG` config dict at the top of the script:

```python
EXPORT_FLIP_X_DEG = {
    "Bottom":     180.0,   # silhouette down → pegs up
    "Top":          0.0,
    "Decoration":   0.0,
}
```

The flip is applied as a temporary 180° rotation **around the part's bbox center** (not its origin — origin may not be the geometric center) just before `bpy.ops.wm.stl_export`. The original transform is restored after the write, so re-running the live scene's animations / camera shots is unaffected.

**Why this matters:** the slicer should see a print-ready STL. Without this flip, the user has to manually re-orient the bottom in Elegoo Slicer every time, and an "auto-orient" feature can flip it the wrong way. With this flip baked into the export, dropping any of these STLs into the slicer Just Works.

To override per bead — for instance if you build the bottom already-flipped — change the dict value to `0.0` for that part and re-export.

## Output location

Default: `<repo>/tmp/stl_export_<timestamp>/` for the timestamped archive of the run. Override via the `OUT_DIR` tunable at the top of `export.py`.

**Always-current copy at `<repo>/tmp/latest/`**: every run also wipes and re-writes the same files into `tmp/latest/` so there's a known-path location for "the latest STLs" — no need to find the most-recent timestamped folder. A `manifest.txt` in that dir records what was exported and from where. `tmp/` is gitignored so these files stay local; they're derived artifacts that any export run will recreate.

## How to invoke

```python
exec(open(r"<repo>/.claude/skills/bead-stl-export/export.py").read())
```

## Why this exists

Without this defensive skill, a sloppy `bpy.ops.wm.stl_export(selected=True)` after running `recolor.py` or `architect_on.py` could include:

- The graph-paper plate (if one was added)
- The line-art Grease Pencil object (technically not exportable as STL but clutters selections)
- DBG_* overlay cylinders (yellow pegs widget, red peg-hole wireframes — these are NOT print geometry)
- Materials that don't carry through to the slicer anyway

`build_<charm>.py` scripts already export by name, but interactive sessions where the user just hit "export selected" can absolutely ship a wrong STL. This skill removes that footgun.

## STL printability check

Beyond bounding-box validation, the script does a sanity pass for each exported mesh:

- **non-empty**: vertex count > 0, face count > 0
- **closed**: every edge has exactly 2 face connections (manifold)
- **dimensions**: bbox X×Y matches the bead's silhouette to ±0.5 mm; Z within the expected half-thickness

A failure raises a clear error rather than producing a silent broken STL.

For deeper verification (per `prompts/nfc-bead/prompt.md` gotcha #8 — "verify everything with raycasts"), the build pipeline's `build_<charm>.py` should be re-run; this skill is for the export step, not full geometric validation.

## When NOT to use

- Mid-build, before the bead geometry is finalized — exporting partial geometry produces non-printable STLs. Run `build_<charm>.py` to completion first.
- If you genuinely WANT to export a debug overlay (you usually don't) — use `bpy.ops.wm.stl_export` directly.
- If the build pipeline already produces print-oriented STLs (rare) and you don't want a double flip — set `EXPORT_FLIP_X_DEG["Bottom"] = 0.0` in the script's tunables block.

## Single-color vs multi-color top half

If `Top` and `Decoration` are still **separate objects** in the scene, `export.py` writes them to separate STLs — use both in the slicer for a multi-color print (red body + black decoration, or any pairing).

If they've been **boolean-UNIONed** (e.g. via the build pipeline's UNION step or by an earlier session), `Top` already contains the decoration as raised relief and `Decoration` may be missing or hidden — the export then produces a single unified `Top.stl` for single-color printing.

To go from unified back to multi-color, you have to rebuild from `build_<charm>.py` (the union is destructive). To go from multi-color to unified, re-run the boolean UNION on `Top` with `Decoration` as the operand.
