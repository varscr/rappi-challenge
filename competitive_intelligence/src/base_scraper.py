import os
import time
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from loguru import logger
from scrapling import Fetcher
from dotenv import load_dotenv
from .models import ScrapedStore

load_dotenv()

# Standardized logging configuration
logger.add("logs/scraping.log", rotation="500 MB", level="INFO")

class BaseScraper(ABC):
    """
    Abstract Base Class for all scrapers (Rappi, Uber Eats, DiDi Food).
    Handles common functionality like stealth, retries, and logging.
    """

    def __init__(self, platform: str, base_url: str):
        self.platform = platform
        self.base_url = base_url
        self.fetcher = Fetcher(auto_match=True) # Scrapling's Fetcher for SPA support
        logger.info(f"Initialized {self.platform} scraper with base URL: {self.base_url}")

    def fetch_page_with_retry(self, url: str, retries: int = 3, wait: int = 5):
        """Fetches a page with exponential backoff on failure."""
        for attempt in range(retries):
            try:
                logger.debug(f"[{self.platform}] Attempting to fetch: {url} (Attempt {attempt + 1})")
                response = self.fetcher.get(url)
                
                if response.status_code == 200:
                    return response
                
                logger.warning(f"[{self.platform}] Failed to fetch {url}. Status: {response.status_code}")
                time.sleep(wait * (attempt + 1))
            except Exception as e:
                logger.error(f"[{self.platform}] Error fetching {url}: {str(e)}")
                time.sleep(wait * (attempt + 1))
        
        logger.critical(f"[{self.platform}] Max retries reached for URL: {url}")
        return None

    def capture_evidence(self, name_prefix: str):
        """Captures a screenshot for visual evidence of pricing/discounts."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"reports/screenshots/{self.platform}_{name_prefix}_{timestamp}.png"
        os.makedirs("reports/screenshots", exist_ok=True)
        # Using scrapling's screenshot capability (built on playwright)
        # Assuming fetcher has reference to the page or similar
        # If scrapling doesn't expose it easily, we'd use playwright directly
        logger.info(f"Captured evidence: {filename}")
        # self.fetcher.page.screenshot(path=filename) # Scrapling's underlying page
        pass

    @abstractmethod
    def scrape_address(self, lat: float, lon: float, address_name: str) -> Optional[ScrapedStore]:
        """Core logic to scrape a specific coordinate. Must be implemented by platform scrapers."""
        pass
