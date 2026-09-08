# Browser API Tracker

Opens a real, visible Chrome window. While you click around it, the tool:

- Records a screenshot on every click, form submit, page load, and select/checkbox/radio change.
- For text fields, only takes a screenshot of the **first and last keystroke** of a typing session (not every keystroke) — one when you start typing, one when you blur/finish the field.
- Captures every API call (XHR/fetch) made by the page — method, URL, request payload, headers, response status/body. Google Tag Manager, Google Analytics, and `www.google.com` traffic is excluded automatically.
- Correlates each API call with the interaction that triggered it, and collapses an API call repeated back-to-back (identical method/URL/payload/status) into a single row with a `×N` count.
- Writes four reports as soon as you close the browser window:
  - **report.html** — technical report: every event, its screenshot, and the API calls it triggered.
  - **report.docx** — the same, as a Word document.
  - **journey.docx** — a readable, step-by-step **User Journey** narrative (Word), aimed at a human reader rather than a developer.
  - **testcases.xlsx** — an Excel sheet of test cases derived from the captured screens/interactions (scenario, steps, related API calls, expected result).

## Setup (one-time)

```bash
npm install
npx playwright install chromium
```

## Usage

```bash
node track.js <start-url>
```

Example:

```bash
node track.js https://example.com
```

A Chromium window opens at that URL. Use the site normally — click links, fill in forms, submit — everything is recorded in the background. When you're done, **close the browser window** (or press `Ctrl+C` in the terminal). The tool then writes:

```
sessions/<timestamp>/
  report.html        <- technical report, open in any browser
  report.docx         <- technical report, open in Word
  journey.docx          <- User Journey narrative, open in Word
  testcases.xlsx           <- test cases, open in Excel
  data.json                  <- raw captured data
  screenshots/                 <- one PNG per event
```

### Options

- `--all` — capture *every* network request (images, CSS, fonts, etc.), not just XHR/fetch API calls:

  ```bash
  node track.js https://example.com --all
  ```

## Notes

- Typed fields generate exactly two events per typing session — `input_start` (first keystroke) and `input_end` (on blur/last keystroke) — never one per character. Non-typed fields (checkbox/radio/select) generate a single `change` event.
- Password field values are recorded as `(hidden)`, never the real value.
- The Excel test cases and Word User Journey both skip `input_start` rows — they only show the completed action per field, to stay readable.
- Response bodies larger than 100KB are truncated in the report to keep it lightweight.
- Works on a single browser session/site per run — start a new run (`node track.js <url>`) for a different site.
- Uses your installed Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`), not Playwright's bundled Chromium.
