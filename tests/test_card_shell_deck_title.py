#!/usr/bin/env python3
"""Run the compositor's card-title policy, including private-title isolation."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeckTitle(unittest.TestCase):
    def test_managed_names_and_unmodified_other_titles(self):
        source = (ROOT / "nix/card-shell/adapter.c").read_text()
        start = source.index("static const char *card_display_title(")
        end = source.index("static bool snapshot(void) {", start)
        function = source[start:end]
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
enum cs_content { CS_UNAVAILABLE, CS_PRIVATE, CS_LIVE };
static const char *cs_card_text(enum cs_content content) {
    return content == CS_PRIVATE ? "Private app" : "Preview unavailable";
}
'''
        checks = r'''
int main(void) {
    assert(!strcmp(card_display_title(CS_LIVE, "shell@device", "k230-terminal", true), "Terminal"));
    assert(!strcmp(card_display_title(CS_LIVE, "htop", "k230-monitor", true), "Monitor"));
    assert(!strcmp(card_display_title(CS_LIVE, "nnn", "nnn", true), "Files"));
    assert(!strcmp(card_display_title(CS_LIVE, "mail to a@b", "mail", true), "mail to a@b"));
    assert(!strcmp(card_display_title(CS_LIVE, "shell@device", "other-terminal", true), "shell@device"));
    assert(!strcmp(card_display_title(CS_LIVE, "shell@device", "k230-terminal", false), "shell@device"));
    assert(!strcmp(card_display_title(CS_LIVE, NULL, "unknown", true), "Application"));
    assert(!strcmp(card_display_title(CS_PRIVATE, "secret@device", "k230-terminal", true), "Private app"));
    assert(!strcmp(card_display_title(CS_UNAVAILABLE, "hidden", "nnn", true), "Preview unavailable"));
}
'''
        with tempfile.TemporaryDirectory(prefix="card-title-") as directory:
            path = Path(directory)
            (path / "test.c").write_text(harness + function + checks)
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            str(path / "test.c"), "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True)


if __name__ == "__main__":
    unittest.main()
