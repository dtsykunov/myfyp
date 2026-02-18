const uploadButton = document.getElementById("upload-button");
const refreshHistoryButton = document.getElementById("refresh-history-button");
const clearHistoryButton = document.getElementById("clear-history-button");
const historyListElement = document.getElementById("history-list");
const statusElement = document.getElementById("status");

function setStatus(message, variant = "") {
  statusElement.textContent = message;
  statusElement.className = "status";
  if (variant) {
    statusElement.classList.add(variant);
  }
}

function runtimeSendMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(response);
    });
  });
}

async function executeActiveTabCommand(command, args = null) {
  const result = await runtimeSendMessage({
    type: "myfyp.executeActiveTabCommand",
    command,
    args
  });

  if (!result || result.ok !== true) {
    throw new Error((result && result.error) || "Unable to execute command in active tab.");
  }

  return result;
}

function formatDate(isoString) {
  if (!isoString) {
    return "Unknown time";
  }
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }
  return date.toLocaleString();
}

function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function renderHistory(entries) {
  clearNode(historyListElement);

  if (!Array.isArray(entries) || entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "history-empty";
    empty.textContent = "No uploaded snapshot links found yet.";
    historyListElement.appendChild(empty);
    return;
  }

  const totalEntries = entries.length;
  for (const [index, entry] of entries.entries()) {
    const row = document.createElement("article");
    row.className = "history-row";

    const meta = document.createElement("div");
    meta.className = "history-row-meta";
    const position = totalEntries - index;
    meta.textContent = `#${position} • ${formatDate(entry.createdAt)}`;
    row.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "history-row-actions";

    if (entry.shareUrl) {
      const shareLink = document.createElement("a");
      shareLink.className = "history-link";
      shareLink.href = entry.shareUrl;
      shareLink.target = "_blank";
      shareLink.rel = "noopener noreferrer";
      shareLink.textContent = "Share";
      actions.appendChild(shareLink);
    }

    if (entry.removeUrl) {
      const removeLink = document.createElement("a");
      removeLink.className = "history-link";
      removeLink.href = entry.removeUrl;
      removeLink.target = "_blank";
      removeLink.rel = "noopener noreferrer";
      removeLink.textContent = "Delete";
      actions.appendChild(removeLink);
    }

    const removeFromListButton = document.createElement("button");
    removeFromListButton.className = "history-remove";
    removeFromListButton.type = "button";
    removeFromListButton.textContent = "Remove from list";
    removeFromListButton.addEventListener("click", async () => {
      try {
        const result = await executeActiveTabCommand("removeHistoryEntry", { entry });
        renderHistory(result.history || []);
        setStatus("Entry removed from list.", "success");
      } catch (error) {
        setStatus(error instanceof Error ? error.message : "Failed to remove entry.", "error");
      }
    });
    actions.appendChild(removeFromListButton);

    row.appendChild(actions);
    historyListElement.appendChild(row);
  }
}

async function refreshHistory() {
  const result = await executeActiveTabCommand("getHistory");
  renderHistory(result.history || []);
}

uploadButton.addEventListener("click", async () => {
  setStatus("Uploading snapshot…");
  try {
    await executeActiveTabCommand("upload");
    await refreshHistory();
    setStatus("Upload finished. Created links are listed below.", "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Upload command failed.", "error");
  }
});

refreshHistoryButton.addEventListener("click", async () => {
  setStatus("Refreshing link list…");
  try {
    await refreshHistory();
    setStatus("Link list refreshed.", "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Failed to refresh link list.", "error");
  }
});

clearHistoryButton.addEventListener("click", async () => {
  setStatus("Clearing link list…");
  try {
    const result = await executeActiveTabCommand("clearHistory");
    renderHistory(result.history || []);
    setStatus("Link list cleared.", "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Failed to clear link list.", "error");
  }
});

(async () => {
  try {
    await refreshHistory();
    setStatus("Ready.");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to initialize popup.";
    setStatus(message, "error");
    renderHistory([]);
  }
})();
