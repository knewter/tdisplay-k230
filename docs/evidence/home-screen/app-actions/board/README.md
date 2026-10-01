# Home app actions: recoverable physical-board component installation

2026-10-01: the physical board started the exact tested Rust executable from
source `288535289172c8465c4fa408eaa8ba2c7ab8a5ac` and the matching theme-helper
source. [result.json](result.json) records its executable, previous executable,
current system identity and restoration command. Shell, shell UI and theme helper
were active. The system profile and boot configuration remained unchanged.

[install.py](install.py) shows the executed installation. It preserves the normal
wrapper environment and service helper flags, uses two owned runtime drop-ins,
arms a separate root restoration timer before changing services, and checks the
live process executable after restart. The wrapper lives under the shell's
runtime directory so the shell user can execute it. The first attempt used a
root scratch-directory wrapper; startup failed, the exception cleanup restored
normal services, and the corrected retry passed.

On the reserved board the script runs as root with the installed Python:

```sh
env PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /root/tmp/k230-home-menu/install.py
```

The coordinator supplied these exact script bytes over the serial console as
base64; neither credentials nor transport addresses are needed by this script.
The normal compositor/kernel/touch/display configuration was retained, and the
installed Rust CLI plus Sway IPC opened Home. The independent timer restores the
previous services after 1,800 seconds; the original restoration command is in
`result.json` and may also be run immediately by the board operator.

This proves recoverable component installation and live process identity. It is
not a persistent full-system installation, a new boot, a physical mouse click or
real-finger menu/grab acceptance. The specifically named individual Rust output and HDMI coherent-system build
both passed from the same pinned source:

```sh
nix build "git+file://$REPO?rev=288535289172c8465c4fa408eaa8ba2c7ab8a5ac#handheld-shell-rust" \
  "git+file://$REPO?rev=288535289172c8465c4fa408eaa8ba2c7ab8a5ac#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.system.build.toplevel" \
  --no-link --print-out-paths --max-jobs 1 --cores 6
```

Individual output: `/nix/store/lf4vif2s9xdbg07y5j7wljki1sja371l-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
HDMI system: `/nix/store/mm16myp66ksyxm3n7i8lva46ximmghdw-nixos-system-nixos-26.11.20260919.20b1ddd`.
These are build identities, not a claim that the full HDMI system was activated.
Task 11.4 still needs operator acceptance. The operator has been asked to confirm that touch
holds still move icons without opening a menu. Right-click is the menu trigger.


## Actual-board pointer delivery

The [pointer probe](pointer-test.py) uses the same real virtual-pointer protocol
as the paired fixture against the physical board's running compositor and Rust
client. [pointer-result.json](pointer-result.json) records three PASS checks:
right-click reaches the real app menu, an outside click dismisses it, and the
compositor still selects Home with no drawer mapped afterward. The probe reads
only journal event counts into the public record; private window titles and
operator data remain excluded. It restores Home in its cleanup.

```sh
env PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /root/tmp/k230-home-menu/pointer-test.py
```

This is injected input on actual hardware. It establishes compositor/client
delivery and dismissal, separately from a physical mouse or finger observation.
The HDMI closure also contains the exact tested Rust executable and helper
`/nix/store/wcv2wmxgpm53dcw0awd5pf125i6mgf3k-handheld-theme-command-0.1`;
the individual flake output has different package dependencies and is separately
identified above. No full HDMI closure activation is inferred.
