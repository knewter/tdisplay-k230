# Physical minimal initrd diagnostic

Run started 2026-10-02 at 07:19:53 UTC from source
`d209a062f6826877173a7d2669d99b18c82c6416`:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal
```

The controller verified the normal p1 system, staged candidate closure and
protected boot files, then checked the five U-Boot load counts and CRCs before
booting the matching mainline bundle with volatile `rdinit=/bin/sh` arguments.
No persistent boot selection, profile or boot file was changed.

The fresh receipt marker and `/bin/true` return code 0 prove that this run
reached the diagnostic shell and executed that external command. The bracketed
`/proc/uptime` command returned 1 with a missing-file error. The probe had not
mounted `/proc`; this error does not prove a broken proc filesystem or kernel.
The reboot receipt marker was followed by the explicit refusal
`Running in chroot, ignoring request.` and a returned shell prompt. The
controller's normal-login deadline then expired. This run **failed** its
diagnostic/recovery gate; the receipt marker does not prove a reboot.

After the controller released serial, a separate deliberate recovery check
sent only a carriage return and waited five seconds for a fresh shell prompt.
None arrived, so it sent no mount, reboot, interrupt or exit command. A physical
power cycle was requested. Normal-system recovery remains pending for this
attempt; the preceding recovery evidence proves the earlier boot only.

`observation.json` records the observed marker results, exact source and
artifact identities, preflight and private capture hash. Raw serial output
remains outside the repository in the protected capture directory. Evidence
is physical-board serial output; there is no new glass acceptance, usable
mainline NixOS root, touch result or SBI reset conclusion. Task 5b.5 stays open.

The next controller revision must mount `/proc` and require its successful
return marker before reading uptime or requesting reboot. Host verification
of that revision will remain distinct from this failed physical run.
