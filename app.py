"""Breadcrumbs: each post looks harmless; together they map your routine."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pydeck as pdk
import streamlit as st
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from breadcrumbs import theme
from breadcrumbs.agents import safe_blur
from breadcrumbs.geo import (
    geocode,
    is_near_group,
    posts_to_fix,
    routine_area,
    tightest_cluster,
)
from breadcrumbs.spark import locate_photo, pixel_box
from breadcrumbs.importer import photos_from_export
from breadcrumbs.tipping import MAX_FEED, scan_feed
from breadcrumbs.views import run_match, show_match_result, show_tipping
from breadcrumbs.views import tile as tile_view

MAX_PHOTOS = 50
MAX_EDGE = 1600
WORKERS = 4
GPS_IFD = 0x8825
GRID_COLUMNS = 5
NEW_POST = -1  # Key for the not-yet-posted photo on the map.
DEMO_PHOTOS = Path(__file__).parent / "demo" / "photos"
SAMPLE_RESULT = Path(__file__).parent / "demo" / "sample_result.json"
SAMPLE_TIPPING = Path(__file__).parent / "demo" / "tipping.json"
BAD_IMAGE = (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError)


def load(file) -> Image.Image:
    """Open an upload, apply rotation, drop metadata, and shrink it."""
    image = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE))
    return image


def safe_locate(image: Image.Image) -> dict:
    """Locate one photo; mark it unchecked if Spark or the network fails."""
    try:
        return {**locate_photo(image), "checked": True}
    except Exception as error:
        return {"place": "", "box_2d": None, "clue": "", "checked": False, "error": str(error)}


def audit(images: list[Image.Image]) -> list[dict]:
    """Return one finding per photo, with a map point when it can be placed."""
    with ThreadPoolExecutor(WORKERS) as pool:
        findings = list(pool.map(safe_locate, images))
    return [{**f, "point": geocode(f["place"])} for f in findings]


def saved_findings() -> list[dict]:
    """Return a saved real run, so the sample demo is repeatable."""
    saved = json.loads(SAMPLE_RESULT.read_text(encoding="utf-8"))
    return [{**f, "point": tuple(f["point"]) if f["point"] else None} for f in saved]


def fix_selected(images, findings, selected: list[int]) -> tuple[list, list]:
    """Blur the selected photos and recheck them with Spark."""
    fixed, rechecked = list(images), list(findings)
    with ThreadPoolExecutor(WORKERS) as pool:
        blurs = list(pool.map(lambda i: safe_blur(images[i]), selected))
    for index, blurred in zip(selected, blurs):
        if blurred is not None:  # A failed blur leaves the photo unchanged and flagged.
            fixed[index] = blurred
            rechecked[index] = audit([blurred])[0]
    return fixed, rechecked


def load_all(files) -> tuple[list, list[int], list[str]]:
    """Open every readable upload; return images, GPS post numbers, and skipped names."""
    images, gps, skipped = [], [], []
    for file in files:
        try:
            found = hasattr(file, "seek") and has_gps(file)  # Sample paths carry no upload GPS.
            images.append(load(file))
        except BAD_IMAGE:
            skipped.append(getattr(file, "name", str(file)))
            continue
        if found:
            gps.append(len(images))
    return images, gps, skipped


def has_gps(file) -> bool:
    """Return True if an uploaded file carries GPS metadata."""
    file.seek(0)
    found = bool(Image.open(file).getexif().get_ifd(GPS_IFD))
    file.seek(0)
    return found


def visible_points(findings: list[dict], hidden: set[int]) -> dict[int, tuple]:
    """Return map points keyed by post index, skipping hidden posts."""
    return {
        i: f["point"] for i, f in enumerate(findings) if f["point"] and i not in hidden
    }


def post_list(posts: list[int]) -> str:
    """Return 0-based post indexes as display numbers."""
    return ", ".join(str(i + 1) for i in sorted(posts))


def radius_text(area: dict | None) -> str:
    """Describe a routine area in words."""
    if not area:
        return "no pattern"
    return f"{area['places']} places within {area['radius_m'] / 1000:.1f} km"


def draw_box(image: Image.Image, finding: dict) -> Image.Image:
    """Return a copy of a photo with its clue boxed."""
    copy = image.copy()
    if finding["box_2d"]:
        box = pixel_box(finding["box_2d"], image)
        ImageDraw.Draw(copy).rectangle(box, outline="red", width=6)
    return copy


def show_map(findings: list[dict], hidden: set[int], title: str) -> None:
    """Map the visible posts and their routine area, computed in code."""
    st.subheader(title)
    points = visible_points(findings, hidden)
    all_points = list(points.values())
    near = {i: p for i, p in points.items() if is_near_group(p, all_points)}
    if len(near) < len(points):
        st.caption(f"{len(points) - len(near)} far-away match left out as a likely mistake.")
    pins = [{"lat": p[0], "lon": p[1], "post": i + 1} for i, p in near.items()]
    area = routine_area(list(near.values()))
    if area:
        st.metric("Routine area", radius_text(area))
    elif pins:
        st.metric("Routine area", "One place, no pattern")
    else:
        st.metric("Routine area", "No place named")
    if not pins:
        return
    center = area or pins[0]
    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=pins,
            get_position="[lon, lat]",
            get_radius=90,
            radius_min_pixels=7,
            get_fill_color=[210, 58, 47, 235],
            pickable=True,
        )
    ]
    if area:
        layers.insert(
            0,
            pdk.Layer(
                "ScatterplotLayer",
                data=[area],
                get_position="[lon, lat]",
                get_radius="radius_m",
                get_fill_color=[29, 122, 114, 45],
            ),
        )
    view = pdk.ViewState(latitude=center["lat"], longitude=center["lon"], zoom=11.5)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "Post {post}"}))


def own_photos_box(key: str) -> bool:
    """Ask the user to confirm the photos are theirs."""
    return st.checkbox("These are my own photos, and I want to protect what they reveal.", key=key)


def export_tab(kind: str) -> list:
    """Show export steps and return the photos from an uploaded export ZIP."""
    st.markdown(theme.SOURCES[kind], unsafe_allow_html=True)
    mine = own_photos_box(f"mine_{kind}")
    archive = st.file_uploader("Upload the export ZIP", type=["zip"], disabled=not mine, key=f"zip_{kind}")
    if not (archive and st.button("Import and check", key=f"go_{kind}")):
        return []
    try:
        photos = photos_from_export(archive)
    except ValueError as error:
        st.warning(f"Could not read that export: {error}")
        return []
    if not photos:
        st.warning("No posted photos found in that export.")
    return photos


st.set_page_config(
    page_title="Breadcrumbs", page_icon=str(Path(__file__).parent / "assets" / "logo.png"), layout="wide"
)
has_results = "findings" in st.session_state
st.markdown(theme.CSS + theme.TRACE_CSS + theme.NAV, unsafe_allow_html=True)
if not has_results:
    st.markdown(theme.HERO, unsafe_allow_html=True)

tab_sample, tab_upload, tab_ig, tab_fb = st.tabs(["Try the sample", "Upload photos", "Instagram", "Facebook"])
with tab_sample:
    st.markdown(
        '<div class="source">Five public photos, staged as one person\'s feed. None of them names a place '
        "on its own. Uses a saved real run, so it loads instantly.</div>",
        unsafe_allow_html=True,
    )
    sample = st.button("Run again on sample photos" if has_results else "See it on sample photos", type="primary")
with tab_upload:
    st.markdown('<p class="hint">Tick the box to turn on upload.</p>', unsafe_allow_html=True)
    mine = own_photos_box("mine_upload")
    files = st.file_uploader(
        "Upload your photos, oldest post first",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        disabled=not mine,
    )
    uploaded = list(files) if files and st.button("Check my photos") else []
with tab_ig:
    imported = export_tab("instagram")
with tab_fb:
    imported = imported or export_tab("facebook")
st.caption("Breadcrumbs saves nothing. Photos are sent to the Meta Model API for analysis.")

chosen = sorted(DEMO_PHOTOS.glob("*.jpg")) if sample else (uploaded or imported)[:MAX_PHOTOS]
if chosen:
    images, gps, skipped = load_all(chosen)
    st.session_state.gps_files = [] if sample else gps
    st.session_state.skipped = skipped
    with st.spinner("Reading your photos..."):
        st.session_state.images = images
        st.session_state.is_sample = bool(sample)
        st.session_state.findings = saved_findings() if sample else audit(images)
        for stale in ("fixed", "match", "match_after", "tipping"):
            st.session_state.pop(stale, None)
    st.rerun()

if st.session_state.get("skipped"):
    st.warning(f"Could not open, so not checked: {', '.join(st.session_state.skipped)}")

if "findings" in st.session_state and st.session_state.images:
    images, findings = st.session_state.images, st.session_state.findings
    if st.session_state.is_sample:
        st.caption("Sample: saved result from a real run, on public photos by different authors.")
    failed = [i + 1 for i, f in enumerate(findings) if not f["checked"]]
    if failed:
        st.warning(f"Not checked, so not cleared: photos {failed}")

    st.markdown(theme.section(
        "Step 1 of 4", "What each post reveals alone",
        "Muse Spark checks every photo on its own for signs and landmarks, the way most privacy checkers do.",
    ), unsafe_allow_html=True)
    points = visible_points(findings, set())
    cluster = tightest_cluster(points)
    picks = posts_to_fix(points)
    named = sum(bool(f["place"]) for f in findings)
    st.markdown(theme.tiles(named, len(findings), len(cluster), len(picks)), unsafe_allow_html=True)
    if cluster:
        detail = f"Smallest fix: change post {post_list(picks)} to break up every cluster."
        title = f"Posts {post_list(cluster)} sit within 1 km of each other"
        st.markdown(theme.verdict(title, detail), unsafe_allow_html=True)
    else:
        message = (f"{named} of {len(findings)} posts name a place, and none sit within 1 km of each other. "
                   "A per-photo checker would clear you. Step 2 checks them together.")
        st.markdown(theme.verdict("Each post looks safe on its own", message, safe=True), unsafe_allow_html=True)

    per_row = min(len(images), GRID_COLUMNS)
    for start in range(0, len(images), per_row):
        for column, index in zip(st.columns(per_row), range(start, min(start + per_row, len(images)))):
            place = findings[index]["place"] or "No place named"
            column.image(tile_view(draw_box(images[index], findings[index])), caption=f"Post {index + 1}: {place}")
    if points:
        show_map(findings, set(), "All posts together")
        st.caption("Model output, placed by OpenStreetMap. A pattern, not a home address.")

    if st.session_state.gps_files:
        st.warning(
            f"Hidden GPS location found in photos {st.session_state.gps_files}. "
            "Many social apps remove it, but direct sharing can keep it."
        )

    st.markdown(theme.section(
        "Step 2 of 4", "Which post gave you away",
        "An attacker agent reads your feed in posting order: post 1 alone, then posts 1-2, and so on. "
        f"Each run is a separate investigation, over your first {MAX_FEED} posts at most.",
    ), unsafe_allow_html=True)
    if st.button("Find the tipping point", type="primary"):
        with st.spinner("Running one investigation per feed length..."):
            if st.session_state.is_sample:
                rows = json.loads(SAMPLE_TIPPING.read_text(encoding="utf-8"))
            else:
                rows = scan_feed(images)
        st.session_state.tipping = rows
    if "tipping" in st.session_state:
        if st.session_state.is_sample:
            st.caption("Saved result from a real run on the sample photos.")
        show_tipping(st.session_state.tipping, images)

    st.markdown(theme.section(
        "Step 3 of 4", "Break the pattern",
        "The attacker investigates with web search and maps. The defender blurs clues with SAM 3.1, "
        "checks the blur held, or hides a post. They repeat until the attacker fails.",
    ), unsafe_allow_html=True)
    if st.button("Start the match", type="primary"):
        run_match(images, st.session_state.is_sample)
    if "match" in st.session_state:
        show_match_result(st.session_state.match, images, st.session_state.is_sample)

    st.markdown(theme.section(
        "Step 4 of 4", "Check a new photo, or fix old ones",
        "See whether a new photo joins a pattern on your map, or blur the clues in posts you already shared.",
    ), unsafe_allow_html=True)
    st.markdown(theme.EXTENSION, unsafe_allow_html=True)
    check_column, fix_column = st.columns(2)
    with check_column:
        new_post = st.file_uploader("A photo you plan to post", type=["jpg", "jpeg", "png"])
        if new_post and st.button("Check this post"):
            try:
                with st.spinner("Checking..."):
                    finding = audit([load(new_post)])[0]
            except BAD_IMAGE:
                finding = None
                st.warning("Could not open that photo.")
            if finding is None:
                pass
            elif finding["point"]:
                grown = tightest_cluster({**points, NEW_POST: finding["point"]})
                st.write(f"This post names: {finding['place']}")
                if NEW_POST in grown:
                    others = post_list([i for i in grown if i != NEW_POST])
                    plural = "s" if "," in others else ""
                    st.error(f"Posting this adds to a pattern with post{plural} {others}.")
                else:
                    st.success("This post does not join a cluster on your map.")
            else:
                st.write("This post did not add a place to your map.")
    with fix_column:
        options = [i for i, f in enumerate(findings) if f["place"]]
        labels = {i: f"Post {i + 1}: {findings[i]['place']}" for i in options}
        selected = st.multiselect("Posts that name a place", options, format_func=labels.get,
                                  placeholder="Choose posts to change" if options else "No post names a place")
        if selected and st.button("Blur those clues and recheck"):
            with st.spinner("Blurring and checking again..."):
                st.session_state.fixed = fix_selected(images, findings, selected)
    if selected:
        show_map(findings, set(selected), "If you delete those posts")

if "fixed" in st.session_state:
    fixed, rechecked = st.session_state.fixed
    changed = [p for p, q in zip(fixed, st.session_state.images) if p is not q]
    if changed:
        st.image(changed, width=240)
    show_map(rechecked, set(), "After blurring")
    st.caption(
        "A smaller result means the model could no longer name those places. "
        "It is not a guarantee: a person who knows the area may still recognize them."
    )

st.markdown(theme.FOOT, unsafe_allow_html=True)
