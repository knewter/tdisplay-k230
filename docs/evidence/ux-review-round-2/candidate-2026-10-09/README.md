# Integrated UX candidate recheck — 2026-10-09

The running candidate is the accepted normal mainline hotplug system, not the
October 1 baseline and not an inferred compositor from a system store path.
All captures have boot ID `4bf73b24-a16a-4786-96fb-f1288244d96f`.

| Identity | Observed artifact |
| --- | --- |
| Normal system/profile | `/nix/store/yl3si5ak6yi709yg1fqsnwgq0zn4xfcs-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel | `/nix/store/f3rnipvbc5vqam8kwdmn3wgcl5rbz9yx-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/Image` |
| Sway unit/PID | `shell.service`, PID 1022; wrapper `/nix/store/gp9gv2nh0zf4bgryk8qp4dbprnfycya2-k230-card-shell/bin/sway` |
| Resolved live Sway | `/nix/store/g7xzwwvr3x05mlmsab5jn5kn1sl41wjb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway` |
| Rust unit/PID | `shell-ui.service`, PID 1044; wrapper `/nix/store/fys5c84qf4z72wnhn87b46z7jvyj18l9-k230-shell-rust/bin/k230-shell-rust` |
| Resolved live Rust | `/nix/store/q2rxmp980f9kxi962f29333z9pbixvbk-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` |
| Loaded Pixman | `/nix/store/brhzfimak2r3c23lmn80y1g6ww6nmb1r-pixman-riscv64-unknown-linux-gnu-0.46.4/lib/libpixman-1.so.0.46.4` |
| Quarter-turn opt-in controls | `WLR_PIXMAN_QUARTER_TURN` and `WLR_PIXMAN_OUTPUT_TURN` are unset in this live compositor. This identifies controls; it does not prove vector or fast-path dispatch. |
| Active output | HDMI 1280×800 @59.910 Hz, transform 90, scale 1, logical 800×1280. |

The normal default promotion is recorded at source `6b4fe555645a`; the review
checkout is `1f1b4ef9`, which contains that implementation plus closeout docs.
No compositor or Rust package was installed, restarted or launched separately
for this review. The live unit/executable/library identities above identify
what was actually used instead of treating historical opt-in packages as the
integrated candidate. The old baseline remains system `p1a1hz`, Rust `3hy6`,
source `5bb67db1` in the research baseline; these identities are not blended.

## Commands and source artifacts

From the change worktree, using new protected output directories:

```sh
python3 docs/evidence/ux-review-round-2/candidate-2026-10-09/capture-console.py --output /protected/ux-console
python3 docs/evidence/ux-review-round-2/candidate-2026-10-09/capture-candidate.py --scene overview --output /protected/ux-overview
python3 docs/evidence/ux-review-round-2/candidate-2026-10-09/capture-candidate.py --scene drawer --output /protected/ux-drawer
python3 docs/evidence/ux-review-round-2/candidate-2026-10-09/capture-candidate.py --scene settings --output /protected/ux-settings-loading
python3 docs/evidence/ux-review-round-2/candidate-2026-10-09/capture-candidate.py --scene settings --settle-seconds 5 --output /protected/ux-settings
```

The console source executes the task's same four identity commands through
`flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3`,
with `SYSTEMD_PAGER=cat` and `SYSTEMD_COLORS=0` set around the remote command.
An initial default-pager attempt truncated ExecStart and is not used as proof.
`console.json` retains system, active status, MainPID, complete ExecStart path
and resolved executable; private arguments, prompts and command echoes are
omitted. The actual complete invocation is recorded there.

The native capture source also reserves `/tmp/k230-board.lock` while opening
`/dev/ttyACM0`. It records the exact route and `grim -c` commands, actual runtime
state and unit identities. Overview uses `swaymsg 'card_shell enter'`; Apps and
Settings use the live Rust client's `--surface` route. Each returns to Home.
Images transfer over UART with matching board/host SHA256, recorded below and
in `capture-index.json`. Every image was inspected before public commitment.
The existing [Home capture](../../shell-responsive/board/acceptance-2026-10-09/README.md)
is from this same normal boot and executable. Raw UART transcripts stay private.

| Capture | Bytes | SHA256 | Board capture UTC |
| --- | ---: | --- | --- |
| `overview.png` | 128369 | `83c8b4261beb9621eaaeed8c8e6c1d4fe25bb16abbad63de4234355d25e16de8` | 2026-10-09T22:06:21.678517+00:00 |
| `drawer.png` | 188988 | `2d009ee5c0b97bfc21e04592bd099b0f21643bafe660043ed9d0a3e7c418b286` | 2026-10-09T22:06:57.383997+00:00 |
| `settings-loading.png` | 306836 | `cabe8ccd9ea9e02dab94e4b12cd4a849b5f3c640ed33dd6d007694a4a2592830` | 2026-10-09T22:08:04.398373+00:00 |
| `settings.png` | 63999 | `28d54e2559cd392b108649241ea60bbdafb4d17ac8d653e84b0e7cee638aa931` | 2026-10-09T22:10:19.320596+00:00 |

## Observations and limits

Overview contains one Terminal card with an empty normal prompt and recognizable
app label. The drawer contains 19 real catalog entries in six columns with
search, distinct icons and labels. This is broader than the old eight-entry host
fixture; it still does not exercise catalog overflow. The first Settings image
shows loading after approximately one second; the later five-second capture
shows Wi-Fi link-up, brightness, volume/sink, Keyboard, Motion and Power rows.
This does not measure precise load latency. No persistent loading defect is
claimed. No named Help or System app is visible in the captured catalog;
those older matrix routes are not demonstrated as separate current apps.

These are native board states reached through injected route commands, not a
new finger walkthrough. The operator's explicit current Home/All Apps/Settings
acceptance is separately committed with the responsive closeout and reused for
those checks only. Keyboard typing, two-app switching and media start/stop are
awaiting the focused operator reply. Optical motion, readability, finger
tracking, keyboard-visible accessibility, refusal/error/denied recovery and
cold-start timing remain UNVERIFIED where matching proof is absent.

All findings were rechecked in the [candidate report](../../../research/handheld-ux/review-round-2/candidate-recheck.md).
No baseline finding has P0/P1 severity. This closes the analysis's candidate
identity/recheck tasks 3.1/3.2, while task 2.2's current journey walkthrough and
4.2's final publication/archive remain open. Runtime implementation and its
physical/performance gates stay with their owners; this is no runtime release.

Ownership: worktree `/home/jadams/tmp/k230-ux-close-final`, branch
`closeout/ux-review-2026-10-09`, initial base
`e637f3f0ff49761c5c403190100a16dd1792f449`, reconciled to `1f1b4ef9` before edits.
Owned paths are this review's evidence/research/planning, the four new PNG
manifest rows, and its work-board status entry. No build slot was taken. The
board and serial slot were held only for these captures and then released.
