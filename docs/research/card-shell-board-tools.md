# Product card board tooling

These tools prepare a temporary product trial; they do not install an image or
change the default shell. Task 5.2 and the Pixman cost gate remain open until the
coordinator runs and reviews real board artifacts. Real-finger and optical
latency proof remain separate. Host proof is in
[`../evidence/card-shell-board-tools-host/README.md`](../evidence/card-shell-board-tools-host/README.md).

## Reservation and recovery

`card-shell-board-session.py --execute` requires the reserved RISC-V board root
session, active normal `shell.service` and `seatd.service`, and the exact config
from the normal service's `ExecStart`. It validates explicit immutable package,
client and config paths. It resolves every host command and Python executable
to an installed Nix store path before stopping anything. Supply `systemctl`,
`systemd-run`, `journalctl`, `evemu-describe`, `evemu-device`, `evemu-event`, `sh`,
`grim`, and `python3` on the coordinator's PATH from reviewed installed closures.
The product wrapper itself must include bash, dbus and coreutils (already true
of the reviewed product package).

A root timer is armed before normal-shell shutdown. The product runs as `shell`
in `k230-card-shell.service` with `KillMode=control-group`, accounting, an
independent runtime limit, and a private Wayland runtime. It includes the actual
normal config, preserving its bar, launcher, terminal, monitor, help and
keyboard programs. The only appended configuration selects DSI-1 native
568x1232, scale one, `render_bit_depth 6` (RGB565), and touch mapping. Its child
apps and normal UI stay in the same accounting cgroup; only then is
`SWAY_K230_CARD_BENCH_CGROUP=1` set.

The input helper has its own bounded root service. It copies the chosen input
descriptor and changes its name to **K230 injected touchscreen**. Discovery and
acceptance require that exact name and `/sys/devices/virtual/input/` origin.
The helper creates a new device; it never terminates an existing event-device
owner. In particular, the historical Goodix-named evemu fixture is not accepted
as injected provenance. The coordinator handles that known old fixture before
this reservation if it would interfere. Physical devices are never killed.

Cleanup closes the reservation irreversibly, stops both complete cgroups,
checks inactivity/MainPID/cgroup population, compares the original service
command, and starts the original normal shell. A late service start must pass
an independent root `ExecCondition`; no `Conflicts=shell.service` dependency can
stop the restored shell before that guard runs. The root recovery timer starts
at duration + 45 seconds and retries every five seconds. It survives owner
process death and remains armed if cleanup fails. A failed cleanup does not
force-kill an unowned compositor. Successful controller cleanup stops the timer.

The acceptance runner also restores in `finally`, including failed observations
and handled SIGINT/SIGTERM. SIGKILL is covered by the independent timer and
service runtime limits. Neither tool is a substitute for observing that the
restored normal screen and controls actually work; the manifest keeps that
manual gate `UNVERIFIED`.

## Host preparation

These modes do not discover devices, contact IPC, run services or claim board
observations. Use the actual package revision and board's normal config path:

```sh
python3 tools/card-shell-board-session.py --prepare \
  --package "$card_package" --config "$normal_config" \
  --client "$card_client" --revision "$card_revision" \
  --duration 600 --output /mnt/MediaVolume/card-tests/card-session-plan
python3 tools/card-shell-acceptance.py --prepare \
  --output /mnt/MediaVolume/card-tests/card-acceptance-plan
```

The package must contain the native input provenance correction from
`935e02155cac7374de10b5db6e642d9479c500b3` or its reviewed landed equivalent.
For that tested source, the narrow output was
`/nix/store/ii5g7635wldnk7jsrfp18ism634w5y70-k230-card-shell`.
A reviewed cross client is
`/nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client`.
These are artifact identities, not an assertion that either is installed.

## Coordinator board command

After reserving the board/UART, import the declared closures and copy the two
Python tools and existing `tools/inject-tap.sh` into a root-owned, non-writable
by other users `/run/card-tools/`. Keep the two Python tools together. The
following runs only on the board, with the dependency PATH described above:

```sh
card_python=$(readlink -f "$(command -v python3)")
card_package=/nix/store/ii5g7635wldnk7jsrfp18ism634w5y70-k230-card-shell
card_revision=935e02155cac7374de10b5db6e642d9479c500b3
card_client=/nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client
normal_config=$(systemctl show shell.service --property=ExecStart --value |
  "$card_python" -c 'import re,sys; s=sys.stdin.read(); m=re.search(r"(?:-c|--config)\s+(/nix/store/[^\s;]+)",s); assert m; print(m[1])')
systemd-run --unit=k230-card-session-owner --property=Type=exec \
  --property=User=root --property=RuntimeMaxSec=650s --setenv=PATH="$PATH" \
  "$card_python" /run/card-tools/card-shell-board-session.py --execute \
  --package "$card_package" --config "$normal_config" \
  --client "$card_client" --revision "$card_revision" --duration 600 \
  --source-device /dev/input/event0 --output /run/card-evidence/session
```

Wait for `/run/k230-card-shell/state.json` to report `phase=active`, a non-null
`device`, and `closed=false`. Confirm the product is the sole compositor and
its output is the panel. The root timer, not this interactive connection, owns
recovery. Then execute:

```sh
"$card_python" /run/card-tools/card-shell-acceptance.py --execute \
  --provenance injected-touch --inject-script /run/card-tools/inject-tap.sh \
  --output /run/card-evidence/acceptance
```

The acceptance command always requests normal restoration on completion or
handled failure. To stop early or recover independently:

```sh
"$card_python" /run/card-tools/card-shell-board-session.py --restore
systemctl stop k230-card-session-owner.service
"$card_python" /run/card-tools/card-shell-board-session.py --collect \
  --output /run/card-evidence/session
systemctl is-active shell.service seatd.service
```

Observe the normal screen, terminal and keyboard after recovery and retain that
observation separately. Before a repeat, stop/reset the completed owner unit;
the session tool rejects an unresolved previous reservation. Never stop the
recovery timer manually to conceal a restoration failure.

## Observations and limits

The runner closes only the fresh normal startup terminal, rejecting unexpected
existing applications. It maps actual animated SHM clients with desynchronized
subsurfaces, measures one-card and two-card runs with the same mapped apps in
baseline/active/restored phases, then exercises marked private/unavailable
states, upward graceful close, explicit client refusal, separate compositor
timeout, accepted source exit, and persistent normal control routes. Gestures
call the existing `inject-tap.sh` against the verified virtual device. No
headless injection hook is used. Privacy marks and fixture launch use normal
Sway IPC; user interactions use native uinput routing.

Captured names cover live cards, mid-drag, expansion, placeholders, close
states, Apps, Help/Back, Terminal, Monitor, Windows/Home, Keyboard, System/Back.
Coordinates are for the reviewed native scale-one normal config. The routine
never invokes Reboot or Power off. An observation failure is retained even if
an independent recovery button subsequently works. Client counters and close
protocol events are exported with a fixed schema. Screenshots require human
review for correct scene composition, privacy, text, focus and control routes;
`CAPTURED_REQUIRES_REVIEW` is not product acceptance. A heartbeat or frame
callback is not presentation proof.

Copy `/run/card-evidence/` to the host using the coordinator's normal protected
transfer procedure. Raw debug journal and private session state are excluded.
Only fixed telemetry grammar, allowlisted client observations, capture hashes,
and named screenshots are exported. The offline collector makes no device
calls and strips unknown JSON fields:

```sh
python3 tools/card-shell-acceptance.py --collect "$transferred_acceptance" \
  --output docs/evidence/card-shell/injected
python3 tools/card-shell-benchmark.py --board \
  --input docs/evidence/card-shell/injected/telemetry.log \
  --manifest docs/evidence/card-shell/injected/manifest.json \
  --output docs/evidence/card-shell/pixman.json
```

Preserve parser `FAIL` or `INCOMPLETE` results. The input script's actual event
cadence and the board's actual samples may fail budget or coverage gates; do
not infer latency or memory from requested delays. The prior headless cadence
failure remains recorded. Image integration, physical gesture proof and board
cost acceptance remain open after this tooling commit.
