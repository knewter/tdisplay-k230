#!/usr/bin/env python3
"""Optional Playwright proof against the locally built committed site.

Pinned remote assets are served from the same local repository revision.
Screenshots stay in /tmp until explicitly reviewed for publication.
"""
import http.server
import json
import mimetypes
import pathlib
import threading
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / 'site/dist'


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = unquote(urlsplit(path).path)
        if path.startswith('/tdisplay-k230/'):
            path = path[len('/tdisplay-k230/'):]
        return str(DIST / path.lstrip('/'))

    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}/tdisplay-k230/work/'
work = json.loads((ROOT / 'site/src/data/work.json').read_text())
revision = work['sourceRevision']
ident = 'the-handheld-presents-a-coherent-shell'
video_path = 'docs/evidence/shell-features/system-controls/native.mp4'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for label, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
        context = browser.new_context(
            viewport={'width': width, 'height': height},
            is_mobile=label == 'mobile', has_touch=label == 'mobile',
        )

        def raw(route):
            path = unquote(urlsplit(route.request.url).path).split('/' + revision + '/', 1)[-1]
            source = ROOT / path
            if not path.startswith(('docs/', 'openspec/')) or not source.is_file():
                route.abort()
                return
            route.fulfill(path=str(source), content_type=mimetypes.guess_type(str(source))[0]
                          or 'application/octet-stream', headers={'Access-Control-Allow-Origin': '*'})

        context.route('https://raw.githubusercontent.com/knewter/tdisplay-k230/**', raw)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base, wait_until='networkidle')
        assert page.locator('#work-detail-content video').count() == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        card = page.locator('#' + ident)
        cover = card.locator('.card-cover')
        cover.scroll_into_view_if_needed()
        box = cover.bounding_box()
        # The whole-card link deliberately overlays the image.
        page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        page.wait_for_selector('#work-detail-dialog[open]')
        original_url = page.url
        trigger = page.locator('#work-detail-content .media-open').first
        trigger.click()
        page.wait_for_selector('#work-media-dialog[open]')
        page.wait_for_function('document.querySelector("#media-image").naturalWidth > 0')
        assert page.locator('#work-media-dialog').evaluate('(e)=>e.clientWidth >= innerWidth-2 && e.clientHeight >= innerHeight-2')
        assert page.locator('#media-image').evaluate('(e)=>getComputedStyle(e).objectFit === "contain"')
        assert page.locator('#media-stage').evaluate('(e)=>e.clientHeight > innerHeight * .7')
        page.screenshot(path=f'/tmp/k230-work-gallery-{label}.png')
        assert page.locator('#media-position').inner_text().startswith('1 /')
        page.keyboard.press('ArrowRight')
        assert page.locator('#media-position').inner_text().startswith('2 /')
        page.keyboard.press('ArrowLeft')
        if label == 'mobile':
            session = context.new_cdp_session(page)
            box = page.locator('#media-stage').bounding_box()
            x, y = box['x'] + box['width'] * .8, box['y'] + box['height'] * .5
            session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
            for delta in (30, 70, 110, 150):
                session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x-delta, 'y': y}]})
            session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            assert page.locator('#media-position').inner_text().startswith('2 /')
        page.keyboard.press('Escape')
        page.wait_for_selector('#work-media-dialog[open]', state='detached')
        assert page.locator('#work-detail-dialog').evaluate('(e)=>e.open')
        assert trigger.evaluate('(e)=>document.activeElement===e')
        assert page.url == original_url

        video_trigger = page.locator('#work-detail-content .media-open[data-src$="' + video_path + '"]')
        video_trigger.click()
        page.wait_for_selector('#work-media-dialog[open]')
        video = page.locator('#media-video')
        assert video.evaluate('(e)=>e.controls')
        page.wait_for_function('document.querySelector("#media-video").currentTime>0 && document.querySelector("#media-video").videoWidth>0')
        # Close owns focus on open: Space must play/pause, never activate it.
        page.keyboard.press('Space')
        assert video.evaluate('(e)=>e.paused')
        assert page.locator('#work-media-dialog').evaluate('(e)=>e.open')
        page.keyboard.press('Space')
        page.wait_for_function('!document.querySelector("#media-video").paused')
        assert page.locator('#work-media-dialog').evaluate('(e)=>e.open')
        video.focus()
        page.keyboard.press('Space')
        assert video.evaluate('(e)=>e.paused')
        page.keyboard.press('Space')
        page.wait_for_function('!document.querySelector("#media-video").paused')
        page.locator('#media-close').click()
        assert video.evaluate('(e)=>e.paused && !e.hasAttribute("src")')
        assert video_trigger.evaluate('(e)=>document.activeElement===e')

        # Inline reports and source Markdown stay over the current card.
        report = page.locator('#work-detail-content .detail-related a').filter(has_text='reveal-integrated-qemu / README.md').first
        report.click()
        page.wait_for_selector('#work-file-dialog[open]')
        page.wait_for_function('document.querySelector("#file-markdown").textContent.length > 0')
        page.screenshot(path=f'/tmp/k230-work-file-{label}.png')
        assert page.url == original_url
        page.locator('#file-close').click()
        assert page.locator('#work-detail-dialog').evaluate('(e)=>e.open')
        assert report.evaluate('(e)=>document.activeElement===e')
        source = page.locator('#work-detail-content .detail-sources a').first
        source.click()
        page.wait_for_selector('#work-file-dialog[open]')
        assert page.locator('#file-markdown h2').count() > 0
        page.keyboard.press('Escape')
        page.wait_for_selector('#work-file-dialog[open]', state='detached')
        page.locator('#work-detail-close').click()
        page.wait_for_selector('#work-detail-dialog[open]', state='detached')

        # Header report and raw log links use the document viewer without opening a card.
        menu = card.locator('.card-evidence')
        menu.locator('summary').click()
        header_report = menu.locator('a').filter(has_text='reveal-integrated-qemu / README.md').first
        header_report.click()
        page.wait_for_selector('#work-file-dialog[open]')
        page.wait_for_function('document.querySelector("#file-markdown").textContent.length > 0')
        assert page.url == base
        page.keyboard.press('Escape')
        log = menu.locator('a[href$=".json"], a[href$=".log"], a[href$=".txt"]').first
        log.click()
        page.wait_for_selector('#work-file-dialog[open]')
        page.wait_for_function('document.querySelector("#file-text").textContent.length > 0')
        assert 'Text preview' in page.locator('#file-status').inner_text()
        assert page.url == base
        page.locator('#file-close').click()
        assert log.evaluate('(e)=>document.activeElement===e')
        assert not page.locator('#work-detail-dialog').evaluate('(e)=>e.open')
        assert not errors, errors
        print(label, 'PASS: largest-fit gallery, arrow/swipe, playback/stop, Markdown/text modals, retained card/URL/focus', flush=True)
        context.close()
    browser.close()
server.shutdown()
print('source', revision, 'Local pinned-artifact routing; not deployment proof.')
