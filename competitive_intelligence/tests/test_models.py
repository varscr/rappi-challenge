import pytest
from src.models import ScrapedProduct, ScrapedStore
from datetime import datetime

def test_valid_scraped_product():
    """Test creating a valid product model."""
    product = ScrapedProduct(
        name="Big Mac",
        price=150.0,
        category="Fast Food"
    )
    assert product.name == "Big Mac"
    assert product.price == 150.0

def test_invalid_product_price():
    """Test that negative prices raise a validation error."""
    with pytest.raises(ValueError):
        ScrapedProduct(name="Free Lunch?", price=-10.0, category="Test")

def test_valid_scraped_store():
    """Test creating a valid store model and its computed fields."""
    store = ScrapedStore(
        platform="Rappi",
        store_name="McDonald's Polanco",
        address_name="Polanco",
        lat=19.4326,
        lon=-99.1916,
        delivery_fee=25.0,
        service_fee=15.0,
        estimated_time="25-35 min",
        time_minutes=30,
        products=[
            ScrapedProduct(name="Big Mac", price=150.0, category="Fast Food")
        ]
    )
    assert store.store_name == "McDonald's Polanco"
    # Total Base Price = 150 (product) + 25 (delivery) + 15 (service) = 190.0
    assert store.total_base_price == 190.0

def test_invalid_store_fees():
    """Test that negative fees raise a validation error."""
    with pytest.raises(ValueError):
        ScrapedStore(
            platform="Rappi",
            store_name="Test Store",
            address_name="Test",
            lat=0, lon=0,
            delivery_fee=-5.0, # This should fail
            estimated_time="10 min"
        )
