#!/usr/bin/env python3
"""
Shapes.inc Memory Exporter
Exports long-term memories from your Shapes.inc bots.

How it works:
  1. Log in to shapes.inc in your normal browser
  2. Go to your shape's memory page (e.g. shapes.inc/sporty-9ujz/user/memory)
  3. Copy the URL
  4. Run: python memexporter.py URL [URL2 URL3 ...]

The script opens a browser, navigates to each URL, scrapes all memory pages,
and exports to JSON + TXT files.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
except ImportError:
    print("ERROR: Playwright is not installed.")
    print("Run: pip install playwright && playwright install chromium")
    sys.exit(1)


DEFAULT_OUTPUT_DIR = "exports"
DEFAULT_PROFILE_DIR = os.path.expanduser("~/.memexporter-profile")


def find_browser():
    """Find a system Chromium/Chrome executable."""
    import shutil
    for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def get_page_info(page):
    """Parse 'Page X of Y' text to get current page and total pages."""
    try:
        body_text = page.inner_text("body")
        match = re.search(r"Page\s+(\d+)\s+of\s+(\d+)", body_text)
        if match:
            return int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    return 1, 1


def scrape_current_page_memories(page):
    """Scrape memory entries from the current page DOM.
    Uses CSS class selectors matching the actual shapes.inc HTML structure:
      - Card: div[class*="cardPreview"]
      - Label: label (contains "automatic memory" or "manual memory")
      - Content: div[class*="result__"] (the memory text)
      - Date: div[class*="date__"] span
    """
    memories = []
    try:
        entries = page.evaluate(r"""
            () => {
                const results = [];
                // Primary: use CSS class selectors from shapes.inc
                const cards = document.querySelectorAll('[class*="cardPreview"]');
                for (const card of cards) {
                    const label = card.querySelector('label');
                    const contentEl = card.querySelector('[class*="result__"]');
                    const dateEl = card.querySelector('[class*="date__"] span');

                    if (!contentEl) continue;
                    const content = contentEl.textContent.trim();
                    if (!content) continue;

                    const memType = label ? label.textContent.trim().toLowerCase() : 'unknown';
                    const date = dateEl ? dateEl.textContent.trim() : '';

                    results.push({
                        type: memType.replace(' memory', ''),
                        content: content,
                        date: date,
                    });
                }

                // Fallback: if no cards found, try text-based matching
                if (results.length === 0) {
                    const allEls = document.querySelectorAll('*');
                    for (const el of allEls) {
                        const text = (el.textContent || '').toLowerCase();
                        if ((text.includes('automatic memory') || text.includes('manual memory'))
                            && el.children.length > 0 && text.length < 2000) {
                            if (el.querySelector('[type="checkbox"]')) {
                                const dateMatch = el.textContent.match(/(\d{1,2}\/\d{1,2}\/\d{4})/);
                                let content = el.textContent.trim();
                                content = content.replace(/automatic memory/gi, '');
                                content = content.replace(/manual memory/gi, '');
                                content = content.replace(/select all\s*\(\d+\)/gi, '');
                                content = content.replace(/page\s+\d+\s+of\s+\d+/gi, '');
                                if (dateMatch) content = content.replace(dateMatch[1], '');
                                content = content.trim();
                                if (content.length > 5) {
                                    results.push({
                                        type: text.includes('automatic') ? 'automatic' : 'manual',
                                        content: content,
                                        date: dateMatch ? dateMatch[1] : '',
                                    });
                                }
                            }
                        }
                    }
                }
                return results;
            }
        """)
        if entries:
            memories.extend(entries)
    except Exception as e:
        print(f"  [!] DOM scrape error: {e}")
    return memories


def click_next_page(page):
    """Click the right/next arrow button in pagination. Returns True if clicked."""
    try:
        buttons = page.query_selector_all("button")
        for btn in buttons:
            try:
                inner = btn.inner_html()
                text = btn.inner_text().strip()
                if ("chevron-right" in inner or "arrow-right" in inner
                        or "ChevronRight" in inner or text in ("\u2192", "\u203a", ">")):
                    if btn.is_visible() and btn.is_enabled():
                        disabled = btn.get_attribute("disabled")
                        if disabled is None:
                            btn.click()
                            time.sleep(2)
                            return True
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: find buttons near "Page X of Y" text
    try:
        pagination = page.query_selector("text=/Page \\d+ of \\d+/")
        if pagination:
            parent = pagination.evaluate_handle("el => el.parentElement")
            if parent:
                btns = parent.query_selector_all("button")
                if len(btns) >= 2:
                    btns[1].click()
                    time.sleep(2)
                    return True
    except Exception:
        pass

    return False


def scrape_all_memory_pages(page):
    """Scrape memories from all pages."""
    all_memories = []
    current_page, total_pages = get_page_info(page)
    print(f"  [*] {total_pages} page(s) of memories")

    for pg in range(1, total_pages + 1):
        if pg > 1:
            if not click_next_page(page):
                print(f"  [!] Could not go to page {pg}")
                break

        page_memories = scrape_current_page_memories(page)
        print(f"  [*] Page {pg}/{total_pages}: {len(page_memories)} memories")
        all_memories.extend(page_memories)

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
        json.dump({
            "shape": shape_name,
            "exported_at": datetime.now().isoformat(),
            "count": len(unique),
            "memories": unique
        }, f, indent=2, ensure_ascii=False)

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


def url_to_memory_url(url):
    """Convert any shapes.inc URL to the memory page URL."""
    if not url.startswith("http"):
        url = f"https://{url}"
    if "/user/memory" in url:
        return url
    match = re.search(r"shapes\.inc/([^/]+)", url)
    if match:
        return f"https://shapes.inc/{match.group(1)}/user/memory"
    return url


def url_to_shape_name(url):
    """Extract shape vanity name from URL."""
    match = re.search(r"shapes\.inc/([^/]+)", url)
    return match.group(1) if match else "unknown_shape"


def main():
    parser = argparse.ArgumentParser(
        description="Export memories from Shapes.inc bots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
How to use:
  1. Log in:    %(prog)s --login
  2. Export:    %(prog)s https://shapes.inc/YOUR-SHAPE/user/memory

  You can export multiple shapes at once:
     %(prog)s URL1 URL2 URL3

  Custom output dir:
     %(prog)s URL --output ./my_exports
        """
    )
    parser.add_argument("urls", nargs="*",
                        help="Memory page URL(s) — e.g. https://shapes.inc/sporty-9ujz/user/memory")
    parser.add_argument("--login", action="store_true",
                        help="Open browser to log in (run this first)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR,
                        help="Output directory (default: exports/)")
    parser.add_argument("--debug", action="store_true",
                        help="Save page HTML for debugging")
    parser.add_argument("--browser-path",
                        help="Path to Chromium/Chrome (auto-detected if not set)")
    parser.add_argument("--profile", default=None,
                        help=f"Browser profile dir (default: {DEFAULT_PROFILE_DIR})")
    args = parser.parse_args()

    profile = args.profile or DEFAULT_PROFILE_DIR
    browser_path = args.browser_path or find_browser()

    print("=" * 50)
    print("  Shapes.inc Memory Exporter")
    print("=" * 50)

    if not browser_path:
        print("[!] Could not find Chromium/Chrome. Install it or use --browser-path.")
        sys.exit(1)

    # --login: open browser via Playwright for manual login
    if args.login:
        print(f"\n[*] Opening browser for login...")
        print(f"[*] Profile: {profile}")
        print(f"[*] Log in in the browser window. The script will detect it automatically.\n")
        os.makedirs(profile, exist_ok=True)
        with sync_playwright() as p:
            launch_kwargs = {
                "headless": False,
                "args": ["--disable-blink-features=AutomationControlled"],
                "viewport": {"width": 1280, "height": 900},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "executable_path": browser_path,
            }
            ctx = p.chromium.launch_persistent_context(profile, **launch_kwargs)
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            pg.goto("https://talk.shapes.inc/login", timeout=30000)
            # Wait for login: URL will change away from /login after success
            print("[*] Waiting for login...")
            for _ in range(600):  # 10 minutes max
                time.sleep(1)
                url = pg.url
                if "/login" not in url and "auth." not in url:
                    break
            print("[+] Login detected!")
            # Visit shapes.inc/dashboard to save cookies for that domain too
            print("[*] Syncing session to shapes.inc...")
            pg.goto("https://shapes.inc/dashboard", timeout=30000)
            time.sleep(3)
            ctx.close()
        print("\n[+] Session saved!")
        print(f"[*] Now run: python {sys.argv[0]} https://shapes.inc/YOUR-SHAPE/user/memory")
        return

    # Need at least one URL
    if not args.urls:
        print("\n[!] No URLs provided.")
        print("    Usage: python memexporter.py https://shapes.inc/YOUR-SHAPE/user/memory")
        print("    First time? Run: python memexporter.py --login")
        sys.exit(1)

    # Launch browser with saved profile
    print(f"\n[*] Using profile: {profile}")
    print(f"[*] Using browser: {browser_path}")

    with sync_playwright() as p:
        launch_kwargs = {
            "headless": False,
            "args": ["--disable-blink-features=AutomationControlled"],
            "viewport": {"width": 1280, "height": 900},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "executable_path": browser_path,
        }
        context = p.chromium.launch_persistent_context(profile, **launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()

        total_exported = 0

        for raw_url in args.urls:
            memory_url = url_to_memory_url(raw_url)
            shape_name = url_to_shape_name(raw_url)

            print(f"\n{'=' * 40}")
            print(f"[*] {shape_name}")
            print(f"[*] {memory_url}")
            print(f"{'=' * 40}")

            # Navigate to memory page
            page.goto(memory_url, timeout=30000)
            time.sleep(4)

            # Check if we landed on the memory page
            body = page.inner_text("body")
            if "User Memory" not in body and "memory" not in body.lower():
                print("  [!] Doesn't look like a memory page.")
                print("  [!] Make sure you're logged in: python memexporter.py --login")
                if args.debug:
                    debug_path = os.path.join(args.output, f"{shape_name}_debug.html")
                    os.makedirs(args.output, exist_ok=True)
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(page.content())
                    print(f"  [*] Debug HTML saved: {debug_path}")
                continue

            print("  [+] On memory page")

            # Scrape all pages
            memories = scrape_all_memory_pages(page)

            if memories:
                json_path, txt_path, count = export_memories(memories, shape_name, args.output)
                print(f"\n  [+] Exported {count} memories:")
                print(f"      JSON: {json_path}")
                print(f"      TXT:  {txt_path}")
                total_exported += count
            else:
                print("\n  [!] No memories found.")
                if args.debug:
                    debug_path = os.path.join(args.output, f"{shape_name}_debug.html")
                    os.makedirs(args.output, exist_ok=True)
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(page.content())
                    print(f"  [*] Debug HTML saved: {debug_path}")

        print(f"\n{'=' * 50}")
        print(f"  Done! Exported {total_exported} total memories.")
        print(f"  Output: {os.path.abspath(args.output)}")
        print(f"{'=' * 50}")

        try:
            context.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
