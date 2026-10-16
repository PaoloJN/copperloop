"""Dump board copper geometry to JSON (mm) for grid_router.py.

KiCad Python: geom_export.py board.kicad_pcb out.json

items: pads (polygon per copper layer, PTH/NPTH on all four), tracks, arcs, vias;
fills: filled zone polygons per layer (after a refill);
keepouts: rule areas with their track/via flags and layers.
Layer index: 0 F.Cu, 1 In1.Cu (GND), 2 In2.Cu (PWR), 3 B.Cu.
"""
import sys, json, pcbnew, shutil, subprocess, tempfile, hashlib
from pathlib import Path

# pcbnew.LoadBoard() alone does not load the project's clearance/net-class
# settings. Its Python zone refill can therefore disagree with CLI DRC and
# falsely join power/ground islands. Refill a disposable copy using the same
# project rules as DRC; never alter the input board during an export.
source = Path(sys.argv[1]).resolve()
project = source.with_suffix('.kicad_pro')
if not project.is_file():
    raise SystemExit(f'Missing project rules: {project}')
cli = shutil.which('kicad-cli') or '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
with tempfile.TemporaryDirectory(prefix='puck-geometry-') as tmp:
    copied = Path(tmp) / source.name
    shutil.copy2(source, copied)
    shutil.copy2(project, copied.with_suffix('.kicad_pro'))
    rules = source.with_suffix('.kicad_dru')
    if rules.exists():
        shutil.copy2(rules, copied.with_suffix('.kicad_dru'))
    result = subprocess.run(
        [cli, 'pcb', 'drc', '--refill-zones', '--save-board', '--format', 'json',
         '-o', str(Path(tmp) / 'drc.json'), str(copied)],
        capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    b = pcbnew.LoadBoard(str(copied))
L = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
def xy(p): return [round(pcbnew.ToMM(p.x), 4), round(pcbnew.ToMM(p.y), 4)]
def polys(ps):
    def chain(c): return [xy(c.CPoint(i)) for i in range(c.PointCount())]
    return [[chain(ps.COutline(i))] + [chain(ps.CHole(i, j)) for j in range(ps.HoleCount(i))] for i in range(ps.OutlineCount())]
out = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
       'items': [], 'fills': [], 'keepouts': []}
for f in b.GetFootprints():
    for p in f.Pads():
        through = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        ls = list(range(4)) if through else [i for i, l in enumerate(L) if p.IsOnLayer(l)]
        for i in ls:
            ps = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(ps, L[i], 0, pcbnew.FromMM(0.001), pcbnew.ERROR_OUTSIDE)
            out['items'].append(dict(id=p.m_Uuid.AsString(), kind='pad', ref=f.GetReference(), num=p.GetNumber(), net=p.GetNetname(),
                                     layer=i, polys=polys(ps), pos=xy(p.GetPosition()), through=through, drill=pcbnew.ToMM(p.GetDrillSize().x) if through else 0))
            out['items'][-1]['clearance'] = pcbnew.ToMM(p.GetOwnClearance(L[i]))
for t in b.GetTracks():
    width = t.GetWidth(pcbnew.F_Cu) if t.GetClass() == 'PCB_VIA' else t.GetWidth()
    q = dict(id=t.m_Uuid.AsString(), net=t.GetNetname(), width=pcbnew.ToMM(width))
    if t.GetClass() == 'PCB_VIA': q.update(kind='via', pos=xy(t.GetPosition()), drill=pcbnew.ToMM(t.GetDrillValue()))
    else:
        q.update(kind='track', layer=L.index(t.GetLayer()), start=xy(t.GetStart()), end=xy(t.GetEnd()))
        if t.GetClass() == 'PCB_ARC': q.update(mid=xy(t.GetMid()))
    out['items'].append(q)
for z in b.Zones():
    if z.GetIsRuleArea():
        out['keepouts'].append(dict(name=z.GetZoneName(), layers=[i for i, l in enumerate(L) if z.IsOnLayer(l)],
                                    tracks=z.GetDoNotAllowTracks(), vias=z.GetDoNotAllowVias(), polys=polys(z.Outline())))
    else:
        for i, l in enumerate(L):
            if z.IsOnLayer(l): out['fills'].append(dict(name=z.GetZoneName(), net=z.GetNetname(), layer=i, polys=polys(z.GetFilledPolysList(l))))
json.dump(out, open(sys.argv[2], 'w'))
print(len(out['items']), 'items', len(out['fills']), 'fills', len(out['keepouts']), 'keepouts ->', sys.argv[2])
