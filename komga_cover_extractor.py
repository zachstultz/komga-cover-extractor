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
from PIL import Image
from PIL import ImageFile
from lxml import etree
from genericpath import isfile
from posixpath import join
from difflib import SequenceMatcher
from datetime import datetime
from discord_webhook import DiscordWebhook
from bs4 import BeautifulSoup, SoupStrainer


# ************************************
# Created by: Zach Stultz            *
# Git: https://github.com/zachstultz *
# ************************************

paths = [""]
download_folders = [""]
ignored_folder_names = [""]

# List of file types used throughout the program
file_extensions = ["epub", "cbz", "cbr"]  # (cbr is only used for the stat printout)
image_extensions = ["jpg", "jpeg", "png", "tbn", "jxl"]
# file extensions deleted from the download folders in an optional method. [".example"]
unaccepted_file_extensions = [""]
series_cover_file_names = ["cover", "poster"]

# Our global folder_accessor
folder_accessor = None

# whether or not to compress the extractred images
compress_image_option = False

# Image compression value
image_quality = 60

# Stat-related
file_count = 0
cbz_count = 0
epub_count = 0
cbr_count = 0
image_count = 0
cbz_internal_covers_found = 0
poster_found = 0
errors = []
items_changed = []
# The remaining files without covers
files_with_no_cover = []

# The required file type matching percentage between
# the download folder and the existing folder
#
# For exmpale, 90% of the folder's files must be CBZ or EPUB
# Used to avoid accdientally matching a epub volume to a manga library
# or vice versa because they can have the same exact series name.
required_matching_percentage = 90

# The required score when comparing two strings likeness, used when matching a series_name to a folder name.
required_similarity_score = 0.9790

# The preferred naming format used by rename_files_in_download_folders()
# v = v01, Volume = Volume01, and so on.
# IF YOU WANT A SPACE BETWEEN THE TWO, ADD IT IN THE PREFERRED NAMING.
preferred_volume_renaming_format = "v"

# A discord webhook url used to send messages to discord about the changes made.
discord_webhook_url = ""

# Whether or not to add the issue number to the file names
# Useful when using ComicTagger
# TRUE: manga v01 #01 (2001).cbz
# FALSE: manga v01 (2001).cbz
add_issue_number_to_cbz_file_name = False

# Whether or not to add a volume number one to one-shot volumes
# Useful for Comictagger matching, and enabling upgrading of
# one-shot volumes.
add_volume_one_number_to_one_shots = False

# Newly released volumes that aren't currently in the library.
new_releases_on_bookwalker = []

# Whether or not to check the library against bookwalker for new releases.
bookwalker_check = False

# False = files with be renamed automatically
# True = user will be prompted for approval
manual_rename = False

# Whether or not an isbn/series_id match should be used
# as an alternative when matching a downloaded file to
# the existing library.
match_through_isbn_or_series_id = False

# Whether or not to output errors and changes to a log file
log_to_file = True

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
    ):
        self.name = name
        self.extensionless_name = extensionless_name
        self.basename = basename
        self.extension = extension
        self.root = root
        self.path = path
        self.extensionless_path = extensionless_path


# Volume Class
class Volume:
    def __init__(
        self,
        volume_type,
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
        self.volume_type = volume_type
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


# Keyword Class
class Keyword:
    def __init__(self, name, score):
        self.name = name
        self.score = score


# Keywords ranked by point values, used when determining if a downloaded volume
# is an upgrade to the existing volume in the library
# EX: Keyword("Keyword or Regex", point_value)
ranked_keywords = []

volume_keywords = [
    "LN",
    "Light Novel",
    "Novel",
    "Book",
    "Volume",
    "Vol",
    "V",
    "第",
    "Disc",
]

volume_one_number_keywords = ["One", "1", "01", "001", "0001"]

# Parses the passed command-line arguments
def parse_my_args():
    global paths
    global download_folders
    global discord_webhook_url
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
    parser = parser.parse_args()
    if not parser.paths and not parser.download_folders:
        print("No paths or download folders were passed to the script.")
        print("Exiting...")
        exit()
    if parser.paths is not None:
        paths = []
        for path in parser.paths:
            for p in path:
                paths.append(p)
    if parser.download_folders is not None:
        download_folders = []
        for download_folder in parser.download_folders:
            for folder in download_folder:
                download_folders.append(folder)
    if parser.webhook is not None:
        discord_webhook_url = parser.webhook
    if parser.bookwalker_check is not None:
        if (
            parser.bookwalker_check == 1
            or parser.bookwalker_check.lower() == "true"
            or parser.bookwalker_check.lower() == "yes"
        ):
            global bookwalker_check
            bookwalker_check = True
    if parser.compress is not None:
        if (
            parser.compress == 1
            or parser.compress.lower() == "true"
            or parser.compress.lower() == "yes"
        ):
            global compress_image_option
            compress_image_option = True
    if parser.compress_quality is not None:
        global image_quality
        image_quality = set_num_as_float_or_int(parser.compress_quality)


def set_num_as_float_or_int(num):
    if num != "":
        if isinstance(num, list):
            result = ""
            for num in num:
                if float(num) == int(num):
                    if num == num[-1]:
                        result += str(int(num))
                    else:
                        result += str(int(num)) + "-"
                else:
                    if num == num[-1]:
                        result += str(float(num))
                    else:
                        result += str(float(num)) + "-"
            return result
        else:
            if float(num) == int(num):
                num = int(num)
            else:
                num = float(num)
    return num


def compress_image(image_path, quality=image_quality, to_jpg=False):
    img = Image.open(image_path)
    filename, ext = os.path.splitext(image_path)
    extension = get_file_extension(image_path)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    if extension == ".png":
        to_jpg = True
    if to_jpg:
        new_filename = f"{filename}.jpg"
    else:
        new_filename = f"{filename}" + extension
    try:
        img.save(new_filename, quality=quality, optimize=True)
        if extension == ".png" and (
            os.path.isfile(new_filename) and os.path.isfile(image_path)
        ):
            os.remove(image_path)
            return image_path
    except OSError as ose:
        send_error_message(
            "\t\tFailed to compress image: " + image_path + " \n\t\tERROR:" + str(ose)
        )


# Appends, sends, and prints our error message
def send_error_message(error, discord=True):
    print(error)
    if discord != False:
        send_discord_message(error)
    errors.append(error)
    write_to_file("errors.txt", error)


# Appends, sends, and prints our change message
def send_change_message(message):
    print(message)
    send_discord_message(message)
    items_changed.append(message)
    write_to_file("changes.txt", message)


# Sends a discord message using the users webhook url
def send_discord_message(message):
    try:
        if discord_webhook_url != "":
            webhook = DiscordWebhook(
                url=discord_webhook_url, content=message, rate_limit_retry=True
            )
            webhook.execute()
    except TypeError as e:
        send_error_message(e, discord=False)


# Removes hidden files
def remove_hidden_files(files, root):
    for file in files[:]:
        if file.startswith("."):
            files.remove(file)


# Removes any unaccepted file types
def remove_unaccepted_file_types(files, root):
    for file in files[:]:
        extension = re.sub("\.", "", get_file_extension(file))
        if extension not in file_extensions and os.path.isfile(
            os.path.join(root, file)
        ):
            files.remove(file)


# Removes any folder names in the ignored_folders
def remove_ignored_folders(dirs):
    if len(ignored_folder_names) != 0:
        dirs[:] = [d for d in dirs if d not in ignored_folder_names]


# Remove hidden folders from the list
def remove_hidden_folders(root, dirs):
    for folder in dirs[:]:
        if folder.startswith(".") and os.path.isdir(os.path.join(root, folder)):
            dirs.remove(folder)


# Removes all chapter releases
def remove_all_chapters(files):
    for file in files[:]:
        if (
            contains_chapter_keywords(file) and not contains_volume_keywords(file)
        ) and not (check_for_exception_keywords(file)):
            files.remove(file)


# Cleans up the files array before usage
def clean_and_sort(root, files=None, dirs=None):
    if files:
        files.sort()
        remove_hidden_files(files, root)
        remove_unaccepted_file_types(files, root)
        remove_all_chapters(files)
    if dirs:
        dirs.sort()
        remove_hidden_folders(root, dirs)
        remove_ignored_folders(dirs)


# Retrieves the file extension on the passed file
def get_file_extension(file):
    return os.path.splitext(file)[1]


# Returns an extensionless name
def get_extensionless_name(file):
    return os.path.splitext(file)[0]


# Trades out our regular files for file objects
def upgrade_to_file_class(files, root):
    clean_and_sort(root, files)
    results = []
    for file in files:
        file_obj = File(
            file,
            get_extensionless_name(file),
            get_series_name_from_file_name(file, root),
            get_file_extension(file),
            root,
            os.path.join(root, file),
            get_extensionless_name(os.path.join(root, file)),
        )
        results.append(file_obj)
    return results


# Updates our output stats
def update_stats(file):
    global file_count
    if (file.name).endswith(".cbz") and os.path.isfile(file.path):
        global cbz_count
        file_count += 1
        cbz_count += 1
    if (file.name).endswith(".epub") and os.path.isfile(file.path):
        global epub_count
        file_count += 1
        epub_count += 1
    if (file.name).endswith(".cbr") and os.path.isfile(file.path):
        global cbr_count
        file_count += 1
        cbr_count += 1


# Gets and returns the basename
def get_base_name(item):
    return os.path.basename(item)


# Removes hidden files with the base name.
def remove_hidden_files_with_basename(files):
    for file in files[:]:
        base = os.path.basename(file)
        if file.startswith(".") or base.startswith("."):
            files.remove(file)


# Credit to original source: https://alamot.github.io/epub_cover/
# Modified by me.
# Retrieves the inner epub cover
def get_epub_cover(epub_path):
    try:
        namespaces = {
            "calibre": "http://calibre.kovidgoyal.net/2009/metadata",
            "dc": "http://purl.org/dc/elements/1.1/",
            "dcterms": "http://purl.org/dc/terms/",
            "opf": "http://www.idpf.org/2007/opf",
            "u": "urn:oasis:names:tc:opendocument:xmlns:container",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        }
        with zipfile.ZipFile(epub_path) as z:
            t = etree.fromstring(z.read("META-INF/container.xml"))
            rootfile_path = t.xpath(
                "/u:container/u:rootfiles/u:rootfile", namespaces=namespaces
            )[0].get("full-path")
            t = etree.fromstring(z.read(rootfile_path))
            cover_id = t.xpath(
                "//opf:metadata/opf:meta[@name='cover']", namespaces=namespaces
            )[0].get("content")
            cover_href = t.xpath(
                "//opf:manifest/opf:item[@id='" + cover_id + "']", namespaces=namespaces
            )[0].get("href")
            cover_path = os.path.join(os.path.dirname(rootfile_path), cover_href)
            return cover_path
        return None
    except Exception as e:
        return None


# Checks if the passed string is a volume one.
def is_volume_one(volume_name):
    for vk in volume_keywords:
        for vonk in volume_one_number_keywords:
            if re.search(
                rf"(\b({vk})([-_. ]|)({vonk})(([-_.]([0-9]+))+)?\b)",
                volume_name,
                re.IGNORECASE,
            ):
                return True
    return False


# Checks if the passed string contains volume keywords
def contains_volume_keywords(file):
    return re.search(
        r"((\s(\s-\s|)(Part|)+(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)([-_. ]|)([0-9]+)\b)|\s(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)([0-9]+)\s|\s(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)([0-9]+)\s)",
        file,
        re.IGNORECASE,
    )


# Checks for volume keywords and chapter keywords.
# If neither are present, the volume is assumed to be a one-shot volume.
def is_one_shot_bk(file_name):
    volume_file_status = contains_volume_keywords(file_name)
    chapter_file_status = contains_chapter_keywords(file_name)
    exception_keyword_status = check_for_exception_keywords(file_name)
    if (not volume_file_status and not chapter_file_status) and (
        not exception_keyword_status
    ):
        return True
    return False


# Checks for volume keywords and chapter keywords.
# If neither are present, the volume is assumed to be a one-shot volume.
def is_one_shot(file_name, root):
    files = os.listdir(root)
    clean_and_sort(root, files)
    continue_logic = False
    if len(files) == 1 or root == download_folders[0]:
        continue_logic = True
    if continue_logic == True:
        volume_file_status = contains_volume_keywords(file_name)
        chapter_file_status = contains_chapter_keywords(file_name)
        exception_keyword_status = check_for_exception_keywords(file_name)
        if (not volume_file_status and not chapter_file_status) and (
            not exception_keyword_status
        ):
            return True
    return False


# Checks similarity between two strings.
def similar(a, b):
    if a == "" or b == "":
        return 0.0
    else:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# Moves the image into a folder if said image exists. Also checks for a cover/poster image and moves that.
def move_images(file, folder_name):
    for extension in image_extensions:
        image = file.extensionless_path + "." + extension
        if os.path.isfile(image):
            shutil.move(image, folder_name)
        for cover_file_name in series_cover_file_names:
            cover_image_file_name = cover_file_name + "." + extension
            cover_image_file_path = os.path.join(file.root, cover_image_file_name)
            if os.path.isfile(cover_image_file_path):
                if not os.path.isfile(os.path.join(folder_name, cover_image_file_name)):
                    shutil.move(cover_image_file_path, folder_name)
                else:
                    remove_file(cover_image_file_path)


# Retrieves the series name through various regexes
# Removes the volume number and anything to the right of it, and strips it.
def get_series_name_from_file_name(name, root):
    if is_one_shot(name, root):
        name = re.sub(
            r"([-_ ]+|)(((\[|\(|\{).*(\]|\)|\}))|LN)([-_. ]+|)(epub|cbz|).*",
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()
    else:
        if re.search(
            r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)([-_. ]|)([0-9]+)(\b|\s).*",
            name,
            flags=re.IGNORECASE,
        ):
            name = (
                re.sub(
                    r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)([-_. ]|)([0-9]+)(\b|\s).*",
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
    return name


# Creates folders for our stray volumes sitting in the root of the download folder.
def create_folders_for_items_in_download_folder():
    for download_folder in download_folders:
        if os.path.exists(download_folder):
            try:
                for root, dirs, files in os.walk(download_folder):
                    clean_and_sort(root, files, dirs)
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
                        for file_extension in file_extensions:
                            download_folder_basename = os.path.basename(download_folder)
                            directory_basename = os.path.basename(file.root)
                            if (file.name).endswith(
                                file_extension
                            ) and download_folder_basename == directory_basename:
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
            except FileNotFoundError:
                send_error_message(
                    "\nERROR: " + download_folder + " is not a valid path.\n"
                )
        else:
            if download_folder == "":
                send_error_message("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + download_folder + " is an invalid path.\n")


# Returns the percentage of files that are epub, to the total amount of files
def get_epub_percent_for_folder(files):
    epub_folder_count = 0
    for file in files:
        if (file).endswith(".epub"):
            epub_folder_count += 1
    epub_percent = (
        (epub_folder_count / (len(files)) * 100) if epub_folder_count != 0 else 0
    )
    return epub_percent


# Returns the percentage of files that are cbz, to the total amount of files
def get_cbz_percent_for_folder(files):
    cbz_folder_count = 0
    for file in files:
        if (file).endswith(".cbz"):
            cbz_folder_count += 1
    cbz_percent = (
        (cbz_folder_count / (len(files)) * 100) if cbz_folder_count != 0 else 0
    )
    return cbz_percent


def check_for_multi_volume_file(file_name):
    if re.search(
        r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc|)([0-9]+(\.[0-9]+)?)[-_]([0-9]+(\.[0-9]+)?)\b",
        file_name,
        re.IGNORECASE,
    ):
        return True
    else:
        return False


def convert_list_of_numbers_to_array(string):
    string = re.sub(r"[-_.]", " ", string)
    return [float(s) for s in string.split() if s.isdigit()]


# Finds the volume number and strips out everything except that number
def remove_everything_but_volume_num(files, root):
    results = []
    is_omnibus = False
    for file in files[:]:
        result = re.search(
            r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)((\.)|)([0-9]+)(([-_.])([0-9]+)|)+\b",
            file,
            re.IGNORECASE,
        )
        if result:
            try:
                file = result
                if hasattr(file, "group"):
                    file = file.group()
                else:
                    file = ""
                file = re.sub(
                    r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)([-_. ])?",
                    "",
                    file,
                    flags=re.IGNORECASE,
                ).strip()
                if re.search(
                    r"\b[0-9]+(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)[0-9]+\b",
                    file,
                    re.IGNORECASE,
                ):
                    file = (
                        re.sub(
                            r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)",
                            ".",
                            file,
                            flags=re.IGNORECASE,
                        )
                    ).strip()
                try:
                    if check_for_multi_volume_file(file):
                        volume_numbers = convert_list_of_numbers_to_array(file)
                        results.append(volume_numbers)
                    else:
                        results.append(float(file))
                except ValueError:
                    message = "Not a float: " + files[0]
                    print(message)
                    write_to_file("errors.txt", message)
            except AttributeError:
                print(str(AttributeError.with_traceback))
        else:
            files.remove(file)
    if is_omnibus == True and len(results) != 0:
        return results
    elif len(results) != 0 and (len(results) == len(files)):
        return results[0]
    elif len(results) == 0:
        return ""


# Retrieves the release year
def get_volume_year(name):
    result = re.search(r"\((\d{4})\)", name, re.IGNORECASE)
    if hasattr(result, "group"):
        result = result.group(1).strip()
        try:
            result = int(result)
        except ValueError as ve:
            print(ve)
    else:
        result == ""
    return result


# Determines whether or not the release is a fixed release
def is_fixed_volume(name):
    if re.search(r"(\(|\[|\{)f([0-9]+|)(\)|\]|\})", name, re.IGNORECASE):
        return True
    else:
        return False


# Retrieves the release_group on the file name
def get_release_group(name):
    result = ""
    for keyword in ranked_keywords:
        if re.search(keyword.name, name, re.IGNORECASE):
            result = keyword.name
    return result


# Checks the extension and returns accordingly
def get_type(name):
    if str(name).endswith(".cbz"):
        return "manga"
    elif str(name).endswith(".epub"):
        return "light novel"


# Retrieves and returns the volume part from the file name
def get_volume_part(file):
    result = ""
    file = re.sub(
        r".*(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)([-_. ]|)([-_. ]|)([0-9]+)(\b|\s)",
        "",
        file,
        flags=re.IGNORECASE,
    ).strip()
    search = re.search(r"(\b(Part)([-_. ]|)([0-9]+)\b)", file, re.IGNORECASE)
    if search:
        result = search.group(1)
        result = re.sub(r"(\b(Part)([-_. ]|)\b)", "", result, flags=re.IGNORECASE)
        try:
            return float(result)
        except ValueError:
            print("Not a float: " + file)
            result = ""
    return result


# Trades out our regular files for file objects
def upgrade_to_volume_class(files):
    results = []
    for file in files:
        volume_obj = Volume(
            get_type(file.extension),
            get_series_name_from_file_name(file.name, file.root),
            get_volume_year(file.name),
            remove_everything_but_volume_num([file.name], file.root),
            get_volume_part(file.name),
            is_fixed_volume(file.name),
            get_release_group(file.name),
            file.name,
            file.extensionless_name,
            file.basename,
            file.extension,
            file.root,
            file.path,
            file.extensionless_path,
            get_extras(file.name, file.root),
            check_for_multi_volume_file(file.name),
            is_one_shot=is_one_shot(file.name, file.root),
        )
        results.append(volume_obj)
    for obj in results:
        if obj.is_one_shot:
            obj.volume_number = 1
    return results


# Retrieves the release_group score from the list, using a high similarity
def get_keyword_score(name, download_folder=False):
    score = 0.0
    for keyword in ranked_keywords:
        if re.search(keyword.name, name, re.IGNORECASE):
            score += keyword.score
    return score


# Checks if the downloaded release is an upgrade for the current release.
def is_upgradeable(downloaded_release, current_release):
    downloaded_release_score = get_keyword_score(downloaded_release.name)
    current_release_score = get_keyword_score(current_release.name)
    if downloaded_release_score > current_release_score:
        return True
    elif (downloaded_release_score == current_release_score) and (
        downloaded_release.is_fixed == True and current_release.is_fixed == False
    ):
        return True
    else:
        return False


# Deletes hidden files, used when checking if a folder is empty.
def delete_hidden_files(files, root):
    for file in files[:]:
        if (str(file)).startswith(".") and os.path.isfile(os.path.join(root, file)):
            remove_file(os.path.join(root, file))


# Removes the old series and cover image
def remove_images(path):
    for image_extension in image_extensions:
        if is_volume_one(os.path.basename(path)):
            for cover_file_name in series_cover_file_names:
                cover_file_name = os.path.join(
                    os.path.dirname(path), cover_file_name + "." + image_extension
                )
                if os.path.isfile(cover_file_name):
                    remove_file(cover_file_name)
        volume_image_cover_file_name = (
            get_extensionless_name(path) + "." + image_extension
        )
        if os.path.isfile(volume_image_cover_file_name):
            remove_file(volume_image_cover_file_name)


# Removes a file
def remove_file(full_file_path):
    try:
        os.remove(full_file_path)
        if not os.path.isfile(full_file_path):
            send_change_message("\t\t\tFile Removed: " + full_file_path)
            remove_images(full_file_path)
            return True
        else:
            send_error_message("\n\t\t\tFailed to remove file: " + full_file_path)
            return False
    except OSError as e:
        send_error_message(e)


# Move a file
def move_file(file, new_location):
    try:
        if os.path.isfile(file.path):
            shutil.move(file.path, new_location)
            if os.path.isfile(os.path.join(new_location, file.name)):
                send_change_message(
                    "\t\tFile: "
                    + file.name
                    + " was successfully moved to: "
                    + new_location
                )
                move_images(file, new_location)
            else:
                send_error_message(
                    "\t\tFailed to move: "
                    + os.path.join(file.root, file.name)
                    + " to: "
                    + new_location
                )
    except OSError as e:
        send_error_message(e)


# Replaces an old file.
def replace_file(old_file, new_file):
    if os.path.isfile(old_file.path) and os.path.isfile(new_file.path):
        remove_file(old_file.path)
        if not os.path.isfile(old_file.path):
            move_file(new_file, old_file.root)
            if os.path.isfile(os.path.join(old_file.root, new_file.name)):
                send_change_message(
                    "\t\tFile: " + old_file.name + " moved to: " + new_file.root
                )
            else:
                send_error_message(
                    "\tFailed to replace: " + old_file.name + " with: " + new_file.name
                )
        else:
            send_error_message(
                "\tFailed to remove old file: " + old_file.name + "\nUpgrade aborted."
            )


# Removes the duplicate after determining it's upgrade status, otherwise, it upgrades
def remove_duplicate_releases_from_download(original_releases, downloaded_releases):
    for download in downloaded_releases[:]:
        if not isinstance(download.volume_number, int) and not isinstance(
            download.volume_number, float
        ):
            send_error_message("\n\t\tThe volume number is empty on: " + download.name)
            send_error_message("\t\tAvoiding file, might be a chapter.")
            downloaded_releases.remove(download)
        if len(downloaded_releases) != 0:
            for original in original_releases:
                if isinstance(download.volume_number, float) and isinstance(
                    original.volume_number, float
                ):
                    if (download.volume_number == original.volume_number) and (
                        (download.volume_number != "" and original.volume_number != "")
                        and (download.volume_part) == (original.volume_part)
                    ):
                        if not is_upgradeable(download, original):
                            send_change_message(
                                "\t\tVolume: "
                                + download.name
                                + " is not an upgrade to: "
                                + original.name
                            )
                            send_change_message(
                                "\t\tDeleting "
                                + download.name
                                + " from download folder."
                            )
                            if download in downloaded_releases:
                                downloaded_releases.remove(download)
                            remove_file(download.path)
                        else:
                            send_change_message(
                                "\t\tVolume: "
                                + download.name
                                + " is an upgrade to: "
                                + original.name
                            )
                            send_change_message("\t\tUpgrading " + original.name)
                            replace_file(original, download)


# Checks if the folder is empty, then deletes if it is
def check_and_delete_empty_folder(folder):
    print("\t\tChecking for empty folder: " + folder)
    delete_hidden_files(os.listdir(folder), folder)
    folder_contents = os.listdir(folder)
    remove_hidden_files(folder_contents, folder)
    if len(folder_contents) == 0:
        try:
            print("\t\tRemoving empty folder: " + folder)
            os.rmdir(folder)
        except OSError as e:
            send_error_message(e)


# Writes a log file
def write_to_file(file, message, without_date=False, overwrite=False):
    if log_to_file:
        try:
            message = re.sub("\t|\n", "", str(message), flags=re.IGNORECASE)
            ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
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
                send_error_message(e)
        except Exception as e:
            send_error_message(e)


# Checks for any missing volumes between the lowest volume of a series and the highest volume.
def check_for_missing_volumes():
    print("\nChecking for missing volumes...")
    paths_clean = [p for p in paths if p not in download_folders]
    for path in paths_clean:
        if os.path.exists(path):
            os.chdir(path)
            # get list of folders from path directory
            path_dirs = [f for f in os.listdir(path) if os.path.isdir(f)]
            clean_and_sort(path, dirs=path_dirs)
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
                clean_and_sort(existing_dir, clean_existing)
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
                    if not isinstance(existing.volume_number, int) and not isinstance(
                        existing.volume_number, float
                    ):
                        existing_dir_volumes.remove(existing)
                if len(existing_dir_volumes) >= 2:
                    volume_numbers = []
                    for volume in existing_dir_volumes:
                        if volume.volume_number != "":
                            volume_numbers.append(volume.volume_number)
                    if len(volume_numbers) >= 2:
                        lowest_volume_number = 1
                        highest_volume_number = int(max(volume_numbers))
                        volume_num_range = list(
                            range(lowest_volume_number, highest_volume_number + 1)
                        )
                        for number in volume_numbers:
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
    src, dest, root, extensionless_filename_src, extenionless_filename_dest
):
    if os.path.isfile(src):
        print("\t\tRenaming " + src)
        os.rename(src, dest)
        if os.path.isfile(dest):
            send_change_message(
                "\t\t"
                + extensionless_filename_src
                + " was renamed to "
                + extenionless_filename_dest
            )
            for image_extension in image_extensions:
                image_file = extensionless_filename_src + "." + image_extension
                image_file_rename = extenionless_filename_dest + "." + image_extension
                if os.path.isfile(os.path.join(root, image_file)):
                    os.rename(
                        os.path.join(root, image_file),
                        os.path.join(root, image_file_rename),
                    )
        else:
            send_error_message("Failed to rename " + src + " to " + dest)


def reorganize_and_rename(files, dir):
    global manual_rename
    base_dir = os.path.basename(dir)
    for file in files:
        if re.search(
            r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)([-_.]|)([0-9]+)((([-_.]|)([0-9]+))+)?(\s|\.epub|\.cbz)",
            file.name,
            re.IGNORECASE,
        ):
            rename = ""
            rename += base_dir
            rename += " " + preferred_volume_renaming_format
            number = None
            numbers = []
            if file.multi_volume:
                for n in file.volume_number:
                    numbers.append(n)
            else:
                numbers.append(file.volume_number)
            for number in numbers:
                if number.is_integer():
                    if number < 10:
                        volume_number = str(int(number)).zfill(2)
                        rename += volume_number
                        if (
                            add_issue_number_to_cbz_file_name == True
                            and file.extension == ".cbz"
                        ):
                            rename += " #" + volume_number
                    else:
                        volume_number = str(int(number))
                        rename += volume_number
                        if (
                            add_issue_number_to_cbz_file_name == True
                            and file.extension == ".cbz"
                        ):
                            rename += " #" + volume_number
                elif isinstance(number, float):
                    if number < 10:
                        volume_number = str(number).zfill(4)
                        rename += volume_number
                        if (
                            add_issue_number_to_cbz_file_name == True
                            and file.extension == ".cbz"
                        ):
                            rename += " #" + volume_number
                    else:
                        volume_number = str(number)
                        rename += volume_number
                        if (
                            add_issue_number_to_cbz_file_name == True
                            and file.extension == ".cbz"
                        ):
                            rename += " #" + volume_number
            if isinstance(file.volume_year, int):
                rename += " (" + str(file.volume_year) + ")"
            if len(file.extras) != 0:
                for extra in file.extras:
                    rename += " " + extra
            rename += file.extension
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
                        send_change_message(
                            "\n\t\tRenamed: " + file.name + " to \n\t\t" + rename
                        )
                    else:
                        user_input = input("\tRename (y or n): ")
                        if (
                            user_input.lower().strip() == "y"
                            or user_input.lower().strip() == "yes"
                        ):
                            rename_file(
                                file.path,
                                os.path.join(file.root, rename),
                                file.root,
                                file.extensionless_name,
                                get_extensionless_name(rename),
                            )
                            send_change_message(
                                "\n\t\tRenamed: " + file.name + " to \n\t\t" + rename
                            )
                    file.series_name = get_series_name_from_file_name(rename, file.root)
                    file.volume_year = get_volume_year(rename)
                    file.volume_number = remove_everything_but_volume_num(
                        [rename], file.root
                    )
                    file.name = rename
                    file.extensionless_name = get_extensionless_name(rename)
                    file.basename = os.path.basename(rename)
                    file.path = os.path.join(file.root, rename)
                    file.extensionless_path = os.path.splitext(file.path)[0]
                    file.extras = get_extras(rename, file.root)
                except OSError as ose:
                    send_error_message(ose)


# Replaces any pesky double spaces
def remove_dual_space(s):
    return re.sub("(\s{2,})", " ", s)


# Removes common words that to improve matching accuracy for titles that sometimes
# include them, and sometimes don't.
def remove_common_words(s):
    common_words_to_remove = [
        "the",
        "a",
        "and",
        "&",
        "I",
        "Complete",
        "Series",
        "of",
        "Novel",
        "Light Novel",
        "Manga",
        "Collection",
    ]
    for word in common_words_to_remove:
        s = re.sub(rf"\b{word}\b", "", s, flags=re.IGNORECASE).strip()
    return s.strip()


# Replaces all numbers
def remove_numbers(s):
    return re.sub("([0-9]+)", "", s, flags=re.IGNORECASE)


# Returns a string without punctuation.
def remove_punctuation(s):
    return convert_to_ascii(
        remove_dual_space(remove_common_words(re.sub(r"[^\w\s+]", " ", s)))
    )


# convert string to acsii
def convert_to_ascii(s):
    return "".join(i for i in s if ord(i) < 128)


class Result:
    def __init__(self, dir, score):
        self.dir = dir
        self.score = score


# gets the user passed result from an epub file
def get_meta_from_file(file, search, extension):
    result = None
    if extension == ".epub":
        with zipfile.ZipFile(file, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".opf"):
                    opf_file = zf.open(name)
                    opf_file_contents = opf_file.read()
                    lines = opf_file_contents.decode("utf-8")
                    search = re.search(search, lines, re.IGNORECASE)
                    if search:
                        result = search.group(0)
                        result = re.sub(r"<\/?.*>", "", result)
                        result = re.sub(
                            r"(series_id:NONE)", "", result, flags=re.IGNORECASE
                        )
                        if re.search(r"(series_id:.*,)", result, re.IGNORECASE):
                            result = re.sub(r",.*", "", result).strip()
                        break
    elif extension == ".cbz":
        zip_comment = get_zip_comment(file)
        if zip_comment:
            search = re.search(search, zip_comment, re.IGNORECASE)
            if search:
                result = search.group(0)
                result = re.sub(r"(series_id:NONE)", "", result, flags=re.IGNORECASE)
                if re.search(r"(series_id:.*,)", result, re.IGNORECASE):
                    result = re.sub(r",.*", "", result).strip()
    return result


# gets the toc.xhtml file from the epub file and checks the toc for premium content
def get_toc(file):
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
    return bonus_content_found


def check_upgrade(existing_root, dir, file):
    existing_dir = os.path.join(existing_root, dir)
    clean_existing = os.listdir(existing_dir)
    clean_and_sort(existing_dir, clean_existing)
    cbz_percent_download_folder = get_cbz_percent_for_folder([file.name])
    cbz_percent_existing_folder = get_cbz_percent_for_folder(clean_existing)
    epub_percent_download_folder = get_epub_percent_for_folder([file.name])
    epub_percent_existing_folder = get_epub_percent_for_folder(clean_existing)
    if (
        (cbz_percent_download_folder and cbz_percent_existing_folder)
        >= required_matching_percentage
    ) or (
        (epub_percent_download_folder and epub_percent_existing_folder)
        >= required_matching_percentage
    ):
        download_dir_volumes = [file]
        reorganize_and_rename(download_dir_volumes, existing_dir)
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
        send_change_message("\t\tFound existing series: " + existing_dir)
        remove_duplicate_releases_from_download(
            existing_dir_volumes,
            download_dir_volumes,
        )
        if len(download_dir_volumes) != 0:
            volume = download_dir_volumes[0]
            if isinstance(
                volume.volume_number,
                float,
            ):
                send_change_message(
                    "\t\tVolume: " + volume.name + " does not exist in: " + existing_dir
                )
                send_change_message(
                    "\t\tMoving: " + volume.name + " to " + existing_dir
                )
                move_file(volume, existing_dir)
                check_and_delete_empty_folder(volume.root)
                return True
        else:
            check_and_delete_empty_folder(file.root)
            return True
    else:
        return False


# remove duplicates elements from the passed in list
def remove_duplicates(items):
    return list(dict.fromkeys(items))


# Return the zip comment for the passed zip file
def get_zip_comment(zip_file):
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        return zip_ref.comment.decode("utf-8")


# Checks for an existing series by pulling the series name from each elidable file in the downloads_folder
# and comparing it to an existin folder within the user's library.
def check_for_existing_series_and_move():
    for download_folder in download_folders:
        if os.path.exists(download_folder):
            for root, dirs, files in os.walk(download_folder):
                clean_and_sort(root, files, dirs)
                volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(
                        [f for f in files if os.path.isfile(os.path.join(root, f))],
                        root,
                    )
                )
                for file in volumes:
                    if not file.multi_volume:
                        done = False
                        dir_clean = file.series_name
                        for path in paths:
                            if os.path.exists(path) and done == False:
                                try:
                                    os.chdir(path)
                                    path_dirs = [
                                        f for f in os.listdir(path) if os.path.isdir(f)
                                    ]
                                    clean_and_sort(path, dirs=path_dirs)
                                    global folder_accessor
                                    folder_accessor = Folder(
                                        path,
                                        path_dirs,
                                        os.path.basename(os.path.dirname(path)),
                                        os.path.basename(path),
                                        [""],
                                    )
                                    current_folder_path = folder_accessor.root
                                    download_folder_basename = os.path.basename(
                                        download_folder
                                    )
                                    if not re.search(
                                        download_folder_basename,
                                        current_folder_path,
                                        re.IGNORECASE,
                                    ):
                                        print("\nFile: " + file.name)
                                        print("Looking for: " + dir_clean)
                                        print("\tInside of: " + folder_accessor.root)
                                        scores = []
                                        for dir in folder_accessor.dirs:
                                            downloaded_file_series_name = (
                                                (str(dir_clean)).lower()
                                            ).strip()
                                            downloaded_file_series_name = (
                                                remove_punctuation(
                                                    downloaded_file_series_name
                                                )
                                            ).lower()
                                            existing_series_folder_from_library = (
                                                remove_punctuation(dir)
                                            ).lower()
                                            similarity_score = similar(
                                                existing_series_folder_from_library,
                                                downloaded_file_series_name,
                                            )
                                            print(
                                                "\t\tCHECKING: "
                                                + downloaded_file_series_name
                                                + "\n\t\tAGAINST: "
                                                + existing_series_folder_from_library
                                                + "\n\t\tSCORE: "
                                                + str(similarity_score)
                                                + "\n"
                                            )
                                            scores.append(Result(dir, similarity_score))
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
                                                    '\t\tSimilarity between: "'
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
                                                )
                                                if done:
                                                    break
                                                else:
                                                    continue
                                        if not done and match_through_isbn_or_series_id:
                                            directories_found = []
                                            download_file_isbn = None
                                            download_file_isbn = get_meta_from_file(
                                                file.path,
                                                "(9([-_. :]+)?7([-_. :]+)?(8|9)(([-_. :]+)?[0-9]){10})",
                                                file.extension,
                                            )
                                            download_file_series_id = None
                                            download_file_series_id = (
                                                get_meta_from_file(
                                                    file.path,
                                                    "series_id:.*",
                                                    file.extension,
                                                )
                                            )
                                            if (
                                                download_file_isbn
                                                or download_file_series_id
                                            ):
                                                print(
                                                    "\t\tChecking existing library for a matching ISBN or Series ID... (may take awhile depending on library size)"
                                                )
                                                for dir, subdir, files in os.walk(path):
                                                    if done:
                                                        break
                                                    clean_and_sort(dir, files, subdir)
                                                    for f in files:
                                                        extension = os.path.splitext(f)[
                                                            1
                                                        ]
                                                        existing_file_isbn = None
                                                        existing_file_isbn = get_meta_from_file(
                                                            os.path.join(dir, f),
                                                            "(9([-_. :]+)?7([-_. :]+)?(8|9)(([-_. :]+)?[0-9]){10})",
                                                            file.extension,
                                                        )
                                                        existing_file_series_id = None
                                                        existing_file_series_id = (
                                                            get_meta_from_file(
                                                                os.path.join(dir, f),
                                                                "series_id:.*",
                                                                file.extension,
                                                            )
                                                        )
                                                        if (
                                                            existing_file_isbn
                                                            or existing_file_series_id
                                                        ):
                                                            if (
                                                                download_file_isbn
                                                                and existing_file_isbn
                                                            ):
                                                                print(
                                                                    (
                                                                        "\t\t("
                                                                        + str(
                                                                            download_file_isbn
                                                                        )
                                                                        + " - "
                                                                        + str(
                                                                            existing_file_isbn
                                                                        )
                                                                        + ")"
                                                                    ),
                                                                    end="\r",
                                                                )
                                                            if (
                                                                download_file_series_id
                                                                and existing_file_series_id
                                                            ):
                                                                print(
                                                                    (
                                                                        "\t\t("
                                                                        + str(
                                                                            download_file_series_id
                                                                        )
                                                                        + " - "
                                                                        + str(
                                                                            existing_file_series_id
                                                                        )
                                                                        + ")"
                                                                    ),
                                                                    end="\r",
                                                                )
                                                            if (
                                                                (
                                                                    download_file_isbn
                                                                    == existing_file_isbn
                                                                )
                                                                and (
                                                                    download_file_isbn
                                                                    and existing_file_isbn
                                                                )
                                                            ) or (
                                                                (
                                                                    download_file_series_id
                                                                    == existing_file_series_id
                                                                )
                                                                and (
                                                                    download_file_series_id
                                                                    and existing_file_series_id
                                                                )
                                                            ):
                                                                directories_found.append(
                                                                    dir
                                                                )
                                            if directories_found:
                                                directories_found = remove_duplicates(
                                                    directories_found
                                                )
                                                if len(directories_found) == 1:
                                                    send_change_message(
                                                        "\t\t\tMach found in: "
                                                        + directories_found[0]
                                                    )
                                                    base = os.path.basename(
                                                        directories_found[0]
                                                    )
                                                    done = check_upgrade(
                                                        folder_accessor.root,
                                                        base,
                                                        file,
                                                    )
                                                else:
                                                    print(
                                                        "\t\t\tMatching ISBN or Series ID found in multiple directories."
                                                    )
                                                    for d in directories_found:
                                                        print("\t\t\t\t" + d)
                                                    print(
                                                        "\t\t\tDisregarding Matches..."
                                                    )
                                            else:
                                                print(
                                                    "\t\t\tNo match found in: " + path
                                                )
                                except FileNotFoundError:
                                    send_error_message(
                                        "\nERROR: " + path + " is not a valid path.\n"
                                    )


# Removes any unnecessary junk through regex in the folder name and returns the result
def get_series_name(dir):
    dir = (
        re.sub(
            r"(\b|\s)((\s|)-(\s|)|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)([-_. ]|)([-_. ]|)([0-9]+)(\b|\s).*",
            "",
            dir,
            flags=re.IGNORECASE,
        )
    ).strip()
    dir = (re.sub(r"(\([^()]*\))|(\[[^\[\]]*\])|(\{[^\{\}]*\})", "", dir)).strip()
    dir = (re.sub(r"(\(|\)|\[|\]|{|})", "", dir, flags=re.IGNORECASE)).strip()
    return dir


# Renames the folders in our download directory.
# EX: You have a folder named "I Was Reincarnated as the 7th Prince so I Can Take My Time Perfecting My Magical Ability (Digital) (release-group)"
# Said folder would be renamed to "I Was Reincarnated as the 7th Prince so I Can Take My Time Perfecting My Magical Ability"
def rename_dirs_in_download_folder():
    for download_folder in download_folders:
        if os.path.exists(download_folder):
            try:
                download_folder_dirs = [
                    f
                    for f in os.listdir(download_folder)
                    if os.path.isdir(join(download_folder, f))
                ]
                download_folder_files = [
                    f
                    for f in os.listdir(download_folder)
                    if os.path.isfile(join(download_folder, f))
                ]
                clean_and_sort(
                    download_folder, download_folder_files, download_folder_dirs
                )
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
                    full_file_path = os.path.join(folder_accessor.root, folderDir)
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
                                r"(\b|\s)((\s|)-(\s|)|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc|)(\.|)([-_. ]|)([0-9]+)(\b|\s)",
                                folderDir,
                                re.IGNORECASE,
                            )
                            or re.search(r"\bPremium\b", folderDir, re.IGNORECASE)
                        ):
                            dir_clean = get_series_name(folderDir)
                            if not os.path.isdir(
                                os.path.join(folder_accessor.root, dir_clean)
                            ):
                                try:
                                    os.rename(
                                        os.path.join(folder_accessor.root, folderDir),
                                        os.path.join(folder_accessor.root, dir_clean),
                                    )
                                except OSError as e:
                                    send_error_message(e)
                            elif (
                                os.path.isdir(
                                    os.path.join(folder_accessor.root, dir_clean)
                                )
                                and dir_clean != ""
                            ):
                                if os.path.join(
                                    folder_accessor.root, folderDir
                                ) != os.path.join(folder_accessor.root, dir_clean):
                                    for root, dirs, files in os.walk(
                                        os.path.join(folder_accessor.root, folderDir)
                                    ):
                                        remove_hidden_files(files, root)
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
                                                    new_location_folder, file.name
                                                )
                                            ):
                                                move_file(
                                                    file,
                                                    os.path.join(
                                                        download_folder, dir_clean
                                                    ),
                                                )
                                            else:
                                                send_error_message(
                                                    "File: "
                                                    + file.name
                                                    + " already exists in: "
                                                    + os.path.join(
                                                        download_folder, dir_clean
                                                    )
                                                )
                                                send_error_message(
                                                    "Removing duplicate from downloads."
                                                )
                                                remove_file(
                                                    os.path.join(
                                                        folder_accessor2.root, file.name
                                                    )
                                                )
                                        check_and_delete_empty_folder(
                                            folder_accessor2.root
                                        )
            except FileNotFoundError:
                send_error_message(
                    "\nERROR: " + download_folder + " is not a valid path.\n"
                )
        else:
            if download_folder == "":
                send_error_message("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + download_folder + " is an invalid path.\n")


def add_to_list(item, list):
    if item != "" and not item in list:
        list.append(item)


def get_extras(file_name, root):
    series_name = get_series_name_from_file_name(file_name, root)
    if (
        re.search(re.escape(series_name), file_name, re.IGNORECASE)
        and series_name != ""
    ):
        file_name = re.sub(
            re.escape(series_name), "", file_name, flags=re.IGNORECASE
        ).strip()
    results = re.findall(r"(\{|\(|\[)(.*?)(\]|\)|\})", file_name, flags=re.IGNORECASE)
    modified = []
    keywords = [
        "Premium",
        "Complete",
        "Fanbook",
        "Short Stories",
        "Short Story",
        "Omnibus",
    ]
    keywords_two = ["Extra", "Arc"]
    for result in results:
        combined = ""
        for r in result:
            combined += r
        add_to_list(combined, modified)
    for item in modified[:]:
        if re.search(
            r"(\{|\(|\[)(Premium|J-Novel Club Premium)(\]|\)|\})", item, re.IGNORECASE
        ) or re.search(r"\((\d{4})\)", item, re.IGNORECASE):
            modified.remove(item)
        if re.search(
            r"(\{|\(|\[)(Omnibus|Omnibus Edition)(\]|\)|\})", item, re.IGNORECASE
        ):
            modified.remove(item)
        if re.search(r"(Extra)(\]|\)|\})", item, re.IGNORECASE):
            modified.remove(item)
        if re.search(r"(\{|\(|\[)Part([-_. ]|)([0-9]+)(\]|\)|\})", item, re.IGNORECASE):
            modified.remove(item)
        if re.search(
            r"(\{|\(|\[)Season([-_. ]|)([0-9]+)(\]|\)|\})", item, re.IGNORECASE
        ):
            modified.remove(item)
        if re.search(
            r"(\{|\(|\[)(Chapter|Ch|Chpt|Chpter|C)([-_. ]|)([0-9]+)(\.[0-9]+|)(([-_. ]|)([0-9]+)(\.[0-9]+|)|)(\]|\)|\})",
            item,
            re.IGNORECASE,
        ):
            modified.remove(item)
    for keyword in keywords:
        if re.search(keyword, file_name, re.IGNORECASE):
            add_to_list("[" + keyword.strip() + "]", modified)
    for keyword_two in keywords_two:
        if re.search(
            rf"(([A-Za-z]|[0-9]+)|)+ {keyword_two}([-_ ]|)([0-9]+|([A-Za-z]|[0-9]+)+|)",
            file_name,
            re.IGNORECASE,
        ):
            result = re.search(
                rf"(([A-Za-z]|[0-9]+)|)+ {keyword_two}([-_ ]|)([0-9]+|([A-Za-z]|[0-9]+)+|)",
                file_name,
                re.IGNORECASE,
            ).group()
            if result != "Episode " or (
                result != "Arc " | result != "arc " | result != "ARC "
            ):
                add_to_list("[" + result.strip() + "]", modified)
    if re.search(r"(\s|\b)Part([-_. ]|)([0-9]+)", file_name, re.IGNORECASE):
        result = re.search(
            r"(\s|\b)Part([-_. ]|)([0-9]+)", file_name, re.IGNORECASE
        ).group()
        add_to_list("[" + result.strip() + "]", modified)
    if re.search(r"(\s|\b)Season([-_. ]|)([0-9]+)", file_name, re.IGNORECASE):
        result = re.search(
            r"(\s|\b)Season([-_. ]|)([0-9]+)", file_name, re.IGNORECASE
        ).group()
        add_to_list("[" + result.strip() + "]", modified)
    if re.search(
        r"(\s|\b)(Chapter|Ch|Chpt|Chpter|C)([-_. ]|)([0-9]+)(\.[0-9]+|)(([-_. ]|)([0-9]+)(\.[0-9]+|)|)(\s|\b)",
        file_name,
        re.IGNORECASE,
    ):
        result = re.search(
            r"(\s|\b)(Chapter|Ch|Chpt|Chpter|C)([-_. ]|)([0-9]+)(\.[0-9]+|)(([-_. ]|)([0-9]+)(\.[0-9]+|)|)(\s|\b)",
            file_name,
            re.IGNORECASE,
        ).group()
        add_to_list("[" + result.strip() + "]", modified)
    # Move Premium to the beginning
    for item in modified:
        if re.search(r"Premium", item, re.IGNORECASE):
            modified.remove(item)
            modified.insert(0, item)
    return modified


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


# Determines if the file name contains an issue number.
def contains_issue_number(file_name, volume_number):
    issue_number = "#" + volume_number
    if re.search(issue_number, file_name, re.IGNORECASE):
        return True
    else:
        return False


# Renames files.
def rename_files_in_download_folders():
    # Set to True for user input renaming, otherwise False
    # Useful for testing
    global manual_rename
    for path in download_folders:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                clean_and_sort(root, files, dirs)
                volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(
                        [f for f in files if os.path.isfile(os.path.join(root, f))],
                        root,
                    )
                )
                print("\nLocation: " + root)
                print("Searching for files to rename...")
                for file in volumes:
                    try:
                        multi_volume = False
                        result = re.search(
                            r"(\s+)?\-?(\s+)?(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.\s?|\s?|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\]|\)|\})?(\s|\.epub|\.cbz)",
                            file.name,
                            re.IGNORECASE,
                        )
                        if result or (
                            file.is_one_shot
                            and add_volume_one_number_to_one_shots == True
                        ):
                            if file.is_one_shot:
                                result = preferred_volume_renaming_format + "01"
                            else:
                                result = result.group().strip()
                            result = re.sub(r"[\[\(\{\]\)\}\_]", "", result).strip()
                            keyword = re.search(
                                r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)",
                                result,
                                re.IGNORECASE,
                            )
                            keyword = keyword.group(0)
                            result = re.sub(
                                rf"(-)(\s+)?{keyword}",
                                keyword,
                                result,
                                flags=re.IGNORECASE,
                                count=1,
                            ).strip()
                            for ext in file_extensions:
                                result = re.sub("\." + ext, "", result).strip()
                            results = re.split(
                                r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)",
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
                                        if check_for_multi_volume_file(r):
                                            multi_volume = True
                                            volume_numbers = (
                                                convert_list_of_numbers_to_array(r)
                                            )
                                            for number in volume_numbers:
                                                try:
                                                    if isint(number):
                                                        number = int(number)
                                                    elif isfloat(number):
                                                        number = float(number)
                                                except ValueError as ve:
                                                    print(ve)
                                                if number == volume_numbers[-1]:
                                                    modified.append(number)
                                                else:
                                                    modified.append(number)
                                                    modified.append("-")
                                        else:
                                            try:
                                                if isint(r):
                                                    r = int(r)
                                                    modified.append(r)
                                                elif isfloat(r):
                                                    r = float(r)
                                                    modified.append(r)
                                            except ValueError as ve:
                                                print(ve)
                                    if isinstance(r, str):
                                        if r != "":
                                            if re.search(
                                                r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)",
                                                r,
                                                re.IGNORECASE,
                                            ):
                                                modified.append(
                                                    re.sub(
                                                        r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)",
                                                        preferred_volume_renaming_format,
                                                        r,
                                                        flags=re.IGNORECASE,
                                                    )
                                                )
                            if ((len(modified) == 2 and len(results) == 2)) or (
                                multi_volume
                                and (
                                    len(modified) == len(results) + len(volume_numbers)
                                )
                            ):
                                combined = ""
                                for item in modified:
                                    if type(item) == int:
                                        if item < 10:
                                            item = str(item).zfill(2)
                                        combined += str(item)
                                    elif type(item) == float:
                                        if item < 10:
                                            item = str(item).zfill(4)
                                        combined += str(item)
                                    elif isinstance(item, str):
                                        combined += item
                                without_keyword = re.sub(
                                    r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)",
                                    "",
                                    combined,
                                    flags=re.IGNORECASE,
                                )
                                issue_number = "#" + without_keyword
                                if (
                                    add_issue_number_to_cbz_file_name == True
                                    and file.extension == ".cbz"
                                ):
                                    combined += " " + issue_number
                                if file.extension == ".epub":
                                    if (
                                        check_for_bonus_xhtml(file.path)
                                        or get_toc(file.path)
                                    ) and not re.search(
                                        r"\bPremium\b", file.name, re.IGNORECASE
                                    ):
                                        print(
                                            "\nBonus content found inside epub, adding [Premium] to file name."
                                        )
                                        combined += " [Premium]"
                                if not file.is_one_shot:
                                    replacement = re.sub(
                                        r"((?<![A-Za-z]+)[-_. ]\s+|)(\[|\(|\{)?(LN|Light Novel|Novel|Book|Volume|Vol|v|第|Disc)(\.|)([-_. ]|)(([0-9]+)(([-_. ]|)([0-9]+)|))(\s#([0-9]+)(([-_. ]|)([0-9]+)|))?(\]|\)|\})?",
                                        combined,
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )
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
                                    extras = get_extras(file.name, file.root)
                                    for extra in extras:
                                        replacement += " " + extra
                                    replacement += file.extension
                                replacement = re.sub(r"\?", " ", replacement).strip()
                                replacement = remove_dual_space(
                                    re.sub(r"_", " ", replacement)
                                ).strip()
                                if file.name != replacement:
                                    try:
                                        if not (
                                            os.path.isfile(
                                                os.path.join(root, replacement)
                                            )
                                        ):
                                            user_input = ""
                                            if not manual_rename:
                                                user_input = "y"
                                            else:
                                                print("\n" + file.name)
                                                print(replacement)
                                                user_input = input(
                                                    "\tRename (y or n): "
                                                )
                                            if user_input == "y":
                                                os.rename(
                                                    os.path.join(root, file.name),
                                                    os.path.join(root, replacement),
                                                )
                                                if os.path.isfile(
                                                    os.path.join(root, replacement)
                                                ):
                                                    send_change_message(
                                                        "\tSuccessfully renamed file: "
                                                        + file.name
                                                        + " to "
                                                        + replacement
                                                    )
                                                    for (
                                                        image_extension
                                                    ) in image_extensions:
                                                        image_file = (
                                                            file.extensionless_name
                                                            + "."
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
                                                                + "."
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
                                                                send_error_message(ose)
                                                else:
                                                    send_error_message(
                                                        "\nRename failed on: "
                                                        + file.name
                                                    )
                                        if os.path.isfile(
                                            os.path.join(root, replacement)
                                        ):
                                            file = upgrade_to_volume_class(
                                                upgrade_to_file_class(
                                                    [replacement],
                                                    root,
                                                )
                                            )[0]
                                    except OSError as ose:
                                        send_error_message(ose)
                            else:
                                send_error_message(
                                    "More than two for either array: " + file.name
                                )
                                print("Modified Array:")
                                for i in modified:
                                    print("\t" + str(i))
                                print("Results Array:")
                                for b in results:
                                    print("\t" + str(b))
                    except Exception as e:
                        send_error_message(
                            "\nERROR: " + str(e) + " (" + file.name + ")"
                        )
                    if not file.multi_volume:
                        reorganize_and_rename([file], file.series_name)
        else:
            if path == "":
                print("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + path + " is an invalid path.\n")


# check if volume file name is a chapter
def contains_chapter_keywords(file_name):
    return re.search(
        r"(((ch|c|d|chapter|chap)([-_. ]+)?([0-9]+))|\s+([0-9]+)(\.[0-9]+)?(\s+|#\d+|\.cbz))",
        file_name,
        re.IGNORECASE,
    )


# Checks for any exception keywords that will prevent the chapter release from being deleted.
def check_for_exception_keywords(file_name):
    return re.search(r"Extra|One(-|)shot", file_name, re.IGNORECASE)


# Deletes chapter files from the download folder.
def delete_chapters_from_downloads():
    try:
        for path in download_folders:
            if os.path.exists(path):
                os.chdir(path)
                for root, dirs, files in os.walk(path):
                    # clean_and_sort(root, files, dirs)
                    remove_ignored_folders(dirs)
                    dirs.sort()
                    files.sort()
                    remove_hidden_files(files, root)
                    for file in files:
                        if (
                            contains_chapter_keywords(file)
                            and not contains_volume_keywords(file)
                        ) and not (check_for_exception_keywords(file)):
                            if file.endswith(".cbz") or file.endswith(".zip"):
                                send_change_message(
                                    "\n\t\tFile: "
                                    + file
                                    + " does not contain a volume keyword"
                                    + "\n\t\tLocation: "
                                    + root
                                    + "\n\t\tDeleting chapter release."
                                )
                                remove_file(os.path.join(root, file))
                for root, dirs, files in os.walk(path):
                    clean_and_sort(root, files, dirs)
                    for dir in dirs:
                        check_and_delete_empty_folder(os.path.join(root, dir))
            else:
                if path == "":
                    print("\nERROR: Path cannot be empty.")
                else:
                    print("\nERROR: " + path + " is an invalid path.\n")
    except Exception as e:
        send_error_message(e)


# execute terminal command
def execute_command(command):
    if command != "":
        try:
            subprocess.call(command, shell=True)
        except Exception as e:
            send_error_message(e)


# remove all non-images from list of files
def remove_non_images(files):
    clean_list = []
    for file in files:
        extension = re.sub(r"\.", "", get_file_extension(os.path.basename(file)))
        if extension in image_extensions:
            clean_list.append(file)
    return clean_list


# Finds and extracts the internal cover from a cbz or epub file
def find_and_extract_cover(file):
    # check if the file is a valid zip file
    if zipfile.is_zipfile(file.path):
        epub_cover_path = ""
        if file.extension == ".epub":
            epub_cover_path = get_epub_cover(file.path)
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
            zip_list.sort()
            if zip_list:
                if not epub_cover_path:
                    for image_file in zip_list:
                        if (
                            re.search(
                                r"(\b(Cover([0-9]+|)|CoverDesign)\b)",
                                image_file,
                                re.IGNORECASE,
                            )
                            or re.search(
                                r"(\b(p000|page_000)\b)", image_file, re.IGNORECASE
                            )
                            or re.search(
                                r"(\bindex[-_. ]1[-_. ]1\b)", image_file, re.IGNORECASE
                            )
                            or re.search(
                                r"(9([-_. :]+)?7([-_. :]+)?(8|9)(([-_. :]+)?[0-9]){10})",
                                image_file,
                                re.IGNORECASE,
                            )
                        ):
                            print("\t\tCover Found: " + image_file)
                            image_extension = get_file_extension(
                                os.path.basename(image_file)
                            )
                            if image_extension == ".jpeg":
                                image_extension = ".jpg"
                            with zip_ref.open(image_file) as image_file_ref:
                                # save image_file_ref as file.extensionless_name + image_extension to file.root
                                with open(
                                    os.path.join(
                                        file.root,
                                        file.extensionless_name + image_extension,
                                    ),
                                    "wb",
                                ) as image_file_ref_out:
                                    image_file_ref_out.write(image_file_ref.read())
                            if compress_image_option:
                                compress_image(
                                    os.path.join(
                                        file.root,
                                        file.extensionless_name + image_extension,
                                    )
                                )
                                image_extension = ".jpg"
                            return file.extensionless_name + image_extension
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
                        with open(
                            os.path.join(
                                file.root,
                                file.extensionless_name + image_extension,
                            ),
                            "wb",
                        ) as default_cover_ref_out:
                            default_cover_ref_out.write(default_cover_ref.read())
                    if compress_image_option:
                        compress_image(
                            os.path.join(
                                file.root,
                                file.extensionless_name + image_extension,
                            )
                        )
                        image_extension = ".jpg"
                    return file.extensionless_name + image_extension
                else:
                    print("\t\tCover Found: " + epub_cover_path)
                    epub_path_extension = get_file_extension(
                        os.path.basename(epub_cover_path)
                    )
                    if epub_path_extension == ".jpeg":
                        epub_path_extension = ".jpg"
                    with zip_ref.open(epub_cover_path) as epub_cover_ref:
                        # save image_file_ref as file.extensionless_name + image_extension to file.root
                        with open(
                            os.path.join(
                                file.root,
                                file.extensionless_name + epub_path_extension,
                            ),
                            "wb",
                        ) as epub_cover_ref_out:
                            epub_cover_ref_out.write(epub_cover_ref.read())
                    if compress_image_option:
                        compress_image(
                            os.path.join(
                                file.root,
                                file.extensionless_name + epub_path_extension,
                            )
                        )
                        epub_path_extension = ".jpg"
                    return file.extensionless_name + epub_path_extension

    else:
        print("\nFile: " + file.name + " is not a valid zip file.")
    return False


# Checks if a volume series cover exists in the passed Directory
def check_for_series_cover(path):
    # get list of files from directory
    files = os.listdir(path)
    # remove hidden files
    remove_hidden_files(files, path)
    for file in files:
        lower_extensionless_name_base = os.path.basename(
            get_extensionless_name(file).lower()
        )
        # file name without extension
        if lower_extensionless_name_base == "cover":
            return True
    return False


# Extracts the covers out from our cbz and epub files
def extract_covers():
    print("\nLooking for covers to extract...")
    for path in paths:
        if os.path.exists(path):
            os.chdir(path)
            for root, dirs, files in os.walk(path):
                global folder_accessor
                clean_and_sort(root, files, dirs)
                remove_ignored_folders(dirs)
                dirs.sort()
                files.sort()
                remove_hidden_files(files, root)
                print("\nRoot: " + root)
                print("Dirs: " + str(dirs))
                print("Files: " + str(files))
                folder_accessor = Folder(
                    root,
                    dirs,
                    os.path.basename(os.path.dirname(root)),
                    os.path.basename(root),
                    upgrade_to_file_class(files, root),
                )
                global image_count
                global files_with_no_cover
                for file in folder_accessor.files:
                    update_stats(file)
                    try:
                        has_cover = False
                        printed = False
                        cover = ""
                        for extension in image_extensions:
                            potential_cover = os.path.join(
                                file.root, file.extensionless_path + "." + extension
                            )
                            if os.path.isfile(potential_cover):
                                cover = potential_cover
                                has_cover = True
                                break
                        if not has_cover:
                            if not printed:
                                print("\tFile: " + file.name)
                                printed = True
                            print("\t\tFile does not have a cover.")
                            result = find_and_extract_cover(file)
                            if result:
                                image_count += 1
                                print("\t\tCover successfully extracted.")
                                has_cover = True
                                cover = result
                            else:
                                print("\t\tCover not found.")
                                files_with_no_cover.append(file)
                        else:
                            image_count += 1
                        if (
                            (
                                is_volume_one(file.name)
                                or is_one_shot(file.name, file.root)
                            )
                            and not check_for_series_cover(file.root)
                            and has_cover
                            and cover
                        ):
                            if not printed:
                                print("\tFile: " + file.name)
                                printed = True
                            print("\t\tMissing volume one cover.")
                            print("\t\tFound volume one cover.")
                            cover_extension = get_file_extension(
                                os.path.basename(cover)
                            )
                            if os.path.isfile(
                                os.path.join(file.root, os.path.basename(cover))
                            ):
                                shutil.copy(
                                    os.path.join(file.root, os.path.basename(cover)),
                                    os.path.join(file.root, "cover" + cover_extension),
                                )
                                print("\t\tCopied cover as series cover.")
                            else:
                                print(
                                    "\t\tCover does not exist at: "
                                    + str(
                                        os.path.join(file.root, os.path.basename(cover))
                                    )
                                )
                    except Exception as e:
                        send_error_message(
                            "\nERROR in extract_covers(): "
                            + str(e)
                            + " with file: "
                            + file.name
                        )
        else:
            if path == "":
                print("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + path + " is an invalid path.\n")


def print_stats():
    print("\nFor all paths.")
    print("Total Files Found: " + str(file_count))
    print("\t" + str(cbz_count) + " were cbz files")
    print("\t" + str(cbr_count) + " were cbr files")
    print("\t" + str(epub_count) + " were epub files")
    print("\tof those we found " + str(image_count) + " had a cover image file.")
    if len(files_with_no_cover) != 0:
        print(
            "\nRemaining files without covers (" + str(len(files_with_no_cover)) + "):"
        )
        for lonely_file in files_with_no_cover:
            print("\t" + lonely_file)
    if len(errors) != 0:
        print("\nErrors (" + str(len(errors)) + "):")
        for error in errors:
            print("\t" + str(error))


def delete_unacceptable_files():
    try:
        for path in download_folders:
            if os.path.exists(path):
                os.chdir(path)
                for root, dirs, files in os.walk(path):
                    # clean_and_sort(root, files, dirs)
                    remove_ignored_folders(dirs)
                    dirs.sort()
                    files.sort()
                    remove_hidden_files(files, root)
                    for file in files:
                        extension = get_file_extension(file)
                        if extension in unaccepted_file_extensions:
                            remove_file(os.path.join(root, file))
                for root, dirs, files in os.walk(path):
                    clean_and_sort(root, files, dirs)
                    for dir in dirs:
                        check_and_delete_empty_folder(os.path.join(root, dir))
            else:
                if path == "":
                    print("\nERROR: Path cannot be empty.")
                else:
                    print("\nERROR: " + path + " is an invalid path.\n")
    except Exception as e:
        send_error_message(e)


# execute terminal command
def execute_command(command):
    if command != "":
        try:
            subprocess.call(command, shell=True)
        except Exception as e:
            send_error_message(e)


class BookwalkerBook:
    def __init__(
        self, title, volume_number, date, is_released, price, url, thumbnail, book_type
    ):
        self.title = title
        self.volume_number = volume_number
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


def scrape_url(url, strainer=None):
    try:
        global session_object
        if not session_object:
            session_object = requests.Session()
        page_obj = session_object.get(url)
        if page_obj.status_code == 403:
            print("\nTOO MANY REQUESTS TO BOOKWALKER, WERE BEING RATE-LIMTIED!")
        soup = None
        if strainer:
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
                    combined_series_item.books = sorted(
                        combined_series_item.books, key=lambda x: x.volume_number
                    )
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


def search_bookwalker(query, type, print_info=False):
    avoid_rate_limit = True
    sleep_timer = 3
    manual_input = True
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
    startTime = datetime.now()
    done = False
    search_type = type
    count = 0
    page_count = 1
    page_count_url = "&page=" + str(page_count)
    search = urllib.parse.quote(query)
    base_url = "https://global.bookwalker.jp/search/?word="
    if search_type.lower() == "m":
        print("\tChecking: " + query + " [MANGA]")
    elif search_type.lower() == "l":
        print("\tChecking: " + query + " [NOVEL]")
    while page_count < total_pages_to_scrape + 1:
        page_count_url = "&page=" + str(page_count)
        url = base_url + search + page_count_url
        if search_type.lower() == "m":
            url += bookwalker_manga_category
        elif search_type.lower() == "l":
            url += bookwalker_light_novel_category
        page_count += 1
        # scrape url page
        page = scrape_url(url)
        if page == "":
            print("\t\tError: Empty page")
            errors.append("Empty page")
            continue
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
                title = re.sub(r"[\n\t\r]", "", title)
                if a_tag_chapter or a_tag_simulpub:
                    chapter_releases.append(title)
                    continue
                volume_number = re.search(
                    r"([0-9]+(\.?[0-9]+)?([-_][0-9]+\.?[0-9]+)?)$", title
                )
                if volume_number:
                    if hasattr(volume_number, "group"):
                        volume_number = volume_number.group(1)
                        volume_number = set_num_as_float_or_int(volume_number)
                    else:
                        if title not in no_volume_number:
                            no_volume_number.append(title)
                        continue
                elif title and is_one_shot_bk(title):
                    volume_number = 1
                else:
                    if title not in no_volume_number:
                        no_volume_number.append(title)
                    continue
                if re.search(
                    r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)",
                    title,
                    re.IGNORECASE,
                ):
                    title = re.sub(
                        r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(LN|Light Novel|Novel|Book|Volume|Vol|V|第|Disc)(\.|)([-_. ]|)([0-9]+)(\b|\s).*",
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
                    date,
                    is_released,
                    0.00,
                    url,
                    thumbnail,
                    book_type,
                )
                books.append(book)
            except Exception as e:
                send_error_message(e)
                errors.append(url)
                continue
        if books is not None and len(books) > 1:
            books = sorted(books, key=lambda x: x.volume_number)
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
            clean_and_sort(path, dirs=path_dirs)
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
                clean_and_sort(existing_dir, clean_existing)
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
                type = None
                bookwalker_volumes = None
                if (
                    get_cbz_percent_for_folder([f.name for f in existing_dir_volumes])
                    >= 70
                ):
                    type = "m"
                elif (
                    get_epub_percent_for_folder([f.name for f in existing_dir_volumes])
                    >= 70
                ):
                    type = "l"

                if type and dir:
                    bookwalker_volumes = search_bookwalker(dir, type, False)
                if existing_dir_volumes and bookwalker_volumes:
                    bk_volume_numbers = []
                    ex_volume_numbers = []
                    for bk_volume in bookwalker_volumes:
                        bk_volume_numbers.append(bk_volume.volume_number)
                    for ex_volume in existing_dir_volumes:
                        ex_volume_numbers.append(ex_volume.volume_number)
                    for num in ex_volume_numbers:
                        if num in bk_volume_numbers:
                            for v in bookwalker_volumes:
                                if v.volume_number == num:
                                    bookwalker_volumes.remove(v)
                                    break
                    if len(bookwalker_volumes) > 0:
                        new_releases_on_bookwalker.extend(bookwalker_volumes)
                        for vol in bookwalker_volumes:
                            if vol.is_released:
                                print("\n\t\t[RELEASED]")
                            else:
                                print("\n\t\t[PRE-ORDER]")
                            print("\t\tVolume Number: " + str(vol.volume_number))
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
    pre_orders.sort(key=lambda x: x.date, reverse=False)
    released.sort(key=lambda x: x.date, reverse=False)
    if len(released) > 0:
        print("\nNew Releases:")
        for r in released:
            print("\t" + r.title)
            print("\tVolume " + str(r.volume_number))
            print("\tDate: " + r.date)
            print("\tURL: " + r.url)
            print("\n")
            message = (
                r.date + " " + r.title + " Volume " + str(r.volume_number) + " " + r.url
            )
            write_to_file("released.txt", message, without_date=True, overwrite=False)
    if len(pre_orders) > 0:
        print("\nPre-orders:")
        for p in pre_orders:
            print("\t" + p.title)
            print("\tVolume: " + str(p.volume_number))
            print("\tDate: " + p.date)
            print("\tURL: " + p.url)
            print("\n")
            message = (
                p.date + " " + p.title + " Volume " + str(p.volume_number) + " " + p.url
            )
            write_to_file("pre-orders.txt", message, without_date=True, overwrite=False)


# Checks the epub for bonus.xhtml or bonus[0-9].xhtml
# then returns whether or not it was found.
def check_for_bonus_xhtml(zip):
    zip = zipfile.ZipFile(zip)
    list = zip.namelist()
    for item in list:
        base = os.path.basename(item)
        if re.search(r"(bonus([0-9]+)?\.xhtml)", base, re.IGNORECASE):
            return True
    return False


# Optional features below have been commented out, use at your own risk.
# I don't intend to advertise these on the git page until I consider them
# close to perfect.
def main():
    global bookwalker_check
    parse_my_args()  # parses the user's arguments
    #delete_unacceptable_files()  # deletes any file with an extension in unaccepted_file_extensions from the download_folers
    #delete_chapters_from_downloads()  # deletes chapter releases from the download_folers
    #rename_files_in_download_folders()  # replaces any detected volume keyword that isn't what the user specified up top and restructures them
    #create_folders_for_items_in_download_folder()  # creates folders for any lone files in the root of the download_folders
    #rename_dirs_in_download_folder()  # cleans up any unnessary information in the series folder names within the download_folders
    extract_covers()  # extracts covers from cbz and epub files recursively from the paths passed in
    #check_for_existing_series_and_move()  # finds the corresponding series name in our existing library for the files in download_folders and handles moving, upgrading, and deletion
    #check_for_missing_volumes()  # checks for any missing volumes bewteen the highest detected volume number and the lowest
    #if bookwalker_check:
        # currently slowed down to avoid rate-limiting, advised not to run on each use, but rather once a week
        #check_for_new_volumes_on_bookwalker()  # checks the library against bookwalker for any missing volumes that are released or on pre-order
    print_stats()


if __name__ == "__main__":
    main()
