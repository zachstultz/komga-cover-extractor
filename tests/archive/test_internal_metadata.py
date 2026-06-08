"""Characterization tests for get_internal_metadata, get_novel_cover, and
get_novel_cover_path.

Design notes
------------
* All return values are pinned from *actual* function invocations observed via
  the .venv interpreter against real synthesized archives.
* Where current behaviour is surprising, a ``# FLAG:`` comment is attached.
* ``isolated_globals`` (autouse) clears every lru_cache before/after each test.

Function signatures (from source):
  get_internal_metadata(file_path, extension) -> dict | None
  get_novel_cover(novel_path) -> str | None
  get_novel_cover_path(file) -> str   (takes a kce.File object)
  parse_html_tags(html) -> dict       (BeautifulSoup-backed; tested as a helper)
"""

from __future__ import annotations

import os
import warnings
import zipfile

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# EPUB builder helpers (stdlib zipfile; no fixtures needed for this layer)
# ---------------------------------------------------------------------------

_CONTAINER_XML_OEBPS = """\
<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

_CONTAINER_XML_ROOT = """\
<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

_CONTAINER_XML_EMPTY_ROOTFILES = """\
<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
  </rootfiles>
</container>"""


def _make_epub(
    tmp_path,
    name: str = "test.epub",
    container_xml: str = _CONTAINER_XML_OEBPS,
    content_opf: str = "",
    opf_path: str = "OEBPS/content.opf",
    extra_entries: dict | None = None,
) -> str:
    """Build a minimal EPUB in tmp_path; return the file path as str."""
    epub_path = str(tmp_path / name)
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        if content_opf:
            zf.writestr(opf_path, content_opf)
        if extra_entries:
            for arcname, data in extra_entries.items():
                zf.writestr(arcname, data)
    return epub_path


def _make_file_obj(path: str, extension: str = ".epub") -> kce.File:
    """Create a minimal kce.File pointing at *path*."""
    root = os.path.dirname(path)
    name = os.path.basename(path)
    extensionless_name = os.path.splitext(name)[0]
    return kce.File(
        name=name,
        extensionless_name=extensionless_name,
        basename=root,
        extension=extension,
        root=root,
        path=path,
        extensionless_path=os.path.join(root, extensionless_name),
        volume_number=[],
        file_type="novel" if extension == ".epub" else "manga",
        header_extension=extension,
    )


# ---------------------------------------------------------------------------
# Minimal EPUB OPF templates
# ---------------------------------------------------------------------------

def _opf_with_cover(cover_id: str = "cover-image", cover_href: str = "images/cover.jpg") -> str:
    return f"""\
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>My Novel Title</dc:title>
    <dc:creator>Some Author</dc:creator>
    <meta name="cover" content="{cover_id}"/>
  </metadata>
  <manifest>
    <item id="{cover_id}" href="{cover_href}" media-type="image/jpeg"/>
  </manifest>
  <spine/>
</package>"""


def _opf_without_cover() -> str:
    return """\
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>My Novel Title</dc:title>
    <dc:creator>Some Author</dc:creator>
  </metadata>
  <manifest/>
  <spine/>
</package>"""


def _opf_html_cover() -> str:
    """OPF where the cover manifest item is an HTML file, not an image."""
    return """\
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>HTML Cover Novel</dc:title>
    <meta name="cover" content="cover-page"/>
  </metadata>
  <manifest>
    <item id="cover-page" href="cover.html" media-type="application/xhtml+xml"/>
  </manifest>
  <spine/>
</package>"""


# ---------------------------------------------------------------------------
# TestGetInternalMetadata — CBZ branch
# ---------------------------------------------------------------------------

class TestGetInternalMetadataCbz:
    """Pin get_internal_metadata behaviour for manga (.cbz / .zip) archives."""

    def test_cbz_with_comicinfo_returns_dict(self, cbz_factory, comicinfo_xml):
        """A cbz with ComicInfo.xml returns a dict (not None)."""
        path = cbz_factory(comicinfo_xml=comicinfo_xml(Title="T", Volume="3"))
        result = kce.get_internal_metadata(str(path), ".cbz")
        assert isinstance(result, dict)

    def test_cbz_comicinfo_title_and_volume(self, cbz_factory, comicinfo_xml):
        """ComicInfo Title and Volume values are returned as strings."""
        path = cbz_factory(comicinfo_xml=comicinfo_xml(Title="My Title", Volume="3"))
        result = kce.get_internal_metadata(str(path), ".cbz")
        assert result["Title"] == "My Title"
        assert result["Volume"] == "3"       # string, not int

    def test_cbz_comicinfo_namespace_attrs(self, cbz_factory, comicinfo_xml):
        """xmltodict surfaces xmlns attributes as '@xmlns:...' keys."""
        path = cbz_factory(comicinfo_xml=comicinfo_xml(Title="T"))
        result = kce.get_internal_metadata(str(path), ".cbz")
        assert result["@xmlns:xsi"] == "http://www.w3.org/2001/XMLSchema-instance"
        assert result["@xmlns:xsd"] == "http://www.w3.org/2001/XMLSchema"

    def test_cbz_without_comicinfo_returns_none(self, cbz_factory):
        """A cbz with no ComicInfo.xml returns None (contains_comic_info → False)."""
        path = cbz_factory()  # no comicinfo_xml kwarg → no ComicInfo.xml entry
        result = kce.get_internal_metadata(str(path), ".cbz")
        assert result is None

    def test_zip_with_comicinfo_returns_dict(self, cbz_factory, comicinfo_xml):
        """Extension .zip is also in manga_extensions; same code path executes."""
        path = cbz_factory(name="vol.zip", comicinfo_xml=comicinfo_xml(Title="Zip", Volume="7"))
        result = kce.get_internal_metadata(str(path), ".zip")
        assert isinstance(result, dict)
        assert result["Title"] == "Zip"
        assert result["Volume"] == "7"

    def test_zip_without_comicinfo_returns_none(self, cbz_factory):
        """A .zip without ComicInfo.xml → None."""
        path = cbz_factory(name="empty.zip")
        result = kce.get_internal_metadata(str(path), ".zip")
        assert result is None

    def test_cbz_multiple_comicinfo_fields(self, cbz_factory, comicinfo_xml):
        """Multiple ComicInfo fields survive the round-trip intact."""
        path = cbz_factory(
            comicinfo_xml=comicinfo_xml(
                Title="My Series", Volume="3", Year="2020", Publisher="Viz"
            )
        )
        result = kce.get_internal_metadata(str(path), ".cbz")
        assert result["Title"] == "My Series"
        assert result["Volume"] == "3"
        assert result["Year"] == "2020"
        assert result["Publisher"] == "Viz"

    def test_cbz_corrupt_file_returns_none(self, tmp_path):
        """A file that is not a valid zip → None (exception swallowed).

        FLAG: BadZipFile raised inside get_file_from_zip is caught; the outer
        try/except in get_internal_metadata also catches any propagated errors
        and returns None.
        """
        bad = tmp_path / "corrupt.cbz"
        bad.write_bytes(b"NOT A ZIP FILE")
        result = kce.get_internal_metadata(str(bad), ".cbz")
        assert result is None

    def test_unknown_extension_returns_none(self, cbz_factory):
        """An extension that is neither manga_extensions nor novel_extensions → None."""
        path = cbz_factory()
        result = kce.get_internal_metadata(str(path), ".unknown")
        assert result is None

    def test_cbz_return_type_is_dict(self, cbz_factory, comicinfo_xml):
        """The returned dict is a plain dict (not an OrderedDict subclass)."""
        path = cbz_factory(comicinfo_xml=comicinfo_xml(Title="T"))
        result = kce.get_internal_metadata(str(path), ".cbz")
        assert type(result) is dict


# ---------------------------------------------------------------------------
# TestGetInternalMetadataEpub — EPUB branch
# ---------------------------------------------------------------------------

class TestGetInternalMetadataEpub:
    """Pin get_internal_metadata behaviour for novel (.epub) archives."""

    def test_epub_with_opf_returns_dict(self, tmp_path):
        """An EPUB with a content.opf returns a dict parsed by BeautifulSoup."""
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover())
        warnings.filterwarnings("ignore")
        result = kce.get_internal_metadata(epub, ".epub")
        assert isinstance(result, dict)

    def test_epub_dc_title_present(self, tmp_path):
        """The dc:title field is extracted from the OPF metadata."""
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover())
        warnings.filterwarnings("ignore")
        result = kce.get_internal_metadata(epub, ".epub")
        assert result["dc:title"] == "My Novel Title"

    def test_epub_dc_creator_present(self, tmp_path):
        """The dc:creator field is extracted from the OPF metadata."""
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover())
        warnings.filterwarnings("ignore")
        result = kce.get_internal_metadata(epub, ".epub")
        assert result["dc:creator"] == "Some Author"

    def test_epub_meta_tag_value_is_empty_string(self, tmp_path):
        """The <meta name='cover' .../> element: BeautifulSoup returns '' for get_text().

        FLAG: BeautifulSoup's html.parser flattens the 'name' and 'content'
        attributes; the text content of the <meta> tag is the empty string ''.
        """
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover())
        warnings.filterwarnings("ignore")
        result = kce.get_internal_metadata(epub, ".epub")
        assert result["meta"] == ""

    def test_epub_package_key_is_concatenated_text(self, tmp_path):
        """The root <package> tag's text() is all inner text concatenated."""
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover())
        warnings.filterwarnings("ignore")
        result = kce.get_internal_metadata(epub, ".epub")
        # 'package' key exists and contains the title text
        assert "package" in result
        assert "My Novel Title" in result["package"]

    def test_epub_without_opf_returns_none(self, tmp_path):
        """An EPUB whose container.xml points to a non-existent OPF → None.

        FLAG: get_file_from_zip finds nothing → opf is None → metadata stays
        None, and send_message logs 'No opf file found'.
        """
        # container.xml points to OEBPS/content.opf, but we don't write that file.
        epub = _make_epub(tmp_path, name="noopf.epub", content_opf="")
        result = kce.get_internal_metadata(epub, ".epub")
        assert result is None

    def test_epub_return_type_is_dict_when_found(self, tmp_path):
        """get_internal_metadata returns a plain dict for a well-formed EPUB."""
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover())
        warnings.filterwarnings("ignore")
        result = kce.get_internal_metadata(epub, ".epub")
        assert type(result) is dict

    def test_epub_item_tag_value_is_empty_string(self, tmp_path):
        """Void <item ...> tags: BeautifulSoup get_text() returns '' for each.

        FLAG: The html.parser does not preserve self-closing attribute values;
        both 'item' and 'itemref' keys map to '' (last seen tag wins).
        """
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover())
        warnings.filterwarnings("ignore")
        result = kce.get_internal_metadata(epub, ".epub")
        assert result["item"] == ""


# ---------------------------------------------------------------------------
# TestGetNovelCover — direct function tests
# ---------------------------------------------------------------------------

class TestGetNovelCover:
    """Pin get_novel_cover(novel_path) behaviour."""

    def test_epub_with_cover_returns_internal_path(self, tmp_path):
        """When the OPF has a cover meta + manifest item, the internal path is returned."""
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover(cover_href="images/cover.jpg"))
        result = kce.get_novel_cover(epub)
        # cover_path = os.path.join(os.path.dirname("OEBPS/content.opf"), "images/cover.jpg")
        assert result == "OEBPS/images/cover.jpg"

    def test_epub_with_root_level_opf_cover(self, tmp_path):
        """When the OPF is at the zip root (no parent dir), the cover path is direct."""
        epub = _make_epub(
            tmp_path,
            name="root.epub",
            container_xml=_CONTAINER_XML_ROOT,
            content_opf=_opf_with_cover(cover_href="cover.jpg"),
            opf_path="content.opf",
        )
        result = kce.get_novel_cover(epub)
        assert result == "cover.jpg"

    def test_epub_without_cover_meta_returns_none(self, tmp_path):
        """When OPF has no <meta name='cover'> element, None is returned."""
        epub = _make_epub(tmp_path, name="nocover.epub", content_opf=_opf_without_cover())
        result = kce.get_novel_cover(epub)
        assert result is None

    def test_epub_no_rootfiles_returns_none(self, tmp_path):
        """When container.xml has empty <rootfiles>, None is returned."""
        epub = _make_epub(
            tmp_path,
            name="norootfile.epub",
            container_xml=_CONTAINER_XML_EMPTY_ROOTFILES,
            content_opf="",
        )
        result = kce.get_novel_cover(epub)
        assert result is None

    def test_epub_url_encoded_cover_href_is_decoded(self, tmp_path):
        """URL-encoded spaces in href (e.g. 'cover%20image.jpg') are decoded.

        FLAG: The code calls urllib.parse.unquote() when '%' appears in the href,
        so the returned path has literal spaces, not percent-encoding.
        """
        encoded_opf = _opf_with_cover(cover_href="images/cover%20image.jpg")
        epub = _make_epub(tmp_path, name="encoded.epub", content_opf=encoded_opf)
        result = kce.get_novel_cover(epub)
        assert result == "OEBPS/images/cover image.jpg"

    def test_epub_html_cover_returns_html_path(self, tmp_path):
        """When the cover manifest item is an HTML file, its path is still returned."""
        epub = _make_epub(tmp_path, name="htmlcover.epub", content_opf=_opf_html_cover())
        result = kce.get_novel_cover(epub)
        assert result == "OEBPS/cover.html"

    def test_nonexistent_path_returns_none(self):
        """A path that doesn't exist on disk → None (exception swallowed)."""
        result = kce.get_novel_cover("/nonexistent/path.epub")
        assert result is None

    def test_return_type_is_str_when_found(self, tmp_path):
        """The returned cover path is a plain str."""
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover())
        result = kce.get_novel_cover(epub)
        assert isinstance(result, str)

    def test_return_type_is_none_when_not_found(self, tmp_path):
        """When no cover is found, the return value is exactly None."""
        epub = _make_epub(tmp_path, name="nocov2.epub", content_opf=_opf_without_cover())
        result = kce.get_novel_cover(epub)
        assert result is None


# ---------------------------------------------------------------------------
# TestGetNovelCoverPath — File-object-level function
# ---------------------------------------------------------------------------

class TestGetNovelCoverPath:
    """Pin get_novel_cover_path(file) behaviour."""

    def test_epub_with_image_cover_returns_basename(self, tmp_path):
        """When the EPUB has an image cover, the basename of the cover is returned."""
        epub = _make_epub(tmp_path, content_opf=_opf_with_cover(cover_href="images/cover.jpg"))
        f = _make_file_obj(epub, ".epub")
        result = kce.get_novel_cover_path(f)
        # os.path.basename("OEBPS/images/cover.jpg") == "cover.jpg"
        assert result == "cover.jpg"

    def test_non_epub_extension_returns_empty_string(self, tmp_path):
        """Files with .cbz extension (not in novel_extensions) → '' immediately."""
        cbz = tmp_path / "test.cbz"
        with zipfile.ZipFile(str(cbz), "w") as zf:
            zf.writestr("page.jpg", b"fake")
        f = _make_file_obj(str(cbz), ".cbz")
        result = kce.get_novel_cover_path(f)
        assert result == ""

    def test_epub_without_cover_returns_empty_string(self, tmp_path):
        """EPUB with no cover meta tag → get_novel_cover returns None → '' returned."""
        epub = _make_epub(tmp_path, name="nocover2.epub", content_opf=_opf_without_cover())
        f = _make_file_obj(epub, ".epub")
        result = kce.get_novel_cover_path(f)
        assert result == ""

    def test_epub_html_cover_returns_empty_string(self, tmp_path):
        """When cover href points to an HTML file (not an image), '' is returned.

        FLAG: get_novel_cover returns the path but get_novel_cover_path checks
        whether the extension is in image_extensions; HTML is not, so '' is returned.
        """
        epub = _make_epub(tmp_path, name="htmlcov2.epub", content_opf=_opf_html_cover())
        f = _make_file_obj(epub, ".epub")
        result = kce.get_novel_cover_path(f)
        assert result == ""

    def test_epub_url_encoded_image_cover_returns_basename(self, tmp_path):
        """URL-encoded cover href: after decoding it should be a .jpg → basename returned."""
        encoded_opf = _opf_with_cover(cover_href="images/cover%20main.jpg")
        epub = _make_epub(tmp_path, name="urlenc2.epub", content_opf=encoded_opf)
        f = _make_file_obj(epub, ".epub")
        result = kce.get_novel_cover_path(f)
        assert result == "cover main.jpg"

    def test_return_type_is_str(self, tmp_path):
        """get_novel_cover_path always returns str (never None)."""
        epub = _make_epub(tmp_path, name="rettype.epub", content_opf=_opf_with_cover())
        f = _make_file_obj(epub, ".epub")
        result = kce.get_novel_cover_path(f)
        assert type(result) is str

    def test_return_empty_str_on_no_cover(self, tmp_path):
        """get_novel_cover_path returns '' (empty str), never None, on failure."""
        epub = _make_epub(tmp_path, name="empty2.epub", content_opf=_opf_without_cover())
        f = _make_file_obj(epub, ".epub")
        result = kce.get_novel_cover_path(f)
        assert result == ""
        assert result is not None


# ---------------------------------------------------------------------------
# TestParseHtmlTags — direct BS4 helper
# ---------------------------------------------------------------------------

class TestParseHtmlTags:
    """Pin parse_html_tags behaviour (BeautifulSoup html.parser backend)."""

    def test_basic_xml_tag_extraction(self):
        """Each tag name becomes a key; get_text() is the value."""
        html = b"<root><title>Hello</title></root>"
        warnings.filterwarnings("ignore")
        result = kce.parse_html_tags(html)
        assert isinstance(result, dict)
        assert result["title"] == "Hello"

    def test_meta_self_closing_tag_has_empty_value(self):
        """Self-closing tags like <meta .../> have empty string text content."""
        html = b'<root><meta name="cover" content="img"/></root>'
        warnings.filterwarnings("ignore")
        result = kce.parse_html_tags(html)
        assert result["meta"] == ""

    def test_opf_dc_title_extracted(self):
        """dc:title tags (which use colons) are extracted with their qualified name."""
        html = b"<metadata><dc:title>My Book</dc:title></metadata>"
        warnings.filterwarnings("ignore")
        result = kce.parse_html_tags(html)
        assert result["dc:title"] == "My Book"

    def test_returns_dict(self):
        """Return type is plain dict."""
        html = b"<root><a>1</a></root>"
        warnings.filterwarnings("ignore")
        result = kce.parse_html_tags(html)
        assert type(result) is dict

    def test_empty_bytes_returns_empty_dict(self):
        """Empty bytes input → empty dict (no tags to find)."""
        warnings.filterwarnings("ignore")
        result = kce.parse_html_tags(b"")
        assert result == {}

    def test_repeated_tag_name_last_value_wins(self):
        """When the same tag appears multiple times, the last text value is stored.

        FLAG: parse_html_tags uses a dict comprehension, so repeated tag names
        collide and the last occurrence wins.
        """
        html = b"<root><item>first</item><item>second</item></root>"
        warnings.filterwarnings("ignore")
        result = kce.parse_html_tags(html)
        # FLAG: dict comprehension = last item's text wins
        assert result["item"] == "second"
