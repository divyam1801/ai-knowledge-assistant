from pathlib import Path

from PIL import Image


def extract_text_from_image(file_path: str | Path) -> str:
    import pytesseract

    image = Image.open(file_path)
    return pytesseract.image_to_string(image)
