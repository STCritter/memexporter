// Shapes.inc Memory Exporter — Content Script
// Runs on shapes.inc pages. Listens for messages from the popup to scrape memories.

function scrapeCurrentPageMemories() {
  const results = [];
  const cards = document.querySelectorAll('[class*="cardPreview"]');
  for (const card of cards) {
    const label = card.querySelector("label");
    const contentEl = card.querySelector('[class*="result__"]');
    const dateEl = card.querySelector('[class*="date__"] span');

    if (!contentEl) continue;
    const content = contentEl.textContent.trim();
    if (!content) continue;

    const memType = label ? label.textContent.trim().toLowerCase() : "unknown";
    const date = dateEl ? dateEl.textContent.trim() : "";

    results.push({
      type: memType.replace(" memory", ""),
      content: content,
      date: date,
    });
  }

  // Fallback: text-based matching
  if (results.length === 0) {
    const allEls = document.querySelectorAll("*");
    for (const el of allEls) {
      const text = (el.textContent || "").toLowerCase();
      if (
        (text.includes("automatic memory") || text.includes("manual memory")) &&
        el.children.length > 0 &&
        text.length < 2000
      ) {
        if (el.querySelector('[type="checkbox"]')) {
          const dateMatch = el.textContent.match(/(\d{1,2}\/\d{1,2}\/\d{4})/);
          let content = el.textContent.trim();
          content = content.replace(/automatic memory/gi, "");
          content = content.replace(/manual memory/gi, "");
          content = content.replace(/select all\s*\(\d+\)/gi, "");
          content = content.replace(/page\s+\d+\s+of\s+\d+/gi, "");
          if (dateMatch) content = content.replace(dateMatch[1], "");
          content = content.trim();
          if (content.length > 5) {
            results.push({
              type: text.includes("automatic") ? "automatic" : "manual",
              content: content,
              date: dateMatch ? dateMatch[1] : "",
            });
          }
        }
      }
    }
  }

  return results;
}

function getPageInfo() {
  const body = document.body.innerText;
  const match = body.match(/Page\s+(\d+)\s+of\s+(\d+)/);
  if (match) {
    return { current: parseInt(match[1]), total: parseInt(match[2]) };
  }
  return { current: 1, total: 1 };
}

function clickNextPage() {
  return new Promise((resolve) => {
    // Try chevron/arrow buttons
    const buttons = document.querySelectorAll("button");
    for (const btn of buttons) {
      try {
        const inner = btn.innerHTML;
        const text = btn.innerText.trim();
        if (
          inner.includes("chevron-right") ||
          inner.includes("arrow-right") ||
          inner.includes("ChevronRight") ||
          text === "\u2192" ||
          text === "\u203a" ||
          text === ">"
        ) {
          if (btn.offsetParent !== null && !btn.disabled) {
            btn.click();
            setTimeout(() => resolve(true), 2500);
            return;
          }
        }
      } catch (e) {
        continue;
      }
    }

    // Fallback: find buttons near "Page X of Y"
    const allEls = document.querySelectorAll("*");
    for (const el of allEls) {
      if (/Page\s+\d+\s+of\s+\d+/.test(el.textContent) && el.children.length < 10) {
        const btns = el.querySelectorAll("button");
        if (btns.length >= 2) {
          btns[btns.length - 1].click();
          setTimeout(() => resolve(true), 2500);
          return;
        }
      }
    }

    resolve(false);
  });
}

function isMemoryPage() {
  const body = document.body.innerText;
  return (
    body.includes("User Memory") &&
    (body.includes("Page") || body.includes("SELECT ALL") || body.includes("Add New Memory"))
  );
}

function getShapeName() {
  const match = window.location.pathname.match(/\/([^/]+)/);
  return match ? match[1] : "unknown_shape";
}

async function scrapeAllPages(sendProgress) {
  const allMemories = [];
  const { total } = getPageInfo();

  sendProgress(`Found ${total} page(s) of memories`);

  for (let pg = 1; pg <= total; pg++) {
    if (pg > 1) {
      const clicked = await clickNextPage();
      if (!clicked) {
        sendProgress(`Could not navigate to page ${pg}`);
        break;
      }
      // Wait for page content to update
      await new Promise((r) => setTimeout(r, 2000));
    }

    const memories = scrapeCurrentPageMemories();
    sendProgress(`Page ${pg}/${total}: ${memories.length} memories`);
    allMemories.push(...memories);
  }

  return allMemories;
}

function deduplicateMemories(memories) {
  const seen = new Set();
  return memories.filter((m) => {
    if (seen.has(m.content)) return false;
    seen.add(m.content);
    return true;
  });
}

function memoriesToJSON(memories, shapeName) {
  return JSON.stringify(
    {
      shape: shapeName,
      exported_at: new Date().toISOString(),
      count: memories.length,
      memories: memories,
    },
    null,
    2
  );
}

function memoriesToTXT(memories, shapeName) {
  let txt = `Memories for: ${shapeName}\n`;
  txt += `Exported: ${new Date().toISOString()}\n`;
  txt += `Total: ${memories.length}\n`;
  txt += "=".repeat(60) + "\n\n";
  memories.forEach((m, i) => {
    const type = (m.type || "unknown").toUpperCase();
    const date = m.date || "";
    txt += `--- Memory #${i + 1} [${type}] ${date} ---\n`;
    txt += (m.content || "(empty)") + "\n\n";
  });
  return txt;
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "check") {
    sendResponse({
      isMemoryPage: isMemoryPage(),
      shapeName: getShapeName(),
      pageInfo: getPageInfo(),
      url: window.location.href,
    });
    return true;
  }

  if (msg.action === "scrape") {
    const shapeName = getShapeName();

    // Use a port for streaming progress
    scrapeAllPages((progress) => {
      chrome.runtime.sendMessage({ action: "progress", text: progress });
    }).then((allMemories) => {
      const unique = deduplicateMemories(allMemories);
      const jsonStr = memoriesToJSON(unique, shapeName);
      const txtStr = memoriesToTXT(unique, shapeName);

      chrome.runtime.sendMessage({
        action: "done",
        count: unique.length,
        shapeName: shapeName,
        json: jsonStr,
        txt: txtStr,
      });
    });

    sendResponse({ started: true });
    return true;
  }
});
