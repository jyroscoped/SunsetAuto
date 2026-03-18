# The Sunset Club — Phase 2: Async API Engine

## Overview

The async API engine is in `api_engine.py`. It concurrently fetches:

1. **Sunrise-Sunset API** — Sunset time, sunrise time, golden hour times
2. **NWS Weather API** — Cloud cover percentage at sunset time (2-step process)

**Benefits:**
- ✅ Fast: All API calls happen concurrently (1 sec vs 10 sec sequential)
- ✅ Cached: NWS grid points are cached locally to avoid repeated lookups
- ✅ Error handling: Graceful fallbacks if an API fails

---

## Installation

Install the new dependencies:

```bash
pip install aiohttp python-dateutil
```

---

## Usage

### Single Trail Forecast

Test fetching weather for a trail on a specific date:

```bash
python api_engine.py 37.3715 -122.2250 2026-03-20
```

**Output:**
```json
{
  "sunset": "2026-03-20T19:47:32+00:00",
  "sunrise": "2026-03-20T07:16:18+00:00",
  "civil_twilight_begin": "2026-03-20T06:46:39+00:00",
  "cloud_cover": 45,
  "error": null
}
```

### In Python Code

```python
import asyncio
from api_engine import fetch_trail_weather

# Get forecast for Windy Hill on March 20, 2026
result = asyncio.run(fetch_trail_weather(37.3715, -122.2250, "2026-03-20"))

print(f"Sunset: {result['sunset']}")
print(f"Cloud cover: {result['cloud_cover']}%")
```

---

## API Functions

### `fetch_trail_weather(lat, lon, date) → Dict`

**Parameters:**
- `lat` (float): Trail latitude
- `lon` (float): Trail longitude
- `date` (str): Date in YYYY-MM-DD format

**Returns:**
```python
{
    "sunset": "ISO 8601 UTC time string",
    "sunrise": "ISO 8601 UTC time string",
    "civil_twilight_begin": "ISO 8601 UTC time string (for golden hour)",
    "cloud_cover": int (0-100, or None if unavailable),
    "error": str (error message, or None on success)
}
```

---

## Caching

NWS grid point lookups are cached in `.nws_grid_cache.json`:

```json
{
  "37.3715,-122.2250": {
    "gridId": "LOX",
    "gridX": 72,
    "gridY": 52,
    "forecastGridDataUrl": "..."
  }
}
```

This avoids repeated requests to `api.weather.gov/points/{lat},{lon}`.

---

## Error Handling

If something fails, the `error` field will contain a message:

```python
result = asyncio.run(fetch_trail_weather(999, 999, "2026-03-20"))
if result["error"]:
    print(f"⚠️  {result['error']}")
```

---

## Next: Phase 3

Phase 3 adds:
- ✅ Google Maps Distance Matrix API for drive times
- ✅ Hike scoring function based on cloud cover, drive time, and elevation

**You'll need:**
- A Google Maps API key (get one at: https://console.cloud.google.com/)
  - Enable the **Distance Matrix API**
  - Create a new API key

Then you'll be ready to integrate everything into the Streamlit UI!
