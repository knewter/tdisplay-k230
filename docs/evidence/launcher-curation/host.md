# Curated Apps catalog: host fixtures

Evidence class: **host** (x86_64 compile of the production launcher sources
and GLib desktop provider against isolated XDG directories). No board,
panel, touch or cross-build is claimed. Recorded 2026-09-28T13:54Z on branch
`close/shell-umbrella`.

Change: `the-launcher-explains-app-actions`, tasks 1.1 and 1.2.

## What changed

- `nix/touch-launcher/catalog.c` holds a small curated policy table keyed by
  desktop-entry ID. `footclient.desktop` and `foot-server.desktop` are
  suppressed. `foot.desktop` ("Plain terminal") and `htop.desktop`
  ("Process viewer") duplicate the built-in Terminal and Monitor rows, so they
  are demoted after every other entry. Unknown entries are retained under
  their own name. Their description comes from `Comment=`, then
  `GenericName=`, then "Installed application".
  GLib still does discovery, `should_show` and launching. The launcher does
  not parse `Exec`.
- `nix/touch-launcher/touch-launcher.c` renders the curated label and hint
  instead of the fixed "Installed application" text. After a failed launch it
  shows `Could not open <label> · Back returns to Apps`. The raw GLib message,
  which can contain a filesystem path, goes only to stderr/journal.
- The built-in Terminal, Monitor, New terminal and Help rows are unchanged,
  and so are the footer Previous/Back/Next controls, which every Apps page
  draws.

## Commands and results

```
$ python3 tests/test_desktop_catalog.py -v
test_curation_applies_after_refresh ... ok
test_curation_suppresses_endpoints_demotes_duplicates_and_retains_unknown ... ok
test_escaped_names_do_not_break_catalogue_records ... ok
test_failed_launch_reports_short_copy_without_raw_path ... ok
test_glib_launch_preserves_argv_fields_and_working_directory ... ok
test_visibility_precedence_add_remove_and_hidden_override ... ok
Ran 6 tests — OK

$ python3 tests/test_launcher_navigation.py -v
test_threshold_dominance_cancellation_and_overview_bounds ... ok
A failed curated launch leaves the page model intact and Back usable. ... ok
test_help_return_page_bounds_and_desktop_action_indexes ... ok
Compile the production client helpers and exercise their child boundary. ... ok
Ran 4 tests — OK
```

The following suites also compile `touch-launcher.c` and still pass:
`tests/test_shell_routes.py` (route-socket), `tests/test_shell_gestures.py`,
`tests/test_shell_icons.py` (8) and `tests/test_shell_appearance_receiver.py`
(6).

## Limits

- The failed-launch fixture makes GLib's spawn fail with a missing `Path=`
  working directory. It checks that stdout carries only the short copy and
  no `/`, and that the raw diagnostic is on stderr.
- The Back route after a failure is tested in the page model
  (`navigation.h`). Its rendered visibility and 56 px target on the panel are
  not tested here. They belong to board task 2.2.
- `nix build .#touch-launcher` (task 2.1) has not been run. A dry run lists
  12 riscv64 derivations to build, including cairo, pango, librsvg and
  json-glib, and that needs the shared build slot.
