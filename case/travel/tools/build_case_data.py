"""Generate case_data.scad for combined_case.scad.

The keyboard pockets come from f3rn4nd0d's Charybdis Mini Travel Case
(https://github.com/f3rn4nd0d/Charybdis-Mini-Travel-Case, CC BY-NC-SA 4.0).
The script downloads that repository, measures the inside of each closed half
(wall outline and cover ceiling) and writes everything combined_case.scad needs.

Needs: git, OpenSCAD (a 2025+ build with the Manifold backend), Python with
numpy and shapely.  Set OPENSCAD to the openscad executable if it is not at
the default Windows nightly location.
"""
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
TRAVEL = HERE.parent
CACHE = HERE / ".cache"
SRC_REPO = "https://github.com/f3rn4nd0d/Charybdis-Mini-Travel-Case.git"
SRC_COMMIT = "e74aa3ab013a66593b5b0628cd530225ea31bd40"
OPENSCAD = os.environ.get("OPENSCAD", r"C:\Program Files\OpenSCAD (Nightly)\openscad.com")

# Placement of the original parts so that each cover sits on its bottom
# (found by matching the outlines; the bottoms stay where they are).
COVER_LEFT = (270, -103.0, 217.5)    # rotate about z (deg), then translate x, y
COVER_RIGHT = (90, -179.0, -288.5)
# Where the right pocket goes, relative to its original position: next to the
# left pocket with a 4.5 mm divider. This layout leaves a corner for the dongle.
RIGHT_SHIFT = (12.0, 314.9)

WALL_OUT = 6.0     # outline of the cavities to the outside of the case
WALL_IN = 4.5      # between two cavities
FLOOR = 2.5
TOP = 2.5
Z_POCKET = -3.0    # keyboard floor (the original bottom has a 2 mm deep pocket)
CLEAR = 1.0        # extra space above the keycaps
CABLE_W = 40.0     # cable compartment across one end (1 m USB cable)
# Dongle standing on its rear cap: 43.2 x 38.0 footprint, 51.3 tall, plus clearance
DONGLE = (46.2, 41.0, 53.5)
GRID = 1.0         # ceiling height map resolution (mm)


def run_openscad(scad_text, out_path):
    scad = CACHE / (Path(out_path).stem + ".scad")
    scad.write_text(scad_text)
    fmt = ["--export-format", "binstl"] if str(out_path).endswith(".stl") else []
    subprocess.run([OPENSCAD, *fmt, "-o", str(out_path), str(scad)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fetch_source():
    repo = CACHE / "Charybdis-Mini-Travel-Case"
    if not repo.exists():
        subprocess.run(["git", "clone", "-q", SRC_REPO, str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", SRC_COMMIT], check=True)
    models = repo / "models" / "flat"
    for name in ["left", "left_bottom", "right", "right_bottom"]:
        out = CACHE / f"{name}.stl"
        if not out.exists():
            run_openscad(f'import("{(models / (name + ".3mf")).as_posix()}");', out)


def load_stl(path):
    data = Path(path).read_bytes()
    n = struct.unpack("<I", data[80:84])[0]
    rec = np.frombuffer(data[84:84 + n * 50],
                        dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", 9), ("a", "<u2")]))
    return rec["v"].reshape(-1, 3, 3).astype(float)


def transform(tri, rot, tx, ty):
    t = np.radians(rot)
    c, s = np.cos(t), np.sin(t)
    x = tri[..., 0] * c - tri[..., 1] * s + tx
    y = tri[..., 0] * s + tri[..., 1] * c + ty
    return np.stack([x, y, tri[..., 2]], -1)


def inner_outline(side, cover):
    """Area inside the cover wall, 10 mm above the bottom, as a shapely polygon."""
    rot, tx, ty = cover
    c = (CACHE / f"{side}.stl").as_posix()
    b = (CACHE / f"{side}_bottom.stl").as_posix()
    out = CACHE / f"inner_{side}.svg"
    run_openscad(f"""
        module cover() translate([{tx}, {ty}, 0]) rotate([0, 0, {rot}]) import("{c}");
        module bottom() import("{b}");
        offset(1) offset(-1) difference() {{
            projection(cut = true) translate([0, 0, 4]) bottom();
            offset(0.05) projection(cut = true) translate([0, 0, -10]) cover();
        }}""", out)
    polys = []
    for d in re.findall(r'd="([^"]+)"', out.read_text()):
        for part in re.split(r"[Mm]", d):
            nums = list(map(float, re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", part)))
            if len(nums) >= 6:
                polys.append(Polygon([(nums[i], -nums[i + 1]) for i in range(0, len(nums) - 1, 2)]).buffer(0))
    return max(getattr(u := unary_union(polys), "geoms", [u]), key=lambda g: g.area)


def neighbours(h, r):
    p = np.pad(h, r, mode="edge")
    n, m = h.shape
    return np.stack([p[j:j + n, i:i + m] for j in range(2 * r + 1) for i in range(2 * r + 1)])


def ceiling(side, cover):
    """Height map of the inner surface of the cover top (faces that point down)."""
    tri = transform(load_stl(CACHE / f"{side}.stl"), *cover)
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    pts = tri[(nrm[:, 2] < -0.3) & (tri.mean(1)[:, 2] > 3)].reshape(-1, 3)
    x0, y0 = pts[:, 0].min() - GRID, pts[:, 1].min() - GRID
    gx = np.arange(x0, pts[:, 0].max() + GRID + 0.01, GRID)
    gy = np.arange(y0, pts[:, 1].max() + GRID + 0.01, GRID)
    h = np.full((len(gy), len(gx)), np.inf)
    ix = np.clip(((pts[:, 0] - x0) / GRID).round().astype(int), 0, len(gx) - 1)
    iy = np.clip(((pts[:, 1] - y0) / GRID).round().astype(int), 0, len(gy) - 1)
    np.minimum.at(h, (iy, ix), pts[:, 2])
    h[np.isinf(h)] = np.nan
    while np.isnan(h).any():                       # fill empty cells from their neighbours
        with np.errstate(all="ignore"):
            filled = np.nanmin(np.where(np.isnan(neighbours(h, 1)), np.inf, neighbours(h, 1)), axis=0)
        h = np.where(np.isnan(h) & np.isfinite(filled), filled, h)
    r_med, r_avg = round(4 / GRID), round(2 / GRID)
    med = np.median(neighbours(h, r_med), axis=0)
    h = np.where(h < med - 1.5, med, h)            # remove low spikes
    h = neighbours(h, r_avg).mean(axis=0)          # smooth
    pad = round(6 / GRID)                          # extend past the walls
    h = np.pad(h, pad, mode="edge")
    gx = np.concatenate([gx[0] - GRID * np.arange(pad, 0, -1), gx, gx[-1] + GRID * np.arange(1, pad + 1)])
    gy = np.concatenate([gy[0] - GRID * np.arange(pad, 0, -1), gy, gy[-1] + GRID * np.arange(1, pad + 1)])
    return gx, gy, h


def find_rect(region, w, h, score):
    best = None
    for g in getattr(region, "geoms", [region]):
        x0, y0, x1, y1 = g.bounds
        for ww, hh in [(w, h), (h, w)]:
            for x in np.arange(x0, x1 - ww + 0.1, 1):
                for y in np.arange(y0, y1 - hh + 0.1, 1):
                    if g.contains(box(x, y, x + ww, y + hh)):
                        s = score(x, y, ww, hh)
                        if best is None or s < best[0]:
                            best = (s, (x, y, ww, hh))
    return best[1]


def scad_polygon(p):
    pts = list(p.simplify(0.15).exterior.coords)[:-1]
    return "polygon(%s);" % [[round(x, 2), round(y, 2)] for x, y in pts]


def scad_ceiling(name, gx, gy, h, ox, oy):
    nj, ni = len(gy), len(gx)
    top = [[round(float(gx[i] + ox), 2), round(float(gy[j] + oy), 2), round(float(h[j, i]), 2)]
           for j in range(nj) for i in range(ni)]
    bottom = [[p[0], p[1], Z_POCKET - 1] for p in top]
    base = len(top)
    faces = []
    for j in range(nj - 1):
        for i in range(ni - 1):
            a, b, c, d = j * ni + i, j * ni + i + 1, (j + 1) * ni + i + 1, (j + 1) * ni + i
            faces += [[a, d, c, b], [base + a, base + b, base + c, base + d]]
    def side(seq):
        for p0, p1 in zip(seq[:-1], seq[1:]):
            a, b = p0[0] * ni + p0[1], p1[0] * ni + p1[1]
            faces.append([a, b, base + b, base + a])
    side([(0, i) for i in range(ni)])
    side([(j, ni - 1) for j in range(nj)])
    side([(nj - 1, i) for i in range(ni - 1, -1, -1)])
    side([(j, 0) for j in range(nj - 1, -1, -1)])
    return "module %s() polyhedron(points=%s, faces=%s, convexity=6);\n" % (name, top + bottom, faces)


def main():
    CACHE.mkdir(exist_ok=True)
    fetch_source()
    left = inner_outline("left", COVER_LEFT)
    right = affinity.translate(inner_outline("right", COVER_RIGHT), *RIGHT_SHIFT)
    print("divider between the halves: %.1f mm" % left.distance(right))
    ceil_l = ceiling("left", COVER_LEFT)
    ceil_r = ceiling("right", COVER_RIGHT)

    pockets = unary_union([left, right])
    b = pockets.bounds
    free = box(*b).difference(pockets.buffer(WALL_IN))
    dongle = find_rect(free, DONGLE[0], DONGLE[1],
                       lambda x, y, w, h: min(abs(x - b[0]), abs(x + w - b[2])) + min(abs(y - b[1]), abs(y + h - b[3])))
    dongle_box = box(dongle[0], dongle[1], dongle[0] + dongle[2], dongle[1] + dongle[3])
    ob = unary_union([pockets, dongle_box]).bounds
    cable = (ob[0], ob[3] + WALL_IN, ob[2] - ob[0], CABLE_W)
    cable_box = box(cable[0], cable[1], cable[0] + cable[2], cable[1] + cable[3])
    x0, y0, x1, y1 = ob[0] - WALL_OUT, ob[1] - WALL_OUT, ob[2] + WALL_OUT, cable[1] + cable[3] + WALL_OUT
    zmax = max(ceil_l[2].max(), ceil_r[2].max()) + CLEAR

    # magnets: spread over the material around the cavities (farthest point sampling)
    cavities = unary_union([pockets, dongle_box, cable_box])
    rounded = box(x0, y0, x1, y1).buffer(-12).buffer(12)
    cand = [Point(x, y) for x in np.arange(x0, x1, 1.5) for y in np.arange(y0, y1, 1.5)]
    cand = [p for p in cand if rounded.contains(p) and rounded.exterior.distance(p) >= 4.6
            and cavities.distance(p) >= 4.6]
    mags = [min(cand, key=lambda p: p.x + p.y)]
    while True:
        d = [min(p.distance(m) for m in mags) for p in cand]
        i = int(np.argmax(d))
        if d[i] < 45:
            break
        mags.append(cand[i])

    out = TRAVEL / "case_data.scad"
    with open(out, "w") as f:
        f.write("// Generated by tools/build_case_data.py - do not edit by hand.\n")
        f.write("outer = [%.2f, %.2f, %.2f, %.2f];\n" % (x0, y0, x1, y1))
        f.write("z_pocket = %.2f; z_floor = %.2f; z_top = %.2f; clear = %.2f;\n"
                % (Z_POCKET, Z_POCKET - FLOOR, zmax + TOP, CLEAR))
        f.write("dongle_pocket = %s; dongle_h = %.2f;\n" % ([round(float(v), 2) for v in dongle], DONGLE[2]))
        f.write("cable_pocket = %s;\n" % [round(float(v), 2) for v in cable])
        f.write("magnets = %s;\n" % [[round(p.x, 2), round(p.y, 2)] for p in mags])
        f.write("module outline_left() %s\n" % scad_polygon(left))
        f.write("module outline_right() %s\n" % scad_polygon(right))
        f.write(scad_ceiling("ceiling_left", *ceil_l, 0, 0))
        f.write(scad_ceiling("ceiling_right", *ceil_r, *RIGHT_SHIFT))
    print("case %.1f x %.1f x %.1f mm, %d magnets -> %s"
          % (x1 - x0, y1 - y0, zmax + TOP - (Z_POCKET - FLOOR), len(mags), out.relative_to(TRAVEL.parent.parent)))


if __name__ == "__main__":
    sys.exit(main())
