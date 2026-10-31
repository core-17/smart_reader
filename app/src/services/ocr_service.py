import difflib
import logging
import os
import time
from functools import lru_cache

os.environ["ORT_DISABLE_THREAD_AFFINITY"] = "1"
os.environ["OMP_NUM_THREADS"] = "4"

import cv2
import httpx
import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR

from core.config import settings

logger = logging.getLogger("smart_reader.ocr")

DPI = 200
MIN_NATIVE_CHARS = 40
ALLOWED_LANGS = {"eng", "ukr", "ukr+eng", "eng+ukr"}

_rapid_engine: RapidOCR | None = None


def get_rapid_engine() -> RapidOCR:
    global _rapid_engine
    if _rapid_engine is None:
        logger.info("Ініціалізація RapidOCR (DBNet)...")
        _rapid_engine = RapidOCR(
            det_db_box_thresh=0.35,
            det_db_unclip_ratio=1.6,
        )
    return _rapid_engine


@lru_cache(maxsize=1)
def get_available_ocr_languages() -> list[str]:
    return ["eng", "ukr", "ukr+eng"]


def resize_image_for_vlm(img_bytes: bytes, max_dim: int = 1120) -> bytes:
    """Зменшує роздільність картинки для VLM, щоб уникнути переповнення токенів і таймауту."""
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    _, encoded = cv2.imencode(".png", img)
    return encoded.tobytes()


def extract_gemma_lines(img_bytes: bytes, model_name: str | None = None) -> tuple[list[str], float]:
    """Отримує чистий список рядків від Gemma 4 через локальну Ollama з оптимізованим розміром кадру."""
    target_model = model_name or settings.OLLAMA_MODEL
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    # Зменшуємо кадр перед відправкою у VLM
    vlm_img_bytes = resize_image_for_vlm(img_bytes)

    prompt = (
        "Perform exact OCR on this image. Extract ALL printed text precisely as written. "
        "Pay special attention to book titles, logos, subtitles, and character profile speech boxes. "
        "Output ONLY raw extracted lines from top to bottom. Do not describe the image. No preamble."
    )

    t0 = time.perf_counter()
    raw_text = ""

    try:
        import ollama

        client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        res = client.chat(
            model=target_model,
            messages=[{"role": "user", "content": prompt, "images": [vlm_img_bytes]}],
            options={"temperature": 0.0, "num_ctx": 8192},
        )
        raw_text = res.get("message", {}).get("content", "").strip()
    except Exception:
        import base64

        img_b64 = base64.b64encode(vlm_img_bytes).decode("utf-8")
        payload = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
            "options": {"temperature": 0.0, "num_ctx": 8192},
            "stream": False,
        }
        try:
            # Збільшено таймаут до 180 секунд
            with httpx.Client(timeout=180.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                raw_text = resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error("Помилка звернення до Ollama (%s): %s", target_model, e)
            return [], time.perf_counter() - t0

    elapsed = time.perf_counter() - t0
    clean_lines = []
    for line in raw_text.splitlines():
        l = line.strip().lstrip("-*•0123456789. ")
        if l and not l.lower().startswith("here is") and not l.lower().startswith("the image"):
            clean_lines.append(l)

    return clean_lines, elapsed


def match_and_align_words(rapid_results: list, gemma_lines: list[str]) -> list:
    """Зіставляє геометрію боксів RapidOCR із семантично точним текстом Gemma 4."""
    if not gemma_lines:
        return [(b, t, s) for b, t, s in rapid_results]

    full_gemma_blob = " ".join(gemma_lines).lower()
    corrected_boxes = []

    for bbox, r_text, score in rapid_results:
        clean_r = r_text.strip()
        if not clean_r:
            continue

        best_candidate = clean_r
        highest_ratio = 0.0

        for g_line in gemma_lines:
            ratio = difflib.SequenceMatcher(None, clean_r.lower(), g_line.lower()).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                if ratio > 0.45 and len(g_line) <= len(clean_r) * 2.2:
                    best_candidate = g_line

        if score < 0.90:
            for g_word in full_gemma_blob.split():
                w_ratio = difflib.SequenceMatcher(None, clean_r.lower(), g_word.strip(",.!?\"'")).ratio()
                if w_ratio > 0.70 and len(clean_r) >= 3:
                    best_candidate = g_word.strip(",.!?\"'")
                    highest_ratio = max(highest_ratio, w_ratio)
                    break

        final_text = best_candidate if (score < 0.90 and highest_ratio > 0.50) else clean_r
        corrected_boxes.append((bbox, final_text, score))

    return corrected_boxes


def render_invisible_layer(page, matched_boxes: list, scale_x: float, scale_y: float) -> None:
    """Накладає шар тексту за точними координатами (render_mode=3)."""
    for bbox, text, _ in matched_boxes:
        if not text.strip():
            continue

        pts = np.array(bbox, dtype=np.float32)
        x0 = float(pts[:, 0].min() * scale_x)
        y0 = float(pts[:, 1].min() * scale_y)
        x1 = float(pts[:, 0].max() * scale_x)
        y1 = float(pts[:, 1].max() * scale_y)

        box_h = max(y1 - y0, 6.0)
        fontsize = max(box_h * 0.75, 4.0)
        baseline_y = y1 - (box_h * 0.18)
        origin = pymupdf.Point(x0, baseline_y)

        page.insert_text(
            origin,
            text,
            fontsize=fontsize,
            fontname="helv",
            render_mode=3,
        )


def process_pdf_with_ocr(pdf_bytes: bytes, lang: str = "ukr+eng", dpi: int = DPI) -> bytes:
    """Повний цикл гібридного OCR з динамічним підключенням Gemma 4."""
    if lang not in ALLOWED_LANGS:
        raise ValueError(f"Непідтримувана мова: {lang}")

    src_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out_doc = pymupdf.open()
    rapid = get_rapid_engine()

    try:
        total_pages = len(src_doc)
        logger.info(
            "Початок гібридного OCR: %d сторінок | Модель VLM: %s | URL: %s",
            total_pages,
            settings.OLLAMA_MODEL,
            settings.OLLAMA_BASE_URL,
        )

        processed_ocr_count = 0
        skipped_count = 0
        t_start = time.perf_counter()

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = src_doc[page_idx]
            native_text = page.get_text().strip()

            # 1. Пропуск цифрових сторінок
            if len(native_text) > MIN_NATIVE_CHARS:
                out_doc.insert_pdf(src_doc, from_page=page_idx, to_page=page_idx)
                skipped_count += 1
                logger.info("[%03d/%03d] [ПРОПУСК] Текст уже присутній (%d симв.)", page_num, total_pages, len(native_text))
                continue

            processed_ocr_count += 1
            logger.info("[%03d/%03d] [ГРАФІКА] Обробка сторінки...", page_num, total_pages)

            # Рендеринг зображення
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
            img_bytes = pix.tobytes("png")
            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

            # 2. Швидкий прогін RapidOCR
            t_rapid = time.perf_counter()
            rapid_results, _ = rapid(img_bgr)
            elapsed_rapid = time.perf_counter() - t_rapid
            rapid_results = rapid_results or []

            scores = [float(item[2]) for item in rapid_results] if rapid_results else []
            min_score = min(scores) if scores else 1.0

            # 3. Виклик Gemma 4 тільки за необхідності (обкладинка або низька впевненість RapidOCR)
            need_vlm = (page_num == 1) or (min_score < 0.88)
            gemma_lines = []

            if need_vlm and rapid_results:
                logger.info("[%03d/%03d]  ├── Низька впевненість (%.2f). Запуск Gemma 4...", page_num, total_pages, min_score)
                gemma_lines, elapsed_gemma = extract_gemma_lines(img_bytes, settings.OLLAMA_MODEL)
                logger.info("[%03d/%03d]  ├── Gemma 4: вилучено %d рядків за %.2f с", page_num, total_pages, len(gemma_lines), elapsed_gemma)
            else:
                logger.info("[%03d/%03d]  ├── RapidOCR впорався самостійно (%d боксів, %.2f с, min_score=%.2f)", page_num, total_pages, len(rapid_results), elapsed_rapid, min_score)

            # 4. Зіставлення результатів
            matched_boxes = match_and_align_words(rapid_results, gemma_lines)

            # 5. Створення сторінки
            p_final = out_doc.new_page(width=page.rect.width, height=page.rect.height)
            p_final.insert_image(p_final.rect, stream=img_bytes)

            scale_x = page.rect.width / pix.width
            scale_y = page.rect.height / pix.height
            render_invisible_layer(p_final, matched_boxes, scale_x, scale_y)

        elapsed_total = time.perf_counter() - t_start
        logger.info(
            "Гібридний OCR завершено за %.1f с! (Оброблено: %d, Пропущено цифрових: %d)",
            elapsed_total,
            processed_ocr_count,
            skipped_count,
        )

        return out_doc.tobytes(garbage=4, deflate=True)
    finally:
        out_doc.close()
        src_doc.close()