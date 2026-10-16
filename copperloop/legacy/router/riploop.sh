#!/bin/zsh
# usage: riploop.sh start.kicad_pcb tag maxiter [extra grid_router args]
# Iterates: geom export -> grid_router (--rip, protecting every net routed so far)
# on the nets KiCad still reports open -> apply -> DRC, until nothing improves.
set -e
S=$ROUTE_WORK; SC=/Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/scripts
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CUR=$1; TAG=$2; MAX=${3:-8}; shift 3 || true; EXTRA="$@"
PROTECT=""; BEST=999; BESTF=$CUR
$S/drc.sh $CUR ${TAG}0 | tail -1
for i in $(seq 1 $MAX); do
  NETS=$(python3 -I -c "
import json,re,sys
j=json.load(open('$S/drc/${TAG}$((i-1)).json')); seen=[]
for x in j['unconnected_items']:
    m=re.search(r'\[([^\]]+)\]', x['items'][0]['description']); n=m.group(1) if m else '?'
    if n not in ('GND','3V3') and n not in seen: seen.append(n)
print(' '.join(seen))")
  N=$(echo $NETS | wc -w | tr -d ' ')
  echo "== iter $i: $N open nets: $NETS"
  [ "$N" = "0" ] && break
  $KP $SC/geom_export.py $CUR $S/${TAG}$i-geom.json 2>&1 | grep -v assert | tail -1
  uv run --with numpy,scipy,shapely python3 $SC/grid_router.py $S/${TAG}$i-geom.json $S/${TAG}$i-plans.json --rip --nets ${=NETS} --protect ${=PROTECT} $EXTRA 2>&1 | grep -vE '^Installed' > $S/${TAG}$i-router.log || true
  grep -E 'SUMMARY|failed:' $S/${TAG}$i-router.log | tail -2
  grep -c routed: $S/${TAG}$i-router.log | xargs -I{} echo "   plans: {}"
  $KP $SC/apply_plans.py $CUR $S/${TAG}$i-plans.json $S/${TAG}$i.kicad_pcb 2>&1 | grep -E 'removed|SKIPPED|applied'
  $S/drc.sh $S/${TAG}$i.kicad_pcb ${TAG}$i | tail -2
  ROUTED=$(python3 -I -c "
import json; print(' '.join(sorted(set(p['net'] for p in json.load(open('$S/${TAG}$i-plans.json'))))))")
  PROTECT="$PROTECT $ROUTED"
  CUR=$S/${TAG}$i.kicad_pcb
  OPEN=$(python3 -I -c "import json;print(len(json.load(open('$S/drc/${TAG}$i.json'))['unconnected_items']))")
  ERR=$(python3 -I -c "import json;print(sum(1 for v in json.load(open('$S/drc/${TAG}$i.json'))['violations'] if v['severity']=='error'))")
  echo "   -> $CUR opens=$OPEN errors=$ERR"
  if [ "$ERR" = "0" ] && [ "$OPEN" -lt "$BEST" ]; then BEST=$OPEN; BESTF=$CUR; fi
done
echo "BEST $BESTF opens=$BEST"
