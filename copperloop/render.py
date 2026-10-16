"""`see`: render a region of the board, per layer, to PNG so an agent can look at it.

kicad-cli exports the board as SVG in page coordinates (mm). We crop by editing
the viewBox to the requested window and rasterise with cairosvg.
"""
from __future__ import annotations
import re
from pathlib import Path
from .kicad import cli

DEFAULT_LAYERS = ["F.Cu", "B.Cu"]
ALWAYS = ["Edge.Cuts"]

def _crop_svg(svg: Path, x: float, y: float, w: float, h: float, px_per_mm: float) -> str:
    txt = svg.read_text()
    txt = re.sub(r'width="[^"]*" height="[^"]*" viewBox="[^"]*"',
                 f'width="{w*px_per_mm:.0f}" height="{h*px_per_mm:.0f}" viewBox="{x:.4f} {y:.4f} {w:.4f} {h:.4f}"', txt, count=1)
    return txt

def see(board: Path, x: float, y: float, w: float, h: float, layers: list[str] | None = None,
        out_dir: Path | None = None, px_per_mm: float = 40.0, mirror_bottom: bool = False) -> list[Path]:
    """Render window (x, y, w, h) in board mm for each layer. Returns PNG paths."""
    import cairosvg
    board = Path(board).resolve()
    out_dir = Path(out_dir or board.parent / ".copperloop" / "see"); out_dir.mkdir(parents=True, exist_ok=True)
    pngs = []
    for layer in layers or DEFAULT_LAYERS:
        svg = out_dir / f"{layer}.svg"
        mirror = mirror_bottom and layer.startswith("B.")
        cli.export_svg(board, [layer, *ALWAYS], svg, mirror=mirror, page_mode=1)
        cropped = _crop_svg(svg, x, y, w, h, px_per_mm)
        png = out_dir / f"{layer}_{x:g}_{y:g}_{w:g}x{h:g}.png"
        cairosvg.svg2png(bytestring=cropped.encode(), write_to=str(png), background_color="white")
        pngs.append(png)
    return pngs
