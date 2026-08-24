"""Encryption utilities for Frappe Vault."""

import frappe
from frappe.utils.password import get_decrypted_password


def decrypt_secret_field(doctype: str, name: str, fieldname: str) -> str:
    """Decrypt a password field value safely.

    Args:
        doctype: DocType name
        name: Document name
        fieldname: The password field to decrypt

    Returns:
        Decrypted string or empty string
    """
    try:
        val = get_decrypted_password(doctype, name, fieldname, raise_exception=False)
        if val:
            return val
    except Exception:
        frappe.log_error(title=f"Vault Secret Decryption Warning ({name}.{fieldname})")

    # Direct Auth table fallback for unauthenticated guest link consumers
    try:
        auth_val = frappe.db.get_value(
            "__Auth", {"doctype": doctype, "docname": name, "fieldname": fieldname}, "password"
        )
        if auth_val:
            from frappe.utils.password import decrypt

            return decrypt(auth_val)
    except Exception:
        frappe.log_error(title=f"Vault Auth Fallback Decryption Warning ({name}.{fieldname})")

    return ""


def get_decrypted_secret_data(secret_name: str, ignore_permissions: bool = False) -> dict:
    """Get all decrypted fields for a Vault Secret based on its type.

    Args:
        secret_name: Vault Secret document name
        ignore_permissions: Skip permission check (used by guest one-time link)

    Returns:
        dict with decrypted field values
    """
    # Reading a secret's *values* is deliberately stricter than reading the
    # record. `has_permission` lets Vault Admins, System Managers and
    # Administrator through so they can administer any secret; that bypass must
    # not extend to the plaintext. Only people actually granted this secret pass
    # here — see can_reveal_secret_value for what this does and does not
    # guarantee.
    if not ignore_permissions:
        from frappe import _

        from frappe_vault.utils.permissions import can_reveal_secret_value

        if not can_reveal_secret_value(secret_name):
            frappe.throw(
                _(
                    "Only this secret's owner and the people it has been shared with can view its "
                    "values. Administering the vault does not grant access to what is stored in it."
                ),
                frappe.PermissionError,
            )

        _log_reveal(secret_name)

    doc = frappe.get_doc("Vault Secret", secret_name)
    result = {}

    if doc.secret_type == "Password":
        result["password"] = decrypt_secret_field("Vault Secret", secret_name, "password")
        result["totp_secret"] = decrypt_secret_field("Vault Secret", secret_name, "totp_secret")
    elif doc.secret_type == "API Key":
        result["api_key"] = doc.api_key
        result["api_secret"] = decrypt_secret_field("Vault Secret", secret_name, "api_secret")
        result["totp_secret"] = decrypt_secret_field("Vault Secret", secret_name, "totp_secret")
    elif doc.secret_type == "Credit Card":
        result["card_number"] = decrypt_secret_field("Vault Secret", secret_name, "card_number")
        result["card_cvv"] = decrypt_secret_field("Vault Secret", secret_name, "card_cvv")
        result["card_holder"] = doc.card_holder
        result["card_expiry"] = doc.card_expiry
    elif doc.secret_type == "Database":
        result["database_type"] = doc.database_type
        result["db_host"] = doc.db_host
        result["db_port"] = doc.db_port
        result["db_name"] = doc.db_name
        result["db_auth_source"] = doc.db_auth_source
        result["db_use_ssl"] = doc.db_use_ssl
        result["username"] = doc.username
        result["db_password"] = decrypt_secret_field("Vault Secret", secret_name, "db_password")
        # rotation_admin_password is deliberately absent: it is an operational
        # credential the rotation job retrieves server-side, never something the
        # UI needs back — exactly like zip_passphrase.
    elif doc.secret_type == "SSH Key":
        result["username"] = doc.username
        result["ssh_private_key"] = doc.ssh_private_key
    elif doc.secret_type == "Certificate":
        result["certificate"] = doc.certificate

    return result


def _log_reveal(secret_name: str):
    """Record that someone decrypted this secret's values.

    Revealing plaintext is the event worth being able to reconstruct later, so
    it is logged separately from merely opening the record. A failure to write
    the audit row must never be the reason a legitimate reveal breaks, but it is
    logged loudly rather than swallowed.
    """
    try:
        from frappe_vault.services import audit_service

        audit_service._create_log(
            "Viewed",
            secret=secret_name,
            details={"revealed_values": True},
        )
    except Exception:
        frappe.log_error(title=f"Vault Reveal Audit Failed ({secret_name})")
