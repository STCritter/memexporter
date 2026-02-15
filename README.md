# Shapes.inc Memory Exporter

Bulk export all long-term memories from your [Shapes.inc](https://shapes.inc) bots.

Shapes.inc disables browser DevTools on their dashboard, making it difficult to access your own data. This tool uses browser automation to log in through the normal UI, navigate to your shapes' memory pages, and export everything to JSON and TXT files.

## How It Works

1. Opens a real browser window (Chromium via Playwright)
2. Navigates to shapes.inc and waits for you to log in via Discord OAuth
3. Detects your shapes from the dashboard
4. For each shape, navigates to the memories page
5. Scrolls to load all memories (handles infinite scroll + "Load More" buttons)
6. Scrapes memories from the page DOM **and** intercepts API responses
7. Exports to both JSON (structured) and TXT (human-readable) files

## Requirements

- Python 3.8+
- A Shapes.inc account with bots that have memories

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

### Interactive mode (recommended)
```bash
python memexporter.py
```
A browser window opens → log in with Discord → pick a shape → memories get exported.

### Export from a specific shape
```bash
python memexporter.py --shape-url "https://shapes.inc/dashboard/your-shape-id"
```

### Export ALL shapes at once
```bash
python memexporter.py --all
```

### Custom output directory
```bash
python memexporter.py --output ./my_backup
```

### Show browser window the whole time (for debugging)
```bash
python memexporter.py --headed
```

## Output

Memories are saved in the `exports/` directory (or your custom path):

```
exports/
├── MyBot_20260215_110000.json    # Structured data
└── MyBot_20260215_110000.txt     # Human-readable
```

### JSON format
```json
{
  "shape": "MyBot",
  "exported_at": "2026-02-15T11:00:00",
  "count": 42,
  "memories": [
    {
      "id": "mem_abc123",
      "content": "User likes pizza and hates mornings..."
    }
  ]
}
```

### TXT format
```
Memories for: MyBot
Exported: 2026-02-15T11:00:00
Total: 42
============================================================

--- Memory #1 ---
User likes pizza and hates mornings...

--- Memory #2 ---
...
```

## Troubleshooting

### "No memories found"
- The script saves a `_debug.html` file when this happens. Open it to see what the page looks like.
- Shapes.inc may have changed their page structure. Open an issue with the debug file.

### Login doesn't work
- Make sure you're logging in with the Discord account that owns the shapes.
- The script waits 5 minutes for login by default. Use `--timeout 600` for more time.

### Browser doesn't open
- Make sure you ran `playwright install chromium` after installing.
- On headless Linux servers, you may need: `playwright install --with-deps chromium`

## Limitations

- This tool scrapes the web UI, so it may break if Shapes.inc changes their dashboard layout.
- DevTools detection bypass works on most setups but isn't guaranteed.
- Rate limiting: the script adds delays between requests to be respectful.

## License

MIT — do whatever you want with it.

## Contributing

Found a bug or Shapes.inc changed their UI? Open an issue or PR.
