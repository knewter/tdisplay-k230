## Context

This preserves original HDMI tasks 3.1–3.3 and the complete manual-switch
requirement. Source prototype `58498320` is parked and removed, with no matching
physical Settings/restore sequence. Automatic HDMI switching is separate and
accepted. The successor is a reviewable plan, not a shipped requirement.

## Goals / Non-Goals

Provide the optional confirmed Settings switch and panel restoration only after
new implementation authorization. Keep default automatic switching, recovery
bundles and protected stage 1 intact. No landscape or latency work belongs here.

## Decisions

Layers: Nix boot-file wiring, userspace selector/controller and early restoration,
and Rust Settings UI. Reuse the existing `force_dtb` selector atomically rather
than overwrite protected payloads. Target mainline qualification trees; retain
vendor toplevel as a rollback host regression check.

The original guarantee covers every next-boot cause. Early Linux restoration
cannot establish it if the HDMI boot fails before Linux restores the selector.
Keep that requirement UNVERIFIED. Before implementation, either establish a
stage-1-safe one-shot mechanism meeting the original guarantee or obtain an
explicit scope revision; do not silently weaken it to a Linux-only guarantee.
Until proved, protected serial recovery is required and a power cycle is not
advertised as recovery. The historical prototype does not resolve this risk.

## Validation

Original host and physical commands remain in tasks. Physical forward/revert,
connector state, visible output and actual touch acceptance belong to this
successor; the automatic HDMI trial cannot satisfy them. No monitor photo is
required. Reserve the single board/serial port before operating selectors.

## Ownership

Worktree `/home/jadams/tmp/k230-hdmi-manual-successor`, branch
`proposal/hdmi-settings-successor-2026-10-09`, base `ba5217ca`.
Owned paths: only this proposal directory. No build slot or board reservation.
