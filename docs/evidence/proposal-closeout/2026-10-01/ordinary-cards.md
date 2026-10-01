# Ordinary cards, including video: operator acceptance

Recorded 2026-10-01 from the project operator's conversation.
Evidence class: physical operator report, supplementing existing physical-board
injected interactions/native captures. No new capture or timing run is claimed.

> Ordinary cards, including video <-- this is fine.

The coordinator had described the remaining real-finger live-preview and close
check, and the unperformed entry/acknowledgement measurements. The operator
accepts functional behavior and requests closeout. Existing evidence in
`docs/evidence/card-shell/live-card-cost/README.md` proves the injected live
video and busy `btop`/Foot previews, switching, close and mpv exit without
relaunch. Existing source and QEMU proof retain their recorded identities.

The sub-400ms entry-animation and sub-100ms touch-acknowledgement checks were
not performed successfully. They are preserved, unchecked and UNVERIFIED, in
`the-shell-profiles-reported-interaction-jank` task 4.1, landed before this
archive. Functional acceptance is not a claim that either budget passed.

The delta removes the old video-only stop-hook/frozen-preview requirement and
replaces it with the actual generic close and live-thumbnail policy.

Worktree: `.scratch/coordinated-work/accepted-ordinary-cards-closeout`;
branch `closeout/accepted-ordinary-cards`; base `48ead951`.
Owned paths: this evidence, this change/archive, its CLI-generated capability
spec, and its work-board override. No board operation for this closeout.
