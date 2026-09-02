"""Folders API — folder CRUD endpoints."""

import frappe
from frappe import _


@frappe.whitelist()
def get_all() -> list[dict]:
    folders = frappe.get_list(
        "Vault Folder",
        fields=["name", "folder_name", "icon", "owner", "parent_vault_folder", "is_group", "lft", "rgt"],
        order_by="lft asc",
    )

    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = user == "Administrator" or "Vault Admin" in roles or "System Manager" in roles

    writable_folder_names = set()
    if not is_admin:
        # User has write access if they have Edit/Full Control on this folder OR any of its ancestors
        writable_shares = frappe.db.sql(
            """
            SELECT `tabVault Folder`.name FROM `tabVault Folder`
            WHERE EXISTS (
                SELECT 1 FROM `tabVault Folder` ancestor
                JOIN `tabVault Share` vs ON vs.shared_doctype = 'Vault Folder' AND vs.shared_name = ancestor.name
                WHERE `tabVault Folder`.lft >= ancestor.lft AND `tabVault Folder`.rgt <= ancestor.rgt
                AND vs.is_revoked = 0
                AND vs.permission_level IN ('Edit', 'Full Control')
                AND (
                    (vs.share_type = 'User' AND vs.user = %(user)s)
                    OR (vs.share_type = 'Role' AND vs.frappe_role IN (
                        SELECT role FROM `tabHas Role` WHERE parent = %(user)s
                    ) AND NOT EXISTS (
                        SELECT 1 FROM `tabVault Share` override
                        WHERE override.shared_doctype = 'Vault Folder'
                        AND override.shared_name = vs.shared_name
                        AND override.share_type = 'User'
                        AND override.user = %(user)s
                        AND override.is_revoked = 1
                    ))
                )
                AND (vs.expires_on IS NULL OR vs.expires_on > NOW())
            )
            """,
            {"user": user},
            pluck=True,
        )
        writable_folder_names = set(writable_shares)

    for f in folders:
        if is_admin or f.get("owner") == user or f.get("name") in writable_folder_names:
            f["can_write"] = 1
        else:
            f["can_write"] = 0

    return folders


@frappe.whitelist()
def create(
    folder_name: str,
    icon: str | None = None,
    parent_vault_folder: str | None = None,
    is_group: int = 0,
    **kwargs,
) -> dict:
    if not folder_name or not isinstance(folder_name, str):
        frappe.throw(_("Folder name is required"), frappe.ValidationError)
    if not frappe.has_permission("Vault Folder", "create"):
        frappe.throw(_("You don't have permission to create folders"), frappe.PermissionError)

    doc = frappe.get_doc(
        {
            "doctype": "Vault Folder",
            "folder_name": folder_name,
            "icon": icon,
            "parent_vault_folder": parent_vault_folder,
            "is_group": is_group,
        }
    )
    doc.insert()

    # Notify Vault Admins of new folder creation
    from frappe_vault.services.notification_service import notify_vault_admins

    creator_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    notify_vault_admins(
        subject=f"New Folder Created: '{doc.folder_name}'",
        email_content=f"{creator_name} created folder '{doc.folder_name}'.",
        document_type="Vault Folder",
        document_name=doc.name,
    )

    return {"name": doc.name}


@frappe.whitelist()
def delete(
    name: str, delete_secrets: bool = False, subfolder_action: str = "move_up", target_folder: str = None
) -> dict:
    if not name or not isinstance(name, str):
        frappe.throw(_("Invalid folder identifier"), frappe.ValidationError)
    from frappe_vault.utils.permissions import has_folder_permission

    if not has_folder_permission(name, ptype="delete"):
        frappe.throw(_("You don't have permission to delete this folder"), frappe.PermissionError)

    folder_name = frappe.db.get_value("Vault Folder", name, "folder_name") or name

    should_delete_secrets = (
        frappe.utils.cint(delete_secrets) if not isinstance(delete_secrets, bool) else delete_secrets
    )

    # Handle Subfolders
    folder_doc = frappe.get_doc("Vault Folder", name)
    children = frappe.get_all("Vault Folder", filters={"parent_vault_folder": name}, pluck="name")

    if subfolder_action == "delete_all":
        for child in children:
            # Recursively delete children and their secrets
            delete(child, delete_secrets=should_delete_secrets, subfolder_action="delete_all")
    else:
        # Move children to another folder (or root)
        new_parent = None
        if subfolder_action == "move_up":
            new_parent = folder_doc.parent_vault_folder
        elif subfolder_action == "move_to" and target_folder:
            new_parent = target_folder

        for child in children:
            frappe.db.set_value("Vault Folder", child, "parent_vault_folder", new_parent)
            # Fetch and save doc to rebuild nested set indices
            c_doc = frappe.get_doc("Vault Folder", child)
            c_doc.save(ignore_permissions=True)

    secrets = frappe.get_all("Vault Secret", filters={"folder": name}, fields=["name"])
    if should_delete_secrets:
        from frappe_vault.services.secret_service import delete_secret

        for s in secrets:
            delete_secret(s.name)
    else:
        # Move secrets to root (no folder)
        for s in secrets:
            frappe.db.set_value("Vault Secret", s.name, "folder", None)

    # Delete folder shares
    shares = frappe.get_all(
        "Vault Share", filters={"shared_doctype": "Vault Folder", "shared_name": name}, pluck="name"
    )
    for share_name in shares:
        frappe.delete_doc("Vault Share", share_name, force=True, ignore_permissions=True)

    # Unlink historical Vault Audit Log records for this folder so audit trail remains intact without blocking deletion
    frappe.db.sql("UPDATE `tabVault Audit Log` SET folder = NULL WHERE folder = %s", (name,))

    # Delete the folder document itself
    frappe.delete_doc(
        "Vault Folder", name, force=True, ignore_doctypes=["Vault Audit Log"], ignore_permissions=True
    )

    # Notify Vault Admins
    from frappe_vault.services.notification_service import notify_vault_admins

    actor_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    notify_vault_admins(
        subject=f"Folder Deleted: '{folder_name}'",
        email_content=f"{actor_name} deleted folder '{folder_name}'.",
        document_type="Vault Folder",
        document_name=name,
    )

    return {"deleted": name, "deleted_secrets": bool(should_delete_secrets)}


@frappe.whitelist()
def update(
    name: str,
    folder_name: str | None = None,
    icon: str | None = None,
    parent_vault_folder: str | None = None,
    is_group: int | None = None,
    **kwargs,
) -> dict:
    if not name or not isinstance(name, str):
        frappe.throw(_("Invalid folder identifier"), frappe.ValidationError)
    from frappe_vault.utils.permissions import has_folder_permission

    if not has_folder_permission(name, ptype="write"):
        frappe.throw(_("You don't have permission to update this folder"), frappe.PermissionError)

    if folder_name and folder_name != name and isinstance(folder_name, str):
        from frappe.model.rename_doc import rename_doc as _rename_doc

        name = _rename_doc("Vault Folder", name, folder_name)

    doc = frappe.get_doc("Vault Folder", name)
    if icon is not None:
        doc.icon = icon
    if parent_vault_folder is not None:
        doc.parent_vault_folder = parent_vault_folder
    if is_group is not None:
        doc.is_group = is_group

    doc.save()
    return {"name": doc.name}


@frappe.whitelist()
def get_folder_secrets(folder_name: str, limit: int = 50, offset: int = 0) -> dict:
    if not folder_name or not isinstance(folder_name, str):
        frappe.throw(_("Invalid folder identifier"), frappe.ValidationError)
    if not frappe.has_permission("Vault Folder", "read", folder_name):
        frappe.throw(_("You don't have permission to view this folder"), frappe.PermissionError)

    from frappe_vault.utils.constants import LIST_VIEW_FIELDS

    filters = {"folder": folder_name}
    secrets = frappe.get_list(
        "Vault Secret",
        filters=filters,
        fields=LIST_VIEW_FIELDS,
        order_by="modified desc",
        limit=int(limit),
        limit_start=int(offset),
    )
    total = frappe.db.count("Vault Secret", filters=filters)
    return {"secrets": secrets, "total": total}
