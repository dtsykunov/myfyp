const APP_NAME = "myfyp";
const DEFAULT_API_BASE_URL = "https://myfyp.link";
const API_BASE_URL_STORAGE_KEY = "myfyp.apiBaseUrl";
const LINK_HISTORY_STORAGE_KEY = "myfyp.linkHistory";
const LINK_HISTORY_MAX_ITEMS = 500;

const MENU_UPLOAD = "myfyp-upload";
const ACTION_CONTEXT = "browser_action";
const HOME_PAGE_REQUIRED_ERROR =
  "myfyp works only on YouTube Home. Open https://www.youtube.com/ or https://m.youtube.com/ and stay on the homepage (/).";

function getRuntimeErrorMessage() {
  const runtimeError = chrome.runtime && chrome.runtime.lastError;
  return runtimeError && runtimeError.message ? runtimeError.message : "";
}

function storageGet(keys) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(keys, (items) => {
      const errorMessage = getRuntimeErrorMessage();
      if (errorMessage) {
        reject(new Error(errorMessage));
        return;
      }
      resolve(items || {});
    });
  });
}

function storageSet(items) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set(items, () => {
      const errorMessage = getRuntimeErrorMessage();
      if (errorMessage) {
        reject(new Error(errorMessage));
        return;
      }
      resolve();
    });
  });
}

function queryTabs(queryInfo) {
  return new Promise((resolve, reject) => {
    chrome.tabs.query(queryInfo, (tabs) => {
      const errorMessage = getRuntimeErrorMessage();
      if (errorMessage) {
        reject(new Error(errorMessage));
        return;
      }
      resolve(Array.isArray(tabs) ? tabs : []);
    });
  });
}

function sendMessageToTab(tabId, payload) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, payload, (response) => {
      const errorMessage = getRuntimeErrorMessage();
      if (errorMessage) {
        reject(new Error(errorMessage));
        return;
      }
      resolve(response);
    });
  });
}

function removeAllContextMenus() {
  return new Promise((resolve, reject) => {
    chrome.contextMenus.removeAll(() => {
      const errorMessage = getRuntimeErrorMessage();
      if (errorMessage) {
        reject(new Error(errorMessage));
        return;
      }
      resolve();
    });
  });
}

function normalizeApiBaseUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function normalizeText(value) {
  return String(value || "").trim();
}

function normalizeLinkHistoryEntry(entry) {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const normalized = {
    createdAt: normalizeText(entry.createdAt),
    shareUrl: normalizeText(entry.shareUrl),
    removeUrl: normalizeText(entry.removeUrl),
    hash: normalizeText(entry.hash)
  };
  if (!normalized.createdAt && !normalized.shareUrl && !normalized.removeUrl && !normalized.hash) {
    return null;
  }
  return normalized;
}

function historyTimestampMs(isoString) {
  if (!isoString) {
    return 0;
  }
  const parsedMs = new Date(isoString).getTime();
  return Number.isFinite(parsedMs) ? parsedMs : 0;
}

function isSameLinkHistoryEntry(left, right) {
  return (
    left.createdAt === right.createdAt
    && left.shareUrl === right.shareUrl
    && left.removeUrl === right.removeUrl
    && left.hash === right.hash
  );
}

function getSortedLinkHistory(entries) {
  return entries
    .slice()
    .sort((left, right) => historyTimestampMs(right.createdAt) - historyTimestampMs(left.createdAt));
}

async function getLinkHistory() {
  const stored = await storageGet([LINK_HISTORY_STORAGE_KEY]);
  const rawEntries = stored[LINK_HISTORY_STORAGE_KEY];
  if (!Array.isArray(rawEntries)) {
    return [];
  }
  return getSortedLinkHistory(
    rawEntries
      .map((entry) => normalizeLinkHistoryEntry(entry))
      .filter((entry) => entry !== null)
  );
}

async function setLinkHistory(entries) {
  await storageSet({
    [LINK_HISTORY_STORAGE_KEY]: entries.slice(0, LINK_HISTORY_MAX_ITEMS)
  });
}

async function appendLinkHistoryEntry(entry) {
  const normalizedEntry = normalizeLinkHistoryEntry(entry);
  if (!normalizedEntry) {
    return getLinkHistory();
  }

  const history = await getLinkHistory();
  const deduplicated = history.filter(
    (existing) => !(existing.shareUrl === normalizedEntry.shareUrl && existing.removeUrl === normalizedEntry.removeUrl)
  );
  deduplicated.unshift({
    createdAt: normalizedEntry.createdAt || new Date().toISOString(),
    shareUrl: normalizedEntry.shareUrl,
    removeUrl: normalizedEntry.removeUrl,
    hash: normalizedEntry.hash
  });
  const sorted = getSortedLinkHistory(deduplicated);
  await setLinkHistory(sorted);
  return sorted;
}

async function removeLinkHistoryEntry(entry) {
  const normalizedEntry = normalizeLinkHistoryEntry(entry);
  if (!normalizedEntry) {
    return getLinkHistory();
  }
  const history = await getLinkHistory();
  const filtered = history.filter((existing) => !isSameLinkHistoryEntry(existing, normalizedEntry));
  const sorted = getSortedLinkHistory(filtered);
  await setLinkHistory(sorted);
  return sorted;
}

function buildApiErrorMessage(status, statusText, bodyText) {
  const base = `API request failed: ${status}${statusText ? ` ${statusText}` : ""}`;
  const detail = extractApiErrorDetail(bodyText);
  if (!detail) {
    return base;
  }
  return `${base}. ${detail}`;
}

function extractApiErrorDetail(bodyText) {
  const normalizedBody = String(bodyText || "").trim();
  if (!normalizedBody) {
    return "";
  }
  try {
    const parsed = JSON.parse(normalizedBody);
    if (!parsed || typeof parsed !== "object") {
      return normalizedBody;
    }
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail.trim();
    }
    if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
      return JSON.stringify(parsed.detail);
    }
    return normalizedBody;
  } catch {
    return normalizedBody;
  }
}

async function getApiBaseUrl() {
  const stored = await storageGet([API_BASE_URL_STORAGE_KEY]);
  const fromStorage = normalizeApiBaseUrl(stored[API_BASE_URL_STORAGE_KEY]);
  return fromStorage || DEFAULT_API_BASE_URL;
}

async function setApiBaseUrl(apiBaseUrl) {
  const normalized = normalizeApiBaseUrl(apiBaseUrl);
  if (!normalized) {
    throw new Error("API base URL cannot be empty.");
  }
  await storageSet({ [API_BASE_URL_STORAGE_KEY]: normalized });
  return normalized;
}

async function postSnapshot(snapshot, apiBaseUrl) {
  const normalizedBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
  if (!normalizedBaseUrl) {
    return {
      ok: false,
      error: "API base URL is empty."
    };
  }

  let response;
  try {
    response = await fetch(`${normalizedBaseUrl}/api/snapshots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(snapshot)
    });
  } catch (error) {
    return {
      ok: false,
      error: `API request failed due to network error: ${
        error instanceof Error ? error.message : "Unknown network error"
      }`
    };
  }

  const responseText = await response.text();
  if (!response.ok) {
    return {
      ok: false,
      error: buildApiErrorMessage(response.status, response.statusText, responseText)
    };
  }

  try {
    return {
      ok: true,
      response: JSON.parse(responseText)
    };
  } catch (error) {
    return {
      ok: false,
      error: `Failed to parse API response: ${
        error instanceof Error ? error.message : "Unknown parse error"
      }`
    };
  }
}

function buildSnapshotUrl(apiBaseUrl, response) {
  if (response && typeof response.url === "string" && response.url.trim()) {
    return response.url.trim();
  }
  const snapshotHash = response && typeof response.hash === "string" ? response.hash : "";
  if (!snapshotHash) {
    return "";
  }
  try {
    return new URL(`/${snapshotHash}`, `${apiBaseUrl}/`).toString();
  } catch {
    return "";
  }
}

function buildRemoveUrl(apiBaseUrl, response) {
  if (response && typeof response.removeUrl === "string" && response.removeUrl.trim()) {
    return response.removeUrl.trim();
  }
  const snapshotHash = response && typeof response.hash === "string" ? response.hash : "";
  const removeToken = response && typeof response.removeToken === "string" ? response.removeToken : "";
  if (!snapshotHash || !removeToken) {
    return "";
  }
  try {
    return new URL(
      `/api/snapshots/${encodeURIComponent(snapshotHash)}/remove/${encodeURIComponent(removeToken)}`,
      `${apiBaseUrl}/`
    ).toString();
  } catch {
    return "";
  }
}

async function executeInActiveTab(command, args = null) {
  const tabs = await queryTabs({ active: true, currentWindow: true });
  const activeTab = Array.isArray(tabs) && tabs.length > 0 ? tabs[0] : null;
  if (!activeTab || typeof activeTab.id !== "number") {
    return { ok: false, error: "No active tab found." };
  }
  if (!isSupportedYoutubeHomeUrl(activeTab.url)) {
    return { ok: false, error: HOME_PAGE_REQUIRED_ERROR };
  }

  try {
    const result = await sendMessageToTab(activeTab.id, {
      type: "myfyp.command",
      command,
      args
    });
    if (!result || result.ok !== true) {
      return {
        ok: false,
        error: (result && result.error) || "Unable to execute command in active tab."
      };
    }
    return result;
  } catch (error) {
    if (isReceivingEndMissingError(error)) {
      return { ok: false, error: HOME_PAGE_REQUIRED_ERROR };
    }
    return {
      ok: false,
      error: `Unable to reach YouTube page: ${
        error instanceof Error ? error.message : "Unknown runtime error"
      }`
    };
  }
}

function isSupportedYoutubeHomeUrl(rawUrl) {
  if (typeof rawUrl !== "string" || !rawUrl.trim()) {
    return false;
  }
  try {
    const parsedUrl = new URL(rawUrl);
    const hostname = parsedUrl.hostname.toLowerCase();
    if (hostname !== "www.youtube.com" && hostname !== "m.youtube.com") {
      return false;
    }
    return parsedUrl.pathname === "/";
  } catch {
    return false;
  }
}

function isReceivingEndMissingError(error) {
  if (!(error instanceof Error)) {
    return false;
  }
  return /receiving end does not exist/i.test(error.message);
}

async function createContextMenus() {
  await removeAllContextMenus();
  chrome.contextMenus.create({
    id: MENU_UPLOAD,
    title: "myfyp: Upload Snapshot",
    contexts: [ACTION_CONTEXT]
  });
}

chrome.runtime.onInstalled.addListener(() => {
  void createContextMenus();
});

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === MENU_UPLOAD) {
    void executeInActiveTab("upload");
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  void (async () => {
    try {
      if (!message || typeof message !== "object") {
        sendResponse({ ok: false, error: "Invalid message payload." });
        return;
      }

      switch (message.type) {
        case "myfyp.getApiBaseUrl": {
          const apiBaseUrl = await getApiBaseUrl();
          sendResponse({ ok: true, apiBaseUrl });
          return;
        }
        case "myfyp.setApiBaseUrl": {
          const apiBaseUrl = await setApiBaseUrl(message.apiBaseUrl);
          sendResponse({ ok: true, apiBaseUrl });
          return;
        }
        case "myfyp.uploadSnapshot": {
          const apiBaseUrl = await getApiBaseUrl();
          const result = await postSnapshot(message.snapshot, apiBaseUrl);
          if (result.ok && result.response) {
            const shareUrl = buildSnapshotUrl(apiBaseUrl, result.response);
            const removeUrl = buildRemoveUrl(apiBaseUrl, result.response);
            await appendLinkHistoryEntry({
              createdAt: new Date().toISOString(),
              hash: normalizeText(result.response.hash),
              shareUrl,
              removeUrl
            });
          }
          sendResponse({
            ok: result.ok,
            apiBaseUrl,
            response: result.response || null,
            error: result.error || null
          });
          return;
        }
        case "myfyp.getLinkHistory": {
          const history = await getLinkHistory();
          sendResponse({ ok: true, history });
          return;
        }
        case "myfyp.removeLinkHistoryEntry": {
          const history = await removeLinkHistoryEntry(message.entry);
          sendResponse({ ok: true, history });
          return;
        }
        case "myfyp.executeActiveTabCommand": {
          const result = await executeInActiveTab(message.command, message.args);
          sendResponse(result);
          return;
        }
        default:
          sendResponse({ ok: false, error: `Unknown message type: ${String(message.type)}` });
      }
    } catch (error) {
      sendResponse({
        ok: false,
        error: error instanceof Error ? error.message : "Unexpected background error."
      });
    }
  })();

  return true;
});
