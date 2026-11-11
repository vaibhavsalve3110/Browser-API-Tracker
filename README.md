# Browser API Tracker

Opens a visible Chrome window, records a screenshot for every interaction, captures the XHR/fetch API calls each interaction triggers, and writes HTML, Word and Excel reports when you close the window.

The same tool is provided in two languages. Both produce the same reports.

| Folder | Language | Start here |
| --- | --- | --- |
| [`node/`](node/README.md) | Node.js + Playwright | `cd node && npm install && node track.js <url>` |
| [`python/`](python/README.md) | Python + Playwright | `cd python && pip install -r requirements.txt && python track.py <url>` |

Each version writes its output to its own `sessions/` folder (git-ignored). Session files contain real tokens, keys and request headers: do not share them outside the team.
