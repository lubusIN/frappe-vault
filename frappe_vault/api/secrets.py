import builtins

import frappe
from frappe import _


@frappe.whitelist()
def list(
    search: str | None = None,
    title: str | None = None,
    username: str | None = None,
    secret_type: str | None = None,
    folder: str | None = None,
    bookmarks_only: bool = False,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "modified desc",
    **kwargs,
) -> dict:
    from frappe_vault.services.secret_service import get_secrets

    return get_secrets(
        search=search,
        title=title,
        username=username,
        secret_type=secret_type,
        folder=folder,
        bookmarks_only=frappe.utils.cint(bookmarks_only),
        limit=int(limit),
        offset=int(offset),
        order_by=order_by,
        **kwargs,
    )


@frappe.whitelist()
def get(name: str, decrypt: bool = False) -> dict:
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)
    from frappe_vault.services.secret_service import get_secret

    return get_secret(name, decrypt=frappe.utils.cint(decrypt))


@frappe.whitelist()
def create(**kwargs) -> dict:
    from frappe_vault.services.secret_service import create_secret

    return create_secret(kwargs)


@frappe.whitelist()
def update(name: str, **kwargs) -> dict:
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)
    from frappe_vault.services.secret_service import update_secret

    return update_secret(name, kwargs)


@frappe.whitelist()
def delete(name: str) -> dict:
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)
    from frappe_vault.services.secret_service import delete_secret

    return delete_secret(name)


@frappe.whitelist()
def bulk_delete(secret_names: str | builtins.list) -> dict:
    from frappe_vault.services.secret_service import bulk_delete as _delete

    if isinstance(secret_names, str):
        secret_names = frappe.parse_json(secret_names)
    if not isinstance(secret_names, builtins.list):
        frappe.throw(_("Invalid secret names list"), frappe.ValidationError)
    return _delete([s for s in secret_names if isinstance(s, str)])


@frappe.whitelist()
def toggle_bookmark(name: str) -> dict:
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)
    from frappe_vault.services.secret_service import toggle_bookmark as _toggle

    return _toggle(name)


@frappe.whitelist()
def bulk_move(secret_names: str | builtins.list, target_folder: str) -> dict:
    from frappe_vault.services.secret_service import bulk_move as _move

    if isinstance(secret_names, str):
        secret_names = frappe.parse_json(secret_names)
    if not isinstance(secret_names, builtins.list) or not isinstance(target_folder, str):
        frappe.throw(_("Invalid input parameters"), frappe.ValidationError)
    return _move([s for s in secret_names if isinstance(s, str)], target_folder)


@frappe.whitelist()
def stats() -> dict:
    from frappe_vault.services.secret_service import get_vault_stats

    return get_vault_stats()


@frappe.whitelist()
def decrypt(name: str) -> dict:
    """Decrypt a secret's sensitive fields."""
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)
    from frappe_vault.services.secret_service import get_secret

    return get_secret(name, decrypt=True)


@frappe.whitelist()
def rotate_now(name: str) -> dict:
    """Rotate a secret's password immediately, off the rotation schedule.

    Generates a new password and emails it to everyone with access, exactly as
    the scheduled job would. If the secret has its own passphrase set, it is
    retrieved and used automatically — no need to supply it here. Requires
    write access to the secret.
    """
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)

    from frappe_vault.utils.permissions import has_secret_permission

    if not has_secret_permission(name, ptype="write"):
        frappe.throw(_("You don't have permission to rotate this secret"), frappe.PermissionError)

    from frappe_vault.background_jobs.password_rotation import rotate_secret

    result = rotate_secret(name)

    return {
        "success": True,
        "name": result["name"],
        "recipients": result["recipients"],
        "message": _("Password rotated and sent to {0} recipient(s).").format(len(result["recipients"])),
    }


@frappe.whitelist()
def clear_zip_passphrase(name: str) -> dict:
    """Remove custom passphrase protection from a secret's rotation archive.

    Restores it to the shared site passphrase and re-enables the unattended
    hourly rotation job for it. Requires write access to the secret.
    """
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)

    from frappe_vault.utils.permissions import has_secret_permission

    if not has_secret_permission(name, ptype="write"):
        frappe.throw(_("You don't have permission to modify this secret"), frappe.PermissionError)

    doc = frappe.get_doc("Vault Secret", name)
    doc.clear_zip_passphrase()
    doc.save(ignore_permissions=True)

    return {"success": True, "name": name}


@frappe.whitelist()
def get_totp(name: str) -> dict:
    """Get live TOTP code and remaining seconds."""
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)
    from frappe_vault.services.secret_service import get_totp_code

    return get_totp_code(name)


@frappe.whitelist()
def upload_file() -> dict:
    """Upload a file attachment for a Vault Secret (works for both standard Vault Users and Admins)."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required"), frappe.PermissionError)

    files = frappe.request.files
    if "file" not in files:
        frappe.throw(_("No file attached"), frappe.ValidationError)

    file = files["file"]
    filename = file.filename
    is_private = frappe.utils.cint(frappe.form_dict.get("is_private", 1))
    doctype = frappe.form_dict.get("doctype")
    docname = frappe.form_dict.get("docname")

    from frappe_vault.services.secret_service import upload_secret_attachment

    return upload_secret_attachment(
        file_obj=file.stream,
        filename=filename,
        is_private=is_private,
        doctype=doctype,
        docname=docname,
    )
