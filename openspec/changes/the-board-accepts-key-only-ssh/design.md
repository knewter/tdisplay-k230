## Context

`nix/k230.nix` is the base module for every image. It sets root's password
to empty so that the serial console autologs in. The NixOS firewall is on
(`nixos-fw`). On 2026-10-11 the installed system had an `sshd` binary but no
running service, no `sshd` privilege-separation user and no port open.

## Decisions

- **Enable `services.openssh` in the base module.** NixOS creates the `sshd`
  user, `/var/empty` and host keys, and `openFirewall` opens port 22.
- **Key-only root login.** `PermitRootLogin = "prohibit-password"`,
  `PasswordAuthentication = false`, `KbdInteractiveAuthentication = false`.
  `PermitEmptyPasswords = false` is set explicitly, not left to OpenSSH's default. The empty console
  password therefore cannot be used over the network.
- **One dedicated key.** A new ed25519 key made for this board is authorized,
  rather than the operator's general keys, so access can be revoked on its
  own. Only the `.pub` file is committed.
- **Host keys are generated on the device** at first start (the NixOS
  default) and are not committed.

## Rejected

- Rebuilding in place on the board: the board has no source tree, building on
  the C908 is very slow, and it would switch the profile outside the guarded
  installer and its rollback roots.
- Keeping the runtime-only `/run` sshd: it disappears at every reboot and
  needs a bind-mounted `passwd` entry and a runtime firewall rule.
- Password login: root's password is empty by design for the console.

## Risks

- Anyone holding the private key can log in as root over the local network.
  Mitigation: a dedicated key, kept in the operator's `~/.ssh`, can be
  dropped from `nix/keys/` in a later image.
