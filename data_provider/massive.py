import logging
import time
from datetime import date
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import quote

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

# Transient network failures worth retrying. ChunkedEncodingError shows up on
# the large grouped-daily payloads when the connection is reset mid-body.
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


class MassiveError(Exception):
    """Raised when a Massive request fails after all retries."""


class MassiveClient:
    """
    Client for the Massive API.

    The API key travels in the Authorization header, never in the query
    string, so it cannot leak into logs or exception messages via a URL.
    Every request has a timeout and a bounded retry budget: a scheduled job
    must fail loudly, not hang forever.
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        timeout: float = 60,
        max_retries: int = 5,
        pool_size: int = 16,
    ):
        self.base_url = (base_url or settings.MASSIVE_API_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        api_key = api_key or settings.MASSIVE_API_KEY
        if not api_key:
            raise MassiveError("MASSIVE_API_KEY is not configured")

        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"
        # Sized for the threaded details sync, which shares this session.
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get(self, url: str, params: Optional[dict] = None, allow_404: bool = False) -> Optional[dict]:
        """
        GET with retries on 429, 5xx and transient network errors.
        Returns parsed JSON, or None on 404 when allow_404 is set.
        """
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except RETRYABLE_EXCEPTIONS as e:
                last_error = f"{type(e).__name__}"
                wait = self._backoff(attempt)
            else:
                status = response.status_code
                if status == 404 and allow_404:
                    return None
                if status == 429:
                    last_error = "429 Too Many Requests"
                    retry_after = response.headers.get("Retry-After", "")
                    wait = float(retry_after) if retry_after.isdigit() else 60
                elif status >= 500:
                    last_error = f"{status} server error"
                    wait = self._backoff(attempt)
                elif status >= 400:
                    # Client errors will not fix themselves on retry.
                    raise MassiveError(f"GET {response.url} -> {status}: {response.text[:300]}")
                else:
                    return response.json()

            if attempt < self.max_retries:
                logger.warning(
                    f"Massive request failed ({last_error}); "
                    f"retry {attempt + 1}/{self.max_retries} in {wait:.0f}s"
                )
                time.sleep(wait)

        raise MassiveError(f"GET {url} failed after {self.max_retries} retries: {last_error}")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(2 ** (attempt + 1), 60)

    def get_tickers(
        self, market: str = "stocks", active: bool = True, limit: int = 1000
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Fetches all tickers matching the criteria, following pagination.
        Yields individual ticker dictionaries.
        """
        url = "/v3/reference/tickers"
        params = {
            "market": market,
            "active": "true" if active else "false",
            "limit": limit,
            "sort": "ticker",
            "order": "asc",
        }

        while url:
            data = self._get(url, params=params)
            yield from data.get("results", [])

            # next_url already carries the cursor and the original filters.
            url = data.get("next_url")
            params = None

    def get_ticker_details(self, ticker: str) -> Dict[str, Any]:
        """
        Fetches the detailed profile for a single ticker.
        Returns {} when Massive does not know the ticker.
        """
        data = self._get(f"/v3/reference/tickers/{quote(ticker, safe='')}", allow_404=True)
        if data is None:
            logger.warning(f"Ticker {ticker} not found on Massive API.")
            return {}
        return data.get("results") or {}

    def get_exchanges(self, asset_class: str = "stocks", locale: str = "us") -> List[Dict[str, Any]]:
        """Reference list of exchanges, TRFs and SIPs for one asset class. One call, no paging."""
        data = self._get("/v3/reference/exchanges", params={"asset_class": asset_class, "locale": locale})
        return data.get("results") or []

    def get_grouped_daily(self, day: date, adjusted: bool = True) -> List[Dict[str, Any]]:
        """
        Daily OHLCV bars for every U.S. stock on one session, in one call.
        Non-trading days return an empty list.
        """
        data = self._get(
            f"/v2/aggs/grouped/locale/us/market/stocks/{day.isoformat()}",
            params={"adjusted": "true" if adjusted else "false"},
        )
        return data.get("results") or []
