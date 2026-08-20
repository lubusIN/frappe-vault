import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import split_emails, validate_email_address


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=60 * 60)
def accept_invitation(key: str | None = None):
    if not key or not isinstance(key, str):
        frappe.throw(_("Invalid or expired key"))

    result = frappe.db.get_all("Vault Invitation", filters={"key": key}, pluck="name")
    if not result:
        frappe.throw(_("Invalid or expired key"))
    invitation = frappe.get_doc("Vault Invitation", result[0])
    is_new_user = invitation.accept()
    invitation.reload()

    # this is a GET request, which is rolled back unless a commit is requested
    frappe.local.flags.commit = True

    if invitation.status == "Accepted":
        frappe.local.response["type"] = "redirect"
        if is_new_user:
            # a new user has no password yet, send them to the set password page
            # which logs them in and redirects to /vault once the password is set
            user = frappe.get_doc("User", invitation.email)
            reset_url = user._reset_password()
            if ":8000" in reset_url:
                reset_url = reset_url.replace(":8000", "")
            frappe.local.response["location"] = reset_url
        else:
            frappe.local.login_manager.login_as(invitation.email)
            frappe.local.response["location"] = "/vault"


@frappe.whitelist()
def invite_by_email(emails: str, role: str):
    frappe.only_for(["System Manager", "Vault Admin"], True)

    user_roles = frappe.get_roles(frappe.session.user)

    if role == "System Manager" and "System Manager" not in user_roles:
        frappe.throw(_("You are not allowed to invite System Managers"), frappe.PermissionError)

    if role not in ["Vault Admin", "Vault User"]:
        frappe.throw(_("Cannot invite for this role"), frappe.PermissionError)

    if not emails:
        return
    email_string = validate_email_address(emails, throw=False)
    email_list = split_emails(email_string)
    if not email_list:
        return

    existing_members = frappe.db.get_all("User", filters={"email": ["in", email_list]}, pluck="email")
    existing_invites = frappe.db.get_all(
        "Vault Invitation",
        filters={
            "email": ["in", email_list],
            "status": "Pending",
        },
        pluck="email",
    )

    to_invite = list(set(email_list) - set(existing_members) - set(existing_invites))

    for email in to_invite:
        frappe.get_doc(doctype="Vault Invitation", email=email, role=role).insert(ignore_permissions=True)

    return {
        "existing_members": existing_members,
        "existing_invites": existing_invites,
        "to_invite": to_invite,
    }


@frappe.whitelist()
def add_existing_users(users: str | list, role: str = "Vault User"):
    """
    Add existing users to the Vault by assigning them a role (Vault User or Vault Admin).
    """
    frappe.only_for(["System Manager", "Vault Admin"], True)

    users = frappe.parse_json(users)

    for user in users:
        update_user_role(user, role)


@frappe.whitelist()
def update_user_role(user: str, new_role: str):
    """
    Update the role of the user to Vault Admin or Vault User.
    """
    frappe.only_for(["System Manager", "Vault Admin"], True)

    if new_role not in ["Vault Admin", "Vault User"]:
        frappe.throw(_("Cannot assign this role"))

    user_doc = frappe.get_doc("User", user)

    if new_role == "Vault Admin":
        user_doc.append_roles("Vault Admin")
        remove_roles(user_doc, "Vault User")

    if new_role == "Vault User":
        user_doc.append_roles("Vault User")
        remove_roles(user_doc, "Vault Admin")

    user_doc.save(ignore_permissions=True)


@frappe.whitelist()
def remove_vault_roles_from_user(user: str):
    """
    Remove a user means removing Vault User & Vault Admin roles from the user.
    """
    frappe.only_for(["System Manager", "Vault Admin"], True)

    if user == frappe.session.user:
        frappe.throw(_("You cannot remove yourself."), frappe.PermissionError)

    user_doc = frappe.get_doc("User", user)
    roles = [d.role for d in user_doc.roles]

    if user_doc.get("role_profiles") or user_doc.get("role_profile_name"):
        frappe.throw(_("User {0} cannot be removed as it has a Role Profile assigned to it.").format(user))

    if "Vault User" in roles:
        remove_roles(user_doc, "Vault User")
    if "Vault Admin" in roles:
        remove_roles(user_doc, "Vault Admin")

    user_doc.save(ignore_permissions=True)

    frappe.msgprint(_("User {0} has been removed from Vault.").format(user))


def remove_roles(user_doc, *roles):
    existing_roles = {d.role: d for d in user_doc.get("roles")}
    for role in roles:
        if role in existing_roles:
            user_doc.get("roles").remove(existing_roles[role])


@frappe.whitelist()
def update_profile(first_name=None, last_name=None, user_image=None):
    """Update the current user's profile information."""
    if frappe.session.user == "Guest":
        raise frappe.PermissionError

    user = frappe.get_doc("User", frappe.session.user)

    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if user_image is not None:
        user.user_image = user_image

    user.save(ignore_permissions=True)
    return {"first_name": user.first_name, "last_name": user.last_name, "user_image": user.user_image}


@frappe.whitelist()
def change_password(old_password, new_password):
    """Wrapper to update user password."""
    from frappe.core.doctype.user.user import update_password

    return update_password(new_password=new_password, old_password=old_password)
