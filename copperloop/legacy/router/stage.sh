#!/bin/zsh
# usage: stage.sh base.kicad_pcb tag passes [router_export extra args...]
set -e
S=$ROUTE_WORK
SC=/Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/scripts
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
BASE=$1; TAG=$2; PASSES=$3; shift 3
$KP $SC/router_export.py $BASE /Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/puck-carrier.kicad_pro $S/$TAG.dsn "$@" 2>&1 | grep -E 'protected|capped' | cut -c1-150
$S/freeroute.sh $S/$TAG.dsn $S/$TAG.ses $PASSES $S/$TAG.log
echo "router: $(grep -o 'for [0-9]* unrouted items' $S/$TAG.log) -> $(grep -E 'Stopping' $S/$TAG.log | grep -o '([0-9]* items still unconnected' | tail -1)"
$S/import.sh $BASE $S/$TAG.ses $S/$TAG.kicad_pcb $TAG 2>&1 | grep -v -e Debug -e Fontconfig -e 'ses import'
