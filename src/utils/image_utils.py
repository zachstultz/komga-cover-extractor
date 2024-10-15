import io
import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from src.config import *

def compress_image(image_path, quality=60, to_jpg=False, raw_data=None):
    new_filename = None
    buffer = None
    save_format = "JPEG"

    # Load the image from the file or raw data
    image = Image.open(image_path if not raw_data else io.BytesIO(raw_data))

    # Convert the image to RGB if it has an alpha channel or uses a palette
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    filename, ext = os.path.splitext(image_path)

    if ext == ".webp":
        save_format = "WEBP"

    # Determine the new filename for the compressed image
    if not raw_data:
        if to_jpg or ext.lower() == ".png":
            ext = ".jpg"
            if not to_jpg:
                to_jpg = True
        new_filename = f"{filename}{ext}"

    # Try to compress and save the image
    try:
        if not raw_data:
            image.save(new_filename, format=save_format, quality=quality, optimize=True)
        else:
            buffer = io.BytesIO()
            image.save(buffer, format=save_format, quality=quality)
            return buffer.getvalue()
    except Exception as e:
        # Log the error and continue
        send_message(f"Failed to compress image {image_path}: {e}", error=True)

    # Remove the original file if it's a PNG that was converted to JPG
    if to_jpg and ext.lower() == ".jpg" and os.path.isfile(image_path):
        os.remove(image_path)

    # Return the path to the compressed image file, or the compressed image data
    return new_filename if not raw_data else buffer.getvalue()

def prep_images_for_similarity(blank_image_path, internal_cover_data, both_cover_data=False, silent=False):
    def resize_images(img1, img2, desired_width=400, desired_height=600):
        img1_resized = cv2.resize(img1, (desired_width, desired_height), interpolation=cv2.INTER_AREA)
        img2_resized = cv2.resize(img2, (desired_width, desired_height), interpolation=cv2.INTER_AREA)
        return img1_resized, img2_resized

    def match_image_channels(img1, img2):
        if len(img1.shape) == 3 and len(img2.shape) == 3:
            min_channels = min(img1.shape[2], img2.shape[2])
            img1, img2 = img1[:, :, :min_channels], img2[:, :, :min_channels]
        elif len(img1.shape) == 3 and len(img2.shape) == 2:
            img1 = img1[:, :, 0]
        elif len(img1.shape) == 2 and len(img2.shape) == 3:
            img2 = img2[:, :, 0]
        return img1, img2

    # Decode internal cover data
    internal_cover = cv2.imdecode(np.frombuffer(internal_cover_data, np.uint8), cv2.IMREAD_UNCHANGED)

    # Load blank image either from path or data buffer based on condition
    blank_image = cv2.imread(blank_image_path) if not both_cover_data else cv2.imdecode(np.frombuffer(blank_image_path, np.uint8), cv2.IMREAD_UNCHANGED)
    internal_cover = np.array(internal_cover)

    # Resize both images to 600x400
    blank_image, internal_cover = resize_images(blank_image, internal_cover)

    # Ensure both images have the same number of color channels
    blank_image, internal_cover = match_image_channels(blank_image, internal_cover)

    # Ensure both images are in the same format (grayscale or color)
    if len(blank_image.shape) != len(internal_cover.shape):
        if len(blank_image.shape) == 3:
            blank_image = cv2.cvtColor(blank_image, cv2.COLOR_BGR2GRAY)
        else:
            internal_cover = cv2.cvtColor(internal_cover, cv2.COLOR_BGR2GRAY)

    # Compare images and return similarity score
    score = compare_images(blank_image, internal_cover, silent=silent)

    return score

def compare_images(imageA, imageB, silent=False):
    try:
        if not silent:
            print(f"\t\t\tBlank Image Size: {imageA.shape}")
            print(f"\t\t\tInternal Cover Size: {imageB.shape}")

        # Preprocess images
        grayA = preprocess_image(imageA)
        grayB = preprocess_image(imageB)

        # Compute SSIM between the two images
        ssim_score = ssim(grayA, grayB, data_range=1.0)

        if not silent:
            print(f"\t\t\t\tSSIM: {ssim_score}")

        return ssim_score
    except Exception as e:
        send_message(str(e), error=True)
        return 0

def preprocess_image(image):
    # Check if the image is already grayscale
    if len(image.shape) == 2 or (len(image.shape) == 3 and image.shape[2] == 1):
        gray_image = image
    else:
        # Convert to grayscale if it's a color image
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply histogram equalization
    gray_image = cv2.equalizeHist(gray_image)

    # Normalize the image
    gray_image = gray_image / 255.0

    return gray_image

# Add other image utility functions here
