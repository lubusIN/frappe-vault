"""Rotation of Database secrets, and the target-apply configuration around it.

Nothing here contacts a real database server — the engine handlers are exercised
against live servers only in manual testing. What is covered is everything that
decides *whether* and *how* a connection would be made: which field rotates,
which configurations are allowed to be saved at all, and how a Vault Secret
resolves into a connection target.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from frappe_vault.services.db_rotation_service import (
    DEFAULT_PORTS,
    MONGODB,
    MYSQL,
    POSTGRESQL,
    TargetApplyError,
    build_target,
    describe,
    make_target,
)
from frappe_vault.vault.doctype.vault_secret.vault_secret import ROTATABLE_FIELD_BY_TYPE

TEST_TITLES = [
    "DB Rotation Postgres Secret",
    "DB Rotation MySQL Secret",
    "DB Rotation Mongo Secret",
    "DB Rotation Admin Secret",
    "DB Rotation Due Secret",
    "DB Rotation Invalid Secret",
    "DB Rotation History Secret",
]


def make_db_secret(**kwargs):
    """Create a Database Vault Secret with sane defaults for these tests."""
    doc = frappe.get_doc(
        {
            "doctype": "Vault Secret",
            "secret_type": "Database",
            "database_type": POSTGRESQL,
            "db_host": "db.internal.example",
            "db_name": "appdb",
            "username": "app_user",
            "db_password": "InitialDbPassword123!",
            **kwargs,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


class TestDatabaseRotation(FrappeTestCase):
    def setUp(self):
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        # This site's tests run against the live DB, so fixtures must not
        # survive the run.
        names = frappe.get_all("Vault Secret", filters={"title": ["in", TEST_TITLES]}, pluck="name")
        for name in names:
            frappe.db.delete("Vault Share", {"shared_name": name})
            frappe.db.delete("Vault Audit Log", {"secret": name})
            frappe.delete_doc("Vault Secret", name, force=True, ignore_permissions=True)

        # One test commits so the due-secret query can see its fixture. The test
        # case rolls back afterwards, which would take this delete with it — so
        # commit the cleanup too, or that fixture outlives the run.
        frappe.db.commit()  # nosemgrep — test fixtures must not survive on this site

    # ------------------------------------------------------------------
    # Which field rotates
    # ------------------------------------------------------------------

    def test_database_secret_rotates_its_db_password(self):
        doc = make_db_secret(title="DB Rotation Postgres Secret")
        self.assertEqual(doc.rotating_field, "db_password")

    def test_password_secret_still_rotates_its_password(self):
        self.assertEqual(ROTATABLE_FIELD_BY_TYPE["Password"], "password")

    def test_unrotatable_type_has_no_rotating_field(self):
        doc = frappe.get_doc({"doctype": "Vault Secret", "title": "x", "secret_type": "API Key"})
        self.assertIsNone(doc.rotating_field)

    # ------------------------------------------------------------------
    # Rotation schedule
    # ------------------------------------------------------------------

    def test_database_secret_may_enable_rotation(self):
        doc = make_db_secret(
            title="DB Rotation Postgres Secret",
            enable_rotation=1,
            rotation_interval=30,
            rotation_unit="Days",
            rotation_admin_username="postgres",
            rotation_admin_password="AdminPassword123!",
        )
        self.assertIsNotNone(doc.next_rotation_on)

    def test_enabling_rotation_forces_the_change_to_reach_the_server(self):
        # Sync is not optional: a rotation that only changed the stored value
        # would leave the vault holding a password the server never received.
        doc = make_db_secret(
            title="DB Rotation Postgres Secret",
            enable_rotation=1,
            rotation_interval=30,
            rotation_unit="Days",
            apply_rotation_to_target=0,
            rotation_admin_username="postgres",
            rotation_admin_password="AdminPassword123!",
        )
        self.assertTrue(doc.apply_rotation_to_target)

    def test_due_query_includes_database_secrets(self):
        due = make_db_secret(
            title="DB Rotation Due Secret",
            enable_rotation=1,
            rotation_interval=1,
            rotation_unit="Hours",
            rotation_admin_username="postgres",
            rotation_admin_password="AdminPassword123!",
        )
        frappe.db.set_value(
            "Vault Secret", due.name, "next_rotation_on", add_to_date(now_datetime(), hours=-2)
        )
        frappe.db.commit()

        selected = frappe.get_all(
            "Vault Secret",
            filters={
                "enable_rotation": 1,
                "secret_type": ["in", sorted(ROTATABLE_FIELD_BY_TYPE)],
                "next_rotation_on": ["<=", now_datetime()],
                "title": ["in", TEST_TITLES],
            },
            pluck="name",
        )
        self.assertIn(due.name, selected)

    # ------------------------------------------------------------------
    # History and the reuse policy follow the rotating field
    # ------------------------------------------------------------------

    def test_history_is_recorded_for_db_password(self):
        doc = make_db_secret(title="DB Rotation History Secret")
        self.assertEqual(len(doc.password_history), 1)
        self.assertTrue(doc.password_history[0].password_hash)

    def test_is_password_reused_matches_a_previous_db_password(self):
        doc = make_db_secret(title="DB Rotation History Secret")
        self.assertTrue(doc.is_password_reused("InitialDbPassword123!", reuse_count=5))
        self.assertFalse(doc.is_password_reused("SomethingCompletelyElse456!", reuse_count=5))

    def test_reuse_check_is_off_when_the_policy_allows_zero(self):
        doc = make_db_secret(title="DB Rotation History Secret")
        self.assertFalse(doc.is_password_reused("InitialDbPassword123!", reuse_count=0))

    # ------------------------------------------------------------------
    # Target-apply configuration
    # ------------------------------------------------------------------

    def test_apply_to_target_requires_a_database_type(self):
        with self.assertRaises(frappe.ValidationError):
            make_db_secret(
                title="DB Rotation Invalid Secret",
                database_type=None,
                enable_rotation=1,
                rotation_interval=30,
                rotation_unit="Days",
                apply_rotation_to_target=1,
                rotation_admin_username="postgres",
                rotation_admin_password="AdminPassword123!",
            )

    def test_apply_to_target_requires_a_username(self):
        with self.assertRaises(frappe.ValidationError):
            make_db_secret(
                title="DB Rotation Invalid Secret",
                username=None,
                enable_rotation=1,
                rotation_interval=30,
                rotation_unit="Days",
                apply_rotation_to_target=1,
                rotation_admin_username="postgres",
                rotation_admin_password="AdminPassword123!",
            )

    def test_apply_to_target_requires_an_admin_username(self):
        # Self-service is no longer an option once a rotation reaches a live
        # server: an account that cannot change its own password would fail
        # unattended, hours after the setup that caused it.
        with self.assertRaises(frappe.ValidationError):
            make_db_secret(
                title="DB Rotation Invalid Secret",
                enable_rotation=1,
                rotation_interval=30,
                rotation_unit="Days",
                apply_rotation_to_target=1,
            )

    def test_apply_to_target_requires_an_admin_password_alongside_an_admin_user(self):
        with self.assertRaises(frappe.ValidationError):
            make_db_secret(
                title="DB Rotation Invalid Secret",
                enable_rotation=1,
                rotation_interval=30,
                rotation_unit="Days",
                apply_rotation_to_target=1,
                rotation_admin_username="postgres",
            )

    def test_apply_to_target_is_cleared_when_rotation_is_disabled(self):
        doc = make_db_secret(
            title="DB Rotation Postgres Secret",
            enable_rotation=1,
            rotation_interval=30,
            rotation_unit="Days",
            apply_rotation_to_target=1,
            rotation_admin_username="postgres",
            rotation_admin_password="AdminPassword123!",
        )
        doc.enable_rotation = 0
        doc.save(ignore_permissions=True)
        self.assertFalse(doc.apply_rotation_to_target)

    def test_dropping_the_admin_username_drops_its_password(self):
        doc = make_db_secret(
            title="DB Rotation Admin Secret",
            enable_rotation=1,
            rotation_interval=30,
            rotation_unit="Days",
            apply_rotation_to_target=1,
            rotation_admin_username="postgres",
            rotation_admin_password="AdminPassword123!",
        )
        self.assertTrue(doc.get_password("rotation_admin_password", raise_exception=False))

        # Removing the admin means giving up rotation for this secret. Rotation
        # implies reaching the server, and reaching the server needs the admin,
        # so the three can no longer be separated.
        doc.enable_rotation = 0
        doc.apply_rotation_to_target = 0
        doc.rotation_admin_username = ""
        doc.save(ignore_permissions=True)

        self.assertFalse(doc.rotation_admin_username)
        self.assertFalse(doc.get_password("rotation_admin_password", raise_exception=False))

    def test_admin_cannot_be_dropped_while_still_applying_to_the_server(self):
        doc = make_db_secret(
            title="DB Rotation Admin Secret",
            enable_rotation=1,
            rotation_interval=30,
            rotation_unit="Days",
            apply_rotation_to_target=1,
            rotation_admin_username="postgres",
            rotation_admin_password="AdminPassword123!",
        )

        doc.rotation_admin_username = ""
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    # ------------------------------------------------------------------
    # Resolving a secret into a connection target
    # ------------------------------------------------------------------

    def test_target_defaults_the_port_per_engine(self):
        for engine in (POSTGRESQL, MYSQL, MONGODB):
            doc = make_db_secret(title="DB Rotation Postgres Secret", database_type=engine, db_port=None)
            target = build_target(doc, "InitialDbPassword123!")
            self.assertEqual(target.port, DEFAULT_PORTS[engine])
            self.cleanup()

    def test_target_keeps_an_explicit_port(self):
        doc = make_db_secret(title="DB Rotation Postgres Secret", db_port=6543)
        target = build_target(doc, "InitialDbPassword123!")
        self.assertEqual(target.port, 6543)

    def test_target_authenticates_as_the_account_itself_by_default(self):
        doc = make_db_secret(title="DB Rotation Postgres Secret")
        target = build_target(doc, "InitialDbPassword123!")

        self.assertFalse(target.via_admin)
        self.assertEqual(target.auth_username, "app_user")
        self.assertEqual(target.auth_password, "InitialDbPassword123!")

    def test_target_prefers_the_rotation_admin_when_one_is_set(self):
        doc = make_db_secret(
            title="DB Rotation Admin Secret",
            enable_rotation=1,
            rotation_interval=30,
            rotation_unit="Days",
            apply_rotation_to_target=1,
            rotation_admin_username="postgres",
            rotation_admin_password="AdminPassword123!",
        )
        target = build_target(doc, "InitialDbPassword123!")

        self.assertTrue(target.via_admin)
        self.assertEqual(target.auth_username, "postgres")
        self.assertEqual(target.auth_password, "AdminPassword123!")
        # The account being *changed* is still the secret's own user.
        self.assertEqual(target.username, "app_user")

    def test_target_defaults_the_mongo_auth_source(self):
        doc = make_db_secret(title="DB Rotation Mongo Secret", database_type=MONGODB, db_auth_source=None)
        target = build_target(doc, "InitialDbPassword123!")
        self.assertEqual(target.auth_source, "admin")

    def test_target_rejects_an_unsupported_engine(self):
        doc = make_db_secret(title="DB Rotation Invalid Secret")
        doc.database_type = "Cassandra"

        with self.assertRaises(TargetApplyError):
            build_target(doc, "InitialDbPassword123!")

    def test_target_rejects_a_non_database_secret(self):
        doc = frappe.get_doc(
            {"doctype": "Vault Secret", "title": "x", "secret_type": "Password", "password": "y"}
        )
        with self.assertRaises(TargetApplyError):
            build_target(doc, "y")

    def test_target_without_any_usable_credential_is_refused(self):
        doc = make_db_secret(title="DB Rotation Invalid Secret")

        # No admin configured and no current password to authenticate with.
        with self.assertRaises(TargetApplyError):
            build_target(doc, "")

    def test_describe_names_the_server_without_leaking_a_password(self):
        doc = make_db_secret(title="DB Rotation MySQL Secret", database_type=MYSQL, db_port=3306)
        description = describe(build_target(doc, "InitialDbPassword123!"))

        self.assertIn("db.internal.example:3306", description)
        self.assertIn("app_user", description)
        self.assertNotIn("InitialDbPassword123!", description)

    # ------------------------------------------------------------------
    # Building a target from unsaved form values
    # ------------------------------------------------------------------

    def test_make_target_builds_from_plain_values(self):
        target = make_target(
            database_type=POSTGRESQL,
            host="  db.example  ",
            username="  app_user  ",
            admin_username="postgres",
            admin_password="AdminPassword123!",
        )

        self.assertEqual(target.host, "db.example")
        self.assertEqual(target.username, "app_user")
        self.assertEqual(target.port, DEFAULT_PORTS[POSTGRESQL])
        self.assertTrue(target.via_admin)
        self.assertEqual(target.auth_username, "postgres")

    def test_make_target_falls_back_to_self_service(self):
        target = make_target(
            database_type=MYSQL,
            host="db.example",
            username="app_user",
            current_password="CurrentPassword123!",
        )

        self.assertFalse(target.via_admin)
        self.assertEqual(target.auth_username, "app_user")
        self.assertEqual(target.auth_password, "CurrentPassword123!")

    def test_make_target_rejects_an_admin_without_a_password(self):
        with self.assertRaises(TargetApplyError):
            make_target(
                database_type=POSTGRESQL,
                host="db.example",
                username="app_user",
                admin_username="postgres",
                admin_password="",
            )

    def test_make_target_rejects_a_missing_host(self):
        with self.assertRaises(TargetApplyError):
            make_target(
                database_type=POSTGRESQL,
                host="   ",
                username="app_user",
                admin_username="postgres",
                admin_password="AdminPassword123!",
            )

    def test_make_target_rejects_an_unsupported_engine(self):
        with self.assertRaises(TargetApplyError):
            make_target(
                database_type="Cassandra",
                host="db.example",
                username="app_user",
                admin_username="postgres",
                admin_password="AdminPassword123!",
            )

    def test_make_target_rejects_no_credential_at_all(self):
        with self.assertRaises(TargetApplyError):
            make_target(database_type=POSTGRESQL, host="db.example", username="app_user")

    def test_every_engine_has_an_existence_probe(self):
        from frappe_vault.services.db_rotation_service import (
            _EXISTENCE_PROBES,
            SUPPORTED_DATABASE_TYPES,
        )

        self.assertEqual(set(_EXISTENCE_PROBES), set(SUPPORTED_DATABASE_TYPES))


class TestRotationWithoutEmail(FrappeTestCase):
    """Rotation must not depend on email being configured or enabled.

    Emailing a rotated password used to be a precondition: a missing passphrase
    or outgoing mail account aborted the whole run and left every due credential
    unrotated. Changing the credential is the job; telling people is a separate,
    best-effort step.
    """

    def setUp(self):
        self.cleanup()
        self.original = frappe.db.get_single_value("Vault Settings", "send_rotation_emails")

    def tearDown(self):
        frappe.db.set_single_value("Vault Settings", "send_rotation_emails", self.original)
        self.cleanup()

    def cleanup(self):
        names = frappe.get_all("Vault Secret", filters={"title": ["in", TEST_TITLES]}, pluck="name")
        for name in names:
            frappe.db.delete("Vault Audit Log", {"secret": name})
            frappe.delete_doc("Vault Secret", name, force=True, ignore_permissions=True)
        frappe.db.commit()  # nosemgrep — fixtures must not survive on this site

    def test_delivery_is_skipped_when_emailing_is_disabled(self):
        from frappe_vault.background_jobs.password_rotation import _resolve_delivery

        frappe.db.set_single_value("Vault Settings", "send_rotation_emails", 0)
        doc = make_db_secret(title="DB Rotation Postgres Secret")

        self.assertIsNone(_resolve_delivery(doc))

    def test_a_broken_mail_setup_downgrades_instead_of_aborting(self):
        from frappe_vault.background_jobs import password_rotation

        frappe.db.set_single_value("Vault Settings", "send_rotation_emails", 1)
        doc = make_db_secret(title="DB Rotation Postgres Secret")

        original = password_rotation._check_delivery_prereqs
        password_rotation._check_delivery_prereqs = lambda: frappe.throw("no mail account")
        try:
            # None means "skip the email", not an exception that stops the rotation.
            self.assertIsNone(password_rotation._resolve_delivery(doc))
        finally:
            password_rotation._check_delivery_prereqs = original

    def test_rotation_still_changes_the_stored_password_with_email_off(self):
        from frappe_vault.background_jobs.password_rotation import rotate_secret

        frappe.db.set_single_value("Vault Settings", "send_rotation_emails", 0)
        doc = make_db_secret(title="DB Rotation Postgres Secret")
        before = doc.get_password("db_password", raise_exception=False)

        result = rotate_secret(doc.name)

        after = frappe.get_doc("Vault Secret", doc.name).get_password("db_password", raise_exception=False)
        self.assertNotEqual(before, after)
        self.assertTrue(after)
        self.assertFalse(result["emailed"])


class TestResavingAnUnchangedPassword(FrappeTestCase):
    """Saving a secret without touching its password must not look like a change.

    The edit form is populated with the decrypted value, so editing any other
    field sends the password back verbatim. Against the masked value held in the
    row that reads as a brand new password — and since a secret's current
    password is by definition its most recent history entry, the reuse policy
    then rejects the save for reusing the password it already has. Which made
    Database secrets uneditable.
    """

    def setUp(self):
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        for title in TEST_TITLES + ["Resave Password Secret"]:
            for name in frappe.get_all("Vault Secret", filters={"title": title}, pluck="name"):
                frappe.db.delete("Vault Audit Log", {"secret": name})
                frappe.delete_doc("Vault Secret", name, force=True, ignore_permissions=True)
        frappe.db.commit()  # nosemgrep — fixtures must not survive on this site

    def test_resubmitting_the_same_db_password_is_not_a_change(self):
        doc = make_db_secret(title="DB Rotation Postgres Secret")
        rows_before = len(doc.password_history)

        doc = frappe.get_doc("Vault Secret", doc.name)
        doc.db_name = "a_different_database"
        doc.db_password = "InitialDbPassword123!"  # unchanged, as the edit form sends it
        doc.save(ignore_permissions=True)

        self.assertEqual(doc.db_name, "a_different_database")
        self.assertEqual(len(doc.password_history), rows_before)

    def test_resubmitting_the_same_password_is_not_a_change(self):
        # The same bug applied to Password secrets before db_password shared
        # this code path, so cover both.
        doc = frappe.get_doc(
            {
                "doctype": "Vault Secret",
                "title": "Resave Password Secret",
                "secret_type": "Password",
                "password": "InitialPassword123!",
            }
        )
        doc.insert(ignore_permissions=True)
        rows_before = len(doc.password_history)

        doc = frappe.get_doc("Vault Secret", doc.name)
        doc.url = "https://example.test"
        doc.password = "InitialPassword123!"
        doc.save(ignore_permissions=True)

        self.assertEqual(len(doc.password_history), rows_before)

    def test_a_genuinely_new_password_is_still_recorded(self):
        doc = make_db_secret(title="DB Rotation Postgres Secret")
        rows_before = len(doc.password_history)

        doc = frappe.get_doc("Vault Secret", doc.name)
        doc.db_password = "AnEntirelyDifferentValue789!"
        doc.save(ignore_permissions=True)

        self.assertEqual(len(doc.password_history), rows_before + 1)

    def test_going_back_to_a_previous_password_is_still_rejected(self):
        # The fix must not disarm the reuse policy it was tripping over.
        original = "InitialDbPassword123!"
        doc = make_db_secret(title="DB Rotation Postgres Secret")

        doc = frappe.get_doc("Vault Secret", doc.name)
        doc.db_password = "AnEntirelyDifferentValue789!"
        doc.save(ignore_permissions=True)

        doc = frappe.get_doc("Vault Secret", doc.name)
        doc.db_password = original
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
