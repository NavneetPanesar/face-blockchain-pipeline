#!/usr/bin/env python3
"""
Face ID + Blockchain Verification Pipeline
=========================================
Face detection → encoding → genuine reverse-image search →
face-match verification (cosine similarity) → SHA-256 evidence →
Ethereum Sepolia store → on-chain verification.

Usage:
    python pipeline.py <path_to_photo>
"""

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv
from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich import box

load_dotenv()

from src.face   import FaceDetector
from src.search import ImageSearcher
from src.match  import find_matching_candidate
from src.chain  import BlockchainVerifier

console = Console()


# ── Helpers ─────────────────────────────────────────────────────────────────

def banner(text: str):
    console.print(Rule(f"[bold cyan]{text}[/bold cyan]"))


def ok(msg: str):
    console.print(f"  [green]✓[/green] {msg}")


def fail(msg: str):
    console.print(f"  [red]✗[/red] {msg}")
    sys.exit(1)


def warn(msg: str):
    console.print(f"  [yellow]⚠[/yellow] {msg}")


def load_env() -> dict:
    keys = [
        "SERPAPI_KEY",
        "IMGBB_KEY",
        "RPC_URL",
        "PRIVATE_KEY",
        "CONTRACT_ADDRESS",
    ]
    cfg     = {k: os.environ.get(k, "").strip() for k in keys}
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        console.print(f"\n[red]Missing environment variables:[/red] {', '.join(missing)}")
        console.print("Copy .env.example → .env and fill in all values.\n")
        sys.exit(1)
    return cfg


# ── Main pipeline ────────────────────────────────────────────────────────────

def run(image_path: str):
    if not os.path.isfile(image_path):
        console.print(f"[red]File not found:[/red] {image_path}")
        sys.exit(1)

    cfg     = load_env()
    results = {}                    # accumulated for JSON save at the end

    # ── Stage 1: Face detection & encoding ──────────────────────────────
    banner("Stage 1 — Face Detection & Encoding")
    detector = FaceDetector()
    try:
        face = detector.detect_and_encode(image_path)
    except Exception as e:
        fail(f"Face detection failed: {e}")

    results["face"] = {
        "embedding_len":     face["embedding_len"],
        "embedding_preview": face["embedding"][:6],
        "cropped_path":      face["cropped_path"],
        "face_count":        face["face_count"],
    }
    ok(f"Detected {face['face_count']} face(s) — using the first one")
    ok(f"Embedding: {face['embedding_len']}-dimensional vector (Facenet)")
    ok(f"Preview  : {[round(v, 4) for v in face['embedding'][:4]]} ...")
    ok(f"Cropped face saved → {face['cropped_path']}")

    # ── Stage 2: Reverse image search ───────────────────────────────────
    banner("Stage 2 — Reverse Image Search (Google Lens via SerpAPI)")
    searcher = ImageSearcher(cfg["SERPAPI_KEY"], cfg["IMGBB_KEY"])
    try:
        console.print("  → Uploading cropped face to temporary image host ...")
        search = searcher.search(face["face_bytes"])
    except Exception as e:
        fail(f"Search API call failed: {e}")

    results["search"] = {
        "hosted_url":  search["hosted_url"],
        "total_found": search["total_found"],
        "person_name": search["person_name"],
        "candidates":  search["candidates"][:5],    # save first 5 for JSON
    }

    ok(f"Face uploaded → {search['hosted_url']}")
    ok(f"Google Lens returned {search['total_found']} visual matches with thumbnails")

    if search["person_name"]:
        ok(f"Knowledge graph identified: {search['person_name']}")

    if not search["candidates"]:
        fail(
            "No visual matches with thumbnails were returned by Google Lens.\n"
            "  Try a clearer, better-lit photo, or one that already exists on the web."
        )

    social_count = sum(1 for c in search["candidates"] if c["is_social"])
    ok(f"Social media candidates : {social_count}")
    ok(f"Other web candidates    : {search['total_found'] - social_count}")
    console.print("  Top candidates:")
    for c in search["candidates"][:4]:
        tag = "[cyan]social[/cyan]" if c["is_social"] else "web"
        console.print(f"    [{tag}] {c['source']} — {c['title'][:55]}")

    # ── Stage 3: Face-match verification ────────────────────────────────
    banner("Stage 3 — Face Comparison (Cosine Similarity)")
    console.print(
        "  Downloading each thumbnail and comparing face embeddings ...\n"
        f"  Threshold: cosine similarity ≥ 0.60 (Facenet standard)\n"
    )
    try:
        match = find_matching_candidate(
            original_embedding=face["embedding"],
            candidates=search["candidates"],
        )
    except Exception as e:
        fail(f"Face comparison crashed unexpectedly: {e}")

    results["match"] = {
        "matched":       match["matched"],
        "similarity":    match["similarity"],
        "tried":         match["tried"],
        "face_found_in": match["face_found_in"],
        "candidate":     match["candidate"],
    }

    if not match["matched"]:
        console.print()
        fail(
            f"Face verification failed after checking {match['tried']} candidate(s).\n"
            "  None of the search results contained a face similar enough to the input.\n"
            "  Suggestion: use a photo of yourself that is already publicly visible\n"
            "  on LinkedIn, GitHub, or another indexed social media profile."
        )

    candidate = match["candidate"]
    sim_pct   = match["similarity"] * 100
    ok(f"FACE MATCHED! Cosine similarity = {match['similarity']:.4f} ({sim_pct:.2f} %)")
    ok(f"Matched post URL  : {candidate['url']}")
    ok(f"Source            : {candidate['source']}")
    ok(f"Title             : {candidate['title'][:65]}")
    ok(f"Face image found in: {match['face_found_in']}")

    # ── Stage 4: Create evidence record ─────────────────────────────────
    banner("Stage 4 — SHA-256 Evidence Record")
    chain = BlockchainVerifier(
        cfg["RPC_URL"], cfg["PRIVATE_KEY"], cfg["CONTRACT_ADDRESS"]
    )
    info = chain.info()
    ok(f"Connected   : chain ID {info['chain_id']}")
    ok(f"Wallet      : {info['address']}")
    ok(f"Balance     : {info['balance']:.6f} ETH")

    data_hash = chain.compute_hash(candidate, face["embedding"])
    results["data_hash"] = data_hash.hex()
    ok(
        f"SHA-256 hash of (post URL + face fingerprint + timestamp):\n"
        f"    {data_hash.hex()}"
    )

    # ── Stage 5: Blockchain upload ───────────────────────────────────────
    banner("Stage 5 — Uploading to Ethereum Sepolia")
    console.print("  → Sending transaction ... (may take 15–60 seconds)")
    try:
        tx = chain.store(data_hash, candidate["url"], match["similarity"])
    except Exception as e:
        fail(f"Blockchain store failed: {e}")

    results["blockchain"] = tx
    status_label = "[green]CONFIRMED[/green]" if tx["status"] == 1 else "[red]REVERTED[/red]"
    ok(f"Transaction : {status_label}")
    ok(f"TX hash     : {tx['tx_hash']}")
    ok(f"Block       : #{tx['block']}")
    ok(f"Gas used    : {tx['gas_used']:,}")
    if tx["explorer"]:
        ok(f"Etherscan   : {tx['explorer']}")

    if tx["status"] != 1:
        fail("Transaction was reverted by the contract (hash may already be stored).")

    # ── Stage 6: On-chain verification ──────────────────────────────────
    banner("Stage 6 — On-Chain Verification")
    console.print("  → Reading the record back from the contract ...")
    try:
        v = chain.verify(data_hash)
    except Exception as e:
        fail(f"Verification read failed: {e}")

    results["verification"] = v

    if not v["exists"]:
        fail("Hash was NOT found on-chain immediately after writing — something went wrong.")

    ok(f"Record found on-chain ✓")
    ok(f"Stored at   : {v['ts_human']}")
    ok(f"Submitter   : {v['submitter']}")
    ok(f"Post URL    : {v['post_url']}")
    ok(f"Similarity  : {v['similarity'] * 100:.2f} %")

    # ── Summary ──────────────────────────────────────────────────────────
    console.print()
    t = Table(title="Pipeline Summary", box=box.ROUNDED, show_lines=True)
    t.add_column("Stage",               style="cyan", min_width=20)
    t.add_column("Status",              min_width=14)
    t.add_column("Key detail")

    t.add_row(
        "Face detection",
        "[green]✓ done[/green]",
        f"{face['embedding_len']}-dim Facenet embedding",
    )
    t.add_row(
        "Reverse image search",
        "[green]✓ done[/green]",
        f"{search['total_found']} candidates ({social_count} social media)",
    )
    t.add_row(
        "Face match verification",
        "[green]✓ matched[/green]",
        f"similarity {match['similarity'] * 100:.2f} % (threshold 60 %)",
    )
    t.add_row(
        "SHA-256 evidence",
        "[green]✓ created[/green]",
        results["data_hash"][:32] + "...",
    )
    t.add_row(
        "Blockchain upload",
        "[green]✓ confirmed[/green]" if tx["status"] == 1 else "[red]✗ failed[/red]",
        f"Block #{tx['block']}",
    )
    t.add_row(
        "On-chain verification",
        "[green]✓ verified[/green]" if v["exists"] else "[red]✗ not found[/red]",
        v["ts_human"],
    )

    console.print(t)

    # ── Save JSON ─────────────────────────────────────────────────────────
    fname = f"results_{int(time.time())}.json"
    with open(fname, "w") as f:
        json.dump(results, f, indent=2, default=str)
    console.print(f"\n[dim]Full results saved → {fname}[/dim]\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Face ID + Blockchain Verification Pipeline"
    )
    parser.add_argument("image", help="Path to the input photo (JPG or PNG)")
    args = parser.parse_args()
    run(args.image)
