# Komga-Cover-Extractor
A python automation script that detects and extracts the cover from your cbz and epub files for each individal volume. 
Then takes the cover from the first volume and copies that as a cover file for your overall collection.

Allowing the user to use local high-resolution covers within Komga instead of the compressed versions that Komga generates.

Primary usage is with https://github.com/gotson/komga, **with volume releases**.

**There is no compression of the cover by default, so take that into account in-relation to your setup.
**
## Cover Detection
Cover-string detection is based on various scene releases, if none are detected, it will default to the first image. Which, unless you have scans from online, will almost always be the cover.

## Finished Result EX:
![image](https://user-images.githubusercontent.com/8385256/152403016-90660098-0b04-4178-babd-87e56ff1b390.png)

## Usage
1. Run ```git clone https://github.com/zachstultz/komga-cover-extractor.git``` or download the repository up above.
2. Run ```pip3 install -r requirements.txt```
3. Add desired paths that you want scanned into the paths string array at the top of komga-cover-extractor.py
![image](https://user-images.githubusercontent.com/8385256/152403252-8799fe4c-a5b0-4296-9d13-43728a060491.png)
5. Run ```python3 komga-cover-extractor.py```
