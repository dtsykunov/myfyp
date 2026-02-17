// ==UserScript==
// @name         For Us Page (MVP Scaffold)
// @namespace    https://for-us-page.local
// @version      0.1.4
// @description  MVP scaffold for sharing YouTube recommendation pages
// @match        https://www.youtube.com/*
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @connect      *
// ==/UserScript==

(function () {
  "use strict";

  const APP_NAME = "For Us Page";
  const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;
  const API_BASE_URL_STORAGE_KEY = "forUsPage.apiBaseUrl";
  const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
  const pageWindow = typeof unsafeWindow !== "undefined" ? unsafeWindow : window;

  function extractVideoHashFromHref(href, baseUrl) {
    if (!href) {
      return null;
    }

    let url;
    try {
      url = new URL(href, baseUrl);
    } catch {
      return null;
    }

    if (url.pathname === "/watch") {
      const videoHash = url.searchParams.get("v");
      return videoHash && VIDEO_ID_PATTERN.test(videoHash) ? videoHash : null;
    }

    if (url.pathname.startsWith("/shorts/")) {
      const videoHash = url.pathname.split("/")[2] || "";
      return VIDEO_ID_PATTERN.test(videoHash) ? videoHash : null;
    }

    return null;
  }

  function collectVideoHashesFromDocument(doc) {
    const items = doc.querySelectorAll("ytd-rich-item-renderer");
    const videos = [];
    const shorts = [];
    const seenVideos = new Set();
    const seenShorts = new Set();

    for (const item of items) {
      const isShortsItem = Boolean(item.closest("ytd-rich-section-renderer"));
      const links = item.querySelectorAll("a[href]");

      for (const link of links) {
        const videoHash = extractVideoHashFromHref(
          link.getAttribute("href"),
          window.location.origin
        );
        if (!videoHash) {
          continue;
        }

        if (isShortsItem) {
          if (seenShorts.has(videoHash)) {
            continue;
          }
          seenShorts.add(videoHash);
          shorts.push(videoHash);
          continue;
        }

        if (seenVideos.has(videoHash)) {
          continue;
        }
        seenVideos.add(videoHash);
        videos.push(videoHash);
      }
    }

    return { videos, shorts };
  }

  function createRecommendationSnapshot(doc = document) {
    const collections = collectVideoHashesFromDocument(doc);
    return {
      capturedAt: new Date().toISOString(),
      pageUrl: window.location.href,
      videos: collections.videos,
      shorts: collections.shorts,
    };
  }

  function logSnapshot() {
    const snapshot = createRecommendationSnapshot();
    console.info(
      `[${APP_NAME}] Parsed ${snapshot.videos.length} videos and ${snapshot.shorts.length} shorts.`
    );
    console.debug(`[${APP_NAME}] Snapshot JSON:`, snapshot);
    return snapshot;
  }

  function normalizeApiBaseUrl(url) {
    return String(url || "").trim().replace(/\/+$/, "");
  }

  function getApiBaseUrl() {
    const fromStorage = pageWindow.localStorage.getItem(API_BASE_URL_STORAGE_KEY);
    return normalizeApiBaseUrl(fromStorage || DEFAULT_API_BASE_URL);
  }

  function setApiBaseUrl(url) {
    const normalized = normalizeApiBaseUrl(url);
    if (!normalized) {
      throw new Error("API base URL cannot be empty.");
    }
    pageWindow.localStorage.setItem(API_BASE_URL_STORAGE_KEY, normalized);
    return normalized;
  }

  function postSnapshotWithGmRequest(apiBaseUrl, snapshot) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: "POST",
        url: `${apiBaseUrl}/api/snapshots`,
        headers: { "Content-Type": "application/json" },
        data: JSON.stringify(snapshot),
        onload: (response) => {
          if (response.status < 200 || response.status >= 300) {
            reject(
              new Error(
                `API request failed: ${response.status} ${response.statusText}`
              )
            );
            return;
          }
          try {
            resolve(JSON.parse(response.responseText));
          } catch (error) {
            reject(
              new Error(
                `Failed to parse API response: ${
                  error instanceof Error ? error.message : "Unknown error"
                }`
              )
            );
          }
        },
        onerror: () => reject(new Error("API request failed due to network error.")),
      });
    });
  }

  async function postSnapshotWithFetch(apiBaseUrl, snapshot) {
    const response = await fetch(`${apiBaseUrl}/api/snapshots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(snapshot),
    });
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }
    return response.json();
  }

  async function uploadSnapshot(snapshot, apiBaseUrl = getApiBaseUrl()) {
    const normalizedBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
    if (!normalizedBaseUrl) {
      throw new Error("API base URL is empty.");
    }
    if (typeof GM_xmlhttpRequest === "function") {
      return postSnapshotWithGmRequest(normalizedBaseUrl, snapshot);
    }
    return postSnapshotWithFetch(normalizedBaseUrl, snapshot);
  }

  async function uploadLatestSnapshot() {
    const snapshot = logSnapshot();
    if (snapshot.videos.length === 0 && snapshot.shorts.length === 0) {
      console.warn(`[${APP_NAME}] No recommendations found, skipping upload.`);
      return null;
    }
    const apiBaseUrl = getApiBaseUrl();
    try {
      const response = await uploadSnapshot(snapshot, apiBaseUrl);
      console.info(`[${APP_NAME}] Upload response:`, response);
      return response;
    } catch (error) {
      console.error(
        `[${APP_NAME}] Failed to upload snapshot to ${apiBaseUrl}:`,
        error
      );
      return null;
    }
  }

  function registerPublicApi() {
    pageWindow.forUsPage = Object.assign(pageWindow.forUsPage || {}, {
      extractVideoHashFromHref,
      collectVideoHashesFromDocument,
      createRecommendationSnapshot,
      logSnapshot,
      getApiBaseUrl,
      setApiBaseUrl,
      uploadSnapshot,
      uploadLatestSnapshot,
    });
  }

  function bootstrap() {
    registerPublicApi();
    console.info(
      `[${APP_NAME}] Userscript loaded. Run window.forUsPage.uploadLatestSnapshot() to upload and print API response.`
    );
  }

  bootstrap();
})();
