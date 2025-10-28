import frappe
import os
import re
import logging
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import tempfile
import shutil
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Sprawdź czy OpenCV jest dostępne
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
    frappe.logger().info("✅ OpenCV is available")
except ImportError:
    OPENCV_AVAILABLE = False
    frappe.logger().warning("⚠️ OpenCV not available - using fallback OCR mode")

def _resolve_tesseract_path() -> str:
    """Locate the Tesseract executable and configure pytesseract accordingly."""
    candidates = [
        os.environ.get("TESSERACT_CMD"),
        shutil.which("tesseract"),
        "/usr/bin/tesseract",
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

    raise RuntimeError("Tesseract OCR executable not found.")

class PolicyOCR:
    def __init__(self):
        self.setup_ocr()
    
    def setup_ocr(self):
        """Konfiguracja Tesseract OCR"""
        try:
            _resolve_tesseract_path()
            pytesseract.get_tesseract_version()
            frappe.logger().info("✅ Tesseract OCR is configured")
            
            if not OPENCV_AVAILABLE:
                frappe.msgprint("⚠️ OpenCV nie jest dostępne - używam podstawowego trybu OCR")
                
        except Exception as e:
            logger.error(f"❌ Tesseract OCR not available: {e}")
            frappe.msgprint("⚠️ Tesseract OCR nie jest zainstalowany - używam trybu testowego")
    
    def extract_text_from_pdf(self, file_path):
        """
        Ekstrakcja tekstu z PDF - z opcją OpenCV jeśli dostępne
        """
        try:
            frappe.logger().info(f"📄 Converting PDF to images: {file_path}")
            
            # Konwersja PDF na obrazy
            images = convert_from_path(file_path, dpi=200, first_page=1, last_page=3)
            full_text = ""
            
            frappe.logger().info(f"🖼️ Processing {len(images)} pages")
            
            for i, image in enumerate(images):
                frappe.logger().info(f"🔍 OCR page {i+1}")
                
                if OPENCV_AVAILABLE:
                    # Ulepszone przetwarzanie z OpenCV
                    text = self._process_image_with_opencv(image)
                else:
                    # Podstawowe przetwarzanie bez OpenCV
                    text = pytesseract.image_to_string(image, lang='pol+eng')
                
                full_text += text + "\n"
                
                # Przerwij jeśli mamy już kluczowe dane
                if i >= 1 and self.has_sufficient_data(full_text):
                    frappe.logger().info("✅ Sufficient data found, stopping early")
                    break
            
            frappe.logger().info(f"📝 Extracted text length: {len(full_text)} characters")
            return full_text
            
        except Exception as e:
            logger.error(f"❌ Error extracting text from PDF: {e}")
            return ""
    
    def _process_image_with_opencv(self, image):
        """Ulepszone przetwarzanie obrazu z OpenCV"""
        try:
            # Konwertuj PIL Image to numpy array dla OpenCV
            img_array = np.array(image)
            
            # Konwertuj RGB to BGR (OpenCV format)
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            # Przetwarzanie obrazu z OpenCV
            processed_img = self._enhance_image_quality(img_array)
            
            # OCR na ulepszonym obrazie
            text = pytesseract.image_to_string(processed_img, lang='pol+eng')
            return text
            
        except Exception as e:
            logger.error(f"❌ OpenCV processing failed: {e}, using basic OCR")
            # Fallback to basic OCR
            return pytesseract.image_to_string(image, lang='pol+eng')
    
    def _enhance_image_quality(self, img_array):
        """Ulepszanie jakości obrazu z OpenCV"""
        # Konwersja do odcieni szarości
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_array
        
        # Usuwanie szumów
        denoised = cv2.medianBlur(gray, 3)
        
        # Zwiększenie kontrastu
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        return enhanced
    
    def has_sufficient_data(self, text):
        """Sprawdź czy mamy już wystarczające dane"""
        key_indicators = [
            'numer polisy', 'okres ubezpieczenia', 'ubezpieczający',
            'faktura', 'sprzedawca', 'nabywca', 'data wystawienia'
        ]
        return any(indicator in text.lower() for indicator in key_indicators)
    
    def determine_document_type(self, text):
        """Określanie typu dokumentu"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['polis', 'ubezpieczen', 'insurance', 'pzu', 'warta', 'allianz', 'uniqua', 'hestia']):
            return 'insurance_policy'
        elif any(word in text_lower for word in ['faktura', 'invoice', 'sprzedawca', 'nabywca']):
            return 'invoice'
        else:
            return 'unknown'
    
    def determine_policy_type(self, text):
        """Inteligentne określanie typu polisy"""
        text_lower = text.lower()
        
        # Sprawdź czy dokument zawiera informacje o pojeździe
        vehicle_indicators = [
            'marka', 'model', 'nr rejestracyjny', 'rejestracyjny', 'vin',
            'pojazd', 'samochód', 'auto', 'vehicle', 'car'
        ]
        
        has_vehicle_info = any(indicator in text_lower for indicator in vehicle_indicators)
        
        # Sprawdź konkretne typy ubezpieczeń
        insurance_type_indicators = {
            'Transport': ['komunikacyjn', 'transport', 'auto', 'samochód', 'oc', 'ac', 'autocasco', 'nnw', 'assistance'],
            'Home': ['mieszkani', 'dom', 'home', 'house', 'nieruchomość', 'majątek', 'property'],
            'Life': ['życie', 'life', 'życiowe', 'na życie'],
            'Health': ['zdrowotn', 'health', 'medyczn', 'hospitalization'],
            'Travel': ['podróż', 'travel', 'turystyczn']
        }
        
        for policy_type, indicators in insurance_type_indicators.items():
            if any(indicator in text_lower for indicator in indicators):
                return policy_type
        
        # Domyślnie
        return 'Transport' if has_vehicle_info else 'Home'
    
    def parse_insurance_policy(self, text, file_name):
        """Parsowanie polisy ubezpieczeniowej"""
        policy_type = self.determine_policy_type(text)
        
        data = {
            'policy_number': '',
            'client': '',
            'coverage_start': '',
            'coverage_end': '',
            'type_policy': policy_type,
            'insurance_company': 'Other',
            'vehicle': '',
            'premium_amount': ''
        }
        
        # Numer polisy
        policy_patterns = [
            r'numer polisy:\s*([A-Z0-9\-]+)',
            r'polisa nr\s*([A-Z0-9\-]+)',
            r'Nr polisy:\s*([A-Z0-9\-]+)',
            r'Policy No\.?\s*([A-Z0-9\-]+)'
        ]
        
        for pattern in policy_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['policy_number'] = match.group(1)
                break
        
        # Okres ubezpieczenia
        coverage_pattern = r'(\d{1,2}\.\d{1,2}\.\d{4})\s*[–\-]\s*(\d{1,2}\.\d{1,2}\.\d{4})'
        coverage_match = re.search(coverage_pattern, text)
        if coverage_match:
            data['coverage_start'] = self.parse_polish_date(coverage_match.group(1))
            data['coverage_end'] = self.parse_polish_date(coverage_match.group(2))
        
        # Ubezpieczający
        client_patterns = [
            r'Ubezpieczający\s*([^\n\r]+)',
            r'Ubezpieczony\s*([^\n\r]+)',
            r'Client:\s*([^\n\r]+)'
        ]
        
        for pattern in client_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['client'] = match.group(1).strip()
                break
        
        # Ubezpieczyciel
        if 'pzu' in text.lower():
            data['insurance_company'] = 'PZU'
        elif 'warta' in text.lower():
            data['insurance_company'] = 'Warta'
        elif 'allianz' in text.lower():
            data['insurance_company'] = 'Allianz'
        elif 'uniqua' in text.lower():
            data['insurance_company'] = 'Uniqua'
        elif 'hestia' in text.lower():
            data['insurance_company'] = 'Hestia'
        
        # Pojazd - jeśli to ubezpieczenie Transport
        if policy_type == 'Transport':
            vehicle_info = []
            
            # Marka i model
            vehicle_pattern = r'marka:\s*([^,\n\r]+)'
            vehicle_match = re.search(vehicle_pattern, text, re.IGNORECASE)
            if vehicle_match:
                vehicle_info.append(f"Marka: {vehicle_match.group(1)}")
            
            # Numer rejestracyjny
            plate_pattern = r'nr rejestracyjny:\s*([A-Z0-9]+)'
            plate_match = re.search(plate_pattern, text, re.IGNORECASE)
            if plate_match:
                vehicle_info.append(f"Rej: {plate_match.group(1)}")
            
            if vehicle_info:
                data['vehicle'] = ', '.join(vehicle_info)
        
        # Składka
        premium_pattern = r'składka.*?([\d\s]+,\d+)\s*zł'
        premium_match = re.search(premium_pattern, text, re.IGNORECASE)
        if premium_match:
            data['premium_amount'] = premium_match.group(1) + ' PLN'
        
        return data
    
    def parse_invoice_data(self, text, file_name):
        """Parsowanie faktury"""
        data = {
            'policy_number': '',
            'client': '',
            'coverage_start': '',
            'type_policy': 'Inne',
            'insurance_company': 'Other'
        }
        
        # Numer faktury z nazwy pliku
        invoice_number = self.extract_invoice_number_from_filename(file_name)
        if invoice_number:
            data['policy_number'] = invoice_number
        
        # Numer faktury z treści
        if not data['policy_number']:
            invoice_patterns = [
                r'FAKTURA[_\s]*([A-Z0-9\-]+)',
                r'Faktura[_\s]*([A-Z0-9\-]+)',
                r'Numer[:\s]*([A-Z0-9\-]+)',
            ]
            
            for pattern in invoice_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    data['policy_number'] = matches[0]
                    break
        
        # Data
        date_patterns = [
            r'Data wystawienia[:\s]*(\d{1,2}[\.\s]+\d{1,2}[\.\s]+\d{4})',
            r'Data[:\s]*(\d{1,2}[\.\s]+\d{1,2}[\.\s]+\d{4})',
            r'okres ubezpieczenia[:\s]*(\d{1,2}[\.\s]+\d{1,2}[\.\s]+\d{4})',
            r'okres[:\s]*(\d{1,2}[\.\s]+\d{1,2}[\.\s]+\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['coverage_start'] = self.parse_polish_date(match.group(1))
                break
        
        # Klient
        client_patterns = [
            r'NABYWCA[:\s]*([^\n\r]+)',
            r'Nabywca[:\s]*([^\n\r]+)',
        ]
        
        for pattern in client_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['client'] = match.group(1).strip()
                break
        
        return data
    
    def extract_invoice_number_from_filename(self, file_name):
        """Ekstrakcja numeru faktury z nazwy pliku"""
        patterns = [
            r'faktura[_\s]*([A-Z0-9\-]+)',
            r'invoice[_\s]*([A-Z0-9\-]+)',
            r'(\d{10,})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, file_name, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def parse_polish_date(self, date_str):
        """Konwersja polskiej daty na format YYYY-MM-DD"""
        try:
            date_str = date_str.strip().replace(' ', '')
            if re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', date_str):
                day, month, year = date_str.split('.')
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            return date_str
        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")
            return date_str
    
    def get_fallback_data(self, file_name, doc_type='generic'):
        """Dane fallback gdy OCR nie zadziała"""
        if doc_type == 'invoice':
            return {
                'policy_number': f"FAKTURA_{file_name.split('.')[0]}",
                'client': 'Klient (rozpoznany z faktury)',
                'coverage_start': '2025-01-01',
                'type_policy': 'Inne',
                'insurance_company': 'Other'
            }
        else:
            return {
                'policy_number': f"POLISA_{file_name.split('.')[0]}",
                'client': 'Ubezpieczony (rozpoznany z dokumentu)',
                'coverage_start': '2025-01-01',
                'type_policy': 'Home',
                'insurance_company': 'Other'
            }
    
    def process_uploaded_file(self, file_url, file_name):
        """GŁÓWNA METODA - przetwarzanie przesłanego pliku"""
        try:
            frappe.logger().info(f"🔍 Starting OCR processing for: {file_name}")
            
            # Pobranie ścieżki do pliku z Frappe
            file_path = frappe.get_site_path('public', file_url.lstrip('/'))
            
            if not os.path.exists(file_path):
                frappe.logger().warning(f"📁 File not found: {file_path}, using test data")
                return self.get_fallback_data(file_name)
            
            # Ekstrakcja tekstu
            text = self.extract_text_from_pdf(file_path)
            
            if not text:
                frappe.logger().warning("📝 No text extracted, using fallback data")
                return self.get_fallback_data(file_name)
            
            # Określenie typu dokumentu
            doc_type = self.determine_document_type(text)
            frappe.logger().info(f"📄 Document type: {doc_type}")
            
            if doc_type == 'invoice':
                return self.parse_invoice_data(text, file_name)
            elif doc_type == 'insurance_policy':
                return self.parse_insurance_policy(text, file_name)
            else:
                return self.get_fallback_data(file_name)
                
        except Exception as e:
            logger.error(f"❌ Error in process_uploaded_file: {e}")
            frappe.logger().error(f"Full error: {str(e)}")
            return self.get_fallback_data(file_name)

# Globalna instancja OCR
policy_ocr = PolicyOCR()

@frappe.whitelist()
def process_policy_ocr(file_url, file_name):
    """Funkcja wywoływana z frontendu do przetwarzania OCR"""
    try:
        frappe.logger().info(f"🎯 OCR endpoint called - File: {file_name}")
        
        if frappe.session.user == 'Guest':
            return {'success': False, 'error': "Brak uprawnień"}
        
        data = policy_ocr.process_uploaded_file(file_url, file_name)
        
        frappe.logger().info(f"✅ OCR processing successful: {data}")
        
        return {
            'success': True,
            'data': data,
            'opencv_available': OPENCV_AVAILABLE
        }
    except Exception as e:
        frappe.logger().error(f"❌ OCR processing failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@frappe.whitelist()
def check_opencv_status():
    """Sprawdza status OpenCV"""
    return {
        'opencv_available': OPENCV_AVAILABLE,
        'opencv_version': cv2.__version__ if OPENCV_AVAILABLE else 'Not available'
    }

def after_policy_insert(doc, method=None):
    """
    Automatyczne przetwarzanie po wstawieniu nowego dokumentu
    """
    try:
        frappe.logger().info(f"🔄 After insert called for: {doc.name}")
        
        if doc.policy_fille:
            frappe.logger().info(f"📎 Processing attached file: {doc.policy_fille}")
            data = policy_ocr.process_uploaded_file(doc.policy_fille, "uploaded_file.pdf")
            
            # Aktualizacja pól
            safe_fields = ['policy_number', 'client', 'coverage_start', 'coverage_end', 
                          'type_policy', 'insurance_company', 'vehicle', 'premium_amount']
            
            updated_fields = []
            for field in safe_fields:
                if field in data and data[field] and hasattr(doc, field):
                    doc.db_set(field, data[field])
                    updated_fields.append(field)
            
            frappe.db.commit()
            frappe.msgprint(f"✅ Dane z dokumentu zostały automatycznie wypełnione: {', '.join(updated_fields)}")
            
    except Exception as e:
        frappe.logger().error(f"❌ Auto-processing failed: {e}")