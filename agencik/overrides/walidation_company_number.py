
import frappe
from frappe import _


# def length_company(doc, method):
#     if doc.insurance_company == "Allianz":
#         if len(doc.policy_number) != 10:
#             frappe.throw(_("For Allianz the policy number must be exactly 10 characters long"))
        
#     elif doc.insurance_company == "Warta":
#         if len(doc.policy_number) != 15:
#             frappe.throw(_("For Warta the policy number must be exactly 15 characters long"))
        
#     elif doc.insurance_company == "Proama":
#         if len(doc.policy_number) != 11:
#             frappe.throw(_("For Proama the policy number must be exactly 11 characters long"))


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

    