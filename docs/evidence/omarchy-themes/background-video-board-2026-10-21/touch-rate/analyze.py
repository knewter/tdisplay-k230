import sys,statistics as st
rows=[tuple(map(int,l.split())) for l in open(sys.argv[1])]
down=False; strokes=[]; cur=None; moved=False; allsyn=[]
for t,ty,c,v in rows:
    if ty==1 and c==330:
        if v: down=True; cur=[]
        else:
            down=False
            if cur: strokes.append(cur)
            cur=None
    elif ty==3 and c in (53,54,0,1): moved=True
    elif ty==0 and c==0:
        if down: allsyn.append(t)
        if down and moved: cur.append(t)
        moved=False
pct=lambda q,f:q[max(0,int(len(q)*f+.999)-1)]
print('strokes',len(strokes))
allg=[]
for s in strokes:
    g=sorted((b-a)/1000 for a,b in zip(s,s[1:]))
    allg+=g
    if g: print(' reports %3d dur %5d ms median %.2f p95 %.2f max %.1f'%(len(s),(s[-1]-s[0])/1000,st.median(g),pct(g,.95),g[-1]))
q=sorted(allg)
if q: print('ALL moving-report gaps n',len(q),'median %.3f mean %.3f p5 %.2f p95 %.2f'%(st.median(q),st.mean(q),pct(q,.05),pct(q,.95)))
