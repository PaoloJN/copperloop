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

KEEP = []   # planned PCB items kept alive; their GetEffectiveShape() supports Collide(SHAPE) unlike bare SHAPE_CIRCLE/SEGMENT
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

def arc_points(sx, sy, mx, my, ex, ey, n=24):
    """Sample points along the circular arc through start, mid, end (board mm)."""
    ax, ay, bx, by, cx_, cy_ = sx, sy, mx, my, ex, ey
    d = 2 * (ax * (by - cy_) + bx * (cy_ - ay) + cx_ * (ay - by))
    if abs(d) < 1e-9: return [(sx, sy), (mx, my), (ex, ey)]
    ux = ((ax * ax + ay * ay) * (by - cy_) + (bx * bx + by * by) * (cy_ - ay) + (cx_ * cx_ + cy_ * cy_) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx_ - bx) + (bx * bx + by * by) * (ax - cx_) + (cx_ * cx_ + cy_ * cy_) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, am, a1 = (math.atan2(y - uy, x - ux) for x, y in ((sx, sy), (mx, my), (ex, ey)))
    # choose the sweep direction that passes through the mid point
    def norm(t): return (t + 2 * math.pi) % (2 * math.pi)
    ccw = norm(am - a0) < norm(a1 - a0)
    sweep = norm(a1 - a0) if ccw else -norm(a0 - a1)
    return [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]

def check_arc(sx, sy, mx, my, ex, ey, w, layer, net):
    probs = []; lid = LAYERS[layer]
    t = pcbnew.PCB_ARC(b); t.SetStart(P(sx, sy)); t.SetMid(P(mx, my)); t.SetEnd(P(ex, ey)); t.SetWidth(mm(w)); t.SetLayer(lid); KEEP.append(t)
    arc = t.GetEffectiveShape()
    for sh, n, l, lab in obst:
        if n == net or (l is not None and l != lid): continue
        if sh.Collide(arc, mm(clr(net, n))): probs.append(f'arc ({sx},{sy})~({ex},{ey}) {layer} hits {lab} (need {clr(net, n)} mm)')
    pts_ = arc_points(sx, sy, mx, my, ex, ey)
    for name, o, layers in no_trk:
        if lid in layers and any(o.Collide(P(px, py), mm(w / 2)) for px, py in pts_): probs.append(f'arc ({sx},{sy})~({ex},{ey}) inside no-track area {name} on {layer}')
    for px, py in pts_:
        if math.hypot(px - CX, py - CY) + w / 2 + edge_clr > R: probs.append(f'arc ({sx},{sy})~({ex},{ey}) too close to the board edge'); break
    return probs, arc

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

def near(ax, ay, bx, by, tol=0.05): return abs(ax - bx) <= tol and abs(ay - by) <= tol
def drop_items(e):
    """Remove the listed same-net vias/tracks from the obstacle model; return (found, missing)."""
    found, missing = [], []
    for x, y in e.get('remove_vias', []):
        hit = [i for i, (sh, n, l, lab) in enumerate(obst) if l is None and lab.startswith('via') and '@' in lab and n == e['net'] and near(x, y, *map(float, lab.split('@')[1].split(',')))]
        (found if hit else missing).append(f'via ({x},{y})')
        for i in sorted(hit, reverse=True): del obst[i]
    for x1, y1, x2, y2 in e.get('remove_tracks', []):
        hit = []
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA' or t.GetNetname() != e['net']: continue
            sx, sy, ex, ey = tomm(t.GetStart().x), tomm(t.GetStart().y), tomm(t.GetEnd().x), tomm(t.GetEnd().y)
            if (near(x1, y1, sx, sy) and near(x2, y2, ex, ey)) or (near(x1, y1, ex, ey) and near(x2, y2, sx, sy)): hit.append(t)
        (found if hit else missing).append(f'track ({x1},{y1})-({x2},{y2})')
        for t in hit:
            key = f'track[{t.GetNetname()}]@{b.GetLayerName(t.GetLayer())}'
            for i, (sh, n, l, lab) in enumerate(obst):
                if lab == key and l == t.GetLayer() and sh.Collide(t.GetEffectiveShape(), 0) and sh.BBox() == t.GetEffectiveShape().BBox(): del obst[i]; break
    return found, missing

def planned_track(x1, y1, x2, y2, w, lid):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(mm(w)); t.SetLayer(lid); KEEP.append(t); return t.GetEffectiveShape()
def planned_via(x, y, d):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(mm(d)); v.SetDrill(mm(d / 2)); v.SetViaType(pcbnew.VIATYPE_THROUGH); KEEP.append(v); return v.GetEffectiveShape(pcbnew.F_Cu)
def planned_arc(sx, sy, mx, my, ex, ey, w, lid):
    t = pcbnew.PCB_ARC(b); t.SetStart(P(sx, sy)); t.SetMid(P(mx, my)); t.SetEnd(P(ex, ey)); t.SetWidth(mm(w)); t.SetLayer(lid); KEEP.append(t); return t.GetEffectiveShape()

spec = json.load(open(a.spec)); results = []
for e in spec:
    net, layer, w = e['net'], e.get('layer', 'B.Cu'), e.get('width', 0.3)
    vd, vdr = e.get('via_d', 0.6), e.get('via_drill', 0.3)
    probs = []
    found, missing = drop_items(e)
    probs += [f'nothing to remove at {m}' for m in missing]
    pts = e.get('pts', [])
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if (x1, y1) != (x2, y2): probs += check_seg(x1, y1, x2, y2, w, layer, net)
    arcs = []
    for sx, sy, mx, my, ex, ey in e.get('arcs', []):
        pr, arc = check_arc(sx, sy, mx, my, ex, ey, w, layer, net); probs += pr; arcs.append(arc)
    for x, y in e.get('vias', []): probs += check_via(x, y, net, vd)
    ok = not probs
    if ok:  # add to the model so later entries respect it
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) != (x2, y2): obst.append((planned_track(x1, y1, x2, y2, w, LAYERS[layer]), net, LAYERS[layer], f'planned track[{net}]'))
        for x, y in e.get('vias', []): obst.append((planned_via(x, y, vd), net, None, f'via[{net}] planned'))
        for sx, sy, mx, my, ex, ey in e.get('arcs', []): obst.append((planned_arc(sx, sy, mx, my, ex, ey, w, LAYERS[layer]), net, LAYERS[layer], f'planned arc[{net}]'))
    results.append({'name': e.get('name', net), 'ok': ok, 'problems': sorted(set(probs))})
json.dump(results, open(a.json, 'w'), indent=1)
for r in results: print(('OK   ' if r['ok'] else 'FAIL ') + r['name'] + ('' if r['ok'] else '\n    ' + '\n    '.join(r['problems'][:8])))
