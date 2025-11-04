
import frappe

from frappe import _


def length_company(doc, method):
    if doc.insurance_company == "Allianz":
        if len(doc.policy_number) != 10:
            frappe.throw(_("For Allianz the policy number must be exactly 10 characters long"))
        
    elif doc.insurance_company == "Warta":
        if len(doc.policy_number) != 15:
            frappe.throw(_("For Warta the policy number must be exactly 15 characters long"))
        
    elif doc.insurance_company == "Proama":
        if len(doc.policy_number) != 11:
            frappe.throw(_("For Proama the policy number must be exactly 11 characters long"))


   # def validate_policy_length(doc, method=None):
    #     if not doc.insurance_company or not doc.policy_number:
    #         return
            
    #     company_lengths = {
    #         "Allianz": 10,
    #         "Warta": 15, 
    #         "Proama": 11
    #     }
        
    #     if doc.insurance_company in company_lengths:
    #         required_length = company_lengths[doc.insurance_company]
    #         if len(doc.policy_number) != required_length:
    #             frappe.throw(_(
    #                 f"Dla {doc.insurance_company} numer polisy musi mieć dokładnie {required_length} znaków. "
    #                 f"Wprowadzono {len(doc.policy_number)} znaków."
    #             ))