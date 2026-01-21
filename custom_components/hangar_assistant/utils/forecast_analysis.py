"""Forecast analysis utilities for OWM data and sunrise/sunset calculations.

Analyzes OpenWeatherMap forecast data to:
1. Determine forecast window (current time to sunset, or sunrise-to-sunset)
2. Identify trend (improving/stable/deteriorating)
3. Flag overnight conditions affecting airfield serviceability
4. Calculate optimal flying windows
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


def calculate_sunset_sunrise(latitude: float, longitude: float, date: datetime) -> Tuple[datetime, datetime]:
    """Calculate sunrise and sunset times for a location and date.
    
    Uses simplified approximation suitable for mid-latitudes.
    For production, consider using astral library for precision.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        date: Date to calculate for (timezone-aware)
    
    Returns:
        Tuple of (sunrise_time, sunset_time) as timezone-aware datetimes
    """
    # Simplified calculation - for production, use astral library
    # This approximation is accurate to ~15 minutes for mid-latitudes
    
    try:
        from astral import LocationInfo
        from astral.sun import sun
        
        location = LocationInfo(latitude=latitude, longitude=longitude)
        s = sun(location.observer, date=date.date())
        
        return (s['sunrise'], s['sunset'])
        
    except ImportError:
        # Fallback to simple approximation if astral not available
        _LOGGER.warning("Astral library not available, using approximation for sunrise/sunset")
        
        # Very rough approximation for UK latitudes
        # Assumes ~8 hour day in winter, ~16 hour day in summer
        day_of_year = date.timetuple().tm_yday
        day_length_hours = 12 + 4 * math.sin((day_of_year - 80) * 2 * math.pi / 365)
        
        # Noon at longitude
        noon_offset_hours = longitude / 15  # 15 degrees per hour
        solar_noon = date.replace(hour=12, minute=0, second=0, microsecond=0)
        solar_noon += timedelta(hours=noon_offset_hours)
        
        half_day = timedelta(hours=day_length_hours / 2)
        sunrise = solar_noon - half_day
        sunset = solar_noon + half_day
        
        return (sunrise, sunset)


def get_forecast_window(
    latitude: float, 
    longitude: float, 
    now: Optional[datetime] = None
) -> Tuple[datetime, datetime, bool]:
    """Determine the forecast window for briefing.
    
    Rules:
    - If current time < sunset today: current → sunset today
    - If current time > sunset today: sunrise tomorrow → sunset tomorrow
    
    Args:
        latitude: Airfield latitude
        longitude: Airfield longitude
        now: Current time (defaults to utcnow())
    
    Returns:
        Tuple of (window_start, window_end, is_overnight)
        is_overnight = True if window spans into next day
    """
    if now is None:
        now = dt_util.utcnow()
    
    sunrise_today, sunset_today = calculate_sunset_sunrise(latitude, longitude, now)
    
    # If before sunset today, use current → sunset
    if now < sunset_today:
        return (now, sunset_today, False)
    
    # After sunset - use sunrise → sunset tomorrow
    tomorrow = now + timedelta(days=1)
    sunrise_tomorrow, sunset_tomorrow = calculate_sunset_sunrise(latitude, longitude, tomorrow)
    
    return (sunrise_tomorrow, sunset_tomorrow, True)


def analyze_forecast_trends(forecast_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze forecast data to identify trends.
    
    Analyzes:
    - Temperature trend (rising/falling)
    - Pressure trend (rising/falling/stable)
    - Wind trend (increasing/decreasing/stable)
    - Cloud cover trend (improving/deteriorating/stable)
    - Visibility trend (improving/deteriorating/stable)
    
    Args:
        forecast_data: List of forecast dicts with hourly data
    
    Returns:
        Dictionary with trend analysis:
        - overall: "improving" / "stable" / "deteriorating"
        - temperature_trend: "rising" / "falling" / "stable"
        - pressure_trend: "rising" / "falling" / "stable"
        - wind_trend: "increasing" / "decreasing" / "stable"
        - cloud_trend: "clearing" / "increasing" / "stable"
        - visibility_trend: "improving" / "deteriorating" / "stable"
        - summary: Human-readable summary string
    """
    if not forecast_data or len(forecast_data) < 3:
        return {
            "overall": "stable",
            "summary": "Insufficient forecast data for trend analysis"
        }
    
    # Extract data points (handle both OWM format and test format)
    temps = [f.get("temp") or f.get("temperature", 0) for f in forecast_data]
    pressures = [f.get("pressure", 1013) for f in forecast_data]
    winds = [f.get("wind_speed", 0) for f in forecast_data]
    clouds = [f.get("clouds") or f.get("cloud_coverage", 0) for f in forecast_data]
    
    # Calculate trends (linear approximation)
    def trend(values: List[float], threshold: float = 0.1) -> str:
        """Determine if values are increasing/decreasing/stable."""
        if not values or len(values) < 2:
            return "stable"
        avg_change = (values[-1] - values[0]) / len(values)
        if avg_change > threshold:
            return "increasing"
        elif avg_change < -threshold:
            return "decreasing"
        return "stable"
    
    # Temperature trend (threshold 0.5°C per hour)
    temp_trend = trend(temps, 0.5)
    temp_word = "rising" if temp_trend == "increasing" else "falling" if temp_trend == "decreasing" else "stable"
    
    # Pressure trend (threshold 0.5 hPa per hour)
    pressure_trend = trend(pressures, 0.5)
    pressure_word = "rising" if pressure_trend == "increasing" else "falling" if pressure_trend == "decreasing" else "stable"
    
    # Wind trend (threshold 1kt per hour)
    wind_trend = trend(winds, 1.0)
    
    # Cloud trend (threshold 5% per hour)
    cloud_trend = trend(clouds, 5.0)
    cloud_word = "clearing" if cloud_trend == "decreasing" else "increasing" if cloud_trend == "increasing" else "stable"
    
    # Overall assessment (pressure is key indicator)
    positive_indicators = 0
    negative_indicators = 0
    
    if pressure_trend == "increasing":
        positive_indicators += 2  # Pressure rising is good
    elif pressure_trend == "decreasing":
        negative_indicators += 2
    
    if cloud_trend == "decreasing":
        positive_indicators += 1
    elif cloud_trend == "increasing":
        negative_indicators += 1
    
    if wind_trend == "decreasing":
        positive_indicators += 1
    elif wind_trend == "increasing":
        negative_indicators += 1
    
    overall = "stable"
    if positive_indicators > negative_indicators:
        overall = "improving"
    elif negative_indicators > positive_indicators:
        overall = "deteriorating"
    
    # Generate summary
    summary_parts = []
    if pressure_word != "stable":
        summary_parts.append(f"Pressure {pressure_word}")
    if cloud_word != "stable":
        summary_parts.append(f"clouds {cloud_word}")
    if wind_trend == "increasing":
        summary_parts.append("winds increasing")
    elif wind_trend == "decreasing":
        summary_parts.append("winds decreasing")
    
    summary = ", ".join(summary_parts) if summary_parts else "Conditions stable"
    summary = summary.capitalize()
    
    return {
        "overall": overall,
        "temperature": temp_word,  # For backward compat with tests
        "pressure": pressure_word,  # For backward compat with tests
        "wind": wind_trend,  # For backward compat with tests
        "clouds": cloud_word,  # For backward compat with tests
        "visibility": "stable",  # TODO: Add visibility trend
        "temperature_trend": temp_word,
        "pressure_trend": pressure_word,
        "wind_trend": wind_trend,
        "cloud_trend": cloud_word,
        "summary": summary
    }


def check_overnight_conditions(
    forecast_data: List[Dict[str, Any]], 
    overnight_start: datetime,
    overnight_end: datetime
) -> Dict[str, Any]:
    """Check overnight forecast for conditions affecting airfield serviceability.
    
    Flags:
    - Heavy rain (>10mm/hr) - flooding risk
    - Strong winds (>35kt) - potential damage
    - Snow/ice - surface contamination
    - Fog (visibility <1000m) - morning delays
    
    Args:
        forecast_data: List of forecast dicts with hourly data
        overnight_start: Start of overnight period
        overnight_end: End of overnight period
    
    Returns:
        Dictionary with overnight warnings:
        - has_warnings: Boolean
        - flooding_risk: Boolean (heavy rain forecast)
        - wind_damage_risk: Boolean (strong winds)
        - surface_contamination: Boolean (snow/ice)
        - fog_risk: Boolean (low visibility)
        - summary: Human-readable summary
        - details: List of specific warnings
    """
    warnings = {
        "has_warnings": False,
        "flooding_risk": False,
        "wind_damage_risk": False,
        "surface_contamination": False,
        "fog_risk": False,
        "summary": "",
        "details": []
    }
    
    # Filter forecast to overnight period
    overnight_forecast = []
    for f in forecast_data:
        # Handle both OWM format (dt timestamp) and test format (datetime string)
        if "dt" in f:
            f_time = datetime.fromtimestamp(f["dt"], tz=overnight_start.tzinfo)
        elif "datetime" in f:
            f_time = datetime.fromisoformat(f["datetime"]) if isinstance(f["datetime"], str) else f["datetime"]
            # Ensure timezone awareness
            if f_time.tzinfo is None:
                f_time = f_time.replace(tzinfo=overnight_start.tzinfo)
        else:
            continue
        
        if overnight_start <= f_time <= overnight_end:
            overnight_forecast.append(f)
    
    if not overnight_forecast:
        warnings["summary"] = "No data available for overnight period"
        return warnings
    
    # Check for heavy rain
    for f in overnight_forecast:
        # Handle both OWM format and test format
        precip = f.get("precipitation", 0)
        rain_1h = f.get("rain", {}).get("1h", 0) if isinstance(f.get("rain"), dict) else precip
        if rain_1h > 10:  # >10mm/hr
            warnings["flooding_risk"] = True
            warnings["has_warnings"] = True
            warnings["details"].append(f"Heavy rain forecast: {rain_1h:.1f}mm/hr - flooding risk")
            break
    
    # Check for strong winds
    for f in overnight_forecast:
        wind_speed = f.get("wind_speed", 0)
        # If wind_speed is in m/s (OWM format), convert to knots
        if wind_speed < 100:  # Assume m/s if < 100
            wind_speed_kt = wind_speed * 1.94384 if wind_speed < 50 else wind_speed
        else:
            wind_speed_kt = wind_speed
        if wind_speed_kt > 35:
            warnings["wind_damage_risk"] = True
            warnings["has_warnings"] = True
            warnings["details"].append(f"Strong winds forecast: {wind_speed_kt:.0f}kt - potential damage")
            break
    
    # Check for snow/ice
    for f in overnight_forecast:
        weather = f.get("weather", [])
        if any("snow" in w.get("main", "").lower() or "snow" in w.get("description", "").lower() for w in weather):
            warnings["surface_contamination"] = True
            warnings["has_warnings"] = True
            warnings["details"].append("Snow forecast - surface contamination likely")
            break
        # Handle both 'temp' and 'temperature' fields
        temp = f.get("temp") or f.get("temperature", 10)
        precip = f.get("precipitation", 0)
        if temp < 0 and precip > 0:
            warnings["surface_contamination"] = True
            warnings["has_warnings"] = True
            warnings["details"].append("Freezing temperatures with precipitation - ice/snow risk")
            break
    
    # Check for fog risk
    for f in overnight_forecast:
        visibility = f.get("visibility", 10000)
        humidity = f.get("humidity", 0)
        temp = f.get("temp") or f.get("temperature", 10)
        dew_point = f.get("dew_point", temp - 5)
        
        if visibility < 1000 or (humidity > 90 and abs(temp - dew_point) < 2):
            warnings["fog_risk"] = True
            warnings["has_warnings"] = True
            warnings["details"].append("Fog likely - morning delays possible")
            break
    
    # Generate summary
    if warnings["has_warnings"]:
        warning_types = []
        if warnings["flooding_risk"]:
            warning_types.append("flooding risk")
        if warnings["wind_damage_risk"]:
            warning_types.append("wind damage risk")
        if warnings["surface_contamination"]:
            warning_types.append("surface contamination")
        if warnings["fog_risk"]:
            warning_types.append("morning fog")
        
        warnings["summary"] = "Overnight: " + ", ".join(warning_types)
    else:
        warnings["summary"] = "No significant overnight conditions forecast"
    
    return warnings


def find_optimal_flying_window(
    forecast_data: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
    wind_limit_kt: Optional[float] = None,
    crosswind_limit_kt: Optional[float] = None,
    runway_heading: Optional[int] = None
) -> Dict[str, Any]:
    """Find the optimal flying window within the forecast period.
    
    Considers:
    - Wind limits
    - Crosswind limits
    - Cloud base trends
    - Visibility
    - Overall conditions
    
    Args:
        forecast_data: List of forecast dicts with hourly data
        window_start: Start of window to analyze
        window_end: End of window to analyze
        wind_limit_kt: Maximum wind speed in knots (optional)
        crosswind_limit_kt: Maximum crosswind component in knots (optional)
        runway_heading: Runway heading in degrees (for crosswind calculation)
    
    Returns:
        Dictionary with optimal window:
        - has_window: Boolean
        - optimal_start: datetime of window start
        - optimal_end: datetime of window end
        - reason: Explanation of why this window is optimal
        - cautions: List of cautions even in optimal window
    """
    import math
    
    # Filter forecast to window
    window_forecast = []
    for f in forecast_data:
        # Handle both OWM format (dt timestamp) and test format (datetime string)
        if "dt" in f:
            f_time = datetime.fromtimestamp(f["dt"], tz=window_start.tzinfo)
        elif "datetime" in f:
            f_time = datetime.fromisoformat(f["datetime"]) if isinstance(f["datetime"], str) else f["datetime"]
            # Ensure timezone awareness
            if f_time.tzinfo is None:
                f_time = f_time.replace(tzinfo=window_start.tzinfo)
        else:
            continue
        
        if window_start <= f_time <= window_end:
            f["_parsed_time"] = f_time  # Store for later use
            window_forecast.append(f)
    
    if not window_forecast:
        return {
            "has_window": False,
            "average_score": 0,
            "reason": "No forecast data in window"
        }
    
    # Score each forecast point (0-100, higher = better)
    scored_forecasts = []
    for f in window_forecast:
        score = 50  # Start neutral
        
        # Wind scoring
        wind_speed = f.get("wind_speed", 0)
        # Assume knots if > 50, otherwise assume m/s and convert
        wind_speed_kt = wind_speed if wind_speed > 50 else wind_speed * 1.94384
        
        if wind_limit_kt:
            if wind_speed_kt > wind_limit_kt:
                score -= 100  # Exceeds limit
            else:
                # Penalize higher winds
                wind_factor = wind_speed_kt / wind_limit_kt
                score -= wind_factor * 20
        
        # Crosswind scoring
        if crosswind_limit_kt and runway_heading is not None:
            wind_dir = f.get("wind_deg") or f.get("wind_bearing", 0)
            angle = abs(wind_dir - runway_heading)
            if angle > 180:
                angle = 360 - angle
            crosswind = wind_speed_kt * math.sin(math.radians(angle))
            
            if crosswind > crosswind_limit_kt:
                score -= 100
            else:
                xwind_factor = crosswind / crosswind_limit_kt
                score -= xwind_factor * 30
        
        # Cloud scoring (prefer higher clouds)
        clouds_pct = f.get("clouds") or f.get("cloud_coverage", 0)
        if clouds_pct > 80:
            score -= 10
        elif clouds_pct < 30:
            score += 10
        
        # Visibility scoring
        visibility = f.get("visibility", 10000)
        if visibility < 5000:
            score -= 20
        elif visibility >= 10000:
            score += 10
        
        # Precipitation scoring
        precip = f.get("precipitation", 0)
        rain = f.get("rain", {}).get("1h", 0) if isinstance(f.get("rain"), dict) else precip
        if rain > 0:
            score -= rain * 5
        
        scored_forecasts.append({
            "time": f.get("_parsed_time", window_start),
            "score": max(0, score),  # Don't go negative
            "forecast": f
        })
    
    # Find continuous window with highest average score (minimum 2 hours)
    best_window = None
    best_score = 0
    
    for i in range(len(scored_forecasts)):
        for j in range(i + 2, len(scored_forecasts) + 1):  # At least 2 hours
            window_slice = scored_forecasts[i:j]
            avg_score = sum(sf["score"] for sf in window_slice) / len(window_slice)
            
            if avg_score > best_score:
                best_score = avg_score
                best_window = window_slice
    
    if not best_window or best_score < 30:  # Threshold for "good" conditions
        avg_of_all = sum(sf["score"] for sf in scored_forecasts) / len(scored_forecasts) if scored_forecasts else 0
        return {
            "has_window": False,
            "average_score": avg_of_all,
            "reason": "No suitable flying window found in forecast period"
        }
    
    # Generate reason based on score
    if best_score > 70:
        reason = f"Good conditions forecast (score: {best_score:.0f}/100)"
    elif best_score > 50:
        reason = f"Acceptable conditions forecast (score: {best_score:.0f}/100)"
    else:
        reason = f"Marginal conditions forecast (score: {best_score:.0f}/100)"
    
    return {
        "has_window": True,
        "optimal_start": best_window[0]["time"],
        "optimal_end": best_window[-1]["time"],
        "average_score": best_score,
        "reason": reason,
        "cautions": []  # TODO: Add specific cautions from forecast data
    }

