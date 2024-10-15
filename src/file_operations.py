import os
import shutil
import re
import tempfile
import zipfile
from src.config import *
from src.utils.file_utils import get_file_extension, remove_file, move_file, rename_file, extract, compress
from src.utils.string_utils import remove_dual_space, clean_str, similar
from src.models.file import File
from src.models.folder import Folder

def correct_file_extensions():
    print("\nChecking for incorrect file extensions...")

    if not download_folders:
        print("\tNo download folders specified.")
        return

    for folder in download_folders:
        if not os.path.isdir(folder):
            print(f"\t{folder} does not exist.")
            continue

        print(f"\t{folder}")
        for root, dirs, files in os.walk(folder):
            files, dirs = process_files_and_folders(
                root,
                files,
                dirs,
                just_these_files=transferred_files,
                just_these_dirs=transferred_dirs,
                is_correct_extensions_feature=file_extensions + rar_extensions,
            )
            volumes = upgrade_to_file_class(
                [f for f in files if os.path.isfile(os.path.join(root, f))],
                root,
                skip_get_header_extension=False,
                is_correct_extensions_feature=file_extensions + rar_extensions,
            )

            if not volumes:
                continue

            for volume in volumes:
                if not volume.header_extension:
                    continue

                print(
                    f"\n\t\t{volume.name}\n\t\t\tfile extension:   {volume.extension}\n\t\t\theader extension: {volume.header_extension}"
                )
                if volume.extension != volume.header_extension:
                    print(
                        f"\n\t\t\tRenaming File:\n\t\t\t\t{volume.name}\n\t\t\t\t\tto\n\t\t\t\t{volume.extensionless_name}{volume.header_extension}"
                    )
                    user_input = (
                        get_input_from_user("\t\t\tRename", ["y", "n"], ["y", "n"])
                        if manual_rename
                        else "y"
                    )

                    if user_input == "y":
                        new_path = (
                            f"{volume.extensionless_path}{volume.header_extension}"
                        )
                        rename_status = rename_file(
                            volume.path,
                            new_path,
                            silent=True,
                        )
                        if rename_status:
                            print("\t\t\tRenamed successfully")
                            if not mute_discord_rename_notifications:
                                embed = handle_fields(
                                    DiscordEmbed(
                                        title="Renamed File",
                                        color=grey_color,
                                    ),
                                    fields=[
                                        {
                                            "name": "From",
                                            "value": f"```{volume.name}```",
                                            "inline": False,
                                        },
                                        {
                                            "name": "To",
                                            "value": f"```{volume.extensionless_name}{volume.header_extension}```",
                                            "inline": False,
                                        },
                                    ],
                                )
                                grouped_notifications = group_notification(
                                    grouped_notifications,
                                    Embed(embed, None),
                                )
                                if watchdog_toggle:
                                    if volume.path in transferred_files:
                                        transferred_files.remove(volume.path)
                                    if new_path not in transferred_files:
                                        transferred_files.append(new_path)
                    else:
                        print("\t\t\tSkipped")

def convert_to_cbz():
    print("\nLooking for archives to convert to CBZ...")

    if not download_folders:
        print("\tNo download folders specified.")
        return

    for folder in download_folders:
        if not os.path.isdir(folder):
            print(f"\t{folder} is not a valid directory.")
            continue

        print(f"\t{folder}")
        for root, dirs, files in os.walk(folder):
            files, dirs = process_files_and_folders(
                root,
                files,
                dirs,
                just_these_files=transferred_files,
                just_these_dirs=transferred_dirs,
                skip_remove_unaccepted_file_types=True,
                keep_images_in_just_these_files=True,
            )

            for entry in files:
                try:
                    extension = get_file_extension(entry)
                    file_path = os.path.join(root, entry)

                    if not os.path.isfile(file_path):
                        continue

                    print(f"\t\t{entry}")

                    if extension in convertable_file_extensions:
                        source_file = file_path
                        repacked_file = f"{get_extensionless_name(source_file)}.cbz"

                        if os.path.isfile(repacked_file):
                            if get_file_size(repacked_file) == 0:
                                send_message("\t\t\tCBZ file is zero bytes, deleting...", discord=False)
                                remove_file(repacked_file)
                            elif not zipfile.is_zipfile(repacked_file):
                                send_message("\t\t\tCBZ file is not a valid zip file, deleting...", discord=False)
                                remove_file(repacked_file)
                            else:
                                send_message("\t\t\tCBZ file already exists, skipping...", discord=False)
                                continue

                        temp_dir = tempfile.mkdtemp("_source2cbz")

                        if os.listdir(temp_dir):
                            send_message(f"\t\t\tTemp directory {temp_dir} is not empty, deleting...", discord=False)
                            remove_folder(temp_dir)
                            temp_dir = tempfile.mkdtemp("source2cbz")

                        if not os.path.isdir(temp_dir):
                            send_message(f"\t\t\tFailed to create temp directory {temp_dir}", error=True)
                            continue

                        send_message(f"\t\t\tCreated temp directory {temp_dir}", discord=False)

                        extract_status = extract(source_file, temp_dir, extension)

                        if not extract_status:
                            send_message(f"\t\t\tFailed to extract {source_file}", error=True)
                            remove_folder(temp_dir)
                            continue

                        print(f"\t\t\tExtracted contents to {temp_dir}")

                        hashes = []
                        for root2, dirs2, files2 in os.walk(temp_dir):
                            for file2 in files2:
                                path = os.path.join(root2, file2)
                                hashes.append(get_file_hash(path))

                        compress_status = compress(temp_dir, repacked_file)

                        if not compress_status:
                            remove_folder(temp_dir)
                            continue

                        print(f"\t\t\tCompressed to {repacked_file}")

                        source_file_list = []
                        repacked_file_list = []

                        if os.path.isfile(source_file):
                            if extension in rar_extensions:
                                with rarfile.RarFile(source_file) as rar:
                                    for file in rar.namelist():
                                        if get_file_extension(file):
                                            source_file_list.append(file)
                            elif extension in seven_zip_extensions:
                                with py7zr.SevenZipFile(source_file) as seven_zip:
                                    for file in seven_zip.getnames():
                                        if get_file_extension(file):
                                            source_file_list.append(file)

                        if os.path.isfile(repacked_file):
                            with zipfile.ZipFile(repacked_file) as zip:
                                for file in zip.namelist():
                                    if get_file_extension(file):
                                        repacked_file_list.append(file)

                        source_file_list.sort()
                        repacked_file_list.sort()

                        if (source_file_list and repacked_file_list) and (source_file_list != repacked_file_list):
                            print("\t\t\tVerifying that all files are present in both archives...")
                            for file in source_file_list:
                                if file not in repacked_file_list:
                                    print(f"\t\t\t\t{file} is not in {repacked_file}")
                            for file in repacked_file_list:
                                if file not in source_file_list:
                                    print(f"\t\t\t\t{file} is not in {source_file}")

                            remove_folder(temp_dir)
                            remove_file(repacked_file)
                            continue
                        else:
                            print("\t\t\tAll files are present in both archives.")

                        hashes_verified = False

                        with zipfile.ZipFile(repacked_file) as zip:
                            for file in zip.namelist():
                                if get_file_extension(file):
                                    hash = get_file_hash(repacked_file, True, file)
                                    if hash and hash not in hashes:
                                        print(f"\t\t\t\t{file} hash did not match")
                                        break
                            else:
                                hashes_verified = True

                        remove_folder(temp_dir)

                        if hashes_verified:
                            send_message("\t\t\tHashes verified.", discord=False)
                            send_message(f"\t\t\tConverted {source_file} to {repacked_file}", discord=False)
                            embed = handle_fields(
                                DiscordEmbed(
                                    title="Converted to CBZ",
                                    color=grey_color,
                                ),
                                fields=[
                                    {
                                        "name": "From",
                                        "value": f"```{os.path.basename(source_file)}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "To",
                                        "value": f"```{os.path.basename(repacked_file)}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "Location",
                                        "value": f"```{os.path.dirname(repacked_file)}```",
                                        "inline": False,
                                    },
                                ],
                            )
                            grouped_notifications = group_notification(
                                grouped_notifications, Embed(embed, None)
                            )

                            remove_file(source_file)

                            if watchdog_toggle:
                                if source_file in transferred_files:
                                    transferred_files.remove(source_file)
                                if repacked_file not in transferred_files:
                                    transferred_files.append(repacked_file)
                        else:
                            send_message("\t\t\tHashes did not verify", error=True)
                            remove_file(repacked_file)

                    elif extension == ".zip" and rename_zip_to_cbz:
                        header_extension = get_header_extension(file_path)
                        if zipfile.is_zipfile(file_path) or header_extension in manga_extensions:
                            rename_path = f"{get_extensionless_name(file_path)}.cbz"

                            user_input = (
                                get_input_from_user(
                                    "\t\t\tRename to CBZ",
                                    ["y", "n"],
                                    ["y", "n"],
                                )
                                if manual_rename
                                else "y"
                            )

                            if user_input == "y":
                                rename_file(
                                    file_path,
                                    rename_path,
                                )
                                if os.path.isfile(rename_path) and not os.path.isfile(file_path):
                                    if watchdog_toggle:
                                        if file_path in transferred_files:
                                            transferred_files.remove(file_path)
                                        if rename_path not in transferred_files:
                                            transferred_files.append(rename_path)
                            else:
                                print("\t\t\t\tSkipping...")
                except Exception as e:
                    send_message(f"Error when correcting extension: {entry}: {e}", error=True)

                    if 'temp_dir' in locals() and os.path.isdir(temp_dir):
                        remove_folder(temp_dir)

                    if 'repacked_file' in locals() and os.path.isfile(repacked_file):
                        remove_file(repacked_file)

# ... [rest of the code remains unchanged]
def delete_unacceptable_files():
    print("\nSearching for unacceptable files...")

    if not download_folders:
        print("\tNo download folders specified, skipping deleting unacceptable files...")
        return

    if not unacceptable_keywords:
        print("\tNo unacceptable keywords specified, skipping deleting unacceptable files...")
        return

    try:
        for path in download_folders:
            if not os.path.exists(path):
                print(f"\nERROR: {path} is an invalid path.\n")
                continue

            os.chdir(path)
            for root, dirs, files in os.walk(path):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                    skip_remove_unaccepted_file_types=True,
                    keep_images_in_just_these_files=True,
                )
                for file in files:
                    file_path = os.path.join(root, file)
                    if not os.path.isfile(file_path):
                        continue

                    extension = get_file_extension(file)
                    for keyword in unacceptable_keywords:
                        unacceptable_keyword_search = re.search(keyword, file, re.IGNORECASE)
                        if unacceptable_keyword_search:
                            send_message(
                                f"\tUnacceptable: {unacceptable_keyword_search.group()} match found in {file}\n\t\tDeleting file from: {root}",
                                discord=False,
                            )
                            embed = handle_fields(
                                DiscordEmbed(
                                    title="Unacceptable Match Found",
                                    color=yellow_color,
                                ),
                                fields=[
                                    {
                                        "name": "Found Regex/Keyword Match",
                                        "value": f"```{unacceptable_keyword_search.group()}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "In",
                                        "value": f"```{file}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "Location",
                                        "value": f"```{root}```",
                                        "inline": False,
                                    },
                                ],
                            )
                            grouped_notifications = group_notification(
                                grouped_notifications,
                                Embed(embed, None),
                            )
                            remove_file(file_path)
                            break
            for root, dirs, files in os.walk(path):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )
                for folder in dirs:
                    check_and_delete_empty_folder(os.path.join(root, folder))
    except Exception as e:
        send_message(str(e), error=True)

def delete_chapters_from_downloads():
    print("\nSearching for chapter files to delete...")

    if not download_folders:
        print("\tNo download folders specified, skipping deleting chapters...")

    try:
        for path in download_folders:
            if not os.path.exists(path):
                send_message(f"Download folder {path} does not exist, skipping...", error=True)
                continue

            os.chdir(path)
            for root, dirs, files in os.walk(path):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    chapters=True,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )

                for file in files:
                    if (contains_chapter_keywords(file) and not contains_volume_keywords(file)) and not (check_for_exception_keywords(file, exception_keywords)):
                        if get_file_extension(file) in manga_extensions:
                            send_message(
                                f"\n\t\tFile: {file}"
                                f"\n\t\tLocation: {root}"
                                f"\n\t\tContains chapter keywords/lone numbers and does not contain any volume/exclusion keywords"
                                f"\n\t\tDeleting chapter release.",
                                discord=False,
                            )
                            embed = handle_fields(
                                DiscordEmbed(
                                    title="Chapter Release Found",
                                    color=grey_color,
                                ),
                                fields=[
                                    {
                                        "name": "File",
                                        "value": f"```{file}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "Location",
                                        "value": f"```{root}```",
                                        "inline": False,
                                    },
                                    {
                                        "name": "Checks",
                                        "value": "```"
                                        + "Contains chapter keywords/lone numbers ✓\n"
                                        + "Does not contain any volume keywords ✓\n"
                                        + "Does not contain any exclusion keywords ✓"
                                        + "```",
                                        "inline": False,
                                    },
                                ],
                            )
                            grouped_notifications = group_notification(
                                grouped_notifications, Embed(embed, None)
                            )
                            remove_file(os.path.join(root, file))
            for root, dirs, files in os.walk(path):
                files, dirs = process_files_and_folders(
                    root,
                    files,
                    dirs,
                    just_these_files=transferred_files,
                    just_these_dirs=transferred_dirs,
                )
                for folder in dirs:
                    check_and_delete_empty_folder(os.path.join(root, folder))
    except Exception as e:
        send_message(str(e), error=True)

def rename_files(only_these_files=[], download_folders=download_folders, test_mode=False):
    global transferred_files, grouped_notifications

    print("\nSearching for files to rename...")

    if not download_folders:
        print("\tNo download folders specified, skipping renaming files...")
        return

    for path in download_folders:
        if not os.path.exists(path):
            send_message(f"\tDownload folder {path} does not exist, skipping...", error=True)
            continue

        for root, dirs, files in os.walk(path):
            if test_mode:
                if root not in download_folders:
                    return

                dirs = []
                files = only_these_files

            files, dirs = process_files_and_folders(
                root,
                files,
                dirs,
                just_these_files=transferred_files,
                just_these_dirs=transferred_dirs,
                test_mode=test_mode,
            )

            if not files:
                continue

            volumes = upgrade_to_volume_class(
                upgrade_to_file_class(
                    [f for f in files if os.path.isfile(os.path.join(root, f)) or test_mode],
                    root,
                    test_mode=test_mode,
                ),
                test_mode=test_mode,
            )

            if not volumes:
                continue

            print(f"\t{root}")
            for file in volumes:
                if "_extra" in file.name and ".5" in str(file.volume_number):
                    file.volume_number = int(file.volume_number)
                    file.index_number = int(file.index_number)
                if test_mode:
                    print(f"\t\t[{volumes.index(file) + 1}/{len(volumes)}] {file.name}")

                if file.file_type == "chapter" and not rename_chapters_with_preferred_chapter_keyword:
                    continue

                no_keyword = False
                preferred_naming_format = preferred_volume_renaming_format
                keywords = volume_regex_keywords
                zfill_int = zfill_volume_int_value
                zfill_float = zfill_volume_float_value

                if file.file_type == "chapter":
                    keywords = chapter_regex_keywords
                    preferred_naming_format = preferred_chapter_renaming_format
                    zfill_int = zfill_chapter_int_value
                    zfill_float = zfill_chapter_float_value

                if only_these_files and file.name not in only_these_files:
                    continue

                try:
                    file_extensions_with_prefix = "".join([f"巻?{re.escape(x)}|" for x in file_extensions])[:-1]

                    keyword_regex = (
                        r"(\s+)?\-?(\s+)?((%s)%s)(\.\s?|\s?|)([0-9]+)(([-_.])([0-9]+)|)+(x[0-9]+)?(#([0-9]+)(([-_.])([0-9]+)|)+)?(\]|\)|\})?(\s|%s)"
                        % (subtitle_exclusion_keywords_regex if file.subtitle else "", keywords, file_extensions_with_prefix)
                    )

                    result = re.search(keyword_regex, file.name, re.IGNORECASE)

                    full_chapter_match_attempt_allowed = False
                    regex_match_number = None

                    if result:
                        full_chapter_match_attempt_allowed = True
                    elif (
                        not result
                        and file.file_type == "chapter"
                        and (
                            (file.volume_number and (extract_all_numbers(file.name, subtitle=file.subtitle).count(file.volume_number) == 1))
                            or has_one_set_of_numbers(
                                remove_brackets(
                                    re.sub(
                                        r"((\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})\s?){2,}.*",
                                        "",
                                        re.sub(rf"^{re.escape(file.series_name)}", "", file.name, flags=re.IGNORECASE),
                                        flags=re.IGNORECASE,
                                    )
                                ),
                                chapter=True,
                                file=file,
                                subtitle=file.subtitle,
                            )
                        )
                    ):
                        full_chapter_match_attempt_allowed = True

                    if file.file_type == "chapter" and not result:
                        searches = chapter_searches if full_chapter_match_attempt_allowed else [chapter_searches[0]]

                        for regex in searches:
                            result = re.search(regex, remove_dual_space(file.name.replace("_extra", "")).strip(), re.IGNORECASE)

                            if result:
                                regex_match_number = searches.index(regex)
                                result = chapter_file_name_cleaning(result.group(), skip=True, regex_matched=regex_match_number)

                                if result:
                                    chapter_num_search = None
                                    converted_num = set_num_as_float_or_int(file.volume_number) if isinstance(file.volume_number, list) else file.volume_number

                                    if converted_num != "":
                                        if "-" in str(converted_num):
                                            split = converted_num.split("-")
                                            new_split = [f"(0+)?{s}" for s in split]
                                            if new_split:
                                                converted_num = "-".join(new_split)
                                                search = re.search(converted_num, file.name)
                                                if search:
                                                    chapter_num_search = search
                                        else:
                                            chapter_num_search = re.search(str(converted_num), file.name)

                                    if chapter_num_search:
                                        result = chapter_num_search.group()
                                    else:
                                        result = None

                                    if result:
                                        if re.search(r"(\d+_\d+)", result):
                                            result = result.replace("_", ".")

                                    if result:
                                        split = None

                                        if "-" in result:
                                            split = result.split("-")
                                            count = sum(1 for s in split if set_num_as_float_or_int(s) != "")
                                            if count != len(split):
                                                result = None
                                        elif set_num_as_float_or_int(result) == "":
                                            result = None
                                break

                    if result or (file.is_one_shot and add_volume_one_number_to_one_shots):
                        if file.is_one_shot:
                            result = f"{preferred_naming_format}{str(1).zfill(zfill_int)}"
                        elif not isinstance(result, str):
                            result = result.group().strip()

                        if result.startswith("-"):
                            result = result[1:]

                        result = re.sub(r"([\[\(\{\]\)\}]|((?<!\d+)_(?!\d+)))", "", result).strip()
                        keyword = re.search(r"(%s)" % keywords, result, re.IGNORECASE)

                        if keyword:
                            keyword = keyword.group()
                            result = re.sub(rf"(-)(\s+)?{keyword}", keyword, result, flags=re.IGNORECASE, count=1).strip()
                        elif file.file_type == "chapter" and result:
                            no_keyword = True
                        else:
                            continue

                        extensions_pattern = "|".join(re.escape(ext) for ext in file_extensions)
                        result = re.sub(extensions_pattern, "", result).strip()
                        results = re.split(r"(%s)(\.|)" % keywords, result, flags=re.IGNORECASE)
                        modified = []

                        for r in results[:]:
                            if r:
                                r = r.strip()

                            if r == "" or r == "." or r == None:
                                results.remove(r)
                            else:
                                found = re.search(r"([0-9]+)((([-_.])([0-9]+))+|)", r, re.IGNORECASE)
                                if found:
                                    r = found.group()
                                    if file.multi_volume:
                                        volume_numbers = get_min_and_max_numbers(r)
                                        for number in volume_numbers:
                                            modified.append(number)
                                            if number != volume_numbers[-1]:
                                                modified.append("-")
                                    else:
                                        try:
                                            if isint(r) and not re.search(r"(\.\d+$)", str(r)):
                                                r = int(r)
                                                modified.append(r)
                                            elif isfloat(r):
                                                r = float(r)
                                                modified.append(r)
                                        except ValueError as ve:
                                            send_message(str(ve), error=True)
                                if r and isinstance(r, str):
                                    if re.search(r"(%s)" % keywords, r, re.IGNORECASE):
                                        modified.append(re.sub(r"(%s)" % keywords, preferred_naming_format, r, flags=re.IGNORECASE))
                        if (((len(modified) == 2 and len(results) == 2)) or (len(modified) == 1 and len(results) == 1 and no_keyword)) or (file.multi_volume and (len(modified) == len(results) + len(volume_numbers))):
                            combined = ""

                            for item in modified:
                                if isinstance(item, (int, float)):
                                    if item < 10 or (file.file_type == "chapter" and item < 100):
                                        fill_type = zfill_int if isinstance(item, int) else zfill_float
                                        combined += str(item).zfill(fill_type)
                                    else:
                                        combined += str(item)
                                elif isinstance(item, str):
                                    combined += item

                            without_keyword = re.sub(r"(%s)(\.|)" % keywords, "", combined, flags=re.IGNORECASE)
                            if (file.extension in manga_extensions and add_issue_number_to_manga_file_name and file.file_type == "volume"):
                                combined += f" #{without_keyword}"

                            if not file.is_one_shot:
                                converted_value = re.sub(keywords, "", combined, flags=re.IGNORECASE)

                                if "-" not in converted_value:
                                    converted_value = set_num_as_float_or_int(converted_value, silent=True)
                                else:
                                    converted_value = ""

                                converted_and_filled = None

                                if converted_value != "":
                                    if isinstance(converted_value, (int, float)):
                                        if converted_value < 10 or (file.file_type == "chapter" and converted_value < 100):
                                            if isinstance(converted_value, int):
                                                converted_and_filled = str(converted_value).zfill(zfill_int)
                                            elif isinstance(converted_value, float):
                                                converted_and_filled = str(converted_value).zfill(zfill_float)
                                        elif converted_value >= 100:
                                            converted_and_filled = converted_value

                                if not no_keyword:
                                    replacement = re.sub(
                                        r"((?<![A-Za-z]+)|)(\[|\(|\{)?(?<![A-Za-z])(%s)(\.|)([-_. ]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s#(([0-9]+)((([-_.]|)([0-9]+))+|)))?(\]|\)|\})?"
                                        % keywords,
                                        combined,
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )
                                elif (converted_value == file.volume_number and converted_and_filled):
                                    optional_following_zero = rf"\b({str(exclusion_keywords_regex)})(0+)?{str(converted_value)}(\b|(?=x|#))"

                                    if (file.file_type == "chapter" and regex_match_number == 0):
                                        optional_following_zero = rf"(#)?{optional_following_zero}"

                                    without_series_name = re.sub(
                                        rf"^{re.escape(file.series_name)}",
                                        "",
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )

                                    without_end_brackets = re.sub(
                                        r"((\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})\s?){2,}.*",
                                        "",
                                        without_series_name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )

                                    without_brackets_replacement = re.sub(
                                        optional_following_zero,
                                        f" {preferred_naming_format}{converted_and_filled}",
                                        remove_dual_space(
                                            without_end_brackets.replace("_extra", ".5")
                                        ),
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )

                                    without_series_name_replacement = re.sub(
                                        re.escape(without_end_brackets),
                                        without_brackets_replacement,
                                        without_series_name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )

                                    replacement = re.sub(
                                        re.escape(without_series_name),
                                        without_series_name_replacement,
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )
                                    replacement = remove_dual_space(replacement).strip()
                                else:
                                    replacement = re.sub(
                                        r"((?<![A-Za-z]+)|)(\[|\(|\{)?(?<![A-Za-z])(%s)(\.|)([-_. ]|)(([0-9]+)((([-_.]|)([0-9]+))+|))(\s#(([0-9]+)((([-_.]|)([0-9]+))+|)))?(\]|\)|\})?"
                                        % "",
                                        f" {preferred_naming_format}{combined}",
                                        file.name,
                                        flags=re.IGNORECASE,
                                        count=1,
                                    )
                                    replacement = remove_dual_space(replacement)
                            else:
                                base = re.sub(
                                    r"(%s)" % file_extensions_regex,
                                    "",
                                    file.basename,
                                    flags=re.IGNORECASE,
                                ).strip()

                                replacement = f"{base} {combined}"

                                if file.volume_year:
                                    replacement += f" ({file.volume_year})"

                                extras = (
                                    get_extras(
                                        file.name,
                                        series_name=file.series_name,
                                        subtitle=file.subtitle,
                                    )
                                    if file.file_type != "chapter"
                                    else get_extras(
                                        file.name,
                                        chapter=True,
                                        series_name=file.series_name,
                                        subtitle=file.subtitle,
                                    )
                                )

                                replacement += " ".join([""] + extras)

                                replacement += file.extension

                            replacement = replacement.replace("?", "").strip()

                            replacement = remove_dual_space(
                                replacement.replace("_", " ")
                            ).strip()

                            replacement = re.sub(
                                r"([A-Za-z])(\:|：)", r"\1 -", replacement
                            )

                            replacement = remove_dual_space(replacement)
                            processed_files.append(replacement)

                            if file.name != replacement:
                                if test_mode:
                                    write_to_file(
                                        "test_renamed_files.txt",
                                        f"{file.name} -> {replacement}",
                                        without_timestamp=True,
                                    )
                                    continue

                                if watchdog_toggle:
                                    transferred_files.append(
                                        os.path.join(file.root, replacement)
                                    )
                                try:
                                    if not (
                                        os.path.isfile(os.path.join(root, replacement))
                                    ):
                                        send_message(
                                            f"\n\t\tBEFORE: {file.name}",
                                            discord=False,
                                        )
                                        send_message(
                                            f"\t\tAFTER:  {replacement}",
                                            discord=False,
                                        )

                                        user_input = user_input = (
                                            get_input_from_user(
                                                "\t\tRename", ["y", "n"], ["y", "n"]
                                            )
                                            if manual_rename
                                            else "y"
                                        )

                                        if user_input == "y":
                                            try:
                                                rename_file(
                                                    file.path,
                                                    os.path.join(root, replacement),
                                                    silent=True,
                                                )
                                                if file.path in transferred_files:
                                                    transferred_files.remove(file.path)

                                            except OSError as e:
                                                send_message(
                                                    f"{e}\nError renaming file: {file.name} to {replacement}",
                                                    error=True,
                                                )
                                            if os.path.isfile(
                                                os.path.join(root, replacement)
                                            ):
                                                send_message(
                                                    "\t\t\tSuccessfully renamed file.",
                                                    discord=False,
                                                )
                                                if (
                                                    not mute_discord_rename_notifications
                                                ):
                                                    embed = handle_fields(
                                                        DiscordEmbed(
                                                            title="Renamed File",
                                                            color=grey_color,
                                                        ),
                                                        fields=[
                                                            {
                                                                "name": "From",
                                                                "value": f"```{file.name}```",
                                                                "inline": False,
                                                            },
                                                            {
                                                                "name": "To",
                                                                "value": f"```{replacement}```",
                                                                "inline": False,
                                                            },
                                                        ],
                                                    )
                                                    grouped_notifications = group_notification(
                                                        grouped_notifications,
                                                        Embed(embed, None),
                                                    )
                                                volume_index = volumes.index(file)
                                                file = upgrade_to_volume_class(
                                                    upgrade_to_file_class(
                                                        [replacement], file.root
                                                    )
                                                )[0]
                                                volumes[volume_index] = file
                                            else:
                                                send_message(
                                                    f"\n\tRename failed on: {file.name}",
                                                    error=True,
                                                )
                                        else:
                                            send_message(
                                                "\t\t\tSkipping...\n", discord=False
                                            )
                                    else:
                                        send_message(
                                            f"\n\tFile already exists: {os.path.join(root, replacement)}"
                                            f"\n\t\twhen renaming: {file.name}"
                                            f"\n\tDeleting: {file.name}",
                                            discord=False,
                                        )
                                        remove_file(file.path, silent=True)
                                        continue
                                except OSError as ose:
                                    send_message(str(ose), error=True)
                            else:
                                if test_mode:
                                    write_to_file(
                                        "test_renamed_files.txt",
                                        f"{file.name} -> {replacement}",
                                        without_timestamp=True,
                                        check_for_dup=True,
                                    )
                                    continue
                        else:
                            send_message(
                                f"More than two for either array: {file.name}",
                                error=True,
                            )
                            print("Modified Array:")
                            for i in modified:
                                print(f"\t{i}")

                            print("Results Array:")
                            for b in results:
                                print(f"\t{b}")

                except Exception as e:
                    send_message(f"\nERROR: {e} ({file.name})", error=True)
                if resturcture_when_renaming and not test_mode:
                    reorganize_and_rename([file], file.series_name)

# ... [rest of the code remains unchanged]
