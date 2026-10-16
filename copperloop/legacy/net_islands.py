"""Print one pad per disconnected cluster ("island") of a net, after refilling zones.

KiCad Python: net_islands.py board.kicad_pcb NET [NET ...]
Output lines:  NET REF-PAD REF-PAD ...   (one representative pad per island)
Feed them to router_export.py --net-pins so Freerouting only has to bridge the islands.
"""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
conn = b.GetConnectivity()
for netname in sys.argv[2:]:
    pads = [(f.GetReference() + '-' + p.GetNumber(), p) for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == netname]
    seen = set(); reps = []
    for name, p in pads:
        if p.m_Uuid.AsString() in seen: continue
        cluster = {i.m_Uuid.AsString() for i in conn.GetConnectedItems(p)} | {p.m_Uuid.AsString()}
        seen |= cluster; reps.append(name)
    print(netname, ' '.join(reps))
