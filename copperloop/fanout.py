"""`cl fanout NET`: plane fan-out on the live board.

1. Pull the open board as text over IPC (no disk dependency on an unsaved editor).
2. Plan stubs + vias with KiCad's own collision shapes (route/fanout_plan.py under
   KiCad's bundled Python).
3. Apply over IPC, one commit per pad, so the editor shows every step and Ctrl+Z
   undoes one pad at a time.
4. Gate: pull the board again, run kicad-cli DRC + parity beside the real project files.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from .kicad import ipc

KICAD_PY_CANDIDATES = [
    os.environ.get("KICAD_PYTHON", ""),
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3",
    "/usr/bin/python3",
]

def kicad_python() -> str:
    for c in KICAD_PY_CANDIDATES:
        if c and Path(c).exists():
            if subprocess.run([c, "-c", "import pcbnew"], capture_output=True).returncode == 0:
                return c
    raise FileNotFoundError("no Python with the pcbnew module found; set KICAD_PYTHON")

def snapshot(session: ipc.Session, work: Path) -> Path:
    """Write the live board plus the project's .kicad_pro/.kicad_sch into work/."""
    work.mkdir(parents=True, exist_ok=True)
    doc = session.board.document
    proj = Path(doc.project.path); name = doc.board_filename
    board = work / name; board.write_text(session.board.get_as_string())
    for ext in (".kicad_pro", ".kicad_sch"):
        src = proj / (Path(name).stem + ext)
        if src.exists(): shutil.copy(src, work / src.name)
    for extra in ("fp-lib-table", "sym-lib-table"):   # without these DRC reports every footprint as a library mismatch
        if (proj / extra).exists(): shutil.copy(proj / extra, work / extra)
    if (proj / "lib").is_dir() and not (work / "lib").exists():
        os.symlink(proj / "lib", work / "lib")
    return board

def plan(board: Path, nets: list[str], clr: float, via: tuple[float, float], stub: float, only: list[str] | None, gnd_pads: list[str]) -> dict:
    out = board.parent / "plan.json"
    cmd = [kicad_python(), str(Path(__file__).parent / "route" / "fanout_plan.py"), str(board), "--json", str(out),
           "--nets", *nets, "--clr", str(clr), "--via", str(via[0]), str(via[1]), "--stub", str(stub)]
    if only: cmd += ["--only", *only]
    if gnd_pads: cmd += ["--gnd-pads", *gnd_pads]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not out.exists():
        raise RuntimeError(f"planner failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return json.loads(out.read_text())

def apply(session: ipc.Session, placed: list[dict]) -> int:
    from kipy.board_types import Track, Via, BoardLayer
    from kipy.geometry import Vector2
    from kipy.util.units import from_mm
    b = session.board
    nets = {n.name: n for n in b.get_nets()}
    LAYER = {"F.Cu": BoardLayer.BL_F_Cu, "B.Cu": BoardLayer.BL_B_Cu}
    n = 0
    for p in placed:
        net = nets[p["net"]]
        items = []
        for x1, y1, x2, y2 in p["stubs"]:
            t = Track(); t.start = Vector2.from_xy(from_mm(x1), from_mm(y1)); t.end = Vector2.from_xy(from_mm(x2), from_mm(y2))
            t.width = from_mm(p["stub_w"]); t.layer = LAYER[p["layer"]]; t.net = net; items.append(t)
        v = Via(); v.position = Vector2.from_xy(from_mm(p["via"][0]), from_mm(p["via"][1]))
        v.diameter = from_mm(p["via_d"]); v.drill_diameter = from_mm(p["via_drill"]); v.net = net; items.append(v)
        c = b.begin_commit()
        try:
            b.create_items(items)
            b.push_commit(c, f"copperloop fanout {p['net']} {p['ref']}.{p['pad']}")
            n += 1
        except Exception:
            b.drop_commit(c); raise
    return n

def run(nets: list[str], apply_changes: bool, clr: float = 0.2, via: tuple[float, float] = (0.6, 0.3), stub: float = 0.3,
        only: list[str] | None = None, gnd_pads: list[str] | None = None, refill: bool = True) -> dict:
    from . import gate
    s = ipc.connect()
    work = Path(tempfile.mkdtemp(prefix="copperloop-fanout-"))
    board = snapshot(s, work)
    before = gate.run(board, state_dir=work / "before")
    pl = plan(board, nets, clr, via, stub, only, gnd_pads or [])
    result = {"work": str(work), "placed": len(pl["placed"]), "served": len(pl["served"]), "failed": [(f["ref"], f["pad"]) for f in pl["failed"]],
              "before": before["now"], "applied": 0, "after": None, "ok": None}
    if not apply_changes or not pl["placed"]:
        return result
    result["applied"] = apply(s, pl["placed"])
    if refill: s.board.refill_zones()
    (work / "after").mkdir(exist_ok=True); board2 = snapshot(s, work / "after")
    after = gate.run(board2, state_dir=work / "after" / ".copperloop")
    result["after"] = after["now"]
    result["ok"] = after["now"]["errors"] <= before["now"]["errors"] and after["now"]["parity"] == 0 and after["now"]["unconnected"] <= before["now"]["unconnected"]
    result["after_open_nets"] = after["open_nets"]
    return result
