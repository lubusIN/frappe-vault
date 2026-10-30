"""Demo data service handling generation, verification, and cleanup domain logic."""

import json

import frappe
from frappe import _

from frappe_vault.services.demo_data_catalog import DEMO_FOLDER_SHARES, DEMO_FOLDERS, DEMO_SECRETS


def check_has_demo_data() -> bool:
    """Check if demo data exists in system defaults or actual records."""
    has_demo = frappe.db.get_default("frappe_vault_has_demo_data")
    if has_demo == "1":
        records_raw = frappe.db.get_default("frappe_vault_demo_records")
        if records_raw:
            try:
                records = json.loads(records_raw)
                for s_name in records.get("secrets", []):
                    if frappe.db.exists("Vault Secret", s_name):
                        return True
            except Exception:
                pass
        frappe.db.set_default("frappe_vault_has_demo_data", "0")
    return False


def generate_demo_data() -> dict:
    """Orchestrate generation of realistic demo folders, secrets, bookmarks, and shares."""
    if check_has_demo_data():
        return {"status": "already_exists", "message": _("Demo data is already generated.")}

    created_secrets = []
    created_folders = []

    # 1. Create Demo Folders
    for f in DEMO_FOLDERS:
        if not frappe.db.exists("Vault Folder", f["folder_name"]):
            doc = frappe.get_doc({"doctype": "Vault Folder", **f}).insert(ignore_permissions=True)
            created_folders.append(doc.name)
        else:
            created_folders.append(f["folder_name"])

    # Add folder share access
    for fs in DEMO_FOLDER_SHARES:
        f_name = fs["folder_name"]
        if f_name in created_folders and not frappe.db.exists(
            "Vault Share",
            {
                "shared_doctype": "Vault Folder",
                "shared_name": f_name,
                "share_type": "Role",
                "frappe_role": fs["frappe_role"],
            },
        ):
            frappe.get_doc(
                {
                    "doctype": "Vault Share",
                    "share_type": "Role",
                    "frappe_role": fs["frappe_role"],
                    "permission_level": fs.get("permission_level", "View Only"),
                    "shared_doctype": "Vault Folder",
                    "shared_name": f_name,
                    "shared_by": frappe.session.user,
                }
            ).insert(ignore_permissions=True)

    # 2. Create Demo Secrets
    for s_raw in DEMO_SECRETS:
        s = dict(s_raw)  # copy dict before mutating
        is_bookmark = s.pop("is_bookmark", 0)
        share_role = s.pop("share_role", None)
        share_perm = s.pop("share_perm", "View Only")

        doc = frappe.get_doc({"doctype": "Vault Secret", **s}).insert(ignore_permissions=True)
        created_secrets.append(doc.name)

        if is_bookmark:
            if not frappe.db.exists("Vault Bookmark", {"user": frappe.session.user, "secret": doc.name}):
                frappe.get_doc(
                    {"doctype": "Vault Bookmark", "user": frappe.session.user, "secret": doc.name}
                ).insert(ignore_permissions=True)

        if share_role:
            if not frappe.db.exists(
                "Vault Share",
                {
                    "shared_doctype": "Vault Secret",
                    "shared_name": doc.name,
                    "share_type": "Role",
                    "frappe_role": share_role,
                },
            ):
                frappe.get_doc(
                    {
                        "doctype": "Vault Share",
                        "share_type": "Role",
                        "frappe_role": share_role,
                        "permission_level": share_perm,
                        "shared_doctype": "Vault Secret",
                        "shared_name": doc.name,
                        "shared_by": frappe.session.user,
                    }
                ).insert(ignore_permissions=True)

    frappe.db.set_default(
        "frappe_vault_demo_records", json.dumps({"secrets": created_secrets, "folders": created_folders})
    )
    frappe.db.set_default("frappe_vault_has_demo_data", "1")
    frappe.db.commit()  # nosemgrep

    return {"status": "success", "secrets": len(created_secrets)}


def clear_demo_data() -> dict:
    """Clear all generated demo secrets, bookmarks, shares, and empty folders."""
    records_raw = frappe.db.get_default("frappe_vault_demo_records")
    records = {"secrets": [], "folders": []}
    if records_raw:
        try:
            records = json.loads(records_raw)
        except Exception:
            pass

    # Collect all possible demo secrets (by ID or by catalog title)
    secret_names = set(records.get("secrets", []))
    catalog_titles = [s["title"] for s in DEMO_SECRETS]
    for s_doc in frappe.get_all("Vault Secret", filters={"title": ["in", catalog_titles]}, pluck="name"):
        secret_names.add(s_doc)

    # Delete recorded secrets along with their bookmarks, links, and shares
    for s_name in secret_names:
        if frappe.db.exists("Vault Secret", s_name):
            for fav in frappe.get_all("Vault Bookmark", filters={"secret": s_name}, pluck="name"):
                frappe.delete_doc("Vault Bookmark", fav, ignore_permissions=True, force=True)
            for link in frappe.get_all("Vault One Time Link", filters={"secret": s_name}, pluck="name"):
                frappe.delete_doc("Vault One Time Link", link, ignore_permissions=True, force=True)
            for sh in frappe.get_all(
                "Vault Share", filters={"shared_doctype": "Vault Secret", "shared_name": s_name}, pluck="name"
            ):
                frappe.delete_doc("Vault Share", sh, ignore_permissions=True, force=True)
            frappe.delete_doc("Vault Secret", s_name, ignore_permissions=True, force=True)

    # Collect all demo folders
    folder_names = set(records.get("folders", []))
    for f in DEMO_FOLDERS:
        folder_names.add(f["folder_name"])

    # Delete demo folders if empty along with their shares
    sorted_folders = frappe.get_all(
        "Vault Folder", filters={"name": ["in", list(folder_names)]}, order_by="lft desc", pluck="name"
    )
    for f_name in sorted_folders:
        for sh in frappe.get_all(
            "Vault Share", filters={"shared_doctype": "Vault Folder", "shared_name": f_name}, pluck="name"
        ):
            frappe.delete_doc("Vault Share", sh, ignore_permissions=True, force=True)
        remaining_secrets = frappe.get_all("Vault Secret", filters={"folder": f_name})
        if not remaining_secrets:
            # Move any manual subfolders to root before deleting the demo parent
            children = frappe.get_all("Vault Folder", filters={"parent_vault_folder": f_name}, pluck="name")
            for child in children:
                frappe.db.set_value("Vault Folder", child, "parent_vault_folder", None)
                c_doc = frappe.get_doc("Vault Folder", child)
                c_doc.save(ignore_permissions=True)

            frappe.delete_doc("Vault Folder", f_name, ignore_permissions=True, force=True)

    # Final cleanup: scrub any orphan share records pointing to deleted records
    for sh in frappe.get_all("Vault Share", fields=["name", "shared_doctype", "shared_name"]):
        if not frappe.db.exists(sh.shared_doctype, sh.shared_name):
            frappe.delete_doc("Vault Share", sh.name, ignore_permissions=True, force=True)

    frappe.db.set_default("frappe_vault_has_demo_data", "0")
    frappe.db.set_default("frappe_vault_demo_records", "")
    frappe.db.commit()  # nosemgrep

    return {"status": "success"}
