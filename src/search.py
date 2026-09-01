import base64
import requests

SOCIAL_DOMAINS = [
    "twitter.com", "x.com", "instagram.com", "facebook.com",
    "linkedin.com", "reddit.com", "github.com", "threads.net",
    "tiktok.com", "youtube.com", "medium.com", "substack.com",
    "behance.net", "dribbble.com", "pinterest.com",
]


class ImageSearcher:
    def __init__(self, serpapi_key: str, imgbb_key: str):
        self.serpapi_key = serpapi_key
        self.imgbb_key   = imgbb_key

    def _upload(self, face_bytes: bytes) -> str:
        """Upload JPEG bytes to imgbb, return the public URL."""
        b64  = base64.b64encode(face_bytes).decode()
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": self.imgbb_key, "image": b64, "expiration": 600},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"imgbb upload failed: {data}")
        return data["data"]["url"]

    def _lens(self, image_url: str) -> dict:
        """Call SerpAPI Google Lens with the hosted image URL."""
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

    def search(self, face_bytes: bytes) -> dict:
        """
        Upload cropped face → Google Lens search.

        Returns:
        {
          "hosted_url":   str,         # temporary public URL of the uploaded face
          "candidates":   list[dict],  # ordered: social-media first, then others
          "person_name":  str,         # from Google knowledge graph (may be empty)
          "total_found":  int,
        }

        Each candidate dict:
        {
          "url":       str,   # page URL where the image appeared
          "title":     str,
          "source":    str,   # domain name
          "thumbnail": str,   # direct image URL — used for face comparison
          "is_social": bool,
        }

        Raises RuntimeError on API failure.
        """
        hosted_url = self._upload(face_bytes)
        raw        = self._lens(hosted_url)

        visual     = raw.get("visual_matches", [])
        knowledge  = raw.get("knowledge_graph", {})

        candidates = []
        for m in visual:
            link      = m.get("link", "")
            thumbnail = m.get("thumbnail", "")
            if not thumbnail:           # no image to compare against — skip
                continue
            is_social = any(d in link.lower() for d in SOCIAL_DOMAINS)
            candidates.append({
                "url":       link,
                "title":     m.get("title", ""),
                "source":    m.get("source", ""),
                "thumbnail": thumbnail,
                "is_social": is_social,
            })

        # Social-media results first (better chance of a clean face photo)
        social = [c for c in candidates if     c["is_social"]]
        other  = [c for c in candidates if not c["is_social"]]
        ordered = social + other

        return {
            "hosted_url":  hosted_url,
            "candidates":  ordered,
            "person_name": knowledge.get("title", ""),
            "total_found": len(ordered),
        }
