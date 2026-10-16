"""`cl tidy NET`: remove redundant plane-net copper on the live board (see route/tidy_plan.py).
One undoable IPC commit per cluster, zones refilled, then the gate."""
from __future__ import annotations
import json, subprocess, tempfile
from pathlib import Path
from .kicad import ipc
from .fanout import kicad_python, snapshot

def plan(board: Path, net: str, keep_ref: list[str]) -> dict:
    out = board.parent / "tidy.json"
    cmd = [kicad_python(), str(Path(__file__).parent / "route" / "tidy_plan.py"), str(board), "--json", str(out), "--net", net]
    if keep_ref: cmd += ["--keep-ref", *keep_ref]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not out.exists(): raise RuntimeError(f"tidy planner failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return json.loads(out.read_text())

def apply(session: ipc.Session, clusters: list[dict]) -> tuple[int, int]:
    b = session.board
    by_id = {}
    for t in list(b.get_tracks()) + list(b.get_vias()):
        by_id[str(t.id.value)] = t
    n_items = n_commits = 0
    for c in clusters:
        items = [by_id[u] for u in c["remove"] if u in by_id]
        if not items: continue
        commit = b.begin_commit()
        try:
            b.remove_items(items)
            b.push_commit(commit, f"copperloop tidy {','.join(c['pads'])}")
            n_items += len(items); n_commits += 1
        except Exception:
            b.drop_commit(commit); raise
    return n_items, n_commits

def run(net: str, apply_changes: bool, keep_ref: list[str] | None = None) -> dict:
    from . import gate
    s = ipc.connect()
    work = Path(tempfile.mkdtemp(prefix="copperloop-tidy-"))
    board = snapshot(s, work)
    before = gate.run(board, state_dir=work / "before")
    pl = plan(board, net, keep_ref or [])
    res = {"work": str(work), "clusters": pl["clusters"], "remove_count": pl["remove_count"], "before": before["now"], "applied": 0, "after": None, "ok": None}
    if not apply_changes or not pl["remove_count"]: return res
    res["applied"], res["commits"] = apply(s, pl["clusters"])
    s.board.refill_zones()
    board2 = snapshot(s, work / "after")
    after = gate.run(board2, state_dir=work / "after" / ".copperloop")
    res["after"] = after["now"]
    res["ok"] = after["now"]["errors"] <= before["now"]["errors"] and after["now"]["unconnected"] <= before["now"]["unconnected"] and after["now"]["parity"] == 0
    res["after_open_nets"] = after["open_nets"]
    return res
