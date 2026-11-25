"""Vault Share DocType controller."""

import frappe
from frappe import _
from frappe.model.document import Document


class VaultShare(Document):
    """Controls sharing of secrets and folders with users or roles."""

    def validate(self):
        self.validate_share_target()
        self.set_shared_by()
        self.validate_permissions()

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

    def validate_permissions(self):
        """Ensure caller has permission to share or modify sharing for this document."""
        user = frappe.session.user
        if not user or user == "Guest":
            frappe.throw(_("Authentication required"), frappe.PermissionError)

        if frappe.flags.in_install or frappe.flags.in_migrate:
            return

        roles = frappe.get_roles(user)
        is_admin = user == "Administrator" or "Vault Admin" in roles or "System Manager" in roles
        if is_admin:
            return

        # Users cannot grant shares to themselves to escalate privileges
        if self.share_type == "User" and self.user == user and self.is_new():
            frappe.throw(_("You cannot share items with yourself"), frappe.PermissionError)

        if not self.shared_doctype or not self.shared_name:
            return

        from frappe_vault.utils.permissions import get_effective_user_permission

        # Check document ownership or Full Control
        owner = frappe.db.get_value(self.shared_doctype, self.shared_name, "owner")
        eff_perm = get_effective_user_permission(self.shared_doctype, self.shared_name, user)

        if owner != user and eff_perm != 4:
            frappe.throw(
                _("You do not have permission to manage shares for this item"),
                frappe.PermissionError,
            )

        # On update: ensure non-admin / non-owner recipient cannot modify or unrevoke their own share
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and self.share_type == "User" and self.user == user:
                frappe.throw(_("You cannot modify your own share record"), frappe.PermissionError)

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
