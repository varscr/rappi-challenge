from pydantic import BaseModel, Field, computed_field
from typing import Optional, List
from datetime import datetime, timezone

class ScrapedProduct(BaseModel):
    name: str = Field(..., description="Name of the product")
    price: float = Field(..., ge=0, description="Current price of the product")
    original_price: Optional[float] = Field(None, ge=0, description="Original price before discount")
    category: str = Field(..., description="Category (Fast Food, Retail, Pharmacy, etc.)")
    description: Optional[str] = Field(None, description="Product description")
    status: str = Field("available", description="available, out_of_stock")

class ScrapedStore(BaseModel):
    platform: str = Field(..., description="Source platform (Rappi, Uber Eats, DiDi Food)")
    store_name: str = Field(..., description="Name of the store/restaurant")
    address_name: str = Field(..., description="The neighborhood or address name used for the search")
    lat: float = Field(..., description="Latitude of the search location")
    lon: float = Field(..., description="Longitude of the search location")
    delivery_fee: float = Field(0.0, ge=0, description="Shipping/Delivery cost")
    service_fee: float = Field(0.0, ge=0, description="Platform service commission")
    estimated_time: str = Field(..., description="Estimated delivery time range or average")
    time_minutes: int = Field(..., ge=0, description="Normalized time in minutes for analysis and charting")
    availability: bool = Field(True, description="Whether the store is currently open/available")
    source_type: str = Field("DOM", description="DOM, API, Fallback")
    active_discounts: List[str] = Field(default_factory=list, description="List of visible promotions/coupons")
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of the scrape")
    products: List[ScrapedProduct] = Field(default_factory=list, description="List of standardized products found")

    @computed_field
    @property
    def total_final_price(self) -> float:
        """Sum of all scraped product prices + fees."""
        products_total = sum(p.price for p in self.products)
        return round(products_total + self.delivery_fee + self.service_fee, 2)
