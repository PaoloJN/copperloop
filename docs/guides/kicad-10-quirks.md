# KiCad 10 quirks we hit (and how to live with them)

- **pcbnew.SaveBoard from Python overwrites the `.kicad_pro` next to the board** with defaults (net classes, clearances gone). Always run scripts on a copy in a scratch folder, re-copy the real `.kicad_pro`/`.kicad_sch` next to it before DRC, and copy only the `.kicad_pcb` back.
- **Schematic parity needs the `.kicad_sch` beside the board** or `kicad-cli pcb drc --schematic-parity` silently reports nothing; result is in JSON key `schematic_parity`.
- **One `FootprintLoad` per Python process**; add footprints before flipping them.
- **Deleting tracks through SWIG can crash KiCad 10**; strip them textually (S-expression) instead. Tracks store the net by name in KiCad 10 files.
- **Stale zone fills look like clearance errors.** Refill (`--refill-zones`) before trusting DRC on a board someone edited by hand.
- **Rule areas on inner planes**: a via inside a "no copper on GND/PWR" area is a dangling via. Route the pad out of the area to a via that actually touches the plane.
- **IPC API (kipy) in KiCad 10**: GUI must be open with the board loaded; modal dialogs block the socket; no DRC, no plot, no library placement, no schematic. Use kicad-cli for those.
- **SWIG pcbnew is removed in KiCad 11** (~Mar 2027). Keep it behind an adapter and prefer kicad-cli/IPC.
- **zsh**: `$c:hardware/...` triggers the `:h` modifier. Write `"${c}:path"`.
- **Freerouting DSN** carries only net-class width/clearance/via. `class_class` pair clearances, custom `.kicad_dru` rules and no-via regions are dropped; model them as keepouts. `protect`ed wires are obstacles, not connectivity, so a partially protected net never completes.
