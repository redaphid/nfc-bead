"""Defensive STL export for an NFC bead.

Strips any architect aesthetic + debug overlays first, then exports
each printable object as its own STL with sanity checks.

Single source of truth for "send the bead to the slicer." Use this
instead of bare `bpy.ops.wm.stl_export(selection=True)` after a
debug-coloring or cinematic-mode session — those leave overlay
objects in the scene that absolutely should NOT ship to the printer.

Print-orientation: the Bottom half is flipped 180° around X on export
so the silhouette face touches the build plate and the pegs point up,
matching `prompts/nfc-bead/prompt.md`'s print-orientation contract.
The flip is applied via a temporary rotation that is restored after
the STL write — the live scene is unchanged.
"""
import bpy
import math
import os
import time
from mathutils import Matrix, Vector

# ─── Tunables ─────────────────────────────────────────────────────────
# Canonical bead-component names (project-wide convention).
# Build scripts MUST produce in-Blender objects with exactly these names.
# - Bottom / Top: structural halves
# - Hair:        large filament-color region covering most of the show face
# - Decoration:  small accent (eye dots, embossed mark, raised glyph)
# Charms that don't need a hair color region simply omit the `Hair` object;
# the export silently skips any name with no matching mesh.
EXPECTED_OBJECTS = [
    "Bottom",
    "Top",
    "Hair",
    "Decoration",
]

# Parts that should share another part's bed-flatten shift instead of computing
# their own bbox center. Preserves the assembly position when the user merges
# them in the slicer ("one object with parts" / "Combine"). Without this both
# Top.stl and Decoration.stl would import to the build plate with their own
# bbox centers at origin, and the merge would overlap the decoration inside
# the body instead of stacking it on the outer face.
EXPORT_SHARE_SHIFT_WITH = {
    "Hair":       "Top",
    "Decoration": "Top",
}

OUT_DIR = None     # default: tmp/stl_export_<timestamp>/ in repo root

# Per-part print-orientation transform applied at export-time only (the live
# scene's transforms are restored after the STL write). Values are degrees
# around the X axis; 180 flips the part upside-down, 0 leaves it.
#   Bottom: 180  → silhouette face on build plate, pegs point up
#   Top:    0    → peg-hole face naturally on build plate, outer face up
#   Decoration: 0
EXPORT_FLIP_X_DEG = {
    "Bottom":     180.0,
    "Top":          0.0,
    "Hair":         0.0,
    "Decoration":   0.0,
}

# Expected dimensions per prompts/nfc-bead/prompt.md.
# Overall bead is ~25mm diameter × ~5.5mm total thickness.
EXPECTED_DIA_MM    = 25.0
DIA_TOL_MM         = 1.5     # wide tolerance (different beads scale differently)
EXPECTED_THICK_MM  = 5.5
THICK_TOL_MM       = 3.0


# ─── Helpers ──────────────────────────────────────────────────────────
def _bbox_world(obj):
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def _mesh_sanity(obj):
    """Return list of issues. Empty list = ok."""
    issues = []
    me = obj.data
    if not me.vertices:
        issues.append("no vertices")
    if not me.polygons:
        issues.append("no faces")
    # Manifold: each edge should have exactly 2 face uses
    edge_uses = {}
    for poly in me.polygons:
        for i in range(len(poly.vertices)):
            v0 = poly.vertices[i]
            v1 = poly.vertices[(i + 1) % len(poly.vertices)]
            key = tuple(sorted((v0, v1)))
            edge_uses[key] = edge_uses.get(key, 0) + 1
    bad_edges = [k for k, c in edge_uses.items() if c != 2]
    if bad_edges:
        issues.append(f"{len(bad_edges)}/{len(edge_uses)} non-manifold edges")
    return issues


def _resolve_targets():
    """Pick up exact matches AND `Decoration<Suffix>` siblings.

    Multi-color charms (e.g. filibertos-taco) split the show-face decoration
    into several named meshes (DecorationFilling, DecorationShellOutline,
    …). Treat any mesh whose name starts with `Decoration` as a printable
    target so the slicer 3MF gets all filament regions.
    """
    targets = []
    seen = set()
    for name in EXPECTED_OBJECTS:
        o = bpy.data.objects.get(name)
        if o and o.type == 'MESH':
            targets.append(o); seen.add(o.name)
        # multi-decoration siblings
        if name == 'Decoration':
            for o in bpy.data.objects:
                if (o.type == 'MESH' and o.name.startswith('Decoration')
                        and o.name not in seen):
                    targets.append(o); seen.add(o.name)
    return targets


# ─── Step 1: drop out of edit mode ────────────────────────────────────
if bpy.context.mode != 'OBJECT':
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        if bpy.context.view_layer.objects.active:
            bpy.context.view_layer.objects.active = None

# ─── Step 2: strip architect (MA_*) and debug (DBG_*) overlay objects ──
removed = []
for obj in list(bpy.data.objects):
    if obj.name.startswith(("MA_", "DBG_")):
        removed.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)
print(f"[stl_export] stripped {len(removed)} overlay object(s)" + (f": {removed}" if removed else ""))

# Also drop unused MA_/DBG_ materials
removed_mats = []
for m in list(bpy.data.materials):
    if (m.name.startswith("MA_") or m.name.startswith("DBG_")) and m.users == 0:
        removed_mats.append(m.name)
        bpy.data.materials.remove(m)
if removed_mats:
    print(f"[stl_export] dropped {len(removed_mats)} unused overlay material(s)")

# ─── Step 3: locate printable targets ─────────────────────────────────
targets = _resolve_targets()
if not targets:
    raise RuntimeError(f"No printable objects found. Scene must contain meshes named {EXPECTED_OBJECTS}.")

print(f"[stl_export] export targets: {[o.name for o in targets]}")

# ─── Step 4: validate each before export ──────────────────────────────
overall_dim = [0.0, 0.0, 0.0]
report = []
for obj in targets:
    issues = _mesh_sanity(obj)
    bb = _bbox_world(obj)
    overall_dim[0] = max(overall_dim[0], bb[0])
    overall_dim[1] = max(overall_dim[1], bb[1])
    overall_dim[2] += bb[2]   # sum thickness across halves
    report.append({"name": obj.name, "bbox": bb, "issues": issues})
    if issues:
        print(f"[stl_export] WARNING {obj.name}: {issues}")

# Sanity check overall dimensions
diameter = max(overall_dim[0], overall_dim[1])
if abs(diameter - EXPECTED_DIA_MM) > DIA_TOL_MM:
    print(f"[stl_export] WARNING bead diameter {diameter:.1f}mm out of expected {EXPECTED_DIA_MM}±{DIA_TOL_MM}mm")
# Note: thickness check is a sum of stacked halves, may overshoot if halves overlap; soft check
if abs(overall_dim[2] - EXPECTED_THICK_MM) > THICK_TOL_MM:
    print(f"[stl_export] note bead total Z extent {overall_dim[2]:.1f}mm "
          f"(expected {EXPECTED_THICK_MM}±{THICK_TOL_MM}mm — soft check, halves may overlap in Z)")

# ─── Step 5: prepare output directory ─────────────────────────────────
if OUT_DIR is None:
    repo_root = bpy.path.abspath("//") or os.getcwd()
    # Walk up from the .blend dir to find a `tmp/` sibling
    for _ in range(4):
        candidate = os.path.join(repo_root, "tmp")
        if os.path.isdir(candidate):
            break
        repo_root = os.path.dirname(repo_root)
    else:
        candidate = os.path.join(os.getcwd(), "tmp")
    out_dir = os.path.join(candidate, f"stl_export_{time.strftime('%Y%m%d_%H%M%S')}")
else:
    out_dir = OUT_DIR
os.makedirs(out_dir, exist_ok=True)
print(f"[stl_export] writing to {out_dir}")

# ─── Step 6: export each target individually ──────────────────────────
# Per-part flip is applied as a temporary 180° X rotation around the part's
# bbox center, then restored. The STL is captured in print orientation,
# while the live scene is identical to its pre-export state.

def _resolve_flip(obj_name):
    """Flip-deg for a given object. The scene custom-property
    `nfc_export_flip_override` can override per-charm — useful when a
    build script's pipeline already produces a part in print orientation
    and the canonical 180° flip would un-orient it. Set as a JSON
    string of `{name: deg}` pairs on bpy.context.scene before running
    the export."""
    overrides = bpy.context.scene.get("nfc_export_flip_override")
    if overrides:
        try:
            import json  # noqa: PLC0415
            d = json.loads(overrides) if isinstance(overrides, str) else overrides
            if obj_name in d:
                return float(d[obj_name])
        except (ValueError, TypeError):
            pass
    return EXPORT_FLIP_X_DEG.get(obj_name, 0.0)

manifest = []
_shifts = {}     # remember each parent's bed-flatten shift so children can re-use
for obj in targets:
    flip_deg = _resolve_flip(obj.name)

    # Save original transform; we restore it after the export
    orig_loc = obj.location.copy()
    orig_rot_mode = obj.rotation_mode
    obj.rotation_mode = 'XYZ'
    orig_rot = obj.rotation_euler.copy()

    if flip_deg != 0.0:
        # Rotate 180° around X about the bbox center so the object stays
        # roughly in the same world position (just flipped). Without the
        # bbox-pivot adjustment the object would rotate around its origin
        # which usually isn't the geometric center.
        bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        center = Vector((sum(v.x for v in bb)/8, sum(v.y for v in bb)/8, sum(v.z for v in bb)/8))
        rot = Matrix.Rotation(math.radians(flip_deg), 4, 'X')
        # New world matrix: translate to origin, rotate, translate back to bbox center
        T_neg = Matrix.Translation(-center)
        T_pos = Matrix.Translation(center)
        obj.matrix_world = T_pos @ rot @ T_neg @ obj.matrix_world
        bpy.context.view_layer.update()
        print(f"[stl_export]   {obj.name}: applied {flip_deg:.0f}° X-flip about bbox center for export")

    # ── Shift each part to (X=0, Y=0, Z>=0) so the slicer sees it bed-flat ──
    # Bottom and Top use their own bbox center → they import flush on the
    # build plate. Children listed in EXPORT_SHARE_SHIFT_WITH inherit their
    # parent's shift instead, preserving stacking when the user merges parts
    # in the slicer.
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    cx_own = sum(v.x for v in bb) / 8
    cy_own = sum(v.y for v in bb) / 8
    zmin_own = min(v.z for v in bb)

    share_with = EXPORT_SHARE_SHIFT_WITH.get(obj.name)
    # Multi-decoration siblings (DecorationFilling, …) share Top's shift.
    if share_with is None and obj.name.startswith('Decoration'):
        share_with = EXPORT_SHARE_SHIFT_WITH.get('Decoration', 'Top')
    if share_with and share_with in _shifts:
        cx, cy, zoff = _shifts[share_with]
        obj.matrix_world = Matrix.Translation((cx, cy, zoff)) @ obj.matrix_world
        print(f"[stl_export]   {obj.name}: shared shift from {share_with} (X={cx:+.2f} Y={cy:+.2f} Z={zoff:+.2f}); preserves stacking")
    else:
        obj.matrix_world = Matrix.Translation((-cx_own, -cy_own, -zmin_own)) @ obj.matrix_world
        _shifts[obj.name] = (-cx_own, -cy_own, -zmin_own)
        print(f"[stl_export]   {obj.name}: bed-flattened (shift X={-cx_own:+.2f} Y={-cy_own:+.2f} Z={-zmin_own:+.2f})")
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    out_path = os.path.join(out_dir, f"{obj.name}.stl")
    try:
        bpy.ops.wm.stl_export(filepath=out_path, export_selected_objects=True)
    except TypeError:
        bpy.ops.wm.stl_export(filepath=out_path, use_selection=True)
    size = os.path.getsize(out_path) if os.path.isfile(out_path) else 0

    # Restore original transform regardless of whether we flipped
    obj.location = orig_loc
    obj.rotation_euler = orig_rot
    obj.rotation_mode = orig_rot_mode
    bpy.context.view_layer.update()

    manifest.append({"obj": obj.name, "stl": out_path, "bytes": size, "flipped": flip_deg != 0.0})
    print(f"[stl_export] {obj.name} -> {out_path} ({size} bytes" + (" [print-flipped]" if flip_deg != 0.0 else "") + ")")

# ─── Step 7: also mirror to tmp/latest/ so the user always has a known-path copy ──
import shutil
tmp_root = os.path.dirname(out_dir)            # e.g. <repo>/tmp
latest_dir = os.path.join(tmp_root, "latest")
# Wipe only files this script previously created — never touch user-placed
# files (e.g. a hand-built .3mf project, an extracted reference template).
if os.path.isdir(latest_dir):
    for old in os.listdir(latest_dir):
        old_path = os.path.join(latest_dir, old)
        if not os.path.isfile(old_path):
            continue
        if old.lower().endswith(".stl") or old == "manifest.txt":
            try: os.remove(old_path)
            except OSError: pass
os.makedirs(latest_dir, exist_ok=True)
for m in manifest:
    if os.path.isfile(m["stl"]):
        latest_path = os.path.join(latest_dir, os.path.basename(m["stl"]))
        shutil.copy2(m["stl"], latest_path)
        m["latest"] = latest_path

# Also drop a manifest.txt in latest/ so the user (or future Claude) knows
# what was exported and from where.
manifest_path = os.path.join(latest_dir, "manifest.txt")
with open(manifest_path, "w", encoding="utf-8") as fh:
    fh.write(f"timestamp:    {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    fh.write(f"timestamped:  {out_dir}\n")
    fh.write(f"latest:       {latest_dir}\n\n")
    for m in manifest:
        flag = " [print-flipped]" if m.get("flipped") else ""
        fh.write(f"  {m['obj']:<24} {m['bytes']:>8} bytes{flag}\n")

# ─── Step 8: report ───────────────────────────────────────────────────
print("\n=== STL EXPORT MANIFEST ===")
for m in manifest:
    print(f"  {m['obj']:<24} {m['bytes']:>8} bytes   {m['stl']}")
print("============================")
print(f"[stl_export] done. {len(manifest)} STL(s) in {out_dir}")
print(f"[stl_export] mirrored to {latest_dir}/ (always-current copy + manifest.txt)")
