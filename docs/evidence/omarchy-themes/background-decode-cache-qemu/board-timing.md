# Wallpaper decode cache: board timing

Observed 2026-09-24 about 23:15 UTC. **Evidence class:** installed system on
the reserved board, with shell-user `k230-theme` commands timed over the
serial console. No camera was used and nothing was touched by a finger.

- **System:** `/nix/store/8apcw30v99la98j0pdzqpyz3p7ixhqx3-nixos-system-nixos-26.11.20260919.20b1ddd`
  (`master` `aab56856`).
- **Install:** guarded `switch-to-configuration test`. The rollback timer was
  stopped after a healthy native frame.

| Round | Theme | Generation has `background.cache` | preview | activate | Result |
| --- | --- | --- | ---: | ---: | --- |
| 1 | catppuccin-latte | yes (written at prepare) | 3396 ms | 2761 ms | activated |
| 1 | community-proof | yes | 5320 ms | 3426 ms | activated |
| 1 | catppuccin | yes | 5032 ms | 2785 ms | activated |
| 2 | catppuccin-latte | yes | 2496 ms | 2958 ms | activated |
| 2 | community-proof | yes | 3426 ms | 3460 ms | activated |
| 2 | catppuccin | yes | 2568 ms | 3181 ms | activated |

There were zero `appearance-*-failed` or `appearance-*-rejected` lines in the
shell journal. Before the cache, the same three activations took 3.7–5.0 s
(`../commit-fix-board/README.md`). Round 1 previews include writing the cache
(about 2–3 s extra); round 2 reuses the generation.

**Where the remaining time goes.** A bare `k230-theme --help` takes 1259 ms
and `list` takes 1282 ms, against 71 ms for `runuser` alone. So each command
pays about 1.2 s of Python interpreter start-up and imports on the K230
before doing any work. With `PYTHONPROFILEIMPORTTIME`, `theme_activate`
accounts for 357 ms cumulative, with `dataclasses` and `inspect` about 137 ms
and 107 ms. The activation also restarts `wvkbd` for keyboard colours.
Startup on this build still logged `wallpaper-commit` at 4066 ms, because the
active generation was prepared before the cache existed.

**Follow-ups:**
- A persistent catalog helper, or trimmed imports, to remove most of the
  per-command start-up.
- Warming the cache for existing generations.

Real-finger chooser timing remains unmeasured.
