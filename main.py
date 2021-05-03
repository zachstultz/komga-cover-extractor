import os
import shutil
import time
import zipfile
import zlib
from html.parser import HTMLParser

# ************************************
# Created by: Zach Stultz            *
# Git: https://github.com/zachstultz *
# ***************************************************
# A manga/light novel processor script for use with *
# the manga/light novel reader gotson/komga.        *
# ************************************************************************************************************************
# REMINDER : Add logic for a .rar file, aka .cbr file, also add logic for parsing cover.xhtml for exact cover image name *
# ************************************************************************************************************************

# [ADD IN THE PATHS YOU WANT SCANNED]
paths = ["Y:\\torrents", "Z:\\manga", "Z:\\novels"]
# [ADD IN THE PATHS YOU WANT SCANNED]

# List of image types used throughout the program
image_types = ["jpg", "jpeg", "png", "tbn"]

# List of cover strings used for detection
cover_detection_strings = ["Cover", "cover", "p000", "000 ", "-000", "000a", "_000.", " 001.", "index-1_1"]

volume_detection_strings = ["v01", "Volume 1", "volume 1", "volume 01", "Volume 01", "volume one", "Volume one",
                            "Volume One", "LN 01"]

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
    for image_type in image_types:
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
            with zip_file as z:
                print("\n" + "Zip found\n" + "Entering zip: " + file)
                from platform import system
                if system() == "Windows":
                    with z.open(os.path.join(file_path, image_file).replace("\\", "/")) as zf, open(
                            os.path.join(root,
                                         os.path.basename(name + os.path.splitext(image_file)[1])),
                            'wb') as f:
                        print("Copying file and renaming.")
                        shutil.copyfileobj(zf, f)
                if system() == "Linux":
                    with z.open(os.path.join(file_path, image_file).replace("/", "\\")) as zf, open(
                            os.path.join(root,
                                         os.path.basename(name + os.path.splitext(image_file)[1])),
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
            for item in narrowed:
                head_tail = os.path.split(item)
                file_path = head_tail[0]
                image_file = head_tail[1]
                for string in cover_detection_strings:
                    if item.__contains__(string):
                        print("found cover: " + os.path.basename(os.path.basename(item)) + " in " + file)
                        cover_found = 1
                        cbz_internal_covers_found += 1
                        extract_cover(zip_file, file_path, image_file, root, file, full_path, os.path.splitext(file)[0],
                                      item)
                        break
                    if item.__contains__("cover.xhtml"):
                        print("cover.xhtml found in " + os.path.join(file_path, image_file))
                        # Add logic to parse cover.xhtml for cover image name, then search and extract it.
                    else:
                        if ((item.endswith(".jpg") | item.endswith(".jpeg") | item.endswith(
                                ".png") | item.endswith(".tbn ")) and cover_found != 1):
                            cover_found = 1
                            print("potential cover found: " + os.path.basename(item) + " in " + file_path)
                            print("")
                            break

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
    duplicate_found1 = 0
    duplicate_found2 = 0
    dup = ""
    for image_type in image_types:
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
    if zipfile.is_zipfile(full_path):
        try:
            zip_file = zipfile.ZipFile(full_path)
            if (not (os.path.isfile(os.path.join(root, "cover.jpg")) |
                     os.path.isfile(os.path.join(root, "cover.jpeg")) |
                     os.path.isfile(os.path.join(root, "cover.png")) |
                     os.path.isfile(os.path.join(root, "cover.tbn")))) and (
                    not (os.path.isfile(os.path.join(root, "poster.jpg")) |
                         os.path.isfile(os.path.join(root, "poster.jpeg")) |
                         os.path.isfile(os.path.join(root, "poster.png")) |
                         os.path.isfile(os.path.join(root, "poster.tbn")))) and (
                    os.path.basename(zip_file.filename).__contains__("v01") |
                    os.path.basename(zip_file.filename).__contains__('volume 1') |
                    os.path.basename(zip_file.filename).__contains__('Volume 1') |
                    os.path.basename(zip_file.filename).__contains__('volume 01') |
                    os.path.basename(zip_file.filename).__contains__('Volume 01') |
                    os.path.basename(zip_file.filename).__contains__('volume one') |
                    os.path.basename(zip_file.filename).__contains__('Volume one') |
                    os.path.basename(zip_file.filename).__contains__('Volume One') |
                    os.path.basename(zip_file.filename).__contains__('LN 01')):
                print("Volume 1 Cover Found: " + os.path.basename(zip_file.filename) + " in " + root)
                full_path_without_extension = os.path.join(root, os.path.splitext(
                    os.path.basename(zip_file.filename))[0])
                if os.path.isfile(full_path_without_extension + '.jpg'):
                    shutil.copyfile(full_path_without_extension + '.jpg', os.path.join(root, 'cover.jpg'))
                if os.path.isfile(full_path_without_extension + '.jpeg'):
                    shutil.copyfile(full_path_without_extension + '.jpeg', os.path.join(root, 'cover.jpeg'))
                if os.path.isfile(full_path_without_extension + '.png'):
                    shutil.copyfile(full_path_without_extension + '.png', os.path.join(root, 'cover.png'))
                if os.path.isfile(full_path_without_extension + '.tbn'):
                    shutil.copyfile(full_path_without_extension + '.tbn', os.path.join(root, 'cover.tbn'))
        except zipfile.BadZipFile:
            print("Bad zip file: ")


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
            print("\nCurrent Path: ", root + "\nDirectories: ", dirs)
            print("Files: ", files)
            for file in files:
                full_path = os.path.join(root, file)
                individual_volume_cover_file_stuff(file, root, full_path)
                cover_file_stuff(root, full_path)


main()
print("\nFor all " + str(len(paths)) + " paths.")
print("Total Files Found: " + str(file_count))
print("\t" + str(cbz_count) + " were cbz files")
print("\t" + str(cbr_count) + " were cbr files")
print("\t" + str(epub_count) + " were epub files")
print("\tof those we found " + str(image_count) + " had a cover image file.")