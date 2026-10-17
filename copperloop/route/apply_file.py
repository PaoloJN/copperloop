"""Apply a route spec to a board FILE (KiCad closed). Mirror of routing.apply() for the live board.

KICAD_PY apply_file.py in.kicad_pcb spec.json out.kicad_pcb [--only-ok check.json]

Removals are done textually (deleting tracks through SWIG crashes KiCad 10); additions through pcbnew.
Zones are refilled before saving. The project file beside OUT is NOT touched by us, but pcbnew.SaveBoard
overwrites a .kicad_pro beside the board with defaults: callers must save to a scratch directory or
re-copy the real project file afterwards.
"""
import sys, json, argparse, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'kicad'))
from sexp import parse, find, atom, serialize
import pcbnew

ap = argparse.ArgumentParser()
ap.add_argument('inp'); ap.add_argument('spec'); ap.add_argument('out')
ap.add_argument('--only-ok', help='route_check result json: apply only entries marked ok')
a = ap.parse_args()
spec = json.load(open(a.spec))
if a.only_ok:
    res = json.load(open(a.only_ok)); spec = [e for e, r in zip(spec, res) if r['ok']]
mm = pcbnew.FromMM
def near(ax, ay, bx, by, tol=0.05): return abs(ax - bx) <= tol and abs(ay - by) <= tol

# --- textual removals
doc = parse(Path(a.inp).read_text())[0]
def xy(node, key):
    n = find(node, key); return float(atom(n[1])), float(atom(n[2]))
removed = 0
for e in spec:
    net = e['net']
    for item in [i for i in doc if isinstance(i, list) and i and atom(i[0]) in ('segment', 'via', 'arc')]:
        n = find(item, 'net')
        if not n or atom(n[1]) != net: continue
        kind = atom(item[0])
        hit = False
        if kind == 'via':
            x, y = xy(item, 'at'); hit = any(near(x, y, vx, vy) for vx, vy in e.get('remove_vias', []))
        else:
            sx, sy = xy(item, 'start'); ex, ey = xy(item, 'end')
            hit = any((near(sx, sy, x1, y1) and near(ex, ey, x2, y2)) or (near(sx, sy, x2, y2) and near(ex, ey, x1, y1)) for x1, y1, x2, y2 in e.get('remove_tracks', []))
        if hit: doc.remove(item); removed += 1
tmp = a.out + '.stripped.kicad_pcb'; Path(tmp).write_text(serialize(doc) + '\n')

# --- additions
b = pcbnew.LoadBoard(tmp)
LAYERS = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu, 'In1.Cu': pcbnew.In1_Cu, 'In2.Cu': pcbnew.In2_Cu}
for lid in (pcbnew.In1_Cu, pcbnew.In2_Cu): LAYERS[b.GetLayerName(lid)] = lid
def P(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))
added = 0
for e in spec:
    net = b.FindNet(e['net']); assert net, e['net']
    lid = LAYERS[e.get('layer', 'B.Cu')]; w = e.get('width', 0.2)
    pts = e.get('pts', [])
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if (x1, y1) == (x2, y2): continue
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(mm(w)); t.SetLayer(lid); t.SetNet(net); b.Add(t); added += 1
    for sx, sy, mx, my, ex, ey in e.get('arcs', []):
        t = pcbnew.PCB_ARC(b); t.SetStart(P(sx, sy)); t.SetMid(P(mx, my)); t.SetEnd(P(ex, ey)); t.SetWidth(mm(w)); t.SetLayer(lid); t.SetNet(net); b.Add(t); added += 1
    for x, y in e.get('vias', []):
        v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(mm(e.get('via_d', 0.6))); v.SetDrill(mm(e.get('via_drill', 0.3))); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net); b.Add(v); added += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(a.out, b); Path(tmp).unlink()
print(f'applied {len(spec)} entries: removed {removed} items, added {added}; saved {a.out}')
