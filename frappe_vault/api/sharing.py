"""Sharing API — share/unshare endpoints and one-time links."""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit


@frappe.whitelist()
def share(
    shared_name: str,
    shared_doctype: str = "Vault Secret",
    share_type: str = "User",
    user: str | None = None,
    frappe_role: str | None = None,
    role: str | None = None,
    permission_level: str = "View Only",
    expires_on: str | None = None,
    cascade_permissions: int = 1,
) -> dict:
    target_role = frappe_role or role
    from frappe_vault.services.sharing_service import share_secret

    return share_secret(
        shared_name=shared_name,
        shared_doctype=shared_doctype,
        share_type=share_type,
        user=user,
        frappe_role=target_role,
        permission_level=permission_level,
        expires_on=expires_on,
        cascade_permissions=cascade_permissions,
    )


@frappe.whitelist()
def unshare(share_name: str) -> dict:
    from frappe_vault.services.sharing_service import unshare as _unshare

    return _unshare(share_name)


@frappe.whitelist()
def get_shares(secret_name: str, shared_doctype: str = "Vault Secret") -> dict:
    from frappe_vault.services.sharing_service import get_shares_for_secret

    return get_shares_for_secret(secret_name, shared_doctype=shared_doctype)


@frappe.whitelist()
def dismiss_shared_logs(share_names: str | list) -> dict:
    import json

    from frappe_vault.services.sharing_service import dismiss_shared_logs as _dismiss

    if isinstance(share_names, str):
        try:
            share_names = json.loads(share_names)
        except Exception:
            share_names = [share_names]

    return _dismiss(share_names)


@frappe.whitelist()
def shared_with_me(limit: int = 20, offset: int = 0) -> dict:
    from frappe_vault.services.sharing_service import get_shared_with_me

    return get_shared_with_me(limit=int(limit), offset=int(offset))


@frappe.whitelist()
def create_one_time_link(
    secret_name: str, expiry_hours: int = 24, max_views: int = 1, passphrase: str | None = None
) -> dict:
    from frappe_vault.services.sharing_service import create_one_time_link as _create

    return _create(
        secret_name, expiry_hours=int(expiry_hours), max_views=int(max_views), passphrase=passphrase
    )


# Guest access required for one-time links, protected by token/passphrase/rate-limit
# nosemgrep: guest-whitelisted-method (safe, token verified & rate limited)
@frappe.whitelist(allow_guest=True)
@rate_limit(key="consume_link", limit=5, seconds=60)
def consume_link(token: str, passphrase: str | None = None) -> dict:
    from frappe_vault.services.sharing_service import consume_one_time_link

    return consume_one_time_link(token, passphrase=passphrase)


@frappe.whitelist()
def get_share_options() -> dict:
    # Only authenticated users
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"), frappe.PermissionError)

    # 1. Fetch users who have 'Vault User' role (excluding Guest, Administrator, and current user)
    vault_users = frappe.get_all(
        "Has Role",
        filters={
            "role": "Vault User",
            "parenttype": "User",
            "parent": ["not in", ["Guest", "Administrator", frappe.session.user]],
        },
        pluck="parent",
    )

    if vault_users:
        users = frappe.get_all(
            "User",
            filters={"enabled": 1, "name": ["in", vault_users]},
            fields=["name", "full_name"],
            order_by="full_name asc",
        )
        user_options = [{"value": u.name, "label": u.full_name or u.name} for u in users]
    else:
        user_options = []

    # 2. Fetch active system roles (excluding admin/system roles who already have full access)
    excluded_roles = [
        "Administrator",
        "System Manager",
        "Vault Admin",
        "Guest",
        "All",
        "Script Manager",
        "Blogger",
    ]
    roles = frappe.get_all(
        "Role",
        filters={"disabled": 0, "name": ["not in", excluded_roles]},
        fields=["name"],
        order_by="name asc",
    )
    role_options = [{"value": r.name, "label": r.name} for r in roles]

    return {"users": user_options, "roles": role_options}


@frappe.whitelist()
def bulk_delete_shares(share_names: str | list) -> dict:
    from frappe_vault.services.sharing_service import bulk_delete_shares as _bulk_delete

    if isinstance(share_names, str):
        share_names = frappe.parse_json(share_names)
    return _bulk_delete(share_names)


@frappe.whitelist()
def update_share_permission(share_name: str, permission_level: str) -> dict:
    from frappe_vault.services.sharing_service import update_share_permission as _update_perm

    return _update_perm(share_name, permission_level)


@frappe.whitelist()
def get_role_users(
    role_name: str | None = None,
    shared_name: str | None = None,
    shared_doctype: str = "Vault Secret",
    shared_by: str | None = None,
    user_list: str | list | None = None,
) -> dict:
    from frappe_vault.services.sharing_service import get_role_users as _get_role_users

    return _get_role_users(
        role_name=role_name,
        shared_name=shared_name,
        shared_doctype=shared_doctype,
        shared_by=shared_by,
        user_list=user_list,
    )


@frappe.whitelist()
def save_role_member_permission(
    shared_name: str,
    shared_doctype: str = "Vault Secret",
    user: str | None = None,
    permission_level: str = "View Only",
    is_revoked: bool = False,
    is_role_override: bool | str | None = None,
) -> dict:
    from frappe_vault.services.sharing_service import save_role_member_permission as _save_role_member_perm

    if isinstance(is_revoked, str):
        is_revoked = is_revoked.lower() in ("true", "1")

    if isinstance(is_role_override, str):
        is_role_override = is_role_override.lower() in ("true", "1")

    return _save_role_member_perm(
        shared_name=shared_name,
        shared_doctype=shared_doctype,
        user=user,
        permission_level=permission_level,
        is_revoked=bool(is_revoked),
        is_role_override=is_role_override,
    )
