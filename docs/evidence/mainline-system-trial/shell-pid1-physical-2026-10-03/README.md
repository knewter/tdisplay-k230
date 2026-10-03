# Same-image Bash PID1 comparison — userspace prompt, no command receipt

2026-10-03 UTC. Root reserved board/UART for one trial with reviewed source
`473d4ab3` and CI integration `bfce9f8b8e3a162074190cae37e946e6b6336df1`,
branch `integrate/mainline-probe-path`, worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, protected recovery base
`1088e3ee`. Owned paths are this packet and the mainline task progress note.
No new build/transfer: the exact staged brmp bundle and full closure were reused.

[Host proof](../shell-pid1-controller-host-2026-10-03.md) records independent
review, 14 focused and 214 existing tests, actual archived common-loader
inspection and one-variable arguments. CI passed the ordinary, minimal and
new focused gates. Fresh protected normal preflight passed exact identities,
eight unchanged files and three services; its actual helper first asserts
registration absence including dangling symlink. Five loads/CRCs and exact
printed arguments passed. Exactly one received kernel command line matches
expected marker-free/async=0/three controls plus only `rdinit=/bin/sh`.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --mode minimal --same-image-shell-pid1 \
  --bundle /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files \
  --manifest ~/tmp/k230-mainline-shell-pid1-board/candidate-manifest.json \
  --normal-report ~/tmp/k230-mainline-shell-pid1-board/normal-report.json \
  --log ~/tmp/k230-mainline-shell-pid1-board/trial.private.log \
  --result ~/tmp/k230-mainline-shell-pid1-board/result.private.json
```

**Exit 2 at reception.** The controller received a fresh Linux 7.3.0-rc5
banner, `Run /bin/sh as init process`, then the primary `sh-5.3# ` prompt.
Its readiness gate passed. Bash/common-loader userspace startup therefore
has positive physical output evidence, beyond the earlier kernel exec label.
The bounded receipt loop exhausted eight fresh builtin attempts at one second
per attempt with zero complete receipt records or command echoes. Outgoing
write bytes are not separately logged; loop completion establishes the
attempt bound, while the immutable raw capture preserves received output.

No `/bin/true`, proc mount, uptime, PID1/root/kernel/cmdline/boot guard or
reboot was attempted. The controller released UART with no input after this
unknown result. Bash startup is distinct from qualified command reception,
full identity guard, ordinary NixOS root or automatic protected return.
A newly reviewed private camera frame appears dark, with glare/focus/perspective
limits. It does not contradict separate serial evidence of Bash startup.
Exact artifacts and fixed facts/raw byte/hash/timestamps are in
[result.json](result.json); raw UART and camera remain private.

## Recovery and next discriminator

A **new user reset after this trial** restored the protected normal system.
The prepared checker completed successfully (exit 0):

```sh
python3 ~/tmp/k230-mainline-shell-pid1-board/reset-normal-check.py
```

It sent CR only until a fresh normal prompt, then proved a different boot
identity, exact protected system/profile/kernel/init, all eight unchanged boot
files, three active services and registration absence. The Home IPC command
completed with exit 0; a new private camera frame shows normal Home icons,
clock and background, with glare/focus/perspective limits. The fixed
[recovery receipt](operator-reset-recovery.json) preserves raw hash/timestamps
and those facts without boot UUIDs or secret-bearing console text. Board/UART
and camera are released. This manual reset is separate from automatic return,
which remains UNVERIFIED, and supplies no mainline panel/glass acceptance.

The missing receipt narrows the next investigation to serial RX/interrupt/
TTY/task progress after observed userspace startup, without identifying a
cause. The host-only [source/DT receipt](uart-source-equality.json) compares eight
complete source files and thirteen targeted properties against the earlier
candidate that passed minimal receipt. Those files/properties match; full
DTBs, configs, binaries and runtime state are not claimed equivalent. This
result does not identify a source regression.
A finite independent reporter should distinguish cached driver RX/error
counts, actual mapped UART and RISC-V timer IRQ counters, and scheduling/time
progress without requiring Bash input. TTY polling flushes work and queued-input
ioctl takes a semaphore, so neither is a passive first probe. Reporter output
or silence must retain explicit limits and never stand in for recovery.
Kernel observer implementation/build and another qualified operator trial
remain future gates. No ordinary-root/panel/glass/production acceptance or
archive follows; task 5b.5 stays open.
