#!/usr/bin/env python3
import csv

from komga_cover_extractor import *


class Volume:
    def __init__(
        self,
        file_type,
        series_name,
        shortened_series_name,
        volume_year,
        volume_number,
        volume_part,
        index_number,
        is_fixed,
        release_group,
        name,
        extensionless_name,
        basename,
        extension,
        root,
        path,
        extensionless_path,
        extras,
        publisher,
        is_premium,
        subtitle,
        header_extension,
        multi_volume=None,
        is_one_shot=None,
    ):
        self.file_type = file_type
        self.series_name = series_name
        self.shortened_series_name = shortened_series_name
        self.volume_year = volume_year
        self.volume_number = volume_number
        self.volume_part = volume_part
        self.index_number = index_number
        self.is_fixed = is_fixed
        self.release_group = release_group
        self.name = name
        self.extensionless_name = extensionless_name
        self.basename = basename
        self.extension = extension
        self.root = root
        self.path = path
        self.extensionless_path = extensionless_path
        self.extras = extras
        self.publisher = publisher
        self.is_premium = is_premium
        self.subtitle = subtitle
        self.header_extension = header_extension
        self.multi_volume = multi_volume
        self.is_one_shot = is_one_shot


# test def set_num_as_float_or_int(volume_number, silent=False):
def test_set_num_as_float_or_int():
    assert set_num_as_float_or_int(1) == 1
    assert set_num_as_float_or_int(1.0) == 1
    assert set_num_as_float_or_int(1.1) == 1.1
    # try string
    assert set_num_as_float_or_int("1") == 1
    # try array of numbers
    assert set_num_as_float_or_int([1, 2, 3]) == "1-2-3"
    # try array of strings
    assert set_num_as_float_or_int(["1", "2", "3"]) == "1-2-3"
    # assert set_num_as_float_or_int("01-02") == "1-2"
    # assert set_num_as_float_or_int("01.3-02.2") == "1.3-2.2"
    # assert set_num_as_float_or_int(["10", "11.5"]) == "10-11.5"


# test def remove_hidden_files(files):
def test_remove_hidden_files():
    assert remove_hidden_files([".DS_Store", "test.jpg"]) == ["test.jpg"]
    assert remove_hidden_files(["test.jpg", ".DS_Store"]) == ["test.jpg"]
    assert remove_hidden_files(["test.jpg"]) == ["test.jpg"]
    assert remove_hidden_files([".DS_Store"]) == []
    assert remove_hidden_files([]) == []


# test def remove_ignored_folders(dirs):
def test_remove_ignored_folders():
    assert remove_ignored_folders(["isekai", "test"]) == ["isekai"]


# test def remove_hidden_folders(dirs):
def test_remove_hidden_folders():
    assert remove_hidden_folders([".DS_Store", "test"]) == ["test"]
    assert remove_hidden_folders(["test", ".DS_Store"]) == ["test"]
    assert remove_hidden_folders(["test"]) == ["test"]
    assert remove_hidden_folders([".DS_Store"]) == []
    assert remove_hidden_folders([]) == []


# test def remove_unaccepted_file_types(files, root, accepted_extensions):
# def test_remove_unaccepted_file_types(): # needs actual files for isfile() to pass
#     assert remove_unaccepted_file_types(["test.cbz"], "", ["cbz"]) == ["test.cbz"]
#     assert remove_unaccepted_file_types(["test.epub"], "", ["epub"]) == ["test.epub"]
#     assert remove_unaccepted_file_types(["test.cbz"], "", ["epub"]) == []
#     assert remove_unaccepted_file_types(["test.epub"], "", ["cbz"]) == []


# test def filter_non_chapters(files):
def test_filter_non_chapters():
    assert filter_non_chapters(["test c01.cbz"]) == []
    assert filter_non_chapters(["test v01.cbz"]) == ["test v01.cbz"]
    assert filter_non_chapters(["test c01.cbz", "test v01.cbz"]) == ["test v01.cbz"]
    assert filter_non_chapters(["test (2006).cbz"]) == ["test (2006).cbz"]


# test def contains_chapter_keywords(file_name):
def test_contains_chapter_keywords():
    assert (
        contains_chapter_keywords("High School Family - Kokosei Kazoku c042 (2021).cbz")
        == True
    )
    assert (
        contains_chapter_keywords("High School Family - Kokosei Kazoku 042 (2021).cbz")
        == True
    )
    assert (
        contains_chapter_keywords(
            "High School Family - Kokosei Kazoku - 042 - (2021).cbz"
        )
        == True
    )
    assert (
        contains_chapter_keywords("High_School_Family_-_Kokosei_Kazoku_c042_(2021).cbz")
        == True
    )
    assert (
        contains_chapter_keywords("High_School_Family_-_Kokosei_Kazoku_042_(2021).cbz")
        == True
    )
    assert (
        contains_chapter_keywords(
            "High_School_Family_-_Kokosei_Kazoku_-_042_-_(2021).cbz"
        )
        == True
    )
    assert (
        contains_chapter_keywords("High School Family - Kokosei Kazoku v042 (2021).cbz")
        == False
    )
    assert (
        contains_chapter_keywords("Investor-Z v01 (2019) (Digital) (c1fi7) (ED).cbz")
        == False
    )


# test def contains_volume_keywords(file):
# "LN|Light Novels?|Novels?|Books?|Volumes?|Vols?|V|第|Discs?"
def test_contains_volume_keywords():
    assert contains_volume_keywords("Rebuild LN01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild LN 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild LN.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild LN. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild LN01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild LN 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild LN.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild LN. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Light Novel01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Light Novel 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Light Novel.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Light Novel. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Light Novel01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Light Novel 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Light Novel.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Light Novel. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Novel01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Novel 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Novel.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Novel. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Novel01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Novel 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Novel.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Novel. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Book01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Book 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Book.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Book. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Book01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Book 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Book.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Book. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Volume01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Volume 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Volume.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Volume. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Volume01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Volume 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Volume.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Volume. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Vols01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Vols 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Vols.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Vols. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Vols01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Vols 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Vols.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Vols. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Vol01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Vol 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Vol.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Vol. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Vol01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Vol 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Vol.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Vol. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild V01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild V 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild V.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild V. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild V01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild V 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild V.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild V. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild 第01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild 第 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild 第.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild 第. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild 第01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild 第 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild 第.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild 第. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Disc01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Disc 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Disc.01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Disc. 01 (2022).cbz") == True
    assert contains_volume_keywords("Rebuild Disc01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Disc 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Disc.01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild Disc. 01-02 (2021).cbz") == True
    assert contains_volume_keywords("Rebuild 01 (2022).cbz") == False
    assert contains_volume_keywords("Rebuild 01-02 (2021).cbz") == False
    assert contains_volume_keywords("4 Cut Hero c100.4.cbz") == False


# test def get_file_extension(file):
def test_get_file_extension():
    assert get_file_extension("test.jpg") == ".jpg"
    assert get_file_extension("test") == ""
    assert get_file_extension("test.") == "."
    assert get_file_extension("test.jpg.png") == ".png"
    assert get_file_extension("test.jpg.png.zip") == ".zip"


# test def get_extensionless_name(file):
def test_get_extensionless_name():
    assert get_extensionless_name("test.jpg") == "test"
    assert get_extensionless_name("test") == "test"
    assert get_extensionless_name("test.") == "test"
    assert get_extensionless_name("test.jpg.png") == "test.jpg"
    assert get_extensionless_name("test.jpg.png.zip") == "test.jpg.png"


# test def is_volume_one(volume_name):
# "LN|Light Novels?|Novels?|Books?|Volumes?|Vols?|V|第|Discs?"
# "chapters?|chaps?|chs?|cs?"
def test_is_volume_one():
    assert is_volume_one("Rebuild Light Novel01 (2022).cbz") == True
    assert is_volume_one("Rebuild Light Novel 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Light Novel.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Light Novel. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Novel01 (2022).cbz") == True
    assert is_volume_one("Rebuild Novel 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Novel.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Novel. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Book01 (2022).cbz") == True
    assert is_volume_one("Rebuild Book 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Book.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Book. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Volume01 (2022).cbz") == True
    assert is_volume_one("Rebuild Volume 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Volume.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Volume. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Vols01 (2022).cbz") == True
    assert is_volume_one("Rebuild Vols 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Vols.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Vols. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Vol01 (2022).cbz") == True
    assert is_volume_one("Rebuild Vol 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Vol.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Vol. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild V01 (2022).cbz") == True
    assert is_volume_one("Rebuild V 01 (2022).cbz") == True
    assert is_volume_one("Rebuild V.01 (2022).cbz") == True
    assert is_volume_one("Rebuild V. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild 第01 (2022).cbz") == True
    assert is_volume_one("Rebuild 第 01 (2022).cbz") == True
    assert is_volume_one("Rebuild 第.01 (2022).cbz") == True
    assert is_volume_one("Rebuild 第. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Disc01 (2022).cbz") == True
    assert is_volume_one("Rebuild Disc 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Disc.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Disc. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter.01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter. 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter.01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chapter. 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap.01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap. 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap.01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Chap. 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch01 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch.01 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch.01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch. 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch.01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild Ch. 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild C01 (2022).cbz") == True
    assert is_volume_one("Rebuild C 01 (2022).cbz") == True
    assert is_volume_one("Rebuild C.01 (2022).cbz") == True
    assert is_volume_one("Rebuild C. 01 (2022).cbz") == True
    assert is_volume_one("Rebuild C01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild C 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild C.01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild C. 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild C01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild C 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild C.01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild C. 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild 01 (2022).cbz") == True
    assert is_volume_one("Rebuild 01-03 (2022).cbz") == True
    assert is_volume_one("Rebuild 01-02-03 (2022).cbz") == True
    assert is_volume_one("Rebuild (2022).cbz") == False
    assert is_volume_one("Rebuild Volume One (2022).cbz") == True
    assert is_volume_one("4 Cut Hero c100.4.cbz") == False


# test def get_series_name_from_chapter(name, chapter_number=""):
def test_get_series_name_from_chapter():
    assert get_series_name_from_chapter("Red Chapter01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter.01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter. 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter.01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter. 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter.01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter. 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter.01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter. 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter.01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chapter. 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chapter.01-02-03 (2022).cbz", 1) == "Red"
    assert (
        get_series_name_from_chapter("Red - Chapter. 01-02-03 (2022).cbz", 1) == "Red"
    )
    assert get_series_name_from_chapter("Red Chap01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap.01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap. 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap.01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap. 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap.01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap. 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap.01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap. 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap.01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Chap. 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap.01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Chap. 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch.01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch. 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch.01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch. 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch.01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch. 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch.01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch. 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch.01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red Ch. 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch.01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - Ch. 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C.01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C. 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C.01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C. 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C.01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C. 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C.01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C. 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C.01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red C. 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C.01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - C. 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red 01-02-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - 01 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - 01-03 (2022).cbz", 1) == "Red"
    assert get_series_name_from_chapter("Red - 01-02-03 (2022).cbz", 1) == "Red"
    assert (
        get_series_name_from_chapter(
            "All About Lust - 30x1 - Season Epilogue (Digital) (Cobalt001).cbz", 30
        )
        == "All About Lust"
    )
    assert (
        get_series_name_from_chapter("Crossing Time - 0074.00 - Chapter 74.cbz", 74)
        == "Crossing Time"
    )
    assert (
        get_series_name_from_chapter(
            "15 Minutes 09 (2018) (Digital) (repressedrage).cbz", 9
        )
        == "15 Minutes"
    )
    assert (
        get_series_name_from_chapter(
            "A Cursed Sword's Daily Life 001 (2021) (Digital) (Shizu).cbz", 1
        )
        == "A Cursed Sword's Daily Life"
    )
    assert get_series_name_from_chapter("4 Cut Hero c100.4.cbz", 100.4) == "4 Cut Hero"


# test def get_folder_type(files, file_type):
def test_get_folder_type():
    assert get_folder_type(["test.pdf"], extensions=[".pdf"]) == 100
    assert get_folder_type(["test.pdf", "test.cbz"], extensions=[".pdf"]) == 50
    assert (
        get_folder_type(
            ["test.pdf", "test.cbz", "test.epub", "test_two.epub"], extensions=[".pdf"]
        )
        == 25
    )
    # assert (
    #     get_folder_type(["test v01.cbz", "test v02.cbz"], file_type="volume")
    #     == 100
    # )
    # assert (
    #     get_folder_type(["test v01.cbz", "test v02.cbz"], file_type="chapter")
    #     == 0
    # )
    # assert (
    #     get_folder_type(["test c01.cbz", "test c02.cbz"], file_type="chapter")
    #     == 100
    # )


# test def check_for_multi_volume_file(file_name, chapter=False):
# "LN|Light Novels?|Novels?|Books?|Volumes?|Vols?|V|第|Discs?"
# "chapters?|chaps?|chs?|cs?"
def test_check_for_multi_volume_file():
    assert check_for_multi_volume_file("DAR LN01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR LN 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR LN.01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR LN. 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR LN01-02-03 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR LN 01-02-03 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR LN.01-02-03 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR LN. 01-02-03 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Light Novels01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Light Novels 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Light Novels.01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Light Novels. 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Light Books01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Light Books 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Light Books.01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Light Books. 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Volumes01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Volumes 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Volumes.01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Volumes. 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Vols01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Vols 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Vols.01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Vols. 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR V01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR V 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR V.01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR V. 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR 第01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR 第 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR 第.01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR 第. 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Discs01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Discs 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Discs.01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR Discs. 01-02 (2022).cbz") == True
    assert check_for_multi_volume_file("DAR chapters01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chapters 01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chapters.01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chapters. 01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chapters01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chapters 01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chapters.01-02-03 (2022).cbz", True) == True
    assert (
        check_for_multi_volume_file("DAR chapters. 01-02-03 (2022).cbz", True) == True
    )
    assert check_for_multi_volume_file("DAR chaps01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chaps 01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chaps.01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chaps. 01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chaps01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chaps 01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chaps.01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chaps. 01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chs01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chs 01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chs.01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chs. 01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chs01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chs 01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chs.01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR chs. 01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR c01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR c 01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR c.01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR c. 01-02 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR c01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR c 01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR c.01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR c. 01-02-03 (2022).cbz", True) == True
    assert check_for_multi_volume_file("DAR LN01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR LN 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR LN.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR LN. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Light Novel01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Light Novel 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Light Novel.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Light Novel. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Novel01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Novel 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Novel.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Novel. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Book01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Book 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Book.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Book. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Vol01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Vol 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Vol.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Vol. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Volume01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Volume 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Volume.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Volume. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR V01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR V 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR V.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR V. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Vols01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Vols 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Vols.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Vols. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Volumes01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Volumes 01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Volumes.01 (2022).cbz") == False
    assert check_for_multi_volume_file("DAR Volumes. 01 (2022).cbz") == False
    assert check_for_multi_volume_file("4 Cut Hero c100.4.cbz") == False


# test def get_min_and_max_numbers(string):
def test_convert_list_of_numbers_to_array():
    assert get_min_and_max_numbers("1-2-3-4-5") == [1, 5]
    assert get_min_and_max_numbers("1-2-3-4-5-6") == [1, 6]
    assert get_min_and_max_numbers("1-2-3-4-5-6-7") == [1, 7]


# test def get_release_number_cache(files, chapter=False):
def test_get_release_number_cache():
    assert get_release_number_cache("DAR LN01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR LN 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR LN.01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR LN. 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR LN01-02-03 (2022).cbz") == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR LN 01-02-03 (2022).cbz") == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR LN.01-02-03 (2022).cbz") == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR LN. 01-02-03 (2022).cbz") == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR Light Novels01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Light Novels 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Light Novels.01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Light Novels. 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Light Books01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Light Books 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Light Books.01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Light Books. 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Volumes01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Volumes 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Volumes.01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Volumes. 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Vols01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Vols 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Vols.01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Vols. 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR V01-02 (2022).cbz") == [1.0, 2.0]
    assert get_release_number_cache("DAR V 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR V.01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR V. 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR 第01-02 (2022).cbz") == [1.0, 2.0]
    assert get_release_number_cache("DAR 第 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR 第.01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR 第. 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Discs01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Discs 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Discs.01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR Discs. 01-02 (2022).cbz") == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chapters01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chapters 01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chapters.01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chapters. 01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chapters01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chapters 01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chapters.01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chapters. 01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chaps01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chaps 01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chaps.01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chaps. 01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chaps01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chaps 01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chaps.01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chaps. 01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chs01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chs 01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chs.01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chs. 01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR chs01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chs 01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chs.01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR chs. 01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR c01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR c 01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR c.01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR c. 01-02 (2022).cbz", True) == [
        1.0,
        2.0,
    ]
    assert get_release_number_cache("DAR c01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR c 01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR c.01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR c. 01-02-03 (2022).cbz", True) == [
        1.0,
        3.0,
    ]
    assert get_release_number_cache("DAR LN01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR LN 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR LN.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR LN. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Light Novel01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Light Novel 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Light Novel.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Light Novel. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Novel01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Novel 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Novel.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Novel. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Book01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Book 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Book.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Book. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Vol01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Vol 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Vol.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Vol. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Volume01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Volume 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Volume.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Volume. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR V01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR V 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR V.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR V. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Vols01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Vols 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Vols.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Vols. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Volumes01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Volumes 01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Volumes.01 (2022).cbz") == 1.0
    assert get_release_number_cache("DAR Volumes. 01 (2022).cbz") == 1.0
    assert get_release_number_cache("4 Cut Hero c100.4.cbz", True) == 100.4
    assert (
        get_release_number_cache(
            "A Sign of Affection 020#1 (2021) (Digital) (1r0n).cbz", True
        )
        == 20
    )
    assert (
        get_release_number_cache(
            "What Does the Fox Say - 034x1 - Special Episode (Digital) (Cobalt001).cbz",
            True,
        )
        == 34
    )
    assert (
        get_release_number_cache(
            "The Art of Octopath Traveler - 2016-2020 (2024) (Digital) (LuCaZ).cbz",
        )
        == ""
    )


# test def get_volume_year(name):
def test_get_release_year():
    assert get_release_year("DAR v01 (2022).cbz") == "2022"
    assert get_release_year("DAR v01 (2022)") == "2022"
    assert get_release_year("DAR v01 2022") == None
    assert get_release_year("DAR v01") == None


# test def get_release_group(name, release_groups):
def test_get_extra_from_group():
    assert (
        get_extra_from_group(
            "DAR v01 (2022) (fixed) (danke-Empire).cbz", ["danke-Empire"]
        )
        == "danke-Empire"
    )
    assert (
        get_extra_from_group("DAR v01 (2022) (fixed) (danke-Empire).cbz", ["1r0n"])
        == ""
    )
    assert get_extra_from_group("DAR v01 (2022) (fixed) (1r0n).cbz", ["1r0n"]) == "1r0n"


# test def get_file_part(file, chapter=False):
def test_get_file_part():
    assert get_file_part("DAR v01 (2022) (fixed) (danke-Empire).cbz") == ""
    assert get_file_part("DAR v01 (2022) (fixed) (danke-Empire) (part 1).cbz") == 1
    assert get_file_part("DAR v01 (2022) (fixed) (danke-Empire) (part 2).cbz") == 2
    assert get_file_part("DAR v01 (2022) (fixed) (danke-Empire) (part 3).cbz") == 3
    assert get_file_part("Hi c001x2 (2022) (Digital) [nao].cbz", chapter=True) == 2
    assert get_file_part("Hi c001x3 (2022) (Digital) [nao].cbz", chapter=True) == 3
    assert get_file_part("Hi c001x4 (2022) (Digital) [nao].cbz", chapter=True) == 4
    assert get_file_part("Hi c001#5 (2022) (Digital) [nao].cbz", chapter=True) == 5


# test def get_keyword_score(name, file_type, ranked_keywords):
def test_get_keyword_score():
    keywords = [
        Keyword(r"danke-Empire", 1),
        Keyword(r"Digital", 1),
        Keyword(r"\(f\)", 1),
    ]
    assert (
        get_keyword_scores(
            "DAR v01 (2022) (Digital) (f) (danke-Empire).cbz",
            "volume",
            keywords,
        ).total_score
        == 3
    )


# test def remove_dual_space(s):
def test_remove_dual_space():
    assert remove_dual_space("test  test") == "test test"


# test def normalize_str(s):
def test_normalize_str():
    assert normalize_str("The Sword Saint") == "Sword Saint"


# test def clean_str(string):
def test_clean_str():
    assert clean_str("The, Sword, Saint!!!!") == "sword saint"


# test def convert_to_ascii(s):
# def test_convert_to_ascii():
#     assert convert_to_ascii("The Sword Saint") == "The Sword Saint"
#     assert convert_to_ascii("Le Saint Épée") == "Le Saint Epee"
#     assert convert_to_ascii("El Santo Espada") == "El Santo Espada"
#     assert convert_to_ascii("Der Schwertheilige") == "Der Schwertheilige"
#     assert convert_to_ascii("Il Santo Spadaccino") == "Il Santo Spadaccino"
#     assert convert_to_ascii("O Santo Espadachim") == "O Santo Espadachim"
#     assert convert_to_ascii("Saint Épée") == "Saint Epee"
#     assert convert_to_ascii("Santo Espada") == "Santo Espada"
#     assert convert_to_ascii("Schwertheilige") == "Schwertheilige"
#     assert convert_to_ascii("Santo Spadaccino") == "Santo Spadaccino"


# test def array_to_string(array, separator):
def test_array_to_string():
    assert array_to_string(["test", "test2"], ",") == "test,test2"
    assert array_to_string(["test", "test2"], " ") == "test test2"
    assert array_to_string(["test", "test2"], "-") == "test-test2"
    assert array_to_string(["test", "test2"], "") == "testtest2"


# test def remove_duplicates(items):
def test_remove_duplicates():
    assert remove_duplicates(["test", "test", "test2"]) == ["test", "test2"]
    assert remove_duplicates(["test", "test2", "test2"]) == ["test", "test2"]
    assert remove_duplicates(["test", "test2", "test"]) == ["test", "test2"]


# test def remove_brackets(string):
def test_remove_brackets():
    # test all types of brackets
    assert remove_brackets("test (test)") == "test (test)"
    assert remove_brackets("test [test]") == "test [test]"
    assert remove_brackets("test {test}") == "test {test}"
    assert remove_brackets("test (test).cbz") == "test.cbz"
    assert (
        remove_brackets("rent-a-(really shy!)-girlfriend (2009)")
        == "rent-a-(really shy!)-girlfriend"
    )
    assert (
        remove_brackets(
            "The Genius Prince's Guide to Raising a Nation Out of Debt (Hey, How About Treason) v01 [2019] [Yen Press] [LuCaZ].epub"
        )
        == "The Genius Prince's Guide to Raising a Nation Out of Debt (Hey, How About Treason) v01.epub"
    )
    assert (
        remove_brackets(
            "Defeating the Demon Lord's a Cinch (If You've Got a Ringer) v01 [2018] [Yen Press].epub"
        )
        == "Defeating the Demon Lord's a Cinch (If You've Got a Ringer) v01.epub"
    )
    assert remove_brackets("[(OSHI NO KO)] v01 (2018).cbz") == "[(OSHI NO KO)] v01.cbz"
    assert remove_brackets("[(OSHI NO KO)]") == "[(OSHI NO KO)]"


# test def replace_underscores(name):
def test_replace_underscores():
    assert replace_underscores("test_test") == "test test"
    assert replace_underscores("test_test_test") == "test test test"


# test def rename_files(only_these_files=[], group=False, test_mode=False):
def test_rename_files():
    global download_folders

    download_folders = ["/dl/Manga & Novels"]
    file_name = "test_file_list.txt"

    file_list_path = os.path.join(LOGS_DIR, file_name)

    files = get_lines_from_file(file_list_path)
    # files = ["Soul Land III ch 0000.0.cbz"]

    rename_files(files, download_folders=download_folders, test_mode=True)


# test def get_extras(file_name, root, chapter=False, series_name="", chapter_number=""):
def test_get_extras():
    assert get_extras(
        "test c015 (2023) (lol) (Digital) (AntsyLich).cbz",
        chapter=True,
        series_name="test",
    ) == ["(lol)", "(Digital)", "(AntsyLich)"]
    assert get_extras(
        "test v01 (2022) (Digital) (danke-Empire).cbz",
        series_name="test",
    ) == ["(Digital)", "(danke-Empire)"]
    assert get_extras(
        "test c001 (2022) (Digital) (danke-Empire).cbz",
        chapter=True,
        series_name="test",
    ) == ["(Digital)", "(danke-Empire)"]
    assert get_extras(
        "test c001 (2022) (Digital) (Digital) (danke-Empire).cbz",
        chapter=True,
        series_name="test",
    ) == ["(Digital)", "(danke-Empire)"]
    assert get_extras(
        "test c001 (2022) (Digital) (Digital) (danke-Empire) (Premium).cbz",
        chapter=True,
        series_name="test",
    ) == ["(Premium)", "(Digital)", "(danke-Empire)"]
    assert (
        get_extras(
            "4 Cut Hero c100.4.cbz",
            chapter=True,
            series_name="test",
        )
        == []
    )


# test def isfloat(x):
def test_isfloat():
    assert isfloat("1") == True
    assert isfloat("1.1") == True
    assert isfloat("1.1.1") == False


# test def isint(x):
def test_isint():
    assert isint("1") == True
    assert isint("1.1") == False
    assert isint("1.1.1") == False


# test def parse_html_tags(html):
def test_parse_html_tags():
    assert parse_html_tags("<p>test</p>") == {"p": "test"}
    assert parse_html_tags("<p>test</p><p>test2</p>") == {"p": "test", "p": "test2"}
    assert parse_html_tags("<p>test</p><p>test2</p><p>test3</p>") == {
        "p": "test",
        "p": "test2",
        "p": "test3",
    }


# test def check_for_exception_keywords(file_name, exception_keywords):
def test_check_for_exception_keywords():
    assert (
        check_for_exception_keywords(
            "test v01 (2022) (Digital) (One-shot).cbz", ["One-shot"]
        )
        == True
    )
    assert (
        check_for_exception_keywords(
            "test v01 (2022) (Digital) (One-shot).cbz", ["one-shot"]
        )
        == True
    )
    assert (
        check_for_exception_keywords(
            "test v01 (2022) (Digital) (One-shot).cbz", ["Eighty-Six"]
        )
        == False
    )


# test def has_one_set_of_numbers(string):
def test_has_one_set_of_numbers():
    assert has_one_set_of_numbers("test 01") == True
    assert has_one_set_of_numbers("test 01-02") == True
    assert has_one_set_of_numbers("test 01 02") == False


# test def has_multiple_numbers(file_name):
def test_has_multiple_numbers():
    assert has_multiple_numbers("test 01") == False
    assert has_multiple_numbers("test 01-02") == False
    assert has_multiple_numbers("test 01 02") == True
    assert has_multiple_numbers("test 01 02 03") == True
    assert has_multiple_numbers("test 01 01 01") == False


def test_sorting_volumes_by_volume_number():
    volumes = [
        Volume(
            "",
            "",
            "",
            "",
            7,
            "",
            7,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            "",
            False,
            "",
            "",
        ),
        Volume(
            "",
            "",
            "",
            "",
            2,
            "",
            2,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            "",
            False,
            "",
            "",
        ),
        Volume(
            "",
            "",
            "",
            "",
            1,
            "",
            1,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            "",
            False,
            "",
            "",
        ),
        Volume(
            "",
            "",
            "",
            "",
            4,
            "",
            4,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            "",
            False,
            "",
            "",
        ),
        Volume(
            "",
            "",
            "",
            "",
            6,
            "",
            6,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            "",
            False,
            "",
            "",
        ),
        Volume(
            "",
            "",
            "",
            "",
            5,
            "",
            5,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            "",
            False,
            "",
            "",
        ),
        Volume(
            "",
            "",
            "",
            "",
            103,
            "",
            103,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            "",
            False,
            "",
            "",
        ),
        Volume(
            "",
            "",
            "",
            "",
            [3.5, 3.6, 3.7, 3.8],
            "",
            [3.5, 3.6, 3.7, 3.8],
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            "",
            False,
            "",
            "",
        ),
    ]
    sorted(volumes, key=lambda x: get_sort_key(x.volume_number))
    pass


def test_organize_by_first_letter():
    # Test case 1: Empty string
    array_list = ["apple", "banana", "cherry"]
    string = ""
    position_to_insert_at = 1
    exclude = None
    expected_result = ["apple", "banana", "cherry"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test case 2: Non-empty string
    array_list = ["apple", "banana", "cherry"]
    string = "c"
    position_to_insert_at = 1
    exclude = "banana"
    expected_result = ["apple", "cherry", "banana"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test case 3: Non-empty string with no items to move
    array_list = ["apple", "banana", "cherry"]
    string = "d"
    position_to_insert_at = 1
    exclude = None
    expected_result = ["apple", "banana", "cherry"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test case 1.1: Empty string on array of two items
    array_list = ["apple", "banana"]
    string = ""
    position_to_insert_at = 1
    exclude = None
    expected_result = ["apple", "banana"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test case 2.1: Non-empty string on array of two items
    array_list = ["apple", "banana"]
    string = "b"
    position_to_insert_at = 1
    exclude = "banana"
    expected_result = ["apple", "banana"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test case 3.1: Non-empty string with no items to move on array of two items
    array_list = ["apple", "banana"]
    string = "d"
    position_to_insert_at = 1
    exclude = None
    expected_result = ["apple", "banana"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test case 1.2: Empty string on array of one item
    array_list = ["apple"]
    string = ""
    position_to_insert_at = 1
    exclude = None
    expected_result = ["apple"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test case 2.2: Non-empty string on array of one item
    array_list = ["apple"]
    string = "b"
    position_to_insert_at = 1
    exclude = "banana"
    expected_result = ["apple"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test case 3.2: Non-empty string with no items to move on array of one item
    array_list = ["apple"]
    string = "d"
    position_to_insert_at = 1
    exclude = None
    expected_result = ["apple"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test Case 1: Empty string, insert at position 2
    array_list = ["apple", "banana", "cherry"]
    string = ""
    position_to_insert_at = 2
    exclude = None
    expected_result = ["apple", "banana", "cherry"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test Case 2: Non-empty string, insert at position 2
    array_list = ["apple", "banana", "cherry"]
    string = "b"
    position_to_insert_at = 2
    exclude = ""
    expected_result = ["apple", "cherry", "banana"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )

    # Test Case 3: Non-empty string with no items to move, insert at position 2
    array_list = ["apple", "banana", "cherry"]
    string = "d"
    position_to_insert_at = 2
    exclude = None
    expected_result = ["apple", "banana", "cherry"]
    assert (
        organize_by_first_letter(array_list, string, position_to_insert_at, exclude)
        == expected_result
    )


class IncorrectItem:
    def __init__(self, file_name, item_one, item_two):
        self.file_name = file_name
        self.item_one = item_one
        self.item_two = item_two


# Validates that all values in our csv file are correct
def validate_csv():
    # read manga_novel_dataset.csv from root with pandas
    csv_file = os.path.join(ROOT_DIR, "manga_novel_dataset.csv")

    if not os.path.isfile(csv_file):
        print("manga_novel_dataset.csv not found")
        return

    incorrect_release_numbers = []
    incorrect_series_names = []
    incorrect_file_types = []
    skipped_files = [
        "03b. Yu-Gi-Oh! Transcend Game (2016) (Digital).cbz",
        "1 - Mushi, Eyeball and a Teddy Bear.epub",
        "2 - Mushi, Eyeball and Sterilization Disinfection.epub",
        "3 - Mushi, Eyeball and a Chocolate Parfait.epub",
        "3-Gatsu no Lion Review Guidebook - Beginner.cbz",
        "3-Gatsu no Lion Review Guidebook - Intermediate.cbz",
        "4 - Mushi, Eyeball and Lovesong.epub",
        "4 Cut Hero Episode 157.cbz",
        "5 - Mushi, Eyeball and Snow White.epub",
        "6 - Mushi, Eyeball and Damaged Hair.epub",
        "A Certain Magical Index - Volume SS1.epub",
        "A Certain Magical Index - Volume SS2.epub",
        "A Certain Magical Index New Testament 18 Bonus Short Story.epub",
        "A Certain Magical Index New Testament 20 Bonus Short Story.epub",
        "A Certain Magical Index SS v01 [Yen Press] [LuCaZ].epub",
        "A Certain Magical Index SS v02 [Yen Press] [LuCaZ].epub",
        "A Certain March 201st Volume.epub",
        "A Certain Scientific Railgun SS1.epub",
        "A Certain Scientific Railgun SS2.epub",
        "A Certain Scientific Railgun SS3.epub",
        "Ayakashi Triangle-Ch 89 - Shiv and The Shivers.cbz",
        "Ayakashi Triangle-Ch 91 Kanade.cbz",
        "Ayakashi Triangle-Ch 92 Reason to Help.cbz",
        "Ayakashi Triangle-Ch 93 Those in Love with an Ayakashi Medium.cbz",
        "Ayakashi Triangle-Ch 94 Ritta's Nightmare!.cbz",
        "Ayakashi Triangle-Ch 95 The Monster Within.cbz",
        "Barakamon v18+1 (2020) (Digital) (XRA-Empire).cbz",
        "BLEACH OFFICIAL CHARACTER BOOK 3 UNMASKED.cbz",
        "Boku wa Mari no Naka - c072-080 (v09) [CR].cbz",
        "Bouken Ou Beet v14c053-054.cbz",
        "Bouken Ou Beet v14c055-057 [RAW].cbz",
        "Campfire Cooking in Another World with My Absurd Skill Volume-1 Premium Ver.epub",
        "Campfire Cooking in Another World with My Absurd Skill Volume-2.epub",
        "Campfire Cooking in Another World with My Absurd Skill Volume-3.epub",
        "Campfire Cooking in Another World with My Absurd Skill Volume-4.epub",
        "Campfire Cooking in Another World with My Absurd Skill Volume-5.epub",
        "Campfire Cooking in Another World with My Absurd Skill Volume-6.epub",
        "Ch.0216 Shows Her Color (en).cbz",
        "Ch.0217 - Have Never Seen Anything Like It (en).cbz",
        "Ch.0218 - Queen it Over (en) [First Division Scanlations].cbz",
        "Ch.0219 - A Sense of Foreboding  (en) [First Division Scanlations].cbz",
        "Ch.0220 - Bull's-eye (en) [First Division Scanlations].cbz",
        "Ch.0221 - Ups and Downs of His Fate  (en) [First Division Scanlations].cbz",
        "Ch.0222 - Give Back (en) [First Division Scanlations].cbz",
        "Ch.0223 - Good Old Days (en) [First Division Scanlations].cbz",
        "Ch.0224 - Cutthroat (en) [First Division Scanlations].cbz",
        "Ch.0225 - Free-for-all (en) [First Division Scanlations].cbz",
        "Ch.0226 - Dynamic Duo (en) [First Division Scanlations].cbz",
        "Ch.0227 - Gangster (en) [First Division Scanlations].cbz",
        "Ch.0228 - Beat Hell Out of (en) [First Division Scanlations].cbz",
        "Ch.0229 - Go Easy on (en) [First Division Scanlations].cbz",
        "Ch.0230 - Get Stuck-up (en) [First Division Scanlations].cbz",
        "Ch.0231 - Blood-Chilling (en) [First Division Scanlations].cbz",
        "Ch.0232 - It Takes Two to Tango  (en) [First Division Scanlations].cbz",
        "Ch.0233 - Better Late Than Never (en) [First Division Scanlations].cbz",
        "Ch.0234 - There is no Mending (en) [First Division Scanlations].cbz",
        "Ch.0235 - Just Be Yourself  (en) [First Division Scanlations].cbz",
        "Ch.0236 - Band of Brothers  (en) [First Division Scanlations].cbz",
        "Ch.0237 - Make Allies  (en) [First Division Scanlations].cbz",
        "Ch.0238 - Really Into It (en) [First Division Scanlations].cbz",
        "Ch.0239 - Steel The Show (en) [First Division Scanlations].cbz",
        "Ch.0240 - Go Into Retirement  (en) [First Division Scanlations].cbz",
        "Ch.0241 - A Forced Smile (en) [First Division Scanlations].cbz",
        "Ch.0242 - Inherit The Crown (en) [First Division Scanlations].cbz",
        "Ch.0243 - Wide Array Of (en) [First Division Scanlations].cbz",
        "Ch.0244 - The Showdown Battle (en) [First Division Scanlations].cbz",
        "Ch.0245 - Grow Up To (en) [First Division Scanlations].cbz",
        "Ch.0246 - Giant Killing  (en) [First Division Scanlations].cbz",
        "Ch.0247 - Hey Dude (en) [First Division Scanlations].cbz",
        "Ch.38 - Kouhai-chan, Part 12.cbz",
        "Ch.39 - Ai-chan, Part 14.cbz",
        "Ch.40 - Maegami-chan, Part 14.cbz",
        "Ch.41 - Kouhai-chan, Part 13.cbz",
        "Ch.42 - Imouto-chan, Part 1.cbz",
        "Ch.43 - Maegami-chan, Part 15.cbz",
        "Ch.44 - Ai-chan, Part 15.cbz",
        "Ch.45 - Kouhai-chan, Part 14.cbz",
        "Ch.46 - Maegami-chan, Part 16.cbz",
        "Ch.47 - Ai-chan, Part 16.cbz",
        "Ch.48 - Jitome-chan, Part 1.cbz",
        "Ch.49 - Imouto-chan, Part 2.cbz",
        "Ch.50 - Jitome-chan, Part 2.cbz",
        "Ch.51 - Kouhai-chan, Part 15.cbz",
        "Daughter of Evil - 1 - Clôture of Yellow.epub",
        "Daughter of Evil - 2 - Wiegenlied of Green.epub",
        "Daughter of Evil - 3 - Praeludium of Red.epub",
        "Daughter of Evil - 4 - Praefacio of Blue.epub",
        "Death Note - Bonus Chapter (Ch109, One-Shot) (VizMedia - All in One Edition, Scan, PNG).cbz",
        "Devils' Line - Extra 1.5 (2019) (Digital) (danke-Empire).cbz",
        "Don't XXX With Teachers! 030.2 (2022) (Digital) (Gremory)",
        "Final Chapter - To All of You in 2016.cbz",
        "Ghosts of Greywoods - Act 001, Epilogue (Digital) (i -like.yuri).cbz",
        "Grand Blue Dreaming - Extra (2020) (Digital) (danke-Empire).cbz",
        "Grand Blue Dreaming 61 Extra (2021) (Digital) (Edge).cbz",
        "Grand Blue Dreaming 62 Extra (2021) (Digital) (Edge).cbz",
        "Grand Blue Dreaming 65 Extra (2021) (Digital) (Edge).cbz",
        "Grand Blue Dreaming 74 Extra + Artwork (2022) (Digital).cbz",
        "Grand Blue Dreaming 75 + Artwork (2022) (Digital).cbz",
        "Grand Blue Dreaming 75 Extra + Artwork (2022) (Digital).cbz",
        "Grimgar of Fantasy and Ash - Volume 14+ [J-Novel Club][Premium].epub",
        "Grimgar of Fantasy and Ash - Volume 14++ [J-Novel Club][Premium].epub",
        "Grimgar of Fantasy and Ash LN 14+ Premium [C2].epub",
        "Grimgar of Fantasy and Ash LN 14+ Premium [C].epub",
        "Grimgar of Fantasy and Ash LN 14++ Premium [C2].epub",
        "Grimgar of Fantasy and Ash LN 14++ Premium [C].epub",
        "Grimgar of Fantasy and Ash v14+ [Premium].epub",
        "Grimgar of Fantasy and Ash v14++ [Premium].epub",
        "Gundam Acguy - 2250 Miles Across North America.cbz",
        "Haganai, I Don't Have Many Friends {Special One-Shot 1} - Now With 50% More Fail! (2014) (Digital) (KG Manga).cbz",
        "Haganai, I Don't Have Many Friends {Special One-Shot 2} - Club Minutes (2014) (Digital) (KG Manga).cbz",
        "Hey! You’ve Kidnapped the Wrong Royal! [Cross Infinite World] [1r0n].epub",
        "I Reincarnated As Evil Alice, So the Only Thing I’m Courting Is Death! - 01 [C2].epub",
        "I Reincarnated As Evil Alice, So the Only Thing I’m Courting Is Death! - 01 [C].epub",
        "I Reincarnated As Evil Alice, So the Only Thing I’m Courting Is Death! - 01.epub",
        "I Was a Bottom-Tier Bureaucrat for 1,500 Years, and the Demon King Made Me a Minister [Yen Press] [LuCaZ].epub",
        "I Was a Bottom-Tier Bureaucrat for 1,500 Years, and the Demon King Made Me a Minister.cbz",
        "Ichigo 100% East Side Story.cbz",
        "Inside Mari (v02) (2019) (Digital) (t3dio).cbz",
        "Inside Mari (v03) (2019) (Digital) (t3dio).cbz",
        "Inside Mari (v04) (2019) (Digital) (t3dio).cbz",
        "Inside Mari (v05) (2019) (Digital) (t3dio).cbz",
        "Inside Mari (v06) (2020) (Digital) (t3dio).cbz",
        "Inside Mari (v07) (2021) (Digital) (t3dio).cbz",
        "Inside Mari (v08) (2021) (Digital) (t3dio).cbz",
        "KA Esuma Bunko Relay Booklet 2020.epub",
        "Kamijou-san, Two Idiots, Jinnai Shinobu, Gray Pig, and Freedom Award 903, Listen Up! …Fall Asleep and You Die, But Not From the Cold.epub",
        "Kingdom Hearts - Chain of Memories - Complete (Volume 01-02) [Yen Press][Kindle-Kobo].epub",
        "Kingdom Hearts 358-2 Days - Complete (Volume 01-03) [Yen Press][Kindle-Kobo].epub",
        "KinSP-Curry Cook -The Holy Man Of Love And Fury- Part 1.cbz",
        "KinSP-Curry Cook -The Holy Man Of Love And Fury- Part 2.cbz",
        "Made in Abyss Official Anthology - Layer 01 - Irredeemable Cave Raiders (2020) (Digital) (danke-Empire).cbz",
        "Magilumiere Co. Ltd. 087 - Victory Prospects and Business Avenues (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 088 - Kamakura-san's House Party (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 089 - A Grand Assembly (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 090 - RABBIT (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 091 - Infiltration (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 092 - Responsibility and Results (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 093 - Restart (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 094 - A Promise (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 095 - Vow (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 096 - Welcome to Magilumiere (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 097 - Kaii Control Chip (2023) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 098 - MP-Charge-Kun (2024) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 099 - Gratitude (2024) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 100 - A Fun Job (2024) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 101 - Ruin and Revival (2024) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 101.1 - Bonus Chapter 4 (2024) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 102 - Reopen (2024) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 103 - Magikyu!! (2024) (Digital) (Rillant).cbz",
        "Magilumiere Co. Ltd. 104 - 'Tis Time for 'Torture,' Kurairi-sama (2024) (Digital) (Rillant).cbz",
        "Mobile Suit Gundam Silhouette Formula 91 (Complete).cbz",
        "MOBILE SUIT GUNDAM THE ORIGIN  Section 100.cbz",
        "MOBILE SUIT GUNDAM THE ORIGIN  Section 98.cbz",
        "MOBILE SUIT GUNDAM THE ORIGIN  Section 99.cbz",
        "Musume Janakute, Mama ga Sukinano SS1 + extra illustrations.epub",
        "Musume Janakute, Mama ga Sukinano SS2 + extra illustrations.epub",
        "My Stepmom's Daughter Is My Ex v01.epub",
        "One Piece - Romance Dawn ver. 1.cbz",
        "One Piece - Strong World (Chapter 0 [aka Chapter 565.5]).cbz",
        "One Piece 1054 v01 [official] [upscaled].cbz",
        "Owari no Chronicle 1-A.epub",
        "Owari no Chronicle 1-B.epub",
        "Owari no Chronicle 2-A.epub",
        "Owari no Chronicle 2-B.epub",
        "Owari no Chronicle 3-A.epub",
        "Owari no Chronicle 3-B.epub",
        "Owari no Chronicle 3-C.epub",
        "Owari no Chronicle 4-A.epub",
        "Owari no Chronicle 4-B.epub",
        "Owari no Chronicle 5-A.epub",
        "Owari no Chronicle 5-B.epub",
        "Owari no Chronicle 6-A.epub",
        "Owari no Chronicle 6-B.epub",
        "Owari no Chronicle 7.epub",
        "Rakudai Kishi no Eiyuutan - 01.epub",
        "Rakudai Kishi no Eiyuutan - 02.epub",
        "Rakudai Kishi no Eiyuutan - 03.epub",
        "Rakudai Kishi no Eiyuutan - 04.epub",
        "Rakudai Kishi no Eiyuutan - 05.epub",
        "Rakudai Kishi no Eiyuutan - 06.epub",
        "Rakudai Kishi no Eiyuutan - 07.epub",
        "Rakudai Kishi no Eiyuutan - 08.epub",
        "Rakudai Kishi no Eiyuutan - 09.epub",
        "Rakudai Kishi no Eiyuutan - 10.epub",
        "Rakudai Kishi no Eiyuutan - 11.epub",
        "Reflection of Another World Volume v01 [Cross Infinite World] [Stick].epub",
        "Return of the 8th Class Magician - Season 1 - Swaggy Repacks.cbz",
        "Saki Biyori BG Chapter 45-46.cbz",
        "Saki Biyori BG Chapter 47-48.cbz",
        "Saki Biyori BG Chapter 50-51.cbz",
        "Saki Biyori BG Chapter 52-53 v2.cbz",
        "Saki Biyori BG Chapter 54-55.cbz",
        "Saki Biyori BG Chapter 56-57_v2.cbz",
        "Saki Biyori BG Chapter 58-59.cbz",
        "Saki Biyori BG Chapter 62_v2.cbz",
        "Saki v08 extra.cbz",
        "Saki volume 8 extra.cbz",
        "Sensei de ○○ Shicha Ikemasen! (Don't XXX With Teachers!) Chapter 26.3.cbz",
        "Sensei de ○○ Shicha Ikemasen! (Don't XXX With Teachers!) Chapter 30.1- 32.cbz",
        "Sensei de ○○ Shicha Ikemasen! (Don't XXX With Teachers!) Chapter 33.3- 34.cbz",
        "Shojo Fight 18 - Yoko Nihonbashi.cbz",
        "Shoku King (v02) [Digital] [Tikas].cbz",
        "Shoku King (v03) [Digital] [Tikas].cbz",
        "Shoku King (v04) [Digital] [Tikas].cbz",
        "Shoku King (v05) [Digital] [Tikas].cbz",
        "Shoku King (v06) [Digital] [Tikas].cbz",
        "Shoku King (v07) [Digital] [Tikas].cbz",
        "Shoku King (v08) [Digital] [Tikas].cbz",
        "Shoku King (v09) [Digital] [Tikas].cbz",
        "Shoku King (v10) [Digital] [Tikas].cbz",
        "Shoku King (v11) [Digital] [Tikas].cbz",
        "Shoku King (v12) [Digital] [Tikas].cbz",
        "Shoku King (v13) [Digital] [Tikas].cbz",
        "Shoku King (v14) [Digital] [Tikas].cbz",
        "Shoku King (v15) [Digital] [Tikas].cbz",
        "Shoku King (v16) [Digital] [Tikas].cbz",
        "Shoku King (v17) [Digital] [Tikas].cbz",
        "Shoku King (v18) [Digital] [Tikas].cbz",
        "Shoku King (v19) [Digital] [Tikas].cbz",
        "Shoku King (v20) [Digital] [Tikas].cbz",
        "Shoku King (v21) [Digital] [Tikas].cbz",
        "Shoku King (v22) [Digital] [Tikas].cbz",
        "Shoku King (v23) [Digital] [Tikas].cbz",
        "Shoku King (v24) [Digital] [Tikas].cbz",
        "Shoku King (v25) [Digital] [Tikas].cbz",
        "Shoku King (v26) [Digital] [Tikas].cbz",
        "Shoku King (v27) [Digital] [Tikas].cbz",
        "Skeleton Double 031 - CH. 31 SHOKO YOROIBATA (2023) (Digital) (Rillant).cbz",
        "Skeleton Double 032 - CH. 32 SPRING AND STRIFE (2024) (Digital) (Rillant).cbz",
        "Spy x Family 065 v01 [official] [upscaled].cbz",
        "SSS-Class Suicide Hunter 04 v01 [epub].epub",
        "Starting Point - 1979-1996 [VIZ Media] [LuCaZ].epub",
        "Sweetness and Lightning Extra 1 (2018) (Digital) (danke-Empire).cbz",
        "The Irregular at Magic High School v13v2 v01 [Yen Press] [-KS-].epub",
        "The Irregular at Magic High School v13v2 [Yen Press] [-KS-] [C2].epub",
        "The Irregular at Magic High School v13v2 [Yen Press] [-KS-].epub",
        "The Irregular at Magic High School x Sword Art Online Crossover - Part 1 - Dream Game [C2].epub",
        "The Irregular at Magic High School x Sword Art Online Crossover - Part 1 - Dream Game.epub",
        "The Irregular at Magic High School x Sword Art Online Crossover - Part 2 - Versus II [C2].epub",
        "The Irregular at Magic High School x Sword Art Online Crossover - Part 2 - Versus II.epub",
        "The Ryuo_s Work is Never Done!, Vol. 15.epub",
        "The Ryuo_s Work is Never Done!, Vol. 3.epub",
        "The Ryuo_s Work is Never Done!, Vol. 4.epub",
        "the-engagement-of-marielle-clarac v01 [Premium].epub",
        "the-engagement-of-marielle-clarac v01.epub",
        "Turning Point - 1997-2008 [VIZ Media] [LuCaZ].epub",
        "Where to Go in a Whole Other World 024 - 4- A Little Shrine in a Whole Other World (2021) (Digital) (AntsyLich).cbz",
        "ご注文はうさぎですか？ 第5巻 v01.cbz",
        "ご注文はうさぎですか？ 第5巻.cbz",
    ]

    # 1. Open the file
    with open(csv_file, mode="r", newline="", encoding="utf-8") as file:
        # 2. Use DictReader to treat rows as dictionaries (keys are headers)
        csv_reader = csv.DictReader(file)

        # 3. Convert the iterator to a list for length/indexing (like Pandas)
        rows = list(csv_reader)
        total_rows = len(rows)

        # for each row in the dataframe
        for index, row in enumerate(rows):
            # get the file name
            file_name = row["File Name"]

            print(f"[{index+1}/{total_rows}] {file_name}")

            if file_name in skipped_files:
                print(f"  - Skipping validation")
                continue

            series_name = row["Series Name"]
            file_type = (
                "chapter"
                if (
                    not contains_volume_keywords(file_name)
                    and contains_chapter_keywords(file_name)
                )
                else "volume"
            )

            # get the release number
            release_number = row["Release Number"]

            if str(release_number).startswith("["):
                # remove first and last character to remove brackets
                release_number = release_number[1:-1]

                # convert to min and max
                release_number = get_min_and_max_numbers(release_number)

            # convert from string
            release_number_convt = set_num_as_float_or_int(release_number)

            # the parsed number via the script
            script_release_number = set_num_as_float_or_int(
                get_release_number_cache(file_name, chapter=file_type == "chapter")
            )

            is_one_shot_status = is_one_shot(file_name, skip_folder_check=True)

            if not script_release_number and is_one_shot_status:
                script_release_number = 1

            # get the series name
            script_series_name = (
                get_series_name_from_chapter(file_name, ROOT_DIR, script_release_number)
                if file_type == "chapter"
                else get_series_name_from_volume(file_name, ROOT_DIR, test_mode=True)
            )

            # validate that the release number in the csv is correct
            if script_release_number != release_number_convt:
                incorrect_release_numbers.append(
                    IncorrectItem(
                        file_name, release_number_convt, script_release_number
                    )
                )

            # validate that the series name in the csv is correct
            if script_series_name != series_name:
                incorrect_series_names.append(
                    IncorrectItem(file_name, series_name, script_series_name)
                )

            # validate that the file type in the csv is correct
            if file_type != row["File Type"]:
                incorrect_file_types.append(
                    IncorrectItem(file_name, row["File Type"], file_type)
                )

    if len(incorrect_release_numbers) > 0:
        print("\nThe following release numbers are incorrect:")
        for file_name in incorrect_release_numbers:
            print(
                f"\n\t{file_name.file_name}\n\t\t{file_name.item_one} != {file_name.item_two}"
            )

    if len(incorrect_series_names) > 0:
        print("\nThe following series names are incorrect:")
        for file_name in incorrect_series_names:
            print(
                f"\n\t{file_name.file_name}\n\t\t{file_name.item_one} != {file_name.item_two}"
            )

    if len(incorrect_file_types) > 0:
        print("\nThe following file types are incorrect:")
        for file_name in incorrect_file_types:
            print(
                f"\n\t{file_name.file_name}\n\t\t{file_name.item_one} != {file_name.item_two}"
            )

    assert (
        len(incorrect_release_numbers) == 0
        and len(incorrect_series_names) == 0
        and len(incorrect_file_types) == 0
    )


# tests contains_unicode(input_string)
def test_contains_unicode():
    assert contains_unicode("test") == False
    assert contains_unicode("testé") == True
    assert contains_unicode("testéééé") == True
    assert contains_unicode("LES MISÉRABLES") == True


# tests contains_punctuation(s)
def test_contains_punctuation():
    assert contains_punctuation("test") == False
    assert contains_punctuation("test!") == True
    assert contains_punctuation("test!!!") == True
    assert contains_punctuation("test,") == True
    assert contains_punctuation("test, test") == True
    assert contains_punctuation("LES MISÉRABLES") == False


# tests contains_brackets()
def test_contains_brackets():
    assert contains_brackets("test") == False
    assert contains_brackets("test()") == True
    assert contains_brackets("test[]") == True
    assert contains_brackets("test{}") == True
    assert contains_brackets("test()[]{}") == True
    assert contains_brackets("test()[]{} test") == True


if __name__ == "__main__":
    validate_csv()
    # test_rename_files()
    test_set_num_as_float_or_int()
    test_remove_hidden_files()
    test_remove_ignored_folders()
    test_remove_hidden_folders()
    test_filter_non_chapters()
    test_contains_chapter_keywords()
    test_contains_volume_keywords()
    test_get_file_extension()
    test_get_extensionless_name()
    test_is_volume_one()
    test_get_series_name_from_chapter()
    test_get_folder_type()
    test_check_for_multi_volume_file()
    test_convert_list_of_numbers_to_array()
    test_get_release_number_cache()
    test_get_release_year()
    # test_get_extra_from_group()
    test_get_file_part()
    # test_get_keyword_score()
    test_remove_dual_space()
    test_normalize_str()
    test_clean_str()
    # test_convert_to_ascii()
    test_array_to_string()
    test_remove_duplicates()
    test_remove_brackets()
    test_replace_underscores()
    test_get_extras()
    test_isfloat()
    test_isint()
    test_parse_html_tags()
    test_check_for_exception_keywords()
    test_has_one_set_of_numbers()
    test_sorting_volumes_by_volume_number()
    test_organize_by_first_letter()
    test_contains_unicode()
    test_contains_punctuation()
    test_contains_brackets()
    print("ALL TESTS PASSED!")
