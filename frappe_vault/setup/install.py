"""Post-install setup for Frappe Vault."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

VAULT_CUSTOM_FIELDS = ["vault_enabled", "vault_is_default"]
VAULT_DEFAULT_TEMPLATE_NAME = "Vault Invitation Default"


def after_install():
    """Run after app install."""

    # Ensure module exists first
    ensure_module()

    frappe.clear_cache()

    create_roles()
    grant_roles_to_admin()
    create_default_settings()
    create_default_folders()
    create_desktop_icon()
    unpin_home_page()
    add_email_template_custom_fields()
    create_default_email_template()

    frappe.db.commit()  # nosemgrep


def after_migrate():
    """Run after bench migrate."""
    ensure_module()
    create_roles()
    grant_roles_to_admin()
    create_default_settings()
    unpin_home_page()
    add_email_template_custom_fields()
    create_default_email_template()


def unpin_home_page():
    """Ensure installing Vault doesn't hijack the site's default home page."""
    try:
        # Reset Website Settings if it was automatically set to vault
        if frappe.db.exists("Website Settings", "Website Settings"):
            ws = frappe.get_single("Website Settings")
            if ws.home_page in ["vault", "/vault", "frappe_vault"]:
                ws.db_set("home_page", "")
                frappe.clear_cache(doctype="Website Settings")
    except Exception:
        pass


def ensure_module():
    """Create Vault module if missing."""
    if not frappe.db.exists("Module Def", "Vault"):
        frappe.get_doc({"doctype": "Module Def", "module_name": "Vault", "app_name": "frappe_vault"}).insert(
            ignore_permissions=True
        )


def create_roles():
    """Create vault-specific roles with native Desk access settings."""
    if not frappe.db.exists("Role", "Vault User"):
        frappe.get_doc({"doctype": "Role", "role_name": "Vault User", "desk_access": 0}).insert(
            ignore_permissions=True
        )
    else:
        frappe.db.set_value("Role", "Vault User", "desk_access", 0)

    if not frappe.db.exists("Role", "Vault Admin"):
        frappe.get_doc({"doctype": "Role", "role_name": "Vault Admin", "desk_access": 1}).insert(
            ignore_permissions=True
        )


def grant_roles_to_admin():
    """Automatically assign Vault Admin role to Administrator and System Managers, and remove Vault User."""
    vault_roles = ["Vault Admin"]

    # Helper to update roles
    def enforce_admin_roles(user_name):
        try:
            doc = frappe.get_doc("User", user_name)
            existing_roles = {r.role for r in doc.roles}
            updated = False

            # Add Vault Admin
            for r_name in vault_roles:
                if r_name not in existing_roles:
                    doc.append("roles", {"role": r_name})
                    updated = True

            # Remove Vault User
            roles_to_keep = []
            for r in doc.roles:
                if r.role == "Vault User":
                    updated = True
                else:
                    roles_to_keep.append(r)
            doc.roles = roles_to_keep

            if updated:
                doc.save(ignore_permissions=True)
        except Exception:
            pass

    # 1. Assign to Administrator
    if frappe.db.exists("User", "Administrator"):
        enforce_admin_roles("Administrator")

    # 2. Assign to active System Manager users
    sys_managers = frappe.get_all(
        "Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"
    )
    for u_name in sys_managers:
        if u_name not in ["Administrator", "Guest"]:
            enforce_admin_roles(u_name)


def create_default_settings():
    """Initialize Vault Settings singleton."""
    if frappe.db.exists("DocType", "Vault Settings"):
        settings = frappe.get_doc("Vault Settings")
        settings.save(ignore_permissions=True)


def create_default_folders():
    """Create starter folders."""
    folders = [
        {"folder_name": "Work", "icon": "briefcase"},
        {"folder_name": "Personal", "icon": "user"},
        {"folder_name": "Finance", "icon": "credit-card"},
        {"folder_name": "Servers", "icon": "server"},
    ]

    if frappe.db.exists("DocType", "Vault Folder"):
        for folder in folders:
            if not frappe.db.exists("Vault Folder", folder["folder_name"]):
                frappe.get_doc({"doctype": "Vault Folder", **folder}).insert(ignore_permissions=True)


def create_desktop_icon():
    """Create Desk desktop icon for the Vault app."""
    try:
        from frappe.desk.doctype.desktop_icon.desktop_icon import (
            create_desktop_icons_from_installed_apps,
        )

        create_desktop_icons_from_installed_apps()
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Frappe Vault Desktop Icon Creation Failed",
        )


def add_email_template_custom_fields():
    """Add vault_enabled and vault_is_default custom fields to Email Template."""
    meta = frappe.get_meta("Email Template")

    fields = [
        {
            "default": "1",
            "fieldname": "vault_enabled",
            "fieldtype": "Check",
            "label": "Enabled for Vault",
            "insert_after": "",
        },
        {
            "default": "0",
            "fieldname": "vault_is_default",
            "fieldtype": "Check",
            "label": "Default Vault Template",
            "insert_after": "vault_enabled",
        },
    ]

    fields = [field for field in fields if not meta.has_field(field["fieldname"])]
    if not fields:
        return

    create_custom_fields({"Email Template": fields})
    frappe.clear_cache(doctype="Email Template")


def create_default_email_template():
    """Create the default Vault invitation email template if it doesn't already exist."""
    if not frappe.db.exists("Email Template", "Vault Invitation Default"):
        doc = frappe.new_doc("Email Template")
        doc.name = "Vault Invitation Default"
        doc.subject = "You have been invited to join {{ title }}"
        doc.use_html = 1
        doc.vault_enabled = 1
        doc.vault_is_default = 1
        doc.response_html = """<p>Hello,</p>

<p>You have been invited to join <strong>{{ title }}</strong>.</p>

<p>Click the link below to accept your invitation:</p>

<p>
  <a href="{{ invite_link }}" style="display: inline-block; padding: 10px 20px; color: white; background-color: #007bff; text-decoration: none; border-radius: 5px;">
    Accept Invitation
  </a>
</p>

<p>If you have any questions, feel free to contact your administrator.</p>

<p>Thanks,<br>{{ title }} Team</p>"""
        doc.insert(ignore_permissions=True)


def before_uninstall():
    """Clean up all data Vault injected into core Frappe doctypes."""
    _remove_default_email_template()
    _remove_email_template_custom_fields()
    _remove_vault_roles()


def _remove_default_email_template():
    """Delete the default Vault invitation template created during install."""
    try:
        if frappe.db.exists("Email Template", VAULT_DEFAULT_TEMPLATE_NAME):
            frappe.delete_doc("Email Template", VAULT_DEFAULT_TEMPLATE_NAME, ignore_permissions=True)
    except Exception:
        pass


def _remove_email_template_custom_fields():
    """Remove the vault_enabled and vault_is_default custom fields from Email Template."""
    try:
        for fieldname in VAULT_CUSTOM_FIELDS:
            existing = frappe.db.get_value(
                "Custom Field",
                {"dt": "Email Template", "fieldname": fieldname},
                "name",
            )
            if existing:
                frappe.delete_doc("Custom Field", existing, ignore_permissions=True)
        frappe.clear_cache(doctype="Email Template")
    except Exception:
        pass


def _remove_vault_roles():
    """Remove Vault User and Vault Admin roles and their user assignments."""
    try:
        for role in ["Vault Admin", "Vault User"]:
            if frappe.db.exists("Role", role):
                # 1. Remove this role from all users who have it to prevent LinkExistsError
                frappe.db.delete("Has Role", {"role": role})
                # 2. Delete the Role itself
                frappe.delete_doc("Role", role, ignore_permissions=True, force=True)
    except Exception:
        pass
