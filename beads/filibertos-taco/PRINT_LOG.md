# Filiberto's Taco — Print Log

Append-only, newest at the top. Every physical print of this charm gets one entry: what was printed, what failed, what changed for next time.

---

## v1 — 2026-05-08 — not yet printed

First export. Build completed cleanly:

- 0 non-manifold edges on Bottom and Top.
- 3 pegs validated with center + 8-perimeter raycast (recipe gotcha #21) — all in solid silhouette, ≥1.5 mm NFC clearance.
- String hole tube entirely inside Top half via `HOLE_Z_OFFSET=1.25` (recipe gotcha #23) — bridged twice by slicer, no inner-face notch.
- All 3 decorations cropped to silhouette via INTERSECT with extruded Top duplicate.
- `nfc-printability-check` PASS on cantilever ratios + bed contact + peg edges.
- `nfc-make-3mf` produced `print/filibertos-taco.3mf` from concatenated `Decoration.stl`.

Caught one issue during export iteration: `bead-stl-export` default applied a 180° X-flip to Bottom, but my centered-mesh pipeline produces Bottom already in print orientation. Recipe gotcha #16 — overridden via `bpy.context.scene["nfc_export_flip_override"]` set inside `build_filibertos_taco.py`.

**Open questions for first print:**
- Slicer filament assignments: Bottom in brown PETG? Top in yellow + 3 decoration filaments? Need to set up in slicer before slicing.
- Does the 0.4 mm raised relief read clearly at 25 mm scale, or does it look stamped?
- First-layer adhesion on the Top half — 246 mm² bed contact, plenty of margin.

**Pre-print checklist:**
- Open `print/filibertos-taco.3mf` in Elegoo Slicer.
- Assign 3 filaments to the Decoration components (yellow shell, green lettuce, red outline).
- Layer height 0.16 mm, 100% infill (parts are tiny), no supports.
