import cv2
import numpy as np
import os
import shutil
from typing import List, Tuple, Dict
from pytesseract import Output
import pytesseract
from pdf2image import convert_from_path
import frappe


# ===============================================================
# 🔹 Funkcja pomocnicza do wykrywania ścieżki Tesseract
# ===============================================================
def _resolve_tesseract_path() -> str:
    """Locate the Tesseract executable and configure pytesseract accordingly."""
    configured_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    resolved_cmd = shutil.which(configured_cmd)
    if resolved_cmd:
        pytesseract.pytesseract.tesseract_cmd = resolved_cmd
        return resolved_cmd

    candidates = [
        os.environ.get("TESSERACT_CMD"),
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]

    for candidate in candidates:
        if not candidate:
            continue
        expanded = os.path.expanduser(os.path.expandvars(candidate))
        if os.path.isfile(expanded):
            pytesseract.pytesseract.tesseract_cmd = expanded
            return expanded
        resolved = shutil.which(expanded)
        if resolved:
            pytesseract.pytesseract.tesseract_cmd = resolved
            return resolved

    raise RuntimeError(
        "Tesseract OCR executable not found. Install it from "
        "https://github.com/UB-Mannheim/tesseract/wiki and/or set the "
        "TESSERACT_CMD environment variable."
    )


# ===============================================================
# 🔹 Główna klasa OCR — uproszczona, bez wywołania main()
# ===============================================================
class DocumentRegionDetector:
    """Detector for identifying and reading structured insurance PDF documents."""

    def __init__(self, input_path: str, poppler_path: str = None):
        self.input_path = input_path
        self.poppler_path = poppler_path
        self.image_path = None
        self.original = None
        self.processed = None
        self.regions = []

    # -----------------------------------------------------------
    def load_image(self):
        """Ładuje obraz – jeśli PDF, konwertuje do JPG."""
        if self.input_path.lower().endswith(".pdf"):
            pages = convert_from_path(self.input_path, dpi=200, poppler_path=self.poppler_path)
            self.image_path = frappe.generate_hash(length=10) + "_page1.jpg"
            pages[0].save(self.image_path, "JPEG")
        else:
            self.image_path = self.input_path

        self.original = cv2.imread(self.image_path)
        if self.original is None:
            raise ValueError(f"Nie można wczytać obrazu z {self.image_path}")
        return self.original

    # -----------------------------------------------------------
    def preprocess_image(self) -> np.ndarray:
        """Podstawowe czyszczenie obrazu dla lepszego OCR."""
        denoised = cv2.fastNlMeansDenoisingColored(self.original, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21)
        gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
        
        # blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=1)
        self.processed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel, iterations=2)
        return self.processed

    # -----------------------------------------------------------
    def detect_regions(self, min_area: int = 1000, max_area_ratio: float = 0.5, padding: int = 5) -> List[Dict]:
        """Znajduje większe sekcje dokumentu (ramki tekstowe)."""
        if self.processed is None:
            raise ValueError("Call preprocess_image() before detect_regions().")

        contours, _ = cv2.findContours(self.processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        image_height, image_width = self.processed.shape[:2]
        image_area = image_height * image_width

        regions = []
        for idx, contour in enumerate(contours):
            contour_area = cv2.contourArea(contour)
            if contour_area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            bounding_area = w * h
            if bounding_area > image_area * max_area_ratio:
                continue
            x1, y1 = max(x - padding, 0), max(y - padding, 0)
            x2, y2 = min(x + w + padding, image_width), min(y + h + padding, image_height)
            regions.append({"id": idx, "bbox": (x1, y1, x2 - x1, y2 - y1)})
        regions.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))
        self.regions = regions
        return regions

    # -----------------------------------------------------------
    def assign_labels_by_keywords(self, lang='pol+eng') -> List[Dict]:
        """Przypisuje etykiety na podstawie OCR i słów kluczowych."""
        _resolve_tesseract_path()

        label_keywords = {
            "Dane polisy": [ "numer polisy", "data polisy", "Dane", "polisy"],
            "Ubezpieczajacy": ["ubezpieczający", "ubezpieczenia"],
            "Wlasciciel pojazdu": ["właściciel", "pojazdu", "posiadacz","REGON"],
            "Ubezpieczony pojazd": ["ubezpieczony", "pojazd", "marka", "model", "rejestracja"],
            "Leasingodawca": ["leasingodawca","Leasingodawca"],
            "Leasingobiorca": ["leasingobiorca", "DANE KLIENTA"],
            "Platnosci": ["Płatności", "składka", "Platnosci", "platnosc", "odbiorca", "kwota", "płatność"],

        }

        for region in self.regions:
            x, y, w, h = region['bbox']
            roi = self.original[y:y + h, x:x + w]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(gray, lang=lang).lower()
            region['ocr_text'] = text.strip()
            best_label = None
            for label, keywords in label_keywords.items():
                if any(kw in text for kw in keywords):
                    best_label = label
                    break
            region['label'] = best_label if best_label else f"Region_{region['id']}"
        return self.regions

    # -----------------------------------------------------------
    def read_text_from_regions_enhanced(self, lang='pol+eng', scale_factor=2.0) -> List[Dict]:
        """Czyta tekst z każdej sekcji po wstępnym przetworzeniu."""
        _resolve_tesseract_path()
        extracted_texts = []
        for region in self.regions:
            x, y, w, h = region['bbox']
            roi = self.original[y:y + h, x:x + w]
            if scale_factor != 1.0:
                roi = cv2.resize(roi, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            denoised = cv2.bilateralFilter(gray, 9, 75, 75)
            cleaned = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            text = pytesseract.image_to_string(cleaned, lang=lang).strip()
            extracted_texts.append({"label": region.get("label", f"region_{region['id']}"), "text": text})
        return extracted_texts
