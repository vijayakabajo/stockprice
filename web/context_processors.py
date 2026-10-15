from django.conf import settings
from django.urls import reverse

NAV = [
    ("Stocks", "web:directory"),
    ("Sectors", "web:sectors"),
    ("Exchanges", "web:exchanges"),
    ("Guides", "web:guides"),
]


def site(request):
    """Site identity for base.html; constant per deploy, so safe in cached pages."""
    return {
        "site": {
            "name": settings.SITE_NAME,
            "url": settings.SITE_URL,
            "tagline": settings.SITE_TAGLINE,
            "description": settings.SITE_DESCRIPTION,
            "language": settings.SITE_LANGUAGE.split("-")[0],
            "locale": settings.SITE_LOCALE,
            "twitter": settings.SITE_TWITTER,
            "organization": settings.ORGANIZATION,
        },
        "nav": [
            {"label": label, "href": (href := reverse(name)), "current": request.path.startswith(href)}
            for label, name in NAV
        ],
    }
