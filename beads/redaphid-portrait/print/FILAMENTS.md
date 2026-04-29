# redaphid-portrait — filament + slicer config

The per-charm print recipe. Lives next to the STLs / 3MFs so anyone re-slicing this bead has the color map and the must-flip slicer settings in one place. Generic printer config (multi-color workflow, layer height defaults, etc.) lives in `../../../print/PRINT_GUIDE.md`.

## Filament slot → color → part

The four filament slots configured for this charm in Elegoo Slicer (Centauri Carbon 2, all PLA @ 210 °C):

| Slot | Hex      | Color | Used for                          |
|------|----------|-------|-----------------------------------|
| 1    | `#000000` | Black | **Hair** (object default; Hair has no per-part extruder override → inherits slot 1) |
| 2    | `#FF0000` | Red   | _unused on this charm_ — kept loaded for cross-charm consistency |
| 3    | `#FFFFFF` | White | **Decoration** (eyes)             |
| 4    | `#0000FF` | Blue  | **Top body** (the face)            |

Bottom half is single-color — no slot assignments needed; print whichever color you want for the back/snap face. Most sensible default: blue (slot 4) so it matches the visible edge of the face when the halves are pressed together.

The assignments are baked into the model parts in `top.3mf`'s `Metadata/model_settings.config` as `<metadata key="extruder" value="N"/>` overrides per part. If `top.3mf` is regenerated from STLs via `nfc-make-3mf`, these assignments are LOST and have to be reapplied (Elegoo Slicer → right-click each part → "Edit Process Settings → Filament").

## Slicer settings — verified state

These are the keys that actually control where swap purge goes, with the values from the user's saved Elegoo Slicer project (Multimaterial tab). Ship with these values:

| Setting               | Value | Notes |
|-----------------------|-------|-------|
| `enable_prime_tower`  | **1** (on) | 35 mm wide tower with 3 mm brim, parked at (165, 228.5). |
| `flush_into_infill`   | **0** (off) | Flush is *not* painted into the bead body. Earlier diagnosis claimed this was the cause of print failures — it was wrong. |
| `flush_into_objects`  | **0** (off) | |
| `flush_into_support`  | **1** (on)  | This charm has no supports → no-op, harmless. |
| `purge_in_prime_tower`| **0**       | Likely a deprecated key in this slicer version; the actual purge routing is the `flush_into_*` set above, all of which correctly send purge to the prime tower. Don't change it; it isn't the problem. |
| Z-hop on travel       | **≥ 0.4 mm** (recommended) | Defense in depth so a peeled corner can't be caught by a travel move. Verify in Quality → Travel. |
| Filament 4 (blue) initial temp | optional **+5 °C** | Worth trying if peeling persists; first deposit after a swap is on a cooled substrate from a nozzle that dipped during cut/load/purge. |

## Flush volumes (mm³ purged on color swap)

Inherited from Elegoo defaults; documented here for reference, not to be edited unless a print still fails after the above settings are correct.

```
                 to: Black  Red   White  Blue
swap from Black:     —     515   667    414
swap from Red:       197   —     693    344
swap from White:     187   369   —      379
swap from Blue:      187   500   768    —
```

The black→blue (414 mm³) and white→blue (379 mm³) swaps are the two that matter for this charm's print order. Both are large; both go through the prime tower if the settings above are correct.

## Print order (one plate per half)

The build pipeline produces two separate 3MFs in this directory:

- **`top.3mf`** — Top body + Hair + Decoration as one merged object with parts. Print face-up; show face is on the top of the print (z = 2.30 mm body, hair at 2.30–2.70 mm, eyes at 2.31–2.81 mm).
- **`bottom.3mf`** — Bottom only. Print silhouette face down (Bottom is exported pre-flipped in print orientation; pegs point up on the print).

Each is sliced and printed independently. The two halves are press-fit assembled after both prints complete; no glue needed if the pegs grip.
