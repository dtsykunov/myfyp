const uploadButton = document.getElementById("upload-button");
const historyButton = document.getElementById("history-button");
const saveUrlButton = document.getElementById("save-url-button");
const resetUrlButton = document.getElementById("reset-url-button");
const apiBaseUrlInput = document.getElementById("api-base-url");
const statusElement = document.getElementById("status");

const DEFAULT_API_BASE_URL = "https://myfyp.link";

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

async function executeActiveTabCommand(command) {
  const result = await runtimeSendMessage({
    type: "myfyp.executeActiveTabCommand",
    command
  });

  if (!result || result.ok !== true) {
    throw new Error((result && result.error) || "Unable to execute command in active tab.");
  }

  return result;
}

async function loadApiBaseUrl() {
  const result = await runtimeSendMessage({ type: "myfyp.getApiBaseUrl" });
  if (!result || result.ok !== true) {
    throw new Error((result && result.error) || "Failed to load API base URL.");
  }
  apiBaseUrlInput.value = result.apiBaseUrl || DEFAULT_API_BASE_URL;
}

async function saveApiBaseUrl(value) {
  const result = await runtimeSendMessage({
    type: "myfyp.setApiBaseUrl",
    apiBaseUrl: value
  });
  if (!result || result.ok !== true) {
    throw new Error((result && result.error) || "Failed to save API base URL.");
  }
  apiBaseUrlInput.value = result.apiBaseUrl || DEFAULT_API_BASE_URL;
}

uploadButton.addEventListener("click", async () => {
  setStatus("Uploading snapshot…");
  try {
    await executeActiveTabCommand("upload");
    setStatus("Upload command sent. Check YouTube page toast.", "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Upload command failed.", "error");
  }
});

historyButton.addEventListener("click", async () => {
  setStatus("Loading history…");
  try {
    await executeActiveTabCommand("showHistory");
    setStatus("History command sent. Check YouTube page toast.", "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "History command failed.", "error");
  }
});

saveUrlButton.addEventListener("click", async () => {
  setStatus("Saving API base URL…");
  try {
    await saveApiBaseUrl(apiBaseUrlInput.value);
    setStatus("API base URL saved.", "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Failed to save API URL.", "error");
  }
});

resetUrlButton.addEventListener("click", async () => {
  setStatus("Resetting API base URL…");
  try {
    await saveApiBaseUrl(DEFAULT_API_BASE_URL);
    setStatus("API base URL reset to default.", "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Failed to reset API URL.", "error");
  }
});

(async () => {
  try {
    await loadApiBaseUrl();
    setStatus("Ready.");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Failed to initialize popup.", "error");
  }
})();
