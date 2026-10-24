"""Export the printable STL files and preview images of the combined travel case.

Run tools/build_case_data.py first if case_data.scad is missing or the
parameters changed. Rendering the base and lid takes several minutes each;
they run in parallel.
"""
import os
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

TRAVEL = Path(__file__).resolve().parent.parent
OPENSCAD = os.environ.get("OPENSCAD", r"C:\Program Files\OpenSCAD (Nightly)\openscad.com")
SCAD = TRAVEL / "combined_case.scad"
STL = TRAVEL / "stl"
PREVIEW = TRAVEL / "preview"
PARTS = ["base", "lid", "test_frame"]


def openscad(*args):
    subprocess.run([OPENSCAD, *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def export(part):
    out = STL / f"travel_case_{part}.stl"
    openscad("--render", "--export-format", "binstl", "-D", f'part="{part}"', "-o", str(out), str(SCAD))
    return out


def volume_cm3(path):
    data = path.read_bytes()
    n = struct.unpack("<I", data[80:84])[0]
    t = np.frombuffer(data[84:84 + n * 50],
                      dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", 9), ("a", "<u2")]))["v"].reshape(-1, 3, 3)
    t = t.astype(float)
    return abs(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6) / 1000


def preview(name, scad_text, camera, ortho=False):
    src = PREVIEW / f"_{name}.scad"
    src.write_text(scad_text)
    args = ["-o", str(PREVIEW / f"{name}.png"), "--imgsize=1200,900", f"--camera=0,0,0,{camera},0",
            "--viewall", "--autocenter", "--colorscheme=Tomorrow"]
    if ortho:
        args.append("--projection=o")
    openscad(*args, str(src))
    src.unlink()


def main():
    STL.mkdir(exist_ok=True)
    PREVIEW.mkdir(exist_ok=True)
    with ThreadPoolExecutor(len(PARTS)) as pool:
        files = list(pool.map(export, PARTS))
    for f in files:
        print(f"{f.name}: {volume_cm3(f):.0f} cm3")

    base = (STL / "travel_case_base.stl").as_posix()
    lid = (STL / "travel_case_lid.stl").as_posix()
    frame = (STL / "travel_case_test_frame.stl").as_posix()
    views = [
        ("closed", f'color("SteelBlue") import("{base}"); color("Orange") import("{lid}");', "60,0,210"),
        ("open", f'color("SteelBlue") import("{base}");\n'
                 f'color("Orange") translate([186, 0, 77]) mirror([0, 0, 1]) import("{lid}");', "50,0,25"),
        ("base", f'color("SteelBlue") import("{base}");', "20,0,0"),
        ("lid_inside", f'color("Orange") import("{lid}");', "180,0,25"),
        ("test_frame", f'color("SteelBlue") import("{frame}");', "35,0,20"),
    ]
    with ThreadPoolExecutor(len(views)) as pool:
        list(pool.map(lambda v: preview(*v), views))
    print(f"previews in {PREVIEW.relative_to(TRAVEL.parent.parent)}")


if __name__ == "__main__":
    main()
