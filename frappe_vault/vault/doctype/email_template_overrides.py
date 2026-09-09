import frappe
from frappe import _


def validate(doc, method=None):
    # Check if they are unsetting the default flag OR disabling the template
    if not doc.get("vault_is_default") or not doc.get("vault_enabled"):
        if not doc.is_new():
            old_doc = frappe.db.get_value(
                "Email Template", doc.name, ["vault_is_default", "vault_enabled"], as_dict=True
            )
            # If it was the default and enabled, and now it's not...
            if old_doc and old_doc.vault_is_default and old_doc.vault_enabled:
                # Is there ANOTHER template that is default and enabled?
                other_default = frappe.db.exists(
                    "Email Template", {"vault_is_default": 1, "vault_enabled": 1, "name": ["!=", doc.name]}
                )
                if not other_default:
                    frappe.throw(
                        _(
                            "There must be at least one active default Vault template. Please set another as default first."
                        )
                    )

    # If this template IS being set as default AND enabled
    if doc.get("vault_is_default") and doc.get("vault_enabled"):
        # Unset default and disable all other Vault templates
        frappe.db.sql(
            """
            UPDATE `tabEmail Template`
            SET vault_is_default = 0, vault_enabled = 0
            WHERE name != %s AND vault_is_default = 1
            """,
            (doc.name,),
        )


def on_trash(doc, method=None):
    if doc.get("vault_is_default"):
        frappe.throw(
            _(
                "You cannot delete the default Vault Email Template. Please set another template as default first."
            )
        )

    # Also prevent deleting the "Vault Invitation Default" if it's the only one left
    if doc.name == "Vault Invitation Default":
        other_vault_templates = frappe.db.exists(
            "Email Template", {"vault_enabled": 1, "name": ["!=", doc.name]}
        )
        if not other_vault_templates:
            frappe.throw(
                _("You cannot delete the standard Vault Invitation template as it is the only one remaining.")
            )
