"""Post-install setup for Frappe Vault."""

import os

import frappe


def after_install():
    """Run after app install."""

    # Ensure module exists first
    ensure_module()

    frappe.clear_cache()

    create_roles()
    grant_roles_to_admin()
    create_default_settings()
    create_default_folders()
    sync_navigation_fixtures()

    frappe.db.commit()  # nosemgrep


def after_migrate():
    """Run after bench migrate."""
    ensure_module()
    create_roles()
    grant_roles_to_admin()
    create_default_settings()
    sync_navigation_fixtures()


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
    """Automatically assign Vault Admin role to Administrator and System Managers."""
    vault_roles = ["Vault Admin"]

    # 1. Assign to Administrator
    if frappe.db.exists("User", "Administrator"):
        admin_doc = frappe.get_doc("User", "Administrator")
        existing_roles = {r.role for r in admin_doc.roles}
        updated = False
        for r_name in vault_roles:
            if r_name not in existing_roles:
                admin_doc.append("roles", {"role": r_name})
                updated = True
        if updated:
            admin_doc.save(ignore_permissions=True)

    # 2. Assign to active System Manager users
    sys_managers = frappe.get_all(
        "Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"
    )
    for u_name in sys_managers:
        if u_name in ["Administrator", "Guest"]:
            continue
        try:
            u_doc = frappe.get_doc("User", u_name)
            u_roles = {r.role for r in u_doc.roles}
            added = False
            for r_name in vault_roles:
                if r_name not in u_roles:
                    u_doc.append("roles", {"role": r_name})
                    added = True
            if added:
                u_doc.save(ignore_permissions=True)
        except Exception:
            pass


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


def sync_navigation_fixtures():
    """(Re)create the Desk desktop icon and sidebar for Vault from their fixture files.

    `DocType` and `Workspace` are synced from an app's module folder automatically
    on every `bench migrate`. `Desktop Icon` and `Workspace Sidebar` are not —
    Frappe's orphan-cleanup pass only checks that a matching fixture file exists
    to decide whether to leave a `standard` record alone; nothing keeps the
    record's *content* in step with the file, and nothing recreates the record if
    it is ever deleted (by the cleanup pass itself, or by hand). Importing both
    fixtures directly, on every install and every migrate, closes both gaps —
    the vault's entry in the Desk app grid and its Desk sidebar are as durable as
    everything else this app ships.
    """
    from frappe.modules.import_file import import_file_by_path

    app_path = frappe.get_app_path("frappe_vault")
    for relative_path in ("desktop_icon/vault.json", "workspace_sidebar/vault.json"):
        path = os.path.join(app_path, relative_path)
        try:
            import_file_by_path(path, force=True, ignore_version=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Frappe Vault Navigation Fixture Import Failed ({relative_path})",
            )
