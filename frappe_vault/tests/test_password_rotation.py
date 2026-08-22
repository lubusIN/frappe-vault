import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from frappe_vault.background_jobs.password_rotation import (
    _generate_password,
    _rotation_password_length,
    _slugify,
)
from frappe_vault.utils.archive import create_encrypted_zip
from frappe_vault.utils.permissions import get_users_with_secret_access
from frappe_vault.vault.doctype.vault_secret.vault_secret import MIN_ROTATION_PASSWORD_LENGTH

TEST_TITLES = [
    "Rotation Days Secret",
    "Rotation Hours Secret",
    "Rotation Reuse Secret",
    "Rotation Access Secret",
    "Rotation Nontype Secret",
    "Rotation Due Secret",
    "Rotation Future Secret",
    "Rotation Disabled Secret",
]

TEST_USERS = ["rotation-owner@example.com", "rotation-shared@example.com", "rotation-revoked@example.com"]


def make_secret(**kwargs):
    """Create a Vault Secret with sane rotation-test defaults."""
    doc = frappe.get_doc(
        {
            "doctype": "Vault Secret",
            "secret_type": "Password",
            "password": "InitialPassword123!",
            **kwargs,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


class TestPasswordRotation(FrappeTestCase):
    def setUp(self):
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        names = frappe.get_all("Vault Secret", filters={"title": ["in", TEST_TITLES]}, pluck="name")
        for name in names:
            frappe.db.delete("Vault Share", {"shared_name": name})
            frappe.db.delete("Vault Audit Log", {"secret": name})
            frappe.delete_doc("Vault Secret", name, force=True, ignore_permissions=True)

        # This site's tests run against the live DB, so fixtures must not survive
        # the run — remove the throwaway users too, not just their secrets.
        for email in TEST_USERS:
            if frappe.db.exists("User", email):
                frappe.db.delete("Vault Share", {"user": email})
                frappe.delete_doc("User", email, force=True, ignore_permissions=True)

        frappe.db.commit()

    # ------------------------------------------------------------------
    # Schedule computation
    # ------------------------------------------------------------------

    def test_next_rotation_in_days(self):
        doc = make_secret(
            title="Rotation Days Secret", enable_rotation=1, rotation_interval=30, rotation_unit="Days"
        )

        self.assertIsNotNone(doc.next_rotation_on)
        delta = get_datetime(doc.next_rotation_on) - now_datetime()
        self.assertAlmostEqual(delta.total_seconds(), 30 * 86400, delta=120)

    def test_next_rotation_in_hours(self):
        doc = make_secret(
            title="Rotation Hours Secret", enable_rotation=1, rotation_interval=6, rotation_unit="Hours"
        )

        delta = get_datetime(doc.next_rotation_on) - now_datetime()
        self.assertAlmostEqual(delta.total_seconds(), 6 * 3600, delta=120)

    def test_enabling_rotation_anchors_from_now_not_from_old_password(self):
        """Ticking the box on an ancient password must not fire an instant rotation."""
        doc = make_secret(title="Rotation Days Secret")
        frappe.db.set_value(
            "Vault Secret", doc.name, "password_last_changed", add_to_date(now_datetime(), days=-500)
        )

        doc = frappe.get_doc("Vault Secret", doc.name)
        doc.enable_rotation = 1
        doc.rotation_interval = 1
        doc.rotation_unit = "Days"
        doc.save(ignore_permissions=True)

        self.assertGreater(get_datetime(doc.next_rotation_on), now_datetime())

    def test_disabling_rotation_clears_schedule(self):
        doc = make_secret(
            title="Rotation Days Secret", enable_rotation=1, rotation_interval=5, rotation_unit="Days"
        )
        self.assertIsNotNone(doc.next_rotation_on)

        doc.enable_rotation = 0
        doc.save(ignore_permissions=True)
        self.assertIsNone(doc.next_rotation_on)

    def test_rotation_rejected_for_non_password_type(self):
        with self.assertRaises(frappe.ValidationError):
            make_secret(
                title="Rotation Nontype Secret",
                secret_type="API Key",
                password=None,
                api_key="abc",
                enable_rotation=1,
                rotation_interval=30,
                rotation_unit="Days",
            )

    def test_rotation_rejects_zero_interval(self):
        with self.assertRaises(frappe.ValidationError):
            make_secret(
                title="Rotation Days Secret", enable_rotation=1, rotation_interval=0, rotation_unit="Days"
            )

    # ------------------------------------------------------------------
    # Due-secret selection
    # ------------------------------------------------------------------

    def test_due_query_selects_only_overdue_enabled_password_secrets(self):
        due = make_secret(
            title="Rotation Due Secret", enable_rotation=1, rotation_interval=1, rotation_unit="Hours"
        )
        frappe.db.set_value(
            "Vault Secret", due.name, "next_rotation_on", add_to_date(now_datetime(), hours=-2)
        )

        future = make_secret(
            title="Rotation Future Secret", enable_rotation=1, rotation_interval=30, rotation_unit="Days"
        )
        disabled = make_secret(title="Rotation Disabled Secret")
        frappe.db.commit()

        selected = frappe.get_all(
            "Vault Secret",
            filters={
                "enable_rotation": 1,
                "secret_type": "Password",
                "next_rotation_on": ["<=", now_datetime()],
                "title": ["in", TEST_TITLES],
            },
            pluck="name",
        )

        self.assertIn(due.name, selected)
        self.assertNotIn(future.name, selected)
        self.assertNotIn(disabled.name, selected)

    # ------------------------------------------------------------------
    # Password generation policy
    # ------------------------------------------------------------------

    def test_generated_password_respects_hard_floor(self):
        settings = frappe.get_cached_doc("Vault Settings")
        length = _rotation_password_length(settings)
        self.assertGreaterEqual(length, MIN_ROTATION_PASSWORD_LENGTH)

        password = _generate_password(settings, length)
        self.assertGreaterEqual(len(password), MIN_ROTATION_PASSWORD_LENGTH)

    def test_hard_floor_survives_a_misconfigured_settings_doc(self):
        """Even if Vault Settings asks for 4 characters, rotation must not go below 12."""
        settings = frappe._dict(min_password_length=4, default_password_length=6)
        self.assertEqual(_rotation_password_length(settings), MIN_ROTATION_PASSWORD_LENGTH)

    def test_generated_password_honours_charset_policy(self):
        settings = frappe._dict(
            min_password_length=16,
            default_password_length=16,
            require_uppercase=1,
            require_lowercase=1,
            require_digits=1,
            require_special=1,
        )
        password = _generate_password(settings, _rotation_password_length(settings))

        self.assertTrue(any(c.isupper() for c in password))
        self.assertTrue(any(c.islower() for c in password))
        self.assertTrue(any(c.isdigit() for c in password))
        self.assertTrue(any(not c.isalnum() for c in password))

    # ------------------------------------------------------------------
    # Password history and reuse
    # ------------------------------------------------------------------

    def test_history_row_is_appended_and_hashed(self):
        doc = make_secret(title="Rotation Reuse Secret")

        self.assertEqual(len(doc.password_history), 1)
        row = doc.password_history[0]
        self.assertTrue(row.password_hash)
        self.assertNotIn("InitialPassword123!", row.password_hash)
        self.assertEqual(row.source, "Manual")

    def test_history_records_auto_rotation_source(self):
        doc = make_secret(title="Rotation Reuse Secret")
        doc.password = "RotatedByJob456!"
        doc.flags.vault_auto_rotation = True
        doc.save(ignore_permissions=True)

        self.assertEqual(doc.password_history[-1].source, "Auto Rotation")

    def test_reusing_a_recent_password_is_rejected(self):
        reuse_count = frappe.db.get_single_value("Vault Settings", "prevent_reuse_count") or 3
        if reuse_count < 1:
            self.skipTest("Password reuse prevention is disabled in Vault Settings")

        doc = make_secret(title="Rotation Reuse Secret")

        doc.password = "SecondPassword456!"
        doc.save(ignore_permissions=True)

        doc.password = "InitialPassword123!"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_saving_without_touching_password_does_not_add_history(self):
        """A reloaded doc holds a '*' mask, which must never be hashed as a password."""
        doc = make_secret(title="Rotation Reuse Secret")

        doc = frappe.get_doc("Vault Secret", doc.name)
        doc.url = "https://changed.example.com"
        doc.save(ignore_permissions=True)

        self.assertEqual(len(doc.password_history), 1)

    def test_history_is_trimmed(self):
        doc = make_secret(title="Rotation Reuse Secret")
        for i in range(14):
            doc.password = f"UniqueRotation{i}Password!"
            doc.save(ignore_permissions=True)

        self.assertLessEqual(len(doc.password_history), 15)

    # ------------------------------------------------------------------
    # Recipient resolution
    # ------------------------------------------------------------------

    def test_access_resolution_covers_owner_and_shares(self):
        owner, shared, revoked = (self.ensure_user(u) for u in TEST_USERS)

        doc = make_secret(title="Rotation Access Secret")
        frappe.db.set_value("Vault Secret", doc.name, "owner", owner)

        self.make_share(doc.name, shared, is_revoked=0)
        self.make_share(doc.name, revoked, is_revoked=1)
        frappe.db.commit()

        users = get_users_with_secret_access(doc.name)

        self.assertIn(owner, users)
        self.assertIn(shared, users)
        self.assertNotIn(revoked, users)
        self.assertNotIn("Guest", users)

    def test_expired_share_is_excluded(self):
        shared = self.ensure_user(TEST_USERS[1])
        doc = make_secret(title="Rotation Access Secret")

        self.make_share(doc.name, shared, is_revoked=0, expires_on=add_to_date(now_datetime(), days=-1))
        frappe.db.commit()

        self.assertNotIn(shared, get_users_with_secret_access(doc.name))

    def test_disabled_user_is_excluded(self):
        shared = self.ensure_user(TEST_USERS[1])
        doc = make_secret(title="Rotation Access Secret")
        self.make_share(doc.name, shared, is_revoked=0)

        frappe.db.set_value("User", shared, "enabled", 0)
        frappe.db.commit()
        try:
            self.assertNotIn(shared, get_users_with_secret_access(doc.name))
        finally:
            frappe.db.set_value("User", shared, "enabled", 1)
            frappe.db.commit()

    def test_unknown_secret_resolves_to_no_recipients(self):
        self.assertEqual(get_users_with_secret_access("VS-does-not-exist"), [])

    def ensure_user(self, email):
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": email.split("@")[0],
                    "send_welcome_email": 0,
                    "roles": [{"role": "Vault User"}],
                }
            ).insert(ignore_permissions=True)
        return email

    def make_share(self, secret_name, user, is_revoked=0, expires_on=None):
        frappe.get_doc(
            {
                "doctype": "Vault Share",
                "share_type": "User",
                "user": user,
                "permission_level": "View & Copy",
                "shared_doctype": "Vault Secret",
                "shared_name": secret_name,
                "is_revoked": is_revoked,
                "expires_on": expires_on,
            }
        ).insert(ignore_permissions=True)

    # ------------------------------------------------------------------
    # Encrypted archive
    # ------------------------------------------------------------------

    def test_encrypted_zip_roundtrip(self):
        import pyzipper

        data = create_encrypted_zip({"secret.txt": "the-new-password"}, "correct-horse-battery")

        with pyzipper.AESZipFile(__import__("io").BytesIO(data)) as archive:
            archive.setpassword(b"correct-horse-battery")
            self.assertEqual(archive.read("secret.txt"), b"the-new-password")

    def test_encrypted_zip_rejects_wrong_passphrase(self):
        import io

        import pyzipper

        data = create_encrypted_zip({"secret.txt": "the-new-password"}, "correct-horse-battery")

        with self.assertRaises(RuntimeError):
            with pyzipper.AESZipFile(io.BytesIO(data)) as archive:
                archive.setpassword(b"wrong-passphrase-xx")
                archive.read("secret.txt")

    def test_encrypted_zip_content_is_not_plaintext(self):
        data = create_encrypted_zip({"secret.txt": "SuperSecretValue123"}, "correct-horse-battery")
        self.assertNotIn(b"SuperSecretValue123", data)

    def test_encrypted_zip_requires_password_and_files(self):
        with self.assertRaises(ValueError):
            create_encrypted_zip({"a.txt": "x"}, "")
        with self.assertRaises(ValueError):
            create_encrypted_zip({}, "correct-horse-battery")

    def test_slugify_produces_safe_member_names(self):
        self.assertEqual(_slugify("Prod DB / Admin!"), "prod-db-admin")
        self.assertEqual(_slugify(""), "secret")
        self.assertLessEqual(len(_slugify("x" * 200)), 60)
