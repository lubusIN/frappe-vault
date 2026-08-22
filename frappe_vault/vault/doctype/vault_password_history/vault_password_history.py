"""Vault Password History DocType controller."""

from frappe.model.document import Document


class VaultPasswordHistory(Document):
    """Child table of one-way hashes of a secret's previous passwords.

    Only hashes are stored — past plaintext is unrecoverable. Rows exist solely
    to enforce the `prevent_reuse_count` policy from Vault Settings.
    """

    pass
