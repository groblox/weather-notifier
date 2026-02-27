#!/usr/bin/env python3
"""
Weather Notification App for Windows 11

Monitors PWS station KALHOOVE43 for:
1. Significant rainfall (>0.25 inches previous day)
2. Major temperature drops (20°F+ within 3 days)

Sends notifications via Pushover.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Import configuration
from config import (
    AERIS_BASE_URL,
    AERIS_CLIENT_ID,
    AERIS_CLIENT_SECRET,
    ALERT_FIRST_FREEZE,
    ALERT_HEAT_WAVE,
    ALERT_RAINFALL,
    ALERT_SHOULDER_FREEZE,
    ALERT_SNOW_CHANCE,
    ALERT_TEMP_DROP,
    COOLDOWN_FILE,
    FIRST_FREEZE_SEASON_END,
    FIRST_FREEZE_SEASON_START,
    FREEZE_THRESHOLD_F,
    HEAT_WAVE_CONSECUTIVE_DAYS,
    HEAT_WAVE_COOLDOWN_DAYS,
    HEAT_WAVE_THRESHOLD_F,
    PUSHOVER_API_TOKEN,
    PUSHOVER_USER_KEY,
    RAINFALL_THRESHOLD_INCHES,
    SHOULDER_FREEZE_MONTHS,
    SHOULDER_FREEZE_THRESHOLD_F,
    SNOW_CHANCE_THRESHOLD_PERCENT,
    SNOW_COOLDOWN_DAYS,
    STATION_ID,
    TEMP_DROP_COOLDOWN_DAYS,
    TEMP_DROP_THRESHOLD_F,
)


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / 'weather_notifier.log')
    ]
)
logger = logging.getLogger(__name__)


def get_script_dir() -> Path:
    """Get the directory where this script is located."""
    return Path(__file__).parent.resolve()


def get_cooldown_data() -> dict:
    """Load cooldown data from file."""
    cooldown_path = get_script_dir() / COOLDOWN_FILE
    if cooldown_path.exists():
        try:
            with open(cooldown_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cooldown_data(data: dict):
    """Save cooldown data to file."""
    cooldown_path = get_script_dir() / COOLDOWN_FILE
    with open(cooldown_path, 'w') as f:
        json.dump(data, f, indent=2)


def is_temp_drop_on_cooldown() -> bool:
    """Check if we're in a cooldown period after a temp drop notification."""
    data = get_cooldown_data()
    last_alert = data.get('last_temp_drop_alert')
    if not last_alert:
        return False
    
    last_alert_date = datetime.fromisoformat(last_alert)
    cooldown_end = last_alert_date + timedelta(days=TEMP_DROP_COOLDOWN_DAYS)
    return datetime.now() < cooldown_end


def set_temp_drop_cooldown():
    """Set the cooldown after sending a temp drop notification."""
    data = get_cooldown_data()
    data['last_temp_drop_alert'] = datetime.now().isoformat()
    save_cooldown_data(data)


def aeris_request(endpoint: str, params: dict = None) -> dict:
    """Make a request to the Aeris Weather API."""
    url = f"{AERIS_BASE_URL}/{endpoint}"
    params = params or {}
    params['client_id'] = AERIS_CLIENT_ID
    params['client_secret'] = AERIS_CLIENT_SECRET
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    if not data.get('success'):
        raise ValueError(f"API error: {data.get('error', 'Unknown error')}")
    
    return data


def send_pushover_notification(title: str, message: str, priority: int = 0) -> bool:
    """
    Send a notification via Pushover.
    
    Priority levels:
      -2: Lowest (no notification)
      -1: Low (no sound)
       0: Normal
       1: High (bypass quiet hours)
       2: Emergency (requires acknowledgment)
    """
    url = "https://api.pushover.net/1/messages.json"
    
    payload = {
        'token': PUSHOVER_API_TOKEN,
        'user': PUSHOVER_USER_KEY,
        'title': title,
        'message': message,
        'priority': priority,
    }
    
    try:
        response = requests.post(url, data=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get('status') == 1:
            logger.info(f"Notification sent: {title}")
            return True
        else:
            logger.error(f"Pushover error: {result}")
            return False
    except requests.RequestException as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def check_rainfall() -> tuple[bool, float]:
    """
    Check yesterday's rainfall from the PWS station.
    
    Returns:
        Tuple of (should_notify, rainfall_inches)
    """
    logger.info("Checking yesterday's rainfall...")
    
    try:
        data = aeris_request(
            f"observations/summary/{STATION_ID}",
            {'from': 'yesterday', 'to': 'yesterday', 'limit': 1}
        )
        
        response = data.get('response', {})
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        
        periods = response.get('periods', [])
        if not periods:
            logger.warning("No observation data found for yesterday")
            return False, 0.0
        
        precip = periods[0].get('summary', {}).get('precip', {})
        rainfall = precip.get('totalIN', 0) or 0
        
        logger.info(f"Yesterday's rainfall: {rainfall:.2f} inches")
        
        should_notify = rainfall >= RAINFALL_THRESHOLD_INCHES
        return should_notify, rainfall
        
    except Exception as e:
        logger.error(f"Error checking rainfall: {e}")
        return False, 0.0


def check_temp_drop() -> tuple[bool, float, str]:
    """
    Check for significant temperature drops in the 7-day forecast.
    
    Looks for a drop of TEMP_DROP_THRESHOLD_F or more within any 3-day window.
    
    Returns:
        Tuple of (should_notify, max_drop, description)
    """
    logger.info("Checking for temperature drops...")
    
    if is_temp_drop_on_cooldown():
        logger.info("Temperature drop notification is on cooldown, skipping check")
        return False, 0.0, ""
    
    try:
        data = aeris_request(
            f"forecasts/{STATION_ID}",
            {'format': 'json', 'filter': 'day', 'limit': 7}
        )
        
        response = data.get('response', {})
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        
        periods = response.get('periods', [])
        if len(periods) < 2:
            logger.warning("Not enough forecast data")
            return False, 0.0, ""
        
        # Extract high temperatures for each day
        temps = []
        for period in periods:
            max_temp = period.get('maxTempF')
            date_str = period.get('dateTimeISO', '')[:10]
            if max_temp is not None:
                temps.append({'date': date_str, 'high': max_temp})
        
        logger.info(f"Forecast temperatures: {temps}")
        
        # Find the maximum drop within any 3-day window
        max_drop = 0
        drop_desc = ""
        
        for i in range(len(temps)):
            for j in range(i + 1, min(i + 4, len(temps))):  # Within 3 days
                drop = temps[i]['high'] - temps[j]['high']
                if drop > max_drop:
                    max_drop = drop
                    drop_desc = f"{temps[i]['date']} ({temps[i]['high']}°F) → {temps[j]['date']} ({temps[j]['high']}°F)"
        
        logger.info(f"Maximum temperature drop: {max_drop:.1f}°F ({drop_desc})")
        
        should_notify = max_drop >= TEMP_DROP_THRESHOLD_F
        return should_notify, max_drop, drop_desc
        
    except Exception as e:
        logger.error(f"Error checking temperature drop: {e}")
        return False, 0.0, ""


def check_first_freeze() -> tuple[bool, float, str]:
    """
    Check if the first freeze of the season is coming.
    
    Only alerts during Oct-Dec if:
    - We haven't already alerted this season
    - Low temp will hit 32°F or below in the forecast
    
    Returns:
        Tuple of (should_notify, low_temp, date_string)
    """
    now = datetime.now()
    
    # Only check during freeze season (Oct-Dec)
    if not (FIRST_FREEZE_SEASON_START <= now.month <= FIRST_FREEZE_SEASON_END):
        logger.info(f"Not freeze season (month {now.month}), skipping first freeze check")
        return False, 0.0, ""
    
    # Check if we already alerted this season
    data = get_cooldown_data()
    last_freeze_alert = data.get('first_freeze_alert_year')
    if last_freeze_alert == now.year:
        logger.info("Already sent first freeze alert this season")
        return False, 0.0, ""
    
    logger.info("Checking for first freeze of season...")
    
    try:
        data = aeris_request(
            f"forecasts/{STATION_ID}",
            {'format': 'json', 'filter': 'day', 'limit': 7}
        )
        
        response = data.get('response', {})
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        
        periods = response.get('periods', [])
        
        for period in periods:
            min_temp = period.get('minTempF')
            date_str = period.get('dateTimeISO', '')[:10]
            
            if min_temp is not None and min_temp <= FREEZE_THRESHOLD_F:
                logger.info(f"First freeze detected: {min_temp}°F on {date_str}")
                return True, min_temp, date_str
        
        logger.info("No freeze in forecast")
        return False, 0.0, ""
        
    except Exception as e:
        logger.error(f"Error checking first freeze: {e}")
        return False, 0.0, ""


def set_first_freeze_cooldown():
    """Mark that we've sent the first freeze alert this season."""
    data = get_cooldown_data()
    data['first_freeze_alert_year'] = datetime.now().year
    save_cooldown_data(data)


def check_heat_wave() -> tuple[bool, list, int]:
    """
    Check for heat wave conditions (consecutive days of extreme heat).
    
    Returns:
        Tuple of (should_notify, hot_days_list, consecutive_count)
    """
    logger.info("Checking for heat wave conditions...")
    
    # Check cooldown
    data = get_cooldown_data()
    last_heat_alert = data.get('last_heat_wave_alert')
    if last_heat_alert:
        last_alert_date = datetime.fromisoformat(last_heat_alert)
        if datetime.now() < last_alert_date + timedelta(days=HEAT_WAVE_COOLDOWN_DAYS):
            logger.info("Heat wave notification on cooldown")
            return False, [], 0
    
    try:
        data = aeris_request(
            f"forecasts/{STATION_ID}",
            {'format': 'json', 'filter': 'day', 'limit': 7}
        )
        
        response = data.get('response', {})
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        
        periods = response.get('periods', [])
        
        # Find consecutive hot days
        hot_days = []
        current_streak = []
        
        for period in periods:
            max_temp = period.get('maxTempF')
            date_str = period.get('dateTimeISO', '')[:10]
            
            if max_temp is not None and max_temp >= HEAT_WAVE_THRESHOLD_F:
                current_streak.append({'date': date_str, 'high': max_temp})
            else:
                if len(current_streak) >= HEAT_WAVE_CONSECUTIVE_DAYS:
                    hot_days = current_streak
                    break
                current_streak = []
        
        # Check final streak
        if len(current_streak) >= HEAT_WAVE_CONSECUTIVE_DAYS and not hot_days:
            hot_days = current_streak
        
        if hot_days:
            logger.info(f"Heat wave detected: {len(hot_days)} consecutive days >= {HEAT_WAVE_THRESHOLD_F}°F")
            return True, hot_days, len(hot_days)
        
        logger.info("No heat wave in forecast")
        return False, [], 0
        
    except Exception as e:
        logger.error(f"Error checking heat wave: {e}")
        return False, [], 0


def set_heat_wave_cooldown():
    """Set cooldown after heat wave alert."""
    data = get_cooldown_data()
    data['last_heat_wave_alert'] = datetime.now().isoformat()
    save_cooldown_data(data)


def check_snow_chance() -> tuple[bool, float, str]:
    """
    Check if there's a chance of snow in the forecast.
    
    Returns:
        Tuple of (should_notify, snow_probability, date_string)
    """
    logger.info("Checking for snow in forecast...")
    
    # Check cooldown (once per week for snow alerts)
    data = get_cooldown_data()
    last_snow_alert = data.get('last_snow_alert')
    if last_snow_alert:
        last_alert_date = datetime.fromisoformat(last_snow_alert)
        if datetime.now() < last_alert_date + timedelta(days=SNOW_COOLDOWN_DAYS):
            logger.info("Snow notification on cooldown")
            return False, 0.0, ""
    
    try:
        data = aeris_request(
            f"forecasts/{STATION_ID}",
            {'format': 'json', 'filter': 'day', 'limit': 7}
        )
        
        response = data.get('response', {})
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        
        periods = response.get('periods', [])
        
        for period in periods:
            # Check for snow in the weather description or snow accumulation
            weather = period.get('weather', '').lower()
            weather_primary = period.get('weatherPrimary', '').lower()
            snow_in = period.get('snowIN', 0) or 0
            date_str = period.get('dateTimeISO', '')[:10]
            pop = period.get('pop', 0) or 0  # Probability of precipitation
            
            has_snow = 'snow' in weather or 'snow' in weather_primary or snow_in > 0
            
            if has_snow and pop >= SNOW_CHANCE_THRESHOLD_PERCENT:
                logger.info(f"Snow chance detected: {pop}% on {date_str}")
                return True, pop, date_str
        
        logger.info("No significant snow chance in forecast")
        return False, 0.0, ""
        
    except Exception as e:
        logger.error(f"Error checking snow chance: {e}")
        return False, 0.0, ""


def set_snow_cooldown():
    """Set cooldown after snow alert."""
    data = get_cooldown_data()
    data['last_snow_alert'] = datetime.now().isoformat()
    save_cooldown_data(data)


def check_shoulder_freeze() -> tuple[bool, float, str]:
    """
    Check for overnight freeze during shoulder seasons (March, November).
    
    This is designed to run at 4:15 PM to give advance warning for tonight's freeze.
    
    Returns:
        Tuple of (should_notify, low_temp, description)
    """
    now = datetime.now()
    
    # Only check during shoulder months
    if now.month not in SHOULDER_FREEZE_MONTHS:
        logger.info(f"Not shoulder season (month {now.month}), skipping shoulder freeze check")
        return False, 0.0, ""
    
    # Check for cooldown (don't notify twice in same day)
    data = get_cooldown_data()
    last_alert = data.get('last_shoulder_freeze_alert')
    if last_alert:
        last_date = datetime.fromisoformat(last_alert).date()
        if last_date == now.date():
            logger.info("Already sent shoulder freeze alert today")
            return False, 0.0, ""
    
    logger.info("Checking for overnight freeze (shoulder season)...")
    
    try:
        # Get forecast - we want tonight's low
        data = aeris_request(
            f"forecasts/{STATION_ID}",
            {'format': 'json', 'filter': 'daynight', 'limit': 4}
        )
        
        response = data.get('response', {})
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        
        periods = response.get('periods', [])
        
        # Look for tonight or tomorrow night
        for period in periods:
            is_day = period.get('isDay', True)
            min_temp = period.get('minTempF')
            date_str = period.get('dateTimeISO', '')[:10]
            
            # We want night periods
            if not is_day and min_temp is not None:
                if min_temp < SHOULDER_FREEZE_THRESHOLD_F:
                    desc = f"Tonight's low: {min_temp}F on {date_str}"
                    logger.info(f"Shoulder freeze detected: {desc}")
                    return True, min_temp, desc
                else:
                    logger.info(f"Tonight's low ({min_temp}F) above threshold ({SHOULDER_FREEZE_THRESHOLD_F}F)")
                    return False, 0.0, ""
        
        logger.info("No overnight freeze expected")
        return False, 0.0, ""
        
    except Exception as e:
        logger.error(f"Error checking shoulder freeze: {e}")
        return False, 0.0, ""


def set_shoulder_freeze_cooldown():
    """Set cooldown after shoulder freeze alert (once per day)."""
    data = get_cooldown_data()
    data['last_shoulder_freeze_alert'] = datetime.now().isoformat()
    save_cooldown_data(data)


def run_shoulder_freeze_check(test_mode: bool = False):
    """Run only the shoulder season freeze check (for 4:15 PM scheduled task)."""
    logger.info("=" * 50)
    logger.info("Running shoulder season freeze check...")
    logger.info(f"Station: {STATION_ID}")
    logger.info("=" * 50)
    
    if not ALERT_SHOULDER_FREEZE:
        logger.info("Shoulder freeze alert is disabled, skipping")
        return
    
    should_notify, low_temp, desc = check_shoulder_freeze()
    if should_notify:
        title = "Freeze Warning Tonight!"
        message = f"Protect your plants! {desc}"
        
        if test_mode:
            logger.info(f"[TEST MODE] Would send notification: {title} - {message}")
        else:
            if send_pushover_notification(title, message, priority=1):
                set_shoulder_freeze_cooldown()
    
    logger.info("Shoulder freeze check complete.")


def run_checks(test_mode: bool = False):


    """Run all weather checks and send notifications as needed."""
    logger.info("=" * 50)
    logger.info("Starting weather check...")
    logger.info(f"Station: {STATION_ID}")
    logger.info("=" * 50)
    
    # Check rainfall
    if ALERT_RAINFALL:
        should_notify_rain, rainfall = check_rainfall()
        if should_notify_rain:
            title = "🌧️ Significant Rainfall Yesterday"
            message = f"Station {STATION_ID} recorded {rainfall:.2f} inches of rain yesterday."
            
            if test_mode:
                logger.info(f"[TEST MODE] Would send notification: {title} - {message}")
            else:
                send_pushover_notification(title, message)
    else:
        logger.info("Rainfall alert disabled, skipping")
    
    # Check temperature drop
    if ALERT_TEMP_DROP:
        should_notify_temp, max_drop, drop_desc = check_temp_drop()
        if should_notify_temp:
            title = "Major Temperature Drop Coming"
            message = f"Expect a {max_drop:.0f}F temperature drop!\n{drop_desc}"
            
            if test_mode:
                logger.info(f"[TEST MODE] Would send notification: {title} - {message}")
            else:
                if send_pushover_notification(title, message, priority=1):
                    set_temp_drop_cooldown()
    else:
        logger.info("Temp drop alert disabled, skipping")
    
    # Check first freeze of season
    if ALERT_FIRST_FREEZE:
        should_notify_freeze, freeze_temp, freeze_date = check_first_freeze()
        if should_notify_freeze:
            title = "First Freeze of Season Coming!"
            message = f"Low of {freeze_temp:.0f}F expected on {freeze_date}. Protect plants and pipes!"
            
            if test_mode:
                logger.info(f"[TEST MODE] Would send notification: {title} - {message}")
            else:
                if send_pushover_notification(title, message, priority=1):
                    set_first_freeze_cooldown()
    else:
        logger.info("First freeze alert disabled, skipping")
    
    # Check heat wave
    if ALERT_HEAT_WAVE:
        should_notify_heat, hot_days, heat_count = check_heat_wave()
        if should_notify_heat:
            title = "Heat Wave Alert!"
            temps_str = ", ".join([f"{d['date']}: {d['high']}F" for d in hot_days[:3]])
            message = f"{heat_count} days of extreme heat ({HEAT_WAVE_THRESHOLD_F}F+) forecast!\n{temps_str}"
            
            if test_mode:
                logger.info(f"[TEST MODE] Would send notification: {title} - {message}")
            else:
                if send_pushover_notification(title, message, priority=1):
                    set_heat_wave_cooldown()
    else:
        logger.info("Heat wave alert disabled, skipping")
    
    # Check snow chance
    if ALERT_SNOW_CHANCE:
        should_notify_snow, snow_prob, snow_date = check_snow_chance()
        if should_notify_snow:
            title = "Snow in the Forecast!"
            message = f"{snow_prob:.0f}% chance of snow on {snow_date}."
            
            if test_mode:
                logger.info(f"[TEST MODE] Would send notification: {title} - {message}")
            else:
                if send_pushover_notification(title, message):
                    set_snow_cooldown()
    else:
        logger.info("Snow chance alert disabled, skipping")
    
    logger.info("Weather check complete.")


def test_api():
    """Test API connectivity and display current data."""
    print("\n" + "=" * 60)
    print("TESTING AERIS WEATHER API CONNECTION")
    print("=" * 60)
    
    try:
        # Test current observations
        print(f"\n📍 Station: {STATION_ID}")
        data = aeris_request(f"observations/{STATION_ID}", {'limit': 1})
        obs = data.get('response', {})
        if isinstance(obs, list) and len(obs) > 0:
            obs = obs[0]
        
        current = obs.get('ob', {})
        print(f"🌡️  Current temp: {current.get('tempF', 'N/A')}°F")
        print(f"💧 Humidity: {current.get('humidity', 'N/A')}%")
        
        # Test yesterday's summary
        print("\n📊 Yesterday's Summary:")
        should_rain, rainfall = check_rainfall()
        print(f"   Rainfall: {rainfall:.2f} inches")
        print(f"   Would notify: {should_rain} (threshold: {RAINFALL_THRESHOLD_INCHES}\")")
        
        # Test forecast
        print("\n📅 Temperature Forecast:")
        should_temp, max_drop, desc = check_temp_drop()
        print(f"   Max drop in 7-day forecast: {max_drop:.1f}°F")
        print(f"   Would notify: {should_temp} (threshold: {TEMP_DROP_THRESHOLD_F}°F)")
        if desc:
            print(f"   Details: {desc}")
        
        print("\n✅ API connection successful!")
        
    except Exception as e:
        print(f"\n❌ API error: {e}")
        sys.exit(1)


def test_notification():
    """Send a test notification via Pushover."""
    print("\n" + "=" * 60)
    print("TESTING PUSHOVER NOTIFICATION")
    print("=" * 60)
    
    title = "🧪 Weather App Test"
    message = f"Test notification from Weather Notifier.\nStation: {STATION_ID}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    if send_pushover_notification(title, message):
        print("\n✅ Test notification sent successfully!")
        print("   Check your Pushover app for the message.")
    else:
        print("\n❌ Failed to send test notification.")
        print("   Check your Pushover credentials in config.py")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Weather Notification App - Monitors PWS station for rainfall and temperature drops'
    )
    parser.add_argument(
        '--test-api',
        action='store_true',
        help='Test API connectivity and display current data'
    )
    parser.add_argument(
        '--test-notify',
        action='store_true',
        help='Send a test notification via Pushover'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run checks but do not send notifications'
    )
    parser.add_argument(
        '--shoulder-freeze',
        action='store_true',
        help='Run only the shoulder season freeze check (for 4:15 PM task)'
    )
    
    args = parser.parse_args()
    
    if args.test_api:
        test_api()
    elif args.test_notify:
        test_notification()
    elif args.shoulder_freeze:
        run_shoulder_freeze_check(test_mode=args.dry_run)
    else:
        run_checks(test_mode=args.dry_run)


if __name__ == '__main__':
    main()
