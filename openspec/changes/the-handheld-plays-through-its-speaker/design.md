## Context

`docs/evidence/max98357a-speaker.md` has the full research trail and every
citation this design relies on. This file states the decisions and what was
rejected.

The board today has exactly one working audio path recorded anywhere in this
repo: `nix/dts/k230-tdisplay.dts`'s `sound` node, `compatible =
"canaan,k230-audio-inno"`, wired to `&i2s` and `&inno_codec`. It has never
been exercised by a userspace tool -- no `aplay`, no `/proc/asound/cards`
capture, nothing. LILYGO's public README lists "MAX98357A external I2S
amplifier and audio route switching" as included hardware support.

## Layer 1: device tree (`nix/dts/k230-tdisplay.dts`)

**Decision:** document the four MAX98357A pins via `gpio-line-names` on the
existing, always-enabled `gpio1_ports` controller. Add no new device node,
and leave `canaan,external-i2s-output-default` unset on the `sound` node so
the Inno codec stays the boot-time default.

**Why not a `maxim,max98357a` codec node:** `sound/soc/codecs/max98357a.c`
(`CONFIG_SND_SOC_MAX98357A`) exists in the pinned kernel tree and would
probe cleanly on a `sdmode-gpios` property. Rejected because:

1. Its probe calls `devm_gpiod_get()` on `sdmode-gpios`, which requests the
   GPIO line for the lifetime of the driver. `nix/k230-speaker-test.nix`
   (and LILYGO's own launcher, `ui_hardware.c:1655-1731`) needs to toggle
   the identical line from userspace via libgpiod; the kernel's exclusive
   request and a userspace `gpioset` on the same offset cannot coexist.
2. The driver's SD_MODE control is a DAPM widget, powered only when a
   dai-link's playback stream is active *and* that dai-link includes this
   codec component. Nothing in this change wires the max98357a node into
   `canaan_k230_dailink` (see Layer 2 below for why not), so the widget
   would never power on regardless of what userspace asks for -- a DT node
   that looks like support while doing nothing.

**Why not FPIOA pin muxing here:** confirmed by reading this kernel tree
directly (not inferred) that no `pinctrl-k230` driver, `k230-fpioa` binding,
or `pinctrl`/`fpioa` node exists anywhere in `k230.dtsi` or any shipped
board `.dts`. `docs/dts-evidence.md` already established this for our board;
this change re-confirmed it holds for LILYGO's referenced `k230.dtsi` too
(same shared file). FPIOA muxing on this SoC is a stage-1 (U-Boot)
responsibility this project's taxonomy places outside `system/kernel` and
outside the Linux device tree entirely. GPIO32/33/35's actual alternate
function on this board is therefore left as an open, explicitly named gap
rather than asserted.

## Layer 2: kernel (`nix/patches/canaan-audio-external-i2s-switch.patch`)

**Decision:** port LILYGO's `0059-asoc-canaan-add-external-i2s-output-
switch.patch` (commit `37b66b38`) onto `sound/soc/canaan/canaan_k230_inno.c`,
almost unchanged. Verified this file is byte-identical, at every hunk
context 0059 touches, between our pinned tree
(`ruyisdk/linux-xuantie-kernel@7d4e1f4`) and whatever LILYGO's fork carries,
because it is generic Canaan SDK code neither fork's panel/display work ever
touched. `patch -p1` applied cleanly against a fresh copy of the file from
the unpacked `linux-xuantie-k230-src` store path.

**Why this is correct and not a workaround:** the route is not invented --
`audio_i2s_enable_audio_codec()` (`sound/soc/canaan/canaan_k230_audio.c:
50-59`, `EXPORT_SYMBOL_GPL`) already exists in this exact kernel and already
flips a real register bit (`audio_in_pdm_conf_0.audio_codec_bypass`) in the
`canaan,k230-audio` peripheral (`k230.dtsi:644`, `audio@0x9140f400`). The
unpatched driver just calls it with a hardcoded `true` at probe and never
again. This patch adds: a `bool external_i2s_output` field, a
`SOC_SINGLE_BOOL_EXT` control named `"External I2S Output Switch"` (same
name LILYGO's own launcher already drives via `amixer -q cset`), a
`k230_inno_apply_output_route()` helper that re-asserts the chosen route,
called both at probe and (new, beyond 0059) at every stream `startup()` so a
route selected with no active stream survives a SAI clock suspend/resume,
and `of_property_read_bool(np, "canaan,external-i2s-output-default")` to let
a board default to the external route -- which ours deliberately does not
set.

**Why not a second ALSA card (`simple-audio-card`/`audio-graph-card`):**
both exist in this kernel (`sound/soc/generic/`). Rejected because the SoC
has exactly one physical SAI/I2S peripheral, and `canaan,k230-audio-inno`
already claims it as `canaan_k230_dailink`'s sole `cpu`/`platform` node via
`canaan,k230-i2s-controller`. A second card pointed at the same `&i2s` node
would either conflict over the platform device or require rewriting the
existing machine driver to expose multiple dai-links -- more invasive than
"smallest correct change," and LILYGO's own design (confirmed by the 0058
commit message) explicitly avoids this too: "not registered as a second
ALSA sound card... the external amp listens to the same I2S stream."

**Kernel config:** no new `CONFIG_SND_*` symbol was needed.
`CONFIG_SND_SOC_CANAAN_K230_INNO=y` and `CONFIG_SND_SOC_CANAAN_K230_AUDIO=y`
were already set in `arch/riscv/configs/k230_defconfig` (lines 300-301) --
the driver we patch was already built in.

## Layer 3: userspace (`nix/k230-speaker-test.nix`, `nix/hardware.nix`)

**Decision:** a single `writeShellScriptBin` wrapping `alsa-utils`
(`amixer`, `aplay`, `speaker-test`) and `libgpiod` (`gpioset`, `gpioget`,
`gpiodetect`, `gpioinfo`). `status`/`internal`/`external` subcommands. GPIO34
is held active via `gpioset --mode=signal ... &`, released with `kill` --
this is the libgpiod v2 pattern for holding a line across an external
command; it is UNVERIFIED against the exact `libgpiod` version this flake
pins (no board or built closure has run it yet). This kernel has no
`CONFIG_GPIO_SYSFS` (removed from the Kconfig entirely), so the character
device is the only interface available regardless.

**Why not a persistent systemd service holding the GPIO:** rejected for this
change. A held line only during an explicit test avoids leaving the
amplifier powered by default on a board that may not even have one
attached, and matches the task's ask for a narrow operator helper rather
than a standing audio-routing policy. Standing policy (e.g. auto-switching
on a jack-detect signal) is future work once the physical amp's presence
and pin muxing are confirmed.

## Rejected: inferring physical amp presence

Considered treating the LILYGO README's inclusion of "MAX98357A... audio
route switching" as evidence this project's specific board has the
add-on. Rejected once `k230_bsp/docs/HARDWARE_PINMAP.md` was read in full:
that same document places the part on a named optional add-on, separately
purchasable from the main board, and CHANGELOG.MD groups it with other
add-on presets (nRF52840, nRF9151, LoRa). A README feature list describing
the product family is not a photograph of this board's PCB. Per
`.skills/k230-spec-change/SKILL.md`'s grounding order, this stays
`<!-- UNVERIFIED -->` rather than becoming a confident requirement.
