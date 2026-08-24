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

# Which encrypted field a secret type's rotation, history, reuse policy and
# strength score act on. A type absent from this map cannot be rotated at all.
ROTATABLE_FIELD_BY_TYPE = {
    "Password": "password",
    "Database": "db_password",
    "Linux Server": "password",
}

# Types whose rotation must reach the real system it belongs to. A rotation that
# only changed the stored value would leave the vault holding a password the
# server has never heard of, which is worse than not rotating at all: nobody can
# log in, and nobody can tell why.
SYNCED_TYPES = ("Database", "Linux Server")


class VaultSecret(Document):
    """Controller for Vault Secret — the core secrets storage DocType."""

    def validate(self):
        """Validate the secret before saving."""
        self.validate_title()
        self.validate_linux_config()
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
        """Auto-calculate strength whenever the rotating value changes."""
        if not self.has_plaintext_password():
            return

        from frappe_vault.services.generator_service import calculate_password_strength

        strength = calculate_password_strength(self.get_rotating_value())
        self.password_strength = strength.get("level", "")

    def before_save(self):
        """Track password changes and maintain rotation schedule."""
        if self.is_new() or self.has_value_changed(self.rotating_field or "password"):
            self.password_last_changed = today()

        self.append_password_history()
        self.update_has_zip_passphrase()
        self.clear_orphaned_rotation_admin()
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

    @property
    def rotating_field(self) -> str | None:
        """The encrypted fieldname this secret's rotation machinery acts on.

        `password` for a Password secret, `db_password` for a Database one, and
        None for a type that cannot be rotated.
        """
        return ROTATABLE_FIELD_BY_TYPE.get(self.secret_type)

    def get_rotating_value(self) -> str | None:
        """The in-memory value of the rotating field, whatever it is called."""
        field = self.rotating_field
        return self.get(field) if field else None

    def has_plaintext_password(self) -> bool:
        """True when the rotating field currently holds a real, newly-set value.

        Password fields only hold plaintext between the caller assigning them and
        `_save_passwords()` replacing the value with a `"*" * len` mask on write.
        A document loaded from the DB carries that mask, not the secret — hashing
        or strength-checking it would be meaningless.
        """
        field = self.rotating_field
        if not field:
            return False

        value = self.get(field)
        if not value or self.is_dummy_password(value):
            return False

        if self.is_new():
            return True

        if not self.has_value_changed(field):
            return False

        # Re-submitting the value that is already stored is not a change of
        # password. The edit form is populated with the decrypted value, so
        # saving any other field sends it back verbatim; against the masked
        # value held in the row that looks like a brand new password, and the
        # reuse policy would then reject the save for reusing the password the
        # secret already has.
        # Read straight from storage: Document.get_password() short-circuits to
        # the in-memory value when one is set, which here is the very value being
        # compared — that would make every password look unchanged and quietly
        # disable history, the reuse policy and strength scoring alike.
        from frappe.utils.password import get_decrypted_password

        stored = get_decrypted_password(self.doctype, self.name, field, raise_exception=False)
        return stored != value

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

    def clear_orphaned_rotation_admin(self):
        """Drop the rotation admin password once its username is gone.

        Clearing the username is how the UI removes the pair; leaving the
        password behind would keep a privileged credential stored for an account
        nothing references any more.
        """
        if not (self.rotation_admin_username or "").strip():
            self.rotation_admin_username = ""
            self.rotation_admin_password = ""

    def clear_zip_passphrase(self):
        """Remove passphrase protection, restoring this secret to the shared passphrase."""
        self.zip_passphrase = ""
        self.has_zip_passphrase = 0

    def validate_rotation_config(self):
        """Reject rotation settings that the rotation job could not act on."""
        if not self.enable_rotation:
            # A disabled schedule cannot apply anything to a server either.
            self.apply_rotation_to_target = 0
            return

        if not self.rotating_field:
            frappe.throw(
                _("Automatic rotation is only supported for secrets of type {0} — not '{1}'.").format(
                    ", ".join(f"'{t}'" for t in sorted(ROTATABLE_FIELD_BY_TYPE)),
                    self.secret_type,
                )
            )

        if cint(self.rotation_interval) < 1:
            frappe.throw(_("Rotate Every must be at least 1 when automatic rotation is enabled."))

        if self.rotation_unit not in ("Days", "Hours"):
            frappe.throw(_("Interval Unit must be either 'Days' or 'Hours'."))

        # Rotating a Database or Linux credential always reaches the real system.
        # It is not an option to turn off: the whole value of rotating these is
        # that the vault and the server keep agreeing with each other.
        if self.secret_type in SYNCED_TYPES:
            self.apply_rotation_to_target = 1

        if self.secret_type != "Linux Server":
            self.validate_target_apply_config()

    def validate_linux_config(self):
        """Reject a Linux setup the rotation job could not act on.

        Runs for every Linux Server secret, not only rotating ones: the hosts and
        the automation account are what the type *is*, and a secret stored
        half-configured today becomes a rotation that fails unattended the moment
        somebody enables it.
        """
        if self.secret_type != "Linux Server":
            return

        hosts = [r for r in (self.get("linux_hosts") or []) if (r.hostname or "").strip()]
        if not hosts:
            frappe.throw(
                _(
                    "Add at least one host. A Linux rotation has nowhere to apply the new password without one."
                )
            )

        seen = set()
        for row in hosts:
            hostname = row.hostname.strip()
            if hostname in seen:
                frappe.throw(_("Host '{0}' is listed more than once.").format(hostname))
            seen.add(hostname)

        if not self.username:
            frappe.throw(_("Username is required — it names the Linux account whose password is changed."))

        if not (self.ansible_user or "").strip():
            frappe.throw(_("An Ansible User is required to reach these hosts."))

        if self.ansible_user.strip() == self.username.strip():
            frappe.throw(
                _(
                    "The Ansible User cannot be the account being rotated ('{0}') — changing its password "
                    "would lock Vault out of these hosts."
                ).format(self.username)
            )

        # SSH key only, deliberately: no password path for the automation account,
        # so there is no SSH credential for it sitting in the vault to brute-force
        # or reuse.
        if not self.ansible_ssh_private_key:
            frappe.throw(
                _(
                    "An SSH Private Key is required. Vault only connects to Linux hosts by key, never a "
                    "password."
                )
            )

    def validate_target_apply_config(self):
        """Reject an 'apply to the live database' setup the rotation job could not carry out.

        Everything here is checked at save time rather than at rotation time: a
        secret that silently fails its first unattended rotation is worse than
        one that refuses to be saved half-configured.
        """
        if not self.apply_rotation_to_target:
            return

        if self.secret_type != "Database":
            frappe.throw(
                _("Applying a rotated password to a live server is only supported for Database secrets.")
            )

        from frappe_vault.services.db_rotation_service import SUPPORTED_DATABASE_TYPES

        if self.database_type not in SUPPORTED_DATABASE_TYPES:
            frappe.throw(
                _(
                    "Choose a Database Type ({0}) before enabling 'Apply New Password to the Database'."
                ).format(", ".join(SUPPORTED_DATABASE_TYPES))
            )

        if not self.db_host:
            frappe.throw(_("Host is required to apply a rotated password to the database."))

        if not self.username:
            frappe.throw(
                _("Username is required — it names the database account whose password gets changed.")
            )

        # An admin credential is required rather than optional: relying on the
        # account to change its own password fails on any server that withholds
        # that privilege, and it fails unattended, hours after the setup that
        # caused it. Requiring it here means the Test Connection step can prove
        # the whole path works before anything is saved.
        if not (self.rotation_admin_username or "").strip():
            frappe.throw(
                _(
                    "A Rotation Admin Username is required to apply a rotated password to the database. "
                    "It is the account Vault authenticates as to reset '{0}'."
                ).format(self.username or "this account")
            )

        if not self.rotation_admin_password:
            frappe.throw(_("A Rotation Admin Password is required alongside a Rotation Admin Username."))

    def check_password_reuse(self):
        """Block reuse of a recent password, per the Vault Settings policy."""
        if not self.has_plaintext_password():
            return

        reuse_count = cint(frappe.db.get_single_value("Vault Settings", "prevent_reuse_count"))
        if self.is_password_reused(self.get_rotating_value(), reuse_count):
            frappe.throw(
                _("This password was used within the last {0} change(s). Choose a different one.").format(
                    reuse_count
                )
            )

    def is_password_reused(self, candidate: str, reuse_count: int | None = None) -> bool:
        """True when `candidate` matches a recent entry in this secret's history.

        Compares against one-way hashes only; previous plaintext is never stored.
        Rotation calls this to screen a generated password *before* pushing it to
        a live database — discovering the clash on the way back in, after the
        server had already accepted it, would leave the two out of sync.
        """
        if not candidate:
            return False

        if reuse_count is None:
            reuse_count = cint(frappe.db.get_single_value("Vault Settings", "prevent_reuse_count"))

        if reuse_count < 1:
            return False

        from frappe.utils.password import passlibctx

        recent = sorted(self.get("password_history") or [], key=_history_sort_key, reverse=True)[:reuse_count]

        for row in recent:
            if not row.password_hash:
                continue
            try:
                if passlibctx.verify(candidate, row.password_hash):
                    return True
            except Exception:
                # A malformed or legacy hash must never block saving a secret.
                frappe.log_error(title=f"Vault Password History Verify Error ({self.name})")

        return False

    def append_password_history(self):
        """Record a one-way hash of a newly set password."""
        if not self.has_plaintext_password():
            return

        from frappe.utils.password import passlibctx

        self.append(
            "password_history",
            {
                "password_hash": passlibctx.hash(self.get_rotating_value()),
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
