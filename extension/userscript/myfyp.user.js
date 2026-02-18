// ==UserScript==
// @name         For Us Page (MVP Scaffold)
// @namespace    https://myfyp.link
// @version      0.1.19
// @description  MVP scaffold for sharing YouTube recommendation pages
// @match        https://www.youtube.com/*
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @grant        GM_registerMenuCommand
// @downloadURL  https://myfyp.link/myfyp.user.js
// @updateURL    https://myfyp.link/myfyp.user.js
// @connect      *
// ==/UserScript==

(function () {
  "use strict";

  const APP_NAME = "For Us Page";
  const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;
  const AD_HOST_PATTERNS = [
    "googleadservices.com",
    "doubleclick.net",
    "googlesyndication.com",
    "adservice.google.com",
  ];
  const AVATAR_HOST_PATTERNS = ["yt3.ggpht.com", "yt3.googleusercontent.com"];
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
  const API_BASE_URL_MIGRATION_KEY = "forUsPage.apiBaseUrlMigratedFromLocalhost";
  const LINK_HISTORY_STORAGE_KEY = "forUsPage.linkHistory";
  const LINK_HISTORY_MAX_ITEMS = 500;
  const DEBUG_STORAGE_KEY = "forUsPage.debug";
  const DEFAULT_API_BASE_URL = "https://myfyp.link";
  const TOAST_ID = "for-us-page-toast";
  const CHANNEL_PARSE_WARNING_LIMIT = 5;
  const pageWindow = typeof unsafeWindow !== "undefined" ? unsafeWindow : window;
  let channelParseWarnings = 0;
  let avatarParseWarnings = 0;

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

  function isDebugEnabled() {
    return pageWindow.localStorage.getItem(DEBUG_STORAGE_KEY) === "1";
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

  function isChannelHref(href, baseUrl) {
    if (!href) {
      return false;
    }
    let url;
    try {
      url = new URL(href, baseUrl);
    } catch {
      return false;
    }
    if (!/youtube\.com$/i.test(url.hostname)) {
      return false;
    }
    const pathname = url.pathname;
    return (
      pathname.startsWith("/@")
      || pathname.startsWith("/channel/")
      || pathname.startsWith("/c/")
      || pathname.startsWith("/user/")
    );
  }

  function extractChannelNameFromAvatarAria(item) {
    const avatarButton = item.querySelector(
      ".yt-lockup-metadata-view-model__avatar [aria-label]"
    );
    const ariaLabel = normalizeText(
      avatarButton ? avatarButton.getAttribute("aria-label") : ""
    );
    const prefix = "go to channel ";
    const lower = ariaLabel.toLowerCase();
    if (!lower.startsWith(prefix)) {
      return null;
    }
    const extracted = ariaLabel.slice(prefix.length).trim();
    return extracted || null;
  }

  function extractChannelData(item, baseUrl) {
    const linkFromMetadata = item.querySelector(
      ".yt-lockup-metadata-view-model__metadata-row a[href]"
    );
    const linkFromLegacy = item.querySelector("ytd-channel-name a[href], #channel-name a[href]");
    const allAnchors = Array.from(item.querySelectorAll("a[href]"));
    const linkFromPattern = allAnchors.find((anchor) =>
      isChannelHref(anchor.getAttribute("href"), baseUrl)
    );
    const channelAnchor = linkFromMetadata || linkFromLegacy || linkFromPattern || null;

    let channelName = normalizeText(channelAnchor ? channelAnchor.textContent : "");
    if (!channelName) {
      channelName = extractChannelNameFromAvatarAria(item) || "";
    }
    const channelLink = toAbsoluteUrl(
      channelAnchor ? channelAnchor.getAttribute("href") : null,
      baseUrl
    );

    const channelAvatar = extractChannelAvatar(item, baseUrl);

    return {
      channelName: channelName || null,
      channelLink,
      channelAvatar,
    };
  }

  function isAvatarHost(hostname) {
    const normalized = hostname.toLowerCase();
    return AVATAR_HOST_PATTERNS.some(
      (avatarHostPattern) => normalized === avatarHostPattern || normalized.endsWith(`.${avatarHostPattern}`)
    );
  }

  function isLikelyAvatarSrc(src, baseUrl) {
    if (!src) {
      return false;
    }
    let url;
    try {
      url = new URL(src, baseUrl);
    } catch {
      return false;
    }
    if (isAvatarHost(url.hostname)) {
      return true;
    }
    return /\/ytc\//i.test(url.pathname);
  }

  function extractChannelAvatar(item, baseUrl) {
    const selectorCandidates = [
      ".yt-lockup-metadata-view-model__avatar img[src]",
      "yt-decorated-avatar-view-model img[src]",
      "yt-avatar-shape img[src]",
      "img.yt-spec-avatar-shape__image[src]",
      "ytd-channel-name ~ * img[src]",
      "#channel-name ~ * img[src]",
    ];
    for (const selector of selectorCandidates) {
      const element = item.querySelector(selector);
      if (!element) {
        continue;
      }
      const src = element.getAttribute("src");
      if (!isLikelyAvatarSrc(src, baseUrl)) {
        continue;
      }
      const absolute = toAbsoluteUrl(src, baseUrl);
      if (absolute) {
        return absolute;
      }
    }

    const hostFilteredImage = Array.from(item.querySelectorAll("img[src]")).find((image) =>
      isLikelyAvatarSrc(image.getAttribute("src"), baseUrl)
    );
    if (!hostFilteredImage) {
      return null;
    }
    return toAbsoluteUrl(hostFilteredImage.getAttribute("src"), baseUrl);
  }

  function maybeLogMissingChannelMetadata(videoHash, item) {
    if (!isDebugEnabled()) {
      return;
    }
    if (channelParseWarnings >= CHANNEL_PARSE_WARNING_LIMIT) {
      return;
    }
    channelParseWarnings += 1;
    console.debug(
      `[${APP_NAME}] Missing channel metadata for video ${videoHash}.`,
      {
        hint: "Set localStorage.forUsPage.debug='1' to keep debug logs enabled.",
        snippet: item.outerHTML.slice(0, 1200),
      }
    );
  }

  function maybeLogMissingAvatar(videoHash, item, channelName, channelLink) {
    if (!isDebugEnabled()) {
      return;
    }
    if (avatarParseWarnings >= CHANNEL_PARSE_WARNING_LIMIT) {
      return;
    }
    avatarParseWarnings += 1;
    console.debug(
      `[${APP_NAME}] Missing avatar for video ${videoHash}.`,
      {
        channelName,
        channelLink,
        snippet: item.outerHTML.slice(0, 1200),
      }
    );
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

    const channelData = extractChannelData(item, baseUrl);

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

    if (!channelData.channelName && !channelData.channelLink && !channelData.channelAvatar) {
      maybeLogMissingChannelMetadata(videoHash, item);
    }
    if ((channelData.channelName || channelData.channelLink) && !channelData.channelAvatar) {
      maybeLogMissingAvatar(
        videoHash,
        item,
        channelData.channelName,
        channelData.channelLink
      );
    }

    return buildRecommendationItem({
      videoHash,
      title,
      channelName: channelData.channelName,
      channelLink: channelData.channelLink,
      channelAvatar: channelData.channelAvatar,
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

  function isAdLinkHref(href, baseUrl) {
    if (!href) {
      return false;
    }
    let url;
    try {
      url = new URL(href, baseUrl);
    } catch {
      return false;
    }
    const hostname = url.hostname.toLowerCase();
    return AD_HOST_PATTERNS.some(
      (adHostPattern) => hostname === adHostPattern || hostname.endsWith(`.${adHostPattern}`)
    );
  }

  function isAdRichItem(item, baseUrl) {
    if (
      item.querySelector(
        "ytd-ad-slot-renderer, ytd-in-feed-ad-layout-renderer, feed-ad-metadata-view-model, ad-badge-view-model"
      )
    ) {
      return true;
    }

    const sponsoredBadge = item.querySelector(
      ".yt-badge-shape--ad, .ytwAdBadgeViewModelHostIsClickableAdComponent"
    );
    if (sponsoredBadge) {
      return true;
    }

    const adLink = Array.from(item.querySelectorAll("a[href]")).some((link) =>
      isAdLinkHref(link.getAttribute("href"), baseUrl)
    );
    return adLink;
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
      if (isAdRichItem(item, baseUrl)) {
        continue;
      }
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

  function isLegacyLocalApiBaseUrl(baseUrl) {
    const normalized = normalizeApiBaseUrl(baseUrl);
    if (!normalized) {
      return false;
    }
    try {
      const parsed = new URL(normalized);
      const isLoopbackHost =
        parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost";
      const hasDefaultDevPort = !parsed.port || parsed.port === "8000";
      return parsed.protocol === "http:" && isLoopbackHost && hasDefaultDevPort;
    } catch {
      return false;
    }
  }

  function migrateLegacyApiBaseUrl() {
    const alreadyMigrated = pageWindow.localStorage.getItem(API_BASE_URL_MIGRATION_KEY) === "1";
    if (alreadyMigrated) {
      return;
    }
    const fromStorage = pageWindow.localStorage.getItem(API_BASE_URL_STORAGE_KEY);
    if (!isLegacyLocalApiBaseUrl(fromStorage)) {
      pageWindow.localStorage.setItem(API_BASE_URL_MIGRATION_KEY, "1");
      return;
    }
    pageWindow.localStorage.setItem(API_BASE_URL_STORAGE_KEY, DEFAULT_API_BASE_URL);
    pageWindow.localStorage.setItem(API_BASE_URL_MIGRATION_KEY, "1");
  }

  function getApiBaseUrl() {
    migrateLegacyApiBaseUrl();
    const fromStorage = pageWindow.localStorage.getItem(API_BASE_URL_STORAGE_KEY);
    return normalizeApiBaseUrl(fromStorage || DEFAULT_API_BASE_URL);
  }

  function getLinkHistory() {
    const rawValue = pageWindow.localStorage.getItem(LINK_HISTORY_STORAGE_KEY);
    if (!rawValue) {
      return [];
    }
    try {
      const parsed = JSON.parse(rawValue);
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed
        .filter((entry) => entry && typeof entry === "object")
        .map((entry) => ({
          createdAt: normalizeText(entry.createdAt || ""),
          shareUrl: normalizeText(entry.shareUrl || ""),
          removeUrl: normalizeText(entry.removeUrl || ""),
          hash: normalizeText(entry.hash || ""),
        }))
        .filter((entry) => entry.shareUrl || entry.removeUrl);
    } catch {
      return [];
    }
  }

  function setLinkHistory(entries) {
    pageWindow.localStorage.setItem(
      LINK_HISTORY_STORAGE_KEY,
      JSON.stringify(entries.slice(0, LINK_HISTORY_MAX_ITEMS))
    );
  }

  function appendLinkHistoryEntry(entry) {
    const shareUrl = normalizeText(entry && entry.shareUrl);
    const removeUrl = normalizeText(entry && entry.removeUrl);
    if (!shareUrl && !removeUrl) {
      return;
    }
    const hash = normalizeText(entry && entry.hash);
    const createdAt = normalizeText(entry && entry.createdAt) || new Date().toISOString();
    const history = getLinkHistory();
    const deduplicatedHistory = history.filter(
      (existing) =>
        !(existing.shareUrl === shareUrl && existing.removeUrl === removeUrl)
    );
    deduplicatedHistory.unshift({ createdAt, shareUrl, removeUrl, hash });
    setLinkHistory(deduplicatedHistory);
  }

  function isSameLinkHistoryEntry(left, right) {
    return (
      left.createdAt === right.createdAt
      && left.shareUrl === right.shareUrl
      && left.removeUrl === right.removeUrl
      && left.hash === right.hash
    );
  }

  function removeLinkHistoryEntry(entryToRemove) {
    const history = getLinkHistory();
    const filteredHistory = history.filter((entry) => !isSameLinkHistoryEntry(entry, entryToRemove));
    setLinkHistory(filteredHistory);
  }

  function clearLinkHistory() {
    pageWindow.localStorage.removeItem(LINK_HISTORY_STORAGE_KEY);
  }

  function formatHistoryTimestamp(isoString) {
    if (!isoString) {
      return "Unknown time";
    }
    const parsedDate = new Date(isoString);
    if (Number.isNaN(parsedDate.getTime())) {
      return "Unknown time";
    }
    return parsedDate.toLocaleString();
  }

  function historyTimestampMs(isoString) {
    if (!isoString) {
      return 0;
    }
    const parsedMs = new Date(isoString).getTime();
    return Number.isFinite(parsedMs) ? parsedMs : 0;
  }

  function getSortedLinkHistory() {
    return getLinkHistory()
      .slice()
      .sort((left, right) => historyTimestampMs(right.createdAt) - historyTimestampMs(left.createdAt));
  }

  function showLinkHistoryToast(entries) {
    removeToast();

    const toast = document.createElement("div");
    toast.id = TOAST_ID;
    toast.style.position = "fixed";
    toast.style.top = "16px";
    toast.style.right = "16px";
    toast.style.maxWidth = "700px";
    toast.style.maxHeight = "75vh";
    toast.style.overflowY = "auto";
    toast.style.padding = "12px 14px";
    toast.style.borderRadius = "10px";
    toast.style.background = "rgba(26, 26, 26, 0.95)";
    toast.style.color = "#fff";
    toast.style.fontSize = "13px";
    toast.style.lineHeight = "1.35";
    toast.style.zIndex = "2147483647";
    toast.style.boxShadow = "0 8px 24px rgba(0,0,0,0.35)";
    toast.style.border = "1px solid rgba(255,255,255,0.12)";

    const title = document.createElement("div");
    title.textContent = `${APP_NAME} link history`;
    title.style.fontWeight = "700";
    title.style.marginBottom = "6px";
    toast.appendChild(title);

    const subtitle = document.createElement("div");
    subtitle.textContent = `Saved snapshots: ${entries.length}`;
    subtitle.style.color = "rgba(255,255,255,0.82)";
    toast.appendChild(subtitle);

    const list = document.createElement("div");
    list.style.marginTop = "10px";
    list.style.display = "grid";
    list.style.gap = "8px";

    const totalEntries = entries.length;
    for (const [index, entry] of entries.entries()) {
      const line = document.createElement("div");
      const position = totalEntries - index;
      const createdAt = formatHistoryTimestamp(entry.createdAt);
      line.append(document.createTextNode(`#${position} • ${createdAt} • `));

      if (entry.shareUrl) {
        const shareLink = document.createElement("a");
        shareLink.href = entry.shareUrl;
        shareLink.textContent = "Share";
        shareLink.target = "_blank";
        shareLink.rel = "noopener noreferrer";
        shareLink.style.color = "#8ab4ff";
        shareLink.style.textDecoration = "none";
        line.appendChild(shareLink);
      } else {
        line.append(document.createTextNode("Share"));
      }

      line.append(document.createTextNode(" • "));

      if (entry.removeUrl) {
        const deleteLink = document.createElement("a");
        deleteLink.href = entry.removeUrl;
        deleteLink.textContent = "Delete";
        deleteLink.target = "_blank";
        deleteLink.rel = "noopener noreferrer";
        deleteLink.style.color = "#8ab4ff";
        deleteLink.style.textDecoration = "none";
        line.appendChild(deleteLink);
      } else {
        line.append(document.createTextNode("Delete"));
      }

      line.append(document.createTextNode(" • "));
      const removeFromListButton = document.createElement("button");
      removeFromListButton.type = "button";
      removeFromListButton.textContent = "Remove from list";
      removeFromListButton.style.padding = "0";
      removeFromListButton.style.border = "none";
      removeFromListButton.style.background = "transparent";
      removeFromListButton.style.color = "#8ab4ff";
      removeFromListButton.style.cursor = "pointer";
      removeFromListButton.style.fontSize = "13px";
      removeFromListButton.style.lineHeight = "1.35";
      removeFromListButton.addEventListener("click", () => {
        removeLinkHistoryEntry(entry);
        showLinkHistory();
      });
      line.appendChild(removeFromListButton);
      list.appendChild(line);
    }
    toast.appendChild(list);

    const footer = document.createElement("div");
    footer.style.display = "flex";
    footer.style.gap = "8px";
    footer.style.marginTop = "10px";

    const clearAllButton = document.createElement("button");
    clearAllButton.type = "button";
    clearAllButton.textContent = "Clear all";
    clearAllButton.style.padding = "4px 8px";
    clearAllButton.style.border = "1px solid rgba(255,255,255,0.2)";
    clearAllButton.style.borderRadius = "6px";
    clearAllButton.style.background = "transparent";
    clearAllButton.style.color = "#fff";
    clearAllButton.style.cursor = "pointer";
    clearAllButton.addEventListener("click", () => {
      clearLinkHistory();
      showToast({
        title: `${APP_NAME}`,
        message: "History cleared.",
      });
    });
    footer.appendChild(clearAllButton);

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.textContent = "Close";
    closeButton.style.padding = "4px 8px";
    closeButton.style.border = "1px solid rgba(255,255,255,0.2)";
    closeButton.style.borderRadius = "6px";
    closeButton.style.background = "transparent";
    closeButton.style.color = "#fff";
    closeButton.style.cursor = "pointer";
    closeButton.addEventListener("click", removeToast);
    footer.appendChild(closeButton);
    toast.appendChild(footer);

    document.body.appendChild(toast);
  }

  function showLinkHistory() {
    const history = getSortedLinkHistory();
    if (history.length === 0) {
      showToast({
        title: `${APP_NAME}`,
        message: "No uploaded snapshot links found yet.",
        variant: "error",
      });
      return;
    }
    showLinkHistoryToast(history);
  }

  function removeToast() {
    const existing = document.getElementById(TOAST_ID);
    if (existing) {
      existing.remove();
    }
  }

  function showToast(options) {
    removeToast();

    const toast = document.createElement("div");
    toast.id = TOAST_ID;
    toast.style.position = "fixed";
    toast.style.top = "16px";
    toast.style.right = "16px";
    toast.style.maxWidth = options.maxWidth || "420px";
    toast.style.padding = "12px 14px";
    toast.style.borderRadius = "10px";
    toast.style.background = options.variant === "error" ? "rgba(168, 51, 51, 0.95)" : "rgba(26, 26, 26, 0.95)";
    toast.style.color = "#fff";
    toast.style.fontSize = "13px";
    toast.style.lineHeight = "1.35";
    toast.style.zIndex = "2147483647";
    toast.style.boxShadow = "0 8px 24px rgba(0,0,0,0.35)";
    toast.style.border = "1px solid rgba(255,255,255,0.12)";
    if (options.maxHeight) {
      toast.style.maxHeight = options.maxHeight;
      toast.style.overflowY = "auto";
    }

    const title = document.createElement("div");
    title.textContent = options.title;
    title.style.fontWeight = "700";
    title.style.marginBottom = "6px";
    toast.appendChild(title);

    if (options.message) {
      const message = document.createElement("div");
      message.textContent = options.message;
      toast.appendChild(message);
    }

    const linkEntries = Array.isArray(options.links) ? options.links : [];
    if (linkEntries.length > 0) {
      for (const entry of linkEntries) {
        if (!entry || typeof entry.url !== "string" || !entry.url.trim()) {
          continue;
        }
        const row = document.createElement("div");
        row.style.marginTop = "8px";

        if (entry.label) {
          const label = document.createElement("div");
          label.textContent = `${entry.label}:`;
          label.style.fontSize = "12px";
          label.style.color = "rgba(255,255,255,0.8)";
          row.appendChild(label);
        }

        const link = document.createElement("a");
        link.href = entry.url;
        link.textContent = entry.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.style.display = "block";
        link.style.marginTop = "2px";
        link.style.color = "#8ab4ff";
        link.style.wordBreak = "break-all";
        row.appendChild(link);
        toast.appendChild(row);
      }
    }

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.textContent = "Close";
    closeButton.style.marginTop = "10px";
    closeButton.style.padding = "4px 8px";
    closeButton.style.border = "1px solid rgba(255,255,255,0.2)";
    closeButton.style.borderRadius = "6px";
    closeButton.style.background = "transparent";
    closeButton.style.color = "#fff";
    closeButton.style.cursor = "pointer";
    closeButton.addEventListener("click", removeToast);
    toast.appendChild(closeButton);

    document.body.appendChild(toast);
    pageWindow.setTimeout(removeToast, options.durationMs || 12000);
  }

  function buildSnapshotUrl(apiBaseUrl, response) {
    if (response && typeof response.url === "string" && response.url.trim()) {
      return response.url.trim();
    }
    const snapshotHash = response && typeof response.hash === "string" ? response.hash : "";
    if (!snapshotHash) {
      return null;
    }
    try {
      return new URL(`/${snapshotHash}`, `${apiBaseUrl}/`).toString();
    } catch {
      return null;
    }
  }

  function buildRemoveUrl(apiBaseUrl, response) {
    if (response && typeof response.removeUrl === "string" && response.removeUrl.trim()) {
      return response.removeUrl.trim();
    }
    const snapshotHash = response && typeof response.hash === "string" ? response.hash : "";
    const removeToken = response && typeof response.removeToken === "string" ? response.removeToken : "";
    if (!snapshotHash || !removeToken) {
      return null;
    }
    try {
      return new URL(
        `/api/snapshots/${encodeURIComponent(snapshotHash)}/remove/${encodeURIComponent(removeToken)}`,
        `${apiBaseUrl}/`
      ).toString();
    } catch {
      return null;
    }
  }

  function setApiBaseUrl(url) {
    const normalized = normalizeApiBaseUrl(url);
    if (!normalized) {
      throw new Error("API base URL cannot be empty.");
    }
    pageWindow.localStorage.setItem(API_BASE_URL_STORAGE_KEY, normalized);
    return normalized;
  }

  function extractApiErrorDetail(bodyText) {
    const normalizedBody = normalizeText(bodyText);
    if (!normalizedBody) {
      return "";
    }
    try {
      const parsed = JSON.parse(normalizedBody);
      if (!parsed || typeof parsed !== "object") {
        return normalizedBody;
      }
      const detail = parsed.detail;
      if (typeof detail === "string" && detail.trim()) {
        return normalizeText(detail);
      }
      if (Array.isArray(detail) && detail.length > 0) {
        return normalizeText(JSON.stringify(detail));
      }
      return normalizedBody;
    } catch {
      return normalizedBody;
    }
  }

  function buildApiErrorMessage(status, statusText, bodyText) {
    const base = `API request failed: ${status}${statusText ? ` ${statusText}` : ""}`;
    const detail = extractApiErrorDetail(bodyText);
    if (!detail) {
      return base;
    }
    return `${base}. ${detail}`;
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
            const responseBody = typeof response.responseText === "string" ? response.responseText : "";
            reject(
              new Error(
                buildApiErrorMessage(response.status, response.statusText || "", responseBody)
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
    const responseBody = await response.text();
    if (!response.ok) {
      throw new Error(buildApiErrorMessage(response.status, response.statusText, responseBody));
    }
    try {
      return JSON.parse(responseBody);
    } catch (error) {
      throw new Error(
        `Failed to parse API response: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    }
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
      showToast({
        title: `${APP_NAME}`,
        message: "No recommendations were found, upload skipped.",
        variant: "error",
      });
      return null;
    }
    const apiBaseUrl = getApiBaseUrl();
    try {
      const response = await uploadSnapshot(snapshot, apiBaseUrl);
      const snapshotUrl = buildSnapshotUrl(apiBaseUrl, response);
      const removeUrl = buildRemoveUrl(apiBaseUrl, response);
      appendLinkHistoryEntry({
        createdAt: new Date().toISOString(),
        hash: response && typeof response.hash === "string" ? response.hash : "",
        shareUrl: snapshotUrl,
        removeUrl,
      });
      console.info(`[${APP_NAME}] Upload response:`, response);
      showToast({
        title: `${APP_NAME} upload complete`,
        message: snapshotUrl
          ? "Snapshot and remove links:"
          : "Upload succeeded, but no snapshot link was returned.",
        links: [
          snapshotUrl ? { label: "Share link", url: snapshotUrl } : null,
          removeUrl ? { label: "Remove link", url: removeUrl } : null,
        ].filter(Boolean),
      });
      return response;
    } catch (error) {
      console.error(
        `[${APP_NAME}] Failed to upload snapshot to ${apiBaseUrl}:`,
        error
      );
      showToast({
        title: `${APP_NAME} upload failed`,
        message: error instanceof Error ? error.message : "Unknown upload error.",
        variant: "error",
      });
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
      getLinkHistory,
      showLinkHistory,
    });
  }

  function registerMenuCommands() {
    if (typeof GM_registerMenuCommand !== "function") {
      return;
    }
    GM_registerMenuCommand("For Us Page: Upload Snapshot", () => {
      void uploadLatestSnapshot();
    });
    GM_registerMenuCommand("For Us Page: Show Link History", () => {
      showLinkHistory();
    });
  }

  function bootstrap() {
    registerPublicApi();
    registerMenuCommands();
    console.info(
      `[${APP_NAME}] Userscript loaded. Run window.forUsPage.uploadLatestSnapshot() to upload and print API response.`
    );
  }

  bootstrap();
})();
