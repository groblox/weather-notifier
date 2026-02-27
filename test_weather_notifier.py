#!/usr/bin/env python3
"""
Test suite for Weather Notifier App.

All external API calls are mocked — no real network requests are made.
Run with:  python -m pytest test_weather_notifier.py -v
    or:    python -m unittest test_weather_notifier -v
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# We need to mock the config before importing weather_notifier,
# but the functions reference config constants at call time (not import time),
# so we can import normally and patch where needed.
import weather_notifier as wn


# ---------------------------------------------------------------------------
# Helper: build a fake Aeris "observations/summary" response
# ---------------------------------------------------------------------------
def _obs_summary_response(total_rain_in: float):
    """Build a fake Aeris observations/summary API response."""
    return {
        "success": True,
        "response": [
            {
                "periods": [
                    {
                        "summary": {
                            "precip": {"totalIN": total_rain_in}
                        }
                    }
                ]
            }
        ],
    }


def _forecast_response(days: list[dict]):
    """
    Build a fake Aeris forecasts API response.

    Each item in `days` should be a dict with keys like:
        maxTempF, minTempF, dateTimeISO, weather, weatherPrimary, snowIN, pop, isDay
    Missing keys are simply absent from the period dict (the code uses .get()).
    """
    return {
        "success": True,
        "response": [{"periods": days}],
    }


# ---------------------------------------------------------------------------
# Helpers for cooldown tests — use a temp file instead of real cooldown file
# ---------------------------------------------------------------------------
class _CooldownMixin:
    """Mixin that redirects cooldown I/O to a temp directory."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        # Patch get_script_dir so cooldown file lives in our temp dir
        self._patcher = patch.object(wn, "get_script_dir", return_value=Path(self._tmpdir))
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        # Clean up temp cooldown file
        cooldown_path = Path(self._tmpdir) / "notification_cooldown.json"
        if cooldown_path.exists():
            cooldown_path.unlink()
        os.rmdir(self._tmpdir)


# ===================================================================
#  RAINFALL TESTS
# ===================================================================
class TestCheckRainfall(unittest.TestCase):
    """Tests for check_rainfall()."""

    @patch.object(wn, "aeris_request")
    def test_above_threshold_returns_true(self, mock_api):
        mock_api.return_value = _obs_summary_response(0.50)
        should_notify, rainfall = wn.check_rainfall()
        self.assertTrue(should_notify)
        self.assertAlmostEqual(rainfall, 0.50)

    @patch.object(wn, "aeris_request")
    def test_at_threshold_returns_true(self, mock_api):
        mock_api.return_value = _obs_summary_response(0.25)
        should_notify, rainfall = wn.check_rainfall()
        self.assertTrue(should_notify)
        self.assertAlmostEqual(rainfall, 0.25)

    @patch.object(wn, "aeris_request")
    def test_below_threshold_returns_false(self, mock_api):
        mock_api.return_value = _obs_summary_response(0.10)
        should_notify, rainfall = wn.check_rainfall()
        self.assertFalse(should_notify)
        self.assertAlmostEqual(rainfall, 0.10)

    @patch.object(wn, "aeris_request")
    def test_zero_rainfall(self, mock_api):
        mock_api.return_value = _obs_summary_response(0.0)
        should_notify, rainfall = wn.check_rainfall()
        self.assertFalse(should_notify)
        self.assertAlmostEqual(rainfall, 0.0)

    @patch.object(wn, "aeris_request")
    def test_none_rainfall_treated_as_zero(self, mock_api):
        """If the API returns None for totalIN, treat it as 0."""
        mock_api.return_value = {
            "success": True,
            "response": [{"periods": [{"summary": {"precip": {"totalIN": None}}}]}],
        }
        should_notify, rainfall = wn.check_rainfall()
        self.assertFalse(should_notify)
        self.assertAlmostEqual(rainfall, 0.0)

    @patch.object(wn, "aeris_request")
    def test_empty_periods(self, mock_api):
        """No observation data for yesterday."""
        mock_api.return_value = {"success": True, "response": [{"periods": []}]}
        should_notify, rainfall = wn.check_rainfall()
        self.assertFalse(should_notify)
        self.assertAlmostEqual(rainfall, 0.0)

    @patch.object(wn, "aeris_request")
    def test_api_exception_returns_false(self, mock_api):
        mock_api.side_effect = Exception("Network error")
        should_notify, rainfall = wn.check_rainfall()
        self.assertFalse(should_notify)
        self.assertAlmostEqual(rainfall, 0.0)


# ===================================================================
#  TEMPERATURE DROP TESTS
# ===================================================================
class TestCheckTempDrop(_CooldownMixin, unittest.TestCase):
    """Tests for check_temp_drop()."""

    def _make_forecast(self, highs: list[int]):
        """Helper: build forecast days from a list of high temps."""
        return _forecast_response([
            {"maxTempF": h, "dateTimeISO": f"2026-02-{20+i:02d}T00:00:00"}
            for i, h in enumerate(highs)
        ])

    @patch.object(wn, "aeris_request")
    def test_significant_drop_detected(self, mock_api):
        # 70 → 60 → 45  =>  25°F drop from day 0 to day 2 (within 3-day window)
        mock_api.return_value = self._make_forecast([70, 60, 45, 50, 55, 60, 65])
        should_notify, max_drop, desc = wn.check_temp_drop()
        self.assertTrue(should_notify)
        self.assertGreaterEqual(max_drop, 20)

    @patch.object(wn, "aeris_request")
    def test_exactly_at_threshold(self, mock_api):
        # 60 → 40  =>  exactly 20°F drop
        mock_api.return_value = self._make_forecast([60, 50, 40, 45, 50, 55, 60])
        should_notify, max_drop, desc = wn.check_temp_drop()
        self.assertTrue(should_notify)
        self.assertEqual(max_drop, 20)

    @patch.object(wn, "aeris_request")
    def test_small_drop_no_alert(self, mock_api):
        mock_api.return_value = self._make_forecast([70, 65, 60, 58, 55, 52, 50])
        should_notify, max_drop, desc = wn.check_temp_drop()
        # Max drop in any 3-day window: 70→58 = 12 or 65→52 = 13 etc  — all < 20
        self.assertFalse(should_notify)

    @patch.object(wn, "aeris_request")
    def test_cooldown_skips_check(self, mock_api):
        # Set cooldown to now (within the 5-day window)
        wn.set_temp_drop_cooldown()
        mock_api.return_value = self._make_forecast([80, 60, 40, 30, 25, 20, 15])
        should_notify, max_drop, desc = wn.check_temp_drop()
        self.assertFalse(should_notify)

    @patch.object(wn, "aeris_request")
    def test_drop_outside_3day_window_not_detected(self, mock_api):
        # Days: 70, 68, 65, 62, 48  =>  biggest drop within 3-day window is ~17
        # but day0→day4 =22 which is outside the 3-day window
        mock_api.return_value = self._make_forecast([70, 68, 65, 62, 48, 50, 55])
        should_notify, max_drop, desc = wn.check_temp_drop()
        # Window is i to i+3 (exclusive), so day0 compares to day1,2,3
        # day0→day3 = 70-62 = 8; day1→day4 = 68-48 = 20 — this IS within window
        # Actually j goes up to i+4 exclusive, meaning within 3 positions
        # Let's just check the raw logic
        # The code: for j in range(i+1, min(i+4, len(temps))) — so j can be i+1, i+2, i+3
        # day1(68) → day4(48) = 20°F — this IS detected!
        self.assertTrue(should_notify)

    @patch.object(wn, "aeris_request")
    def test_api_exception(self, mock_api):
        mock_api.side_effect = Exception("API timeout")
        should_notify, max_drop, desc = wn.check_temp_drop()
        self.assertFalse(should_notify)


# ===================================================================
#  FIRST FREEZE TESTS
# ===================================================================
class TestCheckFirstFreeze(_CooldownMixin, unittest.TestCase):
    """Tests for check_first_freeze()."""

    @patch.object(wn, "aeris_request")
    @patch("weather_notifier.datetime")
    def test_freeze_detected_in_season(self, mock_dt, mock_api):
        """During Oct-Dec, if a night hits 32°F, should alert."""
        mock_dt.now.return_value = datetime(2026, 11, 1, 7, 0)
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_api.return_value = _forecast_response([
            {"minTempF": 40, "dateTimeISO": "2026-11-01T00:00:00"},
            {"minTempF": 35, "dateTimeISO": "2026-11-02T00:00:00"},
            {"minTempF": 30, "dateTimeISO": "2026-11-03T00:00:00"},
        ])
        should_notify, low_temp, date_str = wn.check_first_freeze()
        self.assertTrue(should_notify)
        self.assertEqual(low_temp, 30)
        self.assertEqual(date_str, "2026-11-03")

    @patch("weather_notifier.datetime")
    def test_out_of_season_skips(self, mock_dt):
        """Outside Oct-Dec, freeze check should skip."""
        mock_dt.now.return_value = datetime(2026, 2, 27, 7, 0)
        should_notify, low_temp, date_str = wn.check_first_freeze()
        self.assertFalse(should_notify)

    @patch.object(wn, "aeris_request")
    @patch("weather_notifier.datetime")
    def test_already_alerted_this_year(self, mock_dt, mock_api):
        """If we already sent a freeze alert this year, skip."""
        mock_dt.now.return_value = datetime(2026, 11, 15, 7, 0)
        mock_dt.fromisoformat = datetime.fromisoformat
        # Pre-set the cooldown for this year
        cooldown_path = Path(self._tmpdir) / "notification_cooldown.json"
        with open(cooldown_path, "w") as f:
            json.dump({"first_freeze_alert_year": 2026}, f)

        should_notify, _, _ = wn.check_first_freeze()
        self.assertFalse(should_notify)
        mock_api.assert_not_called()

    @patch.object(wn, "aeris_request")
    @patch("weather_notifier.datetime")
    def test_no_freeze_in_forecast(self, mock_dt, mock_api):
        """In season but no freezing temps in forecast."""
        mock_dt.now.return_value = datetime(2026, 10, 15, 7, 0)
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_api.return_value = _forecast_response([
            {"minTempF": 45, "dateTimeISO": "2026-10-15T00:00:00"},
            {"minTempF": 42, "dateTimeISO": "2026-10-16T00:00:00"},
            {"minTempF": 40, "dateTimeISO": "2026-10-17T00:00:00"},
        ])
        should_notify, _, _ = wn.check_first_freeze()
        self.assertFalse(should_notify)


# ===================================================================
#  HEAT WAVE TESTS
# ===================================================================
class TestCheckHeatWave(_CooldownMixin, unittest.TestCase):
    """Tests for check_heat_wave()."""

    @patch.object(wn, "aeris_request")
    def test_heat_wave_detected(self, mock_api):
        """3 consecutive days >= 95°F triggers alert."""
        mock_api.return_value = _forecast_response([
            {"maxTempF": 90, "dateTimeISO": "2026-07-01T00:00:00"},
            {"maxTempF": 96, "dateTimeISO": "2026-07-02T00:00:00"},
            {"maxTempF": 98, "dateTimeISO": "2026-07-03T00:00:00"},
            {"maxTempF": 97, "dateTimeISO": "2026-07-04T00:00:00"},
            {"maxTempF": 88, "dateTimeISO": "2026-07-05T00:00:00"},
        ])
        should_notify, hot_days, count = wn.check_heat_wave()
        self.assertTrue(should_notify)
        self.assertEqual(count, 3)

    @patch.object(wn, "aeris_request")
    def test_broken_streak_no_alert(self, mock_api):
        """2 hot days then a cool day — not enough for heat wave."""
        mock_api.return_value = _forecast_response([
            {"maxTempF": 96, "dateTimeISO": "2026-07-01T00:00:00"},
            {"maxTempF": 97, "dateTimeISO": "2026-07-02T00:00:00"},
            {"maxTempF": 85, "dateTimeISO": "2026-07-03T00:00:00"},
            {"maxTempF": 96, "dateTimeISO": "2026-07-04T00:00:00"},
            {"maxTempF": 97, "dateTimeISO": "2026-07-05T00:00:00"},
        ])
        should_notify, hot_days, count = wn.check_heat_wave()
        self.assertFalse(should_notify)

    @patch.object(wn, "aeris_request")
    def test_heat_wave_cooldown(self, mock_api):
        """If alerted recently, should skip."""
        wn.set_heat_wave_cooldown()
        mock_api.return_value = _forecast_response([
            {"maxTempF": 100, "dateTimeISO": "2026-07-01T00:00:00"},
            {"maxTempF": 100, "dateTimeISO": "2026-07-02T00:00:00"},
            {"maxTempF": 100, "dateTimeISO": "2026-07-03T00:00:00"},
        ])
        should_notify, _, _ = wn.check_heat_wave()
        self.assertFalse(should_notify)

    @patch.object(wn, "aeris_request")
    def test_all_cool_days(self, mock_api):
        mock_api.return_value = _forecast_response([
            {"maxTempF": 75, "dateTimeISO": "2026-07-01T00:00:00"},
            {"maxTempF": 78, "dateTimeISO": "2026-07-02T00:00:00"},
            {"maxTempF": 80, "dateTimeISO": "2026-07-03T00:00:00"},
        ])
        should_notify, _, count = wn.check_heat_wave()
        self.assertFalse(should_notify)
        self.assertEqual(count, 0)


# ===================================================================
#  SNOW CHANCE TESTS
# ===================================================================
class TestCheckSnowChance(_CooldownMixin, unittest.TestCase):
    """Tests for check_snow_chance()."""

    @patch.object(wn, "aeris_request")
    def test_snow_detected_high_probability(self, mock_api):
        mock_api.return_value = _forecast_response([
            {"weather": "Clear", "weatherPrimary": "Sunny", "snowIN": 0, "pop": 10, "dateTimeISO": "2026-01-20T00:00:00"},
            {"weather": "Snow likely", "weatherPrimary": "Snow", "snowIN": 2.0, "pop": 60, "dateTimeISO": "2026-01-21T00:00:00"},
        ])
        should_notify, prob, date_str = wn.check_snow_chance()
        self.assertTrue(should_notify)
        self.assertEqual(prob, 60)
        self.assertEqual(date_str, "2026-01-21")

    @patch.object(wn, "aeris_request")
    def test_snow_low_probability_no_alert(self, mock_api):
        """Snow in forecast but only 15% chance — below 30% threshold."""
        mock_api.return_value = _forecast_response([
            {"weather": "Chance of Snow", "weatherPrimary": "Snow", "snowIN": 0.5, "pop": 15, "dateTimeISO": "2026-01-21T00:00:00"},
        ])
        should_notify, _, _ = wn.check_snow_chance()
        self.assertFalse(should_notify)

    @patch.object(wn, "aeris_request")
    def test_no_snow_in_forecast(self, mock_api):
        mock_api.return_value = _forecast_response([
            {"weather": "Sunny", "weatherPrimary": "Clear", "snowIN": 0, "pop": 0, "dateTimeISO": "2026-01-20T00:00:00"},
        ])
        should_notify, _, _ = wn.check_snow_chance()
        self.assertFalse(should_notify)

    @patch.object(wn, "aeris_request")
    def test_snow_cooldown(self, mock_api):
        wn.set_snow_cooldown()
        mock_api.return_value = _forecast_response([
            {"weather": "Heavy Snow", "weatherPrimary": "Snow", "snowIN": 5.0, "pop": 90, "dateTimeISO": "2026-01-21T00:00:00"},
        ])
        should_notify, _, _ = wn.check_snow_chance()
        self.assertFalse(should_notify)


# ===================================================================
#  SHOULDER FREEZE TESTS
# ===================================================================
class TestCheckShoulderFreeze(_CooldownMixin, unittest.TestCase):
    """Tests for check_shoulder_freeze()."""

    @patch.object(wn, "aeris_request")
    @patch("weather_notifier.datetime")
    def test_freeze_tonight_in_march(self, mock_dt, mock_api):
        """March night forecast below 33°F should alert."""
        mock_dt.now.return_value = datetime(2026, 3, 15, 16, 15)
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_api.return_value = _forecast_response([
            {"isDay": True, "minTempF": 45, "dateTimeISO": "2026-03-15T00:00:00"},
            {"isDay": False, "minTempF": 28, "dateTimeISO": "2026-03-15T00:00:00"},
        ])
        should_notify, low_temp, desc = wn.check_shoulder_freeze()
        self.assertTrue(should_notify)
        self.assertEqual(low_temp, 28)

    @patch.object(wn, "aeris_request")
    @patch("weather_notifier.datetime")
    def test_warm_night_no_alert(self, mock_dt, mock_api):
        """March night above threshold — no alert."""
        mock_dt.now.return_value = datetime(2026, 3, 15, 16, 15)
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_api.return_value = _forecast_response([
            {"isDay": True, "minTempF": 55, "dateTimeISO": "2026-03-15T00:00:00"},
            {"isDay": False, "minTempF": 40, "dateTimeISO": "2026-03-15T00:00:00"},
        ])
        should_notify, _, _ = wn.check_shoulder_freeze()
        self.assertFalse(should_notify)

    @patch("weather_notifier.datetime")
    def test_wrong_month_skips(self, mock_dt):
        """In June, should skip entirely."""
        mock_dt.now.return_value = datetime(2026, 6, 15, 16, 15)
        should_notify, _, _ = wn.check_shoulder_freeze()
        self.assertFalse(should_notify)

    @patch.object(wn, "aeris_request")
    @patch("weather_notifier.datetime")
    def test_already_alerted_today(self, mock_dt, mock_api):
        """If we already sent an alert today, don't repeat."""
        now = datetime(2026, 3, 15, 16, 15)
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat

        # Write cooldown for today
        cooldown_path = Path(self._tmpdir) / "notification_cooldown.json"
        with open(cooldown_path, "w") as f:
            json.dump({"last_shoulder_freeze_alert": now.isoformat()}, f)

        should_notify, _, _ = wn.check_shoulder_freeze()
        self.assertFalse(should_notify)
        mock_api.assert_not_called()


# ===================================================================
#  PUSHOVER NOTIFICATION TESTS
# ===================================================================
class TestSendPushoverNotification(unittest.TestCase):
    """Tests for send_pushover_notification()."""

    @patch("weather_notifier.requests.post")
    def test_successful_notification(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": 1, "request": "abc123"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        result = wn.send_pushover_notification("Test Title", "Test Message")
        self.assertTrue(result)
        mock_post.assert_called_once()

        # Verify the payload
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        self.assertEqual(payload["title"], "Test Title")
        self.assertEqual(payload["message"], "Test Message")
        self.assertEqual(payload["priority"], 0)

    @patch("weather_notifier.requests.post")
    def test_failed_notification(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": 0, "errors": ["invalid token"]},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        result = wn.send_pushover_notification("Test", "Test")
        self.assertFalse(result)

    @patch("weather_notifier.requests.post")
    def test_network_exception(self, mock_post):
        import requests
        mock_post.side_effect = requests.RequestException("Connection refused")

        result = wn.send_pushover_notification("Test", "Test")
        self.assertFalse(result)

    @patch("weather_notifier.requests.post")
    def test_high_priority(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": 1},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        wn.send_pushover_notification("Urgent", "Message", priority=1)
        payload = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        self.assertEqual(payload["priority"], 1)


# ===================================================================
#  COOLDOWN SYSTEM TESTS
# ===================================================================
class TestCooldownSystem(_CooldownMixin, unittest.TestCase):
    """Tests for the cooldown load/save/check system."""

    def test_empty_cooldown_file(self):
        data = wn.get_cooldown_data()
        self.assertEqual(data, {})

    def test_save_and_load_cooldown(self):
        wn.save_cooldown_data({"test_key": "test_value"})
        data = wn.get_cooldown_data()
        self.assertEqual(data["test_key"], "test_value")

    def test_temp_drop_cooldown_active(self):
        wn.set_temp_drop_cooldown()
        self.assertTrue(wn.is_temp_drop_on_cooldown())

    def test_temp_drop_cooldown_expired(self):
        data = wn.get_cooldown_data()
        # Set last alert to 10 days ago (beyond 5-day cooldown)
        data["last_temp_drop_alert"] = (datetime.now() - timedelta(days=10)).isoformat()
        wn.save_cooldown_data(data)
        self.assertFalse(wn.is_temp_drop_on_cooldown())

    def test_corrupt_cooldown_file_returns_empty(self):
        cooldown_path = Path(self._tmpdir) / "notification_cooldown.json"
        with open(cooldown_path, "w") as f:
            f.write("not valid json {{{")
        data = wn.get_cooldown_data()
        self.assertEqual(data, {})


# ===================================================================
#  INTEGRATION TEST: run_checks()
# ===================================================================
class TestRunChecks(_CooldownMixin, unittest.TestCase):
    """Integration test for the run_checks() orchestrator."""

    @patch.object(wn, "send_pushover_notification", return_value=True)
    @patch.object(wn, "check_snow_chance", return_value=(False, 0.0, ""))
    @patch.object(wn, "check_heat_wave", return_value=(False, [], 0))
    @patch.object(wn, "check_first_freeze", return_value=(False, 0.0, ""))
    @patch.object(wn, "check_temp_drop", return_value=(True, 25.0, "2026-02-20 (70°F) → 2026-02-22 (45°F)"))
    @patch.object(wn, "check_rainfall", return_value=(True, 0.50))
    def test_sends_notifications_for_triggered_checks(
        self, mock_rain, mock_temp, mock_freeze, mock_heat, mock_snow, mock_notify
    ):
        wn.run_checks(test_mode=False)

        # Should have sent 2 notifications (rain + temp drop)
        self.assertEqual(mock_notify.call_count, 2)

        # Verify the notification titles
        call_titles = [call.args[0] for call in mock_notify.call_args_list]
        self.assertIn("🌧️ Significant Rainfall Yesterday", call_titles)
        self.assertIn("Major Temperature Drop Coming", call_titles)

    @patch.object(wn, "send_pushover_notification", return_value=True)
    @patch.object(wn, "check_snow_chance", return_value=(False, 0.0, ""))
    @patch.object(wn, "check_heat_wave", return_value=(False, [], 0))
    @patch.object(wn, "check_first_freeze", return_value=(False, 0.0, ""))
    @patch.object(wn, "check_temp_drop", return_value=(False, 5.0, ""))
    @patch.object(wn, "check_rainfall", return_value=(False, 0.05))
    def test_no_notifications_when_nothing_triggered(
        self, mock_rain, mock_temp, mock_freeze, mock_heat, mock_snow, mock_notify
    ):
        wn.run_checks(test_mode=False)
        mock_notify.assert_not_called()

    @patch.object(wn, "send_pushover_notification", return_value=True)
    @patch.object(wn, "check_snow_chance", return_value=(True, 60.0, "2026-01-21"))
    @patch.object(wn, "check_heat_wave", return_value=(True, [{"date": "2026-07-01", "high": 98}], 3))
    @patch.object(wn, "check_first_freeze", return_value=(True, 30.0, "2026-11-05"))
    @patch.object(wn, "check_temp_drop", return_value=(True, 25.0, "drop desc"))
    @patch.object(wn, "check_rainfall", return_value=(True, 1.0))
    def test_dry_run_sends_no_real_notifications(
        self, mock_rain, mock_temp, mock_freeze, mock_heat, mock_snow, mock_notify
    ):
        wn.run_checks(test_mode=True)
        mock_notify.assert_not_called()

    @patch.object(wn, "send_pushover_notification", return_value=True)
    @patch.object(wn, "check_snow_chance", return_value=(True, 80.0, "2026-01-22"))
    @patch.object(wn, "check_heat_wave", return_value=(True, [{"date": "2026-07-02", "high": 99}, {"date": "2026-07-03", "high": 100}, {"date": "2026-07-04", "high": 101}], 3))
    @patch.object(wn, "check_first_freeze", return_value=(True, 28.0, "2026-11-10"))
    @patch.object(wn, "check_temp_drop", return_value=(True, 30.0, "big drop"))
    @patch.object(wn, "check_rainfall", return_value=(True, 2.0))
    def test_all_alerts_fire(
        self, mock_rain, mock_temp, mock_freeze, mock_heat, mock_snow, mock_notify
    ):
        """When every check triggers, 5 notifications should be sent."""
        wn.run_checks(test_mode=False)
        self.assertEqual(mock_notify.call_count, 5)


# ===================================================================
#  API REQUEST HELPER TEST
# ===================================================================
class TestAerisRequest(unittest.TestCase):
    """Tests for the aeris_request() helper."""

    @patch("weather_notifier.requests.get")
    def test_successful_request(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": True, "response": {"data": "test"}},
        )
        mock_get.return_value.raise_for_status = MagicMock()

        result = wn.aeris_request("observations/pws_test")
        self.assertTrue(result["success"])

    @patch("weather_notifier.requests.get")
    def test_api_returns_error(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": False, "error": {"code": "invalid_client", "description": "bad creds"}},
        )
        mock_get.return_value.raise_for_status = MagicMock()

        with self.assertRaises(ValueError):
            wn.aeris_request("observations/pws_test")

    @patch("weather_notifier.requests.get")
    def test_http_error(self, mock_get):
        import requests
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("500 Server Error")

        with self.assertRaises(requests.HTTPError):
            wn.aeris_request("observations/pws_test")


if __name__ == "__main__":
    unittest.main()
