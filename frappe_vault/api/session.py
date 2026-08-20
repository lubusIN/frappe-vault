import frappe
from frappe import _

VAULT_ALLOWED_ROLES = ["Vault Admin", "Vault User"]


def get_session_role_flags():
    roles = set(frappe.get_roles())

    is_administrator = frappe.session.user == "Administrator"

    if not roles.intersection(set(VAULT_ALLOWED_ROLES)) and not is_administrator:
        frappe.throw(_("You are not permitted to access Vault resources."), frappe.PermissionError)

    return {
        "is_vault_admin": "Vault Admin" in roles or is_administrator,
        "is_vault_user": "Vault User" in roles and "Vault Admin" not in roles and not is_administrator,
    }


USER_FIELDS = [
    "name",
    "email",
    "enabled",
    "user_image",
    "first_name",
    "last_name",
    "full_name",
    "user_type",
    "language",
]


@frappe.whitelist()
def get_users(include_all: bool = False):
    session_roles = get_session_role_flags()

    if isinstance(include_all, str):
        include_all = include_all.lower() in ("1", "true", "yes")

    if not session_roles["is_vault_admin"]:
        include_all = False

    vault_user_names = set(
        frappe.get_all(
            "Has Role",
            filters={"parenttype": "User", "role": ["in", VAULT_ALLOWED_ROLES]},
            pluck="parent",
            distinct=True,
            ignore_permissions=True,
        )
    )
    vault_user_names.add("Administrator")

    user_filters = {"enabled": 1, "name": ["!=", "Guest"]}
    if not include_all:
        user_filters["name"] = ["in", list(vault_user_names)]

    users = frappe.get_all(
        "User", fields=USER_FIELDS, order_by="full_name asc", filters=user_filters, ignore_permissions=True
    )

    if not users:
        return [], []

    system_language = frappe.db.get_single_value("System Settings", "language")
    session_user = frappe.session.user

    if include_all:
        role_filters = {"parenttype": "User"}
    else:
        role_filters = {"parenttype": "User", "parent": ["in", list(vault_user_names)]}

    role_rows = frappe.get_all(
        "Has Role", filters=role_filters, fields=["parent", "role"], ignore_permissions=True
    )
    roles_by_user = {}
    for row in role_rows:
        roles_by_user.setdefault(row.parent, []).append(row.role)

    role_priority = ("Vault Admin", "Vault User", "Guest")
    vault_users = []

    for user in users:
        if session_user == user.name:
            user.session_user = True

        if user.name == "Administrator":
            user.roles = ["Vault Admin", "System Manager", "All"]
            user.role = "Vault Admin"
        else:
            user.roles = [*roles_by_user.get(user.name, []), "All", "Guest"]
            user.role = ""
            for role in role_priority:
                if role in user.roles:
                    user.role = role
                    break

        user.language = user.language or system_language

        if user.role in VAULT_ALLOWED_ROLES:
            vault_users.append(user)

    if not include_all:
        return vault_users, vault_users

    return users, vault_users


@frappe.whitelist()
def get_user_info(users: str | list):
    get_session_role_flags()

    if isinstance(users, str):
        users = frappe.parse_json(users)
    if not users:
        return []

    return frappe.get_all(
        "User",
        filters={"name": ["in", list(users)[:200]]},
        fields=["name", "email", "full_name", "user_image", "user_type"],
        ignore_permissions=True,
    )
