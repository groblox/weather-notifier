<p align="center">
  <h1 align="center">🌦️ Weather Notifier</h1>
  <p align="center">
    Automated weather monitoring and push notifications for your personal weather station.
    <br />
    <em>Built for Windows · Powered by Aeris Weather · Alerts via Pushover</em>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/platform-Windows_11-0078D4?logo=windows&logoColor=white" alt="Windows 11">
  <img src="https://img.shields.io/badge/notifications-Pushover-249DF1?logo=pushbullet&logoColor=white" alt="Pushover">
  <img src="https://img.shields.io/badge/data-Aeris_Weather_API-FF6B35" alt="Aeris Weather">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

---

## Overview

Weather Notifier is a lightweight background service that monitors a personal weather station (PWS) via the [Aeris Weather API](https://www.aerisweather.com/) and delivers push notifications through [Pushover](https://pushover.net/) when significant weather events are detected.

It runs silently via Windows Task Scheduler — no browser, no dashboard, just timely alerts delivered straight to your phone.

## 🚨 Alert Types

<table>
  <tr>
    <th>Alert</th>
    <th>Trigger</th>
    <th>Cooldown</th>
    <th>Schedule</th>
  </tr>
  <tr>
    <td>🌧️ <strong>Significant Rainfall</strong></td>
    <td>Yesterday's total ≥ 0.25 in</td>
    <td>—</td>
    <td>6:40 AM</td>
  </tr>
  <tr>
    <td>🌡️ <strong>Temperature Drop</strong></td>
    <td>20°F+ drop within a 3-day forecast window</td>
    <td>5 days</td>
    <td>6:40 AM</td>
  </tr>
  <tr>
    <td>❄️ <strong>First Freeze of Season</strong></td>
    <td>Low ≤ 32°F in forecast (Oct–Dec only)</td>
    <td>Once per season</td>
    <td>6:40 AM</td>
  </tr>
  <tr>
    <td>🔥 <strong>Heat Wave</strong></td>
    <td>3+ consecutive days ≥ 95°F</td>
    <td>7 days</td>
    <td>6:40 AM</td>
  </tr>
  <tr>
    <td>🌨️ <strong>Snow Chance</strong></td>
    <td>≥ 30% snow probability in forecast</td>
    <td>3 days</td>
    <td>6:40 AM</td>
  </tr>
  <tr>
    <td>🥶 <strong>Shoulder Season Freeze</strong></td>
    <td>Overnight low &lt; 33°F (Mar &amp; Nov)</td>
    <td>Once per day</td>
    <td>4:15 PM</td>
  </tr>
</table>

> All thresholds are configurable in `config.py`.

## 🏗️ Architecture

```
┌──────────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  Windows Task        │     │  Aeris Weather API   │     │    Pushover      │
│  Scheduler           │────▶│                      │────▶│                  │
│                      │     │  • Observations      │     │  Push to phone   │
│  6:40 AM  All checks │     │  • 7-day Forecast    │     │  with priority   │
│  4:15 PM  Freeze only│     └─────────────────────┘     └──────────────────┘
└──────────────────────┘              │
           │                          ▼
           │               ┌─────────────────────┐
           └──────────────▶│  weather_notifier.py │
                           │                      │
                           │  • Rainfall check    │
                           │  • Temp drop check   │
                           │  • Freeze checks     │
                           │  • Heat wave check   │
                           │  • Snow check        │
                           │  • Cooldown system    │
                           └─────────────────────┘
```

## 📁 Project Structure

```
weather-notifier/
├── weather_notifier.py       # Main application — all check logic
├── config.py                 # Configuration & thresholds (loads .env)
├── test_weather_notifier.py  # 45 unit tests (mocked API, no network)
├── requirements.txt          # Python dependencies
├── install_scheduler.bat     # Register Windows scheduled tasks
├── uninstall_scheduler.bat   # Remove scheduled tasks
├── .env.example              # Template for API credentials
└── .env                      # Your API keys (gitignored)
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** with `pip`
- **Windows 10/11** (for Task Scheduler integration)
- [Aeris Weather](https://www.aerisweather.com/) API credentials
- [Pushover](https://pushover.net/) account with an application token

### 1. Clone & Install

```bash
git clone https://github.com/groblox/weather-notifier.git
cd weather-notifier
pip install -r requirements.txt
```

### 2. Configure

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Then edit `.env`:

```ini
AERIS_CLIENT_ID=your_aeris_client_id
AERIS_CLIENT_SECRET=your_aeris_client_secret
PUSHOVER_USER_KEY=your_pushover_user_key
PUSHOVER_API_TOKEN=your_pushover_api_token
```

### 3. Verify Setup

```bash
# Test API connectivity
python weather_notifier.py --test-api

# Send a test push notification
python weather_notifier.py --test-notify
```

### 4. Schedule

Run `install_scheduler.bat` **as Administrator** to register two daily tasks:

| Task | Time | Checks |
|------|------|--------|
| `WeatherNotifier` | 6:40 AM | All alerts |
| `WeatherNotifier-ShoulderFreeze` | 4:15 PM | Shoulder freeze only (Mar/Nov) |

To uninstall: run `uninstall_scheduler.bat` as Administrator.

## 🛠️ CLI Reference

```
usage: weather_notifier.py [-h] [--test-api] [--test-notify] [--dry-run] [--shoulder-freeze]

options:
  --test-api          Test API connectivity and display current data
  --test-notify       Send a test notification via Pushover
  --dry-run           Run all checks but suppress notifications
  --shoulder-freeze   Run only the shoulder season freeze check
```

**Examples:**

```bash
# Full run with live notifications
python weather_notifier.py

# Preview what would alert without sending anything
python weather_notifier.py --dry-run

# Shoulder freeze check only (what the 4:15 PM task runs)
python weather_notifier.py --shoulder-freeze
```

## 🧪 Testing

The test suite uses `unittest` with fully mocked API calls — no network access, no API keys needed:

```bash
python -m unittest test_weather_notifier -v
```

**Coverage: 45 tests** across all check functions, the cooldown system, Pushover delivery, and end-to-end integration.

## ⚙️ Configuration

All thresholds in `config.py` can be tuned to your preferences:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `STATION_ID` | `pws_kalhoove43` | Your PWS station identifier |
| `RAINFALL_THRESHOLD_INCHES` | `0.25` | Min rainfall to trigger alert |
| `TEMP_DROP_THRESHOLD_F` | `20` | Min temp drop (°F) within 3 days |
| `FREEZE_THRESHOLD_F` | `32` | First freeze temperature |
| `HEAT_WAVE_THRESHOLD_F` | `95` | Heat wave high temp threshold |
| `HEAT_WAVE_CONSECUTIVE_DAYS` | `3` | Days of heat to qualify as wave |
| `SNOW_CHANCE_THRESHOLD_PERCENT` | `30` | Min snow probability (%) |
| `SHOULDER_FREEZE_THRESHOLD_F` | `33` | Shoulder season overnight low |
| `TEMP_DROP_COOLDOWN_DAYS` | `5` | Cooldown between temp drop alerts |

## 📄 License

This project is licensed under the MIT License.
