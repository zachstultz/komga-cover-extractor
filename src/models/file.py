class File:
    def __init__(
        self,
        name,
        extensionless_name,
        basename,
        extension,
        root,
        path,
        extensionless_path,
        volume_number,
        file_type,
        header_extension,
    ):
        self.name = name
        self.extensionless_name = extensionless_name
        self.basename = basename
        self.extension = extension
        self.root = root
        self.path = path
        self.extensionless_path = extensionless_path
        self.volume_number = volume_number
        self.file_type = file_type
        self.header_extension = header_extension

    def __str__(self):
        return f"File(name={self.name}, extensionless_name={self.extensionless_name}, basename={self.basename}, extension={self.extension}, root={self.root}, path={self.path}, extensionless_path={self.extensionless_path}, volume_number={self.volume_number}, file_type={self.file_type}, header_extension={self.header_extension})"

    def __repr__(self):
        return str(self)
