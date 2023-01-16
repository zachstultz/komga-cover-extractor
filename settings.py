########################### FEATURES ###########################
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
# extracts covers from cbz and epub files recursively from the paths array.
extract_covers_toggle = True
# finds the corresponding series name in our existing library for the files in download_folders and handles moving, upgrading, and deletion
check_for_existing_series_toggle = False
# checks for any missing volumes bewteen the highest detected volume number and the lowest
check_for_missing_volumes_toggle = False
# caches the roots of each item obtained through os.scandir at the beginning of the script,
# used when matching a downloaded volume to an existing library
cache_each_root_for_each_path_in_paths_at_beginning_toggle = False
# sends a scan request to each komga library after check_for_existing_series is done, requires komga settings at the bottom
send_scan_request_to_komga_libraries_toggle = False
################################################################

########################### RENAMING/PROCESSING ###########################
# The preferred naming format used by rename_files_in_download_folders()
# v = v01, Volume = Volume01, and so on.
# IF YOU WANT A SPACE BETWEEN THE TWO, ADD IT IN THE PREFERRED NAMING.
preferred_volume_renaming_format = "v"

# Whether or not to add a volume number one to one-shot volumes
# Useful for Comictagger matching, and enabling upgrading of
# one-shot volumes.
# Requires the one shot to be the only cbz or epub file within the folder.
add_volume_one_number_to_one_shots = False

# Whether or not to add the issue number to the file name
# Useful when using ComicTagger
# TRUE: manga v01 #01 (2001).cbz
# FALSE: manga v01 (2001).cbz
add_issue_number_to_cbz_file_name = False

# False = files/folders with be renamed automatically
# True = user will be prompted for approval
manual_rename = True

# If enabled, it will extract all important bits of information from the file, basically restructuring
# when renaming
# Also changes the series name to the folder name that it's being moved to.
resturcture_when_renaming = False

# Whether or not to search an epub file for premium content if no
# premium keyword is found, then it adds it into the file name in square brackets.
search_and_add_premium_to_file_name = False

# Whether or not to add the pulled publisher from the cbz or epub file to the
# file name when renmaing.
add_publisher_name_to_file_name_when_renaming = False

# Exception keywords used when deleting chapter files with the delete_chapters_from_downloads() function.
# Files containing a match to any exception keywords will be ignored.
# Case is ignored when checked.
exception_keywords = [
    r"Extra",
    r"One(-|)shot",
    r"Omake",
    r"Special",
    r"Bonus",
    r"Side(-|)story",
]
################################################################

########################### UPGRADING ###########################
# Whether or not an isbn/series_id match should be used
# as an alternative when matching a downloaded file to
# the existing library.
# ONLY ACTIVATE IF MY ISBN SCRIPT IS RELEASED
# AND YOU ARE USING IT
match_through_isbn_or_series_id = False

# True = Multi-volumes can match against single volumes, but not the other way around.
#   EX: volume 3-4 can match to the individual volumes 3 and 4.
# False = Multi-volumes can only match against multi-volumes.
#   EX: volume 3-4 can only match to another multi-volume release of 3-4
allow_matching_single_volumes_with_multi_volumes = False

# The required file type matching percentage between
# the download folder and the existing folder
#
# For exmpale, 90% of the folder's files must be CBZ or EPUB
# Used to avoid accdientally matching an epub volume to a manga library
# or vice versa because they can have the same exact series name.
required_matching_percentage = 90

# The required score when comparing two strings likeness, used when matching a series_name to a folder name.
required_similarity_score = 0.9790

# Keyword Class
class Keyword:
    def __init__(self, name, score, file_type="both"):
        self.name = name
        self.score = score
        self.file_type = file_type

# Keywords ranked by point values, used when determining if a downloaded volume
# is an upgrade to the existing volume in the library.
# Case is ignored when checked.
# EX: Keyword(r"Keyword or Regex", point_value, "chapter" or "volume" or "both") # "both" is default
ranked_keywords = []
#################################################################

############################# MISC #############################
# Folder names to be ignored
ignored_folder_names = [""]
# List of file types used throughout the program
file_extensions = ["epub", "cbz"]
image_extensions = ["jpg", "jpeg", "png", "tbn", "jxl"]
# file extensions that will be deleted from the download folders in an optional method. EX: [".example"]
unaccepted_file_extensions = []
series_cover_file_names = ["cover", "poster"]
# Whether or not to output errors and changes to a log file
log_to_file = False
# Whether or not to check the library against bookwalker for new releases.
bookwalker_check = False
# Prompts the user when deleting a lower-ranking duplicate volume when running
# check_for_duplicate_volumes()
manual_delete = True  # for testing, verify the results
# Any keywords/regexes within this array that are found within a file name,
# will be automatically deleted from the download_folders by delete_unacceptable_files()
# Case is ignored.
# EX: r"Keyword or Regex"
unacceptable_keywords = []

# When creating a folder for a lone file, if enabled, it will first check if any existing folder names
# are similar enough, and instead use that.
# (Fixes multiple folders for the same series where the file name did or did not include punctuation)
# (Similarity check uses required_similarity_score)
move_lone_files_to_similar_folder = True

# Replaces the series name in the file name with the similar folders name.
replace_series_name_in_file_name_with_similar_folder_name = True


###### EXPERIMENTAL SETTINGS/FEATURES ######

# KOMGA SCAN REQUEST - sends a scan request to komga after files have been moved
komga_ip = ""  # ex: http://localhost
komga_port = ""  # komga default is 8080
komga_login_email = ""  # your login email
komga_login_password = ""  # your login password

# ex: http://localhost:8080/libraries/0647PPYWAC6AX/series
# ex: komga_library_ids = ["0647PPYWAC6AX"] separate ids by commas
komga_library_ids = []

# Whether or not to generate a release_groups.txt file in the logs folder or add to it
# with the help of the user's input. (remember to disable afterwards!)
# Used when renaming files with reorganize_and_rename.
# Release group names will be moved to the end of the file name.
# encased by () brackets with manga, [] brackets with light novels
# REQUIRES log_to_file=True above!
generate_release_group_list_toggle = False

# The similarity score requirement when matching any brackted release group
# within a file name. Used when rebuilding the file name in reorganize_and_rename.
release_group_similarity_score = 0.8

# Will forgo sending any discord notifications related to renaming files.
mute_discord_rename_notifications = False

# Chapter support is currently experimental and may not work as intended.
# This will enable chapter support for all relavent functions and features.
chapter_support_toggle = False  # EXPERIMENTAL

# The preferred naming format for chapters, used by rename_files_in_download_folders()
# c = c001, Chapter = Chapter01, and so on.
# IF YOU WANT A SPACE BETWEEN THE TWO, ADD IT IN THE PREFERRED NAMING.
preferred_chapter_renaming_format = "c"

# Whether or not covers should be outputted to discord when a new chapter release
# is moved to the library.
output_chapter_covers_to_discord = False

# Whether or not to rename the chapter number in releases with the preferred chapter keyword.
rename_chapters_with_preferred_chapter_keyword = False

# Whether or not to extract chapter covers from chapter files.
extract_chapter_covers = False
################################################################
