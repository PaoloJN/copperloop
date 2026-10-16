"""`cl autoroute NET...`: plan with the grid A* router, then run each net through the same
check / commit / gate transaction as `cl route`.

snapshot (IPC) -> route/geom_export.py (KiCad Python, refills a copy with the project rules)
-> route/grid_router.py (venv: numpy/scipy/shapely) -> route spec -> routing.run
"""
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path
from .kicad import ipc
from .fanout import kicad_python, snapshot

LAYER = {0: "F.Cu", 2: "In2.Cu", 3: "B.Cu"}

def plans_to_spec(plans: list[dict]) -> list[dict]:
    spec = []
    for p in plans:
        path = p["path"]; runs = []; vias = []; run = [path[0]]
        for q in path[1:]:
            if q[0] == run[-1][0]: run.append(q)
            else: runs.append((run[0][0], [[x, y] for _, x, y in run])); vias.append([q[1], q[2]]); run = [q]
        runs.append((run[0][0], [[x, y] for _, x, y in run]))
        for i, (l, pts) in enumerate(runs):
            e = {"name": f"{p['net']} part {i + 1}/{len(runs)}", "net": p["net"], "layer": LAYER[l], "width": p["width"], "pts": pts}
            if i < len(vias): e["vias"] = [vias[i]]
            spec.append(e)
    return spec

def run(nets: list[str], apply_changes: bool, router_args: list[str], work: Path | None = None) -> dict:
    from . import routing, gate
    s = ipc.connect()
    work = work or Path(tempfile.mkdtemp(prefix="copperloop-autoroute-"))
    board = snapshot(s, work)
    geom = work / "geom.json"
    r = subprocess.run([kicad_python(), str(Path(__file__).parent / "route" / "geom_export.py"), str(board), str(geom)], capture_output=True, text=True)
    if not geom.exists(): raise RuntimeError(f"geometry export failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    plans = work / "plans.json"
    cmd = [sys.executable, str(Path(__file__).parent / "route" / "grid_router.py"), str(geom), str(plans), "--nets", *nets, *router_args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    (work / "router.log").write_text(log)
    if not plans.exists(): raise RuntimeError(f"router failed:\n{log[-3000:]}")
    spec = plans_to_spec(json.loads(plans.read_text()))
    spec_path = work / "autoroute-spec.json"; spec_path.write_text(json.dumps(spec, indent=1))
    failed = [l.split(':')[0] for l in log.splitlines() if l.startswith('failed:')]
    res = routing.run(spec_path, apply_changes, only_ok=False) if spec else {"results": [], "applied": 0, "after": None, "ok": None}
    res.update({"work": str(work), "spec": str(spec_path), "router_log_tail": log[-2500:], "planned_nets": sorted({e["net"] for e in spec})})
    return res
