########################### FEATURES ###########################
# corrects any incorrect file extensions in the download_folders, using the file header
correct_file_extensions_toggle = False
# converts any rar/cbr/7zip files in the download_folders to cbz files
convert_to_cbz_toggle = False
# deletes any file with an extension in unaccepted_file_extensions from the download_folers
delete_unacceptable_files_toggle = False
# deletes chapter releases from the download_folers
delete_chapters_from_downloads_toggle = False
# replaces any detected volume keyword that isn't what the user specified up top and restructures them
rename_files_in_download_folders_toggle = False
# creates folders for any lone files in the root of the download_folders
create_folders_for_items_in_download_folder_toggle = False
# cleans up any unnessary information in the series folder names within the download_folders
rename_dirs_in_download_folder_toggle = False
# Checks for any duplicate volumes and deletes the lower scoring copies based on ranked_keywords.
check_for_duplicate_volumes_toggle = False
# extracts covers from manga and novel files recursively from the paths array.
extract_covers_toggle = True
# finds the corresponding series name in our existing library for the files in download_folders and handles moving, upgrading, and deletion
check_for_existing_series_toggle = False
# checks for any missing volumes bewteen the highest detected volume number and the lowest
check_for_missing_volumes_toggle = False
# caches the roots of each item obtained through os.scandir at the beginning of the script,
# used when matching a downloaded volume to an existing library
cache_each_root_for_each_path_in_paths_at_beginning_toggle = False
# sends a scan request to each komga library after check_for_existing_series is done, if something got added, requires komga settings at the bottom
send_scan_request_to_komga_libraries_toggle = False
# unchecks any qbitorrents that are not an upgrade to the existing library
# requires: qbittorrent settings at the bottom and check_for_existing_series_toggle = True
uncheck_non_qbit_upgrades_toggle = False
################################################################

########################### RENAMING/PROCESSING ###########################
# The preferred naming format used by rename_files_in_download_folders()
# v = v01, Volume = Volume01, and so on.
# IF YOU WANT A SPACE BETWEEN THE TWO, ADD IT IN THE PREFERRED NAMING.
preferred_volume_renaming_format = "v"

# Adds a volume number one to one-shot volumes
# Useful for Comictagger matching, and enabling upgrading of
# one-shot volumes.
# Requires the one shot to be the only manga or novel file within the folder.
add_volume_one_number_to_one_shots = False

# Adds the issue number to the file name
# Useful when using ComicTagger
# TRUE:  manga v01 #01 (2001).extension
# FALSE: manga v01 (2001).extension
add_issue_number_to_manga_file_name = False

# False = files/folders with be renamed automatically
# True = user will be prompted for approval
manual_rename = True

# If enabled, it will extract all important bits of information from the file, basically restructuring
# when renaming
# Also changes the series name to the folder name that it's being moved to.
resturcture_when_renaming = False

# Searches a novel file for premium content and adds it to the file name.
search_and_add_premium_to_file_name = False

# Adds the pulled publisher from the manga or novel file to the file name when renmaing.
add_publisher_name_to_file_name_when_renaming = False

# Exception keywords used when deleting chapter files with the delete_chapters_from_downloads() function.
# Files containing a match to any exception keyword will be ignored.
# Case is ignored when checked.
exception_keywords = [
    r"Extra",
    r"One(-|)shot",
    r"Omake",
    r"Special",
    r"Bonus",
    r"Side(-|)story",
]

# If a release_groups.txt is found within the logs folder, and a match is found,
# and this is enabled, then when using reorganize & rename,
# it will move the release group to the end of the file name.
#
# A release_groups.txt list can be created with the input of the user by enabling
# generate_release_group_list_toggle = True and log_to_file = True, below, create it, and then turn this off after creation.
#
# BEFORE: Series Name v01 (Group) (f).extension
# AFTER : Series Name v01 (f) (Group).extension
move_release_group_to_end_of_file_name = False

# Uses unidecode to replace unicode characters when restructuring a file name.
# Requires: resturcture_when_renaming = True
replace_unicode_when_restructuring = False

# Will forgo sending any discord notifications related to renaming files.
mute_discord_rename_notifications = False

# When creating a folder for a lone file, if enabled, it will first check if any existing folder names
# are similar enough, and instead use that.
# (Fixes multiple folders for the same series where the file name did or did not include punctuation)
# (Similarity check uses required_similarity_score)
# Requires: create_folders_for_items_in_download_folder_toggle = True
move_lone_files_to_similar_folder = False

# Replaces the series name in the file name with the similar folders name.
# Requires: move_lone_files_to_similar_folder = True
replace_series_name_in_file_name_with_similar_folder_name = False
################################################################

########################### UPGRADING ###########################
# Zip comment identifier match
# when matching a downloaded file to the existing library.
# (ONLY ACTIVATE IF MY ISBN SCRIPT IS RELEASED AND YOU ARE USING IT)
match_through_identifiers = False

# The required score when comparing two strings likeness, used when matching a series_name to a folder name.
required_similarity_score = 0.9790


# Keyword Class
class Keyword:
    def __init__(self, name, score, file_type="both"):
        self.name = name
        self.score = score
        self.file_type = file_type

    # to string
    def __str__(self):
        return f"Name: {self.name}, Score: {self.score}, File Type: {self.file_type}"

    def __repr__(self):
        return str(self)


# Keywords ranked by point values, used when determining if a downloaded volume
# is an upgrade to the existing volume in the library. Case is ignored when checked.
#
# EX: Keyword(
#       r"Keyword or Regex", point_value, "chapter" or "volume" or "both"
#     )
# "both" is default
ranked_keywords = []
#################################################################

############################# MISC #############################
# Folder names to be ignored
ignored_folder_names = []

# Outputs errors and changes to a log file
log_to_file = False

# Any keywords/regexes within this array that are found within a file name,
# will be automatically deleted from the download_folders by delete_unacceptable_files()
# Case is ignored.
# EX: r"Keyword or Regex"
unacceptable_keywords = []

# Komaga Server Settings
komga_ip = ""  # Ex: http://localhost
komga_port = ""  # komga default is 25600
komga_login_email = ""  # your login email
komga_login_password = ""  # your login password

###### EXPERIMENTAL SETTINGS/FEATURES ######
# Generates a release_groups.txt file in the logs folder or add to it
# with the help of the user's input. (remember to disable afterwards!)
# Used when renaming files with reorganize_and_rename.
# Release group names will be moved to the end of the file name.
# encased by () brackets with manga, [] brackets with light novels
# REQUIRES log_to_file=True above!
generate_release_group_list_toggle = False

# Chapter support is currently experimental and may not work as intended.
# This will enable chapter support for all relavent functions and features.
chapter_support_toggle = False  # EXPERIMENTAL

# The preferred naming format for chapters, used by rename_files_in_download_folders()
# c = c001, Chapter = Chapter001, and so on.
# IF YOU WANT A SPACE BETWEEN THE TWO, ADD IT IN THE PREFERRED NAMING.
preferred_chapter_renaming_format = "c"

# Outputs chapter covers to discord when there's a new chapter release.
# is moved to the library.
output_chapter_covers_to_discord = False

# Renames the chapter number in releases with the preferred chapter keyword.
rename_chapters_with_preferred_chapter_keyword = False

# Extracts chapter covers from chapter files.
extract_chapter_covers = False

# When the program has detected a cover image file within the manga or novel file, it will compare that image
# against a blank white image and a blank black image to avoid picking the wrong cover.
compare_detected_cover_to_blank_images = False  # WILL INCREASE PROCESSING TIME

# Uses the latest volume cover as the series cover, when extracting covers, instead of the first volumes' cover.
# Using modification date and hashing for matching, it can automatically switch your covers back and forth
# between the latest and volume one covers. All you have to do is flick the setting on and off.
use_latest_volume_cover_as_series_cover = False

# Renames .zip files to .cbz with convert_to_cbz() if they're valid zip files
# Requires: convert_to_cbz_toggle = True
rename_zip_to_cbz = True

# Attempts to auto-classifyin the user's watchdog paths'
# extension types and library type ("volume" or "chapter")
# Requires: --watchdog "True" and check_for_existing_series_toggle = True
auto_classify_watchdog_paths = False

# qBittorrent API credentials
# Requires: uncheck_non_qbit_upgrades_toggle = True
#           check_for_existing_series_toggle = True
#
# REQUIRED:
qbittorrent_ip = ""  # EX: localhost
qbittorrent_port = ""  # default is 8080
qbittorrent_target_category = ""  # create a category in qbit and put it here
# OPTIONAL:
qbittorrent_username = ""  # leave blank if you don't require login
qbittorrent_password = ""  # leave blank if you don't require login

# Will remove unacceptable torrent titles in qbittorrent
# if they contain an unacceptable keyword match.
# Requires: delete_unacceptable_files_toggle = True
#           check_for_existing_series_toggle = True
#           uncheck_non_qbit_upgrades_toggle = True
delete_unacceptable_torrent_titles_in_qbit = False
################################################################
