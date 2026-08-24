"""Automatic password rotation.

Runs hourly. For every Vault Secret with rotation enabled and a due
`next_rotation_on`, generates a new policy-compliant password and stores it.
Everyone with access is notified in-app; the value itself is read from the
record by the people entitled to it.

Emailing the new password as an AES-256 encrypted ZIP is optional and off by
default — Vault Settings, "Email Rotated Passwords". Rotation never depends on
it: if mail is disabled, misconfigured, or simply fails, the password is still
rotated and applied. Getting the credential changed is the job; telling people
about it is a separate, best-effort step.

Two secret types rotate: `Password` (rotating the `password` field) and
`Database` (rotating `db_password`). A Database secret may additionally set
`apply_rotation_to_target`, in which case the new password is pushed to the
live PostgreSQL / MySQL / MariaDB / MongoDB server before it is stored here —
see services/db_rotation_service.py.

When emailing is enabled, the archive passphrase is normally a standing value in bench config under
`vault_rotation_zip_password`, distributed to recipients out of band. A
secret's owner may instead set their own passphrase (Vault Secret.zip_passphrase),
stored encrypted the same way as the secret's own password — this job decrypts
and uses it automatically, so a secret protected this way still rotates on
schedule; the archive just opens with the owner's passphrase instead of the
shared one. Neither passphrase ever appears in the email body.

Scope note: unless a Database secret opts into applying the change to its live
server, rotation updates the value *stored in the vault only* — it does not
authenticate to the target server or service. Until someone applies the new
value there, the vault and the real system are out of sync, and the emails say
so explicitly. Secrets that do apply to their server get the opposite notice.
"""

import re
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import cint, format_datetime, now_datetime

from frappe_vault.services import audit_service
from frappe_vault.services.notification_service import notify_vault_admins, send_vault_notification
from frappe_vault.utils.archive import create_encrypted_zip, get_rotation_zip_password
from frappe_vault.utils.permissions import get_users_with_secret_access
from frappe_vault.vault.doctype.vault_secret.vault_secret import (
    MIN_ROTATION_PASSWORD_LENGTH,
    ROTATABLE_FIELD_BY_TYPE,
    SYNCED_TYPES,
)

# The reuse policy can reject a generated password. Collisions are vanishingly
# unlikely, but retry rather than fail the secret.
MAX_GENERATION_ATTEMPTS = 5

APPLY_WARNING = (
    "This password has been changed in Frappe Vault ONLY.\n"
    "It has NOT been applied to the target system.\n"
    "You must update the actual server / database / account yourself,\n"
    "otherwise the stored value and the real credential are out of sync."
)

APPLIED_NOTICE = (
    "This password has ALREADY been changed on the live database:\n"
    "    {target}\n"
    "The vault and the server are in sync — no manual step is needed.\n"
    "Update any application, connection string, or config file that still\n"
    "carries the old password, or those connections will start failing."
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
            "secret_type": ["in", sorted(ROTATABLE_FIELD_BY_TYPE)],
            "next_rotation_on": ["<=", now_datetime()],
        },
        fields=["name", "title"],
    )

    if not due:
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
    """Rotate one secret: regenerate, apply, store, audit, and deliver.

    Raises on failure so the caller can count and report it.

    The order is deliberate. A secret that applies to a live database contacts
    the server *before* the new value is written here, so a server that refuses
    the change leaves the vault holding the credential that still works. Only
    once the target has accepted and re-authenticated does the vault record the
    new value.
    """
    doc = frappe.get_doc("Vault Secret", secret_name)

    field = doc.rotating_field
    if not field:
        frappe.throw(
            _("Only secrets of type {0} can be rotated.").format(
                ", ".join(f"'{t}'" for t in sorted(ROTATABLE_FIELD_BY_TYPE))
            )
        )

    # Delivery is resolved up front but never gates the rotation: a missing
    # passphrase or mail account is a reason to skip the email, not a reason to
    # leave a credential unrotated. When email is off this is None throughout.
    zip_password = _resolve_delivery(doc)

    new_password = _generate_candidate(doc)

    applied = None
    if _applies_to_target(doc):
        if doc.secret_type == "Linux Server":
            applied = _apply_to_linux(doc, new_password)
        else:
            applied = _apply_to_target(doc, new_password, zip_password)

    try:
        _store(doc, field, new_password)
    except Exception:
        # The server already has the new password but the vault does not. Put the
        # server back so the two agree on the old value, which is still stored here.
        if applied:
            _undo_target_apply(doc, applied, new_password, zip_password)
        raise

    audit_service._create_log(
        "Rotated",
        secret=doc.name,
        folder=doc.folder,
        details={
            "length": len(new_password),
            "field": field,
            "interval": cint(doc.rotation_interval),
            "unit": doc.rotation_unit,
            "next_rotation_on": str(doc.next_rotation_on),
            "custom_passphrase": bool(doc.has_zip_passphrase),
            "applied_to_target": applied.description if applied else None,
        },
    )

    recipients = get_users_with_secret_access(doc.name)
    if recipients:
        # The rotation stands at this point. Notifying people is best-effort by
        # design: a failure here is surfaced loudly but never undoes the new
        # password, because the vault is the source of truth and everyone
        # entitled to the secret can read it in the app.
        try:
            _deliver(doc, new_password, recipients, zip_password, applied)
        except Exception:
            frappe.log_error(title=f"Vault Rotation Delivery Failed ({doc.name})")

    return {
        "name": doc.name,
        "recipients": recipients,
        "rotated_on": str(doc.last_rotated_on),
        "applied_to_target": applied.description if applied else None,
        "emailed": bool(zip_password),
    }


def _emailing_enabled() -> bool:
    """Whether rotated passwords should be emailed at all."""
    return bool(frappe.db.get_single_value("Vault Settings", "send_rotation_emails"))


def _resolve_delivery(doc) -> str | None:
    """The archive passphrase to deliver this rotation with, or None to skip email.

    Returns None both when emailing is switched off and when it is on but
    unusable — a missing passphrase or mail account downgrades this rotation to
    in-app only rather than aborting it. Rotation is the job; the email is how
    the result used to travel, and it is no longer allowed to hold it up.
    """
    if not _emailing_enabled():
        return None

    try:
        _check_delivery_prereqs()
        return _resolve_zip_password(doc)
    except Exception as e:
        frappe.log_error(
            message=f"{doc.name}: {e}\nRotating anyway; the new value is readable in Vault.",
            title="Vault Rotation Email Skipped",
        )
        return None


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


def _generate_candidate(doc) -> str:
    """Generate a policy-compliant password the reuse policy will accept.

    Screened here rather than on the way back in. A candidate rejected at save
    time, after a live database had already accepted it, would leave the vault
    and the server disagreeing with no clean way back.
    """
    settings = frappe.get_cached_doc("Vault Settings")
    length = _rotation_password_length(settings)

    for _attempt in range(MAX_GENERATION_ATTEMPTS):
        candidate = _generate_password(settings, length)
        if not doc.is_password_reused(candidate):
            return candidate

    raise frappe.ValidationError(_("Could not generate an acceptable password for {0}").format(doc.name))


def _store(doc, field: str, new_password: str):
    """Write the rotated value onto the secret and save it."""
    doc.set(field, new_password)
    doc.last_rotated_on = now_datetime()
    doc.flags.vault_auto_rotation = True
    doc.save(ignore_permissions=True)


# ----------------------------------------------------------------------
# Applying the new password to a live database
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _Applied:
    """A password change that a live database has accepted and confirmed."""

    target: object
    previous_password: str
    description: str


def _applies_to_target(doc) -> bool:
    """True when this rotation has to reach the systems the credential lives on."""
    return bool(doc.secret_type in SYNCED_TYPES and doc.apply_rotation_to_target)


def _apply_to_linux(doc, new_password: str) -> "_Applied":
    """Change the account's password on every host, or leave them all alone.

    A vault entry holds one password, so a run that succeeded on eight of ten
    machines is not a partial success — it is two machines nobody can log into
    and a stored value that is wrong for them. Any failure puts the hosts that
    did accept the change back before this returns.
    """
    from frappe_vault.services import linux_rotation_service as linux

    target = linux.build_linux_target(doc)
    description = target.describe()

    # Reach every host first, while the stored password is still true everywhere.
    reachable = linux.ping(target)
    if not reachable.all_ok:
        _record_host_results(doc, reachable)
        _record_target_failure(doc.name, description, reachable.summary())
        frappe.throw(
            _("Not every host could be reached, so nothing was changed — {0}").format(reachable.summary()),
            linux.LinuxApplyError,
        )

    previous_password = doc.get_password(doc.rotating_field, raise_exception=False)
    applied = linux.apply_password(target, new_password)
    _record_host_results(doc, applied)

    if not applied.all_ok:
        _revert_linux_hosts(doc, target, previous_password, applied)
        _record_target_failure(doc.name, description, applied.summary())
        frappe.throw(
            _("The password could not be set on every host — {0}").format(applied.summary()),
            linux.LinuxApplyError,
        )

    doc.last_target_apply_status = "Success"
    doc.last_target_apply_on = now_datetime()
    doc.last_target_apply_error = None

    return _Applied(target=target, previous_password=previous_password, description=description)


def _revert_linux_hosts(doc, target, previous_password: str, applied):
    """Put back the hosts that accepted a change the others refused."""
    from frappe_vault.services import linux_rotation_service as linux

    done = [o.hostname for o in applied.succeeded]
    if not done or not previous_password:
        return

    try:
        linux.apply_password_to_hosts(target, previous_password, done)
    except Exception:
        frappe.log_error(
            message=f"{doc.name}: could not restore {', '.join(done)} after a partial rotation.",
            title=f"Vault Linux Rollback Failed ({doc.name})",
        )


def _record_host_results(doc, result):
    """Write each host's outcome onto its row, outside the rotation transaction.

    The caller aborts on failure and the transaction is rolled back, so this has
    to be committed on its own — otherwise the per-host detail that says which
    machines are out of step would be discarded with everything else.
    """
    stamp = now_datetime()
    by_host = {o.hostname: o for o in result.outcomes}

    try:
        frappe.db.rollback()
        for row in doc.get("linux_hosts") or []:
            outcome = by_host.get((row.hostname or "").strip())
            if not outcome:
                continue
            frappe.db.set_value(
                "Vault Linux Host",
                row.name,
                {
                    "last_status": "Success" if outcome.ok else "Failed",
                    "last_applied_on": stamp,
                    "last_error": outcome.error[:500] if outcome.error else None,
                },
                update_modified=False,
            )
        frappe.db.commit()  # nosemgrep — per-host results must outlive the rollback
    except Exception:
        frappe.log_error(title=f"Vault Linux Host Status Write Failed ({doc.name})")


def _apply_to_target(doc, new_password: str, zip_password: str) -> "_Applied":
    """Change the password on the live database, and prove it took effect.

    Returns the applied change so the caller can undo it if the vault write that
    follows fails. Raises if the server refused, having recorded why.
    """
    from frappe_vault.services import db_rotation_service as target_service

    previous_password = doc.get_password(doc.rotating_field, raise_exception=False)
    target = target_service.build_target(doc, previous_password)
    description = target_service.describe(target)

    try:
        target_service.apply_password(target, new_password)
    except Exception as e:
        # Nothing changed anywhere; the vault still holds the working credential.
        _record_target_failure(doc.name, description, str(e))
        raise

    try:
        # The server said yes — confirm the account actually authenticates with
        # the new value before this secret starts claiming that it does.
        target_service.verify_credentials(target, new_password)
    except Exception as e:
        _handle_unverified_apply(doc, target, description, new_password, zip_password, str(e))
        raise

    doc.last_target_apply_status = "Success"
    doc.last_target_apply_on = now_datetime()
    doc.last_target_apply_error = None

    return _Applied(target=target, previous_password=previous_password, description=description)


def _undo_target_apply(doc, applied: "_Applied", new_password: str, zip_password: str):
    """Restore the server's previous password after the vault write failed.

    Without this the server would hold a password nothing has a record of.
    """
    from dataclasses import replace

    from frappe_vault.services import db_rotation_service as target_service
    from frappe_vault.services.linux_rotation_service import LinuxTarget

    target = applied.target

    if isinstance(target, LinuxTarget):
        # Ansible authenticates as its own account, never as the one that just
        # changed, so putting every host back needs no special handling.
        from frappe_vault.services import linux_rotation_service as linux

        try:
            linux.apply_password(target, applied.previous_password)
        except Exception as e:
            _escalate_desync(
                doc,
                applied.description,
                _("The vault could not be updated, and the hosts could not be put back — {0}").format(str(e)),
                new_password,
                zip_password,
            )
        return

    if not target.via_admin:
        # Self-service authenticates as the account itself, whose password is now
        # the one we just set — the stored credential no longer opens the door.
        target = replace(target, auth_password=new_password)

    try:
        target_service.apply_password(target, applied.previous_password)
    except Exception as e:
        _escalate_desync(
            doc,
            applied.description,
            _("The vault could not be updated, and the database could not be put back — {0}").format(str(e)),
            new_password,
            zip_password,
        )
        return

    _record_target_failure(
        doc.name,
        applied.description,
        "Applied, then reverted: the new password could not be stored in the vault.",
    )


def _handle_unverified_apply(
    doc, target, description: str, new_password: str, zip_password: str, reason: str
):
    """The server accepted the change but the account will not authenticate with it.

    Recoverable only when a rotation admin is configured, since its own password
    is untouched and can still reach the server. Otherwise nothing here can log
    in any more, so hand the candidate to an administrator and stop.
    """
    from frappe_vault.services import db_rotation_service as target_service

    if target.via_admin:
        # The admin credential is not the one that just changed, so it still works.
        try:
            target_service.apply_password(target, doc.get_password(doc.rotating_field))
            _record_target_failure(
                doc.name,
                description,
                f"Reverted: the new password did not authenticate after the change — {reason}",
            )
            return
        except Exception as revert_error:
            reason = f"{reason}; revert also failed — {revert_error}"

    _escalate_desync(doc, description, reason, new_password, zip_password)


def _escalate_desync(doc, description: str, reason: str, new_password: str, zip_password: str | None):
    """Vault and server may now disagree — give an admin what they need to fix it.

    Reached only when a database has (or may have) taken a password the vault
    could not record. The candidate travels in the usual AES-256 archive, never
    in the email body.
    """
    _record_target_failure(doc.name, description, f"OUT OF SYNC — {reason}")

    detail = f"Secret     : {doc.title} ({doc.name})\nTarget     : {description}\nWhat failed: {reason}\n"
    frappe.log_error(message=detail, title=f"Vault Rotation Left Secret Out Of Sync ({doc.name})")

    try:
        notify_vault_admins(
            subject=_("Rotation left '{0}' out of sync with its database").format(doc.title),
            email_content=_(
                "A rotated password may be live on {0} but could not be stored in the vault. "
                "The candidate has been emailed to Vault Admins as an encrypted archive."
            ).format(frappe.utils.escape_html(description)),
            document_type="Vault Secret",
            document_name=doc.name,
        )
    except Exception:
        frappe.log_error(title=f"Vault Desync Notification Failed ({doc.name})")

    if not zip_password:
        return

    from frappe_vault.services.notification_service import get_vault_admins

    try:
        admins = get_vault_admins()
        if not admins:
            return

        stamp = now_datetime().strftime("%Y%m%d-%H%M")
        archive = create_encrypted_zip(
            {
                f"{doc.name}-recovery.txt": (
                    detail + f"\nCandidate Password: {new_password}\n\n"
                    "Try this password against the target. If it works, set it as the secret's\n"
                    "value here so the two agree again; if it does not, the old stored password\n"
                    "is still the live one and no action is needed.\n"
                )
            },
            zip_password,
        )
        frappe.sendmail(
            recipients=admins,
            subject=_("[Vault] ACTION NEEDED: '{0}' may be out of sync with its database").format(doc.title),
            message=_(
                "<p>Rotation of <strong>{0}</strong> could not be completed cleanly.</p>"
                "<p>Target: {1}<br>Reason: {2}</p>"
                "<p>The candidate password is in the attached encrypted archive. "
                "Open it with this secret's rotation passphrase.</p>"
            ).format(
                frappe.utils.escape_html(doc.title or ""),
                frappe.utils.escape_html(description),
                frappe.utils.escape_html(reason),
            ),
            attachments=[{"fname": f"vault-recovery-{doc.name}-{stamp}.zip", "fcontent": archive}],
            reference_doctype="Vault Secret",
            reference_name=doc.name,
        )
    except Exception:
        frappe.log_error(title=f"Vault Desync Recovery Mail Failed ({doc.name})")


def _record_target_failure(secret_name: str, description: str, reason: str):
    """Persist why a live-database apply failed, outside the rotation transaction.

    The caller aborts the rotation right after this, and `run_password_rotation`
    rolls the transaction back — so the record of the failure has to be committed
    on its own or it would be discarded along with everything else.
    """
    try:
        frappe.db.rollback()
        frappe.db.set_value(
            "Vault Secret",
            secret_name,
            {
                "last_target_apply_status": "Failed",
                "last_target_apply_on": now_datetime(),
                "last_target_apply_error": f"{description}\n{reason}"[:2000],
            },
            update_modified=False,
        )
        frappe.db.commit()  # nosemgrep — this record must outlive the rollback above
    except Exception:
        frappe.log_error(title=f"Vault Rotation Target Status Write Failed ({secret_name})")


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


def _deliver(doc, new_password: str, recipients: list, zip_password: str | None, applied=None):
    """Tell everyone with access that the password changed.

    The encrypted archive only goes out when emailing is enabled and usable
    (`zip_password` is not None). Otherwise the in-app notification is the whole
    delivery, and it points people at the record — where the value is readable
    by exactly the people entitled to it, and by nobody else.
    """
    target = applied.description if applied else None

    if zip_password:
        _email_archive(doc, new_password, recipients, zip_password, target)

    if target:
        in_app = _("A new password was generated for '{0}' and applied to {1}.")
    else:
        in_app = _("A new password was generated for '{0}'.")

    where = (
        _("It has been emailed to you as an encrypted archive.")
        if zip_password
        else _("Open the secret in Vault to see it.")
    )

    for user in recipients:
        send_vault_notification(
            for_user=user,
            subject=_("Password rotated: {0}").format(doc.title),
            email_content=f"{in_app.format(doc.title, target)} {where}",
            notification_type="Alert",
            document_type="Vault Secret",
            document_name=doc.name,
            from_user="Administrator",
        )


def _email_archive(doc, new_password: str, recipients: list, zip_password: str, target: str | None):
    """Queue the AES-256 archive carrying the new password."""
    stamp = now_datetime().strftime("%Y%m%d-%H%M")
    filename = f"vault-rotation-{doc.name}-{stamp}.zip"
    custom = bool(doc.has_zip_passphrase)

    archive = create_encrypted_zip(
        {
            f"{doc.name}-{_slugify(doc.title)}.txt": _secret_payload(doc, new_password, target),
            "README.txt": _readme(custom, target),
        },
        zip_password,
    )

    frappe.sendmail(
        recipients=recipients,
        subject=_("[Vault] Password rotated: {0}").format(doc.title),
        message=_email_body(doc, custom, target),
        attachments=[{"fname": filename, "fcontent": archive}],
        reference_doctype="Vault Secret",
        reference_name=doc.name,
    )


def _secret_payload(doc, new_password: str, target: str | None = None) -> str:
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
    if doc.secret_type == "Database":
        if doc.database_type:
            lines.append(f"Engine       : {doc.database_type}")
        if doc.db_host:
            lines.append(f"Host         : {doc.db_host}:{doc.db_port or ''}".rstrip(":"))
        if doc.db_name:
            lines.append(f"Database     : {doc.db_name}")

    lines += [
        "",
        f"New Password : {new_password}",
        "",
        f"Rotated On   : {format_datetime(doc.last_rotated_on)}",
        f"Next Rotation: {format_datetime(doc.next_rotation_on)}",
        "",
        "-" * 60,
        APPLIED_NOTICE.format(target=target) if target else APPLY_WARNING,
        "-" * 60,
    ]
    return "\n".join(lines) + "\n"


def _readme(custom_passphrase: bool, target: str | None = None) -> str:
    passphrase_note = (
        "The passphrase is the one set specifically for this secret, shared with you\n"
        "by its owner separately — NOT the standing site-wide Vault passphrase."
        if custom_passphrase
        else "The passphrase is the standing Vault rotation passphrase issued to you\nseparately."
    )
    return (
        "Frappe Vault — Automatic Password Rotation\n"
        "==========================================\n\n"
        "A password you have access to was rotated on schedule. The new value is\n"
        "in the accompanying .txt file.\n\n"
        f"{APPLIED_NOTICE.format(target=target) if target else APPLY_WARNING}\n\n"
        "This archive is AES-256 encrypted. Open it with 7-Zip, WinRAR, Keka, or\n"
        "another tool that supports WinZip AES — the built-in extractor on some\n"
        "systems only handles legacy ZipCrypto and will report a bad passphrase.\n\n"
        f"{passphrase_note} It is never sent in the same email as this archive.\n\n"
        "Delete this archive once you have applied or recorded the new password.\n"
    )


def _email_body(doc, custom_passphrase: bool, target: str | None = None) -> str:
    """Email body. Deliberately contains neither the password nor the passphrase."""
    rows = [
        (_("Secret"), frappe.utils.escape_html(doc.title or "")),
        (_("Record"), frappe.utils.escape_html(doc.name)),
        (_("Rotated On"), format_datetime(doc.last_rotated_on)),
        (_("Next Rotation"), format_datetime(doc.next_rotation_on)),
    ]
    if doc.url:
        rows.insert(2, (_("URL"), frappe.utils.escape_html(doc.url)))
    if target:
        rows.insert(2, (_("Applied To"), frappe.utils.escape_html(target)))

    table = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#666;'>{label}</td>"
        + f"<td style='padding:4px 0;'><strong>{value}</strong></td></tr>"
        for label, value in rows
    )

    passphrase_hint = (
        _("Open it with the passphrase set specifically for this secret — not the shared site passphrase.")
        if custom_passphrase
        else _("Open it with the standing Vault rotation passphrase issued to you separately.")
    )

    if target:
        callout = (
            '<p style="padding:12px;background:#e8f5e9;border-left:3px solid #43a047;">'
            f"<strong>{_('The database has already been updated.')}</strong><br>"
            f"{_('Vault and the server are in sync. Update any application, connection string, or config file still using the old password.')}"
            "</p>"
        )
    else:
        callout = (
            '<p style="padding:12px;background:#fff8e1;border-left:3px solid #f5a623;">'
            f"<strong>{_('This changed the value stored in Vault only.')}</strong><br>"
            f"{_('The password on the actual server, database, or account has NOT been changed. Apply the new value there yourself, or the two will remain out of sync.')}"
            "</p>"
        )

    return f"""
        <p>{_("A password you have access to has been rotated automatically.")}</p>
        <table style="border-collapse:collapse;margin:16px 0;">{table}</table>
        <p>{_("The new password is in the attached encrypted archive.")} {passphrase_hint} {_("For your safety it is never included in this email.")}</p>
        {callout}
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
