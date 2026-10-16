"""Fan out plane nets (3V3 -> PWR/In2, GND -> GND/In1) with one via per pad.

KiCad Python: fanout_planes.py input.kicad_pcb output.kicad_pcb [--nets 3V3] [--gnd-pads U4:7]

For every SMD pad on the given nets that does not already touch a via of
that net, search for a via spot just outside the footprint that clears every
pad, track, via and no-via rule area (KiCad's own shape collision, board
minimum clearance), then add a short stub on the pad's layer plus a through
via. GND pads are only stubbed when listed in --gnd-pads (the pours reach the
rest). Prints every pad it could not place so the author can route it by
hand. Never deletes anything.
"""
import math, sys, argparse, pcbnew

CX, CY = 150.0, 100.0          # board centre (mm)
RIM_R = 21.8                   # keep via centres inside this radius (KO_RIM + edge clearance)
CLR = 0.15                     # board min clearance
VIA_D, VIA_DRILL = 0.6, 0.3
STUB_W = 0.3
COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)

ap = argparse.ArgumentParser()
ap.add_argument('inp'); ap.add_argument('out')
ap.add_argument('--nets', nargs='*', default=['3V3'])
ap.add_argument('--gnd-pads', nargs='*', default=[], help='REF:PAD list of GND pads to stub (e.g. U4:7)')
ap.add_argument('--debug', action='store_true', help='print the first blocking item per candidate')
ap.add_argument('--skip', nargs='*', default=[], help='REF:PAD list to leave for route_manual.py')
ap.add_argument('--only', nargs='*', default=None, help='REF:PAD list; restrict to these pads')
a = ap.parse_args()

b = pcbnew.LoadBoard(a.inp)
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
def P(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))

# ---- obstacle model: (shape, net, layer or None for all-copper) -------------
obst = []
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            obst.append((p.GetEffectiveShape(pcbnew.F_Cu), p.GetNetname(), None, f'{f.GetReference()}.{p.GetNumber()}'))
        else:
            for l in COPPER:
                if p.IsOnLayer(l): obst.append((p.GetEffectiveShape(l), p.GetNetname(), l, f'{f.GetReference()}.{p.GetNumber()}'))
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA': obst.append((t.GetEffectiveShape(pcbnew.F_Cu), t.GetNetname(), None, f'via {t.GetNetname()}'))
    else: obst.append((t.GetEffectiveShape(), t.GetNetname(), t.GetLayer(), f'track {t.GetNetname()}'))
no_via = [z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
no_trk = [(z.Outline(), set(z.GetLayerSet().Seq())) for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]

WHY = []
def via_ok(x, y, net):
    if math.hypot(x - CX, y - CY) > RIM_R: WHY.append('rim'); return False
    c = pcbnew.SHAPE_CIRCLE(P(x, y), mm(VIA_D / 2))
    if any(o.Collide(P(x, y), mm(VIA_D / 2)) for o in no_via): WHY.append('no-via area'); return False
    for sh, n, l, lab in obst:
        if n == net: continue
        if sh.Collide(c, mm(CLR)): WHY.append(lab); return False
    # same-net vias: keep hole-to-hole spacing
    for sh, n, l, lab in obst:
        if n == net and l is None and sh.Collide(c, mm(0.3)): WHY.append('same-net ' + lab); return False
    return True

def stub_ok(x1, y1, x2, y2, net, layer):
    s = pcbnew.SHAPE_SEGMENT(P(x1, y1), P(x2, y2), mm(STUB_W))
    for sh, n, l, lab in obst:
        if n == net or (l is not None and l != layer): continue
        if sh.Collide(s, mm(CLR)): WHY.append('stub:' + lab); return False
    for o, layers in no_trk:
        if layer in layers:
            for px, py in ((x1, y1), (x2, y2), ((x1 + x2) / 2, (y1 + y2) / 2)):
                if o.Collide(P(px, py), mm(STUB_W / 2)): WHY.append('stub:no-track area'); return False
    return True

def add_via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(mm(VIA_DRILL)); v.SetWidth(mm(VIA_D)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net); b.Add(v)
    obst.append((v.GetEffectiveShape(pcbnew.F_Cu), net.GetNetname(), None, 'new via'))

def add_track(x1, y1, x2, y2, layer, net):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(mm(STUB_W))
    t.SetLayer(layer); t.SetNet(net); b.Add(t)
    obst.append((t.GetEffectiveShape(), net.GetNetname(), layer, 'new stub'))

def already_served(p, netname):
    sh = p.GetEffectiveShape(p.GetLayer())
    return any(n == netname and l is None and sh.Collide(o, 0) for o, n, l, lab in obst)

def place_for_pad(f, p, netname):
    net = p.GetNet(); layer = f.GetLayer()
    px, py = tomm(p.GetPosition().x), tomm(p.GetPosition().y)
    if already_served(p, netname): return 'served'
    fx, fy = tomm(f.GetPosition().x), tomm(f.GetPosition().y)
    base = math.atan2(py - fy, px - fx) if math.hypot(px - fx, py - fy) > 0.05 else math.atan2(py - CY, px - CX)
    for dist in (0.75, 0.85, 0.95, 1.05, 1.2, 1.35, 1.5, 1.7, 1.9, 2.1, 2.3, 2.6, 2.9, 3.2, 3.6, 4.0):
        for da in (0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180):
            ang = base + math.radians(da)
            vx, vy = round(px + dist * math.cos(ang), 3), round(py + dist * math.sin(ang), 3)
            del WHY[:]
            if not via_ok(vx, vy, netname):
                if a.debug: print(f'   cand ({vx},{vy}) d={dist} da={da}: {WHY[-1]}')
                continue
            # straight stub, else an L through either corner
            for path in (((px, py), (vx, vy)), ((px, py), (px, vy), (vx, vy)), ((px, py), (vx, py), (vx, vy))):
                if all(stub_ok(x1, y1, x2, y2, netname, layer) for (x1, y1), (x2, y2) in zip(path, path[1:])):
                    for (x1, y1), (x2, y2) in zip(path, path[1:]):
                        if (x1, y1) != (x2, y2): add_track(x1, y1, x2, y2, layer, net)
                    add_via(vx, vy, net)
                    return f'via ({vx},{vy}) d={dist} da={da} {"L" if len(path) == 3 else "straight"}'
            if a.debug: print(f'   cand ({vx},{vy}) d={dist} da={da}: stub blocked ({WHY[-1]})')
    return None

report = []
want = set(a.nets)
gnd_targets = set(tuple(s.split(':')) for s in a.gnd_pads)
only = set(tuple(s.split(':')) for s in a.only) if a.only else None
skip = set(tuple(s.split(':')) for s in a.skip)
for f in b.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname()
        if only is not None and (f.GetReference(), p.GetNumber()) not in only: continue
        if (f.GetReference(), p.GetNumber()) in skip: continue
        if n == 'GND':
            if (f.GetReference(), p.GetNumber()) not in gnd_targets: continue
        elif n not in want: continue
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
        res = place_for_pad(f, p, n)
        report.append((n, f.GetReference(), p.GetNumber(), res))
fail = [r for r in report if r[3] is None]
for r in report: print(f'{r[0]:4s} {r[1]:5s}.{r[2]:3s} -> {r[3]}')
print(f'placed {sum(1 for r in report if r[3] and r[3] != "served")}, served {sum(1 for r in report if r[3] == "served")}, FAILED {len(fail)}: {[(r[1], r[2]) for r in fail]}')
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(a.out, b); print('saved', a.out)
