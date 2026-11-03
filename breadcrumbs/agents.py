"""Attacker and defender agents: red-team the user's own photos, then fix them."""
import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI
from PIL import Image

from breadcrumbs.config import BASE_URL, SPARK_MODEL, load_key
from breadcrumbs.geo import distance_m, geocode
from breadcrumbs.sam import blur_where, clue_boxes, clue_mask
from breadcrumbs.spark import _image_part, locate_photo, parse_json

MAX_STEPS = 8
MAX_ROUNDS = 5
BOX_PADDING = 0.15
CLUE_NOUNS = ["sign", "letters", "logo"]  # SAM boxes these tightly; Spark boxes often miss.
BLUR_PASSES = 2
MIN_PATTERN_POSTS = 2  # One public place is not a pattern; two linked posts are.
MIN_THEORY_CONFIDENCE = 0.7
WRONG_CITY_M = 25_000  # This far from the first answer, the attacker is misled.

ATTACKER_PROMPT = """This is a defensive red-team exercise on photos the user uploaded of their
own posts, so they can learn what to remove. Work out which public neighborhood or district these
posts point to as a group. Work step by step with your tools: read visible public signs and
landmarks, look things up, map them, and compare distances.
Rules: name only public places and a general area. Never identify, describe, or guess anything
about a person. Never guess a home, a school a child attends, or a schedule.
Finish by calling submit_theory. If the evidence is weak, submit an empty area."""

DEFENDER_PROMPT = """You protect a user's privacy. An attacker reviewing their public posts
concluded: {area}
Evidence posts: {evidence}
Attacker's reasoning: {reasoning}
Choose the fewest changes that break this reasoning. Prefer "blur" for one readable sign or
logo. Use "hide" when the whole scene gives the place away. Only use evidence posts.
Return only JSON: {{"moves": [{{"post": <number>, "action": "blur" or "hide", "why": "<short>"}}]}}"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for a public place, business, or sign.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "map_place",
            "description": "Get map coordinates for a public place name.",
            "parameters": {
                "type": "object",
                "properties": {"place": {"type": "string"}},
                "required": ["place"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "measure_distance",
            "description": "Get the distance in km between two public places.",
            "parameters": {
                "type": "object",
                "properties": {"place_a": {"type": "string"}, "place_b": {"type": "string"}},
                "required": ["place_a", "place_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_theory",
            "description": "Submit the final conclusion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "Public area, or empty"},
                    "city": {"type": "string", "description": "That area's 'City, State'"},
                    "confidence": {"type": "number"},
                    "evidence_posts": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Post numbers that support the area",
                    },
                    "reasoning": {"type": "string"},
                },
                "required": ["area", "city", "confidence", "evidence_posts", "reasoning"],
            },
        },
    },
]


def _client() -> OpenAI:
    return OpenAI(api_key=load_key(), base_url=BASE_URL)


def search_web(query: str) -> str:
    """Answer a query with Spark's hosted web search on the Responses API."""
    reply = _client().responses.create(
        model=SPARK_MODEL,
        tools=[{"type": "web_search"}],
        input=f"Answer in two short sentences using web search: {query}",
    )
    return reply.output_text[:800]


def run_tool(name: str, args: dict) -> str:
    """Run one attacker tool and return its text result."""
    if name == "search_web":
        return search_web(str(args.get("query", "")))
    if name == "map_place":
        point = geocode(str(args.get("place", "")))
        return f"Found at {point}" if point else "Not found on the map"
    if name == "measure_distance":
        a, b = geocode(str(args.get("place_a", ""))), geocode(str(args.get("place_b", "")))
        return f"{distance_m(a, b) / 1000:.1f} km" if a and b else "Could not map both places"
    return "Unknown tool"


def clean_theory(raw: dict, posts_allowed: set[int]) -> dict:
    """Validate a theory; a weak theory counts as the attacker finding nothing."""
    try:
        confidence = float(raw.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    posts = raw.get("evidence_posts", [])
    posts = posts if isinstance(posts, list) else []
    numbers = set()
    for p in posts:
        try:
            numbers.add(int(p))
        except (TypeError, ValueError):
            continue
    valid = sorted(numbers & posts_allowed)
    area = str(raw.get("area") or "") if confidence >= MIN_THEORY_CONFIDENCE else ""
    return {
        "area": area,
        "city": str(raw.get("city") or "") if area else "",
        "confidence": confidence,
        "evidence": valid if area else [],
        "reasoning": str(raw.get("reasoning") or ""),
    }


def attack(posts: dict[int, Image.Image]) -> Iterator[dict]:
    """Investigate visible posts (keyed by post number); end with a 'theory' event."""
    content: list = [{"type": "text", "text": ATTACKER_PROMPT}]
    for number, image in posts.items():
        content += [{"type": "text", "text": f"Post {number}:"}, _image_part(image)]
    allowed = set(posts)
    messages: list = [{"role": "user", "content": content}]
    client = _client()
    for step in range(1, MAX_STEPS + 1):
        reply = client.chat.completions.create(
            model=SPARK_MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
        )
        message = reply.choices[0].message
        if not message.tool_calls:  # Prose is not a conclusion; ask for one.
            messages.append({"role": "assistant", "content": message.content or ""})
            messages.append({"role": "user", "content": "Use your tools, then call submit_theory."})
            continue
        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if name == "submit_theory":
                yield {"kind": "theory", **clean_theory(args, allowed)}
                return
            result = run_tool(name, args)
            yield {"kind": "tool", "step": step, "tool": name, "args": args, "result": result}
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        if step == MAX_STEPS - 1:
            messages.append({"role": "user", "content": "Last step: call submit_theory now."})
    yield {"kind": "note", "step": MAX_STEPS, "text": "Step limit reached."}
    yield {"kind": "theory", **clean_theory({}, allowed), "timed_out": True}


def clean_moves(raw: list, evidence: list[int]) -> list[dict]:
    """Keep valid moves on evidence posts; fall back to hiding the first evidence post."""
    moves: list[dict] = []
    for move in raw if isinstance(raw, list) else []:
        if not isinstance(move, dict):
            continue
        post, action = move.get("post"), move.get("action")
        if post in evidence and action in ("blur", "hide"):
            if post not in [m["post"] for m in moves]:
                moves.append({"post": post, "action": action, "why": str(move.get("why", ""))})
    return moves or [{"post": evidence[0], "action": "hide", "why": "Fallback move."}]


def plan_defense(theory: dict) -> list[dict]:
    """Ask Spark for the smallest set of changes that breaks the attacker's reasoning."""
    prompt = DEFENDER_PROMPT.format(
        area=theory["area"], evidence=theory["evidence"], reasoning=theory["reasoning"]
    )
    reply = _client().chat.completions.create(
        model=SPARK_MODEL, messages=[{"role": "user", "content": prompt}]
    )
    parsed = parse_json(reply.choices[0].message.content or "")
    return clean_moves(parsed.get("moves", []), theory["evidence"])


def blur_clue(image: Image.Image) -> Image.Image | None:
    """Blur every clue SAM finds until Spark can't name the place; None if it still can."""
    nouns = [*CLUE_NOUNS, locate_photo(image)["noun"]]
    changed = image
    for _ in range(BLUR_PASSES):
        boxes = clue_boxes(changed, nouns)
        if boxes:
            mask = clue_mask(changed, boxes)
            for box in boxes:  # A sign's box can hold text its object mask misses.
                left, top, right, bottom = padded(box, changed.size)
                mask[top:bottom, left:right] = True
            changed = blur_where(changed, mask)
        finding = locate_photo(changed)
        if not finding["place"]:
            return None if changed is image else changed
        nouns = [finding["noun"]]
    return None


def padded(box: tuple, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Grow a box by BOX_PADDING on each side, staying inside the image."""
    left, top, right, bottom = box
    pad_x = int((right - left) * BOX_PADDING)
    pad_y = int((bottom - top) * BOX_PADDING)
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(size[0], right + pad_x),
        min(size[1], bottom + pad_y),
    )


def safe_blur(image: Image.Image) -> Image.Image | None:
    """Blur a post's clues; None means it must be hidden instead."""
    try:
        return blur_clue(image)
    except Exception:  # A SAM or Spark failure must not leave the clue visible.
        return None


def match_winner(theory: dict) -> str | None:
    """Return who a round decided; running out of steps proves nothing either way."""
    if theory.get("timed_out"):
        return "inconclusive"
    if len(theory.get("evidence", [])) < MIN_PATTERN_POSTS or not theory.get("area"):
        return "defender"
    return None


def is_misled(first: tuple | None, now: tuple | None) -> bool:
    """Return True if the attacker's city moved far from its first, unblurred answer."""
    return bool(first and now) and distance_m(first, now) >= WRONG_CITY_M


def play_match(images: list[Image.Image]) -> Iterator[dict]:
    """Yield a full attacker-vs-defender match over the user's own photos."""
    posts = {i + 1: image for i, image in enumerate(images)}
    blurred_already: set[int] = set()
    first_city = None
    for round_number in range(1, MAX_ROUNDS + 1):
        yield {"kind": "round", "round": round_number, "posts": sorted(posts)}
        theory: dict = {}
        for event in attack(posts):
            yield event
            if event["kind"] == "theory":
                theory = event
        winner = match_winner(theory)
        if winner:
            yield {
                "kind": "end",
                "winner": winner,
                "round": round_number,
                "leftover": theory.get("area", ""),
                "images": posts,
            }
            return
        city = geocode(theory.get("city", ""))
        first_city = first_city or city
        if is_misled(first_city, city):
            yield {
                "kind": "end",
                "winner": "defender",
                "misled": True,
                "round": round_number,
                "leftover": theory["city"],
                "images": posts,
            }
            return
        if round_number == MAX_ROUNDS:
            break
        moves = []
        for move in plan_defense(theory):
            if move["post"] in posts:
                if move["post"] in blurred_already:  # Blurring it once did not stop the attacker.
                    move = {**move, "action": "hide", "why": "Still used after blurring."}
                moves.append(move)
        with ThreadPoolExecutor(max(1, len(moves))) as pool:
            blurs = list(pool.map(
                lambda m: safe_blur(posts[m["post"]]) if m["action"] == "blur" else None, moves
            ))
        for move, image in zip(moves, blurs):
            if image is None:
                del posts[move["post"]]
            else:
                posts[move["post"]] = image
                blurred_already.add(move["post"])
            done = "hidden" if image is None else "blurred"
            yield {"kind": "move", **move, "done": done, "image": image}
    yield {
        "kind": "end",
        "winner": "attacker",
        "round": MAX_ROUNDS,
        "leftover": theory.get("area", ""),
        "images": posts,
    }
