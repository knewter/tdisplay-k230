# Optional mainline DRM power-domain port

Source and host build evidence for task group 5c of
`the-board-runs-a-mainline-kernel`. Physical display power, DRM probe,
illumination and touch remain **UNVERIFIED**; task 5b.5 stays open. No board,
serial, card or normal boot/profile operation was performed for this port.

## Grounding and exact source boundary

The pinned vendor source is
`ruyisdk/linux-xuantie-kernel` revision
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`, specifically:

- `drivers/soc/canaan/k230-power-domains.c`;
- `include/dt-bindings/soc/canaan,k230_pm_domains.h`;
- `drivers/soc/canaan/Kconfig` and `Makefile`;
- `arch/riscv/boot/dts/canaan/k230.dtsi`, `sysctl_power` at `0x91103000`.

These files were read from the project's evaluated vendor source output
`/nix/store/hn11x8zd5linl193d8q0k9k99b46zqbm-linux-xuantie-k230-src`.
The pinned mainline source still has no K230 provider; its
`drivers/soc/canaan/Kconfig`/`Makefile` wire only K210 sysctl. The port is
added in `nix/kernel-mainline-drm.nix`, never in the console/default kernel.
The candidate DTB builder includes the local binding header, while the
console DTB uses its original inputs.

Prior vendor-board evidence in `docs/evidence/dsi-phy-hang.md` records all-ones
DSI reads/DCS timeouts until a probe-time DISP runtime-PM reference was held;
that reference allowed PHY/DCS initialization to progress. It establishes a
real power dependency on this board. It does not establish that this new
mainline provider runs correctly, nor that U-Boot always leaves DISP off.

## Changes preserved and adapted

`nix/patches/mainline/k230-power-domains.c` retains the vendor five-domain
one-cell ABI: CPU1=0, AI=1, DISP=2, VPU=3, DPU=4. The binding header is copied
verbatim. The full offset table is preserved; DISP uses power-enable/status
at `0x3c`/`0x40`, on/off bits 1/0 and write-enable bits 17/16. Only AI uses
repair, with vendor enable/write-enable bits 4/20 and the existing status
mask `0x7`. Poll loops retain the vendor 1000 one-microsecond iterations,
including the early return when the requested status is already present.
CPU1/AI/DPU retain their always-on policy; DISP/VPU retain the vendor initial
genpd-off state. No clock/reset mapping was changed.

The port replaces global controller/domain state with per-device allocation.
Every vendor domain had `soft_control_enable=true`, so that unused condition
is removed. The vendor hardlock values were read but never used; the port
omits those reads/globals and the unused `CANAAN_HARDLOCK` selection. Genpd
initialization and provider registration now check their results and use a
managed cleanup action for successfully initialized domains. The built-in
controller suppresses manual unbind while consumers may exist.

The mainline `include/linux/pm_domain.h` still declares the genpd init,
remove and one-cell provider APIs used here; `kernel/power/Kconfig` defines
`PM_GENERIC_DOMAINS_OF` from generic domains plus OF. The DRM-only config
requests PM, generic/OF domains, and `SOC_K230_PM_DOMAINS` as built-ins.

The candidate DRM master already held power at probe. It now uses
`pm_runtime_resume_and_get()` and returns a probe error on failed resume,
disables runtime PM on that failure, and releases the probe-owned reference
on component registration/matching failure or platform removal. Successful
probe retains the reference before binding/modesetting. This keeps the
vendor-observed lifetime rather than relying on opening a DRM device later.

The candidate DTB retains the vendor compatible spelling
`"canaan, k230-sysctl-power"` on both source/DT sides. Its provider has
`reg=<0 0x91103000 0 0x1000>` and `#power-domain-cells=<1>`. The logical
`/display-subsystem` consumer has `<provider-phandle K230_PM_DOMAIN_DISP>`.

## Host proof and limits

`nix build .#deviceTreeMainlineDrm --no-link --print-out-paths --max-jobs 1
--cores 8` exited 0 with
`/nix/store/nxbrd4smrcmknipjn4hjk32n87p4g9k6-k230-tdisplay-mainline-drm.dtb`.
`fdtget` confirmed provider phandle `0xd`, display consumer `<0xd 2>`, the
expected reg tuple, one domain cell, and matching compatible. A full DTB
round-trip produced only two existing `graph_child_address` warnings for
single-child VO and panel graph nodes. The companion log preserves them.

The resolved candidate config has `CONFIG_PM=y`,
`CONFIG_PM_GENERIC_DOMAINS=y`, `CONFIG_PM_GENERIC_DOMAINS_OF=y`,
`CONFIG_SOC_K230_PM_DOMAINS=y` and `CONFIG_DRM_CANAAN=y`, so the provider
and OF genpd attach path are built in rather than stubbed out.

`nix build .#kernelMainlineDrm --no-link --print-out-paths --max-jobs 1
--cores 8` exited 0 with
`/nix/store/i77i3ppi72k9hw0v2xmnhilc3q7rvv50-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
The full kernel log includes both the provider and DRM master object
compilations. The matching bundle build also exited 0 with
`/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-k230-mainline-drm-trial-boot-files`,
selecting system
`/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd`.
The durable inspector passed Image/kernel identity, DTB/environment bootargs,
U-Boot architecture/header/payload CRCs, exact system initrd payload,
checksums, and the 629-path closure inventory. `nix flake check --no-build`
also passed. Default and console source inputs were unchanged, as recorded
by the narrow diff command in the log. The initial matching boot
preparation snapshot in `mainline-display-boot-preparation.md` names the
older candidate without this provider. Use the matching bundle above for
the operator trial; do not mix snapshots.

The operator staging/manual U-Boot/normal-restoration procedure remains in
`docs/evidence/mainline-display-boot-preparation.md`. This work addresses
the source power boundary. Actual root boot, probe-time power acquisition,
DSI PHY/DCS results, panel photograph, finger interaction and normal-system
restoration still require committed physical evidence before 5b.5 can close.
