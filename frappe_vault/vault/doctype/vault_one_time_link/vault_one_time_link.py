"""Vault One Time Link DocType controller."""

import secrets

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, get_url, now_datetime


def get_clean_url() -> str:
    """Get site URL stripped of developer port :8000 if proxied."""
    url = get_url()
    if frappe.conf.get("host_name"):
        url = frappe.conf.get("host_name")
    elif ":8000" in url:
        url = url.replace(":8000", "")
    return url.rstrip("/")


class VaultOneTimeLink(Document):
    """One-time shareable links for secrets."""

    def validate(self):
        self.validate_permissions()
        self.validate_limits()

    def validate_permissions(self):
        user = frappe.session.user
        if not user or user == "Guest":
            frappe.throw(_("Authentication required"), frappe.PermissionError)

        if frappe.flags.in_install or frappe.flags.in_migrate:
            return

        roles = frappe.get_roles(user)
        is_admin = user == "Administrator" or "Vault Admin" in roles or "System Manager" in roles
        if is_admin:
            return

        if not self.secret:
            frappe.throw(_("Secret is required"), frappe.ValidationError)

        if not frappe.has_permission("Vault Secret", "read", self.secret):
            frappe.throw(
                _("You don't have permission to create a share link for this secret"),
                frappe.PermissionError,
            )

    def validate_limits(self):
        if self.max_views and self.max_views > 100:
            self.max_views = 100
        elif not self.max_views or self.max_views < 1:
            self.max_views = 1

        from frappe.utils import add_days

        max_expiry = add_days(now_datetime(), 30)
        if self.expires_at:
            if get_datetime(self.expires_at) > get_datetime(max_expiry):
                self.expires_at = max_expiry
        else:
            self.expires_at = add_days(now_datetime(), 7)

    def before_insert(self):
        """Generate unique token, shareable URL, and set creator."""
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        self.created_by = frappe.session.user
        self.share_url = f"{get_clean_url()}/vault/shared/{self.token}"

    def after_insert(self):
        """Log audit entry when one time link is created."""
        from frappe_vault.services.audit_service import log_one_time_link_created

        log_one_time_link_created(self)

    def before_save(self):
        """Ensure shareable URL is clean and up to date."""
        if self.token:
            self.share_url = f"{get_clean_url()}/vault/shared/{self.token}"

    def is_valid(self):
        """Check if link is still valid."""
        if self.is_consumed:
            return False
        if (self.view_count or 0) >= (self.max_views or 1):
            return False
        if self.expires_at:
            exp = get_datetime(self.expires_at)
            now = get_datetime(now_datetime())
            if now > exp:
                return False
        return True

    def consume(self):
        """Mark the link as consumed, record accessor metadata, and increment view count."""
        self.view_count = (self.view_count or 0) + 1
        if self.view_count >= (self.max_views or 1):
            self.is_consumed = 1

        self.last_accessed_at = now_datetime()
        self.last_accessed_ip = getattr(frappe.local, "request_ip", "")
        if hasattr(frappe, "request") and frappe.request:
            self.last_user_agent = frappe.request.headers.get("User-Agent", "")[:500]

        self.save(ignore_permissions=True)
