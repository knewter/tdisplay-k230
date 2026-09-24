## Context

The pinned source assessment in `docs/research/quickshell-qtquick-feasibility.md` identifies Qt's software scene graph as a plausible route under the existing Sway/Pixman session. It does not establish a working RISC-V Qt closure, Wayland client buffers, QML execution mode or device cost. Current card workloads already miss CPU/tracking targets; a weak baseline cannot certify a new toolkit.

Layers: **Nix and userspace**. The trial runs as clients of the normal compositor. It requires neither a kernel experiment nor a change of persistent boot selection.

## Goals / Non-Goals

**Goals:** Answer whether ordinary simple Qt Quick apps and then simple Quickshell surfaces are usable, with repeatable package identities, direct-touch observations and comparable costs. Distinguish buildability, rendering correctness, feasibility and suitability for production.

**Non-goals:** A Qt rewrite, full Omarchy runtime, media/codec acceleration, blanket Qt module certification, new notification daemon, or interpreting a host screenshot as physical proof.

## Decisions

1. **Two sequential probes, one baseline.** First build `qtquick-software-probe`: Qt Base/Declarative/Wayland with primitive text/images, bounded scrolling, tap feedback, editable text and reversible position/opacity animation. Use an equivalent small SHM fixture with the same viewport/content/motion/input script. Only a successful Qt prerequisite permits the separate minimal `quickshell-software-probe`. A full shell transplant was rejected because it confounds toolkit, effects, desktop services and compositor integration.

2. **Make the actual renderer observable.** The trial pins `QT_QPA_PLATFORM=wayland`, `QT_QUICK_BACKEND=software`, and `QSG_INFO=1`, clears inherited RHI forcing for the child, and records effective environment, Qt backend logs, mapped runtime libraries, buffer type/format and presented pixels. Unexpected GL/Vulkan rendering fails the software-route gate. Incidental graphics libraries in a closure are recorded, not treated as proof of hardware use. Keep integer display scaling. A shader/effect negative-control fixture must show the documented unsupported behavior, with a separate simple software-safe replacement; silently missing art cannot pass a feature check.

3. **Pin and measure the build.** Use the repository's pinned Qt packages and exact Quickshell source/Qt ABI. Record cross/native tool separation, configure summaries, QV4 execution mode and QML cache/AOT settings; compare forced interpreter only if the pinned build supports that distinction. Record build duration, unique store closure bytes and incremental closure relative to the normal image. No RISC-V JIT claim is inferred from general Qt documentation. Only opt-in flake outputs are added; normal system dependencies stay unchanged during evaluation.

4. **Freeze a trial manifest before measuring.** Record package/system/compositor/Pixman identities, boot ID, panel mode, viewport, scale, workloads, repeats, thermal/frequency samples and budget version. Use three alternating matched pairs per toolkit, 30-second idle and active phases, and at least 24 scripted scroll/drag interactions per active arm. Retain per-run results, not only a pooled favorable percentile. Record cold-after-boot and warm startup separately; process restart is not a cold cache claim. Kernel page-cache flushing is unnecessary.

5. **Separate feasibility gates from production budgets.** Functional prerequisite gates are correct pixels, positively identified software/SHM path, usable scroll/tap/text entry/focus, bounded process lifetime, successful restoration, complete measurements and no failure of a previously passing baseline control. Initial *proposed trial ceilings*, not observed limits, are startup to first presentation at most 5 seconds per run, incremental active-session memory at most 128 MiB, and idle added client CPU at most 2% of one core averaged over 30 seconds. Freeze these in the manifest before trial; changing them requires a versioned rationale, never retroactive PASS.

   Compare combined client-plus-Sway CPU and latency against the matched fixture. Report any regression greater than 10% with absolute values and variability; a failed or noisy baseline is INCONCLUSIVE for that comparison. Keep the existing card budget suite and thresholds unchanged (`tools/card-shell-benchmark.py`), including 16.667 ms p95 frame CPU and 33.334 ms p95 tracking interval. The diagnostic's 128 MiB ceiling does not relax the card feature's 64 MiB memory budget. A passing minimal-app prerequisite can justify measuring a Quickshell panel, but cannot justify adopting a production shell while card budgets fail. A frame callback or submit timestamp is not an optical input-to-photon measurement; report measurement boundaries exactly.

6. **Constrain the Quickshell experiment.** Reuse the same Qt build and a minimal QML panel with no screencopy, Hyprland, X11, multimedia, notification-server or unrelated services. Verify effective CMake flags (`SCREENCOPY=OFF` gates the GPU buffer path) and runtime protocols. Test layer-shell anchors, nonexclusive geometry, input region, bounded focus acquisition and release, repeated show/hide and process exit. Test coexistence with keyboard and shell edge gestures. This proves a layer-shell client, not compositor ownership of live cards.

7. **Independent restoration and evidence.** Reserve the board and reuse established root watchdog/session patterns, scoped to the transient probe processes. Arm a fixed deadline before any focus or scene changes; kill only owned process groups and release their surfaces on timeout/cancellation/SSH loss. Observe the original normal compositor identity and reachable Terminal/keyboard after every trial. Native capture, physical camera, real finger, injected input and host fixture results remain labeled separately. Public results contain fixed-schema measurements and reviewed media, not raw process environment, desktop titles or network details.

## Risks / Trade-offs

- RISC-V Qt cross-build or private Quickshell ABI failure → commit the exact failure and bounded correction attempt; stop dependent trials rather than silently switching architecture/backend.
- Software rendering hides unsupported effects → explicit negative controls and visual inspection, not only exit status.
- Qt client plus compositor doubles some work → combined CPU/session-memory measurements and matched content, including partial-update and idle behavior.
- A panel captures focus/gestures → transient scope, independent deadline and verified normal-session restoration.
- Existing card baseline fails → retain the failure; report toolkit feasibility separately from production acceptance.

## Migration Plan

Land this plan, implement host fixtures/manifest/analyzer and separate probe packages, then take the board only after host guards pass. Record the Qt result before opening the Quickshell gate. Publish an apps decision and a shell-surfaces decision, each linked to its evidence. Adoption needs a separate implementation decision/proposal; these packages never become normal defaults merely because they build. If an earlier gate fails, keep dependent tasks explicitly unperformed and the proposal open; do not tick tests or archive by implication.
