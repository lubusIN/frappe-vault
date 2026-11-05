"""Envelope encryption of vault secrets with HashiCorp Vault's Transit engine.

Frappe encrypts Password fields with one site-wide key kept in site_config.json,
next to the database. Whoever has both - a backup, a copied server - can read
every secret. With Transit enabled, each secret value is first encrypted by
HashiCorp Vault with a key that never leaves it; Frappe then stores only that
ciphertext (`vault:v1:...`), still under its own encryption as before.

Consequences:
  * a database dump plus the site key yields only Transit ciphertext;
  * every decryption is a request to HashiCorp, recorded by its audit device
    (outside the reach of Frappe administrators) and stoppable by revoking the
    AppRole;
  * the Transit key can be rotated in HashiCorp and data rewrapped.

Enabled per site in site_config.json - deliberately not in Vault Settings, so a
Frappe administrator cannot switch it off from the web UI:

    "vault_transit_key": "frappe-vault-secrets",
    "vault_transit_mount": "transit"            (optional, default "transit")

The connection (URL, namespace, AppRole credentials, TLS verification) is the
HashiCorp configuration in Vault Settings.

Failure is closed: with Transit enabled, a secret that cannot be encrypted is
not stored. Values written before Transit was enabled remain readable and are
converted by `rewrap_existing()`.
"""

import base64
import re

import frappe
from frappe import _

# DocTypes whose Password fields are Transit-wrapped. Vault Settings is not:
# its HashiCorp credentials are what Frappe uses to reach HashiCorp at all.
TRANSIT_DOCTYPES = ("Vault Secret", "Vault One Time Link")

_CIPHERTEXT_RE = re.compile(r"^vault:v\d+:[A-Za-z0-9+/=]+$")


class TransitError(frappe.ValidationError):
    """HashiCorp Transit could not encrypt or decrypt a value."""


def transit_key() -> str | None:
    """The Transit key name, or None when Transit is not enabled for this site."""
    return (frappe.conf.get("vault_transit_key") or "").strip() or None


def transit_mount() -> str:
    return (frappe.conf.get("vault_transit_mount") or "transit").strip().strip("/")


def is_ciphertext(value) -> bool:
    return isinstance(value, str) and bool(_CIPHERTEXT_RE.match(value))


# ----------------------------------------------------------------------
# Encrypt / decrypt
# ----------------------------------------------------------------------


def encrypt(plaintext: str) -> str:
    """Encrypt with the site's Transit key; returns `vault:vN:...`."""
    encoded = base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
    data = _call("encrypt", {"plaintext": encoded})
    ciphertext = data.get("ciphertext")
    if not is_ciphertext(ciphertext):
        raise TransitError(_("HashiCorp Transit returned no ciphertext."))
    return ciphertext


def decrypt(ciphertext: str) -> str:
    """Decrypt a `vault:vN:...` value with the site's Transit key."""
    data = _call("decrypt", {"ciphertext": ciphertext})
    try:
        return base64.b64decode(data["plaintext"]).decode("utf-8")
    except Exception as e:
        raise TransitError(_("HashiCorp Transit returned an unreadable value.")) from e


def wrap(value):
    """Transit-encrypt `value` when Transit is enabled; pass through otherwise."""
    if not value or not transit_key() or is_ciphertext(value):
        return value
    return encrypt(value)


def unwrap(value):
    """Decrypt a Transit ciphertext; leave anything else (legacy values) as is."""
    if not is_ciphertext(value):
        return value
    return decrypt(value)


def get_stored_password(doctype: str, name: str, fieldname: str, raise_exception: bool = False):
    """`frappe.utils.password.get_decrypted_password`, plus Transit unwrapping."""
    from frappe.utils.password import get_decrypted_password

    return unwrap(get_decrypted_password(doctype, name, fieldname, raise_exception=raise_exception))


def _call(operation: str, payload: dict) -> dict:
    """POST transit/<operation>/<key>, re-authenticating once on a stale token."""
    import requests

    from frappe_vault.integrations import hashicorp_vault as hv

    key = transit_key()
    if not key:
        raise TransitError(
            _(
                "A value is protected by HashiCorp Transit, but vault_transit_key is not set in site_config.json."
            )
        )

    settings = hv.get_settings()
    if not settings["url"]:
        raise TransitError(_("HashiCorp Vault URL is not configured in Vault Settings."))

    url = f"{settings['url']}/v1/{transit_mount()}/{operation}/{key}"
    for attempt in (1, 2):
        token = hv._resolve_token(settings)
        if not token:
            raise TransitError(_("Could not authenticate to HashiCorp Vault - check Vault Settings."))
        try:
            resp = requests.post(
                url,
                headers=hv._headers(settings, token),
                json=payload,
                verify=settings["verify_ssl"],
                timeout=hv.DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise TransitError(_("HashiCorp Vault is unreachable: {0}").format(type(e).__name__)) from e

        if resp.status_code == 403 and attempt == 1 and settings["auth_method"] == "AppRole":
            hv._invalidate_approle_token()  # cached AppRole token expired; log in again
            continue
        if resp.status_code >= 400:
            # The body can echo request data; report the status only.
            raise TransitError(
                _("HashiCorp Transit refused to {0} (HTTP {1}).").format(operation, resp.status_code)
            )
        return (resp.json() or {}).get("data") or {}

    raise TransitError(_("HashiCorp Transit refused to {0}.").format(operation))


# ----------------------------------------------------------------------
# Document integration
# ----------------------------------------------------------------------


class TransitPasswordsMixin:
    """Mix into a Document controller (before `Document`) to Transit-wrap its
    Password fields on save and unwrap them on read.

    Wrapping happens in `_save_passwords`, after `validate`/`before_save`, so
    all of Vault's own logic (strength, reuse, history, rotation flags) still
    sees plaintext.
    """

    def _save_passwords(self):
        ignore = self.flags.ignore_save_passwords
        if transit_key() and ignore is not True:
            for df in self.meta.get("fields", {"fieldtype": ("=", "Password")}):
                if ignore and df.fieldname in ignore:
                    continue
                value = self.get(df.fieldname)
                if value and not self.is_dummy_password(value) and not is_ciphertext(value):
                    self.set(df.fieldname, encrypt(value))
        super()._save_passwords()

    def get_password(self, fieldname="password", raise_exception=True):
        value = self.get(fieldname)
        if value and not self.is_dummy_password(value):
            return unwrap(value)
        return get_stored_password(self.doctype, self.name, fieldname, raise_exception=raise_exception)


# ----------------------------------------------------------------------
# Migration / verification (bench execute)
# ----------------------------------------------------------------------


def rewrap_existing(dry_run: bool = True) -> dict:
    """Transit-encrypt every stored secret value that is not yet Transit-protected.

    bench --site <site> execute frappe_vault.integrations.transit.rewrap_existing --kwargs "{'dry_run': False}"
    """
    from frappe.utils.password import get_decrypted_password, set_encrypted_password

    if not transit_key():
        frappe.throw(_("Set vault_transit_key in site_config.json first."))

    counts = {"already_protected": 0, "rewrapped": 0, "would_rewrap": 0, "empty": 0}
    for doctype, name, fieldname in _stored_fields():
        value = get_decrypted_password(doctype, name, fieldname, raise_exception=False)
        if not value:
            counts["empty"] += 1
        elif is_ciphertext(value):
            counts["already_protected"] += 1
        elif dry_run:
            counts["would_rewrap"] += 1
        else:
            set_encrypted_password(doctype, name, encrypt(value), fieldname)
            counts["rewrapped"] += 1

    if not dry_run:
        frappe.db.commit()  # nosemgrep - one-off migration run from bench execute
    return counts


def verify_protection() -> dict:
    """Prove the stored values are Transit ciphertext under Frappe's own key.

    Decrypts every stored value with Frappe's site key only - what anyone holding
    a database dump plus site_config.json could do - and counts how many come
    out as plaintext. Prints nothing secret.
    """
    from frappe.utils.password import get_decrypted_password

    report = {"transit_ciphertext": 0, "plaintext": 0, "plaintext_fields": []}
    for doctype, name, fieldname in _stored_fields():
        value = get_decrypted_password(doctype, name, fieldname, raise_exception=False)
        if not value:
            continue
        if is_ciphertext(value):
            report["transit_ciphertext"] += 1
        else:
            report["plaintext"] += 1
            report["plaintext_fields"].append(f"{doctype}/{name}/{fieldname}")
    return report


def _stored_fields():
    auth = frappe.qb.Table("__Auth")
    rows = (
        frappe.qb.from_(auth)
        .select(auth.doctype, auth.name, auth.fieldname)
        .where(auth.doctype.isin(TRANSIT_DOCTYPES) & (auth.encrypted == 1))
    ).run()
    return [tuple(r) for r in rows]
