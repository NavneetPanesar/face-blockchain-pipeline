import os
import tempfile

import numpy as np
import requests
from deepface import DeepFace
from rich.console import Console

console = Console()

# Facenet cosine similarity: >= 0.60 is considered the same person.
# (Cosine distance threshold of 0.40 used by DeepFace internally = similarity 0.60)
COSINE_THRESHOLD  = 0.60
MAX_TO_TRY        = 12   # check at most this many candidates


# ── Internal helpers ────────────────────────────────────────────────────────

def _cosine_similarity(a: list, b: list) -> float:
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _download(url: str, timeout: int = 15) -> str | None:
    """
    Download image at url into a temp file.
    Returns the temp-file path, or None on any error.
    Caller must delete the file when done.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        resp.raise_for_status()

        ctype = resp.headers.get("Content-Type", "")
        if "image" not in ctype and "octet" not in ctype:
            return None

        suffix = ".jpg"
        if "png"  in ctype: suffix = ".png"
        if "webp" in ctype: suffix = ".webp"

        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return path
    except Exception:
        return None


def _embed_from_url(image_url: str) -> list | None:
    """
    Download image → detect face → return Facenet embedding.
    Returns None if download fails or no face is detected.
    """
    path = _download(image_url)
    if path is None:
        return None
    try:
        results = DeepFace.represent(
            img_path=path,
            model_name="Facenet",
            enforce_detection=True,
            detector_backend="opencv",
            align=True,
        )
        if not results:
            return None
        return results[0]["embedding"]
    except Exception:
        return None
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ── Public entry point ──────────────────────────────────────────────────────

def find_matching_candidate(
    original_embedding: list,
    candidates: list,
    threshold: float = COSINE_THRESHOLD,
) -> dict:
    """
    For each candidate (social-media-first order from search.py):
      1. Download its thumbnail image.
      2. Detect a face in it with DeepFace.
      3. Compute cosine similarity against original_embedding.
      4. If similarity >= threshold → confirmed match, return immediately.

    Returns:
    {
      "matched":      bool,
      "candidate":    dict | None,   # the winning candidate
      "similarity":   float,         # 0.0 if not matched
      "face_found_in":str,           # thumbnail URL where the face was found
      "tried":        int,           # number of thumbnails attempted
    }
    """
    tried = 0
    for c in candidates[:MAX_TO_TRY]:
        thumb = c.get("thumbnail", "")
        if not thumb:
            continue

        tried += 1
        console.print(
            f"    [dim]Trying candidate {tried}: {c['source'] or c['url'][:50]}[/dim]"
        )

        embedding = _embed_from_url(thumb)
        if embedding is None:
            console.print(f"    [dim]  → no face detected in thumbnail[/dim]")
            continue

        sim = _cosine_similarity(original_embedding, embedding)
        console.print(f"    [dim]  → face found, similarity = {sim:.4f}[/dim]")

        if sim >= threshold:
            return {
                "matched":       True,
                "candidate":     c,
                "similarity":    round(sim, 6),
                "face_found_in": thumb,
                "tried":         tried,
            }

    return {
        "matched":       False,
        "candidate":     None,
        "similarity":    0.0,
        "face_found_in": "",
        "tried":         tried,
    }
