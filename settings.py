########################### FEATURES ###########################
# deletes any file with an extension in unaccepted_file_extensions from the download_folers
delete_unacceptable_files_toggle = True
# deletes chapter releases from the download_folers
delete_chapters_from_downloads_toggle = True
# replaces any detected volume keyword that isn't what the user specified up top and restructures them
rename_files_in_download_folders_toggle = True
# creates folders for any lone files in the root of the download_folders
create_folders_for_items_in_download_folder_toggle = True
# cleans up any unnessary information in the series folder names within the download_folders
rename_dirs_in_download_folder_toggle = True
# Checks for any duplicate volumes and deletes the inferior copies based on ranked_keywords.
check_for_duplicate_volumes_toggle = True
# extracts covers from cbz and epub files recursively from the paths passed in
extract_covers_toggle = True
# finds the corresponding series name in our existing library for the files in download_folders and handles moving, upgrading, and deletion
check_for_existing_series_toggle = True
# checks for any missing volumes bewteen the highest detected volume number and the lowest
check_for_missing_volumes_toggle = True
################################################################

########################### RENAMING ###########################
# The preferred naming format used by rename_files_in_download_folders()
# v = v01, Volume = Volume01, and so on.
# IF YOU WANT A SPACE BETWEEN THE TWO, ADD IT IN THE PREFERRED NAMING.
preferred_volume_renaming_format = "v"

# Whether or not to add a volume number one to one-shot volumes
# Useful for Comictagger matching, and enabling upgrading of
# one-shot volumes.
# Requires the one shot to be the only cbz or epub file within the folder.
add_volume_one_number_to_one_shots = True

# Whether or not to add the issue number to the file name
# Useful when using ComicTagger
# TRUE: manga v01 #01 (2001).cbz
# FALSE: manga v01 (2001).cbz
add_issue_number_to_cbz_file_name = False

# False = files with be renamed automatically
# True = user will be prompted for approval
manual_rename = False

# If enabled, it will extract all important bits of information from the file, basically restructuring
# when renaming
# Also changes the series name to the folder name that it's being moved to.
resturcture_when_renaming = True

# Whether or not to search an epub file for premium content if no
# premium keyword is found, and add it into the file name.
search_and_add_premium_to_file_name = True
################################################################

########################### UPGRADING ###########################
# Whether or not an isbn/series_id match should be used
# as an alternative when matching a downloaded file to
# the existing library.
# ONLY ACTIVATE IF MY ISBN SCRIPT IS RELEASED
# AND YOU ARE USING IT
match_through_isbn_or_series_id = True

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
    def __init__(self, name, score):
        self.name = name
        self.score = score


# Keywords ranked by point values, used when determining if a downloaded volume
# is an upgrade to the existing volume in the library. Case is ignored when checked.
# EX: Keyword(r"Keyword or Regex", point_value)
ranked_keywords = [
    Keyword(r"(HCAZS?)", 110),
    Keyword(r"Premium", 110),  # For LN releases
    Keyword(r"danke-empire", 100),
    Keyword(r"LuCaZ", 75),
    Keyword(r"DigitalMangaFan", 60),
    Keyword(r"(\b1r0n\b)", 50),
    Keyword(r"Shizu", 25),
    Keyword(r"Digital HD", 5),
    Keyword(r"([\[\{\(](f|r|v)6[\]\}\)])", 5),
    Keyword(r"([\[\{\(](f|r|v)5[\]\}\)])", 4),
    Keyword(r"([\[\{\(](f|r|v)4[\]\}\)])", 3),
    Keyword(r"([\[\{\(](f|r|v)3[\]\}\)])", 2),
    Keyword(r"([\[\{\(](f|r|v)2[\]\}\)])", 1),
    Keyword(r"\[Stick\]", 1),  # For LN releases
    Keyword(r"Shellshock|Ushi|Edge|Nao", 1),
    Keyword(r"AkaHummingBird|aKraa|LostNerevarine-Empire|0v3r", 0),
    Keyword(r"(\[C[0-9]?\])", -1),
    Keyword(r"Scanlated|Scan", -5),
    Keyword(r"([\(\[\{]|\s)PRE([\)\]\}]|\s)", -5),
    Keyword(r"PNG4", -5),
    Keyword(r"Translation", -5),
]
#################################################################

############################# MISC #############################
# Folder names to be ignored
ignored_folder_names = ["Test"]
# List of file types used throughout the program
file_extensions = ["epub", "cbz", "cbr"]  # (cbr is only used for the stat printout)
image_extensions = ["jpg", "jpeg", "png", "tbn", "jxl"]
# file extensions deleted from the download folders in an optional method. [".example"]
unaccepted_file_extensions = [".zip", ".cbr", ".pdf", ".mobi", ".rar", ".doc", ".docx"]
series_cover_file_names = ["cover", "poster"]
# Whether or not to output errors and changes to a log file
log_to_file = True
# Whether or not to check the library against bookwalker for new releases.
bookwalker_check = False
# Prompts the user when deleting an inferior duplicate volume when running
# check_for_duplicate_volumes
manual_delete = True  # for testing
################################################################
