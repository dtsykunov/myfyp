// ==UserScript==
// @name         For Us Page (MVP Scaffold)
// @namespace    https://for-us-page.local
// @version      0.1.5
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
  const RELATIVE_ENGLISH_TIME_PATTERN =
    /^(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago$/i;
  const RELATIVE_SECONDS_BY_UNIT = {
    second: 1,
    minute: 60,
    hour: 3600,
    day: 86400,
    week: 604800,
    month: 2592000,
    year: 31536000,
  };
  const API_BASE_URL_STORAGE_KEY = "forUsPage.apiBaseUrl";
  const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
  const pageWindow = typeof unsafeWindow !== "undefined" ? unsafeWindow : window;

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function toAbsoluteUrl(href, baseUrl) {
    if (!href) {
      return null;
    }
    try {
      return new URL(href, baseUrl).toString();
    } catch {
      return null;
    }
  }

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

  function parseViewCount(text) {
    const normalized = normalizeText(text).toLowerCase();
    if (!normalized) {
      return null;
    }

    let numericPart = normalized.replace(/\bviews?\b/g, "").trim();
    if (!numericPart || /[^0-9kmb.,\s]/i.test(numericPart)) {
      return null;
    }

    const match = numericPart.match(/^([0-9]+(?:[.,][0-9]+)?)\s*([kmb])?$/i);
    if (!match) {
      numericPart = numericPart.replace(/[^\d]/g, "");
      if (!numericPart) {
        return null;
      }
      const parsedInteger = Number.parseInt(numericPart, 10);
      return Number.isNaN(parsedInteger) ? null : parsedInteger;
    }

    const suffix = (match[2] || "").toLowerCase();
    if (!suffix) {
      const parsedInteger = Number.parseInt(match[1].replace(/[^\d]/g, ""), 10);
      return Number.isNaN(parsedInteger) ? null : parsedInteger;
    }

    const parsedNumber = Number.parseFloat(match[1].replace(",", "."));
    if (Number.isNaN(parsedNumber)) {
      return null;
    }

    const multiplier = suffix === "k" ? 1_000 : suffix === "m" ? 1_000_000 : 1_000_000_000;
    return Math.round(parsedNumber * multiplier);
  }

  function parsePublishedAt(text, nowMs = Date.now()) {
    const normalized = normalizeText(text).toLowerCase();
    if (!normalized) {
      return null;
    }
    if (normalized === "just now") {
      return new Date(nowMs).toISOString();
    }

    const withoutPrefix = normalized.replace(/^streamed\s+/, "");
    const match = withoutPrefix.match(RELATIVE_ENGLISH_TIME_PATTERN);
    if (!match) {
      return null;
    }

    const amount = Number.parseInt(match[1], 10);
    const unit = match[2].toLowerCase();
    const unitSeconds = RELATIVE_SECONDS_BY_UNIT[unit];
    if (Number.isNaN(amount) || !unitSeconds) {
      return null;
    }

    return new Date(nowMs - amount * unitSeconds * 1000).toISOString();
  }

  function buildRecommendationItem(fields) {
    const item = {
      videoHash: fields.videoHash,
      title: fields.title || fields.videoHash,
    };
    if (fields.channelName) {
      item.channelName = fields.channelName;
    }
    if (fields.channelLink) {
      item.channelLink = fields.channelLink;
    }
    if (fields.channelAvatar) {
      item.channelAvatar = fields.channelAvatar;
    }
    if (typeof fields.viewCount === "number" && Number.isFinite(fields.viewCount)) {
      item.viewCount = fields.viewCount;
    }
    if (fields.publishedAt) {
      item.publishedAt = fields.publishedAt;
    }
    return item;
  }

  function parseStandardVideoItem(item, baseUrl, nowMs) {
    const primaryVideoLink = item.querySelector("a[href*='/watch?v=']");
    const videoHash = extractVideoHashFromHref(
      primaryVideoLink ? primaryVideoLink.getAttribute("href") : null,
      baseUrl
    );
    if (!videoHash) {
      return null;
    }

    const titleLink = item.querySelector("h3 a[href*='/watch?v=']");
    const titleText = normalizeText(titleLink ? titleLink.textContent : "");
    const titleAttr = normalizeText(titleLink ? titleLink.getAttribute("title") : "");
    const title = titleText || titleAttr || videoHash;

    const channelLinkElement = item.querySelector(
      ".yt-lockup-metadata-view-model__metadata-row a[href]"
    );
    const channelName = normalizeText(
      channelLinkElement ? channelLinkElement.textContent : ""
    );
    const channelLink = toAbsoluteUrl(
      channelLinkElement ? channelLinkElement.getAttribute("href") : null,
      baseUrl
    );
    const channelAvatar = toAbsoluteUrl(
      item
        .querySelector(".yt-lockup-metadata-view-model__avatar img[src]")
        ?.getAttribute("src"),
      baseUrl
    );

    const metadataTexts = Array.from(
      item.querySelectorAll(
        ".yt-lockup-metadata-view-model__metadata .yt-content-metadata-view-model__metadata-row [role='text']"
      )
    )
      .map((node) => normalizeText(node.textContent))
      .filter(Boolean);

    let viewCount = null;
    let publishedAt = null;
    for (const metadataText of metadataTexts) {
      if (viewCount === null) {
        const parsedViews = parseViewCount(metadataText);
        if (parsedViews !== null) {
          viewCount = parsedViews;
        }
      }
      if (publishedAt === null) {
        const parsedPublishedAt = parsePublishedAt(metadataText, nowMs);
        if (parsedPublishedAt !== null) {
          publishedAt = parsedPublishedAt;
        }
      }
      if (viewCount !== null && publishedAt !== null) {
        break;
      }
    }

    return buildRecommendationItem({
      videoHash,
      title,
      channelName: channelName || null,
      channelLink,
      channelAvatar,
      viewCount,
      publishedAt,
    });
  }

  function parseShortItem(item, baseUrl, nowMs) {
    const shortLink = item.querySelector("a[href*='/shorts/']");
    const videoHash = extractVideoHashFromHref(
      shortLink ? shortLink.getAttribute("href") : null,
      baseUrl
    );
    if (!videoHash) {
      return null;
    }

    const titleElement = item.querySelector(
      ".shortsLockupViewModelHostMetadataTitle [role='text']"
    );
    const titleLink = item.querySelector(".shortsLockupViewModelHostMetadataTitle a[href]");
    const title = normalizeText(titleElement ? titleElement.textContent : "")
      || normalizeText(titleLink ? titleLink.getAttribute("title") : "")
      || videoHash;

    const viewText = normalizeText(
      item.querySelector(".shortsLockupViewModelHostMetadataSubhead [role='text']")
        ?.textContent
    );
    const viewCount = parseViewCount(viewText);
    const publishedAt = parsePublishedAt(viewText, nowMs);

    return buildRecommendationItem({
      videoHash,
      title,
      viewCount,
      publishedAt,
    });
  }

  function collectRecommendationsFromDocument(doc) {
    const items = doc.querySelectorAll("ytd-rich-item-renderer");
    const videos = [];
    const shorts = [];
    const seenVideos = new Set();
    const seenShorts = new Set();
    const baseUrl = window.location.origin;
    const nowMs = Date.now();

    for (const item of items) {
      const isShortsItem = Boolean(item.closest("ytd-rich-section-renderer"));
      const parsedItem = isShortsItem
        ? parseShortItem(item, baseUrl, nowMs)
        : parseStandardVideoItem(item, baseUrl, nowMs);
      if (!parsedItem) {
        continue;
      }

      if (isShortsItem) {
        if (seenShorts.has(parsedItem.videoHash)) {
          continue;
        }
        seenShorts.add(parsedItem.videoHash);
        shorts.push(parsedItem);
        continue;
      }

      if (seenVideos.has(parsedItem.videoHash)) {
        continue;
      }
      seenVideos.add(parsedItem.videoHash);
      videos.push(parsedItem);
    }

    return { videos, shorts };
  }

  function createRecommendationSnapshot(doc = document) {
    const collections = collectRecommendationsFromDocument(doc);
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
      collectVideoHashesFromDocument: collectRecommendationsFromDocument,
      collectRecommendationsFromDocument,
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
