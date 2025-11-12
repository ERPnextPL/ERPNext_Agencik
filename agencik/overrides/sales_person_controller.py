import frappe
from frappe import _

# W Server Script dla danego DocType
def validate_item(doc, method):
    if doc.commission_rate and (doc.commission_rate < 0 or doc.commission_rate > 100):
        frappe.throw(_("The value must be between 0 and 100%"))


def printWord(doc, method):
    print("Hello World")
    