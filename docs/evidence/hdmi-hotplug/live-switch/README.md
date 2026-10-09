# Automatic plug/unplug switching

Worktree `/home/jadams/tmp/k230-hdmi-continue`, branch
`codex/hdmi-mainline-continue`; continuation starts at `58498320` on original
base `edd74d1626d03770e08e328320b18118ece24508`. The operator requested automatic
plug/unplug switching after accepting HDMI, and waived a monitor photograph.
The Settings prototype is parked at `58498320` and removed from the active
source. It is not a prerequisite for this work.

Owned paths: mainline LT9611/DSI driver sources under
`nix/patches/mainline/drm/`, qualification/combined device trees under
`nix/dts/`, their `flake.nix` and NixOS wiring, narrow tests, this evidence
and the HDMI OpenSpec change. Reverting the uninstalled Settings prototype
also touches its owned Python/Rust/Nix source and test paths; no other
worktree or unrelated dirt is modified.

## Cable detection while the panel is active (task 4.1)

The qualification driver mode is selected only by
`lontium,hpd-monitor-only`. It waits for touch to finish the shared reset,
enables register access through the existing revision probe, masks HPD IRQ
sources, and exposes read-only `/sys/bus/i2c/devices/*-003b/hpd`. It does
not register a bridge, attach DSI, or acquire reset/IRQ GPIOs. The compiled
tree retains the panel as the sole DSI endpoint.

Host command:

```sh
nix build .#kernelMainlineDrmShellHpdMonitorBootFiles --max-jobs 1 --cores 8
```

The bundle includes `deviceTreeMainlineDrmHpdMonitor` and the matching kernel,
initrd and normal shell system. [Compiled tree inspection](monitor-dtb-inspection.json)
passes via [this recipe](inspect-monitor-dtb.py). The full bundle builds,
its identity inspection and all 15 inspector fixtures pass; see
[host checks](monitor-host-checks.json). The final bundle adds its matching
`/chosen` boot arguments, so it has a different DTB hash; the
[wrapped graph inspection](monitor-wrapped-dtb-inspection.json) also passes.
This is host proof only; physical plug/unplug and glass/touch proof remain
separate from the build result.

The existing protected panel boot was rechecked before staging: mainline
7.3.0-rc5, Goodix bound on adapter 0 at `0x5d`, and connected panel. The
vendor-era adapter number 1 does not apply to this boot. A userspace register
probe could not proceed because `/dev/i2c-1` was absent; no GPIO was changed.
Loading the available `i2c-dev` module and using adapter 0 allowed the
[raw-register probe](panel-raw-hpd.json): revision `0xe2`, HPD `0x78`. After
the operator reported "i just plugged in hdmi", HPD changed to `0x7d` and
the panel connector remained connected on the same boot ID. This establishes
raw cable detection alongside touch, not the new monitor-driver boot or a
visible display switch. The status-only driver does not depend on an I2C
character-device node or adapter-number assumption.

The [matching volatile boot](monitor-serial-boot.json) passes serial identity
checks: system `wwpymaab8wp65kayxbnvsjdacj9ksx86`, kernel Image SHA256
`8c3d1b8ee1a0cc983975668e5def4f4ea97fe5a36ef45cb2c7a8372fba9087d4`,
protected profile still `kp6ldmdx33lgjl55hzv3xba5a55ils48`. The
[LT9611 probe](monitor-probe.txt) reports revision `0xe2` and the new monitor
ready message. [Initial state](monitor-initial-state.json) records HPD
connected, panel connected/enabled, and touch bound. The normal boot files
and profile were preserved; this is not persistent installation proof.

The [matching cable cycle](monitor-cable-cycle.json) records connected →
disconnected at 16:31:01 UTC → connected at 16:31:09 UTC on the same boot,
with DSI connected/enabled throughout. The operator clarified the action as
"replug i mean go on". The explicit real-touch report remains pending; task
4.1 stays open until that report. [The sysfs watcher](watch-cable.py) records
DRM state and UTC/monotonic times independently of the operator report.
A matching unchanged boot ID proves this observation did not reboot Linux.
The operator's glass/touch report is recorded separately from those sysfs
observations. No photograph is required.

## Runtime display switching (tasks 4.2–4.4)

Pending task 4.1's matching board proof. The [source preflight](source-preflight.md)
explains why a device-tree-only change cannot implement it. Cable detection
alone does not prove that visible output or touch mode switches.

The trial must preserve the accepted panel/HDMI geometry and HDMI trackpad
behavior, use touch as the sole reset/IRQ owner, and retain the protected
panel boot for serial recovery. Actual panel→HDMI→panel observations,
matching DRM/Sway state and unchanged boot identity remain required.
No hardware task is checked off from the host build or an injected event.
