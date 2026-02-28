"""
SunsetAuto  ·  Web Edition
Sunrise & Sunset Quality Checker powered by SunsetHue API.
Built with Streamlit — deploy free on Streamlit Community Cloud.
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import math
import time as _time
from datetime import datetime, timedelta, timezone
from collections import OrderedDict
from urllib.parse import urlparse


# ──────────────────────────── Page Config ─────────────────────────────
st.set_page_config(
    page_title="SunsetAuto — Sunset Quality Checker",
    page_icon="🌅",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ──────────────────────────── Custom CSS ──────────────────────────────
st.markdown("""
<style>
    /* tighten default padding */
    .block-container { padding-top: 2rem; }
    /* quality event card */
    .event-card {
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 6px 0 10px 0;
    }
    .event-card .q-score {
        font-size: 1.45em;
        font-weight: 700;
        line-height: 1.3;
    }
    .event-card .q-details {
        font-size: 0.88em;
        margin-top: 6px;
        line-height: 1.7;
        color: #a6adc8;
    }
    .event-card .q-magic {
        margin-top: 4px;
        font-size: 0.82em;
    }
    /* scan rank badge */
    .rank-num {
        font-size: 1.5em;
        font-weight: 800;
        line-height: 1.2;
    }
    /* progress bar for quality */
    .q-bar-bg {
        background: #45475a;
        border-radius: 4px;
        overflow: hidden;
        height: 7px;
        margin: 5px 0 2px 0;
    }
    .q-bar-fg {
        height: 100%;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────── Constants ───────────────────────────────
SUNSETHUE_BASE = "https://api.sunsethue.com"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SunsetAuto/2.0 (sunset-auto-web)"

QUALITY_COLORS = {
    "Poor":      "#7f8c8d",
    "Fair":      "#e67e22",
    "Good":      "#f1c40f",
    "Great":     "#2ecc71",
    "Excellent": "#a855f7",
}

HIKING_SPOTS = [
    ("Marin Headlands",             37.8270, -122.4990,  50, "Coastal bluffs with epic Pacific sunset views"),
    ("Mt. Tamalpais",               37.9235, -122.5965,  55, "2,571 ft peak above the fog, panoramic sunsets"),
    ("Point Reyes",                 38.0682, -122.8783,  80, "Dramatic coastal cliffs & lighthouse"),
    ("Muir Beach Overlook",         37.8602, -122.5722,  45, "Classic coastal overlook facing due west"),
    ("Lands End, SF",               37.7878, -122.5046,  40, "Urban trail with Golden Gate sunset views"),
    ("Twin Peaks, SF",              37.7544, -122.4477,  35, "360-degree city & ocean panorama"),
    ("Pacifica (Mori Point)",       37.6180, -122.4930,  25, "Coastal headland, whale-watching & sunsets"),
    ("Montara Mountain",            37.5685, -122.5035,  30, "McNee Ranch summit, sweeping ocean views"),
    ("Half Moon Bay",               37.4636, -122.4286,  25, "Coastal bluff trails above the beach"),
    ("Windy Hill",                  37.3715, -122.2250,  15, "Midpeninsula ridge with bay & ocean views"),
    ("Russian Ridge",               37.3230, -122.2050,  20, "Rolling grasslands on Skyline ridge"),
    ("Skyline Ridge",               37.3110, -122.1830,  25, "Alpine-feel ridge above Silicon Valley"),
    ("Black Mountain",              37.3210, -122.1530,  20, "Rancho San Antonio to summit panorama"),
    ("Castle Rock State Park",      37.2310, -122.0945,  45, "Sandstone formations in redwood forest"),
    ("Big Basin Redwoods",          37.1720, -122.2190,  55, "Old-growth redwoods near coast"),
    ("Santa Cruz (West Cliff)",     36.9505, -122.0580,  60, "Oceanfront path with wide sunset horizon"),
    ("Ano Nuevo State Park",        37.1085, -122.3378,  45, "Wild coastal bluffs, elephant seal habitat"),
    ("Pinnacles National Park",     36.4906, -121.1825, 110, "Volcanic spires, condors, dark sky sunsets"),
    ("Point Lobos",                 36.5152, -121.9420, 100, "Crown jewel of CA coast, cypress & coves"),
    ("Garrapata State Park",        36.4638, -121.9142, 105, "Big Sur northern gateway, dramatic cliffs"),
    ("Mt. Diablo",                  37.8816, -121.9142,  55, "East Bay summit with 360-degree views"),
    ("Sunol Regional Wilderness",   37.5130, -121.8310,  35, "Little Yosemite gorge, rolling hills"),
    ("Mission Peak",                37.5126, -121.8806,  35, "Iconic Bay Area summit hike"),
    ("Mt. Hamilton / Lick Obs.",    37.3414, -121.6426,  60, "High-altitude views above South Bay"),
    ("Henry Coe State Park",        37.1850, -121.4470,  70, "Rugged backcountry, sweeping valleys"),
    ("Bodega Head",                 38.2990, -123.0650, 110, "Dramatic Sonoma Coast headland"),
    ("Stinson Beach / Steep Ravine", 37.8988, -122.6370, 65, "Beach & coastal canyon trails"),
    ("Fremont Peak",                36.7570, -121.5000,  90, "3,169 ft summit with Monterey Bay views"),
]


# ──────────────────────────── Helpers ─────────────────────────────────

def quality_color(qt):
    return QUALITY_COLORS.get(qt, "#a6adc8")


def degrees_to_compass(deg):
    if deg is None:
        return ""
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(deg / 22.5) % 16]


def format_quality(q, qt):
    if q is None:
        return "N/A"
    return f"{q * 100:.0f}%  ({qt})"


def lng_to_utc_offset(lng):
    return round(lng / 15)


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def format_utc_time(iso_str, utc_off=None):
    dt = _parse_iso(iso_str)
    if dt is None:
        return iso_str if iso_str else None
    if utc_off is not None:
        dt = dt.astimezone(timezone(timedelta(hours=utc_off)))
    return dt.strftime("%I:%M %p  (%b %d)")


def _grid_snap(lat, lng):
    """Snap to the SunsetHue 0.5° grid cell."""
    return (round(math.floor(lat / 0.5) * 0.5, 1),
            round(math.floor(lng / 0.5) * 0.5, 1))


# ──────────────────── Cached API Functions ────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def geocode_city(city):
    """Nominatim geocoding. Cached 24 h."""
    params = {"q": city, "format": "json", "limit": 1}
    resp = requests.get(NOMINATIM_URL, params=params,
                        headers={"User-Agent": USER_AGENT}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    return {
        "lat": float(data[0]["lat"]),
        "lng": float(data[0]["lon"]),
        "display": data[0].get("display_name", city),
    }


@st.cache_data(ttl=86400, show_spinner=False)
def extract_alltrails_location(url):
    """
    Scrape an AllTrails trail page for exact coordinates & display name.
    Uses Googlebot UA (AllTrails serves full HTML to crawlers).
    Cached 24 h.
    """
    lat, lng, display = None, None, None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; "
                          "+http://www.google.com/bot.html)",
            "Accept": "text/html",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy 1: <meta name="place:location:latitude/longitude">
        ml = soup.find("meta", attrs={"name": "place:location:latitude"})
        mn = soup.find("meta", attrs={"name": "place:location:longitude"})
        if ml and mn:
            try:
                lat, lng = float(ml["content"]), float(mn["content"])
            except (ValueError, KeyError, TypeError):
                pass

        # Strategy 2: JSON-LD geo
        if lat is None:
            for tag in soup.find_all("script", type="application/ld+json"):
                if not tag.string:
                    continue
                try:
                    ld = json.loads(tag.string)
                    for item in (ld if isinstance(ld, list) else [ld]):
                        if not isinstance(item, dict):
                            continue
                        for geo_src in [item.get("geo", {}),
                                        (item.get("contentLocation", {}) or {}).get("geo", {})]:
                            if isinstance(geo_src, dict) and geo_src.get("latitude"):
                                lat = float(geo_src["latitude"])
                                lng = float(geo_src["longitude"])
                                break
                        if lat is not None:
                            break
                except Exception:
                    continue
                if lat is not None:
                    break

        # Extract display name from JSON-LD
        for tag in soup.find_all("script", type="application/ld+json"):
            if not tag.string:
                continue
            try:
                ld = json.loads(tag.string)
                for item in (ld if isinstance(ld, list) else [ld]):
                    if isinstance(item, dict) and item.get("name"):
                        name = item["name"]
                        addr = item.get("address", {})
                        loc_str = addr.get("addressLocality", "") if isinstance(addr, dict) else ""
                        display = name + (f" — {loc_str}" if loc_str else "")
                        break
            except Exception:
                continue
            if display:
                break

        if not display:
            h1 = soup.find("h1")
            if h1:
                display = h1.get_text(strip=True)

    except Exception:
        pass

    # Strategy 3 fallback: URL slug → Nominatim
    if lat is None:
        path = urlparse(url).path.strip("/")
        parts = path.split("/")
        if len(parts) >= 4 and parts[0] == "trail":
            trail_name = parts[-1].replace("-", " ")
            state_slug = parts[2]
            state = (state_slug.upper() if len(state_slug) <= 3
                     else state_slug.replace("-", " ").title())
            geo = geocode_city(f"{trail_name}, {state}")
            if geo:
                lat, lng = geo["lat"], geo["lng"]
                display = display or geo["display"]

    if lat is None or lng is None:
        return None

    if not display:
        parts = urlparse(url).path.strip("/").split("/")
        display = parts[-1].replace("-", " ").title() if parts else url

    return {"lat": lat, "lng": lng, "display": display}


@st.cache_data(ttl=10800, show_spinner=False)
def _fetch_forecast_cached(grid_lat, grid_lng, api_key):
    """Actual SunsetHue API call, cached 3 h by grid cell."""
    resp = requests.get(
        f"{SUNSETHUE_BASE}/forecast",
        params={"latitude": grid_lat, "longitude": grid_lng},
        headers={"x-api-key": api_key, "User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_forecast(lat, lng, api_key):
    """Public wrapper: snaps to 0.5° grid, then fetches (with cache)."""
    glat, glng = _grid_snap(lat, lng)
    return _fetch_forecast_cached(glat, glng, api_key)


# ──────────────────── Data Processing ─────────────────────────────────

def pair_by_day(items, utc_off=0):
    """Group API items into (day_label, sunrise, sunset) tuples."""
    local_tz = timezone(timedelta(hours=utc_off))
    days = OrderedDict()

    for item in items:
        if not item.get("model_data"):
            continue
        dt = _parse_iso(item.get("time"))
        if dt:
            day_key = dt.astimezone(local_tz).strftime("%A, %b %d %Y")
        else:
            day_key = "Unknown"
        if day_key not in days:
            days[day_key] = {"sunrise": None, "sunset": None}
        t = item.get("type", "").lower()
        if t in ("sunrise", "sunset"):
            days[day_key][t] = item

    return [(d, p["sunrise"], p["sunset"]) for d, p in days.items()]


# ──────────────────── HTML Rendering ──────────────────────────────────

def _event_html(event, utc_off, emoji="🌅"):
    """Generate styled HTML for a single sunrise/sunset event."""
    if not event or event.get("quality") is None:
        return f"""
        <div style="padding: 14px; color: #585b70; font-size: 1.2em;
                    text-align: center;">{emoji} N/A</div>
        """

    q_raw = event.get("quality_percent")
    q = q_raw / 100.0 if q_raw is not None else event["quality"]
    qt = event.get("quality_text", "")
    col = quality_color(qt)
    pct = round(q * 100)

    lines = []

    # Time
    t = format_utc_time(event.get("time"), utc_off)
    if t:
        lines.append(f"⏰ {t}")

    # Cloud cover
    cc = event.get("cloud_cover")
    if cc is not None:
        lines.append(f"☁️ {round(cc * 100)}% clouds")

    # Direction
    d = event.get("direction")
    if d is not None:
        lines.append(f"🧭 {degrees_to_compass(d)} ({round(d)}°)")

    details_html = "<br>".join(lines)

    # Magic hours
    magic_parts = []
    magics = event.get("magics", {})
    gh = magics.get("golden_hour", [None, None])
    if gh and gh[0]:
        gs, ge = format_utc_time(gh[0], utc_off), format_utc_time(gh[1], utc_off)
        if gs and ge:
            magic_parts.append(
                f'<span style="color:#f1c40f;">✨ Golden: {gs} — {ge}</span>')
    bh = magics.get("blue_hour", [None, None])
    if bh and bh[0]:
        bs, be = format_utc_time(bh[0], utc_off), format_utc_time(bh[1], utc_off)
        if bs and be:
            magic_parts.append(
                f'<span style="color:#89b4fa;">🌀 Blue: {bs} — {be}</span>')
    magic_html = "<br>".join(magic_parts)
    magic_section = f'<div class="q-magic">{magic_html}</div>' if magic_html else ""

    return f"""
    <div class="event-card" style="background:{col}12; border-left:4px solid {col};">
        <div class="q-score" style="color:{col};">{emoji} {pct}% {qt}</div>
        <div class="q-bar-bg"><div class="q-bar-fg" style="width:{pct}%; background:{col};"></div></div>
        <div class="q-details">{details_html}</div>
        {magic_section}
    </div>
    """


# ─────────────────────── Sidebar ──────────────────────────────────────

def setup_sidebar():
    """Build sidebar, return the active API key."""
    with st.sidebar:
        st.header("⚙️ Settings")

        # Try secrets first
        secret_key = None
        try:
            secret_key = st.secrets["SUNSETHUE_API_KEY"]
        except (KeyError, FileNotFoundError):
            pass

        if secret_key:
            st.success("🔑 API key loaded from app secrets")
            override = st.text_input(
                "Override with your own key (optional)",
                type="password", key="key_override",
            )
            api_key = override.strip() if override.strip() else secret_key
        else:
            api_key = st.text_input(
                "SunsetHue API Key", type="password", key="key_input",
            ).strip()

        st.caption("[Get a free API key →](https://sunsethue.com/dev-api/portal)")

        st.divider()
        st.markdown(
            "**SunsetAuto** v2.0  \n"
            "Powered by [SunsetHue](https://sunsethue.com)  \n"
            "Geocoding by [OpenStreetMap](https://www.openstreetmap.org)"
        )

    return api_key


# ─────────────────────── Main App ─────────────────────────────────────

def main():
    api_key = setup_sidebar()

    # ── Header ──
    st.markdown(
        "<h1 style='text-align:center; margin-bottom:0;'>🌅 SunsetAuto</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#a6adc8; margin-top:-4px;'>"
        "Check sunrise &amp; sunset quality for any trail or city</p>",
        unsafe_allow_html=True,
    )

    # ── Tabs ──
    tab_check, tab_scan = st.tabs(["🔍  Check Location", "🏔️  Scan Nearby Hikes"])

    # ────────────── TAB 1 : Check a single location ──────────────
    with tab_check:
        location = st.text_input(
            "AllTrails link  **or**  city / trail name",
            placeholder="e.g. https://www.alltrails.com/trail/us/california/... or San Francisco",
            key="location_input",
        )

        if st.button("🌅  Check Sunset & Sunrise Quality",
                      type="primary", use_container_width=True, key="check_btn"):
            if not api_key:
                st.error("Enter your SunsetHue API key in the sidebar.")
            elif not location.strip():
                st.warning("Please enter an AllTrails link or a city name.")
            else:
                _run_check(location.strip(), api_key)

        # Persist results across reruns
        if st.session_state.get("check_payload"):
            _display_check_results(**st.session_state.check_payload)

    # ────────────── TAB 2 : Scan nearby hikes ─────────────────────
    with tab_scan:
        st.markdown(
            f"**{len(HIKING_SPOTS)} curated hiking spots** within ~2.5 hrs of "
            "Menlo Park, CA — ranked by best upcoming sunset / sunrise quality."
        )
        if st.button("🏔️  Scan All Spots",
                      type="primary", use_container_width=True, key="scan_btn"):
            if not api_key:
                st.error("Enter your SunsetHue API key in the sidebar.")
            else:
                _run_scan(api_key)

        if st.session_state.get("scan_payload"):
            _display_scan_results(**st.session_state.scan_payload)


# ──────────── Check-location logic ────────────────────────────────────

def _run_check(raw, api_key):
    is_url = raw.startswith("http://") or raw.startswith("https://")

    with st.status("Processing…", expanded=True) as status:
        try:
            if is_url:
                status.update(label="🔗 Extracting trail location from AllTrails…")
                loc = extract_alltrails_location(raw)
                if not loc:
                    st.error("Could not extract coordinates from that AllTrails link. "
                             "Try entering the trail or city name instead.")
                    return
                lat, lng, display = loc["lat"], loc["lng"], loc["display"]
            else:
                status.update(label=f"📍 Geocoding '{raw}'…")
                geo = geocode_city(raw)
                if not geo:
                    st.error(f"Could not find coordinates for '{raw}'. "
                             "Try a different spelling or a nearby city.")
                    return
                lat, lng, display = geo["lat"], geo["lng"], geo["display"]

            status.update(label=f"🌤️ Fetching forecast for {display}…")
            data = fetch_forecast(lat, lng, api_key)

            apiloc = data.get("location", {})
            if apiloc.get("latitude") is None:
                st.error("SunsetHue returned null coordinates. Try another location.")
                return

            status.update(label="✅ Done!", state="complete", expanded=False)

        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            try:
                msg = exc.response.json().get("message", str(exc))
            except Exception:
                msg = str(exc)
            st.error(f"API error ({code}): {msg}")
            return
        except requests.ConnectionError:
            st.error("Network error — check your internet connection.")
            return
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
            return

    # Store for persistence
    st.session_state.check_payload = {
        "data": data, "display": display,
        "lat": lat, "lng": lng, "is_trail": is_url,
    }


def _display_check_results(data, display, lat, lng, is_trail=False):
    utc_off = lng_to_utc_offset(lng)
    tz_label = f"UTC{'+' if utc_off >= 0 else ''}{utc_off}"

    st.markdown(f"### 📍 {display}")
    st.caption(f"Coordinates: {round(lat, 5)}, {round(lng, 5)}  ·  {tz_label}")

    items = data.get("data", [])
    if not items:
        st.info("No forecast data available for this location.")
        return

    days = pair_by_day(items, utc_off)
    if not days:
        st.info("No model data available yet — try again later.")
        return

    for day_label, sunrise, sunset in days:
        with st.container(border=True):
            st.markdown(f"**{day_label}**")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**🌅 Sunrise**")
                st.markdown(_event_html(sunrise, utc_off, "🌅"),
                            unsafe_allow_html=True)
            with c2:
                st.markdown("**🌇 Sunset**")
                st.markdown(_event_html(sunset, utc_off, "🌇"),
                            unsafe_allow_html=True)


# ──────────── Scan-nearby logic ───────────────────────────────────────

def _run_scan(api_key):
    total = len(HIKING_SPOTS)
    progress = st.progress(0, text="Starting scan…")
    status_box = st.empty()

    results = []
    seen_grids = set()
    api_calls = 0
    cache_hits = 0

    for i, (name, lat, lng, drive, desc) in enumerate(HIKING_SPOTS):
        progress.progress((i + 1) / total,
                          text=f"Scanning {i+1}/{total}: {name}…")

        grid = _grid_snap(lat, lng)
        is_new = grid not in seen_grids
        seen_grids.add(grid)
        if is_new:
            api_calls += 1
        else:
            cache_hits += 1

        try:
            data = fetch_forecast(lat, lng, api_key)
            if is_new:
                _time.sleep(0.15)   # gentle rate limit

            best_q, best_entry = -1, None
            for item in data.get("data", []):
                if not item.get("model_data"):
                    continue
                q = item.get("quality", 0) or 0
                if q > best_q:
                    best_q = q
                    best_entry = item

            if best_entry:
                results.append({
                    "name": name, "desc": desc, "drive": drive,
                    "lat": lat, "lng": lng,
                    "best_type": best_entry.get("type", "?"),
                    "best_quality": best_entry.get("quality", 0),
                    "best_qt": best_entry.get("quality_text", ""),
                    "best_time": best_entry.get("time"),
                    "cloud": best_entry.get("cloud_cover"),
                    "magics": best_entry.get("magics", {}),
                    "direction": best_entry.get("direction"),
                })
        except Exception:
            continue

    progress.empty()
    status_box.empty()
    results.sort(key=lambda r: r["best_quality"], reverse=True)

    st.session_state.scan_payload = {
        "results": results,
        "api_calls": api_calls,
        "cache_hits": cache_hits,
    }


def _display_scan_results(results, api_calls, cache_hits):
    st.markdown("### 🏆 Ranked by Best Upcoming Quality")
    cols = st.columns(3)
    cols[0].metric("Spots scanned", len(HIKING_SPOTS))
    cols[1].metric("API calls", api_calls)
    cols[2].metric("Grid cache hits", cache_hits)

    if not results:
        st.info("No forecast data returned for any spot.")
        return

    rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}

    for rank, r in enumerate(results, 1):
        col = quality_color(r["best_qt"])
        pct = round(r["best_quality"] * 100)
        event_label = "Sunrise" if r["best_type"] == "sunrise" else "Sunset"
        emoji = rank_emoji.get(rank, f"**#{rank}**")
        utc_off = lng_to_utc_offset(r["lng"])

        with st.container(border=True):
            top = st.columns([1, 5, 3])
            with top[0]:
                if rank <= 3:
                    st.markdown(
                        f"<div class='rank-num'>{emoji}</div>",
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<div class='rank-num' style='color:#6c7086;'>#{rank}</div>",
                        unsafe_allow_html=True)
            with top[1]:
                st.markdown(f"**{r['name']}**")
                st.caption(r["desc"])
            with top[2]:
                st.markdown(
                    f"<div style='text-align:right;'>"
                    f"<span style='font-size:1.3em; font-weight:700; color:{col};'>"
                    f"{pct}% {r['best_qt']}</span><br>"
                    f"<span style='font-size:0.85em; color:#a6adc8;'>{event_label}</span>"
                    f"</div>",
                    unsafe_allow_html=True)

            # Meta row
            parts = [f"🚗 ~{r['drive']} min"]
            t = format_utc_time(r.get("best_time"), utc_off)
            if t:
                parts.append(f"⏰ {t}")
            cc = r.get("cloud")
            if cc is not None:
                parts.append(f"☁️ {round(cc * 100)}%")
            d = r.get("direction")
            if d is not None:
                parts.append(f"🧭 {degrees_to_compass(d)} ({round(d)}°)")
            st.caption("   ·   ".join(parts))

            # Golden hour
            gh = r.get("magics", {}).get("golden_hour", [None, None])
            if gh and gh[0]:
                gs = format_utc_time(gh[0], utc_off)
                ge = format_utc_time(gh[1], utc_off)
                if gs and ge:
                    st.caption(f"✨ Golden hour: {gs} — {ge}")


# ──────────────────────────── Run ─────────────────────────────────────
main()
