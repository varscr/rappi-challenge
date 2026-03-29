"""Competitive Intelligence scraping pipeline.

Scrapes McDonald's data from Rappi, Uber Eats, and DiDi Food across
20 representative Mexican addresses. Outputs JSON to data/raw/.
"""

import os
import json
import time
import random
import pandas as pd
from typing import List, Dict, Optional
from loguru import logger
from datetime import datetime
from src.scrapers.rappi import RappiScraper
from src.scrapers.uber import UberEatsScraper
from src.scrapers.didi import DiDiScraper
from src.models import ScrapedStore

# Rate-limiting bounds (seconds between scrape calls)
WAIT_MIN = int(os.getenv("WAIT_TIME_MIN", 5))
WAIT_MAX = int(os.getenv("WAIT_TIME_MAX", 15))


def load_addresses(file_path: str = "data/geography/mexico_addresses.csv") -> List[Dict]:
    """Load geocoded addresses from CSV."""
    if not os.path.exists(file_path):
        logger.error(f"Address file not found: {file_path}")
        return []
    df = pd.read_csv(file_path)
    logger.info(f"Loaded {len(df)} addresses from {file_path}")
    return df.to_dict("records")


def scrape_all(
    addresses: List[Dict],
    limit: Optional[int] = None,
) -> List[Dict]:
    """Run all scrapers across addresses with rate limiting.

    Args:
        addresses: List of address dicts with city, neighborhood, lat, lon.
        limit: Max addresses to scrape (None = all).

    Returns:
        List of serialized ScrapedStore dicts.
    """
    scrapers = [
        RappiScraper(),
        UberEatsScraper(),
        DiDiScraper(),
    ]

    subset = addresses[:limit] if limit else addresses
    total = len(subset) * len(scrapers)
    all_data: List[Dict] = []
    successes = 0
    failures = 0

    logger.info(f"Starting pipeline: {len(subset)} addresses x {len(scrapers)} platforms = {total} scrapes")

    for i, addr in enumerate(subset, 1):
        full_name = f"{addr['neighborhood']}, {addr['city']}"
        logger.info(f"--- Address {i}/{len(subset)}: {full_name} ---")

        for scraper in scrapers:
            try:
                store_data = scraper.scrape_address(addr["lat"], addr["lon"], full_name)
                if store_data:
                    all_data.append(store_data.model_dump())
                    successes += 1
                    logger.info(f"  [{scraper.platform}] OK ({successes + failures}/{total})")
                else:
                    failures += 1
                    logger.warning(f"  [{scraper.platform}] No data ({successes + failures}/{total})")
            except Exception as e:
                failures += 1
                logger.error(f"  [{scraper.platform}] Error: {e} ({successes + failures}/{total})")

            # Rate limit between scrapes
            wait = random.uniform(WAIT_MIN, WAIT_MAX)
            logger.debug(f"  Waiting {wait:.1f}s before next scrape...")
            time.sleep(wait)

    logger.info(f"Pipeline complete: {successes} successes, {failures} failures out of {total}")
    return all_data


def save_results(data: List[Dict], output_dir: str = "data/raw") -> str:
    """Save scrape results to timestamped JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"scrape_results_{timestamp}.json")
    with open(output_file, "w") as f:
        json.dump(data, f, indent=4, default=str)
    logger.info(f"Data saved to {output_file}")
    return output_file


def main():
    """Entry point for the scraping pipeline."""
    logger.info("=== Rappi Competitive Intelligence Pipeline ===")

    addresses = load_addresses()
    if not addresses:
        return

    data = scrape_all(addresses)
    if data:
        save_results(data)
    else:
        logger.warning("No data collected.")


if __name__ == "__main__":
    main()
