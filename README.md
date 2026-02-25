# 🌅 SunsetAuto — Sunrise & Sunset Quality Checker

A Python GUI app that uses the **SunsetHue API** to check sunrise and sunset quality ratings for any location. Paste an **AllTrails trail link** (the app auto-detects the city) or type a **city name** directly.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **AllTrails integration** — paste any AllTrails trail URL and the app scrapes the city/region automatically.
- **City name input** — just type a city name as an alternative.
- **SunsetHue quality ratings** — sunrise and sunset quality forecasts (0–100%) with categories: Poor, Fair, Good, Great, Excellent.
- **Rich forecast details** — cloud cover, golden hour, blue hour, and sun times when available.
- **Dark-themed GUI** — clean, modern tkinter interface.

---

## Quick Start

### 1. Get a SunsetHue API Key (free)

1. Go to [sunsethue.com/dev-api](https://sunsethue.com/dev-api)
2. Sign up for a free account
3. Generate your API key in the [API portal](https://sunsethue.com/dev-api/portal)
4. The free plan gives **1 000 credits/day** (or request a quota increase for up to **10 000/day**)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the App

```bash
python sunset_auto.py
```

### 4. Use It

1. Paste your **SunsetHue API key** in the top field
2. Enter an **AllTrails link** (e.g. `https://www.alltrails.com/trail/us/colorado/flatirons-loop`)  
   **OR** a **city name** (e.g. `Denver, Colorado`)
3. Click **Check Sunset & Sunrise Quality**
4. View the sunrise & sunset quality ratings and forecast details

---

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  User Input  │────▶│ AllTrails    │────▶│  Nominatim   │────▶│  SunsetHue  │
│  (URL/City)  │     │ City Extract │     │  Geocoding   │     │  Forecast   │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
                                                                      │
                                                               ┌──────▼──────┐
                                                               │   Display   │
                                                               │   Results   │
                                                               └─────────────┘
```

1. **AllTrails link** → scrapes the trail page to extract the nearby city
2. **City name** → used directly
3. City is **geocoded** to lat/lng via OpenStreetMap Nominatim
4. Lat/lng are sent to the **SunsetHue API** for quality forecast
5. Results are displayed in the GUI with color-coded quality ratings

---

## Quality Categories (from SunsetHue)

| Range     | Category   | Description                                      |
|-----------|------------|--------------------------------------------------|
| 0–20%     | Poor       | Little to no color, heavy cloud blocking          |
| 20–40%    | Fair       | Bland, few or no reflective clouds                |
| 40–60%    | Good       | Some nice clouds reflecting light                 |
| 60–80%    | Great      | Vivid, colorful, long-lasting                     |
| 80–100%   | Excellent  | Spectacular, rare, full sky illumination           |

---

## Dependencies

| Package          | Purpose                            |
|------------------|------------------------------------|
| `requests`       | HTTP calls to APIs                 |
| `beautifulsoup4` | Scraping AllTrails trail pages      |
| `tkinter`        | GUI (included with Python)          |

---

## Credits

- Forecasts powered by [SunsetHue](https://sunsethue.com/)
- Geocoding by [OpenStreetMap / Nominatim](https://nominatim.openstreetmap.org/)
