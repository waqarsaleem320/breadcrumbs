"""Tipping point: replay the feed in posting order and find the post that gave it away."""
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from breadcrumbs.agents import MIN_PATTERN_POSTS, attack

WORKERS = 5
MAX_FEED = 8  # Runs grow with every post; later posts add little.
TIPPING_KEYS = ("area", "city", "confidence", "evidence", "reasoning", "tools", "timed_out", "failed")


def final_theory(posts: dict[int, Image.Image]) -> dict:
    """Run one attacker investigation and return its theory with its tool count."""
    tools, theory = 0, {}
    try:
        for event in attack(posts):
            tools += event["kind"] == "tool"
            if event["kind"] == "theory":
                theory = event
    except Exception:  # One failed run must not sink the others; it is shown as failed.
        return {"tools": tools, "failed": True}
    return {**theory, "tools": tools}


def level(theory: dict) -> str:
    """Name how exposed a theory shows the feed to be."""
    if theory.get("failed"):
        return "failed"
    if not theory.get("area"):
        return "hidden"
    return "pattern" if len(theory.get("evidence", [])) >= MIN_PATTERN_POSTS else "place"


def scan_feed(images: list[Image.Image]) -> list[dict]:
    """Attack the first 1, 2, ... N posts in parallel; one row per feed length."""
    images = images[:MAX_FEED]
    feeds = [{n + 1: image for n, image in enumerate(images[:k])} for k in range(1, len(images) + 1)]
    with ThreadPoolExecutor(WORKERS) as pool:
        theories = list(pool.map(final_theory, feeds))
    return [
        {"posts": k, "level": level(t), **{key: t.get(key) for key in TIPPING_KEYS}}
        for k, t in enumerate(theories, start=1)
    ]


def tipping_post(rows: list[dict]) -> dict | None:
    """Return the first row where posts link into a pattern, else where a place is named."""
    for wanted in ("pattern", "place"):
        for row in rows:
            if row["level"] == wanted:
                return row
    return None
