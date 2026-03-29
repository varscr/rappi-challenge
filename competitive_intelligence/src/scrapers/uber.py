from typing import Optional
from loguru import logger
from ..base_scraper import BaseScraper
from ..models import ScrapedStore, ScrapedProduct
import json
import re
import base64

# Target products for competitive comparison
TARGET_PRODUCTS = [
    "big mac",
    "mctrío",
    "mctrio",
    "nuggets",
]


class UberEatsScraper(BaseScraper):
    """Uber Eats Mexico scraper.

    Two-phase extraction:
    1. Search feed API (getSearchFeedV1) → store-level: ETA, rating, availability, promos
    2. Store page SSR HTML → JSON-LD schema with full menu and real prices

    No auth required — all data is public via SSR.
    """

    def __init__(self) -> None:
        super().__init__(platform="Uber Eats", base_url="https://www.ubereats.com/mx")

    def _build_pl(self, lat: float, lon: float, address: str) -> str:
        """Build Base64 placement param for Uber's location system."""
        return base64.b64encode(
            json.dumps({"address": address, "latitude": lat, "longitude": lon}).encode()
        ).decode()

    def scrape_address(self, lat: float, lon: float, address_name: str) -> Optional[ScrapedStore]:
        logger.info(f"[{self.platform}] Scraping: {address_name} ({lat}, {lon})")

        pl = self._build_pl(lat, lon, address_name)
        search_feed = {}
        store_html = ""

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    locale="es-MX",
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    geolocation={"latitude": lat, "longitude": lon},
                    permissions=["geolocation"],
                )
                page = context.new_page()

                # Capture search feed API
                def on_response(response):
                    nonlocal search_feed, store_html
                    url = response.url
                    try:
                        if "getSearchFeedV1" in url:
                            search_feed = json.loads(response.text()).get("data", {})
                        elif "/store/" in url and response.status == 200:
                            ct = response.headers.get("content-type", "")
                            if "text/html" in ct:
                                store_html = response.text()
                    except Exception:
                        pass

                page.on("response", on_response)

                # Phase 1: Search for McDonald's to get store-level data
                search_url = f"{self.base_url}/search?q=mcdonalds&pl={pl}"
                page.goto(search_url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(3000)

                # Find McDonald's in search results
                mcd_store = self._find_mcdonalds_in_feed(search_feed)
                if not mcd_store:
                    logger.warning(f"[{self.platform}] McDonald's not in search feed for {address_name}")
                    return None

                # Phase 2: Navigate to store page for menu/product data
                action_url = mcd_store.get("actionUrl", "")
                if action_url:
                    store_page_url = f"https://www.ubereats.com{action_url}?pl={pl}"
                    logger.info(f"[{self.platform}] Loading store page: {action_url}")
                    page.goto(store_page_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000)

                # Extract products from JSON-LD
                products = self._extract_products_from_jsonld(store_html)

                # Extract delivery fee from HTML
                delivery_fee = self._extract_delivery_fee(store_html)

                # Build result from search feed data
                tracking = mcd_store.get("tracking", {}).get("storePayload", {})
                etd_info = tracking.get("etdInfo", {})
                eta_range = etd_info.get("dropoffETARange", {})
                rating_info = tracking.get("ratingInfo", {})

                eta_min = eta_range.get("min", 0)
                eta_max = eta_range.get("max", 0)
                eta_text = f"{eta_min}-{eta_max} min" if eta_min != eta_max else f"{eta_min} min"
                time_minutes = eta_range.get("raw", eta_min) or 25

                availability_state = tracking.get("storeAvailablityState", "")
                is_available = availability_state == "ACCEPTING_ORDERS"

                # Extract promotions from signposts
                discounts = [
                    sp["text"]
                    for sp in mcd_store.get("signposts", [])
                    if sp.get("text")
                ]

                store_name = mcd_store.get("title", {}).get("text", "McDonald's").strip()

                result = ScrapedStore(
                    platform=self.platform,
                    store_name=store_name,
                    address_name=address_name,
                    lat=lat, lon=lon,
                    delivery_fee=delivery_fee,
                    service_fee=0.0,  # Not exposed in public SSR
                    estimated_time=eta_text,
                    time_minutes=time_minutes,
                    availability=is_available,
                    source_type="SSR",
                    active_discounts=discounts,
                    products=products,
                )

                logger.success(
                    f"[{self.platform}] {store_name} | "
                    f"Fee: ${delivery_fee} | ETA: {eta_text} | "
                    f"{len(products)} products | "
                    f"{'OPEN' if is_available else 'CLOSED'}"
                )
                return result

            except Exception as e:
                logger.error(f"[{self.platform}] Scrape failed for {address_name}: {e}")
                return None
            finally:
                browser.close()

    def _find_mcdonalds_in_feed(self, feed: dict) -> Optional[dict]:
        """Find the main McDonald's store in search feed items."""
        for item in feed.get("feedItems", []):
            store = item.get("store", {})
            title = store.get("title", {}).get("text", "").lower()
            # Skip variants (Postres, Pollos, McCafé)
            if "mcdonald" in title and not any(x in title for x in ["postres", "pollos", "mccafé"]):
                return store
        return None

    def _extract_products_from_jsonld(self, html: str) -> list[ScrapedProduct]:
        """Extract products from JSON-LD Restaurant schema in store page HTML."""
        if not html:
            return []

        json_ld_blocks = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL,
        )

        matched = []
        seen_names = set()

        for block in json_ld_blocks:
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue

            if data.get("@type") != "Restaurant":
                continue

            sections = data.get("hasMenu", {}).get("hasMenuSection", [])
            for section in sections:
                for item in section.get("hasMenuItem", []):
                    name = item.get("name", "")
                    name_lower = name.lower()

                    if name in seen_names:
                        continue
                    if not any(t in name_lower for t in TARGET_PRODUCTS):
                        continue

                    seen_names.add(name)
                    offers = item.get("offers", {})
                    price = float(offers.get("price", 0))

                    matched.append(ScrapedProduct(
                        name=name,
                        price=price,
                        original_price=None,
                        category="Fast Food",
                        status="available",
                    ))

        return matched

    def _extract_delivery_fee(self, html: str) -> float:
        """Extract delivery fee from store page HTML content."""
        if not html:
            return 0.0

        # Check for free delivery first
        if re.search(r'(?:Env[ií]o|Delivery)\s*(?:gratis|free)', html, re.IGNORECASE):
            return 0.0

        # Look for specific delivery fee patterns (tight context)
        # Uber shows "$X.XX Delivery Fee" or "Costo de envío: $X"
        fee_patterns = [
            r'\$\s*(\d+(?:\.\d{2})?)\s*(?:Delivery Fee|de envío)',
            r'(?:Costo de envío|Tarifa de envío)[^$]{0,20}\$\s*(\d+(?:\.\d{2})?)',
            r'deliveryFee["\s:]+(\d+(?:\.\d+)?)',
        ]
        for pattern in fee_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                fee = float(match.group(1))
                if fee <= 99:  # Delivery fees are typically < $100 MXN
                    return fee

        return 0.0
