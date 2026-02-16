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

## Troubleshooting

- **"Could not fetch memories"** — you're not logged in, or the session expired. Run the script again.
- **Browser doesn't open** — make sure Chrome or Chromium is installed. Use `--browser-path /path/to/chrome` if auto-detection fails.

## Limitations

- Uses the Shapes.inc web API — may break if they change their API.
- Only exports **memory entries** — shape config, personality, etc. are not included.

## License

MIT
