# 0.6mm nozzle — derived constants and the PEG_CLEAR fit ladder

**Nothing in this document has been printed.** It is geometry prepared ahead of a
nozzle swap, verified only against the exported STLs. The one number that
actually matters — `PEG_CLEAR` — is deliberately left unresolved, because it
cannot be derived. The fit ladder below is how one print settles it.

---

## [!] THE ASSUMPTION EVERYTHING RESTS ON

> **0.6mm nozzle → 0.63mm line width, 0.30mm layer height.**

Every constant below is a *ratio* against those two numbers. **If the real
Elegoo profile differs, re-derive rather than copy.** The 0.4mm template that
ships in `tmp/latest/slicer_template/` states its own equivalents, and they are
the shape this assumption is modelled on:

    line_width              0.42        layer_height     0.2
    outer_wall_line_width   0.42        wall_loops       2
    initial_layer_line_width 0.5        max_layer_height 0.28
    printer_settings_id     Elegoo Centauri Carbon 2 0.4 nozzle

Two of those are load-bearing for the reasoning that follows:

- **`wall_loops = 2`.** Every "minimum wall" argument below is really "two
  perimeters, back to back" — `2 × 0.63 = 1.26mm` at a 0.6 nozzle.
- **`initial_layer_line_width` is *wider* than `line_width`** (0.5 vs 0.42).
  That extra first-layer squish is what deforms a socket bore, and it scales
  with the nozzle. It is the whole argument for `SOCKET_LEADIN`.

`max_layer_height 0.28` is a 0.4-nozzle printer limit; a 0.6 profile raises it
(typically ~0.45), so 0.30 layers sits comfortably inside it.

---

## How the two nozzles coexist

`beads/glow-set/nozzle.py` holds the nozzle-dependent constants as named
profiles. `shapes.py` and `build_talisman.py` read from it.

    BEAD_NOZZLE unset  ->  "0.4"   the shipped, hardware-proven set
    BEAD_NOZZLE=0.6    ->  the derived set in this document

Any single key can be overridden with `BEAD_<KEY>` for a single-variable
experiment — that is how the ladder is built without editing a profile:

    BEAD_NOZZLE=0.6 BEAD_PEG_CLEAR=0.10 blender -b --python build_talisman.py

### The 0.4 build is untouched — and here is the proof, plus a caveat

**`build_talisman.py` does not produce byte-identical STLs, and never did.**
Building the same bead three times from *identical* code gave three different
sha256 values. Blender's EXACT boolean solver does not emit triangles in a
stable order, so byte-identity is not a property this pipeline has and cannot be
used as a regression test.

What was verified instead is *geometric* identity, building the same bead from
the pre-change code and the post-change code:

| part | volume before | volume after | Δ | bounds Δ | unique verts | vertex sets equal |
|---|---|---|---|---|---|---|
| Bottom | 361.785473 | 361.785473 | 5.7e-14 | 0.0 | 1354 / 1354 | yes |
| Top | 758.829462 | 758.829462 | 0.0 | 0.0 | 962 / 962 | yes |

Same vertex set, same volume to 1e-14, same bounding box. The 0.4 path is
unchanged.

---

## A. The constant table

Ratios are against line width unless stated.

| constant | 0.4 | 0.6 | why |
|---|---|---|---|
| `LINE_W` | 0.42 | **0.63** | assumption |
| `LAYER` | 0.20 | **0.30** | assumption |
| `WALL` *(shapes.py)* | 0.6 | **1.2** | 0.6mm is **0.95 line widths — under a single perimeter** at 0.63. Two perimeters back to back need 1.26. 1.20 is 0.06 under that, which the slicer absorbs by thinning both; see the note below on why not 1.26. |
| `HOLE_R` *(shapes.py)* | 0.6 | **0.9** | must track `HOLE_D` |
| `HOLE_D` | 1.2 | **1.8** | 1.2mm is only 1.9 line widths at 0.63, and small bores print *undersized* because extrusion on a tight concave curve over-fills inward. 1.8 restores the exact ratio 1.2 had at 0.4 (2.86 line widths). It also spans 6 layers instead of 4, so the bore shape resolves. **Measured on the STL: 1.80 × 1.80, round.** |
| `HOLE_CROWN` | 2.5 | **2.5** | unchanged on purpose — a cord-strength rule (a bead snapped off a bracelet at 1.6mm), not a nozzle rule. Still met: 2.59–2.60mm on all four variants. |
| `NFC_DEPTH` | 0.8 | **0.9** | 3 × 0.30. 0.8 is 2.67 layers, so the slicer picks the rounding for you and you get 0.6 or 0.9 anyway — better to choose. The NTAG215 is ~0.2mm, so 0.9 is ample. **Cost: pocket floor 0.7 → 0.6mm.** |
| `SOCKET_LEADIN` | 0.4 | **0.6** | 2 × 0.30. At 0.30 layers, 0.4 is 1.33 layers and relieves only the *first* of the two squished layers gotcha #42 names; 0.6 relieves both. **Cost: 0.10mm of engagement — see the risk section.** |
| `PEG_DIAMETER` | 2.6 | **2.6** | verified sane, not merely carried over: 2.6mm is 4.1 line widths, so it takes two perimeters (2.52mm) plus a narrow gap-fill core. It prints solid. It is also a *grip* dimension — what actually moves at a wider line width is the bore around it, which is what `PEG_CLEAR` absorbs. |
| `PEG_CLEAR` | 0.01 | **LADDER** | cannot be derived; see section B |
| `BOTTOM_THICK` | 1.5 | 1.5 | 5 × 0.30 and 7.5 × 0.20 — clean at both, left alone |
| `TOP_THICK` | 3.0 | 3.0 | 10 × 0.30 — left alone, **but see the risk section** |
| `PEG_HEIGHT` | 1.8 | 1.8 | 6 × 0.30 — left alone |
| `PEG_CHAMFER` | 0.35 | 0.35 | tip taper, not a wall or a bore; unchanged |

### Why `WALL` is 1.2 and not 1.26

1.26 is the honest two-perimeter figure and it is *nearly* affordable. It is not
used because it costs a silhouette for no real gain: `kikyo` clears the pocket by
6.55mm, and `POCKET_R + 1.26 = 6.51` leaves **0.04mm** of margin — inside the
solver's own grid noise. 1.2 leaves 0.10mm. The 0.06mm shortfall against a true
two-perimeter wall is well inside slicer flow compensation.

---

## B. The PEG_CLEAR fit ladder — the main deliverable

### Direction: UP from the 0.4 value, and why

A wider extrusion pushes more material into a bore, so the printed socket comes
out **tighter** than nominal, and more so than at 0.4. `PEG_CLEAR` should
therefore go **up**. The ladder spans 0.02 → 0.15.

The bottom rung is **0.02**, not the currently-shipped 0.01, because 0.02 is the
value recipe gotcha #40 records as *"perfect"* on hardware; 0.01 was a later
tightening. Anchoring the ladder to the best-attested 0.4 value makes the result
readable as a *shift* from a known point. If 0.02 already prints loose at 0.6,
that is still a clean answer — it says the direction assumption was wrong and
the next ladder goes down.

### The mapping — count the sides

**Each rung is a different silhouette.** No embossed text: at 0.63mm line width
a legible digit would need ~3mm of glyph and would not survive the show face.

| rung | shape | what it looks like | `PEG_CLEAR` | directory |
|---|---|---|---|---|
| 1 | `chinese_changming` | **gourd** — all curves, no straight edge | **0.02** | `print/n06-c002-changming/` |
| 2 | `japanese_kikyo` | **flower** — 5 round petals, sharp notches | **0.06** | `print/n06-c006-kikyo/` |
| 3 | `chinese_yaxing` | **stepped cross** — all right angles | **0.10** | `print/n06-c010-yaxing/` |
| 4 | `japanese_kikko` | **hexagon** — 6 flat sides | **0.15** | `print/n06-c015-kikko/` |

**Mnemonic: the rounder it is, the tighter it is.** The progression runs
all-curves → curves-with-notches → right-angles → straight-sided polygon, so the
ordering is recoverable by eye without the table.

> **Do not add `chinese_plum` or `japanese_ume` to this set.** Both are 5-petal
> flowers essentially indistinguishable from `kikyo` in the hand. They were
> rejected for exactly that reason. If a rung ever needs replacing, the next
> visually-distinct survivor is `adinkra_bese_saka` (a lobed sack with four
> interior voids), which also needs a 20mm outline generated first.

### The plate

    python tools/make_plate.py --pitch 30 --cols 2 \
        --out beads/glow-set/print/n06-plate4 \
        beads/glow-set/print/n06-c002-changming \
        beads/glow-set/print/n06-c006-kikyo \
        beads/glow-set/print/n06-c010-yaxing \
        beads/glow-set/print/n06-c015-kikko

Two 50 × 50mm blocks (four Bottoms, four Tops), each part sitting at z=0, laid
out the standard way — `row_gap 0`, so the blocks are separated by
`build_3mf.py --bottom-xy / --top-xy` exactly as `tray3` and `tray6` were. It
drops into the existing flow unchanged once a 0.6 template exists.

---

## C. Verification

All numbers measured off the exported STLs.

### Manifoldness — all four clean, none excluded

| variant | Blender non-manifold edges (Bottom / Top) | trimesh watertight | Euler (Bottom / Top) |
|---|---|---|---|
| `n06-c002-changming` | 0 / 0 | yes | 2 / 0 |
| `n06-c006-kikyo` | 0 / 0 | yes | 2 / 0 |
| `n06-c010-yaxing` | 0 / 0 | yes | 2 / 0 |
| `n06-c015-kikko` | 0 / 0 | yes | 2 / 0 |

Euler **2** on every Bottom (a plain solid) and **0** on every Top is an
independent confirmation of the internal features: genus 1 means the cord bore is
a real through-hole, and the three peg sockets correctly are *not* — they are
blind, or the Top would be genus 4. All 8 bodies on the ganged plate are
individually watertight.

### Engagement and gap — `measure_fit.py`

The 0.4 geometry is included as the control.

| variant | design `PEG_CLEAR` | engagement (3 pegs) | **measured gap** |
|---|---|---|---|
| `sm-japanese_kikko` *(0.4 control)* | 0.01 | **1.00** / 1.00 / 1.00 | 0.020 |
| `sm-chinese_yaxing` *(0.4 control)* | 0.01 | **1.00** / 1.10 / 1.00 | 0.020 |
| `n06-c002-changming` | 0.02 | **0.90** / 0.90 / 0.90 | **0.020** |
| `n06-c006-kikyo` | 0.06 | **0.90** / 0.90 / 0.90 | **0.060** |
| `n06-c010-yaxing` | 0.10 | **0.90** / 0.90 / 0.90 | **0.100** |
| `n06-c015-kikko` | 0.15 | **0.90** / 0.90 / 0.90 | **0.150** |

Engagement is flat at 0.90mm across the ladder — expected, since the ladder
varies the gap, not the depth — and **the measured gap reproduces the design
clearance exactly on every rung**. That is the ladder working: one variable
moves, and it is the intended one.

Engagement is **0.90mm, down from 1.00mm** on the 0.4 geometry. That is the
`SOCKET_LEADIN 0.4 → 0.6` cost, and it is the risk called out below.

### `measure_fit.py` needed fixing first — two real bugs

Run unmodified, the tool reported **engagement 0.00mm on the 0.10 and 0.15
rungs** and failed the whole ladder.

1. **The engagement threshold was the hardcoded literal `0.08`.** Its own
   docstring defines engagement as the length over which the gap is "at or below
   the design clearance", but 0.08 is only that while the design clearance is a
   0.4-nozzle value. A rung built at `PEG_CLEAR = 0.10` has a uniform 0.100mm gap
   down its whole engaged length, every sample lands above 0.08, and the tool
   reports "never gripped" for geometry as engaged as the tight rungs. Now
   `--gap-max`, **defaulting to 0.08 so every existing invocation is unchanged.**
2. **The pass gate compared a float-accumulated sum against `0.9`.** Engagement
   is a sum of 0.1 steps, so an exact 0.90 arrives as 0.8999999999999999 and
   failed. Now compared with a 1e-6 slack.

Both are pre-existing and would have mis-reported any future ladder.

> **This corrects the brief**, which said engagement "will read the same across
> the ladder — that is expected". True of the geometry, but *not* of the tool as
> it stood: the threshold was absolute, so the loose rungs read 0.00 and exited
> non-zero.

### Cord wall — `check_cord_wall.py --dia 1.8`

| variant | bore | crown (min 2.50) |
|---|---|---|
| `n06-c002-changming` | 1.80 × 1.80 | 2.60 |
| `n06-c006-kikyo` | 1.80 × 1.80 | 2.59 |
| `n06-c010-yaxing` | 1.80 × 1.80 | 2.60 |
| `n06-c015-kikko` | 1.80 × 1.80 | 2.60 |

PASS. The solver drops the hole ~0.3mm to keep the crown as the bore grows.

### `uv run nfc-verify-stls`

Per variant: **geometry, watertight and bed-flat OK on both parts.**

Four `expected-dim` checks fail on every variant — and **also on the shipped 0.4
bead that has physically printed**, which is the control that settles it:

    sm-japanese_kikko (0.4, printed)   FAIL diameter 20.00 (expected 17 +- 1.5)
                                       FAIL thickness 3.30 (expected 4.0 +- 0.5)

`EXPECTED_DIA_MM = 17.0` and the thickness tolerances are tuned for a different
charm. Pre-existing, identical at both nozzles, **not** caused by the 0.6
constants. Left alone rather than retuned, because those constants are a shared
default that other charms verify against.

One genuine fix was needed: `verify_stls.py` hard-required a `Decoration.stl` and
refused to check a two-part bead at all. Single-filament Bottom + Top is
`build_talisman.py`'s documented default and how the whole glow set prints, so
Decoration is now optional; Bottom and Top are still required. **Backport
candidate for `main`.**

---

## D. Solver pass count — 8 → 6 of 30, above the floor

All 30 motifs (11 japanese + 10 chinese + 9 adinkra) at **20mm**, unchanged:

| | pass | shapes |
|---|---|---|
| **0.4** (`WALL 0.6`, `HOLE_R 0.6`) | **8 / 30** | kikko, kikyo, ume, changming, plum, yaxing, akoma, bese_saka |
| **0.6** (`WALL 1.2`, `HOLE_R 0.9`) | **6 / 30** | kikko, kikyo, ume, changming, yaxing, bese_saka |

**Lost:** `chinese_plum` (pocket 6.17 < 6.45) and `adinkra_akoma` (6.24 < 6.45).
Both are pocket-clearance failures — the 10.5mm NTAG215 pocket plus a 1.2mm wall
needs 6.45mm of interior room, and those two silhouettes have 6.2.

**6 is above the floor of 4, so this proceeds. The bead size was NOT increased.**
All four ladder variants measure 20.0mm or under on their long axis
(19.8 × 20.0, 20.0 × 19.5, 20.0 × 20.0, 17.7 × 20.0). Growing the bead is the
obvious way to make more shapes fit and it is the wrong one; it has been asked
about and refused before.

If more motifs are wanted at 0.6 and 20mm, the honest levers are, in order:

1. **Drop `WALL` to 1.0** (~1.6 perimeters — one full perimeter plus a real
   gap-fill, not a void). Recovers `plum` and `akoma`. This is a genuine
   trade, not a free win.
2. **Redraw the failing silhouettes fatter** — they fail by 0.2–0.3mm.
3. **A smaller tag.** `POCKET_R` is the dominant term in every failure; the
   NTAG215 is what crowds a 20mm bead, not the wall.

---

## E. [!] RISKS — read before printing

### 1. The cord tube's Z walls drop from 0.90mm to 0.60mm

This is the one place the brief's "leave `TOP_THICK`" instruction has a
consequence it did not account for. Measured on `Top.stl`:

| | bore | Top | wall above bore | wall below bore |
|---|---|---|---|---|
| 0.4, `HOLE_D 1.2` | 0.90 → 2.10 | 0 → 3.00 | **0.90mm** (4.5 layers) | **0.90mm** |
| 0.6, `HOLE_D 1.8` | 0.60 → 2.40 | 0 → 3.00 | **0.60mm** (2 layers) | **0.60mm** |

A bigger bore inside an unchanged 3.0mm half has to come out of the walls.
0.60mm is two layers at 0.30, and the wall above the bore prints as a *bridge*
over it.

**Mitigating it:** the cord pulls in +Y, against the **crown** (2.60mm,
unchanged), not against these Z walls. So this is a secondary load path.

**The one-line fix if it proves weak:** `TOP_THICK 3.0 → 3.3` (11 × 0.30)
restores 0.75mm walls, at the cost of a 4.8mm bead instead of 4.5mm. Not applied,
because it was explicitly out of scope and the crown still governs.

### 2. Engagement is 0.90mm, at the gate — and `PEG_HEIGHT` is the next knob, not `PEG_CLEAR`

`SOCKET_LEADIN 0.4 → 0.6` spends 0.10mm of engagement, taking it from the
proven 1.00mm to 0.90mm. Recipe gotcha #40 targets ~1.0mm and is explicit that
**`PEG_HEIGHT` is the first knob and `PEG_CLEAR` the second** — at 0.50mm
engagement no clearance value rescued the fit, because there was scarcely any
length over which clearance applied.

0.90mm is close to the proven 1.00, so the ladder should still be informative.
But:

> **If every rung on the ladder reads loose, do not run a looser ladder.** The
> next single-variable move is **`PEG_HEIGHT` 1.8 → 2.1** (7 × 0.30), which
> restores ~1.20mm of engagement. Only after that does more clearance mean
> anything.

`PEG_HEIGHT 2.1` is not free either: it deepens the socket to 2.4mm in a 3.0mm
Top, cutting the socket floor from 0.90mm to 0.60mm. It stays clear of the cord
bore — the solver keeps pegs ≥ 2.8mm in Y from the hole axis and only 2.21mm is
needed.

### 3. `build_3mf.py` hardcodes `"nozzle_diameter": 0.4`

Independently of the template. Even given a correct 0.6 template, the generated
`slice_info.config` would still claim 0.4. That line needs to become a parameter
before a 0.6 3MF is built. **No 3MF was built and nothing was sliced**, per
scope.

---

## F. What you have to do in Elegoo Slicer

`tools/build_3mf.py` inherits its printer and process preset from a reference
3MF the user saved out of the slicer — `tmp/latest/slicer_template/`. The one
there now is a **0.4 nozzle** template
(`printer_settings_id: Elegoo Centauri Carbon 2 0.4 nozzle`). A 0.6 template can
only be produced in the GUI. Steps:

1. Install the 0.6mm nozzle and run the printer's **nozzle-change / calibration**
   flow so the firmware knows. Re-level the bed — and given the PRINT_LOG
   history, do a **cold pull** first so the melt zone is clean going in.
2. In Elegoo Slicer, select the printer preset for the **Centauri Carbon 2, 0.6
   nozzle**. If it is not offered, add the nozzle in printer settings; do not
   hand-edit a 0.4 preset's `nozzle_diameter`.
3. Pick a **0.30mm layer-height process preset** for that nozzle
   (e.g. "0.30mm Standard @Elegoo CC2 0.6 nozzle").
4. **Read back the numbers this document assumed** and write down anything that
   differs — `line_width`, `outer_wall_line_width`, `initial_layer_line_width`,
   `layer_height`, `wall_loops`. If `line_width` is not ~0.63 or `layer_height`
   not 0.30, **re-derive the table in section A before printing.**
5. Import any part, then **File → Save Project As** a `.3mf`.
6. Extract that `.3mf` over `tmp/latest/slicer_template/` so
   `Metadata/project_settings.config` is the 0.6 one.
7. Fix `build_3mf.py`'s hardcoded `"nozzle_diameter": 0.4` (risk 3).
8. Then, and only then, plate and slice. Per PRINT_LOG: verify the slot with
   `get_canvas_status` and prefer **black on `T0`** — red on `T1` is 1/4.

---

## Reproducing everything here

    # a ladder rung
    BEAD_NOZZLE=0.6 BEAD_PEG_CLEAR=0.10 BEAD_NAME=n06-c010-yaxing \
    BEAD_SHAPE="json:<repo>/tmp/outlines/sm_chinese_yaxing.json" \
    "D:\tools\blender\blender.exe" -b --gpu-backend opengl \
        --python beads/glow-set/build_talisman.py

    # measure a rung against its OWN design clearance (+~0.03)
    .venv/Scripts/python.exe beads/glow-set/measure_fit.py \
        n06-c010-yaxing --gap-max 0.13

    .venv/Scripts/python.exe beads/glow-set/check_cord_wall.py \
        beads/glow-set/print/n06-*/Top.stl --dia 1.8
    uv run nfc-verify-stls --dir beads/glow-set/print/n06-c010-yaxing

The `sm_*.json` 20mm outlines live in `tmp/` (gitignored) and are regenerated
with `motif_outline.py --r 10.0`.
