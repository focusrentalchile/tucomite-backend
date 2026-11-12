"""From header should show TuComité, not a bare no-reply local-part."""

from app.services.email_service import format_from_header


def test_format_from_header_wraps_bare_address() -> None:
    assert format_from_header("no-reply@tucomite.cl") == "TuComité <no-reply@tucomite.cl>"


def test_format_from_header_replaces_existing_display_name() -> None:
    assert (
        format_from_header("Something <hola@tucomite.cl>")
        == "TuComité <hola@tucomite.cl>"
    )
