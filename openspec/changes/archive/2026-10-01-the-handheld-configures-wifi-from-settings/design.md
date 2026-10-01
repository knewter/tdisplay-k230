## Context

See proposal.md. `nix/hardware.nix` already defines `k230-wifi.service`: `wlan0`, root-private `/var/lib/k230/wifi/wpa_supplicant.conf`, systemd `LoadCredential`, and a root-only supplicant control directory. `tools/device_settings.py` reports only link state. The Rust shell has an asynchronous Settings worker and touch-routed Settings panel. Existing physical evidence in `docs/evidence/wifi-persistent/` proves operator-installed persistence, not Settings-driven setup. Stage 1, kernel, device tree and radio driver remain unchanged.

## Goals / Non-Goals

**Goals:** A usable 568×1232 touch route, no terminal procedure in the user flow; strict secret and service ownership; bounded asynchronous work; safe coexistence with the already proven persistent service; inspectable host and physical gates.

**Non-Goals:** Enterprise/EAP, hidden-network manual entry, captive-portal login, hotspot mode, or a claim that association proves Internet access. Do not make the unprivileged shell a network administrator.

## Decisions

1. **A small root-owned userspace broker owns Wi-Fi changes.** A private local socket accepts bounded typed scan/status/connect/forget messages from the shell session UID, authenticates peer credentials, rate-limits scans and connection attempts, and emits bounded typed results. A fresh image has no credential and therefore no active supplicant: the broker first brings `wlan0` up using fixed `ip` arguments, then scans with fixed `iw` arguments. The service never shells out with SSIDs or passwords in argv; diagnostics use fixed error codes. The `wlan0` and root-only supplicant control paths remain authoritative. Rejected: direct `wpa_cli` from the shell (root-only socket and privilege), `sudo` from Settings (argv and authorization surface), or running a second supplicant (radio conflict).
2. **Only the root broker writes persistence.** It validates SSID bytes and supported security, writes a root-owned 0600 candidate file under `/run`, stops the existing service, and runs a private candidate supplicant for `wlan0`. It verifies candidate `COMPLETED` state before writing a root-owned 0600 temporary file in `/var/lib/k230/wifi`, fsyncing and atomically replacing the credential, then starts `k230-wifi.service` to consume its `LoadCredential` copy. A bounded set of eight saved network stanzas survives switching; an accepted connection replaces only its own stanza, and Forget removes only the selected stanza. Existing operator stanzas are preserved byte-for-byte when their identity and top-level format can be parsed safely; unknown global directives or ambiguous identities block mutation while retaining the previous file. Connection failure leaves prior configuration intact; start failure restores it. The shell sees network names and statuses but never stored secrets. Rejected: simultaneous supplicants, home-directory persistence or passing a credential through Nix/systemd unit environment.
3. **The shell owns a Wi-Fi subview under Settings.** Network opens a list with current/saved badges, a refresh action, and tap selection. The selected WPA2-Personal entry opens a masked editor; open networks skip password. Connect/Forget are explicit distinct actions. The editor has backspace, cancel and disabled/working states; the password buffer is cleared on exit, successful submit and route teardown. Worker requests carry monotonically increasing IDs, and the UI accepts only the active route's matching reply. Rejected: relying on an external terminal.

   Password entry originally drew its own in-app keypad rather than raising
   the shell's own system keyboard (wvkbd), because every layer surface this
   shell owns requests `KeyboardInteractivity::None` (`ensure_layer`,
   `ensure_home`, `ensure_wallpaper`): a deliberate, shell-wide policy so
   chrome never contests keyboard focus with an application, not a security
   requirement about this one field. wvkbd delivers keys as ordinary
   `wl_keyboard` input to whichever surface currently holds keyboard focus,
   so a layer surface that never requests it can never be that surface --
   the keys had nowhere to go. The in-app keypad worked around that gap
   instead of closing it, at the cost of a dense, easily mis-hit custom
   keyboard glued mid-screen above Cancel/Connect, with duplicate Del/Delete
   keys and a release/down-position hit test tight enough (an 18px combined
   tolerance over ~50px-wide keys) to drop taps under ordinary fingertip
   jitter.
   Corrected: the overlay surface requests `KeyboardInteractivity::Exclusive`
   only for the narrow lifetime of an unsaved WPA2-Personal password field
   (`WifiView::wants_keyboard`), releasing it back to `None` the instant the
   field is no longer active (Connect, Cancel, Back, or leaving Settings), so
   the "never contest an app's focus" policy still holds everywhere else.
   The shell raises/lowers wvkbd itself through the same
   `k230-keyboard-gesture-signal` helper the compositor's own two-finger
   keyboard gesture already uses (one show/hide path, not two), and reflows
   Cancel/Connect to sit above the keyboard's reserved height
   (`entry_buttons_rect`, `K230_KEYBOARD_HEIGHT`) like Android's
   `adjustResize`. Typed text, Backspace, Enter (Connect) and Escape
   (Cancel) all arrive as normal `wl_keyboard` key events
   (`wifi_ui::key_event_intent`), through the exact same `wifi_action`
   dispatcher a touch-hit intent already used.
4. **Status is a staged state machine.** A scan result is not association; association is not DHCP or Internet. The backend reports radio unavailable, scan pending/empty/failure, connecting, authentication failure, association, and saved state independently. Timeout and cancellation do not claim success. Long-running requests stay off the Wayland loop and bounded queues coalesce scans; no secret enters debug formatting or UI error strings.
5. **A separate systemd recovery timer is armed before stopping the persistent service.** The candidate remains in the broker service cgroup. If the broker crashes or exceeds the bounded attempt window, the timer stops that cgroup, restarts the previously saved service, and restores the broker. A normal completion cancels the timer only after service restart. The timer's fixed arguments contain no network data.

## Risks / Trade-offs

- [Vendor driver scanning or control differs on the board] → keep scan/connect physical gates open, capture only sanitized status and real-glass observation, and preserve existing root operator path for recovery.
- [Power loss between association and persistence] → atomic root-private replacement; previous credential remains until a confirmed new connection.
- [Privilege broker reachable by an unrelated local client] → peer UID check, private socket directory, no broad group access, bounded requests and fixed commands.
- [Password remains in shell process memory during entry] → clear on route exit; do not clone into logs, history, argv or long-lived worker state. Process memory cannot be promised zeroized by ordinary Rust strings; avoid claiming that.
- [Long SSIDs, duplicates, or stale scans crowd the small display] → bounded rows, safe text layout, stable selection IDs and explicit refresh/retry; never select by truncated display text.
- [A legacy operator file uses unsupported global directives or ambiguous SSIDs] → refuse modification with a specific error and preserve the file; do not silently drop saved networks.
- [Exclusive keyboard focus outlives the field it was granted for, stranding the shell unable to take touch/keyboard input elsewhere] → released on every path that leaves the field (Connect, Cancel, Back, route change, Settings/Wi-Fi teardown) through the single `sync_wifi_keyboard` chokepoint, and unconditionally on seat keyboard-capability loss (`forget_wifi_keyboard`) rather than trusting that capability to still be there to release cleanly.

## Migration Plan

Add the broker and Settings client without changing the credential-free default or existing operator file format. Install and host-test the isolated package, then cross-build the full closure. The root operator activates a recovery-capable image and tests open/WPA2 connection, Forget and reboot reconnect on the physical board. Rollback disables the new broker and restores the previous image; the existing root-owned credential remains usable by the proven service.

## Password visibility follow-up (2026-09-30)

The physical operator found the Wi-Fi flow usable but requested an eye toggle to inspect touchscreen typos. Add explicit Show/Hide beside the field with a usable touch target. Keep masked entry as the default and reset visibility on every editor exit and new selection. Preserve the existing secret holder and focus lifecycle; public status/debug state may contain a visibility flag and length, but never the secret. A visible-field render is transient user-requested output, not permission to put its content in worker/debug messages, cache keys, logs or committed captures. Verify with a disposable sample rather than recording actual credentials. See `docs/evidence/wifi-settings/operator-2026-09-30.md`; broad positive feedback does not stand in for the unperformed reboot/Forget cases.
