"""Vault Secret DocType controller."""

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, get_datetime, now_datetime, today

# Absolute floor for generated and stored passwords, regardless of Vault Settings.
MIN_ROTATION_PASSWORD_LENGTH = 12

# Never let the history child table grow without bound.
MIN_HISTORY_ROWS = 10

# Floor for a user-supplied rotation passphrase — matches the site-wide
# vault_rotation_zip_password minimum in utils/archive.py.
MIN_ZIP_PASSPHRASE_LENGTH = 12


class VaultSecret(Document):
    """Controller for Vault Secret — the core secrets storage DocType."""

    def validate(self):
        """Validate the secret before saving."""
        self.validate_title()
        self.validate_rotation_config()
        self.validate_zip_passphrase()
        self.check_password_reuse()
        self.calculate_password_strength()
        self.validate_totp_secret()

    def validate_title(self):
        """Ensure title is present and trimmed."""
        if self.title:
            self.title = self.title.strip()
        if not self.title:
            frappe.throw(_("Title is required"))

    def validate_totp_secret(self):
        """Ensure the provided TOTP secret is a valid Base32 string and auto-pad if needed."""
        totp_secret_val = getattr(self, "totp_secret", None)
        if totp_secret_val and totp_secret_val != "*****":
            import re

            import pyotp

            clean_secret = str(totp_secret_val).strip().replace(" ", "").upper()
            if not clean_secret:
                self.totp_secret = ""
                return

            if clean_secret.isdigit() and len(clean_secret) in (6, 8):
                frappe.throw(
                    _(
                        "You entered a 6-digit TOTP passcode instead of the TOTP Secret Key. Please enter the Base32 2FA seed key."
                    )
                )

            unpadded = clean_secret.rstrip("=")
            if not unpadded or not re.match(r"^[A-Z2-7]+$", unpadded):
                frappe.throw(
                    _(
                        "Invalid TOTP Secret Key. Base32 keys can only contain letters A-Z and digits 2-7 (equal signs are only allowed at the end)."
                    )
                )

            if len(unpadded) < 16:
                frappe.throw(
                    _("TOTP Secret Key is too short. Base32 seed keys must be at least 16 characters long.")
                )

            rem = len(unpadded) % 8
            if rem in (1, 3, 6):
                frappe.throw(
                    _("Invalid Base32 TOTP Secret key length. You may have missed copying a character.")
                )

            try:
                pyotp.TOTP(unpadded).now()
                self.totp_secret = unpadded
            except Exception:
                frappe.throw(
                    _("Invalid TOTP Secret (2FA Seed). Please ensure you pasted a valid Base32 key.")
                )

    def calculate_password_strength(self):
        """Auto-calculate password strength when password changes."""
        if self.secret_type == "Password" and self.password:
            from frappe_vault.services.generator_service import calculate_password_strength

            strength = calculate_password_strength(self.password)
            self.password_strength = strength.get("level", "")

    def before_save(self):
        """Track password changes and maintain rotation schedule."""
        if self.is_new() or self.has_value_changed("password"):
            self.password_last_changed = today()

        self.append_password_history()
        self.update_has_zip_passphrase()
        self.compute_next_rotation()

    def after_insert(self):
        """Post-insert: update access metadata."""
        self.update_access_metadata()

    def update_access_metadata(self):
        """Update access tracking fields without triggering modified."""
        try:
            # Use direct frappe.db.set_value to avoid document reload deadlocks
            frappe.db.set_value(
                "Vault Secret",
                self.name,
                {
                    "last_accessed": now_datetime(),
                    "access_count": (self.access_count or 0) + 1,
                },
                update_modified=False,
            )
        except Exception:
            # Log the error with full traceback but never let statistics tracking block secret retrieval
            frappe.log_error(title=f"Vault Access Metadata Error ({self.name})")

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    def has_plaintext_password(self) -> bool:
        """True when `self.password` currently holds a real, newly-set password.

        Password fields only hold plaintext between the caller assigning them and
        `_save_passwords()` replacing the value with a `"*" * len` mask on write.
        A document loaded from the DB carries that mask, not the secret — hashing
        or strength-checking it would be meaningless.
        """
        if not self.password or self.is_dummy_password(self.password):
            return False

        return bool(self.is_new() or self.has_value_changed("password"))

    # ------------------------------------------------------------------
    # Custom rotation passphrase
    #
    # A secret's owner may set their own passphrase to protect its rotation
    # archive instead of the shared site-wide one. It is stored the same way
    # as this secret's own `password` — encrypted via Frappe's standard
    # Password-field mechanism, masked in this table, decryptable via
    # `get_password()` by anyone who could already decrypt `password` (i.e.
    # Administrator, or anyone with direct DB + site encryption_key access).
    # It is NOT a stronger guarantee than the rest of the vault; it exists so
    # this one archive can be opened with a passphrase distinct from the
    # shared site one, and so the hourly job can retrieve and use it
    # automatically — a genuinely unrecoverable (hashed) passphrase could
    # never be used by anything unattended, which is the tradeoff this field
    # deliberately does not make.
    # ------------------------------------------------------------------

    def has_plaintext_zip_passphrase(self) -> bool:
        """True when `self.zip_passphrase` holds a freshly typed value.

        Mirrors `has_plaintext_password` — a document loaded from the DB
        carries Frappe's `"*" * len` mask here, not the real value.
        """
        if not self.zip_passphrase or self.is_dummy_password(self.zip_passphrase):
            return False

        return bool(self.is_new() or self.has_value_changed("zip_passphrase"))

    def validate_zip_passphrase(self):
        """Enforce the same minimum length as the shared site passphrase."""
        if not self.has_plaintext_zip_passphrase():
            return

        if len(self.zip_passphrase) < MIN_ZIP_PASSPHRASE_LENGTH:
            frappe.throw(
                _("Custom Rotation Passphrase must be at least {0} characters.").format(
                    MIN_ZIP_PASSPHRASE_LENGTH
                )
            )

    def update_has_zip_passphrase(self):
        """Keep the status flag in sync with whether a passphrase is set.

        Always recomputed from the real field, never settable independently —
        nothing to forge here, since this simply mirrors `zip_passphrase`.
        """
        self.has_zip_passphrase = 1 if self.zip_passphrase else 0

    def clear_zip_passphrase(self):
        """Remove passphrase protection, restoring this secret to the shared passphrase."""
        self.zip_passphrase = ""
        self.has_zip_passphrase = 0

    def validate_rotation_config(self):
        """Reject rotation settings that the rotation job could not act on."""
        if not self.enable_rotation:
            return

        if self.secret_type != "Password":
            frappe.throw(
                _("Automatic rotation is only supported for secrets of type 'Password', not '{0}'.").format(
                    self.secret_type
                )
            )

        if cint(self.rotation_interval) < 1:
            frappe.throw(_("Rotate Every must be at least 1 when automatic rotation is enabled."))

        if self.rotation_unit not in ("Days", "Hours"):
            frappe.throw(_("Interval Unit must be either 'Days' or 'Hours'."))

    def check_password_reuse(self):
        """Block reuse of a recent password, per the Vault Settings policy.

        Compares against one-way hashes only; previous plaintext is never stored.
        """
        if not self.has_plaintext_password():
            return

        reuse_count = cint(frappe.db.get_single_value("Vault Settings", "prevent_reuse_count"))
        if reuse_count < 1:
            return

        from frappe.utils.password import passlibctx

        recent = sorted(self.get("password_history") or [], key=_history_sort_key, reverse=True)[:reuse_count]

        for row in recent:
            if not row.password_hash:
                continue
            try:
                if passlibctx.verify(self.password, row.password_hash):
                    frappe.throw(
                        _(
                            "This password was used within the last {0} change(s). Choose a different one."
                        ).format(reuse_count)
                    )
            except frappe.ValidationError:
                raise
            except Exception:
                # A malformed or legacy hash must never block saving a secret.
                frappe.log_error(title=f"Vault Password History Verify Error ({self.name})")

    def append_password_history(self):
        """Record a one-way hash of a newly set password."""
        if not self.has_plaintext_password():
            return

        from frappe.utils.password import passlibctx

        self.append(
            "password_history",
            {
                "password_hash": passlibctx.hash(self.password),
                "rotated_on": now_datetime(),
                "rotated_by": frappe.session.user if frappe.session else "Administrator",
                "source": "Auto Rotation" if self.flags.get("vault_auto_rotation") else "Manual",
            },
        )

        self.trim_password_history()

    def trim_password_history(self):
        """Keep only the newest rows needed to enforce the reuse policy."""
        reuse_count = cint(frappe.db.get_single_value("Vault Settings", "prevent_reuse_count"))
        keep = max(reuse_count, MIN_HISTORY_ROWS)

        rows = self.get("password_history") or []
        if len(rows) <= keep:
            return

        # Newest first, truncate, then restore chronological order for the grid.
        kept = list(reversed(sorted(rows, key=_history_sort_key, reverse=True)[:keep]))
        for idx, row in enumerate(kept, start=1):
            row.idx = idx

        self.set("password_history", kept)

    def compute_next_rotation(self):
        """Recalculate when this secret is next due for rotation."""
        if not self.enable_rotation:
            self.next_rotation_on = None
            return

        interval = cint(self.rotation_interval)
        if interval < 1:
            return

        # Anchor from now whenever the clock legitimately restarts: rotation was
        # just switched on, the password was just changed, or it has never been
        # rotated. Anchoring a freshly enabled secret from its (possibly ancient)
        # password_last_changed would fire an unannounced rotation within the hour.
        restart = (
            self.is_new()
            or self.has_value_changed("enable_rotation")
            or self.has_plaintext_password()
            or not self.last_rotated_on
        )
        anchor = now_datetime() if restart else get_datetime(self.last_rotated_on)

        if self.rotation_unit == "Hours":
            self.next_rotation_on = add_to_date(anchor, hours=interval)
        else:
            self.next_rotation_on = add_to_date(anchor, days=interval)


def _history_sort_key(row):
    """Sort password history rows newest-first, tolerating a missing timestamp."""
    return get_datetime(row.rotated_on) if row.rotated_on else datetime.min
