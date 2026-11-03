"""Streamlit views for the tipping point and the attacker-vs-defender match."""
import json
import time
from collections.abc import Iterator
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

from breadcrumbs import theme
from breadcrumbs.agents import play_match
from breadcrumbs.tipping import tipping_post

SAMPLE_DIR = Path(__file__).parent.parent / "demo" / "match"
SAMPLE_MATCH = SAMPLE_DIR / "match.json"
REPLAY_PAUSE_S = 0.25


def saved_match() -> Iterator[dict]:
    """Replay a saved real match, paced for reading."""
    for event in json.loads(SAMPLE_MATCH.read_text(encoding="utf-8")):
        time.sleep(REPLAY_PAUSE_S)
        yield event


def move_photo(event: dict, is_sample: bool) -> Image.Image | None:
    """Return the blurred photo a defender move made, if any."""
    if is_sample:
        return Image.open(SAMPLE_DIR / event["photo"]) if event.get("photo") else None
    return event.get("image")


def after_photos(log: list[dict], is_sample: bool) -> dict[int, Image.Image]:
    """Return the posts still visible after the match, keyed by post number."""
    if is_sample:
        return {n: Image.open(SAMPLE_DIR / f"post{n}.jpg") for n in log[-1].get("left", [])}
    return st.session_state.get("match_after", {})


def dimmed(image: Image.Image) -> Image.Image:
    """Return a darkened copy, for a hidden post."""
    return Image.blend(image, Image.new("RGB", image.size), 0.8)


def tile(image: Image.Image) -> Image.Image:
    """Crop to one shape so the before/after grid lines up."""
    return ImageOps.fit(image, (480, 360))


def show_tipping(rows: list[dict], images: list[Image.Image]) -> None:
    """Headline the post that gave the feed away, then chart every feed length."""
    tipping = tipping_post(rows)
    if tipping:
        k = tipping["posts"]
        first = next(r for r in rows if r["level"] in ("place", "pattern"))
        if tipping["level"] == "pattern":
            linked = ", ".join(str(p) for p in tipping["evidence"])
            title = f"Post {k} turned your posts into a pattern"
            detail = f"Posts {linked} together pointed to {tipping['area']}."
            if first["posts"] < k:
                detail += f" Post {first['posts']} alone already named {first['area']}."
            elif k > 1:
                detail += f" Before post {k}, the attacker could not name an area with confidence."
        else:
            title = f"Post {k} is where you became findable"
            detail = f"That post alone pointed to {tipping['area']}."
        st.markdown(theme.verdict(title, detail), unsafe_allow_html=True)
    else:
        detail = "At no point could the attacker name an area from your posts."
        st.markdown(theme.verdict("No post gave you away", detail, safe=True), unsafe_allow_html=True)
    chart_column, photo_column = st.columns([3, 1])
    with chart_column:
        st.markdown(theme.tipping_chart(rows, tipping and tipping["posts"]), unsafe_allow_html=True)
    if tipping:
        with photo_column:
            st.image(images[tipping["posts"] - 1], caption=f"Post {tipping['posts']}")


def round_label(event: dict) -> str:
    """Return a round's heading."""
    count = len(event["posts"])
    return f"Round {event['round']}: {count} post{'s' if count != 1 else ''}"


def show_event(box, event: dict, images: list[Image.Image], is_sample: bool) -> None:
    """Write one trace line, plus before/after photos for a blur."""
    box.markdown(theme.trace_line(event), unsafe_allow_html=True)
    photo = move_photo(event, is_sample) if event["kind"] == "move" else None
    if photo:
        box.image([images[event["post"] - 1], photo], width=260, caption=["Before", "After blur"])


def run_match(images: list[Image.Image], is_sample: bool) -> None:
    """Show a match as it happens, keep its log, then rerun to show the result."""
    events = saved_match() if is_sample else play_match(images)
    if is_sample:
        st.caption("Replay of a saved real match. Live matches take several minutes.")
    else:
        st.caption("Live match: this takes several minutes. Clicking elsewhere stops it.")
    log: list[dict] = []
    box = None
    try:
        for event in events:
            log.append({k: v for k, v in event.items() if k != "images"})
            if event["kind"] == "end" and not is_sample:
                st.session_state.match_after = event["images"]
            if box and event["kind"] in ("round", "end"):
                box.update(state="complete", expanded=False)
            if event["kind"] == "round":
                box = st.status(round_label(event), expanded=True)
            elif event["kind"] != "end" and box:
                show_event(box, event, images, is_sample)
    except Exception as error:
        st.error(f"The match did not finish, so nothing is cleared. {error}")
        return
    st.session_state.match = log
    st.rerun()


def round_summary(events: list[dict]) -> str:
    """Name what a round decided, for its heading."""
    theory = next((e for e in events if e["kind"] == "theory"), {})
    moves = [f"{e['done']} post {e['post']}" for e in events if e["kind"] == "move"]
    found = f"attacker found {theory['area']}" if theory.get("area") else "attacker found nothing"
    return found + (f", defender {', '.join(moves)}" if moves else "")


def show_trace(log: list[dict], images: list[Image.Image], is_sample: bool) -> None:
    """Re-draw every round of a finished match; the last one stays open."""
    rounds: list[tuple[dict, list[dict]]] = []
    for event in log:
        if event["kind"] == "round":
            rounds.append((event, []))
        elif event["kind"] != "end" and rounds:
            rounds[-1][1].append(event)
    for number, (start, events) in enumerate(rounds, start=1):
        box = st.expander(f"{round_label(start)}: {round_summary(events)}", expanded=number == len(rounds))
        for event in events:
            show_event(box, event, images, is_sample)


def show_match_result(log: list[dict], images: list[Image.Image], is_sample: bool) -> None:
    """Show the rounds, who won, and what it cost."""
    show_trace(log, images, is_sample)
    end = log[-1]
    moves = [e for e in log if e["kind"] == "move"]
    tools = sum(e["kind"] == "tool" for e in log)
    st.markdown(theme.match_tiles(end["round"], tools, len(moves)), unsafe_allow_html=True)
    after = after_photos(log, is_sample)
    blurred = {e["post"] for e in moves if e["done"] == "blurred"} & set(after)
    cost = (
        f" Privacy cost: {len(blurred)} blurred, {len(images) - len(after)} hidden, "
        f"{len(after) - len(blurred)} unchanged."
    )
    leftover = end.get("leftover") or "nothing"
    if end.get("misled"):
        detail = f"The attacker now points to the wrong city: {leftover}."
        st.markdown(theme.verdict("Attacker misled", detail + cost, safe=True), unsafe_allow_html=True)
    elif end["winner"] == "defender":
        detail = "The attacker could no longer link your posts to one area."
        st.markdown(theme.verdict("Pattern broken", detail + cost, safe=True), unsafe_allow_html=True)
    elif end["winner"] == "inconclusive":
        detail = "The attacker ran out of steps, so this run proves nothing either way."
        st.markdown(theme.verdict("No result", detail), unsafe_allow_html=True)
    else:
        detail = f"The attacker still reached: {leftover}. Consider keeping more posts private."
        st.markdown(theme.verdict("Attacker still wins", detail), unsafe_allow_html=True)
    st.caption("A result for this model on this run. It does not guarantee safety from people.")
    st.subheader("Your posts after the match")
    for number, (column, image) in enumerate(zip(st.columns(len(images)), images), start=1):
        with column:
            st.image(tile(image), caption=f"Post {number} before")
            if number not in after:
                st.image(dimmed(tile(image)), caption="Hidden")
            else:
                st.image(tile(after[number]), caption="Blurred" if number in blurred else "Unchanged")
