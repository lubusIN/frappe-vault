"""Vault Folder DocType controller."""

import frappe
from frappe.utils.nestedset import NestedSet


class VaultFolder(NestedSet):
    """Folder organization for vault secrets."""

    nsm_parent_field = "parent_vault_folder"

    def validate(self):
        if self.folder_name:
            self.folder_name = self.folder_name.strip()

        # Keep is_group consistent so NestedSet never throws leaf node errors
        if not self.is_new():
            has_children = frappe.db.count("Vault Folder", {"parent_vault_folder": self.name})
            if has_children:
                self.is_group = 1

        if self.parent_vault_folder:
            frappe.db.set_value("Vault Folder", self.parent_vault_folder, "is_group", 1)
