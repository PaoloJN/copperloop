"""Plan a plane fan-out (one stub + one through via per pad) without touching the board.

Runs under KiCad's bundled Python (needs the legacy pcbnew module for its shape
collision; KiCad 11 will need the IPC pad polygons instead):

    KICAD_PY fanout_plan.py board.kicad_pcb --nets 3V3 [--gnd-pads REF:PAD ...]
             [--clr 0.2] [--via 0.6 0.3] [--stub 0.3] [--only REF:PAD ...] --json plan.json

Never saves. Output: {"placed": [{ref, pad, net, layer, stubs: [[x1,y1,x2,y2],...], via: [x,y]}],
"served": [...], "failed": [{ref, pad, net}]}. Coordinates in board mm.
"""
import math, sys, argparse, json, pcbnew

ap = argparse.ArgumentParser()
ap.add_argument('board'); ap.add_argument('--json', required=True)
ap.add_argument('--nets', nargs='*', default=['3V3'])
ap.add_argument('--gnd-pads', nargs='*', default=[])
ap.add_argument('--only', nargs='*', default=None)
ap.add_argument('--skip', nargs='*', default=[])
ap.add_argument('--clr', type=float, default=0.2)
ap.add_argument('--via', type=float, nargs=2, default=[0.6, 0.3])
ap.add_argument('--stub', type=float, default=0.3)
ap.add_argument('--rim', type=float, default=0.0, help='keep via centres within this radius of the board centre (0 = use board bbox inset)')
ap.add_argument('--edge', type=float, default=1.2, help='min distance of a via centre from the board bbox edge')
a = ap.parse_args()
VIA_D, VIA_DRILL = a.via; STUB_W = a.stub; CLR = a.clr
b = pcbnew.LoadBoard(a.board)
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
def P(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))
COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
bb = b.GetBoardEdgesBoundingBox(); X0, Y0, X1, Y1 = tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom())
CX, CY = (X0 + X1) / 2, (Y0 + Y1) / 2

obst = []
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            obst.append((p.GetEffectiveShape(pcbnew.F_Cu), p.GetNetname(), None, f'{f.GetReference()}.{p.GetNumber()}'))
        else:
            for l in COPPER:
                if p.IsOnLayer(l): obst.append((p.GetEffectiveShape(l), p.GetNetname(), l, f'{f.GetReference()}.{p.GetNumber()}'))
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA': obst.append((t.GetEffectiveShape(pcbnew.F_Cu), t.GetNetname(), None, f'via {t.GetNetname()}'))
    else: obst.append((t.GetEffectiveShape(), t.GetNetname(), t.GetLayer(), f'track {t.GetNetname()}'))
no_via = [(z.GetZoneName(), z.Outline()) for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
no_trk = [(z.GetZoneName(), z.Outline(), set(z.GetLayerSet().Seq())) for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
planned_vias = []    # (x, y, net)
planned_stubs = []   # (x1, y1, x2, y2, layer, net)

def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0: return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

def seg_seg_dist(a1, a2, b1, b2):
    return min(seg_dist(*a1, *b1, *b2), seg_dist(*a2, *b1, *b2), seg_dist(*b1, *a1, *a2), seg_dist(*b2, *a1, *a2))

def planned_via_ok(x, y, net):
    for vx, vy, n in planned_vias:
        need = (VIA_D if n != net else 0) / 2 + VIA_D / 2 + (CLR if n != net else 0.3)
        if math.hypot(x - vx, y - vy) < need: return False
    for x1, y1, x2, y2, l, n in planned_stubs:
        if n != net and seg_dist(x, y, x1, y1, x2, y2) < VIA_D / 2 + STUB_W / 2 + CLR: return False
    return True

def planned_stub_ok(x1, y1, x2, y2, net, layer):
    for vx, vy, n in planned_vias:
        if n != net and seg_dist(vx, vy, x1, y1, x2, y2) < VIA_D / 2 + STUB_W / 2 + CLR: return False
    for sx1, sy1, sx2, sy2, l, n in planned_stubs:
        if n != net and l == layer and seg_seg_dist((x1, y1), (x2, y2), (sx1, sy1), (sx2, sy2)) < STUB_W + CLR: return False
    return True

def via_ok(x, y, net):
    if a.rim and math.hypot(x - CX, y - CY) > a.rim: return False
    if not (X0 + a.edge < x < X1 - a.edge and Y0 + a.edge < y < Y1 - a.edge): return False
    c = pcbnew.SHAPE_CIRCLE(P(x, y), mm(VIA_D / 2))
    if any(o.Collide(P(x, y), mm(VIA_D / 2)) for _, o in no_via): return False
    for sh, n, l, lab in obst:
        if n == net:
            if l is None and 'via' in lab and sh.Collide(c, mm(0.3)): return False
            continue
        if sh.Collide(c, mm(CLR)): return False
    return planned_via_ok(x, y, net)

def stub_ok(x1, y1, x2, y2, net, layer):
    s = pcbnew.SHAPE_SEGMENT(P(x1, y1), P(x2, y2), mm(STUB_W))
    for sh, n, l, lab in obst:
        if n == net or (l is not None and l != layer): continue
        if sh.Collide(s, mm(CLR)): return False
    for _, o, layers in no_trk:
        if layer in layers:
            for px, py in ((x1, y1), (x2, y2), ((x1 + x2) / 2, (y1 + y2) / 2)):
                if o.Collide(P(px, py), mm(STUB_W / 2)): return False
    return planned_stub_ok(x1, y1, x2, y2, net, layer)

def served(p, netname):
    """A pad is served when a same-net via or track already touches it.
    Note: PAD.GetLayer() reports F.Cu even for pads of a B.Cu footprint; use the footprint's layer."""
    layer = p.GetParent().GetLayer()
    sh = p.GetEffectiveShape(layer)
    for o, n, l, lab in obst:
        if n != netname or not (lab.startswith('via') or lab.startswith('track')): continue
        if l is not None and l != layer: continue
        if sh.Collide(o, 0): return True
    return False

LAYER_NAME = {pcbnew.F_Cu: 'F.Cu', pcbnew.B_Cu: 'B.Cu'}
def plan_pad(f, p, netname):
    layer = f.GetLayer(); px, py = tomm(p.GetPosition().x), tomm(p.GetPosition().y)
    fx, fy = tomm(f.GetPosition().x), tomm(f.GetPosition().y)
    base = math.atan2(py - fy, px - fx) if math.hypot(px - fx, py - fy) > 0.05 else math.atan2(py - CY, px - CX)
    for dist in (0.75, 0.85, 0.95, 1.05, 1.2, 1.35, 1.5, 1.7, 1.9, 2.1, 2.3, 2.6, 2.9, 3.2, 3.6, 4.0):
        for da in (0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180):
            ang = base + math.radians(da)
            vx, vy = round(px + dist * math.cos(ang), 3), round(py + dist * math.sin(ang), 3)
            if not via_ok(vx, vy, netname): continue
            for path in (((px, py), (vx, vy)), ((px, py), (px, vy), (vx, vy)), ((px, py), (vx, py), (vx, vy))):
                segs = [(x1, y1, x2, y2) for (x1, y1), (x2, y2) in zip(path, path[1:]) if (x1, y1) != (x2, y2)]
                if all(stub_ok(*s, netname, layer) for s in segs):
                    # register as obstacles so later pads avoid them
                    for s in segs: planned_stubs.append((*s, layer, netname))
                    planned_vias.append((vx, vy, netname))
                    return {'ref': f.GetReference(), 'pad': p.GetNumber(), 'net': netname, 'layer': LAYER_NAME[layer],
                            'stubs': [[round(v, 4) for v in s] for s in segs], 'via': [vx, vy], 'via_d': VIA_D, 'via_drill': VIA_DRILL, 'stub_w': STUB_W}
    return None

want = set(a.nets); gnd_targets = {tuple(s.split(':')) for s in a.gnd_pads}
only = {tuple(s.split(':')) for s in a.only} if a.only else None; skip = {tuple(s.split(':')) for s in a.skip}
out = {'placed': [], 'served': [], 'failed': []}
for f in b.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname(); key = (f.GetReference(), p.GetNumber())
        if only is not None and key not in only: continue
        if key in skip or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
        if n == 'GND' and key not in gnd_targets: continue
        if n != 'GND' and n not in want: continue
        if served(p, n): out['served'].append({'ref': key[0], 'pad': key[1], 'net': n}); continue
        r = plan_pad(f, p, n)
        (out['placed'] if r else out['failed']).append(r or {'ref': key[0], 'pad': key[1], 'net': n})
json.dump(out, open(a.json, 'w'), indent=1)
print(f"placed {len(out['placed'])}, served {len(out['served'])}, failed {len(out['failed'])}: {[(x['ref'], x['pad']) for x in out['failed']]}")
