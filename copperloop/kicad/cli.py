"""kicad-cli wrapper. kicad-cli is the only authority for DRC, ERC and exports."""
from __future__ import annotations
import json, os, shutil, subprocess
from pathlib import Path

CANDIDATES = [
    os.environ.get("KICAD_CLI", ""),
    shutil.which("kicad-cli") or "",
    "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    "/usr/bin/kicad-cli",
    "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe",
]

def kicad_cli() -> str:
    for c in CANDIDATES:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("kicad-cli not found; set KICAD_CLI")

def run(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run([kicad_cli(), *args], capture_output=True, text=True, check=check)

def version() -> str:
    return run("version").stdout.strip()

def drc(board: Path, out: Path, parity: bool = True, all_track_errors: bool = True, refill: bool = True) -> dict:
    """Run DRC, return the parsed JSON report (schema drc.v1).

    refill=True re-pours zones in memory first (never saves the board): a board saved
    with stale fills otherwise reports phantom clearance errors against every new via.
    """
    args = ["pcb", "drc", "--format", "json", "--severity-all", "-o", str(out)]
    if refill: args.append("--refill-zones")
    if parity: args.append("--schematic-parity")
    if all_track_errors: args.append("--all-track-errors")
    r = run(*args, str(board))
    if not out.exists():
        raise RuntimeError(f"DRC produced no report:\n{r.stdout}\n{r.stderr}")
    return json.loads(out.read_text())

def erc(sch: Path, out: Path) -> dict:
    r = run("sch", "erc", "--format", "json", "--severity-all", "-o", str(out), str(sch))
    if not out.exists():
        raise RuntimeError(f"ERC produced no report:\n{r.stdout}\n{r.stderr}")
    return json.loads(out.read_text())

def export_svg(board: Path, layers: list[str], out: Path, mirror: bool = False, bw: bool = False, page_mode: int = 2) -> Path:
    """SVG of the given layers (one file). page_mode 2 = board area only, 1 = page coordinates (absolute mm)."""
    args = ["pcb", "export", "svg", "-l", ",".join(layers), "--page-size-mode", str(page_mode),
            "--exclude-drawing-sheet", "--mode-single", "-o", str(out)]
    if mirror: args.append("--mirror")
    if bw: args.append("--black-and-white")
    r = run(*args, str(board))
    if not out.exists():
        raise RuntimeError(f"svg export failed:\n{r.stdout}\n{r.stderr}")
    return out
