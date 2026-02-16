# Shapes.inc Memory Exporter

Bulk export long-term memories from your [Shapes.inc](https://shapes.inc) bots.

## How It Works

1. You log in to shapes.inc via a browser (one-time setup)
2. You give the script the URL of your shape's memory page
3. The script navigates there, paginates through all pages, and scrapes every memory
4. Exports to JSON + TXT files

## Requirements

- Python 3.8+
- Chromium or Google Chrome installed
- A Shapes.inc account with shapes that have memories

## Installation

```bash
# Clone the repo
git clone https://github.com/STCritter/memexporter.git
cd memexporter

# Install dependencies
pip install -r requirements.txt

# Install the browser (one-time)
playwright install chromium
```

## Usage

Just run:
```bash
python memexporter.py
```

The script guides you through everything step by step:

1. **Login** — checks if you're logged in, opens a browser if not
2. **Paste URLs** — asks you to paste your shape memory page URLs
3. **Export** — scrapes all memory pages and saves the results

That's it!

### How to find your memory URL

1. Go to `shapes.inc` in your browser
2. Open your shape's settings
3. Click **Memory** in the sidebar
4. Copy the URL — it looks like: `shapes.inc/your-shape-name/user/memory`

### Pass URLs directly (skip the prompts)
```bash
python memexporter.py https://shapes.inc/shape1/user/memory https://shapes.inc/shape2/user/memory
```

### Custom output directory
```bash
python memexporter.py --output ./my_backup
```

### Debug mode
```bash
python memexporter.py --debug
```
Saves a `_debug.html` file if something goes wrong — useful for troubleshooting.

## Output

Memories are saved in the `exports/` directory (or your custom path):

```
exports/
├── my-shape_20260216_091345.json    # Structured data
└── my-shape_20260216_091345.txt     # Human-readable
```

### JSON format
```json
{
  "shape": "my-shape",
  "exported_at": "2026-02-16T09:13:45",
  "count": 36,
  "memories": [
    {
      "type": "automatic",
      "content": "User likes pizza and hates mornings...",
      "date": "04/07/2025"
    }
  ]
}
```

### TXT format
```
Memories for: my-shape
Exported: 2026-02-16T09:13:45
Total: 36
============================================================

--- Memory #1 [AUTOMATIC] 04/07/2025 ---
User likes pizza and hates mornings...

--- Memory #2 [AUTOMATIC] 03/01/2025 ---
...
```

## Troubleshooting

### "Doesn't look like a memory page"
- Make sure you logged in when prompted.
- Your session may have expired — just run the script again and it will re-prompt login.

### "No memories found"
- Run with `--debug` and check the `_debug.html` file.
- Shapes.inc may have changed their page structure. Open an issue with the debug file.

### Browser doesn't open
- Make sure Chromium or Chrome is installed on your system.
- Use `--browser-path /path/to/chrome` if auto-detection doesn't work.
- On headless Linux servers: `playwright install --with-deps chromium`

## Limitations

- Scrapes the web UI, so it may break if Shapes.inc changes their page structure.
- Only exports **memory entries** — shape config, personality, backstory, etc. are not included.

## License

MIT — do whatever you want with it.

## Contributing

Found a bug or Shapes.inc changed their UI? Open an issue or PR.
