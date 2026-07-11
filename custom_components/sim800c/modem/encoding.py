"""SMS text encoding helpers: GSM 03.38 detection and UCS2 hex."""

from __future__ import annotations


def to_ucs2_hex(text: str) -> str:
    """Encode text as a UCS2 hex string (4 uppercase hex digits per char)."""
    return "".join(f"{ord(char):04X}" for char in text)


def from_ucs2_hex(hex_str: str) -> str:
    """
    Decode a UCS2 (UTF-16 big-endian) hex string back to text.

    Whitespace is ignored. Returns the input unchanged if it is not valid
    UCS2 hex, so a mis-tagged GSM body never raises.
    """
    cleaned = "".join(hex_str.split())
    if len(cleaned) % 4 != 0:
        return hex_str
    try:
        return bytes.fromhex(cleaned).decode("utf-16-be")
    except (ValueError, UnicodeDecodeError):
        return hex_str


def choose_encoding(text: str, force_unicode: bool) -> str:  # noqa: FBT001 — public API, matches the send_sms service field
    """
    Return 'GSM' or 'UCS2' for the given text.

    Only pure-ASCII text is sent as GSM 7-bit (ASCII maps 1:1 to the GSM
    default alphabet). Any non-ASCII character routes to UCS2, because this
    module does not implement GSM 03.38 code-point packing and such
    characters cannot be transmitted correctly in GSM mode.
    """
    if force_unicode or not text.isascii():
        return "UCS2"
    return "GSM"
