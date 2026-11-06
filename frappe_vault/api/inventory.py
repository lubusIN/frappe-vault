"""Picking Linux hosts from the Inventory Management app's VM records.

Soft integration, deliberately: `inventory_management` is a separate app that
may or may not be installed on any given site running `frappe_vault`. Nothing
here imports from it directly — every function checks the doctype exists
before touching it, and returns a "not available" answer rather than raising
when it doesn't, so a site without inventory_management sees an ordinary Vault
with no picker, not a broken one.

Permissions are the other half of that carefulness: this never elevates
access. A user who cannot read `Virtual Machines` in the desk gets the same
answer here — none of the API below uses `ignore_permissions`. Inventory
Management's own role model (System Manager / Inventory Manager / Inventory
Operator / Inventory Viewer) decides who sees anything, same as it always did;
being a Vault User grants nothing extra.
"""

import ipaddress
import re

import frappe
from frappe import _

VM_DOCTYPE = "Virtual Machines"

# The synthetic bucket for VMs with no server_role set. Most of the inventory
# falls here in practice — role tagging is the exception, not the rule — so
# without this bucket the picker would only ever surface a small minority of
# the fleet.
UNASSIGNED = "__unassigned__"


def _available() -> bool:
    """Whether the picker has anything to offer: the doctype exists, and the
    current user can read it."""
    return bool(frappe.db.exists("DocType", VM_DOCTYPE)) and frappe.has_permission(VM_DOCTYPE, "read")


@frappe.whitelist()
def is_available() -> dict:
    """Whether the "pick from inventory" option should appear at all.

    The frontend calls this once, up front, rather than surfacing a picker
    that then fails — a site without inventory_management, or a user without
    an Inventory role, should never see the option in the first place.
    """
    return {"available": _available()}


@frappe.whitelist()
def list_server_roles() -> list:
    """Every server_role in use, each with how many VMs carry it.

    Includes a synthetic "Unassigned" bucket for VMs with no role set — real
    data on this site has the large majority of VMs untagged, so omitting it
    would make the picker cover only a small slice of the fleet.
    """
    if not _available():
        return []

    # The whole table is small enough (hundreds of rows) that counting in
    # Python is simpler and more portable than an aggregate query, and avoids
    # this needing to track ORM-version-specific syntax for one.
    from collections import Counter

    values = frappe.get_list(VM_DOCTYPE, fields=["server_role"], pluck="server_role")
    counts = Counter((v or "").strip() for v in values)

    roles, unassigned_count = [], counts.pop("", 0)
    for role, count in counts.items():
        roles.append({"label": role, "value": role, "count": count})

    roles.sort(key=lambda r: r["label"].lower())
    if unassigned_count:
        roles.append({"label": _("Unassigned"), "value": UNASSIGNED, "count": unassigned_count})

    return roles


@frappe.whitelist()
def list_vms_for_role(server_role: str) -> list:
    """VMs carrying the given role, each with the best IPv4 address found.

    A VM whose only recorded addresses are unusable — "N/A", blank, an IPv6
    link-local address — is still returned, marked accordingly, rather than
    silently dropped: the caller needs to know a host exists but cannot be
    added yet, not just see a shorter list than the role count promised.
    """
    if not _available():
        return []

    filters = (
        {"server_role": ["in", ["", None]]} if server_role == UNASSIGNED else {"server_role": server_role}
    )

    rows = frappe.get_list(
        VM_DOCTYPE,
        filters=filters,
        fields=["name", "vm_name", "primary_ip", "extra_ip_address", "power_state"],
        order_by="vm_name asc",
    )

    result = []
    for row in rows:
        ip = _best_ipv4(row.get("primary_ip"), row.get("extra_ip_address"))
        result.append(
            {
                "name": row["name"],
                "vm_name": row.get("vm_name") or row["name"],
                "ip": ip,
                "power_state": row.get("power_state"),
                "has_usable_ip": bool(ip),
            }
        )

    return result


_IPV4_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def _best_ipv4(primary_ip: str | None, extra_ip_address: str | None) -> str | None:
    """The first usable IPv4 address across primary_ip and extra_ip_address.

    Source data mixes real addresses with the literal string "N/A", blank
    entries, and IPv6 link-local addresses in the same comma-separated field —
    none of those are something a Linux Server secret could ever connect to.
    """
    candidates = []
    if primary_ip:
        candidates.append(primary_ip)
    if extra_ip_address:
        candidates.extend(part.strip() for part in extra_ip_address.split(","))

    for candidate in candidates:
        match = _IPV4_RE.fullmatch(candidate.strip()) if candidate else None
        if not match:
            continue
        try:
            ipaddress.IPv4Address(match.group())
        except ValueError:
            continue
        return match.group()

    return None
