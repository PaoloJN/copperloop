"""strip_thin.py in.kicad_pcb out.kicad_pcb  -- drop router neck-downs below the board minimum width (textual, KiCad 10)."""
import sys
sys.path.insert(0,'/Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/scripts/wiring')
from sexp import parse,find,atom,serialize
doc=parse(open(sys.argv[1]).read())[0]; n=0
for item in [i for i in doc if isinstance(i,list) and i and atom(i[0])=='segment']:
    w=find(item,'width')
    if w and float(atom(w[1]))<0.15: doc.remove(item); n+=1
open(sys.argv[2],'w').write(serialize(doc)+'\n'); print('stripped thin segments',n)
