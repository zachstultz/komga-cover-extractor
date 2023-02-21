import os
import re
import zipfile
import shutil
import string
import regex as re
import sys
import argparse
import subprocess
import urllib.request
import calendar
import requests
import time
import scandir
import random
import xml.etree.ElementTree as ET
import io
import concurrent.futures
import numpy as np
import cv2
from PIL import Image
from PIL import ImageFile
from lxml import etree
from genericpath import isfile
from posixpath import join
from difflib import SequenceMatcher
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed
from bs4 import BeautifulSoup, SoupStrainer
from settings import *
from langdetect import detect
from titlecase import titlecase
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from base64 import b64encode
from unidecode import unidecode
from io import BytesIO
from functools import lru_cache
from skimage.metrics import structural_similarity as ssim

script_version = "2.2.3"

# Paths = existing library
# Download_folders = newly aquired manga/novels
paths = []
download_folders = []

# paths within paths that were passed in with a defined path_type
# EX: "volume" or "chapter"
paths_with_types = []

# global folder_accessor
folder_accessor = None

# whether or not to compress the extractred images
compress_image_option = False

# Default image compression value.
# Pass in via cli
image_quality = 60

# Stat-related
file_count = 0
cbz_count = 0
epub_count = 0
image_count = 0
cbz_internal_covers_found = 0
poster_found = 0
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

# Whether or not to check the library against bookwalker for new releases.
bookwalker_check = False

# All the release groups stored in release_groups.txt
# Used when renaming files where it has a matching group.
release_groups = []

# skipped files that don't have a release group
skipped_files = []

# Newly released volumes that aren't currently in the library.
new_releases_on_bookwalker = []

# A quick and dirty fix to avoid non-processed files from
# being moved over to the existing library. Will be removed in the future.
processed_files = []

# Any files moved to the existing library.
# Used when determining whether or not to trigger a library scan in komga.
moved_files = []

# All extensions that aren't in this list will be ignored when searching
# an epubs internal contents.
internal_epub_extensions = [".xhtml", ".opf", ".ncx", ".xml", ".html"]

# Where logs are written to.
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

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

# Volume Regex Keywords to be used throughout the script
volume_regex_keywords = (
    "LN|Light Novels?|Novels?|Books?|Volumes?|Vols?|Discs?|Tomo|Tome|V|第|T"
)

# Chapter Regex Keywords to be used throughout the script
chapter_regex_keywords = "chapters?|chaps?|chs?|cs?"

# REMINDER: ORDER IS IMPORTANT, Top to bottom is the order it will be checked in.
# Once a match is found, it will stop checking the rest.
chapter_searches = [
    r"\s-(\s+)?(#)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(\s+)?-\s",
    r"(\b(?<![A-Za-z])(%s)((\.)|)(\s+)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?\b)"
    % chapter_regex_keywords,
    r"((\b(?<![A-Za-z])(%s|)((\.)|)(\s+)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?\b)(\s+)?((\(|\{|\[)\w+(([-_. ])+\w+)?(\]|\}|\))|(?<!\w(\s+)?)(\.cbz|\.epub)(?!\w)))"
    % chapter_regex_keywords,
    r"(?<!([A-Za-z]|(Part|Episode|Season|Story|Arc)(\s+)?))(((%s)([-_. ]+)?([0-9]+))|\s+([0-9]+)(\.[0-9]+)?(x\d+((\.\d+)+)?)?(\s+|#\d+|\.cbz))"
    % chapter_regex_keywords,
    r"^((#)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?)$",
]

# Used in check_for_existing_series when sending
# a bulk amount of chapter releases to discord after the function is done,
# so they can be sent in one message or in order.
messages_to_send = []

# ONLY FOR TESTING
output_execution_times = False


# Folder Class
class Folder:
    def __init__(self, root, dirs, basename, folder_name, files):
        self.root = root
        self.dirs = dirs
        self.basename = basename
        self.folder_name = folder_name
        self.files = files


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
        number,
        file_type,
    ):
        self.name = name
        self.extensionless_name = extensionless_name
        self.basename = basename
        self.extension = extension
        self.root = root
        self.path = path
        self.extensionless_path = extensionless_path
        self.number = number
        self.file_type = file_type


# Volume Class
class Volume:
    def __init__(
        self,
        file_type,
        series_name,
        volume_year,
        volume_number,
        volume_part,
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
        multi_volume=None,
        is_one_shot=None,
    ):
        self.file_type = file_type
        self.series_name = series_name
        self.volume_year = volume_year
        self.volume_number = volume_number
        self.volume_part = volume_part
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
        self.multi_volume = multi_volume
        self.is_one_shot = is_one_shot


class Path:
    def __init__(
        self, path, path_types=["volume", "chapter"], path_extensions=file_extensions
    ):
        self.path = path
        self.path_types = path_types
        self.path_extensions = path_extensions


# It watches the download directory for any changes.
class Watcher:
    def __init__(self):
        self.observer = Observer()

    def run(self):
        event_handler = Handler()
        if download_folders:
            self.observer.schedule(event_handler, download_folders[0], recursive=True)
            self.observer.start()
            try:
                while True:
                    time.sleep(10)
            except:
                self.observer.stop()
                print("Observer Stopped")

            self.observer.join()


# Sends a message, prints it, and writes it to a file depending on whether the error parameter is set to True or False
def send_message(message, discord=True, error=False):
    print(message)
    if discord != False:
        send_discord_message(message)
    if error:
        errors.append(message)
        write_to_file("errors.txt", message)
    else:
        items_changed.append(message)
        write_to_file("changes.txt", message)


# The last valid file that was found by the watchdog
last_watchdog_file = None


class Handler(FileSystemEventHandler):
    @staticmethod
    def on_any_event(event):
        global last_watchdog_file
        if (
            not event.is_directory
            and not os.path.basename(event.src_path).startswith(".")
            and event.event_type == "created"
            and os.path.isfile(event.src_path)
            and get_file_extension(os.path.basename(event.src_path)) in file_extensions
        ):
            time.sleep(10)
            if os.path.isfile(event.src_path) and zipfile.is_zipfile(event.src_path):
                last_watchdog_file = event.src_path
                send_message("Starting Script (WATCHDOG) (EXPERIMENTAL)", discord=False)
                send_discord_message(
                    None,
                    "Starting Script (WATCHDOG) (EXPERIMENTAL)",
                    color=7615723,
                    fields=[
                        {
                            "name": "File Found:",
                            "value": "```" + str(event.src_path) + "```",
                            "inline": False,
                        }
                    ],
                )
                main()


# Read all the lines of a text file and return them
def read_lines_from_file(file_path, ignore=set(), ignore_paths_not_in_paths=False):
    result = []
    try:
        with open(file_path, "r") as file:
            for line in file:
                line = line.strip()
                if line and line not in ignore:
                    if ignore_paths_not_in_paths:
                        for path in paths:
                            if line.startswith(path) and line not in result:
                                result.append(line)
                                break
                    else:
                        result.append(line)
    except FileNotFoundError:
        print(f"{file_path} not found.")
    except:
        print(f"An error occured while reading {file_path}.")
    return result


new_volume_webhook = None

# Parses the passed command-line arguments
def parse_my_args():
    global paths
    global download_folders
    global discord_webhook_url
    global paths_with_types
    parser = argparse.ArgumentParser(
        description="Scans for covers in the cbz and epub files."
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
        help="Whether or not to compress the extracted cover images.",
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
        help="Whether or not to use the watchdog library to watch for file changes in the download folders.",
        required=False,
    )
    parser.add_argument(
        "-nw",
        "--new_volume_webhook",
        help="If passed in, the new volume release notification will be redirected to this single discord webhook channel.",
        required=False,
    )
    parser = parser.parse_args()
    if not parser.paths and not parser.download_folders:
        print("No paths or download folders were passed to the script.")
        print("Exiting...")
        exit()
    if parser.paths is not None:
        for path in parser.paths:
            if path:
                if len(path) == 1:
                    paths.append(path[0])
                elif len(path) == 2 and (
                    str(path[1]).lower() == "chapter"
                    or str(path[1]).lower() == "volume"
                ):
                    paths_with_types.append(Path(path[0], path_types=[path[1]]))
                    paths.append(path[0])
                # otherwise if there are 2 arguments and they passed a single extension or list of extensions separated by commas
                elif len(path) == 2 and re.search(r"\.[a-zA-Z0-9]{1,4}", path[1]):
                    extensions = path[1].split(",")
                    # get rid of any whitespace
                    extensions = [extension.strip() for extension in extensions]
                    found_in_file_extensions = False
                    for extension in extensions:
                        if extension in file_extensions:
                            found_in_file_extensions = True
                            break
                    if found_in_file_extensions:
                        paths_with_types.append(
                            Path(path[0], path_extensions=extensions)
                        )
                        paths.append(path[0])
                    else:
                        paths.append(path[0])
                elif len(path) == 3:
                    if (
                        str(path[1]).lower() == "chapter"
                        or str(path[1]).lower() == "volume"
                    ):
                        extensions = path[2].split(",")
                        # get rid of any whitespace
                        extensions = [extension.strip() for extension in extensions]
                        found_in_file_extensions = False
                        for extension in extensions:
                            if extension in file_extensions:
                                found_in_file_extensions = True
                                break
                        if found_in_file_extensions:
                            paths_with_types.append(
                                Path(
                                    path[0],
                                    path_types=[path[1]],
                                    path_extensions=extensions,
                                )
                            )
                            paths.append(path[0])
                        else:
                            paths.append(path[0])
                    elif (
                        str(path[2]).lower() == "chapter"
                        or str(path[2]).lower() == "volume"
                    ):
                        extensions = path[1].split(",")
                        # get rid of any whitespace
                        extensions = [extension.strip() for extension in extensions]
                        found_in_file_extensions = False
                        for extension in extensions:
                            if extension in file_extensions:
                                found_in_file_extensions = True
                                break
                        if found_in_file_extensions:
                            paths_with_types.append(
                                Path(
                                    path[0],
                                    path_types=[path[2]],
                                    path_extensions=extensions,
                                )
                            )
                            paths.append(path[0])
                        else:
                            paths.append(path[0])
                    else:
                        paths.append(path[0])
                else:
                    paths.append(path[0])
    if parser.download_folders is not None:
        download_folders = [
            folder
            for download_folder in parser.download_folders
            for folder in download_folder
        ]
    if parser.webhook is not None:
        discord_webhook_url = list(
            set(
                [
                    hook
                    for item in parser.webhook
                    for hook in item
                    if hook not in discord_webhook_url
                ]
            )
        )
    if parser.bookwalker_check is not None:
        if parser.bookwalker_check.lower() == "true":
            global bookwalker_check
            bookwalker_check = True
    if parser.compress is not None:
        if parser.compress.lower() == "true":
            global compress_image_option
            compress_image_option = True
    if parser.compress_quality is not None:
        global image_quality
        image_quality = set_num_as_float_or_int(parser.compress_quality)
    if parser.bookwalker_webhook_urls is not None:
        global bookwalker_webhook_urls
        bookwalker_webhook_urls = list(
            set([hook for item in parser.bookwalker_webhook_urls for hook in item])
        )
    if parser.watchdog is not None:
        if parser.watchdog.lower() == "true":
            if download_folders:
                global watchdog_toggle
                watchdog_toggle = True
            else:
                send_message(
                    "Watchdog was enabled, but no download folders were passed to the script.",
                    error=True,
                )
    if parser.new_volume_webhook is not None:
        global new_volume_webhook
        new_volume_webhook = parser.new_volume_webhook


def set_num_as_float_or_int(volume_number, silent=False):
    start_time = time.time()
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
                + str(volume_number),
                error=True,
            )
            send_message(e, error=True)
        return ""
    if output_execution_times:
        print_function_execution_time(start_time, "set_num_as_float_or_int()")
    return volume_number


# Handles image compression
def compress_image(image_path, quality=image_quality, to_jpg=False, raw_data=None):
    img = None
    filename = None
    extension = None
    new_filename = None
    if not raw_data:
        img = Image.open(image_path)
    else:
        img = Image.open(io.BytesIO(raw_data))
    if not raw_data:
        filename, ext = os.path.splitext(image_path)
        extension = get_file_extension(image_path)
        if extension == ".png" and not raw_data:
            to_jpg = True
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    if to_jpg and not raw_data:
        new_filename = f"{filename}.jpg"
    elif not raw_data:
        new_filename = f"{filename}" + extension
    try:
        if not raw_data:
            img.save(new_filename, quality=quality, optimize=True)
        else:
            # compress the image data using BytesIO and return the data
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=50)
            # return the compressed image data
            return buffer.getvalue()
        if extension == ".png" and (
            os.path.isfile(new_filename) and os.path.isfile(image_path) and not raw_data
        ):
            os.remove(image_path)
            return image_path
    except OSError as ose:
        send_message(
            "\t\tFailed to compress image: " + image_path + " \n\t\tERROR: " + str(ose),
            error=True,
        )


# Check the text file line by line for the passed message
def check_text_file_for_message(text_file, message):
    with open(text_file, "r") as f:
        for line in f:
            if message.strip() == line.strip():
                return True
    return False


last_hook_index = None

# Sends a discord message using the users webhook url
def send_discord_message(
    message,
    title=None,
    url=None,
    rate_limit=True,
    color=None,
    proxies={},
    fields=[],
    timestamp=True,
    passed_webhook=None,
    image=None,
    image_local=None,
):
    hook = None
    global discord_webhook_url
    global last_hook_index
    global script_version
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
    webhook = DiscordWebhook()
    embed = None
    try:
        if hook:
            if color and not embed:
                embed = DiscordEmbed()
                embed.color = color
            elif color and embed:
                embed.color = color
            if title and not embed:
                embed = DiscordEmbed()
                # discord max title length is 256
                if len(title) > 256:
                    title = title[:253] + "..."
                embed.title = title
            elif title and embed:
                # discord max title length is 256
                if len(title) > 256:
                    title = title[:253] + "..."
                embed.title = title
            if message and not embed:
                webhook.content = message
            elif message and embed:
                embed.description = message
            webhook.url = hook
            if rate_limit:
                webhook.rate_limit_retry = rate_limit
            if embed:
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
                if script_version:
                    # Embed footer is limited to 2048 characters
                    if len("v" + script_version) > 2048:
                        embed.set_footer(text="v" + script_version[:2045] + "...")
                    else:
                        embed.set_footer(text="v" + script_version)
                if timestamp:
                    embed.set_timestamp()
                if image and not image_local:
                    embed.set_image(url=image)
                elif image_local and not image:
                    webhook.add_file(file=image_local, filename="cover.jpg")
                    embed.set_image(url="attachment://cover.jpg")
                webhook.add_embed(embed)
            if proxies:
                webhook.proxies = proxies
            response = webhook.execute()
        else:
            return
    except Exception as e:
        send_message(e, discord=False, error=True)


# Removes hidden files
def remove_hidden_files(files):
    return [x for x in files if not x.startswith(".")]


# Removes any unaccepted file types
def remove_unaccepted_file_types(files, root, accepted_extensions):
    return [
        file
        for file in files
        if get_file_extension(file) in accepted_extensions
        and os.path.isfile(os.path.join(root, file))
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
    global chapter_searches
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
    return any(
        result and not re.search(r"^((\(|\{|\[)\d{4}(\]|\}|\)))$", result.group(0))
        for result in chapter_search_results
    )


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
    root, files=[], dirs=[], sort=False, chapters=chapter_support_toggle
):
    global ignored_folder_names
    global file_extensions
    start_time = time.time()
    if ignored_folder_names:
        ignored_folder_names_start = time.time()
        ignored_parts = [
            part for part in root.split(os.sep) if part and part in ignored_folder_names
        ]
        if output_execution_times:
            print_function_execution_time(
                ignored_folder_names_start,
                "ignored_folder_names in clean_and_sort()",
            )
        if any(ignored_parts):
            return [], []
    if files:
        if sort:
            files.sort()
        hidden_files_remove_start = time.time()
        files = remove_hidden_files(files)
        if output_execution_times:
            print_function_execution_time(
                hidden_files_remove_start,
                "remove_hidden_files() in clean_and_sort()",
            )
        remove_unnaccepted_file_types_start = time.time()
        files = remove_unaccepted_file_types(files, root, file_extensions)
        if output_execution_times:
            print_function_execution_time(
                remove_unnaccepted_file_types_start,
                "remove_unaccepted_file_types() in clean_and_sort()",
            )
        if not chapters:
            filter_non_chapters_start = time.time()
            files = filter_non_chapters(files)
            if output_execution_times:
                print_function_execution_time(
                    filter_non_chapters_start,
                    "filter_non_chapters() in clean_and_sort()",
                )
    if dirs:
        if sort:
            dirs.sort()
        remove_hidden_folders_start = time.time()
        dirs = remove_hidden_folders(dirs)
        if output_execution_times:
            print_function_execution_time(
                remove_hidden_folders_start,
                "remove_hidden_folders() in clean_and_sort()",
            )
        remove_ignored_folder_names_start = time.time()
        dirs = remove_ignored_folder_names(dirs)
        if output_execution_times:
            print_function_execution_time(
                remove_ignored_folder_names_start,
                "remove_ignored_folder_names() in clean_and_sort()",
            )
    if output_execution_times:
        print_function_execution_time(start_time, "clean_and_sort()")
    return files, dirs


# Retrieves the file extension on the passed file
def get_file_extension(file):
    return os.path.splitext(file)[1]


# Returns an extensionless name
def get_extensionless_name(file):
    return os.path.splitext(file)[0]


# Trades out our regular files for file objects
def upgrade_to_file_class(files, root):
    start_time = time.time()
    files = clean_and_sort(root, files)[0]

    # Create a list of tuples with arguments to pass to the File constructor
    file_args = [
        (
            file,
            get_extensionless_name(file),
            (
                get_series_name_from_file_name_chapter(file, chapter_number)
                if file_type == "chapter"
                else get_series_name_from_file_name(file, root)
            ),
            get_file_extension(file),
            root,
            os.path.join(root, file),
            get_extensionless_name(os.path.join(root, file)),
            chapter_number,
            file_type,
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
    if output_execution_times:
        print_function_execution_time(start_time, "upgrade_to_file_class()")

    # Process the files sequentially
    results = [File(*args) for args in file_args]

    # clear lru_cache for contains_chapter_keywords
    contains_chapter_keywords.cache_clear()

    # clear lru_cache for contains_volume_keywords
    contains_volume_keywords.cache_clear()

    return results


# Updates our output stats
def update_stats(file):
    if not os.path.isfile(file.path):
        return

    global file_count
    file_count += 1

    if file.extension == ".cbz":
        global cbz_count
        cbz_count += 1
    elif file.extension == ".epub":
        global epub_count
        epub_count += 1


# Credit to original source: https://alamot.github.io/epub_cover/
# Modified by me.
# Retrieves the inner epub cover
def get_epub_cover(epub_path):
    namespaces = {
        "calibre": "http://calibre.kovidgoyal.net/2009/metadata",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
        "opf": "http://www.idpf.org/2007/opf",
        "u": "urn:oasis:names:tc:opendocument:xmlns:container",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    with zipfile.ZipFile(epub_path) as z:
        try:
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
                        print("\t\t\tNo cover_href found in get_epub_cover()")
                else:
                    print("\t\t\tNo cover_id found in get_epub_cover()")
            else:
                print(
                    "\t\t\tNo rootfile_path found in META-INF/container.xml in get_epub_cover()"
                )
        except Exception as e:
            send_message(e, error=True)
    return None


# Checks if the passed string is a volume one.
def is_volume_one(volume_name):
    global volume_regex_keywords
    global chapter_regex_keywords
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
def is_one_shot_bk(file_name):
    number_status = re.search(r"\d+", file_name)
    chapter_file_status = contains_chapter_keywords(file_name)
    exception_keyword_status = check_for_exception_keywords(
        file_name, exception_keywords
    )
    if (not number_status and not chapter_file_status) and (
        not exception_keyword_status
    ):
        return True
    return False


# Checks for volume keywords and chapter keywords.
# If neither are present, the volume is assumed to be a one-shot volume.
def is_one_shot(file_name, root):
    files = clean_and_sort(root, os.listdir(root))[0]
    continue_logic = False
    if len(files) == 1 or (download_folders and root == download_folders[0]):
        continue_logic = True
    if continue_logic == True:
        volume_file_status = contains_volume_keywords(file_name)
        chapter_file_status = contains_chapter_keywords(file_name)
        exception_keyword_status = check_for_exception_keywords(
            file_name, exception_keywords
        )
        if (not volume_file_status and not chapter_file_status) and (
            not exception_keyword_status
        ):
            return True
    return False


# Checks similarity between two strings.
@lru_cache(maxsize=None)
def similar(a, b):
    if a == "" or b == "":
        return 0.0
    else:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# Moves the image into a folder if said image exists. Also checks for a cover/poster image and moves that.
def move_images(file, folder_name):
    for extension in image_extensions:
        image = file.extensionless_path + extension
        if os.path.isfile(image):
            shutil.move(image, folder_name)
        for cover_file_name in series_cover_file_names:
            cover_image_file_name = cover_file_name + extension
            cover_image_file_path = os.path.join(file.root, cover_image_file_name)
            if os.path.isfile(cover_image_file_path):
                if not os.path.isfile(os.path.join(folder_name, cover_image_file_name)):
                    shutil.move(cover_image_file_path, folder_name)
                else:
                    remove_file(cover_image_file_path)


# Retrieves the series name through various regexes
# Removes the volume number and anything to the right of it, and strips it.
def get_series_name_from_file_name(name, root):
    global volume_regex_keywords
    name = remove_bracketed_info_from_name(name)
    start_time = time.time()
    if is_one_shot(name, root):
        name = re.sub(
            r"([-_ ]+|)(((\[|\(|\{).*(\]|\)|\}))|LN)([-_. ]+|)(epub|cbz|).*",
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
                r"(\d+)?([-_. ]+)?((\[|\(|\})(.*)(\]|\)|\}))?([-_. ]+)?(\.cbz|\.epub)$",
                "",
                name,
                flags=re.IGNORECASE,
            ).strip()
    if output_execution_times:
        print_function_execution_time(start_time, "get_series_name_from_file_name()")
    return name


def chapter_file_name_cleaning(file_name, chapter_number="", skip=False):
    global chapter_regex_keywords
    start_time = time.time()
    # removes any brackets and their contents
    file_name = remove_bracketed_info_from_name(file_name)

    # Remove any single brackets at the end of the file_name
    # EX: "Death Note - Bonus Chapter (" --> "Death Note - Bonus Chapter"
    file_name = re.sub(r"([\(\[\{])|([\)\]\}])$", "", file_name).strip()

    # EX: "006.3 - One Piece" --> "One Piece"
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
    if re.search(r"(Season|Sea|S)(\s+)?([0-9]+)$", file_name, re.IGNORECASE):
        file_name = re.sub(
            r"(Season|Sea|S)(\s+)?([0-9]+)$", "", file_name, flags=re.IGNORECASE
        )
    if output_execution_times:
        print_function_execution_time(start_time, "chapter_file_name_cleaning()")
    return file_name


def get_series_name_from_file_name_chapter(name, chapter_number=""):
    start_time = time.time()
    # remove the file extension
    name = re.sub(r"(\.cbz|\.epub)$", "", name).strip()

    # remove underscores
    name = replace_underscore_in_name(name)

    for regex in chapter_searches:
        search = re.search(regex, name, flags=re.IGNORECASE)
        if search:
            name = re.sub(regex + "(.*)", "", name, flags=re.IGNORECASE).strip()
            break
    if isinstance(chapter_number, list):
        result = chapter_file_name_cleaning(name, chapter_number[0])
    else:
        result = chapter_file_name_cleaning(name, chapter_number)
    if output_execution_times:
        print_function_execution_time(
            start_time, "get_series_name_from_file_name_chapter()"
        )
    return result


# Creates folders for our stray volumes sitting in the root of the download folder.
def create_folders_for_items_in_download_folder():
    for download_folder in download_folders:
        if os.path.exists(download_folder):
            try:
                for root, dirs, files in scandir.walk(download_folder):
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
                                                    file.root,
                                                    file.extensionless_path,
                                                    new_file_obj.extensionless_path,
                                                )
                                                file = new_file_obj
                                            else:
                                                # if it does exist, delete the file
                                                remove_file(file.path)
                                        # check that the file doesn't already exist in the folder
                                        if os.path.isfile(
                                            file.path
                                        ) and not os.path.isfile(
                                            os.path.join(root, dir, file.name)
                                        ):
                                            # it doesn't, we move it and the image associated with it, to that folder
                                            move_file(file, os.path.join(root, dir))
                                            done = True
                                            break
                                        else:
                                            # it does, so we remove the duplicate file
                                            remove_file(os.path.join(root, file.name))
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
                                    move_file(file, folder_location)
                                else:
                                    move_file(file, folder_location)
            except Exception as e:
                send_message(e, error=True)
        else:
            if download_folder == "":
                send_message("\nERROR: Path cannot be empty.", error=True)
            else:
                send_message(
                    "\nERROR: " + download_folder + " is an invalid path.\n", error=True
                )


# Returns the percentage of files in the given list that have the specified extension or file type.
def get_percent_for_folder(files, extension=None, file_type=None):
    if file_type:
        count = len([file for file in files if file.file_type == file_type])
    elif extension:
        count = len([file for file in files if file.endswith(extension)])
    else:
        return 0
    percent = (count / len(files)) * 100 if count != 0 else 0
    return percent


def check_for_multi_volume_file(file_name, chapter=False):
    keywords = volume_regex_keywords
    if chapter:
        keywords = chapter_regex_keywords + "|"
    if re.search(
        r"(\b({})(\.)?(\s+)?([0-9]+(\.[0-9]+)?)([-]([0-9]+(\.[0-9]+)?))+\b)".format(
            keywords
        ),
        remove_bracketed_info_from_name(file_name),
        re.IGNORECASE,
    ):
        return True
    else:
        return False


def convert_list_of_numbers_to_array(string):
    numbers = []
    numbers_search = re.sub(r"[-_]", " ", string)
    numbers_search = remove_dual_space(numbers_search).strip()
    numbers_search = numbers_search.split(" ")
    # convert them to numbers using set_num_as_float_or_int
    numbers_search = [set_num_as_float_or_int(num) for num in numbers_search]
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
    return numbers


# Finds the volume number and strips out everything except that number
def remove_everything_but_volume_num(files, chapter=False):
    start_time = time.time()
    global chapter_searches
    results = []
    is_multi_volume = False
    keywords = volume_regex_keywords
    if chapter:
        keywords = chapter_regex_keywords
    for file in files[:]:
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
                    r"((Episode|Ep)(\.)?(\s+)?(#)?(([0-9]+)(([-_.])([0-9]+)|)+))$",
                    re.sub(r"(\.cbz|\.epub)", "", file),
                    re.IGNORECASE,
                ):
                    file = re.sub(
                        r"((Episode|Ep)(\.)?(\s+)?(#)?(([0-9]+)(([-_.])([0-9]+)|)+))$",
                        "",
                        re.sub(r"(\.cbz|\.epub)", "", file),
                        re.IGNORECASE,
                    ).strip()
                    # remove - at the end of the string
                    if not re.search(
                        r"-(\s+)?(#)?([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(\s+)?-", file
                    ) and re.search(r"(-)$", file):
                        file = re.sub(r"(-)$", "", file).strip()
            # With a chapter keyword, without, but before bracketed info, or without and with .cbz or .epub after the number
            # Series Name c001.cbz or Series Name 001 (2021) (Digital) (Release).cbz or Series Name 001.cbz
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
                    file = re.sub(
                        r"(\(|\{|\[)(\w+(([-_. ])+\w+)?)?(\]|\}|\))", "", file
                    ).strip()

                    # Removes the - characters.cbz or .epub from the end of the string, with
                    # the dash and characters being optional
                    # EX:  - prologue.cbz or .cbz
                    file = re.sub(
                        r"(((\s+)?-(\s+)?([A-Za-z]+))?(\.cbz|\.epub))",
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
                        multi_numbers = convert_list_of_numbers_to_array(file)
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
    if output_execution_times:
        print_function_execution_time(start_time, "remove_everything_but_volume_num()")
    if is_multi_volume == True and len(results) != 0:
        return results
    elif len(results) != 0 and (len(results) == len(files)):
        return results[0]
    elif len(results) == 0:
        return ""


# Retrieves the release year
def get_volume_year(name):
    match = re.search(r"(\(|\[|\{)(\d{4})(\)|\]|\})", name, re.IGNORECASE)
    if match:
        return int(re.sub(r"(\(|\[|\{)|(\)|\]|\})", "", match.group(0)))
    else:
        return ""


# Compile the regular expression pattern outside of the function
fixed_volume_pattern = re.compile(
    r"(\(|\[|\{)(f|fix(ed)?)([-_. :]+)?([0-9]+)?(\)|\]|\})", re.IGNORECASE
)

# Determines whether or not the release is a fixed release
def is_fixed_volume(name, fixed_volume_pattern=fixed_volume_pattern):
    result = fixed_volume_pattern.search(name)
    return True if result else False


# Retrieves the release_group on the file name
def get_release_group(name, release_groups):
    result = ""
    if release_groups:
        for group in release_groups:
            group_escaped = re.escape(group)
            left_brackets = r"(\(|\[|\{)"
            right_brackets = r"(\)|\]|\})"
            search = re.search(
                rf"{left_brackets}{group_escaped}{right_brackets}", name, re.IGNORECASE
            )
            if search:
                result = search.group()
                if result:
                    # remove any brackets that it starts with or ends with
                    result = re.sub(rf"^{left_brackets}|{right_brackets}$", "", result)
                break
    return result


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
def get_file_part(file, chapter=False):
    global rx_remove, rx_search_part, rx_search_chapters, rx_remove_x_hash
    result = ""
    if not chapter:
        # Remove the matched string from the input file name
        file = rx_remove.sub("", file).strip()
        search = rx_search_part.search(file)
        if search:
            result = search.group(1)
            result = re.sub(r"Part([-_. ]|)+", " ", result, flags=re.IGNORECASE).strip()
            try:
                return float(result)
            except ValueError:
                print("Not a float: " + file)
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


# Trades out our regular files for file objects
def upgrade_to_volume_class(
    files,
):
    start_time = time.time()
    results = []
    for file in files:
        file_obj = Volume(
            file.file_type,
            file.basename,
            get_volume_year(file.name),
            file.number,
            (
                get_file_part(file.name)
                if file.file_type != "chapter"
                else get_file_part(file.name, chapter=True)
            ),
            is_fixed_volume(file.name),
            get_release_group(file.name, release_groups),
            file.name,
            file.extensionless_name,
            file.basename,
            file.extension,
            file.root,
            file.path,
            file.extensionless_path,
            (
                get_extras(file.name, series_name=file.basename)
                if file.file_type != "chapter"
                else get_extras(file.name, series_name=file.basename, chapter=True)
            ),
            (
                check_for_multi_volume_file(file.name)
                if file.file_type != "chapter"
                else check_for_multi_volume_file(file.name, chapter=True)
            ),
            (
                is_one_shot(file.name, file.root)
                if file.file_type != "chapter"
                else False
            ),
        )
        if file_obj.is_one_shot:
            file_obj.volume_number = 1
        results.append(file_obj)
    if output_execution_times:
        print_function_execution_time(start_time, "upgrade_to_volume_class()")
    return results


# The RankedKeywordResult class is a container for the total score and the keywords
class RankedKeywordResult:
    def __init__(self, total_score, keywords):
        self.total_score = total_score
        self.keywords = keywords


# > This class represents the result of an upgrade check
class UpgradeResult:
    def __init__(self, is_upgrade, downloaded_ranked_result, current_ranked_result):
        self.is_upgrade = is_upgrade
        self.downloaded_ranked_result = downloaded_ranked_result
        self.current_ranked_result = current_ranked_result


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


# Checks if the downloaded release is an upgrade for the current release.
def is_upgradeable(downloaded_release, current_release):
    global ranked_keywords
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
            remove_file(os.path.join(root, file))


# Removes the old series and cover image
def remove_images(path):
    for extension in image_extensions:
        if is_volume_one(os.path.basename(path)):
            for cover_file_name in series_cover_file_names:
                cover_file_name = os.path.join(
                    os.path.dirname(path), cover_file_name + extension
                )
                if os.path.isfile(cover_file_name):
                    remove_file(cover_file_name, silent=True)
        volume_image_cover_file_name = get_extensionless_name(path) + extension
        if os.path.isfile(volume_image_cover_file_name):
            remove_file(volume_image_cover_file_name, silent=True)
            if not os.path.isfile(volume_image_cover_file_name):
                break


# Removes a file
def remove_file(full_file_path, silent=False):
    if os.path.isfile(full_file_path):
        try:
            os.remove(full_file_path)
            if not os.path.isfile(full_file_path):
                if not silent:
                    send_message("\t\t\tFile Removed: " + full_file_path, discord=False)
                    send_discord_message(
                        None,
                        "Removed File",
                        color=16711680,
                        fields=[
                            {
                                "name": "File:",
                                "value": "```"
                                + os.path.basename(full_file_path)
                                + "```",
                                "inline": False,
                            },
                            {
                                "name": "Location:",
                                "value": "```"
                                + os.path.dirname(full_file_path)
                                + "```",
                                "inline": False,
                            },
                        ],
                    )
                if get_file_extension(full_file_path) not in image_extensions:
                    remove_images(full_file_path)
                return True
            else:
                send_message(
                    "\n\t\t\tFailed to remove file: " + full_file_path, error=True
                )
                return False
        except OSError as e:
            send_message(e, error=True)
            return False
    else:
        send_message(
            "\n\t\t\tFile does not exist when trying to remove: " + full_file_path,
            error=True,
        )
        return False


# Move a file
def move_file(file, new_location, silent=False):
    try:
        if os.path.isfile(file.path):
            shutil.move(file.path, new_location)
            if os.path.isfile(os.path.join(new_location, file.name)):
                if not silent:
                    send_message(
                        "\t\tMoved File: " + file.name + " to " + new_location,
                        discord=False,
                    )
                    send_discord_message(
                        None,
                        "Moved File",
                        color=8421504,
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
                move_images(file, new_location)
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
        send_message(e, error=True)
        return False


# Replaces an old file.
def replace_file(old_file, new_file):
    try:
        if os.path.isfile(old_file.path) and os.path.isfile(new_file.path):
            file_removal_status = remove_file(old_file.path)
            if not os.path.isfile(old_file.path) and file_removal_status:
                move_file(new_file, old_file.root, silent=True)
                if os.path.isfile(os.path.join(old_file.root, new_file.name)):
                    send_message(
                        "\t\tFile: "
                        + new_file.name
                        + " was moved to: "
                        + old_file.root,
                        discord=False,
                    )
                    send_discord_message(
                        None,
                        "Moved File",
                        color=8421504,
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
        send_message(e, error=True)
        send_message("Failed file replacement.", error=True)


# execute command with subprocess and reutrn the output
def execute_command(command):
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
        send_message(e, error=True)


# Removes the duplicate after determining it's upgrade status, otherwise, it upgrades
def remove_duplicate_releases_from_download(original_releases, downloaded_releases):
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
        if len(downloaded_releases) != 0:
            for original in original_releases[:]:
                if (
                    (
                        isinstance(download.volume_number, float)
                        and isinstance(original.volume_number, float)
                    )
                    or (
                        download.volume_number
                        and download.multi_volume
                        and isinstance(download.volume_number, list)
                    )
                ) and os.path.isfile(original.path):
                    fields = []
                    if (
                        download.volume_number != ""
                        and original.volume_number != ""
                        and download.volume_part == original.volume_part
                        and (
                            download.volume_number == original.volume_number
                            or (
                                (
                                    (
                                        (
                                            download.multi_volume
                                            and download.volume_number
                                            and not original.multi_volume
                                            and download.volume_number[0]
                                            == original.volume_number
                                        )
                                    )
                                    or (
                                        original.multi_volume
                                        and original.volume_number
                                        and not download.multi_volume
                                        and original.volume_number[0]
                                        == download.volume_number
                                    )
                                )
                                and allow_matching_single_volumes_with_multi_volumes
                            )
                        )
                        and download.file_type == original.file_type
                    ):
                        if allow_matching_single_volumes_with_multi_volumes and (
                            (download.multi_volume and not original.multi_volume)
                            or (original.multi_volume and not download.multi_volume)
                        ):
                            send_message(
                                "\n\t\tallow_matching_single_volumes_with_multi_volumes=True"
                            )
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
                                "\t\tNOT UPGRADE: "
                                + download.name
                                + " is not an upgrade to: "
                                + original.name
                                + "\n\t\tDeleting: "
                                + download.name
                                + " from download folder.",
                                discord=False,
                            )
                            send_discord_message(
                                None,
                                "Upgrade Process (Not Upgrade)",
                                color=16776960,
                                fields=fields,
                            )
                            if download in downloaded_releases:
                                downloaded_releases.remove(download)
                            remove_file(download.path)
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
                            send_discord_message(
                                None,
                                "Upgrade Process (Upgrade)",
                                color=65280,
                                fields=fields,
                            )
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
                                            remove_file(original_volume.path)
                                            original_releases.remove(original_volume)
                            replace_file(original, download)
                            moved_files.append(download)
                            if download in downloaded_releases:
                                downloaded_releases.remove(download)
                    elif (download.volume_number == original.volume_number) and (
                        (download.volume_number != "" and original.volume_number != "")
                        and (not download.volume_part and original.volume_part)
                        and download.file_type == original.file_type
                    ):
                        upgrade_status = is_upgradeable(download, original)
                        if not upgrade_status.is_upgrade:
                            send_message(
                                "\t\tNOT UPGRADE: "
                                + download.name
                                + " is not an upgrade to: "
                                + original.name
                                + "\n\t\tDeleting: "
                                + download.name
                                + " from download folder.",
                                discord=False,
                            )
                            send_discord_message(
                                None,
                                "Upgrade Process (Not Upgrade)",
                                color=16776960,
                                fields=fields,
                            )
                            if download in downloaded_releases:
                                downloaded_releases.remove(download)
                            remove_file(download.path)
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
                            send_discord_message(
                                None,
                                "Upgrade Process (Upgrade)",
                                color=65280,
                                fields=fields,
                            )
                            send_message(
                                "\t\tRemoving remaining part files with matching release numbers:"
                            )
                            clone_original_releases = original_releases.copy()
                            clone_original_releases.remove(original)
                            for v in clone_original_releases:
                                if (
                                    (download.volume_number == v.volume_number)
                                    and (
                                        download.volume_number != ""
                                        and v.volume_number != ""
                                    )
                                    and (not download.volume_part and v.volume_part)
                                ):
                                    remove_file(v.path)
                                    original_releases.remove(v)
                            replace_file(original, download)
                            moved_files.append(download)
                            if download in downloaded_releases:
                                downloaded_releases.remove(download)


# Checks if the folder is empty, then deletes if it is
def check_and_delete_empty_folder(folder):
    try:
        print("\t\tChecking for empty folder: " + folder)
        delete_hidden_files(os.listdir(folder), folder)
        folder_contents = os.listdir(folder)
        folder_contents = remove_hidden_files(folder_contents)
        if len(folder_contents) == 0 and (
            folder not in paths and folder not in download_folders
        ):
            try:
                print("\t\t\tRemoving empty folder: " + folder)
                os.rmdir(folder)
            except OSError as e:
                send_message(e, error=True)
    except Exception as e:
        send_message(e, error=True)


# Writes a log file
def write_to_file(
    file, message, without_date=False, overwrite=False, check_for_dup=False
):
    if log_to_file:
        message = re.sub("\t|\n", "", str(message), flags=re.IGNORECASE).strip()
        contains = False
        if check_for_dup and os.path.isfile(os.path.join(ROOT_DIR, file)):
            contains = check_text_file_for_message(
                os.path.join(ROOT_DIR, file), message
            )
        if not contains or overwrite:
            try:
                file_path = os.path.join(ROOT_DIR, file)
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
                        if without_date:
                            file.write("\n " + message)
                        else:
                            file.write("\n" + dt_string + " " + message)
                        file.close()
                except Exception as e:
                    send_message(e, error=True)
            except Exception as e:
                send_message(e, error=True)


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
                                if volume.extension == ".cbz":
                                    message += " [MANGA]"
                                elif volume.extension == ".epub":
                                    message += " [NOVEL]"
                                print(message)
                                write_to_file("missing_volumes.txt", message)


# Renames the file.
def rename_file(
    src, dest, root, extensionless_filename_src, extensionless_filename_dst
):
    if os.path.isfile(src):
        print("\n\t\tRenaming " + src)
        try:
            os.rename(src, dest)
        except Exception as e:
            send_message(e, error=True)
        if os.path.isfile(dest):
            send_message(
                "\t\t"
                + extensionless_filename_src
                + " was renamed to "
                + extensionless_filename_dst,
                discord=False,
            )
            for image_extension in image_extensions:
                image_file = extensionless_filename_src + image_extension
                image_file_rename = extensionless_filename_dst + image_extension
                if os.path.isfile(os.path.join(root, image_file)):
                    try:
                        os.rename(
                            os.path.join(root, image_file),
                            os.path.join(root, image_file_rename),
                        )
                    except Exception as e:
                        send_message(e, error=True)
        else:
            send_message(
                "Failed to rename " + src + " to " + dest + "\n\tERROR: " + str(e),
                error=True,
            )


def reorganize_and_rename(files, dir):
    global manual_rename
    base_dir = os.path.basename(dir)
    for file in files:
        preferred_naming_format = preferred_volume_renaming_format
        keywords = volume_regex_keywords
        if file.file_type == "chapter":
            keywords = chapter_regex_keywords
            preferred_naming_format = preferred_chapter_renaming_format
        try:
            if re.search(
                r"(\b(%s)([-_.]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s|\.epub|\.cbz))"
                % keywords,
                file.name,
                re.IGNORECASE,
            ):
                comic_info_xml = ""
                epub_info_html = ""
                if file.extension == ".cbz":
                    contains_comic_info = check_if_zip_file_contains_comic_info_xml(
                        file.path
                    )
                    if contains_comic_info:
                        comicinfo = get_file_from_zip(
                            file.path, "comicinfo.xml", allow_base=False
                        )
                        tags = None
                        if comicinfo:
                            comicinfo = comicinfo.decode("utf-8")
                            # not parsing pages correctly
                            comic_info_xml = parse_comicinfo_xml(comicinfo)
                elif file.extension == ".epub":
                    epub_content_opf = get_file_from_zip(file.path, "content.opf")
                    epub_package_opf = get_file_from_zip(file.path, "package.opf")
                    if epub_content_opf:
                        epub_info_html = parse_html_tags(epub_content_opf)
                    elif epub_package_opf:
                        epub_info_html = parse_html_tags(epub_package_opf)
                release_year_from_file = ""
                publisher = ""
                if comic_info_xml:
                    if "Year" in comic_info_xml:
                        release_year_from_file = comic_info_xml["Year"]
                        if release_year_from_file and release_year_from_file.isdigit():
                            release_year_from_file = int(release_year_from_file)
                    if "Publisher" in comic_info_xml:
                        publisher = titlecase(comic_info_xml["Publisher"])
                        publisher = remove_dual_space(publisher)
                        publisher = re.sub(r", LLC.*", "", publisher)
                elif epub_info_html:
                    if "dc:date" in epub_info_html:
                        release_year_from_file = epub_info_html["dc:date"].strip()
                        release_year_from_file = re.search(
                            r"\d{4}", release_year_from_file
                        )
                        if release_year_from_file:
                            release_year_from_file = release_year_from_file.group(0)
                            if (
                                release_year_from_file
                                and release_year_from_file.isdigit()
                            ):
                                release_year_from_file = int(release_year_from_file)
                    if "dc:publisher" in epub_info_html:
                        publisher = titlecase(epub_info_html["dc:publisher"])
                        publisher = remove_dual_space(publisher)
                        publisher = re.sub(r", LLC.*", "", publisher).strip()
                        publisher = re.sub(r"LLC", "", publisher).strip()
                        publisher = re.sub(r":", " - ", publisher).strip()
                        publisher = remove_dual_space(publisher)
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
                number_string = ""
                zfill_int = 2  # 01
                zfill_float = 4  # 01.0
                if file.file_type == "chapter":
                    zfill_int = 3  # 001
                    zfill_float = 5  # 001.0
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
                    add_issue_number_to_cbz_file_name
                    and file.file_type == "volume"
                    and file.extension == ".cbz"
                    and number_string
                ):
                    rename += " #" + number_string
                if file.extension == ".cbz":
                    if isinstance(file.volume_year, int):
                        rename += " (" + str(file.volume_year) + ")"
                    elif release_year_from_file and isinstance(
                        release_year_from_file, int
                    ):
                        file.volume_year = release_year_from_file
                        rename += " (" + str(file.volume_year) + ")"
                elif file.extension == ".epub":
                    if isinstance(file.volume_year, int):
                        rename += " [" + str(file.volume_year) + "]"
                    elif release_year_from_file and isinstance(
                        release_year_from_file, int
                    ):
                        file.volume_year = release_year_from_file
                        rename += " [" + str(file.volume_year) + "]"
                if publisher:
                    for item in file.extras[:]:
                        score = similar(
                            re.sub(
                                r"(Entertainment|Pictures?|LLC|Americas?|USA?|International|Books?|Comics?|Media|Advanced|Club|On|Press|Enix Manga|Enix|[-_.,\(\[\{\)\]\}])",
                                "",
                                item,
                            ).strip(),
                            re.sub(
                                r"(Entertainment|Pictures?|LLC|Americas?|USA?|International|Books?|Comics?|Media|Advanced|Club|On|Press|Enix Manga|Enix|[-_.,\(\[\{\)\]\}])",
                                "",
                                publisher,
                            ).strip(),
                        )
                        if (
                            re.search(
                                publisher,
                                item,
                                re.IGNORECASE,
                            )
                            or score >= 0.90
                        ):
                            file.extras.remove(item)
                    if add_publisher_name_to_file_name_when_renaming:
                        if file.extension == ".cbz":
                            rename += " (" + publisher + ")"
                        elif file.extension == ".epub":
                            rename += " [" + publisher + "]"
                if file.volume_year:
                    for item in file.extras[:]:
                        score = similar(
                            item,
                            str(file.volume_year),
                        )
                        if (
                            re.search(
                                str(file.volume_year),
                                item,
                                re.IGNORECASE,
                            )
                            or score >= required_similarity_score
                            or re.search(r"([\[\(\{]\d{4}[\]\)\}])", item)
                        ):
                            file.extras.remove(item)
                if release_year_from_file:
                    for item in file.extras[:]:
                        score = similar(
                            item,
                            str(release_year_from_file),
                        )
                        if (
                            re.search(
                                str(release_year_from_file),
                                item,
                                re.IGNORECASE,
                            )
                            or score >= required_similarity_score
                            or re.search(r"([\[\(\{]\d{4}[\]\)\}])", item)
                        ):
                            file.extras.remove(item)
                if (
                    move_release_group_to_end_of_file_name
                    and file.release_group
                    and file.release_group != publisher
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
                        if (
                            re.search(
                                rf"{left_brackets}{item_escaped}{right_brackets}",
                                file.release_group,
                                re.IGNORECASE,
                            )
                            or score >= release_group_similarity_score
                        ):
                            file.extras.remove(item)
                if len(file.extras) != 0:
                    for extra in file.extras:
                        rename += " " + extra
                if move_release_group_to_end_of_file_name:
                    release_group_escaped = None
                    if file.release_group:
                        release_group_escaped = re.escape(file.release_group)
                    if release_group_escaped and not re.search(
                        rf"\b{release_group_escaped}\b", rename, re.IGNORECASE
                    ):
                        if file.extension == ".cbz":
                            rename += " (" + file.release_group + ")"
                        elif file.extension == ".epub":
                            rename += " [" + file.release_group + "]"
                rename += file.extension
                processed_files.append(rename)
                if file.name != rename:
                    try:
                        print("\n\t\tOriginal: " + file.name)
                        print("\t\tRename:   " + rename)
                        if not manual_rename:
                            rename_file(
                                file.path,
                                os.path.join(file.root, rename),
                                file.root,
                                file.extensionless_name,
                                get_extensionless_name(rename),
                            )
                            send_message(
                                "\n\t\tRenamed: " + file.name + " to \n\t\t" + rename,
                                discord=False,
                            )
                            if not mute_discord_rename_notifications:
                                send_discord_message(
                                    None,
                                    "Reorganized & Renamed File",
                                    color=8421504,
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
                        else:
                            user_input = input("\tReorganize & Rename (y or n): ")
                            if (
                                user_input.lower().strip() == "y"
                                or user_input.lower().strip() == "yes"
                            ):
                                if not os.path.isfile(os.path.join(file.root, rename)):
                                    rename_file(
                                        file.path,
                                        os.path.join(file.root, rename),
                                        file.root,
                                        file.extensionless_name,
                                        get_extensionless_name(rename),
                                    )
                                    send_message(
                                        "\n\t\tReorganized & Renamed File: "
                                        + file.name
                                        + " to \n\t\t"
                                        + rename
                                        + "\n",
                                        discord=False,
                                    )
                                    if not mute_discord_rename_notifications:
                                        send_discord_message(
                                            None,
                                            "Reorganized & Renamed File",
                                            color=8421504,
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
                                else:
                                    print(
                                        "\t\tFile already exists, skipping rename of "
                                        + file.name
                                        + " to "
                                        + rename
                                        + " and deleting "
                                        + file.name
                                    )
                                    remove_file(file.path)
                        if file.file_type == "volume":
                            file.volume_number = remove_everything_but_volume_num(
                                [rename]
                            )
                            file.series_name = get_series_name_from_file_name(
                                rename, file.root
                            )
                        elif file.file_type == "chapter":
                            file.volume_number = remove_everything_but_volume_num(
                                [rename], chapter=True
                            )
                            file.series_name = get_series_name_from_file_name_chapter(
                                rename, file.volume_number
                            )
                        file.volume_year = get_volume_year(rename)
                        file.name = rename
                        file.extensionless_name = get_extensionless_name(rename)
                        file.basename = os.path.basename(rename)
                        file.path = os.path.join(file.root, rename)
                        file.extensionless_path = os.path.splitext(file.path)[0]
                        if file.file_type == "volume":
                            file.extras = get_extras(rename)
                        elif file.file_type == "chapter":
                            file.extras = get_extras(rename, chapter=True)
                    except OSError as ose:
                        send_message(ose, error=True)
        except Exception as e:
            send_message(
                "Failed to Reorganized & Renamed File: "
                + file.name
                + ": "
                + str(e)
                + " with reoganize_and_rename",
                error=True,
            )


# Replaces any pesky double spaces
def remove_dual_space(s):
    return re.sub("(\s{2,})", " ", s)


# Removes common words to improve string matching accuracy between a series_name
# from a file name, and a folder name, useful for when releasers sometimes include them,
# and sometimes don't.
def normalize_string_for_matching(s):
    if len(s) > 1:
        words_to_remove = []
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
        editions = [
            "Collection",
            "Master Edition",
            "Edition",
            "Exclusive",
            "Anniversary",
            "Deluxe",
            "Omnibus",
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
        type_keywords = [
            "Novel",
            "Light Novel",
            "Manga",
            "Comic",
            "LN",
            "Series",
            "Volume",
            "Chapter",
            "Book",
            "MANHUA",
        ]
        words_to_remove.extend(type_keywords)
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
            "no",
            "ne",
            "yo",
        ]
        words_to_remove.extend(japanese_particles)
        misc_words = [
            "((\d+)([-_. ]+)?th)",
            "x",
            "×",
        ]
        words_to_remove.extend(misc_words)
        for word in words_to_remove:
            s = re.sub(rf"\b{word}\b", " ", s, flags=re.IGNORECASE).strip()
            s = remove_dual_space(s)
    return s.strip()


# Returns a string without punctuation.
def remove_punctuation(s, disable_lang=False):
    s = re.sub(r":", "", s)
    language = ""
    if not disable_lang and not s.isdigit():
        language = detect_language(s)
    if language and language != "en" and not disable_lang:
        return remove_dual_space(
            normalize_string_for_matching(re.sub(r"[^\w\s+]", " ", s))
        )
    else:
        return convert_to_ascii(
            unidecode(
                remove_dual_space(
                    normalize_string_for_matching(re.sub(r"[^\w\s+]", " ", s))
                )
            )
        )


# detect language of the passed string using langdetect
def detect_language(s):
    language = ""
    if s:
        try:
            language = detect(s)
        except Exception as e:
            send_message(e, error=True)
            return language
    return language


# convert string to acsii
def convert_to_ascii(s):
    return "".join(i for i in s if ord(i) < 128)


# convert array to string separated by whatever is passed in the separator parameter
def array_to_string(array, separator):
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


# gets the toc.xhtml or copyright.xhtml file from the epub file and checks for premium content
def get_toc_or_copyright(file):
    bonus_content_found = False
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
                if search:
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
    existing_root, dir, file, similarity_strings=None, cache=False, isbn=False
):
    global moved_files
    global new_volume_webhook
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
    cbz_percent_download_folder = get_percent_for_folder([file.name], extension=".cbz")
    cbz_percent_existing_folder = get_percent_for_folder(
        [f.name for f in clean_existing], extension=".cbz"
    )
    epub_percent_download_folder = get_percent_for_folder(
        [file.name], extension=".epub"
    )
    epub_percent_existing_folder = get_percent_for_folder(
        [f.name for f in clean_existing], extension=".epub"
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
    print("\t\tDownload Folder CBZ Percent: {}%".format(cbz_percent_download_folder))
    print("\t\tExisting Folder CBZ Percent: {}%".format(cbz_percent_existing_folder))
    print(
        "\n\t\tDownload Folder EPUB Percent: {}%".format(epub_percent_download_folder)
    )
    print("\t\tExisting Folder EPUB Percent: {}%".format(epub_percent_existing_folder))
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
            (cbz_percent_download_folder and cbz_percent_existing_folder)
            >= required_matching_percentage
        )
        or (
            (epub_percent_download_folder and epub_percent_existing_folder)
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
        if resturcture_when_renaming:
            reorganize_and_rename(download_dir_volumes, existing_dir)
        fields = []
        if similarity_strings:
            if not isbn:
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
                        "value": "```>=" + str(similarity_strings[3]) + "```",
                        "inline": True,
                    },
                ]
            else:
                if similarity_strings and len(similarity_strings) >= 2:
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
        if cache:
            send_message(
                "\n\t\tFound existing series from cache: " + existing_dir, discord=False
            )
            if fields:
                send_discord_message(
                    None, "Found Series Match (CACHE)", color=8421504, fields=fields
                )
        elif isbn:
            send_message("\n\t\tFound existing series: " + existing_dir, discord=False)
            if fields:
                send_discord_message(
                    None,
                    "Found Series Match (Matching Identifier)",
                    color=8421504,
                    fields=fields,
                )
        else:
            send_message("\n\t\tFound existing series: " + existing_dir, discord=False)
            if fields:
                send_discord_message(
                    None, "Found Series Match", color=8421504, fields=fields
                )
        remove_duplicate_releases_from_download(
            clean_existing,
            download_dir_volumes,
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
                    + array_to_string(volume.volume_number, ",")
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
                        "value": "```"
                        + array_to_string(volume.volume_number, ",")
                        + "```",
                        "inline": False,
                    },
                    {
                        "name": volume.file_type.capitalize() + " Name",
                        "value": "```" + volume.name + "```",
                        "inline": False,
                    },
                ]
                if volume.volume_part:
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
                green_color = 65280
                move_status = move_file(volume, existing_dir)
                if move_status:
                    check_and_delete_empty_folder(volume.root)
                    volume.extensionless_path = get_extensionless_name(
                        os.path.join(existing_dir, volume.name)
                    )
                    volume.path = os.path.join(existing_dir, volume.name)
                    volume.root = existing_dir
                    moved_files.append(volume)
                if volume.file_type == "volume":
                    send_discord_message(
                        None,
                        title,
                        color=green_color,
                        fields=fields,
                        image_local=cover,
                        passed_webhook=new_volume_webhook,
                    )
                elif volume.file_type == "chapter" and new_volume_webhook:
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
                elif volume.file_type == "chapter" and not new_volume_webhook:
                    send_discord_message(
                        None,
                        title,
                        color=green_color,
                        fields=fields,
                        image_local=cover,
                    )
                return True
        else:
            check_and_delete_empty_folder(file.root)
            return True
    else:
        print("\t\tNo match found.")
        return False


# remove duplicates elements from the passed in list
def remove_duplicates(items):
    return list(dict.fromkeys(items))


# Return the zip comment for the passed zip file
def get_zip_comment(zip_file):
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            if zip_ref.comment:
                return zip_ref.comment.decode("utf-8")
            else:
                return ""
    except Exception as e:
        send_message(str(e), error=True)
        send_message("\tFailed to get zip comment for: " + zip_file, error=True)
        write_to_file("errors.txt", str(e))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return ""


# Removes bracketed content from the string, alongwith any whitespace.
# As long as the bracketed content is not immediately preceded or followed by a dash.
def remove_bracketed_info_from_name(string):
    # Use a while loop to repeatedly apply the regular expression to the string and remove the matched bracketed content
    while True:
        # The regular expression matches any substring enclosed in brackets and not immediately preceded or followed by a dash, along with the surrounding whitespace characters
        match = re.search(r"(?<!-)\s*([\(\[\{][^\)\]\}]+[\)\]\}])\s*(?!-)", string)

        # If there are no more matches, exit the loop
        if not match:
            break

        # Replace the first set of brackets and their contents, along with the surrounding whitespace characters, with an empty string
        string = re.sub(
            r"(?<!-)\s*([\(\[\{][^\)\]\}]+[\)\]\}])\s*(?!-)", " ", string, 1
        )

    # Remove all whitespace characters from the right side of the string
    string = string.rstrip()

    # Remove any space before the extension from having removed bracketed content
    string = re.sub(r"\s\.(\w+)$", r".\1", string)

    # Return the modified string
    return string.strip()


# Checks for any duplicate releases and deletes the lower ranking one.
def check_for_duplicate_volumes(paths_to_search=[]):
    try:
        for p in paths_to_search:
            if os.path.exists(p):
                print("\nSearching " + p + " for duplicate releases...")
                for root, dirs, files in scandir.walk(p):
                    print("\t" + root)
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
                        and (fo.number != "" and compare.number != "")
                        and fo.number == compare.number
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
                        and v.volume_number == compare.volume_number
                        and v.volume_part == compare.volume_part
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
                                    and x.volume_number == file.volume_number
                                    and x.volume_part == file.volume_part
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
                                                        file.volume_number != ""
                                                        and compare_file.volume_number
                                                        != ""
                                                    )
                                                    and file.volume_number
                                                    == compare_file.volume_number
                                                    and file.volume_part
                                                    == compare_file.volume_part
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
                                                        send_discord_message(
                                                            None,
                                                            "Duplicate Download Release (NOT UPGRADE)",
                                                            color=16776960,
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
                                                        if not manual_delete:
                                                            remove_file(
                                                                duplicate_file.path
                                                            )
                                                        elif (
                                                            input(
                                                                "\t\t\t\tDelete: "
                                                                + duplicate_file.name
                                                                + "? (y/n): "
                                                            )
                                                            == "y"
                                                        ):
                                                            remove_file(
                                                                duplicate_file.path
                                                            )
                                                        else:
                                                            send_message(
                                                                "\t\t\t\tBased on user input, Skipping: "
                                                                + duplicate_file.name
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
                                                        send_discord_message(
                                                            None,
                                                            "Duplicate Download Release (REQUIRES MANUAL DECISION)",
                                                            color=16776960,
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
                                                        print("\t\t\t\t\tSkipping...")
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
    except Exception as e:
        send_message("\n\t\tError: " + str(e), error=True)


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
        for item in array_list:
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


# Checks for an existing series by pulling the series name from each elidable file in the downloads_folder
# and comparing it to an existin folder within the user's library.
def check_for_existing_series():
    global cached_paths
    global cached_identifier_results
    global messages_to_send
    global paths_with_types
    if download_folders:
        print("\nChecking download folders for items to match to existing library...")
        for download_folder in download_folders:
            if os.path.exists(download_folder):
                # an array of unmatched items, used for skipping subsequent series
                # items that won't match
                unmatched_series = []
                for root, dirs, files in scandir.walk(download_folder):
                    print("\n" + root)
                    clean = clean_and_sort(root, files, dirs)
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
                        if (
                            file.name in processed_files or not processed_files
                        ) and os.path.isfile(file.path):
                            if unmatched_series and (
                                (
                                    not match_through_isbn_or_series_id
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
                                and match_through_isbn_or_series_id
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
                                            os.path.basename(cached_identifier.path),
                                            file,
                                            similarity_strings=cached_identifier.matches,
                                            isbn=True,
                                        )
                                        if cached_identifier.path not in cached_paths:
                                            cached_paths.append(cached_identifier.path)
                                            write_to_file(
                                                "cached_paths.txt",
                                                cached_identifier.path,
                                                without_date=True,
                                                check_for_dup=True,
                                            )
                                        found = True
                                        break
                                if found:
                                    continue
                            if cached_paths:
                                if exclude:
                                    cached_paths = organize_array_list_by_first_letter(
                                        cached_paths, file.name, 1, exclude
                                    )
                                else:
                                    cached_paths = organize_array_list_by_first_letter(
                                        cached_paths, file.name, 1
                                    )
                            downloaded_file_series_name = (
                                (str(file.series_name)).lower()
                            ).strip()
                            downloaded_file_series_name = (
                                (
                                    replace_underscore_in_name(
                                        remove_punctuation(downloaded_file_series_name)
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
                                    cached_paths = organize_array_list_by_first_letter(
                                        cached_paths,
                                        downloaded_file_series_name,
                                        2,
                                        exclude,
                                    )
                                else:
                                    cached_paths = organize_array_list_by_first_letter(
                                        cached_paths,
                                        downloaded_file_series_name,
                                        2,
                                    )
                            done = False
                            if cached_paths:
                                print("\n\tChecking path types...")
                                for p in cached_paths:
                                    if paths_with_types:
                                        skip_cached_path = False
                                        for item in paths_with_types:
                                            if p.startswith(item.path):
                                                if (
                                                    file.file_type
                                                    not in item.path_types
                                                ):
                                                    print(
                                                        "\t\tSkipping: "
                                                        + p
                                                        + " - Path: "
                                                        + str(item.path_types)
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
                                                    + str(successful_similarity_score)
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
                                            )
                                            if done:
                                                if p not in cached_paths:
                                                    cached_paths.append(p)
                                                    write_to_file(
                                                        "cached_paths.txt",
                                                        p,
                                                        without_date=True,
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
                                continue
                            download_file_zip_comment = get_zip_comment(file.path)
                            download_file_meta = None
                            if download_file_zip_comment and re.search(
                                r"Identifiers", download_file_zip_comment, re.IGNORECASE
                            ):
                                # split on Identifiers: and only keep the second half
                                download_file_zip_comment = (
                                    download_file_zip_comment.split("Identifiers:")[1]
                                ).strip()
                                if re.search(r",", download_file_zip_comment):
                                    download_file_meta = (
                                        download_file_zip_comment.split(",")
                                    )
                                else:
                                    download_file_meta = [
                                        download_file_zip_comment,
                                    ]
                                if download_file_meta:
                                    download_file_meta = [
                                        x
                                        for x in download_file_meta
                                        if not re.search(r"NONE", x, re.IGNORECASE)
                                    ]
                                # strip whitespace from each item in the list
                                download_file_meta = [
                                    x.strip() for x in download_file_meta
                                ]
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
                                                    not in item.path_types
                                                ):
                                                    print(
                                                        "\nSkipping path: "
                                                        + path
                                                        + " - Path: "
                                                        + str(item.path_types)
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
                                                        + str(item.path_extensions)
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
                                                dirs = (
                                                    organize_array_list_by_first_letter(
                                                        dirs,
                                                        file.series_name,
                                                        1,
                                                        exclude=exclude,
                                                    )
                                                )
                                                dirs = (
                                                    organize_array_list_by_first_letter(
                                                        dirs,
                                                        file.series_name,
                                                        2,
                                                        exclude=exclude,
                                                    )
                                                )
                                                reorganized = True
                                            if (
                                                not match_through_isbn_or_series_id
                                                or file.file_type == "chapter"
                                            ) and root in cached_paths:
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
                                                os.path.basename(os.path.dirname(root)),
                                                os.path.basename(root),
                                                file_objects,
                                            )
                                            if (
                                                root not in cached_paths
                                                and root not in download_folders
                                            ):
                                                if (
                                                    cached_paths
                                                    and root not in cached_paths
                                                    and path not in download_folders
                                                    and root not in paths
                                                ):
                                                    write_to_file(
                                                        "cached_paths.txt",
                                                        root,
                                                        without_date=True,
                                                        check_for_dup=True,
                                                    )
                                                if done:
                                                    break
                                                print(
                                                    "\nLooking for: " + file.series_name
                                                )
                                                print(
                                                    "\tInside of: "
                                                    + folder_accessor.root
                                                )
                                                for dir in folder_accessor.dirs:
                                                    dir_position = (
                                                        folder_accessor.dirs.index(dir)
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
                                                    # print(similar.cache_info()) # only for testing
                                                    print(
                                                        "\n\t\t-(NOT CACHE)- "
                                                        + str(dir_position)
                                                        + " of "
                                                        + str(len(folder_accessor.dirs))
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
                                                                + str(similarity_score)
                                                                + " out of 1.0"
                                                            ),
                                                        )
                                                        print(
                                                            '\n\t\tSimilarity between: "'
                                                            + existing_series_folder_from_library
                                                            + '" and "'
                                                            + downloaded_file_series_name
                                                            + '" Score: '
                                                            + str(similarity_score)
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
                                                        )
                                                        if done:
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
                                                                    without_date=True,
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
                                                                != cached_paths[0]
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
                                            if (
                                                not done
                                                and match_through_isbn_or_series_id
                                                and root not in download_folders
                                                and download_file_meta
                                                and file.file_type == "volume"
                                            ):
                                                if folder_accessor.files:
                                                    if done:
                                                        break
                                                    for f in folder_accessor.files:
                                                        if (
                                                            f.extension
                                                            == file.extension
                                                        ):
                                                            existing_file_zip_comment = get_zip_comment(
                                                                f.path
                                                            )
                                                            existing_file_meta = None
                                                            if (
                                                                existing_file_zip_comment
                                                                and re.search(
                                                                    r"Identifiers",
                                                                    existing_file_zip_comment,
                                                                    re.IGNORECASE,
                                                                )
                                                            ):
                                                                # split on Identifiers: and only keep the second half
                                                                existing_file_zip_comment = (
                                                                    existing_file_zip_comment.split(
                                                                        "Identifiers:"
                                                                    )[
                                                                        1
                                                                    ]
                                                                ).strip()
                                                                if re.search(
                                                                    r",",
                                                                    existing_file_zip_comment,
                                                                ):
                                                                    existing_file_meta = existing_file_zip_comment.split(
                                                                        ","
                                                                    )
                                                                else:
                                                                    existing_file_meta = [
                                                                        existing_file_zip_comment
                                                                    ]
                                                            if existing_file_meta:
                                                                existing_file_meta = [
                                                                    x
                                                                    for x in existing_file_meta
                                                                    if not re.search(
                                                                        r"NONE",
                                                                        x,
                                                                        re.IGNORECASE,
                                                                    )
                                                                ]
                                                            if existing_file_meta:
                                                                found_existing_meta_match = (
                                                                    False
                                                                )
                                                                # strip whitespace from each item in the list
                                                                existing_file_meta = [
                                                                    x.strip()
                                                                    for x in existing_file_meta
                                                                ]
                                                                for (
                                                                    d_meta
                                                                ) in download_file_meta:
                                                                    if found_existing_meta_match:
                                                                        break
                                                                    for (
                                                                        e_meta
                                                                    ) in existing_file_meta:
                                                                        print(
                                                                            (
                                                                                "\t\t("
                                                                                + str(
                                                                                    d_meta
                                                                                )
                                                                                + " - "
                                                                                + str(
                                                                                    e_meta
                                                                                )
                                                                                + ")"
                                                                            ),
                                                                            end="\r",
                                                                        )
                                                                        if (
                                                                            d_meta
                                                                            == e_meta
                                                                            and f.root
                                                                            not in directories_found
                                                                        ):
                                                                            directories_found.append(
                                                                                f.root
                                                                            )
                                                                            matched_ids.append(
                                                                                download_file_meta
                                                                            )
                                                                            matched_ids.append(
                                                                                existing_file_meta
                                                                            )
                                                                            found_existing_meta_match = (
                                                                                True
                                                                            )
                                                                            break

                                    except Exception as e:
                                        send_message(e, error=True)
                            if (
                                not done
                                and match_through_isbn_or_series_id
                                and file.file_type == "volume"
                            ):
                                if directories_found:
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
                                        )
                                        if done:
                                            if directories_found[0] not in cached_paths:
                                                cached_paths.append(
                                                    directories_found[0]
                                                )
                                                write_to_file(
                                                    "cached_paths.txt",
                                                    directories_found[0],
                                                    without_date=True,
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
    if messages_to_send:
        grouped_by_series_names = []
        # go through messages_to_send and group them by series name,
        # one group per series name and each group will contian all the messages for that series
        for message in messages_to_send:
            if grouped_by_series_names:
                found = False
                for group in grouped_by_series_names:
                    if message.series_name == group["series_name"]:
                        group["messages"].append(message)
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
        messages_to_send = []
        if grouped_by_series_names:
            # sort them alphabetically by series name
            grouped_by_series_names.sort(key=lambda x: x["series_name"])
            for group in grouped_by_series_names:
                # sort the group's messages lowest to highest by the number field
                # the number can be a float or an array of floats
                group["messages"].sort(key=lambda x: x.fields[0]["value"].split(",")[0])
                if output_chapter_covers_to_discord:
                    for message in group["messages"][:]:
                        cover = find_and_extract_cover(
                            message.volume_obj, return_data_only=True
                        )
                        if cover:
                            send_discord_message(
                                None,
                                message.title,
                                color=message.color,
                                fields=message.fields,
                                image_local=cover,
                                passed_webhook=message.webhook,
                            )
                            group["messages"].remove(message)
                        else:
                            send_discord_message(
                                None,
                                message.title,
                                color=message.color,
                                fields=message.fields,
                                passed_webhook=message.webhook,
                            )
                else:
                    volume_numbers_mts = []
                    volume_names_mts = []
                    title = group["messages"][0].fields[0]["name"]
                    title_2 = group["messages"][0].fields[1]["name"] + "(s)"
                    series_name = group["messages"][0].series_name
                    for message in group["messages"]:
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
                        send_discord_message(
                            None,
                            group["messages"][0].title + "(s)",
                            color=group["messages"][0].color,
                            fields=new_fields,
                            passed_webhook=group["messages"][0].webhook,
                        )


# Removes any unnecessary junk through regex in the folder name and returns the result
# !OLD METHOD!: Only used for cleaning a folder name as a backup if no volumes were found inside the folder
# when renaming folders in the dowload directory.
def get_series_name(dir):
    global volume_regex_keywords
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
def rename_dirs_in_download_folder():
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
                clean = clean_and_sort(
                    download_folder, download_folder_files, download_folder_dirs
                )
                download_folder_files, download_folder_dirs = clean[0], clean[1]
                global folder_accessor
                global volume_regex_keywords
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
                            print("\n\tBEFORE: " + folderDir)
                            print("\tAFTER:  " + volume_one.series_name)
                            if volumes:
                                print("\t\tVOLUMES:")
                                for v in volumes:
                                    print("\t\t\t" + v.name)
                            user_input = ""
                            if manual_rename:
                                user_input = input(
                                    "\nRename (y or n or i (input rename all volumes' series names and folder) ): "
                                )
                            else:
                                user_input = "y"
                            try:
                                if user_input.lower() == "y":
                                    # if the direcotry doesn't exist, then rename to it
                                    if not os.path.exists(
                                        os.path.join(
                                            folder_accessor.root,
                                            volume_one.series_name,
                                        )
                                    ):
                                        try:
                                            os.rename(
                                                os.path.join(
                                                    folder_accessor.root, folderDir
                                                ),
                                                os.path.join(
                                                    folder_accessor.root,
                                                    volume_one.series_name,
                                                ),
                                            )
                                            done = True
                                            print(
                                                "\t\tRenamed: "
                                                + folderDir
                                                + " to "
                                                + volume_one.series_name
                                                + "\n"
                                            )
                                        except Exception as e:
                                            print(
                                                "\t\tCould not rename "
                                                + folderDir
                                                + " to "
                                                + volume_one.series_name
                                            )
                                            print(e)
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
                                                )
                                            else:
                                                print(
                                                    "\t\t"
                                                    + v.name
                                                    + " already exists in "
                                                    + volume_one.series_name
                                                )
                                                remove_file(v.path)
                                        # check for an empty folder, and delete it if it is
                                        check_and_delete_empty_folder(v.root)
                                        done = True
                                elif user_input.lower() == "i":
                                    print("\tInput mode selected.")
                                    print(
                                        "\n\tWARNING: This will rename all voluems with similar series names and the folder name to the user inputted series name"
                                    )
                                    print(
                                        "\tONLY USE IF YOU KNOW WHAT YOU ARE DOING, otherwise enter nothing or 'q' to quit"
                                    )
                                    print(
                                        "\n\tCurrent Series Name: "
                                        + volume_one.series_name
                                    )
                                    series_user_input = input(
                                        "\tReplacement Series Name: "
                                    )
                                    if (
                                        series_user_input != ""
                                        and series_user_input != "q"
                                    ):
                                        if len(volumes) > 1:
                                            matching.append(volumes[0])
                                        for v in matching:
                                            new_file_name = re.sub(
                                                v.series_name,
                                                series_user_input,
                                                v.name,
                                            )
                                            new_file_path = os.path.join(
                                                v.root, new_file_name
                                            )
                                            if not os.path.isfile(new_file_path):
                                                rename_file(
                                                    v.path,
                                                    new_file_path,
                                                    v.root,
                                                    v.extensionless_name,
                                                    get_extensionless_name(
                                                        new_file_name
                                                    ),
                                                )
                                            else:
                                                print(
                                                    "\t\t"
                                                    + new_file_name
                                                    + " already exists."
                                                )
                                        # if the folder doesn't already exist, rename it to series_user_input
                                        if volume_one.root != os.path.join(
                                            download_folder, series_user_input
                                        ):
                                            if not os.path.isdir(
                                                os.path.join(
                                                    download_folder,
                                                    series_user_input,
                                                )
                                            ):
                                                os.rename(
                                                    volume_one.root,
                                                    os.path.join(
                                                        download_folder,
                                                        series_user_input,
                                                    ),
                                                )
                                            else:
                                                print(
                                                    "\t\tFolder: "
                                                    + os.path.join(
                                                        download_folder,
                                                        series_user_input,
                                                    )
                                                    + " already exists."
                                                )
                                    done = True
                                else:
                                    print("Skipping...")
                            except Exception as e:
                                print(e)
                                print("Skipping...")
                    if not done:
                        download_folder_basename = os.path.basename(download_folder)
                        if re.search(
                            download_folder_basename, full_file_path, re.IGNORECASE
                        ):
                            if (
                                re.search(
                                    r"((\s\[|\]\s)|(\s\(|\)\s)|(\s\{|\}\s))",
                                    folderDir,
                                    re.IGNORECASE,
                                )
                                or re.search(r"(\s-\s|\s-)$", folderDir, re.IGNORECASE)
                                or re.search(r"(\bLN\b)", folderDir, re.IGNORECASE)
                                or re.search(
                                    r"(\b|\s)((\s|)-(\s|)|)(Part|)(%s|)(\.|)([-_. ]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\b|\s)"
                                    % volume_regex_keywords,
                                    folderDir,
                                    re.IGNORECASE,
                                )
                                or re.search(r"\bPremium\b", folderDir, re.IGNORECASE)
                                or re.search(r":", folderDir, re.IGNORECASE)
                                or re.search(r"([A-Za-z])(_)", folderDir, re.IGNORECASE)
                                or re.search(r"([?])", folderDir)
                            ):
                                dir_clean = get_series_name(folderDir)
                                dir_clean = re.sub(r"([A-Za-z])(_)", r"\1 ", dir_clean)
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
                                    print("\tBEFORE: " + folderDir)
                                    print("\tAFTER:  " + dir_clean + "\n")
                                    user_input = ""
                                    if manual_rename:
                                        user_input = input("Rename (y or n): ")
                                    else:
                                        user_input = "y"
                                    try:
                                        if user_input.lower().strip() == "y":
                                            try:
                                                os.rename(
                                                    os.path.join(
                                                        folder_accessor.root,
                                                        folderDir,
                                                    ),
                                                    os.path.join(
                                                        folder_accessor.root,
                                                        dir_clean,
                                                    ),
                                                )
                                            except Exception as e:
                                                send_message(
                                                    "Error renaming folder: " + str(e),
                                                    error=True,
                                                )
                                        else:
                                            continue
                                    except OSError as e:
                                        send_message(e, error=True)
                                elif (
                                    os.path.isdir(
                                        os.path.join(folder_accessor.root, dir_clean)
                                    )
                                    and dir_clean != ""
                                ):
                                    if os.path.join(
                                        folder_accessor.root, folderDir
                                    ) != os.path.join(folder_accessor.root, dir_clean):
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
                                                os.path.basename(os.path.dirname(root)),
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
            except Exception as e:
                send_message(e, error=True)
        else:
            if download_folder == "":
                send_message("\nERROR: Path cannot be empty.", error=True)
            else:
                send_message(
                    "\nERROR: " + download_folder + " is an invalid path.\n", error=True
                )


def get_extras(file_name, chapter=False, series_name=""):
    extension = get_file_extension(file_name)
    if (
        re.search(re.escape(series_name), file_name, re.IGNORECASE)
        and series_name != ""
    ):
        file_name = re.sub(
            re.escape(series_name), "", file_name, flags=re.IGNORECASE
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
    modifiers = {".epub": "[%s]", ".cbz": "(%s)"}
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
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        list = zip_ref.namelist()
        for name in list:
            if name.lower() == "ComicInfo.xml".lower():
                return True
    return False


# Retrieve the file specified from the zip file and return the data for it.
def get_file_from_zip(zip_file, file_name, allow_base=True):
    result = None
    try:
        with zipfile.ZipFile(zip_file, "r") as z:
            # Iterate through all the files in the zip
            for info in z.infolist():
                if allow_base:
                    # Check the base name of the file
                    if os.path.basename(info.filename).lower() == file_name.lower():
                        # Read the contents of the file
                        result = z.read(info)
                        break
                else:
                    # Check the entire path of the file
                    if info.filename.lower() == file_name.lower():
                        # Read the contents of the file
                        result = z.read(info)
                        break
    except (zipfile.BadZipFile, FileNotFoundError) as e:
        send_message(e, error=True)
        send_message("Attempted to read file: " + file_name, error=True)
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
            send_message(e, error=True)
            send_message("Attempted to parse comicinfo.xml", error=True)
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
def rename_files_in_download_folders(only_these_files=[]):
    global manual_rename
    global cached_paths
    global chapter_searches
    print("\nSearching for files to rename...")
    for path in download_folders:
        if os.path.exists(path):
            for root, dirs, files in scandir.walk(path):
                if (
                    root not in cached_paths
                    and root not in download_folders
                    and root not in paths
                    and path not in download_folders
                    and check_for_existing_series_toggle
                ):
                    write_to_file(
                        "cached_paths.txt", root, without_date=True, check_for_dup=True
                    )
                clean = clean_and_sort(root, files, dirs)
                files, dirs = clean[0], clean[1]
                if not files:
                    continue
                volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(
                        [f for f in files if os.path.isfile(os.path.join(root, f))],
                        root,
                    )
                )
                print("\t" + root)
                for file in volumes:
                    if (
                        file.file_type == "chapter"
                        and not rename_chapters_with_preferred_chapter_keyword
                    ):
                        continue
                    no_keyword = False
                    preferred_naming_format = preferred_volume_renaming_format
                    keywords = volume_regex_keywords
                    result_two = None
                    if file.file_type == "chapter":
                        keywords = chapter_regex_keywords
                        preferred_naming_format = preferred_chapter_renaming_format
                    if only_these_files and file.name not in only_these_files:
                        continue
                    try:
                        result = re.search(
                            r"(\s+)?\-?(\s+)?(%s)(\.\s?|\s?|)([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?(\]|\)|\})?(\s|巻?\.epub|巻?\.cbz)"
                            % keywords,
                            file.name,
                            re.IGNORECASE,
                        )
                        if (
                            not result
                            and file.file_type == "chapter"
                            and (
                                only_has_one_set_of_numbers(
                                    remove_bracketed_info_from_name(file.name)
                                )
                                or (
                                    not re.search(
                                        "(0+)?"
                                        + str(
                                            set_num_as_float_or_int(file.volume_number)
                                        ),
                                        file.series_name,
                                        re.IGNORECASE,
                                    )
                                    and only_has_one_set_of_numbers(
                                        remove_bracketed_info_from_name(
                                            re.sub(
                                                file.series_name,
                                                "",
                                                file.name,
                                                flags=re.IGNORECASE,
                                            )
                                        )
                                    )
                                )
                            )
                        ):
                            for regex in chapter_searches:
                                result = re.search(regex, file.name, re.IGNORECASE)
                                if result:
                                    result = chapter_file_name_cleaning(
                                        result.group(), skip=True
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
                                r = r.strip()
                                if r == "" or r == ".":
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
                                            volume_numbers = (
                                                convert_list_of_numbers_to_array(r)
                                            )
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
                                                print(ve)
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
                                zfill_int = 2  # 01
                                zfill_float = 4  # 01.5
                                if file.file_type == "chapter":
                                    zfill_int = 3  # 001
                                    zfill_float = 5  # 001.5
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
                                    file.extension == ".cbz"
                                    and add_issue_number_to_cbz_file_name
                                    and file.file_type == "volume"
                                ):
                                    combined += " " + "#" + without_keyword
                                elif (
                                    file.extension == ".epub"
                                    and search_and_add_premium_to_file_name
                                ):
                                    if not re.search(
                                        r"\bPremium\b", file.name, re.IGNORECASE
                                    ) and (
                                        check_for_bonus_xhtml(file.path)
                                        or get_toc_or_copyright(file.path)
                                    ):
                                        print(
                                            "\n\t\tBonus content found inside epub, adding [Premium] to file name."
                                        )
                                        combined += " [Premium]"
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
                                        optional_following_zero = r"(0+)?"
                                        replacement = re.sub(
                                            optional_following_zero
                                            + str(converted_value),
                                            " "
                                            + preferred_naming_format
                                            + str(converted_and_filled),
                                            file.name,
                                            flags=re.IGNORECASE,
                                            count=1,
                                        )
                                        replacement = remove_dual_space(replacement)
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
                                        r"(.epub|.cbz)",
                                        "",
                                        file.basename,
                                        flags=re.IGNORECASE,
                                    ).strip()
                                    replacement = base + " " + combined
                                    if file.volume_year:
                                        replacement += (
                                            " (" + str(file.volume_year) + ")"
                                        )
                                    extras = get_extras(file.name)
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
                                    try:
                                        if not (
                                            os.path.isfile(
                                                os.path.join(root, replacement)
                                            )
                                        ):
                                            user_input = ""
                                            print("\n\t\tBEFORE: " + file.name)
                                            print("\t\tAFTER:  " + replacement)
                                            if not manual_rename:
                                                user_input = "y"
                                            else:
                                                user_input = input(
                                                    "\t\tRename (y or n): "
                                                )
                                            if user_input == "y":
                                                try:
                                                    os.rename(
                                                        file.path,
                                                        os.path.join(root, replacement),
                                                    )
                                                except OSError as e:
                                                    send_message(
                                                        e,
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
                                                        "\t\t\tSuccessfully renamed file: \n\t\t"
                                                        + file.name
                                                        + " to "
                                                        + replacement,
                                                        discord=False,
                                                    )
                                                    if (
                                                        not mute_discord_rename_notifications
                                                    ):
                                                        send_discord_message(
                                                            None,
                                                            "Renamed File",
                                                            color=8421504,
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
                                                    for (
                                                        image_extension
                                                    ) in image_extensions:
                                                        image_file = (
                                                            file.extensionless_name
                                                            + image_extension
                                                        )
                                                        if os.path.isfile(
                                                            os.path.join(
                                                                root, image_file
                                                            )
                                                        ):
                                                            extensionless_replacement = get_extensionless_name(
                                                                replacement
                                                            )
                                                            replacement_image = (
                                                                extensionless_replacement
                                                                + image_extension
                                                            )
                                                            try:
                                                                os.rename(
                                                                    os.path.join(
                                                                        root, image_file
                                                                    ),
                                                                    os.path.join(
                                                                        root,
                                                                        replacement_image,
                                                                    ),
                                                                )
                                                            except OSError as ose:
                                                                send_message(
                                                                    ose, error=True
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
                                            # if it already exists, then delete file.name
                                            print(
                                                "\n\tFile already exists: "
                                                + os.path.join(root, replacement)
                                                + "\n\t\twhen renaming: "
                                                + file.name
                                                + "\n\tDeleting: "
                                                + file.name
                                            )
                                            remove_file(file.path)
                                            continue
                                    except OSError as ose:
                                        send_message(ose, error=True)
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
                    if resturcture_when_renaming:
                        reorganize_and_rename([file], file.series_name)
        else:
            if path == "":
                print("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + path + " is an invalid path.\n")


# Checks for any exception keywords that will prevent the chapter release from being deleted.
def check_for_exception_keywords(file_name, exception_keywords):
    pattern = "|".join(exception_keywords)
    return bool(re.search(pattern, file_name, re.IGNORECASE))


# Deletes chapter files from the download folder.
def delete_chapters_from_downloads():
    try:
        for path in download_folders:
            if os.path.exists(path):
                os.chdir(path)
                for root, dirs, files in scandir.walk(path):
                    if (
                        root not in cached_paths
                        and root not in download_folders
                        and root not in paths
                        and path not in download_folders
                        and check_for_existing_series_toggle
                    ):
                        write_to_file(
                            "cached_paths.txt",
                            root,
                            without_date=True,
                            check_for_dup=True,
                        )
                    # clean = clean_and_sort(root, files, dirs)
                    # files, dirs = clean[0], clean[1]
                    dirs = remove_ignored_folder_names(dirs)
                    files = remove_hidden_files(files)
                    for file in files:
                        if (
                            contains_chapter_keywords(file)
                            and not contains_volume_keywords(file)
                        ) and not (
                            check_for_exception_keywords(file, exception_keywords)
                        ):
                            if file.endswith(".cbz"):
                                send_message(
                                    "\n\t\tFile: "
                                    + file
                                    + "\n\t\tLocation: "
                                    + root
                                    + "\n\t\tContains chapter keywords/lone numbers and does not contain any volume/exclusion keywords"
                                    + "\n\t\tDeleting chapter release.",
                                    discord=False,
                                )
                                send_discord_message(
                                    None,
                                    "Chapter Release Found",
                                    color=8421504,
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
                                remove_file(os.path.join(root, file))
                for root, dirs, files in scandir.walk(path):
                    clean_two = clean_and_sort(root, files, dirs)
                    files, dirs = clean_two[0], clean_two[1]
                    for dir in dirs:
                        check_and_delete_empty_folder(os.path.join(root, dir))
            else:
                if path == "":
                    print("\nERROR: Path cannot be empty.")
                else:
                    print("\nERROR: " + path + " is an invalid path.\n")
    except Exception as e:
        send_message(e, error=True)


# remove all non-images from list of files
def remove_non_images(files):
    clean_list = []
    for file in files:
        extension = get_file_extension(os.path.basename(file))
        if extension in image_extensions:
            clean_list.append(file)
    return clean_list


# Finds and extracts the internal cover from a cbz or epub file
def find_and_extract_cover(file, return_data_only=False):
    start_time = time.time()
    global blank_cover_required_similarity_score
    # check if the file is a valid zip file
    if zipfile.is_zipfile(file.path):
        epub_cover_path = ""
        if file.extension == ".epub":
            epub_cover_path = get_epub_cover(file.path)
            if epub_cover_path:
                epub_cover_path = os.path.basename(epub_cover_path)
                epub_cover_extension = get_file_extension(epub_cover_path)
                if epub_cover_extension not in image_extensions:
                    epub_cover_path = ""
        with zipfile.ZipFile(file.path, "r") as zip_ref:
            zip_list = zip_ref.namelist()
            zip_list = [
                x
                for x in zip_list
                if not os.path.basename(x).startswith(".")
                and not os.path.basename(x).startswith("__")
            ]
            zip_list = remove_non_images(zip_list)
            # remove anything that isn't a file
            zip_list = [
                x for x in zip_list if not x.endswith("/") and re.search(r"\.", x)
            ]
            # remove any non-supported image files from the list
            for item in zip_list:
                extension = get_file_extension(item)
                if extension not in image_extensions:
                    zip_list.remove(item)
            zip_list.sort()
            # parse zip_list and check each os.path.basename for epub_cover_path if epub_cover_path exists, then put it at the front of the list
            if epub_cover_path:
                for item in zip_list:
                    if os.path.basename(item) == epub_cover_path:
                        zip_list.remove(item)
                        zip_list.insert(0, item)
                        break
            cover_searches = [
                r"(cover\.([A-Za-z]+))$",
                r"(\b(Cover([0-9]+|)|CoverDesign|page([-_. ]+)?cover)\b)",
                r"(\b(p000|page_000)\b)",
                r"((\s+)0+\.(.{2,}))",
                r"(\bindex[-_. ]1[-_. ]1\b)",
                r"(9([-_. :]+)?7([-_. :]+)?(8|9)(([-_. :]+)?[0-9]){10})",
            ]
            image_data = None
            if zip_list and cover_searches:
                blank_images = []  # used to avoid comparing the same image twice
                global blank_white_image_path
                global blank_black_image_path
                for image_file in zip_list:
                    for search in cover_searches:
                        if (
                            epub_cover_path
                            and os.path.basename(image_file) == epub_cover_path
                        ) or re.search(
                            search, os.path.basename(image_file), re.IGNORECASE
                        ):
                            if (
                                compare_detected_cover_to_blank_image
                                and blank_white_image_path
                                and blank_black_image_path
                            ):
                                # read the image data from the zip file
                                print(
                                    "\t\tChecking if cover is blank on: " + image_file
                                )
                                image_data_for_sim_check = zip_ref.read(image_file)
                                ssim_score_white = prep_images_for_similarity(
                                    blank_white_image_path, image_data_for_sim_check
                                )
                                ssim_score_black = prep_images_for_similarity(
                                    blank_black_image_path, image_data_for_sim_check
                                )
                                if (
                                    ssim_score_white != None
                                    and ssim_score_black != None
                                ):
                                    if (
                                        ssim_score_white
                                        >= blank_cover_required_similarity_score
                                        or ssim_score_black
                                        >= blank_cover_required_similarity_score
                                    ):
                                        print(
                                            "\t\t\t\t"
                                            + str(ssim_score_white)
                                            + " >= "
                                            + str(blank_cover_required_similarity_score)
                                            + " and "
                                            + str(ssim_score_black)
                                            + " >= "
                                            + str(blank_cover_required_similarity_score)
                                        )
                                        print("\t\t\tCover is blank, skipping...")
                                        blank_images.append(image_file)
                                        break
                                else:
                                    print(
                                        "\t\t\tCould not compare cover to blank image."
                                    )
                                    break
                            print("\t\tCover Found: " + image_file)
                            image_extension = get_file_extension(
                                os.path.basename(image_file)
                            )
                            if image_extension == ".jpeg":
                                image_extension = ".jpg"
                            with zip_ref.open(image_file) as image_file_ref:
                                # save image_file_ref as file.extensionless_name + image_extension to file.root
                                if not return_data_only:
                                    with open(
                                        os.path.join(
                                            file.root,
                                            file.extensionless_name + image_extension,
                                        ),
                                        "wb",
                                    ) as image_file_ref_out:
                                        image_file_ref_out.write(image_file_ref.read())
                                else:
                                    image_data = image_file_ref.read()
                            if compress_image_option or return_data_only:
                                if not return_data_only:
                                    compress_image(
                                        os.path.join(
                                            file.root,
                                            file.extensionless_name + image_extension,
                                        )
                                    )
                                    return file.extensionless_path + image_extension
                                elif return_data_only and image_data:
                                    compress_result_data = compress_image(
                                        os.path.join(
                                            file.root,
                                            file.extensionless_name + image_extension,
                                        ),
                                        raw_data=image_data,
                                    )
                                    if compress_result_data:
                                        return compress_result_data
                                    else:
                                        return image_data
                                else:
                                    return None
                            elif not compress_image_option and not return_data_only:
                                return file.extensionless_path + image_extension
                default_cover_path = None
                if (
                    compare_detected_cover_to_blank_image
                    and blank_white_image_path
                    and blank_black_image_path
                ):
                    print("\n\t\tNo cover found, using first image that isn't blank...")
                    for test_file in zip_list:
                        if test_file in blank_images:
                            continue
                        print("\t\tChecking if cover is blank on: " + test_file)
                        ssim_score_white = prep_images_for_similarity(
                            blank_white_image_path, zip_ref.read(test_file)
                        )
                        ssim_score_black = prep_images_for_similarity(
                            blank_black_image_path, zip_ref.read(test_file)
                        )
                        if ssim_score_white != None and ssim_score_black != None:
                            if (
                                ssim_score_white
                                >= blank_cover_required_similarity_score
                                or ssim_score_black
                                >= blank_cover_required_similarity_score
                            ):
                                print(
                                    "\t\t\t\t"
                                    + str(ssim_score_white)
                                    + " >= "
                                    + str(blank_cover_required_similarity_score)
                                    + " and "
                                    + str(ssim_score_black)
                                    + " >= "
                                    + str(blank_cover_required_similarity_score)
                                )
                                print("\t\tCover is blank, skipping...")
                                continue
                            else:
                                print(
                                    "\n\t\tNon-Blank-Default Cover Found: " + test_file
                                )
                                default_cover_path = test_file
                                break
                        else:
                            print("\t\t\tCould not compare cover to blank image.")
                            continue
                else:
                    print(
                        "\t\tNo cover found, defaulting to first image: " + zip_list[0]
                    )
                    default_cover_path = zip_list[0]
                image_extension = get_file_extension(
                    os.path.basename(default_cover_path)
                )
                if image_extension == ".jpeg":
                    image_extension = ".jpg"
                with zip_ref.open(default_cover_path) as default_cover_ref:
                    # save image_file_ref as file.extensionless_name + image_extension to file.root
                    if not return_data_only:
                        with open(
                            os.path.join(
                                file.root,
                                file.extensionless_name + image_extension,
                            ),
                            "wb",
                        ) as default_cover_ref_out:
                            default_cover_ref_out.write(default_cover_ref.read())
                    else:
                        image_data = default_cover_ref.read()
                if compress_image_option or return_data_only:
                    if not return_data_only:
                        compress_image(
                            os.path.join(
                                file.root,
                                file.extensionless_name + image_extension,
                            )
                        )
                        return file.extensionless_path + image_extension
                    elif return_data_only and image_data:
                        compress_result_data = compress_image(
                            os.path.join(
                                file.root,
                                file.extensionless_name + image_extension,
                            ),
                            raw_data=image_data,
                        )
                        if compress_result_data:
                            return compress_result_data
                        else:
                            return image_data
                    else:
                        return None
    else:
        send_message("\nFile: " + file.name + " is not a valid zip file.", error=True)
    if output_execution_times:
        print_function_execution_time(start_time, "extract_cover_from_zip()")
    return False


# Extracts the covers out from our cbz and epub files
def extract_covers():
    global cached_paths
    print("\nLooking for covers to extract...")
    for path in paths:
        if os.path.exists(path):
            os.chdir(path)
            for root, dirs, files in scandir.walk(path):
                if (
                    root not in cached_paths
                    and root not in download_folders
                    and root not in paths
                    and path not in download_folders
                ):
                    write_to_file(
                        "cached_paths.txt", root, without_date=True, check_for_dup=True
                    )
                clean = clean_and_sort(root, files, dirs)
                files, dirs = clean[0], clean[1]
                global folder_accessor
                print("\nRoot: " + root)
                # print("Dirs: " + str(dirs))
                print("Files: " + str(files))
                if files:
                    folder_accessor = Folder(
                        root,
                        dirs,
                        os.path.basename(os.path.dirname(root)),
                        os.path.basename(root),
                        upgrade_to_file_class(files, root),
                    )
                    global image_count
                    start_time = time.time()
                    contains_volume_one = any(
                        file.file_type == "volume" and file.number == 1
                        for file in folder_accessor.files
                    )
                    if output_execution_times:
                        print_function_execution_time(start_time, "contains_volume_one")
                    start_time = time.time()
                    [
                        process_cover_extraction(file, contains_volume_one)
                        for file in folder_accessor.files
                        if file.file_type == "volume"
                        or (file.file_type == "chapter" and extract_chapter_covers)
                    ]
                    if output_execution_times:
                        print_function_execution_time(
                            start_time, "process_cover_extraction()"
                        )
        else:
            if path == "":
                print("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + path + " is an invalid path.\n")


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
                os.remove(webp_file_path)
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
                "ERROR: Could not convert " + webp_file_path + " to jpg", error=True
            )
            send_message("ERROR: " + str(e), error=True)
    return None


def process_cover_extraction(file, contains_volume_one):
    start_time = time.time()
    global image_count
    update_stats(file)
    try:
        has_cover = False
        printed = False
        cover = ""
        cover_start_time = time.time()
        cover = next(
            (
                file.extensionless_path + extension
                for extension in image_extensions
                if os.path.isfile(file.extensionless_path + extension)
            ),
            "",
        )
        if output_execution_times:
            print_function_execution_time(cover_start_time, "cover = next()")
        if cover:
            has_cover = True

        if not has_cover:
            not_has_cover_start_time = time.time()
            if not printed:
                print("\n\tFile: " + file.name)
                printed = True
            print("\t\tFile does not have a cover.")
            result = find_and_extract_cover(file)
            if result and result.endswith(".webp"):
                print("\t\tCover is a .webp file. Converting to .jpg...")
                conversion_result = convert_webp_to_jpg(result)
                if conversion_result:
                    print("\t\tCover successfully converted to .jpg")
                    result = conversion_result
                else:
                    print("\t\tCover conversion failed.")
                    print("\t\tCleaning up webp file...")
                    remove_file(result)
                    if not os.path.isfile(result):
                        print("\t\tWebp file successfully deleted.")
                    else:
                        print("\t\tWebp file could not be deleted.")
                    result = None
            if result:
                image_count += 1
                print("\t\tCover successfully extracted.\n")
                has_cover = True
                cover = result
            else:
                print("\t\tCover not found.")
            if output_execution_times:
                print_function_execution_time(
                    not_has_cover_start_time,
                    "not_has_cover in process_cover_extraction()",
                )
        else:
            image_count += 1
        if (
            file.number == 1
            and not any(
                os.path.isfile(os.path.join(file.root, f"cover{ext}"))
                for ext in image_extensions
            )
            and has_cover
            and cover
        ):
            volume_and_chap_cover_start_time = time.time()
            if (
                file.file_type == "chapter" and not contains_volume_one
            ) or file.file_type == "volume":
                if not printed:
                    print("\tFile: " + file.name)
                    printed = True
                print("\t\tMissing volume one cover.")
                print("\t\tFound volume one cover.")
                cover_extension = get_file_extension(os.path.basename(cover))
                if os.path.isfile(os.path.join(file.root, os.path.basename(cover))):
                    shutil.copy(
                        os.path.join(file.root, os.path.basename(cover)),
                        os.path.join(file.root, "cover" + cover_extension),
                    )
                    print("\t\tCopied cover as series cover.")
                else:
                    print(
                        "\t\tCover does not exist at: "
                        + str(os.path.join(file.root, os.path.basename(cover)))
                    )
            if output_execution_times:
                print_function_execution_time(
                    volume_and_chap_cover_start_time,
                    "volume_and_chap_cover in process_cover_extraction()",
                )
    except Exception as e:
        send_message(
            "\nERROR in extract_covers(): " + str(e) + " with file: " + file.name,
            error=True,
        )
    if output_execution_times:
        print_function_execution_time(start_time, "process_cover_extraction()")


def print_stats():
    print("\nFor all paths.")
    print("Total Files Found: " + str(file_count))
    print("\t" + str(cbz_count) + " were cbz files")
    print("\t" + str(epub_count) + " were epub files")
    print("\tof those we found that " + str(image_count) + " had a cover image file.")
    if len(errors) != 0:
        print("\nErrors (" + str(len(errors)) + "):")
        for error in errors:
            print("\t" + str(error))


# Deletes any file with an extension in unaccepted_file_extensions from the download_folers
def delete_unacceptable_files():
    global cached_paths
    if unaccepted_file_extensions:
        print("Searching for unacceptable files...")
        try:
            for path in download_folders:
                if os.path.exists(path):
                    os.chdir(path)
                    for root, dirs, files in scandir.walk(path):
                        if (
                            root not in cached_paths
                            and root not in download_folders
                            and root not in paths
                            and path not in download_folders
                            and check_for_existing_series_toggle
                        ):
                            write_to_file(
                                "cached_paths.txt",
                                root,
                                without_date=True,
                                check_for_dup=True,
                            )
                        dirs = remove_ignored_folder_names(dirs)
                        files = remove_hidden_files(files)
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.isfile(file_path):
                                extension = get_file_extension(file)
                                if (
                                    unaccepted_file_extensions
                                    and extension
                                    and extension in unaccepted_file_extensions
                                ):
                                    send_message(
                                        "\tUnacceptable: "
                                        + extension
                                        + " file found in "
                                        + file
                                        + "\n\t\tDeleting file from: "
                                        + root,
                                        discord=False,
                                    )
                                    remove_file(file_path)
                                elif unacceptable_keywords:
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
                                            send_discord_message(
                                                None,
                                                "Unacceptable Match Found",
                                                color=16776960,
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
                                            remove_file(file_path)
                                            if not os.path.isfile(file_path):
                                                print(
                                                    "\t\t\tSuccessfully removed unacceptable file: "
                                                    + file
                                                    + "\n\t\t\tFrom: "
                                                    + root
                                                )
                                            else:
                                                send_message(
                                                    "\t\t\tFailed to remove unacceptable file: "
                                                    + file
                                                    + "\n\t\t\tFrom: "
                                                    + root,
                                                    error=True,
                                                )
                                            break
                    for root, dirs, files in scandir.walk(path):
                        clean_two = clean_and_sort(root, files, dirs)
                        files, dirs = clean_two[0], clean_two[1]
                        for dir in dirs:
                            check_and_delete_empty_folder(os.path.join(root, dir))
                else:
                    if path == "":
                        print("\nERROR: Path cannot be empty.")
                    else:
                        print("\nERROR: " + path + " is an invalid path.\n")
        except Exception as e:
            send_message(e, error=True)


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


class BookwalkerSeries:
    def __init__(self, title, books, book_count, book_type):
        self.title = title
        self.books = books
        self.book_count = book_count
        self.book_type = book_type


# our session object, helps speed things up
# when scraping
session_object = None


def scrape_url(url, strainer=None, headers=None, cookies=None):
    try:
        global session_object
        if not session_object:
            session_object = requests.Session()
        page_obj = None
        if headers and cookies:
            page_obj = session_object.get(url, headers=headers, cookies=cookies)
        elif headers and not cookies:
            page_obj = session_object.get(url, headers=headers)
        else:
            page_obj = session_object.get(url)
        if page_obj and page_obj.status_code == 403:
            print("\nTOO MANY REQUESTS, WE'RE BEING RATE-LIMTIED!")
        soup = None
        if strainer and page_obj:
            soup = BeautifulSoup(page_obj.text, "lxml", parse_only=strainer)
        else:
            soup = BeautifulSoup(page_obj.text, "lxml")
        return soup
    except Exception as e:
        print("Error: " + str(e))
        return ""


def get_all_matching_books(books, book_type, title):
    matching_books = []
    for book in books:
        if book.book_type == book_type and book.title == title:
            matching_books.append(book)
    # remove them from books
    for book in matching_books:
        books.remove(book)
    return matching_books


# combine series in series_list that have the same title and book_type
def combine_series(series_list):
    combined_series = []
    for series in series_list:
        if len(combined_series) == 0:
            combined_series.append(series)
        else:
            for combined_series_item in combined_series:
                if (
                    similar(
                        remove_punctuation(series.title).lower().strip(),
                        remove_punctuation(combined_series_item.title).lower().strip(),
                    )
                    >= required_similarity_score
                    and series.book_type == combined_series_item.book_type
                ):
                    combined_series_item.books.extend(series.books)
                    combined_series_item.book_count = len(combined_series_item.books)
                    # combined_series_item.books = sorted(
                    #     combined_series_item.books, key=lambda x: x.volume_number
                    # )
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


def search_bookwalker(query, type, print_info=False, alternative_search=False):
    global volume_regex_keywords
    sleep_timer = 8
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
    startTime = datetime.now()
    done = False
    search_type = type
    count = 0
    page_count = 1
    page_count_url = "&page=" + str(page_count)
    search = urllib.parse.quote(query)
    base_url = "https://global.bookwalker.jp/search/?word="
    if not alternative_search:
        if search_type.lower() == "m":
            print("\tChecking: " + query + " [MANGA]")
        elif search_type.lower() == "l":
            print("\tChecking: " + query + " [NOVEL]")
    while page_count < total_pages_to_scrape + 1:
        page_count_url = "&page=" + str(page_count)
        alternate_url = ""
        url = base_url + search + page_count_url
        if search_type.lower() == "m":
            if not alternative_search:
                url += bookwalker_manga_category
            else:
                url += bookwalker_intll_manga_category
        elif search_type.lower() == "l":
            url += bookwalker_light_novel_category
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
                print("\t\tError: Empty page")
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
                print("\t\tNo pages found.")
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
                time.sleep(sleep_timer / 2)
            if alternate_result:
                return alternate_result
            if not alternative_search:
                print("\t\t! NO BOOKS FOUND ON BOOKWALKER !")
            no_book_result_searches.append(query)
            continue
        o_tile_list = list_area_ul.find_all("li", class_="o-tile")
        for item in o_tile_list:
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
                title = o_tile_book_info.find("h2", class_="a-tile-ttl").text
                title = re.sub(r"[\n\t\r]", " ", title)
                # replace any unicode characters in the title with spaces
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
                if part and re.search(r"(\b(Part)([-_. ]|)\b)", title):
                    title = re.sub(r"(\b(Part)([-_. ]|)\b)", " ", title)
                    title = re.sub(str(part), " ", title)
                    title = remove_dual_space(title).strip()
                volume_number = ""
                if not re.search(r"(\b(Vol)([-_. ]|)\b)", title):
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
                    elif title and is_one_shot_bk(title):
                        volume_number = 1
                    elif not volume_number and not isinstance(volume_number, list):
                        if title not in no_volume_number:
                            no_volume_number.append(title)
                        continue
                else:
                    volume_number = remove_everything_but_volume_num([title])
                if not re.search(r"(\b(Vol)([-_. ]|)\b)", title):
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
                clean_title = remove_punctuation(title).lower().strip()
                clean_query = remove_punctuation(query).lower().strip()
                score = similar(clean_title, clean_query)
                if not (score >= required_similarity_score):
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
                    continue
                # html from url
                page_two = scrape_url(
                    url, SoupStrainer("div", class_="product-detail-inner")
                )
                # print(str((datetime.now() - startTime)))
                # parse html
                soup_two = page_two
                # find table class="product-detail"
                product_detail = soup_two.find("table", class_="product-detail")
                # print(str((datetime.now() - startTime)))
                # find all <td> inside of product-detail
                product_detail_td = product_detail.find_all("td")
                date = ""
                for detail in product_detail_td:
                    date = re.search(
                        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(\s+)?\d{2}([,]+)?\s+\d{4}",
                        detail.text,
                        re.IGNORECASE,
                    )
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
                )
                books.append(book)
            except Exception as e:
                send_message(e, error=True)
                errors.append(url)
                continue
        # if books is not None and len(books) > 1:
        #     books = sorted(books, key=lambda x: x.volume_number)
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
                print("\tBooks:")
                for book in series.books:
                    # print the current books index
                    if not book.is_released:
                        print(
                            "\t\t("
                            + str(series.books.index(book) + 1)
                            + ")------------------------------ [PRE-ORDER]"
                        )
                    else:
                        print(
                            "\t\t("
                            + str(series.books.index(book) + 1)
                            + ")------------------------------"
                        )
                    print("\t\t\tNumber: " + str(book.volume_number))
                    # print("\t\t\tTitle: " + book.title)
                    print("\t\t\tDate: " + book.date)
                    print("\t\t\tReleased: " + str(book.is_released))
                    # print("\t\t\tPrice: " + str(book.price))
                    print("\t\t\tURL: " + book.url)
                    print("\t\t\tThumbnail: " + book.thumbnail)
                    # print("\t\t\tBook Type: " + book.book_type)
            else:
                print("\n\tNo results found.")

            if len(no_volume_number) > 0:
                print("\nNo Volume Results (" + str(len(no_volume_number)) + "):")
                for title in no_volume_number:
                    print("\t" + title)
                no_volume_number = []
            if len(chapter_releases) > 0:
                print("\nChapter Releases: (" + str(len(chapter_releases)) + ")")
                for title in chapter_releases:
                    print("\t" + title)
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
                        "\t["
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
                    print("\t" + url)
                no_book_result_searches = []
    series_list = combine_series(series_list)
    # print("\tSleeping for " + str(sleep_timer) + " to avoid being rate-limited...")
    time.sleep(sleep_timer)
    if len(series_list) == 1:
        if len(series_list[0].books) > 0:
            return series_list[0].books
    elif len(series_list) > 1:
        print("\t\tNumber of series from bookwalker search is greater than one.")
        print("\t\tNum: " + str(len(series_list)))
        return None
    else:
        if not alternative_search:
            print("\t\tNo matching books found.")
        return None


# Checks the library against bookwalker for any missing volumes that are released or on pre-order
# Doesn't work with NSFW results atm.
def check_for_new_volumes_on_bookwalker():
    print("\nChecking for new volumes on bookwalker...")
    paths_clean = [p for p in paths if p not in download_folders]
    for path in paths_clean:
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
                        [f.name for f in existing_dir_volumes], ".cbz"
                    )
                    >= 70
                ):
                    type = "m"
                elif (
                    get_percent_for_folder(
                        [f.name for f in existing_dir_volumes], ".epub"
                    )
                    >= 70
                ):
                    type = "l"
                # if len(new_releases_on_bookwalker) >= 10:  # used for quick testing
                #     break
                if type and dir:
                    bookwalker_volumes = search_bookwalker(dir, type, False)
                if existing_dir_volumes and bookwalker_volumes:
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
                        for vol in bookwalker_volumes:
                            if vol.is_released:
                                print("\n\t\t[RELEASED]")
                            else:
                                print("\n\t\t[PRE-ORDER]")
                            print(
                                "\t\tVolume Number: "
                                + str(set_num_as_float_or_int(vol.volume_number))
                            )
                            print("\t\tDate: " + vol.date)
                            if vol == bookwalker_volumes[-1]:
                                print("\t\tURL: " + vol.url + "\n")
                            else:
                                print("\t\tURL: " + vol.url)
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
    # Get rid of the old released and pre-orders and replace them with new ones.
    if log_to_file:
        if os.path.isfile(os.path.join(ROOT_DIR, "released.txt")):
            os.remove(os.path.join(ROOT_DIR, "released.txt"))
        if os.path.isfile(os.path.join(ROOT_DIR, "pre-orders.txt")):
            os.remove(os.path.join(ROOT_DIR, "pre-orders.txt"))
    if len(released) > 0:
        # send_discord_message(
        #     "/clear amount:500", passed_webhook=bookwalker_webhook_urls[0]
        # )
        print("\nNew Releases:")
        for r in released:
            print("\t" + r.title)
            print("\tVolume " + str(set_num_as_float_or_int(r.volume_number)))
            print("\tDate: " + r.date)
            print("\tURL: " + r.url)
            print("\n")
            message = (
                r.date
                + " "
                + r.title
                + " Volume "
                + str(set_num_as_float_or_int(r.volume_number))
                + " "
                + r.url
            )
            write_to_file("released.txt", message, without_date=True, overwrite=False)
            if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
                send_discord_message(message, passed_webhook=bookwalker_webhook_urls[0])
    if len(pre_orders) > 0:
        # if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 1:
        #     send_discord_message(
        #         "/clear amount:500", passed_webhook=bookwalker_webhook_urls[0]
        #     )
        # elif bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
        #     send_discord_message(
        #         "/clear amount:500", passed_webhook=bookwalker_webhook_urls[1]
        #     )
        print("\nPre-orders:")
        for p in pre_orders:
            print("\t" + p.title)
            print("\tVolume: " + str(set_num_as_float_or_int(p.volume_number)))
            print("\tDate: " + p.date)
            print("\tURL: " + p.url)
            print("\n")
            message = (
                p.date
                + " "
                + p.title
                + " Volume "
                + str(set_num_as_float_or_int(p.volume_number))
                + " "
                + p.url
            )
            write_to_file("pre-orders.txt", message, without_date=True, overwrite=False)
            if bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 2:
                send_discord_message(message, passed_webhook=bookwalker_webhook_urls[1])
            elif bookwalker_webhook_urls and len(bookwalker_webhook_urls) == 1:
                send_discord_message(message, passed_webhook=bookwalker_webhook_urls[0])


# Checks the epub for bonus.xhtml or bonus[0-9].xhtml
# then returns whether or not it was found.
def check_for_bonus_xhtml(zip):
    with zipfile.ZipFile(zip) as zip:
        list = zip.namelist()
        for item in list:
            base = os.path.basename(item)
            if re.search(r"(bonus([0-9]+)?\.xhtml)", base, re.IGNORECASE):
                return True
    return False


# caches all roots encountered when walking paths
def cache_paths():
    global cached_paths
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
                                without_date=True,
                                check_for_dup=True,
                            )
                except Exception as e:
                    send_message(e, error=True)
        else:
            if path == "":
                send_message("\nERROR: Path cannot be empty.", error=True)
            else:
                print("\nERROR: " + path + " is an invalid path.\n")


# Sends scan requests to komga for all libraries in komga_library_ids
# Reqiores komga settings to be set in settings.py
def scan_komga_libraries():
    komga_url = f"{komga_ip}:{komga_port}"
    if komga_library_ids and komga_url and komga_login_email and komga_login_password:
        for library_id in komga_library_ids:
            try:
                request = requests.post(
                    f"{komga_url}/api/v1/libraries/{library_id}/scan",
                    headers={
                        "Authorization": "Basic %s"
                        % b64encode(
                            f"{komga_login_email}:{komga_login_password}".encode(
                                "utf-8"
                            )
                        ).decode("utf-8"),
                        "Accept": "*/*",
                    },
                )
                if request.status_code == 202:
                    send_message(
                        "Successfully Initiated Scan for: " + library_id + " Library.",
                        discord=False,
                    )
                else:
                    send_message(
                        "Failed to Initiate Scan for: "
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
                    "Failed to Initiate Scan for: " + library_id + " Komga Library.",
                    error=True,
                )


def generate_release_group_list_file():
    print("\nGenerating Release Group List File...")
    global release_groups
    global skipped_files
    for path in paths:
        if os.path.exists(path):
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
                                                    skipped_file.extras.remove(extra)
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
                                            and file.extension == skipped_file.extension
                                            and file.series_name
                                            == skipped_file.series_name
                                        ):
                                            print(
                                                "\t\tSkipping: "
                                                + file.name
                                                + " because it has the same extras, extension, and series name as: "
                                                + skipped_file.name
                                                + " (in skipped_files.txt)"
                                            )
                                            found = True
                                            write_to_file(
                                                "skipped_files.txt",
                                                file.name,
                                                without_date=True,
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
                                                + '" skipping file.'
                                            )
                                            found = True
                                            break
                                if not found:
                                    # ask the user what the release group is, then write it to the file, add it to the list, and continue. IF the user inputs "none" then skip it.
                                    # loop until the user inputs a valid response
                                    while True:
                                        print(
                                            "\t\tCould not find a release group for: \n\t\t\t"
                                            + file.name
                                        )
                                        group = input(
                                            "\n\t\tPlease enter the release group "
                                            + '("none" to add to skipped_files.txt, "skip" to skip): '
                                        )
                                        if group == "none":
                                            print(
                                                "\t\t\tAdding to skipped_files.txt and skipping in the future..."
                                            )
                                            write_to_file(
                                                "skipped_files.txt",
                                                file.name,
                                                without_date=True,
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
                                                "release_groups.txt",
                                                group,
                                                without_date=True,
                                                check_for_dup=True,
                                            )
                                            if group not in release_groups:
                                                release_groups.append(group)
                                            break
                                        else:
                                            print("\t\t\tInvalid input.")
                            else:
                                print("\t\tSkipping... File is in skipped_files.txt")
            except Exception as e:
                send_message(e, error=True)
        else:
            if path == "":
                send_message("\nERROR: Path cannot be empty.", error=True)
            else:
                send_message("\nERROR: " + path + " is an invalid path.\n", error=True)


# Checks if a string only contains one set of numbers
def only_has_one_set_of_numbers(string):
    result = False
    search = re.search(
        r"(^[^\d]*(([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?)?[^\d]*$)",
        string,
        re.IGNORECASE,
    )
    if search:
        result = True
    return result


# Checks if the file name contains multiple numbers
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


# Result class that is used for our image_comparison results from our
# image comparison function
class Image_Result:
    def __init__(self, ssim_score, image_source):
        self.ssim_score = ssim_score
        self.image_source = image_source


def prep_images_for_similarity(blank_image_path, internal_cover_data):
    internal_cover = cv2.imdecode(
        np.frombuffer(internal_cover_data, np.uint8), cv2.IMREAD_UNCHANGED
    )
    blank_image = cv2.imread(blank_image_path)
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
    score = compare_images(blank_image, internal_cover)
    return score


# compares our two images likness and returns the ssim score
def compare_images(imageA, imageB):
    ssim_score = None
    try:
        print("\t\t\tBlank Image Size: " + str(imageA.shape))
        print("\t\t\tInternal Cover Size: " + str(imageB.shape))

        if len(imageA.shape) == 3 and len(imageB.shape) == 3:
            grayA = cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY)
            grayB = cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY)
            ssim_score = ssim(grayA, grayB)
        else:
            ssim_score = ssim(imageA, imageB)
        print("\t\t\t\tSSIM: " + str(ssim_score))
    except Exception as e:
        send_message(e, error=True)
    return ssim_score


# takes the start time, end time, and name of the function and prints the time it took to run
def print_function_execution_time(start_time, function_name):
    end_time = time.time()
    time_diff = end_time - start_time
    rounded_time = round(time_diff, 3)
    send_message(
        "\t\t\t\t"
        + function_name
        + " took "
        + str(rounded_time)
        + " seconds to complete.",
        discord=False,
    )
    write_to_file(function_name + ".txt", str(rounded_time), without_date=True)


# Optional features below, use at your own risk.
# Activate them in settings.py
def main():
    global bookwalker_check
    global cached_paths
    global processed_files
    global moved_files
    global release_groups
    global skipped_files
    processed_files = []
    moved_files = []
    download_folder_in_paths = False
    if download_folders and paths:
        for folder in download_folders:
            if folder in paths:
                download_folder_in_paths = True
                break
    if (
        os.path.isfile(os.path.join(ROOT_DIR, "cached_paths.txt"))
        and check_for_existing_series_toggle
    ):
        cached_paths = read_lines_from_file(
            os.path.join(ROOT_DIR, "cached_paths.txt"),
            ignore=paths + download_folders,
            ignore_paths_not_in_paths=True,
        )
    if (
        (
            cache_each_root_for_each_path_in_paths_at_beginning_toggle
            or not os.path.isfile(os.path.join(ROOT_DIR, "cached_paths.txt"))
        )
        and paths
        and check_for_existing_series_toggle
    ):
        cache_paths()
    if os.path.isfile(os.path.join(ROOT_DIR, "release_groups.txt")):
        release_groups_read = read_lines_from_file(
            os.path.join(ROOT_DIR, "release_groups.txt")
        )
        if release_groups_read:
            release_groups = release_groups_read
    if os.path.isfile(os.path.join(ROOT_DIR, "skipped_files.txt")):
        skipped_files_read = read_lines_from_file(
            os.path.join(ROOT_DIR, "skipped_files.txt")
        )
        if skipped_files_read:
            skipped_files = skipped_files_read
    if delete_unacceptable_files_toggle and (
        download_folders and (unaccepted_file_extensions or unacceptable_keywords)
    ):
        start_time = time.time()
        delete_unacceptable_files()
        if output_execution_times:
            print_function_execution_time(start_time, "delete_unacceptable_files()")
    if delete_chapters_from_downloads_toggle and download_folders:
        start_time = time.time()
        delete_chapters_from_downloads()
        if output_execution_times:
            print_function_execution_time(
                start_time, "delete_chapters_from_downloads()"
            )
    if generate_release_group_list_toggle and log_to_file and paths:
        generate_release_group_list_file()
    if rename_files_in_download_folders_toggle and download_folders:
        start_time = time.time()
        rename_files_in_download_folders()
        if output_execution_times:
            print_function_execution_time(
                start_time, "rename_files_in_download_folders()"
            )
    if create_folders_for_items_in_download_folder_toggle and download_folders:
        start_time = time.time()
        create_folders_for_items_in_download_folder()
        if output_execution_times:
            print_function_execution_time(
                start_time,
                "create_folders_for_items_in_download_folder()",
            )
    if rename_dirs_in_download_folder_toggle and download_folders:
        start_time = time.time()
        rename_dirs_in_download_folder()
        if output_execution_times:
            print_function_execution_time(
                start_time, "rename_dirs_in_download_folder()"
            )
    if check_for_duplicate_volumes_toggle and download_folders:
        start_time = time.time()
        check_for_duplicate_volumes(download_folders)
        if output_execution_times:
            print_function_execution_time(start_time, "check_for_duplicate_volumes()")
    if extract_covers_toggle and paths and download_folder_in_paths:
        start_time = time.time()
        extract_covers()
        if output_execution_times:
            print_function_execution_time(start_time, "extract_covers()")
    if check_for_existing_series_toggle and download_folders and paths:
        start_time = time.time()
        check_for_existing_series()
        if output_execution_times:
            print_function_execution_time(start_time, "check_for_existing_series()")
    if extract_covers_toggle and paths and not download_folder_in_paths:
        start_time = time.time()
        extract_covers()
        if output_execution_times:
            print_function_execution_time(start_time, "extract_covers()")
    if send_scan_request_to_komga_libraries_toggle and moved_files:
        scan_komga_libraries()
    if check_for_missing_volumes_toggle and paths:
        start_time = time.time()
        check_for_missing_volumes()
        if output_execution_times:
            print_function_execution_time(start_time, "check_for_missing_volumes()")
    if bookwalker_check:
        # currently slowed down to avoid rate limiting,
        # advised not to run on each use, but rather once a week
        check_for_new_volumes_on_bookwalker()  # checks the library against bookwalker for any missing volumes that are released or on pre-order
    if extract_covers_toggle and paths:
        start_time = time.time()
        print_stats()
        if output_execution_times:
            print_function_execution_time(start_time, "print_stats()")


if __name__ == "__main__":
    parse_my_args()  # parses the user's arguments
    if watchdog_toggle:
        print("\nWatchdog is enabled, watching for changes...\n")
        watch = Watcher()
        watch.run()
    else:
        main()
