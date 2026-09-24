"""Check generated runtime paths against the actual session guard contract."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

runner=load('repaint_runner','docs/evidence/card-shell/repaint-stages/run-board.py')
session=load('repaint_session','tools/card-shell-board-session.py')

class RuntimeContractTests(unittest.TestCase):
    def test_distinct_sessions_satisfy_real_guard_and_socket_length(self):
        paths=set()
        for output in ('/var/lib/k230/card-repaint-stages-one',
                       '/var/lib/k230/card-repaint-stages-two',
                       '/var/lib/k230/card-repaint-stages-'+('a'*200)):
            for index in (1,2):
                path=runner.runtime_directory(output,index)
                self.assertIsNotNone(session.RUNTIME_PATH.fullmatch(str(path)))
                self.assertLess(len(str(path/'wayland/sway-ipc.sock').encode()),108)
                self.assertNotIn(path,paths)
                paths.add(path)

    def test_old_bad_prefix_remains_rejected(self):
        self.assertIsNone(session.RUNTIME_PATH.fullmatch('/run/k230-card-repaint-0123456789abcdef-1'))

if __name__=='__main__':unittest.main()
