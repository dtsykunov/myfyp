import type { RecommendationItem, StoredSnapshotRecord } from "./types";

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatSnapshotTakenAt(isoDateTime: string): string {
  const parsedMs = Date.parse(isoDateTime);
  if (Number.isNaN(parsedMs)) {
    return "Unknown";
  }
  return new Date(parsedMs)
    .toISOString()
    .replace("T", " ")
    .replace(".000Z", " UTC");
}

function formatRelativeTime(publishedAtIso: string, referenceIso: string): string {
  const publishedMs = Date.parse(publishedAtIso);
  const referenceMs = Date.parse(referenceIso);
  if (Number.isNaN(publishedMs) || Number.isNaN(referenceMs)) {
    return "";
  }

  const deltaSeconds = Math.max(0, Math.floor((referenceMs - publishedMs) / 1000));
  if (deltaSeconds <= 0) {
    return "just now";
  }

  const units: ReadonlyArray<[string, number]> = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
    ["second", 1]
  ];

  for (const [unitName, unitSeconds] of units) {
    const amount = Math.floor(deltaSeconds / unitSeconds);
    if (amount < 1) {
      continue;
    }

    const suffix = amount === 1 ? "" : "s";
    return `${amount} ${unitName}${suffix} ago`;
  }

  return "just now";
}

function formatCompactViews(viewCount: number): string {
  if (viewCount < 1_000) {
    return `${viewCount} views`;
  }

  let value = viewCount;
  let suffix = "";
  if (viewCount < 1_000_000) {
    value = viewCount / 1_000;
    suffix = "K";
  } else if (viewCount < 1_000_000_000) {
    value = viewCount / 1_000_000;
    suffix = "M";
  } else {
    value = viewCount / 1_000_000_000;
    suffix = "B";
  }

  const formatted = value >= 10 ? `${Math.round(value)}` : `${value.toFixed(1).replace(/\.0$/, "")}`;
  return `${formatted}${suffix} views`;
}

function renderStatsText(item: RecommendationItem, referenceTimeIso: string): string {
  const parts: string[] = [];
  if (item.viewCount !== undefined) {
    parts.push(formatCompactViews(item.viewCount));
  }
  if (item.publishedAt !== undefined) {
    const formattedRelative = formatRelativeTime(item.publishedAt, referenceTimeIso);
    if (formattedRelative) {
      parts.push(formattedRelative);
    }
  }
  return parts.join(" • ");
}

function renderChannelAvatar(item: RecommendationItem): string {
  if (item.channelAvatar === undefined) {
    return '<div class="channel-avatar-placeholder" aria-hidden="true">?</div>';
  }

  const channelName = escapeHtml(item.channelName ?? "Channel avatar");
  return `<img class="channel-avatar" src="${escapeHtml(item.channelAvatar)}" alt="${channelName}" loading="lazy" referrerpolicy="no-referrer">`;
}

function renderChannelLine(item: RecommendationItem): string {
  if (item.channelName === undefined) {
    return '<div class="channel-line">unknown channel</div>';
  }

  const channelName = escapeHtml(item.channelName);
  if (item.channelLink === undefined) {
    return `<div class="channel-line">${channelName}</div>`;
  }

  return `<div class="channel-line"><a href="${escapeHtml(item.channelLink)}" target="_blank" rel="noopener noreferrer">${channelName}</a></div>`;
}

function renderVideoCard(item: RecommendationItem, referenceTimeIso: string): string {
  const title = escapeHtml(item.title);
  const videoHash = escapeHtml(item.videoHash);
  const watchUrl = `https://www.youtube.com/watch?v=${videoHash}`;
  const thumbnailUrl = `https://i.ytimg.com/vi/${videoHash}/hqdefault.jpg`;
  const statsText = renderStatsText(item, referenceTimeIso);

  return `
    <article class="video-card" aria-label="Video: ${title}">
      <a class="thumb" href="${watchUrl}" target="_blank" rel="noopener noreferrer">
        <img class="thumb-image" data-video-hash="${videoHash}" data-thumb-kind="video" src="${thumbnailUrl}" alt="${title}" loading="lazy" referrerpolicy="no-referrer">
      </a>
      <div class="card-body">
        <div class="card-meta">
          ${renderChannelAvatar(item)}
          <div class="meta-text">
            <h3 class="video-title">${title}</h3>
            ${renderChannelLine(item)}
            ${statsText ? `<div class="channel-row">${escapeHtml(statsText)}</div>` : ""}
          </div>
        </div>
      </div>
    </article>
  `;
}

function renderShortCard(item: RecommendationItem, referenceTimeIso: string): string {
  const title = escapeHtml(item.title);
  const videoHash = escapeHtml(item.videoHash);
  const watchUrl = `https://www.youtube.com/shorts/${videoHash}`;
  const thumbnailUrl = `https://i.ytimg.com/vi/${videoHash}/oar1.jpg`;
  const statsText = renderStatsText(item, referenceTimeIso);

  return `
    <article class="short-card" aria-label="Short: ${title}">
      <a class="thumb" href="${watchUrl}" target="_blank" rel="noopener noreferrer">
        <img class="thumb-image" data-video-hash="${videoHash}" data-thumb-kind="short" src="${thumbnailUrl}" alt="${title}" loading="lazy" referrerpolicy="no-referrer">
      </a>
      <div class="card-body">
        <h3 class="title">${title}</h3>
        ${item.channelName ? `<div class="meta-line">${escapeHtml(item.channelName)}</div>` : ""}
        ${statsText ? `<div class="meta-line">${escapeHtml(statsText)}</div>` : ""}
      </div>
    </article>
  `;
}

function renderGrid(items: RecommendationItem[], referenceTimeIso: string, kind: "video" | "short"): string {
  if (items.length === 0) {
    return '<p class="empty">No items in this list.</p>';
  }

  if (kind === "video") {
    return items.map((item) => renderVideoCard(item, referenceTimeIso)).join("\n");
  }

  return items.map((item) => renderShortCard(item, referenceTimeIso)).join("\n");
}

export function renderSnapshotHtml(snapshot: StoredSnapshotRecord): string {
  const referenceTimeIso = snapshot.payload.capturedAt ?? snapshot.createdAt;
  const escapedHash = escapeHtml(snapshot.hash);
  const escapedTakenAt = escapeHtml(formatSnapshotTakenAt(referenceTimeIso));

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700&display=swap" rel="stylesheet">
    <title>For Us Page by dtsykunov - ${escapedHash}</title>
    <style>
      :root {
        --bg: #0f0f0f;
        --card: #181818;
        --text: #f1f1f1;
        --muted: #aaaaaa;
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, sans-serif;
      }

      main {
        max-width: 2400px;
        margin: 0 auto;
        padding: 20px;
      }

      .top-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 0 12px;
      }

      .brand-logo {
        width: 29px;
        height: 20px;
        background: #ff0033;
        border-radius: 6px;
        position: relative;
        overflow: hidden;
        flex-shrink: 0;
      }

      .brand-logo::after {
        content: "";
        position: absolute;
        left: 11px;
        top: 5px;
        border-style: solid;
        border-width: 5px 0 5px 8px;
        border-color: transparent transparent transparent #fff;
      }

      h1 { margin: 0; font-size: 28px; }

      .title-link {
        color: #2c9cd3;
        text-decoration: underline;
        font-family: "Zen Kaku Gothic New", sans-serif;
        letter-spacing: .01em;
        font-weight: 300;
        font-style: italic;
        font-optical-sizing: auto;
        text-rendering: optimizeLegibility;
      }

      .meta { margin: 0; color: var(--muted); font-size: 14px; line-height: 1.4; }
      .meta-stack { margin: 0 0 24px; display: grid; gap: 2px; }
      .page-description { margin: 0 0 6px; color: #c6c6c6; font-size: 14px; line-height: 1.45; }
      .section-title { margin: 24px 0 12px; font-size: 22px; }

      .shorts-section-title {
        display: inline-flex;
        align-items: center;
        gap: 10px;
      }

      .shorts-icon {
        width: 24px;
        height: 24px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .videos-grid,
      .shorts-grid {
        display: grid;
        gap: 16px;
        justify-content: center;
      }

      .videos-grid { grid-template-columns: repeat(6, 365px); }
      .shorts-grid { grid-template-columns: repeat(6, 365px); }

      .video-card,
      .short-card {
        width: 365px;
        background: var(--card);
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid transparent;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition: transform 250ms ease, box-shadow 250ms ease, border-color 250ms ease;
      }

      .video-card { min-height: 305px; }
      .short-card { min-height: 547px; }

      .video-card:hover,
      .short-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.18);
        border-color: rgba(255, 255, 255, 0.12);
      }

      .thumb { display: block; }
      .video-card .thumb { width: 365px; aspect-ratio: 16 / 9; }
      .short-card .thumb { width: 365px; aspect-ratio: 3 / 4; }

      .video-card .thumb img,
      .short-card .thumb img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .video-card .card-body { padding: 12px; }
      .short-card .card-body { padding: 10px 12px; }

      .card-meta {
        display: flex;
        gap: 12px;
        align-items: flex-start;
      }

      .meta-text {
        display: flex;
        flex-direction: column;
        min-width: 0;
        flex: 1;
      }

      .video-title {
        margin: 0 0 6px;
        font-size: 14px;
        font-weight: 600;
        line-height: 1.3;
        color: var(--text);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      .title {
        margin: 0;
        font-size: 14px;
        line-height: 1.25;
        color: var(--text);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      .channel-avatar,
      .channel-avatar-placeholder {
        width: 36px;
        height: 36px;
        border-radius: 999px;
        flex-shrink: 0;
      }

      .channel-avatar { object-fit: cover; }

      .channel-avatar-placeholder {
        display: flex;
        align-items: center;
        justify-content: center;
        background: #2a2a2a;
        color: #9f9f9f;
        font-size: 14px;
      }

      .channel-line,
      .channel-row,
      .meta-line {
        color: var(--muted);
        font-size: 12px;
        line-height: 1.3;
      }

      .channel-line a {
        color: inherit;
        text-decoration: none;
      }

      .channel-line a:hover { text-decoration: underline; }
      .empty { color: var(--muted); }

      .faq-footer {
        margin-top: 36px;
        padding-top: 18px;
        border-top: 1px solid rgba(255, 255, 255, 0.12);
      }

      .faq-title { margin: 0 0 10px; font-size: 18px; }
      .faq-item { margin: 0 0 12px; }
      .faq-question { margin: 0 0 4px; font-size: 14px; font-weight: 600; color: var(--text); }
      .faq-answer { margin: 0; font-size: 13px; line-height: 1.45; color: var(--muted); }

      @media (max-width: 2280px) { .videos-grid, .shorts-grid { grid-template-columns: repeat(5, 365px); } }
      @media (max-width: 1900px) { .videos-grid, .shorts-grid { grid-template-columns: repeat(4, 365px); } }
      @media (max-width: 1520px) { .videos-grid, .shorts-grid { grid-template-columns: repeat(3, 365px); } }
      @media (max-width: 1140px) { .videos-grid, .shorts-grid { grid-template-columns: repeat(2, 365px); } }
      @media (max-width: 767px) {
        main { padding: 12px; }
        .videos-grid { grid-template-columns: 1fr; justify-content: stretch; }
        .video-card { width: 100%; min-height: auto; }
        .video-card .thumb { width: 100%; }
        .shorts-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .short-card { width: 100%; min-height: auto; }
        .short-card .thumb { width: 100%; }
      }
    </style>
  </head>
  <body>
    <main>
      <header class="top-header">
        <div class="brand-logo" aria-hidden="true"></div>
        <h1>For Us Page by <a class="title-link" href="https://dtsykunov.com/" target="_blank" rel="noopener noreferrer">dtsykunov</a></h1>
      </header>

      <div class="meta-stack">
        <p class="page-description">A snapshot of a personal YouTube recommendation page.</p>
        <p class="meta"><strong>Taken at:</strong> ${escapedTakenAt}</p>
        <p class="meta"><strong>Snapshot hash:</strong> ${escapedHash}</p>
      </div>

      <section>
        <h2 class="section-title">Videos</h2>
        <div class="videos-grid">
          ${renderGrid(snapshot.payload.videos, referenceTimeIso, "video")}
        </div>
      </section>

      <section>
        <h2 class="section-title shorts-section-title">
          <span class="shorts-icon" aria-hidden="true">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" focusable="false" aria-hidden="true">
              <path d="m19.45,3.88c1.12,1.82.48,4.15-1.42,5.22l-1.32.74.94.41c1.36.58,2.27,1.85,2.35,3.27.08,1.43-.68,2.77-1.97,3.49l-8,4.47c-1.91,1.06-4.35.46-5.48-1.35-1.12-1.82-.48-4.15,1.42-5.22l1.33-.74-.94-.41c-1.36-.58-2.27-1.85-2.35-3.27-.08-1.43.68-2.77,1.97-3.49l8-4.47c1.91-1.06,4.35-.46,5.48,1.35Z" fill="#f03"></path>
              <path d="m10,15l5-3-5-3v6Z" fill="#fff"></path>
            </svg>
          </span>
          <span>Shorts</span>
        </h2>
        <div class="shorts-grid">
          ${renderGrid(snapshot.payload.shorts, referenceTimeIso, "short")}
        </div>
      </section>

      <footer class="faq-footer">
        <h2 class="faq-title">FAQ</h2>
        <section class="faq-item">
          <h3 class="faq-question">1. What is this?</h3>
          <p class="faq-answer">This is a captured snapshot of someone&#39;s personal YouTube recommendation page at a specific moment in time.</p>
        </section>
        <section class="faq-item">
          <h3 class="faq-question">2. Why?</h3>
          <p class="faq-answer">It makes it easy to share and compare recommendation feeds without screen recordings or manual copy/paste.</p>
        </section>
      </footer>
    </main>
    <script>
      (function () {
        const fallbackSets = {
          video: ["maxresdefault", "sddefault", "hq720", "hqdefault", "mqdefault"],
          short: ["oar2", "oar1", "maxresdefault", "sddefault", "hq720", "hqdefault", "mqdefault"],
        };

        function applyFallback(image) {
          const videoHash = image.dataset.videoHash;
          const kind = image.dataset.thumbKind === "short" ? "short" : "video";
          const candidates = fallbackSets[kind];
          if (!videoHash || !Array.isArray(candidates) || candidates.length === 0) {
            return;
          }

          let index = 0;
          function setCandidate() {
            if (index >= candidates.length) {
              return;
            }
            image.src = "https://i.ytimg.com/vi/" + videoHash + "/" + candidates[index] + ".jpg";
            index += 1;
          }

          image.addEventListener("error", setCandidate);
          image.addEventListener("load", function () {
            if (image.naturalWidth > 200 || index >= candidates.length) {
              return;
            }
            setCandidate();
          });

          setCandidate();
        }

        const thumbnails = document.querySelectorAll("img.thumb-image[data-video-hash]");
        for (const image of thumbnails) {
          applyFallback(image);
        }
      })();
    </script>
  </body>
</html>`;
}
