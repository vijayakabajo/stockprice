"""
Editorial content that is not derived from market data: authors, glossary
terms and guides.

Guides rarely change, so they live in the repo as templates
(web/templates/guides/) with their metadata here. Changing one is a code
change and a deploy; bump `updated` in the same commit so the page, its
structured data and the sitemap all report the new date.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Author:
    slug: str
    name: str
    role: str
    bio: str
    # Organization for a desk or team, Person for a named writer. Prefer
    # named people with real credentials as the site grows: author expertise
    # is one of the strongest trust signals for finance content.
    kind: str = "Organization"


AUTHORS = {
    "research-desk": Author(
        slug="research-desk",
        name="Research Desk",
        role="Editorial team",
        bio=(
            "The Research Desk builds and reviews every company profile on this site. It works from SEC "
            "filings and licensed market reference data, dates every figure to its source, and corrects "
            "errors as soon as they are reported."
        ),
    ),
}
DEFAULT_AUTHOR = AUTHORS["research-desk"]


@dataclass(frozen=True)
class Term:
    slug: str
    name: str
    definition: str


# Short, self-contained definitions. Each one must make sense quoted alone.
GLOSSARY = [
    Term(
        "market-cap",
        "Market capitalization",
        "The total market value of a company's shares: the share price multiplied by the number of shares outstanding. It measures the value of the equity, not the price of buying the whole company.",
    ),
    Term(
        "shares-outstanding",
        "Shares outstanding",
        "The number of a company's shares held by all its owners, including the public, insiders and institutions.",
    ),
    Term(
        "size-bucket",
        "Size bucket",
        "A label for a company's scale by market cap. This site uses mega cap ($200B and above), large cap ($10B to $200B), mid cap ($2B to $10B), small cap ($300M to $2B), micro cap ($50M to $300M) and nano cap (below $50M).",
    ),
    Term(
        "ticker",
        "Ticker symbol",
        "A short code of letters, sometimes with a dot and a share-class letter, that identifies a security on an exchange, such as A for Agilent Technologies or BRK.B for Berkshire Hathaway Class B.",
    ),
    Term(
        "exchange",
        "Stock exchange",
        "A regulated marketplace where shares are listed and traded. Nasdaq and the New York Stock Exchange (NYSE) are the largest U.S. exchanges.",
    ),
    Term(
        "sic-code",
        "SIC code",
        "A four-digit Standard Industrial Classification number that groups companies by their main line of business. The SEC assigns one to every company that files with it.",
    ),
    Term(
        "cik",
        "CIK",
        "The Central Index Key, a number the SEC assigns to every company and person that files with it. It is the key to a company's filings on SEC EDGAR.",
    ),
    Term(
        "figi",
        "FIGI",
        "The Financial Instrument Global Identifier, an open 12-character code that identifies one specific security. A composite FIGI covers a security across all U.S. exchanges; a share-class FIGI covers the share class worldwide.",
    ),
    Term(
        "round-lot",
        "Round lot",
        "The standard trading unit for a security, usually 100 shares. Orders for fewer shares are called odd lots.",
    ),
    Term(
        "adr",
        "ADR",
        "An American depositary receipt: a U.S.-traded certificate issued by a U.S. bank that represents shares of a non-U.S. company. ADRs trade and settle in U.S. dollars.",
    ),
    Term(
        "spac",
        "SPAC",
        "A special purpose acquisition company: a shell company that raises money in an IPO to merge with a private operating business later. Before that merger it has no operations of its own.",
    ),
    Term(
        "edgar",
        "SEC EDGAR",
        "The SEC's Electronic Data Gathering, Analysis, and Retrieval system, the free public database of company filings such as annual reports (10-K) and quarterly reports (10-Q).",
    ),
]
GLOSSARY_BY_SLUG = {t.slug: t for t in GLOSSARY}

# The terms a company profile explains inline, by security type.
PROFILE_TERMS = {
    "common": ["market-cap", "shares-outstanding", "sic-code", "cik", "figi", "round-lot"],
    "adr": ["adr", "market-cap", "shares-outstanding", "cik", "figi", "round-lot"],
    "spac": ["spac", "market-cap", "shares-outstanding", "sic-code", "cik", "round-lot"],
}


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    publisher: str
    published: str = ""  # free text, as the publisher dates it


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str  # the H1, phrased as the reader's question
    seo_title: str  # <title>, 50-60 characters
    description: str  # meta description, 150-160 characters
    summary: str  # the one-paragraph answer shown on the guides index
    published: date
    updated: date
    author: Author = DEFAULT_AUTHOR
    image: str = ""  # static path of the 1200x630 hero/OG image, without extension
    image_alt: str = ""
    sources: list = field(default_factory=list)

    @property
    def template(self):
        return f"guides/{self.slug}.html"


SEC_ADR_BULLETIN = Source(
    "Investor Bulletin: American Depositary Receipts",
    "https://www.sec.gov/investor/alerts/adr-bulletin.pdf",
    "U.S. Securities and Exchange Commission",
    "August 2012",
)
SEC_SPAC_BULLETIN = Source(
    "What You Need to Know About SPACs: Investor Bulletin",
    "https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/what-you",
    "U.S. Securities and Exchange Commission, Investor.gov",
)
INVESTOR_GOV_MARKET_CAP = Source(
    "Market Capitalization (glossary)",
    "https://www.investor.gov/introduction-investing/investing-basics/glossary/market-capitalization",
    "U.S. Securities and Exchange Commission, Investor.gov",
)
SEC_EDGAR = Source(
    "EDGAR full-text and company search",
    "https://www.sec.gov/search-filings",
    "U.S. Securities and Exchange Commission",
)
OSHA_SIC_MANUAL = Source(
    "SIC Manual", "https://www.osha.gov/data/sic-manual", "U.S. Department of Labor, OSHA"
)

GUIDES = [
    Guide(
        slug="what-is-market-cap",
        title="What is market capitalization, and how are stocks sized?",
        seo_title="What Is Market Cap? Meaning, Formula and Size Classes",
        description=(
            "Market cap is share price times shares outstanding. Learn the formula, what mega to nano cap "
            "mean, and how many U.S. stocks fall into each size class."
        ),
        summary=(
            "Market capitalization is a company's share price multiplied by its shares outstanding. It is "
            "the standard way to compare company size and sorts stocks into classes from mega cap to nano cap."
        ),
        published=date(2026, 10, 14),
        updated=date(2026, 10, 14),
        image="web/img/guides/what-is-market-cap",
        image_alt="Six bars of falling height labelled mega, large, mid, small, micro and nano cap.",
        sources=[INVESTOR_GOV_MARKET_CAP, SEC_EDGAR],
    ),
    Guide(
        slug="what-is-a-spac",
        title="What is a SPAC, and why do SPAC pages look so thin?",
        seo_title="What Is a SPAC? Blank Check Companies Explained",
        description=(
            "A SPAC is a listed shell company that raises cash to merge with a private business. See how "
            "SPACs work and how many trade on U.S. exchanges today."
        ),
        summary=(
            "A SPAC, or special purpose acquisition company, is a shell company that lists on an exchange to "
            "raise cash, then uses it to merge with a private operating business. Until that merger it has no "
            "operations, revenue or employees of its own."
        ),
        published=date(2026, 10, 14),
        updated=date(2026, 10, 14),
        image="web/img/guides/what-is-a-spac",
        image_alt="A box labelled SPAC with an arrow to a box labelled operating business.",
        sources=[SEC_SPAC_BULLETIN, SEC_EDGAR],
    ),
    Guide(
        slug="what-is-an-adr",
        title="What is an ADR, and how do foreign companies list in the U.S.?",
        seo_title="What Is an ADR? American Depositary Receipts Explained",
        description=(
            "An ADR is a U.S.-traded certificate for shares of a non-U.S. company. Learn how ADRs work, how "
            "they differ from common stock and how many are listed."
        ),
        summary=(
            "An American depositary receipt (ADR) is a certificate issued by a U.S. bank that represents shares "
            "of a non-U.S. company. It lets U.S. investors buy that company in U.S. dollars on a U.S. exchange."
        ),
        published=date(2026, 10, 14),
        updated=date(2026, 10, 14),
        image="web/img/guides/what-is-an-adr",
        image_alt="A globe linked to a U.S. exchange by a depositary bank.",
        sources=[SEC_ADR_BULLETIN, SEC_EDGAR],
    ),
]
GUIDES_BY_SLUG = {g.slug: g for g in GUIDES}
