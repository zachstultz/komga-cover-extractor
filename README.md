# Komga-Cover-Extractor
A python automation script that detects and extracts the cover from your cbz and epub files for each individal volume. 
Then takes the cover from the first volume and copies that as a cover file for your overall collection.

Allowing the user to use local high-resolution covers within Komga instead of the compressed versions that Komga generates.

Primary usage is with https://github.com/gotson/komga, **with volume releases**.

## Cover Detection
Cover-string detection is based on various scene releases, if none are detected, it will default to the first image. Which, unless you have scans from online, will almost always be the cover.

## Finished Result EX:
![Screen Shot 2021-11-06 at 11 46 38 AM](https://user-images.githubusercontent.com/8385256/140617357-245cb8e1-0622-45f3-be0b-291dfadcf8a7.png)

## Usage
1. Clone or download repository.
2. Run ```pip3 install -r requirements.txt```
3. Add desired paths that you want scanned into the paths string array at the top of komga-cover-extractor.py
![Screen Shot 2021-12-09 at 11 28 29 AM (1)](https://user-images.githubusercontent.com/8385256/145447043-150a9a96-f85b-4304-94f1-29b71383156b.png)
5. Run komga-cover-extractor.py ```python3 komga-cover-extractor.py```

## Contact
Discord: HCAZ#0665
