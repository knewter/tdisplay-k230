Dependencies: groups 1–3 can proceed after this proposal lands. Group 4 consumes groups 1–3 plus `the-shell-has-a-card-composition-plan` and `the-shell-manages-apps-as-cards` physical gates. Group 5 requires a board reservation and the installed integrated image. No task below is claimed complete by this proposal.

The `tests/test_shell_routes.py`, `tests/test_device_settings.py`, and `tests/test_notification_center.py` files and `.#handheld-settings`/`.#handheld-notifications` attributes are **new interfaces to create** in the named implementation tasks, not presently runnable commands. Their invocations define narrow future proof. Existing `.#touch-launcher`, closure, OpenSpec, and capture tools are current commands.

## 1. Shared shell frame and route contract (host)

- [ ] 1.1 Implement the common palette/type/spacing/target tokens and separate Apps, Windows, Keyboard, System, Back, and Home actions at output scale 1, with final Home→Apps and named Terminal recovery; verify `python3 tests/test_shell_routes.py --case labels --case back-stack --case home --case terminal-recovery` checks target geometry and focus restoration.
- [ ] 1.2 Add loading, empty, stale, failure, cancellation, pressed, and reduced-motion variants without hiding recoverable actions behind wvkbd; verify `python3 tests/test_shell_routes.py --case states --case keyboard --case reduced-motion`.
- [ ] 1.3 Package fresh-home shell defaults and an opt-in rollback flag; verify `nix build .#touch-launcher` (derivation proof only, no panel or touch claim).

## 2. Truthful Settings (host)

- [ ] 2.1 Implement System hub with distinct Settings and Notifications destinations, and settings capability-state adapters for network, display brightness, keyboard, and motion. Show unavailable/read-only/pending states when the installed interface cannot support an action; verify `python3 tests/test_device_settings.py --case capability-states --case no-battery --case fresh-home`.
- [ ] 2.2 Connect confirmation and completion/error feedback for existing restart/power helper without optimistic state; verify `python3 tests/test_device_settings.py --case restart-cancel --case denial --case confirmed`.
- [ ] 2.3 Build the narrow settings package before image integration; verify `nix build .#handheld-settings` (derivation proof only).

## 3. Notification preview and history (host)

- [ ] 3.1 Implement bounded event records for shell/system and deliberately integrated apps, source validation, priority policy, deduplication, and safe body defaults; verify `python3 tests/test_notification_center.py --case priority --case privacy --case retention --case unknown-source`.
- [ ] 3.2 Implement non-focus-taking preview, System count, History, action validation, dismissal, and empty/target-gone/critical states; verify `python3 tests/test_notification_center.py --case preview-timeout --case typing-focus --case action-gone --case dismiss-all --case critical`.
- [ ] 3.3 Build the narrow broker/client package with Nix-provided defaults; verify `nix build .#handheld-notifications` (derivation proof only). A standard desktop notification adapter remains a separately reviewable extension after these sources work.

## 4. Card and catalog integration (host, after sibling gates)

- [ ] 4.1 Consume the card owner's published lifecycle, privacy, and fallback interface so Windows shows eligible live cards only when proven, otherwise names unavailable/private metadata honestly; verify `python3 tests/test_shell_routes.py --case live-card-gate --case private-card --case close-refused`.
- [ ] 4.2 Integrate the curated desktop-entry launcher, shared deck/Apps action dock, Back/Home recovery, and notification transitions across app focus and keyboard display; verify `python3 tests/test_shell_routes.py --case app-to-deck --case catalog-failure --case preview-drag-conflict`.
- [ ] 4.3 Build the integrated system closure only after the narrow packages pass; verify `nix build .#nixosConfigurations.k230.config.system.build.toplevel` (cross-build proof only, not board behavior).

## 5. Physical acceptance and evidence (board reservation required)

- [ ] 5.1 On installed glass, record readable Apps/Windows/Settings/History, all-edge real-finger targets, Back/Home, and keyboard viewport without secrets; verify `python3 tools/capture-feature.py coherent-shell --provenance real-touch --duration 45 --description 'Shell surfaces and recovery on glass' --output-dir docs/evidence/coherent-shell` produces a reviewed camera recording, and separately run `flock /tmp/k230-board.lock ./tools/console.py /dev/ttyACM0 --wait=3 'systemctl is-active shell'` for an actual sanitized console result committed with the capture. A native screenshot or operator-declared camera provenance alone is insufficient.
- [ ] 5.2 Record a real-finger app-to-card-to-adjacent-app sequence only after the card sibling's physical gate, plus unavailable/private and close-refused fallback; verify `python3 tools/capture-feature.py coherent-cards --provenance real-touch --duration 45 --description 'Live cards and fallback on glass' --output-dir docs/evidence/coherent-cards` and cite the card sibling's committed interface/evidence. An injected drag does not complete this task.
- [ ] 5.3 Record ordinary preview while typing, History action/dismissal, critical recovery, a failed settings action, and measured preview/focus/settle limits; verify `python3 tools/capture-feature.py coherent-notifications --provenance real-touch --duration 60 --description 'Notification focus and settings feedback on glass' --output-dir docs/evidence/coherent-notifications`, with sanitized console timestamps and a result table committed under that directory.
- [ ] 5.4 Validate after evidence and keep any unmet physical task open; verify `openspec validate the-handheld-presents-a-coherent-shell --strict` and `python3 tools/work-status.py`. Do not archive from host-only or QEMU proof.
