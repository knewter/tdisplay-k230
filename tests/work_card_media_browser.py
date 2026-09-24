#!/usr/bin/env python3
"""Optional Playwright browser proof against the locally built committed site."""
import functools, http.server, json, mimetypes, pathlib, threading
from urllib.parse import urlsplit, unquote
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]; DIST=ROOT/'site/dist'
class Handler(http.server.SimpleHTTPRequestHandler):
 def translate_path(self,path):
  path=unquote(urlsplit(path).path)
  if path.startswith('/tdisplay-k230/'): path=path[len('/tdisplay-k230/'):]
  return str(DIST/path.lstrip('/'))
 def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}/tdisplay-k230/work/'
work=json.loads((ROOT/'site/src/data/work.json').read_text()); rev=work['sourceRevision']
ident='the-handheld-presents-a-coherent-shell'
video_path='docs/evidence/shell-features/system-controls/native.mp4'
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 for label,w,h in [('desktop',1440,1000),('mobile',390,844)]:
  ctx=browser.new_context(viewport={'width':w,'height':h},is_mobile=label=='mobile',has_touch=label=='mobile')
  def raw(route):
   path=unquote(urlsplit(route.request.url).path).split('/'+rev+'/',1)[-1]
   src=ROOT/path
   if not path.startswith('docs/') or not src.is_file(): route.abort(); return
   route.fulfill(path=str(src),content_type=mimetypes.guess_type(str(src))[0] or 'application/octet-stream',headers={'Access-Control-Allow-Origin':'*'})
  ctx.route('https://raw.githubusercontent.com/knewter/tdisplay-k230/**',raw)
  page=ctx.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(base,wait_until='networkidle')
  assert page.locator('#work-detail-content video').count()==0
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'page overflow'
  card=page.locator('#'+ident); card.scroll_into_view_if_needed()
  cover=card.locator('.card-cover'); cover.scroll_into_view_if_needed(); box=cover.bounding_box(); page.mouse.click(box['x']+box['width']/2, box['y']+box['height']/2)
  page.wait_for_selector('#work-detail-dialog[open]')
  assert page.locator('#work-detail-content .detail-media img').count()>0
  assert page.locator('#work-detail-content video').count()>0
  assert not page.locator('#work-detail-content video[autoplay]').count()
  page.locator('#work-detail-content .detail-media img').first.wait_for(state='visible')
  page.wait_for_function("document.querySelector('#work-detail-content .detail-media img').naturalWidth > 0")
  assert page.locator('#work-detail-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth'), 'dialog overflow'
  page.screenshot(path=f'/tmp/k230-work-media-{label}-dialog.png')
  video=page.locator('#work-detail-content video[src$="'+video_path+'"]')
  assert video.count()==1
  video.scroll_into_view_if_needed()
  video.evaluate('(e)=>{e.muted=true; e.play().catch(()=>{})}')
  page.wait_for_function('(path)=>{let e=[...document.querySelectorAll("#work-detail-content video")].find(e=>e.src.endsWith(path)); return e.currentTime>0 && e.videoWidth>0}',arg=video_path)
  video.evaluate('(e)=>e.pause()')
  page.locator('#work-detail-close').click(); page.wait_for_selector('#work-detail-dialog[open]',state='detached')
  menu=card.locator('.card-evidence'); menu.locator('summary').click()
  assert menu.get_attribute('open') is not None
  assert not page.locator('#work-detail-dialog').evaluate('(e)=>e.open')
  link=menu.locator('a').filter(has_text='reveal-integrated-qemu / README.md').first
  assert link.count()==1
  href=link.get_attribute('href'); assert '/evidence/' in href
  page.screenshot(path=f'/tmp/k230-work-media-{label}-card.png')
  link.click(); page.wait_for_url('**/evidence/**')
  assert page.locator('.ev-markdown').count()==1
  page.goto(base,wait_until='domcontentloaded'); trigger=page.locator('[data-work-id="'+ident+'"]'); trigger.focus(); page.keyboard.press('Enter')
  page.wait_for_selector('#work-detail-dialog[open]'); page.keyboard.press('Escape'); page.wait_for_selector('#work-detail-dialog[open]',state='detached')
  assert trigger.evaluate('(e)=>document.activeElement===e')
  assert not errors,errors
  print(label,'PASS: cover click, inline gallery, video playback, evidence menu/link, Markdown, keyboard/focus, no overflow/errors')
  ctx.close()
 browser.close()
server.shutdown()
print('source',rev,'Raw media routed to same local committed artifacts; not deployment proof.')
