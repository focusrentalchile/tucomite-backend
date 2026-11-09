"""Unit tests for branded support reply email HTML."""

from app.services.email_service import build_support_reply_html


def test_support_reply_html_includes_button_and_body() -> None:
    html = build_support_reply_html(
        visitor_name="Ana",
        reply_body="Te contactamos pronto",
        site_url="https://tucomite.cl",
    )
    assert "Hola Ana" in html
    assert "Te contactamos pronto" in html
    assert 'href="https://tucomite.cl"' in html
    assert "Ir a Tu Comité" in html
