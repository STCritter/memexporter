# Shapes.inc Memory Exporter

Export your long-term memories from [Shapes.inc](https://shapes.inc) bots. Handles pagination automatically (even 500+ pages), saves progress so nothing is lost, and exports to JSON + TXT.

## Setup (one time)

1. Install [Python 3.8+](https://www.python.org/downloads/) and [Chrome](https://www.google.com/chrome/) or [Chromium](https://www.chromium.org/)
2. Download this repo — click the green **Code** button above → **Download ZIP** → unzip it

That's it. Dependencies install automatically on first run.

## Running it

- **Windows** — double-click `run.bat`
- **Linux / macOS** — double-click `run.sh` (or run `./run.sh`)

The script walks you through everything:

1. Checks if you're logged in (opens a browser to log in if not)
2. Asks you to paste your memory page URL(s)
3. Scrapes all pages and downloads the results

### How to find your memory URL

1. Go to `shapes.inc` in your browser
2. Open your shape's page
3. Click **Memory** in the sidebar
4. Copy the URL from the address bar — looks like: `shapes.inc/your-shape/user/memory`

### Options

```bash
# Pass URLs directly (skip the prompts)
python memexporter.py https://shapes.inc/shape1/user/memory https://shapes.inc/shape2/user/memory

# Custom output folder
python memexporter.py --output ./my_backup

# Debug mode (saves page HTML if something goes wrong)
python memexporter.py --debug
```

### Large exports (hundreds of pages)

The script handles large shapes automatically:
- Shows progress with percentage and running total
- Saves progress every 50 pages — if it crashes, your data is safe in `exports/shapename_progress.json`
- Retries automatically if a page fails to load

## Output

Memories are saved in the `exports/` folder:

```
exports/
├── my-shape_20260216_091345.json
└── my-shape_20260216_091345.txt
```

**JSON:**
```json
{
  "shape": "my-shape",
  "exported_at": "2026-02-16T09:13:45",
  "count": 36,
  "memories": [
    {
      "type": "automatic",
      "content": "User mentioned they like pizza...",
      "date": "04/07/2025"
    }
  ]
}
```

**TXT:**
```
Memories for: my-shape
Total: 36
============================================================

--- Memory #1 [AUTOMATIC] 04/07/2025 ---
User mentioned they like pizza...

--- Memory #2 [AUTOMATIC] 03/01/2025 ---
...
```

## Troubleshooting

- **"Doesn't look like a memory page"** — you're not logged in, or the session expired. Run the script again and it will re-prompt login.
- **"No memories found"** — run with `--debug` and check the `_debug.html` file. Open an issue if it persists.
- **Browser doesn't open** — make sure Chrome or Chromium is installed. Use `--browser-path /path/to/chrome` if auto-detection fails.

## Limitations

- Scrapes the web UI — may break if Shapes.inc changes their page structure.
- Only exports **memory entries** — shape config, personality, etc. are not included.

## License

MIT

## Contributing

Found a bug or Shapes.inc changed their UI? Open an issue or PR.
