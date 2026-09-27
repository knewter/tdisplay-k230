## Context
The editor board proof was committed, but the spec used an unrecognized HTML comment. See proposal.md.

## Goals / Non-Goals
Make the existing grounding visible to the site. No changes to userspace, Nix or the installed system.

## Decisions
Use the established `*Grounding: ...*` format and cite the committed board result and normal-reboot record. Preserve every requirement and scenario. Do not widen the classifier to accept arbitrary verification comments.

## Risks / Trade-offs
Injected input is not real-finger acceptance; retain that explicit limit. The dashboard requires this design artifact even for a documentation correction.
