#!/usr/bin/env python3
"""
Shapes.inc Memory Exporter
Exports memories from your Shapes.inc bots via the API.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: Playwright is not installed.")
    print("Run: pip install playwright && playwright install chromium")
    sys.exit(1)

DEFAULT_OUTPUT_DIR = "exports"
DEFAULT_PROFILE_DIR = os.path.expanduser("~/.memexporter-profile")


def find_browser():
    """Find a system Chromium/Chrome executable."""
    import shutil, platform
    for c in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(c)
        if found:
            return found
    mac = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    win = [os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
           os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
           os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")]
    paths = mac if platform.system() == "Darwin" else win if platform.system() == "Windows" else []
    for p in paths:
        if os.path.exists(p):
            return p
    try:
        pw_browsers = os.path.expanduser("~/.cache/ms-playwright")
        if os.path.exists(pw_browsers):
            for root, dirs, files in os.walk(pw_browsers):
                for f in files:
                    if f in ("chromium", "chrome", "chrome.exe"):
                        full = os.path.join(root, f)
                        if os.access(full, os.X_OK):
                            return full
    except Exception:
        pass
    return None


def _launch_browser(p, profile, browser_path):
    """Launch Chromium with persistent context. Returns (context, page)."""
    kwargs = {
        "headless": False,
        "viewport": {"width": 1280, "height": 900},
        "args": ["--disable-blink-features=AutomationControlled"],
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    if browser_path:
        kwargs["executable_path"] = browser_path
    ctx = p.chromium.launch_persistent_context(profile, **kwargs)
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, pg


def do_login(p, profile, browser_path):
    """Handle the login flow. Returns True if login succeeded."""
    print("\n" + "=" * 50)
    print("  Step 1: Log in to Shapes.inc")
    print("=" * 50)
    print()
    print("  A browser window will open.")
    print("  Log in with your Shapes.inc account.")
    print("  The script will detect when you're done.")
    print()
    os.makedirs(profile, exist_ok=True)
    ctx, pg = _launch_browser(p, profile, browser_path)
    pg.goto("https://talk.shapes.inc/login", timeout=60000)
    print("  [*] Waiting for you to log in...")
    logged_in = False
    for _ in range(600):
        time.sleep(1)
        try:
            if "/login" not in pg.url and "auth." not in pg.url:
                logged_in = True
                break
        except Exception:
            break
    if not logged_in:
        print("  [!] Login timed out or failed.")
        ctx.close()
        return False
    print("  [+] Login successful!")
    print("  [*] Syncing session...")
    for url in ["https://shapes.inc", "https://shapes.inc/dashboard"]:
        try:
            pg.goto(url, timeout=30000)
            time.sleep(4)
        except Exception:
            pass
    body = pg.inner_text("body")
    if "My Shapes" in body or "Create Shape" in body:
        print("  [+] Session verified!")
    else:
        print("  [!] Warning: session may not be fully synced.")
    ctx.close()
    return True


def is_logged_in(p, profile, browser_path):
    """Quick check if we have a valid session."""
    if not os.path.exists(profile):
        return False
    try:
        ctx, pg = _launch_browser(p, profile, browser_path)
        pg.goto("https://shapes.inc/dashboard", timeout=30000)
        time.sleep(6)
        body = pg.inner_text("body")
        url = pg.url
        logged = ("My Shapes" in body or "Create Shape" in body) and "/login" not in url
        ctx.close()
        return logged
    except Exception:
        try:
            ctx.close()
        except Exception:
            pass
        return False


def url_to_memory_url(url):
    if not url.startswith("http"):
        url = f"https://{url}"
    if "/user/memory" in url:
        return url
    match = re.search(r"shapes\.inc/([^/]+)", url)
    if match:
        return f"https://shapes.inc/{match.group(1)}/user/memory"
    return url


def url_to_shape_name(url):
    match = re.search(r"shapes\.inc/([^/]+)", url)
    return match.group(1) if match else "unknown_shape"


def get_shape_uuid(page, memory_url):
    """Navigate to memory page and intercept the API call to get the shape UUID."""
    shape_uuid = None

    def on_response(response):
        nonlocal shape_uuid
        if "/api/memory/" in response.url and "?" in response.url:
            match = re.search(r"/api/memory/([a-f0-9-]+)", response.url)
            if match:
                shape_uuid = match.group(1)

    page.on("response", on_response)
    page.goto(memory_url, timeout=60000)
    time.sleep(5)
    try:
        page.wait_for_selector("text=User Memory", timeout=30000)
    except Exception:
        pass
    time.sleep(2)
    page.remove_listener("response", on_response)
    return shape_uuid


def fetch_memories_via_api(context, shape_uuid):
    """Fetch all memories using the API endpoint."""
    all_memories = []
    page_num = 1

    while True:
        api_url = f"https://shapes.inc/api/memory/{shape_uuid}?page={page_num}&limit=1000"
        print(f"  [*] Fetching page {page_num} via API...", end="")
        api_page = context.new_page()
        try:
            resp = api_page.goto(api_url, timeout=30000)
            if resp.status != 200:
                print(f" error {resp.status}")
                api_page.close()
                break
            raw = api_page.inner_text("body")
            data = json.loads(raw)
            api_page.close()
        except Exception as e:
            print(f" error: {e}")
            try:
                api_page.close()
            except Exception:
                pass
            break

        entries = data if isinstance(data, list) else data.get("memories", data.get("data", []))
        if isinstance(data, dict) and not isinstance(entries, list):
            entries = [data]
        if isinstance(data, list):
            entries = data

        page_memories = []
        items = entries if isinstance(entries, list) else [entries]
        for entry in items:
            if not isinstance(entry, dict):
                continue
            content = entry.get("result", entry.get("content", ""))
            if not content:
                continue
            summary_type = entry.get("summary_type", "unknown")
            created = entry.get("created_at", "")
            date_str = ""
            if created:
                try:
                    dt = datetime.fromtimestamp(float(created))
                    date_str = dt.strftime("%m/%d/%Y")
                except Exception:
                    date_str = str(created)
            page_memories.append({"type": summary_type, "content": content, "date": date_str})

        print(f" {len(page_memories)} memories")
        all_memories.extend(page_memories)

        pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
        has_next = pagination.get("has_next", False)
        total = pagination.get("total", len(all_memories))
        total_pages = pagination.get("total_pages", 1)
        if total_pages > 1:
            print(f"  [*] Total: {total} memories across {total_pages} page(s)")
        if not has_next or not page_memories:
            break
        page_num += 1

    return all_memories


def export_memories(memories, shape_name, output_dir):
    """Export memories to JSON and TXT files."""
    os.makedirs(output_dir, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in shape_name).strip()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    seen = set()
    unique = []
    for m in memories:
        key = m.get("content", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(m)

    json_path = os.path.join(output_dir, f"{safe_name}_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"shape": shape_name, "exported_at": datetime.now().isoformat(),
                    "count": len(unique), "memories": unique}, f, indent=2, ensure_ascii=False)

    txt_path = os.path.join(output_dir, f"{safe_name}_{timestamp}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Memories for: {shape_name}\n")
        f.write(f"Exported: {datetime.now().isoformat()}\n")
        f.write(f"Total: {len(unique)}\n")
        f.write("=" * 60 + "\n\n")
        for i, m in enumerate(unique, 1):
            mem_type = m.get("type", "unknown").upper()
            mem_date = m.get("date", "")
            f.write(f"--- Memory #{i} [{mem_type}] {mem_date} ---\n")
            f.write(m.get("content", "(empty)") + "\n\n")

    return json_path, txt_path, len(unique)


def export_shape(page, context, url, output_dir, debug=False):
    """Export memories from a single shape URL. Returns count exported."""
    memory_url = url_to_memory_url(url)
    shape_name = url_to_shape_name(url)

    print(f"\n  [*] Shape: {shape_name}")
    print(f"  [*] URL:   {memory_url}")
    print(f"  [*] Navigating...")

    shape_uuid = get_shape_uuid(page, memory_url)

    if shape_uuid:
        print(f"  [+] Found shape ID: {shape_uuid[:8]}...")
        print(f"  [*] Fetching memories via API...")
        memories = fetch_memories_via_api(context, shape_uuid)
        if memories:
            json_path, txt_path, count = export_memories(memories, shape_name, output_dir)
            print(f"\n  [+] Exported {count} memories!")
            print(f"      JSON: {json_path}")
            print(f"      TXT:  {txt_path}")
            return count

    print("  [!] Could not fetch memories.")
    body = page.inner_text("body")
    if "Log in" in body or "Sign up" in body:
        print("  [!] You're not logged in. Run the script again.")
    else:
        print("  [!] You might not have access to this shape's memories.")
    if debug:
        debug_path = os.path.join(output_dir, f"{shape_name}_debug.html")
        os.makedirs(output_dir, exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"  [*] Debug HTML saved: {debug_path}")
    return 0


def interactive_flow(args):
    """Guided interactive mode."""
    profile = args.profile or DEFAULT_PROFILE_DIR
    browser_path = args.browser_path or find_browser()

    print()
    print("=" * 50)
    print("  Shapes.inc Memory Exporter")
    print("=" * 50)

    if not browser_path:
        print("\n  [!] Could not find Chrome or Chromium.")
        print("  [!] Install one, or use --browser-path /path/to/chrome")
        sys.exit(1)

    print("\n  [*] Checking if you're already logged in...")
    with sync_playwright() as p:
        logged = is_logged_in(p, profile, browser_path)

    if logged:
        print("  [+] You're logged in!")
    else:
        print("  [!] Not logged in yet.")
        with sync_playwright() as p:
            if not do_login(p, profile, browser_path):
                print("\n  [!] Could not log in. Please try again.")
                sys.exit(1)

    print("\n" + "=" * 50)
    print("  Step 2: Choose shapes to export")
    print("=" * 50)
    print()
    print("  Paste your memory URL (e.g. shapes.inc/your-shape/user/memory)")
    print()

    urls = list(args.urls) if args.urls else []
    if not urls:
        while True:
            url = input("  Paste a memory URL (or press Enter to finish): ").strip()
            if not url:
                break
            if "shapes.inc" not in url and not url.startswith("http"):
                print("  [!] That doesn't look like a shapes.inc URL. Try again.")
                continue
            urls.append(url)
            print(f"  [+] Added: {url_to_shape_name(url)}")
            print()

    if not urls:
        print("  [!] No URLs provided.")
        sys.exit(0)

    print("\n" + "=" * 50)
    print(f"  Step 3: Exporting memories ({len(urls)} shape(s))")
    print("=" * 50)

    with sync_playwright() as p:
        ctx, page = _launch_browser(p, profile, browser_path)
        total_exported = 0
        results = []
        for i, raw_url in enumerate(urls, 1):
            print(f"\n  --- Shape {i}/{len(urls)} ---")
            count = export_shape(page, ctx, raw_url, args.output, debug=args.debug)
            total_exported += count
            results.append((url_to_shape_name(raw_url), count))
        try:
            ctx.close()
        except Exception:
            pass

    print("\n" + "=" * 50)
    print("  All done!")
    print("=" * 50)
    print()
    for name, count in results:
        status = f"{count} memories" if count > 0 else "no memories found"
        print(f"    {name}: {status}")
    print()
    print(f"  Total: {total_exported} memories exported")
    print(f"  Saved to: {os.path.abspath(args.output)}/")
    print()


def main():
    parser = argparse.ArgumentParser(description="Export memories from Shapes.inc bots")
    parser.add_argument("urls", nargs="*", help="Memory page URL(s)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Save page HTML for debugging")
    parser.add_argument("--browser-path", help="Path to Chrome/Chromium")
    parser.add_argument("--profile", default=None, help=f"Browser profile dir (default: {DEFAULT_PROFILE_DIR})")
    args = parser.parse_args()
    interactive_flow(args)


if __name__ == "__main__":
    main()
