"""SMS text encoding helpers: GSM 03.38 detection and UCS2 hex."""

from __future__ import annotations

# GSM 03.38 default alphabet (basic set).
_GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ ÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
# Characters reachable via the GSM 03.38 extension table (ESC prefix).
_GSM7_EXTENSION = "^{}\\[~]|€\f"
_GSM7_CHARS = set(_GSM7_BASIC) | set(_GSM7_EXTENSION)


def is_gsm7_encodable(text: str) -> bool:
    """Return True if every character is representable in GSM 03.38."""
    return all(char in _GSM7_CHARS for char in text)


def to_ucs2_hex(text: str) -> str:
    """Encode text as a UCS2 hex string (4 uppercase hex digits per char)."""
    return "".join(f"{ord(char):04X}" for char in text)


def choose_encoding(text: str, force_unicode: bool) -> str:  # noqa: FBT001 — public API, matches the send_sms service field
    """Return 'GSM' or 'UCS2' for the given text."""
    if force_unicode or not is_gsm7_encodable(text):
        return "UCS2"
    return "GSM"
