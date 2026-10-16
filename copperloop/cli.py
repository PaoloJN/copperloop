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
@click.argument("board", type=click.Path(exists=True, path_type=Path))
@click.option("--no-parity", is_flag=True, help="skip schematic parity (needs the .kicad_sch beside the board)")
@click.option("--json", "as_json", is_flag=True)
def gate(board: Path, no_parity: bool, as_json: bool):
    """Run kicad-cli DRC + schematic parity; PASS only if nothing got worse since the last run."""
    from . import gate as g
    r = g.run(board, parity=not no_parity)
    click.echo(json.dumps(r, indent=1) if as_json else g.format_result(r))
    sys.exit(0 if r["ok"] else 1)

@main.command()
@click.argument("board", type=click.Path(exists=True, path_type=Path))
@click.argument("x", type=float)
@click.argument("y", type=float)
@click.argument("w", type=float)
@click.argument("h", type=float)
@click.option("--layers", "-l", default="F.Cu,B.Cu", help="comma-separated KiCad layer names")
@click.option("--scale", default=40.0, help="pixels per mm")
@click.option("--mirror-bottom", is_flag=True, help="mirror B.* layers as seen from the back")
@click.option("--out", type=click.Path(path_type=Path), default=None)
def see(board: Path, x: float, y: float, w: float, h: float, layers: str, scale: float, mirror_bottom: bool, out: Path | None):
    """Render a window of the board (board mm: X Y W H) per layer to PNG."""
    from .render import see as _see
    for p in _see(board, x, y, w, h, layers.split(","), out, scale, mirror_bottom):
        click.echo(p)

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
