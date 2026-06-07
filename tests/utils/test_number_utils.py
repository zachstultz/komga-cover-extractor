"""Characterization tests for number-related utility functions.

Every assertion was verified against the live module BEFORE writing:
    .venv/bin/python -c "import komga_cover_extractor as kce; print(repr(kce.FUNC(ARGS)))"

Surprising / buggy behavior is noted with a ``# FLAG:`` comment and pinned AS-IS.

Functions covered (all from komga_cover_extractor.py):
    set_num_as_float_or_int, isfloat, isint, get_min_and_max_numbers,
    complete_num_array, abbreviate_numbers, has_one_set_of_numbers,
    contains_non_numeric, extract_all_numbers, has_multiple_numbers
"""

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# set_num_as_float_or_int
# ---------------------------------------------------------------------------

def test_set_num_as_float_or_int_integer_string_returns_int():
    # '1' -> 1 (int type)
    result = kce.set_num_as_float_or_int("1")
    assert result == 1
    assert isinstance(result, int)


def test_set_num_as_float_or_int_float_string_returns_float():
    # '1.5' -> 1.5 (float)
    result = kce.set_num_as_float_or_int("1.5")
    assert result == 1.5
    assert isinstance(result, float)


def test_set_num_as_float_or_int_dot_zero_returns_float():
    # FLAG: '2.0' short-circuits into the `elif '.' in volume_number` branch and
    # returns float(2.0) WITHOUT the int-equality check. It is a float, not int.
    result = kce.set_num_as_float_or_int("2.0")
    assert result == 2.0
    assert isinstance(result, float)


def test_set_num_as_float_or_int_ten_dot_zero_returns_float():
    # Same short-circuit: '10.0' -> 10.0 (float)
    result = kce.set_num_as_float_or_int("10.0")
    assert result == 10.0
    assert isinstance(result, float)


def test_set_num_as_float_or_int_empty_string_returns_empty():
    assert kce.set_num_as_float_or_int("") == ""


def test_set_num_as_float_or_int_int_list_returns_hyphen_joined_string():
    # FLAG: a list of ints/floats is joined with '-' and returned as a STRING,
    # not converted to any numeric type.
    result = kce.set_num_as_float_or_int([1, 2, 3])
    assert result == "1-2-3"
    assert isinstance(result, str)


def test_set_num_as_float_or_int_str_list_returns_hyphen_joined_string():
    # FLAG: a list of numeric strings is also joined with '-' as a STRING.
    result = kce.set_num_as_float_or_int(["1", "3"])
    assert result == "1-3"
    assert isinstance(result, str)


def test_set_num_as_float_or_int_float_list_returns_hyphen_joined_string():
    # [1.5, 2.5] -> '1.5-2.5' (floats, no int-equality applied to elements)
    result = kce.set_num_as_float_or_int([1.5, 2.5])
    assert result == "1.5-2.5"
    assert isinstance(result, str)


def test_set_num_as_float_or_int_float_str_list_returns_hyphen_joined_string():
    result = kce.set_num_as_float_or_int(["1.5", "2.5"])
    assert result == "1.5-2.5"
    assert isinstance(result, str)


def test_set_num_as_float_or_int_invalid_silent_returns_empty():
    # 'abc' with silent=True -> '' (suppresses send_message side-effect)
    assert kce.set_num_as_float_or_int("abc", silent=True) == ""


def test_set_num_as_float_or_int_large_integer():
    result = kce.set_num_as_float_or_int("10")
    assert result == 10
    assert isinstance(result, int)


def test_set_num_as_float_or_int_zero_integer():
    result = kce.set_num_as_float_or_int("0")
    assert result == 0
    assert isinstance(result, int)


def test_set_num_as_float_or_int_half():
    result = kce.set_num_as_float_or_int("0.5")
    assert result == 0.5
    assert isinstance(result, float)


def test_set_num_as_float_or_int_native_int_passthrough():
    # Native int 5 goes through else branch: float(5)==int(5) -> int 5
    result = kce.set_num_as_float_or_int(5)
    assert result == 5
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# isfloat
# ---------------------------------------------------------------------------

def test_isfloat_decimal_string():
    assert kce.isfloat("3.14") is True


def test_isfloat_integer_string():
    # '3' converts to float -> True
    assert kce.isfloat("3") is True


def test_isfloat_alpha_string():
    assert kce.isfloat("abc") is False


def test_isfloat_none():
    assert kce.isfloat(None) is False


def test_isfloat_empty_string():
    assert kce.isfloat("") is False


def test_isfloat_native_float():
    assert kce.isfloat(3.14) is True


def test_isfloat_zero_int():
    assert kce.isfloat(0) is True


def test_isfloat_scientific_notation():
    # '1e2' -> float(1e2)=100.0 -> True
    assert kce.isfloat("1e2") is True


# ---------------------------------------------------------------------------
# isint
# ---------------------------------------------------------------------------

def test_isint_integer_string():
    assert kce.isint("3") is True


def test_isint_dot_zero_string():
    # '3.0' -> float(3.0)==int(3) -> True
    assert kce.isint("3.0") is True


def test_isint_decimal_string():
    # '3.5' -> float(3.5) != int(3) -> False
    assert kce.isint("3.5") is False


def test_isint_alpha_string():
    assert kce.isint("abc") is False


def test_isint_empty_string():
    assert kce.isint("") is False


def test_isint_native_int():
    assert kce.isint(3) is True


def test_isint_native_float_whole():
    # 3.0 -> float(3.0)==int(3) -> True
    assert kce.isint(3.0) is True


def test_isint_negative_integer_string():
    assert kce.isint("-1") is True


def test_isint_zero_string():
    assert kce.isint("0") is True


def test_isint_none():
    assert kce.isint(None) is False


def test_isint_scientific_notation():
    # '1e2' -> float(100.0)==int(100) -> True
    assert kce.isint("1e2") is True


# ---------------------------------------------------------------------------
# get_min_and_max_numbers
# ---------------------------------------------------------------------------

def test_get_min_and_max_numbers_range():
    # '1-3' -> split on hyphen -> [1, 3]
    assert kce.get_min_and_max_numbers("1-3") == [1, 3]


def test_get_min_and_max_numbers_reversed_is_sorted():
    # '3-1' -> min=1, max=3 -> [1, 3]  (sorted, not original order)
    assert kce.get_min_and_max_numbers("3-1") == [1, 3]


def test_get_min_and_max_numbers_invalid_silent():
    # FLAG: 'abc-def' -> each token fails conversion -> set_num_as_float_or_int
    # returns '' for each -> numbers_search becomes ['', ''] -> min(['', ''])
    # returns '' -> result is [''] (list of empty string, NOT empty list)
    # (We pass the string as-is; the function calls send_message internally, but
    # since this is a characterization test we accept the side-effect output.)
    result = kce.get_min_and_max_numbers("abc-def")
    assert result == [""]


def test_get_min_and_max_numbers_single_number():
    # '5' -> [5] (no max appended when only one element)
    assert kce.get_min_and_max_numbers("5") == [5]


def test_get_min_and_max_numbers_three_numbers_keeps_min_max():
    # '2-5-8' -> min=2, max=8 -> [2, 8]  (middle value discarded)
    assert kce.get_min_and_max_numbers("2-5-8") == [2, 8]


def test_get_min_and_max_numbers_floats():
    # '1.5-3.5' -> [1.5, 3.5]
    assert kce.get_min_and_max_numbers("1.5-3.5") == [1.5, 3.5]


def test_get_min_and_max_numbers_empty_string():
    assert kce.get_min_and_max_numbers("") == []


def test_get_min_and_max_numbers_whitespace():
    assert kce.get_min_and_max_numbers("   ") == []


def test_get_min_and_max_numbers_underscore_separator():
    # '_' is translated to space by str.maketrans
    assert kce.get_min_and_max_numbers("5.5_10.5") == [5.5, 10.5]


def test_get_min_and_max_numbers_comma_separator():
    # ',' is translated to space by str.maketrans -> '1 3' -> [1, 3]
    assert kce.get_min_and_max_numbers("1,3") == [1, 3]


# ---------------------------------------------------------------------------
# complete_num_array
# ---------------------------------------------------------------------------

def test_complete_num_array_fills_gaps():
    assert kce.complete_num_array([1, 3]) == [1, 2, 3]


def test_complete_num_array_larger_gap():
    assert kce.complete_num_array([1, 5]) == [1, 2, 3, 4, 5]


def test_complete_num_array_empty():
    assert kce.complete_num_array([]) == []


def test_complete_num_array_single_element():
    assert kce.complete_num_array([3]) == [3]


def test_complete_num_array_floats_truncated_to_int_range():
    # FLAG: int(min)=1, int(max)=3 -> range(1, 4) -> [1, 2, 3]
    # The float inputs are truncated to ints for the range generation.
    assert kce.complete_num_array([1.5, 3.5]) == [1, 2, 3]


def test_complete_num_array_same_value_twice():
    # min==max -> range(5, 6) -> [5]
    assert kce.complete_num_array([5, 5]) == [5]


def test_complete_num_array_reversed_input():
    # min=1, max=3 regardless of input order
    assert kce.complete_num_array([3, 1]) == [1, 2, 3]


def test_complete_num_array_non_contiguous_three_values():
    # [2, 4, 6] -> min=2, max=6 -> range(2, 7) -> [2, 3, 4, 5, 6]
    assert kce.complete_num_array([2, 4, 6]) == [2, 3, 4, 5, 6]


# ---------------------------------------------------------------------------
# abbreviate_numbers
# ---------------------------------------------------------------------------

def test_abbreviate_numbers_contiguous_range():
    assert kce.abbreviate_numbers([1, 2, 3]) == "1-3"


def test_abbreviate_numbers_two_ranges():
    assert kce.abbreviate_numbers([1, 2, 3, 5, 6]) == "1-3, 5-6"


def test_abbreviate_numbers_single_element():
    assert kce.abbreviate_numbers([1]) == "1"


def test_abbreviate_numbers_empty():
    assert kce.abbreviate_numbers([]) == ""


def test_abbreviate_numbers_all_individual():
    # [1, 3, 5] -> no runs of consecutive ints -> "1, 3, 5"
    assert kce.abbreviate_numbers([1, 3, 5]) == "1, 3, 5"


def test_abbreviate_numbers_long_contiguous_run():
    assert kce.abbreviate_numbers([1, 2, 3, 4, 5]) == "1-5"


def test_abbreviate_numbers_mixed_range_and_single():
    # [1, 2, 4, 5, 6] -> "1-2, 4-6"
    assert kce.abbreviate_numbers([1, 2, 4, 5, 6]) == "1-2, 4-6"


def test_abbreviate_numbers_single_large():
    assert kce.abbreviate_numbers([10]) == "10"


def test_abbreviate_numbers_two_separate_ranges():
    assert kce.abbreviate_numbers([1, 2, 3, 10, 11, 12]) == "1-3, 10-12"


# ---------------------------------------------------------------------------
# has_one_set_of_numbers
# ---------------------------------------------------------------------------

def test_has_one_set_of_numbers_volume_keyword():
    assert kce.has_one_set_of_numbers("Volume 1") is True


def test_has_one_set_of_numbers_range_counts_as_one():
    # FLAG: a hyphen-separated range like '1-3' matches as ONE set (the regex
    # matches the full token including the hyphen). Not two sets.
    assert kce.has_one_set_of_numbers("Vol 1-3") is True


def test_has_one_set_of_numbers_no_numbers():
    assert kce.has_one_set_of_numbers("No numbers here") is False


def test_has_one_set_of_numbers_two_volume_keywords():
    # Two separate volume number matches -> False (len(search) != 1)
    assert kce.has_one_set_of_numbers("Vol 1 Vol 2") is False


def test_has_one_set_of_numbers_lowercase_v():
    assert kce.has_one_set_of_numbers("v01") is True


def test_has_one_set_of_numbers_bare_number():
    assert kce.has_one_set_of_numbers("1") is True


def test_has_one_set_of_numbers_chapter_mode():
    assert kce.has_one_set_of_numbers("chapter 5", chapter=True) is True


def test_has_one_set_of_numbers_volume_mode_explicit():
    assert kce.has_one_set_of_numbers("volume 1", chapter=False) is True


def test_has_one_set_of_numbers_two_lowercase_v():
    assert kce.has_one_set_of_numbers("v01 v02") is False


# ---------------------------------------------------------------------------
# contains_non_numeric
# ---------------------------------------------------------------------------

def test_contains_non_numeric_pure_integer_string():
    # '123' -> float('123') succeeds -> False
    assert kce.contains_non_numeric("123") is False


def test_contains_non_numeric_decimal_string():
    # '3.14' -> float succeeds -> False
    assert kce.contains_non_numeric("3.14") is False


def test_contains_non_numeric_alpha_string():
    assert kce.contains_non_numeric("abc") is True


def test_contains_non_numeric_alphanumeric():
    # '1a' -> float fails -> not '1a'.isdigit() -> True
    assert kce.contains_non_numeric("1a") is True


def test_contains_non_numeric_empty_string():
    # FLAG: float('') raises ValueError, then ''.isdigit() is False -> True
    # An empty string is considered to "contain non-numeric" content.
    assert kce.contains_non_numeric("") is True


def test_contains_non_numeric_zero():
    assert kce.contains_non_numeric("0") is False


# ---------------------------------------------------------------------------
# extract_all_numbers
# ---------------------------------------------------------------------------

def test_extract_all_numbers_volume_keyword():
    # 'Volume 1' -> [1]
    assert kce.extract_all_numbers("Volume 1") == [1]


def test_extract_all_numbers_range_returns_nested_list():
    # 'Vol 1-3' -> [[1, 3]] (range stored as nested list)
    assert kce.extract_all_numbers("Vol 1-3") == [[1, 3]]


def test_extract_all_numbers_no_numbers():
    assert kce.extract_all_numbers("No numbers here") == []


def test_extract_all_numbers_lowercase_v_no_match():
    # FLAG: 'v01' alone does not match extract_all_numbers' regex — needs a
    # recognized keyword prefix with a word boundary. Result is empty.
    assert kce.extract_all_numbers("v01") == []


def test_extract_all_numbers_decimal():
    # 'Volume 2.5' -> [2.5]
    assert kce.extract_all_numbers("Volume 2.5") == [2.5]


def test_extract_all_numbers_x_suffix_stripped():
    # 'Vol 5x2' -> x-part stripped -> [5]
    assert kce.extract_all_numbers("Vol 5x2") == [5]


def test_extract_all_numbers_hash_stripped():
    # 'v10 #5' -> hash-part stripped -> [5] (only the bare digit prefix remains)
    assert kce.extract_all_numbers("v10 #5") == [5]


def test_extract_all_numbers_volume_mode():
    assert kce.extract_all_numbers("volume 3") == [3]


def test_extract_all_numbers_volume_decimal_mode():
    assert kce.extract_all_numbers("vol 3.5") == [3.5]


def test_extract_all_numbers_chapter_keyword():
    assert kce.extract_all_numbers("Chapter 10") == [10]


def test_extract_all_numbers_with_subtitle():
    # Subtitle stripped before extraction -> 'Volume 5 - My Subtitle' -> [5]
    assert kce.extract_all_numbers("Volume 5 - My Subtitle", subtitle="My Subtitle") == [5]


def test_extract_all_numbers_series_name_no_keyword():
    # Pure series name with no recognized keyword -> []
    assert kce.extract_all_numbers("Series Name") == []


def test_extract_all_numbers_part_keyword():
    # 'Vol 1 Part 2' - only the first recognized set is returned
    assert kce.extract_all_numbers("Vol 1 Part 2") == [1]


# ---------------------------------------------------------------------------
# has_multiple_numbers
# ---------------------------------------------------------------------------

def test_has_multiple_numbers_single_volume():
    # 'Volume 1' -> ['1'] -> len 1 -> False
    assert kce.has_multiple_numbers("Volume 1") is False


def test_has_multiple_numbers_range_has_two():
    # 'Vol 1-3' -> ['1', '3'] -> len 2 -> True
    assert kce.has_multiple_numbers("Vol 1-3") is True


def test_has_multiple_numbers_decimal_is_one_match():
    # FLAG: 'Chapter 1.5' -> regex \d+\.[0-9]+ matches '1.5' as one token -> False
    # (legacy tests.py may have incorrectly expected True for this input)
    assert kce.has_multiple_numbers("Chapter 1.5") is False


def test_has_multiple_numbers_no_numbers():
    assert kce.has_multiple_numbers("No numbers") is False


def test_has_multiple_numbers_two_separate_numbers():
    # '1 2' -> ['1', '2'] -> len 2 -> True
    assert kce.has_multiple_numbers("1 2") is True


def test_has_multiple_numbers_single_large():
    assert kce.has_multiple_numbers("10") is False


def test_has_multiple_numbers_single_decimal():
    # '10.5' -> ['10.5'] -> len 1 -> False
    assert kce.has_multiple_numbers("10.5") is False


def test_has_multiple_numbers_two_zero_decimals():
    # '2.0' -> matches \d+\.[0-9]+ as one token -> False
    assert kce.has_multiple_numbers("2.0") is False


def test_has_multiple_numbers_v_prefix():
    # 'v01' -> ['01'] -> len 1 -> False
    assert kce.has_multiple_numbers("v01") is False


def test_has_multiple_numbers_v_prefix_two():
    # 'v01 c02' -> ['01', '02'] -> len 2 -> True
    assert kce.has_multiple_numbers("v01 c02") is True
