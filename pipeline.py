# ============================================================
# FILE: src/pipeline.py
# ============================================================
#!/usr/bin/env python3

"""
Face ID + Blockchain Verification Pipeline
===========================================

Input image
    -> FaceNet embedding
    -> Google Lens reverse-image search through SerpAPI
    -> Candidate web/social results
    -> Best face-similarity match
    -> Deterministic SHA-256 evidence fingerprint
    -> Ethereum Sepolia storage
    -> On-chain re-verification

IMPORTANT:
The blockchain record proves that a specific evidence
fingerprint was recorded and can later be re-read identically.

Any displayed Google Lens related result comes directly
from search-provider metadata. It is not independently
inferred by this pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box

load_dotenv()

from src.face import FaceDetector
from src.search import search as run_search
from src.match import (
    find_matching_candidate,
    COSINE_THRESHOLD,
)
from src.chain import BlockchainVerifier


console = Console()

PIPELINE_VERSION = "2.2.0"

VALID_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

MAX_INPUT_BYTES = 15 * 1024 * 1024


INPUT_ERROR = "INPUT_ERROR"
FACE_DETECTION_ERROR = "FACE_DETECTION_ERROR"
SEARCH_ERROR = "SEARCH_ERROR"
NO_MATCH = "NO_MATCH"
BLOCKCHAIN_ERROR = "BLOCKCHAIN_ERROR"
VERIFICATION_ERROR = "VERIFICATION_ERROR"
SUCCESS = "SUCCESS"


# ============================================================
# Display helpers
# ============================================================

def step_header(
    number: int,
    total: int,
    label: str,
) -> None:

    console.print(
        f"\n[bold cyan]"
        f"[{number}/{total}] {label}"
        f"[/bold cyan]"
    )


def ok(message: str) -> None:

    console.print(
        f"    [green]✓[/green] {message}"
    )


def bad(message: str) -> None:

    console.print(
        f"    [red]✗[/red] {message}"
    )


def note(message: str) -> None:

    console.print(
        f"    [yellow]⚠[/yellow] {message}"
    )


# ============================================================
# Input validation
# ============================================================

def validate_input_image(
    path: str,
) -> str:

    if not path:
        raise ValueError(
            "No image path provided."
        )

    if not os.path.isfile(path):
        raise ValueError(
            f"File not found: {path}"
        )

    extension = os.path.splitext(
        path
    )[1].lower()

    if extension not in VALID_EXTENSIONS:

        raise ValueError(
            f"Unsupported file extension "
            f"'{extension}'. Expected one of: "
            f"{', '.join(sorted(VALID_EXTENSIONS))}"
        )

    size = os.path.getsize(
        path
    )

    if size == 0:
        raise ValueError(
            "Input file is empty."
        )

    if size > MAX_INPUT_BYTES:

        raise ValueError(
            f"Input file is "
            f"{size / (1024 * 1024):.1f} MB, "
            f"exceeding the "
            f"{MAX_INPUT_BYTES / (1024 * 1024):.0f} MB limit."
        )

    with open(
        path,
        "rb",
    ) as file:

        raw = file.read()

    try:

        from PIL import Image, UnidentifiedImageError
        import io

        with Image.open(
            io.BytesIO(raw)
        ) as image:

            image.verify()

    except UnidentifiedImageError:

        raise ValueError(
            "File does not appear to be a valid image."
        )

    except Exception as exc:

        raise ValueError(
            f"Could not read image data: {exc}"
        )

    return hashlib.sha256(
        raw
    ).hexdigest()


# ============================================================
# Result handling
# ============================================================

def build_result_shell(
    image_path: str,
    threshold: float,
) -> dict[str, Any]:

    return {

        "pipeline_version": PIPELINE_VERSION,

        "status": None,

        "error_detail": None,

        "input": {
            "image_path": image_path,
            "sha256": None,
        },

        "face": None,

        "search": None,

        "match": None,

        "search_provider_metadata": None,

        "blockchain": None,

        "verification": None,

        "threshold": threshold,
    }


def save_json(
    result: dict[str, Any],
) -> str:

    filename = (
        f"results_{int(time.time())}.json"
    )

    with open(
        filename,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            default=str,
        )

    return filename


def finish(
    result: dict[str, Any],
    status: str,
    detail: Optional[str] = None,
    exit_code: int = 1,
) -> None:

    result["status"] = status

    if detail:
        result["error_detail"] = detail

    filename = save_json(
        result
    )

    console.print(
        f"\n[dim]"
        f"Full results saved -> {filename}"
        f"[/dim]"
    )

    if status != SUCCESS:

        console.print(
            f"[bold red]"
            f"FINAL RESULT: {status}"
            f"[/bold red]\n"
        )

    sys.exit(exit_code)


# ============================================================
# Main pipeline
# ============================================================

def run(
    image_path: str,
    threshold: float,
) -> None:

    result = build_result_shell(
        image_path,
        threshold,
    )

    TOTAL = 6

    # ========================================================
    # Input validation
    # ========================================================

    try:

        input_sha256 = (
            validate_input_image(
                image_path
            )
        )

    except ValueError as exc:

        console.print(
            f"[red]"
            f"Input validation failed:"
            f"[/red] {exc}"
        )

        finish(
            result,
            INPUT_ERROR,
            str(exc),
        )

        return

    result["input"]["sha256"] = (
        input_sha256
    )

    # ========================================================
    # [1/6] Face Detection + Encoding
    # ========================================================

    step_header(
        1,
        TOTAL,
        "Face Detection + Encoding",
    )

    try:

        detector = FaceDetector()

        face = detector.detect_and_encode(
            image_path
        )

    except Exception as exc:

        bad(
            f"Face detection failed: {exc}"
        )

        finish(
            result,
            FACE_DETECTION_ERROR,
            str(exc),
        )

        return

    embedding: list[float] = (
        face["embedding"]
    )

    embedding_len = face.get(
        "embedding_len",
        len(embedding),
    )

    if (
        not embedding
        or any(
            value != value
            for value in embedding[:8]
        )
    ):

        bad(
            "Embedding failed validation "
            "(empty or contains NaN values)."
        )

        finish(
            result,
            FACE_DETECTION_ERROR,
            "Invalid embedding returned by face detector.",
        )

        return

    result["face"] = {

        "face_count": face.get(
            "face_count",
            1,
        ),

        "embedding_len": embedding_len,

        "embedding_preview": [
            round(value, 4)
            for value in embedding[:6]
        ],

        "region": face.get(
            "region"
        ),

        "cropped_path": face.get(
            "cropped_path"
        ),
    }

    ok(
        f"Face detected "
        f"({result['face']['face_count']} found, using first)"
    )

    ok(
        f"{embedding_len}-dimensional embedding"
    )

    ok(
        f"Input SHA-256: {input_sha256}"
    )

    # ========================================================
    # [2/6] Web / Social Search
    # ========================================================

    step_header(
        2,
        TOTAL,
        "Web / Social Search",
    )

    try:

        search_result = run_search(
            face["face_bytes"]
        )

    except Exception as exc:

        bad(
            f"Search failed: {exc}"
        )

        finish(
            result,
            SEARCH_ERROR,
            str(exc),
        )

        return

    candidates = search_result.get(
        "candidates",
        [],
    )

    provider_value = search_result.get(
        "person_name"
    )

    provider_source = search_result.get(
        "name_source"
    )

    result["search"] = {

        "hosted_url": search_result.get(
            "hosted_url"
        ),

        "total_found": search_result.get(
            "total_found",
            len(candidates),
        ),

        "social_count": search_result.get(
            "social_count"
        ),

        "web_count": search_result.get(
            "web_count"
        ),

        "provider_related_result": provider_value,

        "provider_metadata_source": provider_source,

        "candidates": candidates[:5],
    }

    result["search_provider_metadata"] = {

        "value": provider_value,

        "source": provider_source,

        "display_value": (
            provider_value
            if provider_value
            else "Not available"
        ),
    }

    ok(
        "Search completed"
    )

    ok(
        f"{result['search']['total_found']} "
        f"candidates found "
        f"({result['search']['social_count']} social, "
        f"{result['search']['web_count']} other)"
    )

    if not candidates:

        bad(
            "No usable candidates returned "
            "by the search API."
        )

        finish(
            result,
            NO_MATCH,
            "No candidates with a comparable image were found.",
        )

        return

    # ========================================================
    # [3/6] Face Matching
    # ========================================================

    step_header(
        3,
        TOTAL,
        "Face Matching",
    )

    try:

        match_result = (
            find_matching_candidate(
                original_embedding=embedding,
                candidates=candidates,
                threshold=threshold,
            )
        )

    except Exception as exc:

        bad(
            f"Face matching crashed: {exc}"
        )

        finish(
            result,
            NO_MATCH,
            f"Matching stage raised an unexpected error: {exc}",
        )

        return

    result["match"] = {

        "matched": match_result[
            "matched"
        ],

        "similarity": match_result[
            "similarity"
        ],

        "threshold": threshold,

        "tried": match_result[
            "tried"
        ],

        "face_found_in": match_result[
            "face_found_in"
        ],

        "candidate": match_result[
            "candidate"
        ],
    }

    if not match_result["matched"]:

        if match_result["tried"] == 0:

            reason = (
                "No candidate exposed a usable "
                "image to compare against."
            )

        elif match_result["candidate"] is None:

            reason = (
                "No face was detected in any of the "
                f"{match_result['tried']} candidate "
                "image(s) checked."
            )

        else:

            reason = (
                f"Best candidate similarity "
                f"{match_result['similarity']:.4f} "
                f"did not reach the "
                f"{threshold:.2f} threshold."
            )

        bad(
            f"No qualifying match. {reason}"
        )

        finish(
            result,
            NO_MATCH,
            reason,
        )

        return

    candidate = match_result[
        "candidate"
    ]

    similarity = match_result[
        "similarity"
    ]

    ok(
        f"Best match: "
        f"{similarity * 100:.2f}%"
    )

    ok(
        f"Source: "
        f"{candidate.get('source', 'unknown')} "
        f"-- {candidate.get('url', '')}"
    )

    # ========================================================
    # Prominent demo output
    # ========================================================

    display_provider_value = (
        provider_value
        if provider_value
        else "Not available"
    )

    console.print(
        "\n"
        "[bold green]BEST MATCH FOUND[/bold green]\n"
        "\n"
        f"    Google Lens related result: "
        f"{display_provider_value}\n"
        f"    Similarity: "
        f"{similarity * 100:.2f}%\n"
        f"    Source: "
        f"{candidate.get('source', 'unknown')}\n"
        f"    URL: "
        f"{candidate.get('url', '')}"
    )

    if provider_value:

        note(
            "The related result is displayed directly "
            "from Google Lens provider metadata."
        )

    # ========================================================
    # [4/6] Evidence Fingerprint
    # ========================================================

    step_header(
        4,
        TOTAL,
        "Evidence Fingerprint",
    )

    try:

        verifier = BlockchainVerifier()

    except Exception as exc:

        bad(
            f"Could not initialize blockchain connection: {exc}"
        )

        finish(
            result,
            BLOCKCHAIN_ERROR,
            str(exc),
        )

        return

    data_hash = verifier.compute_hash(
        candidate,
        embedding,
    )

    result["evidence_hash"] = (
        data_hash.hex()
    )

    ok(
        "SHA-256 generated"
    )

    note(
        "Hash schema: "
        "sha256(sorted-JSON{url, title, source, "
        "face_fingerprint}). Timestamp is not included, "
        "so the same face + post produces the same evidence hash."
    )

    console.print(
        f"    [dim]{data_hash.hex()}[/dim]"
    )

    # ========================================================
    # [5/6] Blockchain Upload
    # ========================================================

    step_header(
        5,
        TOTAL,
        "Blockchain Upload",
    )

    already_existed = False

    try:

        tx = verifier.store(
            data_hash=data_hash,
            post_url=candidate["url"],
            similarity=similarity,
        )

    except Exception as exc:

        message = str(exc).lower()

        if (
            "already stored" in message
            or "already exists" in message
        ):

            note(
                "This evidence hash is already on-chain "
                "from a prior run."
            )

            already_existed = True

            tx = {
                "tx_hash": None,
                "block": None,
                "gas_used": 0,
                "status": 1,
                "explorer": "",
                "data_hash": data_hash.hex(),
            }

        elif "insufficient funds" in message:

            bad(
                "Wallet has insufficient Sepolia ETH "
                f"to submit the transaction: {exc}"
            )

            finish(
                result,
                BLOCKCHAIN_ERROR,
                "Insufficient funds for gas.",
            )

            return

        elif (
            "connect" in message
            or "timeout" in message
            or "rpc" in message
        ):

            bad(
                "Could not reach the Ethereum RPC endpoint: "
                f"{exc}"
            )

            finish(
                result,
                BLOCKCHAIN_ERROR,
                f"RPC connectivity error: {exc}",
            )

            return

        else:

            bad(
                f"Blockchain store failed: {exc}"
            )

            finish(
                result,
                BLOCKCHAIN_ERROR,
                str(exc),
            )

            return

    # --------------------------------------------------------
    # Reverted transaction handling
    # --------------------------------------------------------

    if (
        not already_existed
        and tx.get("status") != 1
    ):

        try:

            existing = verifier.verify(
                data_hash
            )

        except Exception:

            existing = {
                "exists": False
            }

        if existing.get("exists"):

            note(
                "Transaction reverted, but the evidence "
                "hash is already present on-chain."
            )

            already_existed = True

        else:

            bad(
                f"Transaction reverted "
                f"(status={tx.get('status')})."
            )

            result["blockchain"] = tx

            finish(
                result,
                BLOCKCHAIN_ERROR,
                "Transaction was reverted by the contract.",
            )

            return

    result["blockchain"] = {
        **tx,
        "already_existed": already_existed,
    }

    if already_existed:

        ok(
            "Evidence already verified on Ethereum Sepolia "
            "(idempotent re-run)"
        )

    else:

        ok(
            "Ethereum Sepolia transaction confirmed"
        )

        ok(
            f"TX hash: {tx['tx_hash']}"
        )

        ok(
            f"Block: #{tx['block']} "
            f"| Gas used: {tx['gas_used']:,}"
        )

        if tx.get("explorer"):

            ok(
                f"Explorer: {tx['explorer']}"
            )

    # ========================================================
    # [6/6] On-Chain Verification
    # ========================================================

    step_header(
        6,
        TOTAL,
        "On-Chain Verification",
    )

    try:

        verification = verifier.verify(
            data_hash
        )

    except Exception as exc:

        bad(
            f"On-chain read-back failed: {exc}"
        )

        finish(
            result,
            VERIFICATION_ERROR,
            str(exc),
        )

        return

    record_exists = bool(
        verification.get("exists")
    )

    url_matches = (
        verification.get("post_url")
        == candidate["url"]
    )

    on_chain_similarity = (
        verification.get("similarity")
    )

    checks = {

        "record_exists": record_exists,

        "url_matches": url_matches,

        "evidence_fingerprint_verified": (
            record_exists
            and url_matches
        ),
    }

    verified = all(
        checks.values()
    )

    result["verification"] = {

        **verification,

        "checks": checks,

        "verified": verified,
    }

    if record_exists:

        ok(
            "Record exists"
        )

    else:

        bad(
            "Record does not exist on-chain"
        )

    if url_matches:

        ok(
            "URL matches"
        )

    else:

        bad(
            "URL mismatch: "
            f"on-chain='{verification.get('post_url')}' "
            f"expected='{candidate['url']}'"
        )

    if on_chain_similarity is not None:

        ok(
            f"On-chain similarity recorded: "
            f"{float(on_chain_similarity) * 100:.2f}%"
        )

        ok(
            f"Current matching similarity: "
            f"{similarity * 100:.2f}%"
        )

    if not verified:

        finish(
            result,
            VERIFICATION_ERROR,
            f"On-chain verification checks failed: {checks}",
        )

        return

    ok(
        "Evidence fingerprint verified "
        "against the on-chain record"
    )

    # ========================================================
    # Final summary
    # ========================================================

    console.print()

    table = Table(
        box=box.ROUNDED,
        show_lines=True,
        title="Pipeline Summary",
    )

    table.add_column(
        "Stage",
        style="cyan",
    )

    table.add_column(
        "Result"
    )

    table.add_row(
        "Face detection",
        f"{embedding_len}-dimensional FaceNet embedding",
    )

    table.add_row(
        "Reverse image search",
        f"{result['search']['total_found']} candidates",
    )

    table.add_row(
        "Face match",
        (
            f"{similarity * 100:.2f}% "
            f"(best of {match_result['tried']})"
        ),
    )

    table.add_row(
        "Google Lens related result",
        display_provider_value,
    )

    table.add_row(
        "Evidence hash",
        result["evidence_hash"][:32] + "...",
    )

    table.add_row(
        "Blockchain",
        (
            "already verified"
            if already_existed
            else f"block #{tx['block']}"
        ),
    )

    table.add_row(
        "On-chain verification",
        "PASSED" if verified else "FAILED",
    )

    console.print(
        table
    )

    console.print(
        "\n[dim]"
        "The blockchain record proves that the evidence "
        "fingerprint was written to Ethereum Sepolia and "
        "later re-read consistently. The Google Lens "
        "related result shown above is provider-supplied "
        "metadata and is not independently inferred by "
        "this pipeline."
        "[/dim]"
    )

    console.print(
        "\n[bold green]"
        "FINAL RESULT: SUCCESS"
        "[/bold green]\n"
    )

    finish(
        result,
        SUCCESS,
        exit_code=0,
    )


# ============================================================
# Command-line entry point
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Face ID + Blockchain Verification Pipeline"
        )
    )

    parser.add_argument(
        "image",
        help=(
            "Path to the input photo "
            "(JPG/PNG/WEBP)"
        ),
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=(
            "Cosine similarity threshold, 0-1 "
            "(default: MATCH_THRESHOLD or "
            f"{COSINE_THRESHOLD})"
        ),
    )

    args = parser.parse_args()

    threshold = args.threshold

    if threshold is None:

        threshold = float(
            os.environ.get(
                "MATCH_THRESHOLD",
                COSINE_THRESHOLD,
            )
        )

    if not 0.0 <= threshold <= 1.0:

        parser.error(
            "--threshold must be between 0 and 1."
        )

    run(
        args.image,
        threshold,
    )