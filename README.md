# Komga-Cover-Extractor
A python automation script that detects and extracts the cover from your cbz and epub files for each individal volume. 
Then takes the cover from the first volume and copies that as a cover file for your overall collection.

Allowing the user to use local high-resolution covers within Komga instead of the compressed versions that Komga generates.

Primary usage is with https://github.com/gotson/komga, **with volume releases**.

**There is no compression of the cover by default, so take that into account in-relation to your setup.**

## Cover Detection
Cover-string detection is based on various scene releases, if none are detected, it will default to the first image. Which, unless you have scans from online, will almost always be the cover.

## Finished Result EX:
![image](https://user-images.githubusercontent.com/8385256/152403016-90660098-0b04-4178-babd-87e56ff1b390.png)

## Instructions
1. Run ```git clone https://github.com/zachstultz/komga-cover-extractor.git``` or download the repository up above.
2. Run ```pip3 install -r requirements.txt```
3. Read usage below and enjoy!

## Usage
```
usage: komga_cover_extractor.py [-h] [-p [PATHS [PATHS ...]]]
                                [-df [DOWNLOAD_FOLDERS [DOWNLOAD_FOLDERS ...]]]
                                [-wh WEBHOOK]

Scans for covers in the cbz and epub files.

optional arguments:
  -h, --help            show this help message and exit
  -p [PATHS [PATHS ...]], --paths [PATHS [PATHS ...]]
                        The path/paths to be scanned for cover extraction.
  -df [DOWNLOAD_FOLDERS [DOWNLOAD_FOLDERS ...]], --download_folders [DOWNLOAD_FOLDERS [DOWNLOAD_FOLDERS ...]]
                        The download folder/download folders for processing,
                        renaming, and moving of downloaded files.
  -wh WEBHOOK, --webhook WEBHOOK
                        The discord webhook url for notifications about
                        changes and errors.
```
