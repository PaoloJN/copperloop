"""Replace simple two-segment bends with tangent KiCad copper arcs.
No net/layer/width changes. Skips junctions, pads, vias and constrained corners.
Use a fresh geometry export and run a refill/parity DRC after this operation.
"""
import sys,math,json,uuid,collections,hashlib
from pathlib import Path
from shapely import Point,LineString,Polygon,union_all,make_valid,STRtree
sys.path.insert(0, str(Path(__file__).resolve().parent / 'wiring'))
from sexp import parse,find,find_all,atom,serialize,Sym
src,geom,out=sys.argv[1:];b=parse(Path(src).read_text())[0];D=json.load(open(geom));LS=['F.Cu','In1.Cu','In2.Cu','B.Cu']
if D.get('source_sha256') and hashlib.sha256(Path(src).read_bytes()).hexdigest()!=D['source_sha256']:
 raise SystemExit('Geometry export does not match the input board')
def pos(n):return tuple(float(atom(v)) for v in n[1:])
def setpos(n,p):n[1:]=[Sym(f'{v:.6f}') for v in p]
def sub(a,b):return (a[0]-b[0],a[1]-b[1])
def add(a,b):return (a[0]+b[0],a[1]+b[1])
def mul(a,k):return (a[0]*k,a[1]*k)
def length(v):return math.hypot(*v)
segs=find_all(b,'segment');nodes=collections.defaultdict(list)
for i,s in enumerate(segs):
 for k in ('start','end'):nodes[(atom(find(s,'net')[1]),atom(find(s,'layer')[1]),pos(find(s,k)))].append((i,k))
def arc_pts(s, m, e):
    ax, ay = s; bx, by = m; cx, cy = e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9: return [s, e]
    ux = ((ax*ax + ay*ay) * (by - cy) + (bx*bx + by*by) * (cy - ay) + (cx*cx + cy*cy) * (ay - by)) / d
    uy = ((ax*ax + ay*ay) * (cx - bx) + (bx*bx + by*by) * (ax - cx) + (cx*cx + cy*cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy); a0 = math.atan2(ay - uy, ax - ux); a1 = math.atan2(by - uy, bx - ux); a2 = math.atan2(cy - uy, cx - ux)
    def norm(t): return (t + 2 * math.pi) % (2 * math.pi)
    sweep = norm(a2 - a0); mid = norm(a1 - a0)
    if mid > sweep: sweep -= 2 * math.pi
    n = max(4, int(abs(sweep) * r / 0.1))
    return [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]

shapes=[];meta=[]
for q in D['items']:
 if q['kind']=='pad':g=union_all([make_valid(Polygon(p[0],p[1:])) for p in q['polys']]);ls=[q['layer']]
 elif q['kind']=='via':g=Point(q['pos']).buffer(q['width']/2);ls=list(range(4))
 else:g=LineString(arc_pts(q['start'],q['mid'],q['end']) if 'mid' in q else [q['start'],q['end']]).buffer(q['width']/2);ls=[q['layer']]
 shapes.append(g);meta.append((q,ls))
tree=STRtree(shapes);count=0;record=[]
EC={'EC_A','EC_B','EC_SENSE_A','EC_SENSE_B','EC_BIAS','EC_BIAS_EN','EC_DRV_HI','EC_DRV_LO','/EC_NODE_D','EXP_A4','EXP_A5'}
for (net,layer,p),adj in nodes.items():
 if len(adj)!=2:continue
 (i,k),(j,m)=adj;a,c=segs[i],segs[j]
 w=float(atom(find(a,'width')[1]));ww=float(atom(find(c,'width')[1]))
 if abs(w-ww)>1e-6:continue
 ap=pos(find(a,'end' if k=='start' else 'start'));cp=pos(find(c,'end' if m=='start' else 'start'))
 va,vc=sub(ap,p),sub(cp,p);la,lc=length(va),length(vc)
 if min(la,lc)<.23:continue
 u,v=mul(va,1/la),mul(vc,1/lc);theta=math.acos(max(-1,min(1,u[0]*v[0]+u[1]*v[1])))
 if theta<math.radians(35) or theta>math.radians(160):continue
 d=min(.45/math.tan(theta/2),la*.28,lc*.28);r=d*math.tan(theta/2)
 if r<.06:continue
 aa,cc=add(p,mul(u,d)),add(p,mul(v,d));bis=add(u,v);centre=add(p,mul(bis,r/math.sin(theta/2)/length(bis)));mid=add(centre,mul(sub(p,centre),r/length(sub(p,centre))))
 angle1=math.atan2(aa[1]-centre[1],aa[0]-centre[0]);angle2=math.atan2(cc[1]-centre[1],cc[0]-centre[0]);delta=(angle2-angle1+math.pi)%(2*math.pi)-math.pi
 curve=LineString([(centre[0]+r*math.cos(angle1+delta*t/32),centre[1]+r*math.sin(angle1+delta*t/32)) for t in range(33)])
 copper=curve.buffer(w/2+.002);point=Point(p);lid=LS.index(layer);blocked=False
 ids={atom(find(a,'uuid')[1]),atom(find(c,'uuid')[1])}
 for ix in tree.query(copper.buffer(.26)):
  q,ll=meta[ix];g=shapes[ix]
  if lid not in ll:continue
  if q['net']==net:
   if q.get('id') not in ids and g.distance(point)<w/2+.025:blocked=True;break
  else:
   clr=.25 if q.get('through') and not q['net'] else (.2 if net in EC or q['net'] in EC else .15)
   if g.distance(copper)<max(clr,q.get('clearance',0))+.003:blocked=True;break
 if blocked:continue
 for ko in D['keepouts']:
  if ko['tracks'] and lid in ko['layers']:
   if any(copper.intersects(make_valid(Polygon(q[0],q[1:]))) for q in ko['polys']):blocked=True;break
 if blocked:continue
 setpos(find(a,k),aa);setpos(find(c,m),cc)
 uid=str(uuid.uuid4());arc=[Sym('arc'),[Sym('start'),*[Sym(f'{x:.6f}') for x in aa]],[Sym('mid'),*[Sym(f'{x:.6f}') for x in mid]],[Sym('end'),*[Sym(f'{x:.6f}') for x in cc]],[Sym('width'),Sym(str(w))],[Sym('layer'),('str',layer)],[Sym('net'),('str',net)],[Sym('uuid'),('str',uid)]]
 b.append(arc);count+=1;record.append({'arc':uid,'segments':list(ids),'radius':r,'net':net,'layer':layer})
Path(out).write_text(serialize(b)+'\n');Path(out+'.rounding.json').write_text(json.dumps(record,indent=2));print('Rounded',count,'corners')
