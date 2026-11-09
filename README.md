# Browser API Tracker (Python)

Python port of the original Node.js tool (the Node version lives on the `main` branch).
Same behaviour, same reports.

Opens a real, visible Chrome window. While you click around it, the tool:

- Records a screenshot on every click, form submit, page load, and select/checkbox/radio change.
- For text fields, only takes a screenshot of the **first and last keystroke** of a typing session (not every keystroke) — one when you start typing, one when you blur/finish the field.
- Captures every API call (XHR/fetch) made by the page — method, URL, request payload, headers, response status/headers/body. Google Tag Manager, Google Analytics, and `www.google.com` traffic is excluded automatically.
- Correlates each API call with the interaction that triggered it, and collapses an API call repeated back-to-back (identical method/URL/payload/status) into a single row with a `×N` count.
- Writes the reports below as soon as you close the browser window:
  - **report.html** — technical report: every event, its screenshot, and the API calls it triggered.
  - **report.docx** — the same, as a Word document.
  - **journey.docx** — a readable, step-by-step **User Journey** narrative (Word), aimed at a human reader rather than a developer.
  - **testcases.xlsx** — an Excel sheet of test cases derived from the captured screens/interactions (scenario, steps, related API calls, expected result).
  - **api-list.xlsx** — a flat Excel list of every API call: Page Name, Event Name, Method, API URL, Status, Repeats — one row per call.
  - **api-details.xlsx** and **api-details.docx** — no screenshots. Per API call: screen name, event name, method, URL, status, request/response headers, request payload and response body. The Excel file also has **Hardcoded Keys (JS)** (keys/secrets found in the JavaScript the page loads) and **Client Signature & Auth** (key/signature/token values sent with requests, flagged if the same value appears in the page JS, plus HMAC/AES signing logic found in the code). It also has **Auth in Client JS**: where the page code sets Authorization / x-api-key / signature headers and what they are set to (hardcoded literal vs computed). The Word file has the same content.
  - **api-report.html** — a second HTML report with **no screenshots**, limited to API calls to `https://pnservices.bandhanmutual.com`. Per call: page name, page URL, event name, request URL, request headers, response headers, request payload and response body (collapsible, with Expand all). Use `--api-host=https://other.host` to point it at a different API origin.

## Setup (one-time)

Python 3.10+ is required.

```bash
pip install -r requirements.txt
playwright install chromium
```

(A virtual environment is recommended: `python -m venv .venv` and activate it first.)

## Usage

```bash
python track.py <start-url>
```

Example:

```bash
python track.py https://example.com
```

A Chrome window opens at that URL. Use the site normally — click links, fill in forms, submit — everything is recorded in the background. When you're done, **close the browser window** (or press `Ctrl+C` in the terminal).

**Important:** after that, the terminal keeps working for a few seconds to write all the reports (the Word/Excel ones embed full screenshots, so they take noticeably longer than the HTML report). **Do not close the terminal window** until you see `All done.` printed — closing it early kills the process mid-write and you'll only get the first few files. The tool prints a line for each report as it finishes:

```
=================================================================
 Generating reports - KEEP THIS WINDOW OPEN until "All done" prints.
=================================================================

  - raw data (data.json) ... done
  - HTML report (report.html) ... done
  - API report, no screenshots (api-report.html) ... done
  - API list (api-list.xlsx) ... done
  - API details + keys/signatures (api-details.xlsx) ... done
  - API details Word (api-details.docx) ... done
  - test cases (testcases.xlsx) ... done
  - User Journey (journey.docx) ... done
  - Word technical report (report.docx) ... done

All done. 61 events, 282 API calls captured.
```

Output layout:

```
sessions/<timestamp>/
  report.html        <- technical report, open in any browser
  report.docx         <- technical report, open in Word
  journey.docx          <- User Journey narrative, open in Word
  testcases.xlsx           <- test cases, open in Excel
  api-list.xlsx              <- Page Name / Event Name / API URL, open in Excel
  api-details.xlsx             <- headers, payloads, hardcoded keys, signatures (no screenshots)
  api-details.docx               <- same content as api-details.xlsx, in Word
  api-report.html                  <- no screenshots, only the pnservices API host
  data.json                    <- raw captured data
  screenshots/                   <- one PNG per event
```

### Options

| Option | Effect |
| --- | --- |
| `--all` | Capture *every* network request (images, CSS, fonts, etc.), not just XHR/fetch. |
| `--api-host=https://host` | API origin kept in `api-report.html` (default `https://pnservices.bandhanmutual.com`). |
| `--chrome-path=PATH` | Chrome executable to use. Default: `C:\Program Files\Google\Chrome\Application\chrome.exe`, otherwise the installed Chrome channel. |
| `--headless` | Run without a visible window (mainly for automated tests). |
| `--max-seconds=N` | End the session automatically after N seconds (mainly for automated tests). |

### Rebuild reports from a saved session

```bash
python rebuild_reports.py sessions/<timestamp> [--api-host=https://host]
```

Regenerates every report from that folder's `data.json` without a browser. Page JavaScript is not stored, so the key/auth sheets only contain what the original run saved (nothing, for sessions recorded before that existed).

## Notes

- **api-details.\* and api-report.html contain real tokens, keys and request headers.** The `sessions/` folder is git-ignored; keep it that way and do not share these files outside the team. Key detection is heuristic (name patterns, known token formats, and values that also appear in request headers) — treat results as leads to verify. Scripts over 3 MB are skipped, and Google Tag Manager / Analytics scripts are excluded.
- Typed fields generate exactly two events per typing session — `input_start` (first keystroke) and `input_end` (on blur/last keystroke) — never one per character. Non-typed fields (checkbox/radio/select) generate a single `change` event.
- Password field values are recorded as `(hidden)`, never the real value.
- The Excel test cases and Word User Journey both skip `input_start` rows — they only show the completed action per field, to stay readable.
- Response bodies larger than 100KB are truncated in the report to keep it lightweight.
- Works on a single browser session/site per run — start a new run (`python track.py <url>`) for a different site.
- Everything is registered once on the browser context (all tabs/popups), so each API call and event is recorded exactly once.

## Layout

```
track.py                      entry point (browser capture + CLI)
rebuild_reports.py            rebuild reports from a saved data.json
browser_api_tracker/
  injected_tracker.py         JavaScript injected into every page
  secret_scanner.py           hardcoded key / signature / auth-code detection
  reports.py                  call→event correlation and report orchestration
  report_*.py                 one module per report
  api_details_data.py         data shaping shared by api-details.xlsx/.docx
  common.py, xlsx_helpers.py, docx_helpers.py
```
