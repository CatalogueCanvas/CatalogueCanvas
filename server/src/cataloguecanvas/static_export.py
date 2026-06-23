"""Render a public portfolio into a self-contained static site (zip).

The exported folder has no dependency on the running server: HTML with inlined
CSS, the webp previews under assets/, and a README with hosting instructions.
Only the webp previews are bundled (the public deck shows previews only).
"""
from __future__ import annotations

import html
import os
import re
import zipfile
from pathlib import Path
from typing import Any

import markdown as md

# Order matters: base deck styles first, then the scoped theme skins. Mirrors
# web/src/portfolio/deck.css. Token :root block ported from web/src/index.css.
_CSS = r"""
:root{color-scheme:light;
--font-head:'Helvetica Neue',Helvetica,Arial,sans-serif;
--font-body:'Helvetica Neue',Helvetica,Arial,sans-serif;
--font-mono:'IBM Plex Mono',ui-monospace,'SFMono-Regular',monospace;
--head-weight:700;--head-tracking:-0.02em;
--radius-thumb:6px;--radius-pill:9999px;
--ease:cubic-bezier(0.2,0,0,1);--speed:160ms;
--bg:oklch(0.985 0.002 95);--surface:oklch(1 0 0);--surface-2:oklch(0.965 0.003 95);
--border:oklch(0.9 0.004 95);--border-strong:oklch(0.74 0.005 95);
--text:oklch(0.2 0.004 95);--text-sec:oklch(0.46 0.004 95);--text-ter:oklch(0.62 0.004 95);
--accent:oklch(0.6 0.21 30);--accent-contrast:oklch(0.99 0 0);--shadow-lift:none;}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
.cc-mono{font-family:var(--font-mono)}
.cc-tag{display:inline-block;padding:3px 9px;border:1px solid var(--border);border-radius:var(--radius-pill);font-size:12px;font-family:var(--font-mono);color:var(--text-sec)}
.cc-deck{background:var(--bg);color:var(--text);font-family:var(--font-body)}
.cc-deck__sec{padding:clamp(48px,9vw,120px) clamp(24px,7vw,110px);border-bottom:1px solid var(--border)}
.cc-deck__cover{min-height:78vh;display:flex;flex-direction:column;justify-content:center;background:var(--text);color:var(--bg);border-bottom:0}
.cc-deck__cover .cc-deck__kicker{color:color-mix(in oklab,var(--bg) 65%,var(--text))}
.cc-deck__kicker{font-family:var(--font-mono);font-size:12px;letter-spacing:0.22em;text-transform:uppercase;color:var(--text-ter);margin:0 0 22px}
.cc-deck__title{font-family:var(--font-head);font-weight:var(--head-weight);letter-spacing:var(--head-tracking);line-height:0.98;font-size:clamp(44px,8vw,110px);margin:0;max-width:16ch;text-wrap:balance}
.cc-deck__desc{font-size:clamp(17px,1.7vw,22px);max-width:54ch;margin:28px 0 0;line-height:1.5}
.cc-deck__desc>:first-child{margin-top:0}.cc-deck__desc>:last-child{margin-bottom:0}
.cc-deck__cover .cc-deck__desc{color:color-mix(in oklab,var(--bg) 78%,var(--text))}
.cc-deck__cover-foot{display:flex;justify-content:space-between;margin-top:clamp(40px,8vw,90px);font-family:var(--font-mono);font-size:12px;letter-spacing:0.06em;color:color-mix(in oklab,var(--bg) 60%,var(--text))}
.cc-deck__indexhead{display:flex;align-items:baseline;gap:16px;margin-bottom:40px}
.cc-deck__indexhead h2{font-family:var(--font-head);font-weight:var(--head-weight);font-size:clamp(24px,3vw,34px);margin:0;letter-spacing:var(--head-tracking)}
.cc-deck__indexgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:clamp(20px,3vw,40px)}
.cc-deck__idxitem{text-decoration:none;color:inherit}
.cc-deck__idxnum{font-family:var(--font-mono);font-size:12px;color:var(--text-ter)}
.cc-deck__idxitem .cc-thumb{margin:8px 0}
.cc-deck__idxitem .cc-thumb img{width:100%;height:auto;object-fit:contain}
.cc-deck__idxtitle{font-family:var(--font-head);font-weight:var(--head-weight);font-size:16px;letter-spacing:var(--head-tracking)}
.cc-deck__art{display:grid;grid-template-columns:1.5fr 1fr;gap:clamp(28px,5vw,72px);align-items:center}
.cc-deck__plate{aspect-ratio:4/3;border:1px solid var(--border);border-radius:var(--radius-thumb);background:repeating-linear-gradient(45deg,color-mix(in oklab,var(--text) 5%,var(--surface)) 0 12px,transparent 12px 24px),color-mix(in oklab,var(--accent) 5%,var(--surface-2));display:grid;place-items:center;box-shadow:var(--shadow-lift)}
.cc-deck__plate img{max-width:100%;max-height:100%;object-fit:contain}
.cc-deck__plate span{font-family:var(--font-mono);font-size:12px;color:var(--text-ter)}
.cc-deck__caption .cc-deck__kicker{margin-bottom:14px}
.cc-deck__caption h3{font-family:var(--font-head);font-weight:var(--head-weight);letter-spacing:var(--head-tracking);font-size:clamp(26px,3.4vw,44px);margin:0 0 6px;line-height:1.04}
.cc-deck__caption .cc-mono{color:var(--text-ter);font-size:12px}
.cc-deck__caption p{color:var(--text-sec);font-size:16px;line-height:1.6;margin:18px 0;max-width:46ch}
.cc-deck__tags{display:flex;flex-wrap:wrap;gap:6px}
.cc-deck__art--rev{direction:rtl}.cc-deck__art--rev>*{direction:ltr}
.cc-deck__colo{display:grid;grid-template-columns:1fr 1fr;gap:clamp(28px,5vw,72px)}
.cc-deck__colo h2{font-family:var(--font-head);font-weight:var(--head-weight);font-size:clamp(24px,3vw,34px);margin:0 0 16px;letter-spacing:var(--head-tracking)}
.cc-deck__colo p{color:var(--text-sec);line-height:1.6;max-width:48ch}
.cc-deck__worklist{list-style:none;margin:0;padding:0;border-top:1px solid var(--border)}
.cc-deck__worklist li{display:flex;gap:14px;padding:12px 0;border-bottom:1px solid var(--border);font-size:15px}
.cc-deck__worklist .cc-mono{color:var(--text-ter);font-size:12px;min-width:28px}
@media(max-width:760px){.cc-deck__art,.cc-deck__colo{grid-template-columns:1fr}.cc-deck__art--rev{direction:ltr}.cc-deck__follow{display:none}}

/* KINETIC */
.cc-deck[data-portfolio-style="kinetic"]{--bg:oklch(0.155 0.004 110);--surface:oklch(0.19 0.004 110);--surface-2:oklch(0.225 0.005 110);--border:oklch(0.3 0.005 110);--border-strong:oklch(0.46 0.006 110);--text:oklch(0.95 0.006 110);--text-sec:oklch(0.7 0.006 110);--text-ter:oklch(0.54 0.006 110);--accent:oklch(0.86 0.19 124);--accent-contrast:oklch(0.16 0.03 124);--font-head:'Newsreader',Georgia,serif;--font-body:'Albert Sans',system-ui,sans-serif;--head-weight:600;--radius-thumb:0px;color-scheme:dark}
.cc-deck[data-portfolio-style="kinetic"] .cc-deck__sec{padding:clamp(80px,14vw,220px) clamp(28px,9vw,150px)}
.cc-deck[data-portfolio-style="kinetic"] .cc-deck__cover{background:var(--bg);color:var(--text);min-height:94vh;justify-content:flex-end;border-bottom:1px solid var(--border)}
.cc-deck[data-portfolio-style="kinetic"] .cc-deck__cover .cc-deck__kicker{color:var(--accent)}
.cc-deck[data-portfolio-style="kinetic"] .cc-deck__title{font-size:clamp(54px,13vw,184px);letter-spacing:-0.035em;line-height:0.9;max-width:13ch;font-style:normal}
.cc-deck[data-portfolio-style="kinetic"] .cc-deck__cover .cc-deck__desc{color:var(--text-sec);max-width:38ch}
.cc-deck[data-portfolio-style="kinetic"] .cc-deck__caption h3,.cc-deck[data-portfolio-style="kinetic"] .cc-deck__colo h2,.cc-deck[data-portfolio-style="kinetic"] .cc-deck__indexhead h2,.cc-deck[data-portfolio-style="kinetic"] .cc-deck__krow-title{font-style:normal}
.cc-deck__marquee{padding:0!important;overflow:hidden;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
.cc-deck__marquee-track{display:flex;width:max-content;white-space:nowrap;animation:cc-marq 42s linear infinite}
.cc-deck__marquee-track>span{display:inline-flex;align-items:center;font-family:var(--font-mono);font-size:clamp(13px,1.5vw,18px);letter-spacing:0.18em;text-transform:uppercase;padding:22px clamp(14px,2vw,28px) 22px 0}
.cc-deck__marquee-track i{color:var(--accent);font-style:normal;padding:0 clamp(14px,2vw,28px)}
@keyframes cc-marq{to{transform:translateX(-50%)}}
@media(prefers-reduced-motion:reduce){.cc-deck__marquee-track{animation:none}}
.cc-deck__kindex{border-top:1px solid var(--border)}
.cc-deck__krow{display:grid;grid-template-columns:auto 1fr auto;align-items:baseline;gap:clamp(16px,3vw,40px);padding:clamp(18px,2.6vw,36px) 0;border-bottom:1px solid var(--border);text-decoration:none;color:inherit;transition:padding-left var(--speed) var(--ease),color var(--speed) var(--ease)}
.cc-deck__krow:hover{padding-left:clamp(12px,2vw,28px);color:var(--accent)}
.cc-deck__krow-num{font-family:var(--font-mono);font-size:13px;color:var(--text-ter)}
.cc-deck__krow:hover .cc-deck__krow-num{color:var(--accent)}
.cc-deck__krow-title{font-family:var(--font-head);font-weight:var(--head-weight);letter-spacing:-0.03em;font-size:clamp(30px,6vw,76px);line-height:0.98}
.cc-deck__krow-meta{font-size:11px;text-transform:uppercase;letter-spacing:0.14em;color:var(--text-ter)}
.cc-deck__follow{position:fixed;z-index:50;width:min(30vw,300px);pointer-events:none;transform:translate(-50%,-50%);opacity:0;transition:opacity 0.25s var(--ease)}
.cc-deck__follow[data-on="1"]{opacity:1}
.cc-deck__followplate{aspect-ratio:4/3;width:100%}

/* LEDGER */
.cc-deck[data-portfolio-style="ledger"]{--bg:oklch(0.96 0.008 95);--surface:oklch(0.99 0.004 95);--surface-2:oklch(0.93 0.008 95);--border:oklch(0.82 0.01 95);--border-strong:oklch(0.5 0.01 95);--text:oklch(0.22 0.008 95);--text-sec:oklch(0.42 0.008 95);--text-ter:oklch(0.56 0.008 95);--accent:oklch(0.48 0.13 255);--accent-contrast:oklch(0.99 0 0);--font-head:'IBM Plex Mono',ui-monospace,monospace;--font-body:'Albert Sans',system-ui,sans-serif;--head-weight:500;--radius-thumb:0px;color-scheme:light}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__sec{padding:clamp(40px,6vw,88px) clamp(24px,6vw,92px)}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__cover{background:var(--bg);color:var(--text);min-height:74vh;justify-content:flex-end;border-bottom:1px solid var(--border-strong)}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__cover .cc-deck__kicker{color:var(--accent)}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__title{font-family:var(--font-head);text-transform:uppercase;font-weight:500;letter-spacing:-0.01em;font-size:clamp(34px,7vw,92px);line-height:1.02;max-width:18ch}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__cover .cc-deck__desc{color:var(--text-sec);max-width:54ch;border-top:1px solid var(--border);margin-top:26px;padding-top:18px}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__cover-foot{color:var(--text-ter);border-top:1px solid var(--border);padding-top:14px}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__indexhead h2{font-family:var(--font-head);text-transform:uppercase;font-weight:500;letter-spacing:0;font-size:clamp(17px,2.2vw,24px)}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__idxtitle{font-family:var(--font-head);font-weight:500;font-size:14px;letter-spacing:0}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__plate{border:1px solid var(--border-strong);border-radius:0}
.cc-deck[data-portfolio-style="ledger"] .cc-deck__caption h3{font-family:var(--font-head);text-transform:uppercase;font-weight:500;letter-spacing:-0.01em;font-size:clamp(20px,2.6vw,32px)}
.cc-deck[data-portfolio-style="ledger"] .cc-tag{border-radius:0;border:1px solid var(--border-strong);font-family:var(--font-head)}

/* BRUTALIST */
.cc-deck[data-portfolio-style="brutalist"]{--bg:oklch(0.97 0 0);--surface:oklch(1 0 0);--surface-2:oklch(0.93 0 0);--border:oklch(0.14 0 0);--border-strong:oklch(0.14 0 0);--text:oklch(0.14 0 0);--text-sec:oklch(0.32 0 0);--text-ter:oklch(0.46 0 0);--accent:oklch(0.56 0.24 25);--accent-contrast:oklch(0.99 0 0);--font-head:'Archivo','Helvetica Neue',sans-serif;--font-body:'Archivo',system-ui,sans-serif;--head-weight:800;--radius-thumb:0px;color-scheme:light}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__sec{border-bottom:2px solid var(--border);padding:clamp(40px,7vw,100px) clamp(24px,6vw,96px)}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__cover{background:var(--bg);color:var(--text);min-height:82vh;justify-content:flex-end;border-bottom:2px solid var(--border)}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__cover .cc-deck__kicker{color:var(--accent)}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__title{text-transform:uppercase;letter-spacing:-0.02em;font-size:clamp(48px,11vw,150px);line-height:0.9;max-width:14ch}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__cover .cc-deck__desc{color:var(--text-sec)}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__indexhead h2{text-transform:uppercase}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__idxnum{font-size:22px;font-weight:700;color:var(--text)}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__plate{border:2px solid var(--border);border-radius:0}
.cc-deck[data-portfolio-style="brutalist"] .cc-deck__caption h3{text-transform:uppercase}
.cc-deck[data-portfolio-style="brutalist"] .cc-tag{border-radius:0;border:1.5px solid var(--border)}

/* RISO */
.cc-deck[data-portfolio-style="riso"]{--bg:oklch(0.94 0.022 90);--surface:oklch(0.97 0.015 90);--surface-2:oklch(0.9 0.025 88);--border:oklch(0.8 0.03 85);--border-strong:oklch(0.55 0.04 80);--text:oklch(0.22 0.03 268);--text-sec:oklch(0.4 0.05 268);--text-ter:oklch(0.52 0.05 268);--accent:oklch(0.58 0.2 252);--accent-2:oklch(0.62 0.21 28);--accent-contrast:oklch(0.98 0.01 90);--font-head:'Archivo','Helvetica Neue',sans-serif;--font-body:'Albert Sans',system-ui,sans-serif;--head-weight:800;--radius-thumb:4px;color-scheme:light}
.cc-deck[data-portfolio-style="riso"] .cc-deck__cover{background:radial-gradient(60% 80% at 82% 14%,color-mix(in oklab,var(--accent) 30%,transparent),transparent 60%),radial-gradient(52% 70% at 14% 88%,color-mix(in oklab,var(--accent-2) 26%,transparent),transparent 60%),var(--bg);color:var(--text);min-height:86vh;justify-content:flex-end}
.cc-deck[data-portfolio-style="riso"] .cc-deck__cover .cc-deck__kicker{color:var(--accent-2)}
.cc-deck[data-portfolio-style="riso"] .cc-deck__title{text-transform:uppercase;letter-spacing:-0.02em;font-weight:800;font-size:clamp(48px,11vw,156px);line-height:0.9;max-width:13ch;text-shadow:0.05em 0.05em 0 color-mix(in oklab,var(--accent) 75%,transparent),0.1em 0.1em 0 color-mix(in oklab,var(--accent-2) 55%,transparent)}
.cc-deck[data-portfolio-style="riso"] .cc-deck__cover .cc-deck__desc{color:var(--text-sec)}
.cc-deck[data-portfolio-style="riso"] .cc-deck__caption h3{text-transform:uppercase}
.cc-deck[data-portfolio-style="riso"] .cc-deck__plate{border:1px solid var(--border-strong);border-radius:var(--radius-thumb);background:radial-gradient(circle at 1px 1px,color-mix(in oklab,var(--accent) 55%,transparent) 1px,transparent 1.7px) 0 0/7px 7px,color-mix(in oklab,var(--accent) 10%,var(--surface))}
.cc-deck[data-portfolio-style="riso"] .cc-tag{border-radius:var(--radius-pill);background:color-mix(in oklab,var(--accent) 18%,transparent);border-color:color-mix(in oklab,var(--accent) 45%,transparent);color:var(--text)}
"""

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Albert+Sans:ital,wght@0,400;0,500;0,600;1,400&'
    'family=Archivo:ital,wght@0,400;0,700;0,800;1,400&'
    'family=IBM+Plex+Mono:wght@400;500&'
    'family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&display=swap">'
)

_CAPABILITIES = [
    "Archival Systems", "Type Specimens", "Reference Libraries",
    "Editorial Design", "Cataloguing", "Open Data", "Wayfinding",
]

_FOLLOW_JS = (
    "<script>(function(){var f=document.querySelector('.cc-deck__follow');"
    "if(!f)return;document.querySelectorAll('.cc-deck__krow').forEach(function(r){"
    "r.addEventListener('mouseenter',function(){var s=r.getAttribute('data-src');"
    "var img=f.querySelector('img');if(s&&img){img.src=s;}f.setAttribute('data-on','1');});});"
    "var k=document.querySelector('.cc-deck__kindex');"
    "if(k)k.addEventListener('mouseleave',function(){f.setAttribute('data-on','0');});"
    "window.addEventListener('mousemove',function(e){f.style.left=e.clientX+'px';f.style.top=e.clientY+'px';});"
    "})();</script>"
)

README = """\
This folder is a self-contained static portfolio. Open index.html in a browser,
or host the whole folder on any static web host — no server required.

Recommended free static hosts:
  - Codeberg Pages   : push this folder to a repo and enable Pages
  - GitHub Pages      : push to a repo, serve from /docs or a gh-pages branch
  - Netlify Drop       : drag this folder onto https://app.netlify.com/drop
  - Cloudflare Pages  : connect a repo or upload directly

All asset paths are relative, so it works from any sub-path.
Generated with CatalogueCanvas.
"""


def _md(text: str) -> str:
    return md.markdown(text or "", extensions=["extra"])


def _e(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _slugify_asset(item_id: str, src_name: str) -> str:
    ext = Path(src_name).suffix or ".webp"
    safe = re.sub(r"[^a-zA-Z0-9_-]", "-", item_id)
    return f"{safe}{ext}"


def _within(root: Path, candidate: Path) -> bool:
    """True if candidate resolves to a file under root (symlink-safe)."""
    resolved = candidate.resolve()
    return resolved != root and str(resolved).startswith(str(root) + os.sep)


def build_static_site(
    portfolio: dict[str, Any],
    items: list[dict[str, Any]],
    library_roots: dict[str, Path],
    zip_path: Path,
) -> None:
    """Write a self-contained portfolio site to zip_path.

    items: enriched (public) item dicts. library_roots maps library_id -> the
    resolved storage root for that library, used to locate + safely read previews.
    """
    style = portfolio.get("style") or "ledger"
    title = portfolio.get("title") or "Portfolio"
    slug = portfolio.get("slug") or ""
    desc_html = _md(portfolio.get("description") or "")

    # Resolve preview files and assign relative asset names.
    asset_map: dict[str, tuple[Path, str]] = {}  # item_id -> (source_path, rel_name)
    for it in items:
        lib_id = it.get("library_id")
        preview_path = it.get("preview_path")
        root = library_roots.get(lib_id)
        if not preview_path or root is None:
            continue
        src = (root / preview_path)
        if src.is_symlink() or not src.is_file() or not _within(root, src):
            continue
        rel = f"assets/{_slugify_asset(it['id'], preview_path)}"
        asset_map[it["id"]] = (src, rel)

    body = _render_html(style, title, slug, desc_html, items, asset_map)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", body)
        zf.writestr("README.txt", README)
        for src, rel in asset_map.values():
            zf.write(src, rel)


def _render_html(
    style: str,
    title: str,
    slug: str,
    desc_html: str,
    items: list[dict[str, Any]],
    asset_map: dict[str, tuple[Path, str]],
) -> str:
    total = len(items)
    kinetic = style == "kinetic"

    def asset(item_id: str) -> str | None:
        entry = asset_map.get(item_id)
        return entry[1] if entry else None

    parts: list[str] = []
    parts.append(f'<div class="cc-deck" data-portfolio-style="{_e(style)}">')

    # cover
    parts.append('<section class="cc-deck__sec cc-deck__cover">')
    parts.append(f'<p class="cc-deck__kicker">Portfolio · {total} works</p>')
    parts.append(f'<h1 class="cc-deck__title">{_e(title)}</h1>')
    if desc_html:
        parts.append(f'<div class="cc-deck__desc">{desc_html}</div>')
    parts.append('<div class="cc-deck__cover-foot">'
                 f'<span>CatalogueCanvas</span><span>/p/{_e(slug)}</span></div>')
    parts.append('</section>')

    # kinetic marquee
    if kinetic:
        spans = "".join(f"{_e(c)}<i>/</i>" for c in _CAPABILITIES)
        parts.append('<section class="cc-deck__sec cc-deck__marquee" aria-hidden="true">'
                     '<div class="cc-deck__marquee-track">'
                     f'<span>{spans}</span><span>{spans}</span></div></section>')

    # index
    if kinetic:
        parts.append('<section class="cc-deck__sec"><div class="cc-deck__indexhead">'
                     f'<h2>Selected</h2><span class="cc-mono">{total:02d} works</span></div>'
                     '<div class="cc-deck__kindex">')
        for i, it in enumerate(items):
            src = asset(it["id"]) or ""
            tag0 = it["tags"][0] if it.get("tags") else ""
            parts.append(
                f'<a class="cc-deck__krow" href="#work-{_e(it["id"])}" data-src="{_e(src)}">'
                f'<span class="cc-deck__krow-num">{i + 1:02d}</span>'
                f'<span class="cc-deck__krow-title">{_e(it.get("title"))}</span>'
                f'<span class="cc-deck__krow-meta cc-mono">{_e(tag0)}</span></a>'
            )
        parts.append('</div></section>')
    else:
        per_page = 8
        for page_index in range(0, total, per_page):
            page = items[page_index:page_index + per_page]
            head = "Works" if page_index == 0 else "Works (cont.)"
            parts.append('<section class="cc-deck__sec cc-deck__index">'
                         '<div class="cc-deck__indexhead">'
                         f'<h2>{head}</h2><span class="cc-mono">{_e(slug)}</span></div>'
                         '<div class="cc-deck__indexgrid">')
            for j, it in enumerate(page):
                src = asset(it["id"])
                thumb = (f'<img src="{_e(src)}" alt="{_e(it.get("title"))}">'
                         if src else '<span class="cc-thumb__label">no preview</span>')
                parts.append(
                    '<div class="cc-deck__idxitem">'
                    f'<span class="cc-deck__idxnum">{page_index + j + 1:02d}</span>'
                    f'<div class="cc-thumb">{thumb}</div>'
                    f'<div class="cc-deck__idxtitle">{_e(it.get("title"))}</div></div>'
                )
            parts.append('</div></section>')

    # art plates
    for i, it in enumerate(items):
        src = asset(it["id"])
        wide = bool(it.get("width") and it.get("height") and it["width"] > it["height"])
        cls = "cc-deck__sec cc-deck__art"
        if i % 2 == 1:
            cls += " cc-deck__art--rev"
        if wide:
            cls += " cc-deck__art--wide"
        plate = (f'<img src="{_e(src)}" alt="{_e(it.get("title"))}">' if src else '<span>no preview</span>')
        tags = "".join(f'<span class="cc-tag">{_e(t)}</span>' for t in (it.get("tags") or []))
        note = f'<p>{_e(it.get("note"))}</p>' if it.get("note") else ""
        tagblock = f'<div class="cc-deck__tags">{tags}</div>' if tags else ""
        parts.append(
            f'<section id="work-{_e(it["id"])}" class="{cls}">'
            f'<div class="cc-deck__plate">{plate}</div>'
            '<div class="cc-deck__caption">'
            f'<p class="cc-deck__kicker">Work {i + 1:02d} / {total:02d}</p>'
            f'<h3>{_e(it.get("title"))}</h3>'
            f'<span class="cc-mono">{_e(it["id"])}</span>'
            f'{note}{tagblock}</div></section>'
        )

    # colophon
    worklist = "".join(
        f'<li><span class="cc-mono">{i + 1:02d}</span><span>{_e(it.get("title"))}</span></li>'
        for i, it in enumerate(items)
    )
    parts.append('<section class="cc-deck__sec cc-deck__colo"><div><h2>About this work</h2>'
                 f'{desc_html}<p>A portfolio of {total} works shared via CatalogueCanvas.</p></div>'
                 f'<ul class="cc-deck__worklist">{worklist}</ul></section>')

    # kinetic cursor-follow target
    follow = ""
    if kinetic:
        follow = ('<div class="cc-deck__follow" data-on="0" aria-hidden="true">'
                  '<div class="cc-deck__plate cc-deck__followplate"><img src="" alt=""></div></div>')

    parts.append('</div>')
    parts.append(follow)
    if kinetic:
        parts.append(_FOLLOW_JS)

    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        f"<title>{_e(title)} — CatalogueCanvas</title>"
        f"{_FONTS}<style>{_CSS}</style></head><body>"
        + "".join(parts)
        + "</body></html>"
    )
