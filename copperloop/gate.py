"""The gate: kicad-cli DRC + schematic parity, summarised, diffed against the last run.

A change is acceptable only if errors, unconnected and parity counts did not grow.
State lives in <board dir>/.copperloop/gate-last.json (gitignored by the user if they like).
"""
from __future__ import annotations
import json, time
from pathlib import Path
from .kicad import cli

KEYS = ("errors", "warnings", "unconnected", "parity")

def summarise(report: dict) -> dict:
    v = [x for x in report.get("violations", []) if not x.get("excluded")]
    return {
        "errors": sum(1 for x in v if x.get("severity") == "error"),
        "warnings": sum(1 for x in v if x.get("severity") == "warning"),
        "unconnected": len(report.get("unconnected_items", [])),
        "parity": len(real_parity(report)),
    }

def real_parity(report: dict) -> list:
    """Parity items minus KiCad's own 'unconnected-(REF-PIN-PadN)' auto-nets: the GUI's Update PCB names
    no-connect pads that way and kicad-cli then reports 'no corresponding pin' for each. Noise, not a mismatch."""
    return [x for x in report.get("schematic_parity", []) if not any("[unconnected-(" in i.get("description", "") for i in x.get("items", []))]

def by_type(report: dict) -> dict:
    out: dict = {}
    for x in report.get("violations", []):
        if x.get("excluded"): continue
        out[x["type"]] = out.get(x["type"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))

def open_nets(report: dict) -> dict:
    """Unconnected count per net, parsed from item descriptions like 'Pad 3 [GND] of C1'."""
    import re
    out: dict = {}
    for x in report.get("unconnected_items", []):
        net = None
        for it in x.get("items", []):
            m = re.search(r"\[([^\]]+)\]", it.get("description", ""))
            if m: net = m.group(1); break
        out[net or "?"] = out.get(net or "?", 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))

def run(board: Path, state_dir: Path | None = None, parity: bool = True) -> dict:
    board = Path(board).resolve()
    state_dir = state_dir or board.parent / ".copperloop"
    state_dir.mkdir(exist_ok=True)
    out = state_dir / "drc.json"
    report = cli.drc(board, out, parity=parity)
    now = summarise(report)
    last_file = state_dir / "gate-last.json"
    last = json.loads(last_file.read_text()) if last_file.exists() else None
    delta = {k: now[k] - last[k] for k in KEYS} if last else None
    ok = now["errors"] == 0 and now["parity"] == 0 and (delta is None or all(delta[k] <= 0 for k in ("errors", "unconnected", "parity")))
    last_file.write_text(json.dumps({**now, "time": time.time()}))
    return {"ok": ok, "now": now, "delta": delta, "types": by_type(report), "open_nets": open_nets(report), "report": str(out)}

def format_result(r: dict) -> str:
    n, d = r["now"], r["delta"]
    def cell(k):
        s = str(n[k])
        if d and d[k]: s += f" ({d[k]:+d})"
        return s
    line = f"{'PASS' if r['ok'] else 'FAIL'}  errors {cell('errors')}  warnings {cell('warnings')}  unconnected {cell('unconnected')}  parity {cell('parity')}"
    extra = []
    if r["types"]: extra.append("  violations: " + ", ".join(f"{k} {v}" for k, v in list(r["types"].items())[:8]))
    if r["open_nets"]: extra.append("  open nets: " + ", ".join(f"{k} {v}" for k, v in list(r["open_nets"].items())[:12]))
    return "\n".join([line, *extra])
