# Weather Notification App Configuration
#
# All settings are loaded from .env with sensible defaults.
# Users only need to set API keys — everything else is optional.

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this config file
load_dotenv(Path(__file__).parent / ".env")


def _bool(val: str) -> bool:
    """Parse a boolean from an env var string."""
    return val.strip().lower() in ("true", "1", "yes")


def _int_list(val: str) -> list[int]:
    """Parse a comma-separated list of ints."""
    return [int(x.strip()) for x in val.split(",") if x.strip()]


# =============================================================================
#  API Credentials (required)
# =============================================================================

AERIS_CLIENT_ID = os.environ["AERIS_CLIENT_ID"]
AERIS_CLIENT_SECRET = os.environ["AERIS_CLIENT_SECRET"]
AERIS_BASE_URL = "https://api.aerisapi.com"

PUSHOVER_USER_KEY = os.environ["PUSHOVER_USER_KEY"]
PUSHOVER_API_TOKEN = os.environ["PUSHOVER_API_TOKEN"]

# =============================================================================
#  Station
# =============================================================================

STATION_ID = os.getenv("STATION_ID", "pws_kalhoove43")

# =============================================================================
#  Alert Toggles (set to false to disable individual alerts)
# =============================================================================

ALERT_RAINFALL = _bool(os.getenv("ALERT_RAINFALL", "true"))
ALERT_TEMP_DROP = _bool(os.getenv("ALERT_TEMP_DROP", "true"))
ALERT_FIRST_FREEZE = _bool(os.getenv("ALERT_FIRST_FREEZE", "true"))
ALERT_HEAT_WAVE = _bool(os.getenv("ALERT_HEAT_WAVE", "true"))
ALERT_SNOW_CHANCE = _bool(os.getenv("ALERT_SNOW_CHANCE", "true"))
ALERT_SHOULDER_FREEZE = _bool(os.getenv("ALERT_SHOULDER_FREEZE", "true"))

# =============================================================================
#  Thresholds
# =============================================================================

RAINFALL_THRESHOLD_INCHES = float(os.getenv("RAINFALL_THRESHOLD_INCHES", "0.25"))
TEMP_DROP_THRESHOLD_F = int(os.getenv("TEMP_DROP_THRESHOLD_F", "20"))
FREEZE_THRESHOLD_F = int(os.getenv("FREEZE_THRESHOLD_F", "32"))
HEAT_WAVE_THRESHOLD_F = int(os.getenv("HEAT_WAVE_THRESHOLD_F", "95"))
HEAT_WAVE_CONSECUTIVE_DAYS = int(os.getenv("HEAT_WAVE_CONSECUTIVE_DAYS", "3"))
SNOW_CHANCE_THRESHOLD_PERCENT = int(os.getenv("SNOW_CHANCE_THRESHOLD_PERCENT", "30"))
SHOULDER_FREEZE_THRESHOLD_F = int(os.getenv("SHOULDER_FREEZE_THRESHOLD_F", "33"))

# =============================================================================
#  Cooldowns (prevent duplicate notifications)
# =============================================================================

COOLDOWN_FILE = "notification_cooldown.json"
TEMP_DROP_COOLDOWN_DAYS = int(os.getenv("TEMP_DROP_COOLDOWN_DAYS", "5"))
HEAT_WAVE_COOLDOWN_DAYS = int(os.getenv("HEAT_WAVE_COOLDOWN_DAYS", "7"))
SNOW_COOLDOWN_DAYS = int(os.getenv("SNOW_COOLDOWN_DAYS", "3"))

# =============================================================================
#  Seasons
# =============================================================================

FIRST_FREEZE_SEASON_START = int(os.getenv("FIRST_FREEZE_SEASON_START", "10"))
FIRST_FREEZE_SEASON_END = int(os.getenv("FIRST_FREEZE_SEASON_END", "12"))
SHOULDER_FREEZE_MONTHS = _int_list(os.getenv("SHOULDER_FREEZE_MONTHS", "3,11"))

# =============================================================================
#  Schedule (used by setup.bat for Task Scheduler registration)
# =============================================================================

SCHEDULE_MORNING = os.getenv("SCHEDULE_MORNING", "06:40")
SCHEDULE_AFTERNOON = os.getenv("SCHEDULE_AFTERNOON", "16:15")
