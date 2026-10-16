#!/bin/zsh
# usage: bridge.sh base.kicad_pcb tag  -> route only island bridges for GND and 3V3
set -e
S=$ROUTE_WORK
SC=/Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/scripts
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
BASE=$1; TAG=$2
ISL=$($KP $SC/net_islands.py $BASE 3V3 GND 2>&1 | grep -E '^(3V3|GND) ')
echo "$ISL"
ARGS=()
while read -r net reps; do ARGS+=("$net=${reps// /,}"); done <<< "$ISL"
$KP $SC/router_export.py $BASE /Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/puck-carrier.kicad_pro $S/$TAG.dsn --width-cap 250 --route-inner PWR --only NONE --net-pins "${ARGS[@]}" 2>&1 | grep -E 'exposed|protected' | cut -c1-200
$S/freeroute.sh $S/$TAG.dsn $S/$TAG.ses 60 $S/$TAG.log
echo "router: $(grep -o 'for [0-9]* unrouted items' $S/$TAG.log) -> $(grep -E 'Stopping' $S/$TAG.log | grep -o '([0-9]* items still unconnected' | tail -1)"
$S/import.sh $BASE $S/$TAG.ses $S/$TAG.kicad_pcb $TAG 2>&1 | grep -v -e Debug -e Fontconfig -e 'ses import'
