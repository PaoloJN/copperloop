#!/usr/bin/env python3
"""Independent netlist/PCB checks plus KiCad ERC/DRC and a release manifest.

Usage: python3 scripts/verify_design.py [--output /absolute/report/directory]
Does not route, fabricate, suppress violations or edit source CAD. Reports are
engineering evidence; a passing CAD gate does not replace physical validation.
"""
import argparse, csv, hashlib, json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/'wiring'))
from sexp import parse, find, find_all, atom

PROJECT=Path(__file__).resolve().parents[1]

def properties(n):
    return {atom(x[1]):atom(x[2]) for x in find_all(n,'property')}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=PROJECT/'checks')
    a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    cli=shutil.which('kicad-cli') or '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
    pcb=PROJECT/'puck-carrier.kicad_pcb';sch=pcb.with_suffix('.kicad_sch')
    commands=[('netlist',['sch','export','netlist','-o',str(out/'schematic.net'),str(sch)]),
              ('erc',['sch','erc','--format','json','-o',str(out/'erc.json'),str(sch)]),
              ('drc',['pcb','drc','--schematic-parity','--refill-zones','--format','json','-o',str(out/'drc.json'),str(pcb)])]
    for name,cmd in commands:
        with (out/(name+'.log')).open('w') as log:
            result=subprocess.run([cli,*cmd],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError(f'{name} command failed; see {out/(name+".log")}')
    net=parse((out/'schematic.net').read_text())[0]
    board=parse(pcb.read_text())[0]
    expected={}
    for n in find_all(find(net,'nets'),'net'):
        name=atom(find(n,'name')[1])
        for node in find_all(n,'node'):
            expected[(atom(find(node,'ref')[1]),atom(find(node,'pin')[1]))]=name
    fps={properties(f).get('Reference'):f for f in find_all(board,'footprint')}
    comps={atom(find(c,'ref')[1]):c for c in find_all(find(net,'components'),'comp')}
    actual={};errors=[]
    for ref,f in fps.items():
        for pad in find_all(f,'pad'):
            pn=atom(pad[1]);nn=find(pad,'net');name=atom(nn[-1]) if nn else ''
            if pn:actual[(ref,pn)]=name
            want=expected.get((ref,pn),'')
            if want.startswith('unconnected-'):want=''
            if name!=want:errors.append(f'{ref}.{pn}: PCB {name!r}, schematic {want!r}')
    for key,name in expected.items():
        if key[0] in fps and not name.startswith('unconnected-') and key not in actual:
            errors.append(f'Missing board pad {key}')
    critical={('U7','1'):'CHG_STAT',('U7','2'):'GND',('U7','3'):'VBAT',('U7','4'):'VBUS',
        ('C24','1'):'VBUS',('C24','2'):'GND',('C25','1'):'VBAT',('C25','2'):'GND',
        ('R33','1'):'BOOST_EN',('R33','2'):'GND',('U1','14'):'EC_BIAS_EN',
        ('R20','1'):'EC_BIAS_EN',('R20','2'):'EC_BIAS',('U1','13'):'EXP_A4',
        ('U1','10'):'EXP_A5',('U1','17'):'EXP_00',('U1','18'):'EXP_01'}
    for key,want in critical.items():
        if expected.get(key)!=want:errors.append(f'Critical topology: {key} must be {want}')
    for ref,want in {'U7':'MCP73832T-2ACI/OT','R17':'10k','R33':'100k',
        'D1':'67-21/T2C-ZV1W2E/2T','D2':'HIR67-21C/L11/TR8','D3':'VLMU1610-365-135'}.items():
        if atom(find(comps[ref],'value')[1])!=want:errors.append(f'{ref}: expected value {want}')
    dock=[('CP1',146.19,'GND'),('CP3',148.73,'/PAD_DP'),('CP2',151.27,'/PAD_DM'),('CP4',153.81,'/PAD_5V')]
    for ref,x,want in dock:
        at=find(fps[ref],'at')
        if abs(float(at[1])-x)>.001 or abs(float(at[2])-118)>.001:errors.append(f'{ref}: dock geometry mismatch')
        if actual.get((ref,'1'))!=want:errors.append(f'{ref}: dock polarity mismatch')
    for ref in ('C12','C13'):
        attr=find(fps[ref],'attr') or []
        if not any(not isinstance(x,(list,tuple)) and atom(x)=='dnp' for x in attr[1:]):errors.append(f'{ref}: must be DNP until NFC tuning')
    # Export an engineering BOM, deliberately not a supplier-ready assembly CSV.
    with (out/'engineering-bom.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Reference','Value','Footprint','Population'])
        for ref,c in sorted(comps.items()):
            fp=find(c,'footprint')
            if not fp:continue
            feature=ref.startswith(('CP','TP','FID','FDC','E'))
            w.writerow([ref,atom(find(c,'value')[1]),atom(fp[1]),'PCB feature' if feature else 'DNP' if ref in ('C12','C13') else 'MPN/assembly quote review required'])
    erc=json.loads((out/'erc.json').read_text());drc=json.loads((out/'drc.json').read_text())
    ev=[v for s in erc['sheets'] for v in s['violations']]
    dv=drc['violations'];opens=drc['unconnected_items'];parity=drc.get('schematic_parity',[])
    counts={'erc_errors':sum(v['severity']=='error' for v in ev),'erc_warnings':sum(v['severity']=='warning' for v in ev),
        'drc_errors':sum(v['severity']=='error' for v in dv),'drc_warnings':sum(v['severity']=='warning' for v in dv),
        'unconnected_items':len(opens),'schematic_parity':len(parity),'topology_errors':len(errors)}
    passed=not any(counts[k] for k in ('erc_errors','drc_errors','unconnected_items','schematic_parity','topology_errors'))
    manifest={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'cad_gate':'PASS' if passed else 'FAIL',
        'physical_validation':'NOT PERFORMED','counts':counts,'topology_errors':errors,
        'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (sch,pcb,pcb.with_suffix('.kicad_pro'))}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
    return 0 if passed else 1

if __name__=='__main__':sys.exit(main())
