#!/bin/zsh
# usage: drc.sh board.kicad_pcb tag  -> prints summary, writes $S/drc/<tag>.json
S=$ROUTE_WORK
cp "$1" $S/drc/puck-carrier.kicad_pcb
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc --format json --severity-all --refill-zones --schematic-parity -o $S/drc/$2.json $S/drc/puck-carrier.kicad_pcb 2>&1 | grep -E '^Found'
python3 -I - $S/drc/$2.json <<'PY'
import json,sys,collections,re
j=json.load(open(sys.argv[1]))
print(dict(collections.Counter((x['severity'],x['type']) for x in j['violations'])))
c=collections.Counter()
for x in j['unconnected_items']:
    d=x['items'][0]['description']; m=re.search(r'\[([^\]]+)\]',d); c[m.group(1) if m else '?']+=1
print('unconnected',len(j['unconnected_items']),dict(c))
PY
