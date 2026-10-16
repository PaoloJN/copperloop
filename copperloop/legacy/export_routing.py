"""Export DSN with actual project rules and explicit split-plane windows.

Router input omits outer fills and fill-only keepouts, which DSN cannot model.
Final DRC must always use the original PCB with all its zones and keepouts.
"""
import sys
import subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'wiring'))
from sexp import parse,find,find_all,atom,serialize,Sym

def main():
    if sys.argv[1]=='--raw':
        import pcbnew
        boardpath,projectpath,output=sys.argv[2:5]
        manager=pcbnew.GetSettingsManager();manager.LoadProject(projectpath)
        b=pcbnew.LoadBoard(boardpath);b.SetProject(manager.GetProject(projectpath))
        if not pcbnew.ExportSpecctraDSN(b,output):raise RuntimeError('DSN export failed')
        return
    boardpath,projectpath,output=[Path(p).resolve() for p in sys.argv[1:4]]
    doc=parse(boardpath.read_text())[0]
    for z in list(find_all(doc,'zone')):
        n=find(z,'name');name=atom(n[1]) if n else ''
        keep=find(z,'keepout')
        fill_only=keep and atom(find(keep,'tracks')[1])=='allowed' and atom(find(keep,'vias')[1])=='allowed'
        # Dedicated inner layers are not signal-routing layers. DSN turns
        # their track/fill-only rule areas into *via* keepouts too.
        plane_rule=name in ('KO_EC_PLANES','KO_FDC_IN2')
        if name in ('GND_TOP','GND_BOT','KO_RIM') or fill_only or plane_rule:doc.remove(z)
    temp=output.with_suffix('.router-view.kicad_pcb');temp.write_text(serialize(doc)+'\n')
    subprocess.run([sys.executable,__file__,'--raw',str(temp),str(projectpath),str(output)],check=True)
    raw=output.read_text().replace('(string_quote ")','(string_quote QUOTE_MARKER)')
    doc=parse(raw)[0];structure=find(doc,'structure')
    for plane in find_all(structure,'plane'):
        polygon=find(plane,'polygon')
        if atom(plane[1])=='GND' and polygon and atom(polygon[1])=='GND':
            plane.append(parse('(window (circle GND 14400 148400 -100000))')[0])
    for item in find(doc,'wiring')[1:]:
        if isinstance(item,list):
            t=find(item,'type')
            if t:t[1]=Sym('protect')
    output.write_text(serialize(doc).replace('(string_quote QUOTE_MARKER)','(string_quote ")')+'\n')
    print('Exported',output)

if __name__=='__main__':main()
