# suggester_trio.py

import os
import random
import json
import requests
import redis
from openai import OpenAI
from datetime import timedelta

# ==============================================================================
# --- ⚠️ CONFIGURATION - FILL IN YOUR SECRET KEYS AND SETTINGS HERE ⚠️ ---
# ==============================================================================

# --- TMDB Configuration ---
# Get your key from https://www.themoviedb.org/settings/api
TMDB_API_KEY = "a8e91f05284b200aa4b62fa99476083b"

# --- OpenRouter Configuration ---
# Get your key from https://openrouter.ai/keys
OPENROUTER_API_KEY = "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"

# --- Upstash Redis Configuration ---
# Get your URL from the Upstash console.
# It should look like: "redis://default:YOUR_TOKEN@YOUR_HOSTNAME:PORT"
UPSTASH_REDIS_URL = "https://internal-swine-7780.upstash.io"

# --- Platform & Region Configuration ---
# These are the TMDB provider IDs for each platform. We will get a pick from each.
PLATFORM_PROVIDERS = {
    "Netflix": 8,
    "Prime Video": 119, # Amazon Prime Video ID for IN region
    "Crunchyroll": 283
}
WATCH_REGION = "IN"
LANGUAGE = "en-US"

# ==============================================================================
# --- APPLICATION CODE (No need to edit below this line) ---
# ==============================================================================

# --- 1. Initialize Clients ---
if "YOUR_" in TMDB_API_KEY or "YOUR_" in OPENROUTER_API_KEY or "YOUR_" in UPSTASH_REDIS_URL:
    print("❌ Error: Please fill in your API keys and Redis URL in the configuration section.")
    exit()

try:
    redis_client = redis.from_url(UPSTASH_REDIS_URL, decode_responses=True)
    redis_client.ping()
    print("✅ Connected to Upstash Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"❌ Could not connect to Upstash Redis: {e}")
    exit()

openrouter_client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=OPENROUTER_API_KEY,
)

# --- 2. TMDB API Functions ---

def get_popular_content_from_tmdb(provider_id: int, media_type: str) -> list | None:
    """Fetches popular and well-rated content from a specific provider in India."""
    print(f"🌐 Fetching TMDB data for {media_type.upper()}s on provider ID {provider_id}...")
    tmdb_api_url = f"https://api.themoviedb.org/3/discover/{media_type}"
    params = {
        'api_key': TMDB_API_KEY,
        'sort_by': 'popularity.desc',
        'vote_average.gte': 7.0,
        'vote_count.gte': 200, # Lowered slightly for broader results
        'watch_region': WATCH_REGION,
        'with_watch_providers': provider_id,
        'language': LANGUAGE,
        'page': 1
    }
    try:
        response = requests.get(tmdb_api_url, params=params)
        response.raise_for_status()
        return response.json().get('results', []) or None
    except requests.exceptions.RequestException as e:
        print(f"❌ TMDB API Error: {e}")
        return None

# --- 3. Caching Functions (Redis) ---

def get_content_from_cache_or_api(provider_name: str, provider_id: int, media_type: str) -> list | None:
    """Tries to get data from Redis cache. If not found, fetches from TMDB and caches it."""
    cache_key = f"content:{WATCH_REGION}:{provider_name}:{media_type}"
    cached_data_json = redis_client.get(cache_key)
    
    if cached_data_json:
        print(f"✅ Cache hit for '{provider_name}' in region '{WATCH_REGION}'.")
        return json.loads(cached_data_json)
    else:
        print(f"🔍 Cache miss for '{provider_name}'.")
        data = get_popular_content_from_tmdb(provider_id, media_type)
        if data:
            redis_client.setex(cache_key, timedelta(hours=12), json.dumps(data))
            print(f"💾 Saved new data to Redis cache (expires in 12 hours).")
        return data

# --- 4. AI Curation Function (Gemini Flash) ---

def get_gemini_single_suggestion(content_list: list, platform_name: str, media_type: str) -> str:
    """Sends a list to Gemini Flash and asks for the single best suggestion."""
    print(f"🤖 Asking Gemini Flash for the #1 pick from {platform_name}...")
    
    sample_size = min(len(content_list), 25)
    random_sample = random.sample(content_list, sample_size)
    
    formatted_list = []
    for item in random_sample:
        title = item.get('title') or item.get('name')
        year = (item.get('release_date') or item.get('first_air_date', ''))[:4]
        rating = item.get('vote_average')
        formatted_list.append(f"- {title} ({year}) - Rating: {rating:.1f}/10")
    
    content_str = "\n".join(formatted_list)

    prompt = f"""
    You are a fun and sharp movie critic. I have a list of popular and well-rated {media_type} available on {platform_name} in India.

    From this list, pick the *single best one* to recommend right now.

    Your entire response MUST be in this exact format, and nothing else:
    **[Title] ([Year])**: [A short, punchy, and exciting one-sentence reason why it's a must-watch.]

    Here is the list of available titles to analyze:
    {content_str}
    """

    try:
        completion = openrouter_client.chat.completions.create(
            model="google/gemini-1.5-flash",
            messages=[
                {"role": "system", "content": "You are a movie and TV recommendation expert who gives one single, perfectly formatted recommendation."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=150,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error communicating with OpenRouter/Gemini: {e}")
        # Provide a fallback random suggestion if AI fails
        random_pick = random.choice(content_list)
        title = random_pick.get('title') or random_pick.get('name')
        year = (random_pick.get('release_date') or random_pick.get('first_air_date', ''))[:4]
        return f"**{title} ({year})**: The AI is napping, but this randomly selected popular choice is highly rated and worth a look!"

# --- 5. Main Execution ---

def main():
    """Main function to get one suggestion from each platform."""
    print("\n" + "=" * 50)
    print("🎬 Your Curated Streaming Trio (India Edition) 🍿")
    print("=" * 50)

    all_suggestions = []

    # --- Iterate through each platform to get one suggestion ---
    for platform_name, provider_id in PLATFORM_PROVIDERS.items():
        print(f"\n----- Searching on {platform_name} -----")
        # Randomly choose between movie or tv for variety
        media_type = random.choice(['movie', 'tv'])
        media_type_plural = "TV Shows" if media_type == 'tv' else 'Movies'
        
        content_list = get_content_from_cache_or_api(platform_name, provider_id, media_type)
        
        suggestion_text = ""
        if not content_list:
            suggestion_text = f"Couldn't find any top-rated {media_type_plural} on {platform_name} right now. Check back later!"
        else:
            suggestion_text = get_gemini_single_suggestion(content_list, platform_name, media_type_plural)
            
        all_suggestions.append({
            "platform": platform_name,
            "suggestion": suggestion_text
        })

    # --- Display all collected suggestions at the end ---
    print("\n\n" + "="*20 + " YOUR PICKS FOR TONIGHT " + "="*19)
    
    for item in all_suggestions:
        print(f"\n✨ Your recommendation from {item['platform']}:")
        print(f"   {item['suggestion']}")
        
    print("\n" + "="*59)


if __name__ == "__main__":
    main()