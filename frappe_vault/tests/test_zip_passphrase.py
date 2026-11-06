"""Tests for the per-secret rotation passphrase.

Stored encrypted the same way as this secret's own `password` field —
reversible, so the hourly job can retrieve and use it automatically. This is
NOT a stronger guarantee than the rest of the vault: anyone who could already
decrypt `password` (Administrator, or direct DB + site encryption_key access)
could decrypt this too. It exists so a secret's rotation archive can open with
a passphrase distinct from the shared site one, while still rotating on
schedule.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from frappe_vault.background_jobs.password_rotation import rotate_secret, run_password_rotation
from frappe_vault.vault.doctype.vault_secret.vault_secret import MIN_ZIP_PASSPHRASE_LENGTH

TEST_TITLES = [
    "Passphrase Store Secret",
    "Passphrase Clear Secret",
    "Passphrase Rotate Secret",
    "Passphrase Due Secret",
]

VALID_PASSPHRASE = "correct-horse-battery-staple"


def make_protected_secret(title, **kwargs):
    doc = frappe.get_doc(
        {
            "doctype": "Vault Secret",
            "title": title,
            "secret_type": "Password",
            "password": "InitialPassword123!",
            "enable_rotation": 1,
            "rotation_interval": 1,
            "rotation_unit": "Hours",
            "zip_passphrase": VALID_PASSPHRASE,
            **kwargs,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


class TestZipPassphrase(FrappeTestCase):
    def setUp(self):
        self.cleanup()
        # These tests exercise the passphrase-resolution logic in rotate_secret,
        # not delivery infrastructure — a real default outgoing Email Account
        # would need to be the site-wide default, and actually sending mail
        # (or leaving a broken account behind) risks bleeding into unrelated
        # tests. Skip the account precondition and stub the actual send.
        for target in (
            "frappe_vault.background_jobs.password_rotation._check_delivery_prereqs",
            "frappe.sendmail",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        names = frappe.get_all("Vault Secret", filters={"title": ["in", TEST_TITLES]}, pluck="name")
        for name in names:
            frappe.db.delete("Vault Audit Log", {"secret": name})
            frappe.db.delete("Notification Log", {"document_type": "Vault Secret", "document_name": name})
            frappe.delete_doc("Vault Secret", name, force=True, ignore_permissions=True)
        frappe.db.commit()

    # ------------------------------------------------------------------
    # Storage and retrieval
    # ------------------------------------------------------------------

    def test_passphrase_is_stored_and_flagged(self):
        doc = make_protected_secret("Passphrase Store Secret")
        self.assertTrue(doc.has_zip_passphrase)

    def test_passphrase_is_masked_in_the_main_table(self):
        """Same as password/api_secret/db_password — the raw value never sits
        in the plain doctype row, only the dummy mask."""
        doc = make_protected_secret("Passphrase Store Secret")

        raw_value = frappe.db.get_value("Vault Secret", doc.name, "zip_passphrase")
        self.assertNotEqual(raw_value, VALID_PASSPHRASE)
        self.assertTrue(doc.is_dummy_password(raw_value))

    def test_passphrase_is_recoverable_via_get_password(self):
        """This is the point of the switch: the server can retrieve it."""
        doc = make_protected_secret("Passphrase Store Secret")

        recovered = doc.get_password("zip_passphrase", raise_exception=False)
        self.assertEqual(recovered, VALID_PASSPHRASE)

    def test_reload_carries_the_mask_not_a_forgotten_value(self):
        doc = make_protected_secret("Passphrase Store Secret")

        reloaded = frappe.get_doc("Vault Secret", doc.name)
        self.assertTrue(reloaded.has_zip_passphrase)
        self.assertEqual(reloaded.get_password("zip_passphrase", raise_exception=False), VALID_PASSPHRASE)

    def test_get_secret_never_returns_the_passphrase_value(self):
        doc = make_protected_secret("Passphrase Store Secret")

        from frappe_vault.services.secret_service import get_secret

        result = get_secret(doc.name)
        self.assertTrue(result.get("has_zip_passphrase"))
        self.assertNotIn("zip_passphrase", result)

        decrypted = get_secret(doc.name, decrypt=True)
        self.assertNotIn("zip_passphrase", decrypted.get("decrypted", {}))

    def test_short_passphrase_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            make_protected_secret("Passphrase Store Secret", zip_passphrase="short")

    def test_minimum_length_passphrase_is_accepted(self):
        doc = make_protected_secret("Passphrase Store Secret", zip_passphrase="x" * MIN_ZIP_PASSPHRASE_LENGTH)
        self.assertTrue(doc.has_zip_passphrase)

    def test_has_zip_passphrase_cannot_be_forged_without_a_real_value(self):
        """has_zip_passphrase is always recomputed from zip_passphrase itself —
        submitting it directly with no real value has no effect."""
        doc = frappe.get_doc(
            {
                "doctype": "Vault Secret",
                "title": "Passphrase Store Secret",
                "secret_type": "Password",
                "password": "InitialPassword123!",
                "has_zip_passphrase": 1,
            }
        )
        doc.insert(ignore_permissions=True)
        self.assertFalse(doc.has_zip_passphrase)

    def test_leaving_the_field_untouched_on_update_preserves_it(self):
        """Editing an unrelated field must not wipe out an existing passphrase —
        Frappe's dummy-password check must recognize the reloaded mask."""
        doc = make_protected_secret("Passphrase Store Secret")

        from frappe_vault.services.secret_service import update_secret

        update_secret(doc.name, {"title": "Passphrase Store Secret"})

        reloaded = frappe.get_doc("Vault Secret", doc.name)
        self.assertTrue(reloaded.has_zip_passphrase)
        self.assertEqual(reloaded.get_password("zip_passphrase", raise_exception=False), VALID_PASSPHRASE)

    # ------------------------------------------------------------------
    # Clearing protection
    # ------------------------------------------------------------------

    def test_clear_zip_passphrase_removes_protection(self):
        doc = make_protected_secret("Passphrase Clear Secret")

        doc.clear_zip_passphrase()
        doc.save(ignore_permissions=True)

        reloaded = frappe.get_doc("Vault Secret", doc.name)
        self.assertFalse(reloaded.has_zip_passphrase)
        self.assertFalse(reloaded.get_password("zip_passphrase", raise_exception=False))

    def test_clear_zip_passphrase_api_requires_write_permission(self):
        doc = make_protected_secret("Passphrase Clear Secret")

        from frappe_vault.api.secrets import clear_zip_passphrase

        result = clear_zip_passphrase(doc.name)
        self.assertTrue(result["success"])

        reloaded = frappe.get_doc("Vault Secret", doc.name)
        self.assertFalse(reloaded.has_zip_passphrase)

    # ------------------------------------------------------------------
    # rotate_secret: retrieves and uses the custom passphrase automatically
    # ------------------------------------------------------------------

    def test_rotate_secret_uses_the_custom_passphrase_automatically(self):
        """No passphrase argument needed — the server retrieves its own."""
        doc = make_protected_secret("Passphrase Rotate Secret")

        result = rotate_secret(doc.name)

        self.assertEqual(result["name"], doc.name)
        reloaded = frappe.get_doc("Vault Secret", doc.name)
        self.assertIsNotNone(reloaded.last_rotated_on)

    def test_rotated_archive_is_actually_encrypted_with_the_custom_passphrase(self):
        """End-to-end: build the exact archive rotate_secret would build, using
        the passphrase it resolved, and confirm it opens with the value the
        owner set — not the shared site one."""
        doc = make_protected_secret("Passphrase Rotate Secret")

        from frappe_vault.background_jobs.password_rotation import _resolve_zip_password
        from frappe_vault.utils.archive import create_encrypted_zip

        resolved = _resolve_zip_password(doc)
        self.assertEqual(resolved, VALID_PASSPHRASE)

        archive = create_encrypted_zip({"secret.txt": "the-new-password"}, resolved)

        import io

        import pyzipper

        with pyzipper.AESZipFile(io.BytesIO(archive)) as z:
            z.setpassword(VALID_PASSPHRASE.encode())
            self.assertEqual(z.read("secret.txt"), b"the-new-password")

    def test_rotate_secret_uses_shared_passphrase_when_unprotected(self):
        doc = frappe.get_doc(
            {
                "doctype": "Vault Secret",
                "title": "Passphrase Rotate Secret",
                "secret_type": "Password",
                "password": "InitialPassword123!",
                "enable_rotation": 1,
                "rotation_interval": 1,
                "rotation_unit": "Hours",
            }
        )
        doc.insert(ignore_permissions=True)

        key = "vault_rotation_zip_password"
        had_key = key in frappe.conf
        original = frappe.conf.get(key)
        frappe.conf[key] = "a-shared-site-passphrase-123"
        try:
            result = rotate_secret(doc.name)
            self.assertEqual(result["name"], doc.name)
        finally:
            if had_key:
                frappe.conf[key] = original
            else:
                frappe.conf.pop(key, None)

    # ------------------------------------------------------------------
    # Scheduler: protected secrets rotate on schedule, same as any other
    # ------------------------------------------------------------------

    def test_scheduler_rotates_protected_secrets_automatically(self):
        doc = make_protected_secret("Passphrase Due Secret")
        frappe.db.set_value(
            "Vault Secret", doc.name, "next_rotation_on", add_to_date(now_datetime(), hours=-1)
        )
        frappe.db.commit()

        run_password_rotation()

        reloaded = frappe.get_doc("Vault Secret", doc.name)
        self.assertIsNotNone(reloaded.last_rotated_on)

        rotated_entry = frappe.get_all(
            "Vault Audit Log",
            filters={"secret": doc.name, "action": "Rotated"},
            fields=["details"],
            limit_page_length=1,
        )
        self.assertTrue(rotated_entry)
        self.assertIn('"custom_passphrase": true', rotated_entry[0].details)
