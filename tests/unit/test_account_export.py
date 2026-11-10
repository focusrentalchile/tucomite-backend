"""Unit tests for the account export ZIP builder."""

import io
from dataclasses import dataclass
from zipfile import ZipFile

from app.services.account_export import (
    ArchiveBuilder,
    decode_data_url,
    safe_segment,
    slug_with_id,
)


@dataclass(frozen=True)
class _Attachment:
    kind: str
    name: str
    url: str


def test_decode_data_url_reads_base64_and_plain_payloads() -> None:
    assert decode_data_url("data:image/png;base64,aGVsbG8=") == ("image/png", b"hello")
    assert decode_data_url("data:text/plain,hola%20mundo") == ("text/plain", b"hola mundo")
    assert decode_data_url("https://example.com/a.png") is None
    assert decode_data_url("data:image/png;base64,@@@") is None


def test_safe_segment_blocks_path_traversal() -> None:
    assert safe_segment("../../etc/passwd") == "passwd"
    assert safe_segment("a\\b\\foto?.jpg") == "foto_.jpg"
    assert safe_segment("...", "file") == "file"


def test_slug_with_id_is_lowercase_ascii() -> None:
    assert slug_with_id("Reparación del Portón", "1234567890") == "reparacion-del-porton-12345678"


def test_attachments_are_extracted_by_kind_and_deduplicated() -> None:
    archive = ArchiveBuilder()

    manifest = archive.add_attachments(
        "topics/luz-1",
        [
            _Attachment("image", "foto.jpg", "data:image/jpeg;base64,aGVsbG8="),
            _Attachment("image", "foto.jpg", "data:image/jpeg;base64,aGVsbG8="),
            _Attachment("video", "clip.mp4", "data:video/mp4;base64,aGVsbG8="),
            _Attachment("file", "acta", "data:application/pdf;base64,aGVsbG8="),
            _Attachment("file", "externo.pdf", "https://example.com/externo.pdf"),
        ],
    )

    names = ZipFile(io.BytesIO(archive.finish())).namelist()
    assert names == [
        "topics/luz-1/photos/foto.jpg",
        "topics/luz-1/photos/foto-2.jpg",
        "topics/luz-1/videos/clip.mp4",
        "topics/luz-1/files/acta.pdf",
    ]
    assert manifest[3]["path"] == "topics/luz-1/files/acta.pdf"
    assert manifest[4] == {"kind": "file", "name": "externo.pdf", "path": None, "url": "https://example.com/externo.pdf"}


def test_json_is_utf8_and_dataclasses_are_plain() -> None:
    archive = ArchiveBuilder()
    archive.add_json("users/summary.json", [_Attachment("file", "ñandú.pdf", "x")])

    content = ZipFile(io.BytesIO(archive.finish())).read("users/summary.json").decode("utf-8")

    assert "ñandú.pdf" in content
