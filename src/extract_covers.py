import os
import re
import zipfile
import cv2
import numpy as np
from src.config import *
from src.models.folder import Folder
from src.utils.file_utils import get_file_extension, remove_file, get_file_size, get_file_hash
from src.utils.image_utils import compress_image, prep_images_for_similarity
from src.utils.string_utils import clean_str, similar, get_shortened_title

def extract_covers(paths_to_process=paths):
    global checked_series, root_modification_times, series_cover_path, image_count

    print("\nLooking for covers to extract...")

    if not paths_to_process:
        print("\nNo paths to process.")
        return

    for path in paths_to_process:
        if not os.path.exists(path):
            print(f"\nERROR: {path} is an invalid path.\n")
            continue

        checked_series = []
        os.chdir(path)

        for root, dirs, files in os.walk(path):
            if watchdog_toggle:
                root_mod_time = os.path.getmtime(root)
                if root in root_modification_times:
                    if root_modification_times[root] == root_mod_time:
                        continue
                    else:
                        root_modification_times[root] = root_mod_time
                else:
                    root_modification_times[root] = root_mod_time

            files, dirs = process_files_and_folders(
                root,
                files,
                dirs,
                just_these_files=transferred_files,
                just_these_dirs=transferred_dirs,
            )

            contains_subfolders = dirs

            print(f"\nRoot: {root}")
            print(f"Files: {files}")

            if not files:
                continue

            file_objects = upgrade_to_file_class(files, root)
            volume_objects = upgrade_to_volume_class(
                file_objects,
                skip_release_year=True,
                skip_release_group=True,
                skip_extras=True,
                skip_publisher=True,
                skip_premium_content=True,
                skip_subtitle=True,
                skip_multi_volume=True,
            )

            folder_accessor = create_folder_obj(root, dirs, volume_objects)

            series_cover_path = find_series_cover(folder_accessor, image_extensions)
            series_cover_extension = get_file_extension(series_cover_path) if series_cover_path else ""

            if series_cover_extension and (
                (output_covers_as_webp and series_cover_extension != ".webp")
                or (not output_covers_as_webp and series_cover_extension == ".webp")
            ):
                remove_status = remove_file(series_cover_path, silent=True)
                if remove_status:
                    series_cover_path = ""

            is_chapter_directory = folder_accessor.files[0].file_type == "chapter"
            same_series_name = check_same_series_name(folder_accessor.files)

            highest_index_number = get_highest_release(
                tuple(
                    [
                        (
                            item.index_number
                            if not isinstance(item.index_number, list)
                            else tuple(item.index_number)
                        )
                        for item in folder_accessor.files
                    ]
                ),
                is_chapter_directory=is_chapter_directory,
            ) if not is_chapter_directory else ""

            if highest_index_number:
                print(f"\n\t\tHighest Index Number: {highest_index_number}")

            has_multiple_volume_ones = contains_multiple_volume_ones(
                folder_accessor.files,
                use_latest_volume_cover_as_series_cover,
                is_chapter_directory,
            )

            for file in folder_accessor.files:
                if file.file_type == "volume" or (file.file_type == "chapter" and extract_chapter_covers):
                    process_cover_extraction(
                        file,
                        has_multiple_volume_ones,
                        highest_index_number,
                        is_chapter_directory,
                        same_series_name,
                        contains_subfolders,
                    )

def find_and_extract_cover(file, return_data_only=False, silent=False, blank_image_check=compare_detected_cover_to_blank_images):
    if not os.path.isfile(file.path):
        send_message(f"\nFile: {file.path} does not exist.", error=True)
        return None

    if not zipfile.is_zipfile(file.path):
        send_message(f"\nFile: {file.path} is not a valid zip file.", error=True)
        return None

    novel_cover_path = get_novel_cover_path(file) if file.extension in novel_extensions else ""

    with zipfile.ZipFile(file.path, "r") as zip_ref:
        zip_list = filter_and_sort_files(zip_ref.namelist())

        if novel_cover_path:
            novel_cover_basename = os.path.basename(novel_cover_path)
            for i, item in enumerate(zip_list):
                if os.path.basename(item) == novel_cover_basename:
                    zip_list.pop(i)
                    zip_list.insert(0, item)
                    break

        blank_images = set()

        for image_file in zip_list:
            image_basename = os.path.basename(image_file)
            is_novel_cover = novel_cover_path and image_basename == novel_cover_path

            if is_novel_cover or any(pattern.search(image_basename) for pattern in compiled_cover_patterns):
                if blank_image_check and blank_white_image_path and blank_black_image_path:
                    image_data = get_image_data(zip_ref, image_file)
                    if is_blank_image(image_data):
                        blank_images.add(image_file)
                        continue

                image_data = get_image_data(zip_ref, image_file)
                result = process_cover_image(image_file, image_data, file, return_data_only)
                if result:
                    return result

        default_cover_path = find_non_blank_default_cover(zip_list, blank_images, zip_ref, blank_image_check)

        if default_cover_path:
            image_data = get_image_data(zip_ref, default_cover_path)
            result = process_cover_image(default_cover_path, image_data, file, return_data_only)
            if result:
                return result

    return False

def find_series_cover(folder_accessor, image_extensions):
    return next(
        (
            os.path.join(folder_accessor.root, f"cover{ext}")
            for ext in image_extensions
            if os.path.exists(os.path.join(folder_accessor.root, f"cover{ext}"))
        ),
        None,
    )

def check_same_series_name(files, required_percent=0.9):
    if not files:
        return False

    compare_series = clean_str(files[0].series_name, skip_bracket=True)
    file_count = len(files)
    required_count = int(file_count * required_percent)
    return sum(
        clean_str(x.series_name, skip_bracket=True) == compare_series
        for x in files
    ) >= required_count

def contains_multiple_volume_ones(files, use_latest_volume_cover_as_series_cover, is_chapter_directory):
    if not use_latest_volume_cover_as_series_cover or is_chapter_directory:
        volume_ones = sum(
            1
            for file in files
            if not file.is_one_shot
            and not file.volume_part
            and (
                file.index_number == 1
                or (isinstance(file.index_number, list) and 1 in file.index_number)
            )
        )
        return volume_ones > 1
    return False

def process_cover_extraction(file, has_multiple_volume_ones, highest_index_number, is_chapter_directory, same_series_name, contains_subfolders):
    global image_count, series_cover_path

    update_stats(file)

    has_cover = False
    printed = False

    cover = next(
        (
            f"{file.extensionless_path}{extension}"
            for extension in image_extensions
            if os.path.exists(f"{file.extensionless_path}{extension}")
        ),
        "",
    )

    cover_extension = get_file_extension(cover) if cover else ""

    if cover_extension and (
        (output_covers_as_webp and cover_extension != ".webp")
        or (not output_covers_as_webp and cover_extension == ".webp")
    ):
        remove_status = remove_file(cover, silent=True)
        if remove_status:
            cover = ""

    if cover:
        has_cover = True
        image_count += 1
    else:
        if not printed:
            print(f"\n\tFile: {file.name}")
            printed = True

        print("\t\tFile does not have a cover.")
        result = find_and_extract_cover(file)

        if result:
            if result.endswith(".webp") and not output_covers_as_webp:
                print("\t\tCover is a .webp file. Converting to .jpg...")
                conversion_result = convert_webp_to_jpg(result)

                if conversion_result:
                    print("\t\tCover successfully converted to .jpg")
                    result = conversion_result
                else:
                    print("\t\tCover conversion failed.")
                    print("\t\tCleaning up webp file...")
                    remove_file(result, silent=True)

                    if not os.path.isfile(result):
                        print("\t\tWebp file successfully deleted.")
                    else:
                        print("\t\tWebp file could not be deleted.")

                    result = None
            else:
                print("\t\tCover successfully extracted.\n")
                has_cover = True
                cover = result
                image_count += 1
        else:
            print("\t\tCover not found.")

    if (
        file.file_type == "volume"
        and not is_chapter_directory
        and cover
        and series_cover_path
        and not has_multiple_volume_ones
        and (
            (
                use_latest_volume_cover_as_series_cover
                and is_same_index_number(
                    file.index_number, highest_index_number, allow_array_match=True
                )
            )
            or (
                not use_latest_volume_cover_as_series_cover
                and (
                    file.index_number == 1
                    or (
                        isinstance(file.index_number, list)
                        and 1 in file.index_number
                    )
                )
            )
        )
    ):
        update_series_cover(cover, series_cover_path)

    if (
        not has_multiple_volume_ones
        and not contains_subfolders
        and not series_cover_path
        and file.root not in download_folders
        and has_cover
        and cover
        and (
            (
                file.index_number == 1
                and (
                    not use_latest_volume_cover_as_series_cover
                    or is_chapter_directory
                )
            )
            or (
                file.file_type == "volume"
                and not is_chapter_directory
                and use_latest_volume_cover_as_series_cover
                and is_same_index_number(
                    file.index_number, highest_index_number, allow_array_match=True
                )
            )
        )
        and same_series_name
    ):
        create_series_cover(file, cover)

def update_series_cover(cover, series_cover_path):
    current_series_cover_modification_date = os.path.getmtime(series_cover_path)
    latest_volume_cover_modification_date = os.path.getmtime(cover)

    if current_series_cover_modification_date != latest_volume_cover_modification_date:
        if get_file_hash(series_cover_path) != get_file_hash(cover):
            print("\t\tCurrent series cover does not match the appropriate volume cover.")
            print("\t\tRemoving current series cover...")
            remove_file(series_cover_path, silent=True)

            if not os.path.isfile(series_cover_path):
                print("\t\tSeries cover successfully removed.\n")
                series_cover_path = None
            else:
                print("\t\tSeries cover could not be removed.\n")
        else:
            os.utime(series_cover_path, (os.path.getatime(series_cover_path), latest_volume_cover_modification_date))

def create_series_cover(file, cover):
    if not os.path.isfile(cover):
        print(f"\t\tCover does not exist at: {cover}")
        return

    print("\t\tMissing series cover.")
    print("\t\tFound volume for series cover.")

    cover_extension = get_file_extension(os.path.basename(cover))
    cover_path = os.path.join(file.root, os.path.basename(cover))
    series_cover_path = os.path.join(file.root, f"cover{cover_extension}")

    shutil.copy(cover_path, series_cover_path)
    print("\t\tCopied cover as series cover.")
    os.utime(series_cover_path, (os.path.getatime(cover_path), os.path.getmtime(cover_path)))

def filter_and_sort_files(zip_list):
    return sorted(
        [
            x
            for x in zip_list
            if not x.endswith("/")
            and "." in x
            and get_file_extension(x) in image_extensions
            and not os.path.basename(x).startswith((".", "__"))
        ]
    )

def get_image_data(zip_ref, image_path):
    with zip_ref.open(image_path) as image_file_ref:
        return image_file_ref.read()

def is_blank_image(image_data):
    ssim_score_white = prep_images_for_similarity(blank_white_image_path, image_data, silent=True)
    ssim_score_black = prep_images_for_similarity(blank_black_image_path, image_data, silent=True)

    return (
        ssim_score_white is not None
        and ssim_score_black is not None
        and (
            ssim_score_white >= blank_cover_required_similarity_score
            or ssim_score_black >= blank_cover_required_similarity_score
        )
    )

def process_cover_image(cover_path, image_data, file, return_data_only):
    image_extension = get_file_extension(os.path.basename(cover_path))
    if image_extension == ".jpeg":
        image_extension = ".jpg"

    if output_covers_as_webp and image_extension != ".webp":
        image_extension = ".webp"

    output_path = os.path.join(file.root, file.extensionless_name + image_extension)

    if not return_data_only:
        with open(output_path, "wb") as image_file_ref_out:
            image_file_ref_out.write(image_data)
        if compress_image_option:
            result = compress_image(output_path, image_quality)
            return result if result else output_path
        return output_path
    elif image_data:
        compressed_data = compress_image(output_path, raw_data=image_data)
        return compressed_data if compressed_data else image_data
    return None

def find_non_blank_default_cover(zip_list, blank_images, zip_ref, blank_image_check):
    for test_file in zip_list:
        if test_file in blank_images:
            continue

        image_data = get_image_data(zip_ref, test_file)

        if blank_image_check:
            if not is_blank_image(image_data):
                return test_file
        else:
            return test_file

    return None

def get_novel_cover_path(file):
    if file.extension not in novel_extensions:
        return ""

    novel_cover_path = get_novel_cover(file.path)
    if not novel_cover_path:
        return ""

    if get_file_extension(novel_cover_path) not in image_extensions:
        return ""

    return os.path.basename(novel_cover_path)

# Add any additional helper functions here if needed
