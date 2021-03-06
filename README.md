# Komga-Cover-Extractor
A python automation script that detects and extracts the cover from your cbz and epub files for each individal volume. 
Then takes the cover from the first volume and copies that as a cover file for your overall collection.

Allowing the user to use local high-resolution covers within Komga instead of the compressed versions that Komga generates.

Primary usage is with https://github.com/gotson/komga, **with volume releases**.

**There is no compression of the cover by default, see usage at the bottom for compressing the covers.**

## Cover Detection
Detection is based on various scene releases, if none are detected, it will default to the first image. Which, unless you have scans from online, will almost always be the cover.

## Finished Result EX:
![image](https://user-images.githubusercontent.com/8385256/152403016-90660098-0b04-4178-babd-87e56ff1b390.png)

## Instructions
1. Run ```git clone https://github.com/zachstultz/komga-cover-extractor.git``` or download the repository up above.
2. Run ```pip3 install -r requirements.txt```
3. Read usage below and enjoy!

## Goals
1. Transform script into media manager with many features that includes cover extraction, but is not exclusive to it.
2. Modularize volume keyword regexes across the script.
3. Better documentation.

## Usage
```
usage: komga_cover_extractor.py [-h] [-p [PATHS [PATHS ...]]]
                                [-wh WEBHOOK] [-c COMPRESS] 
                                [-cq COMPRESS_QUALITY]

Scans for covers in the cbz and epub files.

optional arguments:
  -h, --help            show this help message and exit
  -p [PATHS [PATHS ...]], --paths [PATHS [PATHS ...]]
                        The path/paths to be scanned for cover extraction.
  -wh WEBHOOK, --webhook WEBHOOK
                        The discord webhook url for notifications about
                        changes and errors.
  -c COMPRESS, --compress COMPRESS
                        Whether or not to compress the extracted cover images.
  -cq COMPRESS_QUALITY, --compress_quality COMPRESS_QUALITY
                        The quality of the compressed cover images.
```
with compression:
  
  ```EX: python3 komga_cover_extractor.py -p "/path/to/manga" -p "/path/to/novels" -wh "WEBHOOK_URL" -c "True" -cq "60"```

without compression:
  
  ```EX: python3 komga_cover_extractor.py -p "/path/to/manga" -p "/path/to/novels" -wh "WEBHOOK_URL"```

