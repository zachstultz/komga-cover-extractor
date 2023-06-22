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

## Instructions
1. Run ```git clone https://github.com/zachstultz/komga-cover-extractor.git``` or download the repository up above.
2. Run ```pip3 install -r requirements.txt```
3. (OPTIONAL) (IGNORE IF ALL YOU INTEND TO USE IS COVER EXTRACTION) (ONLY REQUIRED FOR OPT RAR FEATURES)
    - Install unrar 
      - Linux: ```sudo apt-get install unrar```
      - MacOS: ```brew install unrar``` (untested)
      - Windows: Install UnRAR.dll from https://www.rarlab.com/rar_add.htm (untested)
4. Read usage below and enjoy!

## Usage
```
usage: komga_cover_extractor.py [-h] [-p [PATHS [PATHS ...]]] [-wh [WEBHOOK [WEBHOOK ...]]] [-c COMPRESS] [-cq COMPRESS_QUALITY]

Scans for covers in the zip, cbz, and epub files.

optional arguments:
  -h, --help            show this help message and exit
  -p [PATHS [PATHS ...]], --paths [PATHS [PATHS ...]]
                        The path/paths to be scanned for cover extraction.
  -wh [WEBHOOK [WEBHOOK ...]], --webhook [WEBHOOK [WEBHOOK ...]]
                        The optional discord webhook url for notifications about changes and errors.
  -c COMPRESS, --compress COMPRESS
                        Whether or not to compress the extracted cover images.
  -cq COMPRESS_QUALITY, --compress_quality COMPRESS_QUALITY
                        The quality of the compressed cover images.
```
## Examples
with compression :
  
  &nbsp;&nbsp;&nbsp;```python3 komga_cover_extractor.py -p "/path/to/manga" -p "/path/to/novels" -c "True" -cq "60"```

without compression example:
  
  &nbsp;&nbsp;&nbsp;```python3 komga_cover_extractor.py -p "/path/to/manga" -p "/path/to/novels"```

## Goals
1. Transform script into manga/light novel manager with many features that includes cover extraction, but is not exclusive to it. ***(in-progress)***
2. Modularize volume/chapter keyword regexes across the script. ***(in-progress)***
3. Better documentation. ***(in-progress)***

