class Path:
    def __init__(
        self,
        path,
        path_formats=None,
        path_extensions=None,
        library_types=None,
        translation_source_types=None,
        source_languages=None
    ):
        self.path = path
        self.path_formats = path_formats or []
        self.path_extensions = path_extensions or []
        self.library_types = library_types or []
        self.translation_source_types = translation_source_types or []
        self.source_languages = source_languages or []

    def __str__(self):
        return f"Path(path={self.path}, path_formats={self.path_formats}, path_extensions={self.path_extensions}, library_types={self.library_types}, translation_source_types={self.translation_source_types}, source_languages={self.source_languages})"

    def __repr__(self):
        return str(self)
