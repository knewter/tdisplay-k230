# Full coherent shell on the mainline kernel, display and touch

2026-10-06. Physical UART, camera and real-finger evidence for the mainline
DRM kernel, following [clock ownership](../mainline-clock-ownership-2026-10-06/README.md).
All candidate boots used the guarded staging pattern, volatile U-Boot
selection and the reviewed recovery checker; every run below returned to the
protected normal system (distinct boot, exact identities, eight boot hashes,
three services, registration absent). [runs.json](runs.json) binds each
private capture by SHA256.

## Display: the purple screen

With `spi2axi` fixed the console system logged in, but the panel showed a
uniform purple ([still](panel-purple-background.jpg)). Nothing draws purple:
the VO background register is written `0xffffff`, which the hardware treats as
YUV, so with no layer visible only the background colour reached the panel.
The DRM state and the OSD4 shadow registers all pointed at fbcon's buffer, and
writing a pattern into `/dev/fb0` changed nothing; blanking still worked.

The earlier unused-gate list had been read through `head -150` and was
incomplete. A full `clk_summary` from a live `clk_ignore_unused` boot listed
ten more on-but-unclaimed gates. Camera-judged bisection (no operator resets,
each passing boot rebooted itself): holding those ten restored the console
(M10), as did `vpu_ddrcp2` + `vpu_axi` (N1) and `vpu_ddrcp2` alone (N2/N2b; the
operator also saw the NixOS login prompt). Fix `7fd13b68` marks
`K230_VPU_DDRCP2_GATE` (sysctl `0x60` bit 5, a DDR controller port) critical,
and moves `dphy_dft_gate` from `0x100` bit 0 (aliased onto the USB 480M/100M
bit) to `0x104` bit 0 per the vendor `dphy_test_clk`. The rebuilt console
bundle shows the console on black ([still](console-after-ddrcp2-fix.jpg)).
Power domains were not the cause: `pm_genpd_summary` shows `disp_domain` on
with `display-subsystem` active.

## Full shell

`k230-mainline-drm-shell` (`bb4f49b6`) is `k230-coherent-shell` with only the
mainline DRM kernel swapped in and the vendor-tree Wi-Fi module removed; only
30 store paths (~175 MB) were missing on the board. Its first boot was qualified
by the controller, but `shell.service` restart-looped: sway reported
`Failed to open device: '/dev/dri/card0': Invalid argument` and the kernel
warned at `drm_file.c:329`. Since v6.12 `drm_open_helper()` rejects fops
without `FOP_UNSIGNED_OFFSET`; the hand-ported canaan fops lacked it. Fix
`dfe2cd2c` adds the flag. The rebuilt full shell (bundle `1lc4jd6v…`) was
qualified `candidate-ready-qualified-ordinary-init`; `shell`, `shell-ui` and
`seatd` were active, sway mapped the card shell, and the panel matched the
normal system's Home photographed from the same position seconds later
([comparison](full-shell-mainline-top-vs-normal-bottom.jpg), mainline top).
`firewall.service` failed (kernel netfilter options, not investigated). The
PMU power key and Wi-Fi drivers are vendor-only and absent; audio was not
tested. The camera angle is oblique; this is a visual match, not a pixel
comparison. Sway logs `Failed to import buffer for scan-out` at debug level
(direct scan-out falls back to composition).

## Deliberate touch

On the fixed console candidate (`0b327025`), the controller's `touch --real-touch`
phase ran `evtest` on the Goodix Berlin touchscreen for 30 s while the operator
touched the glass: 533 multitouch position events, 4 `BTN_TOUCH` down/up pairs
and matching tracking-ID releases; the camera shows the finger on the glass
during the window ([still](touch-finger.jpg)). The controller itself returned
`touch retrieval completion unverified`: reading ~240 KB of evtest text back at
115200 baud outlasted its wait, so the event counts above come from the raw
serial capture, not the controller's parser. Touch inside the full shell (sway
input) was not separately exercised.
