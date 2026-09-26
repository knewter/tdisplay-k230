# The MAX98357A speaker amplifier: what's grounded, what isn't

Change: `the-handheld-plays-through-its-speaker`. Investigated 2026-09-25
against `Xinyuan-LilyGO/T-Display-K230` @ `main` (no pinned commit exists at
the time of writing; the repository has no tags) and our own pinned kernel
source, `ruyisdk/linux-xuantie-kernel` @ `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`
(`nix/kernel-src.nix`), read from the unpacked store path
`linux-xuantie-k230-src`.

## The headline finding: this is add-on hardware, not main-board hardware

`k230_bsp/docs/HARDWARE_PINMAP.md` in `Xinyuan-LilyGO/T-Display-K230` splits
the board family into three explicit groups: the K230 main board, the
optional "nRF52840 BLE / Audio / Sensor Base Board", and the optional
"nRF9151 Cellular / GNSS / Keyboard Base Board". The MAX98357A entry sits
entirely inside the **nRF52840 base board** table:

```
## nRF52840 BLE / Audio / Sensor Base Board

This optional base board provides BLE Central functionality through nRF52840,
AHT20 sensing, and the MAX98357A external I2S amplifier.
```

`CHANGELOG.MD` lists it the same way, grouped with other add-on presets:

```
- nRF52840 UART preset.
- nRF9151 UART and enable-pin preset.
- SX1262/LR2021 LoRa SPI preset.
- MAX98357A external I2S amplifier and audio route switching.
- AHT20, BQ25896, BQ27220, XL9555, and TCA8418 keyboard-base I2C devices.
```

So the task's framing -- "whether the amp and speaker are on the main board
or on the optional keyboard base" -- turns out to offer a false choice: it is
on neither. It requires a **third, separate optional add-on** (the nRF52840
base), distinct from both the bare main board and the nRF9151 keyboard base.

**UNVERIFIED: whether this project's physical board has the nRF52840 add-on
attached.** Nothing in this repository has recorded that board before this
change -- no schematic, no boot log, no prior spec or evidence file mentions
it, and the on-board "keyboard board" work referenced elsewhere in this repo
(`docs/evidence/keyboard-*`) is the on-screen software keyboard, not the
physical nRF9151 keyboard base. Everything below makes the software side
correct and ready; it does not establish that a speaker is physically
present to drive.

## Pins and enable line

From the same `HARDWARE_PINMAP.md` table:

| Function | K230 signal | Notes |
| --- | --- | --- |
| DOUT/DIN | GPIO35 | External I2S amplifier data input |
| CLK/BCLK | GPIO32 | External I2S amplifier bit clock |
| WS/LRCK | GPIO33 | External I2S amplifier word-select clock |
| Shutdown | GPIO34 | High enables the amplifier, low shuts it down |

Independently confirmed by
`k230_bsp/overlay/buildroot-overlay/linux/0058-riscv-dts-rm69a10-add-audio-fan-sensor-pins.patch`
(commit `6b5d4c3a`, "riscv: dts: rm69a10: add audio keyboard and sensor
pins"), whose commit message states the same four pins and adds pinctrl
subnodes for them (`amp_i2s_pins`, `amp_shutdown`), and by the LVGL
launcher's own hardware layer,
`k230_launcher/k230_phone_ui/src/ui_hardware.c:68`:

```c
#define AMP_SHUTDOWN_GPIO 34U
```

**GPIO34 is a plain GPIO, not behind the XL9555 I/O expander.** The XL9555
appears in `HARDWARE_PINMAP.md` only under the separate nRF9151 keyboard
base ("XL9555 GPIO expander ... LED and keyboard-base support"), at I2C
address `0x20`-`0x27` on I2C4, alongside the TCA8418 keyboard controller,
BQ25896 charger and BQ27220 gauge -- devices unrelated to audio. The amp's
enable line is a bank-1 GPIO on the SoC itself.

`ui_hardware.c:1655-1731` shows exactly how LILYGO's own launcher drives it:
opens `/dev/gpiochip1` (`chip_index = AMP_SHUTDOWN_GPIO / 32`), requests
offset 2 (`AMP_SHUTDOWN_GPIO % 32`) via libgpiod, and sets it high/low. Our
board's `gpio1_ports` (`k230.dtsi:415-421`) is the identical controller --
bank 1 covers GPIO32-63, so GPIO34 is offset 2 there too
(`docs/dts-evidence.md`, "GPIO bank trap").

## The route is a register bit inside the SAI peripheral, not a second sound card

The commit message on 0058 says so directly:

> The MAX98357A is intentionally not registered as a second ALSA sound card
> in this stage. The board already uses the K230_I2S_INNO card; the external
> amp listens to the same I2S stream and is gated by GPIO34 from userspace.

A second patch,
`k230_bsp/overlay/buildroot-overlay/linux/0059-asoc-canaan-add-external-i2s-output-switch.patch`
(commit `37b66b38`, "ASoC: canaan: add external I2S output switch"), adds the
actual route control. It modifies
`sound/soc/canaan/canaan_k230_inno.c` -- and that file, in our own pinned
kernel tree, is **byte-identical at every hunk context** to what 0059
patches: same struct, same three-line sequence
(`audio_i2s_in_init(); audio_i2s_enable_audio_codec(true);
audio_i2s_out_init(true, 32);`) in `canaan_k230_inno_probe()`. This machine
driver is generic Canaan SDK code, unrelated to either fork's panel work, so
it never diverged between LILYGO's tree and ours.

`audio_i2s_enable_audio_codec()` is exported from
`sound/soc/canaan/canaan_k230_audio.c:50-59`:

```c
void audio_i2s_enable_audio_codec(bool use_audio_codec)
{
	if (sai.base) {
		struct audio_in_reg_s *audio_in_reg = sai.base;
		audio_in_reg->audio_in_pdm_conf_0.audio_codec_bypass = !use_audio_codec;
	}
}
EXPORT_SYMBOL_GPL(audio_i2s_enable_audio_codec);
```

`audio_codec_bypass` is a real register bit
(`sound/soc/canaan/canaan_k230_audio.h`, `audio_in_pdm_conf_0_s`, documented
inline as "bypass audio codec, use I2S directly to IO for digital I2S
microphone") inside the `canaan,k230-audio` peripheral at `0x9140f400`
(`k230.dtsi:644`) -- the same register block `canaan_k230_audio.c` maps as
`sai.base`. Flipping it is a genuine SoC-level mux between the on-die Inno
codec and the raw external I2S pads; it is not DAPM, not a second card, and
does not involve any MAX98357A codec driver.

`sound/soc/canaan/canaan_k230_inno.c` already builds into this kernel:
`CONFIG_SND_SOC_CANAAN_K230_INNO=y` and `CONFIG_SND_SOC_CANAAN_K230_AUDIO=y`
are both already set in `arch/riscv/configs/k230_defconfig` (lines 300-301
of the pinned tree). No kernel config change was needed for the route
switch itself.

## What we ported, and what we deliberately did not

`nix/patches/canaan-audio-external-i2s-switch.patch` is a close port of
0059: same control name (`"External I2S Output Switch"`), same
`canaan,external-i2s-output-default` DT flag, same call sequence, wrapped in
a `k230_inno_apply_output_route()` helper and re-applied on every stream
`startup()` so a route chosen with no active stream still survives a SAI
clock suspend/resume. It applies cleanly to our pinned tree (`patch -p1`
verified against a fresh copy of `sound/soc/canaan/canaan_k230_inno.c` from
the `linux-xuantie-k230-src` store path). Our board file leaves
`canaan,external-i2s-output-default` unset, so the Inno codec (headphone/
line-out) stays the default and only boots-tested route; the external path
is opt-in via `amixer -q cset name='External I2S Output Switch' 1`.

We did **not** add a `compatible = "maxim,max98357a"` DT node, even though
`sound/soc/codecs/max98357a.c` (`CONFIG_SND_SOC_MAX98357A`) exists in this
kernel tree. LILYGO's own board file never adds one either. Two reasons,
both load-bearing:

1. That driver's probe path calls `devm_gpiod_get()` on its `sdmode-gpios`
   property, claiming GPIO34 exclusively for the kernel. A userspace helper
   (or LILYGO's own launcher) toggling the same line via libgpiod would then
   fail with "GPIO busy" -- the two designs cannot coexist on one line.
2. Nothing here wires such a node into any dai-link's DAPM graph (the route
   is a raw register bit, not a codec-managed power path), so a max98357a
   component node would sit unused: its SD_MODE widget would never power on
   because no stream ever attaches to it, permanently holding the GPIO low
   regardless of what userspace wants. Adding the node would look like
   support while doing nothing.

`sound/soc/generic/simple-card.c` and `audio-graph-card.c` (`CONFIG_SND_
SIMPLE_CARD`, `CONFIG_SND_AUDIO_GRAPH_CARD`) also exist in this tree and
were considered as a "second card" design per the task's own framing. Same
objection applies more strongly: a second card would need its own dai-link
against `&i2s`, and the existing `canaan,k230-audio-inno` machine driver
already owns that controller exclusively as this SoC's single physical SAI
peripheral. Splitting it would require machine-driver surgery well past
"smallest correct change," for no capability the register-level route switch
doesn't already provide.

## The open gap: physical pin muxing is unverified

This SoC's FPIOA pin mux (which alternate function IO32/33/35 present) is
set by U-Boot, not by the Linux device tree. `docs/dts-evidence.md`
established this for our board already: "There is no pinctrl in the Linux
device tree... FPIOA muxing is done by U-Boot via pinctrl-single... Our
board .dts cannot set pin functions." Confirmed again while reading this
kernel tree for this change: no `pinctrl-k230` driver, no `k230-fpioa`
binding, and no `pinctrl`/`fpioa` node anywhere in `k230.dtsi` or any board
`.dts` in the pinned source -- only the K210-era `k210-fpioa.h`, for a
different chip.

LILYGO's own pinctrl-based patch (0058) references pin-function macros like
`K230_IO32_IIS_CLK` and a `pinctrl-0 = <&amp_i2s_pins>;` property on `&i2s`.
Patch 0032 (`k230-canmv-rm69a10.dts`, the file 0058 modifies) includes the
same shared `k230.dtsi` our tree does, with no pinctrl infrastructure in it
either -- so LILYGO's fork must supply that pinctrl-k230 driver somewhere
in their `kendryte/k230_linux_sdk` submodule itself, not in a patch visible
in this repository's search. Whatever it is, our pinned tree does not carry
it, and porting 0058 verbatim would reference an undefined pinctrl node and
undefined macros.

This means: setting the ALSA route to "external" makes the SAI peripheral
stop feeding the Inno codec and drive GPIO32/33/35 directly -- but whether
U-Boot has actually muxed those three pins to their I2S alternate function
(rather than leaving them as plain GPIO, their state on the bare 40-pin
header) is **UNVERIFIED**. If they are still plain GPIO, the external route
will be silent even with the amp enabled and the kernel-side switch flipped,
which is a real, distinguishable failure mode -- see the board test plan.

Resolving this needs either: reading U-Boot's FPIOA register configuration
for these four pins on the actual board (a console command, not a source
read), or a stage-1 (U-Boot) change to mux them explicitly. Either is
follow-on work; both are outside "system/kernel" as this project's taxonomy
draws that boundary (`.skills/k230-spec-change/SKILL.md`), since FPIOA muxing
here is a stage-1 concern, not something the Linux device tree owns.
