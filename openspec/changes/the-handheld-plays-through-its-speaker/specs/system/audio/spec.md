## Purpose

Define what this board's audio output actually does: the always-available
Inno codec line-out/headphone path, and the opt-in route to an external
MAX98357A amplifier that some, but not necessarily this, board carries.

## ADDED Requirements

### Requirement: The Inno codec is the default audio output and is unaffected by this change

*Grounding: `nix/dts/k230-tdisplay.dts`'s `sound` node, `compatible =
"canaan,k230-audio-inno"`, unchanged by this proposal except that
`canaan,external-i2s-output-default` is deliberately left unset. Kernel-side,
`sound/soc/canaan/canaan_k230_inno.c`'s probe path now calls
`k230_inno_apply_output_route()` with `external_i2s_output` initialized from
that (absent) property, which evaluates to the same
`audio_i2s_enable_audio_codec(true)` call the unpatched driver made
unconditionally.*

<!-- UNVERIFIED --> The system SHALL boot with the Inno codec as the active
audio route, matching pre-change behavior, on any board regardless of
whether a MAX98357A amplifier is attached.

#### Scenario: A board boots with this change applied
- **WHEN** the system boots with the patched kernel and unmodified device tree
- **THEN** `/proc/asound/cards` shows the `CANAAN-K230-I2S` card and audio played on it reaches the Inno codec's line-out/headphone path, exactly as before this change

### Requirement: An external I2S route to a MAX98357A amplifier is selectable without a reboot

*Grounding: `nix/patches/canaan-audio-external-i2s-switch.patch`, a port of
`Xinyuan-LilyGO/T-Display-K230` commit `37b66b38`
("0059-asoc-canaan-add-external-i2s-output-switch.patch"), verified to apply
cleanly against `sound/soc/canaan/canaan_k230_inno.c` in the pinned kernel
source (`nix/kernel-src.nix`, `ruyisdk/linux-xuantie-kernel@7d4e1f4`). The
underlying register mux, `audio_i2s_enable_audio_codec()`, is vendor source
at `sound/soc/canaan/canaan_k230_audio.c:50-59`, read directly, not inferred
from a datasheet.*

<!-- UNVERIFIED --> The system SHALL expose an ALSA control named "External
I2S Output Switch" that, when set, stops feeding the Inno codec and drives
the raw I2S signal onto GPIO32 (BCLK), GPIO33 (LRCK) and GPIO35 (DOUT)
instead, and SHALL restore the Inno codec route when the control is cleared.

#### Scenario: An operator switches to the external route
- **WHEN** an operator runs `amixer -q cset name='External I2S Output Switch' 1`
- **THEN** the control reads back as set and subsequent playback drives the external I2S pads instead of the Inno codec, without a reboot

#### Scenario: An operator switches back
- **WHEN** an operator runs `amixer -q cset name='External I2S Output Switch' 0`
- **THEN** subsequent playback returns to the Inno codec route

### Requirement: The MAX98357A enable line is a plain, documented GPIO, not a kernel-owned device

*Grounding: `k230_bsp/docs/HARDWARE_PINMAP.md` (Xinyuan-LilyGO/
T-Display-K230), "Shutdown control, GPIO34, high enables the amplifier, low
shuts it down", independently confirmed by `ui_hardware.c:68`
(`AMP_SHUTDOWN_GPIO 34`) and `ui_hardware.c:1655-1731`'s libgpiod-based
implementation. GPIO34 is bank 1 offset 2
(`k230.dtsi:415-421`, `gpio1_ports`).*

<!-- UNVERIFIED --> The system SHALL NOT bind a kernel driver that claims
GPIO34 exclusively. `gpio-line-names` on `gpio1_ports` SHALL document the
line for discoverability without requesting it, so a userspace helper using
libgpiod can request and release the line at will.

#### Scenario: A userspace helper toggles the amplifier
- **WHEN** an operator runs `k230-speaker-test external`
- **THEN** the helper requests GPIO34 (chip `gpiochip1`, offset 2) via libgpiod, drives it high for the duration of the test, and releases it afterward, with no kernel driver reporting the line already busy

### Requirement: Physical amplifier presence and I2S pin muxing are stated as open, not assumed

*Grounding: `k230_bsp/docs/HARDWARE_PINMAP.md` places the MAX98357A on the
optional "nRF52840 BLE / Audio / Sensor Base Board", separate from the main
T-Display-K230 board and from the nRF9151 keyboard base; nothing in this
repository has recorded that add-on's presence before this change. Separately,
`docs/dts-evidence.md` and this change's own re-reading of the pinned kernel
tree confirm no pinctrl/FPIOA driver exists in the Linux device tree, so
GPIO32/33/35's alternate-function muxing is a stage-1 (U-Boot) fact this
project cannot currently read or set from Linux.*

<!-- UNVERIFIED --> The project SHALL record, as a board observation and
not an inference from a README or a schematic for a different SKU, whether
the MAX98357A add-on is physically present, and whether GPIO32/33/35 carry
an I2S signal when the external route is selected.

#### Scenario: The board is checked for the add-on and pin function
- **WHEN** an operator runs the task-group-5 board procedure (`k230-speaker-test status`, `k230-speaker-test external` with a listening operator or a nearby microphone recording)
- **THEN** the outcome is recorded as exactly one of: no add-on present, add-on present but pins not muxed for I2S, or a working external route -- and the recorded outcome, not a source-level plausibility argument, is what this requirement is graded against
