import argparse
from src.config import *
from src.extract_covers import extract_covers
from src.file_operations import (
    correct_file_extensions,
    convert_to_cbz,
    delete_unacceptable_files,
    delete_chapters_from_downloads,
    rename_files,
    create_folders_for_items_in_download_folder,
    check_for_duplicate_volumes,
    rename_dirs_in_download_folder,
    move_series_to_correct_library,
)
from src.bookwalker import check_for_new_volumes_on_bookwalker
from src.komga import scan_komga_library, get_komga_libraries
from src.handlers.watchdog_handler import Watcher
from src.utils.file_utils import cache_existing_library_paths, check_for_existing_series
from src.utils.string_utils import generate_rename_lists

def parse_arguments():
    parser = argparse.ArgumentParser(description=f"Scans for and extracts covers from {', '.join(file_extensions)} files.")
    parser.add_argument("-p", "--paths", help="The path/paths to be scanned for cover extraction.", action="append", nargs="*", required=False)
    parser.add_argument("-df", "--download_folders", help="The download folder/download folders for processing, renaming, and moving of downloaded files.", action="append", nargs="*", required=False)
    parser.add_argument("-wh", "--webhook", action="append", nargs="*", help="The discord webhook url for notifications about changes and errors.", required=False)
    parser.add_argument("-bwc", "--bookwalker_check", help="Checks for new releases on bookwalker.", required=False)
    parser.add_argument("-c", "--compress", help="Compresses the extracted cover images.", required=False)
    parser.add_argument("-cq", "--compress_quality", help="The quality of the compressed cover images.", required=False)
    parser.add_argument("-wd", "--watchdog", help="Uses the watchdog library to watch for file changes in the download folders.", required=False)
    parser.add_argument("--output_covers_as_webp", help="Outputs the covers as WebP format instead of jpg format.", required=False)
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    global cached_paths, processed_files, moved_files, release_groups, publishers, skipped_release_group_files, skipped_publisher_files, transferred_files, transferred_dirs, komga_libraries, libraries_to_scan

    if correct_file_extensions_toggle:
        correct_file_extensions()
    
    if convert_to_cbz_toggle:
        convert_to_cbz()
    
    if delete_unacceptable_files_toggle:
        delete_unacceptable_files()
    
    if delete_chapters_from_downloads_toggle:
        delete_chapters_from_downloads()

    if rename_files_in_download_folders_toggle:
        rename_files()

    if create_folders_for_items_in_download_folder_toggle:
        create_folders_for_items_in_download_folder()

    if check_for_duplicate_volumes_toggle and download_folders:
        check_for_duplicate_volumes(download_folders)

    if extract_covers_toggle and paths and download_folder_in_paths:
        extract_covers()

    if check_for_existing_series_toggle and download_folders and paths:
        check_for_existing_series()

    if rename_dirs_in_download_folder_toggle and download_folders:
        rename_dirs_in_download_folder()

    if move_series_to_correct_library_toggle and library_types and paths_with_types and moved_files:
        move_series_to_correct_library()

    if extract_covers_toggle and paths and not download_folder_in_paths:
        extract_covers()

    if bookwalker_check and not watchdog_toggle:
        check_for_new_volumes_on_bookwalker()

    if send_scan_request_to_komga_libraries_toggle and check_for_existing_series_toggle and moved_files:
        for library_id in libraries_to_scan:
            scan_komga_library(library_id)

if __name__ == "__main__":
    if watchdog_toggle and download_folders:
        print("\nWatchdog is enabled, watching for changes...")
        watch = Watcher()
        watch.run()
    else:
        main()
