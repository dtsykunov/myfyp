from __future__ import annotations

from datetime import datetime
import html

from for_us_shared.formatting import (
    format_compact_views as _format_compact_views,
    format_relative_time as _format_relative_time,
    format_snapshot_taken_at as _format_snapshot_taken_at,
    to_utc as _to_utc,
)
from for_us_shared.models import RecommendationItem, StoredSnapshot


def render_home_html(userscript_url: str) -> str:
    escaped_userscript_url = html.escape(userscript_url)
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700&display=swap" rel="stylesheet">
    <title>myfyp (my for you page) by dtsykunov</title>
    <style>
      :root {{
        --bg: #0f0f0f;
        --text: #f1f1f1;
        --muted: #aaaaaa;
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, sans-serif;
      }}

      main {{
        max-width: 1100px;
        margin: 0 auto;
        padding: 20px;
      }}

      .top-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 0 12px;
      }}

      .brand-logo {{
        width: 29px;
        height: 20px;
        flex-shrink: 0;
      }}

      .brand-logo-link {{
        display: inline-flex;
      }}

      .brand-logo svg {{
        width: 29px;
        height: 20px;
        display: block;
      }}

      h1 {{
        margin: 0;
        font-size: 28px;
      }}

      .title-link {{
        color: #2c9cd3;
        text-decoration: underline;
        font-family: "Zen Kaku Gothic New", sans-serif;
        letter-spacing: .01em;
        font-weight: 300;
        font-style: italic;
        font-optical-sizing: auto;
        text-rendering: optimizeLegibility;
      }}

      .page-description {{
        margin: 0 0 10px;
        color: #c6c6c6;
        font-size: 14px;
        line-height: 1.45;
      }}

      .card {{
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 14px;
        padding: 18px;
        background: #181818;
      }}

      .section-title {{
        margin: 0 0 12px;
        font-size: 20px;
      }}

      .steps {{
        margin: 0;
        padding-left: 20px;
        line-height: 1.6;
      }}

      .steps code {{
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }}

      .userscript-link {{
        color: #8ab4ff;
        word-break: break-all;
      }}

      .privacy-footer {{
        margin-top: 18px;
        text-align: center;
      }}

      .privacy-link {{
        color: #8ab4ff;
        font-size: 13px;
        text-decoration: none;
      }}

      .privacy-link:hover {{
        text-decoration: underline;
      }}
    </style>
  </head>
  <body>
    <main>
      <header class="top-header">
        <a class="brand-logo-link" href="/" aria-label="Open homepage">
          <span class="brand-logo" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" width="29" height="20" viewBox="0 0 29 20" focusable="false" aria-hidden="true">
            <path d="M14.4848 20C14.4848 20 23.5695 20 25.8229 19.4C27.0917 19.06 28.0459 18.08 28.3808 16.87C29 14.65 29 9.98 29 9.98C29 9.98 29 5.34 28.3808 3.14C28.0459 1.9 27.0917 0.94 25.8229 0.61C23.5695 0 14.4848 0 14.4848 0C14.4848 0 5.42037 0 3.17711 0.61C1.9286 0.94 0.954148 1.9 0.59888 3.14C0 5.34 0 9.98 0 9.98C0 9.98 0 14.65 0.59888 16.87C0.954148 18.08 1.9286 19.06 3.17711 19.4C5.42037 20 14.4848 20 14.4848 20Z" fill="#FF0033"></path>
            <path d="M19 10L11.5 5.75V14.25L19 10Z" fill="#fff"></path>
          </svg>
          </span>
        </a>
        <h1>myfyp (my for you page) by <a class="title-link" href="https://dtsykunov.com/" target="_blank" rel="noopener noreferrer">dtsykunov</a></h1>
      </header>
      <p class="page-description">Share a personal YouTube recommendation page snapshot with a temporary link.</p>
      <section class="card">
        <h2 class="section-title">Install and Use</h2>
        <ol class="steps">
          <li>Install Tampermonkey (or another userscript manager).</li>
          <li>Open and install the userscript: <a class="userscript-link" href="{escaped_userscript_url}">{escaped_userscript_url}</a>.</li>
          <li>Open <code>https://www.youtube.com/</code>.</li>
          <li>From Tampermonkey menu, run <code>For Us Page: Upload Snapshot</code>, or run <code>window.forUsPage.uploadLatestSnapshot()</code> in browser console.</li>
          <li>Open the returned snapshot link to view the rendered page.</li>
        </ol>
      </section>
      <footer class="privacy-footer">
        <a class="privacy-link" href="/privacy">Privacy Notice</a>
      </footer>
    </main>
  </body>
</html>
"""


def render_privacy_html() -> str:
    return """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700&display=swap" rel="stylesheet">
    <title>myfyp Privacy Notice</title>
    <style>
      :root {
        --bg: #0f0f0f;
        --text: #f1f1f1;
        --muted: #aaaaaa;
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, sans-serif;
      }

      main {
        max-width: 900px;
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
        flex-shrink: 0;
      }

      .brand-logo svg {
        width: 29px;
        height: 20px;
        display: block;
      }

      .brand-logo-link {
        display: inline-flex;
      }

      .brand-title {
        margin: 0 0 16px;
        font-size: 28px;
      }

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

      h2 {
        margin: 22px 0 8px;
        font-size: 20px;
      }

      p, li {
        color: #d0d0d0;
        line-height: 1.55;
      }

      .muted {
        color: var(--muted);
        font-size: 13px;
      }

      .privacy-footer {
        margin-top: 22px;
        text-align: center;
      }

      .privacy-link {
        color: #8ab4ff;
        font-size: 13px;
        text-decoration: none;
      }

      .privacy-link:hover {
        text-decoration: underline;
      }
    </style>
  </head>
  <body>
    <main>
      <header class="top-header">
        <a class="brand-logo-link" href="/" aria-label="Open homepage">
          <span class="brand-logo" aria-hidden="true">
            <svg xmlns="http://www.w3.org/2000/svg" width="29" height="20" viewBox="0 0 29 20" focusable="false" aria-hidden="true">
              <path d="M14.4848 20C14.4848 20 23.5695 20 25.8229 19.4C27.0917 19.06 28.0459 18.08 28.3808 16.87C29 14.65 29 9.98 29 9.98C29 9.98 29 5.34 28.3808 3.14C28.0459 1.9 27.0917 0.94 25.8229 0.61C23.5695 0 14.4848 0 14.4848 0C14.4848 0 5.42037 0 3.17711 0.61C1.9286 0.94 0.954148 1.9 0.59888 3.14C0 5.34 0 9.98 0 9.98C0 9.98 0 14.65 0.59888 16.87C0.954148 18.08 1.9286 19.06 3.17711 19.4C5.42037 20 14.4848 20 14.4848 20Z" fill="#FF0033"></path>
              <path d="M19 10L11.5 5.75V14.25L19 10Z" fill="#fff"></path>
            </svg>
          </span>
        </a>
        <h1 class="brand-title">myfyp (my for you page) by <a class="title-link" href="https://dtsykunov.com/" target="_blank" rel="noopener noreferrer">dtsykunov</a></h1>
      </header>
      <h2>Privacy Notice</h2>
      <p>This service stores a temporary snapshot of a user's YouTube recommendations so it can be shared by link.</p>

      <h2>What Data Is Stored</h2>
      <ul>
        <li>Video and Shorts identifiers and parsed metadata submitted by the userscript.</li>
        <li>Snapshot creation timestamp and optional source page URL.</li>
      </ul>

      <h2>Retention</h2>
      <p>Snapshots are automatically deleted after 7 days.</p>

      <h2>Removal</h2>
      <p>Each created snapshot includes a private remove link that can immediately delete it.</p>

      <h2>Purpose</h2>
      <p>Data is used only to render the shared snapshot page and is not used for advertising.</p>

      <p class="muted">Last updated: February 17, 2026</p>
      <footer class="privacy-footer">
        <a class="privacy-link" href="/privacy">Privacy Notice</a>
      </footer>
    </main>
  </body>
</html>
"""


def render_snapshot_html(snapshot: StoredSnapshot) -> str:
    metadata_reference_time = _resolve_metadata_reference_time(snapshot)
    videos = _render_video_grid(snapshot.payload.videos, metadata_reference_time)
    shorts = _render_shorts_grid(snapshot.payload.shorts, metadata_reference_time)
    escaped_hash = html.escape(snapshot.hash)
    escaped_taken_at = html.escape(_format_snapshot_taken_at(metadata_reference_time))
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700&display=swap" rel="stylesheet">
    <title>myfyp (my for you page) by dtsykunov - {escaped_hash}</title>
    <style>
      :root {{
        --bg: #0f0f0f;
        --card: #181818;
        --text: #f1f1f1;
        --muted: #aaaaaa;
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, sans-serif;
      }}

      main {{
        max-width: 2400px;
        margin: 0 auto;
        padding: 20px;
      }}

      .top-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 0 12px;
      }}

      .brand-logo {{
        width: 29px;
        height: 20px;
        flex-shrink: 0;
      }}

      .brand-logo-link {{
        display: inline-flex;
      }}

      .brand-logo svg {{
        width: 29px;
        height: 20px;
        display: block;
      }}

      h1 {{
        margin: 0;
        font-size: 28px;
      }}

      .title-link {{
        color: #2c9cd3;
        text-decoration: underline;
        font-family: "Zen Kaku Gothic New", sans-serif;
        letter-spacing: .01em;
        font-weight: 300;
        font-style: italic;
        font-optical-sizing: auto;
        text-rendering: optimizeLegibility;
      }}

      .title-link:hover {{
        text-decoration: underline;
      }}

      .meta {{
        margin: 0;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.4;
      }}

      .meta-stack {{
        margin: 0 0 24px;
        display: grid;
        gap: 2px;
      }}

      .page-description {{
        margin: 0 0 6px;
        color: #c6c6c6;
        font-size: 14px;
        line-height: 1.45;
      }}

      .section-title {{
        margin: 24px 0 12px;
        font-size: 22px;
      }}

      .shorts-section-title {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
      }}

      .shorts-icon {{
        width: 24px;
        height: 24px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }}

      .shorts-icon svg {{
        width: 24px;
        height: 24px;
        display: block;
      }}

      .videos-grid {{
        display: grid;
        grid-template-columns: repeat(6, 365px);
        gap: 16px;
        justify-content: center;
      }}

      .shorts-grid {{
        display: grid;
        grid-template-columns: repeat(6, 365px);
        gap: 16px;
        justify-content: center;
      }}

      .video-card {{
        width: 365px;
        min-height: 305px;
        background: var(--card);
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid transparent;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition:
          transform 250ms ease,
          box-shadow 250ms ease,
          border-color 250ms ease;
      }}

      .video-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.18);
        border-color: rgba(255, 255, 255, 0.12);
      }}

      .short-card {{
        width: 365px;
        min-height: 547px;
        background: var(--card);
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid transparent;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition:
          transform 250ms ease,
          box-shadow 250ms ease,
          border-color 250ms ease;
      }}

      .short-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.18);
        border-color: rgba(255, 255, 255, 0.12);
      }}

      .thumb {{
        display: block;
      }}

      .video-card .thumb {{
        width: 365px;
        aspect-ratio: 16 / 9;
      }}

      .short-card .thumb {{
        width: 365px;
        aspect-ratio: 3 / 4;
      }}

      .video-card .thumb img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }}

      .short-card .thumb img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }}

      .title {{
        margin: 0;
        font-size: 14px;
        line-height: 1.25;
        color: var(--text);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }}

      .empty {{
        color: var(--muted);
      }}

      .short-card .card-body {{
        padding: 10px 12px;
      }}

      .video-card .card-body {{
        padding: 12px;
      }}

      .meta-line {{
        margin-top: 6px;
        color: var(--muted);
        font-size: 12px;
        line-height: 1.25;
      }}

      .card-meta {{
        display: flex;
        gap: 12px;
        align-items: flex-start;
      }}

      .meta-text {{
        display: flex;
        flex-direction: column;
        min-width: 0;
        flex: 1;
      }}

      .video-title {{
        margin: 0 0 6px;
        font-size: 14px;
        font-weight: 600;
        line-height: 1.3;
        color: var(--text);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }}

      .channel-line {{
        color: var(--muted);
        font-size: 12px;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}

      .channel-row {{
        margin-top: 2px;
        color: var(--muted);
        font-size: 12px;
        line-height: 1.3;
      }}

      .channel-avatar {{
        width: 36px;
        height: 36px;
        border-radius: 999px;
        object-fit: cover;
        flex-shrink: 0;
      }}

      .channel-avatar-placeholder {{
        width: 36px;
        height: 36px;
        border-radius: 999px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #2a2a2a;
        color: #9f9f9f;
        font-size: 14px;
      }}

      .channel-line a {{
        color: inherit;
        text-decoration: none;
      }}

      .channel-line a:hover {{
        text-decoration: underline;
      }}

      .faq-footer {{
        margin-top: 36px;
        padding-top: 18px;
        border-top: 1px solid rgba(255, 255, 255, 0.12);
      }}

      .faq-title {{
        margin: 0 0 10px;
        font-size: 18px;
      }}

      .faq-item {{
        margin: 0 0 12px;
      }}

      .faq-question {{
        margin: 0 0 4px;
        font-size: 14px;
        font-weight: 600;
        color: var(--text);
      }}

      .faq-answer {{
        margin: 0;
        font-size: 13px;
        line-height: 1.45;
        color: var(--muted);
      }}

      .privacy-link {{
        margin-top: 4px;
        display: inline-block;
        color: #8ab4ff;
        font-size: 13px;
        text-decoration: none;
      }}

      .privacy-link:hover {{
        text-decoration: underline;
      }}

      @media (max-width: 2280px) {{
        .videos-grid {{
          grid-template-columns: repeat(5, 365px);
        }}
        .shorts-grid {{
          grid-template-columns: repeat(5, 365px);
        }}
      }}

      @media (max-width: 1900px) {{
        .videos-grid {{
          grid-template-columns: repeat(4, 365px);
        }}
        .shorts-grid {{
          grid-template-columns: repeat(4, 365px);
        }}
      }}

      @media (max-width: 1520px) {{
        .videos-grid {{
          grid-template-columns: repeat(3, 365px);
        }}
        .shorts-grid {{
          grid-template-columns: repeat(3, 365px);
        }}
      }}

      @media (max-width: 1140px) {{
        .videos-grid {{
          grid-template-columns: repeat(2, 365px);
        }}
        .shorts-grid {{
          grid-template-columns: repeat(2, 365px);
        }}
      }}

      @media (max-width: 760px) {{
        .videos-grid {{
          grid-template-columns: repeat(1, minmax(0, 1fr));
        }}

        .shorts-grid {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
        }}

        .video-card {{
          width: 100%;
        }}

        .video-card .thumb {{
          width: 100%;
        }}

        .short-card {{
          width: 100%;
          min-height: 0;
        }}

        .short-card .thumb {{
          width: 100%;
        }}

        .short-card .card-body {{
          padding: 10px 8px;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header class="top-header">
        <a class="brand-logo-link" href="/" aria-label="Open homepage">
          <span class="brand-logo" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" width="29" height="20" viewBox="0 0 29 20" focusable="false" aria-hidden="true">
            <path d="M14.4848 20C14.4848 20 23.5695 20 25.8229 19.4C27.0917 19.06 28.0459 18.08 28.3808 16.87C29 14.65 29 9.98 29 9.98C29 9.98 29 5.34 28.3808 3.14C28.0459 1.9 27.0917 0.94 25.8229 0.61C23.5695 0 14.4848 0 14.4848 0C14.4848 0 5.42037 0 3.17711 0.61C1.9286 0.94 0.954148 1.9 0.59888 3.14C0 5.34 0 9.98 0 9.98C0 9.98 0 14.65 0.59888 16.87C0.954148 18.08 1.9286 19.06 3.17711 19.4C5.42037 20 14.4848 20 14.4848 20Z" fill="#FF0033"></path>
            <path d="M19 10L11.5 5.75V14.25L19 10Z" fill="#fff"></path>
          </svg>
          </span>
        </a>
        <h1>myfyp (my for you page) by <a class="title-link" href="https://dtsykunov.com/" target="_blank" rel="noopener noreferrer">dtsykunov</a></h1>
      </header>
      <div class="meta-stack">
        <p class="page-description">Snapshot of a personal YouTube recommendations page captured at a specific moment in time.</p>
        <p class="meta">Taken at: <code>{escaped_taken_at}</code></p>
        <p class="meta">Snapshot hash: <code>{escaped_hash}</code></p>
      </div>
      <h2 class="section-title">Videos</h2>
      {videos}
      <h2 class="section-title shorts-section-title">
        <span class="shorts-icon" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" focusable="false" aria-hidden="true">
            <path d="m19.45,3.88c1.12,1.82.48,4.15-1.42,5.22l-1.32.74.94.41c1.36.58,2.27,1.85,2.35,3.27.08,1.43-.68,2.77-1.97,3.49l-8,4.47c-1.91,1.06-4.35.46-5.48-1.35-1.12-1.82-.48-4.15,1.42-5.22l1.33-.74-.94-.41c-1.36-.58-2.27-1.85-2.35-3.27-.08-1.43.68-2.77,1.97-3.49l8-4.47c1.91-1.06,4.35-.46,5.48,1.35Z" fill="#f03"></path>
            <path d="m10,15l5-3-5-3v6Z" fill="#fff"></path>
          </svg>
        </span>
        <span>Shorts</span>
      </h2>
      {shorts}
      <footer class="faq-footer">
        <h2 class="faq-title">FAQ</h2>
        <section class="faq-item">
          <h3 class="faq-question">1. What is this?</h3>
          <p class="faq-answer">This is a snapshot of one person's YouTube recommendations page at a specific moment.</p>
        </section>
        <section class="faq-item">
          <h3 class="faq-question">2. Why?</h3>
          <p class="faq-answer">To quickly share and compare what YouTube was recommending to someone without requiring account access.</p>
        </section>
        <a class="privacy-link" href="/privacy">Privacy Notice</a>
      </footer>
    </main>
    <script>
      (() => {{
        const THUMBNAIL_CANDIDATES = {{
          video: [
            "maxresdefault.jpg",
            "sddefault.jpg",
            "hq720.jpg",
            "hqdefault.jpg",
            "mqdefault.jpg"
          ],
          short: [
            "oar2.jpg",
            "oar1.jpg",
            "maxresdefault.jpg",
            "sddefault.jpg",
            "hq720.jpg",
            "hqdefault.jpg",
            "mqdefault.jpg"
          ]
        }};
        const MIN_WIDTH = {{ video: 300, short: 180 }};

        const buildThumbnailUrl = (videoHash, fileName) =>
          `https://i.ytimg.com/vi/${{encodeURIComponent(videoHash)}}/${{fileName}}`;

        const attachFallback = (image) => {{
          const videoHash = image.dataset.videoHash || "";
          if (!videoHash) {{
            return;
          }}

          const thumbKind = image.dataset.thumbKind === "short" ? "short" : "video";
          const candidates = THUMBNAIL_CANDIDATES[thumbKind].map((name) =>
            buildThumbnailUrl(videoHash, name)
          );
          const minWidth = MIN_WIDTH[thumbKind];
          let candidateIndex = -1;

          const cleanup = () => {{
            image.removeEventListener("load", onLoad);
            image.removeEventListener("error", onError);
          }};

          const tryNext = () => {{
            candidateIndex += 1;
            if (candidateIndex >= candidates.length) {{
              cleanup();
              return;
            }}
            image.src = candidates[candidateIndex];
          }};

          const onLoad = () => {{
            if (image.naturalWidth > 0 && image.naturalWidth < minWidth) {{
              tryNext();
              return;
            }}
            cleanup();
          }};

          const onError = () => {{
            tryNext();
          }};

          image.addEventListener("load", onLoad);
          image.addEventListener("error", onError);
          tryNext();
        }};

        const images = document.querySelectorAll("img.thumb-image[data-video-hash]");
        images.forEach((image) => attachFallback(image));
      }})();
    </script>
  </body>
</html>
"""


def _render_video_grid(items: list[RecommendationItem], metadata_reference_time: datetime) -> str:
    if not items:
        return '<p class="empty">No videos.</p>'

    list_items: list[str] = []
    for item in items:
        escaped_hash = html.escape(item.video_hash)
        escaped_title = html.escape(item.title)
        href = f"https://www.youtube.com/watch?v={escaped_hash}"
        thumb = f"https://i.ytimg.com/vi/{escaped_hash}/hqdefault.jpg"
        list_items.append(
            (
                '<article class="video-card">'
                f'<a class="thumb" href="{href}" target="_blank" rel="noopener noreferrer">'
                f'<img class="thumb-image" src="{thumb}" alt="{escaped_title} thumbnail" loading="lazy" decoding="async" data-video-hash="{escaped_hash}" data-thumb-kind="video">'
                "</a>"
                '<div class="card-body">'
                f"{_render_video_card_metadata(item, metadata_reference_time)}"
                "</div>"
                "</article>"
            )
        )
    return f'<section class="videos-grid">{"".join(list_items)}</section>'


def _render_shorts_grid(items: list[RecommendationItem], metadata_reference_time: datetime) -> str:
    if not items:
        return '<p class="empty">No shorts.</p>'

    list_items: list[str] = []
    for item in items:
        escaped_hash = html.escape(item.video_hash)
        escaped_title = html.escape(item.title)
        href = f"https://www.youtube.com/shorts/{escaped_hash}"
        thumb = f"https://i.ytimg.com/vi/{escaped_hash}/hqdefault.jpg"
        list_items.append(
            (
                '<article class="short-card">'
                f'<a class="thumb" href="{href}" target="_blank" rel="noopener noreferrer">'
                f'<img class="thumb-image" src="{thumb}" alt="{escaped_title} short thumbnail" loading="lazy" decoding="async" data-video-hash="{escaped_hash}" data-thumb-kind="short">'
                "</a>"
                '<div class="card-body">'
                f'<h3 class="title">{escaped_title}</h3>'
                f"{_render_short_card_metadata(item, metadata_reference_time)}"
                "</div>"
                "</article>"
            )
        )
    return f'<section class="shorts-grid">{"".join(list_items)}</section>'


def _render_video_card_metadata(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    title_html = html.escape(item.title)
    avatar_html = _render_channel_avatar(item, include_fallback=True)
    channel_html = _render_channel_name(item, include_fallback=True)
    stats_text = _render_stats_text(item, metadata_reference_time)
    stats_html = f'<div class="channel-row">{html.escape(stats_text)}</div>' if stats_text else ""
    return (
        '<div class="card-meta">'
        f"{avatar_html}"
        '<div class="meta-text">'
        f'<h3 class="video-title">{title_html}</h3>'
        f'<div class="channel-line">{channel_html}</div>'
        f"{stats_html}"
        "</div>"
        "</div>"
    )


def _render_short_card_metadata(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    channel_html = _render_channel_name(item, include_fallback=False)
    stats_html = _render_stats_line(item, metadata_reference_time)
    if not channel_html:
        return stats_html
    return f'<div class="channel-line">{channel_html}</div>{stats_html}'


def _render_channel_name(item: RecommendationItem, *, include_fallback: bool) -> str:
    if item.channel_name is None and item.channel_link is None:
        if not include_fallback:
            return ""
        return html.escape("Unknown channel")
    name_source = item.channel_name or _channel_name_from_link(item.channel_link) or "Unknown channel"
    name = html.escape(name_source)
    name_html = name
    if item.channel_link is not None:
        escaped_link = html.escape(str(item.channel_link))
        name_html = f'<a href="{escaped_link}" target="_blank" rel="noopener noreferrer">{name}</a>'
    return name_html


def _render_channel_avatar(item: RecommendationItem, *, include_fallback: bool) -> str:
    if item.channel_avatar is not None:
        escaped_avatar = html.escape(str(item.channel_avatar))
        avatar_label = html.escape(item.channel_name or "Channel")
        return f'<img class="channel-avatar" src="{escaped_avatar}" alt="{avatar_label} avatar" loading="lazy">'
    if include_fallback:
        return '<span class="channel-avatar-placeholder" aria-hidden="true">?</span>'
    return ""


def _channel_name_from_link(channel_link: object) -> str | None:
    if channel_link is None:
        return None
    channel_link_text = str(channel_link).rstrip("/")
    if not channel_link_text:
        return None
    last_segment = channel_link_text.rsplit("/", maxsplit=1)[-1]
    if not last_segment:
        return None
    return last_segment


def _render_stats_line(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    stats_text = _render_stats_text(item, metadata_reference_time)
    if not stats_text:
        return ""
    return f'<div class="meta-line">{html.escape(stats_text)}</div>'


def _render_stats_text(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    parts: list[str] = []
    if item.view_count is not None:
        parts.append(_format_compact_views(item.view_count))
    if item.published_at is not None:
        parts.append(_format_relative_time(item.published_at, metadata_reference_time))
    return " • ".join(parts)


def _resolve_metadata_reference_time(snapshot: StoredSnapshot) -> datetime:
    reference_time = snapshot.payload.captured_at or snapshot.created_at
    return _to_utc(reference_time)
