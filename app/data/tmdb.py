"""TMDB poster enrichment — optional, only runs if TMDB_API_KEY is set."""
import os
import httpx

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BASE    = "https://api.themoviedb.org/3"


def fetch_poster_path(title: str, year: int) -> str:
    if not TMDB_API_KEY:
        return ""
    try:
        r = httpx.get(
            f"{TMDB_BASE}/search/movie",
            params={"api_key": TMDB_API_KEY, "query": title, "year": year, "language": "en-US"},
            timeout=5,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            return results[0].get("poster_path") or ""
    except Exception:
        pass
    return ""
