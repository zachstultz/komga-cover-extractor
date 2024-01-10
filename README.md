## Table of Contents
1. [Introduction](#1-introduction)
2. [Installation](#2-installation)
3. [Usage](#3-usage)
4. [Examples](#4-examples)
5. [Future Goals](#5-future-goals)
6. [Contributing](#6-contributing)
7. [License](#7-license)
8. [Support and Contact](#8-support-and-contact)

### 1. Introduction

```markdown
The Komga Cover Extractor is a Python automation script designed to enhance the user experience of Komga, a manga and light novel manager. This script automates the detection and extraction of covers from zip, cbz, and epub files, providing users with high-resolution local covers within Komga.
```

### 2. Installation

To use the Komga Cover Extractor, follow one of the options below:

### Docker (Recommended)
You can use the [Docker image available here](https://hub.docker.com/r/zachstultz/komga-cover-extractor), which simplifies the setup process.

### Manual Installation
If you prefer manual installation, follow these steps:
1. Clone the repository: `git clone https://github.com/zachstultz/komga-cover-extractor.git`
2. Install required Python packages: `pip3 install -r requirements.txt`
3. (OPTIONAL) If you intend to use advanced RAR features, you may need to install unrar:
   - Linux: `sudo apt-get install unrar`
   - MacOS: `brew install rar` (requires [brew](https://brew.sh/)) (untested)
   - Windows: Install UnRAR.dll from [rarlab.com](https://www.rarlab.com/rar_add.htm) (untested)

### 3. Usage
```bash
python3 komga_cover_extractor.py [-h] [-p [PATHS [PATHS ...]]] -wh WEBHOOK1,WEBHOOK2,upto N [-c COMPRESS] [-cq COMPRESS_QUALITY]
```

- `-p` or `--paths`: The path/paths to be scanned for cover extraction.
- `-wh` or `--webhook`: The optional Discord webhook URL for notifications about changes and errors.
- `-c` or `--compress`: Whether or not to compress the extracted cover images.
- `-cq` or `--compress_quality`: The quality of the compressed cover images.

### 4. Examples

- **With Compression:**
  ```bash
  python3 komga_cover_extractor.py -p "/path/to/manga" -p "/path/to/novels" -c "True" -cq "60"
  ```
  
- **Without Compression:**
  ```bash
  python3 komga_cover_extractor.py -p "/path/to/manga" -p "/path/to/novels"
  ```
### 5. Future Goals

```markdown
1. Transforming the script into a comprehensive manga/light novel manager with a wide range of features (in-progress).
2. Modularizing volume/chapter keyword regexes across the script (in-progress).
3. Improving documentation to make the tool even more user-friendly (in-progress).
```

### 6. Contributing

We welcome contributions! If you'd like to contribute to the Komga Cover Extractor, please follow our [Contribution Guidelines](CONTRIBUTING.md)

### 7. License

```markdown
This project is licensed under the [MIT License](LICENSE).
```

### 8. Support and Contact
```markdown

If you need help or want to report issues, please [create an issue](https://github.com/zachstultz/komga-cover-extractor/issues) on GitHub.
```
