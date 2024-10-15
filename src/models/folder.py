class Folder:
    def __init__(self, root, dirs, basename, folder_name, files):
        self.root = root
        self.dirs = dirs
        self.basename = basename
        self.folder_name = folder_name
        self.files = files

    def __str__(self):
        return f"Folder(root={self.root}, dirs={self.dirs}, basename={self.basename}, folder_name={self.folder_name}, files={self.files})"

    def __repr__(self):
        return str(self)
