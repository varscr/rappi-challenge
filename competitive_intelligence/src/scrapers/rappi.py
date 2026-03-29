from typing import Optional
from loguru import logger
from ..base_scraper import BaseScraper
from ..models import ScrapedStore, ScrapedProduct
import json
import re
import base64
import urllib.parse

# Target products for competitive comparison (fuzzy matched by name)
TARGET_PRODUCTS = [
    "big mac",
    "mctrío",  # Medium combo
    "nuggets",
]


class RappiScraper(BaseScraper):
    """Rappi Mexico scraper using Next.js SSR data extraction."""

    def __init__(self) -> None:
        super().__init__(platform="Rappi", base_url="https://www.rappi.com.mx")

    def _build_location_cookie(self, lat: float, lon: float, address: str) -> str:
        """Encodes location as Base64 cookie value for Rappi's currentLocation."""
        payload = {
            "city": "Ciudad de Mexico",
            "lat": lat, "lng": lon,
            "address": address,
            "active": True, "id": 1, "isInitialLocation": True,
        }
        return urllib.parse.quote(
            base64.b64encode(json.dumps(payload).encode()).decode()
        )

    def scrape_address(self, lat: float, lon: float, address_name: str) -> Optional[ScrapedStore]:
        logger.info(f"[{self.platform}] Scraping: {address_name} ({lat}, {lon})")
        cookie_val = self._build_location_cookie(lat, lon, address_name)

        with self.create_dynamic_session() as session:
            try:
                # 1. Establish session and inject location cookie
                session.fetch(self.base_url)
                session.context.add_cookies([
                    {"name": "rappi.acceptedCookies", "value": "1",
                     "domain": ".www.rappi.com.mx", "path": "/"},
                    {"name": "currentLocation", "value": cookie_val,
                     "domain": ".www.rappi.com.mx", "path": "/"},
                ])

                # 2. Fetch search results
                url = f"{self.base_url}/search?query=mcdonalds"
                response = session.fetch(url, network_idle=True)

                if not response or response.status != 200:
                    logger.error(f"[{self.platform}] HTTP {getattr(response, 'status', '?')} for {address_name}")
                    return None

                # 3. Get HTML from response.body (response.text is empty in scrapling)
                html = response.body.decode("utf-8", errors="replace")
                if not html:
                    logger.error(f"[{self.platform}] Empty HTML for {address_name}")
                    return None

                # 4. Extract __NEXT_DATA__ JSON
                next_match = re.search(
                    r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html
                )
                if not next_match:
                    logger.warning(f"[{self.platform}] __NEXT_DATA__ not found for {address_name}")
                    return None

                data = json.loads(next_match.group(1))

                # 5. Navigate to stores in fallback
                # Key format: @"search","mcdonalds","","",#lng:-99.19,lat:19.43,,
                fallback = data.get("props", {}).get("pageProps", {}).get("fallback", {})
                stores = []
                for key, value in fallback.items():
                    if isinstance(value, dict) and "stores" in value:
                        stores = value["stores"]
                        break

                if not stores:
                    logger.warning(f"[{self.platform}] No stores in fallback for {address_name}")
                    return None

                # 6. Find McDonald's (main store, not desserts)
                target_store = None
                for s in stores:
                    name = s.get("storeName", "").lower()
                    if "mcdonald" in name and "postres" not in name:
                        target_store = s
                        break

                if not target_store:
                    logger.warning(f"[{self.platform}] McDonald's not found for {address_name}")
                    return None

                # 7. Extract products matching our targets
                products = self._extract_products(target_store.get("products", []))

                # 8. Extract promotion text
                promo_text = target_store.get("promotionText", "")
                discounts = [promo_text] if promo_text else []

                # 9. Build result
                eta_value = target_store.get("etaValue", 0)
                # etaValue comes as string like "15 min" or int
                if isinstance(eta_value, str):
                    nums = re.findall(r"\d+", eta_value)
                    eta_minutes = int(nums[0]) if nums else 25
                else:
                    eta_minutes = int(eta_value) if eta_value else 25

                result = ScrapedStore(
                    platform=self.platform,
                    store_name=target_store.get("storeName", "McDonald's").strip(),
                    address_name=address_name,
                    lat=lat, lon=lon,
                    delivery_fee=float(target_store.get("shippingCost", 0)),
                    service_fee=0.0,  # Not exposed in search results
                    estimated_time=target_store.get("eta", f"{eta_minutes} min"),
                    time_minutes=eta_minutes,
                    availability=target_store.get("isAvailable", True),
                    source_type="SSR",
                    active_discounts=discounts,
                    products=products,
                )

                logger.success(
                    f"[{self.platform}] {result.store_name} | "
                    f"Fee: ${result.delivery_fee} | ETA: {result.estimated_time} | "
                    f"{len(products)} products"
                )
                return result

            except Exception as e:
                logger.error(f"[{self.platform}] Scrape failed for {address_name}: {e}")
                return None

    def _extract_products(self, raw_products: list) -> list[ScrapedProduct]:
        """Extract target products from Rappi's product list using fuzzy name matching."""
        matched = []
        for p in raw_products:
            name = p.get("name", "")
            name_lower = name.lower()

            # Check if product matches any target
            if not any(t in name_lower for t in TARGET_PRODUCTS):
                continue

            price = p.get("price", 0)
            real_price = p.get("realPrice", None)
            original = float(real_price) if real_price and real_price != price else None

            matched.append(ScrapedProduct(
                name=name,
                price=float(price),
                original_price=original,
                category="Fast Food",
                status="available" if p.get("inStock", True) else "out_of_stock",
            ))

        return matched
