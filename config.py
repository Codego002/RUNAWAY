"""
Configuration centralisée
"""
from pathlib import Path

# Directories
CAPTURES_DIR = Path("captures")
DATA_DIR = Path("data")
OUTPUTS_DIR = Path("outputs")

# Files
AUTH_FILE = CAPTURES_DIR / "runway_auth.json"
CACHE_DB = DATA_DIR / "runway_cache.db"

# Create directories
CAPTURES_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)
