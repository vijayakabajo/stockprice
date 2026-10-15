# Frontend — the server-rendered site

The public site lives in the `web/` app. Every page is rendered by Django
templates on the server, complete, in the first response. The design is a
port of the prototype in `Stockprice_pages_prototype/`; the long-form
"Stock Profile Page.html" layout (answer-first sections, takeaways, glossary,
FAQ, sources, byline) is the model for the stock profile.

**The rule everything follows:** all content is in the HTML that `curl`
receives. GPTBot, ClaudeBot and PerplexityBot run no JavaScript, so anything
JavaScript loads is invisible to them. The site's only script (2.7 KB) adds
search suggestions, the theme toggle, auto-submitting filters and the
"on this page" highlight — nothing that carries content.

Contents: [Pages](#pages) · [Structure](#project-structure) ·
[base.html](#basehtml-and-metadata) · [Structured data](#structured-data) ·
[Content rules](#writing-for-ai-citation) · [Crawlers](#crawler-files) ·
[CSS, JS, fonts, images](#css-js-fonts-and-images) ·
[Performance](#performance-and-caching) · [Deploy](#deploy-settings) ·
[Verification checklist](#verification-checklist)

---

## Pages

| URL | Page | Indexed | JSON-LD |
|---|---|---|---|
| `/` | Home: search, coverage stats, browse, largest companies, FAQ | yes | Organization, WebSite, WebPage, FAQPage |
| `/stocks/` | Directory, paginated (`?page=`) | page 1+ unfiltered only | CollectionPage, BreadcrumbList |
| `/stocks/?exchange=&type=&sector=&size=&ordering=&q=` | Filtered directory | `noindex, follow` | same |
| `/stocks/<ticker>/` | Stock profile (common, ADR, SPAC variants) | if `indexable` (not SPAC, active, has description) | WebPage, Corporation, FAQPage, BreadcrumbList |
| `/sectors/`, `/sectors/<slug>/` | Sector index and hubs, paginated | hubs with ≥ 3 companies | CollectionPage, ItemList, FAQPage, BreadcrumbList |
| `/exchanges/`, `/exchanges/<slug>/` | Exchange index and hubs | same | same |
| `/guides/`, `/guides/<slug>/` | Editorial guides (template files) | yes | Article, WebPage, BreadcrumbList |
| `/glossary/` | Glossary, one anchor per term | yes | DefinedTermSet |
| `/about/` | Data sources, methodology, editors (author bios) | yes | AboutPage, Organization |
| `/search/?q=` | Search results; an exact ticker redirects to its profile | `noindex` | — |
| `/robots.txt`, `/sitemap.xml`, `/sitemap-<section>.xml`, `/llms.txt`, `/<indexnow-key>.txt` | Crawler files | — | — |

Profile URLs are lowercase (`/stocks/brk.b/`); any other case 301s to it. The
JSON API under `/api/v1/` is unchanged, and the site is built from the same
payload functions (`market/payloads.py`), so a figure can never differ between
the API and the page.

## Project structure

```
web/
  views.py              one function per page; builds data, copy and PageMeta
  seo.py                PageMeta, title/description fitting, JSON-LD builders
  copy.py               answer sentences, takeaways, FAQs built from facts
  content.py            authors, glossary terms, guide registry + sources
  formatting.py         $45.66B / 18,200 / "22 Sep 2026" formatting
  sitemaps.py           django.contrib.sitemaps classes + index view
  indexnow.py           IndexNow submit; tasks.py runs it after syncs
  context_processors.py site identity and nav for base.html
  templatetags/web.py   filters: cap, num, asof, jsonld, stock_url, monogram...
  management/commands/indexnow_ping.py
  templates/
    base.html           every SEO/meta/JSON-LD block (below)
    404.html  500.html
    partials/           header, footer, breadcrumbs, stock_table, cap_bars, pagination
    components/         faq, sources, quote, stat, author, byline, picture
    pages/              home, directory, stock, hub, sector_index, exchange_index,
                        search, guide (article layout), guide_index, glossary, about
    guides/             one template per guide, extending pages/guide.html
    seo/                robots.txt, llms.txt, sitemap_index.xml
  static/web/           BUILT OUTPUT — do not edit (css/, js/, fonts/, img/)
assets/                 sources for the build: css/*.css, js/site.js
scripts/
  build-assets.mjs      CSS bundle → PurgeCSS → minify; JS minify; fonts
  build-images.mjs      favicon, icons, OG card, guide hero images (AVIF/WebP/PNG)
  verify_site.py        the crawler's-eye verification run (below)
market/payloads.py      page data, shared by the API and the site
core/cache.py           cache_html: per-data-version HTML cache with ETag/304
```

## base.html and metadata

Each view builds a `seo.PageMeta` and passes it as `page`. `base.html` renders
it into overridable blocks:

| Block | Renders |
|---|---|
| `title` | `<title>` — `fit_title()` picks the longest candidate ≤ 60 chars, adding "\| Equity Profiles" when it fits |
| `meta_description` | whole sentences up to 160 chars (`fit_description()`) |
| `canonical` | `<link rel="canonical">`, absolute, from `SITE_URL` |
| `robots` | `index, follow, max-image-preview:large, max-snippet:-1`, or `noindex, follow` |
| `social` (`og_type`, `og_title`, `og_description`) | Open Graph + Twitter Card, image 1200×630, `article:published_time` / `modified_time` |
| `json_ld` | one `<script type="application/ld+json">` holding an `@graph`; `<`, `>` and `&` are escaped so data can never close the tag |
| `breadcrumbs` | visible `<nav><ol>` breadcrumbs; the same list feeds BreadcrumbList |
| `extra_head`, `content`, `islands` | page additions; `islands` is where a page mounts a rich widget (see below) |

`<html lang="en">`, the viewport meta, font preloads, the deferred script and
icons are fixed in the template. The site name, publisher and URL come from
settings (`app/config/site.py`), never from the request.

## Structured data

Built in `web/seo.py`, one graph per page, nodes linked by `@id`.

- **Organization + WebSite** (home; Organization again on /about/): name,
  logo, publisher, `sameAs` from `ORGANIZATION_SAME_AS`.
- **Corporation** (profiles): name, legal name, `tickerSymbol` as
  "Exchange TICKER", employees, address, CIK and FIGI identifiers, EDGAR link.
- **WebPage** with `author`, `datePublished` (when we first listed the
  company), `dateModified` (its last data refresh), `about`/`mainEntity`.
- **Article** (guides): headline, 1200×630 image, author, publisher, dates.
- **FAQPage**, **BreadcrumbList**, **ItemList** (hub rankings),
  **DefinedTermSet** (glossary).

Two deliberate choices:

- **No Product schema.** A stock is not a product with offers or reviews;
  marking it up as one is a structured-data spam signal. Corporation is the
  correct type.
- **FAQPage stays even though** Google shows FAQ rich results only for
  government and health sites since 2023. The markup is still valid, and AI
  answer engines read it. The questions are also visible on the page as
  `<h3>` + `<p>` — not hidden in an accordion.

## Writing for AI citation

`web/copy.py` builds every generated sentence, and the templates enforce the
shape:

1. **Headings are questions** a reader would type: "How big is Alcoa by
   market cap?", "What is a SPAC?".
2. **The first sentence answers it** (`<p class="answer">`), then the detail.
3. **Every section stands alone**: the company is named again in each
   sentence, never "it" or "as mentioned above". An answer engine quotes one
   paragraph, not the page.
4. **Every figure carries its date** ("as of 11 Oct 2026") and the page lists
   its **sources** (`components/sources.html`, numbered and cited as [1]).
5. **Statistics and quotations** have components: `components/stat.html`
   (value, label, dated note) and `components/quote.html` (verbatim quotation
   with publisher and link — never paraphrase inside a blockquote).
6. **Visible author and dates**: a byline under each H1 and an author box with
   bio (`components/author.html`), linked to `/about/#<author>`.
7. **Missing facts drop their sentence.** Nothing is guessed or padded.

To add a guide: write `web/templates/guides/<slug>.html` extending
`pages/guide.html`, add a `Guide(...)` to `web/content.py` with its sources,
run `npm run build:images` for its hero (add an entry in
`scripts/build-images.mjs`), deploy, then `manage.py indexnow_ping --guides`.
Replace the "Research Desk" author with named people with real credentials
when you can: author expertise is one of the strongest trust signals for
finance content.

## Crawler files

- **robots.txt** (`web/views.py`, `templates/seo/robots.txt`): a group per
  crawler — Googlebot, Bingbot, GPTBot, OAI-SearchBot, ChatGPT-User,
  ClaudeBot, Claude-SearchBot, Claude-User, PerplexityBot, Perplexity-User,
  Google-Extended, Applebot(-Extended), DuckDuckBot — each `Allow: /` with
  `/admin/`, `/api/`, `/search/` disallowed, plus the sitemap.
- **sitemap.xml** (`web/sitemaps.py`): an index of `pages`, `guides`,
  `sectors`, `exchanges` and `stocks` (paginated at 10,000). Only indexable
  pages, using the same rules as the robots meta. `lastmod` is the real date
  the data changed: a profile's own refresh, the last reference sync for hubs,
  the edit date for guides.
- **IndexNow** (`web/indexnow.py`): after every company-profile sync,
  `sync_stock_details_task` queues `indexnow_ping_task`, which submits every
  profile refreshed in that run plus the hubs (batches of 10,000) to
  api.indexnow.org, shared by Bing, Yandex, Seznam and Naver. The key is
  served at `/<INDEXNOW_KEY>.txt`. Manual runs:
  `manage.py indexnow_ping [--hours 24 | --guides | --all | --url URL] [--dry-run]`.
  Google does not use IndexNow; it reads the sitemap's `lastmod`.
- **llms.txt**: a markdown summary with coverage figures, key pages, guides,
  top sectors and exchanges. Cheap to keep; no major AI provider has confirmed
  reading it.

## CSS, JS, fonts and images

Plain modern CSS (custom properties, grid, flexbox, container queries,
`color-mix`, OKLCH) — no framework. Sources in `assets/`, output committed in
`web/static/web/` so a deploy needs no Node.

```bash
npm install          # once; dev only
npm run build        # CSS + JS + fonts  (or: make assets)
npm run build:images # favicon, icons, OG card, guide heroes
```

`scripts/build-assets.mjs` bundles `assets/css/site.css` (tokens → base →
layout → components → pages) with esbuild, runs **PurgeCSS** over
`web/templates/**/*.html`, `web/templatetags/*.py`, `web/views.py` and
`assets/js/*.js` (classes emitted from Python count too), then minifies for
Chrome/Edge 111+, Firefox 114+, Safari 16.4+. State-driven selectors
(`aria-*`, `data-theme`, `hidden`, `is-me`) are safelisted in the script.
A class built dynamically in a template must appear literally somewhere in
those files, or be added to the safelist.

| Asset | Size | Over the wire |
|---|---|---|
| `site.css` | 28.6 KB | 6.0 KB Brotli |
| `site.js` | 2.7 KB | 1.1 KB Brotli |
| Fonts | Bricolage Grotesque (variable, latin) 41 KB; IBM Plex Mono 400/600, 15 KB each | woff2 |

**Fonts:** two families, self-hosted, `font-display: swap`, latin subset, the
two above-the-fold files preloaded. Body text uses the system UI font: no
download and no layout shift on the largest block of text. (The prototype
used three families; Plex Sans was dropped.)

**Images:** `components/picture.html` renders AVIF → WebP → PNG with explicit
`width`/`height`. It lazy-loads by default; pass `eager=True` only for the
above-the-fold LCP image, which then gets `fetchpriority="high"` instead
(guide heroes do this). Company tiles are CSS, not images.

**Interactivity:** one vanilla deferred script instead of Alpine.js or HTMX —
everything the site needs fits in 2.7 KB, against ~15 KB for HTMX and ~16 KB
for Alpine. If a later feature needs them, load them on that page only,
deferred. Nothing may load page content after load.

**Islands:** a rich widget (the planned price chart) goes in the page's
`{% block islands %}` as a deferred `<script type="module">` that mounts
into a server-rendered placeholder holding the same data as text/table, so
crawlers and no-JS readers still get the numbers.

**Dark mode — material black + liquid glass** (`assets/css/glass.css`,
tokens in `tokens.css`): a true-black `#000` base with neutral greys, glass
panels (translucent white sheen that lightens with elevation, a bright
specular top edge and a gradient rim that picks up the accent), and soft
violet/blue/magenta ambient light fixed behind the page. Real backdrop blur
is limited to the sticky header, the search dropdown and the sticky sidebar,
so scrolling stays cheap on phones. With the OS "reduce transparency" setting
(Windows: Transparency effects off) panels turn opaque and nothing blurs; the
sheen, rim and glow stay. Every glass token is a no-op in light mode.

**Design and accessibility:** light and dark themes (system preference, with
a toggle saved in `localStorage`); muted text darkened from the prototype's
3.6:1 to 5.3:1 for WCAG AA; ticker tiles in OKLCH so white text passes on
every hue; tap targets ≥ 44px (small visual links get an enlarged hit area);
skip link; works down to 360px with no horizontal scroll; header is sticky
only on wide screens.

## Performance and caching

- **HTML cache** (`core.cache.cache_html`): a rendered page is cached in
  Redis under the data version (bumped by every successful sync) **and**
  `RELEASE` (so a deploy never serves pages rendered by old templates). Only
  query parameters a page declares are part of the key, so `?utm_source=`
  cannot multiply entries. Responses carry `ETag` and
  `Cache-Control: public, max-age=300`; a matching `If-None-Match` gets a 304.
  Off in `DEBUG`.
- **Static files** (WhiteNoise, `CompressedManifestStaticFilesStorage`):
  content-hashed names, precompressed gzip + Brotli at `collectstatic`, and
  `Cache-Control: max-age=315360000, public, immutable`.
- **Compression**: `GZipMiddleware` for HTML and JSON (below WhiteNoise, so
  static files are never recompressed). Put Brotli for HTML at the CDN or
  reverse proxy if you want the extra ~15%.
- Measured locally with `DEBUG=False`: TTFB 80–125 ms on a cold cache, ~3 ms
  cached, for 5,699 companies.

Static generation (django-distill) was left out on purpose: the per-version
cache already serves every page from memory, and stays correct the moment a
sync lands, without a rebuild step.

## Deploy settings

New environment variables (all optional except `SITE_URL` in production):

| Variable | Default | Purpose |
|---|---|---|
| `SITE_URL` | `HOST_URL`, else `http://localhost:8000` | Absolute URLs: canonical, sitemap, OG, JSON-LD. Set to the public origin, e.g. `https://www.example.com` |
| `SITE_NAME` | `Equity Profiles` | Brand in titles and structured data |
| `RELEASE` | process start time | Set to the git SHA on deploy so workers share the HTML cache |
| `INDEXNOW_KEY` | empty | 8–128 chars of `[a-zA-Z0-9-]`; enables `/<key>.txt` |
| `INDEXNOW_ENABLED` | `True` in production when a key is set | Force on/off |
| `ORGANIZATION_NAME`, `ORGANIZATION_URL`, `ORGANIZATION_EMAIL`, `ORGANIZATION_SAME_AS` | 6sMarketers | Publisher details; `SAME_AS` is a comma-separated list of official profiles |
| `SITE_TWITTER` | empty | `@handle` for Twitter Cards |

Deploy steps: `pip install -r requirements/prod.txt`, then
`python manage.py collectstatic --noinput`, then restart with `RELEASE` set.
Set `ALLOWED_HOSTS` to the real host names in production.

## Verification checklist

### 1. Automated (run these)

```bash
pytest tests/test_web.py
```

41 tests: one H1, title/description lengths and uniqueness, canonical, OG,
JSON-LD validity and escaping, noindex rules (SPAC, inactive, filtered, thin
hubs), sitemap contents, robots.txt groups, llms.txt, cache/ETag behaviour,
IndexNow batching.

```bash
python scripts/verify_site.py http://localhost:8000
```

Fetches robots.txt, the sitemap, llms.txt and the key pages **as GPTBot,
without JavaScript**, and checks content in `<main>`, one H1, title and
description lengths, canonical, OG/Twitter tags, JSON-LD, real links, image
dimensions, deferred scripts, HTML compression, static cache headers and font
preloads. Use `--ua ClaudeBot`, `--ua PerplexityBot` or `--ua Googlebot` to
impersonate others. Run it against staging and production after each deploy;
it exits non-zero on any failure.

### 2. curl test

```bash
curl -s -A "GPTBot" https://www.example.com/stocks/aapl/ | grep -c "What is Apple"
curl -s -A "ClaudeBot" https://www.example.com/stocks/aapl/ | grep -o '<script type="application/ld+json">' | wc -l
curl -sI -H "Accept-Encoding: br, gzip" https://www.example.com/ | grep -i -E "content-encoding|cache-control|etag"
curl -s https://www.example.com/robots.txt
```

The first must print a number above 0 — the answer is in the raw HTML.

### 3. JavaScript disabled

Chrome DevTools → ⌘/Ctrl+Shift+P → "Disable JavaScript" → reload a profile,
a hub and the directory. Everything must read the same; the search form
submits to `/search/`, filters submit with **Apply**, the theme toggle is
hidden.

### 4. Rich Results Test and Schema validator

- <https://search.google.com/test/rich-results> — test a profile, a guide and
  the home page. Expect Breadcrumbs and Article (guides) as eligible; FAQ is
  detected but only shown by Google for gov/health sites.
- <https://validator.schema.org/> — should report 0 errors for every node,
  including Corporation and DefinedTermSet, which Google's tool does not cover.

### 5. PageSpeed Insights / Lighthouse

- <https://pagespeed.web.dev/> — run **Mobile** first, for home, a profile,
  the directory and a guide. Targets: LCP < 2.5 s, CLS < 0.1, INP < 200 ms;
  Performance, Accessibility, Best Practices and SEO ≥ 90.
- Locally: `npx lighthouse http://localhost:8000/stocks/aapl/ --preset=perf --form-factor=mobile --view`
  (run against `DEBUG=False` + `collectstatic`, not the dev server).

### 6. After launch

- Google Search Console and Bing Webmaster Tools: submit `/sitemap.xml`; in
  Bing, confirm IndexNow submissions arrive (Settings → IndexNow).
- Spot-check a few profiles with "URL Inspection → View crawled page" to see
  the HTML Google received.
- Search Console → Page indexing: SPAC and filtered pages should be listed as
  "Excluded by noindex", which is intended.
