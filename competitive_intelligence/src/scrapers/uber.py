from typing import Optional, List
from loguru import logger
from ..base_scraper import BaseScraper
from ..models import ScrapedStore, ScrapedProduct
import os

class UberScraper(BaseScraper):
    """
    Scraper implementation for Uber Eats Mexico.
    """
    def __init__(self):
        base_url = os.getenv("UBER_EATS_BASE_URL", "https://www.ubereats.com")
        super().__init__(platform="Uber Eats", base_url=base_url)

    def scrape_address(self, lat: float, lon: float, address_name: str) -> Optional[ScrapedStore]:
        """
        Executes the scraping flow for a specific coordinate on Uber Eats.
        """
        logger.info(f"[{self.platform}] Starting scrape for: {address_name} ({lat}, {lon})")
        
        try:
            # Simulated data for now
            dummy_store = ScrapedStore(
                platform=self.platform,
                store_name="McDonald's - Polanco",
                address_name=address_name,
                lat=lat,
                lon=lon,
                delivery_fee=19.0,
                service_fee=12.0,
                estimated_time="15-30 min",
                availability=True,
                active_discounts=["Uber One: $0 Delivery"],
                products=[
                    ScrapedProduct(name="Big Mac Combo", price=195.0, category="Fast Food"),
                    ScrapedProduct(name="10-pc Nuggets", price=135.0, category="Fast Food")
                ]
            )
            return dummy_store
        except Exception as e:
            logger.error(f"[{self.platform}] Failed to scrape address {address_name}: {str(e)}")
            return None
