import sys, numpy as np, trimesh
PEG = (7.67, 0.67)

def polys(mesh, z):
    s = mesh.section(plane_origin=[0,0,z], plane_normal=[0,0,1])
    if s is None: return []
    p, _ = s.to_planar(to_2D=np.eye(4))
    return list(p.polygons_full)

def peg_radius(bot, h):
    """radius of the peg column at height h above the mating face"""
    z = MATE_B + h
    best = None
    for poly in polys(bot, z):
        d = poly.distance(__import__('shapely.geometry', fromlist=['Point']).Point(*PEG))
        if d < 1e-9 and poly.area < 40:          # small island = a peg
            best = poly.area
    return None if best is None else (best/np.pi)**0.5

def socket_radius(top, h):
    """radius of the socket bore at depth h below the mating face plane"""
    from shapely.geometry import Point
    z = MATE_T + h
    pt = Point(*PEG)
    for poly in polys(top, z):
        for ring in poly.interiors:
            from shapely.geometry import Polygon
            r = Polygon(ring)
            if r.contains(pt) or r.distance(pt) < 1.5:
                return (r.area/np.pi)**0.5
    return None

for name in sys.argv[1:]:
    bot = trimesh.load(f"beads/glow-set/print/{name}/Bottom.stl")
    top = trimesh.load(f"beads/glow-set/print/{name}/Top.stl")
    # Bottom: mating face = where the bulk ends (pegs stick up above it)
    zb = bot.bounds[:,2]
    MATE_B = None
    for z in np.arange(zb[1]-0.02, zb[0], -0.05):
        a = sum(p.area for p in polys(bot, z))
        if a > 60:                                # bulk body cross-section
            MATE_B = z; break
    MATE_T = top.bounds[0,2]
    print(f"\n=== {name} ===")
    print(f"  Bottom z {zb[0]:.2f}..{zb[1]:.2f}   mating face z={MATE_B:.2f}  peg protrusion={zb[1]-MATE_B:.2f}mm")
    print(f"  {'h(mm)':>7} {'peg r':>8} {'socket r':>9} {'gap':>7}")
    eng = 0.0
    hs = np.arange(0.0, 2.31, 0.1)
    for h in hs:
        pr = peg_radius(bot, h); sr = socket_radius(top, h)
        if pr is None and sr is None: continue
        gap = (sr-pr) if (pr and sr) else None
        if gap is not None and gap <= 0.08: eng += 0.1
        print(f"  {h:7.2f} {('%.3f'%pr) if pr else '   -  ':>8} "
              f"{('%.3f'%sr) if sr else '   -  ':>9} {('%.3f'%gap) if gap is not None else '  -  ':>7}")
    print(f"  ENGAGEMENT (gap<=0.08mm): {eng:.2f} mm")
