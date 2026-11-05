"""Vault Settings DocType controller."""

import frappe
from frappe import _
from frappe.model.document import Document

# Settings that decide where secret values go or who can reach them. Changing
# any of these is audited in Vault's own log and announced to every Vault
# Admin, so e.g. pointing HashiCorp sync at a different server cannot happen
# quietly. Frappe's Version history alone is not enough: an admin can delete it.
SENSITIVE_FIELDS = (
    "enable_hashicorp_vault",
    "hashicorp_auth_method",
    "hashicorp_vault_url",
    "hashicorp_vault_namespace",
    "hashicorp_approle_mount",
    "hashicorp_role_id",
    "hashicorp_vault_mount",
    "hashicorp_vault_path_prefix",
    "hashicorp_verify_ssl",
    "sync_on_password_change",
    "send_rotation_emails",
)
SENSITIVE_PASSWORD_FIELDS = ("hashicorp_vault_token", "hashicorp_secret_id")


class VaultSettings(Document):
    """App-wide settings for Frappe Vault."""

    def on_update(self):
        changed = self.changed_sensitive_fields()
        if not changed:
            return

        from frappe_vault.services import audit_service
        from frappe_vault.services.notification_service import notify_vault_admins

        audit_service._create_log("Settings Changed", details={"fields": changed})
        notify_vault_admins(
            subject=_("Vault security settings changed by {0}").format(frappe.session.user),
            email_content=_("Changed: {0}. If you did not expect this, review Vault Settings now.").format(
                ", ".join(changed)
            ),
            document_type="Vault Settings",
            document_name="Vault Settings",
        )

    def changed_sensitive_fields(self) -> list:
        """Names (never values) of the sensitive settings this save changes."""
        before = self.get_doc_before_save()
        if not before:
            return []

        changed = [f for f in SENSITIVE_FIELDS if self.meta.has_field(f) and self.has_value_changed(f)]
        # Password fields hold a mask unless a new value was typed in.
        for f in SENSITIVE_PASSWORD_FIELDS:
            value = self.get(f)
            if self.meta.has_field(f) and value and set(str(value)) != {"*"}:
                changed.append(f)
        return changed

    def onload(self):
        """Ensure settings is not submittable and docstatus is 0 (Editable/Saveable)."""
        frappe.db.sql("UPDATE `tabDocType` SET is_submittable = 0 WHERE name = 'Vault Settings'")
        if self.docstatus != 0:
            frappe.db.set_single_value("Vault Settings", "docstatus", 0)
            self.docstatus = 0


def get_vault_settings():
    """Get cached vault settings."""
    return frappe.get_cached_doc("Vault Settings")
