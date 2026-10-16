"""Helpers for scripted hand-routing with collision checks (KiCad 10 Python).

    from routelib import Board
    bd = Board('in.kicad_pcb')
    bd.path([(x, y), ...], w=0.2, layer='B.Cu', net='SDA')   # checks, then adds
    bd.via(x, y, 'SDA')
    bd.save('out.kicad_pcb')

Every add is checked against pads, tracks, vias and rule areas with the
board's own shape collision at the 0.15 mm minimum clearance (0.2 for the
EC net class, matching the project rules). A collision raises with the name
of the blocking item instead of silently producing a DRC error.
"""
import math, pcbnew

CX, CY = 150.0, 100.0
COPPER = {'F.Cu': pcbnew.F_Cu, 'GND': pcbnew.In1_Cu, 'In1.Cu': pcbnew.In1_Cu, 'PWR': pcbnew.In2_Cu, 'In2.Cu': pcbnew.In2_Cu, 'B.Cu': pcbnew.B_Cu}
EC_NETS = {'EC_A', 'EC_B', 'EC_SENSE_A', 'EC_SENSE_B', 'EC_BIAS', 'EC_BIAS_EN', 'EC_DRV_HI', 'EC_DRV_LO', '/EC_NODE_D', 'EXP_A4', 'EXP_A5'}
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
def P(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))

class Collision(Exception): pass

class Board:
    def __init__(self, path):
        self.b = pcbnew.LoadBoard(path)
        self.obst = []   # (shape, net, layer_id or None, label)
        for f in self.b.GetFootprints():
            for p in f.Pads():
                lab = f'{f.GetReference()}.{p.GetNumber()}[{p.GetNetname()}]'
                if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                    self.obst.append((p.GetEffectiveShape(pcbnew.F_Cu), p.GetNetname(), None, lab))
                else:
                    for l in COPPER.values():
                        if p.IsOnLayer(l): self.obst.append((p.GetEffectiveShape(l), p.GetNetname(), l, lab))
        for t in self.b.GetTracks():
            if t.GetClass() == 'PCB_VIA': self.obst.append((t.GetEffectiveShape(pcbnew.F_Cu), t.GetNetname(), None, f'via[{t.GetNetname()}]'))
            else: self.obst.append((t.GetEffectiveShape(), t.GetNetname(), t.GetLayer(), f'track[{t.GetNetname()}]@{self.b.GetLayerName(t.GetLayer())}'))
        self.no_via = [(z.GetZoneName(), z.Outline()) for z in self.b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
        self.no_trk = [(z.GetZoneName(), z.Outline(), set(z.GetLayerSet().Seq())) for z in self.b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
        # FDC pads on F.Cu forbid every foreign via under them: handled by the pad shapes above.

    def clr(self, net, other):
        return 0.2 if (net in EC_NETS or other in EC_NETS) else 0.15

    def net(self, name):
        n = self.b.FindNet(name); assert n, name; return n

    def check_via(self, x, y, net, d=0.6):
        if math.hypot(x - CX, y - CY) > 21.8: raise Collision(f'via ({x},{y}) too close to the rim')
        c = pcbnew.SHAPE_CIRCLE(P(x, y), mm(d / 2))
        for name, o in self.no_via:
            if o.Collide(P(x, y), mm(d / 2)): raise Collision(f'via ({x},{y}) inside no-via area {name}')
        for sh, n, l, lab in self.obst:
            if n == net:
                if l is None and sh.Collide(c, mm(0.3)) and 'via' in lab: raise Collision(f'via ({x},{y}) too close to same-net {lab}')
                continue
            if sh.Collide(c, mm(self.clr(net, n))): raise Collision(f'via ({x},{y}) hits {lab}')

    def check_seg(self, x1, y1, x2, y2, w, layer, net):
        lid = COPPER[layer]
        s = pcbnew.SHAPE_SEGMENT(P(x1, y1), P(x2, y2), mm(w))
        for sh, n, l, lab in self.obst:
            if n == net or (l is not None and l != lid): continue
            if sh.Collide(s, mm(self.clr(net, n))): raise Collision(f'segment ({x1},{y1})-({x2},{y2}) on {layer} hits {lab}')
        for name, o, layers in self.no_trk:
            if lid in layers:
                for t in (0, 0.25, 0.5, 0.75, 1):
                    px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                    if o.Collide(P(px, py), mm(w / 2)): raise Collision(f'segment ({x1},{y1})-({x2},{y2}) inside no-track area {name} on {layer}')
        for px, py in ((x1, y1), (x2, y2)):
            if math.hypot(px - CX, py - CY) > 22.2: raise Collision(f'segment end ({px},{py}) too close to the rim')

    def path(self, pts, w, layer, net, check=True):
        segs = [(a, b) for a, b in zip(pts, pts[1:]) if a != b]
        if check:
            for (x1, y1), (x2, y2) in segs: self.check_seg(x1, y1, x2, y2, w, layer, net)
        for (x1, y1), (x2, y2) in segs:
            t = pcbnew.PCB_TRACK(self.b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(mm(w)); t.SetLayer(COPPER[layer]); t.SetNet(self.net(net)); self.b.Add(t)
            self.obst.append((t.GetEffectiveShape(), net, COPPER[layer], f'new track[{net}]@{layer}'))

    def via(self, x, y, net, d=0.6, drill=0.3, check=True):
        if check: self.check_via(x, y, net, d)
        v = pcbnew.PCB_VIA(self.b); v.SetPosition(P(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetDrill(mm(drill)); v.SetWidth(mm(d))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(self.net(net)); self.b.Add(v)
        self.obst.append((v.GetEffectiveShape(pcbnew.F_Cu), net, None, f'new via[{net}]'))

    def pad(self, ref, num):
        f = self.b.FindFootprintByReference(ref)
        for p in f.Pads():
            if p.GetNumber() == str(num): return (round(tomm(p.GetPosition().x), 3), round(tomm(p.GetPosition().y), 3))
        raise KeyError((ref, num))

    def near(self, x, y, r=2.0, layer=None):
        """List obstacles within r mm of (x,y) for planning."""
        c = pcbnew.SHAPE_CIRCLE(P(x, y), mm(r)); out = []
        for sh, n, l, lab in self.obst:
            if layer and l is not None and l != COPPER[layer]: continue
            if sh.Collide(c, 0): out.append(lab)
        return out

    def save(self, out, fill=True):
        if fill: pcbnew.ZONE_FILLER(self.b).Fill(self.b.Zones())
        pcbnew.SaveBoard(out, self.b)
