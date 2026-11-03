"""Routine area: the map pattern that separate posts reveal together."""
import math
import statistics
import threading
import time
from functools import lru_cache

import requests

Point = tuple[float, float]  # lat, lon
METERS_PER_DEGREE = 111_000
CLUSTER_M = 1_000  # Posts this close suggest a regular spot, not a one-off trip.
OUTLIER_M = 50_000  # A pin this far from the group is treated as a geocoding mistake.
NOMINATIM_PAUSE_S = 1.1  # Nominatim's usage policy allows one request per second.
_NOMINATIM_LOCK = threading.Lock()  # Parallel agents must still share that one-per-second limit.


def distance_m(a: Point, b: Point) -> float:
    """Return approximate meters between two nearby points."""
    x = (a[1] - b[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(a[0] - b[0], x) * METERS_PER_DEGREE


def is_near_group(point: Point, points: list[Point]) -> bool:
    """Return True unless a point sits far from the group's median location."""
    middle = (
        statistics.median(p[0] for p in points),
        statistics.median(p[1] for p in points),
    )
    return distance_m(point, middle) <= OUTLIER_M


def routine_area(points: list[Point]) -> dict | None:
    """Return the circle around 2+ nearby points, or None if there is no pattern."""
    near = [p for p in points if is_near_group(p, points)]
    if len(near) < 2:
        return None
    center = (sum(p[0] for p in near) / len(near), sum(p[1] for p in near) / len(near))
    return {
        "lat": center[0],
        "lon": center[1],
        "radius_m": round(max(distance_m(p, center) for p in near)),
        "places": len(near),
    }


def tightest_cluster(points: dict[int, Point]) -> list[int]:
    """Return the largest set of posts within CLUSTER_M of one post (ties: closest)."""
    best: list[int] = []
    best_spread = float("inf")
    for post, point in points.items():
        group = [k for k, v in points.items() if distance_m(point, v) <= CLUSTER_M]
        spread = max(distance_m(point, points[k]) for k in group)
        if len(group) > len(best) or (len(group) == len(best) and spread < best_spread):
            best, best_spread = sorted(group), spread
    return best if len(best) >= 2 else []


def posts_to_fix(points: dict[int, Point]) -> list[int]:
    """Pick the fewest posts to remove so no two remaining posts form a cluster."""
    remaining = dict(points)
    picks: list[int] = []
    while cluster := tightest_cluster(remaining):
        def left_after(post: int) -> int:
            return len(tightest_cluster({k: v for k, v in remaining.items() if k != post}))

        pick = min(cluster, key=left_after)
        picks.append(pick)
        del remaining[pick]
    return picks


def search_names(place: str) -> list[str]:
    """Return the place name, then shorter forms that drop one middle part.

    Never falls back to the bare "City, State": that would pin every unknown
    place on the city center and fake a tight cluster.
    """
    parts = [p.strip() for p in place.split(",") if p.strip()]
    names = [", ".join(parts)]
    if len(parts) > 3:
        names.append(", ".join([parts[0], *parts[-2:]]))
        names.append(", ".join(parts[1:]))
    return names


@lru_cache(maxsize=512)
def _nominatim(name: str) -> Point | None:
    """Look up one name; raises on network errors, so failures are not cached."""
    with _NOMINATIM_LOCK:
        time.sleep(NOMINATIM_PAUSE_S)
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": name, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": "breadcrumbs-hackathon-demo"},
            timeout=15,
        )
    response.raise_for_status()
    hits = response.json()
    return (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else None


def geocode(place: str) -> Point | None:
    """Return (lat, lon) for a place from OpenStreetMap Nominatim, or None."""
    if not place:
        return None
    for name in search_names(place):
        try:
            point = _nominatim(name)
        except (requests.RequestException, ValueError):
            return None
        if point:
            return point
    return None
