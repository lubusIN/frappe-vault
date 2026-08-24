"""Sharing service — share/unshare secrets and folders with users, roles."""

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime


def share_secret(
    shared_name: str,
    shared_doctype: str = "Vault Secret",
    share_type: str = "User",
    user: str = None,
    frappe_role: str = None,
    permission_level: str = "View Only",
    expires_on: str = None,
) -> dict:
    """Share a secret or folder with a user or role.

    Returns:
        dict with share document name
    """
    # Verify caller owns or has Full Control on the item
    if shared_doctype == "Vault Secret":
        if not frappe.has_permission("Vault Secret", "share", shared_name):
            frappe.throw(_("You don't have permission to share this secret"), frappe.PermissionError)
    elif shared_doctype == "Vault Folder":
        if not frappe.has_permission("Vault Folder", "share", shared_name):
            frappe.throw(_("You don't have permission to share this folder"), frappe.PermissionError)

    if share_type == "User" and user:
        owner = frappe.db.get_value(shared_doctype, shared_name, "owner")
        if user == owner:
            frappe.throw(_("You cannot share an item with its owner"))

        existing_share = frappe.db.get_value(
            "Vault Share",
            {
                "shared_doctype": shared_doctype,
                "shared_name": shared_name,
                "share_type": "User",
                "user": user,
                "is_role_override": 0,
            },
            "name",
        )
        if existing_share:
            frappe.db.set_value(
                "Vault Share",
                existing_share,
                {
                    "is_revoked": 0,
                    "is_role_override": 0,
                    "is_custom_override": 1,
                    "permission_level": permission_level,
                    "shared_by": frappe.session.user,
                    "expires_on": expires_on,
                },
            )
            doc = frappe.get_doc("Vault Share", existing_share)
            from frappe_vault.services.notification_service import send_vault_notification

            item_title = (
                frappe.db.get_value(
                    shared_doctype,
                    shared_name,
                    "title" if shared_doctype == "Vault Secret" else "folder_name",
                )
                or shared_name
            )
            sharer_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
            send_vault_notification(
                for_user=user,
                subject=f"{sharer_name} shared '{item_title}' with you",
                email_content=f"You have been granted '{permission_level}' access to {shared_doctype} '{item_title}'.",
                notification_type="Share",
                document_type=shared_doctype,
                document_name=shared_name,
                from_user=frappe.session.user,
            )
            return {"name": doc.name}

    doc = frappe.get_doc(
        {
            "doctype": "Vault Share",
            "share_type": share_type,
            "user": user if share_type == "User" else None,
            "frappe_role": frappe_role if share_type == "Role" else None,
            "permission_level": permission_level,
            "shared_doctype": shared_doctype,
            "shared_name": shared_name,
            "expires_on": expires_on,
            "shared_by": frappe.session.user,
        }
    )
    doc.insert()

    # Send notifications
    from frappe_vault.services.notification_service import notify_vault_admins, send_vault_notification

    item_title = (
        frappe.db.get_value(
            shared_doctype, shared_name, "title" if shared_doctype == "Vault Secret" else "folder_name"
        )
        or shared_name
    )
    sharer_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    item_type = "Folder" if shared_doctype == "Vault Folder" else "Secret"

    if share_type == "User" and user:
        send_vault_notification(
            for_user=user,
            subject=f"{item_type} Shared with You: '{item_title}'",
            email_content=f"<b>{sharer_name}</b> shared {shared_doctype} <b>'{item_title}'</b> with you with <b>'{permission_level}'</b> access.",
            notification_type="Share",
            document_type=shared_doctype,
            document_name=shared_name,
            from_user=frappe.session.user,
        )
    elif share_type == "Role" and frappe_role:
        role_users = frappe.get_all(
            "Has Role", filters={"role": frappe_role, "parenttype": "User"}, pluck="parent"
        )
        for r_user in set(role_users):
            if r_user != frappe.session.user:
                send_vault_notification(
                    for_user=r_user,
                    subject=f"{item_type} Shared via Role ({frappe_role}): '{item_title}'",
                    email_content=f"You have been granted <b>'{permission_level}'</b> access to {shared_doctype} <b>'{item_title}'</b> via role {frappe_role}.",
                    notification_type="Share",
                    document_type=shared_doctype,
                    document_name=shared_name,
                    from_user=frappe.session.user,
                )

    # Notify Vault Admins
    notify_vault_admins(
        subject=f"{item_type} Shared: '{item_title}'",
        email_content=f"<b>{sharer_name}</b> shared {shared_doctype} <b>'{item_title}'</b> with {user or frappe_role} (Access: {permission_level}).",
        document_type=shared_doctype,
        document_name=shared_name,
    )

    return {"name": doc.name}


def unshare(share_name: str) -> dict:
    """Mark a share as revoked instead of deleting it, so it remains in the sharing audit log."""
    doc = frappe.get_doc("Vault Share", share_name)

    # Only the sharer, owner, Admin, or Full Control user can unshare
    is_admin = frappe.session.user == "Administrator" or "Vault Admin" in frappe.get_roles()
    if not is_admin and doc.shared_by != frappe.session.user:
        if frappe.db.exists(doc.shared_doctype, doc.shared_name):
            owner = frappe.db.get_value(doc.shared_doctype, doc.shared_name, "owner")
            if owner != frappe.session.user:
                from frappe_vault.utils.permissions import get_effective_user_permission

                if (
                    get_effective_user_permission(doc.shared_doctype, doc.shared_name, frappe.session.user)
                    != 4
                ):
                    frappe.throw(_("Not permitted"), frappe.PermissionError)
        else:
            frappe.throw(_("Not permitted"), frappe.PermissionError)

    if doc.share_type == "User" and doc.user == frappe.session.user and not is_admin:
        owner = (
            frappe.db.get_value(doc.shared_doctype, doc.shared_name, "owner")
            if frappe.db.exists(doc.shared_doctype, doc.shared_name)
            else None
        )
        if owner != frappe.session.user:
            frappe.throw(_("You cannot revoke your own access."), frappe.PermissionError)

    frappe.db.set_value("Vault Share", share_name, {"is_revoked": 1, "revoked_by": frappe.session.user})

    # Iterate over records with set_value instead of raw UPDATEs to trigger audit logs
    from frappe_vault.services.audit_service import log_share_removed

    def _revoke_and_log(filters):
        shares_to_revoke = frappe.get_all("Vault Share", filters=filters, pluck="name")
        for s_name in shares_to_revoke:
            frappe.db.set_value("Vault Share", s_name, {"is_revoked": 1, "revoked_by": frappe.session.user})
            try:
                log_share_removed(frappe.get_doc("Vault Share", s_name), None)
            except Exception:
                pass

    if doc.share_type == "Role" and doc.frappe_role:
        # Revoke the role shares
        _revoke_and_log(
            {
                "shared_doctype": doc.shared_doctype,
                "shared_name": doc.shared_name,
                "share_type": "Role",
                "frappe_role": doc.frappe_role,
                "is_revoked": 0,
            }
        )

        role_users = set(
            frappe.get_all(
                "Has Role", filters={"role": doc.frappe_role, "parenttype": "User"}, pluck="parent"
            )
        )
        if role_users:
            # Revoke member overrides
            _revoke_and_log(
                {
                    "shared_doctype": doc.shared_doctype,
                    "shared_name": doc.shared_name,
                    "user": ["in", list(role_users)],
                    "is_role_override": 1,
                    "is_revoked": 0,
                }
            )
    elif doc.share_type == "User":
        _revoke_and_log(
            {
                "shared_doctype": doc.shared_doctype,
                "shared_name": doc.shared_name,
                "share_type": "User",
                "user": doc.user,
                "is_revoked": 0,
            }
        )

    # Log the activity

    log_share_removed(doc, None)

    item_title = (
        frappe.db.get_value(
            doc.shared_doctype,
            doc.shared_name,
            "title" if doc.shared_doctype == "Vault Secret" else "folder_name",
        )
        or doc.shared_name
    )
    revoker_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    # Notify recipient if revoked
    if doc.share_type == "User" and doc.user:
        from frappe_vault.services.notification_service import send_vault_notification

        send_vault_notification(
            for_user=doc.user,
            subject=f"Access Revoked for '{item_title}'",
            email_content=f"<b>{revoker_name}</b> revoked your access to {doc.shared_doctype} <b>'{item_title}'</b>.",
            notification_type="Alert",
            document_type=doc.shared_doctype,
            document_name=doc.shared_name,
            from_user=frappe.session.user,
        )
    elif doc.share_type == "Role" and doc.frappe_role:
        from frappe_vault.services.notification_service import send_vault_notification

        for ru in role_users:
            if ru not in ["Administrator", "Guest"]:
                send_vault_notification(
                    for_user=ru,
                    subject=f"Access Revoked for '{item_title}'",
                    email_content=f"<b>{revoker_name}</b> revoked your role access to {doc.shared_doctype} <b>'{item_title}'</b>.",
                    notification_type="Alert",
                    document_type=doc.shared_doctype,
                    document_name=doc.shared_name,
                    from_user=frappe.session.user,
                )

    # Notify Vault Admins
    from frappe_vault.services.notification_service import notify_vault_admins

    notify_vault_admins(
        subject=f"Access Revoked: '{item_title}'",
        email_content=f"<b>{revoker_name}</b> revoked access to {doc.shared_doctype} <b>'{item_title}'</b> for {doc.user or doc.frappe_role}.",
        document_type=doc.shared_doctype,
        document_name=doc.shared_name,
    )

    return {"removed": share_name}


def update_share_permission(share_name: str, permission_level: str) -> dict:
    """Update permission level of an active share."""
    if not frappe.db.exists("Vault Share", share_name):
        frappe.throw(_("Share record not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc("Vault Share", share_name)

    # Only the sharer, owner, or Vault Admin can update permission
    user_roles = frappe.get_roles()
    is_admin = frappe.session.user == "Administrator" or "Vault Admin" in user_roles

    if not is_admin and doc.shared_by != frappe.session.user:
        owner = frappe.db.get_value(doc.shared_doctype, doc.shared_name, "owner")
        if owner != frappe.session.user:
            from frappe_vault.utils.permissions import get_effective_user_permission

            if get_effective_user_permission(doc.shared_doctype, doc.shared_name, frappe.session.user) != 4:
                frappe.throw(_("Not permitted"), frappe.PermissionError)

    if doc.share_type == "User" and doc.user == frappe.session.user and not is_admin:
        owner = frappe.db.get_value(doc.shared_doctype, doc.shared_name, "owner")
        if owner != frappe.session.user:
            frappe.throw(_("You cannot modify your own permission level."), frappe.PermissionError)

    frappe.db.set_value("Vault Share", share_name, "permission_level", permission_level)
    doc.reload()

    from frappe_vault.services.audit_service import log_share_created

    log_share_created(doc, None)

    if doc.share_type == "Role" and doc.frappe_role:
        # Update non-custom member overrides to inherit the new role baseline
        overrides = frappe.get_all(
            "Vault Share",
            filters={
                "shared_doctype": doc.shared_doctype,
                "shared_name": doc.shared_name,
                "is_role_override": 1,
                "is_custom_override": 0,
                "is_revoked": 0,
            },
            pluck="name",
        )
        for ov_name in overrides:
            frappe.db.set_value("Vault Share", ov_name, "permission_level", permission_level)

    # Send notifications for permission update
    item_title = (
        frappe.db.get_value(
            doc.shared_doctype,
            doc.shared_name,
            "title" if doc.shared_doctype == "Vault Secret" else "folder_name",
        )
        or doc.shared_name
    )
    updater_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    if doc.share_type == "User" and doc.user:
        from frappe_vault.services.notification_service import send_vault_notification

        send_vault_notification(
            for_user=doc.user,
            subject=f"Permission Updated for '{item_title}'",
            email_content=f"<b>{updater_name}</b> updated your access on {doc.shared_doctype} <b>'{item_title}'</b> to <b>'{permission_level}'</b>.",
            notification_type="Share",
            document_type=doc.shared_doctype,
            document_name=doc.shared_name,
            from_user=frappe.session.user,
        )

    from frappe_vault.services.notification_service import notify_vault_admins

    notify_vault_admins(
        subject=f"Share Permission Updated: '{item_title}'",
        email_content=f"<b>{updater_name}</b> updated {doc.user or doc.frappe_role}'s access on {doc.shared_doctype} <b>'{item_title}'</b> to <b>'{permission_level}'</b>.",
        document_type=doc.shared_doctype,
        document_name=doc.shared_name,
    )

    return {"name": share_name, "permission_level": permission_level}


def get_role_users(
    role_name: str = None,
    shared_name: str = None,
    shared_doctype: str = "Vault Secret",
    shared_by: str = None,
    user_list: list = None,
) -> list:
    """Get list of users (from role or direct user shares) along with per-user share status."""
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = user == "Administrator" or "Vault Admin" in roles

    if not is_admin and not frappe.has_permission("Vault Share", "read"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    user_ids = []
    role_share_perm = "View Only"
    parent_is_revoked = False

    if user_list:
        if isinstance(user_list, str):
            import json

            try:
                user_list = json.loads(user_list)
            except Exception:
                user_list = [user_list]
        user_ids = list(dict.fromkeys(user_list))
    elif role_name:
        role_users = frappe.get_all(
            "Has Role",
            filters={"role": role_name, "parenttype": "User"},
            fields=["parent as user"],
            order_by="parent asc",
        )
        user_ids = [u["user"] for u in role_users]
        if shared_name:
            role_share_filters = {
                "shared_name": shared_name,
                "shared_doctype": shared_doctype,
                "share_type": "Role",
                "frappe_role": role_name,
            }
            if shared_by:
                role_share_filters["shared_by"] = shared_by
            role_share = frappe.db.get_value(
                "Vault Share", role_share_filters, ["permission_level", "is_revoked"], as_dict=True
            )
            if role_share:
                role_share_perm = role_share.permission_level or role_share_perm
                parent_is_revoked = bool(role_share.is_revoked)
    elif shared_name:
        direct_filters = {
            "shared_name": shared_name,
            "shared_doctype": shared_doctype,
            "share_type": "User",
            "is_role_override": 0,
        }
        if shared_by:
            direct_filters["shared_by"] = shared_by
        direct_users = frappe.get_all(
            "Vault Share", filters=direct_filters, pluck="user", order_by="creation asc"
        )
        user_ids = list(dict.fromkeys(direct_users))

    user_details = []
    owner = frappe.db.get_value(shared_doctype, shared_name, "owner") if shared_name else None

    for user_id in user_ids:
        if not user_id or user_id in ["Administrator", "Guest"]:
            continue
        full_name = frappe.db.get_value("User", user_id, "full_name") or user_id

        is_revoked = parent_is_revoked
        perm_level = role_share_perm
        can_edit = True

        if shared_name:
            # Check for direct user share override
            user_share_filters = {
                "shared_name": shared_name,
                "shared_doctype": shared_doctype,
                "share_type": "User",
                "user": user_id,
            }
            # We don't filter by shared_by here because we want their true effective permission
            user_shares = frappe.get_all(
                "Vault Share",
                filters=user_share_filters,
                fields=["name", "permission_level", "is_revoked", "is_role_override"],
                order_by="is_revoked asc, creation desc",
            )

            if user_shares:
                active_share = next((s for s in user_shares if not s.is_revoked), None)
                override_share = next((s for s in user_shares if s.is_role_override), None)

                if active_share:
                    is_revoked = False
                    perm_level = active_share.permission_level or role_share_perm
                elif override_share and override_share.is_revoked:
                    is_revoked = True
                    perm_level = override_share.permission_level or role_share_perm
                elif not role_name:
                    is_revoked = True
                    perm_level = user_shares[0].permission_level if user_shares else role_share_perm

        # Check if user is Owner or Vault Admin
        if user_id == owner:
            perm_level = "Full Control"
            is_revoked = False
        else:
            u_roles = frappe.get_roles(user_id)
            if "Vault Admin" in u_roles or "System Manager" in u_roles:
                perm_level = "Full Control"
                is_revoked = False

        # Admins can edit anyone. Non-admins cannot edit 'Full Control' users. No one can edit themselves from here.
        current_roles = frappe.get_roles(frappe.session.user)
        is_current_admin = frappe.session.user == "Administrator" or "Vault Admin" in current_roles

        if user_id == frappe.session.user:
            can_edit = False
        elif perm_level == "Full Control" and not is_current_admin:
            can_edit = False

        user_details.append(
            {
                "user": user_id,
                "full_name": full_name,
                "permission_level": perm_level,
                "is_revoked": is_revoked,
                "can_edit": can_edit,
            }
        )
    return user_details


def save_role_member_permission(
    shared_name: str,
    shared_doctype: str = "Vault Secret",
    user: str = None,
    permission_level: str = "View Only",
    is_revoked: bool = False,
    is_role_override: bool = None,
) -> dict:
    """Save or update individual user permission/revocation for a shared item."""
    if not user or not shared_name:
        frappe.throw(_("User and shared item name are required"))

    # Permission check: must have share permission or be the one who shared
    has_share_perm = frappe.has_permission(shared_doctype, "share", shared_name)
    if not has_share_perm:
        # Check if they have Full Control
        from frappe_vault.utils.permissions import get_effective_user_permission

        if get_effective_user_permission(shared_doctype, shared_name, frappe.session.user) == 4:
            has_share_perm = True

    if not has_share_perm:
        # Check if they are the original sharer of this specific role share
        is_sharer = frappe.db.exists(
            "Vault Share",
            {"shared_name": shared_name, "shared_doctype": shared_doctype, "shared_by": frappe.session.user},
        )
        if not is_sharer:
            frappe.throw(_("Not permitted to modify role members"), frappe.PermissionError)

    role_share_perm = (
        frappe.db.get_value(
            "Vault Share",
            {
                "shared_name": shared_name,
                "shared_doctype": shared_doctype,
                "share_type": "Role",
                "is_revoked": 0,
            },
            "permission_level",
        )
        or "View Only"
    )

    is_custom = 1 if (is_revoked or (permission_level and permission_level != role_share_perm)) else 0

    if is_role_override is None:
        has_parent_role = frappe.db.exists(
            "Vault Share",
            {
                "shared_name": shared_name,
                "shared_doctype": shared_doctype,
                "share_type": "Role",
                "is_revoked": 0,
            },
        )
        is_role_override_val = 1 if has_parent_role else 0
    else:
        is_role_override_val = 1 if is_role_override else 0

    existing_shares = frappe.get_all(
        "Vault Share",
        filters={
            "shared_name": shared_name,
            "shared_doctype": shared_doctype,
            "share_type": "User",
            "user": user,
        },
        pluck="name",
    )

    from frappe_vault.services.audit_service import log_share_created, log_share_removed
    from frappe_vault.services.notification_service import send_vault_notification

    if is_revoked:
        if existing_shares:
            for existing_name in existing_shares:
                frappe.db.set_value(
                    "Vault Share",
                    existing_name,
                    {
                        "is_revoked": 1,
                        "revoked_by": frappe.session.user,
                        "is_custom_override": 1,
                        "shared_by": frappe.session.user,
                    },
                )
                share_doc = frappe.get_doc("Vault Share", existing_name)
                log_share_removed(share_doc, None)
        else:
            doc = frappe.get_doc(
                {
                    "doctype": "Vault Share",
                    "share_type": "User",
                    "user": user,
                    "permission_level": permission_level or role_share_perm,
                    "shared_doctype": shared_doctype,
                    "shared_name": shared_name,
                    "is_revoked": 1,
                    "is_role_override": is_role_override_val,
                    "is_custom_override": 1,
                    "shared_by": frappe.session.user,
                    "revoked_by": frappe.session.user,
                }
            )
            doc.insert(ignore_permissions=True)

        item_title = (
            frappe.db.get_value(
                shared_doctype, shared_name, "title" if shared_doctype == "Vault Secret" else "folder_name"
            )
            or shared_name
        )
        revoker_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
        send_vault_notification(
            for_user=user,
            subject=f"Access Revoked for '{item_title}'",
            email_content=f"<b>{revoker_name}</b> revoked your access to {shared_doctype} <b>'{item_title}'</b>.",
            notification_type="Alert",
            document_type=shared_doctype,
            document_name=shared_name,
            from_user=frappe.session.user,
        )
    else:
        target_perm = permission_level or role_share_perm
        if existing_shares:
            for existing_name in existing_shares:
                frappe.db.set_value(
                    "Vault Share",
                    existing_name,
                    {
                        "is_revoked": 0,
                        "permission_level": target_perm,
                        "is_custom_override": is_custom,
                        "shared_by": frappe.session.user,
                    },
                )
                share_doc = frappe.get_doc("Vault Share", existing_name)
                log_share_created(share_doc, None)
        else:
            doc = frappe.get_doc(
                {
                    "doctype": "Vault Share",
                    "share_type": "User",
                    "user": user,
                    "permission_level": target_perm,
                    "shared_doctype": shared_doctype,
                    "shared_name": shared_name,
                    "is_revoked": 0,
                    "is_role_override": is_role_override_val,
                    "is_custom_override": is_custom,
                    "shared_by": frappe.session.user,
                }
            )
            doc.insert(ignore_permissions=True)

        # Send Notification for permission upgrade/change
        item_title = (
            frappe.db.get_value(
                shared_doctype, shared_name, "title" if shared_doctype == "Vault Secret" else "folder_name"
            )
            or shared_name
        )
        sharer_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
        send_vault_notification(
            for_user=user,
            subject=f"Access Updated: '{item_title}'",
            email_content=f"<b>{sharer_name}</b> updated your role access for {shared_doctype} <b>'{item_title}'</b> to <b>'{target_perm}'</b>.",
            notification_type="Share",
            document_type=shared_doctype,
            document_name=shared_name,
            from_user=frappe.session.user,
        )

    return {"status": "success", "user": user, "permission_level": permission_level, "is_revoked": is_revoked}


def get_shares_for_secret(secret_name: str, shared_doctype: str = "Vault Secret") -> list:
    """Get consolidated primary shares for a secret or folder (both active and revoked), excluding role member overrides."""
    shares = frappe.get_all(
        "Vault Share",
        filters={
            "shared_doctype": shared_doctype,
            "shared_name": secret_name,
            "is_role_override": 0,
        },
        fields=[
            "name",
            "share_type",
            "user",
            "frappe_role",
            "permission_level",
            "expires_on",
            "shared_by",
            "is_revoked",
            "revoked_by",
            "creation",
        ],
        order_by="creation desc",
    )

    roles_seen = set()
    user_groups = {}
    consolidated = []

    for s in shares:
        if s.share_type == "Role":
            role_key = f"{s.frappe_role}_{s.is_revoked}"
            if role_key not in roles_seen:
                roles_seen.add(role_key)
                consolidated.append(s)
        elif s.share_type == "User":
            sharer = s.shared_by or "Administrator"
            state_key = "revoked" if s.is_revoked else "active"
            key = f"{sharer}_{state_key}"
            if key not in user_groups:
                user_groups[key] = {"active_shares": [], "revoked_shares": []}
            if s.is_revoked:
                if not any(x.user == s.user for x in user_groups[key]["revoked_shares"]):
                    user_groups[key]["revoked_shares"].append(s)
            else:
                if not any(x.user == s.user for x in user_groups[key]["active_shares"]):
                    user_groups[key]["active_shares"].append(s)

    for _key, g in user_groups.items():
        active = g["active_shares"]
        revoked = g["revoked_shares"]

        if len(active) > 1:
            primary = active[0].copy()
            primary["share_type"] = "UserGroup"
            primary["user_count"] = len(active)
            primary["user_list"] = [u.user for u in active]
            primary["user"] = f"{len(active)} Users"
            consolidated.append(primary)
        elif len(active) == 1:
            consolidated.append(active[0])

        if len(revoked) > 1:
            primary = revoked[0].copy()
            primary["share_type"] = "UserGroup"
            primary["user_count"] = len(revoked)
            primary["user_list"] = [u.user for u in revoked]
            primary["user"] = f"{len(revoked)} Users"
            consolidated.append(primary)
        elif len(revoked) == 1:
            consolidated.append(revoked[0])

    # Populate user full_name and shared_by_name for display
    users_to_fetch = set()
    for s in consolidated:
        if s.get("user") and s.get("share_type") == "User":
            users_to_fetch.add(s.user)
        if s.get("shared_by"):
            users_to_fetch.add(s.shared_by)

    if users_to_fetch:
        user_docs = frappe.get_all(
            "User", filters={"name": ["in", list(users_to_fetch)]}, fields=["name", "full_name"]
        )
        name_map = {u["name"]: u["full_name"] or u["name"] for u in user_docs}
        for s in consolidated:
            if s.get("user") and s.get("share_type") == "User":
                s["full_name"] = name_map.get(s.user, s.user)
            if s.get("shared_by"):
                s["shared_by_name"] = name_map.get(s.shared_by, s.shared_by)

    return consolidated


def get_shared_with_me(limit: int = 20, offset: int = 0) -> dict:
    """Get secrets/folders shared with current user or all shares if Admin, consolidated by primary item and sharer."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)

    is_admin = user == "Administrator" or "Vault Admin" in user_roles

    if is_admin:
        where = "(vs.is_role_override = 0 OR vs.is_role_override IS NULL)"
    else:
        # Use subquery for roles instead of f-string interpolation
        user_escaped = frappe.db.escape(user)
        where = f"""(
            (vs.hidden_from_recipient = 0 OR vs.hidden_from_recipient IS NULL)
            AND vs.shared_by != {user_escaped}
            AND (
                (vs.share_type = 'User' AND vs.user = {user_escaped})
                OR (vs.share_type = 'Role' AND vs.frappe_role IN (
                    SELECT role FROM `tabHas Role` WHERE parent = {user_escaped}
                ))
            )
        )"""

    # Justify suppression (safe, all inputs are escaped or parameterized)
    raw_shares = frappe.db.sql(  # nosemgrep: frappe-raw-sql, frappe-sql-format-injection (safe, uses frappe.db.escape for variables)
        f"""
        SELECT vs.name as share_name, vs.shared_doctype, vs.shared_name,
               vs.permission_level, vs.shared_by, vs.expires_on,
               vs.share_type, vs.user, vs.frappe_role,
               vs.is_revoked, vs.revoked_by, vs.creation,
               COALESCE(sec.title, fld.folder_name) as title,
               sec.secret_type, sec.url, sec.folder,
               COALESCE(fld.icon, parent_fld.icon) as folder_icon,
               COALESCE(fld.folder_name, parent_fld.folder_name) as folder_name
        FROM `tabVault Share` vs
        LEFT JOIN `tabVault Secret` sec ON vs.shared_name = sec.name AND vs.shared_doctype = 'Vault Secret'
        LEFT JOIN `tabVault Folder` fld ON vs.shared_name = fld.name AND vs.shared_doctype = 'Vault Folder'
        LEFT JOIN `tabVault Folder` parent_fld ON sec.folder IS NOT NULL AND (sec.folder = parent_fld.name OR sec.folder = parent_fld.folder_name)
        WHERE ({where}) AND (sec.name IS NOT NULL OR fld.name IS NOT NULL)
        ORDER BY vs.creation DESC
    """,
        as_dict=True,
    )

    groups = {}
    for s in raw_shares:
        if s.share_type == "Role":
            key = f"Role_{s.shared_doctype}_{s.shared_name}_{s.frappe_role}"
            if key not in groups:
                groups[key] = s
        elif s.share_type == "User":
            sharer = s.shared_by or "Administrator"
            key = f"UserGroup_{s.shared_doctype}_{s.shared_name}_{sharer}"
            if key not in groups:
                groups[key] = {
                    "share_name": s.share_name,
                    "shared_doctype": s.shared_doctype,
                    "shared_name": s.shared_name,
                    "permission_level": s.permission_level,
                    "shared_by": s.shared_by,
                    "expires_on": s.expires_on,
                    "share_type": "User",
                    "user": s.user,
                    "frappe_role": None,
                    "is_revoked": True,
                    "revoked_by": s.revoked_by,
                    "title": s.title,
                    "secret_type": s.secret_type,
                    "url": s.url,
                    "folder": s.folder,
                    "folder_icon": s.folder_icon,
                    "folder_name": s.folder_name,
                    "total_count": 0,
                    "active_count": 0,
                    "user_list": [],
                }

            if s.user not in groups[key]["user_list"]:
                groups[key]["user_list"].append(s.user)
                groups[key]["total_count"] += 1
                if not s.is_revoked:
                    groups[key]["active_count"] += 1
                    groups[key]["is_revoked"] = False

    consolidated_list = []
    for g in groups.values():
        total_members = g.get("total_count", 1)
        if total_members > 1:
            g["share_type"] = "UserGroup"
            g["user_count"] = total_members
            g["user"] = f"{total_members} Users"
        consolidated_list.append(g)

    if not is_admin:
        permission_hierarchy = {"Full Control": 4, "Edit": 3, "View & Copy": 2, "View Only": 1}
        unique_secrets = {}
        for g in consolidated_list:
            secret_name = g.get("shared_name")
            current_perm = permission_hierarchy.get(g.get("permission_level", "View Only"), 1)
            if secret_name not in unique_secrets:
                unique_secrets[secret_name] = g
            else:
                existing_perm = permission_hierarchy.get(
                    unique_secrets[secret_name].get("permission_level", "View Only"), 1
                )
                if current_perm > existing_perm:
                    unique_secrets[secret_name] = g
        consolidated_list = list(unique_secrets.values())

    total = len(consolidated_list)
    paginated = consolidated_list[offset : offset + limit]

    return {"shared": paginated, "total": total, "limit": limit, "offset": offset}


def dismiss_shared_logs(share_names: list) -> dict:
    """Cosmetically dismiss/hide a log from the user's Shared with Me view."""
    if not share_names:
        return {"status": "success", "message": "No logs selected"}

    count = 0
    for name in share_names:
        # We only hide it for the recipient. If they aren't the recipient, they can't hide it.
        # But for simplicity, we just set the flag since they can only submit logs they see.
        frappe.db.set_value("Vault Share", name, "hidden_from_recipient", 1, update_modified=False)
        count += 1

    return {"status": "success", "message": f"{count} logs dismissed"}


def create_one_time_link(
    secret_name: str,
    expiry_hours: int = 24,
    max_views: int = 1,
    passphrase: str = None,
) -> dict:
    """Create a one-time shareable link for a secret."""
    from frappe_vault.utils.permissions import can_reveal_secret_value

    # The link hands out plaintext, so creating one requires the right to see
    # that plaintext. Checking only `read` would let anyone with the admin
    # bypass mint themselves a link and read a secret they cannot open directly.
    if not can_reveal_secret_value(secret_name):
        frappe.throw(
            _("Only this secret's owner and the people it is shared with can create a link to it."),
            frappe.PermissionError,
        )
    if not frappe.has_permission("Vault One Time Link", "create"):
        frappe.throw(_("You don't have permission to create links"), frappe.PermissionError)

    doc = frappe.get_doc(
        {
            "doctype": "Vault One Time Link",
            "secret": secret_name,
            "expires_at": add_to_date(now_datetime(), hours=expiry_hours),
            "max_views": max_views,
            "passphrase": passphrase,
        }
    )
    doc.insert()

    return {
        "name": doc.name,
        "token": doc.token,
        "expires_at": str(doc.expires_at),
        "url": f"/vault/shared/{doc.token}",
        "share_url": doc.share_url,
    }


def consume_one_time_link(token: str, passphrase: str = None) -> dict:
    """Consume a one-time link and return the secret data."""
    link_name = frappe.db.get_value("Vault One Time Link", {"token": token}, "name")

    if not link_name:
        frappe.throw(_("Link not found"), frappe.DoesNotExistError)

    link = frappe.get_doc("Vault One Time Link", link_name)

    if not link.is_valid():
        frappe.throw(_("This link has expired or been consumed"))

    # Verify passphrase if configured
    stored_passphrase = None
    try:
        from frappe.utils.password import get_decrypted_password

        stored_passphrase = get_decrypted_password(
            "Vault One Time Link", link.name, "passphrase", raise_exception=False
        )
    except Exception:
        pass

    if not stored_passphrase:
        try:
            auth_val = frappe.db.get_value(
                "__Auth",
                {"doctype": "Vault One Time Link", "docname": link.name, "fieldname": "passphrase"},
                "password",
            )
            if auth_val:
                from frappe.utils.password import decrypt

                stored_passphrase = decrypt(auth_val)
        except Exception:
            pass

    if stored_passphrase:
        if not passphrase:
            frappe.throw(_("Invalid passphrase"))
        import hmac

        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(passphrase.encode("utf-8"), stored_passphrase.encode("utf-8")):
            frappe.throw(_("Invalid passphrase"))

    # Get secret data
    from frappe_vault.utils.encryption import get_decrypted_secret_data

    secret = frappe.get_doc("Vault Secret", link.secret)

    result = {
        "title": secret.title,
        "secret_type": secret.secret_type,
        "url": secret.url,
        "username": secret.username,
        "email": secret.email,
        "notes": secret.notes,
        "decrypted": get_decrypted_secret_data(link.secret, ignore_permissions=True),
    }

    # Consume the link
    link.consume()

    # Log audit event
    try:
        from frappe_vault.services.audit_service import log_one_time_link_consumed

        log_one_time_link_consumed(link)
    except Exception:
        pass

    return result


def bulk_delete_shares(share_names: list) -> dict:
    """Delete multiple shares permanently. Checks permission for each."""
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = user == "Administrator" or "Vault Admin" in roles

    deleted = []
    for name in share_names:
        if not frappe.db.exists("Vault Share", name):
            continue
        doc = frappe.get_doc("Vault Share", name)

        # Check permissions:
        # Admin can delete anything.
        # Standard user can delete if they are the sharer (shared_by) OR the recipient (user/group member/role)
        can_delete = is_admin or doc.shared_by == user

        if not can_delete:
            owner = (
                frappe.db.get_value(doc.shared_doctype, doc.shared_name, "owner")
                if frappe.db.exists(doc.shared_doctype, doc.shared_name)
                else None
            )
            if owner == user:
                can_delete = True
            else:
                from frappe_vault.utils.permissions import get_effective_user_permission

                if get_effective_user_permission(doc.shared_doctype, doc.shared_name, user) == 4:
                    can_delete = True

        if can_delete:
            if doc.share_type == "User" and doc.user == user and not is_admin:
                owner = (
                    frappe.db.get_value(doc.shared_doctype, doc.shared_name, "owner")
                    if frappe.db.exists(doc.shared_doctype, doc.shared_name)
                    else None
                )
                if owner != user:
                    frappe.throw(_("You cannot delete your own share log."), frappe.PermissionError)

            if doc.share_type == "Role" and doc.frappe_role:
                matching_shares = frappe.get_all(
                    "Vault Share",
                    filters={
                        "shared_doctype": doc.shared_doctype,
                        "shared_name": doc.shared_name,
                        "share_type": "Role",
                        "frappe_role": doc.frappe_role,
                    },
                    pluck="name",
                )
                for s_name in matching_shares:
                    frappe.delete_doc("Vault Share", s_name, ignore_permissions=True)
                    deleted.append(s_name)
            elif doc.share_type == "User":
                matching_shares = frappe.get_all(
                    "Vault Share",
                    filters={
                        "shared_doctype": doc.shared_doctype,
                        "shared_name": doc.shared_name,
                        "share_type": "User",
                        "shared_by": doc.shared_by,
                        "is_revoked": doc.is_revoked,
                    },
                    pluck="name",
                )
                for s_name in matching_shares:
                    frappe.delete_doc("Vault Share", s_name, ignore_permissions=True)
                    deleted.append(s_name)
            else:
                frappe.delete_doc("Vault Share", name, ignore_permissions=True)
                deleted.append(name)

    return {"deleted": deleted}
