import frappe
from frappe.model.document import Document
from frappe.utils import add_years
from frappe import _

class InsurancePolicy(Document):

    # def after_insert(self):
    #     """Wywoływane po utworzeniu nowego dokumentu."""
    #     if self.policy_fille:
    #         frappe.enqueue(
    #             "agencik.policy.doctype.insurance_policy.policy_ocr.process_policy_file",
    #             docname=self.name,
    #             queue="short",
    #             timeout=300,
    #             now=False
    #         )

    # def on_update(self):
    #     """Wywoływane po aktualizacji dokumentu."""
    #     if self.policy_fille and not all([self.policy_number, self.insurance_company]):
    #         frappe.enqueue(
    #             "agencik.policy.doctype.insurance_policy.policy_ocr.process_policy_file",
    #             docname=self.name,
    #             queue="short",
    #             timeout=300,
    #             now=False
    #         )


    # def validate(self):
    #     """Automatycznie ustaw coverage_end na podstawie coverage_start"""
    #     if self.coverage_start:
    #         if not self.coverage_end or self.has_value_changed("coverage_start"):
    #             self.coverage_end = add_years(self.coverage_start, 1)
        
    #     # Automatyczne obliczanie prowizji
    #     if self.insurance_components:
    #         self.calculate_commission()

    def calculate_commission(self):
        # """Oblicza prowizję na podstawie wybranych komponentów ubezpieczenia"""
        if not self.insurance_components or len(self.insurance_components) == 0:
            self.commission_vehicle = 0
            return

        premium_values = {
            "OC": 1000,
            "AC": 800, 
            "Mini AC": 400,
            "Assistance": 200,
            "Life": 500,
            "Tires": 200,
            "Windows": 200,
            "Legal protection": 600
        }

        total_premium = 0
        commission_rate = 0.10  # 10%

        for component in self.insurance_components:
            component_name = component.company_list
            total_premium += premium_values.get(component_name, 500)

        self.commission_vehicle = total_premium * commission_rate

    # Prosta metoda whitelist dla obliczeń
    @frappe.whitelist()
    def calculate_commission_api(self):
        # """Metoda API do obliczania prowizji"""
        self.calculate_commission()
        return {
            "commission": self.commission_vehicle,
            "components_count": len(self.insurance_components) if self.insurance_components else 0
        }





 
