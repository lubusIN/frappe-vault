"""Encrypted archive utilities for Frappe Vault.

Rotated passwords leave the vault as AES-256 encrypted ZIP attachments. The
stdlib `zipfile` module can only *read* encrypted archives, never write them,
so this builds them with `pyzipper` (declared in pyproject.toml).
"""

import io

import frappe

# site_config.json / common_site_config.json key holding the archive passphrase.
# Follows the precedent of core's BACKUP_ENCRYPTION_CONFIG_KEY.
ROTATION_ZIP_PASSWORD_KEY = "vault_rotation_zip_password"

# A passphrase shorter than this is treated as absent rather than trusted.
MIN_ZIP_PASSWORD_LENGTH = 12


def get_rotation_zip_password() -> str | None:
    """Return the configured archive passphrase, or None if unusable.

    Set it with:
        bench --site <site> set-config vault_rotation_zip_password '<passphrase>'
    """
    password = frappe.conf.get(ROTATION_ZIP_PASSWORD_KEY)

    if not password or not isinstance(password, str):
        return None

    if len(password) < MIN_ZIP_PASSWORD_LENGTH:
        return None

    return password


def create_encrypted_zip(files: dict[str, str | bytes], password: str) -> bytes:
    """Build an AES-256 encrypted ZIP archive in memory.

    Args:
        files: mapping of archive member name -> text or bytes content
        password: passphrase required to extract the archive

    Returns:
        The complete .zip file as bytes

    Raises:
        ValueError: if no password or no files were supplied
    """
    if not password:
        raise ValueError("A passphrase is required to build an encrypted archive")

    if not files:
        raise ValueError("Refusing to build an empty archive")

    import pyzipper

    buffer = io.BytesIO()

    with pyzipper.AESZipFile(
        buffer,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as archive:
        archive.setpassword(password.encode("utf-8"))
        for filename, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            archive.writestr(filename, content)

    return buffer.getvalue()
