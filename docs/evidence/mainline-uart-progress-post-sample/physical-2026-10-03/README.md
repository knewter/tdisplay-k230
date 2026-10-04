# Physical PostSample comparison: only worker entry observed

The temporary matching PostSample boot reached its fresh 7.3.0-rc5 banner,
exact received arguments, `/bin/sh` entry and primary Bash prompt. One receipt
command was sent. The bounded 180.0975-second capture observed only the
worker-entry breadcrumb: no receipt, first-post-sleep, numeric samples or new
PostSample points arrived. No normal return or parser protocol error was
observed. This is an incomplete diagnostic observation, not ordinary mainline
boot acceptance or an identified cause.

Root operated the board/UART exclusively from worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, controller revision `e7c2b1a9`, using the matching
full build from frozen `75cc49df`. The intervening commits contain host evidence,
not source changes. [Result](result.json) records exact artifact identities,
UTC times, return 2 and private capture SHA256/size. Raw UART, nonce, boot IDs,
protected baseline and transfer URL remain private. No camera or glass proof
was obtained during this candidate test.

[Exact/full host proof](../exact-full-host/README.md) and
[actual positive controller preparation](../positive-controller-host/README.md)
passed before hardware access. Transfer/import staged eight new paths with
return zero; the closure was GC-rooted. Fresh protected preflight checked normal
system/profile/kernel/init, eight boot hashes, services and registration absence.
The controller rebooted normal Linux into U-Boot, checked load sizes/CRCs and
booted the matching Image/initrd/DT with the exact qualified volatile policy.
Persistent normal boot selection stayed unchanged.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --mode minimal --same-image-shell-pid1 --uart-progress \
  --uart-progress-breadcrumbs --uart-progress-post-sample \
  --bundle /nix/store/fjmxf6kn1yq0xk9v783amgymybhcrwkb-k230-mainline-drm-trial-boot-files \
  --manifest "$PRIVATE_RUN/candidate-manifest.json" \
  --normal-report "$PRIVATE_RUN/normal-report.json" \
  --log "$PRIVATE_RUN/trial.private.log" \
  --result "$PRIVATE_RUN/result.private.json"
```

The actual controller's completed structured result qualifies the prompt and
records receipt UNKNOWN; the raw-line monitor is not authoritative. Exactly one stimulus
was attempted. No retry, proc command, guard, extra input or candidate reboot
followed. [Fixed records](fixed-records.txt) contains only the observed constant
line. Entry arrived before the stimulus; host arrival order is not hardware
execution timing.

The selected source places entry immediately before the first `msleep(5000)`.
Entry presence proves reaching its SBI output attempt, not return from that call.
The absent first-post-sleep therefore leaves entry-call return, sleep/wakeup,
later execution and later output unresolved. No numeric counter delta can be
computed in this run. The previous Breadcrumbs run reached sample 1 and returned
a Bash receipt; this run did not repeat that progress. Neither run establishes a
stable stall location or causation by the two new markers. The new markers are
only attempted after sample 1's output and after the third sleep, respectively;
absence provides no evidence that those calls were reached.

The source-only boundary review identifies `schedule_timeout_uninterruptible`,
its timeout timer callback and task wakeup as independent milestones worth
observing. Any next comparison should record progress in memory independently
of the reporter's SBI writes and account for the remaining shared serial output
limit. Another chain of ECALL breadcrumbs alone cannot settle their own return.
No IRQ/clock/firmware fault is claimed from missing serial output.

The capture completed and board/UART reservation was released. The subsequently
requested NEW operator reset passed fresh guarded normal postflight: distinct
boot identity, exact system/profile/kernel/init, eight boot hashes, three active
services and registration absence. Home IPC returned zero; a separate reviewed
camera image shows Home clock/icons/background, with angle/glare/focus limits.
[Operator reset receipt](operator-reset-recovery.json). This does not establish
automatic return, ordinary mainline `/init`, usable root or panel/glass acceptance;
task5b.5 stays **UNVERIFIED**. The historical controller status records the
capture's missing return; the separate receipt establishes later manual recovery.

Physical evidence08ea7370 passed CI37175128998 and both published work/physical
pages returned HTTP200 with that exact revision; [deployment receipt](deployment.json).
Independent review matched the fixed facts and capture digest to protected data.
Group5h is reconciled; group5i's separately landed Memory comparison is next.
