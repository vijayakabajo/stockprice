"""
Page metadata and schema.org structured data.

Every view builds one PageMeta. base.html renders it into <title>, the meta
description, canonical, robots, Open Graph, Twitter Card and a single JSON-LD
@graph. Absolute URLs always come from settings.SITE_URL, never the request.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from django.conf import settings
from django.templatetags.static import static

from web.formatting import to_datetime

TITLE_MAX = 60
DESCRIPTION_MAX = 160

INDEX = "index, follow, max-image-preview:large, max-snippet:-1"
NOINDEX = "noindex, follow"

DEFAULT_IMAGE = "web/img/og-default.png"
IMAGE_WIDTH, IMAGE_HEIGHT = 1200, 630


def absolute(path):
    return path if path.startswith("http") else f"{settings.SITE_URL}{path}"


def static_url(path):
    return absolute(static(path))


# ---------------------------------------------------------------------------
# Titles and descriptions
# ---------------------------------------------------------------------------


def _truncate(text, limit):
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-(")
    return f"{cut}…"


def fit_title(*candidates):
    """
    The most informative candidate that fits in TITLE_MAX characters, with
    the site name appended when there is room. Candidates go longest-first.
    """
    for candidate in candidates:
        suffix = "" if settings.SITE_NAME in candidate else f" | {settings.SITE_NAME}"
        if len(candidate) + len(suffix) <= TITLE_MAX:
            return candidate + suffix
    for candidate in candidates:
        if len(candidate) <= TITLE_MAX:
            return candidate
    return _truncate(candidates[-1], TITLE_MAX)


def fit_description(*sentences):
    """Whole sentences, in order, up to DESCRIPTION_MAX characters."""
    text = ""
    for sentence in filter(None, sentences):
        joined = f"{text} {sentence}".strip()
        if len(joined) > DESCRIPTION_MAX:
            break
        text = joined
    return text or _truncate(next(filter(None, sentences), ""), DESCRIPTION_MAX)


# ---------------------------------------------------------------------------
# Page metadata
# ---------------------------------------------------------------------------


@dataclass
class PageMeta:
    title: str
    description: str
    path: str  # canonical path, with any query string that defines the page
    robots: str = INDEX
    og_type: str = "website"
    image: str = DEFAULT_IMAGE  # static path
    image_alt: str = ""
    published: date | datetime | None = None
    modified: date | datetime | None = None
    breadcrumbs: list = field(default_factory=list)  # [(name, path), ...]; Home is implied
    graph: list = field(default_factory=list)  # JSON-LD nodes

    @property
    def canonical(self):
        return absolute(self.path)

    @property
    def image_url(self):
        return static_url(self.image)

    @property
    def indexable(self):
        return self.robots.startswith("index")

    @property
    def jsonld(self):
        nodes = list(self.graph)
        if self.breadcrumbs:
            nodes.append(breadcrumb_list(self.breadcrumbs))
        return {"@context": "https://schema.org", "@graph": nodes} if nodes else None


# ---------------------------------------------------------------------------
# JSON-LD nodes
# ---------------------------------------------------------------------------

ORG_ID = "/#organization"
SITE_ID = "/#website"


def _iso(value):
    value = to_datetime(value)
    return value.isoformat() if value else None


def _clean(node):
    """Drops empty values: a property with no data is left out, not null."""
    return {k: v for k, v in node.items() if v not in (None, "", [], {})}


def organization():
    org = settings.ORGANIZATION
    return _clean(
        {
            "@type": "Organization",
            "@id": absolute(ORG_ID),
            "name": settings.SITE_NAME,
            "url": absolute("/"),
            "logo": {
                "@type": "ImageObject",
                "url": static_url("web/img/logo-512.png"),
                "width": 512,
                "height": 512,
            },
            "description": settings.SITE_DESCRIPTION,
            "email": org["email"],
            "parentOrganization": {"@type": "Organization", "name": org["name"], "url": org["url"]},
            "sameAs": org["same_as"],
        }
    )


def website():
    return {
        "@type": "WebSite",
        "@id": absolute(SITE_ID),
        "url": absolute("/"),
        "name": settings.SITE_NAME,
        "description": settings.SITE_DESCRIPTION,
        "inLanguage": settings.SITE_LANGUAGE,
        "publisher": {"@id": absolute(ORG_ID)},
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": absolute("/search/?q={search_term_string}")},
            "query-input": "required name=search_term_string",
        },
    }


def breadcrumb_list(crumbs):
    items = [("Home", "/")] + list(crumbs)
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": absolute(path)}
            for i, (name, path) in enumerate(items, start=1)
        ],
    }


def faq_page(meta, faqs):
    return {
        "@type": "FAQPage",
        "@id": f"{meta.canonical}#faq",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faqs
        ],
    }


def author_node(author):
    return {"@type": author.kind, "name": author.name, "url": absolute(f"/about/#{author.slug}")}


def web_page(meta, page_type="WebPage", author=None, about=None, main_entity=None):
    return _clean(
        {
            "@type": page_type,
            "@id": meta.canonical,
            "url": meta.canonical,
            "name": meta.title,
            "description": meta.description,
            "inLanguage": settings.SITE_LANGUAGE,
            "isPartOf": {"@id": absolute(SITE_ID)},
            "primaryImageOfPage": {"@type": "ImageObject", "url": meta.image_url},
            "datePublished": _iso(meta.published),
            "dateModified": _iso(meta.modified),
            "author": author_node(author) if author else None,
            "publisher": {"@id": absolute(ORG_ID)},
            "about": about,
            "mainEntity": main_entity,
        }
    )


def article(meta, headline, author, sections=None):
    """Article for guides: headline, image, author, publisher and both dates."""
    return _clean(
        {
            "@type": "Article",
            "@id": f"{meta.canonical}#article",
            "mainEntityOfPage": meta.canonical,
            "headline": headline[:110],
            "description": meta.description,
            "image": [
                {"@type": "ImageObject", "url": meta.image_url, "width": IMAGE_WIDTH, "height": IMAGE_HEIGHT}
            ],
            "datePublished": _iso(meta.published),
            "dateModified": _iso(meta.modified),
            "author": [author_node(author)],
            "publisher": {"@id": absolute(ORG_ID)},
            "inLanguage": settings.SITE_LANGUAGE,
            "articleSection": sections,
        }
    )


def corporation(profile, url):
    address = profile.get("address") or {}
    return _clean(
        {
            "@type": "Corporation",
            "@id": f"{url}#company",
            "name": profile["display_name"] or profile["name"],
            "legalName": profile["name"],
            "tickerSymbol": f"{(profile.get('exchange') or {}).get('name', '')} {profile['ticker']}".strip(),
            "description": profile.get("description"),
            "url": profile.get("website"),
            "telephone": profile.get("phone"),
            "numberOfEmployees": (
                {"@type": "QuantitativeValue", "value": profile["total_employees"]}
                if profile.get("total_employees")
                else None
            ),
            "address": (
                _clean(
                    {
                        "@type": "PostalAddress",
                        "streetAddress": address.get("line1"),
                        "addressLocality": address.get("city"),
                        "addressRegion": address.get("state"),
                        "postalCode": address.get("postal_code"),
                        "addressCountry": profile.get("country"),
                    }
                )
                if address
                else None
            ),
            "identifier": [
                _clean({"@type": "PropertyValue", "propertyID": pid, "value": profile.get(key)})
                for pid, key in (("CIK", "cik"), ("FIGI", "composite_figi"))
                if profile.get(key)
            ],
            "sameAs": [profile["edgar_url"]] if profile.get("edgar_url") else None,
        }
    )


def item_list(name, rows, url_for):
    return {
        "@type": "ItemList",
        "name": name,
        "numberOfItems": len(rows),
        "itemListOrder": "https://schema.org/ItemListOrderDescending",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i,
                "name": row["display_name"] or row["name"],
                "url": absolute(url_for(row["ticker"])),
            }
            for i, row in enumerate(rows, start=1)
        ],
    }


def defined_term_set(meta, terms):
    return {
        "@type": "DefinedTermSet",
        "@id": f"{meta.canonical}#terms",
        "name": f"{settings.SITE_NAME} glossary",
        "hasDefinedTerm": [
            {
                "@type": "DefinedTerm",
                "@id": f"{meta.canonical}#{t.slug}",
                "name": t.name,
                "description": t.definition,
                "url": f"{meta.canonical}#{t.slug}",
            }
            for t in terms
        ],
    }
