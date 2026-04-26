"""Defensive STL export for an NFC bead.

Strips any architect aesthetic + debug overlays first, then exports
each printable object as its own STL with sanity checks.

Single source of truth for "send the bead to the slicer." Use this
instead of bare `bpy.ops.wm.stl_export(selection=True)` after a
debug-coloring or cinematic-mode session — those leave overlay
objects in the scene that absolutely should NOT ship to the printer.
"""
import bpy
import os
import time
from mathutils import Vector

# ─── Tunables ─────────────────────────────────────────────────────────
# Canonical bead-component names (project-wide convention):
#   Bottom, Top, Decoration. Build scripts must produce these names.
# Legacy bead-specific names (rezz_bottom etc.) are accepted as a fallback.
EXPECTED_OBJECTS = [
    "Bottom",
    "Top",
    "Decoration",
]
# Fallback by suffix if canonical names aren't present
FALLBACK_SUFFIXES = [
    ("_bottom",     "Bottom"),
    ("_top_body",   "Top"),
    ("_top",        "Top"),
    ("_top_spiral", "Decoration"),
    ("_spiral",     "Decoration"),
    ("_decor",      "Decoration"),
    ("_accent",     "Decoration"),
]

OUT_DIR = None     # default: tmp/stl_export_<timestamp>/ in repo root

# Expected dimensions per prompts/nfc-bead/prompt.md (rezz defaults).
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
    targets = []
    for name in EXPECTED_OBJECTS:
        o = bpy.data.objects.get(name)
        if o and o.type == 'MESH':
            targets.append(o)
    if targets:
        return targets
    # Fallback by suffix
    for suffix, fallback in FALLBACK_SUFFIXES:
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.name.lower().endswith(suffix):
                targets.append(o)
        if not targets and (o := bpy.data.objects.get(fallback)):
            if o.type == 'MESH':
                targets.append(o)
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
    raise RuntimeError(f"No printable objects found. Expected one of {EXPECTED_OBJECTS} or any *_bottom/_top/_spiral mesh.")

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
manifest = []
for obj in targets:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    out_path = os.path.join(out_dir, f"{obj.name}.stl")
    try:
        bpy.ops.wm.stl_export(filepath=out_path, export_selected_objects=True)
    except TypeError:
        # Older API
        bpy.ops.wm.stl_export(filepath=out_path, use_selection=True)
    size = os.path.getsize(out_path) if os.path.isfile(out_path) else 0
    manifest.append({"obj": obj.name, "stl": out_path, "bytes": size})
    print(f"[stl_export] {obj.name} -> {out_path} ({size} bytes)")

# ─── Step 7: report ───────────────────────────────────────────────────
print("\n=== STL EXPORT MANIFEST ===")
for m in manifest:
    print(f"  {m['obj']:<24} {m['bytes']:>8} bytes   {m['stl']}")
print("============================")
print(f"[stl_export] done. {len(manifest)} STL(s) in {out_dir}")
