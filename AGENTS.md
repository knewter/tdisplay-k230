# Working agreements

Use one worktree and one branch for each change. Do not edit another agent's
worktree, stage broad path sets, or repair unrelated dirt. State the worktree,
base revision, owned paths, and any build-slot or board reservation when taking
work. A single board and its serial port belong to one operator at a time.

## Keep changes moving

An OpenSpec proposal is a reviewable deliverable, not a private preface to a
large implementation. Validate and commit it promptly, then hand it to the
coordinator for an early merge to `master`. When the coordinator has authorized
merging and pushing, do that rather than holding a proposal behind later source
work. This lets concurrent implementation start from a shared scope and lets
the spec site describe the current plan.

For an authorized implementation, continue through the bounded work rather
than requesting routine approval between proposal, source, tests, and commit.
Keep hardware-only tasks open until their named physical proof exists. A host
build, QEMU run, injected event, camera recording, and real glass interaction
are distinct evidence classes; record exactly which one was obtained.

Before handing off a commit, report:

- branch, base revision, commit hash, and owned paths;
- the narrow command run and its result, or the exact blocker;
- the change's remaining evidence gate, including the operator command if a
  board action is needed;
- whether a review, merge, push, deployment, or physical verification remains.

A reviewer or coordinator should either request a concrete correction or land
the reviewed commit promptly. Do not let finished work accumulate only in
private worktrees. Once a change lands, push `master` and inspect the relevant
CI/deployment result. A successful build is not deployment proof: record the
published URL, installed store path, flashed image, or board observation that
matches the change. Treat a failed run as a task with its log and owner, not as
a reason to leave an otherwise ready change unreported.

## Close OpenSpec changes deliberately

Archive only after the implemented scope is on `master`, all required task
proof is committed, and hardware-dependent tasks have either passed with their
stated evidence or remain explicitly open. Validate before archive, check that
the delta targets existing capability files, sync the resulting specs as the
change requires, and commit/archive/push the result. The final handoff names
the deployment or board verification still required; it never turns an
unverified requirement into a claim merely because source code landed.

## Evidence and secrets

Keep evidence with the change in committed `docs/evidence/` files where the
spec cites it. Preserve the command, source artifact, timestamps, and limits;
do not replace physical observations with inferred claims. Do not commit
credentials, SSIDs, tokens, private addresses, or secret-bearing command
output. Pass runtime secret contents only through the designated protected
configuration path; a harmless pathname may be documented when useful.

Repository-specific OpenSpec rules in `openspec/config.yaml` and the capability
taxonomy in `.skills/k230-spec-change/SKILL.md` remain authoritative. In
particular, use the task group's narrow proof command, retain `UNVERIFIED`
markers where grounding is absent, and do not infer a hardware result from a
host-only check.
