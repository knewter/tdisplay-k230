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
        # The card header now resolves app_id -> .desktop Name= (finding
        # P0-1), so the extracted slice must include that whole helper
        # chain, not just card_display_title itself.
        start = source.index("#define DESKTOP_IDENTITY_CACHE_MAX")
        end = source.index("static bool snapshot(void) {", start)
        function = source[start:end]
        harness = r'''
#include <assert.h>
#include <dirent.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
enum cs_content { CS_UNAVAILABLE, CS_PRIVATE, CS_LIVE };
static const char *cs_card_text(enum cs_content content) {
    return content == CS_PRIVATE ? "Private app" : "Preview unavailable";
}
'''
        checks = r'''
static const char *title(enum cs_content content, const char *raw_title,
        const char *app_id, bool compact) {
    static char buf[128];
    return card_display_title(content, raw_title, app_id, compact, buf, sizeof(buf));
}
int main(void) {
    /* No XDG_DATA_DIRS entry here actually ships a k230-terminal/
     * k230-monitor/nnn StartupWMClass, so these fall through to the
     * hardcoded safety-net names -- the same names desktop_identity_name()
     * resolves for real once XDG_DATA_DIRS points at the installed image's
     * applications/ directories (see handheld-desktop-entries.nix). */
    unsetenv("XDG_DATA_DIRS");
    assert(!strcmp(title(CS_LIVE, "shell@device", "k230-terminal", true), "Terminal"));
    assert(!strcmp(title(CS_LIVE, "htop", "k230-monitor", true), "Monitor"));
    assert(!strcmp(title(CS_LIVE, "nnn", "nnn", true), "Files"));
    assert(!strcmp(title(CS_LIVE, "mail to a@b", "mail", true), "mail to a@b"));
    assert(!strcmp(title(CS_LIVE, "shell@device", "other-terminal", true), "shell@device"));
    assert(!strcmp(title(CS_LIVE, "shell@device", "k230-terminal", false), "shell@device"));
    assert(!strcmp(title(CS_LIVE, NULL, "unknown", true), "Application"));
    assert(!strcmp(title(CS_PRIVATE, "secret@device", "k230-terminal", true), "Private app"));
    assert(!strcmp(title(CS_UNAVAILABLE, "hidden", "nnn", true), "Preview unavailable"));
    /* The header badge glyph (finding P0-1): the resolved title's own first
     * letter, uppercased, matching the drawer's fallback-initial treatment. */
    assert(card_badge_letter("Terminal") == 'T');
    assert(card_badge_letter("monitor") == 'M');
    assert(card_badge_letter("") == '?');
    assert(card_badge_letter(NULL) == '?');
    /* A real .desktop match beats the raw window title even for an app_id
     * outside the 3-entry hardcoded map (the actual P0-1 bug: unmapped
     * app_ids used to always show the live, changing window title). */
    char tmp[] = "/tmp/card-title-desktop-XXXXXX";
    char *dir = mkdtemp(tmp);
    assert(dir);
    /* `dir` is a fixed-length mkdtemp() template in practice, but GCC sees
     * only `char *` and assumes the worst case for -Wformat-truncation,
     * exactly like the identical false positive in adapter.c's own
     * resolve_desktop_name(). */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wformat-truncation"
    char appdir[PATH_MAX];
    snprintf(appdir, sizeof(appdir), "%s/applications", dir);
    assert(mkdir(appdir, 0700) == 0);
    char entry_path[PATH_MAX];
    snprintf(entry_path, sizeof(entry_path), "%s/example.desktop", appdir);
#pragma GCC diagnostic pop
    FILE *entry = fopen(entry_path, "w");
    assert(entry);
    fprintf(entry, "[Desktop Entry]\nName=Example App\nIcon=example\nStartupWMClass=k230-example\n");
    fclose(entry);
    setenv("XDG_DATA_DIRS", dir, 1);
    assert(!strcmp(title(CS_LIVE, "shell@device: ~", "k230-example", true), "Example App"));
    /* Cached: a second call for the same app_id must not rescan the
     * directory (the whole point of the bounded cache), so even removing
     * the file still returns the cached name. */
    assert(remove(entry_path) == 0);
    assert(!strcmp(title(CS_LIVE, "shell@device: ~", "k230-example", true), "Example App"));
    assert(rmdir(appdir) == 0);
    assert(rmdir(dir) == 0);
}
'''
        with tempfile.TemporaryDirectory(prefix="card-title-") as directory:
            path = Path(directory)
            (path / "test.c").write_text(harness + function + checks)
            subprocess.run(["cc", "-std=c11", "-D_DEFAULT_SOURCE", "-Wall", "-Wextra", "-Werror",
                            str(path / "test.c"), "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True)


if __name__ == "__main__":
    unittest.main()
