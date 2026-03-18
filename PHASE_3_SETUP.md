# The Sunset Club — Phase 3: Distance & Scoring Logic

## Overview

Phase 3 extends `api_engine.py` with:

1. **Google Maps Distance Matrix API** — Real-time drive time in traffic
2. **Hike Scoring Function** — Rates hikes on a 0-100 scale based on:
   - Cloud cover (40 pts)
   - Drive time (40 pts)
   - Elevation (20 pts bonus)

---

## Setup: Google Maps API Key

1. **Create a Google Cloud project:**
   - Go to [console.cloud.google.com](https://console.cloud.google.com/)
   - Click **Create Project**
   - Name it "Sunset Club"
   - Click **Create**

2. **Enable Distance Matrix API:**
   - Go to **APIs & Services → Library**
   - Search for **Distance Matrix API**
   - Click it → **Enable**

3. **Create an API key:**
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → API Key**
   - Copy the key

4. **Add to environment:**
   ```bash
   # Windows PowerShell:
   $env:GOOGLE_MAPS_API_KEY = "your-api-key"
   
   # Linux/Mac:
   export GOOGLE_MAPS_API_KEY="your-api-key"
   ```

---

## Usage

### Calculate Drive Time

```python
import asyncio
from api_engine import fetch_drive_time_batch

api_key = "your-google-maps-api-key"

trails = [
    {"id": "trail-1", "lat": 37.3715, "lon": -122.2250},  # Windy Hill
    {"id": "trail-2", "lat": 37.5126, "lon": -121.8806},  # Mission Peak
]

# From user's location (e.g., Palo Alto)
origin_lat, origin_lon = 37.4419, -122.1430

durations = asyncio.run(fetch_drive_time_batch(
    origin_lat, origin_lon, trails, api_key
))

print(durations)
# Output: {'trail-1': 2700, 'trail-2': 3600}  (in seconds)
```

### Calculate Hike Score

```python
from api_engine import calculate_hike_score, seconds_to_minutes

# Scenario: Windy Hill on March 20
cloud_cover = 45  # %
drive_time_sec = 2700  # seconds
elevation = 1900  # feet

drive_time_min = seconds_to_minutes(drive_time_sec)
score = calculate_hike_score(cloud_cover, drive_time_min, elevation)

print(f"🏔️  Windy Hill: {score}/100")
# Output: 🏔️  Windy Hill: 67/100
```

---

## Scoring Logic

### Cloud Cover (40 points)
```
0% clear → 40 pts
100% cloudy → 0 pts
(linear interpolation)
```

### Drive Time (40 points)
```
≤ 15 min → 40 pts
120+ min → 10 pts
(linear interpolation for values in between)
```

### Elevation Bonus (20 points)
```
> 2000 ft → +20 pts
```

### Example Scores

| Trail | Cloud | Drive | Elev | Score |
|-------|-------|-------|------|-------|
| Windy Hill (clear, close, peak) | 0% | 45 min | 1900 ft | 65 |
| Mission Peak (hazy, far, peak) | 60% | 60 min | 2517 ft | 72 |
| Point Reyes (cloudy, very far, low) | 80% | 100 min | 1050 ft | 12 |

---

## API Functions

### `fetch_drive_time(...) → Optional[int]`

Single trail drive time:

```python
async with aiohttp.ClientSession() as session:
    duration_sec = await fetch_drive_time(
        session,
        origin_lat=37.4419,
        origin_lon=-122.1430,
        dest_lat=37.3715,
        dest_lon=-122.2250,
        google_api_key=api_key
    )
    # Returns 2700 (seconds) or None if error
```

### `fetch_drive_time_batch(...) → Dict[str, int]`

Multiple trails concurrently:

```python
durations = asyncio.run(fetch_drive_time_batch(
    origin_lat, origin_lon, trails, api_key
))
# Returns: {'trail-1': 2700, 'trail-2': 3600, ...}
```

### `calculate_hike_score(cloud_cover, drive_time_min, elevation) → int`

Score based on conditions:

```python
score = calculate_hike_score(
    cloud_cover=45,           # %
    drive_time_minutes=45,    # minutes
    elevation=1900            # feet (optional)
)
# Returns: 67 (0-100 scale)
```

---

## Cost Warnings

**Google Maps Distance Matrix API pricing:**
- **Free tier:** 25,000 requests/month
- **Paid:** $0.005 per request after free tier (for 100,000+ requests/month)

**Optimization tips:**
- Cache results for 24 hours (user's location rarely changes)
- Use `departure_time=now` for real-time traffic (not free tier for future dates)
- Batch requests (up to 25 destinations per request)

---

## Next: Phase 4

Phase 4 integrates everything into the Streamlit UI:
- ✅ Sidebar filters (date, drive time, difficulty, length)
- ✅ Fetch trails from Supabase
- ✅ Async API calls for weather + drive time
- ✅ Calculate scores and sort results
- ✅ Display top 3 hikes in expandable cards

**Phase 4 will connect:**
- Supabase (trails database)
- api_engine.py (weather + scoring)
- Streamlit (UI/UX)
