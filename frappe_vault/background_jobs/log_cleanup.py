"""Audit log cleanup & manual purge background tasks."""

import frappe
from frappe import _
from frappe.utils import add_days, today


@frappe.whitelist(methods=["POST"])
def cleanup_old_logs() -> dict:
    """Delete audit logs older than configured retention period in Vault Settings.

    Runs weekly from the scheduler (as Administrator) and from the "Purge Expired
    Logs Now" button on Vault Settings. Deleting audit history must stay an admin
    action: without this check any logged-in user could call the endpoint.
    """
    # Explicit check rather than frappe.only_for, which v15 skips under tests.
    if frappe.session.user != "Administrator" and not {"System Manager", "Vault Admin"} & set(
        frappe.get_roles()
    ):
        frappe.throw(_("Only Vault Admins can purge audit logs."), frappe.PermissionError)

    retention_days = frappe.db.get_single_value("Vault Settings", "log_retention_days") or 365
    threshold = add_days(today(), -int(retention_days))

    logs_to_delete = frappe.get_all("Vault Audit Log", filters={"timestamp": ("<", threshold)}, pluck="name")

    count = len(logs_to_delete)
    if count > 0:
        frappe.db.delete("Vault Audit Log", {"name": ("in", logs_to_delete)})
        frappe.db.commit()  # nosemgrep

    return {
        "deleted_count": count,
        "retention_days": retention_days,
        "threshold": str(threshold),
        "message": _("Purged {0} audit logs older than {1} days.").format(count, retention_days),
    }
