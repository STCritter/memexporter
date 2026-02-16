#!/usr/bin/env python3
"""
Shapes.inc Memory Exporter
Exports long-term memories from your Shapes.inc bots.

Shapes.inc is a React SPA that loads memories via internal API calls.
This script uses Playwright to automate a real browser session, log in
via Discord OAuth, navigate to the memories section, and intercept
the network responses that contain the actual memory data.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
except ImportError:
    print("ERROR: Playwright is not installed.")
    print("Run: pip install playwright && playwright install chromium")
    sys.exit(1)


SHAPES_BASE = "https://shapes.inc"
SHAPES_DASHBOARD = f"{SHAPES_BASE}/dashboard"
DEFAULT_OUTPUT_DIR = "exports"


def wait_for_login(page, timeout=300):
    """Wait for the user to complete Discord OAuth login."""
    print("\n[*] Waiting for login... (you have 5 minutes)")
    print("[*] If a Discord login page appears, log in with your account.")
    print("[*] The script will continue automatically once you're logged in.\n")

    start = time.time()
    while time.time() - start < timeout:
        url = page.url
        if "/dashboard" in url or "shapes.inc" in url:
            # Check if we're actually logged in by looking for dashboard elements
            try:
                page.wait_for_selector(
                    'a[href*="/dashboard"], [class*="avatar"], [class*="user"], [class*="profile"]',
                    timeout=3000
                )
                return True
            except PwTimeout:
                pass
        time.sleep(2)

    return False


def get_shapes_list(page):
    """Get list of all shapes owned by the user from the dashboard."""
    print("[*] Navigating to dashboard...")
    page.goto(SHAPES_DASHBOARD, wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # Try to find shape links/cards on the dashboard
    shapes = []

    # Look for links that point to shape profiles or dashboard pages
    links = page.query_selector_all('a[href*="/dashboard/"]')
    for link in links:
        href = link.get_attribute("href") or ""
        name = link.inner_text().strip()
        if href and name and "/dashboard/" in href:
            shape_id = href.split("/dashboard/")[-1].split("/")[0].split("?")[0]
            if shape_id and shape_id not in [s["id"] for s in shapes]:
                shapes.append({"id": shape_id, "name": name, "url": href})

    # Also try looking for shape cards with data attributes
    if not shapes:
        cards = page.query_selector_all('[data-shape-id], [data-id]')
        for card in cards:
            shape_id = card.get_attribute("data-shape-id") or card.get_attribute("data-id")
            name = card.inner_text().strip().split("\n")[0]
            if shape_id:
                shapes.append({
                    "id": shape_id,
                    "name": name,
                    "url": f"{SHAPES_BASE}/dashboard/{shape_id}"
                })

    return shapes


def intercept_api_calls(page):
    """Set up request interception to capture ALL API/fetch responses.
    We cast a wide net here and filter later."""
    captured = {"responses": [], "requests": []}

    def handle_response(response):
        url = response.url
        # Skip static assets
        if any(url.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".svg", ".ico", ".woff", ".woff2", ".ttf")):
            return
        # Skip known non-data URLs
        if any(skip in url for skip in ("google", "analytics", "sentry", "hotjar", "facebook", "cdn.")):
            return
        try:
            if response.status == 200:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or "text" in content_type:
                    body = response.text()
                    captured["requests"].append(url)
                    try:
                        data = json.loads(body)
                    except (json.JSONDecodeError, ValueError):
                        data = None
                    captured["responses"].append({
                        "url": url,
                        "status": response.status,
                        "data": data,
                        "body_preview": body[:500] if data is None else None,
                        "body_length": len(body)
                    })
        except Exception:
            pass

    page.on("response", handle_response)
    return captured


def extract_memories_from_responses(captured):
    """Extract actual memory entries from captured API responses.
    Filters out shape metadata, config, and non-memory data."""
    memories = []

    # Shape metadata keys that indicate non-memory data
    shape_meta_keys = {
        "vanity_url", "shape_id", "discord_bot_token", "app_id",
        "server_count", "member_count", "backstory", "personality",
        "initial_message", "system_prompt", "profile_image",
        "banner_image", "display_name", "short_description",
        "long_description", "knowledge_base", "model_config",
        "temperature", "top_p", "max_tokens", "settings",
        "configuration", "engine", "free_will",
    }

    for resp in captured["responses"]:
        data = resp.get("data")
        url = resp.get("url", "")
        if data is None:
            continue

        # Try to find memory arrays in the response
        candidates = []

        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            # Look for common memory container keys
            for key in ("memories", "data", "results", "items", "records",
                        "long_term_memories", "ltm", "memory_list"):
                val = data.get(key)
                if isinstance(val, list) and len(val) > 0:
                    candidates = val
                    break
            # If the dict itself looks like a single memory
            if not candidates and "content" in data and "id" in data:
                candidates = [data]

        for item in candidates:
            if not isinstance(item, dict):
                continue

            # Skip if this looks like shape metadata
            item_keys = set(item.keys())
            if item_keys & shape_meta_keys:
                # If more than 2 metadata keys match, skip it
                if len(item_keys & shape_meta_keys) >= 2:
                    continue

            # Extract memory content from common field names
            content = (
                item.get("content")
                or item.get("text")
                or item.get("memory")
                or item.get("summary")
                or item.get("value")
                or item.get("message")
                or ""
            )

            if not content or not isinstance(content, str):
                continue

            # Skip very short entries (likely labels/IDs)
            if len(content.strip()) < 10:
                continue

            memory_entry = {
                "content": content.strip(),
                "source_url": url,
            }

            # Preserve useful metadata fields
            for field in ("id", "created_at", "updated_at", "timestamp",
                          "user_id", "channel_id", "type", "category",
                          "importance", "score", "tags"):
                if field in item:
                    memory_entry[field] = item[field]

            memories.append(memory_entry)

    return memories


def scrape_memories_from_dom(page):
    """Fallback: try to scrape memory entries from the DOM.
    Only used if network interception found nothing."""
    memories = []

    # Look specifically for memory list containers and their children
    selectors = [
        '[class*="memory-list"] > div',
        '[class*="memoryList"] > div',
        '[class*="memory-item"]',
        '[class*="memoryItem"]',
        '[class*="memory-card"]',
        '[class*="memoryCard"]',
        '[class*="memory-entry"]',
        '[class*="memoryEntry"]',
        '[data-memory-id]',
        '[data-memory]',
    ]

    for selector in selectors:
        try:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"  [+] Found {len(elements)} elements matching '{selector}'")
                for el in elements:
                    text = el.inner_text().strip()
                    # Memory entries are typically 10-3000 chars
                    if text and 10 < len(text) < 3000:
                        memory_id = (
                            el.get_attribute("data-memory-id")
                            or el.get_attribute("data-id")
                            or ""
                        )
                        memories.append({
                            "id": memory_id,
                            "content": text,
                            "source": "dom_scrape",
                        })
        except Exception:
            continue

    return memories


def scroll_to_load_all(page, max_scrolls=50):
    """Scroll down to load all memories if the page uses infinite scroll."""
    print("  [*] Scrolling to load all memories...")
    prev_height = 0
    stable_count = 0

    for i in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)

        # Check for "load more" buttons
        load_more = page.query_selector(
            'button:has-text("Load More"), button:has-text("Show More"), '
            'button:has-text("load more"), [class*="load-more"], [class*="loadMore"]'
        )
        if load_more:
            try:
                load_more.click()
                time.sleep(2)
            except Exception:
                pass

        curr_height = page.evaluate("document.body.scrollHeight")
        if curr_height == prev_height:
            stable_count += 1
            if stable_count >= 3:
                break
        else:
            stable_count = 0
        prev_height = curr_height

    print(f"  [*] Scrolling complete after {i + 1} iterations")


def navigate_to_memories(page, shape_url):
    """Navigate to a shape's memory page."""
    # Try common memory page URL patterns
    patterns = [
        f"{shape_url}/memories",
        f"{shape_url}?tab=memories",
        f"{shape_url}#memories",
        f"{shape_url}/memory",
    ]

    for url in patterns:
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(2)

            # Check if we landed on a memories page
            content = page.content().lower()
            if "memory" in content or "memories" in content:
                # Try clicking a memories tab if it exists
                tabs = page.query_selector_all(
                    'a:has-text("Memories"), button:has-text("Memories"), '
                    '[class*="tab"]:has-text("Memories"), '
                    'a:has-text("Memory"), button:has-text("Memory")'
                )
                for tab in tabs:
                    try:
                        tab.click()
                        time.sleep(2)
                        return True
                    except Exception:
                        continue
                return True
        except Exception:
            continue

    # Last resort: go to shape URL and look for memory tab
    try:
        page.goto(shape_url, wait_until="networkidle", timeout=15000)
        time.sleep(2)
        tabs = page.query_selector_all(
            'a:has-text("Memories"), button:has-text("Memories"), '
            'a:has-text("Memory"), button:has-text("Memory"), '
            '[role="tab"]:has-text("Memor")'
        )
        for tab in tabs:
            try:
                tab.click()
                time.sleep(2)
                return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def export_memories(memories, shape_name, output_dir):
    """Export memories to JSON and TXT files."""
    os.makedirs(output_dir, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in shape_name).strip()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Deduplicate
    seen = set()
    unique = []
    for m in memories:
        key = m.get("content", "")
        if key not in seen:
            seen.add(key)
            unique.append(m)

    # JSON export
    json_path = os.path.join(output_dir, f"{safe_name}_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "shape": shape_name,
            "exported_at": datetime.now().isoformat(),
            "count": len(unique),
            "memories": unique
        }, f, indent=2, ensure_ascii=False)

    # TXT export (human-readable)
    txt_path = os.path.join(output_dir, f"{safe_name}_{timestamp}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Memories for: {shape_name}\n")
        f.write(f"Exported: {datetime.now().isoformat()}\n")
        f.write(f"Total: {len(unique)}\n")
        f.write("=" * 60 + "\n\n")
        for i, m in enumerate(unique, 1):
            f.write(f"--- Memory #{i} ---\n")
            f.write(m.get("content", "(empty)") + "\n\n")

    return json_path, txt_path, len(unique)


def main():
    parser = argparse.ArgumentParser(
        description="Export memories from Shapes.inc bots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Interactive: lists your shapes, pick one
  %(prog)s --shape-url URL          # Export from a specific shape dashboard URL
  %(prog)s --all                    # Export memories from ALL your shapes
  %(prog)s --output ./my_exports    # Custom output directory
  %(prog)s --headed                 # Show the browser window (useful for debugging)
        """
    )
    parser.add_argument("--shape-url", help="Direct URL to a shape's dashboard page")
    parser.add_argument("--all", action="store_true", help="Export from all shapes")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output directory (default: exports/)")
    parser.add_argument("--headed", action="store_true", help="Show browser window (default: headless after login)")
    parser.add_argument("--timeout", type=int, default=300, help="Login timeout in seconds (default: 300)")
    parser.add_argument("--debug", action="store_true", help="Dump all captured API responses to a debug file")
    args = parser.parse_args()

    print("=" * 50)
    print("  Shapes.inc Memory Exporter")
    print("=" * 50)

    with sync_playwright() as p:
        # Always start headed so user can log in
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        # Block DevTools detection scripts
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()

        # Set up API interception
        captured = intercept_api_calls(page)

        # Navigate to shapes.inc to trigger login
        print("\n[*] Opening shapes.inc...")
        page.goto(SHAPES_BASE, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Check if already logged in, if not trigger login
        try:
            login_btn = page.query_selector(
                'a:has-text("Login"), button:has-text("Login"), '
                'a:has-text("Sign in"), button:has-text("Sign in"), '
                'a:has-text("Log in"), button:has-text("Log in"), '
                'a[href*="auth"], a[href*="login"], a[href*="discord"]'
            )
            if login_btn:
                print("[*] Found login button, clicking...")
                login_btn.click()
                time.sleep(3)
        except Exception:
            pass

        # Wait for user to complete login
        if not wait_for_login(page, timeout=args.timeout):
            print("\n[!] Login timed out. Please try again.")
            browser.close()
            sys.exit(1)

        print("[+] Login detected!")
        time.sleep(2)

        # Determine which shapes to export
        targets = []

        if args.shape_url:
            targets.append({"id": "custom", "name": "custom_shape", "url": args.shape_url})
        else:
            print("\n[*] Fetching your shapes...")
            shapes = get_shapes_list(page)

            if not shapes:
                print("[!] Could not auto-detect shapes from dashboard.")
                print("[*] Please enter the shape dashboard URL manually.")
                url = input("    Shape URL: ").strip()
                if url:
                    name = input("    Shape name: ").strip() or "unknown_shape"
                    targets.append({"id": "manual", "name": name, "url": url})
                else:
                    print("[!] No URL provided. Exiting.")
                    browser.close()
                    sys.exit(1)
            elif args.all:
                targets = shapes
                print(f"[+] Found {len(shapes)} shapes. Exporting all.")
            else:
                print(f"\n[+] Found {len(shapes)} shapes:")
                for i, s in enumerate(shapes, 1):
                    print(f"    {i}. {s['name']} ({s['id']})")
                print(f"    {len(shapes) + 1}. Export ALL")

                choice = input("\n    Pick a number: ").strip()
                try:
                    idx = int(choice)
                    if idx == len(shapes) + 1:
                        targets = shapes
                    elif 1 <= idx <= len(shapes):
                        targets = [shapes[idx - 1]]
                    else:
                        print("[!] Invalid choice.")
                        browser.close()
                        sys.exit(1)
                except ValueError:
                    print("[!] Invalid input.")
                    browser.close()
                    sys.exit(1)

        # Export memories for each target shape
        total_exported = 0

        for shape in targets:
            print(f"\n{'=' * 40}")
            print(f"[*] Processing: {shape['name']}")
            print(f"{'=' * 40}")

            # Navigate to memories page
            if navigate_to_memories(page, shape["url"]):
                print("  [+] Found memories page")
            else:
                print("  [!] Could not find memories page, trying to scrape current page...")

            # Scroll to load all content
            scroll_to_load_all(page)

            # Wait a bit for any final API calls to complete
            time.sleep(3)

            # Primary: extract memories from intercepted API responses
            print(f"  [*] Captured {len(captured['responses'])} API responses")
            if captured['requests']:
                print(f"  [*] API URLs seen:")
                for url in captured['requests']:
                    print(f"      {url[:120]}")

            memories = extract_memories_from_responses(captured)
            print(f"  [*] Extracted {len(memories)} memories from API responses")

            # Debug: dump all captured responses
            if args.debug:
                os.makedirs(args.output, exist_ok=True)
                debug_path = os.path.join(args.output, f"{shape['name']}_api_debug.json")
                # Strip large bodies to keep debug file manageable
                debug_data = []
                for r in captured["responses"]:
                    entry = {"url": r["url"], "status": r["status"], "body_length": r["body_length"]}
                    if r["data"] is not None:
                        entry["data_preview"] = json.dumps(r["data"])[:2000]
                    elif r.get("body_preview"):
                        entry["body_preview"] = r["body_preview"]
                    debug_data.append(entry)
                with open(debug_path, "w", encoding="utf-8") as f:
                    json.dump(debug_data, f, indent=2, ensure_ascii=False)
                print(f"  [*] Debug: saved {len(debug_data)} API responses to {debug_path}")

            # Fallback: try DOM scraping if API interception got nothing
            if not memories:
                print("  [*] No memories from API, trying DOM fallback...")
                memories = scrape_memories_from_dom(page)

            if memories:
                json_path, txt_path, count = export_memories(memories, shape["name"], args.output)
                print(f"\n  [+] Exported {count} memories:")
                print(f"      JSON: {json_path}")
                print(f"      TXT:  {txt_path}")
                total_exported += count
            else:
                print("\n  [!] No memories found for this shape.")
                # Save page HTML for debugging
                debug_path = os.path.join(args.output, f"{shape['name']}_debug.html")
                os.makedirs(args.output, exist_ok=True)
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"  [*] Saved page HTML for debugging: {debug_path}")
                print("  [*] Please open an issue with this file if you need help.")

        print(f"\n{'=' * 50}")
        print(f"  Done! Exported {total_exported} total memories.")
        print(f"  Output directory: {os.path.abspath(args.output)}")
        print(f"{'=' * 50}")

        browser.close()


if __name__ == "__main__":
    main()
