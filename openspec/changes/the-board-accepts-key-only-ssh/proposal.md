## Why

Every board action today goes through the serial console at 115200 baud:
deployment, test triggers and screenshots. That is slow, and it holds the
single port that the boot controller and recovery need. On 2026-10-11 a
temporary, runtime-only sshd (key-only, under `/run`) made screenshot fetches
and test triggers quick and simple, without taking the serial port. The operator asked for that access to be part of the image.

## What Changes

- The system runs OpenSSH on port 22, reachable over Wi-Fi.
- Login is root by public key only. Password, keyboard-interactive and
  empty-password logins are off, because root's console password stays empty
  for serial autologin.
- The authorized key is one dedicated operator key, committed as a public
  key in `nix/keys/k230-operator.pub`. No private key, address or network
  name is committed.
- The serial console stays the recovery path and keeps its requirements.

## Capabilities

### Modified Capabilities
- `system/console`: adds a requirement for key-only network login alongside
  the serial console.

## Impact

`nix/k230.nix` (all images built from it, including QEMU), `nix/keys/`.
SSH host keys are generated on the board at first start and persist in
`/etc/ssh`.
