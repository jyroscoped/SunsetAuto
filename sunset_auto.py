"""
SunsetAuto -- Sunrise & Sunset Quality Checker
Uses the SunsetHue API to fetch sunrise/sunset quality forecasts.
Accepts an AllTrails link (auto-detects city) or a city name.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
import json
import webbrowser
from datetime import datetime
from collections import OrderedDict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # fallback below

import time as _time


# ---- Forecast Cache ----
#
# The SunsetHue API returns the same forecast for every coordinate inside the
# same 0.5° × 0.5° grid cell (see the "grid_location" field in the response).
# Forecasts are updated only 4 times per day (~every 6 hours), so we can
# safely cache a response and reuse it for any other location that falls in
# the same grid cell.
#
# This dramatically reduces API credit usage when scanning many nearby hiking
# spots (e.g. 28 Bay Area hikes might only need ~10 actual API calls).

class ForecastCache:
    """In-memory cache keyed by the API's grid_location identifier."""

    # Cache entries expire after 3 hours (forecasts update ~every 6h,
    # so 3h is a safe middle ground).
    TTL_SECONDS = 3 * 60 * 60

    def __init__(self):
        self._store = {}   # {grid_key: (timestamp, response_dict)}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _grid_key_for(lat, lng):
        """Pre-compute which 0.5° grid cell a coordinate falls into.

        This mirrors the SunsetHue model grid (resolution 0.5°).  Two
        locations in the same cell will receive identical forecasts.
        """
        import math
        grid_lat = round(math.floor(lat / 0.5) * 0.5, 1)
        grid_lng = round(math.floor(lng / 0.5) * 0.5, 1)
        return (grid_lat, grid_lng)

    def get(self, lat, lng):
        """Return a cached response dict, or None if not cached / expired."""
        key = self._grid_key_for(lat, lng)
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        ts, data = entry
        if _time.time() - ts > self.TTL_SECONDS:
            del self._store[key]
            self.misses += 1
            return None
        self.hits += 1
        return data

    def put(self, response_dict):
        """Store a response, keyed by the grid_location from the API."""
        # Prefer the API's own grid_location field
        grid = response_dict.get("grid_location")
        if grid:
            key = (grid.get("latitude"), grid.get("longitude"))
        else:
            # Fallback: compute from the request location
            loc = response_dict.get("location", {})
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            if lat is None or lng is None:
                return  # can't cache without coords
            key = self._grid_key_for(lat, lng)
        self._store[key] = (_time.time(), response_dict)

    def reset_stats(self):
        self.hits = 0
        self.misses = 0

    def clear(self):
        self._store.clear()
        self.reset_stats()


# Global cache instance
_forecast_cache = ForecastCache()


# ---- Configuration ----
SUNSETHUE_BASE = "https://api.sunsethue.com"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SunsetAuto/1.0 (sunset-auto-checker)"

# Colors mapped to the API's quality_text categories
QUALITY_COLORS = {
    "Poor":      "#7f8c8d",   # grey
    "Fair":      "#e67e22",   # orange
    "Good":      "#f1c40f",   # yellow
    "Great":     "#2ecc71",   # green
    "Excellent": "#a855f7",   # vivid purple – best of the best
}


# Hikeable nature spots within ~2.5 hr driving range of Menlo Park, CA.
# Each: (name, lat, lng, drive_minutes, description)
HIKING_SPOTS = [
    ("Marin Headlands",           37.8270, -122.4990, 50,  "Coastal bluffs with epic Pacific sunset views"),
    ("Mt. Tamalpais",              37.9235, -122.5965, 55,  "2,571 ft peak above the fog, panoramic sunsets"),
    ("Point Reyes",                38.0682, -122.8783, 80,  "Dramatic coastal cliffs & lighthouse"),
    ("Muir Beach Overlook",        37.8602, -122.5722, 45,  "Classic coastal overlook facing due west"),
    ("Lands End, SF",              37.7878, -122.5046, 40,  "Urban trail with Golden Gate sunset views"),
    ("Twin Peaks, SF",             37.7544, -122.4477, 35,  "360-degree city & ocean panorama"),
    ("Pacifica (Mori Point)",      37.6180, -122.4930, 25,  "Coastal headland, whale-watching & sunsets"),
    ("Montara Mountain",           37.5685, -122.5035, 30,  "McNee Ranch summit, sweeping ocean views"),
    ("Half Moon Bay",              37.4636, -122.4286, 25,  "Coastal bluff trails above the beach"),
    ("Windy Hill",                 37.3715, -122.2250, 15,  "Midpeninsula ridge with bay & ocean views"),
    ("Russian Ridge",              37.3230, -122.2050, 20,  "Rolling grasslands on Skyline ridge"),
    ("Skyline Ridge",              37.3110, -122.1830, 25,  "Alpine-feel ridge above Silicon Valley"),
    ("Black Mountain",             37.3210, -122.1530, 20,  "Rancho San Antonio to summit panorama"),
    ("Castle Rock State Park",     37.2310, -122.0945, 45,  "Sandstone formations in redwood forest"),
    ("Big Basin Redwoods",         37.1720, -122.2190, 55,  "Old-growth redwoods near coast"),
    ("Santa Cruz (West Cliff)",    36.9505, -122.0580, 60,  "Oceanfront path with wide sunset horizon"),
    ("Ano Nuevo State Park",       37.1085, -122.3378, 45,  "Wild coastal bluffs, elephant seal habitat"),
    ("Pinnacles National Park",    36.4906, -121.1825, 110, "Volcanic spires, condors, dark sky sunsets"),
    ("Point Lobos",                36.5152, -121.9420, 100, "Crown jewel of CA coast, cypress & coves"),
    ("Garrapata State Park",       36.4638, -121.9142, 105, "Big Sur northern gateway, dramatic cliffs"),
    ("Mt. Diablo",                 37.8816, -121.9142, 55,  "East Bay summit with 360-degree views"),
    ("Sunol Regional Wilderness",  37.5130, -121.8310, 35,  "Little Yosemite gorge, rolling hills"),
    ("Mission Peak",               37.5126, -121.8806, 35,  "Iconic Bay Area summit hike"),
    ("Mt. Hamilton / Lick Obs.",   37.3414, -121.6426, 60,  "High-altitude views above South Bay"),
    ("Henry Coe State Park",       37.1850, -121.4470, 70,  "Rugged backcountry, sweeping valleys"),
    ("Bodega Head",                38.2990, -123.0650, 110, "Dramatic Sonoma Coast headland"),
    ("Stinson Beach / Steep Ravine", 37.8988, -122.6370, 65, "Beach & coastal canyon trails"),
    ("Fremont Peak",               36.7570, -121.5000, 90,  "3,169 ft summit with Monterey Bay views"),
]


# ---- Helpers ----

def quality_color(quality_text):
    """Return a hex color for a quality_text string from the API."""
    return QUALITY_COLORS.get(quality_text, "#a6adc8")


def degrees_to_compass(deg):
    """Convert a direction in degrees to a compass abbreviation."""
    if deg is None:
        return ""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(deg / 22.5) % 16
    return dirs[idx]


def format_quality(quality, quality_text):
    """Format quality value (0-1 float) as a readable percentage string."""
    if quality is None:
        return "N/A"
    pct = quality * 100
    return f"{pct:.0f}%  ({quality_text})"


def lng_to_utc_offset(lng):
    """Estimate the UTC offset (in hours) from a longitude.

    Each 15 degrees of longitude ≈ 1 hour.  This is approximate (it does
    not account for political timezone boundaries) but is accurate enough
    for sunrise/sunset display where being off by ±30 min is acceptable.
    """
    return round(lng / 15)


def _parse_iso(iso_str):
    """Parse an ISO-8601 string into a timezone-aware datetime (UTC)."""
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def format_utc_time(iso_str, utc_offset_hours=None):
    """Convert an ISO-8601 UTC string to a friendly LOCAL time string.

    If *utc_offset_hours* is provided the time is shifted to that offset
    before formatting.  Otherwise the raw timestamp is formatted as-is.
    """
    dt = _parse_iso(iso_str)
    if dt is None:
        return iso_str if iso_str else None
    try:
        if utc_offset_hours is not None:
            from datetime import timedelta, timezone as tz
            local_tz = tz(timedelta(hours=utc_offset_hours))
            dt = dt.astimezone(local_tz)
        return dt.strftime("%I:%M %p  (%b %d)")
    except Exception:
        return iso_str


def geocode_city(city):
    """Convert a city name to lat/lng via Nominatim (OpenStreetMap)."""
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    return {
        "lat": float(data[0]["lat"]),
        "lng": float(data[0]["lon"]),
        "display": data[0].get("display_name", city),
    }


def extract_alltrails_location(url):
    """
    Scrape an AllTrails trail page and extract the trail's exact coordinates
    and display name.

    Uses a Googlebot User-Agent because AllTrails serves full server-rendered
    HTML to search-engine crawlers (including geo meta tags and JSON-LD),
    while blocking or serving a JS-only shell to regular browser UAs.

    Returns a dict  {"lat": float, "lng": float, "display": str}  or None.
    """
    lat, lng, display = None, None, None

    # --- Scrape the trail page ---
    try:
        headers = {
            # AllTrails serves full HTML (with meta geo tags) to Googlebot
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "text/html",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy 1 (best): <meta name="place:location:latitude"> / longitude
        meta_lat = soup.find("meta", attrs={"name": "place:location:latitude"})
        meta_lng = soup.find("meta", attrs={"name": "place:location:longitude"})
        if meta_lat and meta_lng:
            try:
                lat = float(meta_lat["content"])
                lng = float(meta_lng["content"])
            except (ValueError, KeyError, TypeError):
                pass

        # Strategy 2: JSON-LD  geo.latitude / geo.longitude
        if lat is None:
            for script_tag in soup.find_all("script", type="application/ld+json"):
                if not script_tag.string:
                    continue
                try:
                    ld = json.loads(script_tag.string)
                    items = ld if isinstance(ld, list) else [ld]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        geo = item.get("geo", {})
                        if isinstance(geo, dict) and geo.get("latitude"):
                            lat = float(geo["latitude"])
                            lng = float(geo["longitude"])
                            break
                        # Also check contentLocation
                        cl = item.get("contentLocation", {})
                        if isinstance(cl, dict):
                            g = cl.get("geo", {})
                            if isinstance(g, dict) and g.get("latitude"):
                                lat = float(g["latitude"])
                                lng = float(g["longitude"])
                                break
                except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                    continue
                if lat is not None:
                    break

        # Extract a display name from JSON-LD or <h1>
        for script_tag in soup.find_all("script", type="application/ld+json"):
            if not script_tag.string:
                continue
            try:
                ld = json.loads(script_tag.string)
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    if isinstance(item, dict):
                        name = item.get("name")
                        addr = item.get("address", {})
                        locality = ""
                        if isinstance(addr, dict):
                            locality = addr.get("addressLocality", "")
                        if name:
                            display = name + (" \u2014 " + locality if locality else "")
                            break
            except (json.JSONDecodeError, ValueError):
                continue
            if display:
                break

        if not display:
            h1 = soup.find("h1")
            if h1:
                display = h1.get_text(strip=True)

    except Exception:
        pass

    # Strategy 3 (fallback): parse the URL slug and geocode it directly
    # as a trail name + state, which Nominatim often knows.
    if lat is None:
        path = urlparse(url).path.strip("/")
        parts = path.split("/")
        # typical:  trail / us / colorado / royal-arch-trail
        if len(parts) >= 4 and parts[0] == "trail":
            trail_name = parts[-1].replace("-", " ")
            state_slug = parts[2]
            state = state_slug.upper() if len(state_slug) <= 3 else state_slug.replace("-", " ").title()
            query = f"{trail_name}, {state}"
            geo = geocode_city(query)
            if geo:
                lat, lng = geo["lat"], geo["lng"]
                display = display or geo["display"]

    if lat is None or lng is None:
        return None

    if not display:
        # Last-resort display name from URL slug
        path = urlparse(url).path.strip("/")
        parts = path.split("/")
        if parts:
            display = parts[-1].replace("-", " ").title()

    return {"lat": lat, "lng": lng, "display": display}


def fetch_sunsethue_forecast(lat, lng, api_key, use_cache=True):
    """
    Call the SunsetHue API, with grid-based caching.

    Endpoint:  GET https://api.sunsethue.com/forecast
    Params:    latitude, longitude
    Auth:      x-api-key header  OR  key= query param

    Caching:
      The API returns a ``grid_location`` field that identifies which 0.5°
      grid cell the forecast belongs to.  All coordinates inside the same
      cell receive the same forecast, and forecasts only update 4×/day.
      We cache by grid cell to avoid redundant calls.

    Returns (response_dict, from_cache_bool).
    """
    # Check cache first
    if use_cache:
        cached = _forecast_cache.get(lat, lng)
        if cached is not None:
            return cached, True

    url = f"{SUNSETHUE_BASE}/forecast"
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lng, 4),
    }
    headers = {"x-api-key": api_key, "User-Agent": USER_AGENT}
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # Store in cache
    _forecast_cache.put(data)

    return data, False


# ---- GUI ----

class SunsetAutoApp(tk.Tk):
    """Main application window."""

    BG       = "#1e1e2e"
    FG       = "#cdd6f4"
    ACCENT   = "#f38ba8"
    ACCENT2  = "#fab387"
    CARD_BG  = "#313244"
    BTN_BG   = "#cba6f7"
    BTN_FG   = "#1e1e2e"

    def __init__(self):
        super().__init__()
        self.title("SunsetAuto  -  Sunrise & Sunset Quality Checker")
        self.geometry("720x820")
        self.configure(bg=self.BG)
        self.resizable(False, False)
        self._build_ui()

    # -- UI construction --

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=self.BG)
        header.pack(fill="x", pady=(18, 6))
        tk.Label(
            header, text="SunsetAuto", font=("Segoe UI", 22, "bold"),
            bg=self.BG, fg=self.ACCENT,
        ).pack()
        tk.Label(
            header, text="Check sunrise & sunset quality for any trail or city",
            font=("Segoe UI", 10), bg=self.BG, fg=self.FG,
        ).pack()

        # API key input
        key_frame = tk.Frame(self, bg=self.BG)
        key_frame.pack(fill="x", padx=40, pady=(14, 4))
        tk.Label(
            key_frame, text="SunsetHue API Key:", font=("Segoe UI", 10),
            bg=self.BG, fg=self.FG,
        ).pack(anchor="w")
        self.api_key_var = tk.StringVar()
        tk.Entry(
            key_frame, textvariable=self.api_key_var, show="*",
            font=("Consolas", 11), bg=self.CARD_BG, fg=self.FG,
            insertbackground=self.FG, relief="flat", bd=0,
        ).pack(fill="x", ipady=6, pady=(2, 0))
        link_lbl = tk.Label(
            key_frame,
            text="Free key -> sunsethue.com/dev-api/portal",
            font=("Segoe UI", 8), bg=self.BG, fg="#6c7086", cursor="hand2",
        )
        link_lbl.pack(anchor="w", pady=(2, 0))
        link_lbl.bind(
            "<Button-1>",
            lambda _: webbrowser.open("https://sunsethue.com/dev-api/portal"),
        )

        # Input
        input_frame = tk.Frame(self, bg=self.BG)
        input_frame.pack(fill="x", padx=40, pady=(14, 4))
        tk.Label(
            input_frame,
            text="AllTrails link  OR  City name:",
            font=("Segoe UI", 10), bg=self.BG, fg=self.FG,
        ).pack(anchor="w")
        self.input_var = tk.StringVar()
        entry = tk.Entry(
            input_frame, textvariable=self.input_var,
            font=("Segoe UI", 12), bg=self.CARD_BG, fg=self.FG,
            insertbackground=self.FG, relief="flat", bd=0,
        )
        entry.pack(fill="x", ipady=8, pady=(2, 0))
        entry.bind("<Return>", lambda _: self._on_check())

        # Buttons
        btn_frame = tk.Frame(self, bg=self.BG)
        btn_frame.pack(pady=14)
        self.check_btn = tk.Button(
            btn_frame, text="Check Sunset & Sunrise Quality",
            font=("Segoe UI", 12, "bold"), bg=self.BTN_BG, fg=self.BTN_FG,
            activebackground=self.ACCENT, activeforeground="#fff",
            relief="flat", cursor="hand2", padx=20, pady=8,
            command=self._on_check,
        )
        self.check_btn.pack(side="left", padx=(0, 8))

        self.scan_btn = tk.Button(
            btn_frame, text="Scan Best Nearby Hikes",
            font=("Segoe UI", 11, "bold"), bg="#a6e3a1", fg=self.BTN_FG,
            activebackground="#2ecc71", activeforeground="#fff",
            relief="flat", cursor="hand2", padx=16, pady=8,
            command=self._on_scan,
        )
        self.scan_btn.pack(side="left")

        # Status label
        self.status_var = tk.StringVar(value="")
        tk.Label(
            self, textvariable=self.status_var, font=("Segoe UI", 10),
            bg=self.BG, fg="#a6adc8", wraplength=640,
        ).pack()

        # Scrollable results area
        container = tk.Frame(self, bg=self.BG)
        container.pack(fill="both", expand=True, padx=30, pady=(6, 0))

        canvas = tk.Canvas(container, bg=self.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)

        self.results_inner = tk.Frame(canvas, bg=self.BG)
        self.results_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._canvas_window = canvas.create_window(
            (0, 0), window=self.results_inner, anchor="nw", width=640,
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse-wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Footer
        footer = tk.Frame(self, bg=self.BG)
        footer.pack(fill="x", side="bottom", pady=(4, 8))
        tk.Label(
            footer,
            text="Powered by SunsetHue  |  Geocoding by OpenStreetMap/Nominatim",
            font=("Segoe UI", 8), bg=self.BG, fg="#585b70",
        ).pack()

    # -- Logic --

    # -- Nearby scan --

    def _on_scan(self):
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning(
                "API Key Required",
                "Please enter your SunsetHue API key.\n\n"
                "Get a free key at:\nhttps://sunsethue.com/dev-api/portal",
            )
            return
        self.check_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        self._clear_results()
        self.status_var.set("Scanning " + str(len(HIKING_SPOTS)) + " hiking spots near Menlo Park...")
        threading.Thread(
            target=self._scan_worker, args=(api_key,), daemon=True
        ).start()

    def _scan_worker(self, api_key):
        results = []
        total = len(HIKING_SPOTS)
        _forecast_cache.reset_stats()
        api_calls = 0

        for idx, (name, lat, lng, drive_min, desc) in enumerate(HIKING_SPOTS):
            self._set_status(
                "Scanning " + str(idx + 1) + "/" + str(total) + ": " + name + "..."
            )
            try:
                data, from_cache = fetch_sunsethue_forecast(lat, lng, api_key)
                if not from_cache:
                    api_calls += 1
                    # Small delay only for actual API calls
                    _time.sleep(0.15)

                items = data.get("data", [])
                # Find the best single event (sunrise or sunset) across all days
                best_q = -1
                best_entry = None
                for item in items:
                    if not item.get("model_data"):
                        continue
                    q = item.get("quality", 0) or 0
                    if q > best_q:
                        best_q = q
                        best_entry = item
                if best_entry:
                    results.append({
                        "name": name,
                        "desc": desc,
                        "drive": drive_min,
                        "lat": lat,
                        "lng": lng,
                        "best_type": best_entry.get("type", "?"),
                        "best_quality": best_entry.get("quality", 0),
                        "best_qt": best_entry.get("quality_text", ""),
                        "best_time": best_entry.get("time"),
                        "cloud": best_entry.get("cloud_cover"),
                        "magics": best_entry.get("magics", {}),
                        "direction": best_entry.get("direction"),
                        "data": data,
                    })
            except Exception:
                # Skip spots that error out, keep scanning
                continue

        cache_hits = _forecast_cache.hits
        # Sort by best quality descending
        results.sort(key=lambda r: r["best_quality"], reverse=True)
        self.after(0, lambda: self._render_scan_results(
            results, api_calls=api_calls, cache_hits=cache_hits,
        ))
        self.after(0, lambda: self.check_btn.configure(state="normal"))
        self.after(0, lambda: self.scan_btn.configure(state="normal"))

    def _render_scan_results(self, results, api_calls=0, cache_hits=0):
        self._clear_results()
        parent = self.results_inner

        tk.Label(
            parent,
            text="Best Sunrise / Sunset Hikes Near Menlo Park",
            font=("Segoe UI", 14, "bold"), bg=self.BG, fg="#a6e3a1",
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            parent,
            text="Ranked by best upcoming quality across all forecasted days",
            font=("Segoe UI", 9), bg=self.BG, fg="#6c7086",
        ).pack(anchor="w", pady=(0, 2))
        # Cache stats line
        if cache_hits > 0:
            tk.Label(
                parent,
                text="API calls: " + str(api_calls)
                + "   |   Cache hits: " + str(cache_hits)
                + " (same 0.5\u00b0 grid cell)",
                font=("Segoe UI", 8), bg=self.BG, fg="#585b70",
            ).pack(anchor="w", pady=(0, 8))
        else:
            tk.Label(
                parent,
                text="API calls: " + str(api_calls),
                font=("Segoe UI", 8), bg=self.BG, fg="#585b70",
            ).pack(anchor="w", pady=(0, 8))

        if not results:
            tk.Label(
                parent, text="No forecast data returned for any spot.",
                font=("Segoe UI", 11), bg=self.BG, fg=self.FG,
            ).pack(pady=20)
            self.status_var.set("Scan complete - no data.")
            return

        for rank, r in enumerate(results, 1):
            card = tk.Frame(parent, bg=self.CARD_BG, padx=14, pady=10)
            card.pack(fill="x", pady=4)

            # Rank + name row
            top_row = tk.Frame(card, bg=self.CARD_BG)
            top_row.pack(fill="x")

            rank_color = "#a6e3a1" if rank <= 3 else self.FG
            tk.Label(
                top_row,
                text="#" + str(rank),
                font=("Segoe UI", 14, "bold"), bg=self.CARD_BG, fg=rank_color,
            ).pack(side="left", padx=(0, 8))

            tk.Label(
                top_row,
                text=r["name"],
                font=("Segoe UI", 12, "bold"), bg=self.CARD_BG, fg=self.FG,
            ).pack(side="left")

            # Quality badge on the right
            q_pct = r["best_quality"] * 100
            qt = r["best_qt"]
            col = quality_color(qt)
            event_label = "Sunrise" if r["best_type"] == "sunrise" else "Sunset"
            tk.Label(
                top_row,
                text=str(round(q_pct)) + "%  " + qt + "  (" + event_label + ")",
                font=("Segoe UI", 12, "bold"), bg=self.CARD_BG, fg=col,
            ).pack(side="right")

            # Details row
            detail_row = tk.Frame(card, bg=self.CARD_BG)
            detail_row.pack(fill="x", pady=(4, 0))

            tk.Label(
                detail_row,
                text=r["desc"],
                font=("Segoe UI", 9), bg=self.CARD_BG, fg="#a6adc8",
            ).pack(side="left")

            # Meta row
            meta_row = tk.Frame(card, bg=self.CARD_BG)
            meta_row.pack(fill="x", pady=(3, 0))

            meta_parts = []
            meta_parts.append("Drive: ~" + str(r["drive"]) + " min")
            spot_off = lng_to_utc_offset(r["lng"])
            t = format_utc_time(r.get("best_time"), spot_off)
            if t:
                meta_parts.append("When: " + t)
            cc = r.get("cloud")
            if cc is not None:
                meta_parts.append("Clouds: " + str(round(cc * 100)) + "%")
            d = r.get("direction")
            if d is not None:
                compass = degrees_to_compass(d)
                meta_parts.append("Dir: " + compass + " (" + str(round(d)) + "\u00b0)")

            tk.Label(
                meta_row,
                text="   |   ".join(meta_parts),
                font=("Segoe UI", 8), bg=self.CARD_BG, fg="#6c7086",
            ).pack(anchor="w")

            # Golden hour if available
            magics = r.get("magics", {})
            gh = magics.get("golden_hour", [None, None])
            if gh and gh[0]:
                gs = format_utc_time(gh[0], spot_off)
                ge = format_utc_time(gh[1], spot_off)
                if gs and ge:
                    tk.Label(
                        meta_row,
                        text="Golden hr: " + gs + " - " + ge,
                        font=("Segoe UI", 8), bg=self.CARD_BG, fg="#f1c40f",
                    ).pack(anchor="w")

        cache_msg = ""
        if cache_hits > 0:
            cache_msg = (" (" + str(api_calls) + " API calls, "
                         + str(cache_hits) + " cached)")
        self.status_var.set(
            "Scan complete! " + str(len(results)) + " spots ranked."
            + cache_msg
        )

    # -- Single-location check --

    def _on_check(self):
        raw = self.input_var.get().strip()
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning(
                "API Key Required",
                "Please enter your SunsetHue API key.\n\n"
                "Get a free key at:\nhttps://sunsethue.com/dev-api/portal",
            )
            return
        if not raw:
            messagebox.showwarning(
                "Input Required", "Enter an AllTrails link or a city name."
            )
            return

        self.check_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        self._clear_results()
        self.status_var.set("Working...")

        threading.Thread(
            target=self._worker, args=(raw, api_key), daemon=True
        ).start()

    def _worker(self, raw, api_key):
        try:
            is_url = raw.startswith("http://") or raw.startswith("https://")

            if is_url:
                self._set_status("Extracting trail location from AllTrails...")
                loc = extract_alltrails_location(raw)
                if not loc:
                    self._show_error(
                        "Could not extract coordinates from the AllTrails link.\n"
                        "Try entering the trail or city name instead."
                    )
                    return
                lat, lng = loc["lat"], loc["lng"]
                display = loc["display"]
                self._set_status(
                    "Trail found: " + display
                    + "  (" + str(round(lat, 5)) + ", " + str(round(lng, 5)) + ")"
                )
            else:
                # Plain city / trail name — geocode it
                self._set_status("Geocoding '" + raw + "'...")
                geo = geocode_city(raw)
                if not geo:
                    self._show_error(
                        "Could not find coordinates for '" + raw + "'.\n"
                        "Try a different spelling or a nearby major city."
                    )
                    return
                lat, lng = geo["lat"], geo["lng"]
                display = geo["display"]

            self._set_status(
                "Fetching forecast for " + display
                + "  (" + str(round(lat, 2)) + ", " + str(round(lng, 2)) + ")..."
            )

            # Fetch SunsetHue forecast
            data, _from_cache = fetch_sunsethue_forecast(lat, lng, api_key)

            # Check if location was actually resolved by the API
            loc = data.get("location", {})
            if loc.get("latitude") is None:
                self._show_error(
                    "SunsetHue could not resolve that location.\n"
                    "The API returned null coordinates. Try a different city."
                )
                return

            self.after(
                0,
                lambda: self._render_results(
                    data, display, lat, lng, is_url
                ),
            )

        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            try:
                body = exc.response.json()
                msg = body.get("message", str(exc))
            except Exception:
                msg = str(exc)
            self._show_error("API error (" + str(code) + "): " + msg)
        except requests.ConnectionError:
            self._show_error("Network error - check your internet connection.")
        except Exception as exc:
            self._show_error("Unexpected error: " + str(exc))
        finally:
            self.after(0, lambda: self.check_btn.configure(state="normal"))
            self.after(0, lambda: self.scan_btn.configure(state="normal"))

    # -- Result rendering --

    def _render_results(self, data, location, lat, lng, is_trail=False):
        self._clear_results()
        parent = self.results_inner
        utc_off = lng_to_utc_offset(lng)

        # Timezone label
        if utc_off >= 0:
            tz_label = "UTC+" + str(utc_off)
        else:
            tz_label = "UTC" + str(utc_off)

        # Location header
        loc_text = location
        tk.Label(
            parent, text=loc_text,
            font=("Segoe UI", 11, "bold"), bg=self.BG, fg=self.ACCENT2,
            wraplength=620, justify="left",
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            parent,
            text="Coordinates: " + str(round(lat, 4)) + ", " + str(round(lng, 4))
            + "   (" + tz_label + ")",
            font=("Segoe UI", 9), bg=self.BG, fg="#6c7086",
        ).pack(anchor="w", pady=(0, 8))

        # Parse the SunsetHue API response
        items = data.get("data", [])
        if not items:
            tk.Label(
                parent, text="No forecast data available for this location.",
                font=("Segoe UI", 11), bg=self.BG, fg=self.FG,
            ).pack(pady=20)
            self.status_var.set("No forecast data returned.")
            return

        # Group consecutive sunrise+sunset pairs by day
        day_pairs = self._pair_by_day(items, utc_off)

        if not day_pairs:
            tk.Label(
                parent, text="No model data available for this location yet.",
                font=("Segoe UI", 11), bg=self.BG, fg=self.FG,
            ).pack(pady=20)
            self.status_var.set("No model data returned.")
            return

        for day_label, sunrise, sunset in day_pairs:
            self._render_day_card(parent, day_label, sunrise, sunset, utc_off)

        self.status_var.set("Forecast loaded successfully!")

    @staticmethod
    def _pair_by_day(items, utc_off=0):
        """
        Group the flat API list into (day_label, sunrise_dict, sunset_dict).
        The API returns alternating sunrise/sunset entries chronologically.
        Times are converted to LOCAL time before grouping so that an evening
        sunset doesn't land on the next day.
        """
        from datetime import timedelta, timezone as tz
        local_tz = tz(timedelta(hours=utc_off))
        days = OrderedDict()

        for item in items:
            if not item.get("model_data"):
                continue  # skip entries with no actual forecast
            time_str = item.get("time")
            if time_str:
                dt = _parse_iso(time_str)
                if dt:
                    dt_local = dt.astimezone(local_tz)
                    day_key = dt_local.strftime("%A, %b %d %Y")
                else:
                    day_key = "Unknown"
            else:
                day_key = "Unknown"

            if day_key not in days:
                days[day_key] = {"sunrise": None, "sunset": None}

            entry_type = item.get("type", "").lower()
            if entry_type == "sunrise":
                days[day_key]["sunrise"] = item
            elif entry_type == "sunset":
                days[day_key]["sunset"] = item

        return [
            (day, pair["sunrise"], pair["sunset"])
            for day, pair in days.items()
        ]

    def _render_day_card(self, parent, day_label, sunrise, sunset, utc_off=0):
        card = tk.Frame(parent, bg=self.CARD_BG, padx=16, pady=12)
        card.pack(fill="x", pady=5)

        # Day header
        tk.Label(
            card, text=day_label,
            font=("Segoe UI", 11, "bold"), bg=self.CARD_BG, fg=self.FG,
        ).pack(anchor="w")

        row = tk.Frame(card, bg=self.CARD_BG)
        row.pack(fill="x", pady=(6, 0))

        # -- Sunrise column --
        sr_frame = tk.Frame(row, bg=self.CARD_BG)
        sr_frame.pack(side="left", expand=True, fill="both")
        tk.Label(
            sr_frame, text="Sunrise", font=("Segoe UI", 10, "bold"),
            bg=self.CARD_BG, fg="#fab387",
        ).pack(anchor="w")
        self._render_event(sr_frame, sunrise, utc_off)

        # -- Sunset column --
        ss_frame = tk.Frame(row, bg=self.CARD_BG)
        ss_frame.pack(side="right", expand=True, fill="both")
        tk.Label(
            ss_frame, text="Sunset", font=("Segoe UI", 10, "bold"),
            bg=self.CARD_BG, fg="#f38ba8",
        ).pack(anchor="w")
        self._render_event(ss_frame, sunset, utc_off)

    def _render_event(self, frame, event, utc_off=0):
        """Render a single sunrise or sunset entry inside a frame."""
        if not event or event.get("quality") is None:
            tk.Label(
                frame, text="N/A",
                font=("Segoe UI", 14), bg=self.CARD_BG, fg="#585b70",
            ).pack(anchor="w")
            return

        # Prefer quality_percent if available, else quality * 100
        q_raw = event.get("quality_percent")
        if q_raw is not None:
            q = q_raw / 100.0  # normalise to 0-1 for format_quality
        else:
            q = event["quality"]
        qt = event.get("quality_text", "")
        col = quality_color(qt)

        # Quality score
        tk.Label(
            frame, text=format_quality(q, qt),
            font=("Segoe UI", 16, "bold"), bg=self.CARD_BG, fg=col,
        ).pack(anchor="w")

        # Time (LOCAL)
        t = format_utc_time(event.get("time"), utc_off)
        if t:
            tk.Label(
                frame, text="Time: " + t,
                font=("Segoe UI", 9), bg=self.CARD_BG, fg="#a6adc8",
            ).pack(anchor="w")

        # Cloud cover (API returns 0.0-1.0)
        cc = event.get("cloud_cover")
        if cc is not None:
            tk.Label(
                frame,
                text="Cloud cover: " + str(round(cc * 100)) + "%",
                font=("Segoe UI", 9), bg=self.CARD_BG, fg="#a6adc8",
            ).pack(anchor="w")

        # Direction (degrees + compass)
        direction = event.get("direction")
        if direction is not None:
            compass = degrees_to_compass(direction)
            tk.Label(
                frame,
                text="Direction: " + compass + " (" + str(round(direction)) + "\u00b0)",
                font=("Segoe UI", 9), bg=self.CARD_BG, fg="#a6adc8",
            ).pack(anchor="w")

        # Golden hour (LOCAL)
        magics = event.get("magics", {})
        gh = magics.get("golden_hour", [None, None])
        if gh and gh[0]:
            start = format_utc_time(gh[0], utc_off)
            end = format_utc_time(gh[1], utc_off)
            if start and end:
                tk.Label(
                    frame, text="Golden hr: " + start + " - " + end,
                    font=("Segoe UI", 8), bg=self.CARD_BG, fg="#f1c40f",
                ).pack(anchor="w")

        # Blue hour (LOCAL)
        bh = magics.get("blue_hour", [None, None])
        if bh and bh[0]:
            start = format_utc_time(bh[0], utc_off)
            end = format_utc_time(bh[1], utc_off)
            if start and end:
                tk.Label(
                    frame, text="Blue hr: " + start + " - " + end,
                    font=("Segoe UI", 8), bg=self.CARD_BG, fg="#89b4fa",
                ).pack(anchor="w")

    # -- Utilities --

    def _clear_results(self):
        for w in self.results_inner.winfo_children():
            w.destroy()

    def _set_status(self, msg):
        self.after(0, lambda: self.status_var.set(msg))

    def _show_error(self, msg):
        self.after(0, lambda: self.status_var.set("Error: " + msg))
        self.after(0, lambda: self.check_btn.configure(state="normal"))


# ---- Entry Point ----

if __name__ == "__main__":
    app = SunsetAutoApp()
    app.mainloop()
