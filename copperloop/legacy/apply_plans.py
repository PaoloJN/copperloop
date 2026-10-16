"""Put grid_router.py plans on the board.

KiCad Python: apply_plans.py in.kicad_pcb plans.json out.kicad_pcb [--skip NET ...]

1. strips every track listed in the plans' "remove" fields (textually: the SWIG
   Remove() crashes KiCad 10), 2. adds each plan's tracks and vias through
   routelib's collision check (a plan that collides is reported and skipped),
3. refills the zones and saves. Run DRC on the result.
"""
import sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).parent / 'wiring'))
from sexp import parse, find, atom, serialize
import pcbnew
from routelib import Board, Collision, COPPER, P, mm, tomm

ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('plans'); ap.add_argument('out'); ap.add_argument('--skip', nargs='*', default=[])
a = ap.parse_args()
plans = [p for p in json.load(open(a.plans)) if p['net'] not in a.skip]
LAYER = {0: 'F.Cu', 2: 'PWR', 3: 'B.Cu'}

rm = {x['id'] for p in plans for x in p['remove']}
doc = parse(Path(a.inp).read_text())[0]; n_rm = 0
for item in [i for i in doc if isinstance(i, list) and i and atom(i[0]) in ('segment', 'via', 'arc')]:
    u = find(item, 'uuid')
    if u and atom(u[1]) in rm: doc.remove(item); n_rm += 1
tmp = a.out + '.stripped.kicad_pcb'; Path(tmp).write_text(serialize(doc) + '\n')
print(f'removed {n_rm}/{len(rm)} ripped tracks')

bd = Board(tmp)
def same_net_via_near(x, y, net):
    c = pcbnew.SHAPE_CIRCLE(P(x, y), mm(0.1))
    return any(n == net and l is None and 'via' in lab and sh.Collide(c, 0) for sh, n, l, lab in bd.obst)
ok = fail = 0
for p in plans:
    net, w, path = p['net'], p['width'], p['path']
    try:
        # dry run: check everything first, then add
        segs, vias = [], []
        run = [path[0]]
        for q in path[1:]:
            if q[0] == run[-1][0]: run.append(q)
            else:
                segs.append((run[0][0], [(x, y) for _, x, y in run])); vias.append((q[1], q[2])); run = [q]
        segs.append((run[0][0], [(x, y) for _, x, y in run]))
        for l, pts in segs:
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                if (x1, y1) != (x2, y2): bd.check_seg(x1, y1, x2, y2, w, LAYER[l], net)
        vias = [(x, y) for x, y in vias if not same_net_via_near(x, y, net)]
        for x, y in vias: bd.check_via(x, y, net)
        for l, pts in segs: bd.path(pts, w, LAYER[l], net, check=False)
        for x, y in vias: bd.via(x, y, net, check=False)
        ok += 1; print(f'  {net}: added {sum(len(p) - 1 for _, p in segs)} segments, {len(vias)} vias')
    except Collision as e:
        fail += 1; print(f'  {net}: SKIPPED ({e})')
bd.save(a.out); Path(tmp).unlink()
print(f'applied {ok}, skipped {fail} -> {a.out}')
