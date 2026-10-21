# Board-side: record raw Goodix input_event timestamps for a fixed window.
import os,struct,sys,time,select,glob,json
dur=float(sys.argv[1]); out=sys.argv[2]
dev=None
for d in sorted(glob.glob('/sys/class/input/event*')):
    if 'Goodix' in open(d+'/device/name').read(): dev='/dev/input/'+os.path.basename(d)
fd=os.open(dev,os.O_RDONLY|os.O_NONBLOCK); rows=[]; end=time.monotonic()+dur
print(json.dumps({'device':dev,'armed_monotonic':time.monotonic(),'seconds':dur}),flush=True)
while time.monotonic()<end:
    r,_,_=select.select([fd],[],[],0.5)
    if not r: continue
    data=os.read(fd,24*256)
    for i in range(0,len(data),24):
        s,us,t,c,v=struct.unpack('qqHHi',data[i:i+24]); rows.append((s*1_000_000+us,t,c,v))
with open(out,'w') as f:
    for r in rows: f.write('%d %d %d %d\n'%r)
print(json.dumps({'events':len(rows),'out':out}),flush=True)
