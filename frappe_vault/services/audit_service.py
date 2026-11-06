"""Audit service — centralized audit logging for all vault operations."""

import frappe
from frappe.utils import now_datetime


def _create_log(action: str, secret: str = None, folder: str = None, details: dict = None):
    """Create an audit log entry. Never throws — failures are logged silently."""
    try:
        # Outside an HTTP request `frappe.request` is an unbound proxy: it is
        # falsy, and reading an attribute from it raises RuntimeError (not
        # AttributeError), so test truthiness first. A bound request can still
        # lack headers (test harness); never let either drop the audit entry.
        request = getattr(frappe, "request", None)
        headers = (request.headers if request else None) or {}
        log = frappe.get_doc(
            {
                "doctype": "Vault Audit Log",
                "action": action,
                "secret": secret,
                "folder": folder,
                "user": frappe.session.user,
                "timestamp": now_datetime(),
                "ip_address": getattr(frappe.local, "request_ip", "") or "",
                "user_agent": (headers.get("User-Agent") or "")[:500],
                "details": frappe.as_json(details) if details else None,
            }
        )
        log.insert(ignore_permissions=True)
    except Exception:
        try:
            frappe.log_error(title=f"Vault Audit Log Failed ({action})", message=frappe.get_traceback())
        except Exception:
            pass


# --- Doc event hooks (called from hooks.py doc_events) ---


def log_secret_created(doc, method):
    _create_log("Created", secret=doc.name, folder=getattr(doc, "folder", None))


def log_secret_updated(doc, method):
    _create_log("Updated", secret=doc.name, folder=getattr(doc, "folder", None))


def log_secret_deleted(doc, method):
    try:
        frappe.db.sql("UPDATE `tabVault Audit Log` SET secret = NULL WHERE secret = %s", (doc.name,))
    except Exception:
        pass
    _create_log(
        "Deleted",
        secret=None,
        folder=getattr(doc, "folder", None),
        details={"secret_name": doc.name, "title": getattr(doc, "title", doc.name)},
    )


def log_share_created(doc, method=None):
    if doc.get("is_revoked"):
        log_share_removed(doc, method)
        return

    recipient = doc.user if doc.share_type == "User" else doc.frappe_role
    details = {"share_type": doc.share_type, "permission": doc.permission_level, "recipient": recipient}
    if doc.expires_on:
        details["expires_on"] = str(doc.expires_on)
    _create_log(
        "Shared",
        secret=doc.shared_name if doc.shared_doctype == "Vault Secret" else None,
        folder=doc.shared_name if doc.shared_doctype == "Vault Folder" else None,
        details=details,
    )


def log_share_removed(doc, method=None):
    if method == "on_trash" and doc.get("is_revoked"):
        return
    recipient = doc.user if doc.share_type == "User" else doc.frappe_role
    _create_log(
        "Unshared",
        secret=doc.shared_name if doc.shared_doctype == "Vault Secret" else None,
        folder=doc.shared_name if doc.shared_doctype == "Vault Folder" else None,
        details={"share_type": doc.share_type, "recipient": recipient},
    )


# --- Callable from services ---


def log_secret_viewed(secret_name: str):
    folder = frappe.db.get_value("Vault Secret", secret_name, "folder")
    _create_log("Viewed", secret=secret_name, folder=folder)


def log_secret_copied(secret_name: str, field: str = "password"):
    folder = frappe.db.get_value("Vault Secret", secret_name, "folder")
    _create_log("Copied", secret=secret_name, folder=folder, details={"field": field})


def log_password_generated():
    _create_log("Generated")


def log_export(count: int, format: str):
    _create_log("Exported", details={"count": count, "format": format})


def log_import(count: int, format: str):
    _create_log("Imported", details={"count": count, "format": format})


def log_one_time_link_created(link_doc):
    folder = frappe.db.get_value("Vault Secret", link_doc.secret, "folder")
    _create_log(
        "Shared",
        secret=link_doc.secret,
        folder=folder,
        details={
            "type": "One Time Link",
            "one_time_link": link_doc.name,
            "max_views": link_doc.max_views,
            "expires_at": str(link_doc.expires_at) if link_doc.expires_at else None,
        },
    )


def log_one_time_link_consumed(link_doc):
    folder = frappe.db.get_value("Vault Secret", link_doc.secret, "folder")
    _create_log(
        "Viewed",
        secret=link_doc.secret,
        folder=folder,
        details={
            "type": "One Time Link",
            "one_time_link": link_doc.name,
            "view_count": link_doc.view_count,
            "max_views": link_doc.max_views,
        },
    )
