"""Host catalog/transaction integration; no decoded image or physical UI proof."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import theme_catalog as catalog
from theme_sources import source_digest
from theme_transaction import activate_generation, TransactionError


COLORS = ('background="#101820"\nforeground="#e0e5e8"\naccent="#778899"\n'
          'red="#dd5555"\ngreen="#55dd55"\nyellow="#dddd55"\n'
          'blue="#5555dd"\nmagenta="#dd55dd"\ncyan="#55dddd"\nmode="dark"\n')


def theme(path):
    path.mkdir(parents=True)
    (path / "colors.toml").write_text(COLORS)
    (path / "backgrounds").mkdir()
    (path / "backgrounds/portrait.png").write_bytes(b"not decoded in this test")
    (path / "backgrounds/other.jpg").write_bytes(b"not decoded either")
    (path / "backgrounds/video.mp4").write_bytes(b"no video playback claim")
    return path


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.user, self.builtins, self.state = [self.base / name for name in ("user", "builtins", "state")]

    def entries(self):
        return catalog.discover(self.user, self.builtins)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = catalog.main(["--user-themes", str(self.user), "--builtins", str(self.builtins),
                                   "--state-root", str(self.state), "--socket", str(self.base / "missing.sock"),
                                   *args])
        return status, json.loads(out.getvalue() if status == 0 else err.getvalue())

    def test_discovery_is_metadata_only_stable_and_keeps_duplicate_origins(self):
        first = theme(self.user / "catppuccin")
        theme(self.builtins / "catppuccin")
        member = theme(self.user / "omarchy/themes/day")
        (self.user / "omarchy/.git").write_text("gitdir: fixture-only\n")
        (self.user / "linked").symlink_to(first, target_is_directory=True)
        with mock.patch.object(catalog.activation, "prepare", side_effect=AssertionError("eager prepare")):
            entries = self.entries()
        self.assertEqual(len(entries), 3)
        self.assertEqual(len({entry.id for entry in entries}), 3)
        self.assertEqual(next(entry.source for entry in entries if entry.name == "day"), member)
        identities = [entry.id for entry in entries]
        (first / "colors.toml").write_text("temporarily invalid palette")
        self.assertEqual([entry.id for entry in self.entries()], identities)
        self.assertFalse(self.state.exists())

    def test_preview_asset_prefers_own_image_then_first_still_background(self):
        with_own_preview = theme(self.user / "aurora")
        (with_own_preview / "preview.png").write_bytes(b"not decoded in this test")
        without_preview = theme(self.user / "borealis")
        colorless = self.user / "colorless"
        colorless.mkdir()
        (colorless / "colors.toml").write_text(COLORS)
        entries = {entry.name: entry for entry in self.entries()}
        self.assertEqual(entries["aurora"].preview_path, with_own_preview / "preview.png")
        # No preview.* ships for "borealis"; the first still background sorts
        # ahead of the later still and the video this project cannot decode,
        # matching the representative-thumbnail fallback.
        self.assertEqual(entries["borealis"].preview_path, without_preview / "backgrounds/other.jpg")
        self.assertIsNone(entries["colorless"].preview_path)
        _, listing = self.run_cli("list", "--json")
        by_name = {row["name"]: row for row in listing["themes"]}
        self.assertEqual(by_name["aurora"]["preview_path"], str(with_own_preview / "preview.png"))
        self.assertEqual(by_name["borealis"]["preview_path"],
                         str(without_preview / "backgrounds/other.jpg"))
        self.assertIsNone(by_name["colorless"]["preview_path"])

    def test_bounds_include_ignored_directory_entries(self):
        self.user.mkdir()
        for index in range(4):
            (self.user / f"file{index}").touch()
        with mock.patch.object(catalog, "MAX_ENTRIES", 3):
            with self.assertRaisesRegex(catalog.activation.ThemeError, "entry bound"):
                self.entries()

    def test_preview_is_staged_cancellable_and_preserves_source(self):
        source = theme(self.user / "night")
        before = source_digest(source)
        entry = self.entries()[0]
        status, result = self.run_cli("preview", entry.id, "--json")
        self.assertEqual(status, 0, result)
        self.assertFalse(result["activated"])
        self.assertFalse((self.state / "active").exists())
        self.assertEqual(source_digest(source), before)
        self.assertEqual(len(result["backgrounds"]), 3)
        self.assertEqual({asset["kind"] for asset in result["backgrounds"]}, {"image", "video"})
        for asset in result["backgrounds"]:
            self.assertEqual(asset["decode_status"], "unverified")
            self.assertTrue(Path(asset["path"]).is_relative_to(self.state / "generations"))
        source.rename(self.base / "removed")
        self.assertTrue(all(Path(asset["path"]).is_file() for asset in result["backgrounds"]))

    def test_opaque_background_choice_and_stale_generation_rejection(self):
        source = theme(self.user / "night")
        entry = self.entries()[0]
        _, initial = self.run_cli("preview", entry.id)
        image = next(asset for asset in initial["backgrounds"] if asset["label"] == "portrait.png")
        status, chosen = self.run_cli("preview", entry.id, "--background", image["id"])
        self.assertEqual(status, 0, chosen)
        self.assertEqual([asset["id"] for asset in chosen["backgrounds"] if asset["selected"]], [image["id"]])
        self.assertNotEqual(initial["generation"], chosen["generation"])
        status, _ = self.run_cli("preview", entry.id, "--background", "../../outside.png")
        self.assertEqual(status, 1)
        (source / "colors.toml").write_text(COLORS.replace("#101820", "#202830"))
        with mock.patch.object(catalog, "activate_generation") as activate:
            status, result = self.run_cli("activate", entry.id, "--expected-generation", initial["generation"])
        self.assertEqual(status, 1)
        self.assertIn("changed since preview", result["error"])
        activate.assert_not_called()

    def test_activation_requires_receiver_and_acknowledged_commit(self):
        theme(self.user / "night")
        entry = self.entries()[0]
        _, candidate = self.run_cli("preview", entry.id)
        args = ("activate", entry.id, "--expected-generation", candidate["generation"])
        status, result = self.run_cli(*args)
        self.assertEqual(status, 1)
        self.assertFalse(result["activated"])
        self.assertFalse((self.state / "active").exists())
        phases = []

        def transport(endpoint, phase, generation):
            phases.append(phase)

        def commit(generation, **kwargs):
            activate_generation(generation, **kwargs, transport=transport)

        with mock.patch.object(catalog, "activate_generation", side_effect=commit):
            status, result = self.run_cli(*args)
        self.assertEqual(status, 0, result)
        self.assertTrue(result["activated"])
        self.assertEqual(phases, ["prepare", "commit"])
        status, listing = self.run_cli("list", "--json")
        self.assertEqual(listing["active"], {"id": entry.id, "generation": candidate["generation"]})

    def test_commit_failure_rolls_back_and_reports_failure(self):
        source = theme(self.user / "night")
        entry = self.entries()[0]
        generation, report = catalog.prepare_entry(entry, state_root=self.state, tools=catalog.activation.HOST_TOOLS)
        activate_generation(generation, state_root=self.state, endpoint=self.base / "unused",
                            transport=lambda *args: None)
        (source / "colors.toml").write_text(COLORS.replace("#101820", "#202830"))
        _, candidate = self.run_cli("preview", entry.id)

        def reject_commit(endpoint, phase, generation):
            if phase == "commit":
                raise TransactionError("test rejection")

        def commit(generation, **kwargs):
            activate_generation(generation, **kwargs, transport=reject_commit)

        with mock.patch.object(catalog, "activate_generation", side_effect=commit):
            status, result = self.run_cli("activate", entry.id, "--expected-generation", candidate["generation"])
        self.assertEqual(status, 1)
        self.assertIn("previous generation restored", result["error"])
        self.assertEqual((self.state / "active").resolve(), generation)

    def test_catalog_explicit_choice_is_reused_by_both_entry_points(self):
        source = theme(self.user / "night")
        entry = self.entries()[0]
        _, first = self.run_cli("preview", entry.id)
        choice = next(asset for asset in first["backgrounds"] if asset["label"] == "portrait.png")
        _, chosen = self.run_cli("preview", entry.id, "--background", choice["id"])

        def commit(generation, **kwargs):
            activate_generation(generation, **kwargs, transport=lambda *_: None)

        with mock.patch.object(catalog, "activate_generation", side_effect=commit):
            status, applied = self.run_cli("activate", entry.id,
                                           "--background", choice["id"],
                                           "--expected-generation", chosen["generation"])
        self.assertEqual(status, 0, applied)
        _, remembered = self.run_cli("preview", entry.id)
        self.assertEqual(remembered["generation"], chosen["generation"])
        self.assertEqual([asset["id"] for asset in remembered["backgrounds"] if asset["selected"]],
                         [choice["id"]])
        # The compatible omarchy-theme-set path reads the same persisted choice.
        direct, report = catalog.activation.prepare(
            "night", source=source, state_root=self.state,
            user_themes=self.user, builtins=None, tools=catalog.activation.HOST_TOOLS)
        self.assertEqual(direct.name, chosen["generation"])
        self.assertEqual(report["selected_background"], "backgrounds/portrait.png")

    def test_invalid_removed_theme_and_symlink_asset_are_rejected(self):
        source = theme(self.user / "night")
        entry = self.entries()[0]
        self.assertEqual(self.run_cli("preview", "../../escape")[0], 1)
        (source / "backgrounds/leak.png").symlink_to(self.base / "outside")
        self.assertEqual(self.run_cli("preview", entry.id)[0], 1)
        source.rename(self.base / "removed")
        status, result = self.run_cli("preview", entry.id)
        self.assertEqual(status, 1)
        self.assertIn("no longer", result["error"])

    def test_fresh_home_lists_without_creating_state(self):
        status, listing = self.run_cli("list", "--json")
        self.assertEqual(status, 0)
        self.assertEqual(listing, {"schema": 1, "themes": [], "active": {"id": None, "generation": None}})
        self.assertFalse(self.state.exists())

    def preview_with_sockets(self, entry_id, *, prepare_only_effect=None):
        args = ["--user-themes", str(self.user), "--builtins", str(self.builtins),
                "--state-root", str(self.state), "--socket", str(self.base / "missing.sock"),
                "--rust-socket", str(self.base / "rust.sock"),
                "--deck-socket", str(self.base / "deck.sock"),
                "preview", entry_id]
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(
                catalog, "prepare_only", side_effect=prepare_only_effect) as prepared:
            status = catalog.main(args)
        return status, json.loads(out.getvalue()), prepared

    def test_preview_warms_the_wallpaper_cache_when_endpoints_are_configured(self):
        """Browsing (preview) should hint both receivers' Prepare-phase
        state for the candidate, so a later Apply of the *same* selection
        commits against an already-decoded buffer -- see
        tools/theme_transaction.py's prepare_only()."""
        theme(self.user / "night")
        entry = self.entries()[0]
        status, result, prepared = self.preview_with_sockets(entry.id)
        self.assertEqual(status, 0)
        prepared.assert_called_once()
        (generation,), kwargs = prepared.call_args
        self.assertEqual(generation.name, result["generation"])
        self.assertEqual(kwargs["endpoints"], (self.base / "rust.sock", self.base / "deck.sock"))

    def test_preview_survives_a_warm_up_transport_failure(self):
        theme(self.user / "night")
        entry = self.entries()[0]
        status, result, prepared = self.preview_with_sockets(
            entry.id, prepare_only_effect=TransactionError("receiver unreachable"))
        self.assertEqual(status, 0)
        prepared.assert_called_once()
        self.assertIn("generation", result)

    def test_preview_does_not_warm_without_rust_socket_configured(self):
        theme(self.user / "night")
        entry = self.entries()[0]
        with mock.patch.object(catalog, "prepare_only",
                              side_effect=AssertionError("should not be called")):
            status, _ = self.run_cli("preview", entry.id)
        self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
