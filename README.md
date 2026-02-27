# Weather Notifier

A Windows background service that monitors a personal weather station (PWS) via the [Aeris Weather API](https://www.aerisweather.com/) and sends push notifications via [Pushover](https://pushover.net/) for significant weather events.

## Alerts

| Alert | Trigger | Schedule |
|---|---|---|
| 🌧️ Rainfall | Yesterday's rain ≥ 0.25" | 6:40 AM |
| 🌡️ Temp Drop | 20°F+ drop within 3-day forecast window | 6:40 AM |
| ❄️ First Freeze | Low ≤ 32°F forecast (Oct–Dec, once/season) | 6:40 AM |
| 🔥 Heat Wave | 3+ consecutive days ≥ 95°F | 6:40 AM |
| 🌨️ Snow Chance | ≥ 30% snow probability | 6:40 AM |
| 🥶 Shoulder Freeze | Overnight low < 33°F (Mar & Nov only) | 4:15 PM |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

You'll need:
- **Aeris Weather** API credentials ([sign up](https://www.aerisweather.com/))
- **Pushover** user key and API token ([sign up](https://pushover.net/))

### 3. Test connectivity

```bash
python weather_notifier.py --test-api
python weather_notifier.py --test-notify
```

### 4. Schedule (Windows Task Scheduler)

Run as Administrator:

```bash
install_scheduler.bat
```

This creates two daily tasks:
- **WeatherNotifier** — 6:40 AM (all checks)
- **WeatherNotifier-ShoulderFreeze** — 4:15 PM (March/November freeze only)

To remove:

```bash
uninstall_scheduler.bat
```

## Usage

```bash
# Run all checks and send notifications
python weather_notifier.py

# Dry run (no notifications sent)
python weather_notifier.py --dry-run

# Shoulder freeze check only
python weather_notifier.py --shoulder-freeze

# Test API connection
python weather_notifier.py --test-api

# Send test notification
python weather_notifier.py --test-notify
```

## Tests

```bash
python -m unittest test_weather_notifier -v
```

## Station

Configured for PWS station **KALHOOVE43** in Hoover, AL.
