"""Smoke characterization tests for small predicate / utility wrappers.

Each test makes ONE assertion pinning the real observed return value (verified
against .venv/bin/python -c "..." before writing). Surprising behaviour is
noted with a # FLAG: comment rather than being "fixed".

Functions covered (all from komga_cover_extractor.py):
    contains_brackets, starts_with_bracket, ends_with_bracket,
    ends_with_starting_bracket, contains_unicode, contains_punctuation,
    get_file_extension, get_extensionless_name, array_to_string, get_sort_key
"""

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# contains_brackets
# ---------------------------------------------------------------------------

def test_contains_brackets_with_parens():
    assert kce.contains_brackets("hello(world)") is True


def test_contains_brackets_plain_string():
    assert kce.contains_brackets("hello") is False


def test_contains_brackets_square():
    assert kce.contains_brackets("[test]") is True


# ---------------------------------------------------------------------------
# starts_with_bracket
# ---------------------------------------------------------------------------

def test_starts_with_bracket_true():
    assert kce.starts_with_bracket("(hello)") is True


def test_starts_with_bracket_false():
    assert kce.starts_with_bracket("hello") is False


# ---------------------------------------------------------------------------
# ends_with_bracket  (closing brackets)
# ---------------------------------------------------------------------------

def test_ends_with_bracket_true():
    assert kce.ends_with_bracket("hello)") is True


def test_ends_with_bracket_false():
    assert kce.ends_with_bracket("hello") is False


# ---------------------------------------------------------------------------
# ends_with_starting_bracket  (opening brackets at the end)
# ---------------------------------------------------------------------------

def test_ends_with_starting_bracket_true():
    assert kce.ends_with_starting_bracket("hello(") is True


def test_ends_with_starting_bracket_closing_is_false():
    # A closing bracket does NOT match — only opening brackets count.
    assert kce.ends_with_starting_bracket("hello)") is False


# ---------------------------------------------------------------------------
# contains_unicode
# ---------------------------------------------------------------------------

def test_contains_unicode_ascii_is_false():
    assert kce.contains_unicode("hello") is False


def test_contains_unicode_accented_char():
    assert kce.contains_unicode("héllo") is True


def test_contains_unicode_kanji():
    assert kce.contains_unicode("日本語") is True


# ---------------------------------------------------------------------------
# contains_punctuation
# ---------------------------------------------------------------------------

def test_contains_punctuation_exclamation():
    assert kce.contains_punctuation("hello!") is True


def test_contains_punctuation_plain_false():
    assert kce.contains_punctuation("hello") is False


def test_contains_punctuation_comma():
    assert kce.contains_punctuation("hello, world") is True


# ---------------------------------------------------------------------------
# get_file_extension
# ---------------------------------------------------------------------------

def test_get_file_extension_cbz():
    assert kce.get_file_extension("manga.cbz") == ".cbz"


def test_get_file_extension_no_ext():
    assert kce.get_file_extension("manga") == ""


def test_get_file_extension_hidden_file():
    # os.path.splitext(".hidden") -> ('.hidden', '') so extension is ''
    # FLAG: hidden files (dot-files with no second dot) return '' not '.hidden'
    assert kce.get_file_extension(".hidden") == ""


def test_get_file_extension_double_ext_returns_last():
    # os.path.splitext("file.tar.gz") -> ('file.tar', '.gz')
    assert kce.get_file_extension("file.tar.gz") == ".gz"


# ---------------------------------------------------------------------------
# get_extensionless_name
# ---------------------------------------------------------------------------

def test_get_extensionless_name_strips_ext():
    assert kce.get_extensionless_name("manga.cbz") == "manga"


def test_get_extensionless_name_hidden_file_unchanged():
    # os.path.splitext(".hidden") -> ('.hidden', '') so stem is '.hidden'
    assert kce.get_extensionless_name(".hidden") == ".hidden"


def test_get_extensionless_name_no_ext():
    assert kce.get_extensionless_name("no_ext") == "no_ext"


# ---------------------------------------------------------------------------
# array_to_string  (signature: array_to_string(array, separator=", "))
# ---------------------------------------------------------------------------

def test_array_to_string_int_list():
    assert kce.array_to_string([1, 2, 3]) == "1, 2, 3"


def test_array_to_string_str_list():
    assert kce.array_to_string(["a", "b"]) == "a, b"


def test_array_to_string_custom_separator():
    assert kce.array_to_string(["a", "b"], " | ") == "a | b"


def test_array_to_string_non_list_string():
    # Non-list input: str(array) is returned directly
    assert kce.array_to_string("not a list") == "not a list"


def test_array_to_string_non_list_int():
    assert kce.array_to_string(42) == "42"


# ---------------------------------------------------------------------------
# get_sort_key
# ---------------------------------------------------------------------------

def test_get_sort_key_scalar_int():
    assert kce.get_sort_key(5) == 5


def test_get_sort_key_scalar_float():
    assert kce.get_sort_key(3.5) == 3.5


def test_get_sort_key_list_returns_min():
    assert kce.get_sort_key([3, 1, 4]) == 1


def test_get_sort_key_singleton_list():
    assert kce.get_sort_key([10]) == 10
