"""Real Sway/Rust right-click menu proof, imported by the paired QEMU harness."""
import json
import time


def exercise_actions(client, spawn, ipc, wait, tap, capture, route, dock, tile,
                     drawer_tile, hold_drag, release, done, layout_path, marker, log, click):
    def nodes(node):
        yield node
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            yield from nodes(child)

    def windows():
        return {n["id"]: n for n in nodes(ipc("", 4))
                if n.get("app_id") == "k230.card.one"}

    def focused():
        return next((n["id"] for n in nodes(ipc("", 4)) if n.get("focused")), None)

    def home():
        route("hide")
        ipc("card_shell home")
        time.sleep(.6)

    def home_selected():
        scene = ipc("card_shell debug-scene")[0]["error"]
        # Wait for Sway to process the layer destroy, not merely for Rust to
        # log dismissal while that request is still buffered for flush.
        return "home_selected=1 " in scene and "drawer_mapped=0 " in scene

    def menu(point):
        baseline = log().count("app-menu-ready")
        click(point, 3)
        wait(lambda: log().count("app-menu-ready") > baseline)
        time.sleep(.15)

    def select(index, count):
        # AppMenu::geometry at the reference 568x1232 density.
        height = min(90 + max(count, 1) * 56, 1232 - 64)
        click((284, (1232 - height) / 2 + 78 + 56 * (index + .5)))

    proc = spawn("actions-existing", [str(client), "--app-id", "k230.card.one"])
    wait(lambda: len(windows()) == 1)
    original = next(iter(windows()))
    home()
    tap(*dock(0))
    wait(lambda: focused() == original)
    assert list(windows()) == [original]
    assert not marker.exists(), "primary activation launched instead of focusing"

    # Explicit desktop New Window must bypass the existing-window focus path.
    home()
    menu(dock(0))
    capture("home-actions-right-click.png")
    select(1, 6)  # Open / New Window / window / Preferences / Remove / Arrange
    wait(lambda: len(windows()) == 2)
    added = next(window for window in windows() if window != original)
    wait(lambda: focused() == added)
    assert original in windows()
    home()
    tap(*dock(0))
    wait(lambda: focused() == added)
    assert len(windows()) == 2

    # Selecting a specific older window respects its container identity.
    home()
    menu(dock(0))
    select(3, 7)  # most-recent window first, older window second
    wait(lambda: focused() == original)
    assert len(windows()) == 2

    home()
    menu(dock(0))
    select(4, 7)  # the declared Preferences desktop action
    wait(lambda: marker.exists() and "preferences" in marker.read_text())

    # All-apps primary activation uses the same most-recent-window policy.
    home()
    route("drawer")
    time.sleep(.5)
    tap(*drawer_tile(3))  # sorted fixture Terminal entry
    wait(lambda: focused() == original)
    assert len(windows()) == 2

    home()
    before = layout_path.read_bytes()
    before_ids = set(windows())
    menu(dock(0))
    baseline = log().count("app-menu-dismiss")
    click((30, 150))
    wait(lambda: log().count("app-menu-dismiss") > baseline)
    wait(home_selected)
    assert layout_path.read_bytes() == before and set(windows()) == before_ids

    # A second installed entry declares itself single-window. Its menu
    # must omit New Window even though an action with that name is present.
    baseline = log().count("app-menu-ready")
    menu(tile(0))
    ready = [line for line in log().splitlines() if "app-menu-ready" in line][baseline:]
    assert any("new-window=false" in line for line in ready), ready
    click((30, 150))
    wait(home_selected)
    assert layout_path.read_bytes() == before and set(windows()) == before_ids
    # Secondary click toggles dismissal too; it cannot launch or rearrange.
    menu(dock(0))
    baseline = log().count("app-menu-dismiss")
    click(dock(0), 3)
    wait(lambda: log().count("app-menu-dismiss") > baseline)
    wait(home_selected)
    assert layout_path.read_bytes() == before and set(windows()) == before_ids

    # A touch hold remains grab-and-move, with no app menu opening at all.
    capture("home-actions-before-touch.png")
    baseline = log().count("app-menu-open")
    contact = hold_drag(tile(0), tile(2), hold_seconds=1.0)  # Fixture Badge, not Terminal
    capture("home-actions-touch-grab.png", stable_frames=0)
    release(contact, *tile(2))
    wait(lambda: json.loads(layout_path.read_text())["pages"][0][2] ==
         {"kind": "app", "id": "k230-fixture-badge.desktop"})
    assert log().count("app-menu-open") == baseline
    tap(*done())
    # Drawer-to-Home hold/drag is preserved too, including the chosen cell.
    route("drawer")
    time.sleep(.5)
    contact = hold_drag(drawer_tile(1), tile(3), hold_seconds=1.0)
    release(contact, *tile(3))
    wait(lambda: "k230-fixture-extra.desktop" in layout_path.read_text())
    assert log().count("app-menu-open") == baseline
    capture("home-actions-touch-placement.png")
    assert set(windows()) == before_ids

    # Clients launched by GIO are not tracked by the harness process list.
    for window in list(windows()):
        ipc(f"[con_id={window}] kill")
    proc.wait(timeout=5)
    return {name: True for name in (
        "home_primary_focus_keeps_window_identity",
        "desktop_new_window_creates_distinct_window",
        "primary_activation_prefers_recent_window",
        "menu_can_focus_specific_older_window",
        "named_desktop_action_dispatches",
        "all_apps_primary_activation_shares_focus_policy",
        "outside_and_secondary_dismiss_preserve_layout_and_windows",
        "single_window_metadata_hides_unsupported_new_window",
        "touch_hold_keeps_home_grab_and_placement",
        "touch_hold_keeps_drawer_drag_to_home",
    )}
