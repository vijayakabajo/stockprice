"""
Crawler's-eye check of a running site. Standard library only, so it runs
anywhere Python does: locally, in CI, or against production.

    python scripts/verify_site.py http://localhost:8000
    python scripts/verify_site.py https://www.example.com --ua ClaudeBot

Fetches pages the way an AI crawler does (no JavaScript) and checks: the
content is in the HTML, one <h1>, title/description lengths, canonical,
robots meta, parseable JSON-LD, real <a href> links, image dimensions,
deferred scripts, compression and cache headers, robots.txt, sitemap.xml
and llms.txt. Exits non-zero if any check fails.
"""

import argparse
import gzip
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

AI_BOTS = [
    "Googlebot",
    "Bingbot",
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-SearchBot",
    "PerplexityBot",
    "Google-Extended",
]
USER_AGENTS = {
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot",
    "ClaudeBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
}

results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))
    return ok


def fetch(url, ua, accept_encoding="gzip"):
    request = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": accept_encoding})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return response.status, response.headers, body.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, ""


class Page(HTMLParser):
    """Collects what the checks need in one pass."""

    def __init__(self):
        super().__init__()
        self.h1 = 0
        self.title = ""
        self.meta = {}
        self.canonical = None
        self.lang = None
        self.links, self.images, self.scripts, self.jsonld = [], [], [], []
        self.main_text = []
        self._in = {"title": False, "main": 0, "ld": False}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self._in["title"] = True
        elif tag == "meta" and ("name" in a or "property" in a):
            self.meta[a.get("name") or a.get("property")] = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        elif tag == "main":
            self._in["main"] += 1
        elif tag == "a":
            self.links.append(a.get("href"))
        elif tag == "img":
            self.images.append(a)
        elif tag == "script":
            if a.get("type") == "application/ld+json":
                self._in["ld"] = True
                self.jsonld.append("")
            elif a.get("src"):
                self.scripts.append(a)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in["title"] = False
        elif tag == "main":
            self._in["main"] -= 1
        elif tag == "script":
            self._in["ld"] = False

    def handle_data(self, data):
        if self._in["title"]:
            self.title += data
        if self._in["ld"]:
            self.jsonld[-1] += data
        if self._in["main"]:
            self.main_text.append(data)


def check_page(base, path, ua, expect_index=True):
    url = urljoin(base, path)
    status, headers, body = fetch(url, ua)
    label = path
    if not check(f"{label} returns 200", status == 200, f"got {status}"):
        return
    page = Page()
    page.feed(body)
    words = len(" ".join(page.main_text).split())

    check(f"{label} content is in the HTML (no JS)", words >= 80, f"{words} words in <main>")
    check(f"{label} has exactly one <h1>", page.h1 == 1, f"{page.h1} found")
    check(f"{label} <html lang> set", bool(page.lang), page.lang or "missing")
    check(
        f"{label} title 30-60 chars",
        30 <= len(page.title.strip()) <= 60,
        f"{len(page.title.strip())}: {page.title.strip()}",
    )
    desc = page.meta.get("description", "")
    check(f"{label} description 70-160 chars", 70 <= len(desc) <= 160, f"{len(desc)}")
    check(
        f"{label} canonical is absolute",
        bool(page.canonical and page.canonical.startswith("http")),
        page.canonical or "missing",
    )
    check(f"{label} viewport meta", "width=device-width" in page.meta.get("viewport", ""))
    for tag in ("og:title", "og:description", "og:image", "twitter:card"):
        check(f"{label} {tag}", bool(page.meta.get(tag)))
    robots = page.meta.get("robots", "")
    if expect_index:
        check(f"{label} is indexable", robots.startswith("index"), robots)

    try:
        graphs = [json.loads(block) for block in page.jsonld]
        types = sorted({n.get("@type") for g in graphs for n in g.get("@graph", [g])})
        check(f"{label} JSON-LD parses", bool(graphs), ", ".join(map(str, types)))
    except json.JSONDecodeError as e:
        check(f"{label} JSON-LD parses", False, str(e))

    bad_links = [h for h in page.links if not h or h.startswith(("javascript:", "#")) and len(h) <= 1]
    check(f"{label} links are real hrefs", not bad_links, f"{len(bad_links)} bad")
    bad_images = [
        i.get("src") for i in page.images if not (i.get("width") and i.get("height") and "alt" in i)
    ]
    check(f"{label} images have width/height/alt", not bad_images, ", ".join(bad_images[:3]))
    blocking = [
        s.get("src")
        for s in page.scripts
        if "defer" not in s and "async" not in s and s.get("type") != "module"
    ]
    check(f"{label} scripts are deferred", not blocking, ", ".join(blocking))
    check(
        f"{label} HTML is compressed",
        headers.get("Content-Encoding") in ("gzip", "br"),
        headers.get("Content-Encoding") or "none",
    )
    return body


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("base", help="Site root, e.g. http://localhost:8000")
    parser.add_argument("--ua", default="GPTBot", choices=sorted(USER_AGENTS), help="Crawler to impersonate.")
    args = parser.parse_args()
    base = args.base.rstrip("/") + "/"
    ua = USER_AGENTS[args.ua]

    # robots.txt
    status, _, robots = fetch(urljoin(base, "robots.txt"), ua)
    check("robots.txt returns 200", status == 200)
    for bot in AI_BOTS:
        allowed = re.search(rf"User-agent: {re.escape(bot)}\s*\nAllow: /", robots or "")
        check(f"robots.txt allows {bot}", bool(allowed))
    sitemap_line = re.search(r"^Sitemap: (\S+)", robots or "", re.M)
    check("robots.txt links the sitemap", bool(sitemap_line))

    # sitemap.xml -> one stock URL to test
    status, _, index = fetch(urljoin(base, "sitemap.xml"), ua)
    check("sitemap.xml returns 200", status == 200)
    sections = re.findall(r"<loc>(.*?)</loc>", index)
    check("sitemap index has lastmod", "<lastmod>" in index)
    stock_path = None
    for section in sections:
        if "stocks" in section:
            _, _, xml = fetch(
                urlsplit(section)
                ._replace(scheme=urlsplit(base).scheme, netloc=urlsplit(base).netloc)
                .geturl(),
                ua,
            )
            locs = re.findall(r"<loc>(.*?)</loc>", xml)
            check("stock sitemap lists profiles", bool(locs), f"{len(locs)} URLs")
            if locs:
                stock_path = urlsplit(locs[0]).path
            break

    # llms.txt
    status, _, llms = fetch(urljoin(base, "llms.txt"), ua)
    check("llms.txt returns 200", status == 200 and llms.startswith("# "))

    # pages
    paths = [
        "/",
        "/stocks/",
        "/sectors/",
        "/exchanges/",
        "/guides/what-is-market-cap/",
        "/glossary/",
        "/about/",
    ]
    if stock_path:
        paths.insert(2, stock_path)
    home = None
    for path in paths:
        body = check_page(base, path, ua)
        home = home or body

    # static assets: hashed names, long cache, precompressed
    css = re.search(r'href="(/static/[^"]+\.css)"', home or "")
    if check("stylesheet found", bool(css)):
        status, headers, _ = fetch(urljoin(base, css.group(1)), ua, accept_encoding="br, gzip")
        cache_control = headers.get("Cache-Control", "")
        check(
            "CSS cached for a year+",
            "immutable" in cache_control or "max-age=31536000" in cache_control,
            cache_control,
        )
        check(
            "CSS compressed",
            headers.get("Content-Encoding") in ("br", "gzip"),
            headers.get("Content-Encoding") or "none",
        )
    preloads = re.findall(r'<link rel="preload" href="([^"]+)" as="font"', home or "")
    check("fonts preloaded (max 2 families)", 1 <= len(preloads) <= 2, f"{len(preloads)}")

    width = max(len(name) for _, name, _ in results)
    failed = 0
    for ok, name, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    print(f"\n{len(results) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
