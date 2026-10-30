## ADDED Requirements

<!-- UNVERIFIED: the driver, device-tree node and module are not yet built or booted; no board observation of a GPU device on mainline exists. -->
### Requirement: The mainline kernel exposes the VG-Lite GPU

The mainline system SHALL describe the K230 2D GPU in its device tree and SHALL carry a driver for it, so that `/dev/vg_lite` exists after boot and a GPU command submitted through the vendor SDK library completes. The default shell SHALL continue to render with Pixman; the existing opt-in VG-Lite renderer SHALL remain the only consumer.

*Grounding (2026-10-30): the boot-default system has no `/dev/vg_lite`, no `gpu@90800000` node and no GPU driver (`docs/evidence/vglite-mainline-blocker/README.md`); the vendor driver and node are in `ruyisdk/linux-xuantie-kernel` @ `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`, `drivers/gpu/vglite/vg_lite_hal.c` and `arch/riscv/boot/dts/canaan/k230.dtsi`; mainline 7.3-rc5 provides `K230_DISPLAY_GPU_GATE`, `RST_GPU` and `drivers/reset/reset-k230.c`.*

#### Scenario: The device appears after boot

- **WHEN** the board boots the mainline system carrying the GPU node and module
- **THEN** `/dev/vg_lite` exists, the kernel log records the GPU driver probing, and no existing device (panel, touch, Wi-Fi, audio) is missing

#### Scenario: A GPU command completes

- **WHEN** a root process runs the existing VG-Lite probe against `/dev/vg_lite`
- **THEN** its private-buffer fill or blit completes and reads back the expected pixels

#### Scenario: Pixman stays the default

- **WHEN** the shell starts without the explicit experimental renderer selection
- **THEN** it renders with Pixman and does not open `/dev/vg_lite`

#### Scenario: Other hardware is not regressed

- **WHEN** the board has rebooted with the GPU node installed
- **THEN** the panel shows the shell, touch input works, Wi-Fi associates and audio plays as they did before the change
