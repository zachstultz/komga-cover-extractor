"""Characterization tests for directory-scanning helpers.

Functions covered:
  - get_all_folders_recursively_in_dir
  - get_all_files_in_directory
  - cache_existing_library_paths
  - clean_and_sort

All tests pin CURRENT behaviour including surprising / buggy aspects flagged
with ``# FLAG:`` comments. Nothing is "fixed" here — see CLAUDE.md rationale.
"""

from __future__ import annotations

import os

import pytest

import komga_cover_extractor as kce


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _isolate(monkeypatch):
    """Pin the three globals that affect scanning behaviour."""
    monkeypatch.setattr(kce, "paths", [])
    monkeypatch.setattr(kce, "download_folders", [])
    monkeypatch.setattr(kce, "cached_paths", [])
    monkeypatch.setattr(kce, "log_to_file", False)


# =========================================================================== #
# get_all_folders_recursively_in_dir
# =========================================================================== #

class TestGetAllFoldersRecursively:
    """Pin structure and content of get_all_folders_recursively_in_dir."""

    def test_returns_list_of_dicts(self, tmp_path, monkeypatch):
        """Return value is a plain list of dicts."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        root.mkdir()
        result = kce.get_all_folders_recursively_in_dir(str(root))
        assert isinstance(result, list)
        assert all(isinstance(item, dict) for item in result)

    def test_dict_keys(self, tmp_path, monkeypatch):
        """Each dict has exactly the keys 'root', 'dirs', 'files'."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        root.mkdir()
        result = kce.get_all_folders_recursively_in_dir(str(root))
        assert len(result) >= 1
        for item in result:
            assert set(item.keys()) == {"root", "dirs", "files"}

    def test_empty_directory_one_entry(self, tmp_path, monkeypatch):
        """A single empty directory yields exactly one entry."""
        _isolate(monkeypatch)
        root = tmp_path / "empty"
        root.mkdir()
        result = kce.get_all_folders_recursively_in_dir(str(root))
        assert len(result) == 1
        assert result[0]["root"] == str(root)
        assert result[0]["dirs"] == []
        assert result[0]["files"] == []

    def test_tree_with_one_subdir_yields_two_entries(self, tmp_path, monkeypatch):
        """root + 1 subdir yields 2 walk entries."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        sub = root / "Test Series"
        sub.mkdir(parents=True)
        (sub / "v01.cbz").write_bytes(b"")

        result = kce.get_all_folders_recursively_in_dir(str(root))
        roots = [item["root"] for item in result]
        assert len(result) == 2
        assert str(root) in roots
        assert str(sub) in roots

    def test_root_entry_lists_subdirs(self, tmp_path, monkeypatch):
        """The root-level entry's 'dirs' list contains the subdir name."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        sub = root / "Series A"
        sub.mkdir(parents=True)

        result = kce.get_all_folders_recursively_in_dir(str(root))
        root_entry = next(e for e in result if e["root"] == str(root))
        assert "Series A" in root_entry["dirs"]

    def test_files_in_subdir_entry(self, tmp_path, monkeypatch):
        """Files under a subdir appear in that entry's 'files' list."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        sub = root / "Series A"
        sub.mkdir(parents=True)
        (sub / "Series A v01.cbz").write_bytes(b"")
        (sub / "Series A v02.cbz").write_bytes(b"")

        result = kce.get_all_folders_recursively_in_dir(str(root))
        sub_entry = next(e for e in result if e["root"] == str(sub))
        assert set(sub_entry["files"]) == {"Series A v01.cbz", "Series A v02.cbz"}

    def test_no_extension_filtering_done_here(self, tmp_path, monkeypatch):
        """get_all_folders_recursively_in_dir does NOT filter by extension."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        sub = root / "Series"
        sub.mkdir(parents=True)
        (sub / "a.cbz").write_bytes(b"")
        (sub / ".hidden.cbz").write_bytes(b"")
        (sub / "readme.txt").write_bytes(b"")

        result = kce.get_all_folders_recursively_in_dir(str(root))
        sub_entry = next(e for e in result if e["root"] == str(sub))
        # All files are present — no hidden or extension filtering
        assert ".hidden.cbz" in sub_entry["files"]
        assert "readme.txt" in sub_entry["files"]

    def test_root_in_paths_is_skipped(self, tmp_path, monkeypatch):
        """A walk entry whose 'root' is in kce.paths is skipped."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        sub1 = root / "Series A"
        sub2 = root / "Series B"
        sub1.mkdir(parents=True)
        sub2.mkdir(parents=True)

        monkeypatch.setattr(kce, "paths", [str(sub1)])
        result = kce.get_all_folders_recursively_in_dir(str(root))
        returned_roots = {e["root"] for e in result}
        # sub1 is in kce.paths → skipped
        assert str(sub1) not in returned_roots
        # root and sub2 are returned
        assert str(root) in returned_roots
        assert str(sub2) in returned_roots

    def test_root_in_download_folders_is_skipped(self, tmp_path, monkeypatch):
        """A walk entry whose 'root' is in kce.download_folders is skipped."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        sub1 = root / "Series A"
        sub2 = root / "Series B"
        sub1.mkdir(parents=True)
        sub2.mkdir(parents=True)

        monkeypatch.setattr(kce, "download_folders", [str(sub2)])
        result = kce.get_all_folders_recursively_in_dir(str(root))
        returned_roots = {e["root"] for e in result}
        assert str(sub2) not in returned_roots
        assert str(root) in returned_roots
        assert str(sub1) in returned_roots

    def test_files_at_root_level_appear_in_root_entry(self, tmp_path, monkeypatch):
        """Files placed directly in the scan root appear in the root entry."""
        _isolate(monkeypatch)
        root = tmp_path / "library"
        root.mkdir()
        (root / "stray.cbz").write_bytes(b"")

        result = kce.get_all_folders_recursively_in_dir(str(root))
        root_entry = next(e for e in result if e["root"] == str(root))
        assert "stray.cbz" in root_entry["files"]


# =========================================================================== #
# get_all_files_in_directory
# =========================================================================== #

class TestGetAllFilesInDirectory:
    """Pin behaviour of get_all_files_in_directory."""

    def test_returns_list(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        result = kce.get_all_files_in_directory(str(tmp_path))
        assert isinstance(result, list)

    def test_returns_basenames_not_full_paths(self, tmp_path, monkeypatch):
        """Returned items are bare filenames, not absolute or relative paths."""
        _isolate(monkeypatch)
        sub = tmp_path / "Series"
        sub.mkdir()
        (sub / "v01.cbz").write_bytes(b"")

        result = kce.get_all_files_in_directory(str(tmp_path))
        assert len(result) == 1
        assert result[0] == "v01.cbz"
        assert os.sep not in result[0]

    def test_extension_filter_keeps_accepted_types(self, tmp_path, monkeypatch):
        """Only files with kce.file_extensions (.epub, .zip, .cbz) are kept."""
        _isolate(monkeypatch)
        sub = tmp_path / "Series"
        sub.mkdir()
        (sub / "v01.cbz").write_bytes(b"")
        (sub / "v02.epub").write_bytes(b"")
        (sub / "v03.zip").write_bytes(b"")

        result = kce.get_all_files_in_directory(str(tmp_path))
        assert set(result) == {"v01.cbz", "v02.epub", "v03.zip"}

    def test_hidden_files_excluded(self, tmp_path, monkeypatch):
        """Files starting with '.' (dot-files) are filtered out."""
        _isolate(monkeypatch)
        sub = tmp_path / "Series"
        sub.mkdir()
        (sub / ".hidden.cbz").write_bytes(b"")
        (sub / "v01.cbz").write_bytes(b"")

        result = kce.get_all_files_in_directory(str(tmp_path))
        assert ".hidden.cbz" not in result
        assert "v01.cbz" in result

    def test_unaccepted_extensions_excluded(self, tmp_path, monkeypatch):
        """Files with .txt, .jpg, .png extensions are excluded."""
        _isolate(monkeypatch)
        sub = tmp_path / "Series"
        sub.mkdir()
        (sub / "readme.txt").write_bytes(b"")
        (sub / "cover.jpg").write_bytes(b"")
        (sub / "v01.cbz").write_bytes(b"")

        result = kce.get_all_files_in_directory(str(tmp_path))
        assert "readme.txt" not in result
        assert "cover.jpg" not in result
        assert "v01.cbz" in result

    def test_recurses_into_subdirectories(self, tmp_path, monkeypatch):
        """Files in nested subdirectories are collected."""
        _isolate(monkeypatch)
        sub1 = tmp_path / "Series A"
        sub2 = tmp_path / "Series B"
        sub1.mkdir()
        sub2.mkdir()
        (sub1 / "a_v01.cbz").write_bytes(b"")
        (sub2 / "b_v01.cbz").write_bytes(b"")

        result = kce.get_all_files_in_directory(str(tmp_path))
        assert set(result) == {"a_v01.cbz", "b_v01.cbz"}

    def test_empty_directory_returns_empty_list(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        result = kce.get_all_files_in_directory(str(tmp_path))
        assert result == []


# =========================================================================== #
# cache_existing_library_paths
# =========================================================================== #

class TestCacheExistingLibraryPaths:
    """Pin the side-effects and return value of cache_existing_library_paths."""

    def test_returns_list(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        root = tmp_path / "lib"
        root.mkdir()
        monkeypatch.setattr(kce, "paths", [str(root)])

        result = kce.cache_existing_library_paths(
            paths=[str(root)], download_folders=[], cached_paths=kce.cached_paths
        )
        assert isinstance(result, list)

    def test_return_value_is_same_object_as_kce_cached_paths(self, tmp_path, monkeypatch):
        """Return value IS the kce.cached_paths list object (not a copy)."""
        _isolate(monkeypatch)
        root = tmp_path / "lib"
        (root / "Series A").mkdir(parents=True)
        monkeypatch.setattr(kce, "paths", [str(root)])

        before_id = id(kce.cached_paths)
        result = kce.cache_existing_library_paths(
            paths=[str(root)], download_folders=[], cached_paths=kce.cached_paths
        )
        # FLAG: return value is the same list object passed in AND kce.cached_paths
        assert result is kce.cached_paths
        assert id(result) == before_id

    def test_subdirectories_added_to_cached_paths(self, tmp_path, monkeypatch):
        """Subdirectories under the root path are appended to kce.cached_paths."""
        _isolate(monkeypatch)
        root = tmp_path / "lib"
        sub_a = root / "Series A"
        sub_b = root / "Series B"
        sub_a.mkdir(parents=True)
        sub_b.mkdir(parents=True)
        monkeypatch.setattr(kce, "paths", [str(root)])

        kce.cache_existing_library_paths(
            paths=[str(root)], download_folders=[], cached_paths=kce.cached_paths
        )
        assert str(sub_a) in kce.cached_paths
        assert str(sub_b) in kce.cached_paths

    def test_root_itself_not_added_to_cached_paths(self, tmp_path, monkeypatch):
        """The scanned root path itself is NOT added to cached_paths."""
        _isolate(monkeypatch)
        root = tmp_path / "lib"
        (root / "Series A").mkdir(parents=True)
        monkeypatch.setattr(kce, "paths", [str(root)])

        kce.cache_existing_library_paths(
            paths=[str(root)], download_folders=[], cached_paths=kce.cached_paths
        )
        # root is in kce.paths so cache_path skips it
        assert str(root) not in kce.cached_paths

    def test_nested_subdirectories_also_cached(self, tmp_path, monkeypatch):
        """Nested subdirectories (depth > 1) are also cached."""
        _isolate(monkeypatch)
        root = tmp_path / "lib"
        nested = root / "Series A" / "Volume Extra"
        nested.mkdir(parents=True)
        monkeypatch.setattr(kce, "paths", [str(root)])

        kce.cache_existing_library_paths(
            paths=[str(root)], download_folders=[], cached_paths=kce.cached_paths
        )
        assert str(nested) in kce.cached_paths
        assert str(nested.parent) in kce.cached_paths

    def test_path_in_download_folders_is_skipped(self, tmp_path, monkeypatch):
        """A path that is also in download_folders is skipped entirely."""
        _isolate(monkeypatch)
        root = tmp_path / "lib"
        (root / "Series A").mkdir(parents=True)
        monkeypatch.setattr(kce, "paths", [str(root)])

        kce.cache_existing_library_paths(
            paths=[str(root)],
            download_folders=[str(root)],
            cached_paths=kce.cached_paths,
        )
        assert kce.cached_paths == []

    def test_nonexistent_path_does_not_raise(self, monkeypatch):
        """A nonexistent path is silently skipped; cached_paths stays empty."""
        _isolate(monkeypatch)
        result = kce.cache_existing_library_paths(
            paths=["/nonexistent/__kce_test__"],
            download_folders=[],
            cached_paths=kce.cached_paths,
        )
        assert result == []
        assert kce.cached_paths == []

    def test_already_cached_path_not_duplicated(self, tmp_path, monkeypatch):
        """A subdirectory that is already in cached_paths is not re-added."""
        _isolate(monkeypatch)
        root = tmp_path / "lib"
        sub = root / "Series A"
        sub.mkdir(parents=True)
        monkeypatch.setattr(kce, "paths", [str(root)])

        # Pre-populate cached_paths with the subdir
        kce.cached_paths.append(str(sub))
        kce.cache_existing_library_paths(
            paths=[str(root)], download_folders=[], cached_paths=kce.cached_paths
        )
        # Should still be exactly one entry
        assert kce.cached_paths.count(str(sub)) == 1

    def test_empty_paths_list_returns_empty(self, monkeypatch):
        _isolate(monkeypatch)
        result = kce.cache_existing_library_paths(
            paths=[], download_folders=[], cached_paths=kce.cached_paths
        )
        assert result == []


# =========================================================================== #
# clean_and_sort
# =========================================================================== #

class TestCleanAndSort:
    """Pin clean_and_sort behaviour including mutation side-effects."""

    # ---- return type ---------------------------------------------------- #

    def test_returns_tuple_of_two_lists(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        result = kce.clean_and_sort(str(tmp_path), files=[], dirs=[], test_mode=True)
        assert isinstance(result, tuple)
        assert len(result) == 2
        files_out, dirs_out = result
        assert isinstance(files_out, list)
        assert isinstance(dirs_out, list)

    def test_empty_inputs_return_empty_lists(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files_out, dirs_out = kce.clean_and_sort(
            str(tmp_path), files=[], dirs=[], test_mode=True
        )
        assert files_out == []
        assert dirs_out == []

    # ---- hidden file removal -------------------------------------------- #

    def test_hidden_files_removed_by_default(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = [".hidden.cbz", "visible.cbz"]
        files_out, _ = kce.clean_and_sort(
            str(tmp_path), files=files, test_mode=True
        )
        assert ".hidden.cbz" not in files_out
        assert "visible.cbz" in files_out

    def test_skip_remove_hidden_files_keeps_dot_files(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = [".hidden.cbz", "visible.cbz"]
        files_out, _ = kce.clean_and_sort(
            str(tmp_path), files=files, skip_remove_hidden_files=True, test_mode=True
        )
        assert ".hidden.cbz" in files_out

    # ---- extension filtering -------------------------------------------- #

    def test_unaccepted_extensions_removed(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = ["v01.cbz", "readme.txt", "cover.jpg"]
        files_out, _ = kce.clean_and_sort(
            str(tmp_path), files=files, test_mode=True
        )
        assert "v01.cbz" in files_out
        assert "readme.txt" not in files_out
        assert "cover.jpg" not in files_out

    def test_skip_remove_unaccepted_file_types_keeps_all_extensions(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = ["v01.cbz", "readme.txt"]
        files_out, _ = kce.clean_and_sort(
            str(tmp_path), files=files, skip_remove_unaccepted_file_types=True, test_mode=True
        )
        assert "readme.txt" in files_out
        assert "v01.cbz" in files_out

    # ---- sort=True in-place mutation ------------------------------------ #

    def test_sort_true_mutates_input_files_list_in_place(self, tmp_path, monkeypatch):
        """FLAG: sort=True calls files.sort() on the caller's list object.

        The input list is mutated in-place BEFORE the filtered copy is
        returned. This is a side-effect that callers may not expect.
        """
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = ["c.cbz", "a.cbz", "b.cbz"]
        original_id = id(files)
        kce.clean_and_sort(str(tmp_path), files=files, sort=True, test_mode=True)
        # The list object is the same but its contents are now sorted
        assert id(files) == original_id
        assert files == ["a.cbz", "b.cbz", "c.cbz"]  # mutated in-place

    def test_sort_true_mutates_input_dirs_list_in_place(self, tmp_path, monkeypatch):
        """FLAG: sort=True also calls dirs.sort() on the caller's dirs list."""
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        dirs = ["SeriesC", "SeriesA", "SeriesB"]
        original_id = id(dirs)
        kce.clean_and_sort(str(tmp_path), dirs=dirs, sort=True, test_mode=True)
        assert id(dirs) == original_id
        assert dirs == ["SeriesA", "SeriesB", "SeriesC"]  # mutated in-place

    def test_sort_false_does_not_mutate_input_list(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = ["c.cbz", "a.cbz", "b.cbz"]
        files_copy = list(files)
        kce.clean_and_sort(str(tmp_path), files=files, sort=False, test_mode=True)
        assert files == files_copy  # unchanged

    def test_sorted_result_files_is_new_object_not_input_list(self, tmp_path, monkeypatch):
        """The returned files list is a NEW object (not the sorted input list)."""
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = ["b.cbz", "a.cbz"]
        files_out, _ = kce.clean_and_sort(
            str(tmp_path), files=files, sort=True, test_mode=True
        )
        assert files_out is not files

    def test_sort_output_is_sorted(self, tmp_path, monkeypatch):
        """Returned files are in sorted order when sort=True."""
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = ["c.cbz", "a.cbz", "b.cbz"]
        files_out, _ = kce.clean_and_sort(
            str(tmp_path), files=files, sort=True, test_mode=True
        )
        assert files_out == ["a.cbz", "b.cbz", "c.cbz"]

    # ---- hidden folder removal ------------------------------------------ #

    def test_hidden_dirs_removed_by_default(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        dirs = [".hidden", "visible"]
        _, dirs_out = kce.clean_and_sort(
            str(tmp_path), dirs=dirs, test_mode=True
        )
        assert ".hidden" not in dirs_out
        assert "visible" in dirs_out

    def test_skip_remove_hidden_folders_keeps_dot_dirs(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        dirs = [".hidden", "visible"]
        _, dirs_out = kce.clean_and_sort(
            str(tmp_path), dirs=dirs, skip_remove_hidden_folders=True, test_mode=True
        )
        assert ".hidden" in dirs_out

    # ---- ignored_folder_names ------------------------------------------- #

    def test_ignored_folder_in_root_path_returns_empty_tuple(self, tmp_path, monkeypatch):
        """If root path contains an ignored folder segment, returns ([], [])."""
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", ["_ignore"])

        bad_root = tmp_path / "_ignore" / "subdir"
        bad_root.mkdir(parents=True)
        result = kce.clean_and_sort(
            str(bad_root), files=["v01.cbz"], test_mode=True
        )
        assert result == ([], [])

    def test_ignored_folder_names_removed_from_dirs(self, tmp_path, monkeypatch):
        """Dirs matching ignored_folder_names are removed from the dirs list."""
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", ["_ignore"])
        dirs = ["_ignore", "good"]
        _, dirs_out = kce.clean_and_sort(
            str(tmp_path), dirs=dirs, test_mode=True
        )
        assert "_ignore" not in dirs_out
        assert "good" in dirs_out

    def test_skip_remove_ignored_folders_keeps_ignored_dirs(self, tmp_path, monkeypatch):
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", ["_ignore"])
        dirs = ["_ignore", "good"]
        _, dirs_out = kce.clean_and_sort(
            str(tmp_path), dirs=dirs, skip_remove_ignored_folders=True, test_mode=True
        )
        assert "_ignore" in dirs_out

    # ---- chapters toggle ------------------------------------------------ #

    def test_chapters_false_filters_chapter_only_files(self, tmp_path, monkeypatch):
        """When chapters=False, chapter-only releases are filtered out."""
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = ["Series ch001.cbz", "Series v01.cbz"]
        files_out, _ = kce.clean_and_sort(
            str(tmp_path), files=files, chapters=False, test_mode=True
        )
        assert "Series ch001.cbz" not in files_out
        assert "Series v01.cbz" in files_out

    def test_chapters_true_keeps_chapter_files(self, tmp_path, monkeypatch):
        """When chapters=True, chapter files are kept."""
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        files = ["Series ch001.cbz", "Series v01.cbz"]
        files_out, _ = kce.clean_and_sort(
            str(tmp_path), files=files, chapters=True, test_mode=True
        )
        assert "Series ch001.cbz" in files_out
        assert "Series v01.cbz" in files_out

    # ---- just_these_files ------------------------------------------------ #

    def test_just_these_files_filters_to_specified_files(self, tmp_path, monkeypatch):
        """When just_these_files is given, only matching full paths are kept."""
        _isolate(monkeypatch)
        monkeypatch.setattr(kce, "check_for_existing_series_toggle", False)
        monkeypatch.setattr(kce, "ignored_folder_names", [])
        root = str(tmp_path)
        files = ["a.cbz", "b.cbz", "c.cbz"]
        just = [os.path.join(root, "a.cbz")]
        files_out, _ = kce.clean_and_sort(
            root, files=files, just_these_files=just, test_mode=True
        )
        assert files_out == ["a.cbz"]
