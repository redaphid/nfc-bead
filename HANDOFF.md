# HANDOFF — NFC bead print run

Branch `glow-set`. Written 2026-09-04/05 for a fresh session. Deadline is
**MOGEE FEST, 2026-09-06** — wear-and-trade beads, quantity over perfection.

---

## The one thing to read first

**A working system was broken by changing two variables at once.**

Last night this machine printed **17 good beads in a row** — PLA, 0.4mm nozzle,
a settled recipe, zero failures. Then two things changed together:

1. 0.4mm brass nozzle → **0.6mm hardened**
2. PLA → **Prusament PETG Ultraglow**

Since then **nothing has printed at all.** Material extrudes cleanly into the
air but will not stick to the plate; it balls onto the nozzle and the plate
stays bare.

**My honest recommendation, which I did not push hard enough at the time:
put the 0.4 nozzle and PLA back and print the batch.** There are 17 good beads
already and a recipe that produced them without intervention. PETG Ultraglow at
0.6 is a worthwhile project but it is a *new bring-up*, and bringing up a new
nozzle and a new abrasive material the day before a deadline is how you arrive
with nothing. Glow beads are better than black beads only if they exist.

If the user wants to push on with PETG anyway, everything below applies.

---

## What already exists (assets, not theory)

- **17 finished PLA beads**, all six motifs, most in duplicate.
- Six 20/22mm bead designs that are geometrically verified and print reliably.
- A fully headless pipeline: 3MF → gcode → printer, no GUI.

## The PLA recipe that produced 17/17

```
python tools/build_3mf.py -o <out>.3mf \
    --body-extruder 1 --force-brim --brim-width 8 \
    --bed-temp 65 --hole-compensation 0.05
```

Nozzle 210, bed 65, 0.4mm nozzle, 0.2mm layers, textured PEI. **This is known
good. If in doubt, go back to it.**

---

## The failure, in the order the evidence came in

Symptom: extrudate does not adhere to the plate on layer 1. It follows the
nozzle, balls up on the hotend, and the plate stays empty. Reported as "plastic
gunks up on the nozzle" — the same phrase used for a *different* failure earlier
in the night, which caused confusion. **They are not the same failure.**

### Ruled out, with how

| Hypothesis | How it was killed |
|---|---|
| Nozzle leaking at the threads | Air-extrude test: one clean strand from the tip, nothing at the threads or block (photo) |
| Clog / no flow | Same test — continuous, uniform, unbroken strand |
| PLA left in the melt zone | Strand is uniformly pale green, no dark streaks |
| Plate contamination | Washed with dish soap and water |
| Temperature too low | Bed confirmed 85 in telemetry; nozzle molten and flowing |
| Nozzle commanded to 90 °C | **I claimed this and was wrong.** 90 is the standby temperature while *paused*. Proven by identical head position and frozen tick count across two readings |
| Abrasive wear on a brass nozzle | Nozzle is hardened steel |

### Still open

**My current hypothesis is Z offset / first-layer height, and it may be wrong.**

The reasoning: everything else is eliminated, `z_offset` reads `0.00` over the
API, and a nozzle swap changes the tip's height. A nozzle too high lays round
strands that never bond and follow the tip — which matches the symptom exactly.

**What argues against it:** the user says they recalibrated. If auto-level on
this machine probes with the nozzle itself, nozzle length is already accounted
for and the offset should not need to move much.

**Unresolved detail:** the user said "it's 0.3 the last time" and it was not
established whether that meant layer height or Z offset. **If the Z offset is
`+0.3`, that alone explains everything** — a positive offset lifts the nozzle
away from the bed, and +0.3 with a 0.3mm first layer means the tip never touches
the plate. Worth confirming before anything else.

Also unconfirmed: the file that actually ran was named `..._0.2_6m49s.gcode`, so
the last real print used **0.2mm layers on a 0.6mm nozzle**. That is a very
unforgiving first layer for a wide nozzle. 0.3mm is standard.

### Things a fresh pair of eyes should question

- Is the extrusion *volume* right? The air-extrude strand looked thin for a 0.6
  nozzle. Under-extrusion was never measured — no flow calibration was done
  after the swap. **Nobody has checked that the slicer's 0.6 line widths match
  what the machine actually pushes.**
- The 0.6 slicer template is **derived, not vendor-supplied** — the 0.4 profile
  scaled by ratios. Line widths, flow, and pressure advance were never validated
  against real hardware.
- Was the printer's *own* firmware nozzle-diameter setting changed to 0.6? It
  was suggested but never confirmed. A firmware/gcode mismatch would mis-scale
  every extrusion.
- Prusa warn this filament wears **PTFE tubes and extruder gears**, not just
  nozzles. A slipping or worn extruder would under-extrude while still producing
  a clean-looking air strand.

---

## Blocker that is definitely still real

Every Canvas tray reports:

```
filament_type: "PLA"    max_nozzle_temp: 230
```

The PETG files ask for **260**. Until tray 0 is set to PETG on the machine, the
printer may clamp or refuse, and slicer filament auto-mapping fails with
"unmapped filament detected" because mapping matches by type. **This was flagged
repeatedly and never confirmed as done.**

---

## Pipeline mechanics (all verified, save yourself the rediscovery)

**Getting a file to the printer.** `centauri-mcp` declares **no volumes** — it
cannot see any host path. Every `upload_file` path fails until you put the file
*inside* the container:

```
wsl -d survivor -- docker cp /mnt/d/<path>.gcode centauri-mcp:/tmp/x.gcode
upload_file(local_path="/tmp/x.gcode")
```

Run `docker cp` from **PowerShell, not Git Bash** — MSYS rewrites `/tmp/...`
into a `C:\` path and docker then reads the source as a container reference.
Uploads are refused **mid-job** (HTTP 400 on chunk 0); stage between prints.

**Headless slicing works.**

```
elegoo-slicer.exe --slice 0 --outputdir <dir> <file.3mf>
```

It is a GUI-subsystem binary and prints **nothing** to a console — `--help`
looks like it hung. Run via `Start-Process` and judge by the output directory.

**Which 3MF settings survive the CLI cannot be assumed.** Brim, hole
compensation, bed temp, nozzle diameter and layer height all carry through.
**Acceleration does not** — the CLI uses its own stored presets, so CLI slices
run ~2× the GUI's estimate. Always read settings back out of the sliced gcode.

**Telemetry lies about outcomes.** Three separate runs reported `task_status: 1`
with full tick counts while the part was unusable or absent. There is a camera —
`get_snapshot` — and it is the only remote way to see truth. Use it.

---

## Files

```
beads/glow-set/print/GLOW/          everything for the current PETG attempt
    *_Bottom.stl                    print pegs-UP, never flip
    *_Top.stl                       original orientation, sockets DOWN
    *_Top_HOLESUP.stl               flipped, sockets UP (see below)
    g06-*-petg.3mf                  0.6 + PETG 260/85, brim 8
    Prusament_PETG_Ultraglow_CC2_06.json    Orca filament preset, importable

out/queue/*.gcode                   pre-sliced, ready to upload
beads/glow-set/PRINT_LOG.md         full history, newest first
prompts/nfc-bead/prompt.md          the recipe + 43 gotchas
```

Known-good PLA files from the successful run are the `sm-*` 3MFs in
`beads/glow-set/print/sm-*/`.

---

## Open design question, untested

**The Top may have been printing upside down all along** (gotcha #42). Holes-down
puts the mating face — the tolerance surface — against the plate, which:

1. makes the first layer a thin ring perforated by three 2.6mm socket mouths
2. squeezes material into those bores
3. **forces a bridged 2.6mm ceiling over every socket**, three per bead
4. puts elephant-foot spread on the face that must close flush

`*_Top_HOLESUP.stl` are the flipped meshes. **Never printed.** Predictions: round
bores without compensation, halves closing flush, possibly a fit that reads loose
for the first time. This is orthogonal to the PETG problem — don't test both at
once. (That mistake is the theme of this handoff.)

---

## What I would do next

1. **Confirm the Z offset value.** If it is `+0.3`, that is the answer.
2. **Confirm tray 0 says PETG**, not PLA.
3. If those are both fine: **revert to 0.4 + PLA, print the batch for Saturday**,
   and treat PETG/0.6 as a post-deadline project with a proper bring-up —
   flow calibration, a real vendor profile, one variable at a time.

The beads for the fest do not depend on solving this. That is the most useful
thing in this document.
