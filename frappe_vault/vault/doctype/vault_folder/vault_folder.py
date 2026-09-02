"""Vault Folder DocType controller."""

from frappe.utils.nestedset import NestedSet


class VaultFolder(NestedSet):
    """Folder organization for vault secrets."""

    nsm_parent_field = "parent_vault_folder"

    def validate(self):
        if self.folder_name:
            self.folder_name = self.folder_name.strip()
