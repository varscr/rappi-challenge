from typing import Optional
from loguru import logger
from ..base_scraper import BaseScraper
from ..models import ScrapedStore, ScrapedProduct
import json
import re
import base64
import os

# Target products for competitive comparison
TARGET_PRODUCTS = [
    "big mac",
    "mctrío",
    "mctrio",
    "nuggets",
]

# Auth ticket from DiDi session (requires login, set via DIDI_TICKET env var)
DIDI_TICKET = os.getenv("DIDI_TICKET", "")


class DiDiScraper(BaseScraper):
    """DiDi Food Mexico scraper using authenticated Playwright sessions.

    DiDi requires a valid `ticket` cookie (session auth). The scraper:
    1. Injects the ticket cookie + location payload (pl) into localStorage
    2. Navigates to the feed page to trigger API calls
    3. Intercepts `/feed/indexV2` (store list) and `/shop/index` (menu detail)
    4. Extracts store-level and product-level competitive data
    """

    def __init__(self) -> None:
        super().__init__(platform="DiDi Food", base_url="https://www.didi-food.com")

    def _build_pl(self, lat: float, lng: float, address: str) -> str:
        """Build the Base64 placement payload for DiDi's location system."""
        payload = {
            "poiId": "", "displayName": address, "address": address,
            "lat": lat, "lng": lng,
            "srcTag": "newes#takeout_around_search", "poiSrcTag": "manual_sug",
            "coordinateType": "wgs84", "cityId": 52090100,
            "city": "Ciudad de México", "searchId": "",
            "addressAll": address, "addressAllDisplay": address,
            "countryCode": "MX", "countryId": 52, "aid": "",
        }
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def scrape_address(self, lat: float, lon: float, address_name: str) -> Optional[ScrapedStore]:
        logger.info(f"[{self.platform}] Scraping: {address_name} ({lat}, {lon})")

        if not DIDI_TICKET:
            logger.error(f"[{self.platform}] No DIDI_TICKET configured. Set via env var.")
            return None

        pl = self._build_pl(lat, lon, address_name)
        feed_data = {}
        shop_data = {}

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    locale="es-MX",
                    user_agent="Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:148.0) "
                               "Gecko/20100101 Firefox/148.0",
                )
                context.add_cookies([
                    {"name": "ticket", "value": DIDI_TICKET,
                     "domain": ".didi-food.com", "path": "/"},
                ])
                page = context.new_page()

                # Capture API responses
                def on_response(response):
                    nonlocal feed_data, shop_data
                    url = response.url
                    if "c.didi-food.com" not in url:
                        return
                    try:
                        body = response.text()
                        data = json.loads(body)
                        if data.get("errno") != 0:
                            return
                        if "/feed/indexV2" in url or "/feed/search" in url:
                            feed_data = data.get("data", {})
                        elif "/shop/index" in url and data.get("data"):
                            shop_data = data.get("data", {})
                    except Exception:
                        pass

                page.on("response", on_response)

                # 1. Set up session with localStorage
                page.goto(f"{self.base_url}/es-MX/",
                          wait_until="domcontentloaded", timeout=30000)
                page.evaluate(f"""() => {{
                    localStorage.setItem('pl', '{pl}');
                    localStorage.setItem('ticket', '"{DIDI_TICKET}"');
                }}""")

                # 2. Navigate to feed — triggers /feed/indexV2 API
                feed_url = f"{self.base_url}/es-MX/food/feed/?pl={pl}"
                page.goto(feed_url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(3000)

                # 3. Find McDonald's in the feed
                mcd_shop = self._find_mcdonalds_in_feed(feed_data)
                if not mcd_shop:
                    logger.warning(f"[{self.platform}] McDonald's not in feed for {address_name}")
                    return None

                # 4. Click into the store to get product data
                shop_id = mcd_shop.get("shopId", "")
                if shop_id:
                    try:
                        mcd_link = page.locator(f"text=McDonald").first
                        if mcd_link.is_visible(timeout=3000):
                            mcd_link.click()
                            page.wait_for_timeout(5000)
                    except Exception:
                        # Navigate directly to the store page
                        store_url = (f"{self.base_url}/es-MX/food/store/{shop_id}/"
                                     f"?pl={pl}")
                        page.goto(store_url, wait_until="networkidle", timeout=60000)
                        page.wait_for_timeout(3000)

                # 5. Extract products from shop detail
                products = self._extract_products(shop_data)

                # 6. Build result from feed data (store-level metrics)
                delivery_price = mcd_shop.get("deliveryPrice", 0) / 100
                delivery_time = mcd_shop.get("deliveryTime", 0)
                min_time = mcd_shop.get("minDeliveryTime", 0)
                eta_desc = mcd_shop.get("deliveryDesc", "")

                # Convert seconds to minutes
                time_minutes = round(delivery_time / 60) if delivery_time > 60 else delivery_time

                # Extract discounts
                discounts = [
                    tip["content"]
                    for tip in mcd_shop.get("actTips", [])
                    if tip.get("content")
                ]

                status_desc = mcd_shop.get("cShopStatusDesc", "")
                is_available = mcd_shop.get("cShopStatus", 0) == 1

                result = ScrapedStore(
                    platform=self.platform,
                    store_name=mcd_shop.get("shopName", "McDonald's").strip(),
                    address_name=address_name,
                    lat=lat, lon=lon,
                    delivery_fee=delivery_price,
                    service_fee=0.0,  # DiDi doesn't show service fee separately
                    estimated_time=eta_desc or f"{time_minutes} min",
                    time_minutes=time_minutes,
                    availability=is_available,
                    source_type="API",
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
            finally:
                browser.close()

    def _find_mcdonalds_in_feed(self, feed: dict) -> Optional[dict]:
        """Find the first McDonald's store in the feed componentList."""
        for comp in feed.get("componentList", []):
            shop = comp.get("shop", {})
            name = shop.get("shopName", "").lower()
            if "mcdonald" in name:
                return shop
        return None

    def _extract_products(self, shop_detail: dict) -> list[ScrapedProduct]:
        """Extract target products from the shop detail menu (cateInfo)."""
        if not shop_detail:
            return []

        matched = []
        seen_names = set()
        categories = shop_detail.get("cateInfo", [])

        for cate in categories:
            for item in cate.get("items", []):
                name = item.get("itemName", "")
                name_lower = name.lower()

                # Skip duplicates (same item appears in multiple categories)
                if name in seen_names:
                    continue

                # Match against target products
                if not any(t in name_lower for t in TARGET_PRODUCTS):
                    continue

                # Skip unavailable items (status=2 means breakfast-only/unavailable)
                if item.get("status", 0) != 1:
                    continue

                seen_names.add(name)
                price_centavos = item.get("price", 0)
                special_centavos = item.get("specialPrice", 0)

                price = price_centavos / 100
                # specialPrice = -0.01 means no special price
                original = price if special_centavos > 0 else None
                actual_price = special_centavos / 100 if special_centavos > 0 else price

                matched.append(ScrapedProduct(
                    name=name,
                    price=actual_price,
                    original_price=original,
                    category="Fast Food",
                    status="available",
                ))

        return matched
