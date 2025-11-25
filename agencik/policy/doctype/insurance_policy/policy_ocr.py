import frappe
import os
import re
import datetime
import json
from .ocr import DocumentRegionDetector


# ===============================================================
# 🔹 OCR PROCESSING SERVICE
# ===============================================================

class OCRProcessingService:
    """Service class handling OCR processing operations"""
    
    def __init__(self):
        self.detector = None
    
    def process_document(self, file_path):
        """Main OCR processing pipeline"""
        try:
            self.detector = DocumentRegionDetector(file_path)
            self.detector.load_image()
            self.detector.preprocess_image()
            self.detector.detect_regions(min_area=800, max_area_ratio=0.5, padding=10)
            self.detector.assign_labels_by_keywords(lang="pol+eng")
            texts = self.detector.read_text_from_regions_enhanced(lang="pol+eng", scale_factor=3.0)
            
            return texts
        except Exception as e:
            frappe.log_error(f"OCR Processing Error: {e!s}")
            raise

    def extract_and_normalize_data(self, text_blocks):
        """Extract and normalize data from OCR results"""
        extracted_data = TextParser.parse_ocr_results(text_blocks)
        
        # Normalize fields
        extracted_data["insurance_company"] = InsuranceCompanyNormalizer.normalize(
            extracted_data.get("insurance_company")
        )
        extracted_data["client"] = ClientService.ensure_client_exists(
            extracted_data.get("client")
        )
        extracted_data["vehicle"] = VehicleTextCleaner.clean_vehicle_text(
            extracted_data.get("vehicle")
        )
        
        return extracted_data


# ===============================================================
# 🔹 TEXT PARSING
# ===============================================================

class TextParser:
    """Handles parsing of OCR text results"""
    
    MAPPING = {
        "policy_number": ["numer polisy", "nr polisy", "policy no", "polisa nr", "nr umowy","nr"],
        "insurance_company": [
            "pzu", "warta", "allianz", "generali", "link4", "axa", "uniqa", "compensa", "mtu"
        ],
        "coverage_start": [],
        "client": [
            "ubezpieczajacy", "klient", "nabywca", "ubezpieczony",
            "leasingobiorca", "dane klienta", "leasing", "spółka z ograniczoną odpowiedzialnością"
        ],
        "vehicle": ["pojazd", "samochód", "nr rejestracyjny", "rejestracyjny numer", "vin"],
    }

    @classmethod
    def parse_ocr_results(cls, text_blocks):
        """Parse OCR text blocks into structured data"""
        extracted = {k: None for k in cls.MAPPING.keys()}

        for block in text_blocks:
            text, label = cls._normalize_block_text(block)
            
            if not cls._process_dates(extracted, text):
                if not cls._process_policy_number(extracted, text):
                    if not cls._process_vehicle(extracted, text, label):
                        cls._process_client(extracted, text, label)
                        cls._process_insurance_company(extracted, text)

        return extracted

    @staticmethod
    def _normalize_block_text(block):
        """Normalize block text to string format"""
        raw_text = block.get("text", "")
        raw_label = block.get("label", "")

        if isinstance(raw_text, (tuple, list)):
            raw_text = " ".join(str(x) for x in raw_text)
        if isinstance(raw_label, (tuple, list)):
            raw_label = " ".join(str(x) for x in raw_label)

        text = str(raw_text).lower().replace("\n", " ")
        label = str(raw_label).lower()
        # print("normalize_block_text",text, label)
        return text, label

    @classmethod
    def _process_dates(cls, extracted, text):
        """Extract and process date ranges from text"""
        date_range = re.findall(
            r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*r\.\s*(?:godz\.\s*\d{1,2}:\d{2})?\s*[–—-]\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*r\.?",
            text
        )
        print("data", text)
        if date_range:
            start, end = date_range[0]
            extracted["coverage_start"] = DateNormalizer.normalize(start)
            extracted["coverage_end"] = DateNormalizer.normalize(end)
            return True
        return False

    @classmethod
    def _process_policy_number(cls, extracted, text):
        """Extract policy number from text"""
        print("text",text)
        print(cls)
        if any(kw in text for kw in cls.MAPPING["policy_number"]):
            numbers = re.findall(r"\b\d{8,12}\b", text)
            if numbers:
                preferred = [n for n in numbers if n.startswith(('1', '5'))]
                extracted["policy_number"] = preferred[0] if preferred else numbers[0]
                return True
        return False
    
    

    @classmethod
    def _process_vehicle(cls, extracted, text, label):
        """Extract vehicle information from text"""
        if any(kw in label for kw in ["pojazd", "samochód"]) or any(
            kw in text for kw in ["nr rejestracyjny", "vin", "marka", "model", "rok produkcji", "pojazd"]
        ):
            vehicle_data = VehicleDataExtractor.extract(text)
            extracted.update(vehicle_data)
            return True
        return False

    @classmethod
    def _process_client(cls, extracted, text, label):
        """Extract client information from text"""
        if any(k in label for k in ["leasingobiorca", "ubezpieczajacy"]) and not extracted["client"]:
            client_name = ClientDataExtractor.extract(text)
            if client_name:
                extracted["client"] = client_name

    @classmethod
    def _process_insurance_company(cls, extracted, text):
        """Extract insurance company from text"""
        if not extracted["insurance_company"]:
            extracted["insurance_company"] = InsuranceCompanyNormalizer.normalize(text)


# ===============================================================
# 🔹 VEHICLE DATA EXTRACTION
# ===============================================================

class VehicleDataExtractor:
    """Extracts and processes vehicle data from text"""
    
    @staticmethod
    def extract(text):
        """Extract vehicle information from text"""
        clean_text = VehicleTextCleaner.preprocess_vehicle_text(text)
        extracted = {}
        
        # Extract individual vehicle fields
        extracted.update(VehicleDataExtractor._extract_vehicle_fields(clean_text))
        
        # Clean and set full vehicle text
        words_to_remove = [
            "UBEZPIECZONY POJAZD NR REJESTRACYJNY:",
            "ROK PRODUKCJI:",
            "MODEL:",
            "TYP:",
            "VIN:",
            "POJEMNOŚĆ SILNIKA:",
            "CCM"
        ]
        stop_words = ["MARKA:"]
        
        extracted["vehicle"] = TextCleaner.clean_text_advanced(
            clean_text, words_to_remove, stop_words
        )
        
        return extracted

    @staticmethod
    def _extract_vehicle_fields(clean_text):
        """Extract specific vehicle fields from cleaned text"""
        extracted = {}
        
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

        values = []
        if marka_match:
            values.append(marka_match.group(1).strip())
        if model_match:
            values.append(model_match.group(1).strip())
        if rok_match:
            values.append(rok_match.group(1))
        if vin_match:
            vin_num = vin_match.group(1).strip().replace('.', '')
            extracted["vin"] = vin_num

        if values:
            extracted["vehicle_type"] = ", ".join(values).replace('.', '')

        return extracted


# ===============================================================
# 🔹 CLIENT DATA PROCESSING
# ===============================================================

class ClientDataExtractor:
    """Extracts client information from text"""
    
    @staticmethod
    def extract(text):
        """Extract client name from text"""
        clean_text = re.sub(r"\b(ubezpieczaj[ąacyi]+|regon|adres|telefon|nazwa|email)\b", "", 
                           text, flags=re.IGNORECASE)
        
        name_match = re.search(
            r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)+|[A-Z0-9ĄĆĘŁŃÓŚŹŻ\s\.,\-]+sp\. z o\.o\.)",
            clean_text,
            re.IGNORECASE
        )
        
        if name_match:
            name = ClientTextCleaner.clean_client_name(name_match.group(1).strip())
            if name and len(name.split()) >= 2:
                return name
        return None


class ClientService:
    """Handles client creation and validation"""
    
    INVALID_NAMES = {"", "brak", "brak danych", "odmówił", "nieznany", "n/a"}
    PREFIXES = ["Pan ", "Pani ", "Państwo "]
    UNWANTED_WORDS = r"\b(erp|leasing|ubezpieczający|właściciel|regon|adres|pzu|leasingodawca)\b"

    @classmethod
    def ensure_client_exists(cls, name):
        """Return customer docname, create record if doesn't exist"""
        if not name:
            return None

        cleaned_name = ClientTextCleaner.clean_client_name(name)
        if not cleaned_name:
            return None

        # Check existing customer
        existing = frappe.get_value("Customer", {"customer_name": cleaned_name}, "name")
        if existing:
            return existing

        # Create new customer
        return cls._create_customer(cleaned_name)

    @classmethod
    def _create_customer(cls, name):
        """Create new customer record"""
        try:
            new_customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": name,
                "customer_type": "Individual",
            })
            new_customer.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.log_error(f"✅ Utworzono klienta: {name}", "OCR ensure_client_exists")
            return new_customer.name
        except Exception as e:
            frappe.log_error(f"❌ Błąd przy tworzeniu klienta '{name}': {e}", 
                           "OCR ensure_client_exists")
            return None


# ===============================================================
# 🔹 TEXT CLEANING AND NORMALIZATION
# ===============================================================

class TextCleaner:
    """General text cleaning utilities"""
    
    @staticmethod
    def clean_text_advanced(text, words_to_remove=None, stop_words=None, remove_duplicates=True):
        """Clean text by removing specified words and handling duplicates"""
        if words_to_remove is None:
            words_to_remove = []
        if stop_words is None:
            stop_words = []
        
        # Remove specified words
        for word in words_to_remove:
            text = text.replace(word, "")
        
        # Remove everything after stop word
        for stop_word in stop_words:
            if stop_word in text:
                text = text[:text.index(stop_word)].strip()
                break
        
        # Clean up spaces and handle duplicates
        text = ", ".join(text.split())
        
        if remove_duplicates:
            text = TextCleaner.remove_duplicate_words(text)
        
        return text

    @staticmethod
    def remove_duplicate_words(text):
        """Remove duplicate words while preserving order"""
        words = text.split()
        seen = set()
        unique_words = []
        
        for word in words:
            if word not in seen:
                seen.add(word)
                unique_words.append(word)
        
        return ' '.join(unique_words)


class ClientTextCleaner:
    """Specific cleaning for client names"""
    
    @staticmethod
    def clean_client_name(name):
        """Clean and normalize client name"""
        if not name or name.lower() in ClientService.INVALID_NAMES:
            return None

        name = name.strip().title()

        # Remove prefixes
        for prefix in ClientService.PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()

        # Remove unwanted words
        name = re.sub(ClientService.UNWANTED_WORDS, "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s{2,}", " ", name).strip()

        return name if name else None


class VehicleTextCleaner:
    """Specific cleaning for vehicle text"""
    
    @staticmethod
    def clean_vehicle_text(text):
        """Clean vehicle registration text"""
        if not text:
            return None
            
        text = text.lower()
        text = text.replace("nr rejestracyjny", "")
        text = text.replace(":", "")
        text = text.replace(",", "")
        text = text.replace("rejestracyjny", "")
        text = text.strip().upper()
        text = text.replace(" ", "")
        return text

    @staticmethod
    def preprocess_vehicle_text(text):
        """Preprocess vehicle text for extraction"""
        clean_text = re.sub(r"[\n\r,;]+", " ", text)
        clean_text = re.sub(r"\s{2,}", " ", clean_text)
        clean_text = clean_text.upper()
        
        # Add spaces after colons
        clean_text = re.sub(r"([A-Z])(:)([A-Z0-9])", r"\1: \3", clean_text)
        
        return clean_text


class DateNormalizer:
    """Handles date normalization"""
    
    @staticmethod
    def normalize(text):
        """Normalize date string to YYYY-MM-DD format"""
        if not text:
            return None
            
        text = text.lower().replace("r.", "").replace("roku", "").strip()
        text = text.replace("/", ".").replace("-", ".").replace(":", "")
        
        try:
            dt = datetime.datetime.strptime(text, "%d.%m.%Y")
        except ValueError:
            try:
                dt = datetime.datetime.strptime(text, "%d.%m.%y")
            except ValueError:
                return None
                
        return dt.strftime("%Y-%m-%d")


class InsuranceCompanyNormalizer:
    """Normalizes insurance company names"""
    
    @staticmethod
    def normalize(text):
        """Match insurance company name with database records"""
        if not text:
            return None

        text = text.lower()

        try:
            insurers = frappe.get_all("Insurers", fields=["company"])

            for row in insurers:
                company_name = row.get("company", "")
                if not company_name:
                    continue

                normalized_db = re.sub(r"[^a-z0-9]", "", company_name.lower())
                normalized_text = re.sub(r"[^a-z0-9]", "", text)

                if normalized_db in normalized_text or normalized_text in normalized_db:
                    return company_name

            return None

        except Exception as e:
            frappe.log_error(f"Błąd przy pobieraniu firm z Insurers: {e}", 
                           "OCR normalize_insurance_company")
            return None


# ===============================================================
# 🔹 MAIN API ENDPOINTS
# ===============================================================

@frappe.whitelist()
def process_policy_file(docname):
    """Main function called by after_insert / on_update"""
    try:
        doc = frappe.get_doc("Insurance Policy", docname)
        result = process_policy_file_internal(doc)
        return result
    except Exception as e:
        frappe.log_error(f"OCR Error (process_policy_file): {e!s}")
        return {f"error: {e!s}"}


@frappe.whitelist()
def process_policy_temp(data):
    """Temporary document processing before saving (no database save)"""
    try:
        doc_data = json.loads(data)
        file_url = doc_data.get("policy_fille")

        if not file_url:
            return {"error": "Brak pliku PDF do przetworzenia."}

        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_path = file_doc.get_full_path()

        if not os.path.exists(file_path):
            return {"error": f"Nie znaleziono pliku: {file_path}"}

        # Use service for processing
        ocr_service = OCRProcessingService()
        texts = ocr_service.process_document(file_path)
        extracted_data = ocr_service.extract_and_normalize_data(texts)

        frappe.log_error(
            json.dumps(extracted_data, indent=2, ensure_ascii=False)[:4000],
            "OCR Extracted Data (TEMP)"
        )

        return {"success": True, "data": extracted_data}

    except Exception as e:
        frappe.log_error(f"TEMP OCR Error: {e!s}")
        return {f"error: {e!s}"}


def process_policy_file_internal(doc):
    """Full OCR processing"""
    try:
        file_doc = frappe.get_doc("File", {"file_url": doc.policy_fille})
        file_path = file_doc.get_full_path()

        if not os.path.exists(file_path):
            frappe.throw(f"Nie znaleziono pliku: {file_path}")

        # Use service for processing
        ocr_service = OCRProcessingService()
        texts = ocr_service.process_document(file_path)
        extracted_data = ocr_service.extract_and_normalize_data(texts)

        frappe.log_error(
            json.dumps(extracted_data, indent=2, ensure_ascii=False)[:4000],
            "OCR Extracted Data (SAVE PREVIEW)"
        )

        return {"success": True, "data": extracted_data}

    except Exception as e:
        frappe.log_error(f"OCR Processing Error: {e!s}")
        return {f"error: {e!s}"}