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
    print("Run: pip install playwright && playwright install chromium firefox")
    sys.exit(1)


DEFAULT_OUTPUT_DIR = "exports"
DEFAULT_PROFILE_DIR = os.path.expanduser("~/.memexporter-profile")


def find_browser():
    """Find a system Chromium/Chrome executable."""
    import shutil
    import platform

    # Check PATH first (works on all OSes)
    for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(candidate)
        if found:
            return found

    # macOS common locations
    mac_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ]

    # Windows common locations
    win_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]

    check_paths = mac_paths if platform.system() == "Darwin" else win_paths if platform.system() == "Windows" else []
    for path in check_paths:
        if os.path.exists(path):
            return path

    # Fallback: try Playwright's bundled chromium
    try:
        from playwright._impl._driver import compute_driver_executable
        driver = compute_driver_executable()
        pw_browsers = os.path.join(os.path.dirname(driver), "..", "driver", "package", ".local-browsers")
        if not os.path.exists(pw_browsers):
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


def _click_page_button(page, aria_label):
    """Click a pagination button by aria-label. Returns True if clicked."""
    try:
        btn = page.query_selector(f'button[aria-label="{aria_label}"]')
        if btn and btn.is_visible() and btn.is_enabled():
            btn.click(timeout=5000)
            time.sleep(1)
            return True
    except Exception:
        pass

    # Fallback: find buttons with right/left arrow icons
    is_next = "Next" in aria_label
    try:
        buttons = page.query_selector_all("button")
        for btn in buttons:
            try:
                inner = btn.inner_html()
                icon = 'data-icon="right"' if is_next else 'data-icon="left"'
                fa = "fa-right" if is_next else "fa-left"
                if icon in inner or fa in inner:
                    if btn.is_visible() and btn.is_enabled():
                        btn.click(timeout=5000)
                        time.sleep(1)
                        return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def click_next_page(page):
    """Click the next page button. Returns True if clicked."""
    return _click_page_button(page, "Next page")


def click_prev_page(page):
    """Click the previous page button. Returns True if clicked."""
    return _click_page_button(page, "Previous page")


def go_to_first_page(page):
    """Navigate back to page 1 by clicking Previous repeatedly."""
    current, total = get_page_info(page)
    if current > 1:
        print(f"  [*] On page {current}, going back to page 1...")
    while current > 1:
        if not click_prev_page(page):
            break
        time.sleep(1)
        current, total = get_page_info(page)
    if current == 1:
        time.sleep(1)  # Let DOM settle


def scrape_all_memory_pages(page, shape_name=None, output_dir=None, max_pages=None, slow=False):
    """Scrape memories from all pages, starting from page 1."""
    all_memories = []
    page_wait = 3 if slow else 1

    # Always navigate to page 1 first
    go_to_first_page(page)

    current_page, total_pages = get_page_info(page)
    scrape_pages = min(total_pages, max_pages) if max_pages else total_pages
    if max_pages and max_pages < total_pages:
        print(f"  [*] {total_pages} page(s) total, scraping first {scrape_pages}")
    else:
        print(f"  [*] {total_pages} page(s) of memories")

    # For large exports, save incrementally every 50 pages
    save_every = 50

    for pg in range(1, scrape_pages + 1):
        if pg > 1:
            if not click_next_page(page):
                print(f"  [!] Could not go to page {pg}, retrying...")
                time.sleep(3)
                if not click_next_page(page):
                    print(f"  [!] Failed to go to page {pg}. Saving what we have.")
                    break
            if slow:
                time.sleep(page_wait)

        page_memories = scrape_current_page_memories(page)
        count = len(page_memories)
        pct = int(pg / scrape_pages * 100)
        print(f"  [*] Page {pg}/{total_pages} ({pct}%): {count} memories", end="")
        all_memories.extend(page_memories)
        print(f"  [total: {len(all_memories)}]")

        # Incremental save for large exports
        if shape_name and output_dir and scrape_pages > 10 and pg % save_every == 0:
            _save_progress(all_memories, shape_name, output_dir)
            print(f"  [*] Progress saved ({len(all_memories)} memories so far)")

    return all_memories


def _save_progress(memories, shape_name, output_dir):
    """Save partial progress to a temp file."""
    os.makedirs(output_dir, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in shape_name).strip()
    path = os.path.join(output_dir, f"{safe_name}_progress.json")
    seen = set()
    unique = []
    for m in memories:
        key = m.get("content", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(m)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"shape": shape_name, "count": len(unique), "memories": unique}, f, indent=2, ensure_ascii=False)


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


def make_launch_kwargs(browser_path, use_firefox=False):
    """Common kwargs for launching the browser."""
    kwargs = {
        "headless": False,
        "viewport": {"width": 1280, "height": 900},
    }
    if not use_firefox:
        kwargs["args"] = ["--disable-blink-features=AutomationControlled"]
        kwargs["user_agent"] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    if browser_path:
        kwargs["executable_path"] = browser_path
    return kwargs


def _launch_browser(p, profile, browser_path, use_firefox=False):
    """Launch browser with persistent context. Returns (context, page)."""
    kwargs = make_launch_kwargs(browser_path, use_firefox)
    if use_firefox:
        ctx = p.firefox.launch_persistent_context(profile, **kwargs)
    else:
        ctx = p.chromium.launch_persistent_context(profile, **kwargs)
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, pg


def do_login(p, profile, browser_path, use_firefox=False):
    """Handle the login flow. Returns True if login succeeded."""
    print("\n" + "=" * 50)
    print("  Step 1: Log in to Shapes.inc")
    print("=" * 50)
    print()
    print("  A browser window will open.")
    print("  Log in with your Shapes.inc account (Google, email, etc.)")
    print("  The script will detect when you're done.")
    print()

    os.makedirs(profile, exist_ok=True)
    ctx, pg = _launch_browser(p, profile, browser_path, use_firefox)
    pg.goto("https://talk.shapes.inc/login", timeout=60000)

    print("  [*] Waiting for you to log in...")
    logged_in = False
    for _ in range(600):  # 10 min max
        time.sleep(1)
        try:
            url = pg.url
            if "/login" not in url and "auth." not in url:
                logged_in = True
                break
        except Exception:
            break

    if not logged_in:
        print("  [!] Login timed out or failed.")
        ctx.close()
        return False

    print("  [+] Login successful!")
    print("  [*] Syncing session with shapes.inc...")
    # Navigate to shapes.inc pages to ensure cookies are set for that domain
    for sync_url in ["https://shapes.inc", "https://shapes.inc/dashboard"]:
        try:
            pg.goto(sync_url, timeout=30000)
            time.sleep(4)
        except Exception:
            pass
    # Verify we can actually access a dashboard page
    body = pg.inner_text("body")
    if "My Shapes" in body or "Create Shape" in body:
        print("  [+] Session verified!")
    else:
        print("  [!] Warning: session may not be fully synced.")
        print("  [!] If export fails, try running the script again.")
    ctx.close()
    return True


def is_logged_in(p, profile, browser_path, use_firefox=False):
    """Quick check if we have a valid session."""
    if not os.path.exists(profile):
        return False
    try:
        ctx, pg = _launch_browser(p, profile, browser_path, use_firefox)
        pg.goto("https://shapes.inc/dashboard", timeout=30000)
        time.sleep(6)
        body = pg.inner_text("body")
        url = pg.url
        # Must see dashboard content AND not be on a login/auth page
        logged = ("My Shapes" in body or "Create Shape" in body) and "/login" not in url and "auth." not in url
        ctx.close()
        return logged
    except Exception:
        try:
            ctx.close()
        except Exception:
            pass
        return False


def export_shape(page, url, output_dir, debug=False, max_pages=None, slow=False):
    """Export memories from a single shape URL. Returns count exported."""
    memory_url = url_to_memory_url(url)
    shape_name = url_to_shape_name(url)

    wait_nav = 10 if slow else 5
    wait_render = 6 if slow else 3
    timeout = 120000 if slow else 60000

    print(f"\n  [*] Shape: {shape_name}")
    print(f"  [*] URL:   {memory_url}")
    print(f"  [*] Navigating...")

    page.goto(memory_url, timeout=timeout)
    time.sleep(wait_nav)

    # Wait for memory content to render (React SPA)
    try:
        page.wait_for_selector("text=User Memory", timeout=timeout)
    except Exception:
        pass
    time.sleep(wait_render)

    # Check if we landed on the actual memory page (not just the public profile)
    body = page.inner_text("body")
    is_memory_page = "User Memory" in body and ("Page" in body or "SELECT ALL" in body or "Add New Memory" in body)
    if not is_memory_page:
        print("  [!] Doesn't look like a memory page.")
        if "Log in" in body or "Sign up" in body:
            print("  [!] You're not logged in. Run the script again to re-login.")
        else:
            print("  [!] You might not have access to this shape's memories.")
        if debug:
            debug_path = os.path.join(output_dir, f"{shape_name}_debug.html")
            os.makedirs(output_dir, exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"  [*] Debug HTML saved: {debug_path}")
        return 0

    print("  [+] Memory page loaded!")

    # Scrape all pages
    memories = scrape_all_memory_pages(page, shape_name=shape_name, output_dir=output_dir, max_pages=max_pages, slow=slow)

    if memories:
        json_path, txt_path, count = export_memories(memories, shape_name, output_dir)
        print(f"\n  [+] Exported {count} memories!")
        print(f"      JSON: {json_path}")
        print(f"      TXT:  {txt_path}")
        return count
    else:
        print("\n  [!] No memories found on this page.")
        if debug:
            debug_path = os.path.join(output_dir, f"{shape_name}_debug.html")
            os.makedirs(output_dir, exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"  [*] Debug HTML saved: {debug_path}")
        return 0


def interactive_flow(args):
    """Guided interactive mode — walks the user through everything."""
    profile = args.profile or DEFAULT_PROFILE_DIR
    use_firefox = getattr(args, 'firefox', False)
    browser_path = args.browser_path or (None if use_firefox else find_browser())
    max_pages = getattr(args, 'pages', None)
    slow = getattr(args, 'slow', False)

    print()
    print("=" * 50)
    print("  Shapes.inc Memory Exporter")
    print("=" * 50)

    # --- Interactive options (only if not already set via CLI flags) ---
    if not args.urls and not use_firefox and not slow and max_pages is None:
        print()
        print("  Options (just press Enter to skip):")
        print()

        # Browser choice
        browser_choice = input("  Use Firefox instead of Chrome? (y/N): ").strip().lower()
        if browser_choice in ("y", "yes"):
            use_firefox = True
        print()

        # Slow mode
        slow_choice = input("  Slow mode? Recommended for shapes with lots of memories (y/N): ").strip().lower()
        if slow_choice in ("y", "yes"):
            slow = True
        print()

        # Page limit
        pages_input = input("  Max pages to scrape? (Enter = all, or type a number): ").strip()
        if pages_input.isdigit() and int(pages_input) > 0:
            max_pages = int(pages_input)
        print()

    if use_firefox:
        profile = profile + "-firefox"

    if use_firefox:
        print("  [*] Using Firefox")
    if slow:
        print("  [*] Slow mode ON")
    if max_pages:
        print(f"  [*] Scraping first {max_pages} page(s) only")

    if not use_firefox and not browser_path:
        print("\n  [!] Could not find Chromium or Google Chrome.")
        print("  [!] Install one, use --browser-path, or try Firefox")
        sys.exit(1)

    # --- Step 1: Check login ---
    print("\n  [*] Checking if you're already logged in...")

    with sync_playwright() as p:
        logged = is_logged_in(p, profile, browser_path, use_firefox)

    if logged:
        print("  [+] You're logged in!")
    else:
        print("  [!] Not logged in yet.")
        with sync_playwright() as p:
            if not do_login(p, profile, browser_path, use_firefox):
                print("\n  [!] Could not log in. Please try again.")
                sys.exit(1)

    # --- Step 2: Get URLs ---
    print("\n" + "=" * 50)
    print("  Step 2: Choose shapes to export")
    print("=" * 50)
    print()
    print("  How to find your memory URL:")
    print("    1. Go to shapes.inc in your browser")
    print("    2. Open your shape's settings")
    print("    3. Click 'Memory' in the sidebar")
    print("    4. Copy the URL from the address bar")
    print()
    print("  It looks like: shapes.inc/your-shape-name/user/memory")
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
        print("  [!] No URLs provided. Nothing to export.")
        sys.exit(0)

    # --- Step 3: Export ---
    print("\n" + "=" * 50)
    print(f"  Step 3: Exporting memories ({len(urls)} shape(s))")
    print("=" * 50)

    with sync_playwright() as p:
        ctx, page = _launch_browser(p, profile, browser_path, use_firefox)

        total_exported = 0
        results = []

        for i, raw_url in enumerate(urls, 1):
            print(f"\n  --- Shape {i}/{len(urls)} ---")
            count = export_shape(page, raw_url, args.output, debug=args.debug, max_pages=max_pages, slow=slow)
            total_exported += count
            results.append((url_to_shape_name(raw_url), count))

        try:
            ctx.close()
        except Exception:
            pass

    # --- Summary ---
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
    parser = argparse.ArgumentParser(
        description="Export memories from Shapes.inc bots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Just run:  %(prog)s
The script will guide you through login and export step by step.

Or pass URLs directly:
  %(prog)s https://shapes.inc/shape1/user/memory https://shapes.inc/shape2/user/memory
        """
    )
    parser.add_argument("urls", nargs="*",
                        help="Memory page URL(s) (optional — you can paste them interactively)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR,
                        help="Output directory (default: exports/)")
    parser.add_argument("--debug", action="store_true",
                        help="Save page HTML for debugging")
    parser.add_argument("--browser-path",
                        help="Path to Chromium/Chrome (auto-detected if not set)")
    parser.add_argument("--profile", default=None,
                        help=f"Browser profile dir (default: {DEFAULT_PROFILE_DIR})")
    parser.add_argument("--firefox", action="store_true",
                        help="Use Firefox instead of Chrome (requires non-Google login)")
    parser.add_argument("--slow", action="store_true",
                        help="Slow mode — longer wait times for large shapes that take time to load")
    parser.add_argument("--pages", type=int, default=None,
                        help="Only scrape first N pages (useful for very large shapes)")
    args = parser.parse_args()

    interactive_flow(args)


if __name__ == "__main__":
    main()
