from custom_components.sim800c.modem.encoding import (
    choose_encoding,
    is_gsm7_encodable,
    to_ucs2_hex,
)


def test_gsm7_detects_plain_ascii():
    assert is_gsm7_encodable("Hello 123!") is True


def test_gsm7_rejects_cyrillic():
    assert is_gsm7_encodable("Привет") is False


def test_gsm7_accepts_extension_chars():
    assert is_gsm7_encodable("price {50}") is True


def test_ucs2_hex_uppercase_four_digits():
    assert to_ucs2_hex("A") == "0041"
    assert to_ucs2_hex("Пи") == "041F0438"


def test_choose_encoding_prefers_gsm_for_ascii():
    assert choose_encoding("Hello", force_unicode=False) == "GSM"


def test_choose_encoding_uses_ucs2_for_cyrillic():
    assert choose_encoding("Привет", force_unicode=False) == "UCS2"


def test_force_unicode_overrides_ascii():
    assert choose_encoding("Hello", force_unicode=True) == "UCS2"
