import os
import shutil
import zipfile
import py7zr
import rarfile
from src.config import *

def get_file_extension(file):
    return os.path.splitext(file)[1]

def remove_file(full_file_path, silent=False):
    if not os.path.isfile(full_file_path):
        send_message(f"{full_file_path} is not a file.", error=True)
        return False

    try:
        os.remove(full_file_path)
    except OSError as e:
        send_message(f"Failed to remove {full_file_path}: {e}", error=True)
        return False

    if os.path.isfile(full_file_path):
        send_message(f"Failed to remove {full_file_path}.", error=True)
        return False

    if not silent:
        send_message(f"File removed: {full_file_path}", discord=False)

    return True

def move_file(file, new_location, silent=False, highest_index_num="", is_chapter_dir=False):
    try:
        if os.path.isfile(file.path):
            shutil.move(file.path, new_location)
            if os.path.isfile(os.path.join(new_location, file.name)):
                if not silent:
                    send_message(f"\t\tMoved File: {file.name} to {new_location}", discord=False)
                return True
            else:
                send_message(f"\t\tFailed to move: {os.path.join(file.root, file.name)} to: {new_location}", error=True)
                return False
    except OSError as e:
        send_message(str(e), error=True)
        return False

def rename_file(src, dest, silent=False):
    result = False
    if os.path.isfile(src):
        root = os.path.dirname(src)
        if not silent:
            print(f"\n\t\tRenaming {src}")
        try:
            os.rename(src, dest)
        except Exception as e:
            send_message(f"Failed to rename {os.path.basename(src)} to {os.path.basename(dest)}\n\tERROR: {e}", error=True)
            return result
        if os.path.isfile(dest):
            result = True
            if not silent:
                send_message(f"\n\t\t{os.path.basename(src)} was renamed to {os.path.basename(dest)}", discord=False)
        else:
            send_message(f"Failed to rename {src} to {dest}\n\tERROR: {e}", error=True)
    else:
        send_message(f"File {src} does not exist. Skipping rename.", discord=False)
    return result

def extract(file_path, temp_dir, extension):
    successful = False
    try:
        if extension in rar_extensions:
            with rarfile.RarFile(file_path) as rar:
                rar.extractall(temp_dir)
                successful = True
        elif extension in seven_zip_extensions:
            with py7zr.SevenZipFile(file_path, "r") as archive:
                archive.extractall(temp_dir)
                successful = True
    except Exception as e:
        send_message(f"Error extracting {file_path}: {e}", error=True)
    return successful

def compress(temp_dir, cbz_filename):
    successful = False
    try:
        with zipfile.ZipFile(cbz_filename, "w") as zip:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    zip.write(
                        os.path.join(root, file),
                        os.path.join(root[len(temp_dir) + 1 :], file),
                    )
            successful = True
    except Exception as e:
        send_message(f"Error compressing {temp_dir}: {e}", error=True)
    return successful

def cache_existing_library_paths(paths=paths, download_folders=download_folders, cached_paths=cached_paths):
    paths_cached = []
    print("\nCaching paths recursively...")
    for path in paths:
        if os.path.exists(path):
            if path not in download_folders:
                try:
                    for root, dirs, files in os.walk(path):
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

# Add other file utility functions here
