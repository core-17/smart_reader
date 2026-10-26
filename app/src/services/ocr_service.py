import logging
from functools import lru_cache

import pymupdf
import pytesseract
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

ALLOWED_LANGS = {"eng", "ukr", "ukr+eng", "eng+ukr"}
TESSERACT_CONFIG = "--oem 3 --psm 3"
MIN_TEXT_CHARS = 20  # сторінка з меншою кількістю тексту вважається сканом


@lru_cache(maxsize=1)
def get_available_ocr_languages() -> list[str]:
    try:
        return [lang for lang in pytesseract.get_languages(config="") if lang != "osd"]
    except Exception:
        logger.warning("Tesseract недоступний", exc_info=True)
        return []


def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img)
    contrasted = ImageOps.autocontrast(gray, cutoff=1)
    return contrasted.filter(ImageFilter.SHARPEN)


def process_pdf_with_ocr(pdf_bytes: bytes, lang: str = "ukr+eng", dpi: int = 300) -> bytes:
    if lang not in ALLOWED_LANGS:
        raise ValueError(f"Unsupported OCR language: {lang}")

    src_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out_doc = pymupdf.open()

    try:
        for page_index in range(len(src_doc)):
            page = src_doc[page_index]

            if len(page.get_text().strip()) > MIN_TEXT_CHARS:
                out_doc.insert_pdf(src_doc, from_page=page_index, to_page=page_index)
                continue

            # csRGB + alpha=False гарантує 3 канали, незалежно від колірного простору сторінки
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
            raw_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            clean_img = preprocess_image_for_ocr(raw_img)

            ocr_pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                clean_img,
                lang=lang,
                extension="pdf",
                config=TESSERACT_CONFIG,
            )
            ocr_page_doc = pymupdf.open(stream=ocr_pdf_bytes, filetype="pdf")
            try:
                out_doc.insert_pdf(ocr_page_doc)
            finally:
                ocr_page_doc.close()

        return out_doc.tobytes(garbage=4, deflate=True)
    finally:
        out_doc.close()
        src_doc.close()