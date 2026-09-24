# Rust drawer icon checkpoint

The opt-in Rust drawer reads installed desktop entries through GIO, resolves their `GIcon` using the selected freedesktop theme with bounded inheritance and `hicolor` fallback, then decodes PNG/SVG through Cairo/librsvg. A missing or rejected icon retains its text label and letter tile. Source and `index.theme` files, recursive theme depth, directory count, icon count, decoded icon size, and the 12-entry lazy cache are bounded. Calling `set_theme` clears cached hits and misses even when a new appearance generation selects the same theme name. The current session still needs to call it on theme adoption; this is drawer artwork groundwork, not complete task 1.4.

The host tests cover inherited SVG lookup, native decode, cache reuse/invalidation, malformed names, and a rendered absolute SVG app icon. The fixture screenshot below uses three `.desktop` entries with fixed public labels and their real Nix store Foot, htop and mpv icons. `XDG_DATA_HOME` contained only those entries; `XDG_DATA_DIRS` pointed at the three packages' `share` directories. The client rendered `--render-fixture drawer` at 568×1232. The image is a host software render, not a board photograph or physical interaction result.

![Host Rust drawer with Foot, htop and mpv icons](rust-icons-host.png)

The exact icon asset paths, SHA-256 values, source links and license notices are recorded in [the design study's icon provenance](../../design/handheld-prototype/README.md). The screenshot contains no private app catalog or device data.

Exact source commit `23d703f77595f8dea4d69f351b7d22209da02489` subsequently passed:

```sh
nix build "git+file://$PWD?rev=23d703f77595f8dea4d69f351b7d22209da02489#handheld-shell-rust" --max-jobs 1 --cores 4 --no-link --print-out-paths
```

The target derivation `/nix/store/pp2ib3y9ysbpz9mv3nnkzxkpbrrp70xs-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv` produced `/nix/store/4xmskqli9r93qrl41qx6ybs7593pzq8j-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`. `file` reports ELF64 RISC-V LP64D; `nix path-info -S` reports 114,784,312 bytes recursive closure. The added librsvg dependency increases closure relative to the earlier no-icon client. This build is not an installed session or visual board result. Remaining gates are theme generation hookup, app tap/launch, card and notification identity consumers, and physical visual/touch plus measured decode cost.

Source correction `fbcdfd3222f990022db1e029766abeb2227ced37` parses comma-separated freedesktop `Directories`, `ScaledDirectories`, and `Inherits` lists. Fixtures cover a match in the second directory, the second inherited theme, and a scaled directory. Host tests and clippy pass. The exact corrected target was built with:

```sh
nix build "git+file://$PWD?rev=fbcdfd3222f990022db1e029766abeb2227ced37#handheld-shell-rust" --max-jobs 1 --cores 4 --no-link --print-out-paths
```

Derivation `/nix/store/29vdbji0pa6j0j2p29wr3fl97sk8wdp0-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv` produced `/nix/store/cmdsldi6vgq22nrmc9kfqnww3f7s26ci-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`. This remains a target build, not a board or physical icon observation.
