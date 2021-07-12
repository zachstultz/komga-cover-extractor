import os
import shutil
import time
import zipfile
import zlib
from html.parser import HTMLParser
from platform import system
import re

# ************************************
# Created by: Zach Stultz            *
# Git: https://github.com/zachstultz *
# ***************************************************
# A manga/light novel processor script for use with *
# the manga/light novel reader gotson/komga.        *
# ***************************************************

# [ADD IN THE PATHS YOU WANT SCANNED]
paths = [""]
# [ADD IN THE PATHS YOU WANT SCANNED]

# List of image types used throughout the program
image_extensions = ["jpg", "jpeg", "png", "tbn"]

# The remaining files without covers
files_with_no_image = []

# Any errors occured along the way
errors = []

# Stat-related variables
file_count = 0
cbz_count = 0
epub_count = 0
cbr_count = 0
image_count = 0
cbz_internal_covers_found = 0
poster_found = 0


# Checks if the cbz or epub file has a matching cover
def check_for_image(name, root):
    image_found = 0
    for image_type in image_extensions:
        image_type = "." + image_type
        if os.path.isfile(os.path.join(root, name + image_type)):
            image_found = 1
            global image_count
            image_count += 1
    return image_found


# Opens the zip and extracts out the cover
def extract_cover(zip_file, file_path, image_file, root, file, full_path, name):
    for extension in image_extensions:
        if image_file.endswith("."+extension):
            try:
                if system() == "Windows":
                    with zip_file.open(os.path.join(file_path, image_file).replace("\\", "/")) as zf, open(
                            os.path.join(root,os.path.basename(name + os.path.splitext(image_file)[1])),
                            'wb') as f:
                            print("Copying file and renaming.")
                            shutil.copyfileobj(zf, f)
                            return
                if system() == "Linux":
                    with zip_file.open(os.path.join(file_path, image_file).replace("\\", "/")) as zf, open(
                            os.path.join(root,os.path.basename(name + os.path.splitext(image_file)[1])),
                            'wb') as f:
                            print("Copying file and renaming.")
                            shutil.copyfileobj(zf, f)
                            return
            except zipfile.BadZipFile:
                print("Bad Zipfile: " + str(full_path))
                errors.append("Bad Zipfile: " + str(full_path))
    return


# Checks the zip for a cover image matching the cbz file,
# then calls the extract_cover method if found
def check_internal_zip_for_cover(file, full_path, root):
    global poster_found
    global cbz_internal_covers_found
    cover_found = 0
    poster_found = 0
    try:
        # Add logic for a .rar file, aka .cbr file
        if zipfile.is_zipfile(full_path):
            zip_file = zipfile.ZipFile(full_path)
            print("\n" + "Zip found\n" + "Entering zip: " + file)
            narrowed = []
            i = 0
            for z in zip_file.namelist():
                for extension in image_extensions:
                    if z.endswith("." + extension):
                        narrowed.append(z)
            narrowed.sort()
            for item in narrowed:
                head_tail = os.path.split(item)
                file_path = head_tail[0]
                image_file = head_tail[1]
                if(cover_found != 1):
                    if re.search(r"(\b(Cover([0-9]+|)|CoverDesign)\b)", item, re.IGNORECASE) or re.search(r"(\b(p000|page_000)\b)", item, re.IGNORECASE) or re.search(r"(\bindex[-_. ]1[-_. ]1\b)", item, re.IGNORECASE):
                        print("found cover: " + os.path.basename(os.path.basename(item)) + " in " + file)
                        cover_found = 1
                        cbz_internal_covers_found += 1
                        extract_cover(zip_file, file_path, image_file, root, file, full_path, os.path.splitext(file)[0])
                        return
            if (cover_found != 1 and len(narrowed) != 0):
                head_tail = os.path.split(narrowed[0])
                file_path = head_tail[0]
                image_file = head_tail[1]
                cover_found = 1
                print("Defaulting to first image file found: " + narrowed[0] + " in " + full_path)
                extract_cover(zip_file, file_path, image_file, root, file, full_path, os.path.splitext(file)[0])
                print("")
                return
        else:
            files_with_no_image.append(full_path)
            print("Invalid Zip File at: \n" + full_path)

    except zipfile.BadZipFile:
        print("Bad Zipfile: " + full_path)
        errors.append("Bad Zipfile: " + full_path)
    return cover_found


def individual_volume_cover_file_stuff(file, root, full_path):
    global file_count
    global cbz_count
    global epub_count
    global cbr_count

    if file.endswith(".cbz") & os.path.isfile(os.path.join(root, file)):
        file_count += 1
        cbz_count += 1
        if not check_for_image(os.path.splitext(file)[0], root):
            try:
                check_internal_zip_for_cover(file, full_path, root)
            except zlib.error:
                print("Error -3 while decompressing data: invalid stored block lengths")
    if file.endswith(".epub") & os.path.isfile(os.path.join(root, file)):
        file_count += 1
        epub_count += 1
        if not check_for_image(os.path.splitext(file)[0], root):
            try:
                check_internal_zip_for_cover(file, full_path, root)
            except zlib.error:
                print("Error -3 while decompressing data: invalid stored block lengths")
    if file.endswith(".cbr") & os.path.isfile(os.path.join(root, file)):
        file_count += 1
        cbr_count += 1
        if not check_for_image(os.path.splitext(file)[0], root):
            try:
                check_internal_zip_for_cover(file, full_path, root)
            except zlib.error:
                print("Error -3 while decompressing data: invalid stored block lengths")


def cover_file_stuff(root, full_path):
    if zipfile.is_zipfile(full_path):
        try:
            zip_file = zipfile.ZipFile(full_path)
            return check_for_volume_one_cover(root, zip_file)
        except zipfile.BadZipFile:
            print("Bad zip file: " + full_path)
            errors.append("Bad zip file: " + full_path)
    else:
        return 0

def check_for_volume_one_cover(root, zip_file):
    extensionless_path = os.path.join(root, os.path.splitext(os.path.basename(zip_file.filename))[0])
    if re.search(r"(\b(LN|Light Novel|Novel|Book|Volume|Vol|V)([-_. ]|)(One|1|01)\b)", os.path.basename(zip_file.filename), re.IGNORECASE):
        print("Volume 1 Cover Found: " + os.path.basename(zip_file.filename) + " in " + root)
        for extension in image_extensions:
            if os.path.isfile(extensionless_path + '.' + extension):
                shutil.copyfile(extensionless_path + '.' + extension, os.path.join(root, 'cover.' + extension))
                return 1
    return 0

def check_for_existing_cover(files):
    if(str(files).__contains__("cover") |
    str(files).__contains__("poster")):
        return 1
    else:
        return 0

def check_for_duplicate_cover(root):
    duplicate_found1 = 0
    duplicate_found2 = 0
    dup = ""
    for image_type in image_extensions:
        if os.path.isfile(os.path.join(root, "poster." + image_type)):
            duplicate_found1 = 1
            dup = os.path.join(root, "poster." + image_type)
        if os.path.isfile(os.path.join(root, "cover." + image_type)):
            duplicate_found2 = 1
        if duplicate_found1 + duplicate_found2 == 2 and os.path.isfile(dup):
            try:
                print("Removing duplicate poster: " + dup)
                os.remove(dup)
                if not os.path.isfile(dup):
                    print("Duplicate successfully removed.")
                else:
                    print("Failed to remove duplicate poster in " + root)
            except FileNotFoundError:
                print("File not found.")

def print_file_info(root, dirs, files):
    print("\nCurrent Path: ", root + "\nDirectories: ", dirs)
    print("Files: ", files)

def main():
    global file_count
    global cbz_count
    global epub_count
    for path in paths:
        if os.path.exists(path):
            try:
                os.chdir(path)
            except FileNotFoundError:
                print("\nERROR: " + path + " is not a valid path.")
        else:
            print("\nINVALID: " + path + " is an invalid path.")
        # Walk into each directory
        for root, dirs, files in os.walk(path):
            print_file_info(root, dirs, files)
            foundExistingCover = check_for_existing_cover(files)
            for file in files:
                individual_volume_cover_file_stuff(file, root, os.path.join(root, file))
                if(foundExistingCover == 1):
                    check_for_duplicate_cover(root)
                if(foundExistingCover == 0):
                    try:
                        foundExistingCover = foundExistingCover + cover_file_stuff(root, os.path.join(root, file))
                    except Exception:
                        print("Exception thrown when finding existing cover.")
                        print("Excpetion occured on: " + str(file))


main()
print("\nFor all " + str(len(paths)) + " paths.")
print("Total Files Found: " + str(file_count))
print("\t" + str(cbz_count) + " were cbz files")
print("\t" + str(cbr_count) + " were cbr files")
print("\t" + str(epub_count) + " were epub files")
print("\tof those we found " + str(image_count) + " had a cover image file.")
if(len(files_with_no_image) != 0):
    print("\nRemaining files without covers:")
    for lonely_file in files_with_no_image:
        print("\t" + lonely_file)
if(len(errors) != 0):
    print("\nErrors:")
    for error in errors:
        print("\t" + error)
