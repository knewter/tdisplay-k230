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
"replug i mean go on". The operator also affirmed the panel. The task-4.1 driver/probe/cable gate
is satisfied by this matching trial. A separate explicit real-touch report
is still absent; no navigation or real-touch proof is inferred. Those
physical input checks remain in the combined handoff trial. [The sysfs watcher](watch-cable.py) records
DRM state and UTC/monotonic times independently of the operator report.
A matching unchanged boot ID proves this observation did not reboot Linux.
The operator's glass/touch report is recorded separately from those sysfs
observations. No photograph is required.

## Runtime display switching (tasks 4.2–4.4)

The first combined candidate built and passed bundle/compiled-graph checks,
44 relay unit tests, two integration tests, and Clippy. Its matching
[volatile serial boot](runtime-first-serial-boot.json) observed system
`mvjvi0d4vg33ahw08qyj4pb8by977i93`, kernel Image SHA256
`d4955139c0e16e73fec7dc2e90482b1c360fea0f75cad452ff56dffe3de4d02c`, and
unchanged protected profile `kp6ldmdx33lgjl55hzv3xba5a55ils48`.
[Host checks](runtime-host-checks.json) describe the source and limits.
Reverse-applying [the worker patch](runtime-first-to-fast.patch) with
`git apply -R --unidiff-zero` to the
continuation source reproduces the first trial's DSI source/header hashes.

The operator confirmed visible HDMI with working trackpad, unplug restoring
visible panel and direct touch, and a subsequent successful replug. The
[exact reports](runtime-first-operator-report.json) also say both transitions
were too slow and request faster switching. No numerical latency is inferred.
The [matching HDMI state](runtime-first-hdmi-state.json) records enabled HDMI,
1280×800 at 59.910 Hz, the accepted 90° transform, virtual touchpad and
unchanged boot ID. It is serial state, separate from the operator's physical
observations. No monitor photo is required.

The initial implementation relied on DRM's ten-second polling period. The
revised worker reads bridge HPD every 250 ms and invokes DRM's normal hotplug
detection only on changes, retaining generic polling as fallback. Both
connectors are updated without rebinding live components or taking touch's
GPIO23/24. Startup waits for DRM registration; teardown cancels the worker.
[Object compilation](fast-hpd-object-check.json), the [full matching build](fast-host-checks.json), compiled graph and all 15 bundle-inspector fixtures pass.
The [faster volatile boot](fast-runtime-serial-boot.json) records system
`yl3si5ak6yi709yg1fqsnwgq0zn4xfcs`, kernel Image SHA256
`9d94102c65c8e4fd6b8880ef7b19b8bee5fa91c85596384319f0104bd89509cb`
and unchanged protected profile. The [operator report](fast-runtime-operator-report.json)
accepts the result, describes HDMI replug as a couple of seconds, and panel
return as almost instant. Those actions preceded the timing watcher; these
are approximate visible timings, not sampled HPD-to-DRM measurements.
The [matching state](fast-runtime-initial-state.json) captures enabled HDMI,
accepted rotation and virtual touchpad. Timed cable measurements, explicit
three-gesture navigation qualification and ordinary boot installation remain
pending. The bridge enable path retains its 500 ms settling wait; remaining
visible HDMI delay may also include monitor signal lock, which this state
snapshot does not measure.

The [initial image inspection](runtime-first-sd-image-inspection.json)
records a private source snapshot with the combined DT wired as the default:
its boot partition payload matches the first candidate byte for byte. This
proves image construction, not a flashed image or accepted fast handoff. The
repository default has not yet been promoted.

The [prepared faster image inspection](fast-private-sd-image-inspection.json)
passes with boot payload byte-identical to the faster bundle. Its private
source snapshot promotes only the two normal DT references; the normal and
explicit trial bundle derivations match. Repository defaults remain
panel-only pending qualification. This is host image inspection, not proof
that the image was flashed.
