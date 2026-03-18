# The Sunset Club — Full-Stack Platform

A community-driven web application for Bay Area hikers to discover the best trails for sunset/sunrise photography based on real-time weather, drive time, and peer reviews.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI                         │
│  (Phase 4: Filters, Cards, Community Reviews)          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ├─────► Supabase (PostgreSQL)
                     │       - trails table
                     │       - users table  
                     │       - reviews table
                     │
        ┌────────────┴────────────┐
        │                         │
    api_engine.py             seed_db.py
    (Phase 2-3)               (Phase 1)
        │                         │
        ├─► Sunrise-Sunset API    └─► Manual DB seeding
        ├─► NWS Weather API           (5 sample trails)
        └─► Google Maps API
```

---

## Phases

### [Phase 1: Database Setup](PHASE_1_SETUP.md)

**Goal:** Create a Supabase project and seed it with 5 Bay Area trails.

**Deliverables:**
- `seed_db.py` — Python script to seed Supabase
- `trails` table with columns: id, name, lat, lon, elevation_ft, difficulty, length_miles, alltrails_url

**Time to complete:** 10 minutes

**What you'll have:**
```
Database: Supabase PostgreSQL
Tables:
  - trails (5 sample hiking spots)
```

---

### [Phase 2: Async API Engine](PHASE_2_SETUP.md)

**Goal:** Build a fast, async API engine that fetches weather and sunset data.

**Deliverables:**
- `api_engine.py` with core functions:
  - `fetch_trail_weather(lat, lon, date)` — Gets sunset time + cloud cover
  - Caching for NWS grid points (avoids repeated API calls)
  - Error handling and graceful fallbacks

**No API keys needed!** Sunrise-Sunset and NWS are free public APIs.

**Time to complete:** 5 minutes (just test the existing code)

**What you'll have:**
```
python api_engine.py 37.3715 -122.2250 2026-03-20
Output:
{
  "sunset": "2026-03-20T19:47:32+00:00",
  "cloud_cover": 45,
  "error": null
}
```

---

### [Phase 3: Distance & Scoring Logic](PHASE_3_SETUP.md)

**Goal:** Add drive time calculation and hike scoring.

**Deliverables:**
- `api_engine.py` extended with:
  - `fetch_drive_time_batch(origin_lat, origin_lon, trails, api_key)` — Google Maps
  - `calculate_hike_score(cloud_cover, drive_time, elevation)` — Scoring logic

**API key needed:** Google Maps Distance Matrix API (free tier: 25K requests/month)

**Time to complete:** 10 minutes

**What you'll have:**
```
Hike scoring based on:
  - Cloud cover (40 pts) — 0% clear = 40 pts, 100% cloudy = 0 pts
  - Drive time (40 pts) — 15 min = 40 pts, 120+ min = 10 pts
  - Elevation (20 pts) — > 2000 ft = +20 pts bonus
  
Result: 0-100 score for each trail
```

---

### Phase 4: Streamlit UI (Coming Next)

**Goal:** Build the full Streamlit interface with filters, sorting, and results.

**Will include:**
- Sidebar filters: Date, max drive time, difficulty, max length
- Sorting options: Best % Good, Closest Drive, Highest Rated
- Results: Top 3 hikes with detailed cards
- Expandable details for each hike
- Community reviews (Phase 5)

---

### Phase 5: Community Social Features (Coming Later)

**Will include:**
- Supabase Auth (email signup/login)
- Review submission form (rating + text)
- Photo upload to Supabase Storage
- Display reviews on each trail card

---

## File Structure

```
SunsetAuto/
├── streamlit_app.py              # Current Streamlit version
├── sunset_auto.py                # Desktop tkinter version (legacy)
├── seed_db.py                    # Phase 1: Database seeding
├── api_engine.py                 # Phase 2-3: Weather + scoring
├── requirements.txt              # Dependencies
├── .streamlit/
│   └── config.toml              # Streamlit theme
├── PHASE_1_SETUP.md             # Database setup guide
├── PHASE_2_SETUP.md             # API engine guide
├── PHASE_3_SETUP.md             # Scoring guide
├── INSTRUCTIONS.md              # Original SunsetAuto docs
└── README.md                    # This file
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit | Interactive web UI |
| **Backend** | Python + aiohttp | Async API orchestration |
| **Database** | Supabase (PostgreSQL) | Trails, users, reviews |
| **Auth** | Supabase Auth | User login/signup |
| **Storage** | Supabase Storage (S3) | Trail photos |
| **APIs** | Sunrise-Sunset (free) | Sunset times |
| | NWS (free) | Cloud cover |
| | Google Maps (freemium) | Drive times |

---

## Quick Start

### For Business School

This project demonstrates:

✅ **Data Ownership** — Static database of curated trails (avoids scraping)  
✅ **Performance** — Async API calls (concurrent, not sequential)  
✅ **Monetization** — Free tier (Google Maps: $0.005/request after 25K/month)  
✅ **Community** — User reviews, ratings, photo uploads  
✅ **Scalability** — Serverless backend (Streamlit Cloud) + managed DB (Supabase)  

### For Immediate Use

1. **Clone the repo:**
   ```bash
   git clone https://github.com/jyroscoped/SunsetAuto.git
   cd SunsetAuto
   ```

2. **Follow Phase 1:** Set up Supabase and seed the database
3. **Follow Phase 2:** Test the async API engine
4. **Follow Phase 3:** Add Google Maps API key for drive times
5. **Wait for Phase 4:** Full Streamlit integration (coming soon)

---

## Current Status

✅ Phase 1: Database setup script (ready)  
✅ Phase 2: Async API engine (ready)  
✅ Phase 3: Distance matrix + scoring (ready)  
🔲 Phase 4: Streamlit UI integration (in progress)  
🔲 Phase 5: Community features (planned)  

---

## Questions?

Refer to the phase-specific guides:
- **Database questions?** → [PHASE_1_SETUP.md](PHASE_1_SETUP.md)
- **API engine questions?** → [PHASE_2_SETUP.md](PHASE_2_SETUP.md)
- **Scoring questions?** → [PHASE_3_SETUP.md](PHASE_3_SETUP.md)

---

## License

MIT
