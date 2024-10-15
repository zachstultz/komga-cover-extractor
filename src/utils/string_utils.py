import re
from difflib import SequenceMatcher
from unidecode import unidecode
from src.config import *

def clean_str(string, skip_lowercase_convert=False, skip_colon_replace=False, skip_bracket=False, skip_unidecode=False, skip_normalize=False, skip_punctuation=False, skip_remove_s=False, skip_convert_to_ascii=False, skip_underscore=False):
    # Convert to lower and strip
    s = string.lower().strip() if not skip_lowercase_convert else string

    # replace : with space
    s = s.replace(":", " ") if not skip_colon_replace and ":" in s else s

    # remove uneccessary spacing
    s = remove_dual_space(s)

    # Remove bracketed info
    s = remove_brackets(s) if not skip_bracket and contains_brackets(s) else s

    # Remove unicode
    s = unidecode(s) if not skip_unidecode and contains_unicode(s) else s

    # normalize the string
    s = normalize_str(s) if not skip_normalize else s

    # Remove punctuation
    s = remove_punctuation(s) if not skip_punctuation and contains_punctuation(s) else s

    # remove trailing s
    s = remove_s(s) if not skip_remove_s else s

    # remove dual spaces
    s = remove_dual_space(s)

    # convert to ascii
    s = convert_to_ascii(s) if not skip_convert_to_ascii else s

    # Replace underscores with periods
    s = replace_underscores(s) if not skip_underscore and "_" in s else s

    return s.strip()

def similar(a, b):
    # convert to lowercase and strip
    a = a.lower().strip()
    b = b.lower().strip()

    # evaluate
    if a == "" or b == "":
        return 0.0
    elif a == b:
        return 1.0
    else:
        return SequenceMatcher(None, a, b).ratio()

def remove_brackets(string):
    # Avoid a string that is only a bracket
    # Probably a series name
    # EX: [(OSHI NO KO)]
    if (
        starts_with_bracket(string)
        and ends_with_bracket(string)
        and bracket_avoidance_pattern.search(string)
    ):
        return string

    # Remove all grouped brackets as long as they aren't surrounded by dashes,
    # letters, or square brackets.
    # Regex 1: ([\[\{\(]((\d{4}))[\]\}\)]) - FOR YEAR
    # Regex 2: (((?<!-|[A-Za-z]\s|\[)(\[[^\]]*\]|\([^\)]*\)|\{[^}]*\})(?!-|\s*[A-Za-z]|\]))(\s+)?)+ - FOR EVERYTHING ELSE
    string = bracket_removal_pattern.sub("", string).strip()

    # Get file extension
    ext = get_file_extension(string)

    if ext:
        # Remove ending bracket against the extension
        # EX: test (digital).cbz -> test .cbz
        string = (
            bracket_against_extension_pattern.sub(r"\2", string).strip()
            if contains_brackets(string)
            else string
        )

        # Remove the extension
        # EX: test.cbz -> test
        string = string.replace(ext, "").strip()

        # Re-add the extension
        # EX: test -> test.cbz
        string = f"{string}{ext}"

    # Return the modified string
    return string

def remove_dual_space(s):
    if "  " not in s:
        return s

    return dual_space_pattern.sub(" ", s)

def normalize_str(s, skip_common_words=False, skip_editions=False, skip_type_keywords=False, skip_japanese_particles=False, skip_misc_words=False, skip_storefront_keywords=False):
    if len(s) <= 1:
        return s

    words_to_remove = []

    if not skip_common_words:
        common_words = ["the", "a", "à", "and", "&", "I", "of",]
        words_to_remove.extend(common_words)

    if not skip_editions:
        editions = ["Collection", "Master Edition", "(2|3|4|5)-in-1 Edition", "Edition", "Exclusive", "Anniversary", "Deluxe", "Digital", "Official", "Anthology", "Limited", "Complete", "Collector", "Ultimate", "Special",]
        words_to_remove.extend(editions)

    if not skip_type_keywords:
        # (?<!^) = Cannot start with this word.
        # EX: "Book Girl" light novel series.
        type_keywords = ["(?<!^)Novel", "(?<!^)Light Novel", "(?<!^)Manga", "(?<!^)Comic", "(?<!^)LN", "(?<!^)Series", "(?<!^)Volume", "(?<!^)Chapter", "(?<!^)Book", "(?<!^)MANHUA",]
        words_to_remove.extend(type_keywords)

    if not skip_japanese_particles:
        japanese_particles = ["wa", "o", "mo", "ni", "e", "de", "ga", "kara", "to", "ya", "no(?!\.)", "ne", "yo",]
        words_to_remove.extend(japanese_particles)

    if not skip_misc_words:
        misc_words = ["((\d+)([-_. ]+)?th)", "x", "×", "HD"]
        words_to_remove.extend(misc_words)

    if not skip_storefront_keywords:
        storefront_keywords = ["Book(\s+)?walker",]
        words_to_remove.extend(storefront_keywords)

    for word in words_to_remove:
        pattern = rf"\b{word}\b" if word not in type_keywords else rf"{word}\s"
        s = re.sub(pattern, " ", s, flags=re.IGNORECASE).strip()

        s = remove_dual_space(s)

    return s.strip()

def get_shortened_title(title):
    shortened_title = ""
    if ("-" in title or ":" in title) and re.search(r"((\s+(-)|:)\s+)", title):
        shortened_title = re.sub(r"((\s+(-)|:)\s+.*)", "", title).strip()
    return shortened_title

def generate_rename_lists():
    global release_groups, publishers, skipped_release_group_files, skipped_publisher_files

    skipped_files = []
    log_file_name = None
    skipped_file_name = None
    text_prompt = None

    print("\nGenerating rename lists, with assistance of user.")
    mode = get_input_from_user(
        "\tEnter Mode",
        ["1", "2", "3"],
        "1 = Release Group, 2 = Publisher, 3 = Exit",
        use_timeout=True,
    )

    if mode == "1":
        mode = "r"
        log_file_name = "release_groups.txt"
        skipped_file_name = "skipped_release_group_files.txt"
        text_prompt = "release group"
        if skipped_release_group_files:
            skipped_files = skipped_release_group_files
    elif mode == "2":
        mode = "p"
        log_file_name = "publishers.txt"
        skipped_file_name = "skipped_publisher_files.txt"
        text_prompt = "publisher"
        if skipped_publisher_files:
            skipped_files = skipped_publisher_files
    else:
        print("\nExiting...")
        return

    if not paths:
        send_message(
            "No paths are set in settings.py. Please set them and try again.",
            error=True,
        )
        return

    for path in paths:
        if not os.path.exists(path):
            send_message(f"Path does not exist: {path}", error=True)
            continue

        if mode == "p" and paths_with_types:
            is_in_path_with_types = [
                x.path
                for x in paths_with_types
                if x.path == path and "chapter" in x.path_formats
            ]
            if is_in_path_with_types:
                continue
        try:
            skipped_file_volumes = []
            for root, dirs, files in os.walk(path):
                files, dirs = clean_and_sort(root, files, dirs, sort=True)

                if not files:
                    continue

                volumes = upgrade_to_volume_class(
                    upgrade_to_file_class(
                        [f for f in files if os.path.isfile(os.path.join(root, f))],
                        root,
                    )
                )
                for file in volumes:
                    if mode == "p" and file.file_type == "chapter":
                        continue

                    print(f"\n\tChecking: {file.name}")
                    found = False

                    if file.name not in skipped_files:
                        if skipped_files and not skipped_file_volumes:
                            skipped_file_volumes = upgrade_to_volume_class(
                                upgrade_to_file_class(
                                    [f for f in skipped_files],
                                    root,
                                    clean=True,
                                )
                            )
                        if skipped_file_volumes:
                            for skipped_file in skipped_file_volumes:
                                if skipped_file.extras:
                                    # sort alphabetically
                                    skipped_file.extras.sort()
                                    # remove any year from the extras
                                    skipped_file.extras = [
                                        extra
                                        for extra in skipped_file.extras
                                        if not re.search(
                                            r"([\[\(\{]\d{4}[\]\)\}])",
                                            extra,
                                            re.IGNORECASE,
                                        )
                                    ]

                                if file.extras:
                                    # sort alphabetically
                                    file.extras.sort()
                                    # remove any year from the extras
                                    file.extras = [
                                        extra
                                        for extra in file.extras
                                        if not re.search(
                                            r"([\[\(\{]\d{4}[\]\)\}])",
                                            extra,
                                            re.IGNORECASE,
                                        )
                                    ]

                                if (
                                    file.extras == skipped_file.extras
                                    and file.extension == skipped_file.extension
                                ):
                                    print(
                                        f"\t\tSkipping: {file.name} because it has the same extras and extension as: {skipped_file.name} (in {skipped_file_name})"
                                    )
                                    found = True
                                    write_to_file(
                                        skipped_file_name,
                                        file.name,
                                        without_timestamp=True,
                                        check_for_dup=True,
                                    )
                                    if file.name not in skipped_files:
                                        skipped_files.append(file.name)
                                        skipped_file_volume = upgrade_to_volume_class(
                                            upgrade_to_file_class([file.name], root)
                                        )
                                        if (
                                            skipped_file_volume
                                            and skipped_file_volume
                                            not in skipped_file_volumes
                                        ):
                                            skipped_file_volumes.append(
                                                skipped_file_volume[0]
                                            )
                                    break

                        left_brackets = r"(\(|\[|\{)"
                        right_brackets = r"(\)|\]|\})"
                        groups_to_use = release_groups if mode == "r" else publishers

                        if groups_to_use and not found:
                            found = next(
                                (
                                    group
                                    for group in groups_to_use
                                    if re.search(
                                        rf"{left_brackets}{re.escape(group)}{right_brackets}",
                                        file.name,
                                        re.IGNORECASE,
                                    )
                                ),
                                None,
                            )
                            if found:
                                print(f'\t\tFound: "{found}", skipping file.')

                        if not found:
                            # ask the user what the release group or publisher is, then write it to the file, add it to the list, and continue. IF the user inputs "none" then skip it.
                            # loop until the user inputs a valid response
                            while True:
                                print(
                                    f"\t\tCould not find a {text_prompt} for: \n\t\t\t{file.name}"
                                )
                                group = input(
                                    f'\n\t\tPlease enter the {text_prompt} ("none" to add to {skipped_file_name}, "skip" to skip): '
                                )
                                if group == "none":
                                    print(
                                        f"\t\t\tAdding to {skipped_file_name} and skipping in the future..."
                                    )
                                    write_to_file(
                                        skipped_file_name,
                                        file.name,
                                        without_timestamp=True,
                                        check_for_dup=True,
                                    )
                                    if file.name not in skipped_files:
                                        skipped_files.append(file.name)
                                        skipped_file_vol = upgrade_to_volume_class(
                                            upgrade_to_file_class([file.name], root)
                                        )
                                        if (
                                            skipped_file_vol
                                            and skipped_file_vol
                                            not in skipped_file_volumes
                                        ):
                                            skipped_file_volumes.append(
                                                skipped_file_vol[0]
                                            )
                                    break
                                elif group == "skip":
                                    print("\t\t\tSkipping...")
                                    break
                                elif group:
                                    # print back what the user entered
                                    print(f"\t\t\tYou entered: {group}")
                                    write_to_file(
                                        log_file_name,
                                        group,
                                        without_timestamp=True,
                                        check_for_dup=True,
                                    )
                                    if mode == "r":
                                        if group not in release_groups:
                                            release_groups.append(group)
                                    elif mode == "p":
                                        if group not in publishers:
                                            publishers.append(group)
                                    break
                                else:
                                    print("\t\t\tInvalid input.")
                    else:
                        print(f"\t\tSkipping... File is in {skipped_file_name}")
        except Exception as e:
            send_message(str(e), error=True)

    # Reassign the global arrays if anything new new got added to the local one.
    if skipped_files:
        if (
            mode == "r"
            and skipped_files
            and skipped_files != skipped_release_group_files
        ):
            skipped_release_group_files = skipped_files
        elif mode == "p" and skipped_files and skipped_files != skipped_publisher_files:
            skipped_publisher_files = skipped_files

# Add other string utility functions here
