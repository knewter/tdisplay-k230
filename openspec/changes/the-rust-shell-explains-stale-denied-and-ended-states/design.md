## Context
Layer: userspace (Rust shell client, built as `.#handheld-shell-rust`). The contract lives in `src/recovery.rs` (state IDs, copy, recovery action, `person_safe` guard). Audit of where each state is rendered (2026-10-11, source reading, not a board observation):

- Window list: the per-app menu (`app_actions::AppMenu`, drawn by `render::draw_app_menu`) is the Rust shell's window list. Loading showed "Loading app actions…" with no visible way out; a ready menu with no open window said nothing; a window that vanished before focus fell through to the generic "Couldn't open <Name>" launch splash.
- Denied/failed system action: `service_ui::action_message` rendered the helper's raw code (`action-denied`, `brightness-denied`, `target-unavailable · try again`), and submit/outcome failures rendered raw worker error strings.
- Video Stop/EOF/cancelled: no Rust shell surface. The Video app is `nix/video-session.py` running mpv inside a terminal, and that window closes when playback stops, ends or is cancelled. The shell's own `VideoPlayback` is wallpaper video only.

## Decisions
- Define state IDs and short copy keys for loading, empty, stale, denied action, Stop, EOF, cancelled; each names one available Back, Apps, Home, Retry, Cancel, or Stop action.
- Raw paths, helper diagnostics, and secrets reach logs only.
- Stale means the focused target vanished; the shell must not focus a different window silently. It gets its own splash status (`SplashStatus::Stale`, "That window has closed · Tap for Apps") that waits for a tap and opens Apps.
- A message names the surface's own visible exit control: Settings' "Done", Power's "Cancel"; a retryable failure names Retry (tap the same control again).
- Video ended-state copy is defined in the contract, but rendering it needs a decision on ownership. Either the session keeps its window open with the copy, or the shell observes the session's end. Task 1.3 tracks it.

## Rejected
- Modal error stack or global notification system: outside scope.
- Porting changes to touch-launcher: it is unreachable under the coherent shell.
- Home disclosure: see proposal.
