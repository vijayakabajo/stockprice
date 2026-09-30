import requests
import time
import logging
from django.conf import settings
from typing import Dict, Any, Generator

logger = logging.getLogger(__name__)

class MassiveClient:
    """Client for the Massive API."""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or settings.MASSIVE_API_KEY
        self.base_url = base_url or settings.MASSIVE_API_BASE_URL
        self.session = requests.Session()

    def get_tickers(self, market: str = "stocks", active: bool = True, limit: int = 1000) -> Generator[Dict[str, Any], None, None]:
        """
        Fetches all tickers matching the criteria.
        Yields individual ticker dictionaries.
        """
        url = f"{self.base_url}/v3/reference/tickers"
        params = {
            "market": market,
            "active": "true" if active else "false",
            "limit": limit,
            "sort": "ticker",
            "order": "asc",
            "apiKey": self.api_key
        }

        while url:
            try:
                response = self.session.get(url, params=params)
                
                # Handle rate limiting (status code 429)
                if response.status_code == 429:
                    logger.warning("Rate limit reached. Sleeping for 60 seconds.")
                    time.sleep(60)
                    continue

                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                for result in results:
                    yield result
                
                # Pagination
                url = data.get("next_url")
                # Remove API key from params if next_url already includes it
                if url:
                    if "apiKey=" in url:
                        params = {}
                    else:
                        params = {"apiKey": self.api_key}
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching from Massive API: {e}")
                raise

    def get_ticker_details(self, ticker: str) -> Dict[str, Any]:
        """
        Fetches the detailed profile for a single ticker.
        """
        url = f"{self.base_url}/v3/reference/tickers/{ticker}"
        params = {"apiKey": self.api_key}

        while True:
            try:
                response = self.session.get(url, params=params)

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning(f"Rate limit reached while fetching details for {ticker}. Sleeping 60s.")
                    time.sleep(60)
                    continue

                if response.status_code == 404:
                    logger.warning(f"Ticker {ticker} not found on Massive API.")
                    return {}

                response.raise_for_status()
                data = response.json()
                return data.get("results", {})
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching details for {ticker}: {e}")
                raise
