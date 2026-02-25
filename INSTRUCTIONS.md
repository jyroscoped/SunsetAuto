# SunsetAuto — Instructions, Solutions & Technical Notes

> A complete reference for how SunsetAuto works, the problems encountered
> during development, how they were solved, and how to maintain the project.

---

## Table of Contents

1. [Overview](#overview)
2. [Setup & Installation](#setup--installation)
3. [SunsetHue API Reference](#sunsethue-api-reference)
4. [Problems Encountered & Solutions](#problems-encountered--solutions)
5. [Caching System](#caching-system)
6. [Feature Reference](#feature-reference)
7. [Quality Categories Guide](#quality-categories-guide)
8. [Architecture](#architecture)
9. [Credits & Contact](#credits--contact)

---

## Overview

SunsetAuto is a Python GUI app (tkinter) that uses the **SunsetHue API** to
check sunrise/sunset quality forecasts.  It accepts either an **AllTrails
trail URL** (auto-detects the city) or a raw **city name**, geocodes the
location, queries SunsetHue, and displays a color-coded multi-day forecast.

It also has a **"Scan Best Nearby Hikes"** feature that queries 28 curated
hiking spots within ~2.5 hours of Menlo Park, CA, ranks them by forecast
quality, and uses grid-based caching to minimize API calls.

---

## Setup & Installation

### Prerequisites

- **Python 3.9+** (3.11 recommended)
- A **SunsetHue API key** (free at <https://sunsethue.com/dev-api/portal>)

### Install dependencies

```bash
pip install -r requirements.txt
```

Dependencies:
| Package          | Purpose                           |
|------------------|-----------------------------------|
| `requests`       | HTTP calls to SunsetHue & Nominatim |
| `beautifulsoup4` | Scraping AllTrails trail pages     |
| `tkinter`        | GUI (bundled with Python)          |

### Run

```bash
python sunset_auto.py
```

Paste your API key, enter a city or AllTrails link, and click "Check".

---

## SunsetHue API Reference

Based on live testing and correspondence with the API creator (Maarten).

### Endpoint

```
GET https://api.sunsethue.com/forecast
```

### Authentication

| Method          | Example                                  |
|-----------------|------------------------------------------|
| Header          | `x-api-key: YOUR_KEY`                    |
| Query parameter | `?key=YOUR_KEY`                          |

### Query Parameters

| Parameter   | Type  | Description                               |
|-------------|-------|-------------------------------------------|
| `latitude`  | float | Latitude of the location (NOT `lat`)      |
| `longitude` | float | Longitude of the location (NOT `lng`)     |

> **IMPORTANT:** The parameter names are `latitude` and `longitude` in full.
> Using `lat` / `lng` will return a 200 response but with all-null data!

### Response Shape

```json
{
  "time": "ISO-8601 timestamp of the forecast run",
  "location": {
    "latitude": 37.4529,
    "longitude": -122.1817
  },
  "grid_location": {
    "latitude": 37.5,
    "longitude": -122.5
  },
  "data": [
    {
      "type": "sunrise",
      "model_data": true,
      "quality": 0.26,
      "quality_text": "Fair",
      "cloud_cover": 0.89,
      "time": "2026-02-18T14:55:00Z",
      "direction": 104,
      "magics": {
        "golden_hour": ["2026-02-18T14:39:00Z", "2026-02-18T15:09:00Z"],
        "blue_hour":   ["2026-02-18T14:21:00Z", "2026-02-18T14:33:00Z"]
      }
    },
    {
      "type": "sunset",
      "model_data": true,
      "quality": 0.0,
      "quality_text": "Poor",
      "cloud_cover": 1.0,
      "time": "2026-02-19T01:50:00Z",
      "direction": 255,
      "magics": { ... }
    }
  ]
}
```

### Key Fields

| Field                | Type    | Range   | Notes                                      |
|----------------------|---------|---------|--------------------------------------------|
| `quality`            | float   | 0.0–1.0 | Multiply by 100 for percentage             |
| `quality_text`       | string  | —       | "Poor", "Fair", "Good", "Great", "Excellent" |
| `cloud_cover`        | float   | 0.0–1.0 | Multiply by 100 for percentage             |
| `time`               | string  | —       | ISO-8601 in **UTC** — must convert to local! |
| `direction`          | float   | 0–360   | Compass bearing of the sun                 |
| `model_data`         | boolean | —       | `false` = no forecast data, skip this entry |
| `grid_location`      | object  | —       | The 0.5°×0.5° grid cell for this forecast  |
| `magics.golden_hour` | array   | —       | [start, end] ISO-8601 UTC strings          |
| `magics.blue_hour`   | array   | —       | [start, end] ISO-8601 UTC strings          |

### Quotas & Rate Limits

| Tier          | Daily Credits | Notes                          |
|---------------|---------------|--------------------------------|
| Free          | 1,000         | No commercial use              |
| Custom        | 10,000        | Granted on request by Maarten  |
| Pay-as-you-go | Unlimited     | $1 per 10,000 credits          |

- Each `/forecast` call costs 1 credit.
- Forecasts update **4 times per day** (at ~05:40, 10:20, 16:40, 22:20 UTC).
- The grid resolution is **0.5° × 0.5°** — all coordinates within the same
  cell return identical forecasts.

### Error Codes

| Status | Code | Message                |
|--------|------|------------------------|
| 400    | 204  | Exceeded daily quota   |
| 400    | ???  | Invalid API key        |
| 404    | —    | Wrong endpoint (e.g. `/v1/forecast`) |

---

## Problems Encountered & Solutions

### 1. 404 "Cannot GET /v1/forecast"

**Problem:** The initial implementation used `/v1/forecast` as the endpoint.
This returned a 404 error.

**Solution:** The correct endpoint is `/forecast` (no version prefix):
```
GET https://api.sunsethue.com/forecast
```

### 2. 200 OK but all-null data

**Problem:** After fixing the endpoint, the API returned `200` with valid
structure but every field (`quality`, `cloud_cover`, `time`, etc.) was `null`.

**Root Cause:** The query parameter names were wrong.  Using `lat` and `lng`
(shorthand) silently returns null data.

**Solution:** Use the full parameter names:
```
?latitude=37.4529&longitude=-122.1817
```

### 3. Times displayed in UTC instead of local time

**Problem:** The API returns all timestamps in UTC.  A sunrise at 6:55 AM PST
was displayed as "02:55 PM" — completely misleading.

**Solution:** Implemented `lng_to_utc_offset(longitude)` which estimates the
UTC offset from the longitude (each 15° ≈ 1 hour).  All times are now
converted to local time before display.  For Menlo Park (lng ≈ −122°):
offset = round(−122/15) = −8 → PST.

### 4. Sunset grouped under wrong day

**Problem:** A sunset at 5:50 PM PST on Feb 18 = 1:50 AM UTC on Feb 19.
The `_pair_by_day()` function was grouping by UTC date, so the sunset
appeared under the next day.

**Solution:** `_pair_by_day()` now converts to local time before extracting
the day key, so sunrise and sunset on the same local day stay together.

### 5. "Excellent" quality colored red

**Problem:** The color for "Excellent" was `#e74c3c` (red), which
psychologically signals "bad/danger" to users.

**Solution:** Changed to `#a855f7` (vivid purple), a distinctly positive and
celebratory color.

### 6. Direction shown as raw degrees only

**Problem:** "Direction: 255 deg" is not intuitive.

**Solution:** Added `degrees_to_compass()` that converts to a 16-point
compass (N, NNE, NE, ...).  Now displays as "WSW (255°)".

### 7. Excessive API calls during scan

**Problem:** Scanning 28 hiking spots used 28 API credits every time, even
though many spots (e.g. Marin Headlands, Mt. Tamalpais, Muir Beach) fall in
the same 0.5° grid cell and return identical forecasts.

**Solution (from Maarten's email):** Implemented `ForecastCache` — an
in-memory cache keyed by the `grid_location` returned by the API.  When a
second spot falls in the same grid cell, the cached response is reused.
This typically reduces the 28-spot scan from 28 calls to ~10–15 calls,
saving roughly 50% of credits.

### 8. Smart quotes causing SyntaxError

**Problem:** During one of the code edits, curly/smart quotes (`""`) were
accidentally inserted into f-strings instead of straight quotes (`""`),
causing a `SyntaxError` on launch.

**Solution:** Replaced all curly quotes with standard ASCII straight quotes.

### 9. Accidental file deletion

**Problem:** During a rewrite, `sunset_auto.py` was deleted via `Remove-Item`
before the replacement file was created, leaving the project empty.

**Solution:** Recreated the entire file from scratch with all accumulated
fixes applied.

---

## Caching System

### How It Works

```
User requests forecast for (lat, lng)
          │
          ▼
   ┌──────────────┐
   │ Compute grid  │   floor(lat / 0.5) × 0.5, floor(lng / 0.5) × 0.5
   │ cell key      │   e.g. (37.5, -122.5)
   └──────┬───────┘
          │
          ▼
  ┌───────────────┐     HIT              ┌─────────────────┐
  │ Cache lookup  │────────────────────▶  │ Return cached   │
  └───────┬───────┘                       │ response        │
          │ MISS                          └─────────────────┘
          ▼
  ┌───────────────┐     ┌──────────┐
  │ API call      │────▶│ Store in │────▶ Return fresh response
  └───────────────┘     │ cache    │
                        └──────────┘
```

### Configuration

| Setting            | Value              | Rationale                         |
|--------------------|--------------------|-----------------------------------|
| Cache key          | `grid_location`    | From API response (0.5° cell)     |
| TTL (expiry)       | 3 hours            | Forecasts update every ~6 hours   |
| Pre-compute key    | `floor(coord/0.5)` | Check cache before API call       |
| Scope              | In-memory (per run)| Resets when the app restarts      |

### Example: Bay Area Scan

Many hiking spots share grid cells:

| Grid Cell (37.5, −122.5) | Grid Cell (37.5, −122.0) | Grid Cell (38.0, −122.5) |
|--------------------------|--------------------------|--------------------------|
| Half Moon Bay            | Windy Hill               | Marin Headlands          |
| Pacifica (Mori Point)    | Russian Ridge            | Muir Beach Overlook      |
| Montara Mountain         | Skyline Ridge            | Lands End, SF            |

These groups share the same forecast, so only ~1 API call per group is needed.

---

## Feature Reference

### 1. Single-Location Check

- Enter an **AllTrails URL** or **city name**
- App detects the city (AllTrails: scrapes meta tags, JSON-LD, breadcrumbs,
  URL parsing; City: used directly)
- Geocodes to lat/lng via OpenStreetMap Nominatim
- Queries SunsetHue for multi-day forecast
- Displays sunrise + sunset side by side for each day with:
  - Quality percentage and category (color-coded)
  - Local event time
  - Cloud cover percentage
  - Compass direction
  - Golden hour and blue hour windows

### 2. Nearby Hike Scan

- Queries 28 curated hiking spots within ~2.5 hours of Menlo Park, CA
- Uses grid-based caching to minimize API calls
- Ranks all spots by their single best upcoming event quality
- Displays ranked cards with:
  - Quality score + category + event type (sunrise/sunset)
  - Location description
  - Estimated drive time
  - Event time, cloud cover, direction
  - Golden hour window
- Shows API call vs. cache hit statistics

---

## Quality Categories Guide

From the [SunsetHue interpreting guide](https://sunsethue.com/guide):

| Range     | Category   | What to Expect                                    | Color in App   |
|-----------|------------|---------------------------------------------------|----------------|
| 0–20%     | Poor       | No colors, heavy clouds blocking light            | Grey (#7f8c8d) |
| 20–40%    | Fair       | Bland, few/no reflective clouds, or too many      | Orange (#e67e22)|
| 40–60%    | Good       | Some middle/high clouds reflecting light           | Yellow (#f1c40f)|
| 60–80%    | Great      | Vivid, colorful, long-lasting, great expanse       | Green (#2ecc71) |
| 80–100%   | Excellent  | Spectacular, rare, full-sky illumination           | Purple (#a855f7)|

### How Quality is Computed (per SunsetHue whitepaper)

SunsetHue uses a **ray-based model**:
1. Rays are cast from the observer toward the sun direction
2. For each ray, clouds along the path are analyzed
3. If sunlight can reach a cloud and reflect back to the observer → high
   reflection potential
4. Quality = average reflection potential across all rays
5. Post-processed for humidity, sunset duration (varies by latitude/season)

Data source: **ICON weather model** (German DWD), 0.5° horizontal resolution,
updated 4× daily.

---

## Architecture

```
sunset_auto.py (single file, ~950 lines)
│
├── Configuration & Constants
│   ├── SUNSETHUE_BASE, NOMINATIM_URL
│   ├── QUALITY_COLORS
│   └── HIKING_SPOTS (28 Bay Area locations with coordinates)
│
├── ForecastCache (grid-based caching)
│   ├── _grid_key_for(lat, lng)  — compute 0.5° cell
│   ├── get(lat, lng)            — check cache
│   ├── put(response_dict)       — store by grid_location
│   └── TTL_SECONDS = 10800     — 3 hour expiry
│
├── Helper Functions
│   ├── quality_color()          — quality_text → hex color
│   ├── degrees_to_compass()     — 104° → "ESE"
│   ├── format_quality()         — 0.26 → "26%  (Fair)"
│   ├── lng_to_utc_offset()      — −122° → −8 (PST)
│   ├── format_utc_time()        — UTC ISO → local time string
│   ├── geocode_city()           — Nominatim geocoding
│   ├── extract_city_from_alltrails()  — scrape AllTrails
│   └── fetch_sunsethue_forecast()     — API call + caching
│
├── SunsetAutoApp (tkinter.Tk)
│   ├── _build_ui()              — dark-themed Catppuccin GUI
│   ├── _on_check() / _worker()  — single-location flow (threaded)
│   ├── _on_scan() / _scan_worker() — 28-spot scan flow (threaded)
│   ├── _render_results()        — multi-day forecast display
│   ├── _render_scan_results()   — ranked hike cards + cache stats
│   ├── _pair_by_day()           — group by local date
│   ├── _render_day_card()       — sunrise+sunset side-by-side
│   └── _render_event()          — single event detail card
│
└── Entry Point: if __name__ == "__main__"
```

### Threading Model

All network I/O runs in daemon threads (`_worker`, `_scan_worker`) to keep
the GUI responsive.  Results are marshalled back to the main thread via
`self.after(0, callback)`.

---

## Credits & Contact

- **SunsetHue API** by Maarten — <https://sunsethue.com>
  - Email: tropoflow@gmail.com
  - API docs: <https://documenter.getpostman.com/view/39964523/2sAYBUDY4W>
  - Quota: 10,000 credits/day (granted by Maarten for this project)
- **Geocoding** by OpenStreetMap / Nominatim
- **SunsetAuto** by Daniel
