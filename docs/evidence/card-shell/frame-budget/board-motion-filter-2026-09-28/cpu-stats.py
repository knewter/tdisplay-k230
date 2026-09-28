import re,sys
for fn in sys.argv[1:]:
    v=sorted(int(m.group(1))/1e6 for line in open(fn,errors="replace") for m in [re.search(r"event=submit .*update_cpu_ns=(\d+)",line)] if m)
    p=lambda q: v[min(len(v)-1,int(q*len(v)))]
    over=sum(1 for x in v if x>19.161)
    print("%s frame-update CPU n=%d p50=%.1f p90=%.1f p95=%.1f max=%.1f ms; over 19.16ms: %d (%.0f%%)"%(fn.split('/')[-1],len(v),p(.5),p(.9),p(.95),v[-1],over,100*over/len(v)))
