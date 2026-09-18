"""HashiCorp Vault integration.

Pushes a Vault Secret's current values out to an external HashiCorp Vault KV v2
store. Frappe Vault stays the single source of truth — this module is
one-directional and never reads HashiCorp Vault back into a secret.

Two paths reach `push_secret`, so the KV entry never has a chance to drift
from what is actually stored here:

- Manual: the "Sync to HashiCorp Vault" button on a Vault Secret, any time.
- Automatic: `on_secret_update` (wired in hooks.py's `on_update` for
  "Vault Secret") re-syncs whenever a secret is first created or one of its
  rotatable credential fields changes — a manual edit, "Rotate Now", or the
  hourly rotation job all end in `doc.save()`, so all three reach it the same
  way. Queued with `enqueue_after_commit` so a slow or unreachable Vault
  server never blocks or fails the save itself.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

DEFAULT_TIMEOUT = 10

# Cache key for the short-lived token an AppRole login exchanges the Secret ID
# for. Site-scoped by frappe.cache() automatically. Never holds the Secret ID
# itself — only the resulting Vault token, and only until it is close to
# expiry (see _login_approle).
_APPROLE_TOKEN_CACHE_KEY = "hashicorp_vault_approle_token"

# How much earlier than its real expiry a cached AppRole token is treated as
# expired, so a request never starts with a token that dies mid-flight.
_TOKEN_EXPIRY_MARGIN_SEC = 30


def get_settings() -> dict:
    """Resolve HashiCorp Vault connection settings from Vault Settings."""
    settings = frappe.get_cached_doc("Vault Settings")
    return {
        "enabled": bool(settings.get("enable_hashicorp_vault")),
        "url": (settings.get("hashicorp_vault_url") or "").rstrip("/"),
        "namespace": (settings.get("hashicorp_vault_namespace") or "").strip() or None,
        "mount": (settings.get("hashicorp_vault_mount") or "secret").strip("/"),
        "prefix": (settings.get("hashicorp_vault_path_prefix") or "frappe-vault").strip("/"),
        # Fail safe: an unset value (e.g. a Single field never backfilled by a
        # migrate) verifies rather than silently disabling certificate checks.
        "verify_ssl": settings.get("hashicorp_verify_ssl") != 0,
        "sync_on_change": settings.get("sync_on_password_change") != 0,
        "auth_method": settings.get("hashicorp_auth_method") or "AppRole",
        "token": settings.get_password("hashicorp_vault_token", raise_exception=False),
        "approle_mount": (settings.get("hashicorp_approle_mount") or "approle").strip("/"),
        "role_id": settings.get("hashicorp_role_id") or None,
        "secret_id": settings.get_password("hashicorp_secret_id", raise_exception=False),
    }


def _resolve_token(settings: dict) -> str | None:
    """The Vault token to authenticate with — static, or a fresh AppRole login.

    With AppRole, the Secret ID never goes on the wire more than it has to:
    it is exchanged for a short-lived token here, that token is cached until
    shortly before it expires, and every actual Vault request downstream
    (KV write, connection test) uses only the cached token, never the
    Secret ID itself.
    """
    if settings["auth_method"] == "Token":
        return settings["token"]

    return _login_approle(settings)


def _login_approle(settings: dict) -> str | None:
    if not settings["role_id"] or not settings["secret_id"]:
        return None

    cached = frappe.cache().get_value(_APPROLE_TOKEN_CACHE_KEY)
    if cached:
        return cached

    import requests

    try:
        resp = requests.post(
            f"{settings['url']}/v1/auth/{settings['approle_mount']}/login",
            json={"role_id": settings["role_id"], "secret_id": settings["secret_id"]},
            verify=settings["verify_ssl"],
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        frappe.log_error(title="HashiCorp Vault AppRole Login Failed", message=str(e))
        return None

    auth = resp.json().get("auth") or {}
    token = auth.get("client_token")
    if not token:
        return None

    lease = frappe.utils.cint(auth.get("lease_duration")) or 3600
    ttl = max(lease - _TOKEN_EXPIRY_MARGIN_SEC, 5)
    frappe.cache().set_value(_APPROLE_TOKEN_CACHE_KEY, token, expires_in_sec=ttl)
    return token


def _invalidate_approle_token():
    """Drop a cached AppRole token so the next call logs in fresh.

    Called whenever Vault itself rejects a request with 403 — the cached
    token may have been revoked or Vault restarted since it was issued, and
    there is no point waiting out the rest of its cached TTL to find that out
    again.
    """
    frappe.cache().delete_value(_APPROLE_TOKEN_CACHE_KEY)


def _headers(settings: dict, token: str) -> dict:
    headers = {"X-Vault-Token": token}
    if settings["namespace"]:
        headers["X-Vault-Namespace"] = settings["namespace"]
    return headers


def _kv_path(settings: dict, secret_name: str) -> str:
    return f"{settings['prefix']}/{secret_name}"


def _kv_url(settings: dict, secret_name: str) -> str:
    return f"{settings['url']}/v1/{settings['mount']}/data/{_kv_path(settings, secret_name)}"


def check_connection() -> dict:
    """Prove the configured URL and token actually reach HashiCorp Vault.

    Raises on any failure — the caller (an explicit "Test Connection" click)
    wants a clear reason, not a best-effort result.
    """
    settings = get_settings()
    if not settings["url"]:
        frappe.throw(_("Set the Vault Server URL in Vault Settings first."))

    token = _resolve_token(settings)
    if not token:
        if settings["auth_method"] == "AppRole":
            frappe.throw(
                _(
                    "Could not obtain a token from AppRole — check the Role ID, Secret ID, and "
                    "AppRole Mount Path in Vault Settings, and the Error Log for details."
                )
            )
        frappe.throw(_("Set the Vault Token in Vault Settings first."))

    import requests

    try:
        resp = requests.get(
            f"{settings['url']}/v1/auth/token/lookup-self",
            headers=_headers(settings, token),
            verify=settings["verify_ssl"],
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        frappe.throw(_("Could not reach {0}: {1}").format(settings["url"], str(e)))

    if resp.status_code == 403 and settings["auth_method"] == "AppRole":
        _invalidate_approle_token()

    if resp.status_code != 200:
        frappe.throw(
            _("HashiCorp Vault rejected the token (HTTP {0}): {1}").format(
                resp.status_code, resp.text[:300]
            )
        )

    policies = (resp.json().get("data") or {}).get("policies") or []
    return {
        "success": True,
        "message": _("Connected to {0}. Token policies: {1}").format(
            settings["url"], ", ".join(policies) or "-"
        ),
    }


def push_secret(secret_name: str) -> dict:
    """Push one Vault Secret's current values to HashiCorp Vault.

    Never raises — every outcome, including a misconfigured or unreachable
    Vault, comes back as a result dict so both the synchronous button click
    and the background auto-sync job can report it without a try/except of
    their own.
    """
    settings = get_settings()
    if not settings["enabled"]:
        return {
            "success": False,
            "skipped": True,
            "message": _("HashiCorp Vault sync is not enabled in Vault Settings."),
        }

    if not settings["url"]:
        return {
            "success": False,
            "skipped": True,
            "message": _("HashiCorp Vault URL is not configured in Vault Settings."),
        }

    token = _resolve_token(settings)
    if not token:
        message = (
            _("Could not obtain a token from AppRole — check Vault Settings.")
            if settings["auth_method"] == "AppRole"
            else _("HashiCorp Vault Token is not configured in Vault Settings.")
        )
        return {"success": False, "skipped": True, "message": message}

    doc = frappe.get_doc("Vault Secret", secret_name)
    payload = _build_payload(doc)
    url = _kv_url(settings, secret_name)

    import requests

    resp = None
    try:
        resp = requests.post(
            url,
            headers=_headers(settings, token),
            json={"data": payload},
            verify=settings["verify_ssl"],
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        if getattr(resp, "status_code", None) == 403 and settings["auth_method"] == "AppRole":
            _invalidate_approle_token()
        error = str(e)
        _record_sync_result(secret_name, "Failed", error)
        frappe.log_error(title=f"HashiCorp Vault Sync Failed ({secret_name})", message=error)
        return {"success": False, "message": _("Sync to HashiCorp Vault failed: {0}").format(error)}

    path = _kv_path(settings, secret_name)
    _record_sync_result(secret_name, "Success", None, path=path)

    from frappe_vault.services import audit_service

    audit_service._create_log(
        "Synced to HashiCorp Vault",
        secret=doc.name,
        folder=doc.folder,
        details={"path": path, "mount": settings["mount"]},
    )

    return {
        "success": True,
        "path": path,
        "message": _("Synced to HashiCorp Vault at {0}.").format(path),
    }


def on_secret_update(doc, method=None):
    """doc_events hook for "Vault Secret" on_update — see module docstring."""
    if not doc.flags.get("vault_sync_pending"):
        return

    settings = get_settings()
    if not (settings["enabled"] and settings["sync_on_change"]):
        return

    frappe.enqueue(
        "frappe_vault.integrations.hashicorp_vault.push_secret",
        queue="short",
        enqueue_after_commit=True,
        secret_name=doc.name,
    )


def _build_payload(doc) -> dict:
    """The document values to store in HashiCorp Vault, decrypted.

    `ignore_permissions=True` is deliberate: this runs only after the caller
    already proved write access to the secret (the API layer's permission
    check, or a system job acting on a save that has already happened) —
    the same standing that "Rotate Now" and the rotation job itself act with,
    not the stricter "reveal in the UI" permission.
    """
    from frappe_vault.utils.encryption import get_decrypted_secret_data

    values = get_decrypted_secret_data(doc.name, ignore_permissions=True)

    payload = {"title": doc.title, "secret_type": doc.secret_type}
    for field in ("username", "url", "notes"):
        value = doc.get(field)
        if value:
            payload[field] = value

    payload.update({k: v for k, v in values.items() if v not in (None, "")})
    return payload


def _record_sync_result(secret_name: str, status: str, error: str | None, path: str | None = None):
    """Persist sync status directly, bypassing the controller.

    `frappe.db.set_value` does not fire doc_events — going through
    `doc.save()` here would re-trigger `on_secret_update` and loop. Rollback
    first and commit after, matching how the rotation job records its own
    out-of-band status (see `password_rotation._record_target_failure`):
    this can run after a request exception already left the transaction in a
    state that must not carry through to this write.
    """
    values = {
        "hashicorp_sync_status": status,
        "hashicorp_synced_on": now_datetime(),
        "hashicorp_sync_error": (error or "")[:2000] if status == "Failed" else "",
    }
    if path:
        values["hashicorp_vault_path"] = path

    try:
        frappe.db.rollback()
        frappe.db.set_value("Vault Secret", secret_name, values, update_modified=False)
        frappe.db.commit()  # nosemgrep — sync status must persist independent of caller's transaction
    except Exception:
        frappe.log_error(title=f"HashiCorp Vault Sync Status Write Failed ({secret_name})")
