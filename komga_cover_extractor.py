import argparse
import hashlib
import io
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import threading
import traceback
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from base64 import b64encode
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from posixpath import join
from urllib.parse import urlparse

import cProfile
import cv2
import filetype
import numpy as np
import py7zr
import rarfile
import regex as re
import requests
import scandir
from bs4 import BeautifulSoup
from discord_webhook import DiscordEmbed, DiscordWebhook
from lxml import etree
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from titlecase import titlecase
from unidecode import unidecode
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from settings import *

# Get all the variables in settings.py
import settings as settings_file

# Version of the script
script_version = (2, 5, 13)
script_version_text = "v{}.{}.{}".format(*script_version)

# Paths = existing library
# Download_folders = newly acquired manga/novels
paths = []
download_folders = []

# paths within paths that were passed in with a defined path_type
# EX: "volume" or "chapter"
paths_with_types = []

# download folders within download_folders that were passed in with a defined path_type
download_folders_with_types = []

# global folder_accessor
folder_accessor = None

# To compress the extracted images
compress_image_option = False

# Default image compression value.
# Pass in via cli
image_quality = 40

# Stat-related variables
image_count = 0
errors = []
items_changed = []

# A discord webhook url used to send messages to discord about the changes made.
# Pass in via cli
discord_webhook_url = []

# Two webhooks specific to the bookwalker check.
# One is used for released books, the other is used for upcoming books.
# Intended to be sent to two seperate channels.
# FIRST WEBHOOK = released books
# SECOND WEBHOOK = upcoming books
bookwalker_webhook_urls = []

# Checks the library against bookwalker for new releases.
bookwalker_check = False

# All the release groups stored in release_groups.txt
# Used when renaming files where it has a matching group.
release_groups = []

# All the publishers stored in publishers.txt
# Used when renaming files where it has a matching publisher.
publishers = []

# skipped files that don't have a release group
skipped_release_group_files = []

# skipped files that don't have a publisher
skipped_publisher_files = []

# A quick and dirty fix to avoid non-processed files from
# being moved over to the existing library. Will be removed in the future.
processed_files = []

# Any files moved to the existing library. Used for triggering a library scan in komga.
moved_files = []

# The script's root directory
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Where logs are written to.
LOGS_DIR = os.path.join(ROOT_DIR, "logs")

# Where the addon scripts are located.
ADDONS_DIR = os.path.join(ROOT_DIR, "addons")

# Docker Status
in_docker = False

# Check if the instance is running in docker.
# If the ROOT_DIR is /app, then it's running in docker.
if ROOT_DIR == "/app":
    in_docker = True
    script_version_text += " • Docker"

# The path location of the blank_white.jpg in the root of the script directory.
blank_white_image_path = (
    os.path.join(ROOT_DIR, "blank_white.jpg")
    if os.path.isfile(os.path.join(ROOT_DIR, "blank_white.jpg"))
    else None
)

blank_black_image_path = (
    os.path.join(ROOT_DIR, "blank_black.png")
    if os.path.isfile(os.path.join(ROOT_DIR, "blank_black.png"))
    else None
)

# Cached paths from the users existing library. Read from cached_paths.txt
cached_paths = []

cached_paths_path = os.path.join(LOGS_DIR, "cached_paths.txt")

# Cached identifier results, aka successful matches via series_id or isbn
cached_identifier_results = []

# watchdog toggle
watchdog_toggle = False

# 7zip extensions
seven_zip_extensions = [".7z"]

# Zip extensions
zip_extensions = [
    ".zip",
    ".cbz",
    ".epub",
]

rar_extensions = [".rar", ".cbr"]

# Accepted file extensions for novels
novel_extensions = [".epub"]

# Accepted file extensions for manga
manga_extensions = [x for x in zip_extensions if x not in novel_extensions]

# All the accepted file extensions
file_extensions = novel_extensions + manga_extensions

# All the accepted convertable file extensions for convert_to_cbz(),
# and the watchdog handler.
convertable_file_extensions = seven_zip_extensions + rar_extensions

# All the accepted image extensions
image_extensions = {".jpg", ".jpeg", ".png", ".tbn", ".webp"}

# Type of file formats for manga and novels
file_formats = ["chapter", "volume"]

# stores our folder path modification times
# used for skipping folders that haven't been modified
# when running extract_covers() with watchdog enabled
root_modification_times = {}

# Stores all the new series paths for series that were added to an existing library
moved_folders = []

# Profiles the execution - for dev use
profile_code = ""

# get all of the non-callable variables
settings = [
    var
    for var in dir(settings_file)
    if not callable(getattr(settings_file, var)) and not var.startswith("__")
]


# Library Type class
class LibraryType:
    def __init__(self, name, extensions, must_contain, must_not_contain):
        self.name = name
        self.extensions = extensions
        self.must_contain = must_contain
        self.must_not_contain = must_not_contain

    # Convert the object to a string representation
    def __str__(self):
        return f"LibraryType(name={self.name}, extensions={self.extensions}, must_contain={self.must_contain}, must_not_contain={self.must_not_contain})"


# The Library Entertainment types
library_types = [
    LibraryType(
        "manga",  # name
        manga_extensions,  # extensions
        [r"\(Digital\b"],  # must_contain
        [
            r"Webtoon",
        ],  # must_not_contain
    ),
    LibraryType(
        "light novel",  # name
        novel_extensions,  # extensions
        [
            r"\[[^\]]*(Lucaz|Stick|Oak|Yen (Press|On)|J-Novel|Seven Seas|Vertical|One Peace Books|Cross Infinite|Sol Press|Hanashi Media|Kodansha|Tentai Books|SB Creative|Hobby Japan|Impress Corporation|KADOKAWA)[^\]]*\]|(faratnis)"
        ],  # must_contain
        [],  # must_not_contain
    ),
]


# The Translation Status source types for a library
translation_source_types = ["official", "fan", "raw"]

# The Library languages
source_languages = [
    "english",
    "japanese",
    "chinese",
    "korean",
]

# Volume Regex Keywords to be used throughout the script
# ORDER IS IMPORTANT, if a single character volume keyword is checked first, then that can break
# cleaning of various bits of input.
volume_keywords = [
    "LN",
    "Light Novels?",
    "Novels?",
    "Books?",
    "Volumes?",
    "Vols?",
    "Discs?",
    "Tomo",
    "Tome",
    "Von",
    "V",
    "第",
    "T",
]

# Chapter Regex Keywords used throughout the script
chapter_keywords = [
    "Chapters?",
    "Chaps?",
    "Chs?",
    "Cs?",
    "D",
]

# Keywords to be avoided in a chapter regex.
# Helps avoid picking the wrong chapter number
# when no chapter keyword was used before it.
exclusion_keywords = [
    r"(\s)Part(\s)",
    r"(\s)Episode(\s)",
    r"(\s)Season(\s)",
    r"(\s)Arc(\s)",
    r"(\s)Prologue(\s)",
    r"(\s)Epilogue(\s)",
    r"(\s)Omake(\s)",
    r"(\s)Extra(\s)",
    r"(\s)- Special(\s)",
    r"(\s)Side Story(\s)",
    # r"(\s)S(\s)",
    r"(\s)Act(\s)",
    r"(\s)Special Episode(\s)",
    r"(\s)Ep(\s)",
    r"(\s)- Version(\s)",
    r"(\s)Ver(\s)",
    r"(\s)PT\.",
    r"(\s)PT(\s)",
    r",",
    r"(\s)×",
    r"\d\s*-\s*",
    r"\bNo.",
    r"\bNo.(\s)",
    r"\bBonus(\s)",
    r"(\]|\}|\)) -",
    r"\bZom(\s)",
]

subtitle_exclusion_keywords = [r"-(\s)", r"-", r"-\s[A-Za-z]+\s"]


# Volume Regex Keywords to be used throughout the script
volume_regex_keywords = "(?<![A-Za-z])" + "|(?<![A-Za-z])".join(volume_keywords)

# Exclusion keywords joined by just |
exclusion_keywords_joined = "|".join(exclusion_keywords)

# Subtitle exclusion keywords joined by just |
subtitle_exclusion_keywords_joined = "|".join(subtitle_exclusion_keywords)

# Put the exclusion_keywords_joined inside of (?<!%s)
exclusion_keywords_regex = r"(?<!%s)" % exclusion_keywords_joined

# Put the subtitle_exclusion_keywords_joined inside of (?<!%s)
subtitle_exclusion_keywords_regex = r"(?<!%s)" % subtitle_exclusion_keywords_joined

# Chapter Regex Keywords to be used throughout the script
chapter_regex_keywords = r"(?<![A-Za-z])" + (r"|(?<![A-Za-z])").join(chapter_keywords)

### EXTENION REGEX ###
# File extensions regex to be used throughout the script
file_extensions_regex = "|".join(file_extensions).replace(".", "\.")
# Manga extensions regex to be used throughout the script
manga_extensions_regex = "|".join(manga_extensions).replace(".", "\.")
# Novel extensions regex to be used throughout the script
novel_extensions_regex = "|".join(novel_extensions).replace(".", "\.")
# Image extensions regex to be used throughout the script
image_extensions_regex = "|".join(image_extensions).replace(".", "\.")

# REMINDER: ORDER IS IMPORTANT, Top to bottom is the order it will be checked in.
# Once a match is found, it will stop checking the rest.
# IMPORTANT: Any change of order or swapping of regexes, requires change in full_chapter_match_attempt_allowed alternative logic!
chapter_searches = [
    r"\b\s-\s*(#)?(\d+)([-_.]\d+)*(x\d+)?\s*-\s",
    r"\b(%s)(\.)?\s*(\d+)([-_.]\d+)*(x\d+)?\b(?<!\s(\d+)([-_.]\d+)*(x\d+)?\s.*)"
    % chapter_regex_keywords,
    r"(?<![A-Za-z]|%s)(((%s)([-_. ]+)?(\d+)([-_.]\d+)*(x\d+)?)|\s+(\d+)(\.\d+)?(x\d+((\.\d+)+)?)?(\s+|#\d+|%s))"
    % (exclusion_keywords_joined, chapter_regex_keywords, manga_extensions_regex),
    r"((?<!^)\b(\.)?\s*(%s)(\d+)([-_.]\d+)*((x|#)(\d+)([-_.]\d+)*)*\b)((\s+-|:)\s+).*?(?=\s*[\(\[\{](\d{4}|Digital)[\)\]\}])"
    % exclusion_keywords_regex,
    r"(\b(%s)?(\.)?\s*(%s)(\d+)([-_.]\d+)*(x\d+)?(#\d+([-_.]\d+)*)?\b)\s*((\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})|((?<!\w(\s))|(?<!\w))(%s)(?!\w))"
    % (chapter_regex_keywords, exclusion_keywords_regex, file_extensions_regex),
    r"^((#)?(\d+)([-_.]\d+)*((x|#)(\d+)([-_.]\d+)*)*)$",
]

# pre-compile the chapter_searches
chapter_search_patterns_comp = [
    re.compile(pattern, flags=re.IGNORECASE) for pattern in chapter_searches
]

# Used in check_for_existing_series() when sending
# a bulk amount of chapter release notifications to discord after the function is done,
# also allows them to be sent in number order.
messages_to_send = []

# Used to store multiple embeds to be sent in one message
grouped_notifications = []

# Discord's maximum amount of embeds that can be sent in one message
discord_embed_limit = 10

# The time to wait before performing the next action in
# the watchdog event handler.
sleep_timer = 10

# The time to wait before scraping another bookwalker page in
# the bookwalker_check feature.
sleep_timer_bk = 2

# The fill values for the chapter and volume files when renaming.
# # VOLUME
zfill_volume_int_value = 2  # 01
zfill_volume_float_value = 4  # 01.0
# # CHAPTER
zfill_chapter_int_value = 3  # 001
zfill_chapter_float_value = 5  # 001.0

# The Discord colors used for the embeds
purple_color = 7615723  # Starting Execution Notification
red_color = 16711680  # Removing File Notification
grey_color = 8421504  # Renaming, Reorganizing, Moving, Series Matching, and Bookwalker Release Notification
yellow_color = 16776960  # Not Upgradeable Notification
green_color = 65280  # Upgradeable and New Release Notification
preorder_blue_color = 5919485  # Bookwalker Preorder Notification

# The similarity score required for a publisher to be considered a match
publisher_similarity_score = 0.9

# Used to store the files and their associated dirs that have been marked as fully transferred
# When using watchdog, this is used to prevent the script from
# trying to process the same file multiple times.
transferred_files = []
transferred_dirs = []

# The logo url for usage in the bookwalker_check discord output
bookwalker_logo_url = "https://play-lh.googleusercontent.com/a7jUyjTxWrl_Kl1FkUSv2FHsSu3Swucpem2UIFDRbA1fmt5ywKBf-gcwe6_zalOqIR7V=w240-h480-rw"

# An alternative matching method that uses the image similarity between covers.
match_through_image_similarity = True

# The required score for two cover images to be considered a match
required_image_similarity_score = 0.9

# Checks the library against bookwalker for new releases.
bookwalker_check = False

# Used when moving the cover between locations.
series_cover_file_names = ["cover", "poster"]

# The required similarity score between the detected cover and the blank image to be considered a match.
# If the similarity score is equal to or greater than this value, the cover will be ignored as
# it is most likely a blank cover.
blank_cover_required_similarity_score = 0.9

# Prompts the user when deleting a lower-ranking duplicate volume when running
# check_for_duplicate_volumes()
manual_delete = False

# The required file type matching percentage between
# the download folder and the existing folder
#
# EX: 90% of the folder's files must have an extension in manga_extensions or novel_extensions
required_matching_percentage = 90

# The similarity score requirement when matching any bracketed release group
# within a file name. Used when rebuilding the file name in reorganize_and_rename.
release_group_similarity_score = 0.8

# searches for and copies an existing volume cover from a volume library over to the chapter library
copy_existing_volume_covers_toggle = False

# The percentage of words in the array of words,
# parsed from a shortened series_name to be kept
# for both series_names being compared.
# EX: 0.7= 70%
short_word_filter_percentage = 0.7

# The amount of time to sleep before checking again if all the files are fully transferred.
# Slower network response times may require a higher value.
watchdog_discover_new_files_check_interval = 5

# The time to sleep between file size checks when determining if a file is fully transferred.
# Slower network response times may require a higher value.
watchdog_file_transferred_check_interval = 1

# The libraries on the user's komga server.
# Used for sending scan reqeusts after files have been moved over.
komga_libraries = []

# Will move new series that couldn't be matched to the library to the appropriate library.
# requires: '--watchdog "True"' and check_for_existing_series_toggle = True
move_new_series_to_library_toggle = False

# Used in get_extra_from_group()
publishers_joined = ""
release_groups_joined = ""

# Outputs the covers as WebP format
# instead of jpg format.
output_covers_as_webp = False

series_cover_path = ""


# Folder Class
class Folder:
    def __init__(self, root, dirs, basename, folder_name, files):
        self.root = root
        self.dirs = dirs
        self.basename = basename
        self.folder_name = folder_name
        self.files = files

    # to string
    def __str__(self):
        return f"Folder(root={self.root}, dirs={self.dirs}, basename={self.basename}, folder_name={self.folder_name}, files={self.files})"

    def __repr__(self):
        return str(self)


# File Class
class File:
    def __init__(
        self,
        name,
        extensionless_name,
        basename,
        extension,
        root,
        path,
        extensionless_path,
        volume_number,
        file_type,
        header_extension,
    ):
        self.name = name
        self.extensionless_name = extensionless_name
        self.basename = basename
        self.extension = extension
        self.root = root
        self.path = path
        self.extensionless_path = extensionless_path
        self.volume_number = volume_number
        self.file_type = file_type
        self.header_extension = header_extension


class Publisher:
    def __init__(self, from_meta, from_name):
        self.from_meta = from_meta
        self.from_name = from_name

    # to string
    def __str__(self):
        return f"Publisher(from_meta={self.from_meta}, from_name={self.from_name})"

    def __repr__(self):
        return str(self)


# Volume Class
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


# Custom sorting key function, sort by index_number
def get_sort_key(index_number):
    if isinstance(index_number, list):
        return min(index_number)
    else:
        return index_number


# Sorts the volumes by the index number if they're all numbers,
# otherwise it sorts the volumes alphabetically by the file name.
def sort_volumes(volumes):
    if any(isinstance(item.index_number, str) for item in volumes):
        # sort alphabetically by the file name
        return sorted(volumes, key=lambda x: x.name)
    else:
        # sort by the index number
        return sorted(volumes, key=lambda x: get_sort_key(x.index_number))


# Path Class
class Path:
    def __init__(
        self,
        path,
        path_formats=file_formats,
        path_extensions=file_extensions,
        library_types=library_types,
        translation_source_types=translation_source_types,
        source_languages=source_languages,
    ):
        self.path = path
        self.path_formats = path_formats
        self.path_extensions = path_extensions
        self.library_types = library_types
        self.translation_source_types = translation_source_types
        self.source_languages = source_languages

    # to string
    def __str__(self):
        return f"Path(path={self.path}, path_formats={self.path_formats}, path_extensions={self.path_extensions}, library_types={self.library_types}, translation_source_types={self.translation_source_types}, source_languages={self.source_languages})"

    def __repr__(self):
        return str(self)


# Watches the download directory for any changes.
class Watcher:
    def __init__(self):
        self.observers = []
        self.lock = threading.Lock()

    def run(self):
        event_handler = Handler(self.lock)
        for folder in download_folders:
            observer = Observer()
            self.observers.append(observer)
            observer.schedule(event_handler, folder, recursive=True)
            observer.start()

        try:
            while True:
                time.sleep(sleep_timer)
        except Exception as e:
            print(f"ERROR in Watcher.run(): {e}")
            for observer in self.observers:
                observer.stop()
                print("Observer Stopped")
            for observer in self.observers:
                observer.join()
                print("Observer Joined")


# Handles our embed object along with any associated file
class Embed:
    def __init__(self, embed, file=None):
        self.embed = embed
        self.file = file


# Our array of file extensions and how many files have that extension
file_counters = {x: 0 for x in file_extensions}


# Sends a message, prints it, and writes it to a file.
def send_message(
    message,
    discord=True,
    error=False,
    log=log_to_file,
    error_file_name="errors.txt",
    changes_file_name="changes.txt",
):
    print(message)
    if discord:
        send_discord_message(message)
    if error:
        errors.append(message)
        if log:
            write_to_file(error_file_name, message)
    else:
        items_changed.append(message)
        if log:
            write_to_file(changes_file_name, message)


# Checks if the file is fully transferred by checking the file size
def is_file_transferred(file_path):
    # Check if the file path exists and is a file
    if not os.path.isfile(file_path):
        return False

    try:
        # Get the file size before waiting for 1 second
        before_file_size = os.path.getsize(file_path)

        # Wait for 1 second
        time.sleep(watchdog_file_transferred_check_interval)

        # Get the file size after waiting for 1 second
        after_file_size = os.path.getsize(file_path)

        # Check if both file sizes are not None and not equal
        if (
            before_file_size is not None
            and after_file_size is not None
            and before_file_size != after_file_size
        ):
            return False

        # If the file size is None or the same, return True, indicating the file transfer is complete
        return True

    except Exception as e:
        send_message(f"ERROR in is_file_transferred(): {e}")
        return False


# Gets the file's file size
def get_file_size(file_path):
    # Check if the file path exists and is a file
    if os.path.isfile(file_path):
        # Get the file information using os.stat()
        file_info = os.stat(file_path)
        # Return the file size using the st_size attribute of file_info
        return file_info.st_size
    else:
        # If the file path does not exist or is not a file, return None
        return None


# Recursively gets all the folders in a directory
def get_all_folders_recursively_in_dir(dir_path):
    results = []

    for root, dirs, files in scandir.walk(dir_path):
        if root in download_folders + paths:
            continue

        folder_info = {"root": root, "dirs": dirs, "files": files}

        results.append(folder_info)

    return results


# Recursively gets all the files in a directory
def get_all_files_in_directory(dir_path):
    results = []
    for root, dirs, files in scandir.walk(dir_path):
        files = remove_hidden_files(files)
        files = remove_unaccepted_file_types(files, root, file_extensions)
        results.extend(files)
    return results


# Resursively gets all files in a directory for watchdog
def get_all_files_recursively_in_dir_watchdog(dir_path):
    results = []
    for root, dirs, files in scandir.walk(dir_path):
        files = remove_hidden_files(files)
        for file in files:
            file_path = os.path.join(root, file)
            if file_path not in results:
                extension = get_file_extension(file_path)
                if extension not in image_extensions:
                    results.append(file_path)
                elif not compress_image_option and (
                    download_folders and dir_path in paths
                ):
                    results.append(file_path)
    return results


# Generates a folder object for a given root
def create_folder_obj(root, dirs=None, files=None):
    return Folder(
        root,
        dirs if dirs is not None else [],
        os.path.basename(os.path.dirname(root)),
        os.path.basename(root),
        get_all_files_recursively_in_dir_watchdog(root) if files is None else files,
    )


class Handler(FileSystemEventHandler):
    def __init__(self, lock):
        self.lock = lock

    def on_created(self, event):
        with self.lock:
            start_time = time.time()
            global grouped_notifications

            try:
                global transferred_files, transferred_dirs

                extension = get_file_extension(event.src_path)
                base_name = os.path.basename(event.src_path)
                is_hidden = base_name.startswith(".")
                is_valid_file = os.path.isfile(event.src_path)
                in_file_extensions = extension in file_extensions

                if not event.event_type == "created":
                    return None

                if not is_valid_file or extension in image_extensions or is_hidden:
                    return None

                print(f"\n\tEvent Type: {event.event_type}")
                print(f"\tEvent Src Path: {event.src_path}")

                # if not extension was found, return None
                if not extension:
                    print("\t\t -No extension found, skipped.")
                    return None

                # if the event is a directory, return None
                if event.is_directory:
                    print("\t\t -Is a directory, skipped.")
                    return None

                # if transferred_files, and the file is already in transferred_files
                # then it already has been processed, so return None
                elif transferred_files and event.src_path in transferred_files:
                    print("\t\t -Already processed, skipped.")
                    return None

                # check if the extension is not in our accepted file extensions
                elif not in_file_extensions:
                    # if we don't have delete_unacceptable_files_toggle enabled, return None
                    # if delete_unacceptable_files_toggle, we let it past so it can purge it with delete_unacceptable_files()
                    if not delete_unacceptable_files_toggle:
                        print(
                            "\t\t -Not in file extensions and delete_unacceptable_files_toggle is not enabled, skipped."
                        )
                        return None
                    elif (
                        (delete_unacceptable_files_toggle or convert_to_cbz_toggle)
                        and (
                            extension not in unacceptable_keywords
                            and "\\" + extension not in unacceptable_keywords
                        )
                        and not (
                            convert_to_cbz_toggle
                            and extension in convertable_file_extensions
                        )
                    ):
                        print("\t\t -Not in file extensions, skipped.")
                        return None

                # Finally if all checks are passed and the file was just created, we can process it
                # Take any action here when a file is first created.

                send_message("\nStarting Execution (WATCHDOG)", discord=False)

                embed = handle_fields(
                    DiscordEmbed(
                        title="Starting Execution (WATCHDOG)",
                        color=purple_color,
                    ),
                    [
                        {
                            "name": "File Found",
                            "value": f"```{event.src_path}```",
                            "inline": False,
                        }
                    ],
                )

                send_discord_message(
                    None,
                    [Embed(embed, None)],
                )

                print(f"\n\tFile Found: {event.src_path}\n")

                if not os.path.isfile(event.src_path):
                    return None

                # Get a list of all files in the root directory and its subdirectories.
                files = [
                    file
                    for folder in download_folders
                    for file in get_all_files_recursively_in_dir_watchdog(folder)
                ]

                # Check if all files in the root directory and its subdirectories are fully transferred.
                while True:
                    all_files_transferred = True
                    print(f"\nTotal files: {len(files)}")

                    for file in files:
                        print(
                            f"\t[{files.index(file) + 1}/{len(files)}] {os.path.basename(file)}"
                        )

                        if file in transferred_files:
                            print("\t\t-already transferred")
                            continue

                        is_transferred = is_file_transferred(file)

                        if is_transferred:
                            print("\t\t-fully transferred")
                            transferred_files.append(file)
                            dir_path = os.path.dirname(file)
                            if dir_path not in download_folders + transferred_dirs:
                                transferred_dirs.append(os.path.dirname(file))
                        elif not os.path.isfile(file):
                            print("\t\t-file no longer exists")
                            all_files_transferred = False
                            files.remove(file)
                            break
                        else:
                            print("\t\t-still transferreing...")
                            all_files_transferred = False
                            break

                    if all_files_transferred:
                        time.sleep(watchdog_discover_new_files_check_interval)

                        # The current list of files in the root directory and its subdirectories.
                        new_files = [
                            file
                            for folder in download_folders
                            for file in get_all_files_recursively_in_dir_watchdog(
                                folder
                            )
                        ]

                        # If any new files started transferring while we were checking the current files,
                        # then we have more files to check.
                        if files != new_files:
                            all_files_transferred = False
                            if len(new_files) > len(files):
                                print(
                                    f"\tNew transfers: +{len(new_files) - len(files)}"
                                )
                                files = new_files
                            elif len(new_files) < len(files):
                                break
                        elif files == new_files:
                            break

                    time.sleep(watchdog_discover_new_files_check_interval)

                # Proceed with the next steps here.
                print("\nAll files are transferred.")

                # Make sure all items are a folder object
                transferred_dirs = [
                    create_folder_obj(x) if not isinstance(x, Folder) else x
                    for x in transferred_dirs
                ]

            except Exception as e:
                send_message(f"Error with watchdog on_any_event(): {e}", error=True)

            if profile_code == "main()":
                cProfile.run(profile_code, sort="cumtime")
            else:
                main()

            end_time = time.time()
            minute_keyword = ""
            second_keyword = ""

            # get the execution time
            execution_time = end_time - start_time
            minutes, seconds = divmod(execution_time, 60)
            minutes = int(minutes)
            seconds = int(seconds)

            if minutes:
                if minutes == 1:
                    minute_keyword = "minute"
                elif minutes > 1:
                    minute_keyword = "minutes"
            if seconds:
                if seconds == 1:
                    second_keyword = "second"
                elif seconds > 1:
                    second_keyword = "seconds"

            execution_time_message = ""

            if minutes and seconds:
                execution_time_message = (
                    f"{minutes} {minute_keyword} and {seconds} {second_keyword}"
                )
            elif minutes:
                execution_time_message = f"{minutes} {minute_keyword}"
            elif seconds:
                execution_time_message = f"{seconds} {second_keyword}"
            else:
                execution_time_message = "less than 1 second"

            # Terminal Message
            send_message(
                f"\nFinished Execution (WATCHDOG)\n\tExecution Time: {execution_time_message}",
                discord=False,
            )

            # Discord Message
            embed = handle_fields(
                DiscordEmbed(
                    title="Finished Execution (WATCHDOG)",
                    color=purple_color,
                ),
                [
                    {
                        "name": "Execution Time",
                        "value": f"```{execution_time_message}```",
                        "inline": False,
                    }
                ],
            )

            # Add it to the queue
            grouped_notifications = group_notification(
                grouped_notifications, Embed(embed, None)
            )

            # Send any remaining queued notifications to Discord
            if grouped_notifications:
                sent_status = send_discord_message(None, grouped_notifications)
                if sent_status:
                    grouped_notifications = []

            send_message("\nWatching for changes... (WATCHDOG)", discord=False)


# Read all the lines from a text file, excluding specified lines.
def get_lines_from_file(file_path, ignore=[], check_paths=False):
    # Initialize an empty list to store the lines of the file
    results = []

    try:
        # Open the file in read mode
        with open(file_path, "r") as file:
            # Iterate over each line in the file
            for line in file:
                # Strip whitespace from the line
                line = line.strip()

                if not line:
                    continue

                if line in ignore + results:
                    continue

                if check_paths and paths and not line.startswith(tuple(paths)):
                    continue

                results.append(line)

    # Handle file not found exception
    except FileNotFoundError as e:
        # Print an error message and return an empty list
        send_message(f"File not found: {file_path}.\n{e}", error=True)
        return []

    # Handle other exceptions
    except Exception as ex:
        # Print an error message and return an empty list
        send_message(f"Error reading {file_path}.\n{ex}", error=True)
        return []

    # Return the list of lines read from the file
    return results


new_volume_webhook = None


# Processes the user paths
def process_path(path, paths_with_types, paths, is_download_folders=False):
    COMMON_EXTENSION_THRESHOLD = 0.3  # 30%

    # Attempts to automatically classify files based on certain thresholds and criteria.
    def process_auto_classification():
        nonlocal path_formats, path_extensions, path_library_types

        CHAPTER_THRESHOLD = 0.9  # 90%
        VOLUME_THRESHOLD = 0.9  # 90%

        files = get_all_files_in_directory(path_str)

        if files:
            print("\t\t\t- attempting auto-classification...")
            print(f"\t\t\t\t- got {len(files)} files.")
            if len(files) >= 100:
                print("\t\t\t\t\t- trimming files to 75%...")
                files = files[: int(len(files) * 0.75)]
                print(f"\t\t\t\t\t- trimmed to {len(files)} files.")

            print("\t\t\t\t- getting file extensions:")
            all_extensions = [get_file_extension(file) for file in files]

            path_extensions = get_common_extensions(all_extensions)

            path_extension_sets = [manga_extensions, novel_extensions]

            # If no common extensions, use default file extensions
            if not path_extensions:
                print(
                    f"\t\t\t\t\t- no accepted path extensions found, defaulting to: {file_extensions}"
                )
                path_extensions = file_extensions
            else:
                # Extend path extensions with known extension sets
                print(f"\t\t\t\t\t- path extensions found: {path_extensions}")
                print(
                    "\t\t\t\t\t- extending path extensions with known extension sets:"
                )
                print(f"\t\t\t\t\t\t- manga_extensions: {manga_extensions}")
                print(f"\t\t\t\t\t\t- novel_extensions: {novel_extensions}")
                path_extension_sets = [manga_extensions, novel_extensions]
                for ext_set in path_extension_sets:
                    if any(extension in path_extensions for extension in ext_set):
                        path_extensions.extend(
                            ext for ext in ext_set if ext not in path_extensions
                        )
                print(f"\t\t\t\t\t- path extensions: {path_extensions}")

            print("\t\t\t\t- getting path types:")
            all_types = [
                (
                    "chapter"
                    if (
                        not contains_volume_keywords(file)
                        and contains_chapter_keywords(file)
                    )
                    else "volume"
                )
                for file in files
            ]

            chapter_count = all_types.count("chapter")
            volume_count = all_types.count("volume")
            total_files = len(all_types)

            print(f"\t\t\t\t\t- chapter count: {chapter_count}")
            print(f"\t\t\t\t\t- volume count: {volume_count}")
            print(f"\t\t\t\t\t- total files: {total_files}")
            print(
                f"\t\t\t\t\t- chapter percentage: {int(chapter_count / total_files * 100)}%"
            )
            print(
                f"\t\t\t\t\t\t- required chapter percentage: {int(CHAPTER_THRESHOLD * 100)}%"
            )
            print(
                f"\t\t\t\t\t- volume percentage: {int(volume_count / total_files * 100)}%"
            )
            print(
                f"\t\t\t\t\t\t- required volume percentage: {int(VOLUME_THRESHOLD * 100)}%"
            )

            path_formats = [
                (
                    "chapter"
                    if chapter_count / total_files >= CHAPTER_THRESHOLD
                    else (
                        "volume"
                        if volume_count / total_files >= VOLUME_THRESHOLD
                        else file_formats
                    )
                )
            ]

            print(f"\t\t\t\t\t- path types: {path_formats}")

    # Gets the common extensions from a list of extensions
    def get_common_extensions(all_extensions):
        nonlocal COMMON_EXTENSION_THRESHOLD
        common_extensions = [
            ext
            for ext in set(all_extensions)
            if all_extensions.count(ext) / len(all_extensions)
            >= COMMON_EXTENSION_THRESHOLD
        ]
        return common_extensions if common_extensions else []

    # Determines what type of path it is, and assigns it to the appropriate list
    def process_single_type_path(path_to_process):
        nonlocal path_formats, path_extensions, path_library_types, path_translation_source_types
        if path_to_process.split(",")[0].strip() in file_formats:
            path_formats = [
                path_type.strip() for path_type in path_to_process.split(",")
            ]
        elif re.search(r"\.\w{1,4}", path_to_process):
            path_extensions = [
                ext.strip()
                for ext in path_to_process.split(",")
                if ext.strip() in file_extensions
            ]
        elif path_to_process.split(",")[0].strip() in [x.name for x in library_types]:
            path_library_types = [
                library_type.strip() for library_type in path_to_process.split(",")
            ]
        elif path_to_process.split(",")[0].strip() in translation_source_types:
            path_translation_source_types = [
                translation_source_type.strip()
                for translation_source_type in path_to_process.split(",")
            ]

    path_formats = []
    path_extensions = []
    path_library_types = []
    path_translation_source_types = []
    path_source_languages = []
    path_obj = None

    path_str = path[0]
    print(f"\t\t{path_str}")

    if len(path) == 1:
        if (
            watchdog_toggle
            and auto_classify_watchdog_paths
            and check_for_existing_series_toggle
            and not (download_folders and path_str in download_folders)
        ):
            process_auto_classification()
            path_obj = Path(
                path_str,
                path_formats=path_formats or [],
                path_extensions=path_extensions or [],
                library_types=path_library_types or [],
                translation_source_types=path_translation_source_types or [],
                source_languages=path_source_languages or [],
            )
    else:
        # process all paths except for the first one
        for path_to_process in path[1:]:
            process_single_type_path(path_to_process)

        path_obj = Path(
            path_str,
            path_formats=path_formats or file_formats,
            path_extensions=path_extensions or file_extensions,
            library_types=path_library_types or library_types,
            translation_source_types=path_translation_source_types
            or translation_source_types,
            source_languages=path_source_languages or [],
        )

    if not is_download_folders:
        paths.append(path_str)

        if path_obj:
            paths_with_types.append(path_obj)
    else:
        download_folders.append(path_str)

        if path_obj:
            download_folders_with_types.append(path_obj)


# Parses the passed command-line arguments
def parse_my_args():
    # Function to parse boolean arguments from string values
    def parse_bool_argument(arg_value):
        return str(arg_value).lower().strip() == "true"

    global paths
    global download_folders
    global discord_webhook_url
    global paths_with_types
    global komga_libraries
    global watchdog_toggle

    parser = argparse.ArgumentParser(
        description=f"Scans for and extracts covers from {', '.join(file_extensions)} files."
    )
    parser.add_argument(
        "-p",
        "--paths",
        help="The path/paths to be scanned for cover extraction.",
        action="append",
        nargs="*",
        required=False,
    )
    parser.add_argument(
        "-df",
        "--download_folders",
        help="The download folder/download folders for processing, renaming, and moving of downloaded files. (Optional, still in testing, requires manual uncommenting of optional method calls at the bottom of the script.)",
        action="append",
        nargs="*",
        required=False,
    )
    parser.add_argument(
        "-wh",
        "--webhook",
        action="append",
        nargs="*",
        help="The discord webhook url for notifications about changes and errors.",
        required=False,
    )
    parser.add_argument(
        "-bwc",
        "--bookwalker_check",
        help="Checks for new releases on bookwalker.",
        required=False,
    )
    parser.add_argument(
        "-c",
        "--compress",
        help="Compresses the extracted cover images.",
        required=False,
    )
    parser.add_argument(
        "-cq",
        "--compress_quality",
        help="The quality of the compressed cover images.",
        required=False,
    )
    parser.add_argument(
        "-bwk_whs",
        "--bookwalker_webhook_urls",
        help="The webhook urls for the bookwalker check.",
        action="append",
        nargs="*",
        required=False,
    )
    parser.add_argument(
        "-wd",
        "--watchdog",
        help="Uses the watchdog library to watch for file changes in the download folders.",
        required=False,
    )
    parser.add_argument(
        "-nw",
        "--new_volume_webhook",
        help="If passed in, the new volume release notification will be redirected to this single discord webhook channel.",
        required=False,
    )
    parser.add_argument(
        "-ltf",
        "--log_to_file",
        help="Whether or not to log the changes and errors to a file.",
        required=False,
    )
    parser.add_argument(
        "--watchdog_discover_new_files_check_interval",
        help="The amount of seconds to sleep before checking again if all the files are fully transferred.",
        required=False,
    )
    parser.add_argument(
        "--watchdog_file_transferred_check_interval",
        help="The seconds to sleep between file size checks when determining if a file is fully transferred.",
        required=False,
    )
    parser.add_argument(
        "--output_covers_as_webp",
        help="Outputs the covers as WebP format instead of jpg format.",
        required=False,
    )

    parser = parser.parse_args()

    print(f"\nScript Version: {script_version_text}")

    print("\nRun Settings:")

    if parser.download_folders is not None:
        new_download_folders = []
        for download_folder in parser.download_folders:
            if download_folder:
                if r"\1" in download_folder[0]:
                    split_download_folders = download_folder[0].split(r"\1")
                    new_download_folders.extend(
                        [split_download_folder]
                        for split_download_folder in split_download_folders
                    )
                else:
                    new_download_folders.append(download_folder)

        parser.download_folders = new_download_folders

        print("\tdownload_folders:")
        for download_folder in parser.download_folders:
            if download_folder:
                if r"\0" in download_folder[0]:
                    download_folder = download_folder[0].split(r"\0")
                process_path(
                    download_folder,
                    download_folders_with_types,
                    download_folders,
                    is_download_folders=True,
                )

        if download_folders_with_types:
            print("\n\tdownload_folders_with_types:")
            for item in download_folders_with_types:
                print(f"\t\tpath: {str(item.path)}")
                print(f"\t\t\tformats: {str(item.path_formats)}")
                print(f"\t\t\textensions: {str(item.path_extensions)}")

    if parser.watchdog:
        if download_folders:
            watchdog_toggle = parse_bool_argument(parser.watchdog)
        else:
            send_message(
                "Watchdog was toggled, but no download folders were passed to the script.",
                error=True,
            )

    if parser.paths is not None:
        new_paths = []
        for path in parser.paths:
            if path and r"\1" in path[0]:
                split_paths = path[0].split(r"\1")
                new_paths.extend([split_path] for split_path in split_paths)
            else:
                new_paths.append(path)

        parser.paths = new_paths
        print("\tpaths:")
        for path in parser.paths:
            if path:
                if r"\0" in path[0]:
                    path = path[0].split(r"\0")
                process_path(path, paths_with_types, paths)

        if paths_with_types:
            print("\n\tpaths_with_types:")
            for item in paths_with_types:
                print(f"\t\tpath: {str(item.path)}")
                print(f"\t\t\tformats: {str(item.path_formats)}")
                print(f"\t\t\textensions: {str(item.path_extensions)}")

    print(f"\twatchdog: {watchdog_toggle}")

    if watchdog_toggle:
        global watchdog_discover_new_files_check_interval, watchdog_file_transferred_check_interval
        if parser.watchdog_discover_new_files_check_interval:
            if parser.watchdog_discover_new_files_check_interval.isdigit():
                watchdog_discover_new_files_check_interval = int(
                    parser.watchdog_discover_new_files_check_interval
                )

        if parser.watchdog_file_transferred_check_interval:
            if parser.watchdog_file_transferred_check_interval.isdigit():
                watchdog_file_transferred_check_interval = int(
                    parser.watchdog_file_transferred_check_interval
                )
        print(
            f"\t\twatchdog_discover_new_files_check_interval: {watchdog_discover_new_files_check_interval}"
        )
        print(
            f"\t\twatchdog_file_transferred_check_interval: {watchdog_file_transferred_check_interval}"
        )

    if parser.output_covers_as_webp:
        global output_covers_as_webp
        output_covers_as_webp = parse_bool_argument(parser.output_covers_as_webp)
    print(f"\toutput_covers_as_webp: {output_covers_as_webp}")

    if not parser.paths and not parser.download_folders:
        print("No paths or download folders were passed to the script.")
        print("Exiting...")
        exit()

    if parser.webhook is not None:
        for item in parser.webhook:
            if item:
                for hook in item:
                    if hook:
                        if r"\1" in hook:
                            hook = hook.split(r"\1")
                        if isinstance(hook, str):
                            if hook and hook not in discord_webhook_url:
                                discord_webhook_url.append(hook)
                        elif isinstance(hook, list):
                            for url in hook:
                                if url and url not in discord_webhook_url:
                                    discord_webhook_url.append(url)
        print(f"\twebhooks: {str(discord_webhook_url)}")

    if parser.bookwalker_check:
        global bookwalker_check
        bookwalker_check = parse_bool_argument(parser.bookwalker_check)
    print(f"\tbookwalker_check: {bookwalker_check}")

    if parser.compress:
        global compress_image_option
        compress_image_option = parse_bool_argument(parser.compress)
    print(f"\tcompress: {compress_image_option}")

    if parser.compress_quality:
        global image_quality
        image_quality = int(parser.compress_quality)
    print(f"\tcompress_quality: {image_quality}")

    if parser.bookwalker_webhook_urls is not None:
        global bookwalker_webhook_urls
        for url in parser.bookwalker_webhook_urls:
            if url:
                for hook in url:
                    if hook:
                        if r"\1" in hook:
                            hook = hook.split(r"\1")
                        if isinstance(hook, str):
                            if hook and hook not in bookwalker_webhook_urls:
                                bookwalker_webhook_urls.append(hook)
                        elif isinstance(hook, list):
                            for url_in_hook in hook:
                                if (
                                    url_in_hook
                                    and url_in_hook not in bookwalker_webhook_urls
                                ):
                                    bookwalker_webhook_urls.append(url_in_hook)
        print(f"\tbookwalker_webhook_urls: {bookwalker_webhook_urls}")

    if parser.new_volume_webhook:
        global new_volume_webhook
        new_volume_webhook = parser.new_volume_webhook
    print(f"\tnew_volume_webhook: {new_volume_webhook}")

    if parser.log_to_file:
        global log_to_file
        log_to_file = parse_bool_argument(parser.log_to_file)
    print(f"\tlog_to_file: {log_to_file}")

    # Print all the settings from settings.py
    print("\nExternal Settings:")

    # print all of the variables
    sensitive_keywords = ["password", "email", "_ip", "token", "user"]
    ignored_settings = ["ranked_keywords", "unacceptable_keywords"]

    for setting in settings:
        if setting in ignored_settings:
            continue

        value = getattr(settings_file, setting)

        if value and any(keyword in setting.lower() for keyword in sensitive_keywords):
            value = "********"

        print(f"\t{setting}: {value}")

    print(f"\tin_docker: {in_docker}")
    print(f"\tblank_black_image_path: {blank_black_image_path}")
    print(f"\tblank_white_image_path: {blank_white_image_path}")

    if (
        send_scan_request_to_komga_libraries_toggle
        and check_for_existing_series_toggle
        and watchdog_toggle
    ):
        komga_libraries = get_komga_libraries()
        komga_library_paths = (
            [x["root"] for x in komga_libraries] if komga_libraries else []
        )
        print(f"\tkomga_libraries: {komga_library_paths}")


# Converts the passed volume_number into a float or an int.
def set_num_as_float_or_int(volume_number, silent=False):
    if volume_number == "":
        return ""

    try:
        if isinstance(volume_number, list):
            result = "-".join(
                [
                    (
                        str(int(float(num)))
                        if float(num) == int(float(num))
                        else str(float(num))
                    )
                    for num in volume_number
                ]
            )
            return result
        elif isinstance(volume_number, str) and "." in volume_number:
            volume_number = float(volume_number)
        else:
            if float(volume_number) == int(volume_number):
                volume_number = int(volume_number)
            else:
                volume_number = float(volume_number)
    except Exception as e:
        if not silent:
            send_message(
                f"Failed to convert volume number to float or int: {volume_number}\nERROR: {e}",
                error=True,
            )
            send_message(f"{e}", error=True)
        return ""
    return volume_number


# Compresses an image and saves it to a file or returns the compressed image data.
def compress_image(image_path, quality=60, to_jpg=False, raw_data=None):
    new_filename = None
    buffer = None
    save_format = "JPEG"

    # Load the image from the file or raw data
    image = Image.open(image_path if not raw_data else io.BytesIO(raw_data))

    # Convert the image to RGB if it has an alpha channel or uses a palette
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    filename, ext = os.path.splitext(image_path)

    if ext == ".webp":
        save_format = "WEBP"

    # Determine the new filename for the compressed image
    if not raw_data:
        if to_jpg or ext.lower() == ".png":
            ext = ".jpg"
            if not to_jpg:
                to_jpg = True
        new_filename = f"{filename}{ext}"

    # Try to compress and save the image
    try:
        if not raw_data:
            image.save(new_filename, format=save_format, quality=quality, optimize=True)
        else:
            buffer = io.BytesIO()
            image.save(buffer, format=save_format, quality=quality)
            return buffer.getvalue()
    except Exception as e:
        # Log the error and continue
        send_message(f"Failed to compress image {image_path}: {e}", error=True)

    # Remove the original file if it's a PNG that was converted to JPG
    if to_jpg and ext.lower() == ".jpg" and os.path.isfile(image_path):
        os.remove(image_path)

    # Return the path to the compressed image file, or the compressed image data
    return new_filename if not raw_data else buffer.getvalue()


# Check the text file line by line for the passed message
def check_text_file_for_message(text_file, message):
    # Open the file in read mode using a context manager
    with open(text_file, "r") as f:
        # Check if any line in the file matches the message
        return any(line.strip() == message.strip() for line in f)


# Adjusts discord embeds fields to fit the discord embed field limits
def handle_fields(embed, fields):
    if fields:
        # An embed can contain a maximum of 25 fields
        fields = fields[:25]

        for field in fields:
            # A field name/title is limited to 256 characters
            if len(field["name"]) > 256:
                field["name"] = (
                    field["name"][:253] + "..."
                    if not field["name"].endswith("```")
                    else field["name"][:-3][:250] + "...```"
                )

            # The value of the field is limited to 1024 characters
            if len(field["value"]) > 1024:
                field["value"] = (
                    field["value"][:1021] + "..."
                    if not field["value"].endswith("```")
                    else field["value"][:-3][:1018] + "...```"
                )

            embed.add_embed_field(
                name=field["name"],
                value=field["value"],
                inline=field["inline"],
            )
    return embed


last_hook_index = None


# Handles picking a webhook url, to evenly distribute the load
@lru_cache(maxsize=None)
def pick_webhook(hook, passed_webhook=None, url=None):
    global last_hook_index

    if passed_webhook:
        hook = passed_webhook
    elif url:
        hook = url
    elif discord_webhook_url:
        if last_hook_index is None or last_hook_index == len(discord_webhook_url) - 1:
            hook = discord_webhook_url[0]
        else:
            hook = discord_webhook_url[last_hook_index + 1]
        last_hook_index = discord_webhook_url.index(hook)

    return hook


webhook_obj = DiscordWebhook(url=None)


# Sends a discord message using the users webhook url
def send_discord_message(
    message,
    embeds=[],
    url=None,
    rate_limit=True,
    timestamp=True,
    passed_webhook=None,
    image=None,
    image_local=None,
):
    global grouped_notifications, webhook_obj

    sent_status = False
    hook = None
    hook = pick_webhook(hook, passed_webhook, url)

    try:
        if hook:
            webhook_obj.url = hook

            if rate_limit:
                webhook_obj.rate_limit_retry = rate_limit

            if embeds:
                # Limit the number of embeds to 10
                for index, embed in enumerate(embeds[:10], start=1):
                    if script_version_text:
                        embed.embed.set_footer(text=script_version_text)

                    if timestamp and (
                        not hasattr(embed.embed, "timestamp")
                        or not embed.embed.timestamp
                    ):
                        embed.embed.set_timestamp()

                    if image and not image_local:
                        embed.embed.set_image(url=image)
                    elif embed.file:
                        file_name = (
                            "cover.jpg" if len(embeds) == 1 else f"cover_{index}.jpg"
                        )
                        webhook_obj.add_file(file=embed.file, filename=file_name)
                        embed.embed.set_image(url=f"attachment://{file_name}")

                    webhook_obj.add_embed(embed.embed)
            elif message:
                webhook_obj.content = message

            webhook_obj.execute()
            sent_status = True
    except Exception as e:
        send_message(f"{e}", error=True, discord=False)
        # Reset the webhook object
        webhook_obj = DiscordWebhook(url=None)
        return sent_status

    # Reset the webhook object
    webhook_obj = DiscordWebhook(url=None)

    return sent_status


# Removes hidden files
def remove_hidden_files(files):
    return [x for x in files if not x.startswith(".")]


# Removes any unaccepted file types
def remove_unaccepted_file_types(files, root, accepted_extensions, test_mode=False):
    return [
        file
        for file in files
        if get_file_extension(file) in accepted_extensions
        and (os.path.isfile(os.path.join(root, file)) or test_mode)
    ]


# Removes any folder names in the ignored_folder_names
def remove_ignored_folders(dirs):
    return [x for x in dirs if x not in ignored_folder_names]


# Remove hidden folders from the list
def remove_hidden_folders(dirs):
    return [x for x in dirs if not x.startswith(".")]


# Determines if the string starts with a bracket
def starts_with_bracket(s):
    return s.startswith(("(", "[", "{"))


# Determines if the string ends with a bracket
def ends_with_bracket(s):
    return s.endswith((")", "]", "}"))


volume_year_regex = r"(\(|\[|\{)(\d{4})(\)|\]|\})"


# check if volume file name is a chapter
@lru_cache(maxsize=None)
def contains_chapter_keywords(file_name):
    # Replace "_extra"
    file_name_clean = file_name.replace("_extra", ".5")

    # Replace underscores
    file_name_clean = (
        replace_underscores(file_name_clean).strip()
        if "_" in file_name_clean
        else file_name_clean
    )

    # Remove "c1fi7"
    file_name_clean = file_name_clean.replace("c1fi7", "")

    # Remove dual spaces
    file_name_clean = remove_dual_space(file_name_clean).strip()

    # Use compiled patterns for searching
    found = False
    for pattern in chapter_search_patterns_comp:
        result = pattern.search(file_name_clean)
        if result:
            result = result.group()
            if not (
                starts_with_bracket(result)
                and ends_with_bracket(result)
                and re.search(r"^((\(|\{|\[)\d{4}(\]|\}|\)))$", result)
            ):
                found = True
                break

    if not found and not contains_volume_keywords(file_name):
        # Remove volume year
        without_year = re.sub(volume_year_regex, "", file_name, flags=re.IGNORECASE)

        # Remove any 2000-2999 numbers at the end
        without_year = re.sub(r"\b(?:2\d{3})\b$", "", without_year, flags=re.IGNORECASE)

        # Check for chapter numbers
        chapter_numbers_found = re.search(
            r"(?<!^)(?<!\d\.)\b([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?(\.\d+)?\b",
            without_year,
        )
        if chapter_numbers_found:
            found = True

    return found


# Pre-compile the bracket pattern
brackets_pattern = re.compile(r"[(){}\[\]]")


# Determines if the string contains brackets
def contains_brackets(s):
    return bool(brackets_pattern.search(s))


# Pre-combiled remove_brackets() patterns
bracket_removal_pattern = re.compile(
    r"((((?<!-|[A-Za-z]\s|\[)(\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})(?!-|\s*[A-Za-z]|\]))(\s+)?)+|([\[\{\(]((\d{4}))[\]\}\)]))",
    re.IGNORECASE,
)
bracket_avoidance_pattern = re.compile(r"^[\(\[\{].*[\)\]\}]$")
bracket_against_extension_pattern = re.compile(
    r"(\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})(\.\w+$)"
)


# Removes bracketed content from the string, alongwith any whitespace.
# As long as the bracketed content is not immediately preceded or followed by a dash.
@lru_cache(maxsize=None)
def remove_brackets(string):
    # Avoid a string that is only a bracket
    # Probably a series name
    # EX: [(OSHI NO KO)]
    if (
        starts_with_bracket(string)
        and ends_with_bracket(string)
        and bracket_avoidance_pattern.search(string)
    ):
        return string

    # Remove all grouped brackets as long as they aren't surrounded by dashes,
    # letters, or square brackets.
    # Regex 1: ([\[\{\(]((\d{4}))[\]\}\)]) - FOR YEAR
    # Regex 2: (((?<!-|[A-Za-z]\s|\[)(\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})(?!-|\s*[A-Za-z]|\]))(\s+)?)+ - FOR EVERYTHING ELSE
    string = bracket_removal_pattern.sub("", string).strip()

    # Get file extension
    ext = get_file_extension(string)

    if ext:
        # Remove ending bracket against the extension
        # EX: test (digital).cbz -> test .cbz
        string = (
            bracket_against_extension_pattern.sub(r"\2", string).strip()
            if contains_brackets(string)
            else string
        )

        # Remove the extension
        # EX: test.cbz -> test
        string = string.replace(ext, "").strip()

        # Re-add the extension
        # EX: test -> test.cbz
        string = f"{string}{ext}"

    # Return the modified string
    return string


# Pre-compile the volume pattern
volume_regex = re.compile(
    r"((\s?(\s-\s|)(Part|)+({})(\.|)([-_. ]|)([0-9]+)\b)|\s?(\s-\s|)(Part|)({})(\.|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(Part|)({})([0-9]+)\s|\s?(\s-\s|)(Part|)({})(\.|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(Part|)({})([0-9]+)\s)".format(
        volume_regex_keywords,
        volume_regex_keywords,
        volume_regex_keywords,
        volume_regex_keywords,
        volume_regex_keywords,
    ),
    re.IGNORECASE,
)


# Checks if the passed string contains volume keywords
@lru_cache(maxsize=None)
def contains_volume_keywords(file):
    # Replace _extra
    file = file.replace("_extra", ".5")

    # Remove dual spaces
    file = remove_dual_space(file).strip()

    # Remove brackets
    clean_file = remove_brackets(file) if contains_brackets(file) else file

    # Replace underscores
    clean_file = (
        replace_underscores(clean_file).strip()
        if "_" in clean_file
        else clean_file.strip()
    )

    # Remove dual spaces
    clean_file = remove_dual_space(clean_file).strip()

    return bool(volume_regex.search(clean_file))


# Removes all chapter releases
def filter_non_chapters(files):
    return [
        file
        for file in files
        if not contains_chapter_keywords(file) or contains_volume_keywords(file)
    ]


# Caches the given path and writes it to a file
def cache_path(path):
    if path in paths + download_folders:
        return

    global cached_paths
    cached_paths.append(path)
    write_to_file(
        "cached_paths.txt",
        path,
        without_timestamp=True,
        check_for_dup=True,
    )


# Cleans and sorts the passed files and directories
def clean_and_sort(
    root,
    files=[],
    dirs=[],
    sort=False,
    chapters=chapter_support_toggle,
    just_these_files=[],
    just_these_dirs=[],
    skip_remove_ignored_folders=False,
    skip_remove_hidden_files=False,
    skip_remove_unaccepted_file_types=False,
    skip_remove_hidden_folders=False,
    keep_images_in_just_these_files=False,
    is_correct_extensions_feature=[],
    test_mode=False,
):
    # Cache the root path
    if (
        check_for_existing_series_toggle
        and not test_mode
        and root not in cached_paths + download_folders + paths
        and not any(root.startswith(path) for path in download_folders)
    ):
        cache_path(root)

    # Remove ignored folder names if present
    if ignored_folder_names and not skip_remove_ignored_folders:
        ignored_parts = any(
            part for part in root.split(os.sep) if part in ignored_folder_names
        )
        if ignored_parts:
            return [], []

    # Sort files and directories
    if sort:
        files.sort()
        dirs.sort()

    # Process files
    if files:
        # Remove hidden files
        if not skip_remove_hidden_files:
            files = remove_hidden_files(files)

        # Remove unaccepted file types
        if not skip_remove_unaccepted_file_types and files:
            files = remove_unaccepted_file_types(
                files,
                root,
                (
                    file_extensions
                    if not is_correct_extensions_feature
                    else is_correct_extensions_feature
                ),
                test_mode=test_mode,
            )

        # Filter files based on just_these_files
        if just_these_files and files:
            files = [
                x
                for x in files
                if os.path.join(root, x) in just_these_files
                or (
                    keep_images_in_just_these_files
                    and get_file_extension(x) in image_extensions
                )
            ]

        # Filter out all chapter releases
        if not chapters and files:
            files = filter_non_chapters(files)

    # Process directories
    if dirs:
        # Remove hidden folders
        if not skip_remove_hidden_folders:
            dirs = remove_hidden_folders(dirs)

        # Remove ignored folder names
        if not skip_remove_ignored_folders and dirs:
            dirs = remove_ignored_folders(dirs)

    return files, dirs


def process_files_and_folders(
    root,
    files=[],
    dirs=[],
    sort=False,
    chapters=chapter_support_toggle,
    just_these_files=[],
    just_these_dirs=[],
    skip_remove_unaccepted_file_types=False,
    keep_images_in_just_these_files=False,
    is_correct_extensions_feature=[],
    test_mode=False,
):
    in_download_folders = (
        watchdog_toggle
        and download_folders
        and any(x for x in download_folders if root.startswith(x))
    )

    files, dirs = clean_and_sort(
        root,
        files,
        dirs,
        sort=sort,
        chapters=chapters,
        just_these_files=just_these_files if in_download_folders else [],
        just_these_dirs=just_these_dirs if in_download_folders else [],
        skip_remove_unaccepted_file_types=skip_remove_unaccepted_file_types,
        keep_images_in_just_these_files=(
            keep_images_in_just_these_files if in_download_folders else False
        ),
        is_correct_extensions_feature=is_correct_extensions_feature,
        test_mode=test_mode,
    )
    return files, dirs


# Retrieves the file extension on the passed file
def get_file_extension(file):
    return os.path.splitext(file)[1]


# Gets the predicted file extension from the file header using filetype
def get_header_extension(file):
    extension_from_name = get_file_extension(file)
    if extension_from_name in manga_extensions or extension_from_name in rar_extensions:
        try:
            kind = filetype.guess(file)
            if kind is None:
                return None
            elif f".{kind.extension}" in manga_extensions:
                return ".cbz"
            elif f".{kind.extension}" in rar_extensions:
                return ".cbr"
            else:
                return f".{kind.extension}"
        except Exception as e:
            send_message(str(e), error=True)
            return None
    else:
        return None


# Returns an extensionless name
def get_extensionless_name(file):
    return os.path.splitext(file)[0]


# Creates and returns file objects from the passed files and root
def upgrade_to_file_class(
    files,
    root,
    skip_get_header_extension=True,
    is_correct_extensions_feature=[],
    test_mode=False,
    clean=False,
):
    if not files:
        return []

    # Avoid any features that require an actual file
    if test_mode:
        skip_get_header_extension = True

    # Clean up the files array before usage
    if clean:
        files = clean_and_sort(
            root,
            files,
            is_correct_extensions_feature=is_correct_extensions_feature,
            test_mode=test_mode,
        )[0]

    # Create a list of tuples with arguments to pass to the File constructor
    file_types = [
        (
            "chapter"
            if not contains_volume_keywords(file) and contains_chapter_keywords(file)
            else "volume"
        )
        for file in files
    ]

    chapter_numbers = [
        get_release_number_cache(file, chapter=file_type == "chapter")
        for file, file_type in zip(files, file_types)
    ]

    file_args = [
        (
            file,
            get_extensionless_name(file),
            (
                get_series_name_from_chapter(file, root, chapter_number)
                if file_type == "chapter"
                else get_series_name_from_volume(file, root, test_mode=test_mode)
            ),
            get_file_extension(file),
            root,
            os.path.join(root, file),
            get_extensionless_name(os.path.join(root, file)),
            chapter_number,
            file_type,
            (
                get_header_extension(os.path.join(root, file))
                if not skip_get_header_extension
                else None
            ),
        )
        for file, file_type, chapter_number in zip(files, file_types, chapter_numbers)
    ]

    results = [File(*args) for args in file_args]

    return results


# Updates our output stats
def update_stats(file):
    global file_counters
    file_counters[file.extension] += 1


# Credit to original source: https://alamot.github.io/epub_cover/
# Modified by me.
# Retrieves the inner novel cover
def get_novel_cover(novel_path):
    namespaces = {
        "calibre": "http://calibre.kovidgoyal.net/2009/metadata",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
        "opf": "http://www.idpf.org/2007/opf",
        "u": "urn:oasis:names:tc:opendocument:xmlns:container",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    try:
        with zipfile.ZipFile(novel_path) as z:
            t = etree.fromstring(z.read("META-INF/container.xml"))
            rootfile_path = t.xpath(
                "/u:container/u:rootfiles/u:rootfile", namespaces=namespaces
            )
            if rootfile_path:
                rootfile_path = rootfile_path[0].get("full-path")
                t = etree.fromstring(z.read(rootfile_path))
                cover_id = t.xpath(
                    "//opf:metadata/opf:meta[@name='cover']", namespaces=namespaces
                )
                if cover_id:
                    cover_id = cover_id[0].get("content")
                    cover_href = t.xpath(
                        f"//opf:manifest/opf:item[@id='{cover_id}']",
                        namespaces=namespaces,
                    )
                    if cover_href:
                        cover_href = cover_href[0].get("href")
                        if "%" in cover_href:
                            cover_href = urllib.parse.unquote(cover_href)
                        cover_path = os.path.join(
                            os.path.dirname(rootfile_path), cover_href
                        )
                        return cover_path
                    else:
                        print("\t\t\tNo cover_href found in get_novel_cover()")
                else:
                    print("\t\t\tNo cover_id found in get_novel_cover()")
            else:
                print(
                    "\t\t\tNo rootfile_path found in META-INF/container.xml in get_novel_cover()"
                )
    except Exception as e:
        send_message(str(e), error=True)
    return None


# Checks if the passed string is a volume one.
@lru_cache(maxsize=None)
def is_volume_one(volume_name):
    keywords = volume_regex_keywords

    if contains_chapter_keywords(volume_name) and not contains_volume_keywords(
        volume_name
    ):
        keywords = chapter_regex_keywords + "|"

    if re.search(
        r"(\b(%s)([-_. ]|)(\s+)?(One|1|01|001|0001)(([-_.]([0-9]+))+)?\b)" % keywords,
        volume_name,
        re.IGNORECASE,
    ):
        return True

    return False


# Checks for volume keywords and chapter keywords.
# If neither are present, the volume is assumed to be a one-shot volume.
def is_one_shot(file_name, root=None, skip_folder_check=False, test_mode=False):
    files = []

    if test_mode:
        skip_folder_check = True

    if (
        contains_volume_keywords(file_name)
        or contains_chapter_keywords(file_name)
        or check_for_exception_keywords(file_name, exception_keywords)
    ):
        return False

    if not skip_folder_check:
        files = clean_and_sort(root, os.listdir(root))[0]

    if (len(files) == 1 or skip_folder_check) or (
        download_folders and root in download_folders
    ):
        return True

    return False


# Checks similarity between two strings.
@lru_cache(maxsize=None)
def similar(a, b):
    # convert to lowercase and strip
    a = a.lower().strip()
    b = b.lower().strip()

    # evaluate
    if a == "" or b == "":
        return 0.0
    elif a == b:
        return 1.0
    else:
        return SequenceMatcher(None, a, b).ratio()


# Sets the modification date of the passed file path to the passed date.
def set_modification_date(file_path, date):
    try:
        os.utime(file_path, (get_modification_date(file_path), date))
    except Exception as e:
        send_message(
            f"ERROR: Could not set modification date of {file_path}\nERROR: {e}",
            error=True,
        )


# Determies if two index_numbers are the same
def is_same_index_number(index_one, index_two, allow_array_match=False):
    if (index_one == index_two and index_one != "") or (
        allow_array_match
        and (
            (isinstance(index_one, list) and index_two in index_one)
            or (isinstance(index_two, list) and index_one in index_two)
        )
    ):
        return True
    return False


# Gets the hash of the passed file and returns it as a string
def get_file_hash(file, is_internal=False, internal_file_name=None):
    try:
        BUF_SIZE = 65536  # 64KB buffer size (adjust as needed)
        hash_obj = hashlib.sha256()

        if is_internal:
            with zipfile.ZipFile(file) as zip:
                with zip.open(internal_file_name) as internal_file:
                    while True:
                        data = internal_file.read(BUF_SIZE)
                        if not data:
                            break
                        hash_obj.update(data)
        else:
            with open(file, "rb") as f:
                while True:
                    data = f.read(BUF_SIZE)
                    if not data:
                        break
                    hash_obj.update(data)

        return hash_obj.hexdigest()
    except FileNotFoundError as e:
        # Handle file not found error
        send_message(f"\n\t\t\tError: File not found - {e}", error=True)
        return None
    except KeyError as e:
        # Handle file not found in the zip error
        send_message(f"\n\t\t\tError: File not found in the zip - {e}", error=True)
        return None
    except Exception as e:
        # Handle other exceptions
        send_message(f"\n\t\t\tError: {e}", error=True)
        return None


# Moves the image into a folder if said image exists. Also checks for a cover/poster image and moves that.
def move_images(
    file,
    folder_name,
    highest_index_num="",
    is_chapter_dir=False,
):
    for extension in image_extensions:
        image = file.extensionless_path + extension
        if os.path.isfile(image):
            already_existing_image = os.path.join(folder_name, os.path.basename(image))
            if os.path.isfile(already_existing_image):
                remove_file(already_existing_image, silent=True)
            shutil.move(image, folder_name)

        for cover_file_name in series_cover_file_names:
            cover_image_file_name = cover_file_name + extension
            cover_image_file_path = os.path.join(file.root, cover_image_file_name)

            if os.path.isfile(cover_image_file_path):
                already_existing_cover_image = os.path.join(
                    folder_name, cover_image_file_name
                )

                # check that the image is not already in the folder
                if not os.path.isfile(already_existing_cover_image):
                    shutil.move(cover_image_file_path, folder_name)
                elif file.volume_number == 1 and (
                    not use_latest_volume_cover_as_series_cover or is_chapter_dir
                ):
                    remove_file(already_existing_cover_image, silent=True)
                    shutil.move(cover_image_file_path, folder_name)
                elif (
                    use_latest_volume_cover_as_series_cover
                    and file.file_type == "volume"
                    and is_same_index_number(
                        file.index_number, highest_index_num, allow_array_match=True
                    )
                ):
                    # get the cover image in the folder
                    existing_cover_image_file_path = [
                        os.path.join(folder_name, f"cover{ext}")
                        for ext in image_extensions
                        if os.path.isfile(os.path.join(folder_name, f"cover{ext}"))
                    ]
                    if existing_cover_image_file_path:
                        existing_cover_image_file_path = existing_cover_image_file_path[
                            0
                        ]
                    if os.path.isfile(cover_image_file_path) and os.path.isfile(
                        existing_cover_image_file_path
                    ):
                        cover_image_file_modification_date = get_modification_date(
                            cover_image_file_path
                        )
                        existing_cover_image_file_modification_date = (
                            get_modification_date(existing_cover_image_file_path)
                        )
                        if (
                            cover_image_file_modification_date
                            != existing_cover_image_file_modification_date
                        ):
                            cover_image_file_hash = get_file_hash(cover_image_file_path)
                            existing_cover_image_file_hash = get_file_hash(
                                existing_cover_image_file_path
                            )
                            if cover_image_file_hash != existing_cover_image_file_hash:
                                # delete the existing cover image
                                remove_file(existing_cover_image_file_path, silent=True)
                                # move the new cover image
                                shutil.move(cover_image_file_path, folder_name)
                            else:
                                # copy the modification date of the existing cover image to the new cover image
                                set_modification_date(
                                    cover_image_file_path,
                                    existing_cover_image_file_modification_date,
                                )
                                # delete the new cover image
                                remove_file(cover_image_file_path, silent=True)
                        else:
                            # delete the new cover image
                            remove_file(cover_image_file_path, silent=True)
                else:
                    # remove the cover image from the folder
                    remove_file(cover_image_file_path, silent=True)


# Retrieves the series name through various regexes
# Removes the volume number and anything to the right of it, and strips it.
@lru_cache(maxsize=None)
def get_series_name_from_volume(name, root, test_mode=False, second=False):
    # Remove starting brackets
    # EX: "[WN] Series Name" -> "Series Name"
    if starts_with_bracket(name) and re.search(
        r"^(\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})+(\s+[A-Za-z]{2})", name
    ):
        # remove the brackets only
        name = re.sub(r"^(\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})+\s+", "", name).strip()

    # replace _extra
    name = remove_dual_space(name.replace("_extra", ".5")).strip()

    # replace underscores
    name = replace_underscores(name) if "_" in name else name

    # remove brackets
    # name = remove_brackets(name) if contains_brackets(name) else name

    if is_one_shot(name, root, test_mode=test_mode):
        name = re.sub(
            r"([-_ ]+|)(((\[|\(|\{).*(\]|\)|\}))|LN)([-_. ]+|)(%s|).*"
            % file_extensions_regex.replace("\.", ""),
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()
    else:
        if re.search(
            r"(\b|\s)(?<![A-Za-z])((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(%s)(\.|)([-_. ]|)([0-9]+)(\b|\s).*"
            % volume_regex_keywords,
            name,
            flags=re.IGNORECASE,
        ):
            name = (
                re.sub(
                    r"(\b|\s)(?<![A-Za-z])((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(%s)(\.|)([-_. ]|)([0-9]+)(\b|\s).*"
                    % volume_regex_keywords,
                    "",
                    name,
                    flags=re.IGNORECASE,
                )
            ).strip()
        else:
            name = re.sub(
                r"(\d+)?([-_. ]+)?((\[|\(|\})(.*)(\]|\)|\}))?([-_. ]+)?(%s)$"
                % file_extensions_regex,
                "",
                name,
                flags=re.IGNORECASE,
            ).strip()

    # Remove a trailing comma at the end of the name
    if name.endswith(","):
        name = name[:-1].strip()

    # remove the file extension if still remaining
    name = re.sub(r"(%s)$" % file_extensions_regex, "", name).strip()

    # Remove "- Complete" from the end
    # "Series Name - Complete" -> "Series Name"
    # EX File: Series Name - Complete v01 [Premium] [Publisher].epub
    if name.lower().endswith("complete"):
        name = re.sub(r"(-|:)\s*Complete$", "", name, flags=re.IGNORECASE).strip()

    # Default to the root folder name if we have nothing left
    # As long as it's not in our download folders or paths
    if (
        not name
        and not second
        and root
        and (
            os.path.basename(root) not in str(download_folders) or not download_folders
        )
        and (os.path.basename(root) not in str(paths) or not paths)
        and not contains_keyword(os.path.basename(root))
    ):
        # Get the series namne from the root folder
        # EX: "Kindaichi 37-sai no Jikenbo -v01-v12-"" -> "Kindaichi 37-sai no Jikenbo"
        name = get_series_name_from_volume(
            os.path.basename(root), root, test_mode=test_mode, second=True
        )

        # Remove any brackets
        name = remove_brackets(name) if contains_brackets(name) else name

    return name


# Cleans the chapter file_name to retrieve the series_name
@lru_cache(maxsize=None)
def chapter_file_name_cleaning(
    file_name, chapter_number="", skip=False, regex_matched=False
):
    # removes any brackets and their contents
    file_name = (
        remove_brackets(file_name) if contains_brackets(file_name) else file_name
    )

    # Remove any single brackets at the end of the file_name
    # EX: "Death Note - Bonus Chapter (" -> "Death Note - Bonus Chapter"
    file_name = re.sub(r"(\s(([\(\[\{])|([\)\]\}])))$", "", file_name).strip()

    # EX: "006.3 - One Piece" -> "One Piece"
    if regex_matched != 2:
        file_name = re.sub(
            r"(^([0-9]+)(([-_.])([0-9]+)|)+(\s+)?([-_]+)(\s+))", "", file_name
        ).strip()

    # Remove number and dash at the end
    # EX: "Series Name 54 -" -> "Series Name"
    if regex_matched != 0 and file_name.endswith("-"):
        file_name = re.sub(
            r"(#)?([0-9]+)([-_.][0-9]+)*((x|#)([0-9]+)([-_.][0-9]+)*)*\s*-$",
            "",
            file_name,
        ).strip()

    # Remove - at the end of the file_name
    # EX: " One Piece -" -> "One Piece"
    if file_name.endswith("-"):
        file_name = re.sub(r"(?<![A-Za-z])(-\s*)$", "", file_name).strip()

    # Return if we have nothing but a digit left, if not skip
    if file_name.replace("#", "").isdigit() and not skip:
        return ""
    elif file_name.replace("#", "").replace(".", "", 1).isdigit() and not skip:
        return ""

    # if chapter_number and it's at the end of the file_name, remove it
    # EX: "One Piece 001" -> "One Piece"
    if not regex_matched:
        if chapter_number != "" and re.search(
            r"-?(\s+)?((?<!({})(\s+)?)(\s+)?\b#?((0+)?({}|{}))#?$)".format(
                chapter_regex_keywords,
                chapter_number,
                chapter_number,
            ),
            file_name,
        ):
            file_name = re.sub(
                r"-?(\s+)?((?<!({})(\s+)?)(\s+)?\b#?((0+)?({}|{}))#?$)".format(
                    chapter_regex_keywords,
                    chapter_number,
                    chapter_number,
                ),
                "",
                file_name,
            ).strip()

    # Remove any season keywords
    if "s" in file_name.lower() and re.search(
        r"(Season|Sea| S)(\s+)?([0-9]+)$", file_name, re.IGNORECASE
    ):
        file_name = re.sub(
            r"(Season|Sea| S)(\s+)?([0-9]+)$", "", file_name, flags=re.IGNORECASE
        )

    # Remove any subtitle
    # EX: "Series Name 179.1 - Epilogue 01 (2023) (Digital) (release_group).cbz"
    # "179.1 - Epilogue 01" -> "179.1"
    if ("-" in file_name or ":" in file_name) and re.search(
        r"(^\d+)", file_name.strip()
    ):
        file_name = re.sub(r"((\s+(-)|:)\s+).*$", "", file_name, re.IGNORECASE).strip()

    return file_name


# Retrieves the series name from the file name and chapter number
def get_series_name_from_chapter(name, root, chapter_number="", second=False):
    # Remove starting brackets
    # EX: "[WN] Series Name" -> "Series Name"
    if starts_with_bracket(name) and re.search(
        r"^(\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})+(\s+[A-Za-z]{2})", name
    ):
        # remove the brackets only
        name = re.sub(r"^(\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})+\s+", "", name).strip()

    # Replace _extra
    name = name.replace("_extra", ".5")

    # Remove dual space
    name = remove_dual_space(name).strip()

    # remove the file extension
    name = get_extensionless_name(name)

    # replace underscores
    name = replace_underscores(name) if "_" in name else name

    regex_matched = False
    search = next(
        (r for pattern in chapter_search_patterns_comp if (r := pattern.search(name))),
        None,
    )

    if search:
        regex_matched = True
        search = search.group()
        name = name.split(search)[0].strip()

    result = ""

    if name:
        if isinstance(chapter_number, list):
            result = chapter_file_name_cleaning(
                name, chapter_number[0], regex_matched=regex_matched
            )
        else:
            result = chapter_file_name_cleaning(
                name, chapter_number, regex_matched=regex_matched
            )

    # Remove a trailing comma at the end of the name
    if result.endswith(","):
        result = result[:-1].strip()

    # Default to the root folder name if we have nothing left
    # As long as it's not in our download folders or paths
    if (
        not result
        and not second
        and root
        and os.path.basename(root) not in str(download_folders + paths)
        and not contains_keyword(os.path.basename(root))
    ):
        root_number = get_release_number_cache(os.path.basename(root))

        # Get series name
        result = get_series_name_from_chapter(
            os.path.basename(root),
            root,
            root_number if root_number else "",
            second=True,
        )

        # Remove any brackets
        result = remove_brackets(result) if contains_brackets(result) else result

    return result


# Calculates the percentage of files in a folder that match a specified extension or file type.
def get_folder_type(files, extensions=None, file_type=None):
    if not files:
        return 0

    count = 0

    # If a file type is specified, count the number of files in the list that match that type
    if file_type:
        count = sum(1 for file in files if file.file_type == file_type)
    # Otherwise, if a list of extensions is specified, count the number of files in the list that have one of those extensions
    elif extensions:
        # Create a set of extensions for efficient lookup
        extension_set = set(extensions)
        # Count the number of files with extensions in the extension_set
        count = sum(1 for file in files if get_file_extension(file) in extension_set)
    else:
        return 0

    # Calculate the percentage of files in the list that match the specified extension or file type
    return (count / len(files)) * 100


# Determines if a volume file is a multi-volume file or not
# EX: TRUE == series_title v01-03.cbz
# EX: FALSE == series_title v01.cbz
@lru_cache(maxsize=None)
def check_for_multi_volume_file(file_name, chapter=False):
    # Set the list of keywords to search for
    keywords = volume_regex_keywords if not chapter else chapter_regex_keywords + "|"

    # Search for a multi-volume or multi-chapter pattern in the file name, ignoring any bracketed information in the name
    if "-" in file_name and re.search(
        # Use regular expressions to search for the pattern of multiple volumes or chapters
        r"(\b({})(\.)?(\s+)?([0-9]+(\.[0-9]+)?)([-]([0-9]+(\.[0-9]+)?))+\b)".format(
            keywords
        ),
        remove_brackets(file_name) if contains_brackets(file_name) else file_name,
        re.IGNORECASE,  # Ignore case when searching
    ):
        # If the pattern is found, return True
        return True
    else:
        # If the pattern is not found, return False
        return False


# Converts our list of numbers into an array of numbers, returning only the lowest and highest numbers in the list
# EX "1, 2, 3" -> [1, 3]
def get_min_and_max_numbers(string):
    # initialize an empty list to hold the numbers
    numbers = []

    # replace hyphens and underscores with spaces using regular expressions
    numbers_search = re.sub(r"[-_,]", " ", string)

    # remove any duplicate spaces
    numbers_search = remove_dual_space(numbers_search).strip()

    # split the resulting string into a list of individual strings
    numbers_search = numbers_search.split(" ")

    # convert each string in the list to either an integer or a float using the set_num_as_float_or_int function
    numbers_search = [set_num_as_float_or_int(num) for num in numbers_search if num]

    # if the resulting list is not empty, filter it further
    if numbers_search:
        # get lowest number in list
        lowest_number = min(numbers_search)

        # get highest number in list
        highest_number = max(numbers_search) if len(numbers_search) > 1 else None

        # discard any numbers in between the lowest and highest number
        numbers = [lowest_number]
        if highest_number:
            numbers.append(highest_number)

    # return the resulting list of numbers
    return numbers


def contains_non_numeric(input_string):
    try:
        # Try converting the string to a float
        float_value = float(input_string)

        # If successful, return False
        return False
    except ValueError:
        # If conversion to float fails, check if it's an integer
        return not input_string.isdigit()


# Pre-compiled chapter-keyword search for get_release_number()
chapter_number_search_pattern = re.compile(
    r"((%s)(\.)?(\s+)?(#)?(([0-9]+)(([-_.])([0-9]+)|)+))$" % exclusion_keywords_joined,
    flags=re.IGNORECASE,
)

# Pre-compiled volume-keyword search for get_release_number()
volume_number_search_pattern = re.compile(
    r"\b({})((\.)|)(\s+)?([0-9]+)(([-_.])([0-9]+)|)+\b".format(volume_regex_keywords),
    re.IGNORECASE,
)


# Finds the volume/chapter number(s) in the file name.
@lru_cache(maxsize=None)
def get_release_number(file, chapter=False):

    # Cleans up the chapter's series name
    def clean_series_name(name):
        # Removes starting period
        # EX: "series_name. 031 (2023).cbz" -> "'. 031 (2023)"" -> "031 (2023)"
        if "." in name:
            name = re.sub(r"^\s*(\.)", "", name, re.IGNORECASE).strip()

        # Remove any subtitle
        # EX: "series_name 179.1 - Epilogue 01 (2023) (Digital) (release_group).cbz" ->
        # "" 179.1 - Epilogue 01"  -> "179.1"
        if ("-" in name or ":" in name) and re.search(r"(^\d+)", name.strip()):
            name = re.sub(r"((\s+(-)|:)\s+).*$", "", name, re.IGNORECASE).strip()

        # Removes # from the number
        # EX: #001 -> 001
        if "#" in name:
            name = re.sub(r"($#)", "", name, re.IGNORECASE).strip()

            # Removes # from bewteen the numbers
            # EX: 154#3 -> 154
            if re.search(r"(\d+#\d+)", name):
                name = re.sub(r"((#)([0-9]+)(([-_.])([0-9]+)|)+)", "", name).strip()

        # removes part from chapter number
        # EX: 053x1 or c053x1 -> 053 or c053
        if "x" in name:
            name = re.sub(r"(x[0-9]+)", "", name, re.IGNORECASE).strip()

        # removes the bracketed info from the end of the string, empty or not
        if contains_brackets(name):
            name = remove_brackets(name).strip()

        # Removes the - characters.extension from the end of the string, with
        # the dash and characters being optional
        # EX:  - prologue.extension or .extension
        name = re.sub(
            r"(((\s+)?-(\s+)?([A-Za-z]+))?(%s))" % file_extensions_regex,
            "",
            name,
            re.IGNORECASE,
        ).strip()

        if "-" in name:
            # - #404 - -> #404
            if name.startswith("- "):
                name = name[1:].strip()
            if name.endswith(" -"):
                name = name[:-1].strip()

        # remove # at the beginning of the string
        # EX: #001 -> 001
        if name.startswith("#"):
            name = name[1:].strip()

        return name

    results = []
    is_multi_volume = False
    keywords = volume_regex_keywords if not chapter else chapter_regex_keywords
    result = None

    # Replace _extra
    file = remove_dual_space(file.replace("_extra", ".5")).strip()

    # Replace underscores
    file = replace_underscores(file) if "_" in file else file

    is_multi_volume = (
        check_for_multi_volume_file(file, chapter=chapter) if "-" in file else False
    )

    if not chapter:  # Search for a volume number
        result = volume_number_search_pattern.search(file)
    else:  # Prep for a chapter search
        if has_multiple_numbers(file):
            extension_less_file = get_extensionless_name(file)

            if chapter_number_search_pattern.search(extension_less_file):
                file = chapter_number_search_pattern.sub("", extension_less_file)

                # remove - at the end of the string
                if file.endswith("-") and not re.search(
                    r"-(\s+)?(#)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(\s+)?-", file
                ):
                    file = file[:-1].strip()

        # Search for a chapter match
        result = next(
            (
                r
                for pattern in chapter_search_patterns_comp
                if (r := pattern.search(file))
            ),
            None,
        )

    if result:
        try:
            file = result.group().strip() if hasattr(result, "group") else ""

            # Clean the series name
            if chapter:
                file = clean_series_name(file)

            # Remove volume/chapter keywords from the file name
            if contains_non_numeric(file):
                file = re.sub(
                    r"\b({})(\.|)([-_. ])?".format(keywords),
                    "",
                    file,
                    flags=re.IGNORECASE,
                ).strip()

                if contains_non_numeric(file) and re.search(
                    r"\b[0-9]+({})[0-9]+\b".format(keywords),
                    file,
                    re.IGNORECASE,
                ):
                    file = (
                        re.sub(
                            r"({})".format(keywords),
                            ".",
                            file,
                            flags=re.IGNORECASE,
                        )
                    ).strip()

            try:
                if is_multi_volume or (
                    ("-" in file or "_" in file)
                    and re.search(
                        r"([0-9]+(\.[0-9]+)?)([-_]([0-9]+(\.[0-9]+)?))+", file
                    )
                ):
                    if not is_multi_volume:
                        is_multi_volume = True

                    multi_numbers = get_min_and_max_numbers(file)
                    if multi_numbers:
                        results.extend(
                            (
                                int(volume_number)
                                if float(volume_number).is_integer()
                                else float(volume_number)
                            )
                            for volume_number in multi_numbers
                        )
                        if len(multi_numbers) == 1:
                            is_multi_volume = False
                else:
                    # Remove trailing ".0" so conversion doesn't fail
                    if file.endswith("0") and ".0" in file:
                        file = file.split(".0")[0]
                    results = int(file) if float(file).is_integer() else float(file)

            except ValueError as v:
                send_message(f"Not a float: {file}: ERROR: {v}", error=True)
        except AttributeError:
            send_message(str(AttributeError.with_traceback), error=True)

    if results or results == 0:
        if is_multi_volume:
            return tuple(results)
        elif chapter:
            return results
        elif results < 2000:
            return results

    return ""


# Allows get_release_number() to use a cache
def get_release_number_cache(file, chapter=False):
    result = get_release_number(file, chapter=chapter)
    return list(result) if isinstance(result, tuple) else result


# Get the release year from the file metadata, if present, otherwise from the file name
def get_release_year(name, metadata=None):
    result = None

    match = re.search(volume_year_regex, name, re.IGNORECASE)
    if match:
        result = int(re.sub(r"(\(|\[|\{)|(\)|\]|\})", "", match.group()))

    if not result and metadata:
        release_year_from_file = None

        if "Summary" in metadata and "Year" in metadata:
            release_year_from_file = metadata["Year"]
        elif "dc:description" in metadata and "dc:date" in metadata:
            release_year_from_file = metadata["dc:date"].strip()
            release_year_from_file = re.search(r"\d{4}", release_year_from_file)
            release_year_from_file = (
                release_year_from_file.group() if release_year_from_file else None
            )

        if release_year_from_file and release_year_from_file.isdigit():
            result = int(release_year_from_file)
            if result < 1000:
                result = None

    return result


# Pre-compiled publisher regex
publishers_joined_regex = ""

# Pre-compile release group regex
release_groups_joined_regex = ""

# Pre-compiled regex for the release group at the end of the file name
release_group_end_regex = re.compile(
    r"-(?! )([^\(\)\[\]\{\}]+)(?:%s)$" % file_extensions_regex, re.IGNORECASE
)


# Retrieves the release_group on the file name
def get_extra_from_group(name, groups, publisher_m=False, release_group_m=False):
    if (
        not groups
        or (publisher_m and not publishers_joined)
        or (release_group_m and not release_groups_joined)
    ):
        return ""

    search = ""

    if publisher_m and publishers_joined_regex and contains_brackets(name):
        search = publishers_joined_regex.search(name)
        if search:
            search = search.group()

    elif release_group_m:
        search = release_group_end_regex.search(name) if "-" in name else ""

        if search:
            search = search.group(1)

        if not search and release_groups_joined_regex and contains_brackets(name):
            search = release_groups_joined_regex.findall(name)
            if search:
                search = search[-1]  # use the last element

    return search if search else ""


# Precompile the regular expressions
rx_remove = re.compile(
    r".*(%s)([-_. ]|)([-_. ]|)([0-9]+)(\b|\s)" % volume_regex_keywords,
    re.IGNORECASE,
)
rx_search_part = re.compile(r"(\b(Part)([-_. ]|)([0-9]+)\b)", re.IGNORECASE)
rx_search_chapters = re.compile(
    r"([0-9]+)(([-_.])([0-9]+)|)+((x|#)([0-9]+)(([-_.])([0-9]+)|)+)", re.IGNORECASE
)
rx_remove_x_hash = re.compile(r"((x|#))", re.IGNORECASE)


# Retrieves and returns the file part from the file name
@lru_cache(maxsize=None)
def get_file_part(file, chapter=False, series_name=None, subtitle=None):
    result = ""

    contains_keyword = (
        re.search(r"\bpart\b", file, re.IGNORECASE) if "part" in file.lower() else ""
    )
    contains_indicator = "#" in file or "x" in file

    if not contains_keyword and not contains_indicator:
        return result

    if series_name:
        # remove it from the file name
        file = re.sub(re.escape(series_name), "", file, flags=re.IGNORECASE).strip()
    if subtitle:
        # remove it from the file name
        file = re.sub(re.escape(subtitle), "", file, flags=re.IGNORECASE).strip()

    if not chapter:
        if contains_keyword:
            # Remove the matched string from the input file name
            file = rx_remove.sub("", file).strip()
            search = rx_search_part.search(file)
            if search:
                result = search.group(1)
                result = re.sub(
                    r"Part([-_. ]|)+", " ", result, flags=re.IGNORECASE
                ).strip()
    else:
        if contains_indicator:
            search = rx_search_chapters.search(file)
            if search:
                part_search = re.search(
                    r"((x|#)([0-9]+)(([-_.])([0-9]+)|)+)", search.group(), re.IGNORECASE
                )
                if part_search:
                    # remove the x or # from the string
                    result = rx_remove_x_hash.sub("", part_search.group())

    # Set the number as float or int
    result = set_num_as_float_or_int(result)

    return result


# Retrieves the publisher from the passed in metadata
def get_publisher_from_meta(metadata):
    # Cleans the publisher name
    def clean_publisher_name(name):
        name = titlecase(name)
        name = remove_dual_space(name)
        if "llc" in name.lower():
            name = re.sub(r", LLC.*", "", name, flags=re.IGNORECASE).strip()
        return name

    publisher = None

    if metadata:
        if "Publisher" in metadata:
            publisher = clean_publisher_name(metadata["Publisher"])
        elif "dc:publisher" in metadata:
            publisher = clean_publisher_name(metadata["dc:publisher"])
            publisher = publisher.replace("LLC", "").strip()
            publisher = publisher.replace(":", " - ").strip()
            publisher = remove_dual_space(publisher)

    return publisher


# Trades out our regular files for file objects
def upgrade_to_volume_class(
    files,
    skip_release_year=False,
    skip_file_part=False,
    skip_release_group=False,
    skip_extras=False,
    skip_publisher=False,
    skip_premium_content=False,
    skip_subtitle=False,
    skip_multi_volume=False,
    test_mode=False,
):
    if not files:
        return []

    if test_mode:
        skip_release_year = True
        skip_publisher = True
        skip_premium_content = True

    results = []
    for file in files:
        internal_metadata = None
        publisher = Publisher(None, None)

        if (not skip_release_year or not skip_publisher) and file.file_type == "volume":
            internal_metadata = get_internal_metadata(file.path, file.extension)

        if add_publisher_name_to_file_name_when_renaming:
            if internal_metadata and not skip_publisher:
                publisher.from_meta = get_publisher_from_meta(internal_metadata)
            if publishers:
                publisher.from_name = get_extra_from_group(
                    file.name, publishers, publisher_m=True
                )

        file_obj = Volume(
            file.file_type,
            file.basename,
            get_shortened_title(file.basename),
            (
                get_release_year(file.name, internal_metadata)
                if not skip_release_year
                else None
            ),
            file.volume_number,
            "",
            "",
            (
                get_extra_from_group(file.name, release_groups, release_group_m=True)
                if not skip_release_group
                else ""
            ),
            file.name,
            file.extensionless_name,
            file.basename,
            file.extension,
            file.root,
            file.path,
            file.extensionless_path,
            [],
            publisher,
            (
                check_for_premium_content(file.path, file.extension)
                if not skip_premium_content and search_and_add_premium_to_file_name
                else False
            ),
            None,
            file.header_extension,
            (
                (
                    check_for_multi_volume_file(
                        file.name,
                        chapter=file.file_type == "chapter",
                    )
                )
                if not skip_multi_volume and "-" in file.name
                else False
            ),
            (
                is_one_shot(file.name, file.root, test_mode=test_mode)
                if file.file_type != "chapter"
                else False
            ),
        )

        if not skip_subtitle:
            file_obj.subtitle = get_subtitle_from_title(
                file_obj, publisher=file_obj.publisher
            )

        if not skip_file_part:
            file_obj.volume_part = get_file_part(
                file_obj.name,
                series_name=file_obj.series_name,
                subtitle=file_obj.subtitle,
                chapter=file_obj.file_type == "chapter",
            )

        if not skip_extras:
            file_obj.extras = get_extras(
                file_obj.name,
                chapter=file_obj.file_type == "chapter",
                series_name=file_obj.series_name,
                subtitle=file_obj.subtitle,
            )

        if file_obj.is_one_shot:
            file_obj.volume_number = 1

        if file_obj.volume_number != "":
            if (
                file_obj.volume_part != ""
                and not isinstance(file_obj.volume_number, list)
                and int(file_obj.volume_number) == file_obj.volume_number
            ):
                file_obj.index_number = file_obj.volume_number + (
                    file_obj.volume_part / 10
                )
            else:
                file_obj.index_number = file_obj.volume_number

        results.append(file_obj)
    return results


# The RankedKeywordResult class is a container for the total score and the keywords
class RankedKeywordResult:
    def __init__(self, total_score, keywords):
        self.total_score = total_score
        self.keywords = keywords

    # to string
    def __str__(self):
        return f"Total Score: {self.total_score}\nKeywords: {self.keywords}"

    def __repr__(self):
        return str(self)


compiled_searches = [
    re.compile(keyword.name, re.IGNORECASE) for keyword in ranked_keywords
]


# Retrieves the ranked keyword score and matching tags
# for the passed releases.
def get_keyword_scores(releases):
    results = []

    for release in releases:
        tags, score = [], 0.0

        for idx, (keyword, compiled_search) in enumerate(
            zip(ranked_keywords, compiled_searches)
        ):
            if keyword.file_type in ["both", release.file_type]:
                search = compiled_search.search(release.name)
                if search:
                    tags.append(Keyword(search.group(), keyword.score))
                    score += keyword.score

        results.append(RankedKeywordResult(score, tags))

    return results


# > This class represents the result of an upgrade check
class UpgradeResult:
    def __init__(self, is_upgrade, downloaded_ranked_result, current_ranked_result):
        self.is_upgrade = is_upgrade
        self.downloaded_ranked_result = downloaded_ranked_result
        self.current_ranked_result = current_ranked_result

    # to string
    def __str__(self):
        return f"Is Upgrade: {self.is_upgrade}\nDownloaded Ranked Result: {self.downloaded_ranked_result}\nCurrent Ranked Result: {self.current_ranked_result}"

    def __repr__(self):
        return str(self)


# Checks if the downloaded release is an upgrade for the current release.
def is_upgradeable(downloaded_release, current_release):
    downloaded_release_result = None
    current_release_result = None

    if downloaded_release.name.lower() == current_release.name.lower():
        results = get_keyword_scores([downloaded_release])
        downloaded_release_result, current_release_result = results[0], results[0]
    else:
        results = get_keyword_scores([downloaded_release, current_release])
        downloaded_release_result, current_release_result = results[0], results[1]

    upgrade_result = UpgradeResult(
        downloaded_release_result.total_score > current_release_result.total_score,
        downloaded_release_result,
        current_release_result,
    )
    return upgrade_result


# Deletes hidden files, used when checking if a folder is empty.
def delete_hidden_files(files, root):
    for file in files:
        path = os.path.join(root, file)
        if (str(file)).startswith(".") and os.path.isfile(path):
            remove_file(path, silent=True)


# Removes the old series and cover image
def remove_images(path):
    # The volume cover for the file. (file_name.image_extension)
    volume_cover = next(
        (
            get_extensionless_name(path) + extension
            for extension in image_extensions
            if os.path.isfile(get_extensionless_name(path) + extension)
        ),
        "",
    )

    # The series cover for the file. (cover.ext)
    series_cover = next(
        (
            os.path.join(os.path.dirname(path), f"cover{ext}")
            for ext in image_extensions
            if os.path.isfile(os.path.join(os.path.dirname(path), f"cover{ext}"))
        ),
        None,
    )

    # Remove the series cover if it exists and matches
    if series_cover and os.path.isfile(series_cover):
        if not use_latest_volume_cover_as_series_cover and is_volume_one(
            os.path.basename(path)
        ):
            remove_file(series_cover, silent=True)
        elif (
            use_latest_volume_cover_as_series_cover
            and volume_cover
            and os.path.isfile(volume_cover)
            and get_modification_date(series_cover)
            == get_modification_date(volume_cover)
            and get_file_hash(series_cover) == get_file_hash(volume_cover)
        ):
            remove_file(series_cover, silent=True)

    # Remove the volume cover if it exists
    if volume_cover and os.path.isfile(volume_cover):
        remove_file(volume_cover, silent=True)


# Handles adding our embed to the list of grouped notifications
# If the list is at the limit, it will send the list and clear it
# Also handles setting the timestamp on the embed of when it was added
def group_notification(notifications, embed, passed_webhook=None):
    failed_attempts = 0

    if len(notifications) >= discord_embed_limit:
        while notifications:
            message_status = send_discord_message(
                None, notifications, passed_webhook=passed_webhook
            )
            if (
                message_status
                or (failed_attempts >= len(discord_webhook_url) and not passed_webhook)
                or (passed_webhook and failed_attempts >= 1)
            ):
                notifications = []
            else:
                failed_attempts += 1

    # Set timestamp on embed
    embed.embed.set_timestamp()

    # Add embed to list
    if embed not in notifications:
        notifications.append(embed)

    return notifications


# Removes the specified folder and all of its contents.
def remove_folder(folder):
    result = False
    if os.path.isdir(folder) and (folder not in download_folders + paths):
        try:
            shutil.rmtree(folder)
            if not os.path.isdir(folder):
                send_message(f"\t\t\tRemoved {folder}", discord=False)
                result = True
            else:
                send_message(f"\t\t\tFailed to remove {folder}", error=True)
        except Exception as e:
            send_message(f"\t\t\tFailed to remove {folder}: {str(e)}", error=True)
            return result
    return result


# Removes a file and its associated image files.
def remove_file(full_file_path, silent=False):
    global grouped_notifications

    # Check if the file exists
    if not os.path.isfile(full_file_path):
        # Send an error message if the file doesn't exist
        send_message(f"{full_file_path} is not a file.", error=True)
        return False

    try:
        # Try to remove the file
        os.remove(full_file_path)
    except OSError as e:
        # Send an error message if removing the file failed
        send_message(f"Failed to remove {full_file_path}: {e}", error=True)
        return False

    # Check if the file was successfully removed
    if os.path.isfile(full_file_path):
        # Send an error message if the file still exists
        send_message(f"Failed to remove {full_file_path}.", error=True)
        return False

    if not silent:
        # Send a notification that the file was removed
        send_message(f"File removed: {full_file_path}", discord=False)

        # Create a Discord embed
        embed = handle_fields(
            DiscordEmbed(
                title="Removed File",
                color=red_color,
            ),
            fields=[
                {
                    "name": "File",
                    "value": f"```{os.path.basename(full_file_path)}```",
                    "inline": False,
                },
                {
                    "name": "Location",
                    "value": f"```{os.path.dirname(full_file_path)}```",
                    "inline": False,
                },
            ],
        )

        # Add it to the group of notifications
        grouped_notifications = group_notification(
            grouped_notifications, Embed(embed, None)
        )

    # If the file is not an image, remove associated images
    if get_file_extension(full_file_path) not in image_extensions:
        remove_images(full_file_path)

    return True


# Move a file
def move_file(
    file,
    new_location,
    silent=False,
    highest_index_num="",
    is_chapter_dir=False,
):
    global grouped_notifications

    try:
        if os.path.isfile(file.path):
            shutil.move(file.path, new_location)
            if os.path.isfile(os.path.join(new_location, file.name)):
                if not silent:
                    send_message(
                        f"\t\tMoved File: {file.name} to {new_location}",
                        discord=False,
                    )
                    embed = handle_fields(
                        DiscordEmbed(
                            title="Moved File",
                            color=grey_color,
                        ),
                        fields=[
                            {
                                "name": "File",
                                "value": f"```{file.name}```",
                                "inline": False,
                            },
                            {
                                "name": "To",
                                "value": f"```{new_location}```",
                                "inline": False,
                            },
                        ],
                    )
                    grouped_notifications = group_notification(
                        grouped_notifications, Embed(embed, None)
                    )
                move_images(
                    file,
                    new_location,
                    highest_index_num=highest_index_num,
                    is_chapter_dir=is_chapter_dir,
                )
                return True
            else:
                send_message(
                    f"\t\tFailed to move: {os.path.join(file.root, file.name)} to: {new_location}",
                    error=True,
                )
                return False
    except OSError as e:
        send_message(str(e), error=True)
        return False


# Replaces an old file.
def replace_file(old_file, new_file, highest_index_num=""):
    global grouped_notifications
    result = False

    try:
        if os.path.isfile(old_file.path) and os.path.isfile(new_file.path):
            file_removal_status = remove_file(old_file.path)
            if not os.path.isfile(old_file.path) and file_removal_status:
                move_file(
                    new_file,
                    old_file.root,
                    silent=True,
                    highest_index_num=highest_index_num,
                )
                if os.path.isfile(os.path.join(old_file.root, new_file.name)):
                    result = True
                    send_message(
                        f"\t\tFile: {new_file.name} was moved to: {old_file.root}",
                        discord=False,
                    )
                    embed = handle_fields(
                        DiscordEmbed(
                            title="Moved File",
                            color=grey_color,
                        ),
                        fields=[
                            {
                                "name": "File",
                                "value": f"```{new_file.name}```",
                                "inline": False,
                            },
                            {
                                "name": "To",
                                "value": f"```{old_file.root}```",
                                "inline": False,
                            },
                        ],
                    )
                    grouped_notifications = group_notification(
                        grouped_notifications, Embed(embed, None)
                    )
                else:
                    send_message(
                        f"\tFailed to replace: {old_file.name} with: {new_file.name}",
                        error=True,
                    )
            else:
                send_message(
                    f"\tFailed to remove old file: {old_file.name}\nUpgrade aborted.",
                    error=True,
                )
        else:
            send_message(
                f"\tOne of the files is missing, failed to replace.\n{old_file.path}{new_file.path}",
                error=True,
            )
    except Exception as e:
        send_message(f"Failed file replacement.\nERROR: {e}", error=True)
    return result


# Executes a command and prints the output to the console.
def execute_command(command):
    process = None
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        while True:
            output = process.stdout.readline()
            if output == b"" and process.poll() is not None:
                break
            if output:
                sys.stdout.buffer.write(output)
                sys.stdout.flush()
    except Exception as e:
        send_message(str(e), error=True)
    return process


# Removes the duplicate after determining it's upgrade status, otherwise, it upgrades
def remove_duplicate_releases(
    original_releases, downloaded_releases, image_similarity_match=False
):
    global moved_files, grouped_notifications

    # Extracts and formats file tags information
    def get_file_tags_info(result):
        tags = result.keywords
        if tags:
            return ", ".join([f"{tag.name} ({tag.score})" for tag in tags])
        return "None"

    # Retrieves and formats file size information in MB
    def get_file_size_info(path):
        if os.path.isfile(path):
            size = os.path.getsize(path) / 1000000  # convert to MB
            return f"{round(size, 1)} MB"
        return None

    new_original_releases = original_releases.copy()
    new_downloaded_releases = downloaded_releases.copy()

    for download in downloaded_releases:
        if download.index_number == "":
            send_message(
                f"\n\t\t{download.file_type.capitalize()} number empty/missing in: {download.name}",
                error=True,
            )
            continue

        chap_dl_percent = get_folder_type(downloaded_releases, file_type="chapter")
        is_chapter_dir = chap_dl_percent >= required_matching_percentage

        highest_index_num = (
            get_highest_release(
                tuple(
                    [
                        (
                            item.index_number
                            if not isinstance(item.index_number, list)
                            else tuple(item.index_number)
                        )
                        for item in new_downloaded_releases + new_original_releases
                    ]
                ),
                is_chapter_directory=is_chapter_dir,
            )
            if not is_chapter_dir
            else ""
        )

        for original in original_releases:
            if not os.path.isfile(download.path):
                break

            if not os.path.isfile(original.path):
                continue

            if download.file_type != original.file_type:
                continue

            if not (
                is_same_index_number(download.index_number, original.index_number)
                or (
                    image_similarity_match
                    and hasattr(image_similarity_match, "name")
                    and image_similarity_match.name == original.name
                )
            ):
                continue

            upgrade_status = is_upgradeable(download, original)

            original_file_tags = get_file_tags_info(
                upgrade_status.current_ranked_result
            )
            downloaded_file_tags = get_file_tags_info(
                upgrade_status.downloaded_ranked_result
            )

            original_file_size = get_file_size_info(original.path)
            downloaded_file_size = get_file_size_info(download.path)

            fields = [
                {
                    "name": "From",
                    "value": f"```{original.name}```",
                    "inline": False,
                },
                {
                    "name": "Score",
                    "value": str(upgrade_status.current_ranked_result.total_score),
                    "inline": True,
                },
                {
                    "name": "Tags",
                    "value": str(original_file_tags),
                    "inline": True,
                },
                {
                    "name": "To",
                    "value": f"```{download.name}```",
                    "inline": False,
                },
                {
                    "name": "Score",
                    "value": str(upgrade_status.downloaded_ranked_result.total_score),
                    "inline": True,
                },
                {
                    "name": "Tags",
                    "value": str(downloaded_file_tags),
                    "inline": True,
                },
            ]

            if original_file_size and downloaded_file_size:
                # insert original file size at index 3
                fields.insert(
                    3,
                    {
                        "name": "Size",
                        "value": str(original_file_size),
                        "inline": True,
                    },
                )
                # append downloaded file size at the end
                fields.append(
                    {
                        "name": "Size",
                        "value": str(downloaded_file_size),
                        "inline": True,
                    }
                )

            status = "Not Upgradeable" if not upgrade_status.is_upgrade else "Upgrade"
            verb = "not an" if not upgrade_status.is_upgrade else "an"
            action = "Deleting" if not upgrade_status.is_upgrade else "Upgrading"
            color = yellow_color if not upgrade_status.is_upgrade else green_color

            send_message(
                f"\t\t{status}: {download.name} is {verb} upgrade to: {original.name}\n\t{action}: {download.name} from download folder.",
                discord=False,
            )

            embed = handle_fields(
                DiscordEmbed(
                    title=f"Upgrade Process ({status})",
                    color=color,
                ),
                fields=fields,
            )
            grouped_notifications = group_notification(
                grouped_notifications, Embed(embed, None)
            )

            if upgrade_status.is_upgrade:
                if download.multi_volume and not original.multi_volume:
                    files_to_remove = [
                        original_volume
                        for original_volume in original_releases
                        for volume_number in download.volume_number
                        if (
                            volume_number != original.volume_number
                            and original_volume.volume_number == volume_number
                            and original_volume.volume_part == original.volume_part
                        )
                    ]

                    # Remove the files
                    for file in files_to_remove:
                        remove_file(file.path)
                        if file in new_original_releases:
                            new_original_releases.remove(file)

                replace_file_status = replace_file(
                    original,
                    download,
                    highest_index_num=highest_index_num,
                )

                if replace_file_status:
                    # append the new path to moved_files
                    moved_files.append(os.path.join(original.root, download.name))
                    if download in new_downloaded_releases:
                        new_downloaded_releases.remove(download)
                break
            else:
                # Additional logic for non-upgrade case
                remove_file(download.path)
                if download in new_downloaded_releases:
                    new_downloaded_releases.remove(download)
                break

    return new_original_releases, new_downloaded_releases


# Checks if the given folder is empty and deletes it if it meets the conditions.
def check_and_delete_empty_folder(folder):
    # Check if the folder exists
    if not os.path.exists(folder):
        return

    try:
        print(f"\t\tChecking for empty folder: {folder}")

        # List the contents of the folder
        folder_contents = os.listdir(folder)

        # Delete hidden files in the folder
        delete_hidden_files(folder_contents, folder)

        # Check if the folder contains subfolders
        contains_subfolders = any(
            os.path.isdir(os.path.join(folder, item)) for item in folder_contents
        )

        # If it contains subfolders, exit
        if contains_subfolders:
            return

        # Remove hidden files from the list
        folder_contents = remove_hidden_files(folder_contents)

        # Check if there is only one file starting with "cover."
        if len(folder_contents) == 1 and folder_contents[0].startswith("cover."):
            cover_file_path = os.path.join(folder, folder_contents[0])

            # Remove the "cover." file
            remove_file(cover_file_path, silent=True)

            # Update the folder contents
            folder_contents = os.listdir(folder)
            folder_contents = remove_hidden_files(folder_contents)

        # Check if the folder is now empty and not in certain predefined paths
        if len(folder_contents) == 0 and folder not in paths + download_folders:
            try:
                print(f"\t\tRemoving empty folder: {folder}")
                os.rmdir(folder)

                if not os.path.exists(folder):
                    print(f"\t\t\tFolder removed: {folder}")
                else:
                    print(f"\t\t\tFailed to remove folder: {folder}")
            except OSError as e:
                send_message(str(e), error=True)
    except Exception as e:
        send_message(str(e), error=True)


# Writes a log file
def write_to_file(
    file,
    message,
    without_timestamp=False,
    overwrite=False,
    check_for_dup=False,
    write_to=None,
    can_write_log=log_to_file,
):
    write_status = False
    logs_dir_loc = write_to or LOGS_DIR

    # check if the logs directory exists, if not create it
    if not os.path.exists(logs_dir_loc):
        try:
            os.makedirs(logs_dir_loc)
        except OSError as e:
            send_message(str(e), error=True)
            return False

    if can_write_log and logs_dir_loc:
        # get rid of formatting
        message = re.sub("\t|\n", "", str(message), flags=re.IGNORECASE).strip()
        contains = False

        # check if it already contains the message
        log_file_path = os.path.join(logs_dir_loc, file)

        if check_for_dup and os.path.isfile(log_file_path):
            contains = check_text_file_for_message(log_file_path, message)

        if not contains or overwrite:
            try:
                append_write = (
                    "a" if os.path.exists(log_file_path) and not overwrite else "w"
                )
                try:
                    now = datetime.now()
                    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

                    with open(log_file_path, append_write) as f:
                        if without_timestamp:
                            f.write(f"\n {message}")
                        else:
                            f.write(f"\n{dt_string} {message}")
                    write_status = True

                except Exception as e:
                    send_message(str(e), error=True, log=False)
            except Exception as e:
                send_message(str(e), error=True, log=False)
    return write_status


# Checks for any missing volumes between the lowest volume of a series and the highest volume.
def check_for_missing_volumes():
    print("\nChecking for missing volumes...")

    if not paths:
        print("\tNo paths found.")
        return

    for path in paths:
        if not os.path.exists(path) or path in download_folders:
            continue

        os.chdir(path)

        folders = get_all_folders_recursively_in_dir(path)

        for folder in folders:
            root = folder["root"]
            dirs = folder["dirs"]
            files = folder["files"]

            # Clean and sort the existing directory.
            filtered_files = clean_and_sort(root, files, chapters=False)[0]

            # Skip if the existing directory is empty.
            if not filtered_files:
                continue

            # Upgrade the existing directory to a list of Volume objects.
            volumes = upgrade_to_volume_class(
                upgrade_to_file_class(
                    [
                        f
                        for f in filtered_files
                        if os.path.isfile(os.path.join(root, f))
                    ],
                    root,
                ),
                skip_release_year=True,
                skip_release_group=True,
                skip_extras=True,
                skip_publisher=True,
                skip_premium_content=True,
                skip_subtitle=True,
            )

            # Filter out volumes that don't have a valid volume number.
            volumes = [
                volume
                for volume in volumes
                if isinstance(volume.volume_number, (int, float, list))
            ]

            # Skip if there are less than 2 volumes in the directory.
            if len(volumes) < 2:
                continue

            # Extract volume numbers from the existing volumes.
            volume_numbers = {
                num
                for volume in volumes
                for num in (
                    range(
                        int(min(volume.volume_number)),
                        int(max(volume.volume_number)) + 1,
                    )
                    if isinstance(volume.volume_number, list)
                    else [volume.volume_number]
                )
                if num != ""
            }

            # Sort and remove duplicate volume numbers.
            volume_numbers_second = sorted(volume_numbers)

            if len(volume_numbers_second) < 2:
                continue

            # Get the lowest and highest volume numbers.
            lowest_volume_number = 1
            highest_volume_number = int(max(volume_numbers_second))

            # Create a range of volume numbers between the lowest and highest.
            volume_num_range = [
                num
                for num in range(lowest_volume_number, highest_volume_number + 1)
                if num not in volume_numbers_second
            ]

            if not volume_num_range:
                continue

            print(f"\t{root}")

            for number in volume_num_range:
                print(f"\t\tVolume {number}")


# Renames the file.
def rename_file(src, dest, silent=False):
    result = False
    if os.path.isfile(src):
        root = os.path.dirname(src)
        if not silent:
            print(f"\n\t\tRenaming {src}")
        try:
            os.rename(src, dest)
        except Exception as e:
            send_message(
                f"Failed to rename {os.path.basename(src)} to {os.path.basename(dest)}\n\tERROR: {e}",
                error=True,
            )
            return result
        if os.path.isfile(dest):
            result = True
            if not silent:
                send_message(
                    f"\n\t\t{os.path.basename(src)} was renamed to {os.path.basename(dest)}",
                    discord=False,
                )
            if get_file_extension(src) not in image_extensions:
                extensionless_filename_src = get_extensionless_name(src)
                extensionless_filename_dst = get_extensionless_name(dest)
                for image_extension in image_extensions:
                    image_file = extensionless_filename_src + image_extension
                    image_file_rename = extensionless_filename_dst + image_extension
                    if os.path.isfile(image_file):
                        try:
                            rename_file(image_file, image_file_rename, silent=True)
                        except Exception as e:
                            send_message(str(e), error=True)
        else:
            send_message(
                f"Failed to rename {src} to {dest}\n\tERROR: {e}",
                error=True,
            )
    else:
        send_message(f"File {src} does not exist. Skipping rename.", discord=False)
    return result


# Renames the folder
def rename_folder(src, dest):
    result = None
    if os.path.isdir(src):
        if not os.path.isdir(dest):
            try:
                os.rename(src, dest)
            except Exception as e:
                send_message(str(e), error=True)
            if os.path.isdir(dest):
                send_message(
                    f"\n\t\t{os.path.basename(src)} was renamed to {os.path.basename(dest)}\n",
                    discord=False,
                )
                result = dest
            else:
                send_message(
                    f"Failed to rename {src} to {dest}\n\tERROR: {e}",
                    error=True,
                )
        else:
            send_message(
                f"Folder {dest} already exists. Skipping rename.", discord=False
            )
    else:
        send_message(f"Folder {src} does not exist. Skipping rename.", discord=False)
    return result


# Gets the user input and checks if it is valid
def get_input_from_user(
    prompt, acceptable_values=[], example=None, timeout=90, use_timeout=False
):
    # Function that gets user input and stores it in the shared_variable
    def input_with_timeout(prompt, shared_variable):
        while not shared_variable.get("done"):
            user_input = input(prompt)
            if user_input and (
                not acceptable_values or user_input in acceptable_values
            ):
                shared_variable["done"] = True
                shared_variable["input"] = user_input

    # Format the prompt with example values if provided
    if example:
        if isinstance(example, list):
            example = f" or ".join(
                [f"{example_item}" for example_item in example[:-1]]
                + [f"{example[-1]}"]
            )
        else:
            example = str(example)
        prompt = f"{prompt} ({example}): "
    else:
        prompt = f"{prompt}: "

    # Create a shared variable to store the user input between threads
    shared_variable = {"input": None, "done": False}

    if use_timeout:
        # Create a timer that sets the 'done' flag in shared_variable when it expires
        timer = threading.Timer(timeout, lambda: shared_variable.update({"done": True}))

    # Create a thread to get the user input using the input_with_timeout function
    input_thread = threading.Thread(
        target=input_with_timeout, args=(prompt, shared_variable)
    )

    # Start the input thread and the timer (if use_timeout is True)
    input_thread.start()
    if use_timeout:
        timer.start()

    while not shared_variable["done"]:
        # Wait for the input thread to finish or timeout, whichever comes first (if use_timeout is True)
        input_thread.join(1)

        if use_timeout and not timer.is_alive():
            break

    if use_timeout:
        timer.cancel()

    return shared_variable["input"] if shared_variable["done"] else None


# Retrieves the internally stored metadata from the file.
# Retrieves the internal metadata from the file based on its extension.
def get_internal_metadata(file_path, extension):
    metadata = None
    try:
        if extension in manga_extensions:
            if contains_comic_info(file_path):
                comicinfo = get_file_from_zip(
                    file_path, ["comicinfo.xml"], ".xml", allow_base=False
                )
                if comicinfo:
                    comicinfo = comicinfo.decode("utf-8")
                    metadata = parse_comicinfo_xml(comicinfo)
        elif extension in novel_extensions:
            regex_searches = [
                r"content.opf",
                r"package.opf",
                r"standard.opf",
                r"volume.opf",
                r"metadata.opf",
                r"978.*.opf",
            ]
            opf = get_file_from_zip(file_path, regex_searches, ".opf")
            if opf:
                metadata = parse_html_tags(opf)
            if not metadata:
                send_message(
                    f"No opf file found in {file_path}. Skipping metadata retrieval.",
                    discord=False,
                )
    except Exception as e:
        send_message(
            f"Failed to retrieve metadata from {file_path}\nERROR: {e}", error=True
        )
    return metadata


# Checks if the epub file contains any premium content.
def check_for_premium_content(file_path, extension):
    result = False
    if extension in novel_extensions:
        if re.search(r"\bPremium\b", os.path.basename(file_path), re.IGNORECASE):
            result = True
        elif is_premium_volume(file_path):
            result = True
    return result


# Determines if the string contains unicode characters.
# or rather non-ascii characters.
def contains_unicode(input_str):
    return not input_str.isascii()


# Rebuilds the file name by cleaning up, adding, and moving some parts around.
def reorganize_and_rename(files, dir):
    global transferred_files, grouped_notifications

    modifiers = {
        ext: (
            "[%s]"
            if ext in novel_extensions
            else "(%s)" if ext in manga_extensions else ""
        )
        for ext in file_extensions
    }
    base_dir = os.path.basename(dir)

    for file in files[:]:
        try:
            keywords, preferred_naming_format, zfill_int, zfill_float = (
                (
                    chapter_regex_keywords,
                    preferred_chapter_renaming_format,
                    zfill_chapter_int_value,
                    zfill_chapter_float_value,
                )
                if file.file_type == "chapter"
                else (
                    volume_regex_keywords,
                    preferred_volume_renaming_format,
                    zfill_volume_int_value,
                    zfill_volume_float_value,
                )
            )
            regex_pattern = rf"(\b({keywords})([-_.]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s|{file_extensions_regex}))"
            if re.search(regex_pattern, file.name, re.IGNORECASE):
                rename = f"{base_dir} {preferred_naming_format}"
                numbers = []

                if file.multi_volume:
                    for n in file.volume_number:
                        numbers.append(n)
                        if n != file.volume_number[-1]:
                            numbers.append("-")
                else:
                    numbers.append(file.volume_number)

                number_string = ""

                for number in numbers:
                    if isinstance(number, (int, float)):
                        if number < 10 or (
                            file.file_type == "chapter" and number < 100
                        ):
                            fill_type = (
                                zfill_int if isinstance(number, int) else zfill_float
                            )
                            number_string += str(number).zfill(fill_type)
                        else:
                            number_string += str(number)
                    elif isinstance(number, str):
                        number_string += number

                rename += number_string

                if (
                    add_issue_number_to_manga_file_name
                    and file.file_type == "volume"
                    and file.extension in manga_extensions
                    and number_string
                ):
                    rename += f" #{number_string}"

                if file.subtitle:
                    rename += f" - {file.subtitle}"

                if file.volume_year:
                    rename += f" {modifiers[file.extension] % file.volume_year}"

                    file.extras = [
                        item
                        for item in file.extras
                        if not (
                            str(file.volume_year) in item
                            or similar(item, str(file.volume_year))
                            >= required_similarity_score
                            or re.search(r"([\[\(\{]\d{4}[\]\)\}])", item)
                        )
                    ]

                if (
                    file.publisher.from_meta or file.publisher.from_name
                ) and add_publisher_name_to_file_name_when_renaming:
                    for item in file.extras[:]:
                        for publisher in publishers:
                            item_without_special_chars = re.sub(
                                r"[\(\[\{\)\]\}]", "", item
                            )
                            meta_similarity = (
                                similar(
                                    item_without_special_chars, file.publisher.from_meta
                                )
                                if file.publisher.from_meta
                                else 0
                            )
                            name_similarity = (
                                similar(
                                    item_without_special_chars, file.publisher.from_name
                                )
                                if file.publisher.from_name
                                else 0
                            )

                            if (
                                similar(item_without_special_chars, publisher)
                                >= publisher_similarity_score
                                or meta_similarity >= publisher_similarity_score
                                or name_similarity >= publisher_similarity_score
                            ):
                                file.extras.remove(item)
                                break
                    if file.publisher.from_meta or file.publisher.from_name:
                        rename += f" {modifiers[file.extension] % (file.publisher.from_meta or file.publisher.from_name)}"

                if file.is_premium and search_and_add_premium_to_file_name:
                    rename += f" {modifiers[file.extension] % 'Premium'}"

                    file.extras = [
                        item for item in file.extras if "premium" not in item.lower()
                    ]

                left_brackets = r"(\(|\[|\{)"
                right_brackets = r"(\)|\]|\})"

                if (
                    move_release_group_to_end_of_file_name
                    and add_publisher_name_to_file_name_when_renaming
                    and file.release_group
                    and file.release_group != file.publisher.from_meta
                    and file.release_group != file.publisher.from_name
                ):
                    file.extras = [
                        item
                        for item in file.extras
                        if not (
                            similar(
                                re.sub(r"[\(\[\{\)\]\}]", "", item), file.release_group
                            )
                            >= release_group_similarity_score
                            or re.search(
                                rf"{left_brackets}{re.escape(item)}{right_brackets}",
                                file.release_group,
                                re.IGNORECASE,
                            )
                        )
                    ]

                if file.extras:
                    extras_to_add = [
                        extra
                        for extra in file.extras
                        if not re.search(re.escape(extra), rename, re.IGNORECASE)
                    ]
                    if extras_to_add:
                        rename += " " + " ".join(extras_to_add)

                # remove * from the replacement
                rename = rename.replace("*", "")

                if move_release_group_to_end_of_file_name and file.release_group:
                    release_group_escaped = re.escape(file.release_group)
                    if not re.search(
                        rf"\b{release_group_escaped}\b", rename, re.IGNORECASE
                    ):
                        rename += f" {modifiers[file.extension] % file.release_group}"

                rename += file.extension
                rename = rename.strip()

                # Replace unicode using unidecode, if enabled
                if replace_unicode_when_restructuring and contains_unicode(rename):
                    rename = unidecode(rename)

                # Replace any quotes with '
                rename = rename.replace('"', "'")

                # Replace / with -
                rename = rename.replace("/", "-")

                processed_files.append(rename)

                if file.name != rename:
                    rename_path = os.path.join(file.root, rename)

                    if watchdog_toggle:
                        transferred_files.append(rename_path)

                    try:
                        send_message(f"\n\t\tBEFORE: {file.name}", discord=False)
                        send_message(f"\t\tAFTER:  {rename}", discord=False)

                        user_input = (
                            get_input_from_user(
                                "\t\tReorganize & Rename", ["y", "n"], ["y", "n"]
                            )
                            if manual_rename
                            else "y"
                        )

                        if user_input == "y":
                            if not os.path.isfile(rename_path):
                                rename_status = rename_file(
                                    file.path,
                                    rename_path,
                                    silent=True,
                                )

                                if not rename_status:
                                    continue

                                # remove old file from list of transferred files
                                if file.path in transferred_files:
                                    transferred_files.remove(file.path)

                                send_message(
                                    "\t\t\tSuccessfully reorganized & renamed file.\n",
                                    discord=False,
                                )

                                if not mute_discord_rename_notifications:
                                    embed = handle_fields(
                                        DiscordEmbed(
                                            title="Reorganized & Renamed File",
                                            color=grey_color,
                                        ),
                                        fields=[
                                            {
                                                "name": "From",
                                                "value": f"```{file.name}```",
                                                "inline": False,
                                            },
                                            {
                                                "name": "To",
                                                "value": f"```{rename}```",
                                                "inline": False,
                                            },
                                        ],
                                    )
                                    grouped_notifications = group_notification(
                                        grouped_notifications, Embed(embed, None)
                                    )
                            else:
                                print(
                                    f"\t\tFile already exists, skipping rename of {file.name} to {rename} and deleting {file.name}"
                                )
                                remove_file(file.path, silent=True)

                            # replace volume obj
                            replacement_obj = upgrade_to_volume_class(
                                upgrade_to_file_class([rename], file.root)
                            )[0]

                            # append the new object and remove the old one
                            if replacement_obj not in files:
                                files.append(replacement_obj)
                                if file in files:
                                    files.remove(file)
                        else:
                            print("\t\t\tSkipping...\n")
                    except OSError as ose:
                        send_message(str(ose), error=True)
        except Exception as e:
            send_message(
                f"Failed to Reorganized & Renamed File: {file.name}: {e} with reoganize_and_rename",
                error=True,
            )

    return files


# Pre-compile dual space removal
dual_space_pattern = re.compile(r"(\s{2,})")


# Replaces any pesky double spaces
@lru_cache(maxsize=None)
def remove_dual_space(s):
    if "  " not in s:
        return s

    return dual_space_pattern.sub(" ", s)


# Removes common words to improve string matching accuracy between a series_name
# from a file name, and a folder name, useful for when releasers sometimes include them,
# and sometimes don't.
@lru_cache(maxsize=None)
def normalize_str(
    s,
    skip_common_words=False,
    skip_editions=False,
    skip_type_keywords=False,
    skip_japanese_particles=False,
    skip_misc_words=False,
    skip_storefront_keywords=False,
):
    if len(s) <= 1:
        return s

    words_to_remove = []

    if not skip_common_words:
        common_words = [
            "the",
            "a",
            "à",
            "and",
            "&",
            "I",
            "of",
        ]
        words_to_remove.extend(common_words)

    if not skip_editions:
        editions = [
            "Collection",
            "Master Edition",
            "(2|3|4|5)-in-1 Edition",
            "Edition",
            "Exclusive",
            "Anniversary",
            "Deluxe",
            # "Omnibus",
            "Digital",
            "Official",
            "Anthology",
            "Limited",
            "Complete",
            "Collector",
            "Ultimate",
            "Special",
        ]
        words_to_remove.extend(editions)

    if not skip_type_keywords:
        # (?<!^) = Cannot start with this word.
        # EX: "Book Girl" light novel series.
        type_keywords = [
            "(?<!^)Novel",
            "(?<!^)Light Novel",
            "(?<!^)Manga",
            "(?<!^)Comic",
            "(?<!^)LN",
            "(?<!^)Series",
            "(?<!^)Volume",
            "(?<!^)Chapter",
            "(?<!^)Book",
            "(?<!^)MANHUA",
        ]
        words_to_remove.extend(type_keywords)

    if not skip_japanese_particles:
        japanese_particles = [
            "wa",
            "o",
            "mo",
            "ni",
            "e",
            "de",
            "ga",
            "kara",
            "to",
            "ya",
            "no(?!\.)",
            "ne",
            "yo",
        ]
        words_to_remove.extend(japanese_particles)

    if not skip_misc_words:
        misc_words = ["((\d+)([-_. ]+)?th)", "x", "×", "HD"]
        words_to_remove.extend(misc_words)

    if not skip_storefront_keywords:
        storefront_keywords = [
            "Book(\s+)?walker",
        ]
        words_to_remove.extend(storefront_keywords)

    for word in words_to_remove:
        pattern = rf"\b{word}\b" if word not in type_keywords else rf"{word}\s"
        s = re.sub(pattern, " ", s, flags=re.IGNORECASE).strip()

        s = remove_dual_space(s)

    return s.strip()


# Removes the s from any words that end in s
@lru_cache(maxsize=None)
def remove_s(s):
    return re.sub(r"\b(\w+)(s)\b", r"\1", s, flags=re.IGNORECASE).strip()


# Precompiled
punctuation_pattern = re.compile(r"[^\w\s]")


# Determines if the string contains punctuation
def contains_punctuation(s):
    return bool(punctuation_pattern.search(s))


# Returns a string without punctuation.
@lru_cache(maxsize=None)
def remove_punctuation(s):
    return re.sub(r"[^\w\s]", " ", s).strip()


# Cleans the string by removing punctuation, bracketed info, and replacing underscores with periods.
# Converts the string to lowercase and removes leading/trailing whitespace.
@lru_cache(maxsize=None)
def clean_str(
    string,
    skip_lowercase_convert=False,
    skip_colon_replace=False,
    skip_bracket=False,
    skip_unidecode=False,
    skip_normalize=False,
    skip_punctuation=False,
    skip_remove_s=False,
    skip_convert_to_ascii=False,
    skip_underscore=False,
):
    # Convert to lower and strip
    s = string.lower().strip() if not skip_lowercase_convert else string

    # replace : with space
    s = s.replace(":", " ") if not skip_colon_replace and ":" in s else s

    # remove uneccessary spacing
    s = remove_dual_space(s)

    # Remove bracketed info
    s = remove_brackets(s) if not skip_bracket and contains_brackets(s) else s

    # Remove unicode
    s = unidecode(s) if not skip_unidecode and contains_unicode(s) else s

    # normalize the string
    s = normalize_str(s) if not skip_normalize else s

    # Remove punctuation
    s = remove_punctuation(s) if not skip_punctuation and contains_punctuation(s) else s

    # remove trailing s
    s = remove_s(s) if not skip_remove_s else s

    # remove dual spaces
    s = remove_dual_space(s)

    # convert to ascii
    s = convert_to_ascii(s) if not skip_convert_to_ascii else s

    # Replace underscores with periods
    s = replace_underscores(s) if not skip_underscore and "_" in s else s

    return s.strip()


# Creates folders for our stray volumes sitting in the root of the download folder.
def create_folders_for_items_in_download_folder():
    global transferred_files, transferred_dirs, grouped_notifications

    print("\nCreating folders for lone items in download folder...")

    if not download_folders:
        print("\tNo download folders found.")
        return

    for download_folder in download_folders:
        if not os.path.exists(download_folder):
            send_message(
                f"\nERROR: {download_folder} is an invalid path.\n", error=True
            )
            continue

        try:
            for root, dirs, files in scandir.walk(download_folder):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )

                if not files:
                    continue

                global folder_accessor
                file_objects = upgrade_to_file_class(files, root)
                folder_accessor = create_folder_obj(root, dirs, file_objects)

                for file in folder_accessor.files:
                    if not (
                        file.extension in file_extensions
                        and os.path.basename(download_folder)
                        == os.path.basename(file.root)
                    ):
                        continue

                    done = False

                    if move_lone_files_to_similar_folder and dirs:
                        for folder in dirs:
                            folder_lower = folder.strip().lower()
                            basename_lower = file.basename.strip().lower()

                            if (folder_lower == basename_lower) or (
                                similar(
                                    clean_str(folder, skip_bracket=True),
                                    clean_str(file.basename, skip_bracket=True),
                                )
                                >= required_similarity_score
                            ):
                                if (
                                    replace_series_name_in_file_name_with_similar_folder_name
                                    and file.basename != folder
                                ):
                                    # replace the series name in the file name with the folder name and rename the file
                                    new_file_name = re.sub(
                                        file.basename,
                                        folder,
                                        file.name,
                                        flags=re.IGNORECASE,
                                    )
                                    new_file_path = os.path.join(root, new_file_name)

                                    # create file object
                                    new_file_obj = File(
                                        new_file_name,
                                        get_extensionless_name(new_file_name),
                                        get_series_name_from_volume(
                                            new_file_name, root
                                        ),
                                        get_file_extension(new_file_name),
                                        root,
                                        new_file_path,
                                        get_extensionless_name(new_file_path),
                                        None,
                                        None,
                                        get_header_extension(new_file_path),
                                    )

                                    # if it doesn't already exist
                                    if not os.path.isfile(
                                        os.path.join(file.root, new_file_obj.name)
                                    ):
                                        rename_file(
                                            file.path,
                                            new_file_obj.path,
                                        )
                                        file = new_file_obj
                                    else:
                                        # if it does exist, delete the file
                                        remove_file(file.path, silent=True)

                                already_existing_file = os.path.join(
                                    root, folder, file.name
                                )
                                # check that the file doesn't already exist in the folder
                                if os.path.isfile(file.path) and not os.path.isfile(
                                    already_existing_file
                                ):
                                    new_folder_location = os.path.join(root, folder)
                                    # it doesn't, we move it and the image associated with it, to that folder
                                    move_file(
                                        file,
                                        new_folder_location,
                                    )
                                    if watchdog_toggle:
                                        transferred_files.append(already_existing_file)

                                        # remove old item from transferred files
                                        if file.path in transferred_files:
                                            transferred_files.remove(file.path)

                                        # add new folder object to transferred dirs
                                        transferred_dirs.append(
                                            create_folder_obj(new_folder_location)
                                        )
                                    done = True
                                    break
                                else:
                                    # it does, so we remove the duplicate file
                                    remove_file(
                                        os.path.join(root, file.name),
                                        silent=True,
                                    )
                                    done = True
                                    break
                    if not done and file.basename:
                        similarity_result = similar(file.name, file.basename)
                        write_to_file(
                            "changes.txt",
                            f"Similarity Result between: {file.name} and {file.basename} was {similarity_result}",
                        )
                        folder_location = os.path.join(file.root, file.basename)
                        does_folder_exist = os.path.exists(folder_location)
                        if not does_folder_exist:
                            os.mkdir(folder_location)
                        move_file(file, folder_location)
                        if watchdog_toggle:
                            transferred_files.append(
                                os.path.join(folder_location, file.name)
                            )
                            # remove old item from transferred files
                            if file.path in transferred_files:
                                transferred_files.remove(file.path)

                            # add new folder object to transferred dirs
                            transferred_dirs.append(
                                create_folder_obj(
                                    folder_location,
                                )
                            )

        except Exception as e:
            send_message(str(e), error=True)


# convert string to acsii
@lru_cache(maxsize=None)
def convert_to_ascii(s):
    return "".join(i for i in s if ord(i) < 128)


# convert array to string separated by whatever is passed in the separator parameter
def array_to_string(array, separator=", "):
    if isinstance(array, list):
        return separator.join([str(x) for x in array])
    elif isinstance(array, (int, float, str)):
        return separator.join([str(array)])
    else:
        return str(array)


class Result:
    def __init__(self, dir, score):
        self.dir = dir
        self.score = score

    # to string
    def __str__(self):
        return f"dir: {self.dir}, score: {self.score}"

    def __repr__(self):
        return str(self)


# Checks the novel for bonus.xhtml or bonus[0-9].xhtml, otherwise it
# gets the toc.xhtml or copyright.xhtml file from the novel file and checks
# that for premium content
def is_premium_volume(file):
    bonus_content_found = False
    try:
        with zipfile.ZipFile(file, "r") as zf:
            if "bonus" in str(zf.namelist()).lower() and re.search(
                r"((bonus)_?([0-9]+)?\.xhtml)",
                str(zf.namelist()).lower(),
                re.IGNORECASE,
            ):
                bonus_content_found = True

            if not bonus_content_found:
                for name in zf.namelist():
                    base_name = os.path.basename(name)
                    if base_name not in ["toc.xhtml", "copyright.xhtml"]:
                        continue

                    with zf.open(name) as file:
                        file_contents = file.read().decode("utf-8")
                        if base_name == "toc.xhtml":
                            if "j-novel" in file_contents.lower() and re.search(
                                r"(Bonus\s+((Color\s+)?Illustrations?|(Short\s+)?Stories))",
                                file_contents,
                                re.IGNORECASE,
                            ):
                                bonus_content_found = True
                                break
                        elif base_name == "copyright.xhtml":
                            if re.search(
                                r"(Premium(\s)+(E?-?Book|Epub))",
                                file_contents,
                                re.IGNORECASE,
                            ):
                                bonus_content_found = True
                                break
    except Exception as e:
        send_message(str(e), error=True)
    return bonus_content_found


class NewReleaseNotification:
    def __init__(self, number, title, color, fields, webhook, series_name, volume_obj):
        self.number = number
        self.title = title
        self.color = color
        self.fields = fields
        self.webhook = webhook
        self.series_name = series_name
        self.volume_obj = volume_obj


# Determines if the downloaded file is an upgrade or not to the existing library.
def check_upgrade(
    existing_root,
    dir,
    file,
    similarity_strings=None,
    cache=False,
    isbn=False,
    image=False,
    test_mode=False,
):
    global moved_files, messages_to_send, grouped_notifications

    # Gets the percentage of files that match a file_type or extension in a folder.
    def get_percent_and_print(existing_files, file, file_type=None):
        percent_dl = 0
        percent_existing = 0

        if file_type in ["manga", "novel"]:
            percent_dl = get_folder_type(
                [file.name],
                extensions=(
                    manga_extensions if file_type == "manga" else novel_extensions
                ),
            )
            percent_existing = get_folder_type(
                [f.name for f in existing_files],
                extensions=(
                    manga_extensions if file_type == "manga" else novel_extensions
                ),
            )
        elif file_type in ["chapter", "volume"]:
            percent_dl = get_folder_type(
                [file],
                file_type=file_type,
            )
            percent_existing = get_folder_type(
                existing_files,
                file_type=file_type,
            )

        print(f"\n\t\tDownload Folder {file_type.capitalize()} Percent: {percent_dl}%")
        print(
            f"\t\tExisting Folder {file_type.capitalize()} Percent: {percent_existing}%"
        )
        return percent_dl, percent_existing

    existing_dir = os.path.join(existing_root, dir)

    clean_existing = [
        entry.name for entry in os.scandir(existing_dir) if entry.is_file()
    ]

    clean_existing = upgrade_to_file_class(
        clean_existing,
        existing_dir,
        clean=True,
    )

    print(f"\tRequired Folder Matching Percent: {required_matching_percentage}%")

    manga_percent_dl, manga_percent_exst = get_percent_and_print(
        clean_existing, file, "manga"
    )
    novel_percent_dl, novel_percent_exst = get_percent_and_print(
        clean_existing, file, "novel"
    )

    chapter_percentage_dl, chapter_percentage_exst = get_percent_and_print(
        clean_existing, file, "chapter"
    )
    volume_percentage_dl, volume_percentage_exst = get_percent_and_print(
        clean_existing, file, "volume"
    )

    matching_manga = (
        manga_percent_dl >= required_matching_percentage
        and manga_percent_exst >= required_matching_percentage
    )
    matching_novel = (
        novel_percent_dl >= required_matching_percentage
        and novel_percent_exst >= required_matching_percentage
    )
    matching_chapter = (
        chapter_percentage_dl >= required_matching_percentage
        and chapter_percentage_exst >= required_matching_percentage
    )
    matching_volume = (
        volume_percentage_dl >= required_matching_percentage
        and volume_percentage_exst >= required_matching_percentage
    )

    if (matching_manga or matching_novel) and (matching_chapter or matching_volume):
        clean_existing = upgrade_to_volume_class(
            clean_existing,
            skip_release_year=True,
            skip_release_group=True,
            skip_extras=True,
            skip_publisher=True,
            skip_premium_content=True,
            skip_subtitle=True,
        )

        if test_mode:
            return clean_existing

        download_dir_volumes = [file]

        if rename_files_in_download_folders_toggle and resturcture_when_renaming:
            reorganize_and_rename(download_dir_volumes, existing_dir)

        fields = [
            {
                "name": "Existing Series Location",
                "value": f"```{existing_dir}```",
                "inline": False,
            }
        ]

        if similarity_strings:
            if not isbn and not image:
                fields.extend(
                    [
                        {
                            "name": "Downloaded File Series Name",
                            "value": f"```{similarity_strings[0]}```",
                            "inline": True,
                        },
                        {
                            "name": "Existing Library Folder Name",
                            "value": f"```{similarity_strings[1]}```",
                            "inline": False,
                        },
                        {
                            "name": "Similarity Score",
                            "value": f"```{similarity_strings[2]}```",
                            "inline": True,
                        },
                        {
                            "name": "Required Score",
                            "value": f"```>= {similarity_strings[3]}```",
                            "inline": True,
                        },
                    ]
                )
            elif isbn and len(similarity_strings) >= 2:
                fields.extend(
                    [
                        {
                            "name": "Downloaded File",
                            "value": "```" + "\n".join(similarity_strings[0]) + "```",
                            "inline": False,
                        },
                        {
                            "name": "Existing Library File",
                            "value": "```" + "\n".join(similarity_strings[1]) + "```",
                            "inline": False,
                        },
                    ]
                )
            elif image and len(similarity_strings) == 4:
                fields.extend(
                    [
                        {
                            "name": "Existing Folder Name",
                            "value": f"```{similarity_strings[0]}```",
                            "inline": True,
                        },
                        {
                            "name": "File Series Name",
                            "value": f"```{similarity_strings[1]}```",
                            "inline": True,
                        },
                        {
                            "name": "Image Similarity Score",
                            "value": f"```{similarity_strings[2]}```",
                            "inline": False,
                        },
                        {
                            "name": "Required Score",
                            "value": f"```>={similarity_strings[3]}```",
                            "inline": True,
                        },
                    ]
                )
            else:
                send_message(
                    f"Error: similarity_strings is not long enough to be valid. {similarity_strings} File: {file.name}",
                    error=True,
                )

        message = f"Found existing series: {existing_dir}"
        title = "Found Series Match"

        if cache:
            message += " (CACHE)"
            title += " (CACHE)"
        elif isbn:
            message += " (Matching Identifier)"
            title += " (Matching Identifier)"
        elif image:
            message += " (Cover Match)"
            title += " (Cover Match)"

        send_message(f"\n\t\t{message}", discord=False)

        if len(fields) > 1:
            embed = handle_fields(
                DiscordEmbed(
                    title=title,
                    color=grey_color,
                ),
                fields=fields,
            )
            grouped_notifications = group_notification(
                grouped_notifications, Embed(embed, None)
            )

        clean_existing, download_dir_volumes = remove_duplicate_releases(
            clean_existing,
            download_dir_volumes,
            image_similarity_match=image,
        )

        if download_dir_volumes:
            volume = download_dir_volumes[0]

            if isinstance(volume.volume_number, (float, int, list)):
                send_message(
                    f"\t\t\t{volume.file_type.capitalize()} {array_to_string(volume.volume_number)}: {volume.name} does not exist in: {existing_dir}\n\t\t\tMoving: {volume.name} to {existing_dir}",
                    discord=False,
                )

                cover = (
                    find_and_extract_cover(volume, return_data_only=True)
                    if volume.file_type == "volume"
                    or (
                        volume.file_type == "chapter"
                        and output_chapter_covers_to_discord
                        and not new_volume_webhook
                    )
                    else None
                )

                fields = [
                    {
                        "name": f"{volume.file_type.capitalize()} Number(s)",
                        "value": f"```{array_to_string(volume.volume_number)}```",
                        "inline": False,
                    },
                    {
                        "name": f"{volume.file_type.capitalize()} Name(s)",
                        "value": f"```{volume.name}```",
                        "inline": False,
                    },
                ]

                if volume.volume_part and volume.file_type == "volume":
                    # insert after volume number in fields
                    fields.insert(
                        1,
                        {
                            "name": f"{volume.file_type.capitalize()} Part",
                            "value": f"```{volume.volume_part}```",
                            "inline": False,
                        },
                    )

                title = f"New {volume.file_type.capitalize()}(s) Added"
                is_chapter_dir = chapter_percentage_dl >= required_matching_percentage
                highest_index_num = (
                    get_highest_release(
                        tuple(
                            [
                                (
                                    item.index_number
                                    if not isinstance(item.index_number, list)
                                    else tuple(item.index_number)
                                )
                                for item in clean_existing + download_dir_volumes
                            ]
                        ),
                        is_chapter_directory=is_chapter_dir,
                    )
                    if not is_chapter_dir
                    else ""
                )

                move_status = move_file(
                    volume,
                    existing_dir,
                    highest_index_num=highest_index_num,
                    is_chapter_dir=is_chapter_dir,
                )

                if move_status:
                    check_and_delete_empty_folder(volume.root)
                    volume.path = os.path.join(existing_dir, volume.name)
                    volume.extensionless_path = get_extensionless_name(volume.path)
                    volume.root = existing_dir
                    moved_files.append(volume.path)

                embed = handle_fields(
                    DiscordEmbed(
                        title=title,
                        color=green_color,
                    ),
                    fields=fields,
                )

                if new_volume_webhook:
                    if volume.file_type == "chapter":
                        messages_to_send.append(
                            NewReleaseNotification(
                                volume.volume_number,
                                title,
                                green_color,
                                fields,
                                new_volume_webhook,
                                volume.series_name,
                                volume,
                            )
                        )
                    elif volume.file_type == "volume":
                        send_discord_message(
                            None,
                            [Embed(embed, cover)],
                            passed_webhook=new_volume_webhook,
                        )
                else:
                    grouped_notifications = group_notification(
                        grouped_notifications, Embed(embed, cover)
                    )

                return True
        else:
            check_and_delete_empty_folder(file.root)
            return True
    else:
        print("\n\t\tNo match found.")
        return False


# remove duplicates elements from the passed in list
def remove_duplicates(items):
    return list(dict.fromkeys(items))


# Return the zip comment for the passed zip file (cached)
# Used on existing library files.
@lru_cache(maxsize=None)
def get_zip_comment_cache(zip_file):
    comment = ""
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            if zip_ref.comment:
                comment = zip_ref.comment.decode("utf-8")
    except Exception as e:
        send_message(
            f"\tFailed to get zip comment for: {zip_file} - Error: {e}", error=True
        )
    return comment


# Return the zip comment for the passed zip file (no cache)
# Used on downloaded files. (more likely to change, hence no cache)
def get_zip_comment(zip_file):
    comment = ""
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            if zip_ref.comment:
                comment = zip_ref.comment.decode("utf-8")
    except Exception as e:
        send_message(
            f"\tFailed to get zip comment for: {zip_file} - Error: {e}", error=True
        )
    return comment


# Checks for any duplicate releases and deletes the lower ranking one.
def check_for_duplicate_volumes(paths_to_search=[]):
    global grouped_notifications

    if not paths_to_search:
        return

    try:
        for p in paths_to_search:
            if not os.path.exists(p):
                send_message(f"\nERROR: {p} is an invalid path.\n", error=True)
                continue

            print(f"\nSearching {p} for duplicate releases...")
            for root, dirs, files in scandir.walk(p):
                print(f"\t{root}")
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )

                if not files:
                    continue

                file_objects = upgrade_to_file_class(
                    [f for f in files if os.path.isfile(os.path.join(root, f))],
                    root,
                )
                file_objects = list(
                    {
                        fo
                        for fo in file_objects
                        for compare in file_objects
                        if fo.name != compare.name
                        and (fo.volume_number != "" and compare.volume_number != "")
                        and fo.volume_number == compare.volume_number
                        and fo.root == compare.root
                        and fo.extension == compare.extension
                        and fo.file_type == compare.file_type
                    }
                )

                volumes = upgrade_to_volume_class(file_objects)
                volumes = list(
                    {
                        v
                        for v in volumes
                        for compare in volumes
                        if v.name != compare.name
                        and v.index_number == compare.index_number
                        and v.root == compare.root
                        and v.extension == compare.extension
                        and v.file_type == compare.file_type
                        and v.series_name == compare.series_name
                    }
                )

                for file in volumes:
                    try:
                        if not os.path.isfile(file.path):
                            continue

                        volume_series_name = clean_str(file.series_name)

                        compare_volumes = [
                            x
                            for x in volumes.copy()
                            if x.name != file.name
                            and x.index_number == file.index_number
                            and x.root == file.root
                            and x.extension == file.extension
                            and x.file_type == file.file_type
                            and x.series_name == file.series_name
                        ]
                        if compare_volumes:
                            print(f"\t\tChecking: {file.name}")
                            for compare_file in compare_volumes:
                                try:
                                    if os.path.isfile(compare_file.path):
                                        print(f"\t\t\tAgainst: {compare_file.name}")
                                        compare_volume_series_name = clean_str(
                                            compare_file.series_name
                                        )

                                        if (
                                            file.root == compare_file.root
                                            and (
                                                file.index_number != ""
                                                and compare_file.index_number != ""
                                            )
                                            and file.index_number
                                            == compare_file.index_number
                                            and file.extension == compare_file.extension
                                            and (
                                                file.series_name.lower()
                                                == compare_file.series_name.lower()
                                                or similar(
                                                    volume_series_name,
                                                    compare_volume_series_name,
                                                )
                                                >= required_similarity_score
                                            )
                                            and file.file_type == compare_file.file_type
                                        ):
                                            main_file_upgrade_status = is_upgradeable(
                                                file, compare_file
                                            )
                                            compare_file_upgrade_status = (
                                                is_upgradeable(compare_file, file)
                                            )
                                            if (
                                                main_file_upgrade_status.is_upgrade
                                                or compare_file_upgrade_status.is_upgrade
                                            ):
                                                duplicate_file = None
                                                upgrade_file = None
                                                if main_file_upgrade_status.is_upgrade:
                                                    duplicate_file = compare_file
                                                    upgrade_file = file
                                                elif (
                                                    compare_file_upgrade_status.is_upgrade
                                                ):
                                                    duplicate_file = file
                                                    upgrade_file = compare_file
                                                send_message(
                                                    f"\n\t\t\tDuplicate release found in: {upgrade_file.root}"
                                                    f"\n\t\t\tDuplicate: {duplicate_file.name} has a lower score than {upgrade_file.name}"
                                                    f"\n\n\t\t\tDeleting: {duplicate_file.name} inside of {duplicate_file.root}\n",
                                                    discord=False,
                                                )
                                                embed = handle_fields(
                                                    DiscordEmbed(
                                                        title="Duplicate Download Release (Not Upgradeable)",
                                                        color=yellow_color,
                                                    ),
                                                    fields=[
                                                        {
                                                            "name": "Location",
                                                            "value": f"```{upgrade_file.root}```",
                                                            "inline": False,
                                                        },
                                                        {
                                                            "name": "Duplicate",
                                                            "value": f"```{duplicate_file.name}```",
                                                            "inline": False,
                                                        },
                                                        {
                                                            "name": "has a lower score than",
                                                            "value": f"```{upgrade_file.name}```",
                                                            "inline": False,
                                                        },
                                                    ],
                                                )
                                                grouped_notifications = (
                                                    group_notification(
                                                        grouped_notifications,
                                                        Embed(embed, None),
                                                    )
                                                )
                                                user_input = (
                                                    get_input_from_user(
                                                        f'\t\t\tDelete "{duplicate_file.name}"',
                                                        ["y", "n"],
                                                        ["y", "n"],
                                                    )
                                                    if manual_delete
                                                    else "y"
                                                )

                                                if user_input == "y":
                                                    remove_file(
                                                        duplicate_file.path,
                                                    )
                                                else:
                                                    print("\t\t\t\tSkipping...\n")
                                            else:
                                                file_hash = get_file_hash(file.path)
                                                compare_hash = get_file_hash(
                                                    compare_file.path
                                                )
                                                # Check if the file hashes are the same
                                                # instead of defaulting to requiring the user to decide.
                                                if (compare_hash and file_hash) and (
                                                    compare_hash == file_hash
                                                ):
                                                    embed = handle_fields(
                                                        DiscordEmbed(
                                                            title="Duplicate Download Release (HASH MATCH)",
                                                            color=yellow_color,
                                                        ),
                                                        fields=[
                                                            {
                                                                "name": "Location",
                                                                "value": f"```{file.root}```",
                                                                "inline": False,
                                                            },
                                                            {
                                                                "name": "File Names",
                                                                "value": f"```{file.name}\n{compare_file.name}```",
                                                                "inline": False,
                                                            },
                                                            {
                                                                "name": "File Hashes",
                                                                "value": f"```{file_hash} {compare_hash}```",
                                                                "inline": False,
                                                            },
                                                        ],
                                                    )
                                                    grouped_notifications = (
                                                        group_notification(
                                                            grouped_notifications,
                                                            Embed(embed, None),
                                                        )
                                                    )
                                                    # Delete the compare file
                                                    remove_file(
                                                        compare_file.path,
                                                    )
                                                else:
                                                    send_message(
                                                        f"\n\t\t\tDuplicate found in: {compare_file.root}"
                                                        f"\n\t\t\t\t{file.name}"
                                                        f"\n\t\t\t\t{compare_file.name}"
                                                        f"\n\t\t\t\t\tRanking scores are equal, REQUIRES MANUAL DECISION.",
                                                        discord=False,
                                                    )
                                                    embed = handle_fields(
                                                        DiscordEmbed(
                                                            title="Duplicate Download Release (REQUIRES MANUAL DECISION)",
                                                            color=yellow_color,
                                                        ),
                                                        fields=[
                                                            {
                                                                "name": "Location",
                                                                "value": f"```{compare_file.root}```",
                                                                "inline": False,
                                                            },
                                                            {
                                                                "name": "Duplicate",
                                                                "value": f"```{file.name}```",
                                                                "inline": False,
                                                            },
                                                            {
                                                                "name": "has an equal score to",
                                                                "value": f"```{compare_file.name}```",
                                                                "inline": False,
                                                            },
                                                        ],
                                                    )
                                                    grouped_notifications = (
                                                        group_notification(
                                                            grouped_notifications,
                                                            Embed(embed, None),
                                                        )
                                                    )
                                                    print("\t\t\t\t\tSkipping...")
                                except Exception as e:
                                    send_message(
                                        f"\n\t\t\tError: {e}\n\t\t\tSkipping: {compare_file.name}",
                                        error=True,
                                    )
                                    continue
                    except Exception as e:
                        send_message(
                            f"\n\t\tError: {e}\n\t\tSkipping: {file.name}",
                            error=True,
                        )
                        continue
    except Exception as e:
        send_message(f"\n\t\tError: {e}", error=True)


# Regex out underscore from passed string and return it
@lru_cache(maxsize=None)
def replace_underscores(name):
    # Replace underscores that are preceded and followed by a number with a period
    name = re.sub(r"(?<=\d)_(?=\d)", ".", name)

    # Replace all other underscores with a space
    name = name.replace("_", " ")
    name = remove_dual_space(name).strip()

    return name


# Reorganizes the passed array list by pulling the first letter of the string passed
# and inserting all matched items into the passed position of the array list
def organize_by_first_letter(array_list, string, position_to_insert_at, exclude=None):
    if not string:
        print(
            "First letter of file name was not found, skipping reorganization of array list."
        )
        return array_list

    if position_to_insert_at < 0 or position_to_insert_at >= len(array_list):
        return array_list

    first_letter_of_file_name = string[0].lower()
    items_to_move = []

    for item in array_list:
        if item in [exclude, array_list[position_to_insert_at]]:
            continue

        first_letter_of_dir = os.path.basename(item)[0].lower()

        if first_letter_of_dir == first_letter_of_file_name:
            items_to_move.append(item)

    # Only keep items that don't need to be moved
    array_list = [item for item in array_list if item not in items_to_move]

    # Insert the items that need to be moved at the passed position
    for item in items_to_move:
        array_list.insert(position_to_insert_at, item)

    return array_list


class IdentifierResult:
    def __init__(self, series_name, identifiers, path, matches):
        self.series_name = series_name
        self.identifiers = identifiers
        self.path = path
        self.matches = matches


# get identifiers from the passed zip comment
def get_identifiers(zip_comment):
    metadata = []

    if "identifiers" in zip_comment.lower():
        # split on Identifiers: and only keep the second half
        identifiers = ((zip_comment.split("Identifiers:")[1]).strip()).split(",")

        # remove any whitespace
        identifiers = [x.strip() for x in identifiers]

        # remove any that are "NONE" - used to be the default vale for the identifier
        # in my isbn script for other reasons
        if identifiers:
            metadata = [x for x in identifiers if "none" not in x.lower()]
    return metadata


# Parses the individual words from the passed string and returns them as an array
# without punctuation, unidecoded, and in lowercase.
@lru_cache(maxsize=None)
def parse_words(user_string):
    words = []
    if user_string:
        try:
            translator = str.maketrans("", "", string.punctuation)
            words_no_punct = user_string.translate(translator)
            words_lower = words_no_punct.lower()
            words_no_uni = (
                unidecode(words_lower) if contains_unicode(words_lower) else words_lower
            )
            words_no_uni_split = words_lower.split()
            if words_no_uni_split:
                words = words_no_uni_split
        except Exception as e:
            send_message(f"parse_words(string={user_string}) - Error: {e}", error=True)
    return words


# Finds a number of consecutive items in both arrays, or returns False if none are found.
@lru_cache(maxsize=None)
def find_consecutive_items(arr1, arr2, count=3):
    if len(arr1) < count or len(arr2) < count:
        return False

    for i in range(len(arr1) - count + 1):
        for j in range(len(arr2) - count + 1):
            if arr1[i : i + count] == arr2[j : j + count]:
                return True
    return False


# Counts the occurrence of each word in a list of strings.
def count_words(strings_list):
    word_count = {}

    for string in strings_list:
        # Remove punctuation and convert to lowercase
        words = parse_words(string)

        # Count the occurrence of each word
        for word in words:
            word_count[word] = word_count.get(word, 0) + 1

    return word_count


# Moves strings in item_array that match the first three words of target_item to the top of the array.
def move_strings_to_top(target_item, item_array):
    target_words = parse_words(unidecode(target_item.lower().strip()))

    # Find items in item_array that match the first three words of target_item
    items_to_move = [
        item
        for item in item_array
        if parse_words(os.path.basename(unidecode(item.lower().strip())))[:3]
        == target_words[:3]
    ]

    # Remove items_to_move from item_array
    item_array = [item for item in item_array if item not in items_to_move]

    # Insert items_to_move at the beginning of item_array
    item_array = items_to_move + item_array

    return item_array


# Checks for an existing series by pulling the series name from each elidable file in the downloads_folder
# and comparing it to an existin folder within the user's library.
def check_for_existing_series(
    test_mode=[],
    test_paths=paths,
    test_download_folders=download_folders,
    test_paths_with_types=paths_with_types,
    test_cached_paths=cached_paths,
):
    global cached_paths, cached_identifier_results, messages_to_send, grouped_notifications

    # Groups messages by their series
    def group_similar_series(messages_to_send):
        # Initialize an empty list to store grouped series
        grouped_series = []

        # Iterate through the messages in the input list
        for message in messages_to_send:
            series_name = message.series_name

            # Try to find an existing group with the same series name
            group = next(
                (
                    group
                    for group in grouped_series
                    if group["series_name"] == series_name
                ),
                None,
            )

            if group is not None:
                # If a group exists, append the message to that group
                group["messages"].append(message)
            else:
                # If no group exists, create a new group and add it to the list
                grouped_series.append(
                    {"series_name": series_name, "messages": [message]}
                )

        # Return the list of grouped series
        return grouped_series

    # Determines whether an alternative match
    # will be allowed to be attemtped or not.
    def alternative_match_allowed(
        inner_dir,
        file,
        short_word_filter_percentage,
        required_similarity_score,
        counted_words,
    ):
        # Get the subtitle from the folder name
        folder_subtitle = get_subtitle_from_dash(inner_dir, replace=True)
        folder_subtitle_clean = clean_str(folder_subtitle) if folder_subtitle else ""

        # Get the cleaned subtitle from the file series name
        file_subtitle = get_subtitle_from_dash(file.series_name, replace=True)
        file_subtitle_clean = clean_str(file_subtitle) if file_subtitle else ""

        # Get the shortened folder name
        short_fldr_name = clean_str(get_shortened_title(inner_dir) or inner_dir)

        # Get the shortened series name from the file
        short_file_series_name = clean_str(
            file.shortened_series_name or file.series_name
        )

        if not short_fldr_name or not short_file_series_name:
            return False

        long_folder_words = parse_words(inner_dir)
        long_file_words = parse_words(file.series_name)

        # use parse_words() to get the words from both strings
        short_fldr_name_words = parse_words(short_fldr_name)
        short_file_series_words = parse_words(short_file_series_name)

        file_wrds_mod = short_file_series_words
        fldr_wrds_mod = short_fldr_name_words

        if not file_wrds_mod or not fldr_wrds_mod:
            return False

        # Determine the minimum length between file_wrds_mod and fldr_wrds_mod
        # and calculate short_word_filter_percentage(70%) of the minimum length, ensuring it's at least 1
        shortened_length = max(
            1,
            int(
                min(len(file_wrds_mod), len(fldr_wrds_mod))
                * short_word_filter_percentage
            ),
        )

        # Shorten both arrays to the calculated length
        file_wrds_mod = file_wrds_mod[:shortened_length]
        fldr_wrds_mod = fldr_wrds_mod[:shortened_length]

        folder_name_match = (
            short_fldr_name.lower().strip() == short_file_series_name.lower().strip()
        )
        similar_score_match = (
            similar(short_fldr_name, short_file_series_name)
            >= required_similarity_score
        )
        consecutive_items_match = find_consecutive_items(
            tuple(short_fldr_name_words), tuple(short_file_series_words)
        ) or find_consecutive_items(tuple(long_folder_words), tuple(long_file_words))
        unique_words_match = any(
            [
                i
                for i in long_folder_words
                if i in long_file_words and i in counted_words and counted_words[i] <= 3
            ]
        )
        subtitle_match = (folder_subtitle_clean and file_subtitle_clean) and (
            folder_subtitle_clean == file_subtitle_clean
            or similar(folder_subtitle_clean, file_subtitle_clean)
            >= required_similarity_score
        )

        return (
            folder_name_match
            or similar_score_match
            or consecutive_items_match
            or unique_words_match
            or subtitle_match
        )

    # Attempts an alternative match and returns the cover score
    def attempt_alternative_match(
        file_root, inner_dir, file, required_image_similarity_score
    ):
        # Returns volumes with a matching index number
        def get_matching_volumes(file, img_volumes):
            matching_volumes = [
                volume
                for volume in img_volumes
                if is_same_index_number(
                    volume.index_number, file.index_number, allow_array_match=True
                )
            ]

            if (len(img_volumes) - len(matching_volumes)) <= 10:
                matching_volumes.extend(
                    [volume for volume in img_volumes if volume not in matching_volumes]
                )

            return matching_volumes

        img_volumes = upgrade_to_volume_class(
            upgrade_to_file_class(
                [
                    f
                    for f in os.listdir(file_root)
                    if os.path.isfile(join(file_root, f))
                ],
                file_root,
                clean=True,
            )
        )
        if not img_volumes:
            print("\t\t\tNo volumees found for alternative match.")
            return 0, None

        matching_volumes = get_matching_volumes(file, img_volumes)

        if not matching_volumes:
            print("\t\t\tNo matching volumes found for alternative match.")
            return 0, None

        downloaded_volume_cover_data = find_and_extract_cover(
            file,
            return_data_only=True,
            silent=True,
            blank_image_check=True,
        )

        if not downloaded_volume_cover_data:
            print("\t\t\tNo downloaded volume cover data found.")
            return 0, None

        for matching_volume in matching_volumes:
            print(
                f"\t\t\tMatching volume:\n\t\t\t\t{matching_volume.name}\n\t\t\t\t{file.name}"
            )

            existing_volume_cover_data = find_and_extract_cover(
                matching_volume,
                return_data_only=True,
                silent=True,
                blank_image_check=True,
            )

            if not existing_volume_cover_data:
                print("\t\t\tNo existing volume cover data found.")
                continue

            score = prep_images_for_similarity(
                existing_volume_cover_data,
                downloaded_volume_cover_data,
                both_cover_data=True,
                silent=True,
            )

            print(f"\t\t\tRequired Image Similarity: {required_image_similarity_score}")
            print(f"\t\t\t\tCover Image Similarity Score: {score}")

            if score >= required_image_similarity_score:
                return score, matching_volume
        return 0, None

    if test_mode:
        global download_folders, paths, paths_with_types, cached_paths

        if test_download_folders:
            download_folders = test_download_folders
        if test_paths:
            paths = test_paths
        if test_paths_with_types:
            paths_with_types = test_paths_with_types
        if test_cached_paths:
            cached_paths = test_cached_paths

    cached_image_similarity_results = []

    if not download_folders:
        print("\nNo download folders specified, skipping check_for_existing_series.")
        return

    print("\nChecking download folders for items to match to existing library...")
    for download_folder in download_folders:
        if not os.path.exists(download_folder) and not test_mode:
            print(f"\n\t{download_folder} does not exist, skipping...")
            continue

        # Get all the paths
        folders = (
            get_all_folders_recursively_in_dir(download_folder)
            if not test_mode
            else [{"root": "/test_mode", "dirs": [], "files": test_mode}]
        )

        # Reverse the list so we start with the deepest folders
        # Helps when purging empty folders, since it won't purge a folder containing subfolders
        folders.reverse()

        # an array of unmatched items, used for skipping subsequent series
        # items that won't match
        unmatched_series = []

        for folder in folders:
            root = folder["root"]
            dirs = folder["dirs"]
            files = folder["files"]

            print(f"\n{root}")
            volumes = []

            if not test_mode:
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    sort=True,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )

                if not files:
                    continue

                volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(
                        [f for f in files if os.path.isfile(os.path.join(root, f))],
                        root,
                    )
                )
            else:
                volumes = test_mode

            # Sort the volumes
            volumes = sort_volumes(volumes)

            exclude = None

            similar.cache_clear()

            for file in volumes:
                try:
                    if not file.series_name:
                        print(f"\tSkipping: {file.name}\n\t\t - has no series_name")
                        continue

                    if file.volume_number == "":
                        print(f"\tSkipping: {file.name}\n\t\t - has no volume_number")
                        continue

                    if (
                        file.extension in manga_extensions
                        and not test_mode
                        and not zipfile.is_zipfile(file.path)
                    ):
                        print(
                            f"\tSkipping: {file.name}\n\t\t - is not a valid zip file, possibly corrupted."
                        )
                        continue

                    if not (
                        (file.name in processed_files or not processed_files)
                        and (test_mode or os.path.isfile(file.path))
                    ):
                        continue

                    done = False

                    # 1.1 - Check cached image similarity results
                    if (
                        cached_image_similarity_results
                        and match_through_image_similarity
                    ):
                        for cached_result in cached_image_similarity_results:
                            # split on @@ and get the value to the right
                            last_item = cached_result.split("@@")[-1].strip()

                            target_key = f"{file.series_name} - {file.file_type} - {file.root} - {file.extension}"

                            if target_key in cached_result:
                                print(
                                    "\n\t\tFound cached cover image similarity result."
                                )
                                done = check_upgrade(
                                    os.path.dirname(last_item),
                                    os.path.basename(last_item),
                                    file,
                                    similarity_strings=[
                                        file.series_name,
                                        file.series_name,
                                        "CACHE",
                                        required_image_similarity_score,
                                    ],
                                    image=True,
                                    test_mode=test_mode,
                                )
                                if done:
                                    break
                    if done:
                        continue

                    if unmatched_series and (
                        (not match_through_identifiers or file.file_type == "chapter")
                    ):
                        if (
                            f"{file.series_name} - {file.file_type} - {file.extension}"
                            in unmatched_series
                        ):
                            # print(f"\t\tSkipping: {file.name}...")
                            continue

                    # 1.2 - Check cached identifier results
                    if cached_identifier_results and file.file_type == "volume":
                        found_item = next(
                            (
                                cached_identifier
                                for cached_identifier in cached_identifier_results
                                if cached_identifier.series_name == file.series_name
                            ),
                            None,
                        )
                        if found_item:
                            done = check_upgrade(
                                os.path.dirname(found_item.path),
                                os.path.basename(found_item.path),
                                file,
                                similarity_strings=found_item.matches,
                                isbn=True,
                            )
                            if found_item.path not in cached_paths:
                                cache_path(found_item.path)
                            if done:
                                continue

                    if cached_paths:
                        if exclude:
                            cached_paths = organize_by_first_letter(
                                cached_paths, file.name, 1, exclude
                            )
                        else:
                            cached_paths = organize_by_first_letter(
                                cached_paths, file.name, 1
                            )

                    downloaded_file_series_name = clean_str(
                        file.series_name, skip_bracket=True
                    )

                    # organize the cached paths
                    if cached_paths and file.name != downloaded_file_series_name:
                        if exclude:
                            cached_paths = organize_by_first_letter(
                                cached_paths,
                                downloaded_file_series_name,
                                2,
                                exclude,
                            )
                        else:
                            cached_paths = organize_by_first_letter(
                                cached_paths,
                                downloaded_file_series_name,
                                2,
                            )

                    # Move paths matching the first three words to the top of the list
                    if cached_paths:
                        cached_paths = move_strings_to_top(
                            file.series_name, cached_paths
                        )

                    # 2 - Use the cached paths
                    if cached_paths:
                        print("\n\tChecking path types...")
                        for cached_path_index, p in enumerate(cached_paths[:], start=1):
                            if (
                                not os.path.exists(p)
                                or not os.path.isdir(p)
                                or p in download_folders
                            ):
                                continue

                            # Skip any paths that don't contain the file type or extension
                            if paths_with_types:
                                skip_path = next(
                                    (
                                        item
                                        for item in paths_with_types
                                        if p.startswith(item.path)
                                        and (
                                            file.file_type not in item.path_formats
                                            or file.extension
                                            not in item.path_extensions
                                        )
                                    ),
                                    None,
                                )

                                if skip_path:
                                    print(
                                        f"\t\tSkipping: {p} - Path: {skip_path.path_formats} File: {file.file_type}"
                                        if file.file_type not in skip_path.path_formats
                                        else f"\t\tSkipping: {p} - Path: {skip_path.path_extensions} File: {file.extension}"
                                    )
                                    continue

                            successful_series_name = clean_str(
                                os.path.basename(p), skip_bracket=True
                            )

                            successful_similarity_score = (
                                1
                                if successful_series_name == downloaded_file_series_name
                                else similar(
                                    successful_series_name,
                                    downloaded_file_series_name,
                                )
                            )

                            print(
                                f"\n\t\t-(CACHE)- {cached_path_index} of {len(cached_paths)} - "
                                f'"{file.name}"\n\t\tCHECKING: {downloaded_file_series_name}\n\t\tAGAINST:  {successful_series_name}\n\t\tSCORE:    {successful_similarity_score}'
                            )
                            if successful_similarity_score >= required_similarity_score:
                                send_message(
                                    f'\n\t\tSimilarity between: "{successful_series_name}"\n\t\t\t"{downloaded_file_series_name}" Score: {successful_similarity_score} out of 1.0\n',
                                    discord=False,
                                )
                                done = check_upgrade(
                                    os.path.dirname(p),
                                    os.path.basename(p),
                                    file,
                                    similarity_strings=[
                                        downloaded_file_series_name,
                                        downloaded_file_series_name,
                                        successful_similarity_score,
                                        required_similarity_score,
                                    ],
                                    cache=True,
                                    test_mode=test_mode,
                                )
                                if done:
                                    if test_mode:
                                        return done
                                    if p not in cached_paths:
                                        cache_path(p)
                                    if (
                                        len(volumes) > 1
                                        and p in cached_paths
                                        and p != cached_paths[0]
                                    ):
                                        cached_paths.remove(p)
                                        cached_paths.insert(0, p)
                                        exclude = p
                                    break
                    if done:
                        continue

                    dl_zip_comment = get_zip_comment(file.path) if not test_mode else ""
                    dl_meta = get_identifiers(dl_zip_comment) if dl_zip_comment else []

                    directories_found = []
                    matched_ids = []

                    for path_position, path in enumerate(paths, start=1):
                        if done or not os.path.exists(path) or path in download_folders:
                            continue

                        skip_path = next(
                            (
                                item
                                for item in paths_with_types
                                if (
                                    (
                                        path == item.path
                                        and file.file_type not in item.path_formats
                                    )
                                    or (
                                        path == item.path
                                        and file.extension not in item.path_extensions
                                    )
                                )
                            ),
                            None,  # default value if no match is found
                        )

                        # Skip any paths that don't contain the file type or extension
                        if paths_with_types and skip_path:
                            print(
                                f"\nSkipping path: {path} - Path: "
                                f"{array_to_string(skip_path.path_formats) if file.file_type not in skip_path.path_formats else array_to_string(skip_path.path_extensions)}"
                                f" File: {str(file.file_type) if file.file_type not in skip_path.path_formats else str(file.extension)}"
                            )
                            continue

                        try:
                            os.chdir(path)
                            reorganized = False

                            for root, dirs, files in scandir.walk(path):
                                if (
                                    test_mode
                                    and cached_paths
                                    and root in cached_paths
                                    and root not in paths + download_folders
                                ):
                                    continue

                                if not dirs and (
                                    test_mode or not match_through_identifiers
                                ):
                                    continue

                                if done:
                                    break

                                if (
                                    not match_through_identifiers
                                    and root in cached_paths
                                ):
                                    continue

                                counted_words = count_words(dirs)

                                if not reorganized:
                                    dirs = organize_by_first_letter(
                                        dirs,
                                        file.series_name,
                                        1,
                                        exclude=exclude,
                                    )
                                    dirs = organize_by_first_letter(
                                        dirs,
                                        file.series_name,
                                        2,
                                        exclude=exclude,
                                    )
                                    reorganized = True

                                    # Move paths matching the first three words to the top of the list
                                    dirs = move_strings_to_top(file.series_name, dirs)

                                files, dirs = clean_and_sort(root, files, dirs)
                                file_objects = upgrade_to_file_class(files, root)

                                global folder_accessor
                                folder_accessor = create_folder_obj(
                                    root, dirs, file_objects
                                )

                                print(f"Looking inside: {folder_accessor.root}")
                                if (
                                    folder_accessor.dirs
                                    and root not in cached_paths + download_folders
                                ):
                                    if done:
                                        break

                                    print(f"\n\tLooking for: {file.series_name}")
                                    for dir_position, inner_dir in enumerate(
                                        folder_accessor.dirs, start=1
                                    ):
                                        if done:
                                            break

                                        existing_series_folder_from_library = clean_str(
                                            inner_dir
                                        )

                                        similarity_score = (
                                            1
                                            if (
                                                existing_series_folder_from_library.lower()
                                                == downloaded_file_series_name.lower()
                                            )
                                            else similar(
                                                existing_series_folder_from_library,
                                                downloaded_file_series_name,
                                            )
                                        )

                                        print(
                                            f'\n\t\t-(NOT CACHE)- {dir_position} of {len(folder_accessor.dirs)} - path {path_position} of {len(paths)} - "{file.name}"\n\t\tCHECKING: {downloaded_file_series_name}\n\t\tAGAINST:  {existing_series_folder_from_library}\n\t\tSCORE:    {similarity_score}'
                                        )
                                        file_root = os.path.join(
                                            folder_accessor.root, inner_dir
                                        )
                                        if (
                                            similarity_score
                                            >= required_similarity_score
                                        ):
                                            send_message(
                                                f'\n\t\tSimilarity between: "{existing_series_folder_from_library}" and "{downloaded_file_series_name}" '
                                                f"Score: {similarity_score} out of 1.0\n",
                                                discord=False,
                                            )
                                            done = check_upgrade(
                                                folder_accessor.root,
                                                inner_dir,
                                                file,
                                                similarity_strings=[
                                                    downloaded_file_series_name,
                                                    existing_series_folder_from_library,
                                                    similarity_score,
                                                    required_similarity_score,
                                                ],
                                                test_mode=test_mode,
                                            )
                                            if not done:
                                                continue

                                            if test_mode:
                                                return done

                                            if (
                                                file_root not in cached_paths
                                                and not test_mode
                                            ):
                                                cache_path(file_root)
                                            if (
                                                len(volumes) > 1
                                                and file_root in cached_paths
                                                and file_root != cached_paths[0]
                                            ):
                                                cached_paths.remove(file_root)
                                                cached_paths.insert(
                                                    0,
                                                    file_root,
                                                )
                                            break
                                        elif (
                                            match_through_image_similarity
                                            and not test_mode
                                            and alternative_match_allowed(
                                                inner_dir,
                                                file,
                                                short_word_filter_percentage,
                                                required_similarity_score,
                                                counted_words,
                                            )
                                        ):
                                            print(
                                                "\n\t\tAttempting alternative match through cover image similarity..."
                                            )
                                            print(
                                                f"\t\t\tSeries Names: \n\t\t\t\t{inner_dir}\n\t\t\t\t{file.series_name}"
                                            )
                                            (
                                                score,
                                                matching_volume,
                                            ) = attempt_alternative_match(
                                                file_root,
                                                inner_dir,
                                                file,
                                                required_image_similarity_score,
                                            )

                                            if score >= required_image_similarity_score:
                                                print(
                                                    "\t\tMatch found through cover image similarity."
                                                )
                                                # check all volumes in volumes, if all the volumes in this inner_dir have the same series_name
                                                all_matching = False
                                                same_root_files = [
                                                    item
                                                    for item in volumes
                                                    if item.root == file.root
                                                ]
                                                if same_root_files:
                                                    all_matching = all(
                                                        item.series_name.lower().strip()
                                                        == file.series_name.lower().strip()
                                                        for item in same_root_files
                                                        if item != file
                                                    )
                                                if all_matching:
                                                    print(
                                                        "\t\t\tAll Download Series Names Match, Adding to Cache.\n"
                                                    )
                                                    cached_image_similarity_results.append(
                                                        f"{file.series_name} - {file.file_type} - {file.root} - {file.extension} @@ {os.path.join(folder_accessor.root, inner_dir)}"
                                                    )
                                                done = check_upgrade(
                                                    folder_accessor.root,
                                                    inner_dir,
                                                    file,
                                                    similarity_strings=[
                                                        inner_dir,
                                                        file.series_name,
                                                        score,
                                                        required_image_similarity_score,
                                                    ],
                                                    image=matching_volume,
                                                )
                                                if done:
                                                    break

                                # 3.1 - Use identifier matching
                                if (
                                    not done
                                    and not test_mode
                                    and match_through_identifiers
                                    and root not in download_folders
                                    and dl_meta
                                    and file.file_type == "volume"
                                    and folder_accessor.files
                                ):
                                    print(
                                        f"\n\t\tMatching Identifier Search: {folder_accessor.root}"
                                    )
                                    for f in folder_accessor.files:
                                        if f.root in directories_found:
                                            break

                                        if f.extension != file.extension:
                                            continue

                                        print(f"\t\t\t{f.name}")
                                        existing_file_zip_comment = (
                                            get_zip_comment_cache(f.path)
                                        )
                                        existing_file_meta = get_identifiers(
                                            existing_file_zip_comment
                                        )

                                        if existing_file_meta:
                                            print(f"\t\t\t\t{existing_file_meta}")
                                            if any(
                                                d_meta in existing_file_meta
                                                and f.root not in directories_found
                                                for d_meta in dl_meta
                                            ):
                                                directories_found.append(f.root)
                                                matched_ids.extend(
                                                    [
                                                        dl_meta,
                                                        existing_file_meta,
                                                    ]
                                                )
                                                print(
                                                    f"\n\t\t\t\tMatch found in: {f.root}"
                                                )
                                                break
                                        else:
                                            print("\t\t\t\t[]")
                        except Exception as e:
                            # print stack trace
                            send_message(str(e), error=True)

                    # 3.2 - Process identifier matches
                    if (
                        not done
                        and not test_mode
                        and match_through_identifiers
                        and file.file_type == "volume"
                        and directories_found
                    ):
                        directories_found = remove_duplicates(directories_found)

                        if len(directories_found) == 1:
                            matched_directory = directories_found[0]
                            print(f"\n\t\tMatch found in: {matched_directory}\n")
                            base = os.path.basename(matched_directory)

                            identifier = IdentifierResult(
                                file.series_name,
                                dl_meta,
                                matched_directory,
                                matched_ids,
                            )
                            if identifier not in cached_identifier_results:
                                cached_identifier_results.append(identifier)

                            done = check_upgrade(
                                os.path.dirname(matched_directory),
                                base,
                                file,
                                similarity_strings=matched_ids,
                                isbn=True,
                            )

                            if done:
                                if matched_directory not in cached_paths:
                                    cache_path(matched_directory)
                                if (
                                    len(volumes) > 1
                                    and matched_directory in cached_paths
                                    and matched_directory != cached_paths[0]
                                ):
                                    cached_paths.remove(matched_directory)
                                    cached_paths.insert(0, matched_directory)
                        else:
                            print(
                                "\t\t\tMatching ISBN or Series ID found in multiple directories."
                            )
                            for d in directories_found:
                                print(f"\t\t\t\t{d}")
                            print("\t\t\tDisregarding Matches...")

                    if not done:
                        unmatched_series.append(
                            f"{file.series_name} - {file.file_type} - {file.extension}"
                        )
                        print(
                            f"No match found for: {file.series_name} - {file.file_type} - {file.extension}"
                        )
                except Exception as e:
                    stack_trace = traceback.format_exc()
                    print(stack_trace)
                    send_message(str(e), error=True)

        # purge any empty folders
        if folders and not test_mode:
            for folder in folders:
                check_and_delete_empty_folder(folder["root"])

    series_notifications = []
    webhook_to_use = pick_webhook(None, new_volume_webhook)

    if messages_to_send:
        grouped_by_series_names = group_similar_series(messages_to_send)
        messages_to_send = []

        for grouped_by_series_name in grouped_by_series_names:
            group_messages = grouped_by_series_name["messages"]

            if output_chapter_covers_to_discord:
                for message in group_messages[:]:
                    cover = find_and_extract_cover(
                        message.volume_obj, return_data_only=True
                    )
                    embed = handle_fields(
                        DiscordEmbed(
                            title=message.title,
                            color=message.color,
                        ),
                        fields=message.fields,
                    )

                    if new_volume_webhook:
                        series_notifications = group_notification(
                            series_notifications,
                            Embed(embed, cover),
                            webhook_to_use,
                        )
                    else:
                        grouped_notifications = group_notification(
                            grouped_notifications,
                            Embed(embed, cover),
                            webhook_to_use,
                        )
                    group_messages.remove(message)
            else:
                volume_numbers_mts = []
                volume_names_mts = []
                first_item = group_messages[0]
                title = first_item.fields[0]["name"]
                title_2 = first_item.fields[1]["name"]
                series_name = first_item.series_name

                for message in group_messages:
                    if message.fields and len(message.fields) >= 2:
                        # remove ``` from the start and end of the value
                        volume_numbers_mts.append(
                            message.fields[0]["value"].replace("```", "")
                        )
                        volume_names_mts.append(
                            message.fields[1]["value"].replace("```", "")
                        )

                if volume_numbers_mts and volume_names_mts and series_name:
                    new_fields = [
                        {
                            "name": "Series Name",
                            "value": "```" + series_name + "```",
                            "inline": False,
                        },
                        {
                            "name": title,
                            "value": "```" + ", ".join(volume_numbers_mts) + "```",
                            "inline": False,
                        },
                        {
                            "name": title_2,
                            "value": "```" + "\n".join(volume_names_mts) + "```",
                            "inline": False,
                        },
                    ]
                    embed = handle_fields(
                        DiscordEmbed(
                            title=first_item.title,
                            color=first_item.color,
                        ),
                        fields=new_fields,
                    )

                    if new_volume_webhook:
                        series_notifications = group_notification(
                            series_notifications,
                            Embed(embed, None),
                            webhook_to_use,
                        )
                    else:
                        grouped_notifications = group_notification(
                            grouped_notifications,
                            Embed(embed, None),
                            webhook_to_use,
                        )

    if series_notifications:
        send_discord_message(
            None,
            series_notifications,
            passed_webhook=webhook_to_use,
        )

    # clear lru_cache for parse_words
    parse_words.cache_clear()

    # clear lru_ache for find_consecutive_items()
    find_consecutive_items.cache_clear()


# Removes any unnecessary junk through regex in the folder name and returns the result
# !OLD METHOD!: Only used for cleaning a folder name as a backup if no volumes were found inside the folder
# when renaming folders in the dowload directory.
def get_series_name(dir):
    dir = remove_dual_space(dir.replace("_extra", ".5")).strip()
    dir = (
        re.sub(
            r"(\b|\s)((\s|)-(\s|)|)(Part|)(%s)([-_. ]|)([-_. ]|)([0-9]+)(\b|\s).*"
            % volume_regex_keywords,
            "",
            dir,
            flags=re.IGNORECASE,
        )
    ).strip()
    dir = (re.sub(r"(\([^()]*\))|(\[[^\[\]]*\])|(\{[^\{\}]*\})", "", dir)).strip()
    dir = (re.sub(r"(\(|\)|\[|\]|{|})", "", dir, flags=re.IGNORECASE)).strip()
    return dir


# Renames the folders in our download directory.
# If volume releases are available, it will rename based on those.
# Otherwise it will fallback to just cleaning the name of any brackets.
def rename_dirs_in_download_folder(paths_to_process=download_folders):
    global grouped_notifications

    # Processes the passed folder
    def process_folder(download_folder):
        # Renames the root folder based on the volumes
        def rename_based_on_volumes(root):
            global transferred_dirs, transferred_files
            nonlocal matching, volume_one, volume_one_series_name, volumes

            dirname = os.path.dirname(root)
            basename = os.path.basename(root)
            result = False

            if not volumes:
                print("\t\t\t\tno volumes detected for folder rename.")
                return

            # Sort volumes by name
            volumes.sort(key=lambda x: x.name)
            first_volume = volumes[0]

            if not first_volume.series_name:
                print(
                    f"\t\t\t\t{first_volume.name} does not have a series name, skipping..."
                )
                return result

            # Find volumes with matching series_name
            matching = [
                v
                for v in volumes[1:]
                if v.series_name.lower() == first_volume.series_name.lower()
                or similar(
                    clean_str(v.series_name),
                    clean_str(first_volume.series_name),
                )
                >= required_similarity_score
            ]

            if (not matching and len(volumes) == 1) or (
                len(matching) + 1 >= len(volumes) * 0.8 and len(volumes) > 1
            ):
                volume_one = volumes[0]
            else:
                print(
                    f"\t\t\t\t{len(matching)} out of {len(volumes)} volumes match the first volume's series name."
                )
                return result

            # Set the series_name for use by the backup renamer, if needed
            if volume_one.series_name:
                volume_one_series_name = volume_one.series_name

                # Series name is the same as the current folder name, skip
                if volume_one.series_name == basename:
                    print(
                        f"\t\t\t\t{volume_one.series_name} is the same as the current folder name, skipping..."
                    )
                    return result

            if not (
                similar(
                    remove_brackets(volume_one.series_name),
                    remove_brackets(basename),
                )
                >= 0.25
                or similar(volume_one.series_name, basename) >= 0.25
            ):
                print(
                    f"\t\t\t\t{volume_one.series_name} is not similar enough to {basename}, skipping..."
                )
                return result

            send_message(
                f"\n\tBEFORE: {basename}\n\tAFTER:  {volume_one.series_name}",
                discord=False,
            )

            print("\t\tFILES:")
            for v in volumes:
                print(f"\t\t\t{v.name}")

            user_input = (
                get_input_from_user("\tRename", ["y", "n"], ["y", "n"])
                if manual_rename
                else "y"
            )

            if user_input != "y":
                send_message("\t\tSkipping...\n", discord=False)
                return result

            new_folder = os.path.join(dirname, volume_one.series_name)

            # New folder doesn't exist, rename to it
            if not os.path.exists(new_folder):
                new_folder_path = rename_folder(root, new_folder)

                if watchdog_toggle:
                    # Update any old paths with the new path
                    transferred_files = [
                        (
                            f.replace(
                                os.path.join(dirname, basename),
                                os.path.join(dirname, volume_one.series_name),
                            )
                            if f.startswith(os.path.join(dirname, basename))
                            else f
                        )
                        for f in transferred_files
                    ]

                    # Add the new folder to transferred dirs
                    transferred_dirs.append(create_folder_obj(new_folder_path))

                result = True
            else:
                # New folder exists, move files to it
                for v in volumes:
                    target_file_path = os.path.join(new_folder, v.name)

                    # File doesn't exist in the new folder, move it
                    if not os.path.isfile(target_file_path):
                        move_file(v, new_folder)

                        if watchdog_toggle:
                            transferred_files.append(target_file_path)
                    else:
                        # File exists in the new folder, delete the one that would've been moved
                        print(
                            f"\t\t\t\t{v.name} already exists in {volume_one.series_name}"
                        )
                        remove_file(v.path, silent=True)

                    if watchdog_toggle and v.path in transferred_files:
                        transferred_files.remove(v.path)
                result = True

            check_and_delete_empty_folder(volumes[0].root)
            return result

        # Backup: Rename by just removing excess brackets from the folder name
        def rename_based_on_brackets(root):
            nonlocal matching, volume_one, volume_one_series_name, volumes
            global transferred_dirs, transferred_files

            # Cleans up the folder name
            def clean_folder_name(folder_name):
                folder_name = get_series_name(folder_name)  # start with the folder name
                folder_name = re.sub(r"([A-Za-z])(_)", r"\1 ", folder_name)  # A_ -> A
                folder_name = re.sub(
                    r"([A-Za-z])(\:)", r"\1 -", folder_name  # A: -> A -
                )
                folder_name = folder_name.replace("?", "")  # remove question marks
                folder_name = remove_dual_space(
                    folder_name
                ).strip()  # remove dual spaces
                return folder_name

            # Searches for a matching regex in the folder name
            def search_for_regex_in_folder_name(folder_name):
                searches = [
                    r"((\s\[|\]\s)|(\s\(|\)\s)|(\s\{|\}\s))",
                    r"(\s-\s|\s-)$",
                    r"(\bLN\b)",
                    r"(\b|\s)((\s|)-(\s|)|)(Part|)(%s|)(\.|)([-_. ]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\b|\s)"
                    % volume_regex_keywords,
                    r"\bPremium\b",
                    r":",
                    r"([A-Za-z])(_)",
                    r"([?])",
                ]
                return any(
                    re.search(search, folder_name, re.IGNORECASE) for search in searches
                )

            result = False
            dirname = os.path.dirname(root)
            basename = os.path.basename(root)

            if not search_for_regex_in_folder_name(basename):
                print(
                    f"\t\t\t\t{basename} does not match any of the regex searches, skipping..."
                )
                return result

            # Cleanup the folder name
            dir_clean = clean_folder_name(basename)

            if not dir_clean:
                print(f"\t\t\t\t{basename} was cleaned to nothing, skipping...")
                return result

            if dir_clean == basename:
                print(
                    f"\t\t\t\t{basename} is the same as the current folder name, skipping..."
                )
                return result

            new_folder_path = os.path.join(dirname, dir_clean)

            # New folder doesn't exist, rename to it
            if not os.path.isdir(new_folder_path):
                send_message(
                    f"\n\tBEFORE: {basename}",
                    discord=False,
                )
                send_message(f"\tAFTER:  {dir_clean}", discord=False)

                user_input = (
                    get_input_from_user("\tRename", ["y", "n"], ["y", "n"])
                    if manual_rename
                    else "y"
                )

                if user_input != "y":
                    send_message(
                        "\t\tSkipping...\n",
                        discord=False,
                    )
                    return result

                new_folder_path_two = rename_folder(
                    os.path.join(
                        dirname,
                        basename,
                    ),
                    os.path.join(
                        dirname,
                        dir_clean,
                    ),
                )

                if watchdog_toggle:
                    # Update any old paths with the new path
                    transferred_files = [
                        (
                            f.replace(os.path.join(dirname, basename), new_folder_path)
                            if f.startswith(os.path.join(dirname, basename))
                            else f
                        )
                        for f in transferred_files
                    ]

                    # Add the new folder to transferred dirs
                    transferred_dirs.append(create_folder_obj(new_folder_path_two))
            else:
                # New folder exists, move files to it
                for root, dirs, files in scandir.walk(root):
                    folder_accessor_two = create_folder_obj(
                        root,
                        dirs,
                        upgrade_to_file_class(
                            remove_hidden_files(files), root, clean=True
                        ),
                    )

                    for file in folder_accessor_two.files:
                        new_location_folder = os.path.join(
                            dirname,
                            dir_clean,
                        )
                        new_file_path = os.path.join(
                            new_location_folder,
                            file.name,
                        )
                        # New file doesn't exist in the new folder, move it
                        if not os.path.isfile(new_file_path):
                            move_file(
                                file,
                                new_location_folder,
                            )
                        else:
                            # File exists in the new folder, delete the one that would've been moved
                            send_message(
                                f"File: {file.name} already exists in: {new_location_folder}\nRemoving duplicate from downloads.",
                                error=True,
                            )
                            remove_file(file.path, silent=True)

                    check_and_delete_empty_folder(root)
            return result

        # Get all the paths
        folders = get_all_folders_recursively_in_dir(download_folder)

        # Reverse the list so we start with the deepest folders
        # Helps when purging empty folders, since it won't purge a folder containing subfolders
        folders.reverse()

        for folder in folders:
            root = folder["root"]
            dirs = folder["dirs"]
            files = folder["files"]

            if not os.path.isdir(root):
                continue

            if root in download_folders:
                continue

            if watchdog_toggle and root not in [item.root for item in transferred_dirs]:
                continue

            try:
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )

                volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(files, root), root
                )

                matching = []
                dirname = os.path.dirname(root)
                basename = os.path.basename(root)
                done = False
                volume_one = None
                volume_one_series_name = None

                # Main: Rename based on common series_name from volumes
                if volumes:
                    done = rename_based_on_volumes(root)
                if (
                    not done
                    and (
                        not volume_one_series_name or volume_one_series_name != basename
                    )
                    and dirname in download_folders
                    and not re.search(basename, root, re.IGNORECASE)
                ):
                    done = rename_based_on_brackets(root)
            except Exception as e:
                send_message(
                    f"Error renaming folder: {e}",
                    error=True,
                )
            check_and_delete_empty_folder(root)

    print("\nLooking for folders to rename...")
    print("\tDownload Paths:")
    for path in paths_to_process:
        print(f"\t\t{path}")
        if not os.path.exists(path):
            if not path:
                send_message(
                    "No download folders specified, skipping renaming folders...",
                    error=True,
                )
            else:
                send_message(
                    f"Download folder {path} does not exist, skipping renaming folders...",
                    error=True,
                )
            continue
        process_folder(path)


# Retrieves any bracketed information in the name that isn't the release year.
def get_extras(file_name, chapter=False, series_name="", subtitle=""):
    # Helper function to remove matching patterns from text
    def remove_matching(text, pattern):
        return re.sub(
            rf"\b{re.escape(pattern)}\b", "", text, flags=re.IGNORECASE
        ).strip()

    # Helper function to extract unique patterns from text
    def extract_unique_patterns(text):
        results = re.findall(
            r"((?:\{|\(|\[).*?(?:\]|\)|\}))", text, flags=re.IGNORECASE
        )
        return results

    # Helper function to remove specific patterns from a list
    def remove_patterns(items, patterns):
        pattern_combined_regex = "|".join(patterns)
        items = [
            item
            for item in items
            if not re.search(pattern_combined_regex, item, re.IGNORECASE)
        ]
        return items

    # Get the file extension
    extension = get_file_extension(file_name)

    # Remove series name and subtitle if provided
    if series_name:
        file_name = remove_matching(file_name, series_name)

    if subtitle:
        file_name = remove_matching(file_name, subtitle)

    # Extract unique patterns from the file name
    results = extract_unique_patterns(file_name)

    # Define patterns and exclude patterns for removal
    patterns = [
        r"((\{|\(|\[)(Premium|J-Novel Club Premium)(\]|\)|\}))",
        r"(\((\d{4})\))",
    ]

    if chapter:
        patterns.append(r"((\{|\(|\[)Part([-_. ]|)([0-9]+)(\]|\)|\}))")

    # Remove specified patterns from the results
    results = remove_patterns(results, patterns)

    # Generate file extension modifiers for keywords
    modifiers = {
        ext: (
            "[%s]"
            if ext in novel_extensions
            else "(%s)" if ext in manga_extensions else ""
        )
        for ext in file_extensions
    }

    # Check for and add "Part" patterns to the results
    part_search = (
        re.search(r"(\s|\b)Part([-_. ]|)([0-9]+)", file_name, re.IGNORECASE)
        if "part" in file_name.lower()
        else None
    )
    if part_search:
        result = part_search.group()
        modified_result = modifiers[extension] % result.strip()
        if modified_result not in results:
            results.append(modified_result)

    # Check for and add keywords to the results
    if "premium" in file_name.lower():
        modified_keyword = modifiers[extension] % "Premium"
        if modified_keyword not in results:
            results.append(modified_keyword)

    premium_items, non_premium_items = [], []
    modified = results.copy()
    for item in modified:
        if "premium" in item.lower():
            premium_items.append(item)
        else:
            non_premium_items.append(item)

    return premium_items + non_premium_items


# Check if the input value can be converted to a float
def isfloat(x):
    try:
        a = float(x)
    except (TypeError, ValueError):
        return False
    else:
        return True


# Check if the input value can be converted to an integer
def isint(x):
    try:
        a = float(x)
        b = int(a)
    except (TypeError, ValueError):
        return False
    else:
        return a == b


# check if zip file contains ComicInfo.xml
@lru_cache(maxsize=None)
def contains_comic_info(zip_file):
    result = False
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            if "comicinfo.xml" in map(str.lower, zip_ref.namelist()):
                result = True
    except (zipfile.BadZipFile, FileNotFoundError) as e:
        send_message(f"\tFile: {zip_file}\n\t\tERROR: {e}", error=True)
    return result


# Retrieve the file specified from the zip file and return the data for it.
def get_file_from_zip(zip_file, searches, extension=None, allow_base=True):
    result = None
    try:
        with zipfile.ZipFile(zip_file, "r") as z:
            # Filter out any item that doesn't end in the specified extension
            file_list = [
                item
                for item in z.namelist()
                if item.endswith(extension) or not extension
            ]

            # Interate through it
            for path in file_list:
                # if allow_base, then change it to the base name of the file
                # otherwise purge the base name
                mod_file_name = (
                    os.path.basename(path).lower()
                    if allow_base
                    else (
                        re.sub(os.path.basename(path), "", path).lower()
                        if re.sub(os.path.basename(path), "", path).lower()
                        else path.lower()
                    )
                )
                found = any(
                    (
                        item
                        for item in searches
                        if re.search(item, mod_file_name, re.IGNORECASE)
                    ),
                )
                if found:
                    result = z.read(path)
                    break
    except (zipfile.BadZipFile, FileNotFoundError) as e:
        send_message(f"Attempted to read file: {zip_file}\nERROR: {e}", error=True)
    return result


# dynamically parse all tags from comicinfo.xml and return a dictionary of the tags
def parse_comicinfo_xml(xml_file):
    tags = {}
    if xml_file:
        try:
            tree = ET.fromstring(xml_file)
            tags = {child.tag: child.text for child in tree}
        except Exception as e:
            send_message(
                f"Attempted to parse comicinfo.xml: {xml_file}\nERROR: {e}",
                error=True,
            )
            return tags
    return tags


# dynamically parse all html tags and values and return a dictionary of them
def parse_html_tags(html):
    soup = BeautifulSoup(html, "html.parser")
    tags = {tag.name: tag.get_text() for tag in soup.find_all(True)}
    return tags


# Renames files.
def rename_files(
    only_these_files=[], download_folders=download_folders, test_mode=False
):
    global transferred_files, grouped_notifications

    print("\nSearching for files to rename...")

    if not download_folders:
        print("\tNo download folders specified, skipping renaming files...")
        return

    for path in download_folders:
        if not os.path.exists(path):
            send_message(
                f"\tDownload folder {path} does not exist, skipping...",
                error=True,
            )
            continue

        for root, dirs, files in scandir.walk(path):
            if test_mode:
                if root not in download_folders:
                    return

                dirs = []
                files = only_these_files

            files, dirs = process_files_and_folders(
                root,
                files,
                dirs,
                just_these_files=transferred_files,
                just_these_dirs=transferred_dirs,
                test_mode=test_mode,
            )

            if not files:
                continue

            volumes = upgrade_to_volume_class(
                upgrade_to_file_class(
                    [
                        f
                        for f in files
                        if os.path.isfile(os.path.join(root, f)) or test_mode
                    ],
                    root,
                    test_mode=test_mode,
                ),
                test_mode=test_mode,
            )

            if not volumes:
                continue

            print(f"\t{root}")
            for file in volumes:
                if "_extra" in file.name and ".5" in str(file.volume_number):
                    # remove .5 from the volume number and index_number
                    file.volume_number = int(file.volume_number)
                    file.index_number = int(file.index_number)
                if test_mode:
                    print(f"\t\t[{volumes.index(file) + 1}/{len(volumes)}] {file.name}")

                if (
                    file.file_type == "chapter"
                    and not rename_chapters_with_preferred_chapter_keyword
                ):
                    continue

                no_keyword = False
                preferred_naming_format = preferred_volume_renaming_format
                keywords = volume_regex_keywords
                zfill_int = zfill_volume_int_value
                zfill_float = zfill_volume_float_value

                if file.file_type == "chapter":
                    keywords = chapter_regex_keywords
                    preferred_naming_format = preferred_chapter_renaming_format
                    zfill_int = zfill_chapter_int_value
                    zfill_float = zfill_chapter_float_value

                if only_these_files and file.name not in only_these_files:
                    continue

                try:
                    # Append 巻 to each extension and join them with |
                    file_extensions_with_prefix = "".join(
                        [f"巻?{re.escape(x)}|" for x in file_extensions]
                    )[:-1]

                    keyword_regex = (
                        r"(\s+)?\-?(\s+)?((%s)%s)(\.\s?|\s?|)([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?(\]|\)|\})?(\s|%s)"
                        % (
                            subtitle_exclusion_keywords_regex if file.subtitle else "",
                            keywords,
                            file_extensions_with_prefix,
                        )
                    )

                    result = re.search(
                        keyword_regex,
                        file.name,
                        re.IGNORECASE,
                    )

                    # chapter match is allwoed to continue
                    full_chapter_match_attempt_allowed = False

                    # The number of the regex inside the regex array that was matched to
                    regex_match_number = None

                    if result:
                        full_chapter_match_attempt_allowed = True
                    elif (
                        not result
                        and file.file_type == "chapter"
                        and (
                            (
                                file.volume_number
                                and (
                                    extract_all_numbers(
                                        file.name, subtitle=file.subtitle
                                    ).count(file.volume_number)
                                    == 1
                                )
                            )
                            or has_one_set_of_numbers(
                                remove_brackets(
                                    re.sub(
                                        r"((\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})\s?){2,}.*",
                                        "",
                                        re.sub(
                                            rf"^{re.escape(file.series_name)}",
                                            "",
                                            file.name,
                                            flags=re.IGNORECASE,
                                        ),
                                        flags=re.IGNORECASE,
                                    )
                                ),
                                chapter=True,
                                file=file,
                                subtitle=file.subtitle,
                            )
                        )
                    ):
                        full_chapter_match_attempt_allowed = True

                    if file.file_type == "chapter" and not result:
                        searches = []

                        if full_chapter_match_attempt_allowed:
                            searches = chapter_searches
                        else:
                            # only include the first search
                            searches = [chapter_searches[0]]

                        for regex in searches:
                            result = re.search(
                                regex,
                                remove_dual_space(
                                    file.name.replace("_extra", "")
                                ).strip(),
                                re.IGNORECASE,
                            )

                            if result:
                                regex_match_number = searches.index(regex)
                                result = chapter_file_name_cleaning(
                                    result.group(),
                                    skip=True,
                                    regex_matched=regex_match_number,
                                )

                                if result:
                                    chapter_num_search = None
                                    converted_num = (
                                        set_num_as_float_or_int(file.volume_number)
                                        if isinstance(file.volume_number, list)
                                        else file.volume_number
                                    )

                                    if converted_num != "":
                                        if "-" in str(converted_num):
                                            # split the string by the dash
                                            split = converted_num.split("-")
                                            new_split = [f"(0+)?{s}" for s in split]
                                            if new_split:
                                                converted_num = "-".join(new_split)
                                                search = re.search(
                                                    converted_num, file.name
                                                )
                                                if search:
                                                    chapter_num_search = search
                                        else:
                                            chapter_num_search = re.search(
                                                str(converted_num), file.name
                                            )

                                    if chapter_num_search:
                                        result = chapter_num_search.group()
                                    else:
                                        result = None

                                    if result:
                                        if re.search(r"(\d+_\d+)", result):
                                            result = result.replace("_", ".")

                                    if result:
                                        # check that the string is a float or int
                                        split = None

                                        if "-" in result:
                                            split = result.split("-")
                                            count = sum(
                                                1
                                                for s in split
                                                if set_num_as_float_or_int(s) != ""
                                            )
                                            if count != len(split):
                                                result = None
                                        elif set_num_as_float_or_int(result) == "":
                                            result = None
                                break

                    if result or (
                        file.is_one_shot and add_volume_one_number_to_one_shots
                    ):
                        if file.is_one_shot:
                            result = (
                                f"{preferred_naming_format}{str(1).zfill(zfill_int)}"
                            )
                        elif not isinstance(result, str):
                            result = result.group().strip()

                        # EX: "- c009" -> "c009"
                        if result.startswith("-"):
                            result = result[1:]

                        result = re.sub(
                            r"([\[\(\{\]\)\}]|((?<!\d+)_(?!\d+)))", "", result
                        ).strip()
                        keyword = re.search(
                            r"(%s)" % keywords,
                            result,
                            re.IGNORECASE,
                        )

                        if keyword:
                            keyword = keyword.group()
                            result = re.sub(
                                rf"(-)(\s+)?{keyword}",
                                keyword,
                                result,
                                flags=re.IGNORECASE,
                                count=1,
                            ).strip()
                        elif file.file_type == "chapter" and result:
                            no_keyword = True
                        else:
                            continue

                        extensions_pattern = "|".join(
                            re.escape(ext) for ext in file_extensions
                        )
                        result = re.sub(extensions_pattern, "", result).strip()
                        results = re.split(
                            r"(%s)(\.|)" % keywords,
                            result,
                            flags=re.IGNORECASE,
                        )
                        modified = []

                        for r in results[:]:
                            if r:
                                r = r.strip()

                            if r == "" or r == "." or r == None:
                                results.remove(r)
                            else:
                                found = re.search(
                                    r"([0-9]+)((([-_.])([0-9]+))+|)",
                                    r,
                                    re.IGNORECASE,
                                )
                                if found:
                                    r = found.group()
                                    if file.multi_volume:
                                        volume_numbers = get_min_and_max_numbers(r)
                                        for number in volume_numbers:
                                            modified.append(number)
                                            if number != volume_numbers[-1]:
                                                modified.append("-")
                                    else:
                                        try:
                                            if isint(r) and not re.search(
                                                r"(\.\d+$)", str(r)
                                            ):
                                                r = int(r)
                                                modified.append(r)
                                            elif isfloat(r):
                                                r = float(r)
                                                modified.append(r)
                                        except ValueError as ve:
                                            send_message(str(ve), error=True)
                                if r and isinstance(r, str):
                                    if re.search(
                                        r"(%s)" % keywords,
                                        r,
                                        re.IGNORECASE,
                                    ):
                                        modified.append(
                                            re.sub(
                                                r"(%s)" % keywords,
                                                preferred_naming_format,
                                                r,
                                                flags=re.IGNORECASE,
                                            )
                                        )
                        if (
                            ((len(modified) == 2 and len(results) == 2))
                            or (len(modified) == 1 and len(results) == 1 and no_keyword)
                        ) or (
                            file.multi_volume
                            and (len(modified) == len(results) + len(volume_numbers))
                        ):
                            combined = ""

                            for item in modified:
                                if isinstance(item, (int, float)):
                                    if item < 10 or (
                                        file.file_type == "chapter" and item < 100
                                    ):
                                        fill_type = (
                                            zfill_int
                                            if isinstance(item, int)
                                            else zfill_float
                                        )
                                        combined += str(item).zfill(fill_type)
                                    else:
                                        combined += str(item)
                                elif isinstance(item, str):
                                    combined += item

                            without_keyword = re.sub(
                                r"(%s)(\.|)" % keywords,
                                "",
                                combined,
                                flags=re.IGNORECASE,
                            )
                            if (
                                file.extension in manga_extensions
                                and add_issue_number_to_manga_file_name
                                and file.file_type == "volume"
                            ):
                                combined += f" #{without_keyword}"

                            if not file.is_one_shot:
                                converted_value = re.sub(
                                    keywords, "", combined, flags=re.IGNORECASE
                                )

                                if "-" not in converted_value:
                                    converted_value = set_num_as_float_or_int(
                                        converted_value,
                                        silent=True,
                                    )
                                else:
                                    converted_value = ""

                                converted_and_filled = None

                                if converted_value != "":
                                    if isinstance(converted_value, (int, float)):
                                        if converted_value < 10 or (
                                            file.file_type == "chapter"
                                            and converted_value < 100
                                        ):
                                            if isinstance(converted_value, int):
                                                converted_and_filled = str(
                                                    converted_value
                                                ).zfill(zfill_int)
                                            elif isinstance(converted_value, float):
                                                converted_and_filled = str(
                                                    converted_value
                                                ).zfill(zfill_float)
                                        elif converted_value >= 100:
                                            converted_and_filled = converted_value

                                if not no_keyword:
                                    replacement = re.sub(
                                        r"((?<![A-Za-z]+)|)(\[|\(|\{)?(?<![A-Za-z])(%s)(\.|)([-_. ]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s#(([0-9]+)((([-_.]|)([0-9]+))+|)))?(\]|\)|\})?"
                                        % keywords,
                                        combined,
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )
                                elif (
                                    converted_value == file.volume_number
                                    and converted_and_filled
                                ):
                                    optional_following_zero = rf"\b({str(exclusion_keywords_regex)})(0+)?{str(converted_value)}(\b|(?=x|#))"

                                    # Gets rid of unwanted "#"
                                    # EX: 'Tower of God - #404 - [Season 2] Ep. 324.cbz'
                                    if (
                                        file.file_type == "chapter"
                                        and regex_match_number == 0
                                    ):
                                        optional_following_zero = (
                                            rf"(#)?{optional_following_zero}"
                                        )

                                    # remove the file.series_name from file.name, and everything to the left of it, store it in a variable
                                    without_series_name = re.sub(
                                        rf"^{re.escape(file.series_name)}",
                                        "",
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )

                                    # remove the end brackets and anything after them.
                                    without_end_brackets = re.sub(
                                        r"((\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})\s?){2,}.*",
                                        "",
                                        without_series_name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )

                                    without_brackets_replacement = re.sub(
                                        optional_following_zero,
                                        f" {preferred_naming_format}{converted_and_filled}",
                                        remove_dual_space(
                                            without_end_brackets.replace("_extra", ".5")
                                        ),
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )

                                    # now replace without_brackets_replacement into without_series_name
                                    without_series_name_replacement = re.sub(
                                        re.escape(without_end_brackets),
                                        without_brackets_replacement,
                                        without_series_name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )

                                    # now re.sub without_series_name_replacement into file.name
                                    replacement = re.sub(
                                        re.escape(without_series_name),
                                        without_series_name_replacement,
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )
                                    replacement = remove_dual_space(replacement).strip()
                                else:
                                    replacement = re.sub(
                                        r"((?<![A-Za-z]+)|)(\[|\(|\{)?(?<![A-Za-z])(%s)(\.|)([-_. ]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s#(([0-9]+)((([-_.]|)([0-9]+))+|)))?(\]|\)|\})?"
                                        % "",
                                        f" {preferred_naming_format}{combined}",
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )
                                    replacement = remove_dual_space(replacement)
                            else:
                                base = re.sub(
                                    r"(%s)" % file_extensions_regex,
                                    "",
                                    file.basename,
                                    flags=re.IGNORECASE,
                                ).strip()

                                replacement = f"{base} {combined}"

                                if file.volume_year:
                                    replacement += f" ({file.volume_year})"

                                extras = (
                                    get_extras(
                                        file.name,
                                        series_name=file.series_name,
                                        subtitle=file.subtitle,
                                    )
                                    if file.file_type != "chapter"
                                    else get_extras(
                                        file.name,
                                        chapter=True,
                                        series_name=file.series_name,
                                        subtitle=file.subtitle,
                                    )
                                )

                                # Add the extras to the replacement
                                replacement += " ".join([""] + extras)

                                # Add the extension back
                                replacement += file.extension

                            # Remove question marks from the replacement
                            replacement = replacement.replace("?", "").strip()

                            # Remove any extra spaces
                            replacement = remove_dual_space(
                                replacement.replace("_", " ")
                            ).strip()

                            # replace : with - in dir_clean
                            replacement = re.sub(
                                r"([A-Za-z])(\:|：)", r"\1 -", replacement
                            )

                            # remove dual spaces from dir_clean
                            replacement = remove_dual_space(replacement)
                            processed_files.append(replacement)

                            if file.name != replacement:
                                if test_mode:
                                    write_to_file(
                                        "test_renamed_files.txt",
                                        f"{file.name} -> {replacement}",
                                        without_timestamp=True,
                                    )
                                    continue

                                if watchdog_toggle:
                                    transferred_files.append(
                                        os.path.join(file.root, replacement)
                                    )
                                try:
                                    if not (
                                        os.path.isfile(os.path.join(root, replacement))
                                    ):
                                        send_message(
                                            f"\n\t\tBEFORE: {file.name}",
                                            discord=False,
                                        )
                                        send_message(
                                            f"\t\tAFTER:  {replacement}",
                                            discord=False,
                                        )

                                        user_input = user_input = (
                                            get_input_from_user(
                                                "\t\tRename", ["y", "n"], ["y", "n"]
                                            )
                                            if manual_rename
                                            else "y"
                                        )

                                        if user_input == "y":
                                            try:
                                                rename_file(
                                                    file.path,
                                                    os.path.join(root, replacement),
                                                    silent=True,
                                                )
                                                # remove old item from list
                                                if file.path in transferred_files:
                                                    transferred_files.remove(file.path)

                                            except OSError as e:
                                                send_message(
                                                    f"{e}\nError renaming file: {file.name} to {replacement}",
                                                    error=True,
                                                )
                                            if os.path.isfile(
                                                os.path.join(root, replacement)
                                            ):
                                                send_message(
                                                    "\t\t\tSuccessfully renamed file.",
                                                    discord=False,
                                                )
                                                if (
                                                    not mute_discord_rename_notifications
                                                ):
                                                    embed = handle_fields(
                                                        DiscordEmbed(
                                                            title="Renamed File",
                                                            color=grey_color,
                                                        ),
                                                        fields=[
                                                            {
                                                                "name": "From",
                                                                "value": f"```{file.name}```",
                                                                "inline": False,
                                                            },
                                                            {
                                                                "name": "To",
                                                                "value": f"```{replacement}```",
                                                                "inline": False,
                                                            },
                                                        ],
                                                    )
                                                    grouped_notifications = (
                                                        group_notification(
                                                            grouped_notifications,
                                                            Embed(embed, None),
                                                        )
                                                    )
                                                # Replaces the file object with an updated one with the replacement values
                                                volume_index = volumes.index(file)
                                                file = upgrade_to_volume_class(
                                                    upgrade_to_file_class(
                                                        [replacement], file.root
                                                    )
                                                )[0]
                                                # replace it in the volumes array
                                                volumes[volume_index] = file
                                            else:
                                                send_message(
                                                    f"\n\tRename failed on: {file.name}",
                                                    error=True,
                                                )
                                        else:
                                            send_message(
                                                "\t\t\tSkipping...\n", discord=False
                                            )
                                    else:
                                        # if it already exists, then delete file.name
                                        send_message(
                                            f"\n\tFile already exists: {os.path.join(root, replacement)}"
                                            f"\n\t\twhen renaming: {file.name}"
                                            f"\n\tDeleting: {file.name}",
                                            discord=False,
                                        )
                                        remove_file(file.path, silent=True)
                                        continue
                                except OSError as ose:
                                    send_message(str(ose), error=True)
                            else:
                                if test_mode:
                                    write_to_file(
                                        "test_renamed_files.txt",
                                        f"{file.name} -> {replacement}",
                                        without_timestamp=True,
                                        check_for_dup=True,
                                    )
                                    continue
                        else:
                            send_message(
                                f"More than two for either array: {file.name}",
                                error=True,
                            )
                            print("Modified Array:")
                            for i in modified:
                                print(f"\t{i}")

                            print("Results Array:")
                            for b in results:
                                print(f"\t{b}")

                except Exception as e:
                    send_message(f"\nERROR: {e} ({file.name})", error=True)
                if resturcture_when_renaming and not test_mode:
                    reorganize_and_rename([file], file.series_name)


# Checks for any exception keywords that will prevent the chapter release from being deleted.
def check_for_exception_keywords(file_name, exception_keywords):
    pattern = "|".join(exception_keywords)
    return bool(re.search(pattern, file_name, re.IGNORECASE))


# Deletes chapter files from the download folder.
def delete_chapters_from_downloads():
    global grouped_notifications

    print("\nSearching for chapter files to delete...")

    if not download_folders:
        print("\tNo download folders specified, skipping deleting chapters...")

    try:
        for path in download_folders:
            if not os.path.exists(path):
                send_message(
                    f"Download folder {path} does not exist, skipping...",
                    error=True,
                )
                continue

            os.chdir(path)
            for root, dirs, files in scandir.walk(path):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    chapters=True,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )

                for file in files:
                    if (
                        contains_chapter_keywords(file)
                        and not contains_volume_keywords(file)
                    ) and not (check_for_exception_keywords(file, exception_keywords)):
                        if get_file_extension(file) in manga_extensions:
                            send_message(
                                f"\n\t\tFile: {file}"
                                f"\n\t\tLocation: {root}"
                                f"\n\t\tContains chapter keywords/lone numbers and does not contain any volume/exclusion keywords"
                                f"\n\t\tDeleting chapter release.",
                                discord=False,
                            )
                            embed = handle_fields(
                                DiscordEmbed(
                                    title="Chapter Release Found",
                                    color=grey_color,
                                ),
                                fields=[
                                    {
                                        "name": "File",
                                        "value": f"```{file}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "Location",
                                        "value": f"```{root}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "Checks",
                                        "value": "```"
                                        + "Contains chapter keywords/lone numbers ✓\n"
                                        + "Does not contain any volume keywords ✓\n"
                                        + "Does not contain any exclusion keywords ✓"
                                        + "```",
                                        "inline": False,
                                    },
                                ],
                            )
                            grouped_notifications = group_notification(
                                grouped_notifications, Embed(embed, None)
                            )
                            remove_file(os.path.join(root, file))
            for root, dirs, files in scandir.walk(path):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )
                for folder in dirs:
                    check_and_delete_empty_folder(os.path.join(root, folder))
    except Exception as e:
        send_message(str(e), error=True)


# Returns the path of the cover image for a novel file, if it exists.
def get_novel_cover_path(file):
    if file.extension not in novel_extensions:
        return ""

    novel_cover_path = get_novel_cover(file.path)
    if not novel_cover_path:
        return ""

    if get_file_extension(novel_cover_path) not in image_extensions:
        return ""

    return os.path.basename(novel_cover_path)


# Regular expressions to match cover patterns
cover_patterns = [
    r"(cover\.([A-Za-z]+))$",
    r"(\b(Cover([0-9]+|)|CoverDesign|page([-_. ]+)?cover)\b)",
    r"(\b(p000|page_000)\b)",
    r"((\s+)0+\.(.{2,}))",
    r"(\bindex[-_. ]1[-_. ]1\b)",
    r"(9([-_. :]+)?7([-_. :]+)?(8|9)(([-_. :]+)?[0-9]){10})",
]

# Pre-compiled regular expressions for cover patterns
compiled_cover_patterns = [
    re.compile(pattern, flags=re.IGNORECASE) for pattern in cover_patterns
]


# Finds and extracts the internal cover from a manga or novel file.
def find_and_extract_cover(
    file,
    return_data_only=False,
    silent=False,
    blank_image_check=compare_detected_cover_to_blank_images,
):
    # Helper function to filter and sort files in the zip archive
    def filter_and_sort_files(zip_list):
        return sorted(
            [
                x
                for x in zip_list
                if not x.endswith("/")
                and "." in x
                and get_file_extension(x) in image_extensions
                and not os.path.basename(x).startswith((".", "__"))
            ]
        )

    # Helper function to read image data from the zip file
    def get_image_data(image_path):
        with zip_ref.open(image_path) as image_file_ref:
            return image_file_ref.read()

    # Helper function to save image data to a file
    def save_image_data(image_path, image_data):
        with open(image_path, "wb") as image_file_ref_out:
            image_file_ref_out.write(image_data)

    # Helper function to process a cover image and save or return the data
    def process_cover_image(cover_path, image_data=None):
        image_extension = get_file_extension(os.path.basename(cover_path))
        if image_extension == ".jpeg":
            image_extension = ".jpg"

        if output_covers_as_webp and image_extension != ".webp":
            image_extension = ".webp"

        output_path = os.path.join(file.root, file.extensionless_name + image_extension)

        if not return_data_only:
            save_image_data(output_path, image_data)
            if compress_image_option:
                result = compress_image(output_path, image_quality)
                return result if result else output_path
            return output_path
        elif image_data:
            compressed_data = compress_image(output_path, raw_data=image_data)
            return compressed_data if compressed_data else image_data
        return None

    # Helper function to check if an image is blank
    def is_blank_image(image_data):
        ssim_score_white = prep_images_for_similarity(
            blank_white_image_path, image_data, silent=silent
        )
        ssim_score_black = prep_images_for_similarity(
            blank_black_image_path, image_data, silent=silent
        )

        return (
            ssim_score_white is not None
            and ssim_score_black is not None
            and (
                ssim_score_white >= blank_cover_required_similarity_score
                or ssim_score_black >= blank_cover_required_similarity_score
            )
        )

    # Check if the file exists
    if not os.path.isfile(file.path):
        send_message(f"\nFile: {file.path} does not exist.", error=True)
        return None

    # Check if the input file is a valid zip file
    if not zipfile.is_zipfile(file.path):
        send_message(f"\nFile: {file.path} is not a valid zip file.", error=True)
        return None

    # Get the novel cover path if the file has a novel extension
    novel_cover_path = (
        get_novel_cover_path(file) if file.extension in novel_extensions else ""
    )

    # Open the zip file
    with zipfile.ZipFile(file.path, "r") as zip_ref:
        # Filter and sort files in the zip archive
        zip_list = filter_and_sort_files(zip_ref.namelist())

        # Move the novel cover to the front of the list, if it exists
        if novel_cover_path:
            novel_cover_basename = os.path.basename(novel_cover_path)
            for i, item in enumerate(zip_list):
                if os.path.basename(item) == novel_cover_basename:
                    zip_list.pop(i)
                    zip_list.insert(0, item)
                    break

        # Set of blank images
        blank_images = set()

        # Iterate through the files in the zip archive
        for image_file in zip_list:
            # Check if the file matches any cover pattern
            for pattern in compiled_cover_patterns:
                image_basename = os.path.basename(image_file)
                is_novel_cover = novel_cover_path and image_basename == novel_cover_path

                if (
                    is_novel_cover
                    or pattern.pattern == image_basename
                    or pattern.search(image_basename)
                ):
                    # Check if the image is blank
                    if (
                        blank_image_check
                        and blank_white_image_path
                        and blank_black_image_path
                    ):
                        image_data = get_image_data(image_file)
                        if is_blank_image(image_data):
                            blank_images.add(image_file)
                            break
                    image_data = get_image_data(image_file)
                    result = process_cover_image(image_file, image_data)
                    if result:
                        return result

        # Find a non-blank default cover
        default_cover_path = None
        for test_file in zip_list:
            if test_file in blank_images:
                continue

            image_data = get_image_data(test_file)

            # Check if the user has enabled the option to compare detected covers to blank images
            if blank_image_check:
                if not is_blank_image(image_data):
                    default_cover_path = test_file
                    break
            else:
                default_cover_path = test_file
                break

        # Process the default cover if found
        if default_cover_path:
            image_data = get_image_data(default_cover_path)
            result = process_cover_image(default_cover_path, image_data)
            if result:
                return result

    return False


# Returns the highest volume number and volume part number of a release in a list of volume releases
@lru_cache(maxsize=None)
def get_highest_release(releases, is_chapter_directory=False):
    highest_num = ""

    if use_latest_volume_cover_as_series_cover and not is_chapter_directory:
        contains_empty_or_tuple_index_number = any(
            isinstance(item, (tuple, list)) or item == "" for item in releases
        )
        if contains_empty_or_tuple_index_number:
            for item in releases:
                if item == "" or item == [] or item is None:
                    continue

                number = item
                if isinstance(number, (int, float)):
                    if highest_num == "" or number > highest_num:
                        highest_num = number
                elif isinstance(number, (tuple, list)):
                    max_number = max(number)
                    if highest_num == "" or max_number > highest_num:
                        highest_num = max_number
        else:
            highest_num = max(releases)

    return highest_num


# Series covers that have been checked and can be skipped.
checked_series = []


# takes a time.time, gets the current time and prints the execution time,
def print_execution_time(start_time, function_name):
    print(f"\nExecution time for: {function_name}: {time.time() - start_time} seconds")


# Extracts the covers out from our manga and novel files.
def extract_covers(paths_to_process=paths):
    global checked_series, root_modification_times
    global series_cover_path

    # Finds the series cover image in the given folder
    def find_series_cover(folder_accessor, image_extensions):
        result = next(
            (
                os.path.join(folder_accessor.root, f"cover{ext}")
                for ext in image_extensions
                if os.path.exists(os.path.join(folder_accessor.root, f"cover{ext}"))
            ),
            None,
        )
        return result

    # Checks if the folder contains files with the same series name
    def check_same_series_name(files, required_percent=0.9):
        result = False

        if files:
            compare_series = clean_str(files[0].series_name, skip_bracket=True)
            file_count = len(files)
            required_count = int(file_count * required_percent)
            result = (
                sum(
                    clean_str(x.series_name, skip_bracket=True) == compare_series
                    for x in files
                )
                >= required_count
            )
        return result

    # Processes the volume paths based on the given parameters
    def process_volume_paths(
        files,
        root,
        copy_existing_volume_covers_toggle,
        is_chapter_directory,
        volume_paths,
        paths_with_types,
    ):
        base_name = None

        if copy_existing_volume_covers_toggle and is_chapter_directory:
            # Set the value of volume_paths
            if not volume_paths and paths_with_types:
                volume_paths = [
                    x
                    for x in paths_with_types
                    if "volume" in x.path_formats
                    and files[0].extension in x.path_extensions
                ]
                for v_path in volume_paths:
                    # Get all the folders in v_path.path
                    volume_series_folders = [
                        x for x in os.listdir(v_path.path) if not x.startswith(".")
                    ]
                    v_path.series_folders = volume_series_folders

            base_name = clean_str(os.path.basename(root))

        return base_name, volume_paths

    # Checks if the folder contains multiple volume ones
    def contains_multiple_volume_ones(
        files, use_latest_volume_cover_as_series_cover, is_chapter_directory
    ):
        result = False

        if not use_latest_volume_cover_as_series_cover or is_chapter_directory:
            volume_ones = sum(
                1
                for file in files
                if not file.is_one_shot
                and not file.volume_part
                and (
                    file.index_number == 1
                    or (isinstance(file.index_number, list) and 1 in file.index_number)
                )
            )
            result = volume_ones > 1
        return result

    if not paths_to_process:
        print("\nNo paths to process.")
        return

    print("\nLooking for covers to extract...")

    # Only volume defined paths in the paths_with_types list
    # Used for copying existing volume covers from a
    # volume library to a chapter library
    volume_paths = []

    # contains cleaned basenames of folders that have been moved
    moved_folder_names = (
        [
            clean_str(
                os.path.basename(x),
                skip_bracket=True,
                skip_underscore=True,
            )
            for x in moved_folders
        ]
        if moved_folders and copy_existing_volume_covers_toggle
        else []
    )

    # Iterate over each path
    for path in paths_to_process:
        if not os.path.exists(path):
            print(f"\nERROR: {path} is an invalid path.\n")
            continue

        checked_series = []
        os.chdir(path)

        # Traverse the directory tree rooted at the path
        for root, dirs, files in scandir.walk(path):
            if watchdog_toggle:
                if not moved_folder_names or (
                    clean_str(
                        os.path.basename(root),
                        skip_bracket=True,
                        skip_underscore=True,
                    )
                    not in moved_folder_names
                ):
                    root_mod_time = get_modification_date(root)
                    if root in root_modification_times:
                        # Modification time hasn't changed; continue to the next iteration
                        if root_modification_times[root] == root_mod_time:
                            continue
                        else:
                            # update the modification time for the root
                            root_modification_times[root] = root_mod_time
                    else:
                        # Store the modification time for the root
                        root_modification_times[root] = root_mod_time

            files, dirs = process_files_and_folders(
                root,
                files,
                dirs,
                just_these_files=transferred_files,
                just_these_dirs=transferred_dirs,
            )

            contains_subfolders = dirs

            global folder_accessor

            print(f"\nRoot: {root}")
            print(f"Files: {files}")

            if not files:
                continue

            # Upgrade files to file classes
            file_objects = upgrade_to_file_class(files, root)

            # Upgrade file objects to a volume classes
            volume_objects = upgrade_to_volume_class(
                file_objects,
                skip_release_year=True,
                skip_release_group=True,
                skip_extras=True,
                skip_publisher=True,
                skip_premium_content=True,
                skip_subtitle=True,
                skip_multi_volume=True,
            )

            # Create a folder accessor object
            folder_accessor = create_folder_obj(root, dirs, volume_objects)

            # Get the series cover
            series_cover_path = find_series_cover(folder_accessor, image_extensions)
            series_cover_extension = (
                get_file_extension(series_cover_path) if series_cover_path else ""
            )

            if series_cover_extension and (
                (output_covers_as_webp and series_cover_extension != ".webp")
                or (not output_covers_as_webp and series_cover_extension == ".webp")
            ):
                # Remove the existing series cover image
                remove_status = remove_file(series_cover_path, silent=True)
                if remove_status:
                    series_cover_path = ""

            # Set the directory type
            is_chapter_directory = folder_accessor.files[0].file_type == "chapter"

            # Check if all the series_name values are the same for all volumes
            same_series_name = check_same_series_name(folder_accessor.files)

            # Used when filtering the series_folders of each paths_with_types
            # by the first letter of a cleaned up name
            clean_basename, volume_paths = process_volume_paths(
                folder_accessor.files,
                folder_accessor.root,
                copy_existing_volume_covers_toggle,
                is_chapter_directory,
                volume_paths,
                paths_with_types,
            )

            # Get the highest volume number and part number
            highest_index_number = (
                get_highest_release(
                    tuple(
                        [
                            (
                                item.index_number
                                if not isinstance(item.index_number, list)
                                else tuple(item.index_number)
                            )
                            for item in folder_accessor.files
                        ]
                    ),
                    is_chapter_directory=is_chapter_directory,
                )
                if not is_chapter_directory
                else ""
            )

            if highest_index_number:
                print(f"\n\t\tHighest Index Number: {highest_index_number}")

            # Check if it contains multiple volume ones
            has_multiple_volume_ones = contains_multiple_volume_ones(
                folder_accessor.files,
                use_latest_volume_cover_as_series_cover,
                is_chapter_directory,
            )

            # Process cover extraction for each file
            [
                process_cover_extraction(
                    file,
                    has_multiple_volume_ones,
                    highest_index_number,
                    is_chapter_directory,
                    volume_paths,
                    clean_basename,
                    same_series_name,
                    contains_subfolders,
                )
                for file in folder_accessor.files
                if file.file_type == "volume"
                or (file.file_type == "chapter" and extract_chapter_covers)
            ]


# Converts the passed path of a .webp file to a .jpg file
# returns the path of the new .jpg file or none if the conversion failed
def convert_webp_to_jpg(webp_file_path):
    if webp_file_path:
        extenionless_webp_file = os.path.splitext(webp_file_path)[0]
        jpg_file_path = f"{extenionless_webp_file}.jpg"

        try:
            with Image.open(webp_file_path) as im:
                im.convert("RGB").save(jpg_file_path)
            # verify that the conversion worked
            if os.path.isfile(jpg_file_path):
                # delete the .webp file
                remove_file(webp_file_path, silent=True)
                # verify that the .webp file was deleted
                if not os.path.isfile(webp_file_path):
                    return jpg_file_path
                else:
                    send_message(
                        f"ERROR: Could not delete {webp_file_path}", error=True
                    )
            else:
                send_message(
                    f"ERROR: Could not convert {webp_file_path} to jpg", error=True
                )
        except Exception as e:
            send_message(
                f"Could not convert {webp_file_path} to jpg\nERROR: {e}",
                error=True,
            )
    return None


# Retrieves the modification date of the passed file path.
def get_modification_date(path):
    return os.path.getmtime(path)


# Handles the processing of cover extraction for a file.
def process_cover_extraction(
    file,
    has_multiple_volume_ones,
    highest_index_number,
    is_chapter_directory,
    volume_paths,
    clean_basename,
    same_series_name,
    contains_subfolders,
):
    global image_count, series_cover_path

    update_stats(file)

    # Gets the first word in the string.
    def get_first_word(input_string):
        words = input_string.split()
        if words:
            return words[0]
        else:
            return None

    # Filters a list of series folders by the first word of a string.
    def filter_series_by_first_word(filtered_series, first_word):
        return [
            folder
            for folder in filtered_series
            if clean_str(folder).lower().startswith(first_word)
        ]

    try:
        has_cover = False
        printed = False

        # Check if a cover image is already present
        cover = next(
            (
                f"{file.extensionless_path}{extension}"
                for extension in image_extensions
                if os.path.exists(f"{file.extensionless_path}{extension}")
            ),
            "",
        )

        cover_extension = get_file_extension(cover) if cover else ""

        # If the user has specified to output covers as .webp files and the cover is not a .webp file,
        # then we will remove the existing cover image so it can be replaced with a .webp file
        if cover_extension and (
            (output_covers_as_webp and cover_extension != ".webp")
            or (not output_covers_as_webp and cover_extension == ".webp")
        ):
            # Remove the existing cover image
            remove_status = remove_file(cover, silent=True)
            if remove_status:
                cover = ""

        if cover:
            # Cover image found
            has_cover = True
            image_count += 1
        else:
            # Cover image not found, try to find it and extract it
            if not printed:
                print(f"\n\tFile: {file.name}")
                printed = True

            print("\t\tFile does not have a cover.")
            result = find_and_extract_cover(file)

            if result:
                if result.endswith(".webp") and not output_covers_as_webp:
                    # Cover image is a .webp file, attempt to convert to .jpg
                    print("\t\tCover is a .webp file. Converting to .jpg...")
                    conversion_result = convert_webp_to_jpg(result)

                    if conversion_result:
                        # Cover image successfully converted to .jpg
                        print("\t\tCover successfully converted to .jpg")
                        result = conversion_result
                    else:
                        # Cover conversion failed, clean up the webp file
                        print("\t\tCover conversion failed.")
                        print("\t\tCleaning up webp file...")
                        remove_file(result, silent=True)

                        # Verify that the webp file was deleted
                        if not os.path.isfile(result):
                            print("\t\tWebp file successfully deleted.")
                        else:
                            print("\t\tWebp file could not be deleted.")

                        result = None
                else:
                    print("\t\tCover successfully extracted.\n")
                    has_cover = True
                    cover = result
                    image_count += 1
            else:
                print("\t\tCover not found.")

        if (
            file.file_type == "volume"
            and not is_chapter_directory
            and cover
            and series_cover_path
            and not has_multiple_volume_ones
            and (
                (
                    use_latest_volume_cover_as_series_cover
                    and is_same_index_number(
                        file.index_number, highest_index_number, allow_array_match=True
                    )
                )
                or (
                    not use_latest_volume_cover_as_series_cover
                    and (
                        file.index_number == 1
                        or (
                            isinstance(file.index_number, list)
                            and 1 in file.index_number
                        )
                    )
                )
            )
        ):
            # get the modification date of the series cover and the latest volume cover
            current_series_cover_modification_date = get_modification_date(
                series_cover_path
            )
            latest_volume_cover_modification_date = get_modification_date(cover)

            if (
                current_series_cover_modification_date
                and latest_volume_cover_modification_date
            ) and (
                current_series_cover_modification_date
                != latest_volume_cover_modification_date
            ):
                # if they don't match, then we will hash the series cover and the latest volume cover,
                # and if the hashes don't match, then we will replace the series cover with the latest volume cover
                if get_file_hash(series_cover_path) != get_file_hash(cover):
                    print(
                        "\t\tCurrent series cover does not match the appropriate volume cover."
                    )
                    print("\t\tRemoving current series cover...")
                    remove_file(series_cover_path, silent=True)

                    if not os.path.isfile(series_cover_path):
                        print("\t\tSeries cover successfully removed.\n")
                        series_cover_path = None
                    else:
                        print("\t\tSeries cover could not be removed.\n")
                else:
                    set_modification_date(
                        series_cover_path, latest_volume_cover_modification_date
                    )

        # Check the volume libaries for a matching series so the series cover can be copied
        # to the chapter library series folder
        if (
            file.root not in checked_series
            and volume_paths
            and is_chapter_directory
            and clean_basename
        ):
            for v_path in volume_paths:
                if not (hasattr(v_path, "series_folders") and v_path.series_folders):
                    continue

                filtered_series = v_path.series_folders

                first_word = get_first_word(
                    clean_basename
                )  # the first word of file.basename

                filtered_series = (
                    filter_series_by_first_word(filtered_series, first_word)
                    if first_word
                    else filtered_series
                )  # series that start with first_word

                for folder in filtered_series:
                    folder_path = os.path.join(v_path.path, folder)
                    clean_folder = clean_str(folder)

                    if not (
                        clean_folder == clean_basename
                        or similar(clean_folder, clean_basename)
                        >= required_similarity_score
                    ):
                        continue

                    volumes = upgrade_to_volume_class(
                        upgrade_to_file_class(
                            [
                                f
                                for f in [
                                    entry.name
                                    for entry in os.scandir(folder_path)
                                    if entry.is_file()
                                ]
                            ],
                            folder_path,
                            clean=True,
                        ),
                        skip_release_year=True,
                        skip_release_group=True,
                        skip_extras=True,
                        skip_publisher=True,
                        skip_premium_content=True,
                        skip_subtitle=True,
                        skip_multi_volume=True,
                    )

                    if not volumes:
                        continue

                    # sort the volumes by name
                    volumes = sort_volumes(volumes)

                    volume_one = (
                        next(
                            (
                                x
                                for x in volumes
                                if x.volume_number == 1
                                or (
                                    isinstance(x.volume_number, list)
                                    and 1 in x.volume_number
                                )
                            ),
                            None,
                        )
                    ) or volumes[0]

                    # find the image cover
                    cover_path = next(
                        (
                            f"{volume_one.extensionless_path}{extension}"
                            for extension in image_extensions
                            if os.path.isfile(
                                f"{volume_one.extensionless_path}{extension}"
                            )
                        ),
                        None,
                    )

                    volume_one_modification_date = (
                        get_modification_date(cover_path) if cover_path else None
                    )

                    if series_cover_path:
                        cover_modification_date = (
                            get_modification_date(series_cover_path)
                            if series_cover_path
                            else None
                        )

                        if cover_modification_date and volume_one_modification_date:
                            if cover_modification_date == volume_one_modification_date:
                                checked_series.append(file.root)
                                return

                            cover_hash = (
                                get_file_hash(series_cover_path)
                                if series_cover_path
                                else None
                            )
                            volume_one_hash = (
                                get_file_hash(cover_path) if series_cover_path else None
                            )

                            if (
                                cover_hash
                                and volume_one_hash
                                and cover_hash != volume_one_hash
                            ):
                                print(
                                    "\t\tCurrent series cover does not match the appropriate volume cover."
                                )
                                print("\t\tRemoving current series cover...")

                                remove_file(series_cover_path, silent=True)

                                if not os.path.isfile(series_cover_path):
                                    print("\t\tSeries cover successfully removed.\n")
                                    series_cover_path = None
                                else:
                                    print("\t\tSeries cover could not be removed.\n")

                                print("\t\tFound volume for series cover.")
                            else:
                                # set the modification date
                                set_modification_date(
                                    series_cover_path,
                                    volume_one_modification_date,
                                )

                    if not series_cover_path and cover_path:
                        cover_path_extension = get_file_extension(cover_path)
                        # copy the file to the series cover folder
                        series_cover_path = os.path.join(
                            file.root, f"cover{cover_path_extension}"
                        )

                        shutil.copy(
                            cover_path,
                            series_cover_path,
                        )

                        if os.path.isfile(series_cover_path):
                            print(
                                "\t\tCopied volume one cover from volume library as series cover."
                            )
                            # set the modification date of the series cover to match the volume cover
                            set_modification_date(
                                series_cover_path,
                                volume_one_modification_date,
                            )
                            checked_series.append(file.root)
                            return
                    else:
                        checked_series.append(file.root)
                        return
                else:
                    checked_series.append(file.root)

        if (
            not has_multiple_volume_ones
            and not contains_subfolders
            and not series_cover_path
            and file.root not in download_folders
            and has_cover
            and cover
            and (
                (
                    file.index_number == 1
                    and (
                        not use_latest_volume_cover_as_series_cover
                        or is_chapter_directory
                    )
                )
                or (
                    file.file_type == "volume"
                    and not is_chapter_directory
                    and use_latest_volume_cover_as_series_cover
                    and is_same_index_number(
                        file.index_number, highest_index_number, allow_array_match=True
                    )
                )
            )
            and same_series_name
        ):
            if not printed:
                print(f"\n\tFile: {file.name}")
                printed = True

            print("\t\tMissing series cover.")
            print("\t\tFound volume for series cover.")

            cover_extension = get_file_extension(os.path.basename(cover))
            cover_path = os.path.join(file.root, os.path.basename(cover))
            series_cover_path = os.path.join(file.root, f"cover{cover_extension}")

            if os.path.isfile(cover_path):
                shutil.copy(
                    cover_path,
                    series_cover_path,
                )
                print("\t\tCopied cover as series cover.")
                # set the creation and modification dates of the series cover to match the volume cover
                set_modification_date(
                    series_cover_path,
                    get_modification_date(cover_path),
                )
            else:
                print(f"\t\tCover does not exist at: {cover_path}")
    except Exception as e:
        send_message(
            f"\nERROR in extract_covers(): {e} with file: {file.name}",
            error=True,
        )


# Prints the collected stats about the paths/files that were processed.
def print_stats():
    print("\nFor all paths.")
    if file_counters:
        # get the total count from file_counters
        total_count = sum(
            [file_counters[extension] for extension in file_counters.keys()]
        )
        print(f"Total Files Found: {total_count}")
        for extension in file_counters.keys():
            count = file_counters[extension]
            if count > 0:
                print(f"\t{count} were {extension} files")
    print(f"\tof those we found that {image_count} had a cover image file.")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors:
            print(f"\t{error}")


# Deletes any file with an extension in unacceptable_keywords from the download_folders
def delete_unacceptable_files():
    global grouped_notifications

    print("\nSearching for unacceptable files...")

    if not download_folders:
        print(
            "\tNo download folders specified, skipping deleting unacceptable files..."
        )
        return

    if not unacceptable_keywords:
        print(
            "\tNo unacceptable keywords specified, skipping deleting unacceptable files..."
        )
        return

    try:
        for path in download_folders:
            if not os.path.exists(path):
                print(f"\nERROR: {path} is an invalid path.\n")
                continue

            os.chdir(path)
            for root, dirs, files in scandir.walk(path):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                    skip_remove_unaccepted_file_types=True,
                    keep_images_in_just_these_files=True,
                )
                for file in files:
                    file_path = os.path.join(root, file)
                    if not os.path.isfile(file_path):
                        continue

                    extension = get_file_extension(file)
                    for keyword in unacceptable_keywords:
                        unacceptable_keyword_search = re.search(
                            keyword, file, re.IGNORECASE
                        )
                        if unacceptable_keyword_search:
                            send_message(
                                f"\tUnacceptable: {unacceptable_keyword_search.group()} match found in {file}\n\t\tDeleting file from: {root}",
                                discord=False,
                            )
                            embed = handle_fields(
                                DiscordEmbed(
                                    title="Unacceptable Match Found",
                                    color=yellow_color,
                                ),
                                fields=[
                                    {
                                        "name": "Found Regex/Keyword Match",
                                        "value": f"```{unacceptable_keyword_search.group()}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "In",
                                        "value": f"```{file}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "Location",
                                        "value": f"```{root}```",
                                        "inline": False,
                                    },
                                ],
                            )
                            grouped_notifications = group_notification(
                                grouped_notifications,
                                Embed(embed, None),
                            )
                            remove_file(file_path)
                            break
            for root, dirs, files in scandir.walk(path):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )
                for folder in dirs:
                    check_and_delete_empty_folder(os.path.join(root, folder))
    except Exception as e:
        send_message(str(e), error=True)


class BookwalkerBook:
    def __init__(
        self,
        title,
        original_title,
        volume_number,
        part,
        date,
        is_released,
        price,
        url,
        thumbnail,
        book_type,
        description,
        preview_image_url,
    ):
        self.title = title
        self.original_title = original_title
        self.volume_number = volume_number
        self.part = part
        self.date = date
        self.is_released = is_released
        self.price = price
        self.url = url
        self.thumbnail = thumbnail
        self.book_type = book_type
        self.description = description
        self.preview_image_url = preview_image_url


class BookwalkerSeries:
    def __init__(self, title, books, book_count, book_type):
        self.title = title
        self.books = books
        self.book_count = book_count
        self.book_type = book_type


# our session objects, one for each domain
session_objects = {}


# Returns a session object for the given URL
def get_session_object(url):
    domain = urlparse(url).netloc.split(":")[0]
    if domain not in session_objects:
        # Create a new session object and set a default User-Agent header
        session_object = requests.Session()
        session_object.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
            }
        )
        session_objects[domain] = session_object
    return session_objects[domain]


# Makes a GET request to the given URL using a reusable session object,
# and returns a BeautifulSoup object representing the parsed HTML response.
def scrape_url(url, strainer=None, headers=None, cookies=None, proxy=None):
    try:
        session_object = get_session_object(url)

        # Create a dictionary of request parameters with only non-None values
        request_params = {
            "url": url,
            "headers": headers,
            "cookies": cookies,
            "proxies": proxy,
            "timeout": 10,
        }
        response = session_object.get(
            **{k: v for k, v in request_params.items() if v is not None}
        )

        # Raise an exception if the status code indicates rate limiting
        if response.status_code == 403:
            raise Exception("Too many requests, we're being rate-limited!")

        soup = None
        if strainer:
            # Use the strainer to parse only specific parts of the HTML document
            soup = BeautifulSoup(response.content, "lxml", parse_only=strainer)
        else:
            soup = BeautifulSoup(response.content, "lxml")

        return soup
    except requests.exceptions.RequestException as e:
        send_message(f"Error scraping URL: {e}", error=True)
        return None


# Groups all books with a matching title and book_type.
def get_all_matching_books(books, book_type, title):
    matching_books = []
    short_title = get_shortened_title(title)

    for book in books:
        short_title_two = get_shortened_title(book.title)
        if book.book_type == book_type and (
            book.title == title
            or (
                (
                    similar(clean_str(book.title), clean_str(title))
                    >= required_similarity_score
                )
                or (
                    (short_title and short_title_two)
                    and similar(
                        clean_str(short_title_two),
                        clean_str(short_title),
                    )
                    >= required_similarity_score
                )
            )
        ):
            matching_books.append(book)

    # remove them from books
    for book in matching_books:
        books.remove(book)

    return matching_books


# combine series in series_list that have the same title and book_type
def combine_series(series_list):
    combined_series = []

    for series in series_list:
        # Sort books by volume number
        series.books.sort(
            key=lambda x: (str(x.volume_number), str(x.part).strip().split(",")[0])
        )

        # Check if series can be combined with existing combined_series
        combined = False
        for combined_series_item in combined_series:
            if series.book_type == combined_series_item.book_type and (
                series.title.lower().strip()
                == combined_series_item.title.lower().strip()
                or similar(
                    clean_str(series.title).lower().strip(),
                    clean_str(combined_series_item.title).lower().strip(),
                )
                >= required_similarity_score
            ):
                combined_series_item.books.extend(series.books)
                combined_series_item.book_count = len(combined_series_item.books)
                combined = True
                break

        # If series cannot be combined, add it to combined_series
        if not combined:
            combined_series.append(series)

    return combined_series


# Gives the user a short version of the title, if a dash or colon is present.
# EX: Series Name - Subtitle -> Series Name
def get_shortened_title(title):
    shortened_title = ""
    if ("-" in title or ":" in title) and re.search(r"((\s+(-)|:)\s+)", title):
        shortened_title = re.sub(r"((\s+(-)|:)\s+.*)", "", title).strip()
    return shortened_title


# Extracts the subtitle from a title that contains a dash or colon.
# If replace is True, it removes the subtitle from the title.
# Example: get_subtitle_from_dash("Series Name - Subtitle", replace=True) -> "Series Name"
def get_subtitle_from_dash(title, replace=False):
    has_match = (
        re.search(r"((\s+(-)|:)\s+)", title) if ("-" in title or ":" in title) else None
    )
    if replace and has_match:
        return re.sub(r"(.*)((\s+(-)|:)\s+)", "", title)
    return has_match.group() if has_match else ""


# Extracts the subtitle from a file.name
# (year required in brackets at the end of the subtitle)
# EX: Sword Art Online v13 - Alicization Dividing [2018].epub -> Alicization Dividing
@lru_cache(maxsize=None)
def get_subtitle_from_title(file, publisher=None):
    subtitle = ""

    # remove the series name from the title
    without_series_name = re.sub(
        rf"^{re.escape(file.series_name)}", "", file.name, flags=re.IGNORECASE
    ).strip()

    # First Search
    dash_or_colon_search = get_subtitle_from_dash(without_series_name)

    # Second Search
    year_or_digital_search = re.search(
        r"([\[\{\(]((\d{4})|(Digital))[\]\}\)])",
        without_series_name,
        re.IGNORECASE,
    )

    # Third Search
    publisher_search = None
    if (
        publisher and (publisher.from_meta or publisher.from_name)
    ) and not year_or_digital_search:
        if publisher.from_meta:
            publisher_search = re.search(
                rf"([\[\{{\(\]])({publisher.from_meta})([\]\}}\)])",
                without_series_name,
                re.IGNORECASE,
            )
        if publisher.from_name and not publisher_search:
            publisher_search = re.search(
                rf"([\[\{{\(\]])({publisher.from_name})([\]\}}\)])",
                without_series_name,
                re.IGNORECASE,
            )

    if dash_or_colon_search and (year_or_digital_search or publisher_search):
        # remove everything to the left of the marker
        subtitle = re.sub(r"(.*)((\s+(-)|:)\s+)", "", without_series_name)

        # remove the file extension, using file.extension
        # EX: series_name c001 (2021) (Digital) - Instincts.cbz -> Instincts.cbz
        if subtitle.endswith(file.extension):
            subtitle = get_extensionless_name(subtitle)

        if not publisher_search:
            # remove everything to the right of the release year/digital
            subtitle = re.sub(
                r"([\[\{\(]((\d{4})|(Digital))[\]\}\)])(.*)",
                "",
                subtitle,
                flags=re.IGNORECASE,
            )
        else:
            # remove everything to the right of the publisher
            if (
                publisher.from_meta
                and publisher_search.group(2).lower().strip()
                == publisher.from_meta.lower().strip()
            ):
                subtitle = re.sub(
                    rf"([\[\{{\(\]])({publisher.from_meta})([\]\}}\)])(.*)",
                    "",
                    subtitle,
                )
            elif (
                publisher.from_name
                and publisher_search.group(2).lower().strip()
                == publisher.from_name.lower().strip()
            ):
                subtitle = re.sub(
                    rf"([\[\{{\(\]])({publisher.from_name})([\]\}}\)])(.*)",
                    "",
                    subtitle,
                )

        # remove any extra spaces
        subtitle = remove_dual_space(subtitle).strip()

        # check that the subtitle isn't present in the folder name, otherwise it's probably not a subtitle
        if re.search(
            rf"{re.escape(subtitle)}",
            os.path.basename(os.path.dirname(file.path)),
            re.IGNORECASE,
        ):
            subtitle = ""

        # check that the subtitle isn't just the volume keyword and a number
        if file.volume_number and re.search(
            rf"^({volume_regex_keywords})(\s+)?(0+)?{file.volume_number}$",
            subtitle.strip(),
            re.IGNORECASE,
        ):
            subtitle = ""

    return subtitle


# Searches bookwalker with the user inputted query and returns the results.
def search_bookwalker(
    query,
    type,
    print_info=False,
    alternative_search=False,
    shortened_search=False,
    total_pages_to_scrape=5,
):
    global required_similarity_score

    # The books returned from the search
    books = []
    # The searches that  results in no book results
    no_book_result_searches = []
    # The series compiled from all the books
    series_list = []
    # The books without a volume number (probably one-shots)
    no_volume_number = []
    # Releases that were identified as chapters
    chapter_releases = []
    # Similarity matches that did not meet the required similarity score
    similarity_match_failures = []
    # Errors encountered while scraping
    errors = []

    bookwalker_manga_category = "&qcat=2"
    bookwalker_light_novel_category = "&qcat=3"
    bookwalker_intll_manga_category = "&qcat=11"

    done = False
    search_type = type
    count = 0

    page_count = 1
    page_count_url = f"&page={page_count}"

    search = urllib.parse.quote(query)
    base_url = "https://global.bookwalker.jp/search/?word="
    chapter_exclusion_url = "&np=1&qnot%5B%5D=Chapter&x=13&y=16"
    series_only = "&np=0"
    series_url = f"{base_url}{search}{series_only}"
    original_similarity_score = required_similarity_score

    # Enables NSFW Search Results
    default_cookies = {
        "glSafeSearch": "1",
        "safeSearch": "111",
    }
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
    }

    if not alternative_search:
        keyword = "\t\tSearch: " if not shortened_search else "\n\t\tShortened Search: "
        category = "MANGA" if search_type.lower() == "m" else "NOVEL"
        series_info = f"({series_url})" if shortened_search else ""

        print(f"{keyword}{query}\n\t\tCategory: {category} {series_info}")

    series_page = scrape_url(
        series_url,
        cookies=default_cookies,
        headers=default_headers,
    )

    series_list_li = []

    if series_page:
        # find ul class o-tile-list in series_page
        series_list_ul = series_page.find_all("ul", class_="o-tile-list")
        if series_list_ul:
            # find all li class="o-tile"
            series_list_li = len(series_list_ul[0].find_all("li", class_="o-tile"))

    if series_list_li == 1:
        required_similarity_score = original_similarity_score - 0.03

    while page_count < total_pages_to_scrape + 1:
        page_count_url = f"&page={page_count}"
        url = f"{base_url}{search}{page_count_url}"
        category = ""

        if search_type.lower() == "m":
            category = (
                bookwalker_manga_category
                if not alternative_search
                else bookwalker_intll_manga_category
            )
        elif search_type.lower() == "l":
            category = bookwalker_light_novel_category

        url += category
        series_url += category

        if shortened_search and series_list_li != 1:
            print("\t\t\t- search does not contain exactly one series, skipping...\n")
            return []

        # url += chapter_exclusion_url
        page_count += 1

        # scrape url page
        page = scrape_url(
            url,
            cookies=default_cookies,
            headers=default_headers,
        )

        if not page:
            alternate_page = None
            if search_type.lower() == "m" and not alternative_search:
                alternate_page = scrape_url(
                    url,
                    cookies=default_cookies,
                    headers=default_headers,
                )
            if not alternate_page:
                print("\t\t\tError: Empty page")
                errors.append("Empty page")
                continue
            else:
                page = alternate_page

        # parse page
        soup = page
        # get total pages
        pager_area = soup.find("div", class_="pager-area")

        if pager_area:
            # find <ul class="clearfix"> in pager-area
            ul_list = pager_area.find("ul", class_="clearfix")
            # find all the <li> in ul_list
            li_list = ul_list.find_all("li")
            # find the highest number in li_list values
            highest_num = max(int(li.text) for li in li_list if li.text.isdigit())

            if highest_num == 0:
                print("\t\t\tNo pages found.")
                errors.append("No pages found.")
                continue
            elif highest_num < total_pages_to_scrape:
                total_pages_to_scrape = highest_num
        else:
            total_pages_to_scrape = 1

        list_area = soup.find(
            "div", class_="book-list-area book-result-area book-result-area-1"
        )
        list_area_ul = soup.find("ul", class_="o-tile-list")

        if list_area_ul is None:
            alternate_result = None
            if search_type.lower() == "m" and not alternative_search:
                alternate_result = search_bookwalker(
                    query, type, print_info, alternative_search=True
                )
                time.sleep(sleep_timer_bk / 2)
            if alternate_result:
                return alternate_result
            if not alternative_search:
                print("\t\t\t! NO BOOKS FOUND ON BOOKWALKER !")
                write_to_file(
                    "bookwalker_no_results.txt",
                    query,
                    without_timestamp=True,
                    check_for_dup=True,
                )
            no_book_result_searches.append(query)
            continue

        o_tile_list = list_area_ul.find_all("li", class_="o-tile")
        print(
            f"\t\t\tPage: {page_count - 1} of {total_pages_to_scrape} ({url})\n\t\t\t\tItems: {len(o_tile_list)}"
        )

        for item in o_tile_list:
            preview_image_url = None
            description = ""
            try:
                o_tile_book_info = item.find("div", class_="o-tile-book-info")
                o_tile_thumb_box = o_tile_book_info.find(
                    "div", class_="m-tile-thumb-box"
                )

                # get href from o_tile_thumb_box
                a_title_thumb = o_tile_thumb_box.find("a", class_="a-tile-thumb-img")
                url = a_title_thumb.get("href")
                img_clas = a_title_thumb.find("img")

                # get data-srcset 2x from img_clas
                img_srcset = img_clas.get("data-srcset")
                img_srcset = re.sub(r"\s\d+x", "", img_srcset)
                img_srcset_split = img_srcset.split(",")
                img_srcset_split = [x.strip() for x in img_srcset_split]

                thumbnail = img_srcset_split[1]

                ul_tag_box = o_tile_book_info.find("ul", class_="m-tile-tag-box")
                li_tag_item = ul_tag_box.find_all("li", class_="m-tile-tag")

                tag_dict = {
                    "a-tag-manga": None,
                    "a-tag-light-novel": None,
                    "a-tag-other": None,
                    "a-tag-chapter": None,
                    "a-tag-simulpub": None,
                }

                for i in li_tag_item:
                    for tag_name in tag_dict.keys():
                        if i.find("div", class_=tag_name):
                            tag_dict[tag_name] = i.find("div", class_=tag_name)

                a_tag_chapter = tag_dict["a-tag-chapter"]
                a_tag_simulpub = tag_dict["a-tag-simulpub"]
                a_tag_manga = tag_dict["a-tag-manga"]
                a_tag_light_novel = tag_dict["a-tag-light-novel"]
                a_tag_other = tag_dict["a-tag-other"]

                book_type = a_tag_manga or a_tag_light_novel or a_tag_other

                if book_type:
                    book_type = book_type.get_text()
                    book_type = re.sub(r"\n|\t|\r", "", book_type).strip()
                else:
                    book_type = "Unknown"

                title = o_tile_book_info.find("h2", class_="a-tile-ttl").text.strip()
                original_title = title

                item_index = o_tile_list.index(item)

                if title:
                    print(f"\t\t\t\t\t[{item_index + 1}] {title}")

                    # remove brackets
                    title = (
                        remove_brackets(title) if contains_brackets(title) else title
                    )

                    # unidecode the title
                    title = unidecode(title)

                    # replace any remaining unicode characters in the title with spaces
                    title = re.sub(r"[^\x00-\x7F]+", " ", title)

                    # remove any extra spaces
                    title = remove_dual_space(title).strip()

                if a_tag_chapter or a_tag_simulpub:
                    chapter_releases.append(title)
                    continue

                if (
                    title
                    and ("chapter" in title.lower() or re.search(r"\s#\d+\b", title))
                    and not re.search(r"re([-_. :]+)?zero", title, re.IGNORECASE)
                ):
                    continue

                part = get_file_part(title)

                if part and re.search(r"(\b(Part)([-_. ]+|)\d+(\.\d+)?)", title):
                    title = re.sub(r"(\b(Part)([-_. ]+|)\d+(\.\d+)?)", "", title)
                    title = remove_dual_space(title).strip()

                volume_number = ""

                # Remove single keyword letter from exclusion, and "Book" and "Novel"
                # Single keywords aren't enough to reject a volume and
                # the keywords "Book" and "Novel" are common in one-shot titles
                modified_volume_keywords = [
                    keyword
                    for keyword in volume_keywords
                    if len(keyword) > 1 and keyword not in ["Books?", "Novels?"]
                ]
                modified_volume_regex_keywords = (
                    "(?<![A-Za-z])" + "|(?<![A-Za-z])".join(modified_volume_keywords)
                )

                # Checks that the title doesn't contain any numbers
                contains_no_numbers = re.search(r"^[^\d]*$", title)

                # Checks if the title contains any of the volume keywords
                contains_volume_keyword = re.search(
                    r"(\b(%s)([-_. ]|)\b)" % modified_volume_regex_keywords, title
                )

                if not contains_volume_keyword or contains_no_numbers:
                    if not re.search(
                        r"(([0-9]+)((([-_.]|)([0-9]+))+|))(\s+)?-(\s+)?(([0-9]+)((([-_.]|)([0-9]+))+|))",
                        title,
                    ):
                        volume_number = re.search(
                            r"(\b(?!2(?:\d{3})\b)\d+\b(\.?[0-9]+)?([-_][0-9]+\.?[0-9]+)?)$",
                            title,
                        )
                    else:
                        title_split = title.split("-")
                        # remove anyting that isn't a number or a period
                        title_split = [re.sub(r"[^0-9.]", "", x) for x in title_split]
                        # clean any extra spaces in the volume_number and set_as_float_or_int
                        title_split = [
                            set_num_as_float_or_int(x.strip()) for x in title_split
                        ]
                        # remove empty results from the list
                        title_split = [x for x in title_split if x]
                        volume_number = title_split if title_split else None

                    if volume_number and not isinstance(volume_number, list):
                        if hasattr(volume_number, "group"):
                            volume_number = volume_number.group(1)
                        else:
                            if title not in no_volume_number:
                                no_volume_number.append(title)
                            continue
                    elif title and is_one_shot(title, skip_folder_check=True):
                        volume_number = 1
                    elif not volume_number and not isinstance(volume_number, list):
                        if title not in no_volume_number:
                            no_volume_number.append(title)
                        continue
                else:
                    volume_number = get_release_number_cache(title)

                volume_number = set_num_as_float_or_int(volume_number)

                if not contains_volume_keyword:
                    title = re.sub(
                        r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(%s|)(\.|)([-_. ]|)(((?!2(?:\d{3})\b)\d+)(\b|\s))$.*"
                        % modified_volume_regex_keywords,
                        "",
                        title,
                        flags=re.IGNORECASE,
                    ).strip()
                    if title.endswith(","):
                        title = title[:-1].strip()
                    title = title.replace("\n", "").replace("\t", "")
                    title = re.sub(rf"\b{volume_number}\b", "", title)
                    title = re.sub(r"(\s{2,})", " ", title).strip()
                    title = re.sub(r"(\((.*)\)$)", "", title).strip()
                else:
                    title = re.sub(
                        r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(%s)(\.|)([-_. ]|)([0-9]+)(\b|\s).*"
                        % modified_volume_regex_keywords,
                        "",
                        title,
                        flags=re.IGNORECASE,
                    ).strip()

                shortened_title = get_shortened_title(title)
                shortened_query = get_shortened_title(query)

                clean_shortened_title = (
                    clean_str(shortened_title).lower().strip()
                    if shortened_title
                    else ""
                )
                clean_shortened_query = (
                    clean_str(shortened_query).lower().strip()
                    if shortened_query
                    else ""
                )

                clean_title = clean_str(title).lower().strip()
                clean_query = clean_str(query).lower().strip()

                score = similar(clean_title, clean_query)
                print(f"\t\t\t\t\t\tBookwalker: {clean_title}")
                print(f"\t\t\t\t\t\tLibrary:    {clean_query}")
                print(
                    f"\t\t\t\t\t\tScore: {score} | Match: {score >= required_similarity_score} (>= {required_similarity_score})"
                )
                print(f"\t\t\t\t\t\tVolume Number: {volume_number}")
                if part:
                    print(f"\t\t\t\t\t\tVolume Part: {part}")

                score_two = 0
                if series_list_li == 1 and not score >= required_similarity_score:
                    score_two = similar(clean_shortened_title, clean_query)
                    print(
                        f"\n\t\t\t\t\t\tBookwalker: {clean_shortened_title if shortened_title and clean_shortened_title else clean_title}"
                    )
                    print(
                        f"\t\t\t\t\t\tLibrary:    {clean_query if shortened_title and clean_shortened_title else clean_shortened_query}"
                    )
                    print(
                        f"\t\t\t\t\t\tScore: {score_two} | Match: {score_two >= required_similarity_score} (>= {required_similarity_score})"
                    )
                    print(f"\t\t\t\t\t\tVolume Number: {volume_number}")
                    if part:
                        print(f"\t\t\t\t\t\tVolume Part: {part}")

                if not (score >= required_similarity_score) and not (
                    score_two >= required_similarity_score
                ):
                    message = f'"{clean_title}": {score} [{book_type}]'
                    if message not in similarity_match_failures:
                        similarity_match_failures.append(message)
                    required_similarity_score = original_similarity_score
                    continue

                # html from url
                page_two = scrape_url(url)

                # parse html
                soup_two = page_two.find("div", class_="product-detail-inner")

                if not soup_two:
                    print("No soup_two")
                    continue

                # Find the book's preview image
                # Find <meta property="og:image" and get the content
                meta_property_og_image = page_two.find("meta", {"property": "og:image"})
                if meta_property_og_image and meta_property_og_image[
                    "content"
                ].startswith("http"):
                    preview_image_url = meta_property_og_image["content"]

                # Backup method for lower resolution preview image
                if not preview_image_url or "ogp-mature" in preview_image_url:
                    # find the img src inside of <div class="book-img">
                    div_book_img = page_two.find("div", class_="book-img")
                    if div_book_img:
                        img_src = div_book_img.find("img")["src"]
                        if img_src and img_src.startswith("http"):
                            preview_image_url = img_src

                # Find the book's description
                div_itemprop_description = page_two.find(
                    "div", {"itemprop": "description"}
                )

                if div_itemprop_description:
                    # find all <p> in div_itemprop_description
                    p_items = div_itemprop_description.find_all("p")
                    if p_items:
                        if len(p_items) > 1:
                            description = "\n".join(
                                p_item.text.strip()
                                for p_item in p_items
                                if p_item["class"][0] != "synopsis-lead"
                                and p_item.text.strip()
                            )
                        else:
                            description = p_items[0].text.strip()

                # find table class="product-detail"
                product_detail = soup_two.find("table", class_="product-detail")

                # find all <td> inside of product-detail
                product_detail_td = product_detail.find_all("td")
                date = ""
                is_released = None

                for detail in product_detail_td:
                    date_match = re.search(
                        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(\s+)?\d{2}([,]+)?\s+\d{4}",
                        detail.text,
                        re.IGNORECASE,
                    )

                    # get the th from the detail
                    th = detail.find_previous_sibling("th")

                    # get the text from the th
                    th_text = th.text

                    if th_text in ["Series Title", "Alternative Title"]:
                        series_title = detail.text

                        # Remove punctuation, convert to lowercase, and strip leading/trailing whitespaces
                        series_title = clean_str(series_title).lower().strip()

                        # Check similarity with the clean_query and clean_shortened_query
                        if not similar(
                            series_title, clean_query
                        ) >= required_similarity_score and not similar(
                            series_title, clean_shortened_query
                        ):
                            continue

                    if date_match:
                        # Clean up the date string by removing non-alphanumeric characters
                        date_match = re.sub(r"[^\s\w]", "", date_match.group())

                        # Split the date into its components (month, day, year)
                        date_parts = date_match.split()
                        month = date_parts[0][:3]
                        day = date_parts[1]
                        year = date_parts[2]

                        # Convert the date string to a datetime object with no time information
                        date = datetime.strptime(f"{month} {day} {year}", "%b %d %Y")

                        # Check if the date is in the past (released) or future (not released yet)
                        is_released = date < datetime.now()

                        # Format the date as a string in "YYYY-MM-DD" format
                        date = date.strftime("%Y-%m-%d")

                        # Break out of the loop since a valid date has been found
                        break

                book = BookwalkerBook(
                    title,
                    original_title,
                    volume_number,
                    part,
                    date,
                    is_released,
                    0.00,
                    url,
                    thumbnail,
                    book_type,
                    description,
                    preview_image_url,
                )
                books.append(book)
            except Exception as e:
                send_message(str(e), error=True)
                errors.append(url)
                continue

        for book in books:
            matching_books = get_all_matching_books(books, book.book_type, book.title)
            if matching_books:
                series_list.append(
                    BookwalkerSeries(
                        book.title,
                        matching_books,
                        len(matching_books),
                        book.book_type,
                    )
                )

    series_list = combine_series(series_list)
    required_similarity_score = original_similarity_score

    # print(f"\t\tSleeping for {sleep_timer_bk} to avoid being rate-limited...")
    time.sleep(sleep_timer_bk)

    if len(series_list) == 1 and len(series_list[0].books) > 0:
        return series_list[0].books
    elif len(series_list) > 1:
        print("\t\t\tNumber of series from bookwalker search is greater than one.")
        print(f"\t\t\tNum: {len(series_list)}")
        return []
    else:
        if not alternative_search:
            print("\t\t\tNo matching books found.")
            write_to_file(
                "bookwalker_no_matching_books.txt",
                query,
                without_timestamp=True,
                check_for_dup=True,
            )
        return []


# Checks the library against bookwalker for any missing volumes that are released or on pre-order
def check_for_new_volumes_on_bookwalker():
    global discord_embed_limit

    # Prints info about the item
    def print_item_info(item):
        print(f"\t\t{item.title}")
        print(f"\t\tType: {item.book_type}")
        print(f"\t\tVolume {item.volume_number}")
        print(f"\t\tDate: {item.date}")
        print(f"\t\tURL: {item.url}\n")

    # Writes info about the item to a file
    def log_item_info(item, file_name):
        message = f"{item.date} | {item.title} | Volume {item.volume_number} | {item.book_type} | {item.url}"
        write_to_file(
            f"{file_name.lower().replace('-', '_')}.txt",
            message,
            without_timestamp=True,
            overwrite=False,
        )

    # Creates a Discord embed for the item
    def create_embed(item, color, webhook_index):
        global grouped_notifications

        embed = handle_fields(
            DiscordEmbed(
                title=f"{item.title} Volume {item.volume_number}",
                color=color,
            ),
            fields=[
                {
                    "name": "Type",
                    "value": item.book_type,
                    "inline": False,
                },
                {
                    "name": "Release Date",
                    "value": item.date,
                    "inline": False,
                },
            ],
        )

        if item.description:
            embed.fields.append(
                {
                    "name": "Description",
                    "value": unidecode(item.description),
                    "inline": False,
                }
            )

        embed.url = item.url

        if item.preview_image_url:
            embed.set_image(url=item.preview_image_url)
            embed.set_thumbnail(url=item.preview_image_url)

        if bookwalker_logo_url and item.url:
            embed.set_author(
                name="Bookwalker", url=item.url, icon_url=bookwalker_logo_url
            )

        if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
            grouped_notifications = group_notification(
                grouped_notifications,
                Embed(embed, None),
                passed_webhook=bookwalker_webhook_urls[webhook_index],
            )

    # Processes the items
    def process_items(items, file_name, color, webhook_index):
        if not items:
            return

        print(f"\n{file_name.capitalize()}:")
        for item in items:
            print_item_info(item)
            log_item_info(item, file_name)
            create_embed(item, color, webhook_index)

        if grouped_notifications:
            if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
                send_discord_message(
                    None,
                    grouped_notifications,
                    passed_webhook=bookwalker_webhook_urls[webhook_index],
                )

    # Gets the volume type based on the extensions in the folder
    def determine_volume_type(volumes):
        if get_folder_type([f.name for f in volumes], manga_extensions) >= 70:
            return "m"
        elif get_folder_type([f.name for f in volumes], novel_extensions) >= 70:
            return "l"
        return None

    def filter_and_compare_volumes(
        volumes, bookwalker_volumes, volume_type, consider_parts=False
    ):
        if volume_type == "l" and volumes and bookwalker_volumes:
            for vol in bookwalker_volumes[:]:
                for existing_vol in volumes:
                    if (
                        (
                            vol.volume_number == existing_vol.volume_number
                            or (
                                isinstance(existing_vol.volume_number, list)
                                and vol.volume_number in existing_vol.volume_number
                            )
                            or (
                                isinstance(vol.volume_number, list)
                                and existing_vol.volume_number in vol.volume_number
                            )
                        )
                        and (
                            (vol.part and not existing_vol.volume_part)
                            or (
                                not consider_parts
                                and not vol.part
                                and not existing_vol.volume_part
                            )
                        )
                        and vol in bookwalker_volumes
                    ):
                        bookwalker_volumes.remove(vol)
        return bookwalker_volumes

    def update_bookwalker_volumes(volumes, bookwalker_volumes):
        if volumes and bookwalker_volumes:
            bookwalker_volumes = [
                vol
                for vol in bookwalker_volumes
                if not any(
                    (
                        vol.volume_number == existing_vol.volume_number
                        or (
                            isinstance(existing_vol.volume_number, list)
                            and vol.volume_number in existing_vol.volume_number
                        )
                        or (
                            isinstance(vol.volume_number, list)
                            and existing_vol.volume_number in vol.volume_number
                        )
                    )
                    and existing_vol.volume_part == vol.part
                    for existing_vol in volumes
                )
            ]
        return bookwalker_volumes

    # Writes info about the missing volumes to a log file.
    def log_missing_volumes(series, volumes, bookwalker_volumes):
        write_to_file(
            "bookwalker_missing_volumes.txt",
            f"{series} - Existing Volumes: {len(volumes)}, Bookwalker Volumes: {len(bookwalker_volumes)}\n",
            without_timestamp=True,
            check_for_dup=True,
        )

    # Prints info about the new/upcoming releases
    def print_releases(bookwalker_volumes, released, pre_orders):
        # Sort them by volume_number
        bookwalker_volumes = sorted(
            bookwalker_volumes, key=lambda x: get_sort_key(x.volume_number)
        )

        for vol in bookwalker_volumes:
            if vol.is_released:
                print("\n\t\t\t[RELEASED]")
                released.append(vol)
            else:
                print("\n\t\t\t[PRE-ORDER]")
                pre_orders.append(vol)

            print(f"\t\t\tTitle: {vol.original_title}")

            print(f"\t\t\tVolume Number: {vol.volume_number}")

            if vol.part:
                print(f"\t\t\tPart: {vol.part}")

            print(f"\t\t\tDate: {vol.date}")
            if vol == bookwalker_volumes[-1]:
                print(f"\t\t\tURL: {vol.url} \n")
            else:
                print(f"\t\t\tURL: {vol.url}")

    # Sorts and logs the releases and pre-orders
    #  - released is sorted by date in ascending order
    #  - pre_orders is sorted by date in descending order
    def sort_and_log_releases(released, pre_orders):
        pre_orders.sort(
            key=lambda x: datetime.strptime(x.date, "%Y-%m-%d"), reverse=True
        )
        released.sort(
            key=lambda x: datetime.strptime(x.date, "%Y-%m-%d"), reverse=False
        )

        if log_to_file:
            released_path = os.path.join(LOGS_DIR, "released.txt")
            pre_orders_path = os.path.join(LOGS_DIR, "pre-orders.txt")

            if os.path.isfile(released_path):
                remove_file(released_path, silent=True)
            if os.path.isfile(pre_orders_path):
                remove_file(pre_orders_path, silent=True)

        process_items(released, "Released", grey_color, 0)
        process_items(pre_orders, "Pre-orders", preorder_blue_color, 1)

    original_limit = discord_embed_limit
    discord_embed_limit = 1

    pre_orders = []
    released = []

    print("\nChecking for new volumes on bookwalker...")

    # Remove any paths that are in the download folders list
    paths_clean = [p for p in paths if p not in download_folders]

    for path_index, path in enumerate(paths_clean, start=1):
        if not os.path.exists(path):
            print(f"\n\tPath does not exist: {path}")
            continue

        os.chdir(path)

        folders = get_all_folders_recursively_in_dir(path)

        if not folders:
            continue

        # sort the folders by "root"
        folders = sorted(folders, key=lambda k: k["root"])

        for dir_index, folder in enumerate(folders, start=1):
            root = folder["root"]
            dirs = folder["dirs"]
            files = clean_and_sort(root, folder["files"], chapters=False, sort=True)[0]

            if not files:
                continue

            base_name = os.path.basename(root)

            print(
                f"\n\t[Folder {dir_index} of {len(folders)} - Path {path_index} of {len(paths_clean)}]"
            )
            print(f"\tPath: {root}")

            series = normalize_str(
                base_name,
                skip_common_words=True,
                skip_japanese_particles=True,
                skip_misc_words=True,
                skip_editions=True,
            )
            series = unidecode(series)

            volumes = upgrade_to_volume_class(
                upgrade_to_file_class(
                    [f for f in files if os.path.isfile(os.path.join(root, f))],
                    root,
                )
            )

            if not volumes:
                continue

            bookwalker_volumes = []
            volume_type = determine_volume_type(volumes)

            if not volume_type or not series:
                continue

            bookwalker_volumes = search_bookwalker(series, volume_type, False)
            shortened_series_title = get_shortened_title(series)

            if shortened_series_title:
                shortened_bookwalker_volumes = search_bookwalker(
                    shortened_series_title,
                    volume_type,
                    False,
                    shortened_search=True,
                )
                if shortened_bookwalker_volumes:
                    bookwalker_volumes.extend(
                        vol
                        for vol in shortened_bookwalker_volumes
                        if not any(
                            vol.url == compare_vol.url
                            for compare_vol in bookwalker_volumes
                        )
                    )

            if not bookwalker_volumes:
                continue

            bookwalker_volumes = filter_and_compare_volumes(
                volumes, bookwalker_volumes, volume_type, consider_parts=True
            )

            print(f"\t\tExisting Volumes: {len(volumes)}")
            print(f"\t\tBookwalker Volumes: {len(bookwalker_volumes)}\n")

            bookwalker_volumes = filter_and_compare_volumes(
                volumes, bookwalker_volumes, volume_type
            )

            if not bookwalker_volumes:
                continue

            if len(volumes) > len(bookwalker_volumes):
                log_missing_volumes(series, volumes, bookwalker_volumes)

            bookwalker_volumes = update_bookwalker_volumes(volumes, bookwalker_volumes)

            if not bookwalker_volumes:
                continue

            print("\t\tNew/Upcoming Releases on Bookwalker:")
            print_releases(bookwalker_volumes, released, pre_orders)

    sort_and_log_releases(released, pre_orders)
    discord_embed_limit = original_limit


# caches all roots encountered when walking paths
def cache_existing_library_paths(
    paths=paths, download_folders=download_folders, cached_paths=cached_paths
):
    paths_cached = []
    print("\nCaching paths recursively...")
    for path in paths:
        if os.path.exists(path):
            if path not in download_folders:
                try:
                    for root, dirs, files in scandir.walk(path):
                        if (root != path and root not in cached_paths) and (
                            not root.startswith(".") and not root.startswith("_")
                        ):
                            cache_path(root)
                            if path not in paths_cached:
                                paths_cached.append(path)
                except Exception as e:
                    send_message(str(e), error=True)
            else:
                print(f"\tSkipping: {path} because it's in the download folders list.")
        else:
            if not path:
                send_message("\nERROR: Path cannot be empty.", error=True)
            else:
                print(f"\nERROR: {path} is an invalid path.\n")
    print("\tdone")

    if paths_cached:
        print("\nRoot paths that were recursively cached:")
        for path in paths_cached:
            print(f"\t{path}")
    return cached_paths


# Sends scan requests to komga for all passed-in libraries
# Reqiores komga settings to be set in settings.py
def scan_komga_library(library_id):
    if not komga_ip:
        send_message(
            "Komga IP is not set in settings.py. Please set it and try again.",
            error=True,
        )
        return

    if not komga_port:
        send_message(
            "Komga Port is not set in settings.py. Please set it and try again.",
            error=True,
        )
        return

    if not komga_login_email:
        send_message(
            "Komga Login Email is not set in settings.py. Please set it and try again.",
            error=True,
        )
        return

    if not komga_login_password:
        send_message(
            "Komga Login Password is not set in settings.py. Please set it and try again.",
            error=True,
        )
        return

    komga_url = f"{komga_ip}:{komga_port}"

    print("\nSending Komga Scan Request:")
    try:
        request = requests.post(
            f"{komga_url}/api/v1/libraries/{library_id}/scan",
            headers={
                "Authorization": "Basic %s"
                % b64encode(
                    f"{komga_login_email}:{komga_login_password}".encode("utf-8")
                ).decode("utf-8"),
                "Accept": "*/*",
            },
        )
        if request.status_code == 202:
            send_message(
                f"\t\tSuccessfully Initiated Scan for: {library_id} Library.",
                discord=False,
            )
        else:
            send_message(
                f"\t\tFailed to Initiate Scan for: {library_id} Library "
                f"Status Code: {request.status_code} Response: {request.text}",
                error=True,
            )
    except Exception as e:
        send_message(
            f"Failed to Initiate Scan for: {library_id} Komga Library, ERROR: {e}",
            error=True,
        )


# Sends a GET library request to Komga for all libraries using
# {komga_url}/api/v1/libraries
# Requires komga settings to be set in settings.py
def get_komga_libraries(first_run=True):
    results = []

    if not komga_ip:
        send_message(
            "Komga IP is not set in settings.py. Please set it and try again.",
            error=True,
        )
        return

    if not komga_port:
        send_message(
            "Komga Port is not set in settings.py. Please set it and try again.",
            error=True,
        )
        return

    if not komga_login_email:
        send_message(
            "Komga Login Email is not set in settings.py. Please set it and try again.",
            error=True,
        )
        return

    if not komga_login_password:
        send_message(
            "Komga Login Password is not set in settings.py. Please set it and try again.",
            error=True,
        )
        return

    komga_url = f"{komga_ip}:{komga_port}"

    try:
        request = requests.get(
            f"{komga_url}/api/v1/libraries",
            headers={
                "Authorization": "Basic %s"
                % b64encode(
                    f"{komga_login_email}:{komga_login_password}".encode("utf-8")
                ).decode("utf-8"),
                "Accept": "*/*",
            },
        )
        if request.status_code == 200:
            results = request.json()
        else:
            send_message(
                f"\t\tFailed to Get Komga Libraries "
                f"Status Code: {request.status_code} "
                f"Response: {request.text}",
                error=True,
            )
    except Exception as e:
        # if first, and error code 104, then try again after sleeping
        if first_run and "104" in str(e):
            time.sleep(60)
            results = get_komga_libraries(first_run=False)
        else:
            send_message(
                f"Failed to Get Komga Libraries, ERROR: {e}",
                error=True,
            )
    return results


# Generates a list of all release groups or publishers.
def generate_rename_lists():
    global release_groups, publishers, skipped_release_group_files, skipped_publisher_files

    skipped_files = []
    log_file_name = None
    skipped_file_name = None
    text_prompt = None

    print("\nGenerating rename lists, with assistance of user.")
    mode = get_input_from_user(
        "\tEnter Mode",
        ["1", "2", "3"],
        "1 = Release Group, 2 = Publisher, 3 = Exit",
        use_timeout=True,
    )

    if mode == "1":
        mode = "r"
        log_file_name = "release_groups.txt"
        skipped_file_name = "skipped_release_group_files.txt"
        text_prompt = "release group"
        if skipped_release_group_files:
            skipped_files = skipped_release_group_files
    elif mode == "2":
        mode = "p"
        log_file_name = "publishers.txt"
        skipped_file_name = "skipped_publisher_files.txt"
        text_prompt = "publisher"
        if skipped_publisher_files:
            skipped_files = skipped_publisher_files
    else:
        print("\nExiting...")
        return

    if not paths:
        send_message(
            "No paths are set in settings.py. Please set them and try again.",
            error=True,
        )
        return

    for path in paths:
        if not os.path.exists(path):
            send_message(f"Path does not exist: {path}", error=True)
            continue

        if mode == "p" and paths_with_types:
            is_in_path_with_types = [
                x.path
                for x in paths_with_types
                if x.path == path and "chapter" in x.path_formats
            ]
            if is_in_path_with_types:
                continue
        try:
            skipped_file_volumes = []
            for root, dirs, files in scandir.walk(path):
                files, dirs = clean_and_sort(root, files, dirs, sort=True)

                if not files:
                    continue

                volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(
                        [f for f in files if os.path.isfile(os.path.join(root, f))],
                        root,
                    )
                )
                for file in volumes:
                    if mode == "p" and file.file_type == "chapter":
                        continue

                    print(f"\n\tChecking: {file.name}")
                    found = False

                    if file.name not in skipped_files:
                        if skipped_files and not skipped_file_volumes:
                            skipped_file_volumes = upgrade_to_volume_class(
                                upgrade_to_file_class(
                                    [f for f in skipped_files],
                                    root,
                                    clean=True,
                                )
                            )
                        if skipped_file_volumes:
                            for skipped_file in skipped_file_volumes:
                                if skipped_file.extras:
                                    # sort alphabetically
                                    skipped_file.extras.sort()
                                    # remove any year from the extras
                                    skipped_file.extras = [
                                        extra
                                        for extra in skipped_file.extras
                                        if not re.search(
                                            r"([\[\(\{]\d{4}[\]\)\}])",
                                            extra,
                                            re.IGNORECASE,
                                        )
                                    ]

                                if file.extras:
                                    # sort alphabetically
                                    file.extras.sort()
                                    # remove any year from the extras
                                    file.extras = [
                                        extra
                                        for extra in file.extras
                                        if not re.search(
                                            r"([\[\(\{]\d{4}[\]\)\}])",
                                            extra,
                                            re.IGNORECASE,
                                        )
                                    ]

                                if (
                                    file.extras == skipped_file.extras
                                    and file.extension == skipped_file.extension
                                ):
                                    print(
                                        f"\t\tSkipping: {file.name} because it has the same extras and extension as: {skipped_file.name} (in {skipped_file_name})"
                                    )
                                    found = True
                                    write_to_file(
                                        skipped_file_name,
                                        file.name,
                                        without_timestamp=True,
                                        check_for_dup=True,
                                    )
                                    if file.name not in skipped_files:
                                        skipped_files.append(file.name)
                                        skipped_file_volume = upgrade_to_volume_class(
                                            upgrade_to_file_class([file.name], root)
                                        )
                                        if (
                                            skipped_file_volume
                                            and skipped_file_volume
                                            not in skipped_file_volumes
                                        ):
                                            skipped_file_volumes.append(
                                                skipped_file_volume[0]
                                            )
                                    break

                        left_brackets = r"(\(|\[|\{)"
                        right_brackets = r"(\)|\]|\})"
                        groups_to_use = release_groups if mode == "r" else publishers

                        if groups_to_use and not found:
                            found = next(
                                (
                                    group
                                    for group in groups_to_use
                                    if re.search(
                                        rf"{left_brackets}{re.escape(group)}{right_brackets}",
                                        file.name,
                                        re.IGNORECASE,
                                    )
                                ),
                                None,
                            )
                            if found:
                                print(f'\t\tFound: "{found}", skipping file.')

                        if not found:
                            # ask the user what the release group or publisher is, then write it to the file, add it to the list, and continue. IF the user inputs "none" then skip it.
                            # loop until the user inputs a valid response
                            while True:
                                print(
                                    f"\t\tCould not find a {text_prompt} for: \n\t\t\t{file.name}"
                                )
                                group = input(
                                    f'\n\t\tPlease enter the {text_prompt} ("none" to add to {skipped_file_name}, "skip" to skip): '
                                )
                                if group == "none":
                                    print(
                                        f"\t\t\tAdding to {skipped_file_name} and skipping in the future..."
                                    )
                                    write_to_file(
                                        skipped_file_name,
                                        file.name,
                                        without_timestamp=True,
                                        check_for_dup=True,
                                    )
                                    if file.name not in skipped_files:
                                        skipped_files.append(file.name)
                                        skipped_file_vol = upgrade_to_volume_class(
                                            upgrade_to_file_class([file.name], root)
                                        )
                                        if (
                                            skipped_file_vol
                                            and skipped_file_vol
                                            not in skipped_file_volumes
                                        ):
                                            skipped_file_volumes.append(
                                                skipped_file_vol[0]
                                            )
                                    break
                                elif group == "skip":
                                    print("\t\t\tSkipping...")
                                    break
                                elif group:
                                    # print back what the user entered
                                    print(f"\t\t\tYou entered: {group}")
                                    write_to_file(
                                        log_file_name,
                                        group,
                                        without_timestamp=True,
                                        check_for_dup=True,
                                    )
                                    if mode == "r":
                                        if group not in release_groups:
                                            release_groups.append(group)
                                    elif mode == "p":
                                        if group not in publishers:
                                            publishers.append(group)
                                    break
                                else:
                                    print("\t\t\tInvalid input.")
                    else:
                        print(f"\t\tSkipping... File is in {skipped_file_name}")
        except Exception as e:
            send_message(str(e), error=True)

    # Reassign the global arrays if anything new new got added to the local one.
    if skipped_files:
        if (
            mode == "r"
            and skipped_files
            and skipped_files != skipped_release_group_files
        ):
            skipped_release_group_files = skipped_files
        elif mode == "p" and skipped_files and skipped_files != skipped_publisher_files:
            skipped_publisher_files = skipped_files


# Checks if a string only contains one set of numbers
def has_one_set_of_numbers(string, chapter=False, file=None, subtitle=None):
    keywords = volume_regex_keywords if not chapter else chapter_regex_keywords + "|"

    if subtitle:
        string = re.sub(
            rf"(-|:)\s*{re.escape(subtitle)}$", "", string, re.IGNORECASE
        ).strip()

    result = False
    search = re.findall(
        r"\b(%s)(%s)?(([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?(_extra)?)\b"
        % (exclusion_keywords_regex, keywords),
        string,
        re.IGNORECASE,
    )
    if search and len(search) == 1:
        result = True
    return result


# Check if there is more than one set of numbers in the string
@lru_cache(maxsize=None)
def has_multiple_numbers(file_name):
    return len(re.findall(r"\d+\.0+[1-9]+|\d+\.[1-9]+|\d+", file_name)) > 1


# Extracts all the numbers from a string
def extract_all_numbers(string, subtitle=None):
    # Replace underscores
    string = replace_underscores(string) if "_" in string else string

    # Remove the subtitle if present
    if subtitle:
        string = re.sub(
            rf"(-|:)\s*{re.escape(subtitle)}$", "", string, re.IGNORECASE
        ).strip()

    numbers = re.findall(
        r"\b(?:%s)(\d+(?:[-_.]\d+|)+(?:x\d+)?(?:#\d+(?:[-_.]\d+|)+)?)"
        % exclusion_keywords_regex,
        string,
    )
    new_numbers = []

    for number in numbers:
        items = number if isinstance(number, tuple) else [number]

        for item in items:
            if not item:
                continue

            if "#" in item and re.search(r"(\d+#\d+)", item):
                item = re.sub(r"((#)([0-9]+)(([-_.])([0-9]+)|)+)", "", item).strip()
            if "x" in item:
                item = re.sub(r"(x[0-9]+)", "", item, re.IGNORECASE).strip()

            if "-" not in item:
                new_numbers.append(set_num_as_float_or_int(item))
            else:
                num_range = item.split("-")
                new_range = [set_num_as_float_or_int(num) for num in num_range]
                new_numbers.append(new_range)

    return new_numbers


# Result class that is used for our image_comparison results from our
# image comparison function
class Image_Result:
    def __init__(self, ssim_score, image_source):
        self.ssim_score = ssim_score
        self.image_source = image_source


# Compares two images and returns the ssim score of the two images similarity.
def prep_images_for_similarity(
    blank_image_path, internal_cover_data, both_cover_data=False, silent=False
):

    # Decode internal cover data
    internal_cover = cv2.imdecode(
        np.frombuffer(internal_cover_data, np.uint8), cv2.IMREAD_UNCHANGED
    )

    # Load blank image either from path or data buffer based on condition
    blank_image = (
        cv2.imread(blank_image_path)
        if not both_cover_data
        else cv2.imdecode(
            np.frombuffer(blank_image_path, np.uint8), cv2.IMREAD_UNCHANGED
        )
    )
    internal_cover = np.array(internal_cover)

    # Resize images to have matching dimensions
    if blank_image.shape[0] > internal_cover.shape[0]:
        blank_image = cv2.resize(
            blank_image,
            (
                internal_cover.shape[1],
                internal_cover.shape[0],
            ),
        )
    else:
        internal_cover = cv2.resize(
            internal_cover,
            (
                blank_image.shape[1],
                blank_image.shape[0],
            ),
        )

    # Ensure both images have the same number of color channels
    if len(blank_image.shape) == 3 and len(internal_cover.shape) == 3:
        min_shape = min(blank_image.shape[2], internal_cover.shape[2])
        blank_image = blank_image[:, :, :min_shape]
        internal_cover = internal_cover[:, :, :min_shape]
    elif len(blank_image.shape) == 3 and len(internal_cover.shape) == 2:
        blank_image = blank_image[:, :, 0]
    elif len(blank_image.shape) == 2 and len(internal_cover.shape) == 3:
        internal_cover = internal_cover[:, :, 0]

    # Compare images and return similarity score
    score = compare_images(blank_image, internal_cover, silent=silent)

    return score


# compares our two images likness and returns the ssim score
def compare_images(imageA, imageB, silent=False):
    ssim_score = None
    try:
        if not silent:
            print(f"\t\t\tBlank Image Size: {imageA.shape}")
            print(f"\t\t\tInternal Cover Size: {imageB.shape}")

        if len(imageA.shape) == 3 and len(imageB.shape) == 3:
            grayA = cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY)
            grayB = cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY)
            ssim_score = ssim(grayA, grayB)
        else:
            ssim_score = ssim(imageA, imageB)
        if not silent:
            print(f"\t\t\t\tSSIM: {ssim_score}")
    except Exception as e:
        send_message(str(e), error=True)
    return ssim_score


# Extracts a supported archive to a temporary directory.
def extract(file_path, temp_dir, extension):
    successfull = False
    try:
        if extension in rar_extensions:
            with rarfile.RarFile(file_path) as rar:
                rar.extractall(temp_dir)
                successfull = True
        elif extension in seven_zip_extensions:
            with py7zr.SevenZipFile(file_path, "r") as archive:
                archive.extractall(temp_dir)
                successfull = True
    except Exception as e:
        send_message(f"Error extracting {file_path}: {e}", error=True)
    return successfull


# Compresses a directory to a CBZ archive.
def compress(temp_dir, cbz_filename):
    successfull = False
    try:
        with zipfile.ZipFile(cbz_filename, "w") as zip:
            for root, dirs, files in scandir.walk(temp_dir):
                for file in files:
                    zip.write(
                        os.path.join(root, file),
                        os.path.join(root[len(temp_dir) + 1 :], file),
                    )
            successfull = True
    except Exception as e:
        send_message(f"Error compressing {temp_dir}: {e}", error=True)
    return successfull


# Converts supported archives to CBZ.
def convert_to_cbz():
    global transferred_files, grouped_notifications

    print("\nLooking for archives to convert to CBZ...")

    if not download_folders:
        print("\tNo download folders specified.")
        return

    for folder in download_folders:
        if not os.path.isdir(folder):
            print(f"\t{folder} is not a valid directory.")
            continue

        print(f"\t{folder}")
        for root, dirs, files in scandir.walk(folder):
            files, dirs = process_files_and_folders(
                root,
                files,
                dirs,
                just_these_files=transferred_files,
                just_these_dirs=transferred_dirs,
                skip_remove_unaccepted_file_types=True,
                keep_images_in_just_these_files=True,
            )

            for entry in files:
                try:
                    extension = get_file_extension(entry)
                    file_path = os.path.join(root, entry)

                    if not os.path.isfile(file_path):
                        continue

                    print(f"\t\t{entry}")

                    if extension in convertable_file_extensions:
                        source_file = file_path
                        repacked_file = f"{get_extensionless_name(source_file)}.cbz"

                        # check that the cbz file doesn't already exist
                        if os.path.isfile(repacked_file):
                            # if the file is zero bytes, delete it and continue, otherwise skip
                            if get_file_size(repacked_file) == 0:
                                send_message(
                                    "\t\t\tCBZ file is zero bytes, deleting...",
                                    discord=False,
                                )
                                remove_file(repacked_file)
                            elif not zipfile.is_zipfile(repacked_file):
                                send_message(
                                    "\t\t\tCBZ file is not a valid zip file, deleting...",
                                    discord=False,
                                )
                                remove_file(repacked_file)
                            else:
                                send_message(
                                    "\t\t\tCBZ file already exists, skipping...",
                                    discord=False,
                                )
                                continue

                        temp_dir = tempfile.mkdtemp("_source2cbz")

                        # if there's already contents in the temp directory, delete it
                        if os.listdir(temp_dir):
                            send_message(
                                f"\t\t\tTemp directory {temp_dir} is not empty, deleting...",
                                discord=False,
                            )
                            remove_folder(temp_dir)
                            # recreate the temp directory
                            temp_dir = tempfile.mkdtemp("source2cbz")

                        if not os.path.isdir(temp_dir):
                            send_message(
                                f"\t\t\tFailed to create temp directory {temp_dir}",
                                error=True,
                            )
                            continue

                        send_message(
                            f"\t\t\tCreated temp directory {temp_dir}",
                            discord=False,
                        )

                        # Extract the archive to the temp directory
                        extract_status = extract(source_file, temp_dir, extension)

                        if not extract_status:
                            send_message(
                                f"\t\t\tFailed to extract {source_file}",
                                error=True,
                            )
                            # remove temp directory
                            remove_folder(temp_dir)
                            continue

                        print(f"\t\t\tExtracted contents to {temp_dir}")

                        # Get hashes of all files in archive
                        hashes = []
                        for root2, dirs2, files2 in scandir.walk(temp_dir):
                            for file2 in files2:
                                path = os.path.join(root2, file2)
                                hashes.append(get_file_hash(path))

                        compress_status = compress(temp_dir, repacked_file)

                        if not compress_status:
                            # remove temp directory
                            remove_folder(temp_dir)
                            continue

                        print(f"\t\t\tCompressed to {repacked_file}")

                        # Check that the number of files in both archives is the same
                        # Print any files that aren't shared between the two archives
                        source_file_list = []
                        repacked_file_list = []

                        if os.path.isfile(source_file):
                            if extension in rar_extensions:
                                with rarfile.RarFile(source_file) as rar:
                                    for file in rar.namelist():
                                        if get_file_extension(file):
                                            source_file_list.append(file)
                            elif extension in seven_zip_extensions:
                                with py7zr.SevenZipFile(source_file) as seven_zip:
                                    for file in seven_zip.getnames():
                                        if get_file_extension(file):
                                            source_file_list.append(file)

                        if os.path.isfile(repacked_file):
                            with zipfile.ZipFile(repacked_file) as zip:
                                for file in zip.namelist():
                                    if get_file_extension(file):
                                        repacked_file_list.append(file)

                        # sort them
                        source_file_list.sort()
                        repacked_file_list.sort()

                        # print any files that aren't shared between the two archives
                        if (source_file_list and repacked_file_list) and (
                            source_file_list != repacked_file_list
                        ):
                            print(
                                "\t\t\tVerifying that all files are present in both archives..."
                            )
                            for file in source_file_list:
                                if file not in repacked_file_list:
                                    print(f"\t\t\t\t{file} is not in {repacked_file}")
                            for file in repacked_file_list:
                                if file not in source_file_list:
                                    print(f"\t\t\t\t{file} is not in {source_file}")

                            # remove temp directory
                            remove_folder(temp_dir)

                            # remove cbz file
                            remove_file(repacked_file)

                            continue
                        else:
                            print("\t\t\tAll files are present in both archives.")

                        hashes_verified = False

                        # Verify hashes of all files inside the cbz file
                        with zipfile.ZipFile(repacked_file) as zip:
                            for file in zip.namelist():
                                if get_file_extension(file):
                                    hash = get_file_hash(repacked_file, True, file)
                                    if hash and hash not in hashes:
                                        print(f"\t\t\t\t{file} hash did not match")
                                        break
                            else:
                                hashes_verified = True

                        # Remove temp directory
                        remove_folder(temp_dir)

                        if hashes_verified:
                            send_message("\t\t\tHashes verified.", discord=False)
                            send_message(
                                f"\t\t\tConverted {source_file} to {repacked_file}",
                                discord=False,
                            )
                            embed = handle_fields(
                                DiscordEmbed(
                                    title="Converted to CBZ",
                                    color=grey_color,
                                ),
                                fields=[
                                    {
                                        "name": "From",
                                        "value": f"```{os.path.basename(source_file)}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "To",
                                        "value": f"```{os.path.basename(repacked_file)}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "Location",
                                        "value": f"```{os.path.dirname(repacked_file)}```",
                                        "inline": False,
                                    },
                                ],
                            )
                            grouped_notifications = group_notification(
                                grouped_notifications, Embed(embed, None)
                            )

                            # remove the source file
                            remove_file(source_file)

                            if watchdog_toggle:
                                if source_file in transferred_files:
                                    transferred_files.remove(source_file)
                                if repacked_file not in transferred_files:
                                    transferred_files.append(repacked_file)
                        else:
                            send_message("\t\t\tHashes did not verify", error=True)
                            # remove cbz file
                            remove_file(repacked_file)

                    elif extension == ".zip" and rename_zip_to_cbz:
                        header_extension = get_header_extension(file_path)
                        # if it's a zip file, then rename it to cbz
                        if (
                            zipfile.is_zipfile(file_path)
                            or header_extension in manga_extensions
                        ):
                            rename_path = f"{get_extensionless_name(file_path)}.cbz"

                            user_input = (
                                get_input_from_user(
                                    "\t\t\tRename to CBZ",
                                    ["y", "n"],
                                    ["y", "n"],
                                )
                                if manual_rename
                                else "y"
                            )

                            if user_input == "y":
                                rename_file(
                                    file_path,
                                    rename_path,
                                )
                                if os.path.isfile(rename_path) and not os.path.isfile(
                                    file_path
                                ):
                                    if watchdog_toggle:
                                        if file_path in transferred_files:
                                            transferred_files.remove(file_path)
                                        if rename_path not in transferred_files:
                                            transferred_files.append(rename_path)
                            else:
                                print("\t\t\t\tSkipping...")
                except Exception as e:
                    send_message(
                        f"Error when correcting extension: {entry}: {e}",
                        error=True,
                    )

                    # if the tempdir exists, remove it
                    if os.path.isdir(temp_dir):
                        remove_folder(temp_dir)

                    # if the cbz file exists, remove it
                    if os.path.isfile(repacked_file):
                        remove_file(repacked_file)


# Goes through each file in download_folders and checks for an incorrect file extension
# based on the file header. If the file extension is incorrect, it will rename the file.
def correct_file_extensions():
    global transferred_files, grouped_notifications

    print("\nChecking for incorrect file extensions...")

    if not download_folders:
        print("\tNo download folders specified.")
        return

    for folder in download_folders:
        if not os.path.isdir(folder):
            print(f"\t{folder} does not exist.")
            continue

        print(f"\t{folder}")
        for root, dirs, files in scandir.walk(folder):
            files, dirs = process_files_and_folders(
                root,
                files,
                dirs,
                just_these_files=transferred_files,
                just_these_dirs=transferred_dirs,
                is_correct_extensions_feature=file_extensions + rar_extensions,
            )
            volumes = upgrade_to_file_class(
                [f for f in files if os.path.isfile(os.path.join(root, f))],
                root,
                skip_get_header_extension=False,
                is_correct_extensions_feature=file_extensions + rar_extensions,
            )

            if not volumes:
                continue

            for volume in volumes:
                if not volume.header_extension:
                    continue

                print(
                    f"\n\t\t{volume.name}\n\t\t\tfile extension:   {volume.extension}\n\t\t\theader extension: {volume.header_extension}"
                )
                if volume.extension != volume.header_extension:
                    print(
                        f"\n\t\t\tRenaming File:\n\t\t\t\t{volume.name}\n\t\t\t\t\tto\n\t\t\t\t{volume.extensionless_name}{volume.header_extension}"
                    )
                    user_input = (
                        get_input_from_user("\t\t\tRename", ["y", "n"], ["y", "n"])
                        if manual_rename
                        else "y"
                    )

                    if user_input == "y":
                        new_path = (
                            f"{volume.extensionless_path}{volume.header_extension}"
                        )
                        rename_status = rename_file(
                            volume.path,
                            new_path,
                            silent=True,
                        )
                        if rename_status:
                            print("\t\t\tRenamed successfully")
                            if not mute_discord_rename_notifications:
                                embed = handle_fields(
                                    DiscordEmbed(
                                        title="Renamed File",
                                        color=grey_color,
                                    ),
                                    fields=[
                                        {
                                            "name": "From",
                                            "value": f"```{volume.name}```",
                                            "inline": False,
                                        },
                                        {
                                            "name": "To",
                                            "value": f"```{volume.extensionless_name}{volume.header_extension}```",
                                            "inline": False,
                                        },
                                    ],
                                )
                                grouped_notifications = group_notification(
                                    grouped_notifications,
                                    Embed(embed, None),
                                )
                                if watchdog_toggle:
                                    if volume.path in transferred_files:
                                        transferred_files.remove(volume.path)
                                    if new_path not in transferred_files:
                                        transferred_files.append(new_path)
                    else:
                        print("\t\t\tSkipped")


# Checks if the file string contains a chapter/volume keyword
def contains_keyword(file_string, chapter=False):
    return re.search(
        rf"(\b({chapter_regex_keywords if chapter else volume_regex_keywords})([-_.]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s|{file_extensions_regex}))",
        file_string,
        re.IGNORECASE,
    )


# Optional features below, use at your own risk.
# Activate them in settings.py
def main():
    global cached_paths
    global processed_files
    global moved_files
    global release_groups
    global publishers
    global skipped_release_group_files
    global skipped_publisher_files
    global transferred_files
    global transferred_dirs
    global komga_libraries
    global publishers_joined
    global release_groups_joined
    global publishers_joined_regex, release_groups_joined_regex

    processed_files = []
    moved_files = []
    download_folder_in_paths = False

    release_groups_path = os.path.join(LOGS_DIR, "release_groups.txt")
    publishers_path = os.path.join(LOGS_DIR, "publishers.txt")
    skipped_release_group_files_path = os.path.join(
        LOGS_DIR, "skipped_release_group_files.txt"
    )
    skipped_publisher_files_path = os.path.join(LOGS_DIR, "skipped_publisher_files.txt")

    # Determines when the cover_extraction should be run
    if download_folders and paths:
        for folder in download_folders:
            if folder in paths:
                download_folder_in_paths = True
                break

    # Load cached_paths.txt into cached_paths
    if (
        os.path.isfile(cached_paths_path)
        and check_for_existing_series_toggle
        and not cached_paths
    ):
        cached_paths = get_lines_from_file(
            cached_paths_path,
            ignore=paths + download_folders,
            check_paths=True,
        )

        # get rid of non-valid paths
        cached_paths = [x for x in cached_paths if os.path.isdir(x)]

    # Cache the paths if the user doesn't have a cached_paths.txt file
    if (
        (
            cache_each_root_for_each_path_in_paths_at_beginning_toggle
            or not os.path.isfile(cached_paths_path)
        )
        and paths
        and check_for_existing_series_toggle
        and not cached_paths
    ):
        cache_existing_library_paths()
        if cached_paths:
            print(f"\n\tLoaded {len(cached_paths)} cached paths")

    # Load release_groups.txt into release_groups
    if os.path.isfile(release_groups_path):
        release_groups_read = get_lines_from_file(release_groups_path)
        if release_groups_read:
            release_groups = release_groups_read
            release_groups_joined = "|".join(map(re.escape, release_groups))
            print(
                f"\tLoaded {len(release_groups)} release groups from release_groups.txt"
            )

    # Load publishers.txt into publishers
    if os.path.isfile(publishers_path):
        publishers_read = get_lines_from_file(publishers_path)
        if publishers_read:
            publishers = publishers_read
            publishers_joined = "|".join(map(re.escape, publishers))
            print(f"\tLoaded {len(publishers)} publishers from publishers.txt")

    # Pre-compiled publisher regex
    publishers_joined_regex = re.compile(
        rf"(?<=[\(\[\{{])({publishers_joined})(?=[\)\]\}}])", re.IGNORECASE
    )

    # Pre-compile release group regex
    release_groups_joined_regex = re.compile(
        rf"(?<=[\(\[\{{])({release_groups_joined})(?=[\)\]\}}])", re.IGNORECASE
    )

    # Correct any incorrect file extensions
    if correct_file_extensions_toggle:
        correct_file_extensions()

    # Convert any non-cbz supported file to cbz
    if convert_to_cbz_toggle:
        convert_to_cbz()

    # Delete any files with unacceptable keywords in their name
    if delete_unacceptable_files_toggle:
        delete_unacceptable_files()

    # Delete any chapters from the downloads folder
    if delete_chapters_from_downloads_toggle:
        delete_chapters_from_downloads()

    # Generate the release group list
    if (
        generate_release_group_list_toggle
        and log_to_file
        and paths
        and not watchdog_toggle
        and not in_docker
    ):
        # Loads skipped_release_group_files.txt into skipped_release_group_files
        if os.path.isfile(skipped_release_group_files_path):
            skipped_release_group_files_read = get_lines_from_file(
                skipped_release_group_files_path
            )
            if skipped_release_group_files_read:
                skipped_release_group_files = skipped_release_group_files_read
                print(
                    f"\n\tLoaded {len(skipped_release_group_files)} skipped release group files from skipped_release_group_files.txt"
                )

        # Loads skipped_publisher_files.txt into skipped_publisher_files
        if os.path.isfile(skipped_publisher_files_path):
            skipped_publisher_files_read = get_lines_from_file(
                skipped_publisher_files_path
            )
            if skipped_publisher_files_read:
                skipped_publisher_files = skipped_publisher_files_read
                print(
                    f"\tLoaded {len(skipped_publisher_files)} skipped publisher files from skipped_publisher_files.txt"
                )
        generate_rename_lists()

    # Rename the files in the download folders
    if rename_files_in_download_folders_toggle:
        rename_files()

    # Create folders for items in the download folder
    if create_folders_for_items_in_download_folder_toggle:
        create_folders_for_items_in_download_folder()

    # Checks for duplicate volumes/chapters in the download folders
    if check_for_duplicate_volumes_toggle and download_folders:
        check_for_duplicate_volumes(download_folders)

    # Extract the covers from the files in the download folders
    if extract_covers_toggle and paths and download_folder_in_paths:
        extract_covers()
        print_stats()

    # Match the files in the download folders to the files in the library
    if check_for_existing_series_toggle and download_folders and paths:
        check_for_existing_series()

    # Rename the root directory folders in the download folder
    if rename_dirs_in_download_folder_toggle and download_folders:
        rename_dirs_in_download_folder()

    if watchdog_toggle:
        # remove any deleted/renamed/moved files
        if transferred_files:
            transferred_files = [x for x in transferred_files if os.path.isfile(x)]

        # remove any deleted/renamed/moved directories
        if transferred_dirs:
            transferred_dirs = [x for x in transferred_dirs if os.path.isdir(x.root)]

    if grouped_notifications and not watchdog_toggle:
        send_discord_message(None, grouped_notifications)

    # Extract the covers from the files in the library
    if extract_covers_toggle and paths and not download_folder_in_paths:
        if (watchdog_toggle and moved_files) or not watchdog_toggle:
            if watchdog_toggle and not copy_existing_volume_covers_toggle:
                paths_to_trigger = []
                for path in paths:
                    if moved_files:
                        if (
                            any(
                                moved_file.startswith(path)
                                for moved_file in moved_files
                            )
                            and path not in paths_to_trigger
                        ):
                            paths_to_trigger.append(path)
                            continue

                if paths_to_trigger:
                    extract_covers(paths_to_process=paths_to_trigger)
            else:
                if profile_code == "extract_covers()":
                    cProfile.run(profile_code, sort="cumtime")
                    exit()
                else:
                    extract_covers()
                print_stats()

    # Check for missing volumes in the library (local solution)
    if check_for_missing_volumes_toggle:
        check_for_missing_volumes()

    # Check for missing volumes in the library (bookwalker solution)
    if bookwalker_check and not watchdog_toggle:
        check_for_new_volumes_on_bookwalker()

    # Sends a scan request to Komga for each library that had a file moved into it.
    if (
        send_scan_request_to_komga_libraries_toggle
        and check_for_existing_series_toggle
        and moved_files
    ):
        # The paths we've already scanned, to avoid unnecessary scans.
        libraries_to_scan = []

        if not komga_libraries:
            # Retrieve the Komga libraries
            komga_libraries = get_komga_libraries()

        for path in moved_files:
            if os.path.isfile(path):
                # Scan the Komga libraries for matching root path
                # and trigger a scan.
                if komga_libraries:
                    for library in komga_libraries:
                        if library["id"] in libraries_to_scan:
                            continue

                        if library["root"] in path:
                            libraries_to_scan.append(library["id"])

        # Send scan requests to each komga library
        if libraries_to_scan:
            for library_id in libraries_to_scan:
                scan_komga_library(library_id)

    # clear lru_cache for contains_comic_info()
    contains_comic_info.cache_clear()


# Checks that the user has the required settings in settings.py
# Will become obselete once I figure out an automated way of
# parsing and updating the user's settings.py file.
def check_required_settings():
    required_settings = {
        "uncheck_non_qbit_upgrades_toggle": (2, 5, 0),
        "qbittorrent_ip": (2, 5, 0),
        "qbittorrent_port": (2, 5, 0),
        "qbittorrent_username": (2, 5, 0),
        "qbittorrent_password": (2, 5, 0),
        "delete_unacceptable_torrent_titles_in_qbit": (2, 5, 0),
    }

    missing_settings = [
        setting
        for setting, version in required_settings.items()
        if script_version == version and setting not in settings
    ]

    if missing_settings:
        send_discord_message(
            f"\nMissing settings in settings.py: \n\t{','.join(missing_settings)}\nPlease update your settings.py file.",
        )

        print("\nMissing settings in settings.py:")
        for setting in missing_settings:
            print(f"\t{setting}")
        print("Please update your settings.py file.\n")
        exit()


if __name__ == "__main__":
    parse_my_args()  # parses the user's arguments

    if settings:
        check_required_settings()

    if watchdog_toggle and download_folders:
        while True:
            print("\nWatchdog is enabled, watching for changes...")
            watch = Watcher()
            watch.run()
    else:
        if profile_code == "main()":
            # run with cprofile and sort by cumulative time
            cProfile.run(profile_code, sort="cumtime")
            exit()
        else:
            main()
