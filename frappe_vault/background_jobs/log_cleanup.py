"""Audit log cleanup & manual purge background tasks."""

import frappe
from frappe import _
from frappe.utils import add_days, today


@frappe.whitelist()
def cleanup_old_logs() -> dict:
    """Delete audit logs older than configured retention period in Vault Settings."""
    if frappe.session.user and frappe.session.user != "Administrator":
        frappe.only_for(["System Manager", "Vault Admin"], True)

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
