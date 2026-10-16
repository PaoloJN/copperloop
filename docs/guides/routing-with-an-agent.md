# Routing a 4-layer board with an agent (what worked on the Water Puck)

Stack: F.Cu / GND plane / PWR (3V3 pour) / B.Cu. Round 46 mm board, nRF52840 module on B.Cu, capacitive sense pads on F.Cu with a no-foreign-via disc under them.

## Layer roles, decided before any trace
- **F.Cu**: sensor pads and short stubs to vias. No through-traffic.
- **GND**: solid plane. Never route on it, never cut it. One island allowed for a shield.
- **PWR**: 3V3 pour. Signals only in defined bands, nowhere else.
- **B.Cu**: all signal routing.

## Order
1. Rules: net classes, a local rule area around the dense module (0.1 mm trace/clearance, 0.45/0.2 via when the fab allows), keepouts for antenna, sensor discs, EC front end.
2. Module fan-out first. Escape the dense column through the gap between pad rows to a via column, then drop to the routing layer. Decide this on paper before touching the board.
3. GND: one stub (≤1 mm, 0.3 mm) plus one through via per GND pad. No pad-to-pad GND traces. Pads inside plane cutouts get routed out to a via that touches the plane.
4. Power: 3V3 stub + via per pad into the pour. VBAT/5V/VBUS/1V8 as 0.3 mm traces on B.Cu.
5. Sensitive pairs (EC excitation/sense, FDC CIN) next, with their own clearance and away from digital.
6. USB pair.
7. Everything else.
8. Stitching vias around the rim and near sensors. Pours last.

## Division of labour
- Human: the chokepoint nets (dense module escapes under a no-via zone) with KiCad's push-and-shove. No tool in KiCad 10 can script that.
- Agent: fan-outs, stitching, power stubs, collision-checked straight routes, DRC triage, parity, renders, docs.

## What failed (don't repeat)
- Whole-board Freerouting on a board with a no-via disc next to a 0.4 mm-gap module: it used the disc as a highway and boxed the escapes in.
- Rip-up loops that diverge (49 → 99 opens).
- Fan-out at the default clearance on nets that carry a larger class clearance: DRC errors. Fan-out must use the pair clearance.
- Trusting a DRC run beside a `.kicad_pro` that a script had just overwritten.

## The loop
propose (collision-checked) → commit over IPC → `kicad-cli pcb drc --format json --schematic-parity` → keep only if violations and unconnected did not increase → render the region and look.
