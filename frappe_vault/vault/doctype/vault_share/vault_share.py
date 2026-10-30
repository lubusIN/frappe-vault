"""Vault Share DocType controller."""

import frappe
from frappe import _
from frappe.model.document import Document


class VaultShare(Document):
    """Controls sharing of secrets and folders with users or roles."""

    def validate(self):
        self.validate_share_target()
        self.set_shared_by()

    def validate_share_target(self):
        """Ensure exactly one target is set based on share_type."""
        if self.share_type == "User" and not self.user:
            frappe.throw(_("User is required when Share Type is User"))
        elif self.share_type == "Role" and not self.frappe_role:
            frappe.throw(_("Role is required when Share Type is Role"))

    def set_shared_by(self):
        """Auto-set the sharing user."""
        if not self.shared_by:
            self.shared_by = frappe.session.user

    def on_trash(self):
        """Clean up orphaned role overrides if a parent role share is deleted directly."""
        if self.share_type == "Role" and self.frappe_role:
            role_users = frappe.get_all(
                "Has Role", filters={"role": self.frappe_role, "parenttype": "User"}, pluck="parent"
            )
            if role_users:
                overrides = frappe.get_all(
                    "Vault Share",
                    filters={
                        "shared_doctype": self.shared_doctype,
                        "shared_name": self.shared_name,
                        "share_type": "User",
                        "user": ["in", role_users],
                        "is_role_override": 1,
                    },
                    pluck="name",
                )
                for override_name in overrides:
                    frappe.delete_doc("Vault Share", override_name, ignore_permissions=True)
