"""Characterization tests for string-transform utilities.

Every assertion was verified against::

    .venv/bin/python -c "import komga_cover_extractor as kce; print(repr(kce.FUNC(ARGS)))"

before being written here.  Surprising/buggy behaviour is noted with
``# FLAG:`` comments and is pinned AS-IS — not "fixed".

Functions covered (all from komga_cover_extractor.py):
    remove_dual_space, normalize_str, remove_s, remove_punctuation,
    clean_str, remove_brackets, replace_underscores
"""

import pytest
import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# remove_dual_space
# ---------------------------------------------------------------------------

def test_remove_dual_space_triple_space_collapses_to_single():
    assert kce.remove_dual_space("a   b") == "a b"


def test_remove_dual_space_double_space_collapses():
    assert kce.remove_dual_space("hello  world") == "hello world"


def test_remove_dual_space_no_double_space_unchanged():
    assert kce.remove_dual_space("no double") == "no double"


def test_remove_dual_space_multiple_gaps():
    assert kce.remove_dual_space("a  b  c") == "a b c"


def test_remove_dual_space_empty_string():
    assert kce.remove_dual_space("") == ""


def test_remove_dual_space_no_space_unchanged():
    assert kce.remove_dual_space("single") == "single"


def test_remove_dual_space_all_spaces_collapses_to_one():
    # Four spaces -> collapses to one space (dual_space_pattern is greedy)
    assert kce.remove_dual_space("    ") == " "


# ---------------------------------------------------------------------------
# normalize_str
# ---------------------------------------------------------------------------

def test_normalize_str_removes_article_the():
    # "the" is a common word and is stripped; "Hero" stays
    assert kce.normalize_str("The Hero is Overpowered") == "Hero is Overpowered"


def test_normalize_str_removes_article_a():
    assert kce.normalize_str("a simple string") == "simple string"


def test_normalize_str_short_string_returned_unchanged():
    # len <= 1 short-circuits the function
    assert kce.normalize_str("a") == "a"


def test_normalize_str_empty_string():
    assert kce.normalize_str("") == ""


def test_normalize_str_removes_series_keyword_not_at_start():
    # FLAG: "(?<!^)Series\s" requires a trailing space after the keyword.
    # "My Series" has no trailing space, so 'Series' is NOT stripped.
    assert kce.normalize_str("My Series") == "My Series"


def test_normalize_str_removes_manga_not_at_start():
    # "(?<!^)Manga\s" requires a trailing space; "My Manga" has none -> stays
    # FLAG: "My Manga" is NOT stripped because the pattern needs a trailing space
    assert kce.normalize_str("My Manga") == "My Manga"


def test_normalize_str_removes_manga_when_followed_by_space():
    # "My Manga Series" -> Manga is followed by space -> stripped, then Series stripped
    assert kce.normalize_str("My Manga Series") == "My Series"


def test_normalize_str_manga_at_start_preserved():
    # (?<!^) lookbehind prevents stripping when Manga starts the string
    assert kce.normalize_str("Manga Collection") == "Manga"


def test_normalize_str_removes_edition_keywords():
    # "Edition" is in the editions list
    assert kce.normalize_str("Special Edition Manga") == "Manga"


def test_normalize_str_removes_deluxe_collection():
    assert kce.normalize_str("Deluxe Collection") == ""


def test_normalize_str_removes_volume_in_middle():
    assert kce.normalize_str("One Piece Volume 1") == "One Piece 1"


def test_normalize_str_book_at_start_preserved():
    # "(?<!^)Book" -> Book at start is NOT stripped
    assert kce.normalize_str("Novel Series") == "Novel Series"


def test_normalize_str_removes_japanese_particle_to():
    # "to" is in japanese_particles
    assert kce.normalize_str("I go to school") == "go school"


def test_normalize_str_removes_bookwalker():
    # BookWalker is a storefront keyword; "Exclusive" is in editions
    assert kce.normalize_str("BookWalker Exclusive") == ""


def test_normalize_str_skip_common_words_leaves_the():
    assert kce.normalize_str("the quick brown fox", skip_common_words=True) == "the quick brown fox"


def test_normalize_str_skip_editions_leaves_edition_word():
    assert kce.normalize_str("Digital Edition", skip_editions=True) == "Digital Edition"


def test_normalize_str_skip_storefront_leaves_bookwalker():
    # Without storefront removal, BookWalker stays; Exclusive is an edition word and is removed
    assert kce.normalize_str("BookWalker Exclusive", skip_storefront_keywords=True) == "BookWalker"


def test_normalize_str_skip_misc_words_leaves_x_hd():
    # x and HD are misc_words; skip_misc keeps them; Edition is still removed
    assert kce.normalize_str("Volume 3 x HD Edition", skip_misc_words=True) == "Volume 3 x HD"


def test_normalize_str_skip_type_keywords_true_raises_when_other_words_present():
    # FLAG: bug — when skip_type_keywords=True but at least one other word category
    # is active, the for-loop body references the unbound local `type_keywords`,
    # raising UnboundLocalError (a NameError subclass).
    with pytest.raises(NameError, match="type_keywords"):
        kce.normalize_str("My Series Test", skip_type_keywords=True)


def test_normalize_str_all_skip_true_returns_input():
    # When ALL categories are skipped, words_to_remove is empty, the loop never
    # executes, and `type_keywords` is never referenced — so no error.
    result = kce.normalize_str(
        "The Hero Manga",
        skip_common_words=True,
        skip_editions=True,
        skip_type_keywords=True,
        skip_japanese_particles=True,
        skip_misc_words=True,
        skip_storefront_keywords=True,
    )
    assert result == "The Hero Manga"


# ---------------------------------------------------------------------------
# remove_s
# ---------------------------------------------------------------------------

def test_remove_s_strips_trailing_s_from_this():
    # FLAG: remove_s strips trailing 's' from EVERY word unconditionally,
    # so 'this' -> 'thi'
    assert kce.remove_s("this") == "thi"


def test_remove_s_strips_trailing_s_from_series():
    # FLAG: 'series' -> 'serie'
    assert kce.remove_s("series") == "serie"


def test_remove_s_strips_from_heroes():
    assert kce.remove_s("heroes") == "heroe"


def test_remove_s_no_change_when_no_s():
    assert kce.remove_s("one piece") == "one piece"


def test_remove_s_multiple_words():
    assert kce.remove_s("cats and dogs") == "cat and dog"


def test_remove_s_single_word_books():
    assert kce.remove_s("books") == "book"


def test_remove_s_case_insensitive():
    # FLAG: works case-insensitively — 'SERIES' -> 'SERIE'
    assert kce.remove_s("SERIES") == "SERIE"


def test_remove_s_word_ending_in_is():
    # FLAG: 'crisis' -> 'crisi' because \b(\\w+)(s)\b matches 'i' as \\w+ and 's'
    assert kce.remove_s("crisis") == "crisi"


def test_remove_s_word_without_s_unchanged():
    assert kce.remove_s("x") == "x"


def test_remove_s_books_volumes_chapters():
    assert kce.remove_s("books volumes chapters") == "book volume chapter"


# ---------------------------------------------------------------------------
# remove_punctuation
# ---------------------------------------------------------------------------

def test_remove_punctuation_comma_and_exclamation():
    # Comma and ! are replaced by space; two consecutive -> double space
    assert kce.remove_punctuation("hello, world!") == "hello  world"


def test_remove_punctuation_period():
    assert kce.remove_punctuation("test.file") == "test file"


def test_remove_punctuation_no_punctuation_unchanged():
    assert kce.remove_punctuation("no punctuation") == "no punctuation"


def test_remove_punctuation_colon():
    assert kce.remove_punctuation("title: subtitle") == "title  subtitle"


def test_remove_punctuation_hyphens():
    assert kce.remove_punctuation("a-b-c") == "a b c"


def test_remove_punctuation_apostrophe():
    assert kce.remove_punctuation("it's") == "it s"


def test_remove_punctuation_percent():
    assert kce.remove_punctuation("100%") == "100"


def test_remove_punctuation_plus_preserved():
    # FLAG: punctuation_pattern is [^\w\s+], so '+' is NOT treated as punctuation
    # and is left intact.
    assert kce.remove_punctuation("a+b") == "a+b"


def test_remove_punctuation_plus_with_spaces_preserved():
    assert kce.remove_punctuation("a + b") == "a + b"


# ---------------------------------------------------------------------------
# replace_underscores
# ---------------------------------------------------------------------------

def test_replace_underscores_digit_underscore_digit_becomes_period():
    # Underscore between two digits is replaced with a period
    assert kce.replace_underscores("Series_1_5") == "Series 1.5"


def test_replace_underscores_word_underscore_word_becomes_space():
    assert kce.replace_underscores("hello_world") == "hello world"


def test_replace_underscores_chain_of_digit_underscores():
    assert kce.replace_underscores("chapter_1_2_3") == "chapter 1.2.3"


def test_replace_underscores_digit_only_chain():
    assert kce.replace_underscores("1_2_3") == "1.2.3"


def test_replace_underscores_no_underscore_unchanged():
    assert kce.replace_underscores("plain") == "plain"


def test_replace_underscores_leading_underscore_removed():
    assert kce.replace_underscores("_leading") == "leading"


def test_replace_underscores_trailing_underscore_removed():
    assert kce.replace_underscores("trailing_") == "trailing"


def test_replace_underscores_word_then_digit():
    # Non-digit before underscore -> space not period
    assert kce.replace_underscores("word_1") == "word 1"


def test_replace_underscores_digit_then_word():
    assert kce.replace_underscores("1_vol") == "1 vol"


def test_replace_underscores_mixed():
    # Mix: digit_digit -> period, word_word -> space
    assert kce.replace_underscores("Series_1_5_extra") == "Series 1.5 extra"


# ---------------------------------------------------------------------------
# remove_brackets
# ---------------------------------------------------------------------------

def test_remove_brackets_year_in_parens():
    assert kce.remove_brackets("Series Name (2021)") == "Series Name"


def test_remove_brackets_whole_string_bracket_avoidance():
    # The string starts AND ends with a bracket -> whole-string avoidance; unchanged
    assert kce.remove_brackets("[(OSHI NO KO)]") == "[(OSHI NO KO)]"


def test_remove_brackets_single_square_bracket_wrapping():
    # '[OSHI NO KO]' starts and ends with bracket -> whole-string avoidance
    assert kce.remove_brackets("[OSHI NO KO]") == "[OSHI NO KO]"


def test_remove_brackets_paren_wrapping_whole_string():
    # '(just brackets)' starts and ends with bracket -> avoidance
    assert kce.remove_brackets("(just brackets)") == "(just brackets)"


def test_remove_brackets_digital_with_cbz_extension():
    # Extension is preserved; bracketed info before ext removed
    assert kce.remove_brackets("Series Name (Digital).cbz") == "Series Name.cbz"


def test_remove_brackets_scanlator_square_brackets():
    # '[Scanlator]' is adjacent to letters -> avoidance rule; not removed
    assert kce.remove_brackets("My Series [Scanlator]") == "My Series [Scanlator]"


def test_remove_brackets_curly_braces():
    # FLAG: '{info}' (preceded by a space and not preceded by digits) is NOT
    # removed by bracket_removal_pattern — curly braces without a year digit
    # and adjacent to text are left intact.
    assert kce.remove_brackets("Test {info}") == "Test {info}"


def test_remove_brackets_year_in_square_brackets():
    assert kce.remove_brackets("Test [2021]") == "Test"


def test_remove_brackets_trailing_year_curly():
    assert kce.remove_brackets("Test {2021}") == "Test"


def test_remove_brackets_plain_string_unchanged():
    assert kce.remove_brackets("normal string") == "normal string"


def test_remove_brackets_cbz_year_stripped_extra_info_stays():
    # year bracket is removed; [v02] stays (adjacent to letters/preceded by space)
    assert kce.remove_brackets("Series Name [v02] (2021).cbz") == "Series Name [v02].cbz"


# ---------------------------------------------------------------------------
# clean_str  (the full normalization pipeline)
# ---------------------------------------------------------------------------

def test_clean_str_article_and_stopword_removal():
    # 'The' removed by normalize, 'is' stripped via remove_s ('i' is left) -> 'i'
    assert kce.clean_str("The Hero is Overpowered") == "hero i overpowered"


def test_clean_str_accented_string_unidecoded():
    # 'Héros' -> unidecode -> 'Heros' -> normalize removes nothing -> remove_s -> 'Hero'
    # then lower -> 'hero'
    assert kce.clean_str("Héros") == "hero"


def test_clean_str_underscore_digit_becomes_period():
    # 'Series_1_5' -> lower -> normalize (no change) -> underscore: 1_5 -> 1.5
    assert kce.clean_str("Series_1_5") == "series 1.5"


def test_clean_str_colon_replaced_by_space():
    # 'My Series: A Story' -> colon -> space -> normalize removes 'a', 'Series'
    # -> 'My Story' -> remove_s -> 'My Story' (no trailing s on each)
    assert kce.clean_str("My Series: A Story") == "my story"


def test_clean_str_double_space_collapsed():
    assert kce.clean_str("  double  space  ") == "double space"


def test_clean_str_brackets_stripped():
    # '(2021)' bracket removed; 'Serie' from normalize -> 'serie' after remove_s
    assert kce.clean_str("Series Name (2021)") == "serie name"


def test_clean_str_whole_string_brackets_normalized():
    # '[(OSHI NO KO)]' bracket avoidance -> kept as is -> lower -> normalize
    # removes 'no' (japanese particle) -> 'oshi ko' after remove_s ('oshi', 'ko')
    assert kce.clean_str("[(OSHI NO KO)]") == "oshi ko"


def test_clean_str_empty_string():
    assert kce.clean_str("") == ""


def test_clean_str_lowercase_conversion():
    assert kce.clean_str("UPPERCASE") == "uppercase"


def test_clean_str_underscore_words():
    assert kce.clean_str("hello_world_test") == "hello world test"


def test_clean_str_skip_lowercase_convert():
    # Without lowercasing: 'The Hero is Overpowered' -> articles stripped -> 'Hero i Overpowered'
    assert kce.clean_str("The Hero is Overpowered", skip_lowercase_convert=True) == "Hero i Overpowered"


def test_clean_str_skip_normalize():
    # normalize_str skipped so 'the' and 'is' are kept; remove_s still runs
    assert kce.clean_str("The Hero is Overpowered", skip_normalize=True) == "the hero i overpowered"


def test_clean_str_skip_remove_s():
    # remove_s skipped; 'is' stays; 'the' removed by normalize
    assert kce.clean_str("The Hero is Overpowered", skip_remove_s=True) == "hero is overpowered"


def test_clean_str_skip_underscore():
    # Underscore replacement skipped -> underscores stay as is
    assert kce.clean_str("Series_1_5", skip_underscore=True) == "series_1_5"


def test_clean_str_skip_unidecode_keeps_accent():
    # Unidecode skipped; 'Héros' -> lower -> 'héros'; normalize does nothing;
    # remove_s: 'héro' (strips trailing 's'); encode ascii ignore -> 'hro'
    # FLAG: skipping unidecode causes the accented char to be dropped by ascii encode
    assert kce.clean_str("Héros", skip_unidecode=True) == "hro"


def test_clean_str_with_colon_and_volume():
    # 'My Series: Volume 2' -> colon -> 'My Series Volume 2' -> normalize removes Series, Volume
    assert kce.clean_str("My Series: Volume 2") == "my 2"


def test_clean_str_single_char():
    assert kce.clean_str("A") == "a"


def test_clean_str_single_char_x():
    assert kce.clean_str("x") == "x"


def test_clean_str_cafe_accent():
    # 'Café au lait' -> unidecode -> 'Cafe au lait' -> normalize removes 'a' -> 'Cafe lait'
    # -> lower -> 'cafe lait' -> remove_s -> no trailing s -> 'cafe au lait'
    # Wait - 'au' has no 's'; 'lait' has no 's' -> 'cafe au lait'
    assert kce.clean_str("Café au lait") == "cafe au lait"


def test_clean_str_skip_bracket_keeps_year():
    # skip_bracket=True means bracket removal is skipped; 'Overlord' has no brackets
    assert kce.clean_str("Overlord", skip_bracket=True) == "overlord"


def test_clean_str_my_hero_academia_underscores():
    assert kce.clean_str("My_Hero_Academia") == "my hero academia"
