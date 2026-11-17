"""Chilean RUT normalization and check-digit validation."""

from __future__ import annotations


class InvalidRut(ValueError):
    """Raised when a RUT fails the Chilean modulo-11 check."""


def normalize_rut(value: str) -> str:
    """Return ``BODY-DV`` (no dots). Raises ``InvalidRut`` when invalid."""
    raw = (value or "").strip().upper().replace(".", "").replace(" ", "")
    if not raw:
        raise InvalidRut("RUT is required.")
    if "-" in raw:
        body, dv = raw.rsplit("-", 1)
    else:
        if len(raw) < 2:
            raise InvalidRut("RUT is invalid.")
        body, dv = raw[:-1], raw[-1]
    body = body.strip()
    dv = dv.strip().upper()
    if not body.isdigit() or len(body) < 7 or len(body) > 8:
        raise InvalidRut("RUT is invalid.")
    if dv not in "0123456789K":
        raise InvalidRut("RUT is invalid.")
    if _expected_dv(body) != dv:
        raise InvalidRut("RUT is invalid.")
    return f"{int(body)}-{dv}"


def _expected_dv(body: str) -> str:
    total = 0
    factor = 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    remainder = 11 - (total % 11)
    if remainder == 11:
        return "0"
    if remainder == 10:
        return "K"
    return str(remainder)
