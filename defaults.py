"""
defaults.py

User-visible RF default values shared across Astra services.
Import these instead of hard-coding magic numbers in individual services.
"""

DEFAULT_EIRP_DBW: float = 70.0
DEFAULT_RX_GAIN_DBI: float = 0.0
DEFAULT_MODULATION: str = "QPSK"
DEFAULT_CODE_RATE: float = 1.0
DEFAULT_COMPUTE_PFD: bool = True
DEFAULT_PFD_LIMIT_BAND = None
DEFAULT_PFD_REF_BW_HZ: float = 1.0e6
