"""`cl route SPEC.json [--apply]`: hand-planned routes as gated transactions on the live board."""
from __future__ import annotations
import json, os, subprocess, tempfile
from pathlib import Path
from .kicad import ipc
from .fanout import kicad_python, snapshot

def check(board: Path, spec: Path) -> list[dict]:
    out = board.parent / "route-check.json"
    r = subprocess.run([kicad_python(), str(Path(__file__).parent / "route" / "route_check.py"), str(board), str(spec), "--json", str(out)], capture_output=True, text=True)
    if not out.exists(): raise RuntimeError(f"route check failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return json.loads(out.read_text())

def apply(session: ipc.Session, entries: list[dict]) -> int:
    from kipy.board_types import Track, Via, ArcTrack, BoardLayer
    from kipy.geometry import Vector2
    from kipy.util.units import from_mm
    b = session.board
    nets = {n.name: n for n in b.get_nets()}
    layer_ids = {"F.Cu": BoardLayer.BL_F_Cu, "B.Cu": BoardLayer.BL_B_Cu, "In1.Cu": BoardLayer.BL_In1_Cu, "In2.Cu": BoardLayer.BL_In2_Cu}
    for i in (BoardLayer.BL_In1_Cu, BoardLayer.BL_In2_Cu): layer_ids[b.get_layer_name(i)] = i
    from kipy.util.units import to_mm
    def near(ax, ay, bx, by, tol=0.05): return abs(ax - bx) <= tol and abs(ay - by) <= tol
    n = 0
    for e in entries:
        net = nets[e["net"]]; items = []
        removals = []
        if e.get("remove_vias") or e.get("remove_tracks"):
            for v in b.get_vias():
                if v.net.name != e["net"]: continue
                if any(near(x, y, to_mm(v.position.x), to_mm(v.position.y)) for x, y in e.get("remove_vias", [])): removals.append(v)
            for t in b.get_tracks():
                if t.net.name != e["net"]: continue
                sx, sy, ex, ey = to_mm(t.start.x), to_mm(t.start.y), to_mm(t.end.x), to_mm(t.end.y)
                if any((near(x1, y1, sx, sy) and near(x2, y2, ex, ey)) or (near(x1, y1, ex, ey) and near(x2, y2, sx, sy)) for x1, y1, x2, y2 in e.get("remove_tracks", [])): removals.append(t)
        pts = e.get("pts", [])
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) == (x2, y2): continue
            t = Track(); t.start = Vector2.from_xy(from_mm(x1), from_mm(y1)); t.end = Vector2.from_xy(from_mm(x2), from_mm(y2))
            t.width = from_mm(e.get("width", 0.3)); t.layer = layer_ids[e.get("layer", "B.Cu")]; t.net = net; items.append(t)
        for sx, sy, mx, my, ex, ey in e.get("arcs", []):
            arc = ArcTrack(); arc.start = Vector2.from_xy(from_mm(sx), from_mm(sy)); arc.mid = Vector2.from_xy(from_mm(mx), from_mm(my)); arc.end = Vector2.from_xy(from_mm(ex), from_mm(ey))
            arc.width = from_mm(e.get("width", 0.3)); arc.layer = layer_ids[e.get("layer", "B.Cu")]; arc.net = net; items.append(arc)
        for x, y in e.get("vias", []):
            v = Via(); v.position = Vector2.from_xy(from_mm(x), from_mm(y)); v.diameter = from_mm(e.get("via_d", 0.6)); v.drill_diameter = from_mm(e.get("via_drill", 0.3)); v.net = net; items.append(v)
        if not items and not removals: continue
        c = b.begin_commit()
        try:
            if removals: b.remove_items(removals)
            if items: b.create_items(items)
            b.push_commit(c, f"copperloop route {e.get('name', e['net'])}"); n += 1
        except Exception:
            b.drop_commit(c); raise
    return n

def run(spec_path: Path, apply_changes: bool, only_ok: bool = True) -> dict:
    from . import gate
    s = ipc.connect()
    work = Path(tempfile.mkdtemp(prefix="copperloop-route-"))
    board = snapshot(s, work)
    spec = json.loads(Path(spec_path).read_text())
    results = check(board, spec_path)
    res = {"work": str(work), "results": results, "applied": 0, "before": None, "after": None, "ok": None}
    good = [e for e, r in zip(spec, results) if r["ok"]]
    if not apply_changes or not good: return res
    if not only_ok and len(good) != len(spec): raise RuntimeError("some routes failed the check; fix them or allow --partial")
    res["before"] = gate.run(board, state_dir=work / "before")["now"]
    res["applied"] = apply(s, good)
    s.board.refill_zones()
    board2 = snapshot(s, work / "after")
    after = gate.run(board2, state_dir=work / "after" / ".copperloop")
    res["after"] = after["now"]
    res["ok"] = after["now"]["errors"] <= res["before"]["errors"] and after["now"]["unconnected"] <= res["before"]["unconnected"] and after["now"]["parity"] == 0
    res["after_open_nets"] = after["open_nets"]
    return res


def run_file(spec_path: Path, board: Path, apply_changes: bool, only_ok: bool = True, allow_opens: bool = False) -> dict:
    """File mode (KiCad closed): check against BOARD, apply with route/apply_file.py into a scratch copy,
    gate there, and on PASS copy only the .kicad_pcb back over BOARD. PASS = errors, unconnected and parity
    did not grow; with allow_opens (clean-up specs that remove copper on purpose) unconnected may grow."""
    import shutil
    from . import gate
    from .fanout import kicad_python
    board = Path(board).resolve(); work = Path(tempfile.mkdtemp(prefix="copperloop-routefile-"))
    for f in board.parent.iterdir():
        if f.suffix in (".kicad_pcb", ".kicad_pro", ".kicad_sch", ".kicad_dru") or f.name in ("fp-lib-table", "sym-lib-table"): shutil.copy(f, work / f.name)
    if (board.parent / "lib").is_dir(): os.symlink(board.parent / "lib", work / "lib")
    wb = work / board.name
    results = check(wb, spec_path)
    res = {"work": str(work), "results": results, "applied": 0, "before": None, "after": None, "ok": None}
    good = [r for r in results if r["ok"]]
    if not apply_changes or not good: return res
    if not only_ok and len(good) != len(results): raise RuntimeError("some routes failed the check")
    res["before"] = gate.run(wb, state_dir=work / "before")["now"]
    out = work / "out.kicad_pcb"; chk = work / "route-check.json"
    r = subprocess.run([kicad_python(), str(Path(__file__).parent / "route" / "apply_file.py"), str(wb), str(spec_path), str(out), "--only-ok", str(chk)], capture_output=True, text=True)
    if not out.exists(): raise RuntimeError(f"file apply failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    shutil.copy(out, wb); shutil.copy(board.parent / board.with_suffix(".kicad_pro").name, work / board.with_suffix(".kicad_pro").name)   # SaveBoard clobbered the scratch .kicad_pro
    after = gate.run(wb, state_dir=work / "after"); res["after"] = after["now"]; res["applied"] = len(good)
    res["ok"] = after["now"]["errors"] <= res["before"]["errors"] and (allow_opens or after["now"]["unconnected"] <= res["before"]["unconnected"]) and after["now"]["parity"] <= res["before"]["parity"]
    res["after_open_nets"] = after["open_nets"]
    if res["ok"]: shutil.copy(wb, board)
    return res
