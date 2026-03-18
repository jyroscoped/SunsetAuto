# The Sunset Club — Phase 1: Database Setup

## Step 1: Create a Supabase Account

1. Go to [supabase.com](https://supabase.com) and sign up (free tier is perfect)
2. Create a new project
3. Go to **Settings → API** and copy:
   - `Project URL` (e.g., `https://xxxxx.supabase.co`)
   - `anon public` key (the one under "API Key")

## Step 2: Create the `trails` Table

1. In your Supabase dashboard, go to **SQL Editor**
2. Click **New Query**
3. Paste and run this SQL:

```sql
CREATE TABLE IF NOT EXISTS trails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    lat FLOAT NOT NULL,
    lon FLOAT NOT NULL,
    elevation_ft INTEGER,
    difficulty TEXT CHECK (difficulty IN ('Easy', 'Moderate', 'Hard')),
    length_miles FLOAT,
    alltrails_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trails_difficulty ON trails(difficulty);
CREATE INDEX IF NOT EXISTS idx_trails_length ON trails(length_miles);
```

4. Execute the query. You should see "Success" ✅

## Step 3: Seed the Database

1. Install the required package:
   ```bash
   pip install supabase
   ```

2. Set environment variables for your Supabase credentials:
   ```bash
   # Windows PowerShell:
   $env:SUPABASE_URL = "https://xxxxx.supabase.co"
   $env:SUPABASE_KEY = "your-anon-public-key"
   
   # Or Linux/Mac:
   export SUPABASE_URL="https://xxxxx.supabase.co"
   export SUPABASE_KEY="your-anon-public-key"
   ```

3. Run the seed script:
   ```bash
   python seed_db.py
   ```

   You should see:
   ```
   🚀 SunsetAuto Database Seeding
   ✅ Added: Windy Hill
   ✅ Added: Mission Peak
   ✅ Added: Mount Tamalpais
   ✅ Added: Point Reyes Alamere Falls
   ✅ Added: Castle Rock State Park
   
   📊 Database contains 5 trails:
   ```

## Step 4: Verify in Supabase

1. Go to **Table Editor** in Supabase
2. Click **trails** table
3. You should see your 5 sample hikes with all their data

---

## Next: Phase 2

Once the database is seeded, you're ready for Phase 2: The Async API Engine.

The engine will:
- ✅ Fetch sunset time from Sunrise-Sunset API
- ✅ Fetch cloud cover from NWS Weather API (async, with caching)
- ✅ Return data as a unified dictionary

**You'll need:**
- A location (latitude/longitude) — we'll use the trails from the database
- A date (YYYY-MM-DD format)

No API keys needed for Phase 2!
