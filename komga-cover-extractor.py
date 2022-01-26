import os
import re
import zlib
import zipfile
import shutil
import string
import regex as re
import sys
import argparse
import subprocess
from lxml import etree
from genericpath import isfile
from posixpath import join
from difflib import SequenceMatcher
from datetime import datetime

# ************************************
# Created by: Zach Stultz            *
# Git: https://github.com/zachstultz *
# ************************************

download_folders = [  # OPTIONAL [STILL IN TESTING]
    "",
]
paths = [  # [ADD IN THE PATHS YOU WANT SCANNED]
    "",
]
ignored_folder_names = [
    "",
]

# List of file types used throughout the program
file_extensions = ["epub", "cbz", "cbr"]
image_extensions = ["jpg", "jpeg", "png", "tbn"]
series_cover_file_names = ["cover", "poster"]

# Our global folder_accessor
folder_accessor = None

# The remaining files without covers
files_with_no_cover = []

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

# The required file type matching percentage between
# the download folder and the existing folder
required_matching_percentage = 90

# The required score when comparing two strings likeness
required_similarity_score = 0.9790

# The preferred naming format used by rename_files()
# v = v01, Volume = Volume01, and so on.
# IF YOU WANT A SPACE BETWEEN THE TWO, ADD IT IN THE PREFERRED NAMING.
preferred_volume_renaming_format = "v"

# A discord webhook url used to send messages to discord about the changes made.
discord_webhook_url = ""

# Whether or not to add the issue number to the file names
# Useful when using ComicTagger
# TRUE: manga v01 #01 (2001).cbz
# FALSE: manga v01 (2001).cbz
add_issue_number_to_file_name = False

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


# Release Group Class
class Release_Group:
    def __init__(self, name, score):
        self.name = name
        self.score = score


# Release Groups Ranked by Point Values
release_groups = [
    Release_Group("Premium", 105),  # For LN releases
    Release_Group("danke-empire", 100),
    Release_Group("LuCaZ", 75),
    Release_Group("Shizu", 50),
    Release_Group("1r0n", 25),
    Release_Group("Digital HD", 5),
    Release_Group("{r2}", 1),
    Release_Group("{r3}", 2),
    Release_Group("{r4}", 3),
    Release_Group("{r5}", 4),
    Release_Group("{f2}", 1),
    Release_Group("{f3}", 2),
    Release_Group("{f4}", 3),
    Release_Group("{f5}", 4),
    Release_Group("(f2)", 1),
    Release_Group("(f3)", 2),
    Release_Group("(f4)", 3),
    Release_Group("(f5)", 4),
    Release_Group("AkaHummingBird", 0),
    Release_Group("Shellshock", 0),
    Release_Group("aKraa", 0),
    Release_Group("Ushi", 0),
    Release_Group("Edge", 0),
    Release_Group("LostNerevarine-Empire", 0),
    Release_Group("0v3r", 0),
    Release_Group("PNG4", -5),
]

# Parses the passed command line arguments
parser = argparse.ArgumentParser(
    description="Scans for covers in the cbz and epub files."
)
parser.add_argument(
    "-d",
    "--download_folder",
    help="The download folder for processing, renaming, and moving of downloaded files.",
    required=False,
)
parser.add_argument(
    "-p",
    "--paths",
    help="The paths to be scanned for cover extraction.",
    required=False,
)
parser.add_argument(
    "-i",
    "--ignored_folder_names",
    help="Ignore the specified folders by name.",
    required=False,
)
parser.add_argument(
    "-rmp",
    "--required_matching_percentage",
    help="The required matching percentage that must be met between the download folder and the existing folder when automatically moving files to existing llibrary folders.",
    default=90,
    required=False,
)
parser.add_argument(
    "-rms",
    "--required_similarity_score",
    help="The required similarity score that must be met when comparing two strings between the volume series name and the existing library folder name.",
    default=0.9790,
    required=False,
)
parser.add_argument(
    "-pvr",
    "--preferred_volume_renaming_format",
    help="The preferred volume naming format. # v = v01, Volume = Volume01, and so on. IF YOU WANT A SPACE BETWEEN THE TWO, ADD IT IN THE PREFERRED NAMING.",
    default="v",
    required=False,
)
parser.add_argument(
    "-a",
    "--add_issue_number_to_file_name",
    help="Whether or not to add the issue number to the renamed file names. Issue number is added directly after the volume number.",
    default=False,
    required=False,
)
parser.add_argument(
    "-w",
    "--discord_webhook_url",
    help="The webhook URL to send the results to Discord.",
    default="",
    required=False,
)


# Appends, sends, and prints our error message
def send_error_message(error):
    send_discord_message(error)
    write_to_file("errors.txt", error)


# Appends, sends, and prints our change message
def send_change_message(message):
    send_discord_message(message)
    items_changed.append(message)
    write_to_file("changes.txt", message)


# Sends a discord message
def send_discord_message(message):
    if discord_webhook_url != "":
        webhook = DiscordWebhook(
            url=discord_webhook_url, content=message, rate_limit_retry=True
        )
        webhook.execute()
    print(message)


# Checks if a file exists
def file_exists(root, file):
    return os.path.isfile(os.path.join(root, file))


# Removes hidden files
def remove_hidden_files(files, root):
    for file in files[:]:
        if file.startswith(".") and file_exists(root, file):
            files.remove(file)


# Removes any unaccepted file types
def remove_unaccepted_file_types(files, root):
    for file in files[:]:
        extension = re.sub("\.", "", get_file_extension(file))
        if extension not in file_extensions and file_exists(root, file):
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


# Cleans up the files array before usage
def clean_and_sort(root, files=None, dirs=None):
    if files is not None:
        files.sort()
        remove_hidden_files(files, root)
        remove_unaccepted_file_types(files, root)
    if dirs is not None:
        dirs.sort()
        remove_hidden_folders(root, dirs)
        remove_ignored_folders(dirs)


# Checks for the existance of a cover or poster file
def check_for_existing_cover(files):
    for file in files:
        for string in series_cover_file_names:
            if string in file:
                return True
    return False


# Prints our os.walk info
def print_info(root, dirs, files):
    print("\nCurrent Path: ", root + "\nDirectories: ", dirs)
    file_names = []
    for f in files:
        file_names.append(f.name)
    print("Files: ", file_names)


def print_info_two(root):
    print("\tCurrent Path: ", root)


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
            os.path.basename(root),
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


# Checks if the cbz or epub file has a matching cover
def check_for_image(file):
    image_found = False
    for image_type in image_extensions:
        image_type = "." + image_type
        if os.path.isfile(file.extensionless_path + image_type):
            image_found = True
            global image_count
            image_count += 1
    return image_found


# Removes all results that aren't an image.
def zip_images_only(zip):
    results = []
    list = zip.namelist()
    for z in list:
        for extension in image_extensions:
            if z.endswith("." + extension):
                results.append(z)
                results.sort()
    return results


# Gets and returns the basename
def get_base_name(item):
    return os.path.basename(item)


# Opens the zip and extracts out the cover
def extract_cover(
    zip_file, zip_internal_image_file_path, zip_internal_image_file, file
):
    for extension in image_extensions:
        if zip_internal_image_file.endswith("." + extension):
            try:
                with zip_file.open(
                    os.path.join(zip_internal_image_file_path, zip_internal_image_file)
                ) as zf, open(
                    os.path.join(
                        file.root,
                        os.path.basename(
                            file.extensionless_name
                            + os.path.splitext(zip_internal_image_file)[1]
                        ),
                    ),
                    "wb",
                ) as f:
                    send_change_message("Copying file and renaming.")
                    shutil.copyfileobj(zf, f)
                    return
            except IOError as io:
                send_error_message(io)
    return


# Removes hidden files with the base name.
def remove_hidden_files_with_basename(files):
    for file in files[:]:
        base = os.path.basename(file)
        if file.startswith(".") or base.startswith("."):
            files.remove(file)


class ImageInfo:
    def __init__(self, path, name):
        self.path = path
        self.name = name


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
        return ImageInfo(
            cover_path,
            get_base_name(cover_path),
        )


# Checks the internal zip for covers.
def check_internal_zip_for_cover(file):
    global poster_found
    global cbz_internal_covers_found
    cover_found = False
    poster_found = False
    image_cover_name = ""
    if file.name.endswith(".epub") and not file.name.startswith("."):
        try:
            image_cover_name = get_epub_cover(file.path).path
        except Exception as e:
            print(e)
    try:
        if zipfile.is_zipfile(file.path):
            zip_file = zipfile.ZipFile(file.path)
            send_change_message("Zip found" + "Entering zip: " + file.name)
            internal_zip_images = zip_images_only(zip_file)
            remove_hidden_files_with_basename(internal_zip_images)
            if image_cover_name != "":
                head_tail = os.path.split(image_cover_name)
                image_file_path = head_tail[0]
                image_file = head_tail[1]
                cover_found = True
                cbz_internal_covers_found += 1
                extract_cover(zip_file, image_file_path, image_file, file)
                return
            else:
                for image_file in internal_zip_images:
                    head_tail = os.path.split(image_file)
                    image_file_path = head_tail[0]
                    image_file = head_tail[1]
                    if cover_found != True:
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
                        ):
                            send_change_message(
                                "Found cover: "
                                + get_base_name(image_file)
                                + " in "
                                + file.name
                            )
                            cover_found = True
                            cbz_internal_covers_found += 1
                            extract_cover(zip_file, image_file_path, image_file, file)
                            return
            if cover_found != True and len(internal_zip_images) != False:
                head_tail = os.path.split(internal_zip_images[0])
                image_file_path = head_tail[0]
                image_file = head_tail[1]
                send_change_message(
                    "Defaulting to first image file found: "
                    + internal_zip_images[0]
                    + " in "
                    + file.path
                )
                cover_found = True
                extract_cover(zip_file, image_file_path, image_file, file)
                return
        else:
            files_with_no_cover.append(file.path)
            send_error_message(
                "Invalid Zip File at: \n"
                + file.path
                + "\nCheck that you have permissions to open the file."
            )

    except zipfile.BadZipFile:
        print("Bad Zipfile: " + file.path)
        errors.append("Bad Zipfile: " + file.path)
    return cover_found


def individual_volume_cover_file_stuff(file):
    for file_extension in file_extensions:
        if (file.name).endswith(file_extension) and os.path.isfile(file.path):
            update_stats(file)
            if not check_for_image(file):
                try:
                    check_internal_zip_for_cover(file)
                except zlib.error:
                    print(
                        "Error -3 while decompressing data: invalid stored block lengths"
                    )


# Checks for a duplicate cover/poster, if cover and poster both exist, it deletes poster.
def check_for_duplicate_cover(file):
    duplicate_found1 = 0
    duplicate_found2 = 0
    dup = ""
    for image_type in image_extensions:
        if os.path.isfile(os.path.join(file.root, "poster." + image_type)):
            duplicate_found1 = 1
            dup = os.path.join(file.root, "poster." + image_type)
        if os.path.isfile(os.path.join(file.root, "cover." + image_type)):
            duplicate_found2 = 1
        if duplicate_found1 + duplicate_found2 == 2 and os.path.isfile(dup):
            try:
                send_change_message("Removing duplicate poster: " + dup)
                os.remove(dup)
                if not os.path.isfile(dup):
                    send_change_message("Duplicate successfully removed.")
                else:
                    send_error_message(
                        "Failed to remove duplicate poster in " + file.root
                    )
            except FileNotFoundError:
                send_error_message("File not found: " + file)


# Checks if the passed string is a volume one.
def is_volume_one(volume_name):
    if re.search(
        r"(\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第)([-_. ]|)(One|1|01|001|0001)\b)",
        volume_name,
        re.IGNORECASE,
    ):
        return True
    else:
        return False


# Checks for the existance of a volume one.
def check_for_volume_one_cover(file, zip_file, files):
    extensionless_path = file.extensionless_path
    zip_basename = os.path.basename(zip_file.filename)
    if is_volume_one(zip_basename):
        send_change_message(
            "Volume 1 Cover Found: " + zip_basename + " in " + file.root
        )
        for extension in image_extensions:
            if os.path.isfile(extensionless_path + "." + extension):
                shutil.copyfile(
                    extensionless_path + "." + extension,
                    os.path.join(file.root, "cover." + extension),
                )
                return True
    else:
        volume_files_exists_within_folder = False
        for item in files:
            if re.search(
                r"((\s(\s-\s|)(Part|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)(\.|)([-_. ]|)([0-9]+)\b)|\s(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)(\.|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)([0-9]+)\s|\s(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)(\.|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)([0-9]+)\s)",
                item.name,
                re.IGNORECASE,
            ):
                volume_files_exists_within_folder = True
        if (
            not re.search(
                r"((\s(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)(\.|)([-_. ]|)([0-9]+)\b)|\s(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)(\.|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)([0-9]+)\s|\s(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)(\.|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)([0-9]+)\s)",
                zip_basename,
                re.IGNORECASE,
            )
            and volume_files_exists_within_folder == False
        ):
            send_change_message(
                "No volume keyword detected, assuming file is a one-shot volume: "
                + zip_basename
                + " in "
                + file.root
            )
            for extension in image_extensions:
                if os.path.isfile(extensionless_path + "." + extension):
                    shutil.copyfile(
                        extensionless_path + "." + extension,
                        os.path.join(file.root, "cover." + extension),
                    )
                    return True
    return False


def cover_file_stuff(file, files):
    for file_extension in file_extensions:
        if str(file.path).endswith(file_extension) and zipfile.is_zipfile(file.path):
            try:
                zip_file = zipfile.ZipFile(file.path)
                return check_for_volume_one_cover(file, zip_file, files)
            except zipfile.BadZipFile:
                send_error_message("Bad zip file: " + file.path)
    return False


# Checks similarity between two strings.
# Credit to: https://stackoverflow.com/users/1561176/inbar-rose
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
def get_series_name_from_file_name(name):
    name = (
        re.sub(
            r"(\b|\s)((\s|)-(\s|)|)(Part|)(\[|\(|\{)?(LN|Light Novel|Novel|Book|Volume|Vol|V)(\.|)([-_. ]|)([0-9]+)(\b|\s).*",
            "",
            name,
            flags=re.IGNORECASE,
        )
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
                                if similarity_result < 0.4:
                                    folder_name = get_series_name_from_file_name(
                                        os.path.splitext(file.name)[0]
                                    )
                                    folder_location = os.path.join(
                                        file.root, folder_name
                                    )
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
        if (file.name).endswith(".epub"):
            epub_folder_count += 1
    epub_percent = (
        (epub_folder_count / (len(files)) * 100) if epub_folder_count != 0 else 0
    )
    return epub_percent


# Returns the percentage of files that are cbz, to the total amount of files
def get_cbz_percent_for_folder(files):
    cbz_folder_count = 0
    for file in files:
        if (file.name).endswith(".cbz"):
            cbz_folder_count += 1
    cbz_percent = (
        (cbz_folder_count / (len(files)) * 100) if cbz_folder_count != 0 else 0
    )
    return cbz_percent


# NEEDS REVISION
# Finds the volume number and strips out everything except that number
def remove_everything_but_volume_num(files, root):
    results = []
    is_omnibus = False
    for file in files[:]:
        if (
            not re.search(
                r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第)([-_. ]|)([-_. ]|)([0-9]+)((\.)([0-9]+)|)\b",
                file,
                re.IGNORECASE,
            )
            and os.path.isfile(os.path.join(root, file))
        ):
            files.remove(file)
        # elif(re.search(r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第)(\d+)(\.\d+)?([-_])(\d+)(\.\d+)?\b", file, re.IGNORECASE)):
        #     is_omnibus = True
        #     x = re.search(r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第)(\d+)(\.\d+)?([-_])(\d+)(\.\d+)?\b", file, re.IGNORECASE).group()
        #     y = x.split("-")
        #     for item in y:
        #         item = re.sub(r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第)", "", item, flags=re.IGNORECASE)
        #         try:
        #             item = float(item)
        #             results.append(item)
        #         except Exception as e:
        #             print(e)
        #     try:
        #         lowest_volume_number = int(min(results))
        #         highest_volume_number = int(max(results))
        #         volume_num_range = list(range(lowest_volume_number, highest_volume_number+1))
        #         results = volume_num_range
        #     except Exception as e:
        #         print(e)
        else:
            try:
                file = re.search(
                    r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第)([-_. ]|)([-_. ]|)([0-9]+)((\.)([0-9]+)|)\b",
                    file,
                    re.IGNORECASE,
                )
                if hasattr(file, "group"):
                    file = file.group()
                else:
                    file = ""
                file = re.sub(
                    r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第)(\.|)([-_. ])?",
                    "",
                    file,
                    flags=re.IGNORECASE,
                ).strip()
                if re.search(
                    r"\b[0-9]+(LN|Light Novel|Novel|Book|Volume|Vol|V|第)[0-9]+\b",
                    file,
                    re.IGNORECASE,
                ):
                    file = (
                        re.sub(
                            r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第)",
                            ".",
                            file,
                            flags=re.IGNORECASE,
                        )
                    ).strip()
                try:
                    results.append(float(file))
                except ValueError:
                    message = "Not a float: " + files[0]
                    print(message)
                    write_to_file("errors.txt", message)
            except AttributeError:
                print(str(AttributeError.with_traceback))
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
    for release_group in release_groups:
        if re.search(release_group.name, name, re.IGNORECASE):
            result = release_group.name
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
            get_series_name_from_file_name(file.name),
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
            get_extras(file.name),
        )
        results.append(volume_obj)
    return results


# Retrieves the release_group score from the list, using a high similarity
def get_release_group_score(name):
    score = 0.0
    for group in release_groups:
        if re.search(group.name, name, re.IGNORECASE):
            score += group.score
    return score


# Checks if the downloaded release is an upgrade for the current release.
def is_upgradeable(downloaded_release, current_release):
    downloaded_release_score = get_release_group_score(downloaded_release.name)
    current_release_score = get_release_group_score(current_release.name)
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
        if (str(file)).startswith(".") and file_exists(root, file):
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
            send_change_message("\t\tFile removed: " + full_file_path)
            remove_images(full_file_path)
            return True
        else:
            send_error_message("\n\t\tFailed to remove file: " + full_file_path)
            return False
    except OSError as e:
        print(e)


# Move a file
def move_file(file, new_location):
    try:
        if os.path.isfile(file.path):
            shutil.move(file.path, new_location)
            if os.path.isfile(os.path.join(new_location, file.name)):
                send_change_message(
                    "File: " + file.name + " was successfully moved to: " + new_location
                )
                move_images(file, new_location)
            else:
                send_error_message(
                    "Failed to move: "
                    + os.path.join(file.root, file.name)
                    + " to: "
                    + new_location
                )
    except OSError as e:
        print(e)


# Replaces an old file.
def replace_file(old_file, new_file):
    if os.path.isfile(old_file.path) and os.path.isfile(new_file.path):
        remove_file(old_file.path)
        if not os.path.isfile(old_file.path):
            move_file(new_file, old_file.root)
            if os.path.isfile(os.path.join(old_file.root, new_file.name)):
                send_change_message(
                    "\tFile: " + old_file.name + " moved to: " + new_file.root
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
            send_error_message("\n\tThe volume number is empty on: " + download.name)
            send_error_message("\tAvoiding file, might be a chapter.")
            downloaded_releases.remove(download)
        if len(downloaded_releases) != 0:
            for original in original_releases:
                if isinstance(download.volume_number, float) and isinstance(
                    original.volume_number, float
                ):
                    if (download.volume_number == original.volume_number) and (
                        download.volume_number != "" and original.volume_number != ""
                    ):
                        if not is_upgradeable(download, original):
                            send_change_message(
                                "\n\tVolume: "
                                + download.name
                                + " is not an upgrade to: "
                                + original.name
                            )
                            send_change_message("\tDeleting " + download.name)
                            if download in downloaded_releases:
                                downloaded_releases.remove(download)
                            remove_file(download.path)
                        else:
                            send_change_message(
                                "\n\tVolume: "
                                + download.name
                                + " is an upgrade to: "
                                + original.name
                            )
                            send_change_message("\tUpgrading " + original.name)
                            replace_file(original, download)


# Checks if the folder is empty, then deletes if it is
def check_and_delete_empty_folder(folder):
    print("\tChecking for empty folder: " + folder)
    delete_hidden_files(os.listdir(folder), folder)
    folder_contents = os.listdir(folder)
    remove_hidden_files(folder_contents, folder)
    if len(folder_contents) == 0:
        try:
            print("Removing empty folder: " + folder)
            os.rmdir(folder)
        except OSError as e:
            send_error_message(e)


# Writes a log file
def write_to_file(file, message):
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(ROOT_DIR, file)
    append_write = ""
    if os.path.exists(file_path):
        append_write = "a"  # append if already exists
    else:
        append_write = "w"  # make a new file if not
    try:
        if append_write != "":
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            file = open(file_path, append_write)
            file.write("\n" + dt_string + " " + message)
            file.close()
    except Exception as e:
        print(e)


# Checks for any missing volumes between the lowest volume of a series and the highest volume.
def check_for_missing_volumes():
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
                                    "\nVolume "
                                    + str(number)
                                    + " in "
                                    + current_folder_path
                                    + " is missing."
                                )
                                print(message)
                                write_to_file("missing_volumes.txt", message)


# Renames the file.
def rename_file(
    src, dest, root, extensionless_filename_src, extenionless_filename_dest
):
    if os.path.isfile(src):
        print("\tRenaming " + src)
        os.rename(src, dest)
        if os.path.isfile(dest):
            send_change_message(
                "\t"
                + extensionless_filename_src
                + " renamed to "
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
    base_dir = os.path.basename(dir)
    for file in files:
        if re.search(
            r"\b(LN|Light Novel|Novel|Book|Volume|Vol|V|第)([-_. ]|)([0-9]+)(\.[0-9]+|)(\s|\.epub|\.cbz)",
            file.name,
            re.IGNORECASE,
        ):
            rename = ""
            rename += base_dir
            rename += " " + preferred_volume_renaming_format
            if file.volume_number.is_integer():
                if file.volume_number < 10:
                    volume_number = str(int(file.volume_number)).zfill(2)
                    rename += volume_number
                    if add_issue_number_to_file_name == True:
                        rename += " #" + volume_number
                else:
                    volume_number = str(int(file.volume_number))
                    rename += volume_number
                    if add_issue_number_to_file_name == True:
                        rename += " #" + volume_number
            elif isinstance(file.volume_number, float):
                if file.volume_number < 10:
                    volume_number = str(file.volume_number).zfill(4)
                    rename += volume_number
                    if add_issue_number_to_file_name == True:
                        rename += " #" + volume_number
                else:
                    volume_number = str(file.volume_number)
                    rename += volume_number
                    if add_issue_number_to_file_name == True:
                        rename += " #" + volume_number
            if isinstance(file.volume_year, int):
                rename += " (" + str(file.volume_year) + ")"
            if len(file.extras) != 0:
                for extra in file.extras:
                    rename += " " + extra
            rename += file.extension
            if file.name != rename:
                try:
                    print("\tOriginal: " + file.name)
                    print("\tRename: " + rename)
                    rename_file(
                        file.path,
                        os.path.join(file.root, rename),
                        file.root,
                        file.extensionless_name,
                        get_extensionless_name(rename),
                    )
                    send_change_message("\tRenamed: " + file.name + " to \n" + rename)
                    file.series_name = get_series_name_from_file_name(rename)
                    file.volume_year = get_volume_year(rename)
                    file.volume_number = remove_everything_but_volume_num(
                        [rename], file.root
                    )
                    file.name = rename
                    file.extensionless_name = get_extensionless_name(rename)
                    file.basename = os.path.basename(rename)
                    file.path = os.path.join(file.root, rename)
                    file.extensionless_path = os.path.splitext(file.path)[0]
                    file.extras = get_extras(rename)
                except OSError as ose:
                    send_error_message(ose)


# Returns a string without punctuation.
def remove_punctuation(s):
    return re.sub(r"[^\w\s]", "", s)


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
                    done = False
                    dir_clean = file.series_name
                    for path in paths:
                        if os.path.exists(path) and done == False:
                            try:
                                os.chdir(path)
                                path_dirs = os.listdir(path)
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
                                    for dir in folder_accessor.dirs:
                                        downloaded_file_series_name = (
                                            (str(dir_clean)).lower()
                                        ).strip()
                                        downloaded_file_series_name = (
                                            remove_punctuation(
                                                downloaded_file_series_name
                                            )
                                        )
                                        existing_series_folder_from_library = (
                                            remove_punctuation(
                                                ((str(dir)).lower()).strip()
                                            )
                                        )
                                        similarity_score = similar(
                                            existing_series_folder_from_library,
                                            downloaded_file_series_name,
                                        )
                                        if (
                                            similarity_score
                                            >= required_similarity_score
                                        ):
                                            write_to_file(
                                                "changes.txt",
                                                (
                                                    '\tSimilarity between: "'
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
                                                '\tSimilarity between: "'
                                                + existing_series_folder_from_library
                                                + '" and "'
                                                + downloaded_file_series_name
                                                + '" Score: '
                                                + str(similarity_score)
                                                + " out of 1.0"
                                            )
                                            existing_dir = os.path.join(
                                                folder_accessor.root, dir
                                            )
                                            clean_existing = os.listdir(existing_dir)
                                            clean_and_sort(existing_dir, clean_existing)
                                            download_dir_volumes = []
                                            download_dir_volumes.append(file)
                                            reorganize_and_rename(
                                                download_dir_volumes, existing_dir
                                            )
                                            existing_dir_volumes = (
                                                upgrade_to_volume_class(
                                                    upgrade_to_file_class(
                                                        [
                                                            f
                                                            for f in clean_existing
                                                            if os.path.isfile(
                                                                os.path.join(
                                                                    existing_dir, f
                                                                )
                                                            )
                                                        ],
                                                        existing_dir,
                                                    )
                                                )
                                            )
                                            cbz_percent_download_folder = (
                                                get_cbz_percent_for_folder(
                                                    download_dir_volumes
                                                )
                                            )
                                            cbz_percent_existing_folder = (
                                                get_cbz_percent_for_folder(
                                                    existing_dir_volumes
                                                )
                                            )
                                            epub_percent_download_folder = (
                                                get_epub_percent_for_folder(
                                                    download_dir_volumes
                                                )
                                            )
                                            epub_percent_existing_folder = (
                                                get_epub_percent_for_folder(
                                                    existing_dir_volumes
                                                )
                                            )
                                            lower_range_score = 1 * 0.089
                                            higher_range_score = 1 * 0.0970
                                            if (
                                                (
                                                    cbz_percent_download_folder
                                                    and cbz_percent_existing_folder
                                                )
                                                > required_matching_percentage
                                            ) or (
                                                (
                                                    epub_percent_download_folder
                                                    and epub_percent_existing_folder
                                                )
                                                > required_matching_percentage
                                            ):
                                                send_change_message(
                                                    "\tFound existing series: "
                                                    + existing_dir
                                                )
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
                                                            "\tVolume: "
                                                            + volume.name
                                                            + " does note exist in: "
                                                            + existing_dir
                                                        )
                                                        send_change_message(
                                                            "\tMoving: "
                                                            + volume.name
                                                            + " to "
                                                            + existing_dir
                                                        )
                                                        move_file(volume, existing_dir)
                                                        check_and_delete_empty_folder(
                                                            volume.root
                                                        )
                                                        done = True
                                                        break
                                                else:
                                                    check_and_delete_empty_folder(
                                                        file.root
                                                    )
                                                    done = True
                                                    break
                                            elif (
                                                similarity_score >= lower_range_score
                                            ) and (
                                                similarity_score <= higher_range_score
                                            ):
                                                print(
                                                    "\tScore between "
                                                    + lower_range_score
                                                    + " and "
                                                    + higher_range_score
                                                    + "\tScore: "
                                                    + str(similarity_score)
                                                )
                                                print(
                                                    '\tScore for: "'
                                                    + existing_series_folder_from_library
                                                    + '" and "'
                                                    + downloaded_file_series_name
                                                    + '"'
                                                )
                                                print("")
                            except FileNotFoundError:
                                send_error_message(
                                    "\nERROR: " + path + " is not a valid path.\n"
                                )


# Removes any unnecessary junk through regex in the folder name and returns the result
def get_series_name(dir):
    dir = (
        re.sub(
            r"(\b|\s)((\s|)-(\s|)|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第)([-_. ]|)([-_. ]|)([0-9]+)(\b|\s).*",
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
                                r"(\b|\s)((\s|)-(\s|)|)(Part|)(LN|Light Novel|Novel|Book|Volume|Vol|V|第|)(\.|)([-_. ]|)([0-9]+)(\b|\s)",
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
                                    print(e)
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


def get_extras(file_name):
    series_name = get_series_name_from_file_name(file_name)
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
    keywords_two = ["Extra", "Arc ", "Episode"]
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
def rename_files():
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
                    # if file.extension != "" and file.extension.startswith("."):
                    # file.name = re.sub(file.extension, "", file.name)
                    if re.search(
                        r"\s(\[|\(|\{)?(LN|Light Novel|Novel|Book|Volume|Vol|V|第)(\.|)([-_. ]|)([0-9]+)(([-_. ]|)([0-9]+)|)(\]|\)|\})?(\s|\.)",
                        file.name,
                        re.IGNORECASE,
                    ):
                        result = (
                            re.search(
                                r"\s(\[|\(|\{)?(LN|Light Novel|Novel|Book|Volume|Vol|V|第)(\.|)([-_. ]|)([0-9]+)(([-_. ]|)([0-9]+)|)(\]|\)|\})?(\s|\.)",
                                file.name,
                                re.IGNORECASE,
                            )
                            .group()
                            .strip()
                        )
                        result = re.sub(r"[\[\(\{\]\)\}]", "", result)
                        results = re.split(
                            r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第)(\.|)",
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
                                    r"([0-9]+)((([-_.])([0-9]+))|)", r, re.IGNORECASE
                                )
                                if found:
                                    r = found.group()
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
                                            r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第)",
                                            r,
                                            re.IGNORECASE,
                                        ):
                                            modified.append(
                                                re.sub(
                                                    r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第)",
                                                    preferred_volume_renaming_format,
                                                    r,
                                                    flags=re.IGNORECASE,
                                                )
                                            )
                        if len(modified) == 2 and len(results) == 2:
                            if type(modified[1]) == int:
                                if modified[1] < 10:
                                    modified[1] = str(modified[1]).zfill(2)
                            elif type(modified[1]) == float:
                                if modified[1] < 10:
                                    modified[1] = str(modified[1]).zfill(4)
                            combined = modified[0] + str(modified[1])
                            issue_number = "#" + str(modified[1])
                            if (
                                not contains_issue_number(file.name, str(modified[1]))
                                and add_issue_number_to_file_name == True
                            ):
                                combined += " " + issue_number
                            replacement = re.sub(
                                r"((?<![A-Za-z]+)[-_. ]\s|)(\[|\(|\{)?(LN|Light Novel|Novel|Book|Volume|Vol|v|第)(\.|)([-_. ]|)([0-9]+)(([-_. ]|)([0-9]+)|)(\]|\)|\})?",
                                combined,
                                file.name,
                                flags=re.IGNORECASE,
                                count=1,
                            )
                            if file.name != replacement:
                                try:
                                    if not (
                                        os.path.isfile(os.path.join(root, replacement))
                                    ):
                                        print(file.name)
                                        print(replacement)
                                        manual_rename = False  # Set to True for user input renaming, otherwise False
                                        user_input = ""
                                        if manual_rename == False:
                                            user_input = "y"
                                        else:
                                            print("y or n")
                                            user_input = input()
                                        if user_input == "y":
                                            os.rename(
                                                os.path.join(root, file.name),
                                                os.path.join(root, replacement),
                                            )
                                            if os.path.isfile(
                                                os.path.join(root, replacement)
                                            ):
                                                send_change_message(
                                                    "Successfully renamed file: "
                                                    + file.name
                                                    + " to "
                                                    + replacement
                                                )
                                                for image_extension in image_extensions:
                                                    image_file = (
                                                        file.extensionless_name
                                                        + "."
                                                        + image_extension
                                                    )
                                                    if os.path.isfile(
                                                        os.path.join(root, image_file)
                                                    ):
                                                        extensionless_replacement = (
                                                            get_extensionless_name(
                                                                replacement
                                                            )
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
                                                    "\nRename failed on: " + file.name
                                                )
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
        else:
            if path == "":
                print("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + path + " is an invalid path.\n")


# Deletes chapter files from the download folder.
def delete_chapters_from_downloads():
    try:
        for path in download_folders:
            if os.path.exists(path):
                os.chdir(path)
                for root, dirs, files in os.walk(path):
                    clean_and_sort(root, files, dirs)
                    for file in files:
                        if not (
                            re.search(
                                r"(LN|Light Novel|Novel|Book|Volume|Vol|V|第)([-_. ]|)([-_. ]|)([0-9]+)(([-_. ])([0-9]+)|)",
                                file,
                                re.IGNORECASE,
                            )
                        ):
                            if re.search(
                                r"\s(\d)+(([.]\d)?)(\s|(.cbz)?(.epub)?)",
                                file,
                                re.IGNORECASE,
                            ):
                                if not file.__contains__("Extra"):
                                    if file.endswith(".cbz"):
                                        message = (
                                            "File: "
                                            + file
                                            + " does not contain volume keyword"
                                        )
                                        print(message)
                                        write_to_file("changes.txt", message)
                                        message = "Location: " + root
                                        write_to_file("changes.txt", message)
                                        print(message)
                                        message = "Deleting chapter releases."
                                        print(message)
                                        write_to_file("changes.txt", message)
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
        print(e)


# execute terminal command
def execute_command(command):
    try:
        subprocess.call(command, shell=True)
    except Exception as e:
        print(e)


def main():
    #delete_chapters_from_downloads()
    #rename_files()
    #create_folders_for_items_in_download_folder()
    #rename_dirs_in_download_folder()
    #check_for_existing_series_and_move()
    #check_for_missing_volumes()
    for path in paths:
        if os.path.exists(path):
            try:
                os.chdir(path)
                for root, dirs, files in os.walk(path):
                    remove_hidden_files(files, root)
                    has_cover = check_for_existing_cover(files)
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
                    print_info(
                        folder_accessor.root,
                        folder_accessor.dirs,
                        folder_accessor.files,
                    )
                    for file in folder_accessor.files:
                        individual_volume_cover_file_stuff(file)
                        if has_cover:
                            check_for_duplicate_cover(file)
                        else:
                            try:
                                has_cover = has_cover + cover_file_stuff(
                                    file, folder_accessor.files
                                )
                            except Exception:
                                send_error_message(
                                    "Exception thrown when finding existing cover."
                                )
                                send_error_message("Excpetion occured on: " + str(file))
            except FileNotFoundError:
                print("\nERROR: " + path + " is not a valid path.\n")
        else:
            if path == "":
                print("\nERROR: Path cannot be empty.")
            else:
                print("\nERROR: " + path + " is an invalid path.\n")


main()
print("\nFor all " + str(len(paths)) + " paths.")
print("Total Files Found: " + str(file_count))
print("\t" + str(cbz_count) + " were cbz files")
print("\t" + str(cbr_count) + " were cbr files")
print("\t" + str(epub_count) + " were epub files")
print("\tof those we found " + str(image_count) + " had a cover image file.")
if len(files_with_no_cover) != 0:
    print("\nRemaining files without covers:")
    for lonely_file in files_with_no_cover:
        print("\t" + lonely_file)
if len(errors) != 0:
    print("\nErrors:")
    for error in errors:
        print("\t" + error)
