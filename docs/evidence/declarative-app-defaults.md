# Declarative application defaults, 2026-09-22

The user requires a usable fresh image, without restoring home-directory state.
Commit `e9d7916` adds system-wide `/etc/htoprc`, `/etc/xdg/foot/foot.ini`, and
`/etc/neofetch/config.conf` through `nix/shell.nix`. The profiles are repository
sources; custom user profiles may override these defaults.

Neofetch's packaged system-config fallback preserves explicit `--config` and
user-file precedence. When the system file exists, it uses that file without
creating a default file in the user's home. The CPU microarchitecture patch
remains part of the same package. Compact display settings previously supplied
as demo flags now live in `nix/neofetch.conf`.

Host verification:

- `nix eval --raw .#nixosConfigurations.k230.config.system.build.toplevel.drvPath`
  produced `/nix/store/x3k77l47skzj50w7z29z6lnmlpyz7sn2-nixos-system-nixos-26.11.20260919.20b1ddd.drv`.
- `nix build .#neofetch --option max-jobs 1 --option cores 8 --option substituters https://cache.nixos.org`
  built `/nix/store/69pxr9pgwzag5nvdf6zvqhf9d4iadrrh-neofetch-7.1.0`; both patches
  applied and the derivation's `bash -n` check passed.
- The shell OpenSpec change validates. Its task 5.7 remains open until these
  defaults are built into the system and demonstrated on the board with a fresh
  home. The earlier normal-image launcher capture predates this defaults change.

No private backup was restored. An in-progress archive transfer was stopped
before extraction and its partial temporary board files removed. Private backup
contents remain outside the repository and are not part of the image workflow.

The complete daily image subsequently built successfully from source `6b59f33`:
`/nix/store/qmib01kmi68dwygxymmwga3b5h23gmal-k230-sd-image.img`
(2,308,689,920 bytes). [Build metadata](declarative-daily-build.json) records the
command and elapsed time, including the wait for the shared kernel build.
Fresh-image board verification remains pending.


Final fresh-image verification passed after committing the portrait gap/distro
layout correction in `7a83afa`. [Evidence](shell-features/declarative-final/README.md)
contains plain-launch screenshots and camera clips, an initially empty home,
immutable config links, 577 automatically registered closure paths, and no
Neofetch-generated user config. Shell task 5.7 is complete.
