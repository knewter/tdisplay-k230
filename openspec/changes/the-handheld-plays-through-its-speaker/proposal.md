## Why

A person cannot currently hear anything the handheld plays without plugging
in headphones. The device tree enables only the SoC's internal Inno codec
(`nix/dts/k230-tdisplay.dts`'s `sound` node), and nothing on this board has
ever exercised even that path with a userspace tool -- there is no committed
boot log, `aplay` run, or `/proc/asound/cards` capture anywhere in this
repository before this change. LILYGO's own firmware README advertises a
"MAX98357A external I2S amplifier and audio route switching" for this board
family, which is the closest thing to a built-in loudspeaker this hardware
offers.

Investigating that claim (`docs/evidence/max98357a-speaker.md`) found a
firmer answer than "which board holds the amp": LILYGO's own hardware map
(`k230_bsp/docs/HARDWARE_PINMAP.md` in `Xinyuan-LilyGO/T-Display-K230`) puts
the MAX98357A on a **third, separate, optional add-on board** ("nRF52840
BLE / Audio / Sensor Base Board") -- not the main T-Display-K230 board this
project has, and not the nRF9151 keyboard base either. Whether that add-on
is physically present here is unrecorded and UNVERIFIED. This proposal
therefore does the software work that is correct regardless of the answer --
the Inno codec keeps working exactly as it does today, and a real,
kernel-level route to the external amp becomes available and testable -- and
states plainly what remains unproven: physical amp presence and the actual
FPIOA pin muxing for its I2S signals.

## What Changes

- Add a `system/audio` capability describing what this board's audio output
  actually does: the Inno codec as the default line-out/headphone path, and
  an opt-in external-I2S route for an attached MAX98357A amplifier.
- Port a small, closely-grounded kernel patch
  (`nix/patches/canaan-audio-external-i2s-switch.patch`) that adds an
  "External I2S Output Switch" ALSA control to the existing
  `canaan,k230-audio-inno` machine driver, exposing a register-level route
  already present in the pinned kernel's own `audio_i2s_enable_audio_codec()`
  (`sound/soc/canaan/canaan_k230_audio.c:50-59`) but previously hardcoded to
  the internal codec. This is a direct, byte-context-verified port of
  LILYGO's own `0059-asoc-canaan-add-external-i2s-output-switch.patch`.
- Document the MAX98357A's four board pins (BCLK GPIO32, LRCK GPIO33, DOUT
  GPIO35, SDMODE GPIO34) in `nix/dts/k230-tdisplay.dts` via `gpio-line-names`
  on the already-enabled `gpio1_ports` controller -- descriptive only, no
  driver claims the line, matching how LILYGO's own launcher controls the
  same enable pin directly from userspace via libgpiod.
- Add a `k230-speaker-test` operator helper (`nix/k230-speaker-test.nix`,
  `alsa-utils` + `libgpiod`) that reports ALSA/GPIO state, and drives each
  route with a 440 Hz test tone, restoring the Inno default afterward.
- Leave the Inno codec's default route untouched: no
  `canaan,external-i2s-output-default` property is set, so a board with no
  amp attached at all still boots exactly as before.

**Non-goals:** Adding a `maxim,max98357a` ALSA codec device-tree node
(rejected -- see `docs/evidence/max98357a-speaker.md`: it would claim
GPIO34 exclusively via `devm_gpiod_get`, conflicting with the userspace
helper, and nothing wires it into any dai-link for its DAPM power sequencing
to do anything). Adding a second ALSA sound card (rejected -- the existing
machine driver already owns the sole physical I2S/SAI peripheral;
LILYGO's own design does not do this either). Muxing GPIO32/33/35 to their
I2S alternate function in U-Boot/stage 1 (this SoC's FPIOA table is a
stage-1 concern outside the Linux device tree; see the same evidence file).
Confirming whether the nRF52840 audio add-on is physically attached to this
project's board (a board observation this proposal cannot make from source
alone).

## Capabilities

### New Capabilities

- `system/audio`: what the board's audio output does today (Inno codec
  default) and the opt-in external-I2S route a MAX98357A amplifier can use,
  with the physical-amp and pin-muxing gaps stated as open, not assumed.

### Modified Capabilities

None. `system/kernel` already covers "kernel carries patches, recorded with
origin and reason" generically; this proposal adds one such patch but does
not change that capability's requirements.

## Impact

`nix/dts/k230-tdisplay.dts`, `nix/kernel.nix`, `nix/patches/canaan-audio-
external-i2s-switch.patch` (new), `nix/k230-speaker-test.nix` (new),
`nix/hardware.nix` (new packages). The kernel derivation rebuilds because its
source patch set changed. A device-tree-only or kernel-only change like this
does not take effect through a plain system activation -- it needs the
built `Image`/`k230-tdisplay.dtb` installed to the board's `/boot` partition
and a reboot, per `.skills/k230-spec-change/SKILL.md`'s DT-push note. No task
here claims board proof; every hardware-observable requirement in the new
spec is marked `<!-- UNVERIFIED -->` and stays open until a board test is
run.
