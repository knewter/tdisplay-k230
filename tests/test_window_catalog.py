"""Exercise real jq metadata parsing, including hostile titles and IPC failure."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'nix/window-catalog.sh'


class WindowCatalog(unittest.TestCase):
    def invoke(self, tree, failed=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tree').write_text(json.dumps(tree))
            helper = root / 'swaymsg'
            helper.write_text('#!/bin/sh\n' + ('exit 1\n' if failed else 'cat "$FIXTURE_TREE"\n'))
            helper.chmod(0o755)
            return subprocess.run(['bash', str(SCRIPT)], capture_output=True, text=True,
                                  env=os.environ | {'K230_SWAYMSG': str(helper),
                                                    'FIXTURE_TREE': str(root / 'tree')})

    def test_nested_floating_and_xwayland_windows(self):
        tree = {'type': 'root', 'nodes': [{'type': 'workspace', 'nodes': [
            {'type': 'con', 'id': 42, 'app_id': 'foot', 'name': 'tab\tline\n$(echo nope)', 'focused': True},
            {'type': 'con', 'id': 43, 'pid': 200, 'name': 'untitled'},
            {'type': 'con', 'id': 44, 'nodes': [{'type': 'con', 'id': 45, 'app_id': 'nested', 'name': 'Nested'}]},
        ], 'floating_nodes': [{'type': 'floating_con', 'id': 46, 'nodes': [
            {'type': 'con', 'id': 47, 'window': 1, 'window_properties': {'class': 'XApp'},
             'name': 'X11', 'urgent': True, 'fullscreen_mode': 1}]}]}]}
        result = self.invoke(tree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            '42\ttab line $(echo nope)\tfoot\tfocused', '43\tuntitled\t\tnormal',
            '45\tNested\tnested\tnormal', '47\tX11\tXApp\turgent,fullscreen'])

    def test_empty_tree_is_success_but_invalid_tree_and_ipc_failure_are_not(self):
        result = self.invoke({'type': 'root', 'nodes': []})
        self.assertEqual((result.returncode, result.stdout), (0, ''))
        self.assertNotEqual(self.invoke([]).returncode, 0)
        self.assertNotEqual(self.invoke({'type': 'root'}, failed=True).returncode, 0)

    def test_invalid_ids_are_not_focus_targets(self):
        result = self.invoke({'type': 'root', 'nodes': [
            {'type': 'con', 'id': value, 'app_id': 'foot'}
            for value in ('42] exec nope', -1, 0, 1.5, None)]})
        self.assertEqual((result.returncode, result.stdout), (0, ''))


if __name__ == '__main__':
    unittest.main()
