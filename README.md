# Komga-Cover-Extractor
A work-in-progress python automation script that detects and extracts the cover from your .cbz and .epub files for each individal volume. 
Then takes the cover from the first volume and copies that as a cover file for your overall collection.

Allowing the user to use local higher-resolution covers within Komga instead of the compressed versions that Komga generates.

Primary usage is with https://github.com/gotson/komga

## Cover Detection
Cover-string detection is based on various scene releases.

## Usuage
Add desired paths that you want scanned into the string array at the top of main.py.
Run main.py

## Goals
### IN-PROGRESS
1. Add remaining necessary exception checks.

### PLANNED
1. Rewrite all instances of an image file to use image_types array at the top of the file.
2. Allow choosing between cover or poster naming preference.
3. Replace current string-cover detection with regex.
4. Rework end-of-file stats.
6. Pretty up the text output.
7. Changable output folder for the extracted images.

## Contact
Discord: HCAZ#0665
