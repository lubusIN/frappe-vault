import builtins

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit


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

    Generates a new password exactly as the scheduled job would — including
    applying it to the live server when a Database secret is configured to do
    that. Everyone with access is notified in-app, and emailed an encrypted
    archive as well if Vault Settings has 'Email Rotated Passwords' enabled.
    Requires write access to the secret.
    """
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)

    from frappe_vault.utils.permissions import has_secret_permission

    if not has_secret_permission(name, ptype="write"):
        frappe.throw(_("You don't have permission to rotate this secret"), frappe.PermissionError)

    from frappe_vault.background_jobs.password_rotation import rotate_secret

    result = rotate_secret(name)
    count = len(result["recipients"])

    if result.get("applied_to_target"):
        message = _("Password rotated and applied to {0}.").format(result["applied_to_target"])
    else:
        message = _("Password rotated.")

    if result.get("emailed"):
        message += " " + _("Sent to {0} recipient(s) as an encrypted archive.").format(count)
    else:
        message += " " + _("{0} person(s) notified; the new value is here in Vault.").format(count)

    return {
        "success": True,
        "name": result["name"],
        "recipients": result["recipients"],
        "applied_to_target": result.get("applied_to_target"),
        "emailed": result.get("emailed"),
        "message": message,
    }


@frappe.whitelist()
@rate_limit(limit=30, seconds=60 * 60)
def test_db_connection_params(
    database_type: str,
    db_host: str,
    username: str,
    admin_username: str,
    admin_password: str,
    db_port: int | str | None = None,
    db_name: str | None = None,
    db_auth_source: str | None = None,
    db_use_ssl: bool = False,
) -> dict:
    """Test a database connection from form values, before any secret exists.

    Backs the Test Connection step in the create dialog: the admin credential is
    proved to work, and the account it will later reset is checked for existence,
    so a typo surfaces now instead of at 2am on the first unattended rotation.

    Nothing is written to the server and nothing is stored here — the credentials
    live only for the duration of this call.

    Rate limited, and restricted to users who could create the secret anyway,
    because it makes this server open an outbound connection to a host the
    caller chooses.
    """
    if not frappe.has_permission("Vault Secret", "create"):
        frappe.throw(_("You don't have permission to create secrets"), frappe.PermissionError)

    if not admin_username or not admin_password:
        frappe.throw(
            _("An admin username and password are required to test the connection."),
            frappe.ValidationError,
        )

    from frappe_vault.services import db_rotation_service

    target = db_rotation_service.make_target(
        database_type=database_type,
        host=db_host,
        port=db_port,
        database=db_name,
        username=username,
        use_ssl=frappe.utils.cint(db_use_ssl),
        auth_source=db_auth_source,
        admin_username=admin_username,
        admin_password=admin_password,
    )

    db_rotation_service.verify_admin_credentials(target)
    exists = db_rotation_service.account_exists(target)
    description = db_rotation_service.describe(target)

    if exists is False:
        frappe.throw(
            _("Connected to {0}, but no account named '{1}' exists there.").format(
                description, target.username
            ),
            frappe.ValidationError,
        )

    if exists is None:
        message = _(
            "Connected as {0}. Could not confirm '{1}' exists — the admin account cannot read the "
            "server's user list, which does not stop rotation from working."
        ).format(admin_username, target.username)
    else:
        message = _("Connected as {0}. The account '{1}' exists and can be rotated.").format(
            admin_username, target.username
        )

    return {
        "success": True,
        "target": description,
        "account_exists": exists,
        "message": message,
    }


@frappe.whitelist()
def test_db_connection(name: str) -> dict:
    """Check that a Database secret's stored credentials actually reach its server.

    Runs the exact connection the rotation job would make, so a secret can be
    proved reachable *before* it is trusted to rotate unattended. Nothing is
    changed on the server. Requires write access to the secret.
    """
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)

    from frappe_vault.utils.permissions import has_secret_permission

    if not has_secret_permission(name, ptype="write"):
        frappe.throw(_("You don't have permission to test this secret"), frappe.PermissionError)

    from frappe_vault.services import db_rotation_service

    doc = frappe.get_doc("Vault Secret", name)
    if doc.secret_type != "Database":
        frappe.throw(_("Only Database secrets can be tested against a server."), frappe.ValidationError)

    current_password = doc.get_password("db_password", raise_exception=False)
    target = db_rotation_service.build_target(doc, current_password)

    # Prove the stored credential works. When a rotation admin is configured,
    # prove that separately too — it is the account that would run the change.
    db_rotation_service.verify_credentials(target, current_password)

    exists = None
    if target.via_admin:
        db_rotation_service.verify_admin_credentials(target)
        exists = db_rotation_service.account_exists(target)

    description = db_rotation_service.describe(target)
    if exists is False:
        frappe.throw(
            _("Connected to {0}, but no account named '{1}' exists there.").format(
                description, target.username
            ),
            frappe.ValidationError,
        )

    return {
        "success": True,
        "target": description,
        "account_exists": exists,
        "message": _("Connected to {0}.").format(description),
    }


@frappe.whitelist()
@rate_limit(limit=30, seconds=60 * 60)
def test_linux_connection_params(
    username: str,
    hosts: str | builtins.list,
    ansible_user: str,
    ansible_ssh_private_key: str,
    ansible_become_password: str | None = None,
    ansible_use_become: bool = True,
    strict_host_key_checking: bool = True,
    ssh_port: int | str = 22,
) -> dict:
    """Reach a set of Linux hosts from form values, before any secret exists.

    Backs the Test Connection step in the create dialog. Proves each host answers
    and that privilege escalation works, so an unreachable machine or a sudo
    problem surfaces now rather than part-way through a rotation.

    Nothing is changed on any host and nothing is stored here — the credentials
    live only for the duration of this call. Rate limited and restricted to users
    who could create the secret anyway, because it makes this server open
    outbound SSH connections to hosts the caller chooses.
    """
    if not frappe.has_permission("Vault Secret", "create"):
        frappe.throw(_("You don't have permission to create secrets"), frappe.PermissionError)

    if isinstance(hosts, str):
        try:
            hosts = frappe.parse_json(hosts)
        except Exception:
            frappe.throw(_("Invalid host list"), frappe.ValidationError)
    if not isinstance(hosts, builtins.list):
        frappe.throw(_("Invalid host list"), frappe.ValidationError)

    from frappe_vault.services import linux_rotation_service as linux

    target = linux.make_linux_target(
        username=username,
        hosts=hosts,
        ansible_user=ansible_user,
        ssh_private_key=ansible_ssh_private_key,
        become_password=ansible_become_password,
        use_become=frappe.utils.cint(ansible_use_become),
        strict_host_key_checking=frappe.utils.cint(strict_host_key_checking),
        ssh_port=ssh_port,
    )

    result = linux.ping(target)

    return {
        "success": result.all_ok,
        "target": target.describe(),
        "hosts": [{"hostname": o.hostname, "ok": o.ok, "error": o.error} for o in result.outcomes],
        "message": _("Reached all {0} host(s), and sudo works.").format(len(result.outcomes))
        if result.all_ok
        else result.summary(),
    }


@frappe.whitelist()
def test_linux_connection(name: str) -> dict:
    """Reach every host of a Linux Server secret without changing anything.

    Runs the same inventory and credentials a rotation would, so an unreachable
    machine or a sudo problem surfaces now rather than mid-rotation. Reports per
    host, because "it failed" is not actionable across twenty of them.
    """
    if not isinstance(name, str):
        frappe.throw(_("Invalid secret identifier"), frappe.ValidationError)

    from frappe_vault.utils.permissions import has_secret_permission

    if not has_secret_permission(name, ptype="write"):
        frappe.throw(_("You don't have permission to test this secret"), frappe.PermissionError)

    from frappe_vault.services import linux_rotation_service as linux

    doc = frappe.get_doc("Vault Secret", name)
    if doc.secret_type != "Linux Server":
        frappe.throw(_("Only Linux Server secrets can be tested against hosts."), frappe.ValidationError)

    target = linux.build_linux_target(doc)
    result = linux.ping(target)

    return {
        "success": result.all_ok,
        "target": target.describe(),
        "hosts": [{"hostname": o.hostname, "ok": o.ok, "error": o.error} for o in result.outcomes],
        "message": _("Reached all {0} host(s).").format(len(result.outcomes))
        if result.all_ok
        else result.summary(),
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
