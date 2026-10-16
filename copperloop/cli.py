"""cl: the CopperLoop command line."""
from __future__ import annotations
import json, sys
from pathlib import Path
import click

@click.group()
def main():
    """CopperLoop: agent-driven PCB design on KiCad 10."""

@main.command()
def connect():
    """Reach the board open in the KiCad PCB editor over IPC and print a summary."""
    from .kicad import ipc
    try:
        s = ipc.connect()
    except ConnectionError as e:
        click.echo(str(e), err=True); sys.exit(2)
    for k, v in ipc.summary(s).items():
        click.echo(f"{k:14s} {v}")

@main.command()
@click.argument("board", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--live", is_flag=True, help="snapshot the board open in the KiCad editor over IPC instead of reading a file")
@click.option("--no-parity", is_flag=True, help="skip schematic parity (needs the .kicad_sch beside the board)")
@click.option("--json", "as_json", is_flag=True)
def gate(board: Path | None, live: bool, no_parity: bool, as_json: bool):
    """Run kicad-cli DRC + schematic parity; PASS only if nothing got worse since the last run."""
    from . import gate as g
    state = None
    if live or board is None:
        from .kicad import ipc
        from .fanout import snapshot
        import tempfile
        try:
            s = ipc.connect()
        except ConnectionError as e:
            click.echo(str(e), err=True); sys.exit(2)
        work = Path(tempfile.mkdtemp(prefix="copperloop-gate-"))
        board = snapshot(s, work)
        state = Path(s.board.document.project.path) / ".copperloop"
    r = g.run(board, state_dir=state, parity=not no_parity)
    click.echo(json.dumps(r, indent=1) if as_json else g.format_result(r))
    sys.exit(0 if r["ok"] else 1)

@main.command()
@click.option("--board", "-b", type=click.Path(exists=True, path_type=Path), default=None, help="board file; default: the board open in the KiCad editor (IPC snapshot)")
@click.argument("x", type=float)
@click.argument("y", type=float)
@click.argument("w", type=float)
@click.argument("h", type=float)
@click.option("--layers", "-l", default="F.Cu,B.Cu", help="comma-separated KiCad layer names")
@click.option("--scale", default=40.0, help="pixels per mm")
@click.option("--mirror-bottom", is_flag=True, help="mirror B.* layers as seen from the back")
@click.option("--out", type=click.Path(path_type=Path), default=None)
def see(board: Path | None, x: float, y: float, w: float, h: float, layers: str, scale: float, mirror_bottom: bool, out: Path | None):
    """Render a window of the board (board mm: X Y W H) per layer to PNG. Live board unless --board."""
    from .render import see as _see
    if board is None:
        from .kicad import ipc
        from .fanout import snapshot
        import tempfile
        try:
            s = ipc.connect()
        except ConnectionError as e:
            click.echo(str(e), err=True); sys.exit(2)
        board = snapshot(s, Path(tempfile.mkdtemp(prefix="copperloop-see-")))
        out = out or Path(s.board.document.project.path) / ".copperloop" / "see"
    for p in _see(board, x, y, w, h, layers.split(","), out, scale, mirror_bottom):
        click.echo(p)

@main.command()
@click.argument("nets", nargs=-1, required=True)
@click.option("--apply", "apply_changes", is_flag=True, help="actually create the stubs and vias (default: plan only)")
@click.option("--clr", default=0.2, help="clearance used for planning, mm")
@click.option("--via", nargs=2, type=float, default=(0.6, 0.3), help="via diameter and drill, mm")
@click.option("--stub", default=0.3, help="stub width, mm")
@click.option("--only", multiple=True, help="REF:PAD, restrict to these pads")
@click.option("--gnd-pads", multiple=True, help="REF:PAD GND pads to stub (GND is skipped otherwise)")
def fanout(nets, apply_changes, clr, via, stub, only, gnd_pads):
    """Plane fan-out on the LIVE board: one stub + via per pad of NETS, one undoable commit per pad."""
    from . import fanout as f
    try:
        r = f.run(list(nets), apply_changes, clr, tuple(via), stub, list(only) or None, list(gnd_pads))
    except ConnectionError as e:
        click.echo(str(e), err=True); sys.exit(2)
    click.echo(f"plan: {r['placed']} to place, {r['served']} already served, failed {r['failed']}")
    click.echo(f"before: {r['before']}")
    if r["after"] is None:
        click.echo("plan only; add --apply to create them in the editor (Ctrl+Z undoes one pad at a time)")
        return
    click.echo(f"applied {r['applied']} pads")
    click.echo(f"after:  {r['after']}  -> {'PASS' if r['ok'] else 'FAIL'}")
    if r.get("after_open_nets"): click.echo("open nets: " + ", ".join(f"{k} {v}" for k, v in list(r["after_open_nets"].items())[:12]))
    sys.exit(0 if r["ok"] else 1)

@main.command()
def version():
    """kicad-cli and kipy versions."""
    from .kicad import cli as kc
    click.echo(f"kicad-cli {kc.version()} at {kc.kicad_cli()}")
    try:
        import kipy; click.echo(f"kipy {getattr(kipy, '__version__', 'installed')}")
    except ImportError:
        click.echo("kipy not installed")

if __name__ == "__main__":
    main()
