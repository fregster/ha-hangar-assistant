"""Tests for forecast analysis utility."""
import pytest
from datetime import datetime, timedelta, timezone
from custom_components.hangar_assistant.utils.forecast_analysis import (
    calculate_sunset_sunrise,
    get_forecast_window,
    analyze_forecast_trends,
    check_overnight_conditions,
    find_optimal_flying_window,
)


class TestForecastAnalysis:
    """Test forecast analysis functionality."""
    
    def test_calculate_sunset_sunrise(self):
        """Test sunrise/sunset calculation."""
        # Test at London coordinates
        lat = 51.5074
        lon = -0.1278
        test_date = datetime(2025, 6, 21, 12, 0, 0, tzinfo=timezone.utc)  # Summer solstice
        
        sunrise, sunset = calculate_sunset_sunrise(lat, lon, test_date)
        
        # Should return datetime objects
        assert isinstance(sunrise, datetime)
        assert isinstance(sunset, datetime)
        
        # Sunrise should be before sunset
        assert sunrise < sunset
        
        # Summer solstice in London: sunrise ~4:30, sunset ~21:20
        # Check approximate times (within 2 hours tolerance for approximation fallback)
        assert 3 <= sunrise.hour <= 6
        assert 19 <= sunset.hour <= 23
    
    def test_calculate_sunset_sunrise_equator(self):
        """Test sunrise/sunset at equator (should be ~6am and 6pm)."""
        lat = 0.0
        lon = 0.0
        test_date = datetime(2025, 3, 21, 12, 0, 0, tzinfo=timezone.utc)  # Equinox
        
        sunrise, sunset = calculate_sunset_sunrise(lat, lon, test_date)
        
        # At equator on equinox, sunrise ~6am, sunset ~6pm
        # Tolerance for approximation fallback
        assert 4 <= sunrise.hour <= 8
        assert 16 <= sunset.hour <= 20
    
    def test_get_forecast_window_before_sunset(self):
        """Test forecast window when current time is before sunset."""
        lat = 51.5074
        lon = -0.1278
        now = datetime(2025, 6, 21, 12, 0, 0, tzinfo=timezone.utc)  # Noon
        
        window_start, window_end, is_overnight = get_forecast_window(lat, lon, now)
        
        # Window start should be now
        assert window_start == now
        
        # Window end should be sunset today
        assert window_end.date() == now.date()
        assert window_end > now
        
        # Should not be overnight window
        assert is_overnight is False
    
    def test_get_forecast_window_after_sunset(self):
        """Test forecast window when current time is after sunset."""
        lat = 51.5074
        lon = -0.1278
        now = datetime(2025, 6, 21, 22, 0, 0, tzinfo=timezone.utc)  # After sunset
        
        window_start, window_end, is_overnight = get_forecast_window(lat, lon, now)
        
        # Window should be sunrise to sunset tomorrow
        assert window_start.date() > now.date()  # Tomorrow
        assert window_end.date() > now.date()
        assert window_end > window_start
        
        # Should be overnight window
        assert is_overnight is True
    
    def test_analyze_forecast_trends_improving(self):
        """Test trend analysis with improving conditions."""
        forecast_data = [
            {
                "datetime": "2025-06-21T12:00:00+00:00",
                "temperature": 15,
                "pressure": 1010,
                "wind_speed": 20,
                "cloud_coverage": 80,
                "visibility": 5000,
            },
            {
                "datetime": "2025-06-21T14:00:00+00:00",
                "temperature": 17,
                "pressure": 1012,
                "wind_speed": 15,
                "cloud_coverage": 60,
                "visibility": 8000,
            },
            {
                "datetime": "2025-06-21T16:00:00+00:00",
                "temperature": 18,
                "pressure": 1015,
                "wind_speed": 10,
                "cloud_coverage": 30,
                "visibility": 10000,
            },
        ]
        
        trends = analyze_forecast_trends(forecast_data)
        
        assert trends["overall"] == "improving"
        assert trends["temperature"] == "rising"
        assert trends["pressure"] == "rising"
        assert trends["wind"] == "decreasing"
        assert trends["clouds"] == "clearing"
        # Visibility not yet implemented - just check it exists
        assert "visibility" in trends
        assert len(trends["summary"]) > 0
    
    def test_analyze_forecast_trends_deteriorating(self):
        """Test trend analysis with deteriorating conditions."""
        forecast_data = [
            {
                "datetime": "2025-06-21T12:00:00+00:00",
                "temperature": 18,
                "pressure": 1015,
                "wind_speed": 10,
                "cloud_coverage": 30,
                "visibility": 10000,
            },
            {
                "datetime": "2025-06-21T14:00:00+00:00",
                "temperature": 16,
                "pressure": 1012,
                "wind_speed": 18,
                "cloud_coverage": 60,
                "visibility": 6000,
            },
            {
                "datetime": "2025-06-21T16:00:00+00:00",
                "temperature": 14,
                "pressure": 1008,
                "wind_speed": 25,
                "cloud_coverage": 90,
                "visibility": 3000,
            },
        ]
        
        trends = analyze_forecast_trends(forecast_data)
        
        assert trends["overall"] == "deteriorating"
        assert trends["temperature"] == "falling"
        assert trends["pressure"] == "falling"
        assert trends["wind"] == "increasing"
        assert trends["clouds"] == "increasing"
        # Visibility not yet implemented - just check it exists
        assert "visibility" in trends
    
    def test_analyze_forecast_trends_stable(self):
        """Test trend analysis with stable conditions."""
        forecast_data = [
            {
                "datetime": "2025-06-21T12:00:00+00:00",
                "temperature": 15,
                "pressure": 1013,
                "wind_speed": 12,
                "cloud_coverage": 50,
                "visibility": 8000,
            },
            {
                "datetime": "2025-06-21T14:00:00+00:00",
                "temperature": 15,
                "pressure": 1013,
                "wind_speed": 13,
                "cloud_coverage": 52,
                "visibility": 8000,
            },
            {
                "datetime": "2025-06-21T16:00:00+00:00",
                "temperature": 16,
                "pressure": 1013,
                "wind_speed": 12,
                "cloud_coverage": 50,
                "visibility": 8000,
            },
        ]
        
        trends = analyze_forecast_trends(forecast_data)
        
        assert trends["overall"] == "stable"
    
    def test_check_overnight_conditions_no_warnings(self):
        """Test overnight check with no warnings."""
        forecast_data = [
            {
                "datetime": "2025-06-21T22:00:00+00:00",
                "temperature": 12,
                "wind_speed": 8,
                "precipitation": 0,
                "visibility": 8000,
                "humidity": 60,
            },
            {
                "datetime": "2025-06-22T02:00:00+00:00",
                "temperature": 10,
                "wind_speed": 6,
                "precipitation": 0,
                "visibility": 9000,
                "humidity": 65,
            },
        ]
        
        overnight_start = datetime.fromisoformat("2025-06-21T20:00:00+00:00")
        overnight_end = datetime.fromisoformat("2025-06-22T06:00:00+00:00")
        
        warnings = check_overnight_conditions(forecast_data, overnight_start, overnight_end)
        
        assert warnings["has_warnings"] is False
        assert warnings["flooding_risk"] is False
        assert warnings["wind_damage_risk"] is False
        assert warnings["surface_contamination"] is False
        assert warnings["fog_risk"] is False
    
    def test_check_overnight_conditions_flooding_risk(self):
        """Test overnight check with flooding risk."""
        forecast_data = [
            {
                "datetime": "2025-06-21T22:00:00+00:00",
                "temperature": 12,
                "wind_speed": 8,
                "precipitation": 15,  # >10mm/hr
                "visibility": 8000,
                "humidity": 85,
            },
        ]
        
        overnight_start = datetime.fromisoformat("2025-06-21T20:00:00+00:00")
        overnight_end = datetime.fromisoformat("2025-06-22T06:00:00+00:00")
        
        warnings = check_overnight_conditions(forecast_data, overnight_start, overnight_end)
        
        assert warnings["has_warnings"] is True
        assert warnings["flooding_risk"] is True
        assert "flooding" in warnings["summary"].lower()
    
    def test_check_overnight_conditions_wind_damage(self):
        """Test overnight check with wind damage risk."""
        forecast_data = [
            {
                "datetime": "2025-06-21T22:00:00+00:00",
                "temperature": 12,
                "wind_speed": 40,  # >35kt
                "precipitation": 0,
                "visibility": 8000,
                "humidity": 60,
            },
        ]
        
        overnight_start = datetime.fromisoformat("2025-06-21T20:00:00+00:00")
        overnight_end = datetime.fromisoformat("2025-06-22T06:00:00+00:00")
        
        warnings = check_overnight_conditions(forecast_data, overnight_start, overnight_end)
        
        assert warnings["has_warnings"] is True
        assert warnings["wind_damage_risk"] is True
        assert "wind" in warnings["summary"].lower()
    
    def test_check_overnight_conditions_surface_contamination(self):
        """Test overnight check with surface contamination risk."""
        forecast_data = [
            {
                "datetime": "2025-06-21T22:00:00+00:00",
                "temperature": -2,  # Below freezing
                "wind_speed": 8,
                "precipitation": 2,
                "visibility": 8000,
                "humidity": 80,
            },
        ]
        
        overnight_start = datetime.fromisoformat("2025-06-21T20:00:00+00:00")
        overnight_end = datetime.fromisoformat("2025-06-22T06:00:00+00:00")
        
        warnings = check_overnight_conditions(forecast_data, overnight_start, overnight_end)
        
        assert warnings["has_warnings"] is True
        assert warnings["surface_contamination"] is True
        assert "contamination" in warnings["summary"].lower()
    
    def test_check_overnight_conditions_fog_risk(self):
        """Test overnight check with fog risk."""
        forecast_data = [
            {
                "datetime": "2025-06-21T22:00:00+00:00",
                "temperature": 5,
                "wind_speed": 3,
                "precipitation": 0,
                "visibility": 800,  # <1000m
                "humidity": 95,
            },
        ]
        
        overnight_start = datetime.fromisoformat("2025-06-21T20:00:00+00:00")
        overnight_end = datetime.fromisoformat("2025-06-22T06:00:00+00:00")
        
        warnings = check_overnight_conditions(forecast_data, overnight_start, overnight_end)
        
        assert warnings["has_warnings"] is True
        assert warnings["fog_risk"] is True
        assert "fog" in warnings["summary"].lower()
    
    def test_find_optimal_flying_window_good_conditions(self):
        """Test optimal window with consistently good conditions."""
        forecast_data = []
        base_time = datetime.fromisoformat("2025-06-21T10:00:00+00:00")
        
        # Create 6 hours of good conditions
        for i in range(6):
            forecast_data.append({
                "datetime": (base_time + timedelta(hours=i)).isoformat(),
                "wind_speed": 8,
                "wind_bearing": 270,
                "cloud_coverage": 30,
                "visibility": 10000,
                "precipitation": 0,
            })
        
        window_start = base_time
        window_end = base_time + timedelta(hours=6)
        
        result = find_optimal_flying_window(
            forecast_data,
            window_start,
            window_end,
            wind_limit_kt=25,
            crosswind_limit_kt=15,
            runway_heading=270,
        )
        
        assert result["has_window"] is True
        assert result["average_score"] > 30  # Above threshold for good conditions
        assert "optimal" in result["reason"].lower() or "conditions" in result["reason"].lower()
    
    def test_find_optimal_flying_window_no_window(self):
        """Test optimal window with consistently poor conditions."""
        forecast_data = []
        base_time = datetime.fromisoformat("2025-06-21T10:00:00+00:00")
        
        # Create 6 hours of poor conditions (high wind, low visibility)
        for i in range(6):
            forecast_data.append({
                "datetime": (base_time + timedelta(hours=i)).isoformat(),
                "wind_speed": 30,  # Above limit
                "wind_bearing": 270,
                "cloud_coverage": 90,
                "visibility": 2000,  # Poor visibility
                "precipitation": 5,  # Rain
            })
        
        window_start = base_time
        window_end = base_time + timedelta(hours=6)
        
        result = find_optimal_flying_window(
            forecast_data,
            window_start,
            window_end,
            wind_limit_kt=25,
            crosswind_limit_kt=15,
            runway_heading=270,
        )
        
        assert result["has_window"] is False
        assert result["average_score"] < 50  # Low score for poor conditions
    
    def test_find_optimal_flying_window_crosswind_penalty(self):
        """Test that crosswind reduces score appropriately."""
        base_time = datetime.fromisoformat("2025-06-21T10:00:00+00:00")
        
        # Create 3 hours of forecast data for headwind
        # Wind speed in m/s (7.7 m/s ≈ 15 kt)
        forecast_data_headwind = []
        for i in range(3):
            forecast_data_headwind.append({
                "datetime": (base_time + timedelta(hours=i)).isoformat(),
                "wind_speed": 7.7,  # m/s (~15 kt)
                "wind_bearing": 270,  # Direct headwind
                "cloud_coverage": 30,
                "visibility": 10000,
                "precipitation": 0,
            })
        
        # Create 3 hours of forecast data for crosswind
        forecast_data_crosswind = []
        for i in range(3):
            forecast_data_crosswind.append({
                "datetime": (base_time + timedelta(hours=i)).isoformat(),
                "wind_speed": 7.7,  # m/s (~15 kt)
                "wind_bearing": 180,  # 90° crosswind
                "cloud_coverage": 30,
                "visibility": 10000,
                "precipitation": 0,
            })
        
        window_start = base_time
        window_end = base_time + timedelta(hours=3)
        
        result_headwind = find_optimal_flying_window(
            forecast_data_headwind,
            window_start,
            window_end,
            wind_limit_kt=25,
            crosswind_limit_kt=15,
            runway_heading=270,
        )
        
        result_crosswind = find_optimal_flying_window(
            forecast_data_crosswind,
            window_start,
            window_end,
            wind_limit_kt=25,
            crosswind_limit_kt=15,
            runway_heading=270,
        )
        
        # Headwind should score higher than crosswind
        assert result_headwind["average_score"] > result_crosswind["average_score"]
    
    def test_analyze_forecast_trends_empty_data(self):
        """Test trend analysis with empty forecast data."""
        trends = analyze_forecast_trends([])
        
        assert trends["overall"] == "stable"
        assert "No data" in trends["summary"] or "Insufficient" in trends["summary"]
    
    def test_check_overnight_conditions_empty_data(self):
        """Test overnight check with empty forecast data."""
        overnight_start = datetime.fromisoformat("2025-06-21T20:00:00+00:00")
        overnight_end = datetime.fromisoformat("2025-06-22T06:00:00+00:00")
        
        warnings = check_overnight_conditions([], overnight_start, overnight_end)
        
        assert warnings["has_warnings"] is False
        assert "No data" in warnings["summary"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
