"""Synchronize pad nets/fields from a fresh KiCad netlist, without moving parts.

Usage (KiCad's Python): sync_board.py schematic.net board.kicad_pcb
Adds the three October reliability parts at reviewed coordinates; replaces D3.
Does not route or remove existing routes. Always run DRC with schematic parity.
"""
from pathlib import Path
import sys
import pcbnew
sys.path.insert(0, str(Path(__file__).parent / 'wiring'))
from sexp import parse, find, find_all, atom, Sym
from revise_spin1 import pretty, prop

PROJECT = Path(__file__).resolve().parents[1]
STOCK = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport')
mm = pcbnew.FromMM
def pt(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))

def main():
    netpath, boardpath = sys.argv[1:3]
    root = parse(Path(netpath).read_text())[0]
    b = pcbnew.LoadBoard(boardpath)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    field_updates = {}
    padnets = {}
    for n in find_all(find(root, 'nets'), 'net'):
        name = atom(find(n, 'name')[1])
        if not b.FindNet(name):
            b.Add(pcbnew.NETINFO_ITEM(b, name))
        for p in find_all(n, 'node'):
            padnets[(atom(find(p, 'ref')[1]), atom(find(p, 'pin')[1]))] = name
    placements = {'C24': (156.3, 115.1, 0), 'C25': (157.6, 109.4, 90), 'R33': (157.5, 93.5, 0)}
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    for c in find_all(find(root, 'components'), 'comp'):
        ref = atom(find(c, 'ref')[1]); fpnode = find(c, 'footprint')
        if not fpnode: continue
        ident = atom(fpnode[1]); nickname, name = ident.split(':', 1)
        f = fps.get(ref)
        if f is None or f.GetFPIDAsString() != ident:
            lib = PROJECT/'lib/footprints/puck-parts.pretty' if nickname == 'puck' else STOCK/'footprints'/(nickname+'.pretty')
            new = io.FootprintLoad(str(lib), name)
            if new is None: raise RuntimeError('Missing footprint '+ident)
            new.SetFPID(pcbnew.LIB_ID(nickname, name)); new.SetReference(ref)
            if f is not None:
                loc, angle, layer, path = f.GetPosition(), f.GetOrientationDegrees(), f.GetLayer(), f.GetPath()
                new.SetPath(path); b.Remove(f)
            else:
                x, y, angle = placements[ref]; loc, layer = pt(x,y), pcbnew.B_Cu
                stamps = find(c, 'tstamps')
                if stamps: new.SetPath(pcbnew.KIID_PATH('/'+atom(stamps[1])))
            b.Add(new)
            if new.GetLayer() != layer: new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            new.SetOrientationDegrees(angle); new.SetPosition(loc); f = new
            fps[ref] = f
            f.Reference().SetVisible(False); f.Value().SetVisible(False)
        f.SetValue(atom(find(c, 'value')[1]))
        props = {atom(find(p,'name')[1]): atom(find(p,'value')[1]) for p in find_all(c,'property') if find(p,'value')}
        fields = {atom(find(p,'name')[1]): atom(p[-1]) if not isinstance(p[-1],list) else '' for p in find_all(find(c,'fields') or [],'field')}
        desc = fields.get('Description','')
        field_updates[ref] = fields
        dnp = ref in ('C12','C13')
        attrs = f.GetAttributes()
        f.SetAttributes(attrs | pcbnew.FP_DNP if dnp else attrs & ~pcbnew.FP_DNP)
        for pad in f.Pads():
            name = padnets.get((ref, pad.GetNumber()))
            pad.SetNet(b.FindNet(name) if name else b.FindNet(0))
    # Connector drawing is the cable's contact face. Board coordinates viewed
    # through the top: GND, D+, D-, 5V. Mirrored bottom view mates the drawing.
    for ref, x in [('CP1',146.19),('CP3',148.73),('CP2',151.27),('CP4',153.81)]:
        f=fps[ref]; f.SetPosition(pt(x,118))
    for ref, (x,y,angle) in placements.items():
        f=fps[ref];f.SetPosition(pt(x,y));f.SetOrientationDegrees(angle)
    # The pressure bypass was left next to the charger; put it at its load.
    f=fps['C10']
    if f.GetLayer()!=pcbnew.F_Cu:f.Flip(f.GetPosition(),pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetPosition(pt(142.2,111.0))
    fps['C14'].SetPosition(pt(144.3,114.0))
    # Solid connections for fine-pitch IC ground pads: no starved thermals.
    for ref in ('U1','U2','U3','U4','U5','U6','U7','U8','U9','U10','U11'):
        for p in fps[ref].Pads():
            if p.GetNetname() == 'GND': p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    pcbnew.SaveBoard(boardpath,b)
    # KiCad 10's macOS SWIG PCB_FIELD accessors are unstable; preserve fields
    # using the documented file representation instead.
    doc=parse(Path(boardpath).read_text())[0]
    for f in find_all(doc,'footprint'):
        ref=prop(f,'Reference')
        for key in ('Description','Datasheet'):
            for p in find_all(f,'property'):
                if atom(p[1])==key: p[2]=('str',field_updates.get(ref,{}).get(key,''))
        if ref.startswith('CP'):
            for g in list(find_all(f,'fp_circle')):
                layer=atom(find(g,'layer')[1])
                if layer=='B.SilkS':f.remove(g)
                elif layer=='B.CrtYd':find(g,'end')[1:]=[Sym('1.2'),Sym('0')]
    Path(boardpath).write_text(pretty(doc)+'\n')
    print('Synchronized',len(list(b.GetFootprints())),'footprints')

if __name__ == '__main__': main()
