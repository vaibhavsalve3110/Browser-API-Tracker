#!/usr/bin/env python3
"""Browser API Tracker.

Opens a real (visible) Chrome window, and while you click around it:
  - records a screenshot for every click / form submit / page load, and for typed fields the
    first and last keystroke of each typing session (not every keystroke)
  - captures every XHR/fetch API call (URL, method, payload, headers, response) and
    correlates it with the interaction that triggered it
  - when you close the window, writes into sessions/<timestamp>/:
      report.html, report.docx, journey.docx, testcases.xlsx, api-list.xlsx,
      api-details.xlsx, api-details.docx, api-report.html, data.json

Usage:
    python track.py <start-url> [--all] [--api-host=https://host] [--chrome-path=PATH]
"""
import asyncio
import os
import signal
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from browser_api_tracker.injected_tracker import INJECTED_TRACKER_JS
from browser_api_tracker.report_api_html import DEFAULT_API_HOST
from browser_api_tracker.reports import assign_calls_to_events, generate_reports
from browser_api_tracker.secret_scanner import ScriptScanner

DEFAULT_CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
API_TYPES = {'xhr', 'fetch'}

# Google Tag Manager / Google Analytics endpoints: noise, not application API calls.
EXCLUDED_HOSTS = [
    'googletagmanager.com',
    'google-analytics.com',
    'analytics.google.com',
    'googleadservices.com',
    'doubleclick.net',
    'stats.g.doubleclick.net',
    'www.google.com',
]


def now_ms():
    return int(time.time() * 1000)


def is_excluded(url):
    try:
        host = urlsplit(url).hostname or ''
    except ValueError:
        return False
    return any(host == h or host.endswith('.' + h) for h in EXCLUDED_HOSTS)


class Tracker:
    def __init__(self, start_url, include_all, api_host, session_dir):
        self.start_url = start_url
        self.include_all = include_all
        self.api_host = api_host
        self.session_dir = session_dir
        self.screenshots_dir = os.path.join(session_dir, 'screenshots')
        os.makedirs(self.screenshots_dir, exist_ok=True)
        self.events = []
        self.network_calls = []
        self.event_counter = 0
        self.scanner = ScriptScanner(is_excluded)
        self._tasks = set()

    def should_track(self, resource_type, url):
        if is_excluded(url):
            return False
        return self.include_all or resource_type in API_TYPES

    # ---- events coming from the injected in-page script -------------------------------
    async def handle_event(self, source, data):
        event_id = self.event_counter
        self.event_counter += 1
        # Use the browser-side timestamp (taken the instant the interaction fired), not the
        # time we get around to recording it: screenshotting is slow enough that a fast API
        # call triggered by the same interaction would otherwise be attributed to the
        # previous event.
        ts = data['ts']
        shot = os.path.join(self.screenshots_dir, f'event-{event_id:03d}-{data["type"]}.png')
        try:
            await source['page'].screenshot(path=shot)
        except Exception as e:  # noqa: BLE001
            print(f'  (screenshot failed for event #{event_id}: {e})')
        self.events.append({
            'id': event_id,
            'type': data['type'],
            'url': data['url'],
            'title': data.get('title') or data['url'],
            'target': data.get('target'),
            'extra': data.get('extra'),
            'timestamp': ts,
            'screenshot': shot if os.path.exists(shot) else None,
        })
        target = data.get('target') or {}
        print(f'[#{event_id}] {data["type"]:<9} {target.get("selector", "")}  ({data["url"]})')

    # ---- network ----------------------------------------------------------------------
    def _spawn(self, coro):
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def on_response(self, response):
        self.scanner.on_response(response)
        self._spawn(self._record_response(response))

    async def _record_response(self, response):
        try:
            request = response.request
            rtype = request.resource_type
            if not self.should_track(rtype, request.url):
                return
            body = None
            try:
                raw = await response.body()
                body = raw.decode('utf-8', errors='replace') if len(raw) < 100000 \
                    else f'[truncated, {len(raw)} bytes]'
            except Exception:  # noqa: BLE001 - no body (redirect, opaque response)
                pass
            self.network_calls.append({
                'timestamp': now_ms(),
                'method': request.method,
                'url': request.url,
                'resourceType': rtype,
                'requestHeaders': dict(request.headers),
                'postData': _post_data(request),
                'status': response.status,
                'statusText': response.status_text,
                'responseHeaders': dict(response.headers),
                'responseBody': body,
            })
        except Exception:  # noqa: BLE001 - response/request already gone
            pass

    def on_request_failed(self, request):
        rtype = request.resource_type
        if not self.should_track(rtype, request.url):
            return
        self.network_calls.append({
            'timestamp': now_ms(),
            'method': request.method,
            'url': request.url,
            'resourceType': rtype,
            'requestHeaders': dict(request.headers),
            'postData': _post_data(request),
            'status': None,
            'statusText': request.failure or 'failed',
            'responseHeaders': {},
            'responseBody': None,
        })

    async def drain(self):
        """Let in-flight response handlers finish before reports are built."""
        if self._tasks:
            await asyncio.wait(set(self._tasks), timeout=3)
        await self.scanner.idle()

    async def finalize(self, started_at):
        finished_at = now_ms()
        print('\n' + '=' * 65)
        print(' Generating reports - KEEP THIS WINDOW OPEN until "All done" prints.')
        print('=' * 65 + '\n')
        await self.drain()
        calls_by_event = assign_calls_to_events(self.events, self.network_calls)
        generate_reports(self.session_dir, self.start_url, started_at, finished_at, self.events,
                         self.network_calls, calls_by_event, self.scanner, self.api_host)
        print(f'\nAll done. {len(self.events)} events, {len(self.network_calls)} API calls captured.')
        print(f'  Session folder: {self.session_dir}')


def _post_data(request):
    try:
        return request.post_data or None
    except Exception:  # noqa: BLE001 - binary body that is not valid UTF-8
        try:
            buf = request.post_data_buffer
            return buf.decode('utf-8', errors='replace') if buf else None
        except Exception:  # noqa: BLE001
            return None


def parse_args(argv):
    opts = {'all': False, 'api_host': DEFAULT_API_HOST, 'chrome': None, 'headless': False,
            'max_seconds': None}
    url = None
    for a in argv:
        if a == '--all':
            opts['all'] = True
        elif a == '--headless':
            opts['headless'] = True
        elif a.startswith('--api-host='):
            opts['api_host'] = a.split('=', 1)[1]
        elif a.startswith('--chrome-path='):
            opts['chrome'] = a.split('=', 1)[1]
        elif a.startswith('--max-seconds='):
            opts['max_seconds'] = float(a.split('=', 1)[1])
        elif not a.startswith('--') and url is None:
            url = a
    return url, opts


async def run(start_url, opts):
    n = datetime.now(timezone.utc)
    stamp = n.strftime('%Y-%m-%dT%H-%M-%S-') + f'{n.microsecond // 1000:03d}Z'
    session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions', stamp)
    tracker = Tracker(start_url, opts['all'], opts['api_host'], session_dir)

    print(f'Launching browser -> {start_url}')
    print('Tracking ALL network requests.' if opts['all']
          else 'Tracking XHR/fetch (API) requests only. Use --all to capture everything.')

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    # Replace asyncio's default Ctrl+C handling so Ctrl+C ends the session and writes reports.
    signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(stop.set))

    async with async_playwright() as pw:
        chrome = opts['chrome'] or (DEFAULT_CHROME if os.path.exists(DEFAULT_CHROME) else None)
        launch = {'headless': opts['headless']}
        if chrome:
            launch['executable_path'] = chrome
        else:
            launch['channel'] = 'chrome'
        browser = await pw.chromium.launch(**launch)
        context = await browser.new_context(viewport={'width': 1400, 'height': 900})
        started_at = now_ms()

        # Everything is registered on the CONTEXT, so every page/tab/popup is covered exactly
        # once and before it navigates: no per-page attach (which double-recorded calls).
        await context.expose_binding('__trackEvent', tracker.handle_event)
        await context.add_init_script(INJECTED_TRACKER_JS)
        context.on('response', tracker.on_response)
        context.on('requestfailed', tracker.on_request_failed)
        browser.on('disconnected', lambda *_: stop.set())

        page = await context.new_page()
        try:
            await page.goto(start_url, wait_until='domcontentloaded')
        except Exception as e:  # noqa: BLE001
            print(f'Failed to open {start_url}: {e}')

        print('\nInteract with the browser normally. Close the browser window (or press Ctrl+C '
              'here) when done to generate the report.\n')

        deadline = time.monotonic() + opts['max_seconds'] if opts['max_seconds'] else None
        while not stop.is_set():
            if deadline and time.monotonic() >= deadline:
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

        await tracker.finalize(started_at)
        try:
            if browser.is_connected():
                await browser.close()
        except Exception:  # noqa: BLE001 - already closed
            pass


def main():
    start_url, opts = parse_args(sys.argv[1:])
    if not start_url:
        print('Usage: python track.py <start-url> [--all] [--api-host=https://host] [--chrome-path=PATH]')
        return 1
    asyncio.run(run(start_url, opts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
