"""
api_engine.py - Async API engine for fetching weather & sunset data.

Concurrently fetches data from:
  - Sunrise-Sunset API (free, no key)
  - NWS Weather API (free, no key)

Includes caching and error handling.
"""

import asyncio
import aiohttp
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import os

# Simple file-based cache for NWS grid points (to avoid repeated lookups)
GRID_CACHE_FILE = ".nws_grid_cache.json"


class GridPointCache:
    """Simple file-based cache for NWS grid point lookups."""
    
    def __init__(self, filename=GRID_CACHE_FILE):
        self.filename = filename
        self.data = self._load()
    
    def _load(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save(self):
        try:
            with open(self.filename, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass
    
    def get_key(self, lat: float, lon: float) -> str:
        """Create a cache key from lat/lon."""
        return f"{lat:.4f},{lon:.4f}"
    
    def get(self, lat: float, lon: float) -> Optional[Dict]:
        """Retrieve cached grid point data."""
        key = self.get_key(lat, lon)
        return self.data.get(key)
    
    def put(self, lat: float, lon: float, grid_data: Dict):
        """Store grid point data."""
        key = self.get_key(lat, lon)
        self.data[key] = grid_data
        self._save()


grid_cache = GridPointCache()


async def fetch_url(session: aiohttp.ClientSession, url: str, 
                    params: Dict = None) -> Optional[Dict]:
    """Fetch a URL and return JSON, with error handling."""
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(10)) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                print(f"❌ API error ({resp.status}): {url}")
                return None
    except asyncio.TimeoutError:
        print(f"⏱️  Timeout: {url}")
        return None
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None


async def fetch_sunset_data(session: aiohttp.ClientSession, 
                            lat: float, lon: float, date: str) -> Optional[Dict]:
    """
    Fetch sunset/sunrise data from sunrise-sunset.org API.
    
    Args:
        session: aiohttp session
        lat, lon: Coordinates
        date: YYYY-MM-DD format
    
    Returns:
        Dict with keys: sunset, sunrise, civil_twilight_begin, civil_twilight_end, etc.
    """
    url = "https://api.sunrise-sunset.org/json"
    params = {
        "lat": lat,
        "lng": lon,
        "date": date,
        "formatted": 0,  # Return ISO 8601 UTC times
    }
    data = await fetch_url(session, url, params)
    if data and data.get("status") == "OK":
        return data.get("results", {})
    return None


async def fetch_nws_grid_points(session: aiohttp.ClientSession, 
                                 lat: float, lon: float) -> Optional[Dict]:
    """
    Fetch NWS grid point data (gridId, gridX, gridY).
    Cached locally to avoid repeated requests.
    
    Args:
        session: aiohttp session
        lat, lon: Coordinates
    
    Returns:
        Dict with keys: gridId, gridX, gridY, forecastGridDataUrl, etc.
    """
    # Check cache first
    cached = grid_cache.get(lat, lon)
    if cached:
        return cached
    
    url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
    data = await fetch_url(session, url)
    if data and data.get("properties"):
        props = data["properties"]
        grid_data = {
            "gridId": props.get("gridId"),
            "gridX": props.get("gridX"),
            "gridY": props.get("gridY"),
            "forecastGridDataUrl": props.get("forecastGridDataUrl"),
        }
        grid_cache.put(lat, lon, grid_data)
        return grid_data
    return None


async def fetch_nws_forecast(session: aiohttp.ClientSession, 
                              gridId: str, gridX: int, gridY: int) -> Optional[Dict]:
    """
    Fetch NWS forecast grid data (includes skyCover).
    
    Args:
        session: aiohttp session
        gridId, gridX, gridY: From NWS grid points API
    
    Returns:
        Raw forecast data with skyCover array, etc.
    """
    url = f"https://api.weather.gov/gridpoints/{gridId}/{gridX},{gridY}/forecast"
    return await fetch_url(session, url)


def extract_sky_cover_at_time(forecast_periods, target_time_iso: str) -> Optional[int]:
    """
    Extract the sky cover percentage at a specific time.
    
    Args:
        forecast_periods: List of forecast periods from NWS API
        target_time_iso: ISO 8601 time string (e.g., from sunset API)
    
    Returns:
        Sky cover percentage (0-100), or None if not found.
    """
    try:
        # Parse the target time
        target_dt = datetime.fromisoformat(target_time_iso.replace("Z", "+00:00"))
        target_hour = target_dt.hour
    except Exception:
        return None
    
    # Find the forecast period that matches the sunset hour
    for period in forecast_periods:
        try:
            start_time = period.get("startTime", "")
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            start_hour = start_dt.hour
            
            # Match on hour (rough but effective for hourly forecasts)
            if start_hour == target_hour:
                sky_cover = period.get("skyCover", {}).get("value")
                return sky_cover
        except Exception:
            continue
    
    return None


async def fetch_trail_weather(lat: float, lon: float, date: str) -> Dict:
    """
    Main async function: Fetch sunset time and cloud cover for a trail on a given date.
    
    Concurrently fetches from Sunrise-Sunset API and NWS Weather API.
    
    Args:
        lat, lon: Trail coordinates
        date: YYYY-MM-DD format
    
    Returns:
        Dict with keys:
        - sunset: ISO 8601 time string
        - sunrise: ISO 8601 time string
        - cloud_cover: Sky cover percentage (0-100) at sunset time
        - error: If something went wrong
    """
    async with aiohttp.ClientSession() as session:
        # Fetch sunset data and NWS grid points concurrently
        sunset_data, grid_data = await asyncio.gather(
            fetch_sunset_data(session, lat, lon, date),
            fetch_nws_grid_points(session, lat, lon),
        )
        
        result = {
            "sunset": None,
            "sunrise": None,
            "civil_twilight_begin": None,
            "cloud_cover": None,
            "error": None,
        }
        
        if not sunset_data:
            result["error"] = "Could not fetch sunset data"
            return result
        
        result["sunset"] = sunset_data.get("sunset")
        result["sunrise"] = sunset_data.get("sunrise")
        result["civil_twilight_begin"] = sunset_data.get("civil_twilight_begin")
        
        if not grid_data:
            result["error"] = "Could not fetch NWS grid data"
            return result
        
        # Fetch NWS forecast
        forecast_url = grid_data.get("forecastGridDataUrl")
        if not forecast_url:
            result["error"] = "No forecast URL from NWS"
            return result
        
        forecast_data = await fetch_url(session, forecast_url)
        if not forecast_data or "properties" not in forecast_data:
            result["error"] = "Could not fetch NWS forecast"
            return result
        
        # Extract sky cover at sunset time
        properties = forecast_data["properties"]
        periods = properties.get("periods", [])
        sky_cover = extract_sky_cover_at_time(periods, result["sunset"])
        result["cloud_cover"] = sky_cover
        
        return result


async def fetch_drive_time(session: aiohttp.ClientSession, 
                            origin_lat: float, origin_lon: float,
                            dest_lat: float, dest_lon: float,
                            google_api_key: str) -> Optional[int]:
    """
    Fetch drive time in traffic from origin to destination using Google Maps API.
    
    Args:
        session: aiohttp session
        origin_lat, origin_lon: User's starting location
        dest_lat, dest_lon: Trail's trailhead
        google_api_key: Google Maps API key
    
    Returns:
        Drive time in seconds, or None if error.
    """
    if not google_api_key:
        return None
    
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin_lat},{origin_lon}",
        "destinations": f"{dest_lat},{dest_lon}",
        "mode": "driving",
        "traffic_model": "best_guess",
        "departure_time": "now",
        "key": google_api_key,
    }
    
    data = await fetch_url(session, url, params)
    if not data or data.get("status") != "OK":
        return None
    
    try:
        rows = data.get("rows", [])
        if rows:
            element = rows[0].get("elements", [])[0]
            if element.get("status") == "OK":
                duration = element.get("duration_in_traffic", {}).get("value")
                return duration  # in seconds
    except (IndexError, KeyError, TypeError):
        pass
    
    return None


async def fetch_drive_time_batch(origin_lat: float, origin_lon: float,
                                  trails: list, google_api_key: str) -> Dict[str, int]:
    """
    Fetch drive times for multiple trails concurrently.
    
    Args:
        origin_lat, origin_lon: User's starting location
        trails: List of dicts with keys: id (UUID), lat, lon
        google_api_key: Google Maps API key
    
    Returns:
        Dict mapping trail_id -> drive_time_seconds
    """
    if not google_api_key:
        return {t["id"]: None for t in trails}
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_drive_time(session, origin_lat, origin_lon,
                            t["lat"], t["lon"], google_api_key)
            for t in trails
        ]
        durations = await asyncio.gather(*tasks)
        return {t["id"]: dur for t, dur in zip(trails, durations)}


def seconds_to_minutes(seconds: Optional[int]) -> Optional[int]:
    """Convert seconds to minutes."""
    return round(seconds / 60) if seconds is not None else None


def calculate_hike_score(cloud_cover: Optional[int], 
                         drive_time_minutes: Optional[int],
                         elevation: Optional[int] = None) -> int:
    """
    Calculate an overall hike score (0-100) based on:
      - Cloud cover (lower is better)
      - Drive time (shorter is better)
      - Elevation (bonus for scenic peaks)
    
    Scoring logic:
      - Cloud cover: 0% = 40 pts, 100% = 0 pts
      - Drive time: 15 min = 40 pts, 120 min = 10 pts
      - Elevation: > 2000 ft = +20 pts
    
    Args:
        cloud_cover: Sky cover percentage (0-100)
        drive_time_minutes: Drive time in minutes
        elevation: Elevation in feet (optional)
    
    Returns:
        Overall score (0-100)
    """
    score = 0
    
    # Sky cover (40 points) - lower is better
    if cloud_cover is not None:
        # 0% clear = 40 pts, 100% cloudy = 0 pts
        sky_score = 40 * (1 - cloud_cover / 100.0)
        score += sky_score
    
    # Drive time (40 points) - shorter is better
    if drive_time_minutes is not None:
        # 15 min = 40 pts, 120 min = 10 pts (linear interpolation)
        if drive_time_minutes <= 15:
            drive_score = 40
        elif drive_time_minutes >= 120:
            drive_score = 10
        else:
            # Linear: 40 at 15 min, 10 at 120 min
            drive_score = 40 - (drive_time_minutes - 15) * (30 / (120 - 15))
        score += drive_score
    
    # Elevation bonus (20 points) - peaks are scenic
    if elevation and elevation > 2000:
        elevation_score = 20
        score += elevation_score
    
    return min(100, max(0, int(score)))


# Test function
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python api_engine.py <lat> <lon> <date>")
        print("Example: python api_engine.py 37.3715 -122.2250 2026-03-20")
        sys.exit(1)
    
    lat, lon, date = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
    
    print(f"🌄 Fetching weather for ({lat}, {lon}) on {date}...")
    result = asyncio.run(fetch_trail_weather(lat, lon, date))
    print(json.dumps(result, indent=2))
    
    # Test scoring
    cloud = result.get("cloud_cover", 50)
    drive_time = 45
    elevation = 2100
    score = calculate_hike_score(cloud, drive_time, elevation)
    print(f"\n📊 Score: {score}/100 (cloud: {cloud}%, drive: {drive_time} min, elev: {elevation} ft)")
