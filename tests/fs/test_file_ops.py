"""Characterization tests for file-operation helpers in komga_cover_extractor.py.

Functions under test
--------------------
  move_file, remove_file, rename_file, replace_file,
  set_modification_date, get_lines_from_file, write_to_file

Design notes
------------
* All assertions pin what the code does TODAY — behaviour is pinned AS-IS.
* FLAG: comments mark surprising or potentially buggy behaviour.
* Every test operates entirely under tmp_path; the real library is never touched.
* grouped_notifications side-effects are verified by snapshotting
  ``len(kce.grouped_notifications)`` before/after each call.
"""

from __future__ import annotations

import os
import stat

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file_obj(tmp_dir: str, filename: str, volume_number: int = 1) -> kce.File:
    """Build a real on-disk file and return a matching kce.File instance."""
    path = os.path.join(tmp_dir, filename)
    open(path, "w").close()
    return kce.File(
        name=filename,
        extensionless_name=kce.get_extensionless_name(filename),
        basename=os.path.splitext(filename)[0],
        extension=kce.get_file_extension(filename),
        root=tmp_dir,
        path=path,
        extensionless_path=kce.get_extensionless_name(path),
        volume_number=volume_number,
        file_type="volume",
        header_extension=None,
    )


def _make_file_obj_no_disk(tmp_dir: str, filename: str) -> kce.File:
    """Build a kce.File instance for a path that does NOT exist on disk."""
    path = os.path.join(tmp_dir, filename)
    return kce.File(
        name=filename,
        extensionless_name=kce.get_extensionless_name(filename),
        basename=os.path.splitext(filename)[0],
        extension=kce.get_file_extension(filename),
        root=tmp_dir,
        path=path,
        extensionless_path=kce.get_extensionless_name(path),
        volume_number=1,
        file_type="volume",
        header_extension=None,
    )


# ---------------------------------------------------------------------------
# move_file
# ---------------------------------------------------------------------------

class TestMoveFile:
    """Pin move_file(file, new_location, silent=False, ...) behaviour."""

    def test_moves_file_to_destination(self, tmp_path, monkeypatch):
        """File is present at destination and absent at source after a successful move."""
        src_dir = str(tmp_path / "src")
        dst_dir = str(tmp_path / "dst")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        f = _make_file_obj(src_dir, "Series v01.cbz")

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.move_file(f, dst_dir, silent=True)

        assert result is True
        assert not os.path.isfile(os.path.join(src_dir, "Series v01.cbz"))
        assert os.path.isfile(os.path.join(dst_dir, "Series v01.cbz"))

    def test_returns_true_on_success(self, tmp_path, monkeypatch):
        """Return value is exactly True (bool) on a successful move."""
        src_dir = str(tmp_path / "src")
        dst_dir = str(tmp_path / "dst")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        f = _make_file_obj(src_dir, "Series v01.cbz")

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.move_file(f, dst_dir, silent=True)

        assert result is True
        assert type(result) is bool

    def test_silent_true_does_not_grow_notifications(self, tmp_path, monkeypatch):
        """silent=True: grouped_notifications length is unchanged."""
        src_dir = str(tmp_path / "src")
        dst_dir = str(tmp_path / "dst")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        f = _make_file_obj(src_dir, "Series v01.cbz")

        notifs = []
        monkeypatch.setattr(kce, "grouped_notifications", notifs)
        before = len(kce.grouped_notifications)
        kce.move_file(f, dst_dir, silent=True)
        assert len(kce.grouped_notifications) - before == 0

    def test_silent_false_grows_notifications_by_one(self, tmp_path, monkeypatch):
        """silent=False: grouped_notifications grows by exactly 1."""
        src_dir = str(tmp_path / "src")
        dst_dir = str(tmp_path / "dst")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        f = _make_file_obj(src_dir, "Series v01.cbz")

        notifs = []
        monkeypatch.setattr(kce, "grouped_notifications", notifs)
        before = len(kce.grouped_notifications)
        kce.move_file(f, dst_dir, silent=False)
        assert len(kce.grouped_notifications) - before == 1

    def test_nonexistent_source_returns_none(self, tmp_path, monkeypatch):
        """If the source file does not exist on disk, move_file returns None.

        FLAG: returns None (not False) because the outer try-block falls through
        without hitting a return statement when os.path.isfile(file.path) is False.
        """
        dst_dir = str(tmp_path / "dst")
        os.makedirs(dst_dir)
        f = _make_file_obj_no_disk(str(tmp_path), "NotExist.cbz")

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.move_file(f, dst_dir, silent=True)

        # FLAG: returns None, not False, when source does not exist.
        assert result is None

    def test_conflict_at_destination_returns_false(self, tmp_path, monkeypatch):
        """If a file with the same name already exists at destination, move fails.

        shutil.move raises OSError on macOS/Python 3.13 when destination exists;
        the except clause returns False.
        """
        src_dir = str(tmp_path / "src")
        dst_dir = str(tmp_path / "dst")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        f = _make_file_obj(src_dir, "Series v01.cbz")
        # Pre-create the file at destination to trigger the conflict
        open(os.path.join(dst_dir, "Series v01.cbz"), "w").close()

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.move_file(f, dst_dir, silent=True)

        assert result is False

    def test_moves_associated_image_alongside_file(self, tmp_path, monkeypatch):
        """move_images() is called after a successful move, carrying the sidecar image."""
        src_dir = str(tmp_path / "src")
        dst_dir = str(tmp_path / "dst")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)

        cbz_path = os.path.join(src_dir, "Series v01.cbz")
        jpg_path = os.path.join(src_dir, "Series v01.jpg")  # sidecar
        open(cbz_path, "w").close()
        open(jpg_path, "w").close()

        f = kce.File(
            name="Series v01.cbz",
            extensionless_name="Series v01",
            basename="Series",
            extension=".cbz",
            root=src_dir,
            path=cbz_path,
            extensionless_path=os.path.join(src_dir, "Series v01"),
            volume_number=1,
            file_type="volume",
            header_extension=None,
        )

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.move_file(f, dst_dir, silent=True)

        assert result is True
        assert os.path.isfile(os.path.join(dst_dir, "Series v01.cbz"))
        assert os.path.isfile(os.path.join(dst_dir, "Series v01.jpg"))
        assert not os.path.isfile(jpg_path)


# ---------------------------------------------------------------------------
# remove_file
# ---------------------------------------------------------------------------

class TestRemoveFile:
    """Pin remove_file(full_file_path, silent=False) behaviour."""

    def test_removes_existing_file(self, tmp_path):
        """A file that exists on disk is deleted; returns True."""
        p = tmp_path / "testfile.cbz"
        p.write_text("")
        result = kce.remove_file(str(p), silent=True)

        assert result is True
        assert type(result) is bool
        assert not p.exists()

    def test_silent_true_does_not_grow_notifications(self, tmp_path, monkeypatch):
        """silent=True: grouped_notifications length is unchanged."""
        p = tmp_path / "testfile.cbz"
        p.write_text("")

        notifs = []
        monkeypatch.setattr(kce, "grouped_notifications", notifs)
        before = len(kce.grouped_notifications)
        kce.remove_file(str(p), silent=True)
        assert len(kce.grouped_notifications) - before == 0

    def test_silent_false_grows_notifications_by_one(self, tmp_path, monkeypatch):
        """silent=False: grouped_notifications grows by exactly 1."""
        p = tmp_path / "testfile.cbz"
        p.write_text("")

        notifs = []
        monkeypatch.setattr(kce, "grouped_notifications", notifs)
        before = len(kce.grouped_notifications)
        kce.remove_file(str(p), silent=False)
        assert len(kce.grouped_notifications) - before == 1

    def test_nonexistent_file_returns_false(self, tmp_path, monkeypatch):
        """remove_file returns False when the target path does not exist."""
        p = tmp_path / "notexist.cbz"

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.remove_file(str(p), silent=True)

        assert result is False

    def test_removes_associated_sidecar_image(self, tmp_path, monkeypatch):
        """Removing a non-image file also removes its associated volume cover image."""
        cbz = tmp_path / "Series v01.cbz"
        jpg = tmp_path / "Series v01.jpg"
        cbz.write_text("")
        jpg.write_text("")

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.remove_file(str(cbz), silent=True)

        assert result is True
        assert not cbz.exists()
        assert not jpg.exists()

    def test_removing_image_file_does_not_recurse(self, tmp_path, monkeypatch):
        """Removing an image file itself returns True and doesn't recurse."""
        img = tmp_path / "cover.jpg"
        img.write_text("")

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.remove_file(str(img), silent=True)

        assert result is True
        assert not img.exists()


# ---------------------------------------------------------------------------
# rename_file
# ---------------------------------------------------------------------------

class TestRenameFile:
    """Pin rename_file(src, dest, silent=False) behaviour."""

    def test_renames_file_on_disk(self, tmp_path):
        """File is absent at src and present at dest after successful rename."""
        src = tmp_path / "Old v01.cbz"
        dst = tmp_path / "New v01.cbz"
        src.write_text("")

        result = kce.rename_file(str(src), str(dst), silent=True)

        assert result is True
        assert not src.exists()
        assert dst.exists()

    def test_returns_bool_true_on_success(self, tmp_path):
        """Return type is exactly bool, value True."""
        src = tmp_path / "A v01.cbz"
        dst = tmp_path / "B v01.cbz"
        src.write_text("")

        result = kce.rename_file(str(src), str(dst), silent=True)

        assert type(result) is bool
        assert result is True

    def test_returns_false_when_src_absent(self, tmp_path):
        """rename_file returns False when src does not exist (file not touched)."""
        src = tmp_path / "NotExist.cbz"
        dst = tmp_path / "Whatever.cbz"

        result = kce.rename_file(str(src), str(dst), silent=True)

        assert result is False

    def test_never_modifies_grouped_notifications_silent_false(self, tmp_path, monkeypatch):
        """rename_file NEVER adds to grouped_notifications even with silent=False.

        FLAG: rename_file uses send_message(..., discord=False) — it only prints to
        stdout and never creates a Discord embed, so grouped_notifications stays
        unchanged regardless of the silent flag.
        """
        src = tmp_path / "Old v01.cbz"
        dst = tmp_path / "New v01.cbz"
        src.write_text("")

        notifs = []
        monkeypatch.setattr(kce, "grouped_notifications", notifs)
        before = len(kce.grouped_notifications)
        kce.rename_file(str(src), str(dst), silent=False)
        after = len(kce.grouped_notifications)

        # FLAG: grouped_notifications delta is 0 even when silent=False.
        assert after - before == 0

    def test_never_modifies_grouped_notifications_silent_true(self, tmp_path, monkeypatch):
        """silent=True also leaves grouped_notifications unchanged."""
        src = tmp_path / "Old v01.cbz"
        dst = tmp_path / "New v01.cbz"
        src.write_text("")

        notifs = []
        monkeypatch.setattr(kce, "grouped_notifications", notifs)
        before = len(kce.grouped_notifications)
        kce.rename_file(str(src), str(dst), silent=True)
        after = len(kce.grouped_notifications)

        assert after - before == 0

    def test_cascades_cover_image_rename_jpg(self, tmp_path):
        """Renaming a cbz also renames its sidecar .jpg cover image.

        FLAG: cover-image cascade — renaming 'X.cbz' to 'Y.cbz' recursively
        calls rename_file('X.jpg', 'Y.jpg', silent=True) for every image extension
        that exists on disk. This is an in-place side-effect of the rename.
        """
        src_cbz = tmp_path / "Old v01.cbz"
        src_jpg = tmp_path / "Old v01.jpg"
        dst_cbz = tmp_path / "New v01.cbz"
        dst_jpg = tmp_path / "New v01.jpg"

        src_cbz.write_text("")
        src_jpg.write_text("")

        result = kce.rename_file(str(src_cbz), str(dst_cbz), silent=True)

        assert result is True
        assert not src_cbz.exists()
        assert dst_cbz.exists()
        assert not src_jpg.exists()    # FLAG: cascade renamed old sidecar away
        assert dst_jpg.exists()        # FLAG: cascade created renamed sidecar

    def test_cascades_cover_image_rename_multiple_extensions(self, tmp_path):
        """Cover cascade fires for every image extension that exists on disk."""
        src_cbz = tmp_path / "Old v01.cbz"
        src_cbz.write_text("")
        src_imgs = {}
        for ext in (".jpg", ".png", ".webp"):
            p = tmp_path / f"Old v01{ext}"
            p.write_text("")
            src_imgs[ext] = p

        result = kce.rename_file(str(src_cbz), str(tmp_path / "New v01.cbz"), silent=True)

        assert result is True
        for ext in (".jpg", ".png", ".webp"):
            assert not src_imgs[ext].exists(), f"src sidecar {ext} should be gone"
            assert (tmp_path / f"New v01{ext}").exists(), f"dst sidecar {ext} should exist"

    def test_no_cascade_when_renaming_image_file(self, tmp_path):
        """Renaming an image file itself does NOT trigger the cascade recursion."""
        src = tmp_path / "cover.jpg"
        dst = tmp_path / "new_cover.jpg"
        src.write_text("")

        result = kce.rename_file(str(src), str(dst), silent=True)

        assert result is True
        assert not src.exists()
        assert dst.exists()

    def test_cascade_skips_non_existent_image_extensions(self, tmp_path):
        """Cascade only renames image files that actually exist; others are silently skipped."""
        src_cbz = tmp_path / "Old v01.cbz"
        dst_cbz = tmp_path / "New v01.cbz"
        src_cbz.write_text("")
        # Only create .jpg sidecar; .png, .webp, etc. are absent

        result = kce.rename_file(str(src_cbz), str(dst_cbz), silent=True)

        assert result is True
        # No .png or .webp sidecar was created at destination
        for ext in (".png", ".webp", ".tbn", ".jpeg"):
            assert not (tmp_path / f"New v01{ext}").exists()


# ---------------------------------------------------------------------------
# replace_file
# ---------------------------------------------------------------------------

class TestReplaceFile:
    """Pin replace_file(old_file, new_file, highest_index_num='') behaviour."""

    def _make_pair(self, tmp_path, old_name="Old v01.cbz", new_name="New v01.cbz"):
        old_dir = str(tmp_path / "old_dir")
        new_dir = str(tmp_path / "new_dir")
        os.makedirs(old_dir)
        os.makedirs(new_dir)
        old_file = _make_file_obj(old_dir, old_name)
        new_file = _make_file_obj(new_dir, new_name)
        return old_dir, new_dir, old_file, new_file

    def test_replace_moves_new_to_old_dir(self, tmp_path, monkeypatch):
        """After replace_file, new_file ends up in old_file's directory."""
        old_dir, new_dir, old_file, new_file = self._make_pair(tmp_path)

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.replace_file(old_file, new_file)

        assert result is True
        assert os.path.isfile(os.path.join(old_dir, new_file.name))

    def test_replace_removes_old_file(self, tmp_path, monkeypatch):
        """replace_file removes the old file from its original location."""
        old_dir, new_dir, old_file, new_file = self._make_pair(tmp_path)

        monkeypatch.setattr(kce, "grouped_notifications", [])
        kce.replace_file(old_file, new_file)

        assert not os.path.isfile(old_file.path)

    def test_returns_true_on_success(self, tmp_path, monkeypatch):
        """Return type is exactly bool, value True on a successful replace."""
        old_dir, new_dir, old_file, new_file = self._make_pair(tmp_path)

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.replace_file(old_file, new_file)

        assert type(result) is bool
        assert result is True

    def test_grows_notifications_by_two(self, tmp_path, monkeypatch):
        """replace_file adds exactly 2 notifications: one from remove_file, one from itself.

        Breakdown:
          * remove_file(old_file.path) — called without silent=True → +1
          * replace_file itself appends its own 'Moved File' embed → +1
        Total delta = 2.
        """
        old_dir, new_dir, old_file, new_file = self._make_pair(tmp_path)

        notifs = []
        monkeypatch.setattr(kce, "grouped_notifications", notifs)
        before = len(kce.grouped_notifications)
        kce.replace_file(old_file, new_file)
        after = len(kce.grouped_notifications)

        assert after - before == 2

    def test_returns_false_when_old_file_missing(self, tmp_path, monkeypatch):
        """If old_file doesn't exist on disk, replace_file returns False without touching anything."""
        old_dir = str(tmp_path / "old_dir")
        new_dir = str(tmp_path / "new_dir")
        os.makedirs(old_dir)
        os.makedirs(new_dir)

        # old_file path doesn't exist
        old_file = _make_file_obj_no_disk(old_dir, "Old v01.cbz")
        new_file = _make_file_obj(new_dir, "New v01.cbz")

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.replace_file(old_file, new_file)

        assert result is False

    def test_returns_false_when_new_file_missing(self, tmp_path, monkeypatch):
        """If new_file doesn't exist on disk, replace_file returns False."""
        old_dir = str(tmp_path / "old_dir")
        new_dir = str(tmp_path / "new_dir")
        os.makedirs(old_dir)
        os.makedirs(new_dir)

        old_file = _make_file_obj(old_dir, "Old v01.cbz")
        new_file = _make_file_obj_no_disk(new_dir, "New v01.cbz")

        monkeypatch.setattr(kce, "grouped_notifications", [])
        result = kce.replace_file(old_file, new_file)

        assert result is False

    def test_returns_false_no_notifications_on_missing_file(self, tmp_path, monkeypatch):
        """On file-missing failure, grouped_notifications does not grow."""
        old_dir = str(tmp_path / "old_dir")
        new_dir = str(tmp_path / "new_dir")
        os.makedirs(old_dir)
        os.makedirs(new_dir)

        old_file = _make_file_obj_no_disk(old_dir, "Old v01.cbz")
        new_file = _make_file_obj(new_dir, "New v01.cbz")

        notifs = []
        monkeypatch.setattr(kce, "grouped_notifications", notifs)
        before = len(kce.grouped_notifications)
        kce.replace_file(old_file, new_file)
        after = len(kce.grouped_notifications)

        assert after - before == 0


# ---------------------------------------------------------------------------
# set_modification_date
# ---------------------------------------------------------------------------

class TestSetModificationDate:
    """Pin set_modification_date(file_path, date) behaviour."""

    def test_sets_mtime_to_given_value(self, tmp_path):
        """mtime is set to the provided timestamp."""
        p = tmp_path / "test.cbz"
        p.write_text("")
        target = 946684800.0  # 2000-01-01 00:00:00 UTC

        kce.set_modification_date(str(p), target)

        assert kce.get_modification_date(str(p)) == target

    def test_preserves_atime_as_original_mtime(self, tmp_path):
        """atime is set to the file's mtime at call time (reads via get_modification_date).

        FLAG: atime is set to the *original mtime* of the file (not the current
        access time), because os.utime is called with
        (get_modification_date(file_path), date) — i.e. atime := old mtime.
        """
        p = tmp_path / "test.cbz"
        p.write_text("")
        original_mtime = kce.get_modification_date(str(p))
        target = 946684800.0

        kce.set_modification_date(str(p), target)

        st = os.stat(str(p))
        assert st.st_atime == original_mtime  # FLAG: atime = old mtime
        assert st.st_mtime == target

    def test_returns_none(self, tmp_path):
        """set_modification_date has no return value (returns None)."""
        p = tmp_path / "test.cbz"
        p.write_text("")
        result = kce.set_modification_date(str(p), 946684800.0)
        assert result is None


# ---------------------------------------------------------------------------
# get_lines_from_file
# ---------------------------------------------------------------------------

class TestGetLinesFromFile:
    """Pin get_lines_from_file(file_path, ignore=[], check_paths=False) behaviour."""

    def test_reads_lines_stripped(self, tmp_path):
        """Lines are stripped of surrounding whitespace."""
        p = tmp_path / "test.txt"
        p.write_text("  line1  \nline2\n  line3\n")
        result = kce.get_lines_from_file(str(p))
        assert result == ["line1", "line2", "line3"]
        assert type(result) is list

    def test_skips_blank_and_whitespace_only_lines(self, tmp_path):
        """Blank lines and lines that are entirely whitespace are omitted."""
        p = tmp_path / "test.txt"
        p.write_text("line1\n\n   \nline2\n")
        result = kce.get_lines_from_file(str(p))
        assert result == ["line1", "line2"]

    def test_deduplicates_lines(self, tmp_path):
        """Duplicate lines appear only once in the result."""
        p = tmp_path / "test.txt"
        p.write_text("line1\nline1\nline2\n")
        result = kce.get_lines_from_file(str(p))
        assert result == ["line1", "line2"]

    def test_ignore_param_excludes_matching_lines(self, tmp_path):
        """Lines that appear in the ignore list are excluded from results."""
        p = tmp_path / "test.txt"
        p.write_text("line1\nline2\nline3\n")
        result = kce.get_lines_from_file(str(p), ignore=["line1"])
        assert result == ["line2", "line3"]

    def test_nonexistent_file_returns_empty_list(self, tmp_path):
        """When the file does not exist, returns an empty list (not an exception)."""
        result = kce.get_lines_from_file(str(tmp_path / "notexist.txt"))
        assert result == []
        assert type(result) is list

    def test_check_paths_filters_by_kce_paths(self, tmp_path, monkeypatch):
        """check_paths=True: only lines starting with a prefix in kce.paths are kept."""
        p = tmp_path / "test.txt"
        p.write_text("/allowed/file1\n/blocked/file2\n/allowed/file3\n")
        monkeypatch.setattr(kce, "paths", ["/allowed"])
        result = kce.get_lines_from_file(str(p), check_paths=True)
        assert result == ["/allowed/file1", "/allowed/file3"]

    def test_check_paths_no_filter_when_paths_empty(self, tmp_path, monkeypatch):
        """check_paths=True with kce.paths=[] performs no path filtering."""
        p = tmp_path / "test.txt"
        p.write_text("/allowed/file1\n/blocked/file2\n")
        monkeypatch.setattr(kce, "paths", [])
        result = kce.get_lines_from_file(str(p), check_paths=True)
        assert result == ["/allowed/file1", "/blocked/file2"]

    def test_returns_list_of_strings(self, tmp_path):
        """Every element in the result is a str."""
        p = tmp_path / "test.txt"
        p.write_text("alpha\nbeta\n")
        result = kce.get_lines_from_file(str(p))
        assert all(isinstance(line, str) for line in result)


# ---------------------------------------------------------------------------
# write_to_file
# ---------------------------------------------------------------------------

class TestWriteToFile:
    """Pin write_to_file(file, message, ...) behaviour."""

    def test_creates_log_file_and_returns_true(self, tmp_path):
        """On first write, creates the log file and returns True."""
        result = kce.write_to_file(
            "run.log", "hello", without_timestamp=True, write_to=str(tmp_path), can_write_log=True
        )
        assert result is True
        assert type(result) is bool
        assert (tmp_path / "run.log").exists()

    def test_without_timestamp_writes_message_only(self, tmp_path):
        """without_timestamp=True writes the message prefixed by a newline, no date."""
        kce.write_to_file(
            "run.log", "hello world", without_timestamp=True, write_to=str(tmp_path), can_write_log=True
        )
        content = (tmp_path / "run.log").read_text()
        assert content == "\nhello world"

    def test_with_timestamp_includes_date_prefix(self, tmp_path):
        """without_timestamp=False (default) prepends a dd/mm/YYYY HH:MM:SS string."""
        import re
        kce.write_to_file(
            "run.log", "msg", without_timestamp=False, write_to=str(tmp_path), can_write_log=True
        )
        content = (tmp_path / "run.log").read_text()
        # Timestamp format: \nDD/MM/YYYY HH:MM:SS msg
        assert re.match(r"\n\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} msg", content)

    def test_appends_on_second_write(self, tmp_path):
        """Subsequent writes (without overwrite=True) append to the existing file."""
        kce.write_to_file("run.log", "first", without_timestamp=True, write_to=str(tmp_path), can_write_log=True)
        kce.write_to_file("run.log", "second", without_timestamp=True, write_to=str(tmp_path), can_write_log=True)
        content = (tmp_path / "run.log").read_text()
        assert content == "\nfirst\nsecond"

    def test_overwrite_truncates_file(self, tmp_path):
        """overwrite=True replaces any existing content."""
        kce.write_to_file("run.log", "original", without_timestamp=True, write_to=str(tmp_path), can_write_log=True)
        kce.write_to_file("run.log", "overwritten", without_timestamp=True, write_to=str(tmp_path), can_write_log=True, overwrite=True)
        content = (tmp_path / "run.log").read_text()
        assert content == "\noverwritten"

    def test_can_write_log_false_returns_false(self, tmp_path):
        """can_write_log=False short-circuits: returns False, no file created."""
        result = kce.write_to_file(
            "run.log", "hello", write_to=str(tmp_path), can_write_log=False
        )
        assert result is False
        assert not (tmp_path / "run.log").exists()

    def test_check_for_dup_prevents_duplicate_message(self, tmp_path):
        """check_for_dup=True: writing the same message a second time returns False and does not append."""
        kce.write_to_file("run.log", "dupe", without_timestamp=True, write_to=str(tmp_path), can_write_log=True)
        r2 = kce.write_to_file("run.log", "dupe", without_timestamp=True, write_to=str(tmp_path), can_write_log=True, check_for_dup=True)
        content = (tmp_path / "run.log").read_text()
        assert r2 is False
        assert content == "\ndupe"  # written only once

    def test_strips_tab_and_newline_from_message(self, tmp_path):
        """Tabs and newlines in the message are stripped before writing."""
        kce.write_to_file("run.log", "  he\tllo\nworld  ", without_timestamp=True, write_to=str(tmp_path), can_write_log=True)
        content = (tmp_path / "run.log").read_text()
        assert content == "\nhelloworld"

    def test_creates_write_to_directory_if_absent(self, tmp_path):
        """write_to_file creates the logs directory if it does not exist."""
        logs_dir = str(tmp_path / "newlogs" / "subdir")
        result = kce.write_to_file(
            "run.log", "hello", without_timestamp=True, write_to=logs_dir, can_write_log=True
        )
        assert result is True
        assert os.path.isfile(os.path.join(logs_dir, "run.log"))
