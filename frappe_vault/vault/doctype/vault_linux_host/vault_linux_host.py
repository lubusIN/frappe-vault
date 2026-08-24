"""Vault Linux Host — one machine a Linux Server secret's account lives on."""

from frappe.model.document import Document


class VaultLinuxHost(Document):
    """A single row in a Linux Server secret's inventory.

    Carries the per-host result of the last rotation, because a run across many
    machines needs to say *which* ones failed — an overall pass or fail is not
    actionable when twenty hosts are involved.
    """
