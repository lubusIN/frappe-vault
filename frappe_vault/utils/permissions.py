"""Permission query conditions for Frappe Vault.

Ensures row-level security: users only see secrets they own or that are shared with them.
"""

import frappe

PERM_HIERARCHY = {"View Only": 1, "View & Copy": 2, "Edit": 3, "Full Control": 4}


def get_effective_user_permission(shared_doctype: str, shared_name: str, user: str = None) -> int:
    """Calculate user's effective numeric permission level (0 to 4) for a secret or folder.

    Priority:
    1. Owner / Admin -> 4 (Full Control)
    2. Direct User Share (is_role_override = 0, is_revoked = 0, not expired)
    3. Role Member Override (is_role_override = 1) -> ONLY IF active role share exists
    4. Highest among active applicable Role Shares
    5. 0 (No access)
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return 4

    roles = frappe.get_roles(user)
    if "Vault Admin" in roles or "System Manager" in roles:
        return 4

    doc_folders = []
    if shared_doctype == "Vault Secret":
        res = frappe.db.get_value("Vault Secret", shared_name, ["owner", "folder"])
        doc_owner, doc_folder = res if res else (None, None)
        if doc_owner == user:
            return 4
        if doc_folder:
            doc_folders.append(doc_folder)
            try:
                from frappe.utils.nestedset import get_ancestors_of

                doc_folders.extend(get_ancestors_of("Vault Folder", doc_folder))
            except Exception:
                pass

            # If the user owns any ancestor folder, they get full control
            folder_owners = frappe.db.get_all(
                "Vault Folder", filters={"name": ("in", doc_folders)}, pluck="owner"
            )
            if user in folder_owners:
                return 4

    elif shared_doctype == "Vault Folder":
        doc_folders.append(shared_name)
        try:
            from frappe.utils.nestedset import get_ancestors_of

            doc_folders.extend(get_ancestors_of("Vault Folder", shared_name))
        except Exception:
            pass

        folder_owners = frappe.db.get_all(
            "Vault Folder", filters={"name": ("in", doc_folders)}, pluck="owner"
        )
        if user in folder_owners:
            return 4

    if not doc_folders:
        doc_folders = [""]  # Dummy to prevent SQL syntax error on empty IN

    # Direct User Shares (non-role-override)
    user_shares = frappe.db.sql(
        """
        SELECT permission_level FROM `tabVault Share`
        WHERE share_type = 'User'
          AND user = %s
          AND is_revoked = 0
          AND (is_role_override = 0 OR is_role_override IS NULL)
          AND (expires_on IS NULL OR expires_on > NOW())
          AND (
              (shared_doctype = %s AND shared_name = %s)
              OR (shared_doctype = 'Vault Folder' AND shared_name IN %s)
          )
        ORDER BY creation DESC
    """,
        (user, shared_doctype, shared_name, tuple(doc_folders)),
        as_dict=True,
    )
    if user_shares:
        highest = max(user_shares, key=lambda s: PERM_HIERARCHY.get(s.permission_level, 0))
        return PERM_HIERARCHY.get(highest.permission_level, 1)

    # Active Role Shares
    active_role_shares = []
    if roles:
        active_role_shares = frappe.db.sql(
            """
            SELECT permission_level FROM `tabVault Share`
            WHERE share_type = 'Role'
              AND frappe_role IN %s
              AND is_revoked = 0
              AND (expires_on IS NULL OR expires_on > NOW())
              AND (
                  (shared_doctype = %s AND shared_name = %s)
                  OR (shared_doctype = 'Vault Folder' AND shared_name IN %s)
              )
        """,
            (tuple(roles), shared_doctype, shared_name, tuple(doc_folders)),
            as_dict=True,
        )

    # Role Member Overrides (applicable only if active role share exists)
    role_overrides = frappe.db.sql(
        """
        SELECT permission_level, is_revoked FROM `tabVault Share`
        WHERE share_type = 'User'
          AND user = %s
          AND is_role_override = 1
          AND (
              (shared_doctype = %s AND shared_name = %s)
              OR (shared_doctype = 'Vault Folder' AND shared_name IN %s)
          )
        ORDER BY creation DESC
    """,
        (user, shared_doctype, shared_name, tuple(doc_folders)),
        as_dict=True,
    )

    if active_role_shares:
        if role_overrides:
            override = role_overrides[0]
            if override.is_revoked:
                return 0
            return PERM_HIERARCHY.get(override.permission_level, 1)

        highest_role = max(active_role_shares, key=lambda s: PERM_HIERARCHY.get(s.permission_level, 0))
        return PERM_HIERARCHY.get(highest_role.permission_level, 1)

    return 0


def get_secret_permission_query(user=None):
    """Return SQL condition to filter Vault Secrets for current user.

    A user can see a secret if:
    1. They own it, OR
    2. It has been shared with them directly, OR
    3. The secret's folder has been shared with them (User/Group/Role)
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return ""

    # Check if user has Vault Admin or System Manager role — they see everything
    roles = frappe.get_roles(user)
    if "Vault Admin" in roles or "System Manager" in roles:
        return ""

    user_escaped = frappe.db.escape(user)

    return f"""(
        `tabVault Secret`.owner = {user_escaped}
        OR `tabVault Secret`.name IN (
            SELECT vs.shared_name
            FROM `tabVault Share` vs
            WHERE vs.shared_doctype = 'Vault Secret'
            AND vs.is_revoked = 0
            AND (
                (vs.share_type = 'User' AND vs.user = {user_escaped})
                OR (vs.share_type = 'Role' AND vs.frappe_role IN (
                    SELECT role FROM `tabHas Role`
                    WHERE parent = {user_escaped}
                ) AND NOT EXISTS (
                    SELECT 1 FROM `tabVault Share` override
                    WHERE override.shared_doctype = 'Vault Secret'
                    AND override.shared_name = vs.shared_name
                    AND override.share_type = 'User'
                    AND override.user = {user_escaped}
                    AND override.is_revoked = 1
                ))
            )
            AND (vs.expires_on IS NULL OR vs.expires_on > NOW())
        )
        OR (
            `tabVault Secret`.folder IS NOT NULL
            AND EXISTS (
                SELECT 1 FROM `tabVault Folder` secret_folder
                JOIN `tabVault Folder` ancestor ON secret_folder.lft >= ancestor.lft AND secret_folder.rgt <= ancestor.rgt
                JOIN `tabVault Share` vs ON vs.shared_doctype = 'Vault Folder' AND vs.shared_name = ancestor.name
                WHERE secret_folder.name = `tabVault Secret`.folder
                AND vs.is_revoked = 0
                AND (
                    (vs.share_type = 'User' AND vs.user = {user_escaped})
                    OR (vs.share_type = 'Role' AND vs.frappe_role IN (
                        SELECT role FROM `tabHas Role`
                        WHERE parent = {user_escaped}
                    ) AND NOT EXISTS (
                        SELECT 1 FROM `tabVault Share` override
                        WHERE override.shared_doctype = 'Vault Folder'
                        AND override.shared_name = vs.shared_name
                        AND override.share_type = 'User'
                        AND override.user = {user_escaped}
                        AND override.is_revoked = 1
                    ))
                )
                AND (vs.expires_on IS NULL OR vs.expires_on > NOW())
            )
        )
        OR (
            `tabVault Secret`.folder IS NOT NULL
            AND EXISTS (
                SELECT 1 FROM `tabVault Folder` secret_folder
                JOIN `tabVault Folder` ancestor ON secret_folder.lft >= ancestor.lft AND secret_folder.rgt <= ancestor.rgt
                WHERE secret_folder.name = `tabVault Secret`.folder
                AND ancestor.owner = {user_escaped}
            )
        )
    )"""


def has_secret_permission(doc, ptype="read", user=None):
    """Check if a user has permission on a specific Vault Secret document."""
    if ptype == "create":
        return True

    # Safely resolve document name
    if isinstance(doc, str):
        doc_name = doc
    elif isinstance(doc, dict):
        doc_name = doc.get("name")
    else:
        doc_name = doc.name

    if not doc_name:
        return False

    level = get_effective_user_permission("Vault Secret", doc_name, user)

    if ptype in ("read",):
        return level >= 1
    elif ptype in ("write",):
        return level >= 3
    elif ptype in ("delete", "share"):
        return level >= 4

    return False


def get_folder_permission_query(user=None):
    """Return SQL condition to filter Vault Folders for current user."""
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)
    if "Vault Admin" in roles or "System Manager" in roles:
        return ""

    user_escaped = frappe.db.escape(user)

    return f"""(
        `tabVault Folder`.owner = {user_escaped}
        OR EXISTS (
            SELECT 1 FROM `tabVault Folder` ancestor
            JOIN `tabVault Share` vs ON vs.shared_doctype = 'Vault Folder' AND vs.shared_name = ancestor.name
            WHERE `tabVault Folder`.lft >= ancestor.lft AND `tabVault Folder`.rgt <= ancestor.rgt
            AND vs.is_revoked = 0
            AND (
                (vs.share_type = 'User' AND vs.user = {user_escaped})
                OR (vs.share_type = 'Role' AND vs.frappe_role IN (
                    SELECT role FROM `tabHas Role`
                    WHERE parent = {user_escaped}
                ) AND NOT EXISTS (
                    SELECT 1 FROM `tabVault Share` override
                    WHERE override.shared_doctype = 'Vault Folder'
                    AND override.shared_name = vs.shared_name
                    AND override.share_type = 'User'
                    AND override.user = {user_escaped}
                    AND override.is_revoked = 1
                ))
            )
            AND (vs.expires_on IS NULL OR vs.expires_on > NOW())
        )
    )"""


def has_folder_permission(doc, ptype="read", user=None):
    """Check if a user has permission on a specific Vault Folder document."""
    if ptype == "create":
        return True

    # Safely resolve folder name
    if isinstance(doc, str):
        doc_name = doc
    elif isinstance(doc, dict):
        doc_name = doc.get("name")
    else:
        doc_name = doc.name

    if not doc_name:
        return False

    level = get_effective_user_permission("Vault Folder", doc_name, user)

    if ptype in ("read",):
        return level >= 1
    elif ptype in ("write",):
        return level >= 3
    elif ptype in ("delete", "share"):
        return level >= 4

    return False


def has_file_permission(doc, ptype="read", user=None):
    """Check if user has permission to read a File attached to a Vault Secret."""
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    roles = frappe.get_roles(user)
    if "Vault Admin" in roles or "System Manager" in roles:
        return True

    if isinstance(doc, str):
        try:
            doc = frappe.get_doc("File", doc)
        except Exception:
            return True

    if doc and doc.attached_to_doctype == "Vault Secret" and doc.attached_to_name:
        return has_secret_permission(doc.attached_to_name, ptype="read", user=user)

    return True
