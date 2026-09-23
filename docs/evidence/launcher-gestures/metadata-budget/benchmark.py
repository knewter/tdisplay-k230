import json,pathlib,subprocess,time,sys
catalog='/nix/store/mz995n6k6f69rv9k8ffzmc9fifpmz851-k230-window-catalog/bin/k230-window-catalog'
sway='/nix/store/0dw6pla4d4qqyndk77mhahijjzv4g81v-sway-1.12/bin/swaymsg'
jq='/nix/store/fy9xmga7mbqqiqp6gaj79239a98ssy9g-jq-riscv64-unknown-linux-gnu-1.8.2-bin/bin/jq'
filter=pathlib.Path('/nix/store/s4b59gdnqx7hjz90cs1dx5gyxx9zw9yz-window-catalog.sh').read_text().split(" -r '",1)[1].rsplit("'",1)[0]
tree=subprocess.check_output([sway,'-t','get_tree','-r'],timeout=2)
result={}
for condition in ['idle','synthetic-one-busy-process']:
 load=subprocess.Popen([sys.executable,'-c','while True: pass']) if condition!='idle' else None
 try:
  result[condition]={}
  for kind,cmd,data in [('catalog',[catalog],None),('sway-ipc',[sway,'-t','get_tree','-r'],None),('jq',[jq,'-r',filter],tree)]:
   samples=[]
   for i in range(20):
    t=time.monotonic();p=subprocess.run(cmd,input=data,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=3)
    samples.append({'ms':round((time.monotonic()-t)*1000,3),'exit':p.returncode})
   result[condition][kind]=samples
 finally:
  if load is not None:load.terminate();load.wait(timeout=2)
pathlib.Path('/run/catalog-benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
print('CATALOG_BENCHMARK_DONE')
