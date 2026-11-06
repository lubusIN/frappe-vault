"""Demo Data API Controller — whitelisted endpoints delegating to domain service."""

import frappe

from frappe_vault.services import demo_service


@frappe.whitelist()
def check_has_demo_data() -> bool:
    """Check if demo data currently exists."""
    return demo_service.check_has_demo_data()


@frappe.whitelist(methods=["POST"])
def generate_demo_data() -> dict:
    """Generate realistic demo folders, secrets, bookmarks, and share accesses."""
    return demo_service.generate_demo_data()


@frappe.whitelist(methods=["POST"])
def clear_demo_data() -> dict:
    """Clear all generated demo secrets, bookmarks, shares, and folders."""
    return demo_service.clear_demo_data()
