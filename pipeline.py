#!/usr/bin/env python3
"""
Face ID + Blockchain Verification Pipeline
Usage: python pipeline.py <image_path>
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich import box

load_dotenv()

from src.face   import FaceDetector
from src.search import ImageSearcher
from src.chain  import BlockchainVerifier

console = Console()


def banner(text: str):
    console.print(Rule(f"[bold cyan]{text}[/bold cyan]"))


def ok(msg: str):
    console.print(f"  [green]✓[/green] {msg}")


def err(msg: str):
    console.print(f"  [red]✗[/red] {msg}")


def load_env() -> dict:
    keys = ["SERPAPI_KEY", "IMGBB_KEY", "RPC_URL", "PRIVATE_KEY", "CONTRACT_ADDRESS"]
    cfg  = {k: os.environ.get(k, "") for k in keys}
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        console.print(f"[red]Missing env vars: {', '.join(missing)}[/red]")
        console.print("Copy .env.example → .env and fill in the values.")
        sys.exit(1)
    return cfg


def run(image_path: str):
    if not os.path.exists(image_path):
        console.print(f"[red]File not found: {image_path}[/red]")
        sys.exit(1)

    cfg = load_env()
    out = {}                            # accumulate results for JSON save

    # ── Stage 1: Face detection ──────────────────────────────────────────
    banner("Stage 1 — Face Detection & Encoding")
    detector = FaceDetector()
    try:
        face = detector.detect_and_encode(image_path)
        out["face"] = {
            "embedding_len": face["embedding_len"],
            "embedding_preview": face["embedding"][:6],
            "cropped_path": face["cropped_path"],
        }
        ok(f"Face detected — {face['embedding_len']}-dim embedding")
        ok(f"Preview: {[round(v,4) for v in face['embedding'][:4]]} ...")
        ok(f"Cropped face saved → {face['cropped_path']}")
    except Exception as e:
        err(f"Face detection failed: {e}")
        sys.exit(1)

    # ── Stage 2: Reverse image search ───────────────────────────────────
    banner("Stage 2 — Reverse Image Search")
    searcher = ImageSearcher(cfg["SERPAPI_KEY"], cfg["IMGBB_KEY"])
    try:
        console.print("  → Uploading cropped face to temporary host...")
        result = searcher.search(face["face_bytes"])
        out["search"] = {k: v for k, v in result.items() if k != "all_matches"}

        ok(f"Uploaded face → {result['hosted_url']}")
        ok(f"Google Lens returned {result['total_matches']} visual matches")

        if result["found"]:
            best = result["best"]
            tag  = "[green]social media[/green]" if best["is_social"] else "web page"
            ok(f"Best match ({tag}): {best['title'][:55]}")
            ok(f"URL: {best['url']}")
            if result["social_matches"]:
                ok(f"Social media hits: {len(result['social_matches'])}")
                for sm in result["social_matches"][:3]:
                    console.print(f"       • {sm['url']}")
            if result["person_name"]:
                ok(f"Knowledge graph: {result['person_name']}")
        else:
            console.print("  [yellow]⚠[/yellow] No visual matches found.")
            console.print("      Storing hosted image URL as the record instead.")
            result["best"] = {
                "url":       result["hosted_url"],
                "title":     "No match found",
                "source":    "none",
                "is_social": False,
            }
    except Exception as e:
        err(f"Search failed: {e}")
        sys.exit(1)

    # ── Stage 3: Blockchain upload ───────────────────────────────────────
    banner("Stage 3 — Blockchain Upload")
    chain = BlockchainVerifier(cfg["RPC_URL"], cfg["PRIVATE_KEY"], cfg["CONTRACT_ADDRESS"])
    info  = chain.info()
    ok(f"Connected — chain ID {info['chain_id']}, wallet {info['address']}")
    ok(f"Balance: {info['balance']:.6f} ETH")

    best      = result["best"]
    data_hash = chain.compute_hash(best)
    out["data_hash"] = data_hash.hex()
    ok(f"SHA256 of post data: {data_hash.hex()}")

    try:
        tx = chain.store(data_hash, best["url"])
        out["blockchain"] = tx
        status = "[green]confirmed[/green]" if tx["status"] == 1 else "[red]failed[/red]"
        ok(f"Transaction {status}")
        ok(f"TX Hash  : {tx['tx_hash']}")
        ok(f"Block    : #{tx['block']}")
        ok(f"Gas used : {tx['gas_used']:,}")
        if tx["explorer"]:
            ok(f"Explorer : {tx['explorer']}")
    except Exception as e:
        err(f"Blockchain store failed: {e}")
        sys.exit(1)

    # ── Stage 4: On-chain verification ──────────────────────────────────
    banner("Stage 4 — On-Chain Verification")
    try:
        v = chain.verify(data_hash)
        out["verification"] = {k: str(v[k]) for k in v}
        if v["exists"]:
            ts_human = datetime.fromtimestamp(v["timestamp"], tz=timezone.utc)
            ok(f"Hash found on-chain ✓")
            ok(f"Stored at  : {ts_human.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            ok(f"Submitter  : {v['submitter']}")
            ok(f"Post URL   : {v['post_url']}")
        else:
            err("Hash NOT found — something went wrong.")
    except Exception as e:
        err(f"Verification failed: {e}")

    # ── Summary table ────────────────────────────────────────────────────
    console.print()
    t = Table(title="Pipeline Summary", box=box.ROUNDED, show_lines=True)
    t.add_column("Stage",   style="cyan",  min_width=18)
    t.add_column("Status",  min_width=12)
    t.add_column("Key detail")

    t.add_row("Face detection",
              "[green]✓ done[/green]",
              f"{out['face']['embedding_len']}-dim embedding")

    sr = out.get("search", {})
    t.add_row("Web search",
              "[green]✓ found[/green]" if sr.get("found") else "[yellow]⚠ no match[/yellow]",
              (sr.get("best") or {}).get("url", "N/A")[:50])

    bc = out.get("blockchain", {})
    t.add_row("Blockchain upload",
              "[green]✓ confirmed[/green]" if bc.get("status") == 1 else "[red]✗ failed[/red]",
              f"Block #{bc.get('block', '?')}")

    vr = out.get("verification", {})
    t.add_row("On-chain verify",
              "[green]✓ verified[/green]" if vr.get("exists") == "True" else "[red]✗ not found[/red]",
              f"Hash: {out.get('data_hash','')[:24]}...")

    console.print(t)

    # ── Save JSON ────────────────────────────────────────────────────────
    fname = f"results_{int(time.time())}.json"
    with open(fname, "w") as f:
        json.dump(out, f, indent=2, default=str)
    console.print(f"\n[dim]Full results saved → {fname}[/dim]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Face ID + Blockchain Pipeline")
    parser.add_argument("image", help="Input photo path")
    args = parser.parse_args()
    run(args.image)
