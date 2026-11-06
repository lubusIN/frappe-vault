"""Vault One Time Link DocType controller."""

import secrets

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, get_url, now_datetime

from frappe_vault.integrations.transit import TransitPasswordsMixin


def get_clean_url() -> str:
    """Get site URL stripped of developer port :8000 if proxied."""
    url = get_url()
    if frappe.conf.get("host_name"):
        url = frappe.conf.get("host_name")
    elif ":8000" in url:
        url = url.replace(":8000", "")
    return url.rstrip("/")


class VaultOneTimeLink(TransitPasswordsMixin, Document):
    """One-time shareable links for secrets."""

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
        self.last_accessed_ip = getattr(frappe.local, "request_ip", "") or ""
        # Unbound outside HTTP (falsy); a bound request can still lack headers.
        request = getattr(frappe, "request", None)
        headers = (request.headers if request else None) or {}
        if headers:
            self.last_user_agent = (headers.get("User-Agent") or "")[:500]

        self.save(ignore_permissions=True)
