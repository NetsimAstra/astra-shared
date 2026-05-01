"""
defaults.py

User-visible RF default values shared across Astra services.
Import these instead of hard-coding magic numbers in individual services.
"""

DEFAULT_EIRP_DBW: float = 70.0
DEFAULT_RX_GAIN_DBI: float = 0.0

# Valid WorldCover land-class IDs for clutter override validation.
# Matches the ESA WorldCover v2 (2021) classification scheme.
VALID_CLUTTER_CLASS_IDS: frozenset[int] = frozenset({
    10,   # Tree cover
    20,   # Shrubland
    30,   # Grassland
    40,   # Cropland
    50,   # Built-up
    60,   # Bare / sparse vegetation
    70,   # Snow & ice
    80,   # Permanent water bodies
    90,   # Herbaceous wetland
    95,   # Mangroves
    100,  # Moss & lichen
})
