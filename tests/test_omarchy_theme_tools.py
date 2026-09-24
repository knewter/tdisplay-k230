"""Check the pinned helper copy and the three-path staging patch on the host."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "nix/omarchy-theme-tools"
UPSTREAM = TOOLS / "upstream"
PATCHED = UPSTREAM / "bin/omarchy-theme-set-templates"
ORIGINAL_LINES = {
    'TEMPLATES_DIR="${OMARCHY_THEME_TEMPLATES_DIR:-$OMARCHY_PATH/default/themed}"':
        'TEMPLATES_DIR="$OMARCHY_PATH/default/themed"',
    'USER_TEMPLATES_DIR="${OMARCHY_THEME_USER_TEMPLATES_DIR:-$HOME/.config/omarchy/themed}"':
        'USER_TEMPLATES_DIR="$HOME/.config/omarchy/themed"',
    'NEXT_THEME_DIR="${OMARCHY_THEME_STAGING_DIR:-$HOME/.local/state/omarchy/current/next-theme}"':
        'NEXT_THEME_DIR="$HOME/.local/state/omarchy/current/next-theme"',
}


def original_script():
    content = PATCHED.read_text()
    for replacement, original in ORIGINAL_LINES.items():
        assert content.count(replacement) == 1
        content = content.replace(replacement, original)
    return content.encode()


def tree_bytes(path):
    return {p.relative_to(path).as_posix(): p.read_bytes()
            for p in path.rglob("*") if p.is_file()}


class PinnedHelpers(unittest.TestCase):
    def test_upstream_byte_manifest_except_documented_patch(self):
        lines = (TOOLS / "SHA256SUMS.upstream").read_text().splitlines()
        self.assertGreater(len(lines), 15)
        visited = set()
        for line in lines:
            match = re.fullmatch(r"([0-9a-f]{64})  (nix/omarchy-theme-tools/upstream/.+)", line)
            self.assertIsNotNone(match, line)
            digest, name = match.groups()
            self.assertNotIn(name, visited)
            visited.add(name)
            actual = original_script() if name.endswith("/omarchy-theme-set-templates") else (ROOT / name).read_bytes()
            self.assertEqual(hashlib.sha256(actual).hexdigest(), digest, name)
        self.assertEqual(set(p.relative_to(ROOT).as_posix() for p in UPSTREAM.rglob("*") if p.is_file()), visited)

    def test_template_output_matches_original_with_isolated_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = base / "original"
            patched = base / "patched"
            old_home = base / "isolated-original-home"
            old_stage = old_home / ".local/state/omarchy/current/next-theme"
            new_stage = base / "isolated-patched-stage"
            for stage in (old_stage, new_stage):
                stage.mkdir(parents=True)
                (stage / "colors.toml").write_text(
                    'background = "#101820"\nforeground = "#e0e5e8"\n'
                    'accent = "#5ba8b5"\nred = "#d86666"\nblue = "#6389d8"\n'
                    'selection_foreground = "#000000"\nmode = "dark"\n'
                )
                (stage / "shell.menu.toml").write_text('[menu]\nbackground = "#123456"\n')
            original.write_bytes(original_script())
            patched.write_bytes(PATCHED.read_bytes())
            # The upstream helper's legacy path is confined to a disposable
            # subprocess home; production always supplies explicit stage paths.
            empty = base / "empty-user-templates"
            empty.mkdir()
            old_env = os.environ | {"HOME": str(old_home), "OMARCHY_PATH": str(UPSTREAM),
                                    "PATH": str(UPSTREAM / "bin") + os.pathsep + os.environ["PATH"]}
            new_env = os.environ | {"OMARCHY_PATH": str(UPSTREAM),
                                    "OMARCHY_THEME_TEMPLATES_DIR": str(UPSTREAM / "default/themed"),
                                    "OMARCHY_THEME_USER_TEMPLATES_DIR": str(empty),
                                    "OMARCHY_THEME_STAGING_DIR": str(new_stage),
                                    "PATH": str(UPSTREAM / "bin") + os.pathsep + os.environ["PATH"]}
            subprocess.run(["bash", str(original)], env=old_env, check=True)
            subprocess.run(["bash", str(patched)], env=new_env, check=True)
            self.assertEqual(tree_bytes(old_stage), tree_bytes(new_stage))
            self.assertIn(b'background = "#123456"', (new_stage / "shell.toml").read_bytes())


if __name__ == "__main__":
    unittest.main()
