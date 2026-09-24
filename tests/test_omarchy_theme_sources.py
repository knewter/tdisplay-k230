"""Source fixture acquisition and unchanged-checkout host gates."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import theme_sources as sources  # noqa: E402


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def create_repo(path, *, builtins):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if builtins:
        for name, mode in (("catppuccin", "dark"), ("catppuccin-latte", "light")):
            theme = path / "themes" / name
            theme.mkdir(parents=True)
            (theme / "colors.toml").write_text(f'mode = "{mode}"\nbackground = "#101820"\n')
            (theme / "backgrounds").mkdir()
            (theme / "backgrounds" / "sample.png").write_bytes(b"synthetic fixture")
    else:
        (path / "colors.toml").write_text('accent = "#123456"\n')
        (path / "shell.menu.toml").write_text('[menu]\nbackground = "#abcdef"\n')
    git(path, "add", ".")
    subprocess.run(["git", "-C", str(path), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
    return git(path, "rev-parse", "HEAD")


class ThemeSources(unittest.TestCase):
    def test_exact_revision_acquisition_and_source_immutability(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            upstream, community = base / "upstream", base / "community-source"
            up_rev = create_repo(upstream, builtins=True)
            community_rev = create_repo(community, builtins=False)
            before = (git(upstream, "status", "--porcelain"), git(community, "status", "--porcelain"))
            result = sources.acquire(base / "fixtures", upstream_url=str(upstream), upstream_rev=up_rev,
                                     community_url=str(community), community_rev=community_rev)
            self.assertEqual({x["revision"] for x in result.values()}, {up_rev, community_rev})
            self.assertEqual([x["git_layout"] for x in result.values()], ["directory"] * 3)
            self.assertEqual(before, (git(upstream, "status", "--porcelain"),
                                      git(community, "status", "--porcelain")))
            self.assertEqual(git(base / "fixtures/builtins", "status", "--porcelain"), "")
            self.assertEqual(git(base / "fixtures/community", "status", "--porcelain"), "")
            self.assertNotEqual(result["dark"]["sha256"], result["light"]["sha256"])
            self.assertTrue((base / "fixtures/community/shell.menu.toml").is_file())
            with self.assertRaises(FileExistsError):
                sources.acquire(base / "fixtures", upstream_url=str(upstream), upstream_rev=up_rev,
                                community_url=str(community), community_rev=community_rev)

    def test_git_directory_git_file_and_no_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            repo = base / "repo"
            rev = create_repo(repo, builtins=False)
            worktree = base / "worktree"
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", "-q",
                            str(worktree), rev], check=True)
            plain = base / "plain"
            shutil.copytree(repo, plain, ignore=shutil.ignore_patterns(".git"))
            snapshots = [sources.inspect(path) for path in (repo, worktree, plain)]
            self.assertEqual([x["git_layout"] for x in snapshots], ["directory", "file", "absent"])
            self.assertEqual([x["revision"] for x in snapshots], [rev, rev, None])
            self.assertEqual(len({x["sha256"] for x in snapshots}), 1)
            self.assertEqual(git(repo, "status", "--porcelain"), "")
            self.assertEqual(git(worktree, "status", "--porcelain"), "")

    def test_path_boundaries_and_content_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            collection = base / "collection"
            create_repo(collection, builtins=True)
            first = sources.inspect(collection, "catppuccin")["sha256"]
            with self.assertRaises(ValueError):
                sources.source_dir(collection, "../catppuccin")
            outsider = base / "outsider"
            outsider.mkdir()
            (outsider / "colors.toml").write_text('background = "#000000"\n')
            (collection / "themes" / "escaped").symlink_to(outsider)
            with self.assertRaises(ValueError):
                sources.source_dir(collection, "escaped")
            (collection / "themes/catppuccin/colors.toml").write_text('background = "#ffffff"\n')
            self.assertNotEqual(first, sources.inspect(collection, "catppuccin")["sha256"])


if __name__ == "__main__":
    unittest.main()
