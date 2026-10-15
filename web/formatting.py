"""Number and date formatting, shared by templates (web.templatetags.web) and generated copy."""

from datetime import date, datetime

SIZE_LABELS = {
    "mega": "Mega cap",
    "large": "Large cap",
    "mid": "Mid cap",
    "small": "Small cap",
    "micro": "Micro cap",
    "nano": "Nano cap",
    "unknown": "Unknown",
}
TYPE_LABELS = {"common": "Common", "adr": "ADR", "spac": "SPAC"}
TYPE_NAMES = {
    "common": "Common stock",
    "adr": "American depositary receipt (ADR)",
    "spac": "SPAC (blank check)",
}


def cap(value):
    """45655558616.76 -> '$45.66B'. None -> 'n/a'."""
    if value is None:
        return "n/a"
    value = float(value)
    for divisor, unit, places in ((1e12, "T", 2), (1e9, "B", 2), (1e6, "M", 1)):
        if abs(value) >= divisor:
            return f"${value / divisor:,.{places}f}{unit}"
    return f"${value:,.0f}"


def num(value):
    if value is None or value == "":
        return "n/a"
    return f"{int(value):,}"


def to_datetime(value):
    """An ISO string, date or datetime as a date/datetime; None stays None."""
    if value in (None, ""):
        return None
    if isinstance(value, (date, datetime)):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def human_date(value):
    """'22 Sep 2026' — the format every as-of label on the site uses."""
    value = to_datetime(value)
    return f"{value.day} {value:%b %Y}" if value else "n/a"


def size_label(bucket):
    return SIZE_LABELS.get(bucket or "unknown", "Unknown")


def with_article(phrase):
    return f"an {phrase}" if phrase[:1].lower() in "aeiou" else f"a {phrase}"


def monogram_hue(ticker):
    """A stable hue per ticker, so a company's tile is the same on every page."""
    return sum(ord(c) for c in ticker or "") * 37 % 360
