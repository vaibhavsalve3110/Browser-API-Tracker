#!/usr/bin/env python3
"""Rebuild every report from a saved sessions/<timestamp>/data.json (no browser needed).

Usage:
    python rebuild_reports.py sessions/<timestamp> [--api-host=https://host]

Page JavaScript is not stored in data.json, so the key/auth sheets only contain what the
original run saved under "jsFindings" (nothing, for sessions recorded before that existed).
"""
import json
import os
import sys

from browser_api_tracker.report_api_html import DEFAULT_API_HOST
from browser_api_tracker.reports import assign_calls_to_events, generate_reports
from browser_api_tracker.secret_scanner import StaticScanner


def main(argv):
    positional = [a for a in argv if not a.startswith('--')]
    if not positional:
        print('Usage: python rebuild_reports.py <session-folder> [--api-host=https://host]')
        return 1
    session_dir = os.path.abspath(positional[0])
    host_arg = next((a for a in argv if a.startswith('--api-host=')), None)
    api_host = host_arg.split('=', 1)[1] if host_arg else DEFAULT_API_HOST

    with open(os.path.join(session_dir, 'data.json'), encoding='utf-8') as fh:
        data = json.load(fh)
    events, calls = data['events'], data['networkCalls']
    calls_by_event = assign_calls_to_events(events, calls)
    scanner = StaticScanner(data.get('jsFindings'))
    print(f'Rebuilding reports in {session_dir}')
    generate_reports(session_dir, data['startUrl'], data['startedAt'], data['finishedAt'], events,
                     calls, calls_by_event, scanner, api_host, write_data=False)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
