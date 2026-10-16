"""`cl route SPEC.json [--apply]`: hand-planned routes as gated transactions on the live board."""
from __future__ import annotations
import json, subprocess, tempfile
from pathlib import Path
from .kicad import ipc
from .fanout import kicad_python, snapshot

def check(board: Path, spec: Path) -> list[dict]:
    out = board.parent / "route-check.json"
    r = subprocess.run([kicad_python(), str(Path(__file__).parent / "route" / "route_check.py"), str(board), str(spec), "--json", str(out)], capture_output=True, text=True)
    if not out.exists(): raise RuntimeError(f"route check failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return json.loads(out.read_text())

def apply(session: ipc.Session, entries: list[dict]) -> int:
    from kipy.board_types import Track, Via, BoardLayer
    from kipy.geometry import Vector2
    from kipy.util.units import from_mm
    b = session.board
    nets = {n.name: n for n in b.get_nets()}
    layer_ids = {"F.Cu": BoardLayer.BL_F_Cu, "B.Cu": BoardLayer.BL_B_Cu, "In1.Cu": BoardLayer.BL_In1_Cu, "In2.Cu": BoardLayer.BL_In2_Cu}
    for i in (BoardLayer.BL_In1_Cu, BoardLayer.BL_In2_Cu): layer_ids[b.get_layer_name(i)] = i
    n = 0
    for e in entries:
        net = nets[e["net"]]; items = []
        pts = e.get("pts", [])
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) == (x2, y2): continue
            t = Track(); t.start = Vector2.from_xy(from_mm(x1), from_mm(y1)); t.end = Vector2.from_xy(from_mm(x2), from_mm(y2))
            t.width = from_mm(e.get("width", 0.3)); t.layer = layer_ids[e.get("layer", "B.Cu")]; t.net = net; items.append(t)
        for x, y in e.get("vias", []):
            v = Via(); v.position = Vector2.from_xy(from_mm(x), from_mm(y)); v.diameter = from_mm(e.get("via_d", 0.6)); v.drill_diameter = from_mm(e.get("via_drill", 0.3)); v.net = net; items.append(v)
        if not items: continue
        c = b.begin_commit()
        try:
            b.create_items(items); b.push_commit(c, f"copperloop route {e.get('name', e['net'])}"); n += 1
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
