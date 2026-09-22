# Kernel support for the image firewall

The daily image's `firewall.service` fails with `iptables: Failed to initialize
nft: Protocol not supported`; see
[shell image journal](shell-features/desktop-launcher/post-boot.txt). Earlier
boots also report a failed firewall unit, including
[shell USB flash](shell-usb-flash-corrected.txt) and
[USB coexistence v2](uboot-ums-host-coexist-v2.txt). This predates the launcher.

The image invokes iptables-nft, not NixOS's native nftables backend. Its actual
`/nix/store/y5w05cq9sg31iqvsxzhkmi00kpgidwih-firewall-start/bin/firewall-start`
uses conntrack, packet types, IPv4/IPv6 reverse-path filters, filter/mangle
chains and DROP/ACCEPT/REJECT rules. Vendor `k230_defconfig` has legacy iptables
modules but omits `NF_TABLES` entirely.

`nix/kernel-firewall.config` seeds the nftables and compatibility dependencies
into the vendor base configuration before Nixpkgs runs oldconfig. Seeding is
necessary because newly enabled NFT_CT and NFT_COMPAT prompts precede some of
their prerequisites in Kconfig; requesting built-ins against the earlier
modular values can leave the interactive generator stuck at a prompt.
`autoModules = false` prevents enabling unrelated vendor modules automatically;
it does not disable runtime module loading.

Configuration-only verification:

```
nix build .#nixosConfigurations.k230.config.boot.kernelPackages.kernel.configfile \
  --option max-jobs 1 --option cores 8 --option substituters https://cache.nixos.org
```

Output: `/nix/store/5y0acf2qzdicdlscn474jfp0xf0807cj-linux-config-riscv64-unknown-linux-gnu-6.6.36-xuantie`.
All 23 requested selections resolve exactly to `y`. No nonexistent NFT_COUNTER
symbol is requested; counter support is part of nftables core in this tree.
The kernel and complete daily image builds passed; see
[build metadata](declarative-daily-build.json). Fresh-image hardware verification passed: [service and rules](shell-features/declarative-defaults/firewall.txt) show active firewall startup, IPv4/IPv6 filter chains with DROP refusal, conntrack acceptance, and mangle reverse-path checks. [Fresh-image state](shell-features/declarative-defaults/fresh-image.txt) records system `whskfvcll29493mgj4lz51mqn23328fa` and no shell service drop-ins. This is installed-policy evidence, not a network packet test.
No firewall policy was disabled or relaxed.
