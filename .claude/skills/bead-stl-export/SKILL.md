---
name: bead-stl-export
description: Export the printable bead halves to STL files in a known-good state — strips any architect aesthetic, debug overlays, or visualization-only objects first so the export contains ONLY the geometry the slicer should see. Use when the user wants to "export the STL", "send it to the slicer", "make it printable", "check it's printable", or similar. Verifies dimensions and basic mesh sanity. Requires the Blender MCP to be connected.
---

# Bead STL Export

A defensive STL export skill that guarantees the exported geometry is the **pure printable form**, not the cinematic / debug-decorated version of the scene.

## What it does

Single script: `export.py`. When invoked it:

1. **Strips the architect aesthetic** — runs the equivalent of `bead-architect-mode/architect_off.py` to remove `MA_*` objects (line-art GP, lights, optional plate) and `MA_*` materials.
2. **Strips debug overlays** — removes any `DBG_*` overlay objects (peg cylinders, peg-hole wireframes, NFC pocket viz, string hole viz) so they can never sneak into an export.
3. **Validates the printable cohort** — confirms `Bottom`, `Top`, and the active decoration object exist as MESH objects with non-degenerate geometry.
4. **Exports each as its own STL** — uses `bpy.ops.wm.stl_export` with `selected_objects=True` so each STL contains ONLY that one object.
5. **Verifies dimensions** — checks each STL's bounding box against the expected ranges (per `prompts/nfc-bead/prompt.md`: ~25mm diameter, ~5–6mm thick total, etc.) and reports any deviation.
6. **Reports** — prints a manifest listing each output STL, its byte size, and its bounding box.

## Output location

Default: `<repo>/tmp/stl_export_<timestamp>/`. Override via the `OUT_DIR` tunable at the top of `export.py`.

## How to invoke

```python
exec(open(r"<repo>/.claude/skills/bead-stl-export/export.py").read())
```

For a different bead, edit `export.py`'s `EXPECTED_OBJECTS` list (defaults match the rezz bead: `rezz_bottom`, `rezz_top_body`, `rezz_top_spiral`).

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
