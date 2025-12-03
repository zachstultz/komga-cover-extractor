from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path as PathlibPath
from typing import Any, List, Optional, Sequence, Union


Number = Union[int, float]
NumberSequence = Sequence[Number]
VolumeNumber = Union[Number, List[Number], str, None]


@dataclass
class LibraryType:
    name: str
    extensions: Sequence[str]
    must_contain: Sequence[str]
    must_not_contain: Sequence[str]
    match_percentage: int = 90

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return (
            f"LibraryType(name={self.name}, extensions={self.extensions}, "
            f"must_contain={self.must_contain}, must_not_contain={self.must_not_contain}, "
            f"match_percentage={self.match_percentage})"
        )

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return str(self)


@dataclass
class Folder:
    root: str
    dirs: List[str]
    basename: str
    folder_name: str
    files: List[Union[str, PathlibPath]]

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return (
            f"Folder(root={self.root}, dirs={self.dirs}, basename={self.basename}, "
            f"folder_name={self.folder_name}, files={self.files})"
        )

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return str(self)


@dataclass
class Publisher:
    from_meta: Optional[str]
    from_name: Optional[str]

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return f"Publisher(from_meta={self.from_meta}, from_name={self.from_name})"

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return str(self)


@dataclass
class File:
    name: str
    extensionless_name: str
    basename: str
    extension: str
    root: str
    path: str
    extensionless_path: str
    volume_number: VolumeNumber
    file_type: str
    header_extension: Optional[str] = None
    release_group: Optional[str] = None
    extras: Optional[Union[str, List[str]]] = None
    publisher: Optional[Publisher] = None
    is_premium: Optional[bool] = None
    subtitle: Optional[str] = None
    index_number: Optional[Union[Number, NumberSequence, str]] = None
    volume_part: Optional[Union[Number, str]] = None
    multi_volume: Optional[bool] = None
    is_one_shot: Optional[bool] = None
    shortened_series_name: Optional[str] = None
    series_name: Optional[str] = None


@dataclass
class Volume:
    file_type: str
    series_name: str
    shortened_series_name: Optional[str]
    volume_year: Optional[Union[str, int]]
    volume_number: VolumeNumber
    volume_part: Optional[Union[Number, str]]
    index_number: Optional[Union[Number, NumberSequence, str]]
    release_group: Optional[str]
    name: str
    extensionless_name: str
    basename: str
    extension: str
    root: str
    path: str
    extensionless_path: str
    extras: List[str] = field(default_factory=list)
    publisher: Optional[Publisher] = None
    is_premium: Optional[bool] = None
    subtitle: Optional[str] = None
    header_extension: Optional[str] = None
    multi_volume: Optional[bool] = None
    is_one_shot: Optional[bool] = None


@dataclass
class TypedPath:
    path: str
    path_formats: Sequence[str]
    path_extensions: Sequence[str]
    library_types: Sequence[LibraryType]
    translation_source_types: Sequence[str]
    source_languages: Sequence[str]

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return (
            f"Path(path={self.path}, path_formats={self.path_formats}, "
            f"path_extensions={self.path_extensions}, "
            f"library_types={self.library_types}, "
            f"translation_source_types={self.translation_source_types}, "
            f"source_languages={self.source_languages})"
        )

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return str(self)


@dataclass
class Embed:
    embed: Any
    file: Any = None


@dataclass
class KomgaLibrary:
    id: str
    name: str
    root: str

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return f"KomgaLibrary(id={self.id}, name={self.name}, root={self.root})"

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return str(self)


@dataclass
class RankedKeywordResult:
    total_score: float
    keywords: Sequence[Any]

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return f"Total Score: {self.total_score}\nKeywords: {self.keywords}"

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return str(self)


@dataclass
class UpgradeResult:
    is_upgrade: bool
    downloaded_ranked_result: RankedKeywordResult
    current_ranked_result: RankedKeywordResult

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return (
            "Is Upgrade: "
            f"{self.is_upgrade}\nDownloaded Ranked Result: {self.downloaded_ranked_result}\n"
            f"Current Ranked Result: {self.current_ranked_result}"
        )

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return str(self)


@dataclass
class Result:
    dir: str
    score: float

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return f"dir: {self.dir}, score: {self.score}"

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return str(self)


@dataclass
class NewReleaseNotification:
    number: int
    title: str
    color: Any
    fields: Sequence[dict]
    webhook: Optional[str]
    series_name: str
    volume_obj: Volume


@dataclass
class IdentifierResult:
    series_name: str
    identifiers: Sequence[str]
    path: str
    matches: Sequence[Any]


@dataclass
class BookwalkerBook:
    title: str
    original_title: Optional[str]
    volume_number: Optional[VolumeNumber]
    part: Optional[str]
    date: Optional[str]
    is_released: bool
    price: Optional[str]
    url: Optional[str]
    thumbnail: Optional[str]
    book_type: Optional[str]
    description: Optional[str]
    preview_image_url: Optional[str]


@dataclass
class BookwalkerSeries:
    title: str
    books: Sequence[BookwalkerBook]
    book_count: int
    book_type: Optional[str]


@dataclass
class Image_Result:
    ssim_score: float
    image_source: str


__all__ = [
    "BookwalkerBook",
    "BookwalkerSeries",
    "Embed",
    "Folder",
    "IdentifierResult",
    "Image_Result",
    "KomgaLibrary",
    "LibraryType",
    "NewReleaseNotification",
    "Publisher",
    "RankedKeywordResult",
    "Result",
    "TypedPath",
    "UpgradeResult",
    "Volume",
    "File",
]
