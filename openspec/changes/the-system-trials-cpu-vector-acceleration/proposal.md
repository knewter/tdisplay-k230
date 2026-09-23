## Why

Live cards still miss their measured CPU/frame budgets, and the normal system cannot expose the CPU-vector path that might reduce software rendering cost. Existing kernel and Pixman build investigations identify disabled vector support; a recoverable physical trial is needed to learn whether it is safe and useful. This kernel experiment needs an explicit scope separate from the userspace-only card proposal.

## What Changes

- Reconcile the existing opt-in kernel, matching system/image, guarded context probe and Pixman build work into a bounded CPU-vector trial.
- Load a matching trial once without replacing the known normal boot selection; verify normal recovery and preserve failures.
- Require truthful kernel capability reporting and actual vector state preservation across signals and scheduling before vector rendering.
- Compare pixel correctness and the same live-card workload with vector dispatch enabled and disabled; record a negative result as carefully as a speedup.

Non-goals: enabling the second core or GPU, replacing stage 1, upgrading the kernel family, making vector support a dependency of card acceptance, changing interaction budgets, or promoting a trial into the default image. Any default promotion needs a separate reviewed proposal and compatibility evidence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/kernel`: a recoverable optional CPU-vector trial with capability, context-safety and measured-rendering gates.

## Impact

The kernel owns vector enablement and context handling; userspace owns capability gating, pixel tests and measurements; Nix owns matching kernel/modules/initrd packaging. Likely paths are the existing RVV derivations and patches, dedicated board-trial tools, optional renderer packaging and committed evidence. Existing host builds and full Linux QEMU context tests can be reused with exact provenance. Physical trial boot, recovery and rendering comparisons require the single board and serial reservation. The normal Pixman shell remains the baseline.
