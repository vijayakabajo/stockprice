"""
Display labels derived from provider data.

The rules here are the ones the frontend prototype applied client-side,
moved to the backend so every consumer shows the same label. Rules that are
plain comparisons (security type, size bucket) live in SQL as generated
columns instead — see sql/0008_add_stock_classification.sql.
"""

import re

from django.utils.text import slugify

# Share-class and listing descriptors the provider appends to company names:
# "Apogee Acquisition Corp Class A Ordinary Shares", "Broadcom Inc. Common Stock".
_SHARE_DESCRIPTORS = re.compile(
    r"[,\s]*\b(?:"
    r"Class [A-Z] (?:Ordinary|Common) (?:Shares?|Stock)"
    r"|American Depositary (?:Shares?|Receipts?)"
    r"|Ordinary Shares?"
    r"|Common (?:Shares?|Stock)"
    r")\b\.?",
    re.IGNORECASE,
)

# Legal-form suffixes, stripped from the end only, repeatedly:
# "American Airlines Group Inc." -> "American Airlines".
_LEGAL_SUFFIX = re.compile(
    r"[,\s]+(?:Incorporated|Corporation|Inc|Corp|Co|Group|Holdings|Ltd|Limited"
    r"|plc|N\.?V|S\.?A|AG|SE|L\.?P|LLC)\.?$",
    re.IGNORECASE,
)

# SPAC series numerals sit after the legal form: "Ares Acquisition Corporation III".
_SERIES_NUMERAL = re.compile(r"\s+[IVX]{1,4}$")

# Acronyms that title-casing would mangle.
_ACRONYMS = {"Nec": "NEC", "Catv": "CATV", "Us": "US", "Usa": "USA"}


def display_name(name: str) -> str:
    """
    A readable company name: share-class descriptors and legal suffixes
    removed, and all-caps names title-cased. Falls back to the raw name if
    the cleanup would leave nothing.
    """
    if not name:
        return ""
    cleaned = _SHARE_DESCRIPTORS.sub("", name).strip()

    # Set a series numeral aside so the legal form before it can be removed.
    numeral = _SERIES_NUMERAL.search(cleaned)
    if numeral:
        cleaned = cleaned[: numeral.start()]

    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _LEGAL_SUFFIX.sub("", cleaned.strip())
    if numeral:
        cleaned += numeral.group(0)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.")

    # "ABBVIE INC." reads as shouting. Short all-caps words are usually
    # acronyms ("AT&T", "IBM"), so only longer words are title-cased.
    if cleaned.isupper():
        cleaned = " ".join(w.capitalize() if len(w) > 4 else w for w in cleaned.split(" "))

    return cleaned or name.strip()


def title_case(text: str) -> str:
    """'AIR TRANSPORTATION, SCHEDULED' -> 'Air Transportation, Scheduled'."""
    if not text:
        return ""
    # Apostrophes belong to the word: "WOMEN'S" -> "Women's", not "Women'S".
    titled = re.sub(r"[A-Za-z']+", lambda m: m.group(0).capitalize(), text.lower())
    return re.sub(r"\b[A-Za-z]+\b", lambda m: _ACRONYMS.get(m.group(0), m.group(0)), titled)


def sector_name(sic_description: str) -> str:
    return title_case(sic_description)


def unique_slug(text: str, taken: set, fallback: str) -> str:
    """slugify(text), made unique against `taken` by appending `fallback`."""
    slug = slugify(text) or slugify(fallback)
    if slug in taken:
        slug = f"{slug}-{slugify(fallback)}"
    return slug
