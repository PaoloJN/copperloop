"""Remove ALL tracks/vias of every non-frozen net that has wiring inside one or more boxes.

python3 strip_nets_region.py in.kicad_pcb out.kicad_pcb x0 y0 x1 y1 [x0 y0 x1 y1 ...] [--keep NET ...]
Whole nets are removed (not just the segments in the box) because Freerouting
cannot complete a net whose remaining wiring is protected.
"""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'wiring'))
from sexp import parse, find, atom, serialize
FROZEN = {'GND', '3V3', 'VBUS', '5V', '/5V_RING', 'SHLD1', '/CIN1', '/CIN2', '/BOOST_SW', 'RING_DATA', 'VSYS'}
ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('out'); ap.add_argument('box', nargs='+', type=float); ap.add_argument('--keep', nargs='*', default=[])
a = ap.parse_args(); keep = FROZEN | set(a.keep); boxes = [a.box[i:i + 4] for i in range(0, len(a.box), 4)]
doc = parse(Path(a.inp).read_text())[0]
def inside(x, y): return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in boxes)
tracks = [i for i in doc if isinstance(i, list) and i and atom(i[0]) in ('segment', 'via', 'arc')]
hit = set()
for item in tracks:
    net = atom(find(item, 'net')[1])
    if net in keep: continue
    pts = [find(item, 'at')[1:3]] if atom(item[0]) == 'via' else [find(item, 'start')[1:3], find(item, 'end')[1:3]]
    if any(inside(float(atom(x)), float(atom(y))) for x, y in pts): hit.add(net)
n = 0
for item in tracks:
    if atom(find(item, 'net')[1]) in hit: doc.remove(item); n += 1
Path(a.out).write_text(serialize(doc) + '\n'); print(f'removed {n} items; nets stripped ({len(hit)}): {sorted(hit)}')
