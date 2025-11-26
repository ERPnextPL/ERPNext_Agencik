
import frappe
from frappe import _

# walidation_company_number
def length_company(doc, method=None):
    if not doc.insurance_company or not doc.policy_number:
        return
    
    # Pobierz dane firmy z doctype Insurers
    insurer = frappe.db.get_value(
        "Insurers",
        {"company": doc.insurance_company},
        ["length"],
        as_dict=True
    )

    if insurer and insurer.length:
        if len(doc.policy_number) != insurer.length:
            frappe.throw(_(
                f"For {doc.insurance_company} the policy number must be exactly {insurer.length} characters long"
            ))
    else:
        frappe.msgprint(_(
            f"No length rule defined for {doc.insurance_company} in Insurers doctype"
        ))
        
    # Sprawdzenie regexa (jeśli zdefiniowany)
    # if insurer.format_regex:
    #     pattern = re.compile(insurer.format_regex)
    #     if not pattern.fullmatch(doc.policy_number):
    #         frappe.throw(_(
    #             f"For {doc.insurance_company}, the policy number does not match the required format."
    #         ))

    