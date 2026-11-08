#!/usr/bin/env python3
"""Runs Trivy and Grype scans on baseline, patched, and VEX-attested images."""

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCANS_DIR = REPO_ROOT / "scans"
BASELINE_IMAGE = os.environ.get("BASELINE_IMAGE", "nginx:1.25-bookworm")
PATCHED_IMAGE = os.environ.get("PATCHED_IMAGE", "nginx:1.25-bookworm-patched")


def find_bin(name: str) -> str:
    return shutil.which(name) or str(Path("D:/DevOps/commands") / f"{name}.exe")


def scan(cmd: list[str], out: Path) -> None:
    print(f"==> {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", check=True)
    out.write_text(res.stdout, encoding="utf-8")


def main() -> None:
    SCANS_DIR.mkdir(exist_ok=True)
    trivy, grype = find_bin("trivy"), find_bin("grype")

    if not (SCANS_DIR / "baseline-trivy.txt").exists():
        scan([trivy, "image", "--quiet", BASELINE_IMAGE], SCANS_DIR / "baseline-trivy.txt")
    shutil.copyfile(SCANS_DIR / "baseline-trivy.txt", REPO_ROOT / "baseline-trivy.txt")

    if not (SCANS_DIR / "baseline-grype.txt").exists():
        scan([grype, "-q", BASELINE_IMAGE], SCANS_DIR / "baseline-grype.txt")
    shutil.copyfile(SCANS_DIR / "baseline-grype.txt", REPO_ROOT / "baseline-grype.txt")

    scan([trivy, "image", "--quiet", PATCHED_IMAGE], SCANS_DIR / "patched-trivy.txt")
    scan([grype, "-q", PATCHED_IMAGE], SCANS_DIR / "patched-grype.txt")
    scan([trivy, "image", "--quiet", "--vex", "vex.openvex.json", PATCHED_IMAGE], SCANS_DIR / "patched-trivy-vex.txt")
    scan([grype, "-q", PATCHED_IMAGE, "--vex", "vex.openvex.json"], SCANS_DIR / "patched-grype-vex.txt")
    print("==> Scans saved to scans/")


if __name__ == "__main__":
    main()
