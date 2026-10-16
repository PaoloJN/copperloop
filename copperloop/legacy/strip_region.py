"""Remove routed signal tracks and vias inside a box so an autorouter can redo that region.

python3 strip_region.py in.kicad_pcb out.kicad_pcb x0 y0 x1 y1 [--keep NET ...]
Keeps GND/3V3/power/ring/sense nets by default (see FROZEN) plus --keep. Textual, no KiCad needed.
"""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'wiring'))
from sexp import parse, find, atom, serialize
FROZEN = {'GND', '3V3', 'VBUS', '5V', '/5V_RING', 'SHLD1', '/CIN1', '/CIN2', '/BOOST_SW', 'RING_DATA', 'VSYS'}
ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('out'); ap.add_argument('x0', type=float); ap.add_argument('y0', type=float); ap.add_argument('x1', type=float); ap.add_argument('y1', type=float); ap.add_argument('--keep', nargs='*', default=[])
a = ap.parse_args(); keep = FROZEN | set(a.keep)
doc = parse(Path(a.inp).read_text())[0]; n = 0; nets = set()
def inside(x, y): return a.x0 <= x <= a.x1 and a.y0 <= y <= a.y1
for item in [i for i in doc if isinstance(i, list) and i and atom(i[0]) in ('segment', 'via', 'arc')]:
    net = atom(find(item, 'net')[1])
    if net in keep: continue
    if atom(item[0]) == 'via': pts = [find(item, 'at')[1:3]]
    else: pts = [find(item, 'start')[1:3], find(item, 'end')[1:3]]
    if any(inside(float(atom(x)), float(atom(y))) for x, y in pts): doc.remove(item); n += 1; nets.add(net)
Path(a.out).write_text(serialize(doc) + '\n'); print(f'removed {n} items of {len(nets)} nets: {sorted(nets)}')
