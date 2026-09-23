# Product board tooling host proof

Date: 2026-09-23. Worktree `k230-card-shell-board-tools`, branch
`impl/card-shell-board-tools`, base `3a296b5`.

Commands:

```sh
TMPDIR=/mnt/MediaVolume/card-tests python3 tests/test_card_shell_board_tools.py
python3 -m py_compile tools/card-shell-board-session.py tools/card-shell-acceptance.py tests/test_card_shell_board_tools.py
openspec validate the-shell-manages-apps-as-cards --strict
```

The 18 test methods pass. They execute the actual session and acceptance
orchestration against a deterministic service/device fault fixture. Coverage:
watchdog armed before shutdown; whole-cgroup teardown ordering; partial launch,
input helper and compositor failure; interruption; watchdog failure without
stopping normal service; failed restoration/stop/populated cgroup retaining the
watchdog; recovery after controller death; stale tokens and late starts;
missing transient-unit properties; changed normal config or competing owner;
acceptance success/error/interruption cleanup; device name plus virtual origin;
configured command comparison excluding mutable systemd PID/timestamp fields;
immutable store-path validation; offline preparation and sanitized collection
with capture-digest verification.

The service fixture is simulated. These tests do not start systemd services,
open board devices, present pixels, or prove real systemd timer recovery. The
PNG fixture is deliberately synthetic and is removed with its temporary test
directory. No board result or physical acceptance is claimed. Review and the
reserved-board first execution remain required.

The bounded coordinator procedure and exact commands are in
[`../../research/card-shell-board-tools.md`](../../research/card-shell-board-tools.md).
All product task 4.2 / 5.2 / 5.3 evidence gates remain open.
