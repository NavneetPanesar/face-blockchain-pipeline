import base64
import json
import requests


SOCIAL_DOMAINS = [
    "twitter.com", "x.com", "instagram.com", "facebook.com",
    "linkedin.com", "reddit.com", "github.com", "threads.net",
    "tiktok.com", "youtube.com", "medium.com", "substack.com",
]


class ImageSearcher:
    def __init__(self, serpapi_key: str, imgbb_key: str):
        self.serpapi_key = serpapi_key
        self.imgbb_key   = imgbb_key

    # ── 1. Upload cropped face to get a public URL ──────────────────────
    def _upload(self, face_bytes: bytes) -> str:
        b64 = base64.b64encode(face_bytes).decode()
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key":        self.imgbb_key,
                "image":      b64,
                "expiration": 600,          # 10 min is enough
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"imgbb upload failed: {data}")
        return data["data"]["url"]

    # ── 2. Google Lens reverse search via SerpAPI ────────────────────────
    def _lens_search(self, image_url: str) -> dict:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine":  "google_lens",
                "url":     image_url,
                "api_key": self.serpapi_key,
                "hl":      "en",
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    # ── 3. Pick best match ───────────────────────────────────────────────
    @staticmethod
    def _best_match(raw: dict) -> dict:
        visual = raw.get("visual_matches", [])
        knowledge = raw.get("knowledge_graph", {})

        social, other = [], []
        for m in visual:
            url   = m.get("link", "")
            entry = {
                "url":       url,
                "title":     m.get("title", ""),
                "source":    m.get("source", ""),
                "thumbnail": m.get("thumbnail", ""),
                "is_social": any(d in url.lower() for d in SOCIAL_DOMAINS),
            }
            (social if entry["is_social"] else other).append(entry)

        best = (social or other or [None])[0]
        return {
            "found":          best is not None,
            "best":           best,
            "social_matches": social,
            "all_matches":    (social + other)[:8],
            "total_matches":  len(visual),
            "person_name":    knowledge.get("title", ""),
        }

    # ── Public entry point ───────────────────────────────────────────────
    def search(self, face_bytes: bytes) -> dict:
        image_url = self._upload(face_bytes)
        raw       = self._lens_search(image_url)
        result    = self._best_match(raw)
        result["hosted_url"] = image_url
        return result
