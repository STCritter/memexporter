#!/usr/bin/env python3
"""Convert a memories JSON file to readable TXT."""
import json
import sys
from datetime import datetime

if len(sys.argv) < 2:
    print("Usage: python json2txt.py memories.json")
    print("  Creates memories.txt in the same folder.")
    sys.exit(1)

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Handle both raw API response and our export format
items = data.get("items", data.get("memories", data if isinstance(data, list) else []))

out_path = path.rsplit(".", 1)[0] + ".txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"Total: {len(items)}\n")
    f.write("=" * 60 + "\n\n")
    for i, m in enumerate(items, 1):
        content = m.get("result", m.get("content", "(empty)"))
        mem_type = m.get("summary_type", m.get("type", "unknown")).upper()
        created = m.get("created_at", m.get("date", ""))
        date_str = ""
        if created:
            try:
                date_str = datetime.fromtimestamp(float(created)).strftime("%m/%d/%Y")
            except Exception:
                date_str = str(created)
        f.write(f"--- Memory #{i} [{mem_type}] {date_str} ---\n")
        f.write(content + "\n\n")

print(f"Done! {len(items)} memories saved to: {out_path}")
