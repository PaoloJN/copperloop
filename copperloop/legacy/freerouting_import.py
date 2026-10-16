# postroute.py <prepped.kicad_pcb> <session.ses> <out.kicad_pcb> [stitch]
import pcbnew, math, sys, json, subprocess, os
prepped,ses,out=sys.argv[1:4]; stitch=len(sys.argv)>4
mm=pcbnew.FromMM; tomm=pcbnew.ToMM; CX,CY=150.0,100.0
b=pcbnew.LoadBoard(prepped)
ok=pcbnew.ImportSpecctraSES(b,ses); print('ses import',ok)
gnd=b.FindNet('GND')
if stitch:
    poly=[(125.5,89.75),(137.3,89.75),(137.3,94.2),(127.9,94.2),(127.9,105.8),(137.3,105.8),(137.3,110.25),(125.5,110.25)]
    def inpoly(x,y):
        n=len(poly); inside=False
        for i in range(n):
            x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
            if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: inside=not inside
        return inside
    pads=[(tomm(p.GetPosition().x),tomm(p.GetPosition().y),max(tomm(p.GetSizeX()),tomm(p.GetSizeY()))/2,p.GetNetname()) for f in b.GetFootprints() for p in f.Pads()]
    segs=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK']
    vias=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA']
    def segdist(x,y,t):
        x1,y1,x2,y2=tomm(t.GetStart().x),tomm(t.GetStart().y),tomm(t.GetEnd().x),tomm(t.GetEnd().y)
        dx,dy=x2-x1,y2-y1; L=dx*dx+dy*dy
        u=0 if L==0 else max(0,min(1,((x-x1)*dx+(y-y1)*dy)/L))
        return math.hypot(x-(x1+u*dx),y-(y1+u*dy))-tomm(t.GetWidth())/2
    added=0
    for gx in range(-20,21):
        for gy in range(-20,21):
            x,y=CX+gx*4.0+ (2.0 if gy%2 else 0),CY+gy*3.5
            r=math.hypot(x-CX,y-CY)
            if r>21.3 or inpoly(x,y): continue
            a=math.degrees(math.atan2(-(y-CY),x-CX))
            if r>10 and -33<a<33: continue                      # EC sector (planes pulled back)
            if math.hypot(x-150,y-100)<6.2 or math.hypot(x-150,y-88.5)<6.2: continue   # FDC guard
            if x<144.8 and 94<y<106: continue                   # module body
            if any(math.hypot(x-px,y-py)<pr+0.75 for px,py,pr,pn in pads): continue
            if any(segdist(x,y,t)<0.55 for t in segs): continue
            if any(math.hypot(x-tomm(v.GetPosition().x),y-tomm(v.GetPosition().y))<1.0 for v in vias): continue
            v=pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(x),mm(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetDrill(mm(0.3)); v.SetWidth(mm(0.6)); v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); v.SetNet(gnd); b.Add(v); added+=1
    print('stitch vias added',added)
filler=pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
pcbnew.SaveBoard(out,b); print('saved',out)
