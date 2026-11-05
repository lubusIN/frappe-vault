"""Overrides of Frappe's generic whitelisted methods for Vault's records.

Registered via `override_whitelisted_methods` in hooks.py.
"""

import frappe
from frappe import _

# DocTypes whose Password fields hold vault secrets or the credentials that
# reach them. Their values are only ever handed out through Vault's own reveal
# path, which checks the caller was granted the secret and audits the read.
PROTECTED_DOCTYPES = frozenset({"Vault Secret", "Vault One Time Link", "Vault Settings"})


@frappe.whitelist()
def get_password(doctype: str, name: str | int, fieldname: str):
    """`frappe.client.get_password`, refused for Vault's DocTypes.

    Frappe lets any System Manager read any Password field through this one
    call. For vault records that would bypass both the reveal check (admin
    roles are not entitled to secret values) and the audit log, so it is
    refused here; every other DocType keeps Frappe's behaviour.
    """
    if doctype in PROTECTED_DOCTYPES:
        frappe.throw(
            _("Password fields of {0} cannot be read through this API. Use the Vault app.").format(
                _(doctype)
            ),
            frappe.PermissionError,
        )

    from frappe.client import get_password as frappe_get_password

    return frappe_get_password(doctype, name, fieldname)
