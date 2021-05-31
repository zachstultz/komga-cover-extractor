import os
import shutil
import time
import zipfile
import zlib
from html.parser import HTMLParser
from platform import system

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

# List of cover strings used for detection
cover_detection_strings = ["Cover", "cover", "- p000", " p000 ", "000a", "_000.", "index-1_1", "p000 [Digital]"]

volume_detection_strings = ["V01", "v01", "Volume 1", "volume 1", "Volume 01", "volume 01", "Volume one", "volume one",
                            "Volume One", "volume One", "LN 01",  "Vol_01", "vol_01", "Vol_1", "vol_1"]
files_with_no_image = []

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
def extract_cover(zip_file, file_path, image_file, root, file, full_path, name, item):
    if image_file.endswith(".png") | image_file.endswith(".jpg") | image_file.endswith(".jpeg") | \
            image_file.endswith(".tbn"):
        try:
            if system() == "Windows":
                with zip_file.open(os.path.join(file_path, image_file).replace("\\", "/")) as zf, open(
                        os.path.join(root,os.path.basename(name + os.path.splitext(image_file)[1])),
                        'wb') as f:
                        print("Copying file and renaming.")
                        shutil.copyfileobj(zf, f)
            if system() == "Linux":
                with zip_file.open(os.path.join(file_path, image_file).replace("\\", "/")) as zf, open(
                        os.path.join(root,os.path.basename(name + os.path.splitext(image_file)[1])),
                        'wb') as f:
                        print("Copying file and renaming.")
                        shutil.copyfileobj(zf, f)
        except zipfile.BadZipFile:
            print("Bad Zipfile")
    else:
        print(image_file + " is not a proper image file!", "issue with " + full_path)
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
                if z.endswith(".jpg") | z.endswith(".jpeg") | z.endswith(".png") | z.endswith(".tbn"):
                    narrowed.append(z)
            narrowed.sort()
            for item in narrowed:
                head_tail = os.path.split(item)
                file_path = head_tail[0]
                image_file = head_tail[1]
                for string in cover_detection_strings:
                    if item.__contains__(string) and cover_found != 1:
                        print("found cover: " + os.path.basename(os.path.basename(item)) + " in " + file)
                        cover_found = 1
                        cbz_internal_covers_found += 1
                        extract_cover(zip_file, file_path, image_file, root, file, full_path, os.path.splitext(file)[0],
                                      item)
                        return
            for item in narrowed:
                head_tail = os.path.split(item)
                file_path = head_tail[0]
                image_file = head_tail[1]
                for string in cover_detection_strings:
                    if ((item.endswith(".jpg") | item.endswith(".jpeg") | item.endswith(
                            ".png") | item.endswith(".tbn ")) and cover_found != 1):
                            cover_found = 1
                            print("Potential cover found: " + os.path.basename(item) + " in " + full_path)
                            print("Defaulting to first image file found")
                            extract_cover(zip_file, file_path, image_file, root, file, full_path, os.path.splitext(file)[0],
                                            item)
                            print("")
                            return
        else:
            files_with_no_image.append(full_path)
            print("Invalid Zip File at: \n" + full_path)

    except zipfile.BadZipFile:
        print("Bad Zipfile.")
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
            print("Bad zip file: ")
    else:
        return 0

def check_for_volume_one_cover(root, zip_file):
    extensionless_path = os.path.join(root, os.path.splitext(os.path.basename(zip_file.filename))[0])
    for volume_string in volume_detection_strings:
        if((os.path.basename(zip_file.filename).__contains__(volume_string))):
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
                        foundExistingCover = foundExistingCover + cover_file_stuff(root, os.path.join(root, file))


main()
print("\nFor all " + str(len(paths)) + " paths.")
print("Total Files Found: " + str(file_count))
print("\t" + str(cbz_count) + " were cbz files")
print("\t" + str(cbr_count) + " were cbr files")
print("\t" + str(epub_count) + " were epub files")
print("\tof those we found " + str(image_count) + " had a cover image file.")
if(files_with_no_image.count != 0):
    print("\nRemaining files without covers:")
    for lonely_file in files_with_no_image:
        print("\t" + lonely_file)
