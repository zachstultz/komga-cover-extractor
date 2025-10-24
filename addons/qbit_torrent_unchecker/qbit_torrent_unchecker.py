#!/usr/bin/env python3
import time
import os
import sys

from qbittorrentapi import Client
import regex as re
import argparse

# Scripts root
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# Get two folders below ROOT_DIR
MAIN_SCRIPT_DIR = os.path.abspath(os.path.join(ROOT_DIR, "..", ".."))
sys.path.append(MAIN_SCRIPT_DIR)

log_file_name = "qbit_torrent_unchecker_log"

# Import everything from the script in that directory
from komga_cover_extractor import *

# state filter
target_states = ["pausedDL", "stoppedDL"]

# Torrents actively being processed
processing_torrents = []

# The amount of seconds to sleep when re-attempting a failed login
qbit_sleep_time = 60

# The amount of seconds to sleep before checking for new torrents
torrent_check_sleep_time = 30

# Whether or not to use cached_paths
cached_paths_toggle = True

# Profiles the execution
profile_code = ""


# An alternative to send_message() in the main script
def send_message_alt(
    message,
    error=False,
    log=True,
    error_file_name=f"{log_file_name}_errors.txt",
    changes_file_name=f"{log_file_name}_changes.txt",
):
    print(message)
    if error:
        if log:
            write_to_file(error_file_name, message, can_write_log=log)
    else:
        if log:
            write_to_file(changes_file_name, message, can_write_log=log)


parser = argparse.ArgumentParser(
    description="Script to automatically uncheck torrents in qBittorrent that are not upgrades to existing series files."
)
parser.add_argument(
    "-p",
    "--paths",
    help="Paths to check for existing series",
    action="append",
    nargs="*",
    required=True,
)
parser.add_argument(
    "-df",
    "--download_folders",
    help="The download folder/download folders for processing, renaming, and moving of downloaded files. (Optional, still in testing, requires manual uncommenting of optional method calls at the bottom of the script.)",
    action="append",
    nargs="*",
    required=False,
)

parser = parser.parse_args()

# Parse the user's download folders
if parser.download_folders is not None:
    new_download_folders = []
    for download_folder in parser.download_folders:
        if download_folder:
            if r"\1" in download_folder[0]:
                split_download_folders = download_folder[0].split(r"\1")
                new_download_folders.extend(
                    [split_download_folder]
                    for split_download_folder in split_download_folders
                )
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
            print(f"\t\tpath: {str(item.path)}")
            print(f"\t\t\tformats: {str(item.path_formats)}")
            print(f"\t\t\textensions: {str(item.path_extensions)}")

# Parse the user's paths
if parser.paths is not None:
    new_paths = []
    for path in parser.paths:
        # Split them up if they contain a delimiter
        if path and r"\1" in path[0]:
            split_paths = path[0].split(r"\1")
            new_paths.extend([split_path] for split_path in split_paths)
        else:
            new_paths.append(path)

    parser.paths = new_paths
    print("\tpaths:")
    for path in parser.paths:
        if path:
            # Split them up if they contain a delimiter
            if r"\0" in path[0]:
                path = path[0].split(r"\0")
            process_path(path, paths_with_types, paths)

    if paths_with_types:
        print("\n\tpaths_with_types:")
        for item in paths_with_types:
            send_message_alt(
                f"\t\tpath: {str(item.path)}",
            )
            send_message_alt(
                f"\t\t\tformats: {str(item.path_formats)}",
            )
            send_message_alt(
                f"\t\t\textensions: {str(item.path_extensions)}",
            )

# Load cached_paths.txt into cached_paths
if (
    os.path.isfile(cached_paths_path)
    and check_for_existing_series_toggle
    and not cached_paths
    and cached_paths_toggle
):
    cached_paths = get_lines_from_file(
        cached_paths_path,
        ignore=paths + download_folders,
        check_paths=True,
    )

    # get rid of non-valid paths
    cached_paths = [x for x in cached_paths if os.path.isdir(x)]

# Cache the paths if the user doesn't have a cached_paths.txt file
if (
    (
        cache_each_root_for_each_path_in_paths_at_beginning_toggle
        or not os.path.isfile(cached_paths_path)
    )
    and paths
    and check_for_existing_series_toggle
    and not cached_paths
    and cached_paths_toggle
):
    cached_paths = cache_existing_library_paths(paths, download_folders, cached_paths)
    if cached_paths:
        send_message_alt(f"\n\tLoaded {len(cached_paths)} cached paths")


# Get filtered torrents
def filter_torrents(torrents):
    return [
        torrent
        for torrent in torrents
        if torrent.category == qbittorrent_target_category
        and torrent.state in target_states
        and torrent.hash not in processing_torrents
    ]


# Checks if the passed torrent still exists in qBittorrent
def torrent_exists(torrent, qb):
    return torrent in get_torrents(qb)


# Get torrents
def get_torrents(qb):
    return [torrent for torrent in qb.torrents.info() if torrent.files.data]


# Returns a list of any files containing unacceptable keywords
def exclude_unacceptable_files(files, unacceptable_regexes):
    return [
        file
        for file in files
        if re.search(
            "|".join(unacceptable_regexes), os.path.basename(file.name), re.IGNORECASE
        )
    ]


# Checks if a volume is an upgrade or a new item
def check_upgrade_or_new(volume, existing_files):
    for existing_file in existing_files:
        if is_same_index_number(volume.index_number, existing_file.index_number):
            # Check if the volume is an upgrade
            upgrade_status = (
                is_upgradeable(volume, existing_file).is_upgrade
                if volume.name.lower() != existing_file.name.lower()
                else False
            )

            message = (
                f"\n\tDownload: {volume.name}"
                f"\n\t\t is {'an' if upgrade_status else 'not an'} upgrade to: "
                f"\n\tExisting: {existing_file.name}"
            )

            send_message_alt(message)

            return [volume.name] if upgrade_status else []

    # If the loop completes without finding a match, it's a new item
    message = f"\n\tNew item found: {volume.name}"
    send_message_alt(message)
    return [volume.name]


# Joins all the unacceptable keywords into a single regex
# for faster searching
modified_keywords = (
    [rf"({keyword})" for keyword in unacceptable_keywords]
    if unacceptable_keywords
    else []
)


# Checks if the torrent name contains unacceptable keywords
def has_unacceptable_keywords(torrent):
    if re.search("|".join(modified_keywords), torrent.name, re.IGNORECASE):
        send_message_alt(
            f"\n\t\tTorrent: `{torrent.name}` contains an unacceptable keyword."
        )
        return True
    return False


# Processes file names, removing excluded files
def process_file_names(files, files_to_exclude):
    file_names = [file.name for file in files if file not in files_to_exclude]
    return file_names


# Organizes the file names into volumes
def organize_files(torrent, file_names):
    volumes = []

    for name in file_names:
        dir_name = os.path.basename(os.path.dirname(name)) or torrent.name
        volume_name = os.path.basename(name)

        volume = upgrade_to_volume_class(
            upgrade_to_file_class(
                [volume_name],
                f"/{dir_name}",
                is_correct_extensions_feature=convertable_file_extensions
                + file_extensions,
                test_mode=True,
            ),
            skip_release_year=True,
            skip_release_group=True,
            skip_extras=True,
            skip_publisher=True,
            skip_premium_content=True,
            skip_subtitle=True,
            test_mode=True,
        )
        if volume:
            volumes.append(volume[0])

    return volumes


# Checks volumes for matches
def process_volumes(
    volumes,
    no_matches,
    cached_series,
    files_dict,
    files_to_exclude,
    torrent,
    qb,
):
    for index, volume in enumerate(volumes):
        # Original volume name for so convertable_file_extensions files can be unchecked
        og_volume_base = os.path.basename(volume.path)

        if volume.extension in convertable_file_extensions:
            volume.extension = ".cbz"
            volume.name = f"{get_extensionless_name(volume.name)}{volume.extension}"

        # [X/TOTAL] volume.name
        print(f"\n[{index + 1}/{len(volumes)}] {volume.name}")

        key = f"{volume.series_name} - {volume.file_type} - {volume.extension}"

        if key in no_matches:
            continue

        existing_files = cached_series.get(key, [])

        if not existing_files:
            existing_files = check_for_existing_series(
                test_mode=[volume],
                test_download_folders=download_folders or [ROOT_DIR],
                test_paths=paths,
                test_paths_with_types=paths_with_types,
                test_cached_paths=cached_paths,
            )
            if key not in cached_series:
                cached_series[key] = existing_files

        if not existing_files:
            send_message_alt(f"No matching series found for: '{og_volume_base}'")
            if key not in no_matches:
                no_matches.append(key)
            continue

        keep = check_upgrade_or_new(volume, existing_files)

        if volume.name not in keep:
            torrent_file_item = files_dict.get(og_volume_base, None)
            if torrent_file_item:
                files_to_exclude.append(torrent_file_item)
                print(f"\n\t\tUnchecking: {og_volume_base}")
                uncheck_files(torrent, torrent_file_item, qb)

    return files_to_exclude


# Displays summary information
def display_summary(files, files_to_exclude):
    send_message_alt(f"\n\tTotal Files: {len(files)}")
    send_message_alt(f"\t\tFiles excluded: {len(files_to_exclude)}")
    send_message_alt(f"\t\tFiles to keep: {len(files) - len(files_to_exclude)}")


# Checks the files in the torrent
def check_files(torrent, files, qb):
    # Limit the number of files to process for efficiency
    files_to_exclude = []

    # Check for unacceptable keywords and delete corresponding files if toggle is enabled
    if modified_keywords and delete_unacceptable_files_toggle:
        print("\n\tChecking for unacceptable keywords")

        # check torent title first
        if delete_unacceptable_torrent_titles_in_qbit and has_unacceptable_keywords(
            torrent
        ):
            files_to_exclude = files
            return files_to_exclude

        files_to_exclude.extend(exclude_unacceptable_files(files, modified_keywords))
        for excluded_file in files_to_exclude:
            base_name = os.path.basename(excluded_file.name)
            print(f"\n\t\tFile: {base_name} contains an unacceptable keyword.")
            print(f"\t\t\tUnchecking: {base_name}")
            uncheck_files(torrent, excluded_file, qb)

    print(
        f"\n\tOrganizing {len(files)-len(files_to_exclude)} file names into volumes..."
    )
    file_names = process_file_names(files, files_to_exclude)
    volumes = organize_files(torrent, file_names)

    # Lists to track unmatched volumes and cached series information
    no_matches = []
    cached_series = {}

    # base name : file_object
    files_dict = {os.path.basename(file.name): file for file in files}

    files_to_exclude = process_volumes(
        volumes,
        no_matches,
        cached_series,
        files_dict,
        files_to_exclude,
        torrent,
        qb,
    )

    # Display summary information
    display_summary(files, files_to_exclude)

    return files_to_exclude


# Unchecks the specified files in the torrent
def uncheck_files(torrent, file, qb):
    # Set the priority of files to exclude to 0 (do not download)
    qb.torrents.file_priority(torrent.hash, file_ids=[file.index], priority=0)


# Starts the torrent
def start_torrent(torrent):
    torrent.start()


# Deletes the torrent
def delete_torrent(torrent):
    torrent.delete()


# Process a single torrent
def process_torrent(torrent, qb):
    files = torrent.files.data
    files_to_exclude = check_files(torrent, files, qb)

    if len(files_to_exclude) != len(files):
        send_message_alt(
            f"\n\tStarting Torrent: `{torrent.name}`",
        )
        start_torrent(torrent)
    else:
        send_message_alt(
            f"\n\tDeleting Torrent: `{torrent.name}`",
        )
        delete_torrent(torrent)

    if torrent.hash in processing_torrents:
        processing_torrents.remove(torrent.hash)


# Process a list of torrents
def process_torrents(torrents, qb):
    try:
        for torrent in torrents:
            send_message_alt(
                f"\tChecking Torrent: `{torrent.name}`",
            )
            process_torrent(torrent, qb)
    except Exception as e:
        send_message_alt(
            f"Error checking torrents: {e}",
            error=True,
        )


# Logs into the qBittorrent API and returns a Client object
def login_to_qbittorrent(ip, port, username, password):
    result = None
    try:
        qb = Client(
            host=ip,
            port=port,
            username=username or None,
            password=password or None,
        )
        if username and password:
            qb.auth_log_in()
        result = qb
    except Exception as e:
        send_message_alt(
            f"Error logging into qBittorrent: {e}",
            error=True,
        )
        return None
    return result


# Connect to qBittorrent
def connect_to_qbittorrent(
    qbittorrent_ip, qbittorrent_port, qbittorrent_username, qbittorrent_password
):
    qb = login_to_qbittorrent(
        qbittorrent_ip,
        qbittorrent_port,
        qbittorrent_username,
        qbittorrent_password,
    )
    if qb and qb.is_logged_in:
        return qb
    else:
        return None


def main():
    if not uncheck_non_qbit_upgrades_toggle:
        send_message_alt(
            "uncheck_non_qbit_upgrades_toggle is disabled, exiting...",
        )
        return None

    if not qbittorrent_ip or not qbittorrent_port:
        send_message_alt(
            "qBittorrent IP or Port not set, exiting...",
        )
        return None

    if not qbittorrent_target_category:
        send_message_alt(
            "qBittorrent target category not set, exiting...",
        )
        return None

    send_message_alt(
        "\nWatching for new torrents... (QBit Unchecker)",
    )

    qb = None

    while True:
        try:
            # Connect to qBittorrent
            if not qb or not qb.is_logged_in:
                while not qb or not qb.is_logged_in:
                    qb = connect_to_qbittorrent(
                        qbittorrent_ip,
                        qbittorrent_port,
                        qbittorrent_username,
                        qbittorrent_password,
                    )
                    if qb and qb.is_logged_in:
                        send_message_alt(
                            "\tConnected to qBittorrent.",
                        )
                    else:
                        send_message_alt(
                            f"\tFailed to connect to qBittorrent, retrying in {qbit_sleep_time} seconds...",
                        )
                        time.sleep(qbit_sleep_time)

            torrents = get_torrents(qb)
            filtered_torrents = filter_torrents(torrents)

            if filtered_torrents:
                send_message_alt(
                    f"\tTorrents found: {len(filtered_torrents)}",
                )

                # sort torrents by number of files, lowest to highest
                filtered_torrents.sort(key=lambda x: len(x.files.data))

                for torrent in filtered_torrents:
                    try:
                        send_message_alt(
                            f"\t\tChecking torrent: '{torrent.name}'",
                        )
                        process_torrent(torrent, qb)
                    except Exception as e:
                        send_message_alt(
                            f"Error processing torrent '{torrent.name}': {e}",
                            error=True,
                        )
            time.sleep(torrent_check_sleep_time)  # Adjust the interval as needed
        except Exception as e:
            send_message_alt(
                f"\tError: {e}",
                error=True,
            )


if __name__ == "__main__":
    try:
        if profile_code == "main()":
            cProfile.run(profile_code, sort="cumtime")
        else:
            main()
    except Exception as e:
        send_message_alt(
            f"Error: {e}",
            error=True,
        )
