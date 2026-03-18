"""
seed_db.py - Initialize Supabase trails table with sample Bay Area hikes.

Usage:
  1. Set environment variables SUPABASE_URL and SUPABASE_KEY
  2. python seed_db.py

Alternatively, pass credentials as arguments:
  python seed_db.py <SUPABASE_URL> <SUPABASE_KEY>
"""

import os
import sys
from supabase import create_client

# Get credentials from env or command line
SUPABASE_URL = os.getenv("SUPABASE_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or (sys.argv[2] if len(sys.argv) > 2 else None)

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_KEY are required.")
    print("   Set them as environment variables or pass as command-line arguments:")
    print("   python seed_db.py <URL> <KEY>")
    sys.exit(1)

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sample Bay Area trails with real coordinates
SAMPLE_TRAILS = [
    {
        "name": "Windy Hill",
        "lat": 37.3715,
        "lon": -122.2250,
        "elevation_ft": 1900,
        "difficulty": "Easy",
        "length_miles": 3.2,
        "alltrails_url": "https://www.alltrails.com/trail/us/california/windy-hill",
    },
    {
        "name": "Mission Peak",
        "lat": 37.5126,
        "lon": -121.8806,
        "elevation_ft": 2517,
        "difficulty": "Hard",
        "length_miles": 6.5,
        "alltrails_url": "https://www.alltrails.com/trail/us/california/mission-peak-via-ohlone-regional-wilderness",
    },
    {
        "name": "Mount Tamalpais",
        "lat": 37.9235,
        "lon": -122.5965,
        "elevation_ft": 2571,
        "difficulty": "Moderate",
        "length_miles": 8.0,
        "alltrails_url": "https://www.alltrails.com/trail/us/california/mount-tamalpais-trail",
    },
    {
        "name": "Point Reyes Alamere Falls",
        "lat": 38.0682,
        "lon": -122.8783,
        "elevation_ft": 1050,
        "difficulty": "Moderate",
        "length_miles": 11.0,
        "alltrails_url": "https://www.alltrails.com/trail/us/california/alamere-falls",
    },
    {
        "name": "Castle Rock State Park",
        "lat": 37.2310,
        "lon": -122.0945,
        "elevation_ft": 3200,
        "difficulty": "Moderate",
        "length_miles": 4.8,
        "alltrails_url": "https://www.alltrails.com/trail/us/california/castle-rock-trail",
    },
]


def create_trails_table():
    """Create the trails table if it doesn't exist."""
    print("📋 Creating 'trails' table...")
    try:
        # Use raw SQL to create table
        query = """
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
        
        -- Create indexes for faster queries
        CREATE INDEX IF NOT EXISTS idx_trails_difficulty ON trails(difficulty);
        CREATE INDEX IF NOT EXISTS idx_trails_length ON trails(length_miles);
        """
        # Execute via Supabase admin API
        supabase.postgrest.raw(query)
        print("✅ Trails table created successfully!")
    except Exception as e:
        print(f"⚠️  Trails table may already exist: {e}")


def seed_trails():
    """Insert sample trails into the database."""
    print("\n🌄 Seeding sample trails...")
    
    for trail in SAMPLE_TRAILS:
        try:
            # Insert trail
            supabase.table("trails").insert(trail).execute()
            print(f"  ✅ Added: {trail['name']}")
        except Exception as e:
            print(f"  ⚠️  Error adding {trail['name']}: {e}")


def verify_data():
    """Verify the data was inserted correctly."""
    print("\n📊 Verifying data...")
    try:
        response = supabase.table("trails").select("*").execute()
        trails = response.data
        print(f"✅ Database contains {len(trails)} trails:")
        for trail in trails:
            print(f"   • {trail['name']} ({trail['difficulty']}, {trail['length_miles']} mi)")
    except Exception as e:
        print(f"❌ Error verifying data: {e}")


if __name__ == "__main__":
    print("🚀 SunsetAuto Database Seeding\n")
    
    # Note: create_trails_table() would require admin privileges
    # For now, we'll just seed the data assuming the table exists
    print("⚠️  Make sure the 'trails' table exists in Supabase first!")
    print("   Go to SQL Editor in Supabase and run:")
    print("""
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
    """)
    print()
    
    seed_trails()
    verify_data()
    print("\n✨ Database seeding complete!")
