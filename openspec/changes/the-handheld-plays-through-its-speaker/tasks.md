All tasks below name the narrowest real command that proves them. Host
build and QEMU boot are one evidence class; a console transcript or
recording from the physical board is a different one, and no task here
claims the second from the first. Store board evidence under
`docs/evidence/max98357a-speaker/` with commands, timestamps and limits.

## 1. Research and record what's grounded

- [x] 1.1 Read `Xinyuan-LilyGO/T-Display-K230` (`k230_bsp/docs/HARDWARE_PINMAP.md`, `README.MD`, `CHANGELOG.MD`, patches 0058/0059, `ui_hardware.c`/`ui_audio.c`) via `gh api` and record pins, enable GPIO, board placement and route-switch mechanism with file/line citations. Recorded in `docs/evidence/max98357a-speaker.md`.
- [x] 1.2 Read the pinned kernel source (`linux-xuantie-k230-src` store path from `nix/kernel-src.nix`) for `sound/soc/canaan/canaan_k230_{inno,audio}.c`, confirm `CONFIG_SND_SOC_MAX98357A`/`CONFIG_SND_SIMPLE_CARD`/`CONFIG_SND_AUDIO_GRAPH_CARD` availability, confirm no `pinctrl-k230`/FPIOA driver exists, and confirm `canaan_k230_inno.c`'s pre-patch state matches LILYGO's 0059 hunk context byte-for-byte.

Proof: `docs/evidence/max98357a-speaker.md`, citing file paths and, where applicable, line numbers or commit hashes.

## 2. Kernel: expose the existing route switch

- [x] 2.1 Add `nix/patches/canaan-audio-external-i2s-switch.patch` (ported from LILYGO's 0059) and wire it into `nix/kernel.nix`'s patch list with a comment explaining provenance and why it applies unmodified.
- [x] 2.2a Build the kernel: `nix build .#kernel --max-jobs 1 --cores 6 --no-link --print-out-paths` -> `/nix/store/ix67lsrfp2y1d6dcb4q5mg1b2aa6snhl-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`. Host cross-build proof only; does not prove the module binds on hardware.
- [ ] 2.2b Board proof: `dmesg | grep -iE 'canaan-k230-snd-inno|External I2S'` on the board after a `/boot` install and reboot.

Proof for 2.1/2.2a: the patch applies (`patch -p1 --dry-run` verified against the unpacked pinned source during development) and `nix build .#kernel` succeeds -- done, host-only. Proof for 2.2b is a board task: a QEMU boot does not model this SoC's audio peripheral (`.skills/k230-spec-change/SKILL.md`'s QEMU-proof table), so only a board `dmesg` capture proves the module bound with the new control present.

## 3. Device tree: document the pins, keep the default route

- [x] 3.1 Add `gpio-line-names` for GPIO32/33/34/35 to `&gpio1_ports` in `nix/dts/k230-tdisplay.dts`, with the UNVERIFIED-FPIOA-muxing note inline. Leave `canaan,external-i2s-output-default` unset.
- [x] 3.2 Build the DTB and confirm it compiles clean: `nix build .#deviceTree --no-link --print-out-paths` -> `/nix/store/mwmnah2mh77zncj83r5kcp2q8yn6k7kd-k230-tdisplay.dtb`. Decompiled with `dtc -I dtb -O dts` and confirmed the `gpio-line-names` property lands on `gpio1_ports` exactly as written.

Proof: `nix build .#deviceTree` -- done, host-only. This proves the DTB compiles; it does not prove the named GPIO lines exist as such at runtime on the board (that needs `gpioinfo gpiochip1` on hardware, task 5.2).

## 4. Userspace helper

- [x] 4.1 Add `nix/k230-speaker-test.nix` (`status`/`internal`/`external` subcommands) and install it plus `alsa-utils`/`libgpiod` in `nix/hardware.nix`'s `environment.systemPackages`, each with a recorded reason per that file's existing convention.
- [x] 4.2a Build the closure: `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths` -> `/nix/store/lfq1j4rb9a1pmbqy3q56vh26j9054hqa-nixos-system-nixos-26.11.20260919.20b1ddd`. `k230-speaker-test.drv` and `alsa-utils`/`libgpiod` both built as part of `.#sdImage-coherent`.
- [ ] 4.2b Board proof: `k230-speaker-test status` on the board.

Proof for 4.1/4.2a: the toplevel closure and SD image build, and the script package builds -- done, host-only. Proof for 4.2b is a board task -- the script's `gpioset --mode=signal` usage is explicitly UNVERIFIED against the flake's actual pinned `libgpiod` version (design.md), so the first board run is also the first real test of that assumption.

## 5. Board verification (all open; this proposal claims none of them)

- [ ] 5.1 Install the built `Image`/`k230-tdisplay.dtb` to `/boot` and reboot (a DT/kernel change does not take effect from a system activation alone). Record `cat /proc/asound/cards`, `dmesg | grep -iE 'max98357|i2s|inno|asoc'`, `aplay -l`.
- [ ] 5.2 Run `k230-speaker-test status` and `gpioinfo gpiochip1` to confirm the named GPIO lines and the presence (or absence) of the "External I2S Output Switch" control.
- [ ] 5.3 Run `k230-speaker-test internal` and have the operator confirm audibly whether the Inno line-out/headphone path still works exactly as before this change (regression check -- this change must not break it).
- [ ] 5.4 Run `k230-speaker-test external` and have the operator listen for the MAX98357A speaker, or record with a microphone near the board if no operator is present (per `docs/evidence/use-the-camera-not-the-user.md`-style discipline: do not infer a hardware result from a host-only check). Record which of the three failure modes below was observed, if any.
- [ ] 5.5 Determine and record whether the nRF52840 audio/sensor add-on board is physically attached to this hardware at all. Absent it, tasks 5.4's success criterion cannot be met regardless of software correctness, and that is the expected, honest outcome to record -- not a bug in this change.

Proof: a committed console transcript/recording under `docs/evidence/max98357a-speaker/`, naming exactly which of these outcomes was observed:

- **No add-on present:** `aplay -l`/`cat /proc/asound/cards` show only `CANAAN-K230-I2S`; `k230-speaker-test external` runs without error but nothing audible plays even with a working GPIO/route, because there is no amplifier on the other end of the pins. Expected if 5.5 finds no add-on.
- **Add-on present, pins not muxed:** the ALSA control and GPIO both operate without error, but no sound plays. Distinguishing evidence: the route bit flips (`amixer cget` reflects the new value) and GPIO34 reads back high, but GPIO32/33/35 never carry an I2S signal because U-Boot left them as plain GPIO -- the open gap in `docs/evidence/max98357a-speaker.md`.
- **Everything works:** audible 440 Hz tone through the speaker on `external`, and the headphone/line-out path unaffected on `internal`. This is the only outcome that would let 5.4/5.5 be ticked as fully passing.

## 6. Close deliberately

- [ ] 6.1 After task groups 2-5 either pass or have their exact blocker recorded, run `openspec validate --strict the-handheld-plays-through-its-speaker` and `python3 scripts/render_work_board.py > /dev/null`.
- [ ] 6.2 If board tasks in group 5 remain open, keep this change open with those tasks unchecked rather than archiving early; do not tick 5.1-5.5 without the named evidence file existing.

Proof: `openspec validate --strict` and `render_work_board.py` exit 0. Neither substitutes for the board evidence group 5 names.
