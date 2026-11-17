"""Unit tests for Chilean RUT normalization."""

import pytest

from app.utils.rut import InvalidRut, normalize_rut


def test_normalize_rut_accepts_dotted_and_plain() -> None:
    assert normalize_rut("12.345.678-5") == "12345678-5"
    assert normalize_rut("12345678-5") == "12345678-5"
    assert normalize_rut("10000013k") == "10000013-K"


def test_normalize_rut_rejects_bad_check_digit() -> None:
    with pytest.raises(InvalidRut):
        normalize_rut("12.345.678-0")
