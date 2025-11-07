import frappe
import os
import re
import datetime
import json
from .ocr import DocumentRegionDetector


# ===============================================================
# 🔹 OCR – przetwarzanie dokumentu
# ===============================================================

@frappe.whitelist()
def process_policy_file(docname):
    """Główna funkcja wywoływana przez after_insert / on_update."""
    try:
        doc = frappe.get_doc("Insurance Policy", docname)
        result = process_policy_file_internal(doc)
        return result
    except Exception as e:
        frappe.log_error(f"OCR Error (process_policy_file): {e!s}")
        return {f"error: {e!s}"}


@frappe.whitelist()
def process_policy_temp(data):
    """Tymczasowe przetwarzanie dokumentu przed zapisaniem (bez zapisu do bazy)."""
    try:
        doc_data = json.loads(data)
        file_url = doc_data.get("policy_fille")

        if not file_url:
            return {"error": "Brak pliku PDF do przetworzenia."}

        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_path = file_doc.get_full_path()

        if not os.path.exists(file_path):
            return {"error": f"Nie znaleziono pliku: {file_path}"}

        detector = DocumentRegionDetector(file_path)
        detector.load_image()
        detector.preprocess_image()
        detector.detect_regions(min_area=800, max_area_ratio=0.5, padding=10)
        detector.assign_labels_by_keywords(lang="pol+eng")
        texts = detector.read_text_from_regions_enhanced(lang="pol+eng", scale_factor=2.0)

        extracted_data = parse_ocr_results(texts)

        # 🔹 Normalizacja pól
        extracted_data["insurance_company"] = normalize_insurance_company(
            extracted_data.get("insurance_company")
        )
        extracted_data["client"] = ensure_client_exists(extracted_data.get("client"))
        extracted_data["vehicle"] = clean_vehicle_text(extracted_data.get("vehicle"))

        frappe.log_error(
            json.dumps(extracted_data, indent=2, ensure_ascii=False)[:4000],
            "OCR Extracted Data (TEMP)"
        )

        return {"success": True, "data": extracted_data}

    except Exception as e:
        frappe.log_error(f"TEMP OCR Error: {e!s}")
        return {f"error: {e!s}"}


def process_policy_file_internal(doc):
    """Pełne przetwarzanie OCR (bez automatycznego zapisu dokumentu)."""
    try:
        file_doc = frappe.get_doc("File", {"file_url": doc.policy_fille})
        file_path = file_doc.get_full_path()

        if not os.path.exists(file_path):
            frappe.throw(f"Nie znaleziono pliku: {file_path}")

        detector = DocumentRegionDetector(file_path)
        detector.load_image()
        detector.preprocess_image()
        detector.detect_regions(min_area=800, max_area_ratio=0.5, padding=10)
        detector.assign_labels_by_keywords(lang="pol+eng")
        texts = detector.read_text_from_regions_enhanced(lang="pol+eng", scale_factor=2.0)

        extracted_data = parse_ocr_results(texts)

        # 🔹 Normalizacja danych
        extracted_data["insurance_company"] = normalize_insurance_company(
            extracted_data.get("insurance_company")
        )
        extracted_data["client"] = ensure_client_exists(extracted_data.get("client"))
        extracted_data["vehicle"] = clean_vehicle_text(extracted_data.get("vehicle"))

        frappe.log_error(
            json.dumps(extracted_data, indent=2, ensure_ascii=False)[:4000],
            "OCR Extracted Data (SAVE PREVIEW)"
        )

        return {"success": True, "data": extracted_data}

    except Exception as e:
        frappe.log_error(f"OCR Processing Error: {e!s}")
        return {f"error: {e!s}"}


# ===============================================================
# 🔹 PARSOWANIE I NORMALIZACJA DANYCH
# ===============================================================

def parse_ocr_results(text_blocks):
    import re

    mapping = {
        "policy_number": ["numer polisy", "nr polisy", "policy no", "polisa nr", "nr umowy"],
        "insurance_company": [
            "pzu", "warta", "allianz", "generali", "link4", "axa", "uniqa", "compensa", "mtu"
        ],
        "coverage_start": [],
        # "coverage_end": [],
        "client": [
            "ubezpieczajacy", "klient", "nabywca", "ubezpieczony",
            "leasingobiorca", "dane klienta", "leasing", "spółka z ograniczoną odpowiedzialnością"
        ],
        "vehicle": ["pojazd", "samochód", "nr rejestracyjny", "rejestracyjny numer", "vin"],
    }

    extracted = {k: None for k in mapping.keys()}

    for block in text_blocks:
        # 🔹 Bezpieczna konwersja do stringa
        raw_text = block.get("text", "")
        raw_label = block.get("label", "")

        if isinstance(raw_text, (tuple, list)):
            raw_text = " ".join(str(x) for x in raw_text)
        if isinstance(raw_label, (tuple, list)):
            raw_label = " ".join(str(x) for x in raw_label)

        text = str(raw_text).lower().replace("\n", " ")
        label = str(raw_label).lower()

        # ---------------- DATY ----------------
        date_range = re.findall(
            r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*(?:r\.|roku)?\s*[–—-]\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
            text
        )
        if date_range:
            start, _ = date_range[0]
            extracted["coverage_start"] = normalize_date(start)
            # extracted["coverage_end"] = None
            continue

        # ---------------- NUMER POLISY ----------------
        if any(kw in text for kw in mapping["policy_number"]):
            numbers = re.findall(r"\b\d{8,12}\b", text)
            if numbers:
                # Prefer policy numbers starting with '1' or '5' due to common numbering conventions used by insurance companies.
                preferred = [n for n in numbers if n.startswith(('1', '5'))]
                extracted["policy_number"] = preferred[0] if preferred else numbers[0]
                continue

        # ---------------- POJAZD ----------------
        if any(kw in label for kw in ["pojazd", "samochód"]) or any(
            kw in text for kw in ["nr rejestracyjny", "vin", "marka", "model", "rok produkcji", "pojazd"]
        ):
            clean_text = re.sub(r"[\n\r,;]+", " ", text)
            clean_text = re.sub(r"\s{2,}", " ", clean_text)
            clean_text = clean_text.upper()

            # 🔹 Wstaw brakujące spacje po dwukropkach, np. "VIN:1C4R" → "VIN: 1C4R"
            clean_text = re.sub(r"([A-Z])(:)([A-Z0-9])", r"\1: \3", clean_text)
            print(f"Clean full vehicle text: {clean_text}")
                    # UBEZPIECZONY POJAZD NR REJESTRACYJNY: DW5WA06 MARKA: JEEP MODEL: GRAND CHEROKEE TYP: GRAND CHEROKEE ROK PRODUKCJI: 2020 VIN: 1.C4RJFBG8LC299113 POJEMNOŚĆ SILNIKA: 3604 CCM
                    #UBEZPIECZONY POJAZD NR REJESTRACYJNY: KK77794 MARKA: BMW MODEL: X1 [F48] 15-19 TYP: X1 XDRIVE25D M SPORT SPORT-AUT ROK PRODUKCJI: 2016 VIN: WBAHU510405E45525 POJEMNOŚĆ SILNIKA: 1995 CCM
            
            # 🔹 Wyszukaj pola niezależnie od kolejności
            # reg_match = re.search(
            #     r"(UBEZPIECZONY\s*POJAZD|NR\s*REJESTRACYJNY|REJESTRACYJNY: |UBEZPIECZONY POJAZD NR REJESTRACYJNY: )[:\s]*([A-Z]{1,3}\s?\d{4,5}[A-Z]{0,2})",
            #     clean_text
            # )
            marka_match = re.search(
                r"MARKA[:\s]*([A-Z0-9ĄĆĘŁŃÓŚŹŻ ]+?)(?=\s+(?:MODEL|TYP|ROK|VIN|POJEMNOŚĆ|$))",
                clean_text
            )
            model_match = re.search(
                r"MODEL[:\s]*([A-Z0-9ĄĆĘŁŃÓŚŹŻ ]+?)(?=\s+(?:TYP|ROK|VIN|POJEMNOŚĆ|$))",
                clean_text
            )
            rok_match = re.search(
                r"ROK\s*PRODUKCJI[:\s]*(\d{4})",
                clean_text
            )
            vin_match = re.search(
                r"VIN:\s*([A-Z0-9\.]+)",
                clean_text
            )

            # # 🔹 Zbuduj listę wartości
            values = []
            # if reg_match:
            #     values.append(reg_match.group(1).replace("", " "))
            #     print(f"Found registration: {reg_match.group(1)}")
            if marka_match:
                values.append(marka_match.group(1).strip())
                print(f"Found marka: {marka_match.group(1)}")
            if model_match:
                values.append(model_match.group(1).strip())
                print(f"Found model: {model_match.group(1)}")
            if rok_match:
                values.append(rok_match.group(1))
                print(f"Found rok: {rok_match.group(1)}")
            if vin_match:
                values.append(vin_match.group(1).strip())
                print(f"Found VIN: {vin_match.group(1)}")
            # # 🔹 Ustaw wynik
            if values:
                extracted["vehicle_type"] = ", ".join(values).replace('.', '')
                print(f"Vehicle extracted: {extracted['vehicle']}")
            else:
                extracted["vehicle"] = clean_text  # fallback – cały tekst
                print(f"Vehicle fallback text: {clean_text}")

            words_to_remove = [
                "UBEZPIECZONY POJAZD NR REJESTRACYJNY:",
                "ROK PRODUKCJI:",
                "MODEL:",
                # "MARKA:",
                "TYP:",
                "VIN:",
                "POJEMNOŚĆ SILNIKA:",
                "CCM"
            ]
            stop_words = ["MARKA:"]

            result = clean_text_advanced(clean_text, words_to_remove, stop_words)
            extracted["vehicle"] = result
            continue


        # ---------------- KLIENT ----------------
        if any(k in label for k in ["leasingobiorca", "ubezpieczajacy"]) and not extracted["client"]:
            clean_text = re.sub(r"\b(ubezpieczaj[ąacyi]+|regon|adres|telefon|nazwa|email)\b", "", text, flags=re.IGNORECASE)
            name_match = re.search(
                r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)+|[A-Z0-9ĄĆĘŁŃÓŚŹŻ\s\.,\-]+sp\. z o\.o\.)",
                clean_text,
                re.IGNORECASE
            )
            if name_match:
                name = name_match.group(1).strip().title()
                name = re.sub(r"\b(erp|leasing|ubezpieczający|właściciel|regon|adres|pzu|leasingodawca)\b", "", name, flags=re.IGNORECASE).strip()
                name = re.sub(r"\s{2,}", " ", name).strip()
                if len(name.split()) >= 2:
                    extracted["client"] = name
                    continue

        # ---------------- FIRMA UBEZPIECZENIOWA ----------------
        if not extracted["insurance_company"]:
            extracted["insurance_company"] = normalize_insurance_company(text)

    return extracted



# ===============================================================
# 🔹 FUNKCJE POMOCNICZE
# ===============================================================

def normalize_date(text):
    text = text.lower().replace("r.", "").replace("roku", "").strip()
    text = text.replace("/", ".").replace("-", ".")
    try:
        dt = datetime.datetime.strptime(text, "%d.%m.%Y")
    except ValueError:
        try:
            dt = datetime.datetime.strptime(text, "%d.%m.%y")
        except ValueError:
            return None
    return dt.strftime("%Y-%m-%d")


def clean_text_advanced(text, words_to_remove=None, stop_words=None, remove_duplicates=True):
    """
    Czyści tekst: usuwa wybrane słowa, wszystko po wskazanym słowie i powtarzające się słowa
    """
    if words_to_remove is None:
        words_to_remove = []
    if stop_words is None:
        stop_words = []
    
    # 1. Usuwanie pojedynczych słów
    for word in words_to_remove:
        text = text.replace(word, "")
    
    # 2. Usuwanie wszystkiego po słowie stop
    for stop_word in stop_words:
        if stop_word in text:
            text = text[:text.index(stop_word)].strip()
            break
    
    # 3. Usuwanie podwójnych spacji
    text = ", ".join(text.split())
    
    # 4. Usuwanie powtarzających się słów
    if remove_duplicates:
        text = remove_duplicate_words(text)
    
    return text

def remove_duplicate_words(text):
    """
    Usuwa powtarzające się słowa zachowując kolejność
    """
    words = text.split()
    seen = set()
    unique_words = []
    
    for word in words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)
    
    return ' '.join(unique_words)

def normalize_insurance_company(text):
    if not text:
        return None

    text = text.lower()
    companies = {
        "pzu": "PZU",
        "warta": "Warta",
        "allianz": "Allianz",
        "uniqa": "Uniqa",
        "compensa": "Compensa",
        "mtu": "MTU",
        "axa": "AXA",
        "generali": "Generali",
        "link4": "LINK4",
    }

    for key, clean_name in companies.items():
        if key in text:
            return clean_name
    return None


def clean_vehicle_text(text):
    if not text:
        return None
    text = text.lower()
    text = text.replace("nr rejestracyjny", "")
    text = text.replace("rejestracyjny", "")
    # text = text.replace("nr", "")
    text = text.strip().upper()
    # text = text.replace(" ", "")
    return text


# ===============================================================
# 🔹 KLIENT – UTWORZENIE LUB WALIDACJA
# ===============================================================

def ensure_client_exists(name):
    """Zwraca nazwę klienta (Customer). Tworzy rekord, jeśli nie istnieje."""
    if not name:
        return None

    name = name.strip().title()
    invalid = {"", "brak", "brak danych", "odmówił", "nieznany", "n/a"}
    if name.lower() in invalid:
        return None

    # Usuwanie typowych prefiksów i zbędnych słów
    for prefix in ["Pan ", "Pani ", "Państwo "]:
        if name.startswith(prefix):
            name = name[len(prefix):]

    name = re.sub(r"\b(erp|leasing|ubezpieczający|właściciel|regon|adres|pzu|leasingodawca)\b", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s{2,}", " ", name).strip()

    # Sprawdź, czy klient istnieje
    existing = frappe.db.exists("Customer", {"customer_name": name})
    if existing:
        return existing  # zwróć nazwę (docname)

    try:
        # Utwórz nowego klienta
        new_customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": "Individual",  # zawsze osoba fizyczna
            "customer_group": "Individual",  # jeśli masz taką grupę
            "territory": "All Territories"   # wymagane w ERPNext
        })
        new_customer.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.log_error(f"✅ Utworzono klienta (Customer): {name}", "OCR ensure_client_exists")
        return new_customer.name
    except Exception as e:
        frappe.log_error(f"❌ Błąd przy tworzeniu klienta '{name}': {e!s}", "OCR ensure_client_exists")
        return None

        # """Ulepszone odczytywanie tekstu z regionów dokumentu z powiększeniem."""
        # _resolve_tesseract_path()

        # results = []
        # for region in self.regions:
        #     x, y, w, h = region['bbox']
        #     roi = self.original[y:y + h, x:x + w]
        #     # Powiększ obraz
        #     new_width = int(w * scale_factor)
        #     new_height = int(h * scale_factor)
        #     resized_roi = cv2.resize(roi, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        #     gray = cv2.cvtColor(resized_roi, cv2.COLOR_BGR2GRAY)
        #     text = pytesseract.image_to_string(gray, lang=lang)
        #     region['text'] = text.strip()
        #     results.append({
        #         "id": region['id'],
        #         "label": region.get('label'),
        #         "bbox": region['bbox'],
        #         "text": region['text']
        #     })
        # return results