import argparse
import calendar
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
from langdetect import detect
from lxml import etree
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from titlecase import titlecase
from unidecode import unidecode
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from settings import *

# Version of the script
script_version = (2, 4, 11)
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
image_quality = 60

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

# Newly released volumes that aren't currently in the library.
new_releases_on_bookwalker = []

# A quick and dirty fix to avoid non-processed files from
# being moved over to the existing library. Will be removed in the future.
processed_files = []

# Any files moved to the existing library. Used for triggering a library scan in komga.
moved_files = []

# The script's root directory
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

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
    script_version_text += "-docker"


# The path location of the blank_white.jpg in the root of the script directory.
blank_white_image_path = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "blank_white.jpg")
    if os.path.isfile(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "blank_white.jpg")
    )
    else None
)

blank_black_image_path = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "blank_black.png")
    if os.path.isfile(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "blank_black.png")
    )
    else None
)

# Cached paths from the users existing library. Read from cached_paths.txt
cached_paths = []

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

# The Library Entertainment types
library_types = [
    "manga",
    "comic",
    "webtoon",
    "webcomic",
    "manhwa",
    "web novel",
    "light novel",
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
    "Part",
    "Episode",
    "Season",
    "Arc",
    "Prologue",
    "Epilogue",
    "Omake",
    "Extra",
    "- Special",
    "Side Story",
    "S",
    "Act",
    "Special Episode",
    "Ep",
    "- Version",
    "Ver",
]

# Volume Regex Keywords to be used throughout the script
volume_regex_keywords = "(?<![A-Za-z])" + "|(?<![A-Za-z])".join(volume_keywords)

# Exclusion keywords joined by just |
exclusion_keywords_joined = "|".join(exclusion_keywords)

# Exclusion Regex Keywords to be used in the Chapter Regex Keywords to avoid incorrect number matches.
exclusion_keywords_joined_with_exclusion = "|".join(
    r"(\s)" + keyword + r"(\s)" for keyword in exclusion_keywords
)

# Put the exclusion_keywords_joined_with_exclusion inside of (?<!%s)
exclusion_keywords_regex = r"(?<!%s)" % exclusion_keywords_joined_with_exclusion

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
    r"\s-(\s+)?(#)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(\s+)?-\s",
    r"(\b(%s)((\.)|)(\s+)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?\b)"
    % chapter_regex_keywords,
    r"((\b(%s|)((\.)|)(\s+)?(%s)([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?\b)(\s+)?((\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})|((?<!\w(\s))|(?<!\w))(%s)(?!\w)))"
    % (chapter_regex_keywords, exclusion_keywords_regex, manga_extensions_regex),
    r"((\b((\.)|)(\s+)?(%s)([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?\b)((\s+(-)|:)\s+).*?(?=(\s+)?[\(\[\{](\d{4}|Digital)[\)\]\}]))"
    % exclusion_keywords_regex,
    r"(?<!([A-Za-z]|(%s)(\s+)?))(((%s)([-_. ]+)?([0-9]+))|\s+([0-9]+)(\.[0-9]+)?(x\d+((\.\d+)+)?)?(\s+|#\d+|%s))"
    % (exclusion_keywords_joined, chapter_regex_keywords, manga_extensions_regex),
    r"^((#)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?)$",
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
# VOLUME
zfill_volume_int_value = 2  # 01
zfill_volume_float_value = 4  # 01.0
# CHAPTER
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

# If True, instead of grouping discord notifications based on their context.
# They will instead be grouped until the maximum of 10 is reached, regardless of context
# then sent.
group_discord_notifications_until_max = True

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
# EX: 0.6 = 60%
shortened_word_filter_percentage = 0.6

# The amount of time to sleep before checking again if all the files are fully transferred.
# Slower network response times may require a higher value.
watchdog_discover_new_files_check_interval = 5

# The time to sleep between file size checks when determining if a file is fully transferred.
# Slower network response times may require a higher value.
watchdog_file_transferred_check_interval = 1

# The libraries on the user's komga server.
# Used for sending scan reqeusts after files have been moved over.
komga_libraries = []


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
        except KeyboardInterrupt:
            for observer in self.observers:
                observer.stop()
                print("Observer Stopped")
            for observer in self.observers:
                observer.join()


# Handles our embed object along with any associated file
class Embed:
    def __init__(self, embed, file=None):
        self.embed = embed
        self.file = file


# Our array of file extensions and how many files have that extension
file_counters = {x: 0 for x in file_extensions}


# Sends a message, prints it, and writes it to a file.
def send_message(message, discord=True, error=False, log=log_to_file):
    print(message)
    if discord != False:
        send_discord_message(message)
    if error:
        errors.append(message)
        if log:
            write_to_file("errors.txt", message)
    else:
        items_changed.append(message)
        if log:
            write_to_file("changes.txt", message)


# Checks if the file is fully transferred by checking the file size
def check_if_file_is_transferred_by_size(file_path):
    # Check if the file path exists and is a file
    if os.path.isfile(file_path):
        # Get the file size before waiting for 1 second
        before_file_size = os.path.getsize(file_path)
        # Wait for 1 second
        time.sleep(watchdog_file_transferred_check_interval)
        # Get the file size after waiting for 1 second
        after_file_size = os.path.getsize(file_path)
        # Check if both file sizes are not None
        if before_file_size is not None and after_file_size is not None:
            # If both file sizes are the same, return True, indicating the file transfer is complete
            return before_file_size == after_file_size
        else:
            # If either file size is None, return False, indicating an error
            return False
    else:
        # If the file path does not exist or is not a file, return False, indicating an error
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


# Recursively gets all the files in a directory
def get_all_files_recursively_in_dir(dir_path):
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


class Handler(FileSystemEventHandler):
    def __init__(self, lock):
        self.lock = lock

    def on_created(self, event):
        with self.lock:
            start_time = time.time()
            try:
                global transferred_files
                global transferred_dirs

                extension = get_file_extension(event.src_path)
                base_name = os.path.basename(event.src_path)
                is_hidden = base_name.startswith(".")
                is_valid_file = os.path.isfile(event.src_path)
                in_file_extensions = extension in file_extensions

                if not event.event_type == "created":
                    return None

                if not is_valid_file or extension in image_extensions or is_hidden:
                    return None

                print("\n\tEvent Type: " + event.event_type)
                print("\tEvent Src Path: " + event.src_path)

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

                embed = [
                    handle_fields(
                        DiscordEmbed(
                            title="Starting Execution (WATCHDOG)",
                            color=purple_color,
                        ),
                        [
                            {
                                "name": "File Found:",
                                "value": "```" + str(event.src_path) + "```",
                                "inline": False,
                            }
                        ],
                    )
                ]

                send_discord_message(
                    None,
                    [Embed(embed[0], None)],
                )

                print("\n\tfile found:  %s" % event.src_path + "\n")

                if not os.path.isfile(event.src_path):
                    return None

                # Get a list of all files in the root directory and its subdirectories.
                files = []
                for x in download_folders:
                    files.extend(get_all_files_recursively_in_dir_watchdog(x))

                # Check if all files in the root directory and its subdirectories are fully transferred.
                while True:
                    all_files_transferred = True
                    print("\nTotal files: %s" % len(files))

                    for file in files:
                        print(
                            "\t["
                            + str(files.index(file) + 1)
                            + "/"
                            + str(len(files))
                            + "] "
                            + os.path.basename(file)
                        )

                        if file in transferred_files:
                            print("\t\t-already transferred")
                            continue

                        is_transferred = check_if_file_is_transferred_by_size(file)

                        if is_transferred:
                            print("\t\t-fully transferred")
                            transferred_files.append(file)
                            dir_path = os.path.dirname(file)
                            if (
                                dir_path not in download_folders
                                and dir_path not in transferred_dirs
                            ):
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
                        new_files = []
                        for x in download_folders:
                            new_files.extend(
                                get_all_files_recursively_in_dir_watchdog(x)
                            )

                        # If any new files started transferring while we were checking the current files,
                        # then we have more files to check.
                        if files != new_files:
                            all_files_transferred = False
                            if len(new_files) > len(files):
                                print(
                                    "\tNew transfers: +%s"
                                    % str(len(new_files) - len(files))
                                )
                                files = new_files
                            elif len(new_files) < len(files):
                                break
                        elif files == new_files:
                            break

                    time.sleep(watchdog_discover_new_files_check_interval)

                # Proceed with the next steps here.
                print("\nAll files are transferred.")

                new_transferred_dirs = []

                if transferred_dirs:
                    # if it's already a folder object, then just add it to the new list
                    for x in transferred_dirs:
                        if isinstance(x, Folder):
                            new_transferred_dirs.append(x)
                        # if it's not a folder object, then make it a folder object
                        elif not isinstance(x, Folder):
                            new_transferred_dirs.append(
                                Folder(
                                    x,
                                    None,
                                    os.path.basename(os.path.dirname(x)),
                                    os.path.basename(x),
                                    get_all_files_recursively_in_dir_watchdog(x),
                                )
                            )

                    transferred_dirs = new_transferred_dirs

            except Exception as e:
                send_message(
                    "Error with watchdog on_any_event(): " + str(e), error=True
                )

            main()
            end_time = time.time()
            time_keyword = ""

            # get the execution time
            execution_time = end_time - start_time

            if execution_time > 60:
                execution_time = int(execution_time / 60)
                if execution_time == 1:
                    time_keyword = "minute"
                else:
                    time_keyword = "minutes"
            else:
                execution_time = int(execution_time)
                if execution_time == 1:
                    time_keyword = "second"
                else:
                    time_keyword = "seconds"

            # Terminal Message
            send_message(
                "\nFinished Execution (WATCHDOG)\n\tExecution Time: "
                + str(execution_time)
                + " "
                + time_keyword,
                discord=False,
            )

            # Discord Message
            embed = [
                handle_fields(
                    DiscordEmbed(
                        title="Finished Execution (WATCHDOG)",
                        color=purple_color,
                    ),
                    [
                        {
                            "name": "Execution Time:",
                            "value": "```"
                            + str(execution_time)
                            + " "
                            + time_keyword
                            + "```",
                            "inline": False,
                        }
                    ],
                )
            ]
            send_discord_message(
                None,
                [Embed(embed[0], None)],
            )

            send_message("\nWatching for changes... (WATCHDOG)", discord=False)


# Read all the lines of a text file and return them
def get_lines_from_file(file_path, ignore=[], ignore_paths_not_in_paths=False):
    # Initialize an empty list to store the lines of the file
    results = []

    try:
        # Open the file in read mode
        with open(file_path, "r") as file:
            # If ignore_paths_not_in_paths flag is True
            if ignore_paths_not_in_paths:
                # Iterate over each line in the file
                for line in file:
                    # Strip whitespace from the line
                    line = line.strip()
                    # If the line is not empty, not in ignore, starts with any of the strings in paths, and not already in results, add it to the list
                    if (
                        line
                        and line not in ignore
                        and line.startswith(tuple(paths))
                        and line not in results
                    ):
                        results.append(line)
            # If ignore_paths_not_in_paths flag is False (default)
            else:
                # Iterate over each line in the file
                for line in file:
                    # Strip whitespace from the line
                    line = line.strip()
                    # If the line is not empty and not in ignore, add it to the list
                    if line and line not in ignore:
                        results.append(line)
    # If the file is not found
    except FileNotFoundError as e:
        # Print an error message and return an empty list
        send_message(f"File not found: {file_path}." + "\n" + str(e), error=True)
        return []
    # If any other exception is raised
    except Exception as ex:
        # Print an error message and return an empty list
        send_message(
            f"An error occured while reading {file_path}." + "\n" + str(ex), error=True
        )
        return []

    # Return the list of lines read from the file
    return results


new_volume_webhook = None


# Processes the user paths
def process_path(path, paths_with_types, paths, is_download_folders=False):
    COMMON_EXTENSION_THRESHOLD = 0.3  # 30%

    def process_auto_classification():
        nonlocal path_formats, path_extensions

        CHAPTER_THRESHOLD = 0.9  # 90%
        VOLUME_THRESHOLD = 0.9  # 90%

        files = get_all_files_recursively_in_dir(path_str)

        if files:
            print("\t\t\t- attempting auto-classification...")
            print("\t\t\t\t- got " + str(len(files)) + " files.")
            if len(files) >= 100:
                print("\t\t\t\t\t- trimming files to 75%...")
                files = files[: int(len(files) * 0.75)]
                print("\t\t\t\t\t- trimmed to " + str(len(files)) + " files.")

            print("\t\t\t\t- getting file extensions:")
            all_extensions = [get_file_extension(file) for file in files]

            path_extensions = get_common_extensions(all_extensions)

            path_extension_sets = [manga_extensions, novel_extensions]

            # If no common extensions, use default file extensions
            if not path_extensions:
                print(
                    "\t\t\t\t\t- no accepted path extensions found, defaulting to: "
                    + str(file_extensions)
                )
                path_extensions = file_extensions
            else:
                # Extend path extensions with known extension sets
                print("\t\t\t\t\t- path extensions found: " + str(path_extensions))
                print(
                    "\t\t\t\t\t- extending path extensions with known extension sets:"
                )
                print("\t\t\t\t\t\t- manga_extensions: " + str(manga_extensions))
                print("\t\t\t\t\t\t- novel_extensions: " + str(novel_extensions))
                path_extension_sets = [manga_extensions, novel_extensions]
                for ext_set in path_extension_sets:
                    if any(extension in path_extensions for extension in ext_set):
                        path_extensions.extend(
                            ext for ext in ext_set if ext not in path_extensions
                        )
                print("\t\t\t\t\t- path extensions: " + str(path_extensions))

            print("\t\t\t\t- getting path types:")
            all_types = [
                "chapter"
                if (
                    not contains_volume_keywords(file)
                    and contains_chapter_keywords(file)
                )
                else "volume"
                for file in files
            ]

            chapter_count = all_types.count("chapter")
            volume_count = all_types.count("volume")
            total_files = len(all_types)

            print("\t\t\t\t\t- chapter count: " + str(chapter_count))
            print("\t\t\t\t\t- volume count: " + str(volume_count))
            print("\t\t\t\t\t- total files: " + str(total_files))
            print(
                "\t\t\t\t\t- chapter percentage: "
                + str(int(chapter_count / total_files * 100))
                + "%"
            )
            print(
                "\t\t\t\t\t\t- required chapter percentage: "
                + str(int(CHAPTER_THRESHOLD * 100))
                + "%"
            )
            print(
                "\t\t\t\t\t- volume percentage: "
                + str(int(volume_count / total_files * 100))
                + "%"
            )
            print(
                "\t\t\t\t\t\t- required volume percentage: "
                + str(int(VOLUME_THRESHOLD * 100))
                + "%"
            )

            path_formats = [
                "chapter"
                if chapter_count / total_files >= CHAPTER_THRESHOLD
                else "volume"
                if volume_count / total_files >= VOLUME_THRESHOLD
                else file_formats
            ]

            print("\t\t\t\t\t- path types: " + str(path_formats))

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
        elif re.search(r"\.[a-zA-Z0-9]{1,4}", path_to_process):
            path_extensions = [
                ext.strip()
                for ext in path_to_process.split(",")
                if ext.strip() in file_extensions
            ]
        elif path_to_process.split(",")[0].strip() in library_types:
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
    path_obj = None

    path_str = path[0]
    print("\t\t" + path_str)

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
                path_formats=path_formats if path_formats else file_formats,
                path_extensions=path_extensions if path_extensions else file_extensions,
                library_types=path_library_types
                if path_library_types
                else library_types,
                translation_source_types=path_translation_source_types
                if path_translation_source_types
                else translation_source_types,
            )
    else:
        # process all paths except for the first one
        for path_to_process in path[1:]:
            process_single_type_path(path_to_process)

        path_obj = Path(
            path_str,
            path_formats=path_formats if path_formats else file_formats,
            path_extensions=path_extensions if path_extensions else file_extensions,
            library_types=path_library_types if path_library_types else library_types,
            translation_source_types=path_translation_source_types
            if path_translation_source_types
            else translation_source_types,
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
    global paths
    global download_folders
    global discord_webhook_url
    global paths_with_types
    global komga_libraries
    global watchdog_toggle

    parser = argparse.ArgumentParser(
        description="Scans for and extracts covers from "
        + ", ".join(file_extensions)
        + " files."
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

    parser = parser.parse_args()

    print(f"\nScript Version: {script_version_text}")

    print("\nRun Settings:")

    if parser.download_folders is not None:
        new_download_folders = []
        for download_folder in parser.download_folders:
            if download_folder:
                if r"\1" in download_folder[0]:
                    split_download_folders = download_folder[0].split(r"\1")
                    for split_download_folder in split_download_folders:
                        new_download_folders.append([split_download_folder])
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
                print("\t\tpath: " + str(item.path))
                print("\t\t\tformats: " + str(item.path_formats))
                print("\t\t\textensions: " + str(item.path_extensions))

    if parser.watchdog:
        if parser.watchdog.lower() == "true":
            if download_folders:
                watchdog_toggle = True
            else:
                send_message(
                    "Watchdog was toggled, but no download folders were passed to the script.",
                    error=True,
                )

    if parser.paths is not None:
        new_paths = []
        for path in parser.paths:
            if path:
                if r"\1" in path[0]:
                    split_paths = path[0].split(r"\1")
                    for split_path in split_paths:
                        new_paths.append([split_path])
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
                print("\t\tpath: " + str(item.path))
                print("\t\t\tformats: " + str(item.path_formats))
                print("\t\t\textensions: " + str(item.path_extensions))

    print("\twatchdog: " + str(watchdog_toggle))

    if watchdog_toggle:
        if parser.watchdog_discover_new_files_check_interval:
            if parser.watchdog_discover_new_files_check_interval.isdigit():
                global watchdog_discover_new_files_check_interval
                watchdog_discover_new_files_check_interval = int(
                    parser.watchdog_discover_new_files_check_interval
                )

        if parser.watchdog_file_transferred_check_interval:
            if parser.watchdog_file_transferred_check_interval.isdigit():
                global watchdog_file_transferred_check_interval
                watchdog_file_transferred_check_interval = int(
                    parser.watchdog_file_transferred_check_interval
                )
        print(
            "\t\twatchdog_discover_new_files_check_interval: "
            + str(watchdog_discover_new_files_check_interval)
        )
        print(
            "\t\twatchdog_file_transferred_check_interval: "
            + str(watchdog_file_transferred_check_interval)
        )

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
        print("\twebhooks: " + str(discord_webhook_url))

    if parser.bookwalker_check:
        if parser.bookwalker_check.lower() == "true":
            global bookwalker_check
            bookwalker_check = True
    print("\tbookwalker_check: " + str(bookwalker_check))

    if parser.compress:
        if parser.compress.lower() == "true":
            global compress_image_option
            compress_image_option = True
    print("\tcompress: " + str(compress_image_option))

    if parser.compress_quality:
        global image_quality
        image_quality = set_num_as_float_or_int(parser.compress_quality)
    print("\tcompress_quality: " + str(image_quality))

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
        print("\tbookwalker_webhook_urls: " + str(bookwalker_webhook_urls))

    if parser.new_volume_webhook:
        global new_volume_webhook
        new_volume_webhook = parser.new_volume_webhook
    print("\tnew_volume_webhook: " + str(new_volume_webhook))

    if parser.log_to_file:
        global log_to_file
        if parser.log_to_file.lower() == "true":
            log_to_file = True
        elif parser.log_to_file.lower() == "false":
            log_to_file = False
    print("\tlog_to_file: " + str(log_to_file))

    # Print all the settings from settings.py
    print("\nExternal Settings:")

    # Get all the variables in settings.py
    import settings as settings_file

    # get all of the non-callable variables
    settings = [
        var
        for var in dir(settings_file)
        if not callable(getattr(settings_file, var)) and not var.startswith("__")
    ]
    # print all of the variables
    for setting in settings:
        if setting == "ranked_keywords" or setting == "unacceptable_keywords":
            continue

        # the settings value
        value = getattr(settings_file, setting)

        # output the value as long as it isn't sensitive,
        # otherwise censor it, assuming there was a value
        if (
            "password" not in setting.lower()
            and "email" not in setting.lower()
            and "token" not in setting.lower()
        ) or not value:
            print("\t" + setting + ": " + str(value))
        else:
            print("\t" + setting + ": " + "********")

    print("\t" + "in_docker: " + str(in_docker))
    print("\t" + "blank_black_image_path: " + str(blank_black_image_path))
    print("\t" + "blank_white_image_path: " + str(blank_white_image_path))

    if (
        send_scan_request_to_komga_libraries_toggle
        and check_for_existing_series_toggle
        and watchdog_toggle
    ):
        komga_libraries = get_komga_libraries()
        komga_library_paths = (
            [x["root"] for x in komga_libraries] if komga_libraries else []
        )
        print("\tkomga_libraries: " + str(komga_library_paths))


# Converts the passed volume_number into a float or an int.
def set_num_as_float_or_int(volume_number, silent=False):
    try:
        if volume_number != "":
            if isinstance(volume_number, list):
                result = ""
                for num in volume_number:
                    if float(num) == int(num):
                        if num == volume_number[-1]:
                            result += str(int(num))
                        else:
                            result += str(int(num)) + "-"
                    else:
                        if num == volume_number[-1]:
                            result += str(float(num))
                        else:
                            result += str(float(num)) + "-"
                return result
            elif isinstance(volume_number, str) and re.search(r"\.", volume_number):
                volume_number = float(volume_number)
            else:
                if float(volume_number) == int(volume_number):
                    volume_number = int(volume_number)
                else:
                    volume_number = float(volume_number)
    except Exception as e:
        if not silent:
            send_message(
                "Failed to convert volume number to float or int: "
                + str(volume_number)
                + "\nERROR: "
                + str(e),
                error=True,
            )
            send_message(str(e), error=True)
        return ""
    return volume_number


# Compresses an image and saves it to a file or returns the compressed image data.
def compress_image(image_path, quality=75, to_jpg=False, raw_data=None):
    new_filename = None
    buffer = None

    # Load the image from the file or raw data
    if not raw_data:
        image = Image.open(image_path)
    else:
        image = Image.open(io.BytesIO(raw_data))

    # Convert the image to RGB if it has an alpha channel or uses a palette
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    # Determine the new filename for the compressed image
    if not raw_data:
        filename, ext = os.path.splitext(image_path)
        if to_jpg or ext.lower() == ".png":
            ext = ".jpg"
            if not to_jpg:
                to_jpg = True
        new_filename = f"{filename}{ext}"

    # Try to compress and save the image
    try:
        if not raw_data:
            image.save(new_filename, quality=quality, optimize=True)
        else:
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=50)
            return buffer.getvalue()
    except Exception as e:
        # Log the error and continue
        send_message(f"Failed to compress image {image_path}: {str(e)}", error=True)

    # Remove the original file if it's a PNG that was converted to JPG
    if to_jpg and ext.lower() == ".jpg" and os.path.isfile(image_path):
        os.remove(image_path)

    # Return the path to the compressed image file, or the compressed image data
    return new_filename if not raw_data else buffer.getvalue()


# Check the text file line by line for the passed message
def check_text_file_for_message(text_file, message):
    # Open the file in read mode
    with open(text_file, "r") as f:
        # Loop through each line in the file
        for line in f:
            # Check if the message is the same as the current line
            if message.strip() == line.strip():
                # If it is, return True
                return True
    # If we get to here, the message was not found so return False
    return False


# Adjusts discord embeds fields to fit the discord embed field limits
def handle_fields(embed, fields):
    if fields:
        # An embed can contain a maximum of 25 fields
        if len(fields) > 25:
            fields = fields[:25]
        for field in fields:
            # A field name/title is limited to 256 character and the value of the field is limited to 1024 characters
            if len(field["name"]) > 256:
                if not re.search(r"```$", field["name"]):
                    field["name"] = field["name"][:253] + "..."
                else:
                    field["name"] = field["name"][:-3][:250] + "...```"
            if len(field["value"]) > 1024:
                if not re.search(r"```$", field["value"]):
                    field["value"] = field["value"][:1021] + "..."
                else:
                    field["value"] = field["value"][:-3][:1018] + "...```"
            embed.add_embed_field(
                name=field["name"],
                value=field["value"],
                inline=field["inline"],
            )
    return embed


last_hook_index = None


# Handles picking a webhook url, to evenly distribute the load
def pick_webhook(hook, passed_webhook=None, url=None):
    global last_hook_index
    if not passed_webhook:
        if discord_webhook_url:
            if not last_hook_index and last_hook_index != 0:
                hook = discord_webhook_url[0]
            else:
                if last_hook_index == len(discord_webhook_url) - 1:
                    hook = discord_webhook_url[0]
                else:
                    hook = discord_webhook_url[last_hook_index + 1]
        if url:
            hook = url
        elif hook:
            last_hook_index = discord_webhook_url.index(hook)
    else:
        hook = passed_webhook
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
    global grouped_notifications
    global webhook_obj
    hook = None
    hook = pick_webhook(hook, passed_webhook, url)
    # Reset the grouped notifications if the embeds are the same as the grouped notifications
    if embeds == grouped_notifications:
        grouped_notifications = []
    try:
        if hook:
            webhook_obj.url = hook
            if rate_limit:
                webhook_obj.rate_limit_retry = rate_limit
            if embeds:
                if len(embeds) > 10:
                    embeds = embeds[:10]
                for embed in embeds:
                    if script_version_text:
                        embed.embed.set_footer(text=script_version_text)
                    if timestamp and not embed.embed.timestamp:
                        embed.embed.set_timestamp()
                    if image and not image_local:
                        embed.embed.set_image(url=image)
                    elif embed.file:
                        file_name = None
                        if len(embeds) == 1:
                            file_name = "cover.jpg"
                        else:
                            index = embeds.index(embed)
                            file_name = "cover_" + str(index + 1) + ".jpg"
                        webhook_obj.add_file(file=embed.file, filename=file_name)
                        embed.embed.set_image(url="attachment://" + file_name)
                    webhook_obj.add_embed(embed.embed)
            elif message:
                webhook_obj.content = message
            webhook_obj.execute()
            # Reset the webhook object
            webhook_obj = DiscordWebhook(url=None)
    except Exception as e:
        send_message(str(e), error=True, discord=False)
        webhook_obj = DiscordWebhook(url=None)


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
def remove_ignored_folder_names(dirs):
    return [x for x in dirs if x not in ignored_folder_names]


# Remove hidden folders from the list
def remove_hidden_folders(dirs):
    return [x for x in dirs if not x.startswith(".")]


# check if volume file name is a chapter
@lru_cache(maxsize=None)
def contains_chapter_keywords(file_name):
    file_name = remove_dual_space(
        re.sub(r"_extra", " ", file_name, flags=re.IGNORECASE)
    ).strip()
    # Removes underscores from the file name
    file_name_clean = replace_underscore_in_name(file_name)
    file_name_clean = re.sub(r"c1fi7", "", file_name_clean, re.IGNORECASE)
    file_name_clean = remove_dual_space(
        re.sub(r"(_)", " ", file_name_clean).strip()
    ).strip()
    chapter_search_results = [
        re.search(pattern, file_name_clean, re.IGNORECASE)
        for pattern in chapter_searches
    ]
    # remove empty results
    chapter_search_results = [x for x in chapter_search_results if x]
    found = any(
        result and not re.search(r"^((\(|\{|\[)\d{4}(\]|\}|\)))$", result.group(0))
        for result in chapter_search_results
    )
    if not found and not contains_volume_keywords(file_name):
        without_year = re.sub(volume_year_regex, "", file_name, flags=re.IGNORECASE)
        # checks for any number in the file name that isn't at the beginning of the string
        # numbers at the beginning of the string are considered part of the series_name
        chapter_numbers_found = re.search(
            r"(?<!^)(?<!\d\.)\b([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?(\.\d+)?\b",
            without_year,
        )
        if chapter_numbers_found:
            found = True
    return found


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
    # remove _extra from the file name, replace with space
    file = remove_dual_space(re.sub(r"_extra", " ", file, flags=re.IGNORECASE)).strip()
    result = volume_regex.search(
        replace_underscore_in_name(remove_bracketed_info_from_name(file))
    )
    if result:
        return True
    return False


# Removes all chapter releases
def filter_non_chapters(files):
    return [
        file
        for file in files
        if not contains_chapter_keywords(file) or contains_volume_keywords(file)
    ]


# Cleans up the files array before usage
def clean_and_sort(
    root,
    files=[],
    dirs=[],
    sort=False,
    chapters=chapter_support_toggle,
    just_these_files=[],
    just_these_dirs=[],
    skip_remove_ignored_folder_names=False,
    skip_remove_hidden_files=False,
    skip_remove_unaccepted_file_types=False,
    skip_remove_hidden_folders=False,
    keep_images_in_just_these_files=False,
    is_correct_extensions_feature=False,
    test_mode=False,
):
    if (
        check_for_existing_series_toggle
        and root not in cached_paths
        and root not in download_folders
        and root not in paths
        and not any(root.startswith(path) for path in download_folders)
        and not test_mode
    ):
        write_to_file(
            "cached_paths.txt",
            root,
            without_timestamp=True,
            check_for_dup=True,
        )
    if ignored_folder_names and not skip_remove_ignored_folder_names:
        ignored_parts = [
            part for part in root.split(os.sep) if part and part in ignored_folder_names
        ]
        if any(ignored_parts):
            return [], []
    if files:
        if sort:
            files.sort()
        if not skip_remove_hidden_files:
            files = remove_hidden_files(files)
        if not skip_remove_unaccepted_file_types:
            if not is_correct_extensions_feature:
                files = remove_unaccepted_file_types(
                    files, root, file_extensions, test_mode=test_mode
                )
            else:
                files = remove_unaccepted_file_types(
                    files, root, file_extensions + rar_extensions, test_mode=test_mode
                )
        if just_these_files and files:
            # just_these_basenames = [os.path.basename(x) for x in just_these_files]
            files = [
                x
                for x in files
                if os.path.join(root, x) in just_these_files
                or (
                    keep_images_in_just_these_files
                    and get_file_extension(x) in image_extensions
                )
            ]
            # for j_file in just_these_files:
            #     if os.path.basename(j_file) not in files:
            #         print("\tRemoved from just_these_files: " + j_file)
        if not chapters:
            files = filter_non_chapters(files)
    if dirs:
        if sort:
            dirs.sort()
        if not skip_remove_hidden_folders:
            dirs = remove_hidden_folders(dirs)
        if just_these_dirs and dirs:
            allowed_dirs = []
            for transferred_dir in just_these_dirs:
                for dir in dirs:
                    if transferred_dir.folder_name == dir:
                        current_files = get_all_files_recursively_in_dir_watchdog(
                            os.path.join(root, dir)
                        )
                        if len(transferred_dir.files) == len(current_files) or len(
                            current_files
                        ) < len(transferred_dir.files):
                            allowed_dirs.append(dir)
            dirs = allowed_dirs
        if not skip_remove_ignored_folder_names:
            dirs = remove_ignored_folder_names(dirs)
    return files, dirs


# Retrieves the file extension on the passed file
def get_file_extension(file):
    return os.path.splitext(file)[1]


# Gets the predicted file extension from the file header using
# import filetype
def get_file_extension_from_header(file):
    extension_from_name = get_file_extension(file)
    if extension_from_name in manga_extensions or extension_from_name in rar_extensions:
        try:
            kind = filetype.guess(file)
            if kind is None:
                return None
            elif "." + kind.extension in manga_extensions:
                return ".cbz"
            elif "." + kind.extension in rar_extensions:
                return ".cbr"
            else:
                return "." + kind.extension
        except Exception as e:
            send_message(str(e), error=True)
            return None
    else:
        return None


# Returns an extensionless name
def get_extensionless_name(file):
    return os.path.splitext(file)[0]


# Trades out our regular files for file objects
def upgrade_to_file_class(
    files,
    root,
    skip_get_file_extension_from_header=True,
    is_correct_extensions_feature=False,
    test_mode=False,
    clean=True,
):
    # Avoid any features that require an actual file
    if test_mode:
        skip_get_file_extension_from_header = True

    # Clean up the files array before usage
    if clean:
        files = clean_and_sort(
            root,
            files,
            is_correct_extensions_feature=is_correct_extensions_feature,
            test_mode=test_mode,
        )[0]

    # Create a list of tuples with arguments to pass to the File constructor
    file_args = [
        (
            file,
            get_extensionless_name(file),
            (
                get_series_name_from_file_name_chapter(file, root, chapter_number)
                if file_type == "chapter"
                else get_series_name_from_file_name(file, root, test_mode=test_mode)
            ),
            get_file_extension(file),
            root,
            os.path.join(root, file),
            get_extensionless_name(os.path.join(root, file)),
            chapter_number,
            file_type,
            get_file_extension_from_header(os.path.join(root, file))
            if not skip_get_file_extension_from_header
            else None,
        )
        for file, file_type, chapter_number in zip(
            files,
            [
                "chapter"
                if not contains_volume_keywords(file)
                and contains_chapter_keywords(file)
                else "volume"
                for file in files
            ],
            [
                remove_everything_but_volume_num([file], chapter=True)
                if file_type == "chapter"
                else remove_everything_but_volume_num([file])
                for file, file_type in zip(
                    files,
                    [
                        "chapter"
                        if not contains_volume_keywords(file)
                        and contains_chapter_keywords(file)
                        else "volume"
                        for file in files
                    ],
                )
            ],
        )
    ]

    # Process the files sequentially
    results = [File(*args) for args in file_args]

    return results


# Updates our output stats
def update_stats(file):
    if not os.path.isfile(file.path):
        return

    global file_counters
    if file.extension in file_counters:
        file_counters[file.extension] += 1
    else:
        file_counters[file.extension] = 1


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
                        "//opf:manifest/opf:item[@id='" + cover_id + "']",
                        namespaces=namespaces,
                    )
                    if cover_href:
                        cover_href = cover_href[0].get("href")
                        if re.search(r"%", cover_href):
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
    if not skip_folder_check:
        files = clean_and_sort(root, os.listdir(root))[0]
    if (len(files) == 1 or skip_folder_check) or (
        download_folders and root in download_folders
    ):
        volume_file_status = contains_volume_keywords(file_name)
        chapter_file_status = contains_chapter_keywords(file_name)
        exception_keyword_status = check_for_exception_keywords(
            file_name, exception_keywords
        )
        if (
            not volume_file_status and not chapter_file_status
        ) and not exception_keyword_status:
            return True
    return False


# Checks similarity between two strings.
@lru_cache(maxsize=None)
def similar(a, b):
    if a == "" or b == "":
        return 0.0
    else:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# Sets the modification date of the passed file path to the passed date.
def set_modification_date(file_path, date):
    try:
        os.utime(file_path, (get_modification_date(file_path), date))
    except Exception as e:
        send_message(
            "ERROR: Could not set modification date of "
            + file_path
            + "\nERROR: "
            + str(e),
            error=True,
        )


# Moves the image into a folder if said image exists. Also checks for a cover/poster image and moves that.
def move_images(
    file,
    folder_name,
    group=False,
    highest_num=None,
    highest_part="",
    is_chapter_dir=False,
):
    for extension in image_extensions:
        image = file.extensionless_path + extension
        if os.path.isfile(image):
            # check that the image is not already in the folder
            if not os.path.isfile(os.path.join(folder_name, os.path.basename(image))):
                shutil.move(image, folder_name)
            else:
                remove_file(
                    os.path.join(folder_name, os.path.basename(image)), silent=True
                )
                shutil.move(image, folder_name)
        for cover_file_name in series_cover_file_names:
            cover_image_file_name = cover_file_name + extension
            cover_image_file_path = os.path.join(file.root, cover_image_file_name)
            if os.path.isfile(cover_image_file_path):
                # check that the image is not already in the folder
                if not os.path.isfile(os.path.join(folder_name, cover_image_file_name)):
                    shutil.move(cover_image_file_path, folder_name)
                elif file.volume_number == 1 and (
                    not use_latest_volume_cover_as_series_cover or is_chapter_dir
                ):
                    remove_file(
                        os.path.join(folder_name, cover_image_file_name), silent=True
                    )
                    shutil.move(cover_image_file_path, folder_name)
                elif (
                    use_latest_volume_cover_as_series_cover
                    and highest_num != None
                    and file.file_type == "volume"
                    and (
                        file.volume_number == highest_num
                        or (
                            isinstance(file.volume_number, list)
                            and highest_num in file.volume_number
                        )
                    )
                    and file.volume_part == highest_part
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
def get_series_name_from_file_name(name, root, test_mode=False):
    name = remove_dual_space(re.sub(r"_extra", " ", name, flags=re.IGNORECASE)).strip()

    # name = remove_bracketed_info_from_name(name)
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
            r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(%s)(\.|)([-_. ]|)([0-9]+)(\b|\s).*"
            % volume_regex_keywords,
            name,
            flags=re.IGNORECASE,
        ):
            name = (
                re.sub(
                    r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(%s)(\.|)([-_. ]|)([0-9]+)(\b|\s).*"
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
    if (
        not name
        and root
        and (
            os.path.basename(root) not in str(download_folders) or not download_folders
        )
        and (os.path.basename(root) not in str(paths) or not paths)
    ):
        name = remove_bracketed_info_from_name(os.path.basename(root))

    return name


# Cleans the chapter file_name to retrieve the series_name
@lru_cache(maxsize=None)
def chapter_file_name_cleaning(
    file_name, chapter_number="", skip=False, regex_matched=False
):
    # removes any brackets and their contents
    file_name = remove_bracketed_info_from_name(file_name)

    # Remove any single brackets at the end of the file_name
    # EX: "Death Note - Bonus Chapter (" --> "Death Note - Bonus Chapter"
    file_name = re.sub(r"(\s(([\(\[\{])|([\)\]\}])))$", "", file_name).strip()

    # EX: "006.3 - One Piece" --> "One Piece"
    if regex_matched != 3:
        file_name = re.sub(
            r"(^([0-9]+)(([-_.])([0-9]+)|)+(\s+)?([-_]+)(\s+))", "", file_name
        ).strip()

    # Remove - at the end of the file_name
    # EX: " One Piece -" --> "One Piece"
    file_name = re.sub(r"(-\s*)$", "", file_name).strip()

    # Return if we have nothing but a digit left, if not skip
    if re.sub(r"(#)", "", file_name).isdigit() and not skip:
        return ""
    elif re.sub(r"(#)", "", file_name).replace(".", "", 1).isdigit() and not skip:
        return ""

    # if chapter_number and it's at the end of the file_name, remove it
    # EX: "One Piece 001" --> "One Piece"
    if not regex_matched:
        if chapter_number != "" and re.search(
            r"-?(\s+)?((?<!({})(\s+)?)(\s+)?\b#?((0+)?({}|{}))#?$)".format(
                chapter_regex_keywords,
                chapter_number,
                set_num_as_float_or_int(chapter_number),
            ),
            file_name,
        ):
            file_name = re.sub(
                r"-?(\s+)?((?<!({})(\s+)?)(\s+)?\b#?((0+)?({}|{}))#?$)".format(
                    chapter_regex_keywords,
                    chapter_number,
                    set_num_as_float_or_int(chapter_number),
                ),
                "",
                file_name,
            ).strip()

    # Remove any season keywords
    if re.search(r"(Season|Sea| S)(\s+)?([0-9]+)$", file_name, re.IGNORECASE):
        file_name = re.sub(
            r"(Season|Sea| S)(\s+)?([0-9]+)$", "", file_name, flags=re.IGNORECASE
        )

    # Remove any subtitle
    # EX: "Solo Leveling 179.1 - Epilogue 01 (2023) (Digital) (LuCaZ).cbz"
    # "179.1 - Epilogue 01" --> "179.1"
    if re.search(r"(^\d+)", file_name.strip()):
        file_name = re.sub(r"((\s+(-)|:)\s+).*$", "", file_name, re.IGNORECASE).strip()

    return file_name


def get_series_name_from_file_name_chapter(name, root, chapter_number=""):
    name = remove_dual_space(re.sub(r"_extra", " ", name, flags=re.IGNORECASE)).strip()

    # remove the file extension
    name = re.sub(r"(%s)$" % file_extensions_regex, "", name).strip()

    # remove underscores
    name = replace_underscore_in_name(name)

    regex_matched = False
    for regex in chapter_searches:
        search = re.search(regex, name, re.IGNORECASE)
        if search:
            regex_matched = True
            name = re.sub(regex + "(.*)", "", name, flags=re.IGNORECASE).strip()
            break

    if isinstance(chapter_number, list):
        result = chapter_file_name_cleaning(
            name, chapter_number[0], regex_matched=regex_matched
        )
    else:
        result = chapter_file_name_cleaning(
            name, chapter_number, regex_matched=regex_matched
        )
    if (
        not result
        and root
        and (
            os.path.basename(root) not in str(download_folders) or not download_folders
        )
        and (os.path.basename(root) not in str(paths) or not paths)
    ):
        result = remove_bracketed_info_from_name(os.path.basename(root))
    return result


# Creates folders for our stray volumes sitting in the root of the download folder.
def create_folders_for_items_in_download_folder(group=False):
    global transferred_files
    for download_folder in download_folders:
        if os.path.exists(download_folder):
            try:
                for root, dirs, files in scandir.walk(download_folder):
                    clean = None
                    if (
                        watchdog_toggle
                        and download_folders
                        and any(x for x in download_folders if root.startswith(x))
                    ):
                        clean = clean_and_sort(
                            root,
                            files,
                            dirs,
                            just_these_files=transferred_files,
                            just_these_dirs=transferred_dirs,
                        )
                    else:
                        clean = clean_and_sort(root, files, dirs)
                    files, dirs = clean[0], clean[1]
                    if not files:
                        continue
                    global folder_accessor
                    file_objects = upgrade_to_file_class(files, root)
                    folder_accessor = Folder(
                        root,
                        dirs,
                        os.path.basename(os.path.dirname(root)),
                        os.path.basename(root),
                        file_objects,
                    )
                    for file in folder_accessor.files:
                        if file.extension in file_extensions and os.path.basename(
                            download_folder
                        ) == os.path.basename(file.root):
                            done = False
                            if move_lone_files_to_similar_folder and dirs:
                                for dir in dirs:
                                    if (
                                        dir.strip().lower()
                                        == file.basename.strip().lower()
                                    ) or (
                                        similar(
                                            replace_underscore_in_name(
                                                remove_punctuation(dir)
                                            )
                                            .strip()
                                            .lower(),
                                            replace_underscore_in_name(
                                                remove_punctuation(file.basename)
                                            )
                                            .strip()
                                            .lower(),
                                        )
                                        >= required_similarity_score
                                    ):
                                        if (
                                            replace_series_name_in_file_name_with_similar_folder_name
                                            and file.basename != dir
                                        ):
                                            # replace the series name in the file name with the folder name and rename the file
                                            new_file_name = re.sub(
                                                file.basename,
                                                dir,
                                                file.name,
                                                flags=re.IGNORECASE,
                                            )
                                            # create file object
                                            new_file_obj = File(
                                                new_file_name,
                                                get_extensionless_name(new_file_name),
                                                get_series_name_from_file_name(
                                                    new_file_name, root
                                                ),
                                                get_file_extension(new_file_name),
                                                root,
                                                os.path.join(root, new_file_name),
                                                get_extensionless_name(
                                                    os.path.join(root, new_file_name)
                                                ),
                                                None,
                                                None,
                                                get_file_extension_from_header(
                                                    os.path.join(root, new_file_name)
                                                ),
                                            )
                                            # if it doesn't already exist
                                            if not os.path.isfile(
                                                os.path.join(
                                                    file.root, new_file_obj.name
                                                )
                                            ):
                                                rename_file(
                                                    file.path,
                                                    new_file_obj.path,
                                                )
                                                file = new_file_obj
                                            else:
                                                # if it does exist, delete the file
                                                remove_file(file.path, silent=True)
                                        # check that the file doesn't already exist in the folder
                                        if os.path.isfile(
                                            file.path
                                        ) and not os.path.isfile(
                                            os.path.join(root, dir, file.name)
                                        ):
                                            # it doesn't, we move it and the image associated with it, to that folder
                                            move_file(
                                                file,
                                                os.path.join(root, dir),
                                                group=group,
                                            )
                                            if watchdog_toggle:
                                                transferred_files.append(
                                                    os.path.join(root, dir, file.name)
                                                )
                                                # remove old item from transferred files
                                                if file.path in transferred_files:
                                                    transferred_files.remove(file.path)
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
                            if not done:
                                similarity_result = similar(file.name, file.basename)
                                write_to_file(
                                    "changes.txt",
                                    "Similarity Result between: "
                                    + file.name
                                    + " and "
                                    + file.basename
                                    + " was "
                                    + str(similarity_result),
                                )
                                folder_location = os.path.join(file.root, file.basename)
                                does_folder_exist = os.path.exists(folder_location)
                                if not does_folder_exist:
                                    os.mkdir(folder_location)
                                move_file(file, folder_location, group=group)
                                if watchdog_toggle:
                                    transferred_files.append(
                                        os.path.join(folder_location, file.name)
                                    )
                                    # remove old item from transferred files
                                    if file.path in transferred_files:
                                        transferred_files.remove(file.path)
            except Exception as e:
                send_message(str(e), error=True)
        else:
            if download_folder == "":
                send_message("\nERROR: Path cannot be empty.", error=True)
            else:
                send_message(
                    "\nERROR: " + download_folder + " is an invalid path.\n", error=True
                )
    if group and grouped_notifications and not group_discord_notifications_until_max:
        send_discord_message(None, grouped_notifications)


def get_percent_for_folder(files, extensions=None, file_type=None):
    # If the list of files is empty, return 0
    if not files:
        return 0

    # Initialize the count of matching files
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
    # If neither a file type nor a list of extensions is specified, return 0
    else:
        return 0

    # Calculate the percentage of files in the list that match the specified extension or file type
    return (count / len(files)) * 100


# Determines if a volume file is a multi-volume file or not
# EX: TRUE == series_title v01-03.cbz
# EX: FALSE == series_title v01.cbz
@lru_cache(maxsize=None)
def check_for_multi_volume_file(file_name, chapter=False):
    # Set the list of keywords to search for, volume keywords by default
    keywords = volume_regex_keywords

    # If the chapter flag is True, set the list of keywords to search for to the chapter keywords instead
    if chapter:
        keywords = chapter_regex_keywords + "|"

    # Search for a multi-volume or multi-chapter pattern in the file name, ignoring any bracketed information in the name
    if re.search(
        # Use regular expressions to search for the pattern of multiple volumes or chapters
        r"(\b({})(\.)?(\s+)?([0-9]+(\.[0-9]+)?)([-]([0-9]+(\.[0-9]+)?))+\b)".format(
            keywords
        ),
        remove_bracketed_info_from_name(file_name),
        re.IGNORECASE,  # Ignore case when searching
    ):
        # If the pattern is found, return True
        return True
    else:
        # If the pattern is not found, return False
        return False


# Converts our list of numbers into an array of numbers, returning only the lowest and highest numbers in the list
# EX "1, 2, 3" --> [1, 3]
def get_min_and_max_numbers(string):
    # initialize an empty list to hold the numbers
    numbers = []

    # replace hyphens and underscores with spaces using regular expressions
    numbers_search = re.sub(r"[-_]", " ", string)

    # remove any duplicate spaces
    numbers_search = remove_dual_space(numbers_search).strip()

    # split the resulting string into a list of individual strings
    numbers_search = numbers_search.split(" ")

    # convert each string in the list to either an integer or a float using the set_num_as_float_or_int function
    numbers_search = [set_num_as_float_or_int(num) for num in numbers_search]

    # remove any empty items from the list
    numbers_search = [num for num in numbers_search if num]

    # if the resulting list is not empty, filter it further
    if numbers_search:
        # get lowest number in list
        lowest_number = min(numbers_search)

        # get highest number in list
        highest_number = max(numbers_search)

        # discard any numbers inbetween the lowest and highest number
        if lowest_number and highest_number:
            numbers = [lowest_number, highest_number]
        elif lowest_number and not highest_number:
            numbers = [lowest_number]
        elif highest_number and not lowest_number:
            numbers = [highest_number]

    # return the resulting list of numbers
    return numbers


# Finds the volume number and strips out everything except that number
def remove_everything_but_volume_num(files, chapter=False):
    results = []
    is_multi_volume = False
    keywords = volume_regex_keywords
    if chapter:
        keywords = chapter_regex_keywords
    for file in files[:]:
        file = remove_dual_space(
            re.sub(r"_extra", " ", file, flags=re.IGNORECASE)
        ).strip()
        result = None
        file = replace_underscore_in_name(file)
        is_multi_volume = check_for_multi_volume_file(file, chapter=chapter)
        if not chapter:
            result = re.search(
                r"\b({})((\.)|)(\s+)?([0-9]+)(([-_.])([0-9]+)|)+\b".format(keywords),
                file,
                re.IGNORECASE,
            )
        else:
            if has_multiple_numbers(file):
                if re.search(
                    r"((%s)(\.)?(\s+)?(#)?(([0-9]+)(([-_.])([0-9]+)|)+))$"
                    % exclusion_keywords_joined,
                    re.sub(r"(%s)" % file_extensions_regex, "", file),
                    re.IGNORECASE,
                ):
                    file = re.sub(
                        r"((%s)(\.)?(\s+)?(#)?(([0-9]+)(([-_.])([0-9]+)|)+))$"
                        % exclusion_keywords_joined,
                        "",
                        re.sub(r"(%s)" % file_extensions_regex, "", file),
                        re.IGNORECASE,
                    ).strip()
                    # remove - at the end of the string
                    if not re.search(
                        r"-(\s+)?(#)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(\s+)?-", file
                    ) and re.search(r"(-)$", file):
                        file = re.sub(r"(-)$", "", file).strip()

            # With a chapter keyword, without, but before bracketed info, or without and with a manga extension or a novel exteion after the number
            # Series Name c001.extension or Series Name 001 (2021) (Digital) (Release).extension or Series Name 001.extension
            for search in chapter_searches:
                search_result = re.search(search, file, re.IGNORECASE)
                if search_result:
                    result = search_result
                    break

        if result:
            try:
                file = result
                if hasattr(file, "group"):
                    file = file.group()
                else:
                    file = ""
                if chapter:
                    # Remove any subtitle
                    # EX: "Solo Leveling 179.1 - Epilogue 01 (2023) (Digital) (LuCaZ).cbz" -->
                    # "" 179.1 - Epilogue 01"  --> "179.1"
                    if re.search(r"(^\d+)", file.strip()):
                        file = re.sub(
                            r"((\s+(-)|:)\s+).*$", "", file, re.IGNORECASE
                        ).strip()

                    # Removes starting period
                    # EX: "series_name. 031 (2023).cbz" --> "'. 031 (2023)"" --> "031 (2023)"
                    file = re.sub(r"^(\s+)?(\.)", "", file, re.IGNORECASE).strip()

                    # Removes # from the number
                    # EX: #001 becomes 001
                    file = re.sub(r"($#)", "", file, re.IGNORECASE).strip()

                    # Removes # from bewteen the numbers
                    # EX: 154#3 becomes 154
                    if re.search(r"(\d+#\d+)", file):
                        file = re.sub(
                            r"((#)([0-9]+)(([-_.])([0-9]+)|)+)", "", file
                        ).strip()

                    # removes part from chapter number
                    # EX: 053x1 or c053x1 becomes 053 or c053
                    file = re.sub(r"(x[0-9]+)", "", file, re.IGNORECASE).strip()

                    # removes the bracketed info from the end of the string, empty or not
                    file = remove_bracketed_info_from_name(file)

                    # Removes the - characters.extension from the end of the string, with
                    # the dash and characters being optional
                    # EX:  - prologue.extension or .extension
                    file = re.sub(
                        r"(((\s+)?-(\s+)?([A-Za-z]+))?(%s))" % file_extensions_regex,
                        "",
                        file,
                        re.IGNORECASE,
                    ).strip()

                    # - #404 - becomes #404
                    file = re.sub(r"^- | -$", "", file).strip()

                    # remove # at the beginning of the string
                    # EX: #001 becomes 001
                    file = re.sub(r"^#", "", file).strip()

                file = re.sub(
                    r"\b({})(\.|)([-_. ])?".format(keywords),
                    "",
                    file,
                    flags=re.IGNORECASE,
                ).strip()

                if re.search(
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
                    if is_multi_volume or re.search(
                        r"([0-9]+(\.[0-9]+)?)([-_]([0-9]+(\.[0-9]+)?))+", file
                    ):
                        if not is_multi_volume:
                            is_multi_volume = True
                        multi_numbers = get_min_and_max_numbers(file)
                        if multi_numbers:
                            if len(multi_numbers) > 1:
                                for volume_number in multi_numbers:
                                    results.append(float(volume_number))
                            elif len(multi_numbers) == 1:
                                results.append(float(multi_numbers[0]))
                                is_multi_volume = False
                    else:
                        results.append(float(file))
                except ValueError:
                    message = "Not a float: " + files[0]
                    print(message)
                    write_to_file("errors.txt", message)
            except AttributeError:
                print(str(AttributeError.with_traceback))
        else:
            if file in files:
                files.remove(file)
    if is_multi_volume == True and results:
        return results
    elif results and (len(results) == len(files)):
        return results[0]
    elif not results:
        return ""


volume_year_regex = r"(\(|\[|\{)(\d{4})(\)|\]|\})"


# Get the release year from the file metadata, if present, otherwise from the file name
def get_release_year(name, metadata=None):
    result = None
    converted = None
    match = re.search(volume_year_regex, name, re.IGNORECASE)
    if match:
        result = int(re.sub(r"(\(|\[|\{)|(\)|\]|\})", "", match.group(0)))
    if metadata and not result:
        release_year_from_file = None
        if "Year" in metadata:
            release_year_from_file = metadata["Year"]
            if release_year_from_file and release_year_from_file.isdigit():
                converted = int(release_year_from_file)
        elif "dc:date" in metadata:
            release_year_from_file = metadata["dc:date"].strip()
            release_year_from_file = re.search(r"\d{4}", release_year_from_file)
            if release_year_from_file:
                release_year_from_file = release_year_from_file.group(0)
                if release_year_from_file and release_year_from_file.isdigit():
                    converted = int(release_year_from_file)
        if converted and converted >= 1000:
            result = converted

    return result


# Compile the regular expression pattern outside of the function
fixed_volume_pattern = re.compile(
    r"(\(|\[|\{)(f|fix(ed)?)([-_. :]+)?([0-9]+)?(\)|\]|\})", re.IGNORECASE
)


# Determines if the release is a fixed release
@lru_cache(maxsize=None)
def is_fixed_volume(name, fixed_volume_pattern=fixed_volume_pattern):
    result = fixed_volume_pattern.search(name)
    return True if result else False


# Retrieves the release_group on the file name
def get_extra_from_group(name, groups):
    if not groups:
        return ""

    # Define regular expressions for left and right brackets
    left_brackets = r"(\(|\[|\{)"
    right_brackets = r"(\)|\]|\})"

    # Compile a regular expression pattern for removing brackets
    bracket_pattern = re.compile(rf"^{left_brackets}|{right_brackets}$")

    # Combine all groups into a single regular expression pattern
    combined_pattern = re.compile(
        rf"{left_brackets}({'|'.join(map(re.escape, groups))}){right_brackets}",
        re.IGNORECASE,
    )

    search = combined_pattern.search(name)

    # If a match is found
    if search:
        result = search.group()

        if result:
            # Remove any brackets that the matched string starts with or ends with
            result = bracket_pattern.sub("", result)

        # Return the result after removing brackets
        return result

    # If no match is found, return an empty string
    return ""


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
    if series_name:
        # remove it from the file name
        file = re.sub(re.escape(series_name), "", file, flags=re.IGNORECASE).strip()
    if subtitle:
        # remove it from the file name
        file = re.sub(re.escape(subtitle), "", file, flags=re.IGNORECASE).strip()

    if not chapter:
        # Remove the matched string from the input file name
        file = rx_remove.sub("", file).strip()
        search = rx_search_part.search(file)
        if search:
            result = search.group(1)
            result = re.sub(r"Part([-_. ]|)+", " ", result, flags=re.IGNORECASE).strip()
            try:
                return float(result)
            except ValueError as ve:
                send_message(
                    "Not a float: "
                    + str(result)
                    + " for "
                    + file
                    + "\nERROR: "
                    + str(ve),
                    error=True,
                )
                result = ""
    else:
        search = rx_search_chapters.search(file)
        if search:
            part_search = re.search(
                r"((x|#)([0-9]+)(([-_.])([0-9]+)|)+)", search.group(0), re.IGNORECASE
            )
            if part_search:
                # remove the x or # from the string
                result = rx_remove_x_hash.sub("", part_search.group(0))
                number = set_num_as_float_or_int(result)
                if number:
                    result = number
    return result


# Retrieves the publisher from the passed in metadata
def get_publisher_from_meta(metadata):
    publisher = None
    if metadata:
        if "Publisher" in metadata:
            publisher = titlecase(metadata["Publisher"])
            publisher = remove_dual_space(publisher)
            publisher = re.sub(r", LLC.*", "", publisher)
        elif "dc:publisher" in metadata:
            publisher = titlecase(metadata["dc:publisher"])
            publisher = remove_dual_space(publisher)
            publisher = re.sub(r", LLC.*", "", publisher).strip()
            publisher = re.sub(r"LLC", "", publisher).strip()
            publisher = re.sub(r":", " - ", publisher).strip()
            publisher = remove_dual_space(publisher)
    return publisher


# Trades out our regular files for file objects
def upgrade_to_volume_class(
    files,
    skip_release_year=False,
    skip_file_part=False,
    skip_fixed_volume=False,
    skip_release_group=False,
    skip_extras=False,
    skip_publisher=False,
    skip_premium_content=False,
    skip_subtitle=False,
    skip_multi_volume=False,
    test_mode=False,
):
    if test_mode:
        skip_release_year = True
        skip_publisher = True
        skip_premium_content = True
    results = []
    for file in files:
        internal_metadata = None
        publisher = Publisher(None, None)
        if not skip_release_year or not skip_publisher:
            internal_metadata = get_internal_metadata(file.path, file.extension)
        if add_publisher_name_to_file_name_when_renaming:
            if internal_metadata and not skip_publisher:
                publisher.from_meta = get_publisher_from_meta(internal_metadata)
            if publishers:
                publisher.from_name = get_extra_from_group(file.name, publishers)
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
            (is_fixed_volume(file.name) if not skip_fixed_volume else False),
            (
                get_extra_from_group(file.name, release_groups)
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
                if not skip_premium_content
                else False
            ),
            None,
            file.header_extension,
            (
                (
                    check_for_multi_volume_file(file.name)
                    if file.file_type != "chapter"
                    else check_for_multi_volume_file(file.name, chapter=True)
                )
                if not skip_multi_volume
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
            if file_obj.subtitle:
                write_to_file(
                    "extracted_subtitles.txt",
                    file_obj.name + " - " + file_obj.subtitle,
                    without_timestamp=True,
                    check_for_dup=True,
                )
        if not skip_file_part:
            if file_obj.file_type != "chapter":
                file_obj.volume_part = get_file_part(
                    file_obj.name,
                    series_name=file_obj.series_name,
                    subtitle=file_obj.subtitle,
                )
            else:
                file_obj.volume_part = get_file_part(
                    file_obj.name,
                    series_name=file_obj.series_name,
                    subtitle=file_obj.subtitle,
                    chapter=True,
                )
        if not skip_extras:
            if file_obj.file_type != "chapter":
                file_obj.extras = get_extras(
                    file_obj.name,
                    series_name=file_obj.series_name,
                    subtitle=file_obj.subtitle,
                )
            else:
                file_obj.extras = get_extras(
                    file_obj.name,
                    chapter=True,
                    series_name=file_obj.series_name,
                    subtitle=file_obj.subtitle,
                )
        if file_obj.is_one_shot:
            file_obj.volume_number = 1

        if file_obj.volume_number:
            if (
                file_obj.volume_part
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


# Retrieves the release_group score from the list, using a high similarity
def get_keyword_score(name, file_type, ranked_keywords):
    tags = []
    score = 0.0
    for keyword in ranked_keywords:
        if file_type == keyword.file_type or keyword.file_type == "both":
            search = re.search(keyword.name, name, re.IGNORECASE)
            if search:
                tags.append(Keyword(search.group(0), keyword.score))
                score += keyword.score
    return RankedKeywordResult(score, tags)


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
    downloaded_release_result = get_keyword_score(
        downloaded_release.name, downloaded_release.file_type, ranked_keywords
    )
    current_release_result = get_keyword_score(
        current_release.name, current_release.file_type, ranked_keywords
    )
    upgrade_result = UpgradeResult(
        downloaded_release_result.total_score > current_release_result.total_score,
        downloaded_release_result,
        current_release_result,
    )
    return upgrade_result


# Deletes hidden files, used when checking if a folder is empty.
def delete_hidden_files(files, root):
    for file in files[:]:
        if (str(file)).startswith(".") and os.path.isfile(os.path.join(root, file)):
            remove_file(os.path.join(root, file), silent=True)


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

    # The series cover for the file. (cover.jpg)
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
def add_to_grouped_notifications(embed, passed_webhook=None):
    global grouped_notifications
    if len(grouped_notifications) >= discord_embed_limit:
        send_discord_message(None, grouped_notifications, passed_webhook=passed_webhook)

    # set timestamp on embed
    embed.embed.set_timestamp()

    # add embed to list
    grouped_notifications.append(embed)


# Removes the specified folder and all of its contents.
def remove_folder(folder):
    result = False
    if os.path.isdir(folder) and (
        folder not in download_folders and folder not in paths
    ):
        shutil.rmtree(folder)
        if not os.path.isdir(folder):
            send_message(f"\t\t\tRemoved {folder}", discord=False)
            result = True
        else:
            send_message(f"\t\t\tFailed to remove {folder}", error=True)
    return result


# Removes a file and its associated image files.
def remove_file(full_file_path, silent=False, group=False):
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
        send_message(f"Failed to remove {full_file_path}: {str(e)}", error=True)
        return False

    # Check if the file was successfully removed
    if os.path.isfile(full_file_path):
        # Send an error message if the file still exists
        send_message(f"Failed to remove {full_file_path}.", error=True)
        return False

    if not silent:
        # Send a notification that the file was removed
        send_message(f"File removed: {full_file_path}", discord=False)

        # If the file is not an image, remove associated images
        if get_file_extension(full_file_path) not in image_extensions:
            remove_images(full_file_path)

        # Create a Discord embed
        embed = [
            handle_fields(
                DiscordEmbed(
                    title="Removed File",
                    color=red_color,
                ),
                fields=[
                    {
                        "name": "File:",
                        "value": "```" + os.path.basename(full_file_path) + "```",
                        "inline": False,
                    },
                    {
                        "name": "Location:",
                        "value": "```" + os.path.dirname(full_file_path) + "```",
                        "inline": False,
                    },
                ],
            )
        ]

        # Add it to the group of notifications
        add_to_grouped_notifications(Embed(embed[0], None))

    return True


# Move a file
def move_file(
    file,
    new_location,
    silent=False,
    group=False,
    highest_num=None,
    highest_part="",
    is_chapter_dir=False,
):
    try:
        if os.path.isfile(file.path):
            shutil.move(file.path, new_location)
            if os.path.isfile(os.path.join(new_location, file.name)):
                if not silent:
                    send_message(
                        "\t\tMoved File: " + file.name + " to " + new_location,
                        discord=False,
                    )
                    embed = [
                        handle_fields(
                            DiscordEmbed(
                                title="Moved File",
                                color=grey_color,
                            ),
                            fields=[
                                {
                                    "name": "File:",
                                    "value": "```" + file.name + "```",
                                    "inline": False,
                                },
                                {
                                    "name": "To:",
                                    "value": "```" + new_location + "```",
                                    "inline": False,
                                },
                            ],
                        )
                    ]
                    add_to_grouped_notifications(Embed(embed[0], None))
                move_images(
                    file,
                    new_location,
                    group=group,
                    highest_num=highest_num,
                    highest_part=highest_part,
                    is_chapter_dir=is_chapter_dir,
                )
                return True
            else:
                send_message(
                    "\t\tFailed to move: "
                    + os.path.join(file.root, file.name)
                    + " to: "
                    + new_location,
                    error=True,
                )
                return False
    except OSError as e:
        send_message(str(e), error=True)
        return False

# Replaces an old file.
def replace_file(old_file, new_file, group=False, highest_num=None, highest_part=""):
    result = False
    try:
        if os.path.isfile(old_file.path) and os.path.isfile(new_file.path):
            file_removal_status = remove_file(old_file.path, group=group)
            if not os.path.isfile(old_file.path) and file_removal_status:
                move_file(
                    new_file,
                    old_file.root,
                    silent=True,
                    highest_num=highest_num,
                    highest_part=highest_part,
                )
                if os.path.isfile(os.path.join(old_file.root, new_file.name)):
                    result = True
                    send_message(
                        "\t\tFile: "
                        + new_file.name
                        + " was moved to: "
                        + old_file.root,
                        discord=False,
                    )
                    embed = [
                        handle_fields(
                            DiscordEmbed(
                                title="Moved File",
                                color=grey_color,
                            ),
                            fields=[
                                {
                                    "name": "File:",
                                    "value": "```" + new_file.name + "```",
                                    "inline": False,
                                },
                                {
                                    "name": "To:",
                                    "value": "```" + old_file.root + "```",
                                    "inline": False,
                                },
                            ],
                        )
                    ]
                    add_to_grouped_notifications(Embed(embed[0], None))
                else:
                    send_message(
                        "\tFailed to replace: "
                        + old_file.name
                        + " with: "
                        + new_file.name,
                        error=True,
                    )
            else:
                send_message(
                    "\tFailed to remove old file: "
                    + old_file.name
                    + "\nUpgrade aborted.",
                    error=True,
                )
        else:
            send_message(
                "\tOne of the files is missing, failed to replace.\n"
                + old_file.path
                + new_file.path,
                error=True,
            )
    except Exception as e:
        send_message("Failed file replacement." + "\nERROR: " + str(e), error=True)
    return result


# execute command with subprocess and reutrn the output
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
def remove_duplicate_releases_from_download(
    original_releases, downloaded_releases, group=False, image_similarity_match=False
):
    global moved_files
    for download in downloaded_releases[:]:
        if (
            not isinstance(download.volume_number, int)
            and not isinstance(download.volume_number, float)
            and not download.multi_volume
        ):
            send_message(
                "\n\t\t"
                + download.file_type.capitalize()
                + " number empty/missing in: "
                + download.name,
                error=True,
            )
            downloaded_releases.remove(download)
        if downloaded_releases:
            chapter_percentage_download_folder = get_percent_for_folder(
                downloaded_releases, file_type="chapter"
            )
            is_chapter_dir = (
                chapter_percentage_download_folder >= required_matching_percentage
            )
            highest_num, highest_part = get_highest_release(
                downloaded_releases + original_releases,
                is_chapter_directory=is_chapter_dir,
            )
            for original in original_releases[:]:
                if not os.path.isfile(download.path):
                    break
                if (
                    (
                        isinstance(download.index_number, float)
                        and isinstance(original.index_number, float)
                    )
                    or (
                        download.index_number
                        and download.multi_volume
                        and isinstance(download.index_number, list)
                    )
                ) and os.path.isfile(original.path):
                    fields = []
                    if (
                        download.index_number != ""
                        and original.index_number != ""
                        and (
                            download.index_number == original.index_number
                            or (
                                image_similarity_match
                                and image_similarity_match.name == original.name
                            )
                        )
                        and download.file_type == original.file_type
                    ):
                        upgrade_status = is_upgradeable(download, original)
                        original_file_tags = (
                            upgrade_status.current_ranked_result.keywords
                        )
                        if original_file_tags:
                            original_file_tags = ", ".join(
                                [
                                    tag.name + " (" + str(tag.score) + ")"
                                    for tag in upgrade_status.current_ranked_result.keywords
                                ]
                            )
                        else:
                            original_file_tags = "None"
                        downloaded_file_tags = (
                            upgrade_status.downloaded_ranked_result.keywords
                        )
                        if downloaded_file_tags:
                            downloaded_file_tags = ", ".join(
                                [
                                    tag.name + " (" + str(tag.score) + ")"
                                    for tag in upgrade_status.downloaded_ranked_result.keywords
                                ]
                            )
                        else:
                            downloaded_file_tags = "None"
                        original_file_size = None
                        if os.path.isfile(original.path):
                            original_file_size = os.path.getsize(original.path)
                            # convert to MB
                            if original_file_size:
                                original_file_size = original_file_size / 1000000
                                original_file_size = (
                                    str(round(original_file_size, 1)) + " MB"
                                )
                        downloaded_file_size = None
                        if os.path.isfile(download.path):
                            downloaded_file_size = os.path.getsize(download.path)
                            # convert to MB
                            if downloaded_file_size:
                                downloaded_file_size = downloaded_file_size / 1000000
                                downloaded_file_size = (
                                    str(round(downloaded_file_size, 1)) + " MB"
                                )
                        fields = [
                            {
                                "name": "From:",
                                "value": "```" + original.name + "```",
                                "inline": False,
                            },
                            {
                                "name": "Score:",
                                "value": str(
                                    upgrade_status.current_ranked_result.total_score
                                ),
                                "inline": True,
                            },
                            {
                                "name": "Tags:",
                                "value": str(original_file_tags),
                                "inline": True,
                            },
                            {
                                "name": "To:",
                                "value": "```" + download.name + "```",
                                "inline": False,
                            },
                            {
                                "name": "Score:",
                                "value": str(
                                    upgrade_status.downloaded_ranked_result.total_score
                                ),
                                "inline": True,
                            },
                            {
                                "name": "Tags:",
                                "value": str(downloaded_file_tags),
                                "inline": True,
                            },
                        ]
                        if original_file_size and downloaded_file_size and fields:
                            # insert original file size at index 3
                            fields.insert(
                                3,
                                {
                                    "name": "Size:",
                                    "value": str(original_file_size),
                                    "inline": True,
                                },
                            )
                            # append downloaded file size at the end
                            fields.append(
                                {
                                    "name": "Size:",
                                    "value": str(downloaded_file_size),
                                    "inline": True,
                                }
                            )
                        if not upgrade_status.is_upgrade:
                            send_message(
                                "\t\tNOT UPGRADEABLE: "
                                + download.name
                                + " is not an upgrade to: "
                                + original.name
                                + "\n\t\tDeleting: "
                                + download.name
                                + " from download folder.",
                                discord=False,
                            )
                            embed = [
                                handle_fields(
                                    DiscordEmbed(
                                        title="Upgrade Process (Not Upgradeable)",
                                        color=yellow_color,
                                    ),
                                    fields=fields,
                                )
                            ]
                            add_to_grouped_notifications(Embed(embed[0], None))
                            if download in downloaded_releases:
                                downloaded_releases.remove(download)
                            remove_file(download.path, group=group)
                        else:
                            send_message(
                                "\t\tUPGRADE: "
                                + download.name
                                + " is an upgrade to: "
                                + original.name
                                + "\n\tUpgrading "
                                + original.name,
                                discord=False,
                            )
                            embed = [
                                handle_fields(
                                    DiscordEmbed(
                                        title="Upgrade Process (Upgradeable)",
                                        color=green_color,
                                    ),
                                    fields=fields,
                                )
                            ]
                            add_to_grouped_notifications(Embed(embed[0], None))
                            if download.multi_volume and not original.multi_volume:
                                for original_volume in original_releases[:]:
                                    for volume_number in download.volume_number:
                                        if (
                                            volume_number != original.volume_number
                                            and (
                                                original_volume.volume_number
                                                == volume_number
                                                and original_volume.volume_part
                                                == original.volume_part
                                            )
                                        ):
                                            remove_file(
                                                original_volume.path, group=group
                                            )
                                            original_releases.remove(original_volume)
                            replace_file_status = replace_file(
                                original,
                                download,
                                group=group,
                                highest_num=highest_num,
                                highest_part=highest_part,
                            )
                            if replace_file_status:
                                # append the new path to moved_files
                                moved_files.append(
                                    os.path.join(original.root, download.name)
                                )
                            if download in downloaded_releases:
                                downloaded_releases.remove(download)
                            if (
                                grouped_notifications
                                and not group_discord_notifications_until_max
                            ):
                                send_discord_message(
                                    None,
                                    grouped_notifications,
                                )


# Checks if the folder is empty, then deletes if it is
def check_and_delete_empty_folder(folder):
    # check that the folder exists
    if os.path.exists(folder):
        try:
            print("\t\tChecking for empty folder: " + folder)
            delete_hidden_files(os.listdir(folder), folder)
            folder_contents = os.listdir(folder)
            folder_contents = remove_hidden_files(folder_contents)
            if len(folder_contents) == 1 and folder_contents[0].startswith("cover."):
                remove_file(os.path.join(folder, folder_contents[0]), silent=True)
                folder_contents = os.listdir(folder)
                folder_contents = remove_hidden_files(folder_contents)
            if len(folder_contents) == 0 and (
                folder not in paths and folder not in download_folders
            ):
                try:
                    print("\t\t\tRemoving empty folder: " + folder)
                    os.rmdir(folder)
                    if not os.path.exists(folder):
                        print("\t\t\t\tFolder removed: " + folder)
                    else:
                        print("\t\t\t\tFailed to remove folder: " + folder)
                except OSError as e:
                    send_message(str(e), error=True)
        except Exception as e:
            send_message(str(e), error=True)
    else:
        print("\t\tFolder does not exist when checking for empty folder: " + folder)


# Writes a log file
def write_to_file(
    file,
    message,
    without_timestamp=False,
    overwrite=False,
    check_for_dup=False,
    write_to=None,
):
    write_status = False
    logs_dir_loc = LOGS_DIR if not write_to else write_to

    # check if the logs directory exists, if not create it
    if not os.path.exists(logs_dir_loc):
        try:
            os.makedirs(logs_dir_loc)
        except OSError as e:
            send_message(str(e), error=True)
            return

    if log_to_file and logs_dir_loc:
        # get rid of formatting
        message = re.sub("\t|\n", "", str(message), flags=re.IGNORECASE).strip()
        contains = False

        # check if it already contains the message
        if check_for_dup and os.path.isfile(os.path.join(logs_dir_loc, file)):
            contains = check_text_file_for_message(
                os.path.join(logs_dir_loc, file), message
            )

        if not contains or overwrite:
            try:
                file_path = os.path.join(logs_dir_loc, file)
                append_write = ""
                if os.path.exists(file_path):
                    if not overwrite:
                        append_write = "a"  # append if already exists
                    else:
                        append_write = "w"
                else:
                    append_write = "w"  # make a new file if not
                try:
                    if append_write != "":
                        now = datetime.now()
                        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
                        file = open(file_path, append_write)
                        if without_timestamp:
                            file.write("\n " + message)
                        else:
                            file.write("\n" + dt_string + " " + message)
                        write_status = True
                        file.close()
                except Exception as e:
                    send_message(str(e), error=True, log=False)
            except Exception as e:
                send_message(str(e), error=True, log=False)
    return write_status


# Checks for any missing volumes between the lowest volume of a series and the highest volume.
def check_for_missing_volumes():
    print("\nChecking for missing volumes...")
    paths_clean = [p for p in paths if p not in download_folders]
    for path in paths_clean:
        if os.path.exists(path):
            os.chdir(path)
            # get list of folders from path directory
            path_dirs = [f for f in os.listdir(path) if os.path.isdir(f)]
            path_dirs = clean_and_sort(path, dirs=path_dirs)[1]
            global folder_accessor
            folder_accessor = Folder(
                path,
                path_dirs,
                os.path.basename(os.path.dirname(path)),
                os.path.basename(path),
                [""],
            )
            for dir in folder_accessor.dirs:
                current_folder_path = os.path.join(folder_accessor.root, dir)
                existing_dir_full_file_path = os.path.dirname(
                    os.path.join(folder_accessor.root, dir)
                )
                existing_dir = os.path.join(existing_dir_full_file_path, dir)
                clean_existing = os.listdir(existing_dir)
                clean_existing = clean_and_sort(
                    existing_dir, clean_existing, chapters=False
                )[0]
                existing_dir_volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(
                        [
                            f
                            for f in clean_existing
                            if os.path.isfile(os.path.join(existing_dir, f))
                        ],
                        existing_dir,
                    )
                )
                for existing in existing_dir_volumes[:]:
                    if (
                        not isinstance(existing.volume_number, int)
                        and not isinstance(existing.volume_number, float)
                        and not isinstance(existing.volume_number, list)
                    ):
                        existing_dir_volumes.remove(existing)
                if len(existing_dir_volumes) >= 2:
                    volume_numbers = []
                    volume_numbers_second = []
                    for volume in existing_dir_volumes:
                        if volume.volume_number != "":
                            volume_numbers.append(volume.volume_number)
                    for item in volume_numbers:
                        if isinstance(item, list):
                            low_num = int(min(item))
                            high_num = int(max(item))
                            # get inbetween numbers
                            for i in range(low_num, high_num + 1):
                                if i not in volume_numbers_second:
                                    volume_numbers_second.append(i)
                            for i in item:
                                if i not in volume_numbers_second:
                                    volume_numbers_second.append(i)
                        else:
                            if item not in volume_numbers_second:
                                volume_numbers_second.append(item)
                    volume_numbers_second.sort()
                    if len(volume_numbers_second) >= 2:
                        lowest_volume_number = 1
                        highest_volume_number = int(max(volume_numbers_second))
                        volume_num_range = list(
                            range(lowest_volume_number, highest_volume_number + 1)
                        )
                        for number in volume_numbers_second:
                            if number in volume_num_range:
                                volume_num_range.remove(number)
                        if len(volume_num_range) != 0:
                            for number in volume_num_range:
                                message = (
                                    "\t"
                                    + os.path.basename(current_folder_path)
                                    + ": Volume "
                                    + str(number)
                                )
                                if volume.extension in manga_extensions:
                                    message += " [MANGA]"
                                elif volume.extension in novel_extensions:
                                    message += " [NOVEL]"
                                print(message)
                                write_to_file("missing_volumes.txt", message)


# Renames the file.
def rename_file(src, dest, silent=False):
    result = False
    if os.path.isfile(src):
        root = os.path.dirname(src)
        if not silent:
            print("\n\t\tRenaming " + src)
        try:
            os.rename(src, dest)
        except Exception as e:
            send_message(str(e), error=True)
        if os.path.isfile(dest):
            result = True
            if not silent:
                send_message(
                    "\t\t"
                    + os.path.basename(src)
                    + " was renamed to "
                    + os.path.basename(dest),
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
                "Failed to rename " + src + " to " + dest + "\n\tERROR: " + str(e),
                error=True,
            )
    else:
        send_message("File " + src + " does not exist. Skipping rename.", discord=False)
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
                    "\t\t"
                    + os.path.basename(src)
                    + " was renamed to "
                    + os.path.basename(dest)
                    + "\n",
                    discord=False,
                )
                result = dest
            else:
                send_message(
                    "Failed to rename " + src + " to " + dest + "\n\tERROR: " + str(e),
                    error=True,
                )
        else:
            send_message(
                "Folder " + dest + " already exists. Skipping rename.", discord=False
            )
    else:
        send_message(
            "Folder " + src + " does not exist. Skipping rename.", discord=False
        )
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
            example = " or ".join(
                [str(example_item) for example_item in example[:-1]]
                + [str(example[-1])]
            )
        else:
            example = str(example)
        prompt = prompt + " (" + str(example) + "): "
    else:
        prompt = prompt + ": "

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
def get_internal_metadata(file_path, extension):
    metadata = None
    try:
        if extension in manga_extensions:
            contains_comic_info = check_if_zip_file_contains_comic_info_xml(file_path)
            if contains_comic_info:
                comicinfo = get_file_from_zip(
                    file_path, "comicinfo.xml", allow_base=False
                )
                if comicinfo:
                    comicinfo = comicinfo.decode("utf-8")
                    # not parsing pages correctly
                    metadata = parse_comicinfo_xml(comicinfo)
        elif extension in novel_extensions:
            opf_files = [
                "content.opf",
                "package.opf",
                "standard.opf",
                "volume.opf",
                "metadata.opf",
            ]
            regex_searches = [
                r"978.*\.opf",
            ]
            opf_files.extend(regex_searches)
            for file in opf_files:
                opf = None
                if file not in regex_searches:
                    opf = get_file_from_zip(file_path, file)
                else:
                    opf = get_file_from_zip(file_path, file, re_search=True)
                if opf:
                    metadata = parse_html_tags(opf)
                    break
            if not metadata:
                send_message(
                    "\t\tNo opf file found in "
                    + file_path
                    + ".\n\t\t\tSkipping metadata retrieval.",
                    discord=False,
                )
    except Exception as e:
        send_message(
            "Failed to retrieve metadata from " + file_path + "\n\tERROR: " + str(e),
            error=True,
        )
    return metadata


# Checks if the epub file contains any premium content.
def check_for_premium_content(file_path, extension):
    result = False
    if extension in novel_extensions and search_and_add_premium_to_file_name:
        if re.search(r"\bPremium\b", os.path.basename(file_path), re.IGNORECASE):
            result = True
        elif check_for_bonus_xhtml(file_path) or get_toc_or_copyright(file_path):
            result = True
    return result


# Rebuilds the file name by cleaning up, adding, and moving some parts around.
def reorganize_and_rename(files, dir, group=False):
    global transferred_files
    base_dir = os.path.basename(dir)
    for file in files[:]:
        preferred_naming_format = preferred_volume_renaming_format
        keywords = volume_regex_keywords
        if file.file_type == "chapter":
            keywords = chapter_regex_keywords
            preferred_naming_format = preferred_chapter_renaming_format
        try:
            if re.search(
                r"(\b(%s)([-_.]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s|%s))"
                % (keywords, file_extensions_regex),
                file.name,
                re.IGNORECASE,
            ):
                rename = ""
                rename += base_dir
                rename += " " + preferred_naming_format
                number = None
                numbers = []
                if file.multi_volume:
                    for n in file.volume_number:
                        numbers.append(n)
                        if n != file.volume_number[-1]:
                            numbers.append("-")
                else:
                    numbers.append(file.volume_number)
                zfill_int = zfill_volume_int_value
                zfill_float = zfill_volume_float_value
                if file.file_type == "chapter":
                    zfill_int = zfill_chapter_int_value
                    zfill_float = zfill_chapter_float_value
                number_string = ""
                for number in numbers:
                    if not isinstance(number, str) and number.is_integer():
                        if number < 10 or file.file_type == "chapter" and number < 100:
                            volume_number = str(int(number)).zfill(zfill_int)
                            number_string += volume_number
                        else:
                            volume_number = str(int(number))
                            number_string += volume_number
                    elif isinstance(number, float):
                        if number < 10 or file.file_type == "chapter" and number < 100:
                            volume_number = str(number).zfill(zfill_float)
                            number_string += volume_number
                        else:
                            volume_number = str(number)
                            number_string += volume_number
                    elif isinstance(number, str) and number == "-":
                        number_string += "-"
                if number_string:
                    rename += number_string
                if (
                    add_issue_number_to_manga_file_name
                    and file.file_type == "volume"
                    and file.extension in manga_extensions
                    and number_string
                ):
                    rename += " #" + number_string
                if file.subtitle:
                    rename += " - " + file.subtitle
                if file.volume_year:
                    if file.extension in manga_extensions:
                        rename += " (" + str(file.volume_year) + ")"
                    elif file.extension in novel_extensions:
                        rename += " [" + str(file.volume_year) + "]"
                    for item in file.extras[:]:
                        score = similar(
                            item,
                            str(file.volume_year),
                        )
                        if (
                            score >= required_similarity_score
                            or re.search(r"([\[\(\{]\d{4}[\]\)\}])", item)
                            or re.search(
                                str(file.volume_year),
                                item,
                                re.IGNORECASE,
                            )
                        ):
                            file.extras.remove(item)

                if (
                    file.publisher.from_meta or file.publisher.from_name
                ) and add_publisher_name_to_file_name_when_renaming:
                    for item in file.extras[:]:
                        for publisher in publishers:
                            if (
                                similar(
                                    re.sub(r"(\(|\[|\{|\)|\]|\})", "", item), publisher
                                )
                                >= publisher_similarity_score
                            ):
                                file.extras.remove(item)
                                break
                            elif file.publisher.from_name and (
                                similar(
                                    re.sub(r"(\(|\[|\{|\)|\]|\})", "", item),
                                    file.publisher.from_name,
                                )
                                >= publisher_similarity_score
                            ):
                                file.extras.remove(item)
                                break
                            elif file.publisher.from_meta and (
                                similar(
                                    re.sub(r"(\(|\[|\{|\)|\]|\})", "", item),
                                    file.publisher.from_meta,
                                )
                                >= publisher_similarity_score
                            ):
                                file.extras.remove(item)
                                break
                    if file.extension in manga_extensions:
                        if file.publisher.from_meta:
                            rename += " (" + file.publisher.from_meta + ")"
                        elif file.publisher.from_name:
                            rename += " (" + file.publisher.from_name + ")"
                    elif file.extension in novel_extensions:
                        if file.publisher.from_meta:
                            rename += " [" + file.publisher.from_meta + "]"
                        elif file.publisher.from_name:
                            rename += " [" + file.publisher.from_name + "]"
                if file.is_premium and search_and_add_premium_to_file_name:
                    if file.extension in manga_extensions:
                        rename += " (Premium)"
                    elif file.extension in novel_extensions:
                        rename += " [Premium]"
                    for item in file.extras[:]:
                        score = similar(
                            item,
                            "Premium",
                        )
                        if score >= required_similarity_score or re.search(
                            "Premium",
                            item,
                            re.IGNORECASE,
                        ):
                            file.extras.remove(item)
                if (
                    move_release_group_to_end_of_file_name
                    and add_publisher_name_to_file_name_when_renaming
                    and (
                        file.release_group
                        and (
                            file.release_group != file.publisher.from_meta
                            and file.release_group != file.publisher.from_name
                        )
                    )
                ):
                    for item in file.extras[:]:
                        # escape any regex characters
                        item_escaped = re.escape(item)
                        score = similar(
                            item,
                            file.release_group,
                        )
                        left_brackets = r"(\(|\[|\{)"
                        right_brackets = r"(\)|\]|\})"
                        if score >= release_group_similarity_score or re.search(
                            rf"{left_brackets}{item_escaped}{right_brackets}",
                            file.release_group,
                            re.IGNORECASE,
                        ):
                            file.extras.remove(item)
                if file.extras:
                    for extra in file.extras:
                        if not re.search(re.escape(extra), rename, re.IGNORECASE):
                            rename += " " + extra
                if move_release_group_to_end_of_file_name:
                    release_group_escaped = None
                    if file.release_group:
                        release_group_escaped = re.escape(file.release_group)
                    if release_group_escaped and not re.search(
                        rf"\b{release_group_escaped}\b", rename, re.IGNORECASE
                    ):
                        if file.extension in manga_extensions:
                            rename += " (" + file.release_group + ")"
                        elif file.extension in novel_extensions:
                            rename += " [" + file.release_group + "]"

                # remove * from the replacement
                rename = re.sub(r"\*", "", rename)
                rename += file.extension
                rename = rename.strip()

                # Replace unicode using unidecode, if enabled
                if replace_unicode_when_restructuring:
                    rename = unidecode(rename)

                # Replace any quotes with '
                rename = re.sub(r"\"", "'", rename)

                processed_files.append(rename)
                if file.name != rename:
                    if watchdog_toggle:
                        transferred_files.append(os.path.join(file.root, rename))
                    try:
                        send_message("\n\t\tBEFORE: " + file.name, discord=False)
                        send_message("\t\tAFTER:  " + rename, discord=False)
                        user_input = None
                        if not manual_rename:
                            user_input = "y"
                        else:
                            user_input = get_input_from_user(
                                "\t\tReorganize & Rename",
                                ["y", "n"],
                                ["y", "n"],
                            )
                        if user_input == "y":
                            if not os.path.isfile(os.path.join(file.root, rename)):
                                rename_file(
                                    file.path,
                                    os.path.join(file.root, rename),
                                    silent=True,
                                )
                                # remove old file from list of transferred files
                                if file.path in transferred_files:
                                    transferred_files.remove(file.path)
                                send_message(
                                    "\t\t\tSuccessfully reorganized & renamed file.\n",
                                    discord=False,
                                )
                                if not mute_discord_rename_notifications:
                                    embed = [
                                        handle_fields(
                                            DiscordEmbed(
                                                title="Reorganized & Renamed File",
                                                color=grey_color,
                                            ),
                                            fields=[
                                                {
                                                    "name": "From:",
                                                    "value": "```" + file.name + "```",
                                                    "inline": False,
                                                },
                                                {
                                                    "name": "To:",
                                                    "value": "```" + rename + "```",
                                                    "inline": False,
                                                },
                                            ],
                                        )
                                    ]
                                    add_to_grouped_notifications(Embed(embed[0], None))
                            else:
                                print(
                                    "\t\tFile already exists, skipping rename of "
                                    + file.name
                                    + " to "
                                    + rename
                                    + " and deleting "
                                    + file.name
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
                "Failed to Reorganized & Renamed File: "
                + file.name
                + ": "
                + str(e)
                + " with reoganize_and_rename",
                error=True,
            )
    if group and grouped_notifications and not group_discord_notifications_until_max:
        send_discord_message(None, grouped_notifications)
    return files


# Replaces any pesky double spaces
@lru_cache(maxsize=None)
def remove_dual_space(s):
    return re.sub("(\s{2,})", " ", s)


# Removes common words to improve string matching accuracy between a series_name
# from a file name, and a folder name, useful for when releasers sometimes include them,
# and sometimes don't.
@lru_cache(maxsize=None)
def normalize_string_for_matching(
    s,
    skip_common_words=False,
    skip_editions=False,
    skip_type_keywords=False,
    skip_japanese_particles=False,
    skip_misc_words=False,
):
    if len(s) > 1:
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
            # (?<!^) = Cannot start with this word
            # EX: "Book Girl" is a light novel series
            # and you wouldn't want to remove that from the series name.
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
        for word in words_to_remove:
            s = re.sub(rf"\b{word}\b", " ", s, flags=re.IGNORECASE).strip()
            s = remove_dual_space(s)
    return s.strip()


# Removes the s from any words that end in s
@lru_cache(maxsize=None)
def remove_s(s):
    return re.sub(r"\b(\w+)(s)\b", r"\1", s, flags=re.IGNORECASE).strip()


# Returns a string without punctuation.
@lru_cache(maxsize=None)
def remove_punctuation(s, disable_lang=False):
    s = re.sub(r":", " ", s)
    s = remove_dual_space(s)
    language = ""
    if not disable_lang and not s.isdigit():
        language = detect_language(s)
    if language and language != "en" and not disable_lang:
        return remove_dual_space(
            remove_s(re.sub(r"[^\w\s+]", " ", normalize_string_for_matching(s)))
        )
    else:
        return convert_to_ascii(
            unidecode(
                remove_dual_space(
                    remove_s(re.sub(r"[^\w\s+]", " ", normalize_string_for_matching(s)))
                )
            )
        )


# detect language of the passed string using langdetect
@lru_cache(maxsize=None)
def detect_language(s):
    language = ""
    if s and len(s) >= 5 and re.search(r"[\p{L}\p{M}]+", s):
        try:
            language = detect(s)
        except Exception as e:
            send_message(str(e), error=True)
            return language
    return language


# convert string to acsii
@lru_cache(maxsize=None)
def convert_to_ascii(s):
    return "".join(i for i in s if ord(i) < 128)


# convert array to string separated by whatever is passed in the separator parameter
def array_to_string(array, separator=", "):
    if isinstance(array, list):
        return separator.join([str(x) for x in array])
    elif isinstance(array, int) or isinstance(array, float) or isinstance(array, str):
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


# gets the toc.xhtml or copyright.xhtml file from the novel file and checks for premium content
def get_toc_or_copyright(file):
    bonus_content_found = False
    try:
        with zipfile.ZipFile(file, "r") as zf:
            for name in zf.namelist():
                if os.path.basename(name) == "toc.xhtml":
                    toc_file = zf.open(name)
                    toc_file_contents = toc_file.read()
                    lines = toc_file_contents.decode("utf-8")
                    search = re.search(
                        r"(Bonus\s+((Color\s+)?Illustrations?|(Short\s+)?Stories))",
                        lines,
                    )
                    if search and re.search(r"J-Novel", lines, re.IGNORECASE):
                        bonus_content_found = search.group(0)
                        break
                elif os.path.basename(name) == "copyright.xhtml":
                    cop_file = zf.open(name)
                    cop_file_contents = cop_file.read()
                    lines = cop_file_contents.decode("utf-8")
                    search = re.search(
                        r"(Premium(\s)+(E?-?Book|Epub))", lines, re.IGNORECASE
                    )
                    if search:
                        bonus_content_found = search.group(0)
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


def check_upgrade(
    existing_root,
    dir,
    file,
    similarity_strings=None,
    cache=False,
    isbn=False,
    group=False,
    image=False,
):
    global moved_files
    global messages_to_send
    existing_dir = os.path.join(existing_root, dir)
    clean_existing = os.listdir(existing_dir)
    clean_existing = clean_and_sort(existing_dir, clean_existing)[0]
    clean_existing = upgrade_to_volume_class(
        upgrade_to_file_class(
            [
                f
                for f in clean_existing
                if os.path.isfile(os.path.join(existing_dir, f))
            ],
            existing_dir,
        )
    )
    manga_percent_download_folder = get_percent_for_folder(
        [file.name], extensions=manga_extensions
    )
    manga_percent_existing_folder = get_percent_for_folder(
        [f.name for f in clean_existing], extensions=manga_extensions
    )
    novel_percent_download_folder = get_percent_for_folder(
        [file.name], extensions=novel_extensions
    )
    novel_percent_existing_folder = get_percent_for_folder(
        [f.name for f in clean_existing], extensions=novel_extensions
    )
    chapter_percentage_download_folder = get_percent_for_folder(
        [file], file_type="chapter"
    )
    chapter_percentage_existing_folder = get_percent_for_folder(
        clean_existing, file_type="chapter"
    )
    volume_percentage_download_folder = get_percent_for_folder(
        [file], file_type="volume"
    )
    volume_percentage_existing_folder = get_percent_for_folder(
        clean_existing, file_type="volume"
    )
    print(
        "\tRequired Folder Matching Percent: {}%".format(required_matching_percentage)
    )
    print(
        "\t\tDownload Folder Manga Percent: {}%".format(manga_percent_download_folder)
    )
    print(
        "\t\tExisting Folder Manga Percent: {}%".format(manga_percent_existing_folder)
    )
    print(
        "\n\t\tDownload Folder Novel Percent: {}%".format(novel_percent_download_folder)
    )
    print(
        "\t\tExisting Folder Novel Percent: {}%".format(novel_percent_existing_folder)
    )
    print(
        "\n\t\tDownload Folder Chapter Percent: {}%".format(
            chapter_percentage_download_folder
        )
    )
    print(
        "\t\tExisting Folder Chapter Percent: {}%".format(
            chapter_percentage_existing_folder
        )
    )
    print(
        "\n\t\tDownload Folder Volume Percent: {}%".format(
            volume_percentage_download_folder
        )
    )
    print(
        "\t\tExisting Folder Volume Percent: {}%".format(
            volume_percentage_existing_folder
        )
    )
    if (
        (
            (manga_percent_download_folder and manga_percent_existing_folder)
            >= required_matching_percentage
        )
        or (
            (novel_percent_download_folder and novel_percent_existing_folder)
            >= required_matching_percentage
        )
    ) and (
        (
            (chapter_percentage_download_folder and chapter_percentage_existing_folder)
            >= required_matching_percentage
        )
        or (
            (volume_percentage_download_folder and volume_percentage_existing_folder)
            >= required_matching_percentage
        )
    ):
        download_dir_volumes = [file]
        if rename_files_in_download_folders_toggle and resturcture_when_renaming:
            reorganize_and_rename(download_dir_volumes, existing_dir, group=group)
        fields = []
        if similarity_strings:
            if not isbn and not image:
                fields = [
                    {
                        "name": "Existing Series Location:",
                        "value": "```" + existing_dir + "```",
                        "inline": False,
                    },
                    {
                        "name": "Downloaded File Series Name:",
                        "value": "```" + similarity_strings[0] + "```",
                        "inline": True,
                    },
                    {
                        "name": "Existing Library Folder Name:",
                        "value": "```" + similarity_strings[1] + "```",
                        "inline": False,
                    },
                    {
                        "name": "Similarity Score:",
                        "value": "```" + str(similarity_strings[2]) + "```",
                        "inline": True,
                    },
                    {
                        "name": "Required Score:",
                        "value": "```>= " + str(similarity_strings[3]) + "```",
                        "inline": True,
                    },
                ]
            elif isbn:
                if len(similarity_strings) >= 2:
                    fields = [
                        {
                            "name": "Existing Series Location:",
                            "value": "```" + existing_dir + "```",
                            "inline": False,
                        },
                        {
                            "name": "Downloaded File:",
                            "value": "```" + "\n".join(similarity_strings[0]) + "```",
                            "inline": False,
                        },
                        {
                            "name": "Existing Library File:",
                            "value": "```" + "\n".join(similarity_strings[1]) + "```",
                            "inline": False,
                        },
                    ]
                else:
                    send_message(
                        "Error: similarity_strings is not long enough to be valid."
                        + str(similarity_strings)
                        + " File: "
                        + file.name,
                        error=True,
                    )
            elif image:
                if len(similarity_strings) == 4:
                    fields = [
                        {
                            "name": "Existing Series Location:",
                            "value": "```" + existing_dir + "```",
                            "inline": False,
                        },
                        {
                            "name": "Existing Shortened Series Name:",
                            "value": "```" + similarity_strings[0] + "```",
                            "inline": True,
                        },
                        {
                            "name": "Download File Shortened Series Name:",
                            "value": "```" + similarity_strings[1] + "```",
                            "inline": True,
                        },
                        {
                            "name": "Image Similarity Score:",
                            "value": "```" + str(similarity_strings[2]) + "```",
                            "inline": False,
                        },
                        {
                            "name": "Required Score:",
                            "value": "```>=" + str(similarity_strings[3]) + "```",
                            "inline": True,
                        },
                    ]
                else:
                    send_message(
                        "Error: similarity_strings is not long enough to be valid."
                        + str(similarity_strings)
                        + " File: "
                        + file.name,
                        error=True,
                    )
        if cache:
            send_message(
                "\n\t\tFound existing series from cache: " + existing_dir, discord=False
            )
            if fields:
                embed = [
                    handle_fields(
                        DiscordEmbed(
                            title="Found Series Match (CACHE)",
                            color=grey_color,
                        ),
                        fields=fields,
                    )
                ]
                add_to_grouped_notifications(Embed(embed[0], None))
        elif isbn:
            send_message("\n\t\tFound existing series: " + existing_dir, discord=False)
            if fields:
                embed = [
                    handle_fields(
                        DiscordEmbed(
                            title="Found Series Match (Matching Identifier)",
                            color=grey_color,
                        ),
                        fields=fields,
                    ),
                ]
                add_to_grouped_notifications(Embed(embed[0], None))
        elif image:
            send_message("\n\t\tFound existing series: " + existing_dir, discord=False)
            if fields:
                embed = [
                    handle_fields(
                        DiscordEmbed(
                            title="Found Series Match (Cover Match)",
                            color=grey_color,
                        ),
                        fields=fields,
                    ),
                ]
                add_to_grouped_notifications(Embed(embed[0], None))
        else:
            send_message("\n\t\tFound existing series: " + existing_dir, discord=False)
            if fields:
                embed = [
                    handle_fields(
                        DiscordEmbed(
                            title="Found Series Match",
                            color=grey_color,
                        ),
                        fields=fields,
                    ),
                ]
                add_to_grouped_notifications(Embed(embed[0], None))
        remove_duplicate_releases_from_download(
            clean_existing,
            download_dir_volumes,
            group=group,
            image_similarity_match=image,
        )
        if len(download_dir_volumes) != 0:
            volume = download_dir_volumes[0]
            if isinstance(
                volume.volume_number,
                float,
            ) or isinstance(volume.volume_number, list):
                send_message(
                    "\t\t\t"
                    + volume.file_type.capitalize()
                    + " "
                    + array_to_string(volume.volume_number)
                    + ": "
                    + volume.name
                    + " does not exist in: "
                    + existing_dir
                    + "\n\t\t\tMoving: "
                    + volume.name
                    + " to "
                    + existing_dir,
                    discord=False,
                )
                cover = None
                if volume.file_type == "volume" or (
                    volume.file_type == "chapter"
                    and output_chapter_covers_to_discord
                    and not new_volume_webhook
                ):
                    cover = find_and_extract_cover(volume, return_data_only=True)
                fields = [
                    {
                        "name": volume.file_type.capitalize() + " Number(s)",
                        "value": "```" + array_to_string(volume.volume_number) + "```",
                        "inline": False,
                    },
                    {
                        "name": volume.file_type.capitalize() + " Name",
                        "value": "```" + volume.name + "```",
                        "inline": False,
                    },
                ]
                if volume.volume_part and volume.file_type == "volume":
                    # insert after volume number in fields
                    fields.insert(
                        1,
                        {
                            "name": volume.file_type.capitalize() + " Part",
                            "value": "```" + str(volume.volume_part) + "```",
                            "inline": False,
                        },
                    )
                title = "New " + volume.file_type.capitalize() + " Release"
                is_chapter_dir = (
                    chapter_percentage_existing_folder
                ) >= required_matching_percentage
                highest_num_and_part = get_highest_release(
                    clean_existing + download_dir_volumes,
                    is_chapter_directory=is_chapter_dir,
                )
                move_status = move_file(
                    volume,
                    existing_dir,
                    group=group,
                    highest_num=highest_num_and_part[0],
                    highest_part=highest_num_and_part[1],
                    is_chapter_dir=is_chapter_dir,
                )
                if move_status:
                    check_and_delete_empty_folder(volume.root)
                    volume.extensionless_path = get_extensionless_name(
                        os.path.join(existing_dir, volume.name)
                    )
                    volume.path = os.path.join(existing_dir, volume.name)
                    volume.root = existing_dir
                    moved_files.append(volume.path)
                embed = [
                    handle_fields(
                        DiscordEmbed(
                            title=title,
                            color=green_color,
                        ),
                        fields=fields,
                    ),
                ]
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
                        if grouped_notifications:
                            send_discord_message(None, grouped_notifications)
                        send_discord_message(
                            None,
                            [Embed(embed[0], cover)],
                            passed_webhook=new_volume_webhook,
                        )
                else:
                    add_to_grouped_notifications(Embed(embed[0], cover))
                    if (
                        grouped_notifications
                        and not group_discord_notifications_until_max
                    ):
                        send_discord_message(None, grouped_notifications)
                return True
        else:
            if grouped_notifications and not group_discord_notifications_until_max:
                send_discord_message(
                    None,
                    grouped_notifications,
                )
            check_and_delete_empty_folder(file.root)
            return True
    else:
        print("\n\t\tNo match found.")
        return False


# remove duplicates elements from the passed in list
def remove_duplicates(items):
    return list(dict.fromkeys(items))


# Return the zip comment for the passed zip file
@lru_cache(maxsize=None)
def get_zip_comment_cache(zip_file):
    comment = ""
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            if zip_ref.comment:
                comment = zip_ref.comment.decode("utf-8")
    except Exception as e:
        send_message(str(e), error=True)
        send_message("\tFailed to get zip comment for: " + zip_file, error=True)
        write_to_file("errors.txt", str(e))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
    return comment


def get_zip_comment(zip_file):
    comment = ""
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            if zip_ref.comment:
                comment = zip_ref.comment.decode("utf-8")
    except Exception as e:
        send_message(str(e), error=True)
        send_message("\tFailed to get zip comment for: " + zip_file, error=True)
        write_to_file("errors.txt", str(e))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
    return comment


# Removes bracketed content from the string, alongwith any whitespace.
# As long as the bracketed content is not immediately preceded or followed by a dash.
@lru_cache(maxsize=None)
def remove_bracketed_info_from_name(string):
    # Avoid a string that is only a bracket
    # Probably a series name
    # EX: [(OSHI NO KO)]
    if re.search(r"^[\(\[\{].*[\)\]\}]$", string):
        return string

    # Use a while loop to repeatedly apply the regular expression to the string and remove the matched bracketed content
    while True:
        # The regular expression matches any substring enclosed in brackets and not immediately preceded or followed by a dash, along with the surrounding whitespace characters
        match = re.search(
            r"(?<!-|[A-Za-z]\s)\s*([\(\[\{][^\)\]\}]+[\)\]\}])\s*(?!-|\s*[A-Za-z])",
            string,
        )

        # If there are no more matches, exit the loop
        if not match:
            break

        # Replace the first set of brackets and their contents, along with the surrounding whitespace characters, with an empty string
        string = re.sub(
            r"(?<!-|[A-Za-z]\s)\s*([\(\[\{][^\)\]\}]+[\)\]\}])\s*(?!-|\s*[A-Za-z])",
            " ",
            string,
            1,
        )

    # Remove all whitespace characters from the right side of the string
    string = string.rstrip()

    # Remove any space before the extension from having removed bracketed content
    string = re.sub(r"\s\.(\w+)$", r".\1", string)

    # Return the modified string
    return string.strip()


# Checks for any duplicate releases and deletes the lower ranking one.
def check_for_duplicate_volumes(paths_to_search=[], group=False):
    try:
        for p in paths_to_search:
            if os.path.exists(p):
                print("\nSearching " + p + " for duplicate releases...")
                for root, dirs, files in scandir.walk(p):
                    print("\t" + root)
                    clean = None
                    if (
                        watchdog_toggle
                        and download_folders
                        and any(x for x in download_folders if root.startswith(x))
                    ):
                        clean = clean_and_sort(
                            root,
                            files,
                            dirs,
                            just_these_files=transferred_files,
                            just_these_dirs=transferred_dirs,
                        )
                    else:
                        clean = clean_and_sort(root, files, dirs)
                    files, dirs = clean[0], clean[1]
                    if not files:
                        continue
                    file_objects = upgrade_to_file_class(
                        [f for f in files if os.path.isfile(os.path.join(root, f))],
                        root,
                    )
                    file_objects = [
                        fo
                        for fo in file_objects
                        for compare in file_objects
                        if fo.name != compare.name
                        and (fo.volume_number != "" and compare.volume_number != "")
                        and fo.volume_number == compare.volume_number
                        and fo.root == compare.root
                        and fo.extension == compare.extension
                        and fo.file_type == compare.file_type
                    ]
                    volumes = upgrade_to_volume_class(file_objects)
                    volumes = [
                        v
                        for v in volumes
                        for compare in volumes
                        if v.name != compare.name
                        and v.index_number == compare.index_number
                        and v.root == compare.root
                        and v.extension == compare.extension
                        and v.file_type == compare.file_type
                        and v.series_name == compare.series_name
                    ]
                    for file in volumes:
                        try:
                            if os.path.isfile(file.path):
                                volume_series_name = (
                                    replace_underscore_in_name(
                                        remove_punctuation(
                                            remove_bracketed_info_from_name(
                                                file.series_name
                                            )
                                        )
                                    )
                                    .lower()
                                    .strip()
                                )
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
                                    print("\t\tChecking: " + file.name)
                                    for compare_file in compare_volumes:
                                        try:
                                            if os.path.isfile(compare_file.path):
                                                print(
                                                    "\t\t\tAgainst:  "
                                                    + compare_file.name
                                                )
                                                compare_volume_series_name = (
                                                    (
                                                        replace_underscore_in_name(
                                                            remove_punctuation(
                                                                remove_bracketed_info_from_name(
                                                                    compare_file.series_name
                                                                )
                                                            )
                                                        )
                                                    )
                                                    .lower()
                                                    .strip()
                                                )
                                                if (
                                                    file.root == compare_file.root
                                                    and (
                                                        file.index_number != ""
                                                        and compare_file.index_number
                                                        != ""
                                                    )
                                                    and file.index_number
                                                    == compare_file.index_number
                                                    and file.extension
                                                    == compare_file.extension
                                                    and (
                                                        file.series_name.lower()
                                                        == compare_file.series_name.lower()
                                                        or similar(
                                                            volume_series_name,
                                                            compare_volume_series_name,
                                                        )
                                                        >= required_similarity_score
                                                    )
                                                    and file.file_type
                                                    == compare_file.file_type
                                                ):
                                                    main_file_upgrade_status = (
                                                        is_upgradeable(
                                                            file, compare_file
                                                        )
                                                    )
                                                    compare_file_upgrade_status = (
                                                        is_upgradeable(
                                                            compare_file, file
                                                        )
                                                    )
                                                    if (
                                                        main_file_upgrade_status.is_upgrade
                                                        or compare_file_upgrade_status.is_upgrade
                                                    ):
                                                        duplicate_file = None
                                                        upgrade_file = None
                                                        if (
                                                            main_file_upgrade_status.is_upgrade
                                                        ):
                                                            duplicate_file = (
                                                                compare_file
                                                            )
                                                            upgrade_file = file
                                                        elif (
                                                            compare_file_upgrade_status.is_upgrade
                                                        ):
                                                            duplicate_file = file
                                                            upgrade_file = compare_file
                                                        send_message(
                                                            "\n\t\t\tDuplicate release found in: "
                                                            + upgrade_file.root
                                                            + "\n\t\t\tDuplicate: "
                                                            + duplicate_file.name
                                                            + " has a lower score than "
                                                            + upgrade_file.name
                                                            + "\n\n\t\t\tDeleting: "
                                                            + duplicate_file.name
                                                            + " inside of "
                                                            + duplicate_file.root
                                                            + "\n",
                                                            discord=False,
                                                        )
                                                        embed = [
                                                            handle_fields(
                                                                DiscordEmbed(
                                                                    title="Duplicate Download Release (NOT UPGRADEABLE)",
                                                                    color=yellow_color,
                                                                ),
                                                                fields=[
                                                                    {
                                                                        "name": "Location:",
                                                                        "value": "```"
                                                                        + upgrade_file.root
                                                                        + "```",
                                                                        "inline": False,
                                                                    },
                                                                    {
                                                                        "name": "Duplicate:",
                                                                        "value": "```"
                                                                        + duplicate_file.name
                                                                        + "```",
                                                                        "inline": False,
                                                                    },
                                                                    {
                                                                        "name": "has a lower score than:",
                                                                        "value": "```"
                                                                        + upgrade_file.name
                                                                        + "```",
                                                                        "inline": False,
                                                                    },
                                                                ],
                                                            )
                                                        ]
                                                        add_to_grouped_notifications(
                                                            Embed(embed[0], None)
                                                        )
                                                        user_input = None
                                                        if not manual_delete:
                                                            user_input = "y"
                                                        else:
                                                            user_input = get_input_from_user(
                                                                '\t\t\tDelete "'
                                                                + duplicate_file.name
                                                                + '"',
                                                                ["y", "n"],
                                                                ["y", "n"],
                                                            )
                                                        if user_input == "y":
                                                            remove_file(
                                                                duplicate_file.path,
                                                                group=group,
                                                            )
                                                        else:
                                                            print(
                                                                "\t\t\t\tSkipping...\n"
                                                            )
                                                    else:
                                                        file_hash = get_file_hash(
                                                            file.path
                                                        )
                                                        compare_hash = get_file_hash(
                                                            compare_file.path
                                                        )
                                                        # Check if the file hashes are the same
                                                        # instead of defaulting to requiring the user to decide.
                                                        if (
                                                            compare_hash and file_hash
                                                        ) and (
                                                            compare_hash == file_hash
                                                        ):
                                                            embed = [
                                                                handle_fields(
                                                                    DiscordEmbed(
                                                                        title="Duplicate Download Release (HASH MATCH)",
                                                                        color=yellow_color,
                                                                    ),
                                                                    fields=[
                                                                        {
                                                                            "name": "Location:",
                                                                            "value": "```"
                                                                            + file.root
                                                                            + "```",
                                                                            "inline": False,
                                                                        },
                                                                        {
                                                                            "name": "File Names:",
                                                                            "value": "```"
                                                                            + file.name
                                                                            + "\n"
                                                                            + compare_file.name
                                                                            + "```",
                                                                            "inline": False,
                                                                        },
                                                                        {
                                                                            "name": "File Hashes:",
                                                                            "value": "```"
                                                                            + file_hash
                                                                            + " "
                                                                            + compare_hash
                                                                            + "```",
                                                                            "inline": False,
                                                                        },
                                                                    ],
                                                                )
                                                            ]
                                                            add_to_grouped_notifications(
                                                                Embed(embed[0], None)
                                                            )
                                                            # Delete the compare file
                                                            remove_file(
                                                                compare_file.path,
                                                                group=group,
                                                            )
                                                        else:
                                                            send_message(
                                                                "\n\t\t\tDuplicate found in: "
                                                                + compare_file.root
                                                                + "\n\t\t\t\t"
                                                                + file.name
                                                                + "\n\t\t\t\t"
                                                                + compare_file.name
                                                                + "\n\t\t\t\t\tRanking scores are equal, REQUIRES MANUAL DECISION.",
                                                                discord=False,
                                                            )
                                                            embed = [
                                                                handle_fields(
                                                                    DiscordEmbed(
                                                                        title="Duplicate Download Release (REQUIRES MANUAL DECISION)",
                                                                        color=yellow_color,
                                                                    ),
                                                                    fields=[
                                                                        {
                                                                            "name": "Location:",
                                                                            "value": "```"
                                                                            + compare_file.root
                                                                            + "```",
                                                                            "inline": False,
                                                                        },
                                                                        {
                                                                            "name": "Duplicate:",
                                                                            "value": "```"
                                                                            + file.name
                                                                            + "```",
                                                                            "inline": False,
                                                                        },
                                                                        {
                                                                            "name": "has an equal score to:",
                                                                            "value": "```"
                                                                            + compare_file.name
                                                                            + "```",
                                                                            "inline": False,
                                                                        },
                                                                    ],
                                                                )
                                                            ]
                                                            add_to_grouped_notifications(
                                                                Embed(embed[0], None)
                                                            )
                                                            print(
                                                                "\t\t\t\t\tSkipping..."
                                                            )
                                        except Exception as e:
                                            send_message(
                                                "\n\t\t\tError: "
                                                + str(e)
                                                + "\n\t\t\tSkipping: "
                                                + compare_file.name,
                                                error=True,
                                            )
                                            continue
                        except Exception as e:
                            send_message(
                                "\n\t\tError: "
                                + str(e)
                                + "\n\t\tSkipping: "
                                + file.name,
                                error=True,
                            )
                            continue
            else:
                print("\n\t\tPath does not exist: " + p)
        if (
            group
            and grouped_notifications
            and not group_discord_notifications_until_max
        ):
            send_discord_message(None, grouped_notifications)
    except Exception as e:
        send_message("\n\t\tError: " + str(e), error=True)


# Gets the hash of the passed file and returns it as a string
def get_file_hash(file):
    try:
        BUF_SIZE = 65536  # 64KB buffer size (adjust as needed)
        hash_obj = hashlib.sha256()

        with open(file, "rb") as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                hash_obj.update(data)

        return hash_obj.hexdigest()
    except FileNotFoundError as e:
        # Handle file not found error
        send_message("\n\t\t\tError: File not found - " + str(e), error=True)
        return None
    except Exception as e:
        # Handle other exceptions
        send_message("\n\t\t\tError: " + str(e), error=True)
        return None


# Retrieves the internal file within the passed zip file.
def get_internal_file_hash(zip_file, file_name):
    try:
        BUF_SIZE = 65536  # 64KB buffer size (adjust as needed)
        hash_obj = hashlib.sha256()

        with zipfile.ZipFile(zip_file) as zip:
            with zip.open(file_name) as file:
                while True:
                    data = file.read(BUF_SIZE)
                    if not data:
                        break
                    hash_obj.update(data)

        return hash_obj.hexdigest()
    except KeyError as e:
        # Handle file not found in the zip error
        send_message("\n\t\t\tError: File not found in the zip - " + str(e), error=True)
        return None
    except Exception as e:
        # Handle other exceptions
        send_message("\n\t\t\tError: " + str(e), error=True)
        return None


# regex out underscore from passed string and return it
def replace_underscore_in_name(name):
    # Replace underscores that are preceded and followed by a number with a period
    name = re.sub(r"(?<=\d)_(?=\d)", ".", name)
    # Replace all other underscores with a space
    name = re.sub(r"_", " ", name)
    name = remove_dual_space(name).strip()
    return name


# Reorganizes the passed array list by pulling the first letter of the string passed
# and inserting all matched items into the passed position of the array list
def organize_array_list_by_first_letter(
    array_list, string, position_to_insert_at, exclude=None
):
    if string:
        first_letter_of_file_name = string[0]
        for item in array_list[:]:
            if item != exclude or not exclude:
                name = os.path.basename(item)
                first_letter_of_dir = name[0]
                if (
                    first_letter_of_dir.lower() == first_letter_of_file_name.lower()
                    and item != array_list[position_to_insert_at]
                ):
                    array_list.remove(item)
                    array_list.insert(position_to_insert_at, item)
    else:
        print(
            "First letter of file name was not found, skipping reorganization of array list."
        )
    return array_list


class IdentifierResult:
    def __init__(self, series_name, identifiers, path, matches):
        self.series_name = series_name
        self.identifiers = identifiers
        self.path = path
        self.matches = matches


# get identifiers from the passed zip comment
def get_identifiers_from_zip_comment(zip_comment):
    metadata = None
    if re.search(
        r"Identifiers",
        zip_comment,
        re.IGNORECASE,
    ):
        # split on Identifiers: and only keep the second half
        identifiers = ((zip_comment.split("Identifiers:")[1]).strip()).split(",")

        # remove any whitespace
        identifiers = [x.strip() for x in identifiers]

        # remove any that are "NONE" - used to be the default vale for the identifier
        # in my isbn script for other reasons
        if identifiers:
            metadata = [
                x
                for x in identifiers
                if not re.search(
                    r"NONE",
                    x,
                    re.IGNORECASE,
                )
            ]
    return metadata


# Parses the individual words from the passed string and returns them as an array
# without punctuation, unidecoded, and in lowercase.
@lru_cache(maxsize=None)
def parse_words(user_string):
    words = []
    try:
        translator = str.maketrans("", "", string.punctuation)
        words = user_string.translate(translator)
        words = words.lower()
        words = unidecode(words).split()
    except Exception as e:
        send_message(f"parse_words(string={string}) - Error: {str(e)}", error=True)
    return words


# Checks for an existing series by pulling the series name from each elidable file in the downloads_folder
# and comparing it to an existin folder within the user's library.
def check_for_existing_series(group=False):
    global cached_paths
    global cached_identifier_results
    global messages_to_send
    cached_image_similarity_results = []
    if download_folders:
        print("\nChecking download folders for items to match to existing library...")
        for download_folder in download_folders:
            if os.path.exists(download_folder):
                # an array of unmatched items, used for skipping subsequent series
                # items that won't match
                unmatched_series = []
                for root, dirs, files in scandir.walk(download_folder):
                    print("\n" + root)
                    clean = None
                    if (
                        watchdog_toggle
                        and download_folders
                        and any(x for x in download_folders if root.startswith(x))
                    ):
                        clean = clean_and_sort(
                            root,
                            files,
                            dirs,
                            sort=True,
                            just_these_files=transferred_files,
                            just_these_dirs=transferred_dirs,
                        )
                    else:
                        clean = clean_and_sort(root, files, dirs, sort=True)

                    files, dirs = clean[0], clean[1]

                    if not files:
                        continue

                    volumes = upgrade_to_volume_class(
                        upgrade_to_file_class(
                            [f for f in files if os.path.isfile(os.path.join(root, f))],
                            root,
                        )
                    )

                    exclude = None
                    similar.cache_clear()
                    for file in volumes:
                        try:
                            if not file.series_name:
                                print(
                                    "\tSkipping: "
                                    + file.name
                                    + "\n\t\t - has no series_name"
                                )
                                continue

                            if (
                                file.name in processed_files or not processed_files
                            ) and os.path.isfile(file.path):
                                done = False

                                if (
                                    cached_image_similarity_results
                                    and match_through_image_similarity
                                ):
                                    for (
                                        cached_result
                                    ) in cached_image_similarity_results:
                                        # split on @@ and get the value to the right
                                        last_item = cached_result.split("@@")[
                                            -1
                                        ].strip()
                                        if not last_item:
                                            continue

                                        if (
                                            file.series_name
                                            + " - "
                                            + file.file_type
                                            + " - "
                                            + file.root
                                            + " - "
                                            + file.extension
                                            in cached_result
                                        ):
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
                                                group=group,
                                                image=True,
                                            )
                                            if done:
                                                break
                                if done:
                                    continue

                                if unmatched_series and (
                                    (
                                        not match_through_identifiers
                                        or file.file_type == "chapter"
                                    )
                                ):
                                    if (
                                        file.series_name
                                        + " - "
                                        + file.file_type
                                        + " - "
                                        + file.extension
                                        in unmatched_series
                                    ):
                                        # print("\t\tSkipping: " + file.name + "...")
                                        continue
                                if (
                                    cached_identifier_results
                                    and match_through_identifiers
                                    and file.file_type == "volume"
                                ):
                                    found = False
                                    for cached_identifier in cached_identifier_results:
                                        if (
                                            cached_identifier.series_name
                                            == file.series_name
                                        ):
                                            check_upgrade(
                                                os.path.dirname(cached_identifier.path),
                                                os.path.basename(
                                                    cached_identifier.path
                                                ),
                                                file,
                                                similarity_strings=cached_identifier.matches,
                                                isbn=True,
                                                group=group,
                                            )
                                            if (
                                                cached_identifier.path
                                                not in cached_paths
                                            ):
                                                cached_paths.append(
                                                    cached_identifier.path
                                                )
                                                write_to_file(
                                                    "cached_paths.txt",
                                                    cached_identifier.path,
                                                    without_timestamp=True,
                                                    check_for_dup=True,
                                                )
                                            found = True
                                            break
                                    if found:
                                        continue
                                if cached_paths:
                                    if exclude:
                                        cached_paths = (
                                            organize_array_list_by_first_letter(
                                                cached_paths, file.name, 1, exclude
                                            )
                                        )
                                    else:
                                        cached_paths = (
                                            organize_array_list_by_first_letter(
                                                cached_paths, file.name, 1
                                            )
                                        )
                                downloaded_file_series_name = (
                                    (str(file.series_name)).lower()
                                ).strip()
                                downloaded_file_series_name = (
                                    (
                                        replace_underscore_in_name(
                                            remove_punctuation(
                                                downloaded_file_series_name
                                            )
                                        )
                                    )
                                    .strip()
                                    .lower()
                                )
                                if (
                                    cached_paths
                                    and file.name != downloaded_file_series_name
                                ):
                                    if exclude:
                                        cached_paths = (
                                            organize_array_list_by_first_letter(
                                                cached_paths,
                                                downloaded_file_series_name,
                                                2,
                                                exclude,
                                            )
                                        )
                                    else:
                                        cached_paths = (
                                            organize_array_list_by_first_letter(
                                                cached_paths,
                                                downloaded_file_series_name,
                                                2,
                                            )
                                        )

                                if cached_paths:
                                    print("\n\tChecking path types...")
                                    for p in cached_paths:
                                        if paths_with_types:
                                            skip_cached_path = False
                                            for item in paths_with_types:
                                                if p.startswith(item.path):
                                                    if (
                                                        file.file_type
                                                        not in item.path_formats
                                                    ):
                                                        print(
                                                            "\t\tSkipping: "
                                                            + p
                                                            + " - Path: "
                                                            + str(item.path_formats)
                                                            + " File: "
                                                            + file.file_type
                                                        )
                                                        skip_cached_path = True
                                                    elif (
                                                        file.extension
                                                        not in item.path_extensions
                                                    ):
                                                        print(
                                                            "\t\tSkipping: "
                                                            + p
                                                            + " - Path: "
                                                            + str(item.path_extensions)
                                                            + " File: "
                                                            + file.extension
                                                        )
                                                        skip_cached_path = True
                                                    break
                                            if skip_cached_path:
                                                continue
                                        position = cached_paths.index(p) + 1
                                        if (
                                            os.path.exists(p)
                                            and os.path.isdir(p)
                                            and p not in download_folders
                                        ):
                                            successful_file_series_name = (
                                                (str(os.path.basename(p))).lower()
                                            ).strip()
                                            successful_file_series_name = (
                                                (
                                                    replace_underscore_in_name(
                                                        remove_punctuation(
                                                            successful_file_series_name
                                                        )
                                                    )
                                                )
                                                .strip()
                                                .lower()
                                            )
                                            successful_similarity_score = None
                                            if (
                                                successful_file_series_name.lower()
                                                == downloaded_file_series_name.lower()
                                            ):
                                                successful_similarity_score = 1
                                            else:
                                                successful_similarity_score = similar(
                                                    successful_file_series_name,
                                                    downloaded_file_series_name,
                                                )
                                            # print(similar.cache_info()) # only for testing
                                            print(
                                                "\n\t\t-(CACHE)- "
                                                + str(position)
                                                + " of "
                                                + str(len(cached_paths))
                                                + " - "
                                                + '"'
                                                + file.name
                                                + '"'
                                                + "\n\t\tCHECKING: "
                                                + downloaded_file_series_name
                                                + "\n\t\tAGAINST:  "
                                                + successful_file_series_name
                                                + "\n\t\tSCORE:    "
                                                + str(successful_similarity_score)
                                            )
                                            if (
                                                successful_similarity_score
                                                >= required_similarity_score
                                            ):
                                                write_to_file(
                                                    "changes.txt",
                                                    (
                                                        '\t\tSimilarity between: "'
                                                        + successful_file_series_name
                                                        + '" and "'
                                                        + downloaded_file_series_name
                                                        + '"'
                                                    ),
                                                )
                                                write_to_file(
                                                    "changes.txt",
                                                    (
                                                        "\tSimilarity Score: "
                                                        + str(
                                                            successful_similarity_score
                                                        )
                                                        + " out of 1.0"
                                                    ),
                                                )
                                                print(
                                                    '\n\t\tSimilarity between: "'
                                                    + successful_file_series_name
                                                    + '" and "'
                                                    + downloaded_file_series_name
                                                    + '" Score: '
                                                    + str(successful_similarity_score)
                                                    + " out of 1.0\n"
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
                                                    group=group,
                                                )
                                                if done:
                                                    if (
                                                        group
                                                        and grouped_notifications
                                                        and not group_discord_notifications_until_max
                                                    ):
                                                        send_discord_message(
                                                            None, grouped_notifications
                                                        )
                                                    if p not in cached_paths:
                                                        cached_paths.append(p)
                                                        write_to_file(
                                                            "cached_paths.txt",
                                                            p,
                                                            without_timestamp=True,
                                                            check_for_dup=True,
                                                        )
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
                                    if (
                                        group
                                        and grouped_notifications
                                        and not group_discord_notifications_until_max
                                    ):
                                        send_discord_message(
                                            None, grouped_notifications
                                        )
                                    continue
                                download_file_zip_comment = get_zip_comment(file.path)
                                download_file_meta = (
                                    get_identifiers_from_zip_comment(
                                        download_file_zip_comment
                                    )
                                    if download_file_zip_comment
                                    else []
                                )
                                directories_found = []
                                matched_ids = []
                                for path in paths:
                                    path_position = paths.index(path) + 1
                                    if (
                                        os.path.exists(path)
                                        and not done
                                        and path not in download_folders
                                    ):
                                        if paths_with_types:
                                            skip_path = False
                                            for item in paths_with_types:
                                                if path == item.path:
                                                    if (
                                                        file.file_type
                                                        not in item.path_formats
                                                    ):
                                                        print(
                                                            "\nSkipping path: "
                                                            + path
                                                            + " - Path: "
                                                            + array_to_string(
                                                                item.path_formats
                                                            )
                                                            + " File: "
                                                            + str(file.file_type)
                                                        )
                                                        skip_path = True
                                                        break
                                                    elif (
                                                        file.extension
                                                        not in item.path_extensions
                                                    ):
                                                        print(
                                                            "\nSkipping path: "
                                                            + path
                                                            + " - Path: "
                                                            + array_to_string(
                                                                item.path_extensions
                                                            )
                                                            + " File: "
                                                            + str(file.extension)
                                                        )
                                                        skip_path = True
                                                        break
                                            if skip_path:
                                                continue
                                        try:
                                            os.chdir(path)
                                            reorganized = False
                                            for root, dirs, files in scandir.walk(path):
                                                if done:
                                                    break
                                                if not reorganized:
                                                    dirs = organize_array_list_by_first_letter(
                                                        dirs,
                                                        file.series_name,
                                                        1,
                                                        exclude=exclude,
                                                    )
                                                    dirs = organize_array_list_by_first_letter(
                                                        dirs,
                                                        file.series_name,
                                                        2,
                                                        exclude=exclude,
                                                    )
                                                    reorganized = True
                                                if (
                                                    not match_through_identifiers
                                                    and root in cached_paths
                                                ):
                                                    continue
                                                clean_two = clean_and_sort(
                                                    root, files, dirs
                                                )
                                                files, dirs = clean_two[0], clean_two[1]
                                                file_objects = upgrade_to_file_class(
                                                    files, root
                                                )
                                                global folder_accessor
                                                folder_accessor = Folder(
                                                    root,
                                                    dirs,
                                                    os.path.basename(
                                                        os.path.dirname(root)
                                                    ),
                                                    os.path.basename(root),
                                                    file_objects,
                                                )
                                                print(
                                                    "Looking inside: "
                                                    + folder_accessor.root
                                                )
                                                if folder_accessor.dirs:
                                                    if (
                                                        root not in cached_paths
                                                        and root not in download_folders
                                                    ):
                                                        if done:
                                                            break
                                                        print(
                                                            "\nLooking for: "
                                                            + file.series_name
                                                        )
                                                        for dir in folder_accessor.dirs:
                                                            if done:
                                                                break
                                                            dir_position = (
                                                                folder_accessor.dirs.index(
                                                                    dir
                                                                )
                                                                + 1
                                                            )
                                                            existing_series_folder_from_library = (
                                                                (
                                                                    replace_underscore_in_name(
                                                                        remove_punctuation(
                                                                            remove_bracketed_info_from_name(
                                                                                dir
                                                                            )
                                                                        )
                                                                    )
                                                                )
                                                                .strip()
                                                                .lower()
                                                            )
                                                            similarity_score = None
                                                            if (
                                                                existing_series_folder_from_library.lower()
                                                                == downloaded_file_series_name.lower()
                                                            ):
                                                                similarity_score = 1
                                                            else:
                                                                similarity_score = similar(
                                                                    existing_series_folder_from_library,
                                                                    downloaded_file_series_name,
                                                                )
                                                            print(
                                                                "\n\t\t-(NOT CACHE)- "
                                                                + str(dir_position)
                                                                + " of "
                                                                + str(
                                                                    len(
                                                                        folder_accessor.dirs
                                                                    )
                                                                )
                                                                + " - path "
                                                                + str(path_position)
                                                                + " of "
                                                                + str(len(paths))
                                                                + " - "
                                                                + '"'
                                                                + file.name
                                                                + '"'
                                                                + "\n\t\tCHECKING: "
                                                                + downloaded_file_series_name
                                                                + "\n\t\tAGAINST:  "
                                                                + existing_series_folder_from_library
                                                                + "\n\t\tSCORE:    "
                                                                + str(similarity_score)
                                                            )
                                                            if (
                                                                similarity_score
                                                                >= required_similarity_score
                                                            ):
                                                                write_to_file(
                                                                    "changes.txt",
                                                                    (
                                                                        '\t\tSimilarity between: "'
                                                                        + existing_series_folder_from_library
                                                                        + '" and "'
                                                                        + downloaded_file_series_name
                                                                        + '"'
                                                                    ),
                                                                )
                                                                write_to_file(
                                                                    "changes.txt",
                                                                    (
                                                                        "\tSimilarity Score: "
                                                                        + str(
                                                                            similarity_score
                                                                        )
                                                                        + " out of 1.0"
                                                                    ),
                                                                )
                                                                print(
                                                                    '\n\t\tSimilarity between: "'
                                                                    + existing_series_folder_from_library
                                                                    + '" and "'
                                                                    + downloaded_file_series_name
                                                                    + '" Score: '
                                                                    + str(
                                                                        similarity_score
                                                                    )
                                                                    + " out of 1.0\n"
                                                                )
                                                                done = check_upgrade(
                                                                    folder_accessor.root,
                                                                    dir,
                                                                    file,
                                                                    similarity_strings=[
                                                                        downloaded_file_series_name,
                                                                        existing_series_folder_from_library,
                                                                        similarity_score,
                                                                        required_similarity_score,
                                                                    ],
                                                                    group=group,
                                                                )
                                                                if done:
                                                                    if (
                                                                        group
                                                                        and grouped_notifications
                                                                        and not group_discord_notifications_until_max
                                                                    ):
                                                                        send_discord_message(
                                                                            None,
                                                                            grouped_notifications,
                                                                        )
                                                                    if (
                                                                        os.path.join(
                                                                            folder_accessor.root,
                                                                            dir,
                                                                        )
                                                                        not in cached_paths
                                                                    ):
                                                                        cached_paths.append(
                                                                            os.path.join(
                                                                                folder_accessor.root,
                                                                                dir,
                                                                            )
                                                                        )
                                                                        write_to_file(
                                                                            "cached_paths.txt",
                                                                            os.path.join(
                                                                                folder_accessor.root,
                                                                                dir,
                                                                            ),
                                                                            without_timestamp=True,
                                                                            check_for_dup=True,
                                                                        )
                                                                    if (
                                                                        len(volumes) > 1
                                                                        and os.path.join(
                                                                            folder_accessor.root,
                                                                            dir,
                                                                        )
                                                                        in cached_paths
                                                                        and os.path.join(
                                                                            folder_accessor.root,
                                                                            dir,
                                                                        )
                                                                        != cached_paths[
                                                                            0
                                                                        ]
                                                                    ):
                                                                        cached_paths.remove(
                                                                            os.path.join(
                                                                                folder_accessor.root,
                                                                                dir,
                                                                            )
                                                                        )
                                                                        cached_paths.insert(
                                                                            0,
                                                                            os.path.join(
                                                                                folder_accessor.root,
                                                                                dir,
                                                                            ),
                                                                        )
                                                                    break
                                                                else:
                                                                    continue
                                                            elif (
                                                                match_through_image_similarity
                                                                and file.file_type
                                                                == "volume"
                                                            ):
                                                                shortened_folder_name = get_shortened_title(
                                                                    dir
                                                                )
                                                                if (
                                                                    not shortened_folder_name
                                                                ):
                                                                    shortened_folder_name = (
                                                                        dir
                                                                    )
                                                                shortened_folder_name = (
                                                                    (
                                                                        replace_underscore_in_name(
                                                                            remove_punctuation(
                                                                                remove_bracketed_info_from_name(
                                                                                    shortened_folder_name
                                                                                )
                                                                            )
                                                                        )
                                                                    )
                                                                    .strip()
                                                                    .lower()
                                                                )
                                                                file_shortened_series_name = (
                                                                    ""
                                                                )
                                                                if (
                                                                    file.shortened_series_name
                                                                ):
                                                                    file_shortened_series_name = (
                                                                        file.shortened_series_name
                                                                    )
                                                                else:
                                                                    file_shortened_series_name = (
                                                                        file.series_name
                                                                    )
                                                                file_shortened_series_name = (
                                                                    (
                                                                        replace_underscore_in_name(
                                                                            remove_punctuation(
                                                                                remove_bracketed_info_from_name(
                                                                                    file_shortened_series_name
                                                                                )
                                                                            )
                                                                        )
                                                                    )
                                                                    .strip()
                                                                    .lower()
                                                                )
                                                                if (
                                                                    shortened_folder_name
                                                                    and file_shortened_series_name
                                                                ):
                                                                    # use parse_words() to get the words from both strings
                                                                    file_shortened_series_name_words = (
                                                                        []
                                                                    )
                                                                    shortened_folder_name_words = parse_words(
                                                                        shortened_folder_name
                                                                    )

                                                                    if shortened_folder_name_words:
                                                                        file_shortened_series_name_words = parse_words(
                                                                            file_shortened_series_name
                                                                        )

                                                                    if (
                                                                        file_shortened_series_name_words
                                                                        and shortened_folder_name_words
                                                                    ):
                                                                        if len(
                                                                            file_shortened_series_name_words
                                                                        ) != len(
                                                                            shortened_folder_name_words
                                                                        ):
                                                                            # determine which array is smaller, then get 40% of that length
                                                                            shortened_length = (
                                                                                1
                                                                            )
                                                                            if len(
                                                                                file_shortened_series_name_words
                                                                            ) < len(
                                                                                shortened_folder_name_words
                                                                            ):
                                                                                shortened_length = int(
                                                                                    len(
                                                                                        file_shortened_series_name_words
                                                                                    )
                                                                                    * shortened_word_filter_percentage
                                                                                )
                                                                            else:
                                                                                shortened_length = int(
                                                                                    len(
                                                                                        shortened_folder_name_words
                                                                                    )
                                                                                    * shortened_word_filter_percentage
                                                                                )

                                                                            # print(
                                                                            #     str(
                                                                            #         shortened_length
                                                                            #     )
                                                                            # )

                                                                            if (
                                                                                shortened_length
                                                                                == 0
                                                                            ):
                                                                                shortened_length = (
                                                                                    1
                                                                                )

                                                                            # shorten the arrays, so if the value was 3, then get the first 3 elements for both
                                                                            file_shortened_series_name_words = file_shortened_series_name_words[
                                                                                :shortened_length
                                                                            ]
                                                                            shortened_folder_name_words = shortened_folder_name_words[
                                                                                :shortened_length
                                                                            ]

                                                                    if (
                                                                        shortened_folder_name
                                                                        == file_shortened_series_name.lower()
                                                                        or similar(
                                                                            shortened_folder_name,
                                                                            file_shortened_series_name,
                                                                        )
                                                                        >= required_similarity_score
                                                                        or (
                                                                            shortened_folder_name_words
                                                                            and file_shortened_series_name_words
                                                                        )
                                                                        and (
                                                                            shortened_folder_name_words
                                                                            == file_shortened_series_name_words
                                                                        )
                                                                    ):
                                                                        print(
                                                                            "\n\t\tAttempting alternative match through cover image similarity..."
                                                                        )
                                                                        print(
                                                                            f"\t\t\tSeries Names: \n\t\t\t\t{dir}\n\t\t\t\t{file.series_name}"
                                                                        )
                                                                        # get the volumes from the dir, only files
                                                                        img_volumes = upgrade_to_volume_class(
                                                                            upgrade_to_file_class(
                                                                                [
                                                                                    f
                                                                                    for f in os.listdir(
                                                                                        os.path.join(
                                                                                            folder_accessor.root,
                                                                                            dir,
                                                                                        )
                                                                                    )
                                                                                    if os.path.isfile(
                                                                                        join(
                                                                                            os.path.join(
                                                                                                folder_accessor.root,
                                                                                                dir,
                                                                                            ),
                                                                                            f,
                                                                                        )
                                                                                    )
                                                                                ],
                                                                                os.path.join(
                                                                                    folder_accessor.root,
                                                                                    dir,
                                                                                ),
                                                                            )
                                                                        )
                                                                        if img_volumes:
                                                                            # find a matching volume number and part
                                                                            matching_volumes = [
                                                                                volume
                                                                                for volume in img_volumes
                                                                                if (
                                                                                    volume.volume_number
                                                                                    != ""
                                                                                    and file.volume_number
                                                                                    != ""
                                                                                    and (
                                                                                        (
                                                                                            (
                                                                                                volume.volume_number
                                                                                                == file.volume_number
                                                                                                or (
                                                                                                    isinstance(
                                                                                                        file.volume_number,
                                                                                                        list,
                                                                                                    )
                                                                                                    and volume.volume_number
                                                                                                    in file.volume_number
                                                                                                )
                                                                                                or (
                                                                                                    isinstance(
                                                                                                        volume.volume_number,
                                                                                                        list,
                                                                                                    )
                                                                                                    and file.volume_number
                                                                                                    in volume.volume_number
                                                                                                )
                                                                                            )
                                                                                            and volume.volume_part
                                                                                            == file.volume_part
                                                                                        )
                                                                                        or (
                                                                                            volume.index_number
                                                                                            != ""
                                                                                            and file.index_number
                                                                                            != ""
                                                                                            and volume.index_number
                                                                                            == file.index_number
                                                                                        )
                                                                                    )
                                                                                )
                                                                            ]

                                                                            # add the remaining volumes to matching volumes if the difference is less than 10
                                                                            if (
                                                                                len(
                                                                                    img_volumes
                                                                                )
                                                                                - len(
                                                                                    matching_volumes
                                                                                )
                                                                            ) <= 10:
                                                                                matching_volumes.extend(
                                                                                    [
                                                                                        volume
                                                                                        for volume in img_volumes
                                                                                        if volume
                                                                                        not in matching_volumes
                                                                                    ]
                                                                                )

                                                                            if matching_volumes:
                                                                                for matching_volume in matching_volumes:
                                                                                    print(
                                                                                        f"\t\t\tMatching volume:\n\t\t\t\t{matching_volume.name}\n\t\t\t\t{file.name}"
                                                                                    )
                                                                                    # get both covers and check the image similarity
                                                                                    existing_volume_cover_data = find_and_extract_cover(
                                                                                        matching_volume,
                                                                                        return_data_only=True,
                                                                                        silent=True,
                                                                                    )
                                                                                    downloaded_volume_cover_data = find_and_extract_cover(
                                                                                        file,
                                                                                        return_data_only=True,
                                                                                        silent=True,
                                                                                    )
                                                                                    if (
                                                                                        existing_volume_cover_data
                                                                                        and downloaded_volume_cover_data
                                                                                    ):
                                                                                        score = prep_images_for_similarity(
                                                                                            existing_volume_cover_data,
                                                                                            downloaded_volume_cover_data,
                                                                                            both_cover_data=True,
                                                                                            silent=True,
                                                                                        )
                                                                                        print(
                                                                                            "\t\t\tCover Image Similarity Score: "
                                                                                            + str(
                                                                                                score
                                                                                            )
                                                                                        )
                                                                                        if (
                                                                                            score
                                                                                            >= required_image_similarity_score
                                                                                        ):
                                                                                            print(
                                                                                                "\t\tMatch found through cover image similarity."
                                                                                            )
                                                                                            # check all volumes in volumes, if all the volumes in this dir have the same series_name
                                                                                            all_matching = True
                                                                                            same_root_files = [
                                                                                                item
                                                                                                for item in volumes
                                                                                                if item.root
                                                                                                == file.root
                                                                                            ]
                                                                                            if same_root_files:
                                                                                                all_matching = all(
                                                                                                    item.series_name.lower().strip()
                                                                                                    == file.series_name.lower().strip()
                                                                                                    for item in same_root_files
                                                                                                    if item
                                                                                                    != file
                                                                                                )
                                                                                            if all_matching:
                                                                                                print(
                                                                                                    "\t\t\tAll Download Series Names Match, Adding to Cache.\n"
                                                                                                )
                                                                                                cached_image_similarity_results.append(
                                                                                                    file.series_name
                                                                                                    + " - "
                                                                                                    + file.file_type
                                                                                                    + " - "
                                                                                                    + file.root
                                                                                                    + " - "
                                                                                                    + file.extension
                                                                                                    + " @@ "
                                                                                                    + os.path.join(
                                                                                                        folder_accessor.root,
                                                                                                        dir,
                                                                                                    )
                                                                                                )
                                                                                            done = check_upgrade(
                                                                                                folder_accessor.root,
                                                                                                dir,
                                                                                                file,
                                                                                                similarity_strings=[
                                                                                                    shortened_folder_name,
                                                                                                    file_shortened_series_name,
                                                                                                    score,
                                                                                                    required_image_similarity_score,
                                                                                                ],
                                                                                                group=group,
                                                                                                image=matching_volume,
                                                                                            )
                                                                                            if done:
                                                                                                break
                                                                                        else:
                                                                                            print(
                                                                                                "\t\tNo match found through image similarity."
                                                                                            )
                                                                                    else:
                                                                                        if (
                                                                                            not existing_volume_cover_data
                                                                                        ):
                                                                                            print(
                                                                                                "\t\t\tNo existing volume cover data found."
                                                                                            )
                                                                                        if (
                                                                                            not downloaded_volume_cover_data
                                                                                        ):
                                                                                            print(
                                                                                                "\t\t\tNo downloaded volume cover data found."
                                                                                            )
                                                                            else:
                                                                                print(
                                                                                    "\t\t\tNo matching volumes found."
                                                                                )
                                                if (
                                                    not done
                                                    and match_through_identifiers
                                                    and root not in download_folders
                                                    and download_file_meta
                                                    and file.file_type == "volume"
                                                    and folder_accessor.files
                                                ):
                                                    if done:
                                                        break
                                                    print(
                                                        "\n\t\tMatching Identifier Search: "
                                                        + folder_accessor.root
                                                    )
                                                    for f in folder_accessor.files:
                                                        if f.root in directories_found:
                                                            break
                                                        if (
                                                            f.extension
                                                            != file.extension
                                                        ):
                                                            continue
                                                        print("\t\t\t" + f.name)
                                                        existing_file_zip_comment = (
                                                            get_zip_comment_cache(
                                                                f.path
                                                            )
                                                        )
                                                        existing_file_meta = get_identifiers_from_zip_comment(
                                                            existing_file_zip_comment
                                                        )
                                                        if existing_file_meta:
                                                            print(
                                                                "\t\t\t\t"
                                                                + str(
                                                                    existing_file_meta
                                                                )
                                                            )
                                                            if any(
                                                                d_meta
                                                                in existing_file_meta
                                                                and f.root
                                                                not in directories_found
                                                                for d_meta in download_file_meta
                                                            ):
                                                                directories_found.append(
                                                                    f.root
                                                                )
                                                                matched_ids.extend(
                                                                    [
                                                                        download_file_meta,
                                                                        existing_file_meta,
                                                                    ]
                                                                )
                                                                print(
                                                                    "\n\t\t\t\tMatch found in: "
                                                                    + f.root
                                                                )
                                                                break
                                                        else:
                                                            print("\t\t\t\t[]")
                                        except Exception as e:
                                            send_message(str(e), error=True)
                                if (
                                    not done
                                    and match_through_identifiers
                                    and file.file_type == "volume"
                                    and directories_found
                                ):
                                    directories_found = remove_duplicates(
                                        directories_found
                                    )
                                    if len(directories_found) == 1:
                                        print(
                                            "\n\n\t\tMach found in: "
                                            + directories_found[0]
                                            + "\n"
                                        )
                                        base = os.path.basename(directories_found[0])
                                        identifier = IdentifierResult(
                                            file.series_name,
                                            download_file_meta,
                                            directories_found[0],
                                            matched_ids,
                                        )
                                        if identifier not in cached_identifier_results:
                                            cached_identifier_results.append(identifier)
                                        done = check_upgrade(
                                            os.path.dirname(directories_found[0]),
                                            base,
                                            file,
                                            similarity_strings=matched_ids,
                                            isbn=True,
                                            group=group,
                                        )
                                        if done:
                                            if (
                                                group
                                                and grouped_notifications
                                                and not group_discord_notifications_until_max
                                            ):
                                                send_discord_message(
                                                    None, grouped_notifications
                                                )
                                            if directories_found[0] not in cached_paths:
                                                cached_paths.append(
                                                    directories_found[0]
                                                )
                                                write_to_file(
                                                    "cached_paths.txt",
                                                    directories_found[0],
                                                    without_timestamp=True,
                                                    check_for_dup=True,
                                                )
                                            if (
                                                len(volumes) > 1
                                                and directories_found[0] in cached_paths
                                                and directories_found[0]
                                                != cached_paths[0]
                                            ):
                                                cached_paths.remove(
                                                    directories_found[0]
                                                )
                                                cached_paths.insert(
                                                    0, directories_found[0]
                                                )
                                    else:
                                        print(
                                            "\t\t\tMatching ISBN or Series ID found in multiple directories."
                                        )
                                        for d in directories_found:
                                            print("\t\t\t\t" + d)
                                        print("\t\t\tDisregarding Matches...")
                                if not done:
                                    unmatched_series.append(
                                        file.series_name
                                        + " - "
                                        + file.file_type
                                        + " - "
                                        + file.extension
                                    )
                                    print("No match found.")
                        except Exception as e:
                            send_message(str(e), error=True)
    if grouped_notifications:
        send_discord_message(
            None,
            grouped_notifications,
        )
    webhook_use = None
    if messages_to_send:
        grouped_by_series_names = group_similar_series(messages_to_send)
        messages_to_send = []
        if grouped_by_series_names:
            # sort them alphabetically by series name
            grouped_by_series_names.sort(key=lambda x: x["series_name"])
            for grouped_by_series_name in grouped_by_series_names:
                # sort the group's messages lowest to highest by the number field
                # the number can be a float or an array of floats
                grouped_by_series_name["messages"].sort(
                    key=lambda x: x.fields[0]["value"].split(",")[0]
                )
                if output_chapter_covers_to_discord:
                    for message in grouped_by_series_name["messages"][:]:
                        cover = find_and_extract_cover(
                            message.volume_obj, return_data_only=True
                        )
                        embed = [
                            handle_fields(
                                DiscordEmbed(
                                    title=message.title,
                                    color=message.color,
                                ),
                                fields=message.fields,
                            )
                        ]
                        if not webhook_use:
                            webhook_use = message.webhook
                        add_to_grouped_notifications(
                            Embed(embed[0], cover), webhook_use
                        )
                        grouped_by_series_name["messages"].remove(message)
                else:
                    volume_numbers_mts = []
                    volume_names_mts = []
                    title = grouped_by_series_name["messages"][0].fields[0]["name"]
                    title_2 = (
                        grouped_by_series_name["messages"][0].fields[1]["name"] + "(s)"
                    )
                    series_name = grouped_by_series_name["messages"][0].series_name
                    for message in grouped_by_series_name["messages"]:
                        if message.fields and len(message.fields) >= 2:
                            # remove ``` from the start and end of the value
                            volume_numbers_mts.append(
                                re.sub(r"```", "", message.fields[0]["value"])
                            )
                            volume_names_mts.append(
                                re.sub(r"```", "", message.fields[1]["value"])
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
                        embed = [
                            handle_fields(
                                DiscordEmbed(
                                    title=grouped_by_series_name["messages"][0].title
                                    + "(s)",
                                    color=grouped_by_series_name["messages"][0].color,
                                ),
                                fields=new_fields,
                            )
                        ]
                        if not webhook_use:
                            webhook_use = grouped_by_series_name["messages"][0].webhook
                        add_to_grouped_notifications(Embed(embed[0], None), webhook_use)
    if grouped_notifications:
        send_discord_message(
            None,
            grouped_notifications,
            passed_webhook=webhook_use,
        )

    # clear lru_cache for parse_words
    parse_words.cache_clear()


# Groups messages by series name
def group_similar_series(messages_to_send):
    grouped_by_series_names = []
    # go through messages_to_send and group them by series name,
    # one group per series name and each group will contian all the messages for that series
    for message in messages_to_send:
        if grouped_by_series_names:
            found = False
            for grouped_series_name in grouped_by_series_names:
                if message.series_name == grouped_series_name["series_name"]:
                    grouped_series_name["messages"].append(message)
                    found = True
                    break
            if not found:
                grouped_by_series_names.append(
                    {
                        "series_name": message.series_name,
                        "messages": [message],
                    }
                )
        else:
            grouped_by_series_names.append(
                {
                    "series_name": message.series_name,
                    "messages": [message],
                }
            )

    return grouped_by_series_names


# Removes any unnecessary junk through regex in the folder name and returns the result
# !OLD METHOD!: Only used for cleaning a folder name as a backup if no volumes were found inside the folder
# when renaming folders in the dowload directory.
def get_series_name(dir):
    dir = remove_dual_space(re.sub(r"_extra", " ", dir, flags=re.IGNORECASE)).strip()
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
def rename_dirs_in_download_folder(group=False):
    global transferred_dirs
    global transferred_files
    print("\nLooking for folders to rename...")
    for download_folder in download_folders:
        if os.path.exists(download_folder):
            try:
                download_folder_dirs = [
                    f
                    for f in os.listdir(download_folder)
                    if os.path.isdir(join(download_folder, f))
                ]
                if not download_folder_dirs:
                    continue
                download_folder_files = [
                    f
                    for f in os.listdir(download_folder)
                    if os.path.isfile(join(download_folder, f))
                ]
                clean = None
                if (
                    watchdog_toggle
                    and download_folders
                    and any(
                        x for x in download_folders if download_folder.startswith(x)
                    )
                ):
                    clean = clean_and_sort(
                        download_folder,
                        download_folder_files,
                        download_folder_dirs,
                        just_these_files=transferred_files,
                        just_these_dirs=transferred_dirs,
                    )
                else:
                    clean = clean_and_sort(
                        download_folder, download_folder_files, download_folder_dirs
                    )
                download_folder_files, download_folder_dirs = clean[0], clean[1]
                global folder_accessor
                file_objects = upgrade_to_file_class(
                    download_folder_files[:], download_folder
                )
                folder_accessor = Folder(
                    download_folder,
                    download_folder_dirs[:],
                    os.path.basename(os.path.dirname(download_folder)),
                    os.path.basename(download_folder),
                    file_objects,
                )
                for folderDir in folder_accessor.dirs[:]:
                    print("\t" + os.path.join(download_folder, folderDir))
                    done = False
                    full_file_path = os.path.join(folder_accessor.root, folderDir)
                    volumes = upgrade_to_volume_class(
                        upgrade_to_file_class(
                            [
                                f
                                for f in os.listdir(full_file_path)
                                if os.path.isfile(join(full_file_path, f))
                            ],
                            full_file_path,
                        )
                    )
                    volume_one = None
                    matching = []
                    volume_one_series_name = None
                    if volumes:
                        # sort by name
                        if len(volumes) > 1:
                            volumes = sorted(volumes, key=lambda x: x.name)
                        first_series_name = volumes[0].series_name
                        if first_series_name:
                            # clone volumes list and remove the first result
                            clone_list = volumes[:]
                            if clone_list and len(clone_list) > 1:
                                clone_list.remove(volumes[0])
                            # check that at least 90% of the volumes have similar series_names
                            for v in clone_list:
                                if (
                                    v.series_name.lower() == first_series_name.lower()
                                    or similar(
                                        remove_punctuation(v.series_name),
                                        remove_punctuation(first_series_name),
                                    )
                                    >= required_similarity_score
                                ):
                                    matching.append(v)
                                else:
                                    print(
                                        "\t\t"
                                        + v.series_name
                                        + " does not match "
                                        + first_series_name
                                    )
                            if (len(matching) >= len(volumes) * 0.9) and len(
                                volumes
                            ) == 1:
                                volume_one = matching[0]
                            elif (len(matching) + 1 >= len(volumes) * 0.8) and len(
                                volumes
                            ) > 1:
                                volume_one = matching[0]
                            else:
                                print(
                                    "\t\t"
                                    + str(len(matching))
                                    + " out of "
                                    + str(len(volumes))
                                    + " volumes match the first volume's series name."
                                )
                        else:
                            print(
                                "\t\tCould not find series name for: " + volumes[0].path
                            )
                        if volume_one and volume_one.series_name:
                            volume_one_series_name = volume_one.series_name
                        if (
                            volume_one
                            and volume_one.series_name != folderDir
                            and (
                                (
                                    similar(
                                        remove_bracketed_info_from_name(
                                            volume_one.series_name
                                        ),
                                        remove_bracketed_info_from_name(folderDir),
                                    )
                                    >= 0.25
                                )
                                or (
                                    similar(
                                        volume_one.series_name,
                                        folderDir,
                                    )
                                    >= 0.25
                                )
                            )
                        ):
                            send_message("\n\tBEFORE: " + folderDir, discord=False)
                            send_message(
                                "\tAFTER:  " + volume_one.series_name, discord=False
                            )
                            if volumes:
                                print("\t\tFILES:")
                                for v in volumes:
                                    print("\t\t\t" + v.name)
                            user_input = ""
                            if manual_rename:
                                user_input = get_input_from_user(
                                    "\tRename", ["y", "n"], ["y", "n"]
                                )
                            else:
                                user_input = "y"
                            try:
                                if user_input == "y":
                                    # if the direcotry doesn't exist, then rename to it
                                    if not os.path.exists(
                                        os.path.join(
                                            folder_accessor.root,
                                            volume_one.series_name,
                                        )
                                    ):
                                        try:
                                            new_folder_path = rename_folder(
                                                os.path.join(
                                                    folder_accessor.root, folderDir
                                                ),
                                                os.path.join(
                                                    folder_accessor.root,
                                                    volume_one.series_name,
                                                ),
                                            )
                                            if watchdog_toggle:
                                                replaced_transferred_files = []
                                                # Go through all the transferred_files and update any that have the old folderDir as their path with the new series_name
                                                for f in transferred_files:
                                                    if f.startswith(
                                                        os.path.join(
                                                            folder_accessor.root,
                                                            folderDir,
                                                        )
                                                    ):
                                                        replacement = f.replace(
                                                            os.path.join(
                                                                folder_accessor.root,
                                                                folderDir,
                                                            ),
                                                            os.path.join(
                                                                folder_accessor.root,
                                                                volume_one.series_name,
                                                            ),
                                                        )
                                                        replaced_transferred_files.append(
                                                            replacement
                                                        )
                                                    else:
                                                        replaced_transferred_files.append(
                                                            f
                                                        )
                                                transferred_files = (
                                                    replaced_transferred_files
                                                )
                                                transferred_dirs.append(
                                                    Folder(
                                                        new_folder_path,
                                                        None,
                                                        os.path.basename(
                                                            os.path.dirname(
                                                                new_folder_path
                                                            )
                                                        ),
                                                        os.path.basename(
                                                            new_folder_path
                                                        ),
                                                        get_all_files_recursively_in_dir_watchdog(
                                                            new_folder_path
                                                        ),
                                                    )
                                                )
                                            done = True
                                        except Exception as e:
                                            send_message(
                                                "\t\tCould not rename "
                                                + folderDir
                                                + " to "
                                                + volume_one.series_name,
                                                error=True,
                                            )
                                    else:
                                        # move the files to the already existing directory if they don't already exist, otherwise delete them
                                        for v in volumes:
                                            if not os.path.isfile(
                                                os.path.join(
                                                    folder_accessor.root,
                                                    volume_one.series_name,
                                                    v.name,
                                                )
                                            ):
                                                move_file(
                                                    v,
                                                    os.path.join(
                                                        folder_accessor.root,
                                                        volume_one.series_name,
                                                    ),
                                                    group=group,
                                                )
                                                if watchdog_toggle:
                                                    transferred_files.append(
                                                        os.path.join(
                                                            folder_accessor.root,
                                                            volume_one.series_name,
                                                            v.name,
                                                        )
                                                    )
                                                    # remove old file
                                                    if v.path in transferred_files:
                                                        transferred_files.remove(v.path)
                                            else:
                                                print(
                                                    "\t\t"
                                                    + v.name
                                                    + " already exists in "
                                                    + volume_one.series_name
                                                )
                                                remove_file(v.path, silent=True)
                                                # remove old file
                                                if v.path in transferred_files:
                                                    transferred_files.remove(v.path)
                                        # check for an empty folder, and delete it if it is
                                        check_and_delete_empty_folder(v.root)
                                        done = True
                                else:
                                    print("\t\tSkipping...\n")
                            except Exception as e:
                                send_message(
                                    "Skipping..." + "\nERROR: " + str(e), error=True
                                )
                    if not done and (
                        not volume_one_series_name
                        or volume_one_series_name != folderDir
                    ):
                        download_folder_basename = os.path.basename(download_folder)
                        if re.search(
                            download_folder_basename, full_file_path, re.IGNORECASE
                        ):
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
                            for search in searches:
                                if re.search(search, folderDir, re.IGNORECASE):
                                    dir_clean = get_series_name(folderDir)
                                    dir_clean = re.sub(
                                        r"([A-Za-z])(_)", r"\1 ", dir_clean
                                    )
                                    # replace : with - in dir_clean
                                    dir_clean = re.sub(
                                        r"([A-Za-z])(\:)", r"\1 -", dir_clean
                                    )
                                    dir_clean = re.sub(r"([?])", "", dir_clean)
                                    # remove dual spaces from dir_clean
                                    dir_clean = remove_dual_space(dir_clean).strip()
                                    if not os.path.isdir(
                                        os.path.join(folder_accessor.root, dir_clean)
                                    ):
                                        send_message(
                                            "\n\tBEFORE: " + folderDir, discord=False
                                        )
                                        send_message(
                                            "\tAFTER:  " + dir_clean, discord=False
                                        )
                                        user_input = ""
                                        if manual_rename:
                                            user_input = get_input_from_user(
                                                "\tRename",
                                                ["y", "n"],
                                                ["y", "n"],
                                            )
                                        else:
                                            user_input = "y"
                                        try:
                                            if user_input == "y":
                                                try:
                                                    new_folder_path_two = rename_folder(
                                                        os.path.join(
                                                            folder_accessor.root,
                                                            folderDir,
                                                        ),
                                                        os.path.join(
                                                            folder_accessor.root,
                                                            dir_clean,
                                                        ),
                                                    )
                                                    if watchdog_toggle:
                                                        replaced_transferred_files_two = (
                                                            []
                                                        )
                                                        # Go through all the transferred_files and update any that have the old folderDir as their path with the new dir_clean
                                                        for f in transferred_files:
                                                            if f.startswith(
                                                                os.path.join(
                                                                    folder_accessor.root,
                                                                    folderDir,
                                                                )
                                                            ):
                                                                replacement = f.replace(
                                                                    os.path.join(
                                                                        folder_accessor.root,
                                                                        folderDir,
                                                                    ),
                                                                    os.path.join(
                                                                        folder_accessor.root,
                                                                        dir_clean,
                                                                    ),
                                                                )
                                                                replaced_transferred_files_two.append(
                                                                    replacement
                                                                )
                                                            else:
                                                                replaced_transferred_files_two.append(
                                                                    f
                                                                )
                                                        transferred_files = replaced_transferred_files_two
                                                        transferred_dirs.append(
                                                            Folder(
                                                                new_folder_path_two,
                                                                None,
                                                                os.path.basename(
                                                                    os.path.dirname(
                                                                        new_folder_path_two
                                                                    )
                                                                ),
                                                                os.path.basename(
                                                                    new_folder_path_two
                                                                ),
                                                                get_all_files_recursively_in_dir_watchdog(
                                                                    new_folder_path_two
                                                                ),
                                                            )
                                                        )
                                                except Exception as e:
                                                    send_message(
                                                        "Error renaming folder: "
                                                        + str(e),
                                                        error=True,
                                                    )
                                            else:
                                                send_message(
                                                    "\t\tSkipping...\n", discord=False
                                                )
                                                continue
                                        except OSError as e:
                                            send_message(str(e), error=True)
                                    elif (
                                        os.path.isdir(
                                            os.path.join(
                                                folder_accessor.root, dir_clean
                                            )
                                        )
                                        and dir_clean != ""
                                    ):
                                        if os.path.join(
                                            folder_accessor.root, folderDir
                                        ) != os.path.join(
                                            folder_accessor.root, dir_clean
                                        ):
                                            for root, dirs, files in scandir.walk(
                                                os.path.join(
                                                    folder_accessor.root, folderDir
                                                ),
                                            ):
                                                files = remove_hidden_files(files)
                                                file_objects = upgrade_to_file_class(
                                                    files, root
                                                )
                                                folder_accessor2 = Folder(
                                                    root,
                                                    dirs,
                                                    os.path.basename(
                                                        os.path.dirname(root)
                                                    ),
                                                    os.path.basename(root),
                                                    file_objects,
                                                )
                                                for file in folder_accessor2.files:
                                                    new_location_folder = os.path.join(
                                                        download_folder, dir_clean
                                                    )
                                                    if not os.path.isfile(
                                                        os.path.join(
                                                            new_location_folder,
                                                            file.name,
                                                        )
                                                    ):
                                                        move_file(
                                                            file,
                                                            os.path.join(
                                                                download_folder,
                                                                dir_clean,
                                                            ),
                                                            group=group,
                                                        )
                                                    else:
                                                        send_message(
                                                            "File: "
                                                            + file.name
                                                            + " already exists in: "
                                                            + os.path.join(
                                                                download_folder,
                                                                dir_clean,
                                                            )
                                                            + "\nRemoving duplicate from downloads.",
                                                            error=True,
                                                        )
                                                        remove_file(
                                                            os.path.join(
                                                                folder_accessor2.root,
                                                                file.name,
                                                            )
                                                        )
                                                check_and_delete_empty_folder(
                                                    folder_accessor2.root
                                                )
                                    break
            except Exception as e:
                send_message(str(e), error=True)
        else:
            if download_folder == "":
                send_message("\nERROR: Path cannot be empty.", error=True)
            else:
                send_message(
                    "\nERROR: " + download_folder + " is an invalid path.\n", error=True
                )
    if group and grouped_notifications and not group_discord_notifications_until_max:
        send_discord_message(None, grouped_notifications)


# Retrieves any bracketed information in the name that isn't the release year.
def get_extras(file_name, chapter=False, series_name="", subtitle=""):
    extension = get_file_extension(file_name)
    if series_name and re.search(re.escape(series_name), file_name, re.IGNORECASE):
        file_name = re.sub(
            re.escape(series_name), "", file_name, flags=re.IGNORECASE
        ).strip()
    if subtitle and re.search(re.escape(subtitle), file_name, re.IGNORECASE):
        file_name = re.sub(
            re.escape(subtitle), "", file_name, flags=re.IGNORECASE
        ).strip()
    results = re.findall(r"(\{|\(|\[)(.*?)(\]|\)|\})", file_name, flags=re.IGNORECASE)
    modified = []

    for result in results:
        combined = ""
        for r in result:
            combined += r
        if combined not in modified:
            modified.append(combined)
    patterns = [
        r"(\{|\(|\[)(Premium|J-Novel Club Premium)(\]|\)|\})",
        r"\((\d{4})\)",
        r"(\{|\(|\[)(Omnibus|Omnibus Edition)(\]|\)|\})",
        r"(Extra)(\]|\)|\})",
        r"(\{|\(|\[)Part([-_. ]|)([0-9]+)(\]|\)|\})",
    ]
    exclude_patterns = [patterns[4]]
    for item in modified[:]:
        for pattern in patterns:
            if pattern in exclude_patterns:
                if not chapter and re.search(pattern, item, re.IGNORECASE):
                    modified.remove(item)
                    break
            elif re.search(pattern, item, re.IGNORECASE):
                modified.remove(item)
                break
    modifiers = {
        ext: "[%s]"
        if ext in novel_extensions
        else "(%s)"
        if ext in manga_extensions
        else ""
        for ext in file_extensions
    }
    keywords = [
        "Premium",
        "Complete",
        "Fanbook",
        "Short Stories",
        "Short Story",
        "Omnibus",
    ]
    for keyword in keywords:
        if re.search(rf"\b{keyword}\b", file_name, re.IGNORECASE):
            modified_keyword = modifiers[extension] % keyword.strip()
            if modified_keyword not in modified:
                modified.append(modified_keyword)
    keywords_two = ["Extra", "Arc"]
    for keyword_two in keywords_two:
        match = re.search(
            rf"(([A-Za-z]|[0-9]+)|)+ {keyword_two}([-_ ]|)([0-9]+|([A-Za-z]|[0-9]+)+|)",
            file_name,
            re.IGNORECASE,
        )
        if match:
            result = match.group()
            if result not in {"Episode ", "Arc", "arc", "ARC"}:
                modified_result = modifiers[extension] % result.strip()
                if modified_result not in modified:
                    modified.append(modified_result)
    part_search = re.search(r"(\s|\b)Part([-_. ]|)([0-9]+)", file_name, re.IGNORECASE)
    if part_search:
        result = part_search.group()
        modified_result = modifiers[extension] % result.strip()
        if modified_result not in modified:
            modified.append(modified_result)
    # Move Premium to the beginning of the list
    premium_items = [item for item in modified if "Premium" in item]
    non_premium_items = [item for item in modified if "Premium" not in item]
    return premium_items + non_premium_items


def isfloat(x):
    try:
        a = float(x)
    except (TypeError, ValueError):
        return False
    else:
        return True


def isint(x):
    try:
        a = float(x)
        b = int(a)
    except (TypeError, ValueError):
        return False
    else:
        return a == b


# check if zip file contains ComicInfo.xml
def check_if_zip_file_contains_comic_info_xml(zip_file):
    result = False
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            list = zip_ref.namelist()
            for name in list:
                if name.lower() == "ComicInfo.xml".lower():
                    result = True
                    break
    except (zipfile.BadZipFile, FileNotFoundError) as e:
        send_message("\tFile: " + zip_file + "\n\t\tERROR: " + str(e), error=True)
    return result


# Retrieve the file specified from the zip file and return the data for it.
def get_file_from_zip(zip_file, file_name, allow_base=True, re_search=False):
    result = None
    try:
        with zipfile.ZipFile(zip_file, "r") as z:
            # Iterate through all the files in the zip
            for info in z.infolist():
                if allow_base:
                    if not re_search:
                        # Check the base name of the file
                        if os.path.basename(info.filename).lower() == file_name.lower():
                            # Read the contents of the file
                            result = z.read(info)
                            break
                    else:
                        if re.search(
                            rf"{file_name}",
                            os.path.basename(info.filename).lower(),
                            re.IGNORECASE,
                        ):
                            # Read the contents of the file
                            result = z.read(info)
                            break

                else:
                    # Check the entire path of the file
                    if not re_search:
                        if info.filename.lower() == file_name.lower():
                            # Read the contents of the file
                            result = z.read(info)
                            break
                    else:
                        if re.search(
                            rf"{file_name}", info.filename.lower(), re.IGNORECASE
                        ):
                            # Read the contents of the file
                            result = z.read(info)
                            break
    except (zipfile.BadZipFile, FileNotFoundError) as e:
        send_message(
            "Attempted to read file: " + file_name + "\nERROR: " + str(e), error=True
        )
    return result


# dynamically parse all tags from comicinfo.xml and return a dictionary of the tags
def parse_comicinfo_xml(xml_file):
    tags = {}
    if xml_file:
        try:
            tree = ET.fromstring(xml_file)
            for child in tree:
                tags[child.tag] = child.text
        except Exception as e:
            send_message(
                "Attempted to parse comicinfo.xml: "
                + str(xml_file)
                + "\nERROR: "
                + str(e),
                error=True,
            )
            return tags
    return tags


# dynamically parse all html tags and values and return a dictionary of them
def parse_html_tags(html):
    soup = BeautifulSoup(html, "html.parser")
    tags = {}
    for tag in soup.find_all(True):
        tags[tag.name] = tag.get_text()
    return tags


# Renames files.
def rename_files_in_download_folders(
    only_these_files=[], group=False, download_folders=download_folders, test_mode=False
):
    global transferred_files
    print("\nSearching for files to rename...")
    for path in download_folders:
        if os.path.exists(path):
            for root, dirs, files in scandir.walk(path):
                if test_mode:
                    dirs = []
                    files = only_these_files
                clean = None
                if (
                    watchdog_toggle
                    and download_folders
                    and any(x for x in download_folders if root.startswith(x))
                ):
                    clean = clean_and_sort(
                        root,
                        files,
                        dirs,
                        just_these_files=transferred_files,
                        just_these_dirs=transferred_dirs,
                        test_mode=test_mode,
                    )
                else:
                    clean = clean_and_sort(root, files, dirs, test_mode=test_mode)
                files, dirs = clean[0], clean[1]
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
                print("\t" + root)
                for file in volumes:
                    if test_mode:
                        print(
                            "\t\t["
                            + str(volumes.index(file) + 1)
                            + "/"
                            + str(len(volumes))
                            + "] "
                            + file.name
                        )
                    if (
                        file.file_type == "chapter"
                        and not rename_chapters_with_preferred_chapter_keyword
                    ):
                        continue
                    no_keyword = False
                    preferred_naming_format = preferred_volume_renaming_format
                    keywords = volume_regex_keywords
                    if file.file_type == "chapter":
                        keywords = chapter_regex_keywords
                        preferred_naming_format = preferred_chapter_renaming_format
                    if only_these_files and file.name not in only_these_files:
                        continue
                    try:
                        # Append 巻 to each extension and join them with |
                        file_extensions_with_prefix = "".join(
                            [f"巻?{re.escape(x)}|" for x in file_extensions]
                        )[:-1]
                        result = re.search(
                            r"(\s+)?\-?(\s+)?(%s)(\.\s?|\s?|)([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?(\]|\)|\})?(\s|%s)"
                            % (keywords, file_extensions_with_prefix),
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
                                only_has_one_set_of_numbers(
                                    remove_bracketed_info_from_name(
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
                                )
                                or (
                                    file.volume_number
                                    and (
                                        extract_all_numbers_from_string(
                                            file.name
                                        ).count(
                                            set_num_as_float_or_int(file.volume_number)
                                        )
                                        == 1
                                    )
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
                                        re.sub(
                                            r"_extra",
                                            " ",
                                            file.name,
                                            flags=re.IGNORECASE,
                                        )
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
                                        converted_num = set_num_as_float_or_int(
                                            file.volume_number
                                        )
                                        if converted_num != "":
                                            if re.search(r"-", str(converted_num)):
                                                # split the string by the dash
                                                split = converted_num.split("-")
                                                new_split = []
                                                for s in split[:]:
                                                    new_split.append("(0+)?" + s)
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
                                                result = re.sub("_", ".", result)
                                        if result:
                                            # check that the string is a float or int
                                            split = None
                                            if re.search(r"-", result):
                                                split = result.split("-")
                                                count = 0
                                                for s in split:
                                                    if set_num_as_float_or_int(s) != "":
                                                        count += 1
                                                if count != len(split):
                                                    result = None
                                            elif set_num_as_float_or_int(result) == "":
                                                result = None
                                    break

                        if result or (
                            file.is_one_shot
                            and add_volume_one_number_to_one_shots == True
                        ):
                            if file.is_one_shot and file.file_type == "volume":
                                result = preferred_naming_format + "01"
                            elif file.is_one_shot and file.file_type == "chapter":
                                result = preferred_naming_format + "001"
                            elif not isinstance(result, str):
                                result = result.group().strip()
                            # EX: "- c009" --> "c009"
                            if re.search(r"^-", result):
                                result = re.sub(r"^-", " ", result).strip()
                            result = re.sub(
                                r"([\[\(\{\]\)\}]|((?<!\d+)_(?!\d+)))", "", result
                            ).strip()
                            keyword = re.search(
                                r"(%s)" % keywords,
                                result,
                                re.IGNORECASE,
                            )
                            if keyword:
                                keyword = keyword.group(0)
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
                            for ext in file_extensions:
                                result = re.sub(ext, "", result).strip()
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
                                                if number == volume_numbers[-1]:
                                                    modified.append(number)
                                                else:
                                                    modified.append(number)
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
                                or (
                                    len(modified) == 1
                                    and len(results) == 1
                                    and no_keyword
                                )
                            ) or (
                                file.multi_volume
                                and (
                                    len(modified) == len(results) + len(volume_numbers)
                                )
                            ):
                                combined = ""
                                zfill_int = zfill_volume_int_value
                                zfill_float = zfill_volume_float_value
                                if file.file_type == "chapter":
                                    zfill_int = zfill_chapter_int_value
                                    zfill_float = zfill_chapter_float_value
                                for item in modified:
                                    if type(item) == int:
                                        if item < 10 or (
                                            file.file_type == "chapter" and item < 100
                                        ):
                                            item = str(item).zfill(zfill_int)
                                        combined += str(item)
                                    elif type(item) == float:
                                        if item < 10 or (
                                            file.file_type == "chapter" and item < 100
                                        ):
                                            item = str(item).zfill(zfill_float)
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
                                    combined += " " + "#" + without_keyword
                                if not file.is_one_shot:
                                    converted_value = re.sub(
                                        keywords, "", combined, flags=re.IGNORECASE
                                    )
                                    if not re.search(r"-", converted_value):
                                        converted_value = set_num_as_float_or_int(
                                            converted_value,
                                            silent=True,
                                        )
                                    else:
                                        converted_value = ""
                                    converted_and_filled = None
                                    if converted_value != "":
                                        if type(converted_value) == int:
                                            if converted_value < 10 or (
                                                file.file_type == "chapter"
                                                and converted_value < 100
                                            ):
                                                converted_and_filled = str(
                                                    converted_value
                                                ).zfill(zfill_int)
                                            elif converted_value >= 100:
                                                converted_and_filled = converted_value
                                        elif type(converted_value) == float:
                                            if converted_value < 10 or (
                                                file.file_type == "chapter"
                                                and converted_value < 100
                                            ):
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
                                            " "
                                            + preferred_naming_format
                                            + str(converted_and_filled),
                                            remove_dual_space(
                                                re.sub(
                                                    r"_extra",
                                                    ".5",
                                                    without_end_brackets,
                                                    flags=re.IGNORECASE,
                                                )
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
                                        replacement = remove_dual_space(
                                            replacement
                                        ).strip()
                                    else:
                                        replacement = re.sub(
                                            r"((?<![A-Za-z]+)|)(\[|\(|\{)?(?<![A-Za-z])(%s)(\.|)([-_. ]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s#(([0-9]+)((([-_.]|)([0-9]+))+|)))?(\]|\)|\})?"
                                            % "",
                                            " " + preferred_naming_format + combined,
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
                                    replacement = base + " " + combined
                                    if file.volume_year:
                                        replacement += (
                                            " (" + str(file.volume_year) + ")"
                                        )
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
                                    for extra in extras:
                                        replacement += " " + extra
                                    replacement += file.extension
                                replacement = re.sub(r"([?])", "", replacement).strip()
                                replacement = remove_dual_space(
                                    re.sub(r"_", " ", replacement)
                                ).strip()
                                # replace : with - in dir_clean
                                replacement = re.sub(
                                    r"([A-Za-z])(\:)", r"\1 -", replacement
                                )
                                # remove dual spaces from dir_clean
                                replacement = remove_dual_space(replacement)
                                processed_files.append(replacement)
                                if file.name != replacement:
                                    if test_mode:
                                        write_to_file(
                                            "test_renamed_files.txt",
                                            file.name + " -> " + replacement,
                                            without_timestamp=True,
                                            check_for_dup=True,
                                        )
                                        continue

                                    if watchdog_toggle:
                                        transferred_files.append(
                                            os.path.join(file.root, replacement)
                                        )
                                    try:
                                        if not (
                                            os.path.isfile(
                                                os.path.join(root, replacement)
                                            )
                                        ):
                                            user_input = ""
                                            send_message(
                                                "\n\t\tBEFORE: " + file.name,
                                                discord=False,
                                            )
                                            send_message(
                                                "\t\tAFTER:  " + replacement,
                                                discord=False,
                                            )
                                            if not manual_rename:
                                                user_input = "y"
                                            else:
                                                user_input = get_input_from_user(
                                                    "\t\tRename",
                                                    ["y", "n"],
                                                    ["y", "n"],
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
                                                        transferred_files.remove(
                                                            file.path
                                                        )
                                                except OSError as e:
                                                    send_message(
                                                        str(e),
                                                        "Error renaming file: "
                                                        + file.name
                                                        + " to "
                                                        + replacement,
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
                                                        embed = [
                                                            handle_fields(
                                                                DiscordEmbed(
                                                                    title="Renamed File",
                                                                    color=grey_color,
                                                                ),
                                                                fields=[
                                                                    {
                                                                        "name": "From:",
                                                                        "value": "```"
                                                                        + file.name
                                                                        + "```",
                                                                        "inline": False,
                                                                    },
                                                                    {
                                                                        "name": "To:",
                                                                        "value": "```"
                                                                        + replacement
                                                                        + "```",
                                                                        "inline": False,
                                                                    },
                                                                ],
                                                            )
                                                        ]
                                                        add_to_grouped_notifications(
                                                            Embed(embed[0], None)
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
                                                        "\n\tRename failed on: "
                                                        + file.name,
                                                        error=True,
                                                    )
                                            else:
                                                send_message(
                                                    "\t\t\tSkipping...\n", discord=False
                                                )
                                        else:
                                            # if it already exists, then delete file.name
                                            send_message(
                                                "\n\tFile already exists: "
                                                + os.path.join(root, replacement)
                                                + "\n\t\twhen renaming: "
                                                + file.name
                                                + "\n\tDeleting: "
                                                + file.name,
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
                                            file.name + " -> " + replacement,
                                            without_timestamp=True,
                                            check_for_dup=True,
                                        )
                                        continue
                            else:
                                send_message(
                                    "More than two for either array: " + file.name,
                                    error=True,
                                )
                                print("Modified Array:")
                                for i in modified:
                                    print("\t" + str(i))
                                print("Results Array:")
                                for b in results:
                                    print("\t" + str(b))
                    except Exception as e:
                        send_message(
                            "\nERROR: " + str(e) + " (" + file.name + ")", error=True
                        )
                    if resturcture_when_renaming and not test_mode:
                        reorganize_and_rename([file], file.series_name, group=group)
        else:
            if path == "":
                print("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + path + " is an invalid path.\n")
    if group and grouped_notifications and not group_discord_notifications_until_max:
        send_discord_message(None, grouped_notifications)


# Checks for any exception keywords that will prevent the chapter release from being deleted.
def check_for_exception_keywords(file_name, exception_keywords):
    pattern = "|".join(exception_keywords)
    return bool(re.search(pattern, file_name, re.IGNORECASE))


# Deletes chapter files from the download folder.
def delete_chapters_from_downloads(group=False):
    try:
        for path in download_folders:
            if os.path.exists(path):
                os.chdir(path)
                for root, dirs, files in scandir.walk(path):
                    clean = None
                    if (
                        watchdog_toggle
                        and download_folders
                        and any(x for x in download_folders if root.startswith(x))
                    ):
                        clean = clean_and_sort(
                            root,
                            files,
                            dirs,
                            chapters=True,
                            just_these_files=transferred_files,
                            just_these_dirs=transferred_dirs,
                        )
                    else:
                        clean = clean_and_sort(root, files, dirs, chapters=True)
                    files, dirs = clean[0], clean[1]
                    for file in files:
                        if (
                            contains_chapter_keywords(file)
                            and not contains_volume_keywords(file)
                        ) and not (
                            check_for_exception_keywords(file, exception_keywords)
                        ):
                            if get_file_extension(file) in manga_extensions:
                                send_message(
                                    "\n\t\tFile: "
                                    + file
                                    + "\n\t\tLocation: "
                                    + root
                                    + "\n\t\tContains chapter keywords/lone numbers and does not contain any volume/exclusion keywords"
                                    + "\n\t\tDeleting chapter release.",
                                    discord=False,
                                )
                                embed = [
                                    handle_fields(
                                        DiscordEmbed(
                                            title="Chapter Release Found",
                                            color=grey_color,
                                        ),
                                        fields=[
                                            {
                                                "name": "File:",
                                                "value": "```" + file + "```",
                                                "inline": False,
                                            },
                                            {
                                                "name": "Location:",
                                                "value": "```" + root + "```",
                                                "inline": False,
                                            },
                                            {
                                                "name": "Checks:",
                                                "value": "```"
                                                + "Contains chapter keywords/lone numbers ✓\n"
                                                + "Does not contain any volume keywords ✓\n"
                                                + "Does not contain any exclusion keywords ✓"
                                                + "```",
                                                "inline": False,
                                            },
                                        ],
                                    )
                                ]
                                add_to_grouped_notifications(Embed(embed[0], None))
                                remove_file(os.path.join(root, file), group=group)
                for root, dirs, files in scandir.walk(path):
                    clean_two = None
                    if (
                        watchdog_toggle
                        and download_folders
                        and any(x for x in download_folders if root.startswith(x))
                    ):
                        clean_two = clean_and_sort(
                            root,
                            files,
                            dirs,
                            just_these_files=transferred_files,
                            just_these_dirs=transferred_dirs,
                        )
                    else:
                        clean_two = clean_and_sort(root, files, dirs)
                    files, dirs = clean_two[0], clean_two[1]
                    for dir in dirs:
                        check_and_delete_empty_folder(os.path.join(root, dir))
            else:
                if path == "":
                    print("\nERROR: Path cannot be empty.")
                else:
                    print("\nERROR: " + path + " is an invalid path.\n")
        if (
            group
            and grouped_notifications
            and not group_discord_notifications_until_max
        ):
            send_discord_message(None, grouped_notifications)
    except Exception as e:
        send_message(str(e), error=True)


# remove all non-images from list of files
def remove_non_images(files):
    clean_list = []
    for file in files:
        extension = get_file_extension(os.path.basename(file))
        if extension in image_extensions:
            clean_list.append(file)
    return clean_list


def get_novel_cover_path(file):
    novel_cover_path = ""
    if file.extension in novel_extensions:
        novel_cover_path = get_novel_cover(file.path)
        if novel_cover_path:
            novel_cover_path = os.path.basename(novel_cover_path)
            novel_cover_extension = get_file_extension(novel_cover_path)
            if novel_cover_extension not in image_extensions:
                novel_cover_path = ""
    return novel_cover_path


# Finds and extracts the internal cover from a manga or novel file.
def find_and_extract_cover(file, return_data_only=False, silent=False):
    # Helper function to filter and sort files in the zip archive
    def filter_and_sort_files(zip_list):
        return sorted(
            [
                x
                for x in zip_list
                if not x.endswith("/")
                and re.search(r"\.", x)
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
        output_path = os.path.join(file.root, file.extensionless_name + image_extension)

        if not return_data_only:
            save_image_data(output_path, image_data)
            if compress_image_option:
                result = compress_image(output_path)
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

        # Regular expressions to match cover patterns
        cover_patterns = [
            r"(cover\.([A-Za-z]+))$",
            r"(\b(Cover([0-9]+|)|CoverDesign|page([-_. ]+)?cover)\b)",
            r"(\b(p000|page_000)\b)",
            r"((\s+)0+\.(.{2,}))",
            r"(\bindex[-_. ]1[-_. ]1\b)",
            r"(9([-_. :]+)?7([-_. :]+)?(8|9)(([-_. :]+)?[0-9]){10})",
        ]

        # Set of blank images
        blank_images = set()

        # Iterate through the files in the zip archive
        for image_file in zip_list:
            # Check if the file matches any cover pattern
            for pattern in cover_patterns:
                image_basename = os.path.basename(image_file)
                is_novel_cover = novel_cover_path and image_basename == novel_cover_path
                if (
                    is_novel_cover
                    or pattern == image_basename
                    or re.search(pattern, image_basename, re.IGNORECASE)
                ):
                    # Check if the image is blank
                    if (
                        compare_detected_cover_to_blank_images
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
            if compare_detected_cover_to_blank_images:
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
def get_highest_release(releases, is_chapter_directory=False):
    highest_volume_number = None
    highest_volume_part_number = ""

    if use_latest_volume_cover_as_series_cover and not is_chapter_directory:
        for item in releases:
            if not item.file_type == "volume":
                continue

            if not item.volume_number:
                continue

            part = None

            if hasattr(item, "volume_part"):
                part = item.volume_part
            else:
                part = get_file_part(item.name)

            number = item.volume_number
            if isinstance(number, (int, float)):
                if highest_volume_number is None or number > highest_volume_number:
                    highest_volume_number = number
                    highest_volume_part_number = part
                elif (
                    number == highest_volume_number
                    and part > highest_volume_part_number
                ):
                    highest_volume_part_number = part
            elif isinstance(number, list):
                if highest_volume_number is None or max(number) > highest_volume_number:
                    highest_volume_number = max(number)
                    highest_volume_part_number = part
                elif (
                    max(number) == highest_volume_number
                    and part > highest_volume_part_number
                ):
                    highest_volume_part_number = part

    return highest_volume_number, highest_volume_part_number


# Series covers that have been checked and can be skipped.
checked_series = []


# takes a time.time, gets the current time and prints the execution time,
def print_execution_time(start_time, function_name):
    print(
        "\nExecution time for: "
        + function_name
        + ": "
        + str(time.time() - start_time)
        + " seconds"
    )


# Extracts the covers out from our manga and novel files.
def extract_covers(paths_to_process=paths):
    global checked_series
    print("\nLooking for covers to extract...")

    # Only volume defined paths in the paths_with_types list
    # Used for copying existing volume covers from a
    # volume library to a chapter library
    volume_paths = []

    # Iterate over each path
    for path in paths_to_process:
        # Check if the path exists
        if not os.path.exists(path):
            # Print an error message for an invalid or empty path
            print("\nERROR: " + path + " is an invalid path.\n")
            continue  # Move to the next iteration

        checked_series = []
        os.chdir(path)

        # Traverse the directory tree rooted at the path
        for root, dirs, files in scandir.walk(path):
            clean = None

            # Clean and sort the files and directories
            if (
                watchdog_toggle
                and download_folders
                and any(x for x in download_folders if root.startswith(x))
            ):
                clean = clean_and_sort(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )
            else:
                clean = clean_and_sort(root, files, dirs)
            global folder_accessor

            files, dirs = clean[0], clean[1]
            print("\nRoot: " + root)
            print("Files: " + str(files))

            if files:
                # Upgrade file objects to a file class
                file_objects = upgrade_to_file_class(files, root, clean=False)

                # Create a folder accessor object
                folder_accessor = Folder(
                    root,
                    dirs,
                    os.path.basename(os.path.dirname(root)),
                    os.path.basename(root),
                    upgrade_to_volume_class(
                        file_objects,
                        skip_release_year=True,
                        skip_fixed_volume=True,
                        skip_release_group=True,
                        skip_extras=True,
                        skip_publisher=True,
                        skip_premium_content=True,
                        skip_subtitle=True,
                        skip_multi_volume=True,
                    ),
                )

                # Get the series cover
                series_cover_path = next(
                    (
                        os.path.join(folder_accessor.root, f"cover{ext}")
                        for ext in image_extensions
                        if os.path.exists(
                            os.path.join(folder_accessor.root, f"cover{ext}")
                        )
                    ),
                    None,
                )

                # Set the directory type
                is_chapter_directory = (
                    True if folder_accessor.files[0].file_type == "chapter" else False
                )

                # Used when filtering the series_folders of each paths_with_types
                # by the first letter of a cleaned up name
                clean_basename = None

                if copy_existing_volume_covers_toggle and is_chapter_directory:
                    # Set the value of volume_paths
                    if not volume_paths and paths_with_types:
                        volume_paths = [
                            x
                            for x in paths_with_types
                            if "volume" in x.path_formats
                            and folder_accessor.files[0].extension in x.path_extensions
                        ]
                        if volume_paths:
                            for v_path in volume_paths:
                                # Get all the folders in v_path.path
                                volume_series_folders = [
                                    x
                                    for x in os.listdir(v_path.path)
                                    if not x.startswith(".")
                                ]
                                v_path.series_folders = volume_series_folders

                    clean_basename = (
                        replace_underscore_in_name(
                            remove_punctuation(
                                remove_bracketed_info_from_name(
                                    os.path.basename(folder_accessor.root)
                                )
                            )
                        )
                        .lower()
                        .strip()
                    )

                # Get the highest volume number and part number
                highest_volume_number, highest_volume_part_number = (
                    get_highest_release(folder_accessor.files, is_chapter_directory)
                    if not is_chapter_directory
                    else (None, "")
                )

                if highest_volume_number:
                    print(f"\n\t\tHighest Volume Number: {highest_volume_number}")

                if highest_volume_part_number:
                    print(
                        f"\t\tHighest Volume Part Number: {highest_volume_part_number}"
                    )

                # Check if it contains multiple volume ones
                contains_multiple_volume_ones = False
                if not use_latest_volume_cover_as_series_cover or is_chapter_directory:
                    volume_ones_counter = 0

                    for file in folder_accessor.files:
                        if not file.is_one_shot and not file.volume_part:
                            if file.volume_number == 1:
                                volume_ones_counter += 1
                                if volume_ones_counter > 1:
                                    contains_multiple_volume_ones = True
                                    break
                            elif (
                                isinstance(file.volume_number, list)
                                and 1 in file.volume_number
                            ):
                                volume_ones_counter += 1
                                if volume_ones_counter > 1:
                                    contains_multiple_volume_ones = True
                                    break

                # Process cover extraction for each file
                [
                    process_cover_extraction(
                        file,
                        contains_multiple_volume_ones,
                        highest_volume_number,
                        highest_volume_part_number,
                        is_chapter_directory,
                        series_cover_path,
                        volume_paths,
                        clean_basename,
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
        try:
            with Image.open(webp_file_path) as im:
                im.convert("RGB").save(extenionless_webp_file + ".jpg")
            # verify that the conversion worked
            if os.path.isfile(extenionless_webp_file + ".jpg"):
                # delete the .webp file
                remove_file(webp_file_path, silent=True)
                # verify that the .webp file was deleted
                if not os.path.isfile(webp_file_path):
                    return extenionless_webp_file + ".jpg"
                else:
                    send_message(
                        "ERROR: Could not delete " + webp_file_path, error=True
                    )
            else:
                send_message(
                    "ERROR: Could not convert " + webp_file_path + " to jpg", error=True
                )
        except Exception as e:
            send_message(
                "Could not convert "
                + webp_file_path
                + " to jpg"
                + "\nERROR: "
                + str(e),
                error=True,
            )
    return None


# Retrieves the modification date of the passed file path.
def get_modification_date(file_path):
    return os.path.getmtime(file_path)


def process_cover_extraction(
    file,
    contains_multiple_volume_ones,
    highest_volume_number,
    highest_volume_part_number,
    is_chapter_directory,
    series_cover_path,
    volume_paths,
    clean_basename,
):
    global image_count
    update_stats(file)

    try:
        has_cover = False
        printed = False

        # Check if a cover image is already present
        cover = next(
            (
                file.extensionless_path + extension
                for extension in image_extensions
                if os.path.exists(file.extensionless_path + extension)
            ),
            "",
        )

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

            if result and result.endswith(".webp"):
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

            # Cover image successfully extracted
            if result:
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
            and not contains_multiple_volume_ones
            and file.volume_part == highest_volume_part_number
            and (
                (
                    use_latest_volume_cover_as_series_cover
                    and highest_volume_number
                    and (
                        file.volume_number == highest_volume_number
                        or (
                            isinstance(file.volume_number, list)
                            and highest_volume_number in file.volume_number
                        )
                    )
                )
                or (
                    not use_latest_volume_cover_as_series_cover
                    and (
                        file.volume_number == 1
                        or (
                            isinstance(file.volume_number, list)
                            and 1 in file.volume_number
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
            volume_paths
            and is_chapter_directory
            and file.root not in checked_series
            and clean_basename
        ):
            for v_path in volume_paths:
                if not (hasattr(v_path, "series_folders") and v_path.series_folders):
                    continue

                filtered_series = v_path.series_folders

                # Get the first letter of file.basename
                # and remove any that don't start with it
                first_letter = re.search(r"^[A-Za-z]+", file.basename)
                if first_letter:
                    first_letter = first_letter.group(0)
                    # Filter filtered_series to only include folders that start with first_set_of_letters
                    filtered_series = [
                        x
                        for x in filtered_series
                        if re.search(r"^" + first_letter, x, re.IGNORECASE)
                    ]

                for folder in filtered_series:
                    folder_path = os.path.join(v_path.path, folder)
                    clean_folder = (
                        replace_underscore_in_name(
                            remove_punctuation(remove_bracketed_info_from_name(folder))
                        )
                        .lower()
                        .strip()
                    )
                    if clean_folder == clean_basename or (
                        similar(clean_folder, clean_basename)
                        >= required_similarity_score
                    ):
                        volumes = upgrade_to_file_class(
                            [
                                f
                                for f in os.listdir(folder_path)
                                if os.path.isfile(os.path.join(folder_path, f))
                            ],
                            folder_path,
                        )
                        if volumes:
                            volume_one = [
                                x
                                for x in volumes
                                if x.volume_number == 1
                                or (
                                    isinstance(file.volume_number, list)
                                    and 1 in file.volume_number
                                )
                            ]
                            if volume_one and len(volume_one) == 1:
                                volume_one = volume_one[0]
                                # find the image cover
                                cover_path = None
                                for extension in image_extensions:
                                    if os.path.isfile(
                                        volume_one.extensionless_path + extension
                                    ):
                                        cover_path = (
                                            volume_one.extensionless_path + extension
                                        )
                                        break
                                volume_one_modification_date = get_modification_date(
                                    cover_path
                                )
                                if series_cover_path:
                                    cover_modification_date = (
                                        get_modification_date(series_cover_path)
                                        if series_cover_path
                                        else None
                                    )
                                    if (
                                        cover_modification_date
                                        and volume_one_modification_date
                                    ) and (
                                        cover_modification_date
                                        != volume_one_modification_date
                                    ):
                                        cover_hash = (
                                            get_file_hash(series_cover_path)
                                            if series_cover_path
                                            else None
                                        )
                                        volume_one_hash = (
                                            get_file_hash(cover_path)
                                            if series_cover_path
                                            else None
                                        )
                                        if (cover_hash and volume_one_hash) and (
                                            cover_hash != volume_one_hash
                                        ):
                                            print(
                                                "\t\tCurrent series cover does not match the appropriate volume cover."
                                            )
                                            print(
                                                "\t\tRemoving current series cover..."
                                            )
                                            remove_file(series_cover_path, silent=True)
                                            if not os.path.isfile(series_cover_path):
                                                print(
                                                    "\t\tSeries cover successfully removed.\n"
                                                )
                                                series_cover_path = None
                                            else:
                                                print(
                                                    "\t\tSeries cover could not be removed.\n"
                                                )
                                            print("\t\tFound volume for series cover.")
                                        else:
                                            # set the modification date
                                            set_modification_date(
                                                series_cover_path,
                                                volume_one_modification_date,
                                            )
                                if not series_cover_path and cover_path:
                                    # copy the file to the series cover folder
                                    series_cover_path = os.path.join(
                                        file.root, "cover" + extension
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
            not contains_multiple_volume_ones
            and not series_cover_path
            and file.root not in download_folders
            and has_cover
            and cover
            and (
                (
                    file.volume_number == 1
                    and (
                        not use_latest_volume_cover_as_series_cover
                        or is_chapter_directory
                    )
                )
                or (
                    file.file_type == "volume"
                    and not is_chapter_directory
                    and use_latest_volume_cover_as_series_cover
                    and highest_volume_number
                    and (
                        file.volume_number == highest_volume_number
                        or (
                            isinstance(file.volume_number, list)
                            and highest_volume_number in file.volume_number
                        )
                    )
                    and file.volume_part == highest_volume_part_number
                )
            )
        ):
            if not printed:
                print("\tFile: " + file.name)
                printed = True
            print("\t\tMissing series cover.")
            print("\t\tFound volume for series cover.")

            cover_extension = get_file_extension(os.path.basename(cover))
            cover_path = os.path.join(file.root, os.path.basename(cover))
            series_cover_path = os.path.join(file.root, "cover" + cover_extension)

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
                print("\t\tCover does not exist at: " + str(cover_path))
    except Exception as e:
        send_message(
            "\nERROR in extract_covers(): " + str(e) + " with file: " + file.name,
            error=True,
        )


def print_stats():
    print("\nFor all paths.")
    if file_counters:
        # get the total count from file_counters
        total_count = sum(
            [file_counters[extension] for extension in file_counters.keys()]
        )
        print("Total Files Found: " + str(total_count))
        for extension in file_counters.keys():
            count = file_counters[extension]
            if count > 0:
                print("\t" + str(count) + " were " + extension + " files")
    print("\tof those we found that " + str(image_count) + " had a cover image file.")
    if len(errors) != 0:
        print("\nErrors (" + str(len(errors)) + "):")
        for error in errors:
            print("\t" + str(error))


# Deletes any file with an extension in unacceptable_keywords from the download_folders
def delete_unacceptable_files(group=False):
    if unacceptable_keywords:
        print("\nSearching for unacceptable files...")
        try:
            for path in download_folders:
                if os.path.exists(path):
                    os.chdir(path)
                    for root, dirs, files in scandir.walk(path):
                        clean = None
                        if (
                            watchdog_toggle
                            and download_folders
                            and any(x for x in download_folders if root.startswith(x))
                        ):
                            clean = clean_and_sort(
                                root,
                                files,
                                dirs,
                                just_these_files=transferred_files,
                                just_these_dirs=transferred_dirs,
                                skip_remove_unaccepted_file_types=True,
                                keep_images_in_just_these_files=True,
                            )
                        else:
                            clean = clean_and_sort(
                                root,
                                files,
                                dirs,
                                skip_remove_unaccepted_file_types=True,
                            )
                        files, dirs = clean[0], clean[1]
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.isfile(file_path):
                                extension = get_file_extension(file)
                                for keyword in unacceptable_keywords:
                                    unacceptable_keyword_search = re.search(
                                        keyword, file, re.IGNORECASE
                                    )
                                    if unacceptable_keyword_search:
                                        send_message(
                                            "\tUnacceptable: "
                                            + unacceptable_keyword_search.group()
                                            + " match found in "
                                            + file
                                            + "\n\t\tDeleting file from: "
                                            + root,
                                            discord=False,
                                        )
                                        embed = [
                                            handle_fields(
                                                DiscordEmbed(
                                                    title="Unacceptable Match Found",
                                                    color=yellow_color,
                                                ),
                                                fields=[
                                                    {
                                                        "name": "Found Regex/Keyword Match:",
                                                        "value": "```"
                                                        + unacceptable_keyword_search.group()
                                                        + "```",
                                                        "inline": False,
                                                    },
                                                    {
                                                        "name": "In:",
                                                        "value": "```" + file + "```",
                                                        "inline": False,
                                                    },
                                                    {
                                                        "name": "Location:",
                                                        "value": "```" + root + "```",
                                                        "inline": False,
                                                    },
                                                ],
                                            )
                                        ]
                                        add_to_grouped_notifications(
                                            Embed(embed[0], None)
                                        )
                                        remove_file(file_path, group=group)
                                        break
                    for root, dirs, files in scandir.walk(path):
                        clean_two = None
                        if (
                            watchdog_toggle
                            and download_folders
                            and any(x for x in download_folders if root.startswith(x))
                        ):
                            clean_two = clean_and_sort(
                                root,
                                files,
                                dirs,
                                just_these_files=transferred_files,
                                just_these_dirs=transferred_dirs,
                            )
                        else:
                            clean_two = clean_and_sort(root, files, dirs)
                        files, dirs = clean_two[0], clean_two[1]
                        for dir in dirs:
                            check_and_delete_empty_folder(os.path.join(root, dir))
                else:
                    if path == "":
                        print("\nERROR: Path cannot be empty.")
                    else:
                        print("\nERROR: " + path + " is an invalid path.\n")
            if (
                group
                and grouped_notifications
                and not group_discord_notifications_until_max
            ):
                send_discord_message(None, grouped_notifications)
        except Exception as e:
            send_message(str(e), error=True)


class BookwalkerBook:
    def __init__(
        self,
        title,
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
        send_message("Error scraping URL: " + str(e), error=True)
        return None


def get_all_matching_books(books, book_type, title):
    matching_books = []
    short_title = get_shortened_title(title)
    for book in books:
        short_title_two = get_shortened_title(book.title)
        if book.book_type == book_type and (
            book.title == title
            or (
                (
                    similar(remove_punctuation(book.title), remove_punctuation(title))
                    >= required_similarity_score
                )
                or (
                    (short_title and short_title_two)
                    and similar(
                        remove_punctuation(short_title_two),
                        remove_punctuation(short_title),
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
        # sort by volume number
        # because volume number can either be a float or an array of floats
        # cast it to a string and split it by the comma, and then sort by the first element
        series.books.sort(
            key=lambda x: str(x.volume_number) + " " + str(x.part).strip().split(",")[0]
        )
        if len(combined_series) == 0:
            combined_series.append(series)
        else:
            for combined_series_item in combined_series:
                if series.book_type == combined_series_item.book_type and (
                    series.title.lower().strip()
                    == combined_series_item.title.lower().strip()
                    or similar(
                        remove_punctuation(series.title).lower().strip(),
                        remove_punctuation(combined_series_item.title).lower().strip(),
                    )
                    >= required_similarity_score
                ):
                    combined_series_item.books.extend(series.books)
                    combined_series_item.book_count = len(combined_series_item.books)
                    break
            if series not in combined_series and not (
                similar(
                    remove_punctuation(series.title).lower().strip(),
                    remove_punctuation(combined_series[0].title).lower().strip(),
                )
                >= required_similarity_score
            ):
                combined_series.append(series)
    return combined_series


# Gives the user a short version of the title, if a dash or colon is present.
# EX: Series Name - Subtitle --> Series Name
def get_shortened_title(title):
    shortened_title = ""
    if re.search(r"((\s+(-)|:)\s+)", title):
        shortened_title = re.sub(r"((\s+(-)|:)\s+.*)", "", title).strip()
    return shortened_title


# Extracts the subtitle from a file.name
# (year required in brackets at the end of the subtitle)
# EX: Sword Art Online v13 - Alicization Dividing [2018].epub --> Alicization Dividing
@lru_cache(maxsize=None)
def get_subtitle_from_title(file, publisher=None):
    subtitle = ""

    # remove the series name from the title
    without_series_name = re.sub(
        rf"^{re.escape(file.series_name)}", "", file.name, flags=re.IGNORECASE
    ).strip()

    # First Search
    dash_or_colon_search = re.search(r"((\s+(-)|:)\s+)", without_series_name)

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
        # EX: series_name c001 (2021) (Digital) - Instincts.cbz --> Instincts.cbz
        subtitle = re.sub(rf"\{file.extension}$", "", subtitle).strip()

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
            rf"^({volume_regex_keywords})(\s+)?(0+)?{set_num_as_float_or_int(file.volume_number)}$",
            subtitle.strip(),
            re.IGNORECASE,
        ):
            subtitle = ""

    return subtitle


def search_bookwalker(
    query, type, print_info=False, alternative_search=False, shortened_search=False
):
    global required_similarity_score
    # The total amount of pages to scrape
    total_pages_to_scrape = 5
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
    start_time = datetime.now()
    done = False
    search_type = type
    count = 0
    page_count = 1
    page_count_url = "&page=" + str(page_count)
    search = urllib.parse.quote(query)
    base_url = "https://global.bookwalker.jp/search/?word="
    series_only = "&np=0"
    series_url = base_url + search + series_only
    if not alternative_search:
        keyword = "\t\tSearch: "
        if shortened_search:
            keyword = "\t\tShortened Search: "
        if search_type.lower() == "m":
            print(keyword + query + "\n\t\tCategory: MANGA")
        elif search_type.lower() == "l":
            print(keyword + query + "\n\t\tCategory: NOVEL")
    chapter_exclusion_url = "&np=1&qnot%5B%5D=Chapter&x=13&y=16"
    series_list_li = None
    series_page = scrape_url(
        series_url,
        cookies={"glSafeSearch": "1", "safeSearch": "111"},
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
        },
    )
    if series_page:
        # find ul class o-tile-list in series_page
        series_list_ul = series_page.find_all("ul", class_="o-tile-list")
        if series_list_ul:
            # find all li class="o-tile"
            series_list_li = series_list_ul[0].find_all("li", class_="o-tile")
    if series_list_li:
        series_list_li = len(series_list_li)
    original_similarity_score = required_similarity_score
    if series_list_li == 1:
        required_similarity_score = original_similarity_score - 0.03
    while page_count < total_pages_to_scrape + 1:
        page_count_url = "&page=" + str(page_count)
        alternate_url = ""
        url = base_url + search + page_count_url
        if search_type.lower() == "m":
            if not alternative_search:
                url += bookwalker_manga_category
                series_url += bookwalker_manga_category
            else:
                url += bookwalker_intll_manga_category
                series_url += bookwalker_intll_manga_category
        elif search_type.lower() == "l":
            url += bookwalker_light_novel_category
            series_url += bookwalker_light_novel_category
        if shortened_search and series_list_li and series_list_li != 1:
            print("\t\t\tsearch does not contain exactly one series, skipping...\n")
            return []
        url += chapter_exclusion_url
        page_count += 1
        # scrape url page
        page = scrape_url(
            url,
            cookies={"glSafeSearch": "1", "safeSearch": "111"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
            },
        )
        if not page:
            alternate_page = None
            if search_type.lower() == "m" and not alternative_search:
                alternate_page = scrape_url(
                    url,
                    cookies={"glSafeSearch": "1", "safeSearch": "111"},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
                    },
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
            highest_num = 0
            for li in li_list:
                text = li.text
                # if text is a number
                if text.isdigit():
                    if int(text) > highest_num:
                        highest_num = int(text)
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
            "\t\t\tPage: "
            + str(page_count - 1)
            + " of "
            + str(total_pages_to_scrape)
            + "\n\t\t\t\tItems: "
            + str(len(o_tile_list))
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
                a_tag_chapter = None
                a_tag_simulpub = None
                a_tag_manga = None
                a_tag_light_novel = None
                a_tag_other = None
                for i in li_tag_item:
                    if i.find("div", class_="a-tag-manga"):
                        a_tag_manga = i.find("div", class_="a-tag-manga")
                    elif i.find("div", class_="a-tag-light-novel"):
                        a_tag_light_novel = i.find("div", class_="a-tag-light-novel")
                    elif i.find("div", class_="a-tag-other"):
                        a_tag_other = i.find("div", class_="a-tag-other")
                    elif i.find("div", class_="a-tag-chapter"):
                        a_tag_chapter = i.find("div", class_="a-tag-chapter")
                    elif i.find("div", class_="a-tag-simulpub"):
                        a_tag_simulpub = i.find("div", class_="a-tag-simulpub")
                if a_tag_manga:
                    book_type = a_tag_manga.get_text()
                elif a_tag_light_novel:
                    book_type = a_tag_light_novel.get_text()
                elif a_tag_other:
                    book_type = a_tag_other.get_text()
                else:
                    book_type = "Unknown"
                book_type = re.sub(r"\n|\t|\r", "", book_type).strip()
                title = o_tile_book_info.find("h2", class_="a-tile-ttl").text.strip()
                item_index = o_tile_list.index(item)
                if title:
                    print("\t\t\t\t\t[" + str(item_index + 1) + "] " + title)
                # remove brackets
                title = remove_bracketed_info_from_name(title)
                # unidecode the title
                title = unidecode(title)
                # replace any remaining unicode characters in the title with spaces
                title = re.sub(r"[^\x00-\x7F]+", " ", title)
                title = remove_dual_space(title).strip()
                if (
                    title
                    and re.search(r"Chapter", title, re.IGNORECASE)
                    and not re.search(r"re([-_. :]+)?zero", title, re.IGNORECASE)
                ):
                    continue
                part = ""
                part_search = get_file_part(title)
                if part_search:
                    part_search = set_num_as_float_or_int(part_search)
                    if part_search:
                        part = set_num_as_float_or_int(part_search)
                if a_tag_chapter or a_tag_simulpub:
                    chapter_releases.append(title)
                    continue
                if part and re.search(r"(\b(Part)([-_. ]+|)\d+(\.\d+)?)", title):
                    title = re.sub(r"(\b(Part)([-_. ]+|)\d+(\.\d+)?)", "", title)
                    title = remove_dual_space(title).strip()
                volume_number = ""
                modified_volume_regex_keywords = volume_regex_keywords
                # split on | and remove any single character words, then rejoin on |
                # use len(x) == 1 to remove any single character words
                modified_volume_regex_keywords = "|".join(
                    [x for x in modified_volume_regex_keywords.split("|") if len(x) > 1]
                )
                if not re.search(r"(\b(%s)([-_. ]|)\b)" % volume_regex_keywords, title):
                    if not re.search(
                        r"(([0-9]+)((([-_.]|)([0-9]+))+|))(\s+)?-(\s+)?(([0-9]+)((([-_.]|)([0-9]+))+|))",
                        title,
                    ):
                        volume_number = re.search(
                            r"([0-9]+(\.?[0-9]+)?([-_][0-9]+\.?[0-9]+)?)$", title
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
                        if title_split:
                            volume_number = title_split
                        else:
                            volume_number = None
                    if volume_number and not isinstance(volume_number, list):
                        if hasattr(volume_number, "group"):
                            volume_number = volume_number.group(1)
                            volume_number = set_num_as_float_or_int(volume_number)
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
                    volume_number = remove_everything_but_volume_num([title])
                if not re.search(r"(\b(%s)([-_. ]|)\b)" % volume_regex_keywords, title):
                    title = re.sub(
                        r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(%s|)(\.|)([-_. ]|)(([0-9]+)(\b|\s))$.*"
                        % volume_regex_keywords,
                        "",
                        title,
                        flags=re.IGNORECASE,
                    ).strip()
                    if re.search(r",$", title):
                        title = re.sub(r",$", "", title).strip()
                    title = title.replace("\n", "").replace("\t", "")
                    title = re.sub(rf"\b{volume_number}\b", "", title)
                    title = re.sub(r"(\s{2,})", " ", title).strip()
                    title = re.sub(r"(\((.*)\)$)", "", title).strip()
                else:
                    title = re.sub(
                        r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(%s)(\.|)([-_. ]|)([0-9]+)(\b|\s).*"
                        % volume_regex_keywords,
                        "",
                        title,
                        flags=re.IGNORECASE,
                    ).strip()
                shortened_title = get_shortened_title(title)
                shortened_query = get_shortened_title(query)
                clean_shortened_title = ""
                clean_shortened_query = ""
                if shortened_title:
                    clean_shortened_title = (
                        remove_punctuation(shortened_title).lower().strip()
                    )
                if shortened_query:
                    clean_shortened_query = unidecode(
                        (remove_punctuation(shortened_query).lower().strip())
                    )
                clean_title = remove_punctuation(title).lower().strip()
                clean_query = unidecode(remove_punctuation(query).lower().strip())
                score = similar(clean_title, clean_query)
                print(
                    "\t\t\t\t\t\tBookwalker: "
                    + clean_title
                    + "\n\t\t\t\t\t\tLibrary:    "
                    + clean_query
                    + "\n\t\t\t\t\t\tVolume Number: "
                    + str(volume_number)
                    + "\n\t\t\t\t\t\tScore: "
                    + str(score)
                    + "\n\t\t\t\t\t\tMatch: "
                    + str(score >= required_similarity_score)
                    + " (>= "
                    + str(required_similarity_score)
                    + ")"
                )
                score_two = 0
                if series_list_li == 1 and not score >= required_similarity_score:
                    if shortened_title and clean_shortened_title:
                        score_two = similar(clean_shortened_title, clean_query)
                        print(
                            "\n\t\t\t\t\t\tBookwalker: "
                            + clean_shortened_title
                            + "\n\t\t\t\t\t\tLibrary:    "
                            + clean_query
                            + "\n\t\t\t\t\t\tVolume Number: "
                            + str(volume_number)
                            + "\n\t\t\t\t\t\tScore: "
                            + str(score_two)
                            + "\n\t\t\t\t\t\tMatch: "
                            + str(score_two >= required_similarity_score)
                            + " (>= "
                            + str(required_similarity_score)
                            + ")"
                            + "\n"
                        )
                    elif shortened_query and clean_shortened_query:
                        score_two = similar(clean_title, clean_shortened_query)
                        print(
                            "\n\t\t\t\t\t\tBookwalker: "
                            + clean_title
                            + "\n\t\t\t\t\t\tLibrary:    "
                            + clean_shortened_query
                            + "\n\t\t\t\t\t\tVolume Number: "
                            + str(volume_number)
                            + "\n\t\t\t\t\t\tScore: "
                            + str(score_two)
                            + "\n\t\t\t\t\t\tMatch: "
                            + str(score_two >= required_similarity_score)
                            + " (>= "
                            + str(required_similarity_score)
                            + ")"
                            + "\n"
                        )
                if not (score >= required_similarity_score) and not (
                    score_two >= required_similarity_score
                ):
                    message = (
                        '"'
                        + clean_title
                        + '"'
                        + ": "
                        + str(score)
                        + " ["
                        + book_type
                        + "]"
                    )
                    if message not in similarity_match_failures:
                        similarity_match_failures.append(message)
                    required_similarity_score = original_similarity_score
                    continue

                # html from url
                page_two = scrape_url(url)

                # parse html
                soup_two = page_two

                soup_two = soup_two.find("div", class_="product-detail-inner")
                if not soup_two:
                    print("No soup_two")
                    continue

                # Find the book's preview image
                # Find <meta property="og:image" and get the content
                meta_property_og_image = page_two.find("meta", {"property": "og:image"})
                if meta_property_og_image:
                    if meta_property_og_image["content"].startswith("http"):
                        preview_image_url = meta_property_og_image["content"]

                # Backup method for lower resolution preview image
                if not preview_image_url:
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
                            for p_item in p_items:
                                # to avoid advertisement, advertisements tend to be
                                # the synopsis-lead
                                if (
                                    p_item.has_attr("class")
                                    and p_item["class"][0] != "synopsis-lead"
                                ):
                                    if p_item.text.strip():
                                        description += p_item.text.strip() + "\n"
                        else:
                            description = p_items[0].text.strip()

                # find table class="product-detail"
                product_detail = soup_two.find("table", class_="product-detail")
                # print(str((datetime.now() - start_time)))
                # find all <td> inside of product-detail
                product_detail_td = product_detail.find_all("td")
                date = ""
                for detail in product_detail_td:
                    date = re.search(
                        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(\s+)?\d{2}([,]+)?\s+\d{4}",
                        detail.text,
                        re.IGNORECASE,
                    )
                    # get the th from the detail
                    th = detail.find_previous_sibling("th")
                    # get the text from the th
                    th_text = th.text
                    if th_text == "Series Title" or th_text == "Alternative Title":
                        series_title = detail.text
                        # remove punctuation
                        series_title = remove_punctuation(series_title).lower().strip()
                        if not similar(
                            series_title, clean_query
                        ) >= required_similarity_score and not similar(
                            series_title, clean_shortened_query
                        ):
                            continue
                    if date:
                        date = date.group(0)
                        date = re.sub(r"[^\s\w]", "", date)
                        month = date.split()[0]
                        if len(month) != 3:
                            month = month[:3]
                        abbr_to_num = {
                            name: num
                            for num, name in enumerate(calendar.month_abbr)
                            if num
                        }
                        month = abbr_to_num[month]
                        day = date.split()[1]
                        year = date.split()[2]
                        date = datetime(int(year), month, int(day))
                        if date < datetime.now():
                            is_released = True
                        else:
                            is_released = False
                        date = date.strftime("%Y-%m-%d")
                        break
                book = BookwalkerBook(
                    title,
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
            if len(matching_books) > 0:
                series_list.append(
                    BookwalkerSeries(
                        book.title,
                        matching_books,
                        len(matching_books),
                        book.book_type,
                    )
                )
        if len(series_list) > 0 and print_info:
            print("Total Series: " + str(len(series_list)) + "\n")
            for series in series_list:
                if series_list.index(series) != 0:
                    print("\n")
                print(
                    "["
                    + str(series_list.index(series) + 1)
                    + "] "
                    + series.title
                    + " ["
                    + str(series.book_type)
                    + "]"
                    + " ("
                    + str(series.book_count)
                    + ")"
                )
                print("\t\tBooks:")
                for book in series.books:
                    # print the current books index
                    if not book.is_released:
                        print(
                            "\t\t\t("
                            + str(series.books.index(book) + 1)
                            + ")------------------------------ [PRE-ORDER]"
                        )
                    else:
                        print(
                            "\t\t\t("
                            + str(series.books.index(book) + 1)
                            + ")------------------------------"
                        )
                    print("\t\t\t\tNumber: " + str(book.volume_number))
                    # print("\t\t\t\tTitle: " + book.title)
                    print("\t\t\t\tDate: " + book.date)
                    print("\t\t\t\tReleased: " + str(book.is_released))
                    # print("\t\t\t\tPrice: " + str(book.price))
                    print("\t\t\t\tURL: " + book.url)
                    print("\t\t\t\tThumbnail: " + book.thumbnail)
                    # print("\t\t\t\tBook Type: " + book.book_type)
            else:
                print("\n\t\tNo results found.")

            if len(no_volume_number) > 0:
                print("\nNo Volume Results (" + str(len(no_volume_number)) + "):")
                for title in no_volume_number:
                    print("\t\t" + title)
                no_volume_number = []
            if len(chapter_releases) > 0:
                print("\nChapter Releases: (" + str(len(chapter_releases)) + ")")
                for title in chapter_releases:
                    print("\t\t" + title)
                chapter_releases = []
            if len(similarity_match_failures) > 0:
                print(
                    "\nSimilarity Match Failures "
                    + "("
                    + str(len(similarity_match_failures))
                    + "):"
                )
                for title in similarity_match_failures:
                    print(
                        "\t\t["
                        + str(similarity_match_failures.index(title) + 1)
                        + "] "
                        + title
                    )
                similarity_match_failures = []
            if len(no_book_result_searches) > 0:
                print(
                    "\nNo Book Result Searches ("
                    + str(len(no_book_result_searches))
                    + "):"
                )
                for url in no_book_result_searches:
                    print("\t\t" + url)
                no_book_result_searches = []
    series_list = combine_series(series_list)
    required_similarity_score = original_similarity_score
    # print("\t\tSleeping for " + str(sleep_timer_bk) + " to avoid being rate-limited...")
    time.sleep(sleep_timer_bk)
    if len(series_list) == 1:
        if len(series_list[0].books) > 0:
            return series_list[0].books
    elif len(series_list) > 1:
        print("\t\t\tNumber of series from bookwalker search is greater than one.")
        print("\t\t\tNum: " + str(len(series_list)))
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
# Doesn't work with NSFW results atm.
def check_for_new_volumes_on_bookwalker():
    global discord_embed_limit
    original_limit = discord_embed_limit
    discord_embed_limit = 1
    print("\nChecking for new volumes on bookwalker...")
    paths_clean = [p for p in paths if p not in download_folders]
    for path in paths_clean:
        path_index = paths_clean.index(path)
        if os.path.exists(path):
            os.chdir(path)
            # get list of folders from path directory
            path_dirs = [f for f in os.listdir(path) if os.path.isdir(f)]
            path_dirs.sort()
            path_dirs = clean_and_sort(path, dirs=path_dirs)[1]
            global folder_accessor
            folder_accessor = Folder(
                path,
                path_dirs,
                os.path.basename(os.path.dirname(path)),
                os.path.basename(path),
                [""],
            )
            for dir in folder_accessor.dirs:
                # if len(new_releases_on_bookwalker) == 5:
                #     break
                dir_index = folder_accessor.dirs.index(dir)
                print(
                    "\n\t[Folder "
                    + str(dir_index + 1)
                    + " of "
                    + str(len(folder_accessor.dirs))
                    + " - Path "
                    + str(path_index + 1)
                    + " of "
                    + str(len(paths_clean))
                    + "]"
                )
                print("\tPath: " + os.path.join(folder_accessor.root, dir))
                series = normalize_string_for_matching(
                    dir,
                    skip_common_words=True,
                    skip_japanese_particles=True,
                    skip_misc_words=True,
                )
                series = unidecode(series)
                current_folder_path = os.path.join(folder_accessor.root, dir)
                existing_dir_full_file_path = os.path.dirname(
                    os.path.join(folder_accessor.root, dir)
                )
                existing_dir = os.path.join(existing_dir_full_file_path, dir)
                clean_existing = os.listdir(existing_dir)
                clean_existing = clean_and_sort(
                    existing_dir, clean_existing, chapters=False
                )[0]
                existing_dir_volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(
                        [
                            f
                            for f in clean_existing
                            if os.path.isfile(os.path.join(existing_dir, f))
                        ],
                        existing_dir,
                    )
                )
                bookwalker_volumes = None
                type = None
                if (
                    get_percent_for_folder(
                        [f.name for f in existing_dir_volumes], manga_extensions
                    )
                    >= 70
                ):
                    type = "m"
                elif (
                    get_percent_for_folder(
                        [f.name for f in existing_dir_volumes], novel_extensions
                    )
                    >= 70
                ):
                    type = "l"
                if type and series:
                    bookwalker_volumes = search_bookwalker(series, type, False)
                    shortened_series_title = get_shortened_title(series)
                    if shortened_series_title:
                        shortened_bookwalker_volumes = search_bookwalker(
                            shortened_series_title, type, False, shortened_search=True
                        )
                        if shortened_bookwalker_volumes:
                            for vol in shortened_bookwalker_volumes:
                                found = False
                                if bookwalker_volumes:
                                    for compare_vol in bookwalker_volumes:
                                        if vol.url == compare_vol.url:
                                            found = True
                                            break
                                    if not found:
                                        bookwalker_volumes.append(vol)
                                else:
                                    bookwalker_volumes.append(vol)
                if existing_dir_volumes and bookwalker_volumes and type == "l":
                    # Go through each bookwalker volume and find a matching volume number in the existing directory
                    # if the bookwalker volume has a part and the existing volume doesn't, remove the bookwalker volume
                    # Avoids outputting part releases as missing volumes when the full volume already exists
                    for vol in bookwalker_volumes[:]:
                        for existing_vol in existing_dir_volumes:
                            if (
                                vol.volume_number == existing_vol.volume_number
                                and vol.part
                                and not existing_vol.volume_part
                            ):
                                print(
                                    "\t\tRemoving Bookwalker Volume: "
                                    + str(vol.volume_number)
                                    + " Part "
                                    + str(vol.part)
                                    + " because the full volume already exists."
                                )
                                bookwalker_volumes.remove(vol)
                if existing_dir_volumes and bookwalker_volumes:
                    if len(existing_dir_volumes) > len(bookwalker_volumes):
                        write_to_file(
                            "bookwalker_missing_volumes.txt",
                            series
                            + " - Existing Volumes: "
                            + str(len(existing_dir_volumes))
                            + ", Bookwalker Volumes: "
                            + str(len(bookwalker_volumes))
                            + "\n",
                            without_timestamp=True,
                            check_for_dup=True,
                        )
                    print("\t\tExisting Volumes: " + str(len(existing_dir_volumes)))
                    print(
                        "\t\tBookwalker Volumes: " + str(len(bookwalker_volumes)) + "\n"
                    )
                    for existing_vol in existing_dir_volumes:
                        for bookwalker_vol in bookwalker_volumes[:]:
                            if (
                                existing_vol.volume_number
                                == bookwalker_vol.volume_number
                                and existing_vol.volume_part == bookwalker_vol.part
                            ):
                                bookwalker_volumes.remove(bookwalker_vol)
                    if len(bookwalker_volumes) > 0:
                        new_releases_on_bookwalker.extend(bookwalker_volumes)
                        print("\t\tNew/Upcoming Releases on Bookwalker:")
                        for vol in bookwalker_volumes:
                            if vol.is_released:
                                print("\n\t\t\t[RELEASED]")
                            else:
                                print("\n\t\t\t[PRE-ORDER]")
                            print(
                                "\t\t\tVolume Number: "
                                + str(set_num_as_float_or_int(vol.volume_number))
                            )
                            if vol.part:
                                print("\t\t\tPart: " + str(vol.part))
                            print("\t\t\tDate: " + vol.date)
                            if vol == bookwalker_volumes[-1]:
                                print("\t\t\tURL: " + vol.url + "\n")
                            else:
                                print("\t\t\tURL: " + vol.url)
    pre_orders = []
    released = []
    if len(new_releases_on_bookwalker) > 0:
        for release in new_releases_on_bookwalker:
            if release.is_released:
                released.append(release)
            else:
                pre_orders.append(release)
    pre_orders.sort(key=lambda x: x.date, reverse=True)
    released.sort(key=lambda x: x.date, reverse=False)
    if log_to_file:
        # Get rid of the old released and pre-orders and replace them with new ones.
        if os.path.isfile(os.path.join(LOGS_DIR, "released.txt")):
            remove_file(os.path.join(LOGS_DIR, "released.txt"), silent=True)
        if os.path.isfile(os.path.join(LOGS_DIR, "pre-orders.txt")):
            remove_file(os.path.join(LOGS_DIR, "pre-orders.txt"), silent=True)
    if len(released) > 0:
        print("\nNew Releases:")
        for r in released:
            print("\t\t" + r.title)
            print("\t\tType: " + r.book_type)
            print("\t\tVolume " + str(set_num_as_float_or_int(r.volume_number)))
            print("\t\tDate: " + r.date)
            print("\t\tURL: " + r.url)
            print("\n")
            message = (
                r.date
                + " | "
                + r.title
                + " Volume "
                + str(set_num_as_float_or_int(r.volume_number))
                + " | "
                + r.book_type
                + " | "
                + r.url
            )
            write_to_file(
                "released.txt", message, without_timestamp=True, overwrite=False
            )
            embed = [
                handle_fields(
                    DiscordEmbed(
                        title=r.title
                        + " Volume "
                        + str(set_num_as_float_or_int(r.volume_number)),
                        color=grey_color,
                    ),
                    fields=[
                        {
                            "name": "Type:",
                            "value": r.book_type,
                            "inline": False,
                        },
                        {
                            "name": "Release Date:",
                            "value": r.date,
                            "inline": False,
                        },
                    ],
                ),
            ]

            # Add the description if it exists
            if r.description:
                # if len(r.description) > 350:
                #     r.description = r.description[:347] + "..."
                embed[0].fields.append(
                    {
                        "name": "Description:",
                        "value": unidecode(r.description),
                        "inline": False,
                    }
                )

            # set the url
            embed[0].url = r.url

            # set the pfp and bottom image
            if r.preview_image_url:
                # set the image to the image url
                embed[0].set_image(url=r.preview_image_url)
                # set the pfp to the image url
                embed[0].set_thumbnail(url=r.preview_image_url)

            # Set the author name, url, and icon url
            if bookwalker_logo_url and r.url:
                embed[0].set_author(
                    name="Bookwalker", url=r.url, icon_url=bookwalker_logo_url
                )

            if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
                add_to_grouped_notifications(
                    Embed(embed[0], None), passed_webhook=bookwalker_webhook_urls[0]
                )

        if grouped_notifications:
            if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
                send_discord_message(
                    None,
                    grouped_notifications,
                    passed_webhook=bookwalker_webhook_urls[0],
                )

    if len(pre_orders) > 0:
        print("\nPre-orders:")
        for p in pre_orders:
            print("\t\t" + p.title)
            print("\t\tType: " + p.book_type)
            print("\t\tVolume: " + str(set_num_as_float_or_int(p.volume_number)))
            print("\t\tDate: " + p.date)
            print("\t\tURL: " + p.url)
            print("\n")
            message = (
                p.date
                + " | "
                + p.title
                + " Volume "
                + str(set_num_as_float_or_int(p.volume_number))
                + " | "
                + p.book_type
                + " | "
                + p.url
            )
            write_to_file(
                "pre-orders.txt", message, without_timestamp=True, overwrite=False
            )
            embed = [
                handle_fields(
                    DiscordEmbed(
                        title=p.title
                        + " Volume "
                        + str(set_num_as_float_or_int(p.volume_number)),
                        color=preorder_blue_color,
                    ),
                    fields=[
                        {
                            "name": "Type:",
                            "value": p.book_type,
                            "inline": False,
                        },
                        {
                            "name": "Release Date:",
                            "value": p.date,
                            "inline": False,
                        },
                    ],
                ),
            ]

            # Add the description if it exists
            if p.description:
                # if len(p.description) > 350:
                #     p.description = p.description[:347] + "..."
                embed[0].fields.append(
                    {
                        "name": "Description:",
                        "value": unidecode(p.description),
                        "inline": False,
                    }
                )

            # set the url
            embed[0].url = p.url

            # get the preview image
            if p.preview_image_url:
                # set the image to the image url
                embed[0].set_image(url=p.preview_image_url)
                # set the pfp to the image url
                embed[0].set_thumbnail(url=p.preview_image_url)

            # Set the author name, url, and icon url
            if bookwalker_logo_url and p.url:
                embed[0].set_author(
                    name="Bookwalker", url=p.url, icon_url=bookwalker_logo_url
                )

            if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
                add_to_grouped_notifications(
                    Embed(embed[0], None), passed_webhook=bookwalker_webhook_urls[1]
                )

        if grouped_notifications:
            if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
                send_discord_message(
                    None,
                    grouped_notifications,
                    passed_webhook=bookwalker_webhook_urls[1],
                )
    discord_embed_limit = original_limit


# Checks the novel for bonus.xhtml or bonus[0-9].xhtml
def check_for_bonus_xhtml(zip):
    result = False
    try:
        with zipfile.ZipFile(zip) as zip:
            list = zip.namelist()
            for item in list:
                base = os.path.basename(item)
                if re.search(r"(bonus([0-9]+)?\.xhtml)", base, re.IGNORECASE):
                    result = True
                    break
    except Exception as e:
        send_message(str(e), error=True)
    return result


# caches all roots encountered when walking paths
def cache_existing_library_paths():
    global cached_paths
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
                            cached_paths.append(root)
                            write_to_file(
                                "cached_paths.txt",
                                root,
                                without_timestamp=True,
                                check_for_dup=True,
                            )
                            if path not in paths_cached:
                                paths_cached.append(path)
                except Exception as e:
                    send_message(str(e), error=True)
            else:
                print(
                    "\tSkipping: "
                    + path
                    + " because it's in the download folders list."
                )
        else:
            if path == "":
                send_message("\nERROR: Path cannot be empty.", error=True)
            else:
                print("\nERROR: " + path + " is an invalid path.\n")
    print("\tdone")

    if paths_cached:
        print("\nRoot paths that were recursively cached:")
        for path in paths_cached:
            print("\t" + path)


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
                "\t\tSuccessfully Initiated Scan for: " + library_id + " Library.",
                discord=False,
            )
        else:
            send_message(
                "\t\tFailed to Initiate Scan for: "
                + library_id
                + " Library"
                + " Status Code: "
                + str(request.status_code)
                + " Response: "
                + request.text,
                error=True,
            )
    except Exception as e:
        send_message(
            "Failed to Initiate Scan for: "
            + library_id
            + " Komga Library, ERROR: "
            + str(e),
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
                "\t\tFailed to Get Komga Libraries"
                + " Status Code: "
                + str(request.status_code)
                + " Response: "
                + request.text,
                error=True,
            )
    except Exception as e:
        # if first, and error code 104, then try again after sleeping
        if first_run and "104" in str(e):
            time.sleep(30)
            results = get_komga_libraries(first_run=False)
        else:
            send_message(
                "Failed to Get Komga Libraries, ERROR: " + str(e),
                error=True,
            )
    return results


# Generates a list of all release groups or publishers.
def generate_rename_lists():
    global release_groups
    global publishers
    global skipped_release_group_files
    global skipped_publisher_files
    skipped_files = []
    log_file_name = None
    skipped_file_name = None
    print("\nGenerating rename lists, with assistance of user.")
    mode = get_input_from_user(
        "\tEnter Mode",
        ["1", "2", "3"],
        "1 = Release Group, 2 = Publisher, 3 = Exit",
        use_timeout=True,
    )
    text_prompt = None
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
    if paths:
        for path in paths:
            if os.path.exists(path):
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
                        clean = clean_and_sort(root, files, dirs, sort=True)
                        files, dirs = clean[0], clean[1]
                        if files:
                            volumes = upgrade_to_volume_class(
                                upgrade_to_file_class(
                                    [
                                        f
                                        for f in files
                                        if os.path.isfile(os.path.join(root, f))
                                    ],
                                    root,
                                )
                            )
                            for file in volumes:
                                if mode == "p" and file.file_type == "chapter":
                                    continue
                                print("\n\tChecking: " + file.name)
                                found = False
                                if file.name not in skipped_files:
                                    if skipped_files and not skipped_file_volumes:
                                        skipped_file_volumes = upgrade_to_volume_class(
                                            upgrade_to_file_class(
                                                [f for f in skipped_files],
                                                root,
                                            )
                                        )
                                    if skipped_file_volumes:
                                        for skipped_file in skipped_file_volumes:
                                            if skipped_file.extras:
                                                # sort alphabetically
                                                skipped_file.extras.sort()
                                                # remove any year from the extras
                                                for extra in skipped_file.extras[:]:
                                                    if re.search(
                                                        r"([\[\(\{]\d{4}[\]\)\}])",
                                                        extra,
                                                        re.IGNORECASE,
                                                    ):
                                                        skipped_file.extras.remove(
                                                            extra
                                                        )
                                                        break
                                            if file.extras:
                                                # sort alphabetically
                                                file.extras.sort()
                                                # remove any year from the extras
                                                for extra in file.extras[:]:
                                                    if re.search(
                                                        r"([\[\(\{]\d{4}[\]\)\}])",
                                                        extra,
                                                        re.IGNORECASE,
                                                    ):
                                                        file.extras.remove(extra)
                                                        break
                                            if (
                                                file.extras == skipped_file.extras
                                                and file.extension
                                                == skipped_file.extension
                                                # and file.series_name
                                                # == skipped_file.series_name
                                            ):
                                                print(
                                                    "\t\tSkipping: "
                                                    + file.name
                                                    # + " because it has the same extras, extension, and series name as: "
                                                    + " because it has the same extras and extension as: "
                                                    + skipped_file.name
                                                    + " (in "
                                                    + skipped_file_name
                                                    + ")"
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
                                                    skipped_file_volume = (
                                                        upgrade_to_volume_class(
                                                            upgrade_to_file_class(
                                                                [file.name], root
                                                            )
                                                        )
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
                                    if mode == "r":
                                        if release_groups and not found:
                                            for group in release_groups:
                                                left_brackets = r"(\(|\[|\{)"
                                                right_brackets = r"(\)|\]|\})"
                                                group_escaped = re.escape(group)
                                                if re.search(
                                                    rf"{left_brackets}{group_escaped}{right_brackets}",
                                                    file.name,
                                                    re.IGNORECASE,
                                                ):
                                                    print(
                                                        '\t\tFound: "'
                                                        + group
                                                        + '", skipping file.'
                                                    )
                                                    found = True
                                                    break
                                    elif mode == "p":
                                        if publishers and not found:
                                            for publisher in publishers:
                                                left_brackets = r"(\(|\[|\{)"
                                                right_brackets = r"(\)|\]|\})"
                                                publisher_escaped = re.escape(publisher)
                                                if re.search(
                                                    rf"{left_brackets}{publisher_escaped}{right_brackets}",
                                                    file.name,
                                                    re.IGNORECASE,
                                                ):
                                                    print(
                                                        '\t\tFound: "'
                                                        + publisher
                                                        + '", skipping file.'
                                                    )
                                                    found = True
                                                    break
                                    if not found:
                                        # ask the user what the release group or publisher is, then write it to the file, add it to the list, and continue. IF the user inputs "none" then skip it.
                                        # loop until the user inputs a valid response
                                        while True:
                                            print(
                                                "\t\tCould not find a "
                                                + text_prompt
                                                + " for: \n\t\t\t"
                                                + file.name
                                            )
                                            group = input(
                                                "\n\t\tPlease enter the "
                                                + text_prompt
                                                + ' ("none" to add to '
                                                + skipped_file_name
                                                + ', "skip" to skip): '
                                            )
                                            if group == "none":
                                                print(
                                                    "\t\t\tAdding to "
                                                    + skipped_file_name
                                                    + " and skipping in the future..."
                                                )
                                                write_to_file(
                                                    skipped_file_name,
                                                    file.name,
                                                    without_timestamp=True,
                                                    check_for_dup=True,
                                                )
                                                if file.name not in skipped_files:
                                                    skipped_files.append(file.name)
                                                    skipped_file_vol = (
                                                        upgrade_to_volume_class(
                                                            upgrade_to_file_class(
                                                                [file.name], root
                                                            )
                                                        )
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
                                                print("\t\t\tYou entered: " + group)
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
                                    print(
                                        "\t\tSkipping... File is in "
                                        + skipped_file_name
                                    )
                except Exception as e:
                    send_message(str(e), error=True)
            else:
                if path == "":
                    send_message("\nERROR: Path cannot be empty.", error=True)
                else:
                    send_message(
                        "\nERROR: " + path + " is an invalid path.\n", error=True
                    )

        # Reassign the global arrays if anything new new got added to the local one.
        if skipped_files:
            if (
                mode == "r"
                and skipped_files
                and skipped_files != skipped_release_group_files
            ):
                skipped_release_group_files = skipped_files
            elif (
                mode == "p"
                and skipped_files
                and skipped_files != skipped_publisher_files
            ):
                skipped_publisher_files = skipped_files


# Checks if a string only contains one set of numbers
def only_has_one_set_of_numbers(string, chapter=False, file=None):
    keywords = volume_regex_keywords
    if chapter:
        keywords = chapter_regex_keywords + "|"
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


# Checks if the file name contains multiple numbers
@lru_cache(maxsize=None)
def has_multiple_numbers(file_name):
    numbers = re.findall(r"([0-9]+(\.[0-9]+)?)", file_name)
    new_numbers = []
    if numbers:
        for number in numbers:
            for item in number:
                if (
                    item
                    and set_num_as_float_or_int(item) not in new_numbers
                    and not re.search(r"(^\.[0-9]+$)", item)
                ):
                    new_numbers.append(set_num_as_float_or_int(item))
    if new_numbers and len(new_numbers) > 1:
        return True
    return False


# Extracts all the numbers from a string
def extract_all_numbers_from_string(string):
    numbers = re.findall(
        r"\b(%s)(([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?)"
        % exclusion_keywords_regex,
        string,
    )
    new_numbers = []
    if numbers:
        for number in numbers:
            if isinstance(number, tuple):
                for item in number:
                    if item:
                        if re.search(r"(x[0-9]+)", item):
                            continue
                        if re.search(r"(#([0-9]+)(([-_.])([0-9]+)|)+)", item):
                            continue
                        if re.search(r"^(-|\.)$", item):
                            continue
                        if item:
                            new_numbers.append(set_num_as_float_or_int(item))
            else:
                if number:
                    if re.search(r"(x[0-9]+)", number):
                        continue
                    if re.search(r"(#([0-9]+)(([-_.])([0-9]+)|)+)", number):
                        continue
                    if re.search(r"^(-|\.)$", number):
                        continue
                    if number:
                        new_numbers.append(set_num_as_float_or_int(number))
    return new_numbers


# Result class that is used for our image_comparison results from our
# image comparison function
class Image_Result:
    def __init__(self, ssim_score, image_source):
        self.ssim_score = ssim_score
        self.image_source = image_source


def prep_images_for_similarity(
    blank_image_path, internal_cover_data, both_cover_data=False, silent=False
):
    internal_cover = cv2.imdecode(
        np.frombuffer(internal_cover_data, np.uint8), cv2.IMREAD_UNCHANGED
    )
    blank_image = None
    if not both_cover_data:
        blank_image = cv2.imread(blank_image_path)
    else:
        blank_image = cv2.imdecode(
            np.frombuffer(blank_image_path, np.uint8), cv2.IMREAD_UNCHANGED
        )
    internal_cover = np.array(internal_cover)
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
    # if they have both have a third channel, make them the same
    if len(blank_image.shape) == 3 and len(internal_cover.shape) == 3:
        if blank_image.shape[2] > internal_cover.shape[2]:
            blank_image = blank_image[:, :, : internal_cover.shape[2]]
        else:
            internal_cover = internal_cover[:, :, : blank_image.shape[2]]
    elif len(blank_image.shape) == 3 and len(internal_cover.shape) == 2:
        blank_image = blank_image[:, :, 0]
    elif len(blank_image.shape) == 2 and len(internal_cover.shape) == 3:
        internal_cover = internal_cover[:, :, 0]
    score = compare_images(blank_image, internal_cover, silent=silent)
    return score


# compares our two images likness and returns the ssim score
def compare_images(imageA, imageB, silent=False):
    ssim_score = None
    try:
        if not silent:
            print("\t\t\tBlank Image Size: " + str(imageA.shape))
            print("\t\t\tInternal Cover Size: " + str(imageB.shape))

        if len(imageA.shape) == 3 and len(imageB.shape) == 3:
            grayA = cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY)
            grayB = cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY)
            ssim_score = ssim(grayA, grayB)
        else:
            ssim_score = ssim(imageA, imageB)
        if not silent:
            print("\t\t\t\tSSIM: " + str(ssim_score))
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
        send_message(f"Error extracting {file_path}: {str(e)}", error=True)
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
        send_message(f"Error compressing {temp_dir}: {str(e)}", error=True)
    return successfull


# Converts supported archives to CBZ.
def convert_to_cbz(group=False):
    global transferred_files
    if download_folders:
        print("\nLooking for archives to convert to CBZ...")
        for folder in download_folders:
            if os.path.isdir(folder):
                print(f"\t{folder}")
                for root, dirs, files in scandir.walk(folder):
                    clean = None
                    if (
                        watchdog_toggle
                        and download_folders
                        and any(x for x in download_folders if root.startswith(x))
                    ):
                        clean = clean_and_sort(
                            root,
                            files,
                            dirs,
                            just_these_files=transferred_files,
                            just_these_dirs=transferred_dirs,
                            skip_remove_unaccepted_file_types=True,
                            keep_images_in_just_these_files=True,
                        )
                    else:
                        clean = clean_and_sort(
                            root,
                            files,
                            dirs,
                            skip_remove_unaccepted_file_types=True,
                        )
                    files, dirs = clean[0], clean[1]
                    for entry in files:
                        try:
                            extension = get_file_extension(entry)
                            file_path = os.path.join(root, entry)

                            if not os.path.isfile(file_path):
                                continue

                            print(f"\t\t{entry}")

                            if extension in convertable_file_extensions:
                                source_file = file_path
                                repacked_file = (
                                    f"{get_extensionless_name(source_file)}.cbz"
                                )

                                # check that the cbz file doesn't already exist
                                if os.path.isfile(repacked_file):
                                    # if the file is zero bytes, delete it and continue, otherwise skip
                                    if get_file_size(repacked_file) == 0:
                                        send_message(
                                            f"\t\t\tCBZ file is zero bytes, deleting...",
                                            discord=False,
                                        )
                                        remove_file(repacked_file, group=group)
                                    elif not zipfile.is_zipfile(repacked_file):
                                        send_message(
                                            f"\t\t\tCBZ file is not a valid zip file, deleting...",
                                            discord=False,
                                        )
                                        remove_file(repacked_file, group=group)
                                    else:
                                        send_message(
                                            f"\t\t\tCBZ file already exists, skipping...",
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
                                extract_status = extract(
                                    source_file, temp_dir, extension
                                )

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
                                        with py7zr.SevenZipFile(
                                            source_file
                                        ) as seven_zip:
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
                                            print(
                                                f"\t\t\t\t{file} is not in {repacked_file}"
                                            )
                                    for file in repacked_file_list:
                                        if file not in source_file_list:
                                            print(
                                                f"\t\t\t\t{file} is not in {source_file}"
                                            )

                                    # remove temp directory
                                    remove_folder(temp_dir)

                                    # remove cbz file
                                    remove_file(repacked_file, group=group)

                                    continue
                                else:
                                    print(
                                        "\t\t\tAll files are present in both archives."
                                    )

                                hashes_verified = False

                                # Verify hashes of all files inside the cbz file
                                with zipfile.ZipFile(repacked_file) as zip:
                                    for file in zip.namelist():
                                        if get_file_extension(file):
                                            hash = get_internal_file_hash(
                                                repacked_file, file
                                            )
                                            if hash and hash not in hashes:
                                                print(
                                                    f"\t\t\t\t{file} hash did not match"
                                                )
                                                break
                                    else:
                                        hashes_verified = True

                                # Remove temp directory
                                remove_folder(temp_dir)

                                if hashes_verified:
                                    send_message(
                                        f"\t\t\tHashes verified.", discord=False
                                    )
                                    send_message(
                                        f"\t\t\tConverted {source_file} to {repacked_file}",
                                        discord=False,
                                    )
                                    embed = [
                                        handle_fields(
                                            DiscordEmbed(
                                                title="Converted to CBZ",
                                                color=grey_color,
                                            ),
                                            fields=[
                                                {
                                                    "name": "From:",
                                                    "value": "```"
                                                    + os.path.basename(source_file)
                                                    + "```",
                                                    "inline": False,
                                                },
                                                {
                                                    "name": "To:",
                                                    "value": "```"
                                                    + os.path.basename(repacked_file)
                                                    + "```",
                                                    "inline": False,
                                                },
                                                {
                                                    "name": "Location:",
                                                    "value": "```"
                                                    + os.path.dirname(repacked_file)
                                                    + "```",
                                                    "inline": False,
                                                },
                                            ],
                                        )
                                    ]
                                    add_to_grouped_notifications(Embed(embed[0], None))

                                    # remove the source file
                                    remove_file(source_file, group=group)

                                    if watchdog_toggle:
                                        if source_file in transferred_files:
                                            transferred_files.remove(source_file)
                                        if repacked_file not in transferred_files:
                                            transferred_files.append(repacked_file)
                                else:
                                    send_message(
                                        f"\t\t\tHashes did not verify", error=True
                                    )
                                    # remove cbz file
                                    remove_file(repacked_file, group=group)

                            elif extension == ".zip" and rename_zip_to_cbz:
                                header_extension = get_file_extension_from_header(
                                    file_path
                                )
                                # if it's a zip file, then rename it to cbz
                                if (
                                    zipfile.is_zipfile(file_path)
                                    or header_extension in manga_extensions
                                ):
                                    rename_path = (
                                        get_extensionless_name(file_path) + ".cbz"
                                    )
                                    user_input = None
                                    if not manual_rename:
                                        user_input = "y"
                                    else:
                                        user_input = get_input_from_user(
                                            "\t\t\tRename to CBZ",
                                            ["y", "n"],
                                            ["y", "n"],
                                        )
                                    if user_input == "y":
                                        rename_file(
                                            file_path,
                                            rename_path,
                                        )
                                        if os.path.isfile(
                                            rename_path
                                        ) and not os.path.isfile(file_path):
                                            if watchdog_toggle:
                                                if file_path in transferred_files:
                                                    transferred_files.remove(file_path)
                                                if rename_path not in transferred_files:
                                                    transferred_files.append(
                                                        rename_path
                                                    )
                                    else:
                                        print("\t\t\t\tSkipping...")
                        except Exception as e:
                            send_message(
                                f"Error when correcting extension: {entry}: {str(e)}",
                                error=True,
                            )

                            # if the tempdir exists, remove it
                            if os.path.isdir(temp_dir):
                                remove_folder(temp_dir)

                            # if the cbz file exists, remove it
                            if os.path.isfile(repacked_file):
                                remove_file(repacked_file, group=group)
            else:
                send_message(f"\t{folder} does not exist.", error=True)
    else:
        print("No download folders specified.")

    if group and grouped_notifications and not group_discord_notifications_until_max:
        send_discord_message(None, grouped_notifications)


# Goes through each file in download_folders and checks for an incorrect file extension
# based on the file header. If the file extension is incorrect, it will rename the file.
def correct_file_extensions(group=False):
    global transferred_files
    if download_folders:
        print("\nChecking for incorrect file extensions...")
        for folder in download_folders:
            if os.path.isdir(folder):
                print("\t{}".format(folder))
                for root, dirs, files in scandir.walk(folder):
                    clean = None
                    if (
                        watchdog_toggle
                        and download_folders
                        and any(x for x in download_folders if root.startswith(x))
                    ):
                        clean = clean_and_sort(
                            root,
                            files,
                            dirs,
                            just_these_files=transferred_files,
                            just_these_dirs=transferred_dirs,
                            is_correct_extensions_feature=True,
                        )
                    else:
                        clean = clean_and_sort(
                            root, files, dirs, is_correct_extensions_feature=True
                        )
                    files, dirs = clean[0], clean[1]
                    volumes = upgrade_to_file_class(
                        [f for f in files if os.path.isfile(os.path.join(root, f))],
                        root,
                        skip_get_file_extension_from_header=False,
                        is_correct_extensions_feature=True,
                    )
                    if volumes:
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
                                user_input = None
                                if not manual_rename:
                                    user_input = "y"
                                else:
                                    user_input = get_input_from_user(
                                        "\t\t\tRename",
                                        ["y", "n"],
                                        ["y", "n"],
                                    )
                                if user_input == "y":
                                    rename_status = rename_file(
                                        volume.path,
                                        volume.extensionless_path
                                        + volume.header_extension,
                                        silent=True,
                                    )
                                    if rename_status:
                                        print("\t\t\tRenamed successfully")
                                        if not mute_discord_rename_notifications:
                                            embed = [
                                                handle_fields(
                                                    DiscordEmbed(
                                                        title="Renamed File",
                                                        color=grey_color,
                                                    ),
                                                    fields=[
                                                        {
                                                            "name": "From:",
                                                            "value": "```"
                                                            + volume.name
                                                            + "```",
                                                            "inline": False,
                                                        },
                                                        {
                                                            "name": "To:",
                                                            "value": "```"
                                                            + volume.extensionless_name
                                                            + volume.header_extension
                                                            + "```",
                                                            "inline": False,
                                                        },
                                                    ],
                                                )
                                            ]
                                            add_to_grouped_notifications(
                                                Embed(embed[0], None)
                                            )
                                            if watchdog_toggle:
                                                if volume.path in transferred_files:
                                                    transferred_files.remove(
                                                        volume.path
                                                    )
                                                if (
                                                    volume.extensionless_path
                                                    + volume.header_extension
                                                    not in transferred_files
                                                ):
                                                    transferred_files.append(
                                                        volume.extensionless_path
                                                        + volume.header_extension
                                                    )
                                else:
                                    print("\t\t\tSkipped")

            else:
                send_message("\t{} does not exist.".format(folder), error=True)
    else:
        print("No download folders specified.")

    if group and grouped_notifications and not group_discord_notifications_until_max:
        send_discord_message(None, grouped_notifications)

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

    processed_files = []
    moved_files = []
    download_folder_in_paths = False

    # Determines when the cover_extraction should be run
    if download_folders and paths:
        for folder in download_folders:
            if folder in paths:
                download_folder_in_paths = True
                break

    # Load cached_paths.txt into cached_paths
    if (
        os.path.isfile(os.path.join(LOGS_DIR, "cached_paths.txt"))
        and check_for_existing_series_toggle
        and not cached_paths
    ):
        cached_paths = get_lines_from_file(
            os.path.join(LOGS_DIR, "cached_paths.txt"),
            ignore=paths + download_folders,
            ignore_paths_not_in_paths=True,
        )

    # Cache the paths if the user doesn't have a cached_paths.txt file
    if (
        (
            cache_each_root_for_each_path_in_paths_at_beginning_toggle
            or not os.path.isfile(os.path.join(LOGS_DIR, "cached_paths.txt"))
        )
        and paths
        and check_for_existing_series_toggle
        and not cached_paths
    ):
        cache_existing_library_paths()
        if cached_paths:
            print(f"\n\tLoaded {len(cached_paths)} cached paths")

    # Load release_groups.txt into release_groups
    if os.path.isfile(os.path.join(LOGS_DIR, "release_groups.txt")):
        release_groups_read = get_lines_from_file(
            os.path.join(LOGS_DIR, "release_groups.txt")
        )
        if release_groups_read:
            release_groups = release_groups_read
            print(
                f"\tLoaded {len(release_groups)} release groups from release_groups.txt"
            )

    # Load publishers.txt into publishers
    if os.path.isfile(os.path.join(LOGS_DIR, "publishers.txt")):
        publishers_read = get_lines_from_file(os.path.join(LOGS_DIR, "publishers.txt"))
        if publishers_read:
            publishers = publishers_read
            print(f"\tLoaded {len(publishers)} publishers from publishers.txt")

    # Correct any incorrect file extensions
    if correct_file_extensions_toggle and download_folders:
        correct_file_extensions(group=True)

    # Convert any non-cbz supported file to cbz
    if convert_to_cbz_toggle and download_folders:
        convert_to_cbz(group=True)

    # Delete any files with unacceptable keywords in their name
    if delete_unacceptable_files_toggle and download_folders and unacceptable_keywords:
        delete_unacceptable_files(group=True)

    # Delete any chapters from the downloads folder
    if delete_chapters_from_downloads_toggle and download_folders:
        delete_chapters_from_downloads(group=True)

    # Generate the release group list
    if (
        generate_release_group_list_toggle
        and log_to_file
        and paths
        and not watchdog_toggle
        and not in_docker
    ):
        # Loads skipped_release_group_files.txt into skipped_release_group_files
        if os.path.isfile(os.path.join(LOGS_DIR, "skipped_release_group_files.txt")):
            skipped_release_group_files_read = get_lines_from_file(
                os.path.join(LOGS_DIR, "skipped_release_group_files.txt")
            )
            if skipped_release_group_files_read:
                skipped_release_group_files = skipped_release_group_files_read
                print(
                    f"\n\tLoaded {len(skipped_release_group_files)} skipped release group files from skipped_release_group_files.txt"
                )

        # Loads skipped_publisher_files.txt into skipped_publisher_files
        if os.path.isfile(os.path.join(LOGS_DIR, "skipped_publisher_files.txt")):
            skipped_publisher_files_read = get_lines_from_file(
                os.path.join(LOGS_DIR, "skipped_publisher_files.txt")
            )
            if skipped_publisher_files_read:
                skipped_publisher_files = skipped_publisher_files_read
                print(
                    f"\tLoaded {len(skipped_publisher_files)} skipped publisher files from skipped_publisher_files.txt"
                )
        generate_rename_lists()

    # Rename the files in the download folders
    if rename_files_in_download_folders_toggle and download_folders:
        rename_files_in_download_folders(group=True)

    # Create folders for items in the download folder
    if create_folders_for_items_in_download_folder_toggle and download_folders:
        create_folders_for_items_in_download_folder(group=True)

    # Rename the root directory folders in the download folder
    if rename_dirs_in_download_folder_toggle and download_folders:
        rename_dirs_in_download_folder(group=True)

    # Checks for duplicate volumes/chapters in the download folders
    if check_for_duplicate_volumes_toggle and download_folders:
        check_for_duplicate_volumes(download_folders, group=True)

    # Extract the covers from the files in the download folders
    if extract_covers_toggle and paths and download_folder_in_paths:
        extract_covers()

    # Match the files in the download folders to the files in the library
    if check_for_existing_series_toggle and download_folders and paths:
        check_for_existing_series(group=True)

    # Extract the covers from the files in the library
    if extract_covers_toggle and paths and not download_folder_in_paths:
        extract_covers()

    # Check for missing volumes in the library (local solution)
    if check_for_missing_volumes_toggle and paths:
        check_for_missing_volumes()

    # Check for missing volumes in the library (bookwalker solution)
    if bookwalker_check and not watchdog_toggle:
        check_for_new_volumes_on_bookwalker()

    # Print the number of files encountered, and their extensions
    if extract_covers_toggle and paths:
        print_stats()

    if watchdog_toggle:
        if transferred_files:
            # remove any deleted/renamed/moved files
            transferred_files = [x for x in transferred_files if os.path.isfile(x)]

        # remove any deleted/renamed/moved directories
        if transferred_dirs:
            transferred_dirs = [x for x in transferred_dirs if os.path.isdir(x.root)]

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

    # Send any remaining queued notifications to Discord
    if watchdog_toggle and grouped_notifications:
        send_discord_message(None, grouped_notifications)


if __name__ == "__main__":
    parse_my_args()  # parses the user's arguments
    if watchdog_toggle and download_folders:
        print("\nWatchdog is enabled, watching for changes...")
        watch = Watcher()
        watch.run()
    else:
        main()
