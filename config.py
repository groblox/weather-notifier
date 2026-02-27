# Weather Notification App Configuration

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this config file
load_dotenv(Path(__file__).parent / ".env")

# Aeris Weather API
AERIS_CLIENT_ID = os.environ["AERIS_CLIENT_ID"]
AERIS_CLIENT_SECRET = os.environ["AERIS_CLIENT_SECRET"]
AERIS_BASE_URL = "https://api.aerisapi.com"

# PWS Weather Station
STATION_ID = "pws_kalhoove43"

# Pushover Notification Service
PUSHOVER_USER_KEY = os.environ["PUSHOVER_USER_KEY"]
PUSHOVER_API_TOKEN = os.environ["PUSHOVER_API_TOKEN"]

# Thresholds
RAINFALL_THRESHOLD_INCHES = 0.25  # Notify if yesterday's rain exceeded this
TEMP_DROP_THRESHOLD_F = 20        # Notify if temp will drop by this much within 3 days
FREEZE_THRESHOLD_F = 32           # Notify when low temp will hit freezing
HEAT_WAVE_THRESHOLD_F = 95        # Notify when high temp exceeds this
HEAT_WAVE_CONSECUTIVE_DAYS = 3    # Must be this many consecutive days of high heat
SNOW_CHANCE_THRESHOLD_PERCENT = 30  # Notify if snow probability exceeds this

# Cooldown settings (prevent duplicate notifications)
COOLDOWN_FILE = "notification_cooldown.json"
TEMP_DROP_COOLDOWN_DAYS = 5       # Don't alert about temp drops within this window
FIRST_FREEZE_SEASON_START = 10    # October - start watching for first freeze
FIRST_FREEZE_SEASON_END = 12      # December - stop watching (winter established)

# Shoulder season freeze alert (March and November - 4:15 PM check)
SHOULDER_FREEZE_MONTHS = [3, 11]  # March and November
SHOULDER_FREEZE_THRESHOLD_F = 33  # Overnight low threshold
