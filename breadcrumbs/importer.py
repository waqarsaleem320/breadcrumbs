"""Read photos, in posting order, from an Instagram or Facebook data export ZIP.

Direct sign-in needs Meta app review, so the user downloads their own export
(Accounts Center > Your information and permissions > Download your information)
and uploads the ZIP. Nothing is extracted to disk.
"""
import io
import json
import zipfile
from pathlib import PurePosixPath

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_MEMBERS = 20_000
MAX_IMAGE_BYTES = 25_000_000
MAX_JSON_BYTES = 50_000_000
MAX_IMPORT = 20  # Most recent posts kept; the scans grow with every post.


def _is_image(name: str) -> bool:
    return PurePosixPath(name).suffix.lower() in IMAGE_EXT


def _media(node, found: list[tuple[int, str]]) -> None:
    """Collect (timestamp, uri) pairs from any nesting of export JSON."""
    if isinstance(node, dict):
        uri, stamp = node.get("uri"), node.get("creation_timestamp")
        if isinstance(uri, str) and isinstance(stamp, (int, float)) and _is_image(uri):
            found.append((int(stamp), uri))
        for value in node.values():
            _media(value, found)
    elif isinstance(node, list):
        for value in node:
            _media(value, found)


def posted_media(archive: zipfile.ZipFile) -> list[str]:
    """Return image paths from the export's post lists, oldest first."""
    names = set(archive.namelist())
    found: list[tuple[int, str]] = []
    for info in archive.infolist():
        name = info.filename.lower()
        if name.endswith(".json") and "post" in name and info.file_size <= MAX_JSON_BYTES:
            try:
                _media(json.loads(archive.read(info)), found)
            except (ValueError, UnicodeDecodeError):
                continue
    ordered = [uri for _, uri in sorted(set(found)) if uri in names]
    if ordered:
        return ordered
    images = [i for i in archive.infolist() if _is_image(i.filename) and not i.is_dir()]
    return [i.filename for i in sorted(images, key=lambda i: i.date_time)]  # No post list: file dates.


def photos_from_export(file) -> list[io.BytesIO]:
    """Return the most recent posted photos as named in-memory files, oldest first.

    Raises:
        ValueError: if the file is not a readable ZIP or holds too many entries.
    """
    try:
        archive = zipfile.ZipFile(file)
    except zipfile.BadZipFile as error:
        raise ValueError("Not a ZIP file.") from error
    if len(archive.infolist()) > MAX_MEMBERS:
        raise ValueError("This ZIP has too many files.")
    photos = []
    for name in posted_media(archive)[-MAX_IMPORT:]:
        if archive.getinfo(name).file_size > MAX_IMAGE_BYTES:
            continue
        data = io.BytesIO(archive.read(name))
        data.name = PurePosixPath(name).name
        photos.append(data)
    return photos
