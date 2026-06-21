# Eye Medallion — print iteration log

Append-only, newest at the top. Each entry: date, version, what was printed
(parameters), failure mode, parameter changes for next attempt, lesson captured.

---

## (not yet printed)

v1 of the geometry is exported and bundled (`print/eye_medallion.3mf`) but has
not been fed to the printer. First physical print should record results here.

Inherited risk to watch (from `gymnast-medallion`): the 1.2 mm string hole in
the 2.0 mm Top leaves ~0.4 mm walls above/below — bridged, printable on a tuned
Centauri Carbon 2 but marginal. If it fails, bump `THICKNESS`/`HOLE` rather than
moving the hole back to the seam (recipe gotcha #23).
