import os
import re
import json
from typing import List, Dict
from loguru import logger
from datetime import datetime
from src.scrapers.rappi import RappiScraper
from src.scrapers.uber import UberScraper
from src.scrapers.didi import DiDiScraper
from src.models import ScrapedStore

def parse_addresses_from_scratch(file_path: str = "SCRATCH.md") -> List[Dict]:
    """Parses the geocoded addresses table from SCRATCH.md."""
    addresses = []
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return addresses

    with open(file_path, "r") as f:
        content = f.read()
    
    # Simple regex to find table rows with coordinates
    # | City | Neighborhood | Type | Lat | Lon |
    pattern = r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([-.\d]+)\s*\|\s*([-.\d]+)\s*\|"
    matches = re.findall(pattern, content)
    
    for match in matches:
        # Skip the header or separator row
        if "City" in match[0] or "-" in match[3]:
            continue
            
        try:
            addresses.append({
                "city": match[0].strip(),
                "neighborhood": match[1].strip(),
                "type": match[2].strip(),
                "lat": float(match[3]),
                "lon": float(match[4])
            })
        except (ValueError, IndexError):
            continue
    
    logger.info(f"Successfully parsed {len(addresses)} addresses from {file_path}")
    return addresses

def main():
    logger.info("Starting Rappi Competitive Intelligence Scraper")
    
    # 1. Load addresses
    addresses = parse_addresses_from_scratch()
    
    # 2. Initialize scrapers
    scrapers = [
        RappiScraper(),
        UberScraper(),
        DiDiScraper()
    ]
    
    all_data = []
    
    # 3. Iterate and scrape (for now, just a few to test)
    # Note: In production, we'd use concurrency or loop through all 50
    test_limit = 3 # Limiting for initial test run
    
    for addr in addresses[:test_limit]:
        logger.info(f"Scraping zone: {addr['neighborhood']}, {addr['city']}")
        
        for scraper in scrapers:
            try:
                store_data = scraper.scrape_address(addr["lat"], addr["lon"], addr["neighborhood"])
                if store_data:
                    # Convert Pydantic model to dict for saving
                    all_data.append(store_data.model_dump())
            except Exception as e:
                logger.error(f"Error running {scraper.platform} scraper: {str(e)}")

    # 4. Save raw data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"data/raw/scrape_results_{timestamp}.json"
    os.makedirs("data/raw", exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(all_data, f, indent=4, default=str)
    
    logger.info(f"Scraping complete. Data saved to {output_file}")
    logger.info(f"Total records collected: {len(all_data)}")

if __name__ == "__main__":
    main()
