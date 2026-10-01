## Context

See proposal.md. There is no existing task runner or release script; repository tasks are direct Python tools. The flake's `sdImage-coherent` selects `k230-coherent-shell` with the normal vendor kernel; `sdImage` remains the old bar-session rollback. Work lands in host tooling and documentation, with no stage 1, kernel, device tree, Nix or userspace changes.

## Goals / Non-Goals

**Goals:** one manual command with separate stage and publish modes, pinned Git revision, outside-repo assets, and verification before and after upload.

**Non-Goals:** changing runtime boot selection, using mainline/SMP/RVV trial outputs, automatic releases or obtaining board proof.

## Decisions

- Use a Python tool following existing tools rather than introduce Make/just solely for one task.
- Evaluate and build `git+file://<repo>?rev=<full-sha>` with the committed lock; the task records source SHA independently from later documentation/tool commits.
- Build `sdImage-coherent`, system, kernel and device tree with outside-repo out-links so Nix registers GC roots. Stage xz image, JSON provenance, SHA256SUMS and Markdown notes under `~/tmp` by default.
- Stage first and publish explicitly. Before publishing, re-evaluate exact source outputs and verify file digests. Create a draft prerelease and save its numeric ID/source/asset digests locally before upload. Authenticated list and ID lookup are required because a GitHub draft may have no tag and the tag endpoint returns 404. Verify remote assets by downloading and hashing, then publish and verify the tag SHA. Never overwrite or resume an existing release automatically; an explicit `--finish-draft` can finish only the locally recorded transaction after complete verification, without re-uploading assets.
- Reject artifact commits, NAR uploads and stable-release claims: GitHub download assets match the user's request; physical acceptance is not proved by a host build.

## Risks / Trade-offs

- [Long cross-build] → use existing exact store outputs and max-jobs 1/cores 8.
- [GC between staging and publication] → retain registered out-links until operator cleanup.
- [Partial remote upload] → remain draft if asset verification fails; report the failed draft and operator recovery rather than replacing it.
- [Unproven fresh boot] → mandatory prerelease notes state the gap and current known-good older vendor boot baseline.
