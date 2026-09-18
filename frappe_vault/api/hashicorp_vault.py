import frappe
from frappe import _


@frappe.whitelist()
def sync_secret(name: str) -> dict:
    """Push one secret's current values to HashiCorp Vault. Requires write access."""
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)

    from frappe_vault.utils.permissions import has_secret_permission

    if not has_secret_permission(name, ptype="write"):
        frappe.throw(_("You don't have permission to sync this secret"), frappe.PermissionError)

    from frappe_vault.integrations.hashicorp_vault import push_secret

    return push_secret(name)


@frappe.whitelist()
def test_connection() -> dict:
    """Verify the configured HashiCorp Vault URL and token both work."""
    roles = frappe.get_roles()
    if "System Manager" not in roles and "Vault Admin" not in roles:
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    from frappe_vault.integrations.hashicorp_vault import check_connection

    return check_connection()
