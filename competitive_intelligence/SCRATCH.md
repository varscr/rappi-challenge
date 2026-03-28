# Project Scratchpad & Brainstorming

## 🏗️ Pydantic Data Models (Draft)
```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ScrapedProduct(BaseModel):
    name: str
    price: float
    original_price: Optional[float] = None
    category: str # Fast Food, Retail, Pharmacy

class ScrapedStore(BaseModel):
    platform: str # Rappi, Uber Eats, DiDi
    store_name: str
    address_id: str
    delivery_fee: float
    service_fee: float
    estimated_time: str
    availability: bool
    active_discounts: List[str] = []
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    products: List[ScrapedProduct]
```

## 📍 Geographic Targets (Mexico - 50 Geocoded Addresses)

| City | Neighborhood | Type | Lat | Lon |
|---|---|---|---|---|
| CDMX | Polanco | Premium | 19.4335 | -99.1909 |
| CDMX | Condesa | Residential | 19.4149 | -99.1764 |
| CDMX | Roma Norte | Residential | 19.4183 | -99.1626 |
| CDMX | Santa Fe | Corporate | 19.3621 | -99.2687 |
| CDMX | Lomas de Chapultepec | Premium | 19.4211 | -99.2185 |
| CDMX | Iztapalapa Centro | Peripheral | 19.3576 | -99.0509 |
| CDMX | Ecatepec Centro | Peripheral | 19.3208 | -99.1515 |
| CDMX | Lindavista | Middle-Class | 19.4881 | -99.1351 |
| CDMX | Coyoacán Centro | Residential | 19.3054 | -99.1693 |
| CDMX | Colonia Del Valle | Residential | 19.3942 | -99.1670 |
| CDMX | Narvarte | Residential | 19.3916 | -99.1513 |
| CDMX | Tlalpan Centro | Residential | 19.2907 | -99.1695 |
| CDMX | Azcapotzalco Centro | Residential | 19.4880 | -99.2084 |
| CDMX | Bosques de las Lomas | Premium | 19.3975 | -99.2507 |
| Monterrey | San Pedro Garza García | Top Premium | 25.6685 | -100.3681 |
| Monterrey | San Jerónimo | Premium | 25.6829 | -100.3634 |
| Monterrey | Cumbres | Residential | 25.7127 | -100.3813 |
| Monterrey | Monterrey Centro | Corporate | 25.6723 | -100.3389 |
| Monterrey | San Nicolás de los Garza | Residential | 25.7154 | -100.2950 |
| Monterrey | Santa Catarina | Industrial/Res | 25.6825 | -100.2733 |
| Monterrey | Apodaca Centro | Industrial/Res | 25.6802 | -100.3153 |
| Monterrey | Contry | Residential | 25.6324 | -100.2764 |
| Monterrey | Carretera Nacional | Premium Res | 25.5538 | -100.2307 |
| Guadalajara | Puerta de Hierro | Premium | 20.5885 | -103.4429 |
| Guadalajara | Colonia Americana | Trendy | 20.6773 | -103.3594 |
| Guadalajara | Tlaquepaque Centro | Residential | 20.6569 | -103.3005 |
| Guadalajara | Tonalá Centro | Peripheral | 20.6464 | -103.2706 |
| Guadalajara | El Salto | Industrial | 20.6921 | -103.2862 |
| Guadalajara | Bugambilias | Residential | 20.6606 | -103.3393 |
| Puebla | Angelópolis | Premium | 19.0172 | -98.2524 |
| Puebla | Puebla Centro | Corporate | 19.0495 | -98.1976 |
| Puebla | San Andrés Cholula | Residential | 19.0220 | -98.2873 |
| Querétaro | Juriquilla | Premium Res | 20.7126 | -100.4584 |
| Querétaro | Querétaro Centro | Corporate | 20.5802 | -100.3711 |
| Querétaro | Milenio III | Residential | 20.5990 | -100.3471 |
| Mérida | Altabrisa | Premium | 21.0226 | -89.5857 |
| Mérida | Mérida Centro | Corporate | 20.9657 | -89.6311 |
| Mérida | Francisco de Montejo | Residential | 21.0275 | -89.6481 |
| Tijuana | Zona Río | Premium/Corporate | 32.5295 | -117.0200 |
| Tijuana | Tijuana Centro | Corporate | 32.5403 | -117.0371 |
| Tijuana | Playas de Tijuana | Residential | 32.5209 | -117.1198 |
| León | Cerro Gordo | Premium | 21.1603 | -101.7159 |
| León | León Centro | Corporate | 21.0957 | -101.6172 |
| León | Poliforum | Business | 21.1145 | -101.6544 |

*(Note: Coordinates with error or missing specific neighborhoods have been manually adjusted to city-center or similar high-activity points.)*

## 🍔 Standardized Product List
- **Fast Food**: Big Mac Combo, Whopper, 10-pc Nuggets.
- **Retail**: Coca-Cola 600ml, 1L Water, Diaper Pack.

## 🚀 Key Insights to Look For
- "Price Gap": Does Rappi charge more/less for the exact same Big Mac?
- "Fee War": Is DiDi subsidizing delivery fees in residential zones?
- "Speed Advantage": Is Rappi faster in CDMX compared to competitors?

## 🛰️ Visual Strategy (Force Multipliers)
### Folium (Geographic Map)
- **Concept:** An interactive `map.html` showing all 50 scrape points in Mexico.
- **Layers:**
  - `Heatmap`: Based on "Delivery Fee" (Red = High, Green = Low).
  - `Markers`: Clicking a point shows "Fastest Platform" in that zone.

### Plotly (Interactive Dashboard)
- **Concept:** A `dashboard.py` (Streamlit) for real-time data exploration.
- **Key Charts:**
  - `Sunburst`: Category (Fast Food/Retail) -> Platform -> Store.
  - `Boxplot`: Delivery fee distribution across platforms (showcasing Rappi vs. DiDi price variability).
  - `Time-Series`: Trend of estimated delivery times by hour (if temporal analysis is done).
