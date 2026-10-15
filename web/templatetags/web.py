import json

from django import template
from django.core.serializers.json import DjangoJSONEncoder
from django.http import QueryDict
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from web import formatting

register = template.Library()

register.filter("cap", formatting.cap)
register.filter("num", formatting.num)
register.filter("asof", formatting.human_date)
register.filter("size_label", formatting.size_label)
register.filter("hue", formatting.monogram_hue)

# JSON-LD sits inside <script>; these keep a company description containing
# "</script>" from closing the tag early (same escapes as json_script).
_JSON_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


@register.filter
def jsonld(data):
    if not data:
        return ""
    body = json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))
    return mark_safe(f'<script type="application/ld+json">{body.translate(_JSON_ESCAPES)}</script>')


@register.filter
def isodate(value):
    value = formatting.to_datetime(value)
    return value.date().isoformat() if hasattr(value, "date") else (value.isoformat() if value else "")


@register.filter
def type_label(security_type):
    return formatting.TYPE_LABELS.get(security_type, (security_type or "").upper())


@register.filter
def type_name(security_type):
    return formatting.TYPE_NAMES.get(security_type, (security_type or "").upper())


@register.filter
def bar(value, maximum):
    """Width of a market-cap bar as a CSS percentage; never so thin it disappears."""
    if not value or not maximum:
        return "2%"
    return f"{max(2.0, float(value) / float(maximum) * 100):.1f}%"


@register.filter
def stock_url(ticker):
    return reverse("web:stock", kwargs={"ticker": ticker.lower()})


@register.simple_tag
def monogram(ticker, size=""):
    """The coloured ticker tile. Decorative: the ticker is always in text beside it."""
    classes = f"mono-tile {size}".strip()
    return format_html(
        '<span class="{}" style="--h:{}" aria-hidden="true">{}</span>',
        classes,
        formatting.monogram_hue(ticker),
        ticker[:2],
    )


@register.simple_tag(takes_context=True)
def page_url(context, page):
    """
    The current page's URL at another page number; page 1 drops the
    parameter. Only the filters in context["filters"] are carried over, never
    the raw query string: the page is cached, and a stray utm tag must not end
    up in every visitor's links.
    """
    params = QueryDict(mutable=True)
    for key, value in (context.get("filters") or {}).items():
        if value:
            params[key] = value
    if page and int(page) > 1:
        params["page"] = page
    query = params.urlencode()
    return f"{context['request'].path}{'?' + query if query else ''}"


@register.simple_tag
def page_window(data, radius=2):
    """Page numbers around the current one, for the pager."""
    return range(max(1, data["page"] - radius), min(data["num_pages"], data["page"] + radius) + 1)
