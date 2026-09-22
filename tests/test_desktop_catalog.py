import os,pathlib,subprocess,tempfile,unittest,time
ROOT=pathlib.Path(__file__).parents[1]; SRC=ROOT/'nix/touch-launcher/catalog.c'
class Catalog(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(); cls.bin=pathlib.Path(cls.tmp.name)/'catalog'
  subprocess.run(['cc','-O2','-o',str(cls.bin),str(SRC),*subprocess.check_output(['pkg-config','--cflags','--libs','gio-unix-2.0'],text=True).split()],check=True)
 def env(self,td):
  e=os.environ.copy(); e.update({'XDG_DATA_HOME':str(td/'home'), 'XDG_DATA_DIRS':str(td/'sys'), 'XDG_CURRENT_DESKTOP':'Sway', 'PATH':str(td/'bin')+':'+e['PATH']}); return e
 def entry(self,d,id,body):
  p=d/'applications';p.mkdir(parents=True,exist_ok=True);(p/(id+'.desktop')).write_text('[Desktop Entry]\nType=Application\n'+body)
 def test_visibility_precedence_and_refresh(self):
  with tempfile.TemporaryDirectory() as x:
   d=pathlib.Path(x); self.entry(d/'sys','same','Name=System\nExec=true\n');self.entry(d/'home','same','Name=Home\nExec=true\n');self.entry(d/'home','hidden','Name=Hide\nExec=true\nHidden=true\n');self.entry(d/'home','nodisplay','Name=No\nExec=true\nNoDisplay=true\n');self.entry(d/'home','try','Name=Try\nExec=true\nTryExec=does-not-exist\n');self.entry(d/'home','only','Name=Only\nExec=true\nOnlyShowIn=GNOME;\n')
   e=self.env(d); out=subprocess.check_output([self.bin,'list'],env=e,text=True)
   self.assertIn('same.desktop\tHome\t0',out); self.assertNotIn('hidden.desktop',out);self.assertNotIn('nodisplay.desktop',out);self.assertNotIn('try.desktop',out);self.assertNotIn('only.desktop',out)
   self.entry(d/'home','added','Name=Added\nExec=true\n');out=subprocess.check_output([self.bin,'list'],env=e,text=True);self.assertIn('added.desktop',out)
 def test_glib_launch_terminal_path_and_fields(self):
  with tempfile.TemporaryDirectory() as x:
   d=pathlib.Path(x); (d/'bin').mkdir(); log=d/'log'; app=d/'bin'/'app'; app.write_text('#!/bin/sh\nprintf "%s|%s|%s\\nDONE\n" "$PWD" "$0" "$*" >>"$LOG"\n');app.chmod(0o755)
   term=d/'bin'/'xdg-terminal-exec';term.write_text('#!/bin/sh\nprintf "term:%s\\n" "$*" >>"$LOG"\nexec "$@"\n');term.chmod(0o755)
   work=d/'work';work.mkdir(); self.entry(d/'home','quoted','Name=Quoted Name\nExec=app "two words" %c %k %% %f %i\nPath='+str(work)+'\nTerminal=true\n')
   e=self.env(d);e['LOG']=str(log); subprocess.run([self.bin,'launch','quoted.desktop'],env=e,check=True); 
   for _ in range(40):
    if log.exists() and 'DONE' in log.read_text(): break
    time.sleep(.05)
   data=log.read_text();self.assertIn('term:app two words Quoted Name',data);self.assertIn(str(work)+'|',data);self.assertIn('%',data);self.assertNotIn('%f',data)
if __name__=='__main__': unittest.main()
