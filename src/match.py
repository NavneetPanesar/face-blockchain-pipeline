import os
import tempfile

import numpy as np
import requests
from deepface import DeepFace
from rich.console import Console


console = Console()

# Facenet cosine similarity threshold.
COSINE_THRESHOLD = 0.60

# Maximum number of search candidates to evaluate.
MAX_TO_TRY = 12


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cosine_similarity(a: list, b: list) -> float:
    """
    Calculate cosine similarity between two embedding vectors.
    Returns 0.0 if either vector has zero magnitude.
    """
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)

    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)

    if na == 0.0 or nb == 0.0:
        return 0.0

    return float(np.dot(va, vb) / (na * nb))


def _download(url: str, timeout: int = 15) -> str | None:
    """
    Download an image URL into a temporary file.

    Returns:
        Temporary file path on success.
        None if the download fails.

    The caller is responsible for deleting the temporary file.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        resp = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            stream=True,
        )

        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "").lower()

        if "image" not in content_type and "octet" not in content_type:
            return None

        suffix = ".jpg"

        if "png" in content_type:
            suffix = ".png"
        elif "webp" in content_type:
            suffix = ".webp"
        elif "jpeg" in content_type or "jpg" in content_type:
            suffix = ".jpg"

        fd, path = tempfile.mkstemp(suffix=suffix)

        with os.fdopen(fd, "wb") as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)

        return path

    except Exception:
        return None


def _embed_from_url(image_url: str) -> list | None:
    """
    Download an image, detect a face, and return its FaceNet embedding.

    Returns None if:
    - the image cannot be downloaded
    - no face is detected
    - DeepFace fails for any other reason
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


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def find_matching_candidate(
    original_embedding: list,
    candidates: list,
    threshold: float = COSINE_THRESHOLD,
) -> dict:
    """
    Evaluate up to MAX_TO_TRY search candidates.

    For every candidate:
      1. Prefer the full-resolution image if available.
      2. Fall back to the thumbnail.
      3. Detect a face using DeepFace.
      4. Calculate cosine similarity against the original embedding.
      5. Keep the candidate with the highest similarity.

    Unlike the previous implementation, this function does NOT stop
    at the first candidate that crosses the threshold.

    It evaluates the available candidates and selects the strongest
    valid match.

    Returns:
        {
            "matched": bool,
            "candidate": dict | None,
            "similarity": float,
            "face_found_in": str,
            "tried": int,
        }
    """

    tried = 0

    best_candidate = None
    best_similarity = 0.0
    best_image_url = ""

    # Only evaluate the configured maximum number of candidates.
    for candidate in candidates[:MAX_TO_TRY]:

        # Prefer a full-resolution image if search.py provides one.
        # Otherwise use the thumbnail.
        image_url = (
            candidate.get("image")
            or candidate.get("thumbnail", "")
        )

        if not image_url:
            continue

        tried += 1

        source = (
            candidate.get("source")
            or candidate.get("url", "")
        )

        console.print(
            f"    [dim]Trying candidate {tried}: "
            f"{source[:70]}[/dim]"
        )

        embedding = _embed_from_url(image_url)

        if embedding is None:
            console.print(
                "    [dim]  → no face detected[/dim]"
            )
            continue

        similarity = _cosine_similarity(
            original_embedding,
            embedding,
        )

        console.print(
            f"    [dim]  → face found, "
            f"similarity = {similarity:.4f}[/dim]"
        )

        # Keep the strongest candidate seen so far.
        if similarity > best_similarity:
            best_similarity = similarity
            best_candidate = candidate
            best_image_url = image_url

    # Only call it a confirmed match if it reaches the threshold.
    if (
        best_candidate is not None
        and best_similarity >= threshold
    ):
        console.print(
            f"    [green]✓ Best match selected: "
            f"{best_similarity:.4f}[/green]"
        )

        return {
            "matched": True,
            "candidate": best_candidate,
            "similarity": round(best_similarity, 6),
            "face_found_in": best_image_url,
            "tried": tried,
        }

    console.print(
        f"    [yellow]No candidate reached the "
        f"{threshold:.2f} similarity threshold[/yellow]"
    )

    return {
        "matched": False,
        "candidate": None,
        "similarity": 0.0,
        "face_found_in": "",
        "tried": tried,
    }