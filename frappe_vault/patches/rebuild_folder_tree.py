import frappe
from frappe.utils.nestedset import rebuild_tree


def execute():
    frappe.reload_doc("Vault", "doctype", "Vault Folder")
    rebuild_tree("Vault Folder")
