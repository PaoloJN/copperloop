"""Export a Specctra DSN "router view" of the board for Freerouting.

KiCad Python: router_export.py board.kicad_pcb project.kicad_pro out.dsn [--hide NET ...]

Differences from a plain File > Export > Specctra DSN:
  * every copper fill is dropped (DSN planes are hard obstacles to a router,
    and KiCad re-pours them around whatever comes back);
  * rule areas that do not forbid tracks or vias on an OUTER layer are
    dropped (fill-only masks and inner-layer track keep-outs would otherwise
    turn into through-via keep-outs);
  * all existing wiring is marked `protect` so the router cannot rip it up;
  * the hidden nets (default GND and 3V3, served by the planes and the
    fan-out vias) are reduced to a single pin so the router ignores them.
The inner layers get a dummy plane each so Freerouting keeps them as `power`
layers and only draws on F.Cu/B.Cu. Run it with --router.fanout.enabled=false.
Final DRC must run on the real board after the session import.
"""
import sys, argparse, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'wiring'))
from sexp import parse, find, find_all, atom, serialize, Sym
import pcbnew

ap = argparse.ArgumentParser()
ap.add_argument('board'); ap.add_argument('project'); ap.add_argument('out')
ap.add_argument('--hide', nargs='*', default=['GND', '3V3'])
ap.add_argument('--width-cap', type=int, default=0, help='cap every DSN class/rule track width to this many um (KiCad DRC only enforces the board minimum, so the router may use thinner traces than the net class default)')
ap.add_argument('--net-pins', nargs='*', default=[], help='NET=REF-PAD,REF-PAD,... : expose only these pins of NET (one per island) so the router just bridges islands')
ap.add_argument('--only', nargs='*', help='route only these nets (every other net is hidden)')
ap.add_argument('--route-inner', nargs='*', default=[], help='inner layer names (GND, PWR) the router may also draw on; default none')
ap.add_argument('--inner-band', nargs=4, type=float, metavar=('X0','Y0','X1','Y1'), help='with --route-inner: confine inner-layer wires to this rectangle (mm) using wire_keepouts, so the plane stays whole elsewhere')
ap.add_argument('--clearance-floor', type=int, default=0, help='raise every DSN clearance rule to at least this many um (Freerouting ignores class_class rules, and KiCad applies the larger of two net-class clearances)')
ap.add_argument('--pair-clearance', nargs='*', default=[], help='CLASS:um — KiCad uses the larger clearance of two net classes; emit class_class rules so the router does too')
ap.add_argument('--keepout-circle', nargs=4, action='append', default=[], metavar=('X','Y','R','LAYER'), help='extra router-only wire keep-out disc (mm, layer F.Cu/B.Cu/PWR) so through-traffic stays out of a region')
ap.add_argument('--hide-connected', metavar='DRC_JSON', help='also hide every net that this KiCad DRC report lists no unconnected item for')
a = ap.parse_args()
OUTER = {'F.Cu', 'B.Cu'}

doc = parse(Path(a.board).read_text())[0]
kept, dropped, inner_ko = [], [], []
for z in list(find_all(doc, 'zone')):
    n = find(z, 'name'); name = atom(n[1]) if n else '?'
    ko = find(z, 'keepout')
    lay = find(z, 'layers') or find(z, 'layer')
    LNAME = {'In1.Cu': 'GND', 'In2.Cu': 'PWR'}   # board layer names as the DSN spells them
    layers = {LNAME.get(atom(x), atom(x)) for x in lay[1:]} if lay else set()
    if '*.Cu' in layers or 'F&B.Cu' in layers: layers |= OUTER
    blocks = ko and any(find(ko, k) and atom(find(ko, k)[1]) == 'not_allowed' for k in ('tracks', 'vias'))
    if ko and blocks and layers & OUTER: kept.append(name)
    else:
        if ko and find(ko, 'tracks') and atom(find(ko, 'tracks')[1]) == 'not_allowed' and layers & set(a.route_inner):
            pts = find(find(z, 'polygon'), 'pts')
            inner_ko.append((name, [l for l in layers if l in a.route_inner], [(float(atom(x[1])), float(atom(x[2]))) for x in find_all(pts, 'xy')]))
        doc.remove(z); dropped.append(name)
print('rule areas kept for the router:', kept)
print('zones dropped from the router view:', dropped)

tmpdir = tempfile.mkdtemp()
view = Path(tmpdir) / 'puck-carrier.kicad_pcb'
view.write_text(serialize(doc) + '\n')
# the project file must sit beside the board so net classes (widths/clearances) reach the DSN
Path(tmpdir, 'puck-carrier.kicad_pro').write_text(Path(a.project).read_text())
mgr = pcbnew.GetSettingsManager(); mgr.LoadProject(str(Path(tmpdir, 'puck-carrier.kicad_pro')))
b = pcbnew.LoadBoard(str(view)); b.SetProject(mgr.GetProject(str(Path(tmpdir, 'puck-carrier.kicad_pro'))))
raw_out = Path(tmpdir) / 'raw.dsn'
if not pcbnew.ExportSpecctraDSN(b, str(raw_out)): raise SystemExit('DSN export failed')

raw = raw_out.read_text().replace('(string_quote ")', '(string_quote QUOTE_MARKER)')
dsn = parse(raw)[0]
wiring = find(dsn, 'wiring')
n_prot = 0
for item in wiring[1:] if wiring else []:
    if isinstance(item, list):
        t = find(item, 'type')
        if t: t[1] = Sym('protect'); n_prot += 1
        else: item.append([Sym('type'), Sym('protect')]); n_prot += 1
# Freerouting treats a `power` layer with no plane as a signal layer. Give each
# inner layer a tiny dummy plane (inside the antenna keep-out, far from any
# copper) so the router keeps its traces on the outer layers.
structure = find(dsn, 'structure')
def wire_keepout(layer, pts):
    coords = ' '.join(f'{x*1000:.0f} {-y*1000:.0f}' for x, y in pts)
    structure.append(parse(f'(wire_keepout "" (polygon {layer} 0 {coords}))')[0])
for name, layers, pts in inner_ko:
    for layer in layers: wire_keepout(layer, pts); print(f'inner-layer track keep-out {name} kept on {layer} as wire_keepout')
import math
for X_, Y_, R_, L_ in a.keepout_circle:
    X_, Y_, R_ = float(X_), float(Y_), float(R_)
    wire_keepout(L_, [(X_ + R_ * math.cos(2 * math.pi * i / 72), Y_ + R_ * math.sin(2 * math.pi * i / 72)) for i in range(72)]); print(f'router-only keep-out disc ({X_},{Y_}) r{R_} on {L_}')
if a.inner_band and a.route_inner:
    x0, y0, x1, y1 = a.inner_band; R = 30
    for layer in a.route_inner:
        for rect in (((120, 70), (180, 70), (180, y0), (120, y0)), ((120, y1), (180, y1), (180, 130), (120, 130)),
                     ((120, y0), (x0, y0), (x0, y1), (120, y1)), ((x1, y0), (180, y0), (180, y1), (x1, y1))):
            wire_keepout(layer, rect)
    print(f'inner-layer wires confined to x{x0}-{x1} y{y0}-{y1} on {a.route_inner}')
for layer, netname, x in (('GND', 'GND', 128000), ('PWR', '3V3', 128600)):
    if layer in a.route_inner:
        for lay in find_all(structure, 'layer'):
            if atom(lay[1]) == layer:
                t = find(lay, 'type'); t[1] = Sym('signal'); print(f'layer {layer} opened for routing')
        continue
    structure.append(parse(f'(plane {netname} (polygon {layer} 0 {x} -99900 {x+300} -99900 {x+300} -100100 {x} -100100))')[0])
network = find(dsn, 'network')
hide = set(a.hide)
if a.hide_connected:
    import json, re
    j = json.load(open(a.hide_connected)); open_nets = set()
    for x in j['unconnected_items']:
        for i in x['items']:
            m = re.search(r'\[([^\]]+)\]', i['description'])
            if m: open_nets.add(m.group(1))
    for net in find_all(network, 'net'):
        if atom(net[1]) not in open_nets: hide.add(atom(net[1]))
if a.only:
    for net in find_all(network, 'net'):
        if atom(net[1]) not in a.only: hide.add(atom(net[1]))
hidden = []
pins_override = {spec.split('=')[0]: spec.split('=')[1].split(',') for spec in a.net_pins}
for net in find_all(network, 'net'):
    if atom(net[1]) in pins_override:
        hide.discard(atom(net[1]))
        pins = find(net, 'pins')
        if pins: del pins[1:]; pins.extend(Sym(x) for x in pins_override[atom(net[1])])
        print(f'net {atom(net[1])}: exposed pins {pins_override[atom(net[1])]}')
        continue
    if atom(net[1]) in hide:
        pins = find(net, 'pins')
        if pins and len(pins) > 2: del pins[2:]
        hidden.append(atom(net[1]))
classes = [atom(c[1]) for c in find_all(network, 'class')]
n_pairs = 0
for spec in a.pair_clearance:
    cname, um = spec.split(':')
    if cname not in classes: continue
    for other in classes:
        network.append(parse(f'(class_class (classes {cname} {other}) (rule (clearance {um})))')[0]); n_pairs += 1
print(f'added {n_pairs} class_class clearance rules')
floored = 0
if a.clearance_floor:
    def floor_(node):
        global floored
        for x in node:
            if isinstance(x, list):
                if x and atom(x[0]) == 'clearance' and len(x) >= 2 and float(atom(x[1])) < a.clearance_floor: x[1] = Sym(str(a.clearance_floor)); floored += 1
                else: floor_(x)
    for cls in find_all(network, 'class'): floor_(cls)
    floor_(find(dsn, 'structure'))
    print(f'raised {floored} clearance rules to {a.clearance_floor} um')
capped = 0
if a.width_cap:
    def cap(node):
        global capped
        for x in node:
            if isinstance(x, list):
                if x and atom(x[0]) == 'width' and len(x) == 2 and float(atom(x[1])) > a.width_cap: x[1] = Sym(str(a.width_cap)); capped += 1
                else: cap(x)
    for cls in find_all(network, 'class'): cap(cls)
    cap(find(dsn, 'structure'))
    print(f'capped {capped} width rules to {a.width_cap} um')
Path(a.out).write_text(serialize(dsn).replace('(string_quote QUOTE_MARKER)', '(string_quote ")') + '\n')
print(f'protected {n_prot} existing wires/vias; hidden nets {hidden}; wrote {a.out}')
