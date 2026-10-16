#!/bin/zsh
# usage: round.sh base.kicad_pcb base_drc.json tag passes   -> $S/<tag>.kicad_pcb + $S/drc/<tag>.json
set -e
S=$ROUTE_WORK
SC=/Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/scripts
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
BASE=$1; DRCJ=$2; TAG=$3; PASSES=${4:-60}
GNDPADS=$(python3 -I -c "
import json,re,sys
j=json.load(open('$DRCJ')); s=set()
for x in j['unconnected_items']:
    for i in x['items']:
        m=re.match(r'Pad (\S+) \[GND\] of (\S+) on',i['description'])
        if m: s.add(m.group(2)+':'+m.group(1))
print(' '.join(sorted(s)))")
echo "GND pads to stitch: $GNDPADS"
python3 -I $S/strip_thin.py $BASE $S/$TAG-a.kicad_pcb
if [ -n "$GNDPADS" ]; then
  $KP $SC/fanout_planes.py $S/$TAG-a.kicad_pcb $S/$TAG-b.kicad_pcb --nets --gnd-pads ${=GNDPADS} 2>&1 | grep -E 'placed|FAILED|-> None'
else
  cp $S/$TAG-a.kicad_pcb $S/$TAG-b.kicad_pcb
fi
$KP $SC/router_export.py $S/$TAG-b.kicad_pcb /Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/puck-carrier.kicad_pro $S/$TAG.dsn --hide-connected $DRCJ --width-cap 250 --route-inner PWR 2>&1 | grep -E 'protected'
$S/freeroute.sh $S/$TAG.dsn $S/$TAG.ses $PASSES $S/$TAG.log
grep -E 'Stopping' $S/$TAG.log | cut -c1-200 | tail -1
$S/import.sh $S/$TAG-b.kicad_pcb $S/$TAG.ses $S/$TAG.kicad_pcb $TAG
