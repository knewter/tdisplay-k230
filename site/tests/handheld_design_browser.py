"""Browser checks for the built handheld interaction study.

Run after `python3 scripts/build_site.py`. Requires Playwright Python and Chromium.
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from playwright.sync_api import sync_playwright


DIST = Path(__file__).resolve().parents[1] / "dist"


def drag(page, x1, y1, x2, y2, *, release=True):
    page.mouse.move(x1, y1)
    page.mouse.down()
    page.mouse.move(x2, y2, steps=8)
    if release:
        page.mouse.up()


def main():
    assert (DIST / "design/handheld/index.html").exists(), "build the site first"
    with TemporaryDirectory() as tmp:
        (Path(tmp) / "tdisplay-k230").symlink_to(DIST, target_is_directory=True)
        handler = partial(SimpleHTTPRequestHandler, directory=tmp)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 1440, "height": 1800})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/tdisplay-k230/design/handheld/", wait_until="networkidle")
                device = page.locator("#device")
                assert device.get_attribute("data-view") == "deck"
                assert all(image.evaluate("el => el.complete && el.naturalWidth > 0") for image in page.locator(".card-top img, .drawer-app img, .notification img").all())
                assert not page.locator(".battery").count()

                # A deck swipe follows the pointer before release and does not tap-open the card.
                box = device.bounding_box()
                x, y = box["x"] + box["width"] * .53, box["y"] + box["height"] * .58
                drag(page, x, y, x - 110, y, release=False)
                assert "translateX" in page.locator('.app-card[data-position="center"]').get_attribute("style")
                page.mouse.up()
                assert device.get_attribute("data-view") == "deck"
                assert page.locator('.app-card[data-position="center"]').get_attribute("data-card") == "monitor"

                # Reversing a short drag settles in place and must not tap-open.
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.move(x - 45, y, steps=4)
                page.mouse.move(x - 8, y, steps=4)
                page.mouse.up()
                assert device.get_attribute("data-view") == "deck"
                assert page.locator('.app-card[data-position="center"]').get_attribute("data-card") == "monitor"

                # Pointer cancellation restores the card instead of finishing the gesture.
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.move(x + 50, y, steps=5)
                device.dispatch_event("pointercancel")
                assert page.locator('.app-card[data-position="center"]').get_attribute("style") in (None, "")
                page.mouse.up()

                # A second contact cancels the first gesture rather than taking it over.
                device.dispatch_event("pointerdown", {"pointerId": 100, "clientX": x, "clientY": y})
                device.dispatch_event("pointerdown", {"pointerId": 101, "clientX": x + 10, "clientY": y})
                device.dispatch_event("pointermove", {"pointerId": 100, "clientX": x - 90, "clientY": y})
                assert page.locator('.app-card[data-position="center"]').get_attribute("style") in (None, "")

                page.locator('[data-demo="expand"]').click()
                page.wait_for_timeout(800)
                assert device.get_attribute("data-view") == "app"
                drag(page, box["x"] + box["width"] / 2, box["y"] + box["height"] * .93,
                     box["x"] + box["width"] / 2, box["y"] + box["height"] * .70, release=False)
                assert "scale" in page.locator(".app-view").get_attribute("style")
                page.mouse.up()
                page.wait_for_timeout(650)
                assert device.get_attribute("data-view") == "deck"

                for demo, expected in [("drawer", "drawer"), ("shade", "shade")]:
                    page.locator(f'[data-demo="{demo}"]').click()
                    page.wait_for_timeout(750)
                    assert device.get_attribute("data-view") == expected
                page.locator("#open-settings").click()
                assert device.get_attribute("data-view") == "settings"
                page.locator("#settings-back").click()
                assert device.get_attribute("data-view") == "shade"

                page.locator('[data-demo="throw"]').click()
                page.wait_for_timeout(3900)
                assert page.locator('.app-card[data-card="video"]').get_attribute("data-position") == "hidden"
                drag(page, box["x"] + box["width"] / 2, box["y"] + box["height"] * .93,
                     box["x"] + box["width"] / 2, box["y"] + box["height"] * .70)
                assert device.get_attribute("data-view") == "drawer"
                assert page.locator('.app-card[data-card="video"]').get_attribute("data-position") == "hidden"
                page.locator('[data-launch="video"]').click()
                drag(page, box["x"] + box["width"] / 2, box["y"] + box["height"] * .93,
                     box["x"] + box["width"] / 2, box["y"] + box["height"] * .70)
                page.wait_for_timeout(650)
                assert page.locator('.app-card[data-card="video"]').get_attribute("data-position") == "center"
                drag(page, box["x"] + box["width"] / 2, box["y"] + box["height"] * .93,
                     box["x"] + box["width"] / 2, box["y"] + box["height"] * .70)
                assert device.get_attribute("data-view") == "drawer"
                page.locator('[data-launch="files"]').click()
                drag(page, box["x"] + box["width"] / 2, box["y"] + box["height"] * .93,
                     box["x"] + box["width"] / 2, box["y"] + box["height"] * .70)
                page.wait_for_timeout(650)
                assert page.locator('.app-card[data-card="files"]').get_attribute("data-position") == "center"
                assert page.locator('.app-card[data-card="files"] img').first.evaluate("el => el.complete && el.naturalWidth > 0")
                page.locator('[data-demo="throw"]').click()
                page.wait_for_timeout(3900)
                assert page.locator('.app-card[data-card="video"]').get_attribute("data-position") == "hidden"
                assert not errors, errors
                page.set_viewport_size({"width": 390, "height": 844})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                browser.close()
        finally:
            server.shutdown()
    print("handheld browser gestures: ok")


if __name__ == "__main__":
    main()
