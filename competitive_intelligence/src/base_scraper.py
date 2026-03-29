import os
import time
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from loguru import logger
from scrapling import DynamicFetcher, StealthyFetcher
from scrapling.fetchers import DynamicSession
from dotenv import load_dotenv
from .models import ScrapedStore

load_dotenv()

class BaseScraper(ABC):
    """
    Hybrid Base Class: Dynamic (Browser) + Stealthy (Requests/API).
    """

    def __init__(self, platform: str, base_url: str):
        self.platform = platform
        self.base_url = base_url
        self.fetcher = DynamicFetcher()
        self.fetcher.configure(adaptive=True) 
        self.stealthy = StealthyFetcher()
        logger.info(f"Initialized {self.platform} scraper (Hybrid)")

    def create_dynamic_session(self, **kwargs) -> DynamicSession:
        """Creates a persistent dynamic session for interaction sequences."""
        return DynamicSession(headless=True, **kwargs)

    def fetch_dynamic(self, url: str, **kwargs) -> Any:
        """Universal fetcher using the browser engine (Playwright)."""
        return self.fetcher.fetch(url, timeout=30000, network_idle=True, **kwargs)

    def fetch_stealthy(self, url: str, method: str = "GET", **kwargs) -> Any:
        """Universal fetcher using the stealthy requests engine (Fast/API)."""
        try:
            # StealthyFetcher uses .fetch() for everything in latest versions
            return self.stealthy.fetch(url, method=method, **kwargs)
        except Exception as e:
            logger.error(f"Stealthy fetch failed: {e}")
            return None

    @abstractmethod
    def scrape_address(self, lat: float, lon: float, address_name: str) -> Optional[ScrapedStore]:
        pass
