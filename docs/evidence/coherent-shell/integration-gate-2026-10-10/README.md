# Coherent-shell integration gate 4.1 — 2026-10-10

The task's exact named command passed against the selected cross-built Sway
component and a freshly built native Wayland protocol probe. [Actual result](result.json),
[command output](command.log) and [provenance](provenance.json) retain executable
paths/hashes, source revision, exact argv/environment, UTC timestamps and
capture identities. This closes task 4.1's integration gate only.

```sh
CARD_SHELL_SWAY=/nix/store/g7xzwwvr3x05mlmsab5jn5kn1sl41wjb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
CARD_SHELL_CLIENT=/nix/store/yjb89ap4bq5vb29szdzkr5sv9lpw1sz6-card-composition-probe-client-0.1/bin/card-composition-probe-client \
python3 tests/test_shell_motion.py --case live-gate --case private-no-icon --case close-refused \
  --output /home/jadams/tmp/k230-coherent-motion-proof-2026-10-10
```

## Observations

- Both applications' root and desynchronized-subsurface frames/callbacks
  advance while their actual pixels remain visible during a held deck drag.
  Marking the selected source unavailable produces a visible uniform neutral
  card distinct from the deck canvas; removing the mark restores live pixels.
- Each public fixture has a different name, icon and live content. Its known
  icon has 1,296 composed pixels before privacy and zero afterward. All live
  content is removed. The two complete private-card captures are byte-equivalent
  in decoded RGB despite the different identities, and show a visible neutral
  card. [Public one](public-one.png), [private one](private-one.png),
  [public two](public-two.png), [private two](private-two.png).
- A refusing client receives one graceful close request, stays mapped through
  the compositor's actual timeout feedback and remains focusable with keyboard
  delivery. An accepting client in that scene receives one close request,
  exits with status zero, unmaps, and leaves the surviving app focused.

The [negative control](negative-control-result.json) deliberately omits the
private mark in an external copy of this fixture. The unchanged compositor
continues rendering public identifying pixels, and the private-card gate fails
with exit 1 at the expected capture. This is an expected sensitivity check,
not a product failure or a replacement for the successful ordinary invocation.

## Artifact selection and helper build

The selected system's `pkgs.callPackage ./nix/card-shell.nix` with
`pkgs.sway-unwrapped` evaluates to the existing `gp9gv2nh…` wrapper and the
`g7xzwwvr…` executable above; the existing compositor was reused, and no kernel build was needed.
The [native client build](native-client-build.log) was guarded by
`/tmp/k230-nix-build.lock`: only one tiny derivation built, fetching 247.9 KiB
of native Wayland development/protocol inputs. The helper now has a registered
host-local root at
`~/.local/state/tdisplay-k230/retained-builds/coherent-integration-2026-10-10/native-client`.
This root is cache retention, not board deployment proof.

## Scope and remaining gates

Worktree `/home/jadams/tmp/k230-coherent-closeout-2026-10-10`, branch
`closeout/coherent-integration-2026-10-10`, base
`03d57adbe0fad4b89a32ee3a865923168daf0fe7`. Owned paths: the named motion fixture,
this evidence directory, the coherent-shell task record and its work-board
override. The temporary native-helper build slot has been released; no board
or serial reservation was taken.

Evidence class: headless Pixman captures of a RISC-V Sway process under QEMU
user emulation with native protocol clients and injected touch. It is neither
a system-mode guest boot nor a physical panel/touch result. All artwork is
synthetic fixture content; raw process logs remain private.

Task 4.2's cross-surface geometry/focus cases and 4.3's interruption/retarget
cases still need implementation and actual runs. The parser rejects those
unimplemented names. Accessibility and all required physical/trace/polish
gates remain open; current operator UX acceptance does not invent their proof.
The umbrella is 27/39 complete and remains open. No physical operator action
was required for this task; remaining board commands are preserved in its
unchecked group-5/6 tasks.
