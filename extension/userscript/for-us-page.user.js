// ==UserScript==
// @name         For Us Page (MVP Scaffold)
// @namespace    https://for-us-page.local
// @version      0.1.1
// @description  MVP scaffold for sharing YouTube recommendation pages
// @match        https://www.youtube.com/*
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  const APP_NAME = "For Us Page";
  const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;

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

  function registerPublicApi() {
    window.forUsPage = Object.assign(window.forUsPage || {}, {
      extractVideoHashFromHref,
      collectVideoHashesFromDocument,
      createRecommendationSnapshot,
      logSnapshot,
    });
  }

  function bootstrap() {
    registerPublicApi();
    console.info(
      `[${APP_NAME}] Userscript loaded. Run window.forUsPage.logSnapshot() to capture video hashes.`
    );

    if (window.location.pathname === "/") {
      logSnapshot();
    }
  }

  bootstrap();
})();
