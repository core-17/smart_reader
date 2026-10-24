import pymupdf
import pytesseract
from PIL import Image, ImageOps, ImageFilter

ALLOWED_LANGS = {"eng", "ukr", "ukr+eng", "eng+ukr"}


def get_available_ocr_languages() -> list[str]:
    try:
        langs = pytesseract.get_languages(config="")
        return [l for l in langs if l != "osd"]
    except Exception:
        return ["eng", "ukr"]


def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img)
    contrasted = ImageOps.autocontrast(gray, cutoff=1)
    return contrasted.filter(ImageFilter.SHARPEN)


def process_pdf_with_ocr(pdf_bytes: bytes, lang: str = "ukr+eng", dpi: int = 300) -> bytes:
    if lang not in ALLOWED_LANGS:
        lang = "ukr+eng"

    src_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out_doc = pymupdf.open()
    tesseract_config = r"--oem 3 --psm 3"

    try:
        for page_num in range(len(src_doc)):
            page = src_doc[page_num]
            existing_text = page.get_text().strip()

            if len(existing_text) > 20:
                out_doc.insert_pdf(src_doc, from_page=page_num, to_page=page_num)
            else:
                pix = page.get_pixmap(dpi=dpi)
                raw_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                clean_img = preprocess_image_for_ocr(raw_img)

                ocr_pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    clean_img,
                    lang=lang,
                    extension="pdf",
                    config=tesseract_config,
                )
                ocr_page_doc = pymupdf.open("pdf", ocr_pdf_bytes)
                out_doc.insert_pdf(ocr_page_doc)
                ocr_page_doc.close()

        return out_doc.tobytes(garbage=4, deflate=True)
    finally:
        out_doc.close()
        src_doc.close()
