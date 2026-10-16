"""Check a route spec against the board with KiCad's own shape collision. Never saves.

KICAD_PY route_check.py board.kicad_pcb spec.json --json result.json [--project board.kicad_pro]

spec.json: [{"name": "3V3 trunk", "net": "3V3", "layer": "B.Cu", "width": 0.3,
             "pts": [[x, y], ...], "vias": [[x, y], ...], "via_d": 0.6, "via_drill": 0.3}, ...]
Clearance per pair of nets = max of the two net-class clearances from the project file
(board minimum if no project). Each entry is checked in order and, if clean, added to the
obstacle model so later entries see it. Result: per entry {"ok": bool, "problems": [str]}.
"""
import sys, json, math, argparse, pcbnew
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('board'); ap.add_argument('spec'); ap.add_argument('--json', required=True)
ap.add_argument('--project', default=None)
a = ap.parse_args()
b = pcbnew.LoadBoard(a.board)
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
def P(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))
LAYERS = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu, 'In1.Cu': pcbnew.In1_Cu, 'In2.Cu': pcbnew.In2_Cu}
for lid in (pcbnew.In1_Cu, pcbnew.In2_Cu): LAYERS[b.GetLayerName(lid)] = lid   # user names like GND / PWR
COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)

# --- clearances from the project net classes
min_clr = tomm(b.GetDesignSettings().m_MinClearance)
class_clr, net_class = {}, {}
proj = a.project or str(Path(a.board).with_suffix('.kicad_pro'))
if Path(proj).exists():
    pj = json.load(open(proj))
    for c in pj.get('net_settings', {}).get('classes', []):
        class_clr[c['name']] = c.get('clearance', min_clr)
    for asg in pj.get('net_settings', {}).get('netclass_assignments', []) if isinstance(pj.get('net_settings', {}).get('netclass_assignments'), list) else []:
        pass
    # KiCad 9/10: net -> class via netclass_patterns or per-net assignments
    for pat in pj.get('net_settings', {}).get('netclass_patterns', []):
        net_class[pat['pattern']] = pat['netclass']
    for net, cls in (pj.get('net_settings', {}).get('netclass_assignments') or {}).items() if isinstance(pj.get('net_settings', {}).get('netclass_assignments'), dict) else []:
        net_class[net] = cls[0] if isinstance(cls, list) else cls
import fnmatch
def clr_of(net):
    for pat, cls in net_class.items():
        if fnmatch.fnmatch(net, pat): return class_clr.get(cls, min_clr)
    return class_clr.get('Default', min_clr)
def clr(n1, n2): return max(clr_of(n1), clr_of(n2), min_clr)

# --- obstacle model
obst = []
for f in b.GetFootprints():
    for p in f.Pads():
        lab = f'{f.GetReference()}.{p.GetNumber()}[{p.GetNetname()}]'
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            obst.append((p.GetEffectiveShape(pcbnew.F_Cu), p.GetNetname(), None, lab))
        else:
            for l in COPPER:
                if p.IsOnLayer(l): obst.append((p.GetEffectiveShape(l), p.GetNetname(), l, lab))
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA': obst.append((t.GetEffectiveShape(pcbnew.F_Cu), t.GetNetname(), None, f'via[{t.GetNetname()}]@{tomm(t.GetPosition().x):.2f},{tomm(t.GetPosition().y):.2f}'))
    else: obst.append((t.GetEffectiveShape(), t.GetNetname(), t.GetLayer(), f'track[{t.GetNetname()}]@{b.GetLayerName(t.GetLayer())}'))
no_via = [(z.GetZoneName(), z.Outline()) for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
no_trk = [(z.GetZoneName(), z.Outline(), set(z.GetLayerSet().Seq())) for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
bb = b.GetBoardEdgesBoundingBox(); X0, Y0, X1, Y1 = tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom())
edge_clr = tomm(b.GetDesignSettings().m_CopperEdgeClearance)
# round boards: approximate the edge as the inscribed circle when the bbox is square-ish
CX, CY, R = (X0 + X1) / 2, (Y0 + Y1) / 2, min(X1 - X0, Y1 - Y0) / 2

def check_via(x, y, net, d):
    probs = []
    if math.hypot(x - CX, y - CY) + d / 2 + edge_clr > R: probs.append(f'via ({x},{y}) too close to the board edge')
    for name, o in no_via:
        if o.Collide(P(x, y), mm(d / 2)): probs.append(f'via ({x},{y}) inside no-via area {name}')
    c = pcbnew.SHAPE_CIRCLE(P(x, y), mm(d / 2))
    for sh, n, l, lab in obst:
        if n == net:
            if l is None and lab.startswith('via') and sh.Collide(c, mm(0.25)): probs.append(f'via ({x},{y}) overlaps same-net {lab}')
            continue
        if sh.Collide(c, mm(clr(net, n))): probs.append(f'via ({x},{y}) hits {lab} (need {clr(net, n)} mm)')
    return probs

def check_seg(x1, y1, x2, y2, w, layer, net):
    probs = []; lid = LAYERS[layer]
    s = pcbnew.SHAPE_SEGMENT(P(x1, y1), P(x2, y2), mm(w))
    for sh, n, l, lab in obst:
        if n == net or (l is not None and l != lid): continue
        if sh.Collide(s, mm(clr(net, n))): probs.append(f'seg ({x1},{y1})-({x2},{y2}) {layer} hits {lab} (need {clr(net, n)} mm)')
    for name, o, layers in no_trk:
        if lid in layers:
            for t in (0, 0.25, 0.5, 0.75, 1):
                if o.Collide(P(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t), mm(w / 2)): probs.append(f'seg ({x1},{y1})-({x2},{y2}) inside no-track area {name} on {layer}'); break
    for px, py in ((x1, y1), (x2, y2)):
        if math.hypot(px - CX, py - CY) + w / 2 + edge_clr > R: probs.append(f'seg end ({px},{py}) too close to the board edge')
    return probs

spec = json.load(open(a.spec)); results = []
for e in spec:
    net, layer, w = e['net'], e.get('layer', 'B.Cu'), e.get('width', 0.3)
    vd, vdr = e.get('via_d', 0.6), e.get('via_drill', 0.3)
    probs = []
    pts = e.get('pts', [])
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if (x1, y1) != (x2, y2): probs += check_seg(x1, y1, x2, y2, w, layer, net)
    for x, y in e.get('vias', []): probs += check_via(x, y, net, vd)
    ok = not probs
    if ok:  # add to the model so later entries respect it
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) != (x2, y2): obst.append((pcbnew.SHAPE_SEGMENT(P(x1, y1), P(x2, y2), mm(w)), net, LAYERS[layer], f'planned track[{net}]'))
        for x, y in e.get('vias', []): obst.append((pcbnew.SHAPE_CIRCLE(P(x, y), mm(vd / 2)), net, None, f'via[{net}] planned'))
    results.append({'name': e.get('name', net), 'ok': ok, 'problems': sorted(set(probs))})
json.dump(results, open(a.json, 'w'), indent=1)
for r in results: print(('OK   ' if r['ok'] else 'FAIL ') + r['name'] + ('' if r['ok'] else '\n    ' + '\n    '.join(r['problems'][:8])))
