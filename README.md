# Shapes.inc Memory Exporter

Export your long-term memories from [Shapes.inc](https://shapes.inc) bots. Uses the Shapes.inc API for instant downloads — even shapes with thousands of memories export in seconds. Exports to JSON + TXT.

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
3. Downloads all memories via the API instantly
4. Saves to `exports/` folder

### Options

```bash
# Pass URLs directly (skip the prompts)
python memexporter.py https://shapes.inc/shape1/user/memory https://shapes.inc/shape2/user/memory

# Custom output folder
python memexporter.py --output ./my_backup

# Debug mode (saves page HTML if something goes wrong)
python memexporter.py --debug
```

## Output

Memories are saved in the `exports/` folder:

```
exports/
├── my-shape_20260216_091345.json
└── my-shape_20260216_091345.txt
```

**JSON** — structured data with type, content, and date for each memory.

**TXT** — human-readable format:

```
Memories for: my-shape
Exported: 2026-02-16T09:13:45
Total: 42
============================================================

--- Memory #1 [AUTOMATIC] 02/15/2026 ---
User talked about their favorite pizza toppings...

--- Memory #2 [AUTOMATIC] 03/01/2025 ---
...
```

## Manual export (no script needed)

If the script doesn't work for you, you can export memories manually from your browser:

1. Go to your shape's memory page (e.g. `shapes.inc/your-shape/user/memory`)
2. Press **F12** to open Developer Tools
3. Click the **Network** tab
4. Reload the page (**F5**)
5. In the filter box, type **`memory`**
6. You'll see a request like `memory/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx?page=1&limit=20`
7. Copy the long ID between `memory/` and `?` — that's your shape's UUID
8. Open a new tab and go to:
   ```
   https://shapes.inc/api/memory/YOUR-UUID?page=1&limit=10000
   ```
9. **Ctrl+A** to select all, **Ctrl+C** to copy
10. Paste into Notepad, save as `memories.json`

### Converting JSON to readable text

Got a `memories.json` and want it as readable text? Use the included converter:

- **Windows** — drag and drop your `.json` file onto `json2txt.bat`
- **Linux / macOS** — run `./json2txt.sh memories.json`
- **Or directly** — `python json2txt.py memories.json`

It creates a `.txt` file with all memories formatted nicely with type and date.

## Troubleshooting

- **"Could not fetch memories"** — you're not logged in, or the session expired. Run the script again.
- **Browser doesn't open** — make sure Chrome or Chromium is installed. Use `--browser-path /path/to/chrome` if auto-detection fails.

## Limitations

- Uses the Shapes.inc web API — may break if they change their API.
- Only exports **memory entries** — shape config, personality, etc. are not included.

## License

MIT
