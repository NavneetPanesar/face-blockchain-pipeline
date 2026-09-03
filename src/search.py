# ============================================================
# FILE: src/search.py
# ============================================================

import os
import json
import requests

from dotenv import load_dotenv
from rich.console import Console
from serpapi import GoogleSearch


load_dotenv()

console = Console()


SOCIAL_DOMAINS = {
    "twitter.com",
    "x.com",
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "reddit.com",
    "github.com",
    "threads.net",
    "tiktok.com",
    "youtube.com",
    "medium.com",
    "substack.com",
    "behance.net",
    "dribbble.net",
    "pinterest.com",
}


def _is_social_url(url: str) -> bool:
    """Return True when the URL belongs to a supported social platform."""

    if not url:
        return False

    url_lower = url.lower()

    return any(
        domain in url_lower
        for domain in SOCIAL_DOMAINS
    )


def _upload(image_bytes: bytes) -> str:
    """Upload the face image to ImgBB and return its temporary URL."""

    api_key = os.getenv("IMGBB_KEY")

    if not api_key:
        raise RuntimeError(
            "IMGBB_KEY is missing from .env"
        )

    response = requests.post(
        "https://api.imgbb.com/1/upload",
        params={
            "key": api_key,
            "expiration": 600,
        },
        files={
            "image": image_bytes,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise RuntimeError(
            "ImgBB upload failed"
        )

    return data["data"]["url"]


def _lens(image_url: str) -> dict:
    """Run Google Lens through SerpAPI."""

    api_key = os.getenv("SERPAPI_KEY")

    if not api_key:
        raise RuntimeError(
            "SERPAPI_KEY is missing from .env"
        )

    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": api_key,
    }

    search = GoogleSearch(params)

    return search.get_dict()


def _extract_provider_metadata(
    results: dict,
) -> tuple[str | None, str]:
    """
    Extract a provider-supplied related result.

    Priority:
        1. Google Lens knowledge graph title/name
        2. Google Lens related_content query

    IMPORTANT:
    This function does not infer a person's identity from:
        - URL
        - username
        - page title
        - face similarity

    It only returns metadata explicitly supplied
    by the search provider.
    """

    # --------------------------------------------------------
    # 1. Knowledge graph
    # --------------------------------------------------------

    knowledge_graph = results.get(
        "knowledge_graph"
    )

    entries = []

    if isinstance(
        knowledge_graph,
        list,
    ):

        entries = [
            entry
            for entry in knowledge_graph
            if isinstance(entry, dict)
        ]

    elif isinstance(
        knowledge_graph,
        dict,
    ):

        entries = [
            knowledge_graph
        ]

    for entry in entries:

        value = (
            entry.get("title")
            or entry.get("name")
        )

        if (
            isinstance(value, str)
            and value.strip()
        ):

            return (
                value.strip(),
                "google_lens_knowledge_graph",
            )

    # --------------------------------------------------------
    # 2. Related content query
    # --------------------------------------------------------

    related_content = results.get(
        "related_content"
    )

    if isinstance(
        related_content,
        list,
    ):

        for item in related_content:

            if not isinstance(
                item,
                dict,
            ):
                continue

            query = item.get(
                "query"
            )

            if (
                isinstance(query, str)
                and query.strip()
            ):

                return (
                    query.strip(),
                    "google_lens_related_query",
                )

    # --------------------------------------------------------
    # Nothing available
    # --------------------------------------------------------

    return (
        None,
        "not_available",
    )


def _save_debug_response(results: dict) -> None:
    """
    Save a local copy of the Lens response for debugging.

    This file is intentionally local and should NOT be committed
    to GitHub if it contains API-specific information.
    """

    try:

        # Make a copy before removing potentially sensitive
        # provider/request fields.
        debug_data = dict(results)

        with open(
            "lens_debug.json",
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                debug_data,
                file,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

    except Exception as exc:

        console.print(
            f"    [yellow]Could not save Lens debug file: {exc}[/yellow]"
        )


def search(
    image_bytes: bytes,
) -> dict:
    """
    Perform reverse-image search.

    Returns:
        {
            hosted_url,
            candidates,
            person_name,
            name_source,
            total_found,
            social_count,
            web_count,
        }
    """

    console.print(
        "    Uploading image for reverse-image search..."
    )

    hosted_url = _upload(
        image_bytes
    )

    console.print(
        "    Running Google Lens search..."
    )

    results = _lens(
        hosted_url
    )

    # Save complete local debug response.
    _save_debug_response(
        results
    )

    # --------------------------------------------------------
    # Extract provider metadata
    # --------------------------------------------------------

    provider_value, provider_source = (
        _extract_provider_metadata(
            results
        )
    )

    if provider_value:

        console.print(
            f"    Google Lens related result: "
            f"[bold]{provider_value}[/bold]"
        )

        console.print(
            f"    Metadata source: "
            f"{provider_source}"
        )

    else:

        console.print(
            "    No provider-supplied related result "
            "in Lens metadata"
        )

    # --------------------------------------------------------
    # Extract visual matches
    # --------------------------------------------------------

    visual_matches = results.get(
        "visual_matches",
        [],
    )

    candidates = []

    for match in visual_matches:

        if not isinstance(
            match,
            dict,
        ):
            continue

        url = match.get(
            "link",
            "",
        )

        title = match.get(
            "title",
            "",
        )

        source = match.get(
            "source",
            "",
        )

        thumbnail = match.get(
            "thumbnail",
            "",
        )

        image = match.get(
            "image",
            "",
        )

        # We need both a URL and a comparable image.
        if not url:
            continue

        if not thumbnail and not image:
            continue

        is_social = _is_social_url(
            url
        )

        candidates.append(
            {
                "url": url,
                "title": title,
                "source": source,
                "thumbnail": thumbnail,
                "image": image,
                "is_social": is_social,
            }
        )

    # Put social results first.
    candidates.sort(
        key=lambda candidate: not candidate["is_social"]
    )

    social_count = sum(
        1
        for candidate in candidates
        if candidate["is_social"]
    )

    web_count = (
        len(candidates)
        - social_count
    )

    console.print(
        f"    Google Lens returned "
        f"{len(candidates)} usable visual matches"
    )

    console.print(
        f"    Social candidates: "
        f"{social_count} | "
        f"Other web candidates: "
        f"{web_count}"
    )

    return {
        "hosted_url": hosted_url,

        "candidates": candidates,

        # Kept for compatibility with pipeline.py.
        # This is provider metadata only.
        "person_name": provider_value,

        "name_source": provider_source,

        "total_found": len(candidates),

        "social_count": social_count,

        "web_count": web_count,
    }