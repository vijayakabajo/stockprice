"""
Sentences built from backend facts: answers, takeaways and FAQs.

The backend owns facts, the site owns copy (PROJECT_OVERVIEW §4). Rules for
everything written here, because answer engines quote it sentence by sentence:

  * Lead with the answer. The first sentence under a heading answers it.
  * Every sentence stands alone: repeat the company's name, never "it",
    "above" or "as mentioned".
  * Every figure carries its date.
  * Never guess. A missing fact drops its sentence or question.
"""

import re

from web.formatting import cap, human_date, num, size_label, with_article

NOT_CLASSIFIED = "not-classified"


def _first_sentence(text, limit=260):
    if not text:
        return ""
    match = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    sentence = match.group(1) if match else text.strip()
    return sentence if len(sentence) <= limit else ""


def _sector_known(row):
    sector = row.get("sector") or {}
    return sector.get("slug") not in (None, NOT_CLASSIFIED)


def _hq(profile):
    address = profile.get("address") or {}
    if not address.get("city"):
        return None
    return f"{address['city']}, {address['state']}" if address.get("state") else address["city"]


def company_name(row):
    return row.get("display_name") or row.get("name") or row["ticker"]


def _size_phrase(bucket):
    return with_article(size_label(bucket).lower()) if bucket and bucket != "unknown" else None


# ---------------------------------------------------------------------------
# Stock profile
# ---------------------------------------------------------------------------


def profile_copy(profile, peers):
    """Every generated sentence on a stock profile."""
    name = company_name(profile)
    ticker = profile["ticker"]
    exchange = (profile.get("exchange") or {}).get("name") or "a U.S. exchange"
    sector = (profile.get("sector") or {}).get("name")
    sector_known = _sector_known(profile)
    kind = profile["security_type"]
    as_of = human_date(profile.get("as_of"))
    market_cap = profile.get("market_cap")
    size = _size_phrase(profile.get("size_bucket"))
    hq = _hq(profile)
    employees = profile.get("total_employees")
    rank, ranked_total = peers.get("rank"), peers.get("ranked_total")

    if kind == "spac":
        identity = f"{name} ({ticker}) is a special purpose acquisition company (SPAC) listed on {exchange}"
    elif kind == "adr":
        identity = (
            f"{name} ({ticker}) is a non-U.S. company whose American depositary receipts trade on {exchange}"
        )
    else:
        identity = f"{name} ({ticker}) is a U.S.-listed company that trades on {exchange}"
    if sector_known and kind != "spac":
        identity += f", in the {sector} industry"
    lead = f"{identity}."
    sic = f" (SIC {profile['sic_code']})" if profile.get("sic_code") else ""

    if kind == "spac":
        does = (
            f"{name} is a blank check company: it raised cash in an IPO to merge with a private operating "
            f"business and has no operations of its own until that merger closes."
        )
    else:
        does = _first_sentence(profile.get("description")) or (
            f"The SEC classifies {name} under {sector}{sic}."
            if sector_known
            else f"{name} has not published a business description in our reference data yet."
        )

    cap_sentence = None
    if market_cap is not None:
        cap_sentence = f"{name} had a market capitalization of about {cap(market_cap)} as of {as_of}"
        cap_sentence += f", which makes it {size} company." if size else "."

    rank_sentence = None
    if rank and ranked_total:
        rank_sentence = (
            f"{name} ranks No. {rank:,} by market cap among the {ranked_total:,} U.S.-listed companies "
            f"with a reported market cap, as of {as_of}."
        )

    takeaways = [f"{name} trades on {exchange} under the ticker {ticker}."]
    if sector_known and kind != "spac":
        takeaways.append(f"The SEC classifies {name} under {sector}{sic}.")
    if kind == "spac":
        takeaways.append(f"{name} is a SPAC: a listed shell company with no operating business yet.")
    if kind == "adr":
        takeaways.append(f"{name} is a non-U.S. company listed through American depositary receipts.")
    if cap_sentence:
        takeaways.append(cap_sentence)
    if employees:
        takeaways.append(f"{name} employs about {num(employees)} people, per its latest reported headcount.")
    if hq:
        takeaways.append(f"{name} is headquartered in {hq}.")

    faqs = [(f"What is {name}?", lead)]
    faqs.append((f"What does {name} do?", does))
    faqs.append(
        (f"What is {name}'s ticker symbol?", f"{name} trades under the ticker {ticker} on {exchange}.")
    )
    if cap_sentence:
        faqs.append(
            (
                f"What is {name}'s market cap?",
                f"{cap_sentence} Market cap is share price times shares outstanding, so it moves with the stock price.",
            )
        )
    if employees:
        faqs.append(
            (
                f"How many employees does {name} have?",
                f"{name} has about {num(employees)} employees, per its latest reported headcount as of {as_of}.",
            )
        )
    if hq:
        faqs.append((f"Where is {name} headquartered?", f"{name} is headquartered in {hq}."))
    if sector_known:
        faqs.append(
            (
                f"What sector is {name} in?",
                f"The SEC classifies {name} under {sector}{sic}, the industry code it assigns by main line of business.",
            )
        )
    if profile.get("cik"):
        faqs.append(
            (
                f"Where can I find {name}'s SEC filings?",
                f"{name}'s filings, including annual (10-K) and quarterly (10-Q) reports, are on SEC EDGAR "
                f"under CIK {profile['cik']}.",
            )
        )
    faqs.append(
        (
            f"Is {name} stock a good investment?",
            f"This page does not give investment advice. It summarizes reference data about {name} for "
            f"education; verify figures in {name}'s filings and consider a licensed adviser before investing.",
        )
    )

    return {
        "name": name,
        "lead": lead,
        "does": does,
        "cap_sentence": cap_sentence,
        "rank_sentence": rank_sentence,
        "takeaways": takeaways,
        "faqs": faqs,
        "hq": hq,
    }


# ---------------------------------------------------------------------------
# Sector and exchange hubs
# ---------------------------------------------------------------------------


def hub_copy(hub, kind):
    """kind is 'sector' or 'exchange'."""
    name = hub["name"]
    as_of = human_date(hub.get("as_of"))
    count = hub["companies"]
    largest = hub["largest"][0] if hub.get("largest") else None
    noun = "company" if count == 1 else "companies"

    if kind == "sector":
        subject = f"{name} stocks"
        lead = f"{count:,} U.S.-listed {noun} {'is' if count == 1 else 'are'} classified under {name}"
    else:
        subject = f"stocks listed on {name}"
        lead = f"{count:,} U.S. {noun} {'lists' if count == 1 else 'list'} {name} as {'its' if count == 1 else 'their'} primary exchange"
    if hub.get("total_market_cap"):
        lead += f", with a combined market cap of {cap(hub['total_market_cap'])}"
    lead += f", as of {as_of}."
    if largest and largest.get("market_cap"):
        lead += (
            f" The largest is {company_name(largest)} ({largest['ticker']}) at {cap(largest['market_cap'])}."
        )

    faqs = [(f"How many {subject} are there?", lead.split(" The largest")[0])]
    if largest and largest.get("market_cap"):
        faqs.append(
            (
                f"What is the largest company among {subject}?",
                f"{company_name(largest)} ({largest['ticker']}) is the largest of the {subject} by market cap, "
                f"at about {cap(largest['market_cap'])} as of {as_of}.",
            )
        )
    if hub.get("average_market_cap"):
        faqs.append(
            (
                f"What is the average market cap of {subject}?",
                f"The average market cap of the {count:,} {subject} is about {cap(hub['average_market_cap'])}, "
                f"as of {as_of}.",
            )
        )
    if hub.get("total_employees"):
        faqs.append(
            (
                f"How many people do {subject} employ?",
                f"The {count:,} {subject} report about {num(hub['total_employees'])} employees combined, "
                f"as of {as_of}.",
            )
        )
    return {"lead": lead, "faqs": faqs, "subject": subject}


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------


def home_faqs(overview, site_name):
    as_of = human_date(overview.get("as_of"))
    return [
        (
            f"How many U.S. stocks does {site_name} cover?",
            f"{site_name} profiles {overview['companies']:,} active U.S.-listed companies with a combined market "
            f"cap of {cap(overview['total_market_cap'])}, as of {as_of}.",
        ),
        (
            f"Where does {site_name} get its data?",
            f"{site_name} builds every profile from SEC filings and licensed U.S. market reference data, "
            f"refreshed daily, and dates each figure to its last refresh.",
        ),
        (
            f"Is {site_name} investment advice?",
            f"No. {site_name} publishes reference information for education only and does not recommend "
            f"buying or selling any security.",
        ),
        (
            f"Does {site_name} show live stock prices?",
            f"Not yet. {site_name} currently shows reference data such as market cap, sector and headcount; "
            f"delayed quotes are planned and will carry their own timestamp.",
        ),
    ]
