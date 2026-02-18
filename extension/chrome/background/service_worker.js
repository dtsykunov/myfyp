const APP_NAME = "myfyp";
const DEFAULT_API_BASE_URL = "https://myfyp.link";
const API_BASE_URL_STORAGE_KEY = "myfyp.apiBaseUrl";

const MENU_UPLOAD = "myfyp-upload";
const HOME_PAGE_REQUIRED_ERROR =
  "myfyp works only on YouTube Home. Open https://www.youtube.com/ or https://m.youtube.com/ and stay on the homepage (/).";

function normalizeApiBaseUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
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
  const stored = await chrome.storage.local.get([API_BASE_URL_STORAGE_KEY]);
  const fromStorage = normalizeApiBaseUrl(stored[API_BASE_URL_STORAGE_KEY]);
  return fromStorage || DEFAULT_API_BASE_URL;
}

async function setApiBaseUrl(apiBaseUrl) {
  const normalized = normalizeApiBaseUrl(apiBaseUrl);
  if (!normalized) {
    throw new Error("API base URL cannot be empty.");
  }
  await chrome.storage.local.set({ [API_BASE_URL_STORAGE_KEY]: normalized });
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

async function executeInActiveTab(command, args = null) {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!activeTab || typeof activeTab.id !== "number") {
    return { ok: false, error: "No active tab found." };
  }
  if (!isSupportedYoutubeHomeUrl(activeTab.url)) {
    return { ok: false, error: HOME_PAGE_REQUIRED_ERROR };
  }

  try {
    const result = await chrome.tabs.sendMessage(activeTab.id, {
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
  await chrome.contextMenus.removeAll();
  chrome.contextMenus.create({
    id: MENU_UPLOAD,
    title: "myfyp: Upload Snapshot",
    contexts: ["action"]
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
          sendResponse({
            ok: result.ok,
            apiBaseUrl,
            response: result.response || null,
            error: result.error || null
          });
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
