// Shapes.inc Memory Exporter — Popup Script

const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const exportBtn = document.getElementById("exportBtn");
const downloadsEl = document.getElementById("downloads");
const dlJsonBtn = document.getElementById("dlJson");
const dlTxtBtn = document.getElementById("dlTxt");

let exportData = { json: null, txt: null, shapeName: "" };

function setStatus(text, type) {
  statusEl.textContent = text;
  statusEl.className = "status-box" + (type ? " " + type : "");
}

function addLog(text, cls) {
  const div = document.createElement("div");
  div.textContent = text;
  if (cls) div.className = cls;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Listen for progress/done messages from content script
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "progress") {
    addLog(msg.text, "ok");
  }
  if (msg.action === "done") {
    if (msg.count > 0) {
      setStatus(`Exported ${msg.count} memories!`, "success");
      addLog(`Done! ${msg.count} unique memories.`, "ok");
      exportData.json = msg.json;
      exportData.txt = msg.txt;
      exportData.shapeName = msg.shapeName;
      downloadsEl.classList.add("show");
      exportBtn.disabled = true;
      exportBtn.textContent = "Export Memories";
    } else {
      setStatus("No memories found on this page.", "error");
      addLog("The page loaded but no memory entries were found.", "warn");
      exportBtn.disabled = false;
      exportBtn.textContent = "Export Memories";
    }
  }
});

// Check if we're on a memory page
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const tab = tabs[0];
  if (!tab) {
    setStatus("No active tab found.", "error");
    return;
  }

  const url = tab.url || "";
  if (!url.includes("shapes.inc")) {
    setStatus("Not on shapes.inc", "error");
    addLog("Go to shapes.inc/your-shape/user/memory first.", "warn");
    return;
  }

  // Ask content script to check the page
  chrome.tabs.sendMessage(tab.id, { action: "check" }, (response) => {
    if (chrome.runtime.lastError) {
      setStatus("Can't access this page.", "error");
      addLog("Try refreshing the page and reopening the extension.", "warn");
      return;
    }

    if (!response) {
      setStatus("No response from page.", "error");
      return;
    }

    if (response.isMemoryPage) {
      setStatus(`Ready to export: ${response.shapeName}`, "success");
      addLog(`Shape: ${response.shapeName}`);
      addLog(`Page ${response.pageInfo.current} of ${response.pageInfo.total}`);
      exportBtn.disabled = false;
    } else {
      if (url.includes("/user/memory")) {
        setStatus("Memory page detected but not loaded yet.", "error");
        addLog("Make sure you're logged in and the page has fully loaded.", "warn");
        addLog("Try refreshing the page.", "warn");
      } else {
        setStatus("Not on a memory page.", "error");
        addLog(`Current URL: ${url}`, "warn");
        addLog("Go to: shapes.inc/your-shape/user/memory", "warn");
      }
    }
  });
});

// Export button
exportBtn.addEventListener("click", () => {
  exportBtn.disabled = true;
  exportBtn.innerHTML = '<span class="spinner"></span> Exporting...';
  setStatus("Scraping memories...", "");
  logEl.innerHTML = "";

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    chrome.tabs.sendMessage(tabs[0].id, { action: "scrape" });
  });
});

// Download buttons
dlJsonBtn.addEventListener("click", () => {
  if (exportData.json) {
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    downloadFile(exportData.json, `${exportData.shapeName}_${ts}.json`, "application/json");
  }
});

dlTxtBtn.addEventListener("click", () => {
  if (exportData.txt) {
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    downloadFile(exportData.txt, `${exportData.shapeName}_${ts}.txt`, "text/plain");
  }
});
