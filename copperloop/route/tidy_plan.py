"""Plan a plane-net tidy: every pad keeps one shortest stub + one via, the rest goes.

KICAD_PY tidy_plan.py board.kicad_pcb --net GND --json plan.json [--keep-ref U1 U8 ...]

Builds the outer-layer copper graph of NET (pads, vias, track pieces), groups it into
clusters, and for each pad picks the cheapest path to a via that does not run through
another pad. Union of the chosen paths is kept; every other via/segment in a cluster
that contains at least one pad is marked for removal. Pads that cannot reach a via
without crossing another pad (module pads, parts under a no-via zone) keep that path
too, so chains that are structurally necessary survive. Never saves.
Output: {"clusters": [{"pads": [...], "remove": [uuid...], "keep": [uuid...], "note": str}], "remove_count": n}
"""
import sys, argparse, json, heapq, pcbnew

ap = argparse.ArgumentParser()
ap.add_argument('board'); ap.add_argument('--json', required=True)
ap.add_argument('--net', default='GND')
ap.add_argument('--keep-ref', nargs='*', default=[], help='footprint refs whose clusters are left untouched')
a = ap.parse_args()
b = pcbnew.LoadBoard(a.board); tomm = pcbnew.ToMM
NET = a.net
vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == NET]
segs = [t for t in b.GetTracks() if t.GetClass() != 'PCB_VIA' and t.GetNetname() == NET]
pads = [(f, p) for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == NET and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]

nodes = []  # (kind, label, shape, layer, uuid, length)
for f, p in pads: nodes.append(('pad', f'{f.GetReference()}.{p.GetNumber()}', p.GetEffectiveShape(f.GetLayer()), f.GetLayer(), None, 0.0))
for v in vias: nodes.append(('via', f'via@{tomm(v.GetPosition().x):.2f},{tomm(v.GetPosition().y):.2f}', v.GetEffectiveShape(pcbnew.F_Cu), None, v.m_Uuid.AsString(), 0.0))
for s in segs: nodes.append(('seg', f'seg@{tomm(s.GetStart().x):.2f},{tomm(s.GetStart().y):.2f}', s.GetEffectiveShape(), s.GetLayer(), s.m_Uuid.AsString(), tomm(s.GetLength())))
adj = {i: set() for i in range(len(nodes))}
for i in range(len(nodes)):
    for j in range(i + 1, len(nodes)):
        x, y = nodes[i], nodes[j]
        if x[0] == 'pad' and y[0] == 'pad': continue
        if x[3] is not None and y[3] is not None and x[3] != y[3]: continue
        if x[2].Collide(y[2], 0): adj[i].add(j); adj[j].add(i)

seen = {}; comps = []
for i in range(len(nodes)):
    if i in seen: continue
    stack, comp = [i], []
    while stack:
        k = stack.pop()
        if k in seen: continue
        seen[k] = len(comps); comp.append(k); stack.extend(adj[k])
    comps.append(comp)

def best_path(start, allow_pads):
    """Dijkstra from a pad to the nearest via; cost = segment length (+0.3 per hop). Returns node list or None."""
    dist = {start: 0.0}; prev = {}; pq = [(0.0, start)]
    while pq:
        d, k = heapq.heappop(pq)
        if d > dist.get(k, 1e9): continue
        if nodes[k][0] == 'via':
            path = [k]
            while path[-1] != start: path.append(prev[path[-1]])
            return path
        for n in adj[k]:
            if nodes[n][0] == 'pad' and n != start and not allow_pads: continue
            nd = d + nodes[n][5] + 0.3
            if nd < dist.get(n, 1e9): dist[n] = nd; prev[n] = k; heapq.heappush(pq, (nd, n))
    return None

out = {'clusters': [], 'remove_count': 0}
for comp in comps:
    pad_nodes = [k for k in comp if nodes[k][0] == 'pad']
    if not pad_nodes: continue   # stitching vias etc.: leave alone
    refs = {nodes[k][1].split('.')[0] for k in pad_nodes}
    if refs & set(a.keep_ref):
        out['clusters'].append({'pads': [nodes[k][1] for k in pad_nodes], 'remove': [], 'keep': [], 'note': 'kept (--keep-ref)'}); continue
    keep = set(); notes = []
    for k in pad_nodes:
        path = best_path(k, allow_pads=False)
        if path is None:
            path = best_path(k, allow_pads=True); notes.append(f'{nodes[k][1]} reaches a via only through another pad')
        if path is None: notes.append(f'{nodes[k][1]} has no via at all'); continue
        keep.update(path)
    remove = [nodes[k][4] for k in comp if nodes[k][0] in ('via', 'seg') and k not in keep]
    if not remove: continue
    out['clusters'].append({'pads': [nodes[k][1] for k in pad_nodes], 'remove': remove,
                            'keep': [nodes[k][4] for k in keep if nodes[k][4]], 'note': '; '.join(notes),
                            'removed_vias': sum(1 for k in comp if nodes[k][0] == 'via' and k not in keep),
                            'removed_segs': sum(1 for k in comp if nodes[k][0] == 'seg' and k not in keep)})
    out['remove_count'] += len(remove)
json.dump(out, open(a.json, 'w'), indent=1)
for c in out['clusters']:
    print(c['pads'], f"-{c.get('removed_vias', 0)} vias -{c.get('removed_segs', 0)} segs", c['note'])
print('total items to remove:', out['remove_count'])
