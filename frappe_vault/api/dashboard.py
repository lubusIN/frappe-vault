"""Vault Dashboard API — Whitelisted endpoints for dashboard layout and charts."""

import json

import frappe
from frappe import _

# Allowlisted chart names to prevent arbitrary function dispatch
ALLOWED_CHART_NAMES = {
    "total_secrets",
    "active_shares",
    "bookmarks",
    "vault_trend",
    "secrets_by_folder",
    "recently_accessed",
    "security_score",
    "revoked_shares",
}


@frappe.whitelist()
def get_vault_dashboard(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> list[dict]:
    from frappe_vault.services.dashboard_service import get_dashboard_layout

    return get_dashboard_layout(from_date=from_date, to_date=to_date, user=user)


@frappe.whitelist()
def get_chart(
    name: str,
    type: str,
    from_date: str | None = None,
    to_date: str | None = None,
    user: str | None = None,
) -> dict:
    # Only allow known chart names
    if name not in ALLOWED_CHART_NAMES:
        frappe.throw(_("Invalid chart name"), frappe.ValidationError)

    # Enforce user scope for non-admins
    user_roles = frappe.get_roles()
    is_admin = (
        frappe.session.user == "Administrator"
        or "Vault Admin" in user_roles
        or "System Manager" in user_roles
    )
    if not is_admin:
        user = frappe.session.user

    from frappe_vault.services import dashboard_service

    method_name = f"get_{name}"
    if hasattr(dashboard_service, method_name):
        func = getattr(dashboard_service, method_name)
        return func(from_date, to_date, user)
    return {"error": _("Chart not found")}


@frappe.whitelist()
def save_dashboard_layout(layout: str | list) -> dict:
    user_roles = frappe.get_roles()
    is_admin = (
        frappe.session.user == "Administrator"
        or "Vault Admin" in user_roles
        or "System Manager" in user_roles
    )
    if not is_admin:
        frappe.throw(_("Only Vault Admins can modify the dashboard layout."), frappe.PermissionError)

    if isinstance(layout, list):
        layout = json.dumps(layout)
    frappe.db.set_single_value("Vault Settings", "dashboard_layout", layout)
    frappe.db.commit()  # nosemgrep
    return {"status": "success"}


@frappe.whitelist()
def reset_dashboard_layout() -> dict:
    user_roles = frappe.get_roles()
    is_admin = (
        frappe.session.user == "Administrator"
        or "Vault Admin" in user_roles
        or "System Manager" in user_roles
    )
    if not is_admin:
        frappe.throw(_("Only Vault Admins can reset the dashboard layout."), frappe.PermissionError)

    frappe.db.set_single_value("Vault Settings", "dashboard_layout", None)
    frappe.db.commit()  # nosemgrep
    return {"status": "reset"}
