from custom_components.sim800c.modem.encoding import (
    choose_encoding,
    to_ucs2_hex,
)


def test_ucs2_hex_uppercase_four_digits():
    assert to_ucs2_hex("A") == "0041"
    assert to_ucs2_hex("Пи") == "041F0438"


def test_choose_encoding_prefers_gsm_for_ascii():
    assert choose_encoding("Hello", force_unicode=False) == "GSM"


def test_choose_encoding_uses_ucs2_for_cyrillic():
    assert choose_encoding("Привет", force_unicode=False) == "UCS2"


def test_force_unicode_overrides_ascii():
    assert choose_encoding("Hello", force_unicode=True) == "UCS2"


def test_choose_encoding_non_ascii_gsm_alphabet_uses_ucs2():
    # chars in the GSM alphabet but non-ASCII must still go UCS2 (no GSM packing)
    assert choose_encoding("café", force_unicode=False) == "UCS2"
    assert choose_encoding("£5 now", force_unicode=False) == "UCS2"
    assert choose_encoding("€10", force_unicode=False) == "UCS2"
