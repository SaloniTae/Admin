# tmdb_module.py
"""
TMDB helper module used by broadcaster_with_web.py

Provides:
 - TMDB_API_KEY, TMDB_IMAGE_BASE_URL
 - PLATFORM_PROVIDERS mapping
 - get_backdrop_url(media_type, item_id) -> str | None
 - verify_provider(media_type, item_id, expected_provider_id) -> bool
 - get_verified_suggestion(provider_id, media_type, platform_name) -> dict | None

This module uses the (blocking) requests library. The broadcaster runs it in a thread
via asyncio.to_thread so it won't block the event loop.
"""

import random
import time
import requests
from typing import Optional, Dict, Any, List

# ---------------- CONFIG ----------------
TMDB_API_KEY = "a8e91f05284b200aa4b62fa99476083b"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

# Platform provider IDs (TMDB provider ids) - keep as-is
PLATFORM_PROVIDERS = {
    "Netflix": 8,
    "Prime Video": 119,  # Amazon Prime Video ID for IN region
    "Crunchyroll": 283
}

WATCH_REGION = "IN"
LANGUAGE = "en-US"

# ---------------- UTILITIES ----------------
def _safe_get(url: str, params: dict, timeout: int = 8) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

# ---------------- CORE FUNCTIONS ----------------
def get_backdrop_url(media_type: str, item_id: int) -> Optional[str]:
    """
    Return a chosen backdrop URL for the given media_type ('movie'|'tv') and TMDB id.
    Preference order: english -> hindi -> tamil/telugu -> other.
    Returns full TMDB image URL or None.
    """
    if not media_type or not item_id:
        return None

    url = f"https://api.themoviedb.org/3/{media_type}/{item_id}/images"
    params = {"api_key": TMDB_API_KEY}
    data = _safe_get(url, params, timeout=6)
    if not data:
        return None

    backdrops: List[dict] = data.get("backdrops", []) or []
    if not backdrops:
        return None

    # bucket by language
    buckets = {"en": [], "hi": [], "south": [], "other": []}
    for b in backdrops:
        lang = b.get("iso_639_1")
        if lang == "en":
            buckets["en"].append(b)
        elif lang == "hi":
            buckets["hi"].append(b)
        elif lang in ("ta", "te"):
            buckets["south"].append(b)
        else:
            buckets["other"].append(b)

    chosen = None
    if buckets["en"]:
        chosen = random.choice(buckets["en"])
    elif buckets["hi"]:
        chosen = random.choice(buckets["hi"])
    elif buckets["south"]:
        chosen = random.choice(buckets["south"])
    elif buckets["other"]:
        chosen = random.choice(buckets["other"])

    if not chosen:
        return None

    file_path = chosen.get("file_path")
    if not file_path:
        return None

    return f"{TMDB_IMAGE_BASE_URL}{file_path}"

def verify_provider(media_type: str, item_id: int, expected_provider_id: int) -> bool:
    """
    Check TMDB /watch/providers for given media item and return True if expected_provider_id
    is present in the 'flatrate' (streaming) providers for the WATCH_REGION.
    """
    if not media_type or not item_id or not expected_provider_id:
        return False

    url = f"https://api.themoviedb.org/3/{media_type}/{item_id}/watch/providers"
    params = {"api_key": TMDB_API_KEY}
    data = _safe_get(url, params, timeout=6)
    if not data:
        return False

    results = data.get("results", {})
    region = results.get(WATCH_REGION, {}) if isinstance(results, dict) else {}
    flatrate = region.get("flatrate", []) or []
    for p in flatrate:
        if p.get("provider_id") == expected_provider_id:
            return True
    return False

def get_verified_suggestion(provider_id: int, media_type: str, platform_name: str) -> Optional[Dict[str, Any]]:
    """
    Discover popular candidates using TMDB discover and then verify provider availability.
    Returns a candidate dict (TMDB discover item) or None if none verified.
    - provider_id: TMDB provider id (int)
    - media_type: 'tv' or 'movie'
    - platform_name: name used for logging (string)
    """
    if not provider_id or media_type not in ("tv", "movie"):
        return None

    discover_url = f"https://api.themoviedb.org/3/discover/{media_type}"
    params = {
        "api_key": TMDB_API_KEY,
        "sort_by": "popularity.desc",
        "vote_average.gte": 7.0,
        "vote_count.gte": 300,
        "watch_region": WATCH_REGION,
        "with_watch_providers": provider_id,
        "language": LANGUAGE,
        "page": 1
    }

    # For Prime we might exclude animation (as in your original logic)
    if platform_name == "Prime Video":
        params["without_genres"] = "16"

    data = _safe_get(discover_url, params, timeout=8)
    if not data:
        return None

    candidates = data.get("results", []) or []
    if not candidates:
        return None

    random.shuffle(candidates)

    # Verify up to first 10 candidates (or fewer if less available)
    for cand in candidates[:10]:
        try:
            cid = cand.get("id")
            if not cid:
                continue
            if verify_provider(media_type, cid, provider_id):
                # return the original candidate dict for later processing
                return cand
        except Exception:
            # ignore individual candidate failures and continue
            continue

    return None

# Optional CLI for manual testing
def main():
    print("TMDB module quick test")
    for platform, pid in PLATFORM_PROVIDERS.items():
        print(f"\n--- Checking {platform} ({pid}) ---")
        # prefer tv for picks
        pick = get_verified_suggestion(pid, "tv", platform)
        if not pick:
            print("No verified pick found.")
            continue
        title = pick.get("title") or pick.get("name")
        year = (pick.get("release_date") or pick.get("first_air_date") or "")[:4]
        rating = pick.get("vote_average")
        backdrop = get_backdrop_url("tv", pick["id"])
        print(f"{title} ({year}) — {rating}")
        print("Backdrop:", backdrop)

if __name__ == "__main__":
    main()
