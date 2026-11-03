"""
Real photo/video sourcing via free, official stock-media APIs (Pexels, Pixabay).

Why this exists: the previous only real-photo source was DuckDuckGo image scraping
(via the unofficial `duckduckgo_search` library), which production logs showed getting
rate-limited mid-run ("DDG rate-limited on multiple queries. Skipping remaining DDG
attempts."). There was also no real *video* b-roll source at all — every non-AI-video
scene fell back to a static photo with a Ken Burns pan. Pexels and Pixabay both offer
genuinely free API keys (no cost, no credit card) with official, documented, reliable
endpoints for both photos and video clips — a direct upgrade in both reliability and
topic relevance.

Both are fully optional: every function here returns an empty list (never raises) if
its API key isn't set in the environment, so the rest of the pipeline's existing
DDG/Wikimedia/NASA/Pollinations fallback chain is untouched when keys are absent.

Setup (both free, ~2 minutes each, no credit card):
  - Pexels:  https://www.pexels.com/api/          -> set PEXELS_API_KEY
  - Pixabay: https://pixabay.com/api/docs/         -> set PIXABAY_API_KEY
"""
import os
import re
import time
import json
import requests

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _clean_query(query: str) -> str:
    q = re.sub(r'[^a-zA-Z0-9 ]', ' ', query or "")
    q = re.sub(r'\s+', ' ', q).strip()
    return q[:80]


def _download(url: str, dest_dir: str, filename: str, min_bytes: int = 2000, timeout: int = 30) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    save_path = os.path.join(dest_dir, filename)
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout, stream=True)
        if resp.status_code != 200:
            print(f"[StockMedia] Download HTTP {resp.status_code}: {url[:90]}")
            return None
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        if os.path.getsize(save_path) < min_bytes:
            os.remove(save_path)
            return None
        return save_path
    except Exception as e:
        print(f"[StockMedia] Download error ({url[:90]}): {e}")
        return None


# ── Pexels ────────────────────────────────────────────────────────────────────────

def fetch_pexels_photos(query: str, count: int, dest_dir: str, base_filename: str,
                         orientation: str = "landscape") -> list:
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": _clean_query(query), "per_page": min(count, 15), "orientation": orientation},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[Pexels] Photo search HTTP {resp.status_code} for '{query}'")
            return []
        data = resp.json()
        paths = []
        for i, photo in enumerate(data.get("photos", [])):
            src = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("original")
            if not src:
                continue
            path = _download(src, dest_dir, f"{base_filename}_{i}_pexels.jpg")
            if path:
                source = photo
                with open(path + ".source.json", "w", encoding="utf-8") as credit:
                    json.dump({"provider": "Pexels", "id": source.get("id"),
                               "url": source.get("url"), "creator": source.get("photographer") or source.get("user", {}).get("name"),
                               "license": "https://www.pexels.com/license/"}, credit)
                paths.append(path)
            if len(paths) >= count:
                break
        if paths:
            print(f"[Pexels] Found {len(paths)} photo(s) for '{query}'.")
        return paths
    except Exception as e:
        print(f"[Pexels] Photo search error: {e}")
        return []


def fetch_pexels_videos(query: str, count: int, dest_dir: str, base_filename: str,
                         orientation: str = "landscape", max_height: int = 1080) -> list:
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": api_key},
            params={"query": _clean_query(query), "per_page": min(count, 15), "orientation": orientation},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[Pexels] Video search HTTP {resp.status_code} for '{query}'")
            return []
        data = resp.json()
        paths = []
        for i, video in enumerate(data.get("videos", [])):
            files = [vf for vf in video.get("video_files", []) if vf.get("file_type") == "video/mp4"]
            # Prefer the largest file that still fits our height budget (keeps downloads
            # small/fast); fall back to the smallest available if none qualify.
            candidates = sorted(
                [vf for vf in files if (vf.get("height") or 0) <= max_height],
                key=lambda vf: vf.get("height") or 0, reverse=True,
            ) or sorted(files, key=lambda vf: vf.get("height") or 999999)
            if not candidates:
                continue
            link = candidates[0].get("link")
            if not link:
                continue
            path = _download(link, dest_dir, f"{base_filename}_{i}_pexels.mp4", min_bytes=20000, timeout=45)
            if path:
                source = video
                with open(path + ".source.json", "w", encoding="utf-8") as credit:
                    json.dump({"provider": "Pexels", "id": source.get("id"),
                               "url": source.get("url"), "creator": source.get("photographer") or source.get("user", {}).get("name"),
                               "license": "https://www.pexels.com/license/"}, credit)
                paths.append(path)
            if len(paths) >= count:
                break
        if paths:
            print(f"[Pexels] Found {len(paths)} video(s) for '{query}'.")
        return paths
    except Exception as e:
        print(f"[Pexels] Video search error: {e}")
        return []


# ── Pixabay ───────────────────────────────────────────────────────────────────────

def fetch_pixabay_photos(query: str, count: int, dest_dir: str, base_filename: str,
                          orientation: str = "horizontal") -> list:
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": api_key, "q": _clean_query(query), "image_type": "photo",
                "orientation": orientation, "safesearch": "true",
                "per_page": max(3, min(count, 15)),
            },
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[Pixabay] Photo search HTTP {resp.status_code} for '{query}'")
            return []
        data = resp.json()
        paths = []
        for i, hit in enumerate(data.get("hits", [])):
            src = hit.get("largeImageURL") or hit.get("webformatURL")
            if not src:
                continue
            path = _download(src, dest_dir, f"{base_filename}_{i}_pixabay.jpg")
            if path:
                paths.append(path)
            if len(paths) >= count:
                break
        if paths:
            print(f"[Pixabay] Found {len(paths)} photo(s) for '{query}'.")
        return paths
    except Exception as e:
        print(f"[Pixabay] Photo search error: {e}")
        return []


def fetch_pixabay_videos(query: str, count: int, dest_dir: str, base_filename: str) -> list:
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": api_key, "q": _clean_query(query), "safesearch": "true",
                    "per_page": max(3, min(count, 15))},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[Pixabay] Video search HTTP {resp.status_code} for '{query}'")
            return []
        data = resp.json()
        paths = []
        for i, hit in enumerate(data.get("hits", [])):
            videos = hit.get("videos", {})
            # Prefer "medium" (~960px) — small enough to be fast, large enough to upscale
            # cleanly to 1080p/1920p after the existing cover-crop step.
            src = (videos.get("medium") or videos.get("small") or videos.get("large") or {}).get("url")
            if not src:
                continue
            path = _download(src, dest_dir, f"{base_filename}_{i}_pixabay.mp4", min_bytes=20000, timeout=45)
            if path:
                paths.append(path)
            if len(paths) >= count:
                break
        if paths:
            print(f"[Pixabay] Found {len(paths)} video(s) for '{query}'.")
        return paths
    except Exception as e:
        print(f"[Pixabay] Video search error: {e}")
        return []


# ── Combined convenience helpers ─────────────────────────────────────────────────

def fetch_real_photos(query: str, count: int, dest_dir: str, base_filename: str,
                       portrait: bool = False) -> list:
    """Tries Pexels then Pixabay. Returns [] (never raises) if neither key is configured
    or neither has a match — callers should fall through to their existing fallback chain."""
    orientation_pexels = "portrait" if portrait else "landscape"
    orientation_pixabay = "vertical" if portrait else "horizontal"
    paths = fetch_pexels_photos(query, count, dest_dir, base_filename, orientation_pexels)
    if len(paths) < count:
        paths += fetch_pixabay_photos(query, count - len(paths), dest_dir, base_filename, orientation_pixabay)
    return paths


def fetch_real_videos(query: str, count: int, dest_dir: str, base_filename: str,
                       portrait: bool = False) -> list:
    """Tries Pexels then Pixabay for real (non-AI) stock video b-roll. [] if unavailable."""
    orientation_pexels = "portrait" if portrait else "landscape"
    paths = fetch_pexels_videos(query, count, dest_dir, base_filename, orientation_pexels)
    if len(paths) < count:
        paths += fetch_pixabay_videos(query, count - len(paths), dest_dir, base_filename)
    return paths


def has_stock_api_keys() -> bool:
    return bool(os.getenv("PEXELS_API_KEY", "").strip() or os.getenv("PIXABAY_API_KEY", "").strip())
