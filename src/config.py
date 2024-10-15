import os
import re
from settings import *

# Version of the script
script_version = (2, 5, 21)
script_version_text = "v{}.{}.{}".format(*script_version)

# Paths and folders
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
ADDONS_DIR = os.path.join(ROOT_DIR, "addons")

# Docker Status
in_docker = ROOT_DIR == "/app"
if in_docker:
    script_version_text += " • Docker"

# Image paths
blank_white_image_path = os.path.join(ROOT_DIR, "blank_white.jpg") if os.path.isfile(os.path.join(ROOT_DIR, "blank_white.jpg")) else None
blank_black_image_path = os.path.join(ROOT_DIR, "blank_black.png") if os.path.isfile(os.path.join(ROOT_DIR, "blank_black.png")) else None

# File extensions
manga_extensions = [".zip", ".cbz"]
novel_extensions = [".epub"]
file_extensions = novel_extensions + manga_extensions
seven_zip_extensions = [".7z"]
rar_extensions = [".rar", ".cbr"]
convertable_file_extensions = seven_zip_extensions + rar_extensions
image_extensions = {".jpg", ".jpeg", ".png", ".tbn", ".webp"}

# Regex patterns
volume_keywords = ["LN", "Light Novels?", "Novels?", "Books?", "Volumes?", "Vols?", "Discs?", "Tomo", "Tome", "Von", "V", "第", "T"]
chapter_keywords = ["Chapters?", "Chaps?", "Chs?", "Cs?", "D"]
volume_regex_keywords = "(?<![A-Za-z])" + "|(?<![A-Za-z])".join(volume_keywords)
chapter_regex_keywords = r"(?<![A-Za-z])" + (r"|(?<![A-Za-z])").join(chapter_keywords)

# Other configurations
image_count = 0
errors = []
items_changed = []
discord_webhook_url = []
bookwalker_webhook_urls = []
release_groups = []
publishers = []
skipped_release_group_files = []
skipped_publisher_files = []
processed_files = []
moved_files = []
cached_paths = []
cached_identifier_results = []
watchdog_toggle = False
compress_image_option = False
image_quality = 40
bookwalker_check = False
log_to_file = True
output_covers_as_webp = False

# Import all settings
for var in dir(settings):
    if not callable(getattr(settings, var)) and not var.startswith("__"):
        globals()[var] = getattr(settings, var)

# Komga settings
komga_libraries = []

# Add any other necessary configurations here
