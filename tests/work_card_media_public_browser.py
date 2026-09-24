#!/usr/bin/env python3
"""Verify a deployed work-board revision and real media without route mocks."""

import argparse
import re

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision', required=True)
args = parser.parse_args()
if not re.fullmatch(r'[0-9a-f]{40}', args.revision):
    parser.error('--revision must be a full commit hash')
URL = 'https://knewter.github.io/tdisplay-k230/work/'
REVISION = args.revision
VIDEO = 'docs/evidence/shell-features/system-controls/native.mp4'
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    for label, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
        context = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=label == 'mobile', has_touch=label == 'mobile')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto(URL, wait_until='networkidle', timeout=30000)
        assert response and response.status == 200
        assert REVISION in page.content()
        card = page.locator('#the-handheld-presents-a-coherent-shell')
        card.locator('.card-primary').click()
        page.wait_for_selector('#work-detail-dialog[open]')
        trigger = page.locator('#work-detail-content .media-open[data-src$="' + VIDEO + '"]')
        trigger.click()
        page.wait_for_selector('#work-media-dialog[open]')
        video = page.locator('#media-video')
        page.wait_for_function('document.querySelector("#media-video").currentTime > 0 && document.querySelector("#media-video").videoWidth > 0', timeout=20000)
        assert video.evaluate('(e) => !e.paused && e.controls')
        assert page.locator('#media-close').evaluate('(e) => document.activeElement === e')
        page.keyboard.press('Space')
        assert video.evaluate('(e) => e.paused')
        assert page.locator('#work-media-dialog').evaluate('(e) => e.open')
        page.keyboard.press('Space')
        page.wait_for_function('!document.querySelector("#media-video").paused')
        video.focus()
        page.keyboard.press('Space')
        assert video.evaluate('(e) => e.paused')
        assert page.locator('#work-media-dialog').evaluate('(e) => e.open')
        page.keyboard.press('Space')
        page.wait_for_function('!document.querySelector("#media-video").paused')
        page.locator('#media-close').click()
        assert video.evaluate('(e) => e.paused && !e.hasAttribute("src")')
        assert trigger.evaluate('(e) => document.activeElement === e')
        assert not errors, errors
        print(label, 'PASS: published revision, direct video playback, Space from Close/video, modal and focus', flush=True)
        context.close()
    browser.close()
