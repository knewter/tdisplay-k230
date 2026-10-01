import serial,time,base64,json
from pathlib import Path
out=Path('/home/jadams/tmp/k230-coordination/files-collected');out.mkdir(exist_ok=True)
with serial.Serial('/dev/ttyACM0',115200,timeout=.2) as s:
 s.write(b'\r\n');s.flush();time.sleep(.5);s.reset_input_buffer()
 for name,path,kind in [('metrics','/root/tmp/k230-deployment/files-metrics-result.json','json'),('portfolio','/run/shell/files-portfolio.jpg','jpg'),('nautilus','/run/shell/files-nautilus.jpg','jpg')]:
  cmd="printf '\\nFILES_BEGIN_"+name+"\\n'; base64 "+path+"; printf '\\nFILES_END_"+name+"\\n'"
  s.write(cmd.encode()+b'\r\n');s.flush();buf=b'';deadline=time.monotonic()+25
  begin=b'\nFILES_BEGIN_'+name.encode()+b'\r\n';end=b'\r\nFILES_END_'+name.encode()+b'\r\n'
  while time.monotonic()<deadline:
   buf+=s.read(4096)
   if begin in buf and end in buf[buf.index(begin)+len(begin):]:break
  assert begin in buf and end in buf,'missing framed capture '+name
  encoded=buf.split(begin,1)[1].split(end,1)[0]
  data=base64.b64decode(b''.join(encoded.split()),validate=True)
  if kind=='jpg':assert data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9')
  else:json.loads(data)
  (out/(name+'.'+kind)).write_bytes(data);print(name,len(data))
