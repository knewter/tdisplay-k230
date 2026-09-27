"""Paired Sway/Rust synthetic gesture proof; imported by the Home fixture."""
import re
import time
from PIL import ImageChops


def exercise_navigation(client, spawn, ipc, wait, drag, release, tap, capture, route, dock):
    def scene():
        return dict(re.findall(r'(\w+)=([^ ]+)', ipc('card_shell debug-scene')[0]['error']))

    def nodes(node):
        yield node
        for child in node.get('nodes', []) + node.get('floating_nodes', []):
            yield from nodes(child)

    def windows():
        return {n['app_id']: n['id'] for n in nodes(ipc('', 4)) if n.get('app_id')}

    def focused():
        return next((n.get('app_id') for n in nodes(ipc('', 4)) if n.get('focused')), None)

    def swipe(end=850):
        touch = drag((284, 1210), (284, end))
        release(touch, 284, end)

    def overview():
        swipe()
        wait(lambda: scene()['mode'] == '1')

    def home():
        swipe()
        wait(lambda: scene()['home_selected'] == '1' and scene()['home_settling'] == '0')

    one = spawn('navigation-one', [str(client), '--app-id', 'k230.card.one'])
    two = spawn('navigation-two', [str(client), '--app-id', 'k230.card.two'])
    wait(lambda: len(windows()) == 2)
    time.sleep(.8)  # allow first client buffers and ordinary-size transaction to commit
    identities = windows()
    overview()
    capture('navigation-overview.png', stable_frames=0)

    # A held drag is exactly one screen pixel per input pixel, then reversal
    # and second-contact cancellation return to Overview without closing apps.
    touch = drag((284, 1210), (284, 1050))
    assert abs(float(scene()['home_offset']) - 160) < 1, scene()
    capture('navigation-home-held.png', stable_frames=0)
    ipc(f'card_shell test-touch motion {touch} 284 1200')
    release(touch, 284, 1200)
    wait(lambda: scene()['home_settling'] == '0')
    assert scene()['mode'] == '1' and scene()['home_selected'] == '0', scene()
    swipe(1180)
    wait(lambda: scene()['home_settling'] == '0')
    assert scene()['mode'] == '1', scene()
    touch = drag((284, 1210), (284, 1000))
    ipc('card_shell test-touch down 999 350 1000')
    ipc('card_shell test-touch up 999')
    release(touch, 284, 1000)
    wait(lambda: scene()['home_settling'] == '0')
    assert scene()['mode'] == '1', scene()
    assert windows() == identities

    home()
    home_image = capture('navigation-home.png')
    assert windows() == identities and focused() is None
    swipe()
    wait(lambda: scene()['drawer_mapped'] == '1')
    drawer = capture('navigation-drawer.png')
    assert ImageChops.difference(home_image, drawer).getbbox()
    assert scene()['home_selected'] == '1' and windows() == identities
    time.sleep(.6)  # let the streamed reveal finish before issuing a separate route
    route('hide')
    time.sleep(.6)
    wait(lambda: scene()['drawer_mapped'] == '0')
    # Real Rust Home icon selection must focus the existing view, not launch
    # another fixture or leave apps invisible behind the Home layer.
    tap(*dock(0))
    wait(lambda: focused() == 'k230.card.one' and scene()['home_selected'] == '0')
    app = capture('navigation-restored-app.png', stable_frames=0)
    assert ImageChops.difference(home_image, app).getbbox()
    assert windows() == identities
    overview()
    home()
    third = spawn('navigation-new', [str(client), '--app-id', 'k230.card.three'])
    wait(lambda: focused() == 'k230.card.three' and scene()['home_selected'] == '0')
    assert all(windows()[name] == value for name, value in identities.items())
    for proc in (third, two, one):
        proc.terminate()
        proc.wait(timeout=5)
    wait(lambda: not windows())
    time.sleep(.2)
    return {name: True for name in (
        'navigation_app_overview_home_drawer', 'navigation_tracks_held_finger_1_to_1',
        'navigation_short_reversed_multitouch_cancel', 'navigation_preserves_window_ids',
        'navigation_home_icon_restores_existing_app', 'navigation_new_app_leaves_home')}
