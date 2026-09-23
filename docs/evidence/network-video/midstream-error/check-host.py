import http.server,threading,subprocess,pathlib,tempfile,os,json,sys,time
repo=pathlib.Path(__file__).resolve().parents[4]
blob=pathlib.Path(sys.argv[1]).read_bytes()
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',str(len(blob)));self.end_headers()
  self.wfile.write(blob[:1343488] if self.server.truncate else blob);self.close_connection=True
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
report=[]
try:
 for truncate in (True,False):
  server.truncate=truncate
  with tempfile.TemporaryDirectory(prefix='k230-host-http-') as temp:
   root=pathlib.Path(temp);url=root/'source.playlist';url.write_text('http://127.0.0.1:%d/fixture.mp4\n'%server.server_port);url.chmod(0o600)
   shim=root/'mpv-null';shim.write_text('#!'+sys.executable+'\nimport os,sys\nos.execv("/usr/bin/mpv",["mpv","--speed=20",*("--vo=null" if a=="--vo=wlshm" else a for a in sys.argv[1:])])\n');shim.chmod(0o755)
   env=dict(os.environ,K230_VIDEO_PLAYER=str(shim),K230_VIDEO_RUNTIME_DIR=str(root),K230_VIDEO_PID_FILE=str(root/'state'),K230_VIDEO_LOG=str(root/'log'))
   before=time.monotonic();r=subprocess.run([sys.executable,str(repo/'nix/video-session.py'),'run','--url-file',str(url)],env=env,capture_output=True,text=True,timeout=20)
   row={'truncated':truncate,'exit':r.returncode,'seconds':round(time.monotonic()-before,3),'state_absent':not (root/'state').exists(),'playlist_absent':not url.exists(),'socket_absent':not list(root.glob('*.sock')),'private_log_empty':(root/'log').read_bytes()==b'','generic_error':r.stderr.strip()=='Video stream was interrupted before all data arrived; retry from Apps.'}
   assert r.returncode==(2 if truncate else 0),row
   assert all(row[k] for k in ('state_absent','playlist_absent','socket_absent','private_log_empty')),row
   assert row['generic_error']==truncate,row
   report.append(row)
finally:server.shutdown();server.server_close()
print(json.dumps({'scope':'host real mpv with null output and 20x speed; no board or sustained playback claim','trials':report},indent=2))
