"""Automatic password rotation.

Runs hourly. For every Vault Secret with rotation enabled and a due
`next_rotation_on`, generates a new policy-compliant password, stores it, and
emails it to everyone with access as an AES-256 encrypted ZIP attachment.

The archive passphrase is normally a standing value in bench config under
`vault_rotation_zip_password`, distributed to recipients out of band. A
secret's owner may instead set their own passphrase (Vault Secret.zip_passphrase),
stored encrypted the same way as the secret's own password — this job decrypts
and uses it automatically, so a secret protected this way still rotates on
schedule; the archive just opens with the owner's passphrase instead of the
shared one. Neither passphrase ever appears in the email body.

Scope note: rotation updates the value *stored in the vault only*. It does not
authenticate to the target server, database, or service. Until someone applies
the new value there, the vault and the real system are out of sync — the emails
say so explicitly.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, format_datetime, now_datetime

from frappe_vault.services import audit_service
from frappe_vault.services.notification_service import notify_vault_admins, send_vault_notification
from frappe_vault.utils.archive import create_encrypted_zip, get_rotation_zip_password
from frappe_vault.utils.permissions import get_users_with_secret_access
from frappe_vault.vault.doctype.vault_secret.vault_secret import MIN_ROTATION_PASSWORD_LENGTH

# The reuse policy can reject a generated password. Collisions are vanishingly
# unlikely, but retry rather than fail the secret.
MAX_GENERATION_ATTEMPTS = 5

APPLY_WARNING = (
    "This password has been changed in Frappe Vault ONLY.\n"
    "It has NOT been applied to the target system.\n"
    "You must update the actual server / database / account yourself,\n"
    "otherwise the stored value and the real credential are out of sync."
)


def run_password_rotation():
    """Scheduler entry point — rotate every secret that is due.

    Every due secret is handled uniformly now: whether it uses the shared site
    passphrase or its own, the server can retrieve either automatically.
    """
    due = frappe.get_all(
        "Vault Secret",
        filters={
            "enable_rotation": 1,
            "secret_type": "Password",
            "next_rotation_on": ["<=", now_datetime()],
        },
        fields=["name", "title"],
    )

    if not due:
        return

    try:
        _check_delivery_prereqs()
    except frappe.ValidationError as e:
        _abort(str(e) + "\nNo passwords were rotated.")
        return

    rotated, failed = 0, 0
    for secret in due:
        try:
            rotate_secret(secret.name)
            rotated += 1
            frappe.db.commit()  # nosemgrep — keep each rotation durable independently
        except Exception:
            failed += 1
            frappe.db.rollback()
            frappe.log_error(title=f"Vault Password Rotation Failed ({secret.name})")

    _notify_admins_summary(rotated, failed)


def rotate_secret(secret_name: str) -> dict:
    """Rotate one secret: regenerate, store, audit, and deliver.

    Raises on failure so the caller can count and report it.
    """
    doc = frappe.get_doc("Vault Secret", secret_name)

    if doc.secret_type != "Password":
        frappe.throw(_("Only secrets of type 'Password' can be rotated."))

    zip_password = _resolve_zip_password(doc)
    _check_delivery_prereqs()

    new_password = _generate_and_store(doc)

    audit_service._create_log(
        "Rotated",
        secret=doc.name,
        folder=doc.folder,
        details={
            "length": len(new_password),
            "interval": cint(doc.rotation_interval),
            "unit": doc.rotation_unit,
            "next_rotation_on": str(doc.next_rotation_on),
            "custom_passphrase": bool(doc.has_zip_passphrase),
        },
    )

    recipients = get_users_with_secret_access(doc.name)
    if recipients:
        # The rotation is already committed to the vault at this point. If delivery
        # fails we surface it loudly, but we do not roll the new password back —
        # the vault remains the source of truth and anyone with access can read it
        # through the UI.
        _deliver(doc, new_password, recipients, zip_password)

    return {"name": doc.name, "recipients": recipients, "rotated_on": str(doc.last_rotated_on)}


def _resolve_zip_password(doc) -> str:
    """Determine which archive passphrase protects this secret's rotation.

    A secret with its own passphrase uses that (decrypted server-side, the
    same as any other stored password); otherwise the shared site passphrase.
    """
    if doc.has_zip_passphrase:
        zip_password = doc.get_password("zip_passphrase", raise_exception=False)
        if not zip_password:
            frappe.throw(_("This secret's custom rotation passphrase could not be retrieved."))
        return zip_password

    zip_password = get_rotation_zip_password()
    if not zip_password:
        frappe.throw(_("The Vault rotation archive passphrase is not configured."))
    return zip_password


def _check_delivery_prereqs():
    """pyzipper + a default outgoing Email Account — required for any delivery.

    Checked before touching any password: rotating a batch of credentials and
    only then discovering there's no way to hand them out would leave every
    recipient locked out of their own secrets.
    """
    try:
        import pyzipper  # noqa: F401
    except ImportError:
        frappe.throw(_("The 'pyzipper' package is not installed; run: bench pip install pyzipper"))

    if not frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1}):
        frappe.throw(_("No default outgoing Email Account is configured; set one up at /app/email-account."))


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _abort(reason: str):
    """Log and escalate a pre-flight failure without touching any secret."""
    frappe.log_error(message=reason, title="Vault Password Rotation Aborted")
    try:
        notify_vault_admins(
            subject=_("Password rotation aborted"),
            email_content=reason,
            document_type="Vault Secret",
        )
    except Exception:
        frappe.log_error(title="Vault Rotation Abort Notification Failed")


def _generate_and_store(doc) -> str:
    """Generate a compliant password, save it on the doc, and return it."""
    settings = frappe.get_cached_doc("Vault Settings")
    length = _rotation_password_length(settings)

    last_error = None
    for _attempt in range(MAX_GENERATION_ATTEMPTS):
        new_password = _generate_password(settings, length)

        doc.password = new_password
        doc.last_rotated_on = now_datetime()
        doc.flags.vault_auto_rotation = True

        try:
            doc.save(ignore_permissions=True)
            return new_password
        except frappe.ValidationError as e:
            # Almost certainly the reuse policy — regenerate rather than give up.
            last_error = e
            doc.reload()
            doc.flags.vault_auto_rotation = True

    raise last_error or frappe.ValidationError(
        _("Could not generate an acceptable password for {0}").format(doc.name)
    )


def _rotation_password_length(settings) -> int:
    """Longest of the policy minimum, the configured default, and the hard floor.

    The hard floor wins unconditionally, so a misconfigured Vault Settings can
    never produce a rotated password below MIN_ROTATION_PASSWORD_LENGTH.
    """
    return max(
        MIN_ROTATION_PASSWORD_LENGTH,
        cint(settings.min_password_length),
        cint(settings.default_password_length),
    )


def _generate_password(settings, length: int) -> str:
    """Generate a password honouring the Vault Settings charset policy."""
    from frappe_vault.services.generator_service import generate_password

    return generate_password(
        length=length,
        use_uppercase=bool(settings.require_uppercase),
        use_lowercase=bool(settings.require_lowercase),
        use_digits=bool(settings.require_digits),
        use_special=bool(settings.require_special),
    )


def _deliver(doc, new_password: str, recipients: list, zip_password: str):
    """Queue the encrypted archive to everyone with access, and notify in-app."""
    stamp = now_datetime().strftime("%Y%m%d-%H%M")
    filename = f"vault-rotation-{doc.name}-{stamp}.zip"
    custom = bool(doc.has_zip_passphrase)

    archive = create_encrypted_zip(
        {
            f"{doc.name}-{_slugify(doc.title)}.txt": _secret_payload(doc, new_password),
            "README.txt": _readme(custom),
        },
        zip_password,
    )

    frappe.sendmail(
        recipients=recipients,
        subject=_("[Vault] Password rotated: {0}").format(doc.title),
        message=_email_body(doc, custom),
        attachments=[{"fname": filename, "fcontent": archive}],
        reference_doctype="Vault Secret",
        reference_name=doc.name,
    )

    for user in recipients:
        send_vault_notification(
            for_user=user,
            subject=_("Password rotated: {0}").format(doc.title),
            email_content=_(
                "A new password was generated for '{0}' and emailed to you as an encrypted archive."
            ).format(doc.title),
            notification_type="Alert",
            document_type="Vault Secret",
            document_name=doc.name,
            from_user="Administrator",
        )


def _secret_payload(doc, new_password: str) -> str:
    """The archive member carrying the new credential."""
    lines = [
        f"Vault Secret : {doc.title}",
        f"Record       : {doc.name}",
        f"Type         : {doc.secret_type}",
    ]
    if doc.url:
        lines.append(f"URL          : {doc.url}")
    if doc.username:
        lines.append(f"Username     : {doc.username}")

    lines += [
        "",
        f"New Password : {new_password}",
        "",
        f"Rotated On   : {format_datetime(doc.last_rotated_on)}",
        f"Next Rotation: {format_datetime(doc.next_rotation_on)}",
        "",
        "-" * 60,
        APPLY_WARNING,
        "-" * 60,
    ]
    return "\n".join(lines) + "\n"


def _readme(custom_passphrase: bool) -> str:
    passphrase_note = (
        "The passphrase is the one set specifically for this secret, shared with you\n"
        "by its owner separately — NOT the standing site-wide Vault passphrase."
        if custom_passphrase
        else "The passphrase is the standing Vault rotation passphrase issued to you\n" "separately."
    )
    return (
        "Frappe Vault — Automatic Password Rotation\n"
        "==========================================\n\n"
        "A password you have access to was rotated on schedule. The new value is\n"
        "in the accompanying .txt file.\n\n"
        f"{APPLY_WARNING}\n\n"
        "This archive is AES-256 encrypted. Open it with 7-Zip, WinRAR, Keka, or\n"
        "another tool that supports WinZip AES — the built-in extractor on some\n"
        "systems only handles legacy ZipCrypto and will report a bad passphrase.\n\n"
        f"{passphrase_note} It is never sent in the same email as this archive.\n\n"
        "Delete this archive once you have applied or recorded the new password.\n"
    )


def _email_body(doc, custom_passphrase: bool) -> str:
    """Email body. Deliberately contains neither the password nor the passphrase."""
    rows = [
        (_("Secret"), frappe.utils.escape_html(doc.title or "")),
        (_("Record"), frappe.utils.escape_html(doc.name)),
        (_("Rotated On"), format_datetime(doc.last_rotated_on)),
        (_("Next Rotation"), format_datetime(doc.next_rotation_on)),
    ]
    if doc.url:
        rows.insert(2, (_("URL"), frappe.utils.escape_html(doc.url)))

    table = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#666;'>{label}</td>"
        f"<td style='padding:4px 0;'><strong>{value}</strong></td></tr>"
        for label, value in rows
    )

    passphrase_hint = (
        _("Open it with the passphrase set specifically for this secret — not the shared site passphrase.")
        if custom_passphrase
        else _("Open it with the standing Vault rotation passphrase issued to you separately.")
    )

    return f"""
        <p>{_("A password you have access to has been rotated automatically.")}</p>
        <table style="border-collapse:collapse;margin:16px 0;">{table}</table>
        <p>{_("The new password is in the attached encrypted archive.")} {passphrase_hint} {_("For your safety it is never included in this email.")}</p>
        <p style="padding:12px;background:#fff8e1;border-left:3px solid #f5a623;">
            <strong>{_("This changed the value stored in Vault only.")}</strong><br>
            {_("The password on the actual server, database, or account has NOT been changed. Apply the new value there yourself, or the two will remain out of sync.")}
        </p>
        <p style="color:#888;font-size:12px;">{_("Sent by Frappe Vault automatic rotation.")}</p>
    """


def _notify_admins_summary(rotated: int, failed: int):
    """Tell Vault Admins what the run did, but only if it did something."""
    if not rotated and not failed:
        return

    try:
        notify_vault_admins(
            subject=_("Password rotation run complete"),
            email_content=_("Rotated {0} secret(s); {1} failed.").format(rotated, failed),
            document_type="Vault Secret",
        )
    except Exception:
        frappe.log_error(title="Vault Rotation Summary Notification Failed")


def _slugify(text: str) -> str:
    """Filesystem-safe archive member name."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "secret")).strip("-").lower()
    return (slug or "secret")[:60]
