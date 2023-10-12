# Komga Cover Extractor
A python automation script that detects and extracts the cover from your zip, cbz, and epub files for each individual volume. 
Then takes the cover from the first volume and copies that as a cover file for your overall collection.

Allowing the user to use local high-resolution covers within Komga instead of the compressed versions that Komga generates.

Primary usage is with https://github.com/gotson/komga, **with volume-based releases**.

**There is no compression of the cover by default, see usage at the bottom for compressing the covers.**

## Cover Detection
Detection is based on various scene releases, if none are detected, it will default to the first image. Which, unless you have scans from the internet, it will almost always be the cover.

## Finished Result Example:
![image](https://user-images.githubusercontent.com/8385256/152403016-90660098-0b04-4178-babd-87e56ff1b390.png)

## Installation
To use the Komga Cover Extractor, you have several options:

1. **Docker (Recommended):** You can use the [Docker image available here](https://hub.docker.com/r/zachstultz/komga-cover-extractor), which simplifies the setup process.

2. **Manual Installation:** If you prefer manual installation, follow these steps:
   1. Clone the repository: `git clone https://github.com/zachstultz/komga-cover-extractor.git`
   2. Install required Python packages: `pip3 install -r requirements.txt`
   3. (OPTIONAL) If you intend to use advanced RAR features, you may need to install unrar:
      - Linux: `sudo apt-get install unrar`
      - MacOS: `brew install rar` (requires [brew](https://brew.sh/)) (untested)
      - Windows: Install UnRAR.dll from [rarlab.com](https://www.rarlab.com/rar_add.htm) (untested)

## Usage
The Komga Cover Extractor provides several options for cover extraction. Here's how to use it:

```
usage: komga_cover_extractor.py [-h] [-p [PATHS [PATHS ...]]] [-wh [WEBHOOK [WEBHOOK ...]]] [-c COMPRESS] [-cq COMPRESS_QUALITY]

Scans for covers in the zip, cbz, and epub files.

optional arguments:
  -h, --help            show this help message and exit
  -p [PATHS [PATHS ...]], --paths [PATHS [PATHS ...]]
                        The path/paths to be scanned for cover extraction.
  -wh [WEBHOOK [WEBHOOK ...]], --webhook [WEBHOOK [WEBHOOK ...]]
                        The optional Discord webhook URL for notifications about changes and errors.
  -c COMPRESS, --compress COMPRESS
                        Whether or not to compress the extracted cover images.
  -cq COMPRESS_QUALITY, --compress_quality COMPRESS_QUALITY
                        The quality of the compressed cover images.
```

## Examples
Here are a couple of usage examples:

- **With Compression:**
  ```
  python3 komga_cover_extractor.py -p "/path/to/manga" -p "/path/to/novels" -c "True" -cq "60"
  ```

- **Without Compression:**
  ```
  python3 komga_cover_extractor.py -p "/path/to/manga" -p "/path/to/novels"
  ```

## Future Goals
Our development team has ambitious plans for the Komga Cover Extractor, which include:

1. Transforming the script into a comprehensive manga/light novel manager with a wide range of features that include cover extraction but are not limited to it (in-progress).
2. Modularizing volume/chapter keyword regexes across the script (in-progress).
3. Improving documentation to make the tool even more user-friendly (in-progress).

For more information and updates, please refer to the [project's GitHub repository](https://github.com/zachstultz/komga-cover-extractor).

Feel free to choose the installation method that suits your needs, and enjoy the benefits of using the Komga Cover Extractor!

