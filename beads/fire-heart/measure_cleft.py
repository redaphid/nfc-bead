"""Measure the heart's top edge near the cleft: tangent angle + curvature vs
arc length, to locate straight (zero-curvature) segments — the 'diagonal lines
leading to the dimple'. Run: uv run python beads/fire-heart/measure_cleft.py
"""
import json
import numpy as np

d = json.load(open('beads/fire-heart/regions.json'))
P = np.array(d['regions']['heart']['polygons'][0]['outer'])  # (N,2) mm, +Y up

# Cleft apex = lowest-y point in the UPPER-center band (between the lobes).
mask = (np.abs(P[:, 0]) < 4.0) & (P[:, 1] > 2.0)
apex_y = P[mask, 1].min()
apex_i = np.where(mask & (P[:, 1] == apex_y))[0][0]
print(f"dimple apex ~ ({P[apex_i,0]:+.2f},{P[apex_i,1]:+.2f})  (index {apex_i} of {len(P)})")

# Walk the RIGHT side upward from the apex: order points by going forward
# in index from the apex, take the first ~70 points (the cleft→lobe stretch).
N = len(P)
idx = [(apex_i + k) % N for k in range(70)]
pts = P[idx]

# Per-step segment angle (deg from +X) and turning (curvature proxy).
seg = np.diff(pts, axis=0)
seglen = np.hypot(seg[:, 0], seg[:, 1])
ang = np.degrees(np.arctan2(seg[:, 1], seg[:, 0]))
turn = np.diff(ang)
turn = (turn + 180) % 360 - 180          # wrap to [-180,180]
s = np.concatenate([[0], np.cumsum(seglen)])

print(f"\n{'s(mm)':>6} {'x':>6} {'y':>6} {'segAngle°':>9} {'turn°/seg':>9}")
for k in range(0, 40):
    t = f"{turn[k]:+8.2f}" if k < len(turn) else "    --"
    print(f"{s[k]:6.2f} {pts[k,0]:6.2f} {pts[k,1]:6.2f} {ang[k]:9.2f} {t:>9}")

# Flag the straight run: consecutive segments with |turn| < 1° = a line.
straight = [k for k in range(len(turn)) if abs(turn[k]) < 1.0]
if straight:
    runs = []
    a = straight[0]; prev = straight[0]
    for k in straight[1:]:
        if k == prev + 1: prev = k
        else: runs.append((a, prev)); a = k; prev = k
    runs.append((a, prev))
    print("\nStraight runs (|turn|<1°/seg):")
    for a, b in runs:
        if b - a >= 2:
            print(f"  s=[{s[a]:.2f},{s[b+1]:.2f}]mm  len={s[b+1]-s[a]:.2f}mm  "
                  f"angle~{np.mean(ang[a:b+1]):.1f}deg  ({b-a+1} segments)")
