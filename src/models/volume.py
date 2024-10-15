class Volume:
    def __init__(self, file_type, series_name, shortened_series_name, volume_year, volume_number, volume_part, index_number, release_group, name, extensionless_name, basename, extension, root, path, extensionless_path, extras, publisher, is_premium, subtitle, header_extension, multi_volume=None, is_one_shot=None):
        self.file_type = file_type
        self.series_name = series_name
        self.shortened_series_name = shortened_series_name
        self.volume_year = volume_year
        self.volume_number = volume_number
        self.volume_part = volume_part
        self.index_number = index_number
        self.release_group = release_group
        self.name = name
        self.extensionless_name = extensionless_name
        self.basename = basename
        self.extension = extension
        self.root = root
        self.path = path
        self.extensionless_path = extensionless_path
        self.extras = extras
        self.publisher = publisher
        self.is_premium = is_premium
        self.subtitle = subtitle
        self.header_extension = header_extension
        self.multi_volume = multi_volume
        self.is_one_shot = is_one_shot

    def __str__(self):
        return f"Volume(series_name={self.series_name}, volume_number={self.volume_number}, file_type={self.file_type})"

    def __repr__(self):
        return str(self)
