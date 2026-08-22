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

    doc_folder = None
    if shared_doctype == "Vault Secret":
        res = frappe.db.get_value("Vault Secret", shared_name, ["owner", "folder"])
        doc_owner, doc_folder = res if res else (None, None)
        if doc_owner == user:
            return 4
        if doc_folder:
            folder_owner = frappe.db.get_value("Vault Folder", doc_folder, "owner")
            if folder_owner == user:
                return 4
    elif shared_doctype == "Vault Folder":
        doc_owner = frappe.db.get_value("Vault Folder", shared_name, "owner")
        if doc_owner == user:
            return 4

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
              OR (%s = 'Vault Secret' AND shared_doctype = 'Vault Folder' AND shared_name = %s)
          )
        ORDER BY creation DESC
    """,
        (user, shared_doctype, shared_name, shared_doctype, doc_folder or ""),
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
                  OR (%s = 'Vault Secret' AND shared_doctype = 'Vault Folder' AND shared_name = %s)
              )
        """,
            (tuple(roles), shared_doctype, shared_name, shared_doctype, doc_folder or ""),
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
              OR (%s = 'Vault Secret' AND shared_doctype = 'Vault Folder' AND shared_name = %s)
          )
        ORDER BY creation DESC
    """,
        (user, shared_doctype, shared_name, shared_doctype, doc_folder or ""),
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
            AND `tabVault Secret`.folder IN (
                SELECT vs.shared_name
                FROM `tabVault Share` vs
                WHERE vs.shared_doctype = 'Vault Folder'
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
            AND `tabVault Secret`.folder IN (
                SELECT name FROM `tabVault Folder`
                WHERE owner = {user_escaped}
            )
        )
    )"""


def has_secret_permission(doc, ptype="read", user=None):
    """Check if a user has permission on a specific Vault Secret document."""
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    roles = frappe.get_roles(user)
    if "Vault Admin" in roles or "System Manager" in roles:
        return True

    if ptype == "create":
        return True

    # Safely resolve document name, owner and folder
    if isinstance(doc, str):
        doc_name = doc
        res = frappe.db.get_value("Vault Secret", doc_name, ["owner", "folder"])
        doc_owner, doc_folder = res if res else (None, None)
    elif isinstance(doc, dict):
        doc_name = doc.get("name")
        doc_owner = doc.get("owner")
        doc_folder = doc.get("folder")
        if not doc_owner or not doc_folder:
            res = frappe.db.get_value("Vault Secret", doc_name, ["owner", "folder"])
            if res:
                doc_owner, doc_folder = res
    else:
        doc_name = doc.name
        doc_owner = doc.owner
        doc_folder = doc.folder

    if not doc_name:
        return False

    # Owner always has access
    if doc_owner == user:
        return True

    # Folder owner always has access to secrets inside
    if doc_folder:
        folder_owner = frappe.db.get_value("Vault Folder", doc_folder, "owner")
        if folder_owner == user:
            return True

    # Check active user-specific share first (explicit user level takes priority over everything else)
    user_shares = frappe.db.sql(
        """
        SELECT permission_level FROM `tabVault Share`
        WHERE share_type = 'User'
          AND user = %s
          AND is_revoked = 0
          AND (expires_on IS NULL OR expires_on > NOW())
          AND (
              (shared_doctype = 'Vault Secret' AND shared_name = %s)
              OR (shared_doctype = 'Vault Folder' AND shared_name = %s)
          )
    """,
        (user, doc_name, doc_folder or ""),
        as_dict=True,
    )

    perm_map = {"View Only": 1, "View & Copy": 2, "Edit": 3, "Full Control": 4}

    if user_shares:
        highest_share = max(user_shares, key=lambda s: perm_map.get(s.permission_level, 0))
        level = perm_map.get(highest_share.permission_level, 1)
        if ptype in ("read",):
            return level >= 1
        elif ptype in ("write",):
            return level >= 3
        elif ptype in ("delete", "share"):
            return level >= 4

    # If no active user share exists, check if user was explicitly revoked
    # This prevents them from inheriting access via a role if they were explicitly removed
    if frappe.db.exists(
        "Vault Share",
        {
            "shared_name": doc_name,
            "shared_doctype": "Vault Secret",
            "share_type": "User",
            "user": user,
            "is_revoked": 1,
        },
    ):
        return False

    # Check active role shares if no explicit user share exists
    if roles:
        role_shares = frappe.db.sql(
            """
            SELECT permission_level FROM `tabVault Share`
            WHERE share_type = 'Role'
              AND frappe_role IN %s
              AND is_revoked = 0
              AND (expires_on IS NULL OR expires_on > NOW())
              AND (
                  (shared_doctype = 'Vault Secret' AND shared_name = %s)
                  OR (shared_doctype = 'Vault Folder' AND shared_name = %s)
              )
        """,
            (tuple(roles), doc_name, doc_folder or ""),
            as_dict=True,
        )
        if role_shares:
            highest_share = max(role_shares, key=lambda s: perm_map.get(s.permission_level, 0))
            level = perm_map.get(highest_share.permission_level, 1)
            if ptype in ("read",):
                return level >= 1
            elif ptype in ("write",):
                return level >= 3
            elif ptype in ("delete", "share"):
                return level >= 4

    return False


def get_users_with_secret_access(secret_name, include_admins=False):
    """Return the users who have been granted access to a specific secret.

    This is the inverse of `get_secret_permission_query` — same access model,
    resolved forwards from a secret to its people instead of backwards from a
    user to their secrets. Keep the two in step.

    Included: the secret's owner, its folder's owner, and the holders of any
    active (non-revoked, unexpired) Vault Share on either the secret or its
    folder — for `User` shares directly, and for `Role` shares by expanding the
    role's members.

    A role member's access can be individually revoked without touching the
    role share itself, via a per-user override row (`is_role_override=1,
    is_revoked=1`) scoped to either the secret or its folder — exactly the two
    `NOT EXISTS` checks in `get_secret_permission_query`. Both are excluded
    here too. Ownership is never subject to this: an owner or folder owner is
    always included regardless of any stray/override share row.

    Vault Admins and System Managers are excluded by default. The role bypass
    lets them read every secret, but they were not "given access" to any
    particular one, and including them would mail them every rotation in the
    system. Pass include_admins=True to add them.

    Only enabled users with an email address are returned; Guest never is.

    Args:
        secret_name: Vault Secret document name
        include_admins: also return Vault Admin / System Manager users

    Returns:
        Sorted list of user IDs
    """
    secret = frappe.db.get_value("Vault Secret", secret_name, ["owner", "folder"], as_dict=True)
    if not secret:
        return []

    always_included = {u for u in (secret.owner,) if u}
    if secret.folder:
        folder_owner = frappe.db.get_value("Vault Folder", secret.folder, "owner")
        if folder_owner:
            always_included.add(folder_owner)

    candidates = set(always_included)

    # Active shares on the secret itself or on the folder containing it.
    shares = frappe.db.sql(
        """
        SELECT share_type, user, frappe_role
        FROM `tabVault Share`
        WHERE is_revoked = 0
          AND (expires_on IS NULL OR expires_on > NOW())
          AND (
              (shared_doctype = 'Vault Secret' AND shared_name = %s)
              OR (shared_doctype = 'Vault Folder' AND shared_name = %s)
          )
    """,
        (secret_name, secret.folder or ""),
        as_dict=True,
    )

    roles = {s.frappe_role for s in shares if s.share_type == "Role" and s.frappe_role}
    candidates.update(s.user for s in shares if s.share_type == "User" and s.user)

    if roles:
        candidates.update(
            frappe.get_all(
                "Has Role",
                filters={"role": ["in", list(roles)], "parenttype": "User"},
                pluck="parent",
            )
        )

    if include_admins:
        candidates.update(
            frappe.get_all(
                "Has Role",
                filters={"role": ["in", ["Vault Admin", "System Manager"]], "parenttype": "User"},
                pluck="parent",
            )
        )

    # A revoked User-type share on either the secret or its folder overrides
    # any role-derived (or stray direct) grant — same scope as the two
    # NOT EXISTS checks in get_secret_permission_query.
    revoked = set(
        frappe.get_all(
            "Vault Share",
            filters={
                "share_type": "User",
                "is_revoked": 1,
                "shared_name": ["in", [n for n in (secret_name, secret.folder) if n]],
            },
            pluck="user",
        )
    )
    candidates -= revoked
    candidates |= always_included
    candidates.discard("Guest")
    candidates.discard(None)

    if not candidates:
        return []

    # Only users who can actually receive mail.
    deliverable = frappe.get_all(
        "User",
        filters={"name": ["in", list(candidates)], "enabled": 1},
        fields=["name", "email"],
    )

    return sorted(u.name for u in deliverable if u.email)


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
        OR `tabVault Folder`.name IN (
            SELECT vs.shared_name
            FROM `tabVault Share` vs
            WHERE vs.shared_doctype = 'Vault Folder'
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
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    roles = frappe.get_roles(user)
    if "Vault Admin" in roles or "System Manager" in roles:
        return True

    if ptype == "create":
        return True

    # Safely resolve folder name
    if isinstance(doc, str):
        doc_name = doc
        doc_owner = frappe.db.get_value("Vault Folder", doc_name, "owner")
    elif isinstance(doc, dict):
        doc_name = doc.get("name")
        doc_owner = doc.get("owner") or frappe.db.get_value("Vault Folder", doc_name, "owner")
    else:
        doc_name = doc.name
        doc_owner = doc.owner

    if doc_owner == user:
        return True

    # Check explicit active user-specific share for this folder first
    user_shares = frappe.db.sql(
        """
        SELECT permission_level FROM `tabVault Share`
        WHERE shared_doctype = 'Vault Folder'
          AND shared_name = %s
          AND share_type = 'User'
          AND user = %s
          AND is_revoked = 0
          AND (expires_on IS NULL OR expires_on > NOW())
    """,
        (doc_name, user),
        as_dict=True,
    )

    perm_map = {"View Only": 1, "View & Copy": 2, "Edit": 3, "Full Control": 4}

    if user_shares:
        highest_share = max(user_shares, key=lambda s: perm_map.get(s.permission_level, 0))
        level = perm_map.get(highest_share.permission_level, 1)
        if ptype in ("read",):
            return level >= 1
        elif ptype in ("write",):
            return level >= 3
        elif ptype in ("delete", "share"):
            return level >= 4

    # Check active role shares if no explicit user share exists for this folder
    if roles:
        role_shares = frappe.db.sql(
            """
            SELECT permission_level FROM `tabVault Share`
            WHERE shared_doctype = 'Vault Folder'
              AND shared_name = %s
              AND share_type = 'Role'
              AND frappe_role IN %s
              AND is_revoked = 0
              AND (expires_on IS NULL OR expires_on > NOW())
        """,
            (doc_name, tuple(roles)),
            as_dict=True,
        )
        if role_shares:
            highest_share = max(role_shares, key=lambda s: perm_map.get(s.permission_level, 0))
            level = perm_map.get(highest_share.permission_level, 1)
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
