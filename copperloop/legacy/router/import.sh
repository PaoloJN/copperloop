#!/bin/zsh
# usage: import.sh base.kicad_pcb session.ses out.kicad_pcb tag
S=$ROUTE_WORK
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 /Users/paolonessim/Projects/sensei-cup/hardware/hardware-puck-carrier/scripts/freerouting_import.py "$1" "$2" "$3" 2>&1 | grep -v -e Fontconfig -e assert
$S/drc.sh "$3" "$4"
