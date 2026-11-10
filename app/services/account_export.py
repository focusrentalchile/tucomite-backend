"""Builds the in-memory ZIP delivered when a building owner closes the account."""

import base64
import binascii
import io
import json
import mimetypes
import re
import unicodedata
from dataclasses import asdict, is_dataclass
from pathlib import PurePath
from typing import Any, Iterable
from urllib.parse import unquote_to_bytes
from zipfile import ZIP_DEFLATED, ZipFile

_DATA_URL = re.compile(r"^data:(?P<mime>[^;,]*)(?P<params>(?:;[^,]*)?),(?P<data>.*)$", re.DOTALL)
_UNSAFE = re.compile(r"[^A-Za-z0-9._\- ]+")
_KIND_FOLDERS = {"image": "photos", "video": "videos", "file": "files"}


def safe_segment(value: str, fallback: str = "item", limit: int = 60) -> str:
    """Return a path-safe name segment: no separators, no control characters, bounded length."""
    cleaned = _UNSAFE.sub("_", PurePath(value.replace("\\", "/")).name).strip(" ._")
    return cleaned[:limit] or fallback


def slugify(value: str, fallback: str = "item", limit: int = 40) -> str:
    """Lowercase ASCII slug with hyphens (accents removed)."""
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:limit].strip("-") or fallback


def slug_with_id(title: str, record_id: str) -> str:
    """Folder name like ``luminarias-1a2b3c4d`` that stays unique per record."""
    return f"{slugify(title)}-{record_id[:8]}"


def decode_data_url(url: str) -> tuple[str, bytes] | None:
    """Return (mime type, bytes) for a data URL, or None when the value is not decodable."""
    match = _DATA_URL.match(url.strip())
    if match is None:
        return None
    mime = match.group("mime") or "application/octet-stream"
    data = match.group("data")
    try:
        if ";base64" in match.group("params"):
            padded = data + "=" * (-len(data) % 4)
            return mime, base64.b64decode(padded, validate=True)
        return mime, unquote_to_bytes(data)
    except (binascii.Error, ValueError):
        return None


def to_plain(value: Any) -> Any:
    """Convert dataclasses (and nested tuples) into JSON-friendly values."""
    if is_dataclass(value) and not isinstance(value, type):
        return to_plain(asdict(value))
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


class ArchiveBuilder:
    """Writes folders, JSON files, and extracted attachments into one ZIP held in memory."""

    def __init__(self) -> None:
        self._buffer = io.BytesIO()
        self._zip = ZipFile(self._buffer, "w", ZIP_DEFLATED)
        self._used: set[str] = set()

    def unique_path(self, path: str) -> str:
        """Return ``path`` or ``path`` with a numeric suffix when it is already in the archive."""
        if path not in self._used:
            return path
        pure = PurePath(path)
        index = 2
        while True:
            candidate = f"{pure.parent.as_posix()}/{pure.stem}-{index}{pure.suffix}"
            if candidate not in self._used:
                return candidate
            index += 1

    def add_bytes(self, path: str, content: bytes) -> str:
        """Add a file and return the (possibly de-duplicated) path used."""
        final = self.unique_path(path)
        self._used.add(final)
        self._zip.writestr(final, content)
        return final

    def add_json(self, path: str, data: Any) -> str:
        """Add a UTF-8 JSON document."""
        payload = json.dumps(to_plain(data), ensure_ascii=False, indent=2, default=str)
        return self.add_bytes(path, payload.encode("utf-8"))

    def add_attachments(
        self,
        base_dir: str,
        attachments: Iterable[Any],
    ) -> list[dict[str, Any]]:
        """Extract attachments under ``base_dir/photos|videos|files``.

        Data URLs are decoded into real files. Anything else (a remote link, or data that
        cannot be decoded) is listed in the returned manifest with its original ``url``.
        """
        manifest: list[dict[str, Any]] = []
        for item in attachments:
            kind = str(getattr(item, "kind", "file"))
            name = str(getattr(item, "name", "") or "file")
            url = str(getattr(item, "url", "") or "")
            decoded = decode_data_url(url) if url.startswith("data:") else None
            entry: dict[str, Any] = {"kind": kind, "name": name, "path": None}
            if decoded is None:
                entry["url"] = url if not url.startswith("data:") else None
                manifest.append(entry)
                continue
            mime, content = decoded
            file_name = safe_segment(name, "file", 120)
            if not PurePath(file_name).suffix:
                file_name += mimetypes.guess_extension(mime) or ""
            folder = _KIND_FOLDERS.get(kind, "files")
            entry["path"] = self.add_bytes(f"{base_dir}/{folder}/{file_name}", content)
            entry["mime"] = mime
            manifest.append(entry)
        return manifest

    def finish(self) -> bytes:
        """Close the archive and return its bytes."""
        self._zip.close()
        return self._buffer.getvalue()
