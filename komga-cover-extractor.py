import os
import shutil
import zipfile
import zlib
import re
from difflib import SequenceMatcher

# ************************************
# Created by: Zach Stultz            *
# Git: https://github.com/zachstultz *
# ***************************************************
# A manga/light novel processor script for use with *
# the manga/light novel reader gotson/komga.        *
# ***************************************************

# [ADD IN THE PATHS YOU WANT SCANNED]
download_folders = [""] #OPTIONAL [STILL IN TESTING]
paths = [""]
ignored_folders = [""]
# [ADD IN THE PATHS YOU WANT SCANNED]

# List of image types used throughout the program
image_extensions = ["jpg", "jpeg", "png", "tbn"]
file_extensions = [".cbz", ".epub", ".cbr"]

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

# Checks similarity between two strings
# Credit to: https://stackoverflow.com/users/1561176/inbar-rose
def similar(a, b):
    return (SequenceMatcher(None, a.lower(), b.lower()).ratio())

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
                with zip_file.open(os.path.join(file_path, image_file)) as zf, open(
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

def updateStats(file, root):
    global file_count
    global cbz_count
    global epub_count
    global cbr_count
    if file.endswith(".cbz") & os.path.isfile(os.path.join(root, file)):
        file_count += 1
        cbz_count += 1
    if file.endswith(".epub") & os.path.isfile(os.path.join(root, file)):
        file_count += 1
        epub_count += 1
    if file.endswith(".cbr") & os.path.isfile(os.path.join(root, file)):
        file_count += 1
        cbr_count += 1

def individual_volume_cover_file_stuff(file, root, full_path):
    for file_extension in file_extensions:
        if file.endswith(file_extension) & os.path.isfile(os.path.join(root, file)):
            updateStats(file, root)
            if not check_for_image(os.path.splitext(file)[0], root):
                try:
                    check_internal_zip_for_cover(file, full_path, root)
                except zlib.error:
                    print("Error -3 while decompressing data: invalid stored block lengths")

def cover_file_stuff(root, full_path, files):
    for file_extension in file_extensions:
        if(str(full_path).endswith(file_extension) and zipfile.is_zipfile(full_path)):
            try:
                zip_file = zipfile.ZipFile(full_path)
                return check_for_volume_one_cover(root, zip_file, files)
            except zipfile.BadZipFile:
                print("Bad zip file: " + full_path)
                errors.append("Bad zip file: " + full_path)
    return 0

def check_for_volume_one_cover(root, zip_file, files):
    extensionless_path = os.path.join(root, os.path.splitext(os.path.basename(zip_file.filename))[0])
    if re.search(r"(\b(LN|Light Novel|Novel|Book|Volume|Vol|V)([-_. ]|)(One|1|01)\b)", os.path.basename(zip_file.filename), re.IGNORECASE):
        print("Volume 1 Cover Found: " + os.path.basename(zip_file.filename) + " in " + root)
        for extension in image_extensions:
            if os.path.isfile(extensionless_path + '.' + extension):
                shutil.copyfile(extensionless_path + '.' + extension, os.path.join(root, 'cover.' + extension))
                return 1
    else:
        volume_files_exists_within_folder = 0
        for item in files:
            if re.search(r"((\s(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)\b)|\s(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([0-9]+)\s|\s(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([0-9]+)\s)", item, re.IGNORECASE):
                volume_files_exists_within_folder = 1
        if(not re.search(r"((\s(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)\b)|\s(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([0-9]+)\s|\s(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([0-9]+)\s)", os.path.basename(zip_file.filename), re.IGNORECASE) and volume_files_exists_within_folder == 0):
            print("No volume keyword detected, assuming file is a one-shot volume: " + os.path.basename(zip_file.filename) + " in " + root)
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

def remove_hidden_files(files, root):
    for file in files[:]:
        if(file.startswith(".") and os.path.isfile(os.path.join(root, file))):
            files.remove(file)

def move_image(extensionless_path, root, folder_name):
    for extension in image_extensions:
        image = extensionless_path + "." + extension
        image_existance = os.path.isfile(image)
        if(image_existance):
            shutil.move(image, os.path.join(root, folder_name))

def rename_dirs_in_download_folder():
    for download_folder in download_folders:
        if os.path.exists(download_folder):
            for root, dirs, files in os.walk(download_folder):
                remove_hidden_files(files, root)
                for dir in dirs:
                    full_file_path = os.path.dirname(os.path.join(root, dir))
                    directory = os.path.basename(os.path.join(root, full_file_path))
                    if(os.path.basename(download_folder) == directory):
                        if (re.search(r"((\s\[|\]\s)|(\s\(|\)\s)|(\s\{|\}\s))", dir, re.IGNORECASE) or re.search(r"(\s-\s|\s-)$", dir, re.IGNORECASE) or re.search(r"(\bLN\b)", dir, re.IGNORECASE) or re.search(r"((\b(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)\b)|\s(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)([-_.])(LN|Light Novel|Novel|Book|Volume|Vol|V|)([0-9]+)\s)", dir, re.IGNORECASE) or re.search(r"\bPremium\b", dir, re.IGNORECASE)):
                            dir_clean = (re.sub(r"((\b(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)\b)|\s(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([0-9]+)\s|\s(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)([-_.])(\s-\s|)(LN|Light Novel|Novel|Book|Volume|Vol|V|)([0-9]+)\s).*", "", dir, flags=re.IGNORECASE)).strip()
                            dir_clean = (re.sub(r"(\([^()]*\))|(\[[^\[\]]*\])|(\{[^\{\}]*\})", "", dir_clean)).strip()
                            if(not os.path.isdir(os.path.join(root, dir_clean))):
                                os.rename(os.path.join(root, dir), os.path.join(root, dir_clean))
                                #check_for_existing_series_and_move(full_file_path, dir_clean, download_folder)
                            elif(os.path.isdir(os.path.join(root, dir_clean)) and (os.path.join(root, dir) != os.path.join(root, dir_clean))):
                                for root, dirs, files in os.walk(os.path.join(root, dir)):
                                    remove_hidden_files(files, root)
                                    for file in files:
                                        shutil.move(os.path.join(root, file), os.path.join(download_folder, dir_clean))
                                    if len(os.listdir(root) ) == 0:
                                        os.rmdir(root)
                                #check_for_existing_series_and_move(full_file_path, dir_clean, download_folder)
        else:
            if download_folder == "":
                print("\nINVALID: Download folder path cannot be empty.")
                errors.append("INVALID: Download folder path cannot be empty.")
            else:
                print("\nINVALID: " + download_folder + " is an invalid path.")
                errors.append("INVALID: " + download_folder + " is an invalid path.")

# Checks for an existing series by pulling the folder name within the downloads_folder
# Then checks for a 1:1 folder within the paths being scanned
def check_for_existing_series_and_move(full_file_path, dir_clean, download_folder):
    for path in paths:
        if os.path.exists(path):
            try:
                os.chdir(path)
                # Walk into each directory
                for root, dirs, files in os.walk(path):
                    remove_hidden_files(files, root)
                    dirs.sort()
                    files.sort()
                    for dir in dirs:
                        existing_dir_full_file_path = os.path.dirname(os.path.join(root, dir))
                        existing_dir_directory = os.path.basename(os.path.join(root, full_file_path))
                        if(dir == dir_clean and not os.path.join(root, dir).__contains__(existing_dir_directory)):
                            print("Found existing series")
                            download_dir = os.path.join(download_folder, dir_clean)
                            existing_dir = os.path.join(existing_dir_full_file_path, dir)
                            download_dir_files = [f for f in os.listdir(download_dir) if os.path.isfile(os.path.join(download_dir, f))]
                            download_dir_files.sort()
                            remove_hidden_files(download_dir_files, download_folder)
                            remove_all_except_cbz_and_epub(download_dir_files, os.path.join(download_folder, dir_clean))
                            download_dir_files = remove_everything_but_volume_num(download_dir_files, os.path.join(download_folder, dir_clean))
                            existing_dir_files = [f for f in os.listdir(existing_dir) if os.path.isfile(os.path.join(existing_dir, f))]
                            existing_dir_files.sort()
                            remove_hidden_files(existing_dir_files, os.path.join(existing_dir_full_file_path, dir))
                            remove_all_except_cbz_and_epub(existing_dir_files, os.path.join(existing_dir_full_file_path, dir))
                            existing_dir_files = remove_everything_but_volume_num(existing_dir_files, os.path.join(existing_dir_full_file_path, dir))
            except FileNotFoundError:
                print("\nERROR: " + path + " is not a valid path.")
        else:
            if path == "":
                print("\nINVALID: Path cannot be empty.")
            else:
                print("\nINVALID: " + path + " is an invalid path.")

def remove_all_except_cbz_and_epub(files, root):
    for file in files[:]:
        if(not (str(file).endswith(".cbz") or str(file).endswith(".epub")) and os.path.isfile(os.path.join(root, file))):
            files.remove(file)

def remove_everything_but_volume_num(files, root):
    cleaned = []
    for file in files[:]:
        if(not re.search(r"(\b(LN|Light Novel|Novel|Book|Volume|Vol|V)([-_. ]|)([0-9]+)(.[0-9]+|)\b)", file, re.IGNORECASE) and os.path.isfile(os.path.join(root, file))):
            files.remove(file)
        else:
            try:
                file = re.search(r"(\b(LN|Light Novel|Novel|Book|Volume|Vol|V)([-_. ]|)([0-9]+)(.[0-9]+|)\b)", file, re.IGNORECASE).group(1)
                file = re.sub(r"(\b(LN|Light Novel|Novel|Book|Volume|Vol|V))", "", file, flags=re.IGNORECASE).strip()
                cleaned.append(float(file))
            except AttributeError:
                print(str(AttributeError.with_traceback))
    if(len(cleaned) != 0 and (len(cleaned) == len(files))):
        return cleaned
        
def create_folders_for_items_in_download_folder():
    for download_folder in download_folders:
        if os.path.exists(download_folder):
            for root, dirs, files in os.walk(download_folder):
                remove_hidden_files(files, root)
                for file in files:
                    extensionless_path = os.path.join(root, os.path.splitext(os.path.basename(file))[0])
                    full_file_path = os.path.dirname(os.path.join(root, file))
                    directory = os.path.basename(os.path.join(root, full_file_path))
                    if(file.endswith(".cbz") or file.endswith(".epub") or file.endswith(".cbr")):
                        if(os.path.basename(download_folder) == directory):
                            similarity_result = similar(file, directory)
                            if(similarity_result < 0.4):
                                folder_name = re.sub(r"(\([^()]*\))|(\[[^\[\]]*\])", "", os.path.splitext(file)[0])
                                folder_name = (re.sub(r"(\b(LN|Light Novel|Novel|Book|Volume|Vol|V|)([-_. ]|)([0-9]+)\b)", "", folder_name, flags=re.IGNORECASE)).strip()
                                #folder_name = (re.sub(r"\s-\s", "", folder_name)).strip()
                                does_folder_exist = os.path.exists(os.path.join(root, folder_name))
                                if not does_folder_exist:
                                    os.mkdir(os.path.join(root, folder_name))
                                    shutil.move(os.path.join(root, file), os.path.join(root, folder_name))
                                    move_image(extensionless_path, root, folder_name)
                                else:
                                    shutil.move(os.path.join(root, file), os.path.join(root, folder_name))
                                    move_image(extensionless_path, root, folder_name)
        else:
            if download_folder == "":
                print("\nINVALID: Download folder path cannot be empty.")
                errors.append("INVALID: Download folder path cannot be empty.")
            else:
                print("\nINVALID: " + download_folder + " is an invalid path.")
                errors.append("INVALID: " + download_folder + " is an invalid path.")
def main():
    global file_count
    global cbz_count
    global epub_count
    rename_dirs_in_download_folder()
    create_folders_for_items_in_download_folder()
    for path in paths:
        if os.path.exists(path):
            try:
                os.chdir(path)
                # Walk into each directory
                for root, dirs, files in os.walk(path):
                    dirs.sort()
                    files.sort()
                    remove_hidden_files(files, root)
                    dirs[:] = [d for d in dirs if d not in ignored_folders]
                    print_file_info(root, dirs, files)
                    foundExistingCover = check_for_existing_cover(files)
                    for file in files:
                        individual_volume_cover_file_stuff(file, root, os.path.join(root, file))
                        if(foundExistingCover == 1):
                            check_for_duplicate_cover(root)
                        if(foundExistingCover == 0):
                            try:
                                foundExistingCover = foundExistingCover + cover_file_stuff(root, os.path.join(root, file), files)
                            except Exception:
                                print("Exception thrown when finding existing cover.")
                                print("Excpetion occured on: " + str(file))
            except FileNotFoundError:
                print("\nERROR: " + path + " is not a valid path.")
        else:
            if path == "":
                print("\nINVALID: Path cannot be empty.")
            else:
                print("\nINVALID: " + path + " is an invalid path.")

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
