import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.services.secret_service import create_secret, delete_secret
from frappe_vault.services.sharing_service import consume_one_time_link, create_one_time_link


class TestOneTimeLink(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Vault Secret", {"title": "Test One-Time Link Secret"})
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Vault Secret", {"title": "Test One-Time Link Secret"})
        frappe.db.commit()

    def test_create_and_consume_link(self):
        secret = create_secret(
            {"title": "Test One-Time Link Secret", "secret_type": "Password", "password": "LinkPassword123!"}
        )

        # Create one-time link without passphrase
        link_doc = create_one_time_link(secret_name=secret.get("name"), max_views=1)
        self.assertTrue(link_doc.get("token"))
        self.assertTrue(link_doc.get("name"))

        # Consume the link
        consumed = consume_one_time_link(token=link_doc.get("token"))
        self.assertEqual(consumed.get("title"), "Test One-Time Link Secret")
        self.assertEqual(consumed.get("decrypted", {}).get("password"), "LinkPassword123!")

        # Attempt to consume again (should raise expired/consumed error)
        self.assertRaises(frappe.ValidationError, consume_one_time_link, token=link_doc.get("token"))

        delete_secret(secret.get("name"))

    def test_passphrase_protected_link(self):
        secret = create_secret(
            {"title": "Test One-Time Link Secret", "secret_type": "Note", "notes": "Secret Notes Content"}
        )

        # Create link with passphrase
        link_doc = create_one_time_link(
            secret_name=secret.get("name"), passphrase="VaultPassphrase123!", max_views=1
        )

        # Consume with wrong passphrase (should fail)
        self.assertRaises(
            frappe.ValidationError,
            consume_one_time_link,
            token=link_doc.get("token"),
            passphrase="WrongPassphrase",
        )

        # Consume with correct passphrase
        consumed = consume_one_time_link(token=link_doc.get("token"), passphrase="VaultPassphrase123!")
        self.assertEqual(consumed.get("title"), "Test One-Time Link Secret")

        delete_secret(secret.get("name"))

    def test_passphrase_link_with_missing_passphrase_is_refused(self):
        secret = create_secret(
            {"title": "Test One-Time Link Secret", "secret_type": "Password", "password": "LinkPassword123!"}
        )
        link_doc = create_one_time_link(secret_name=secret.get("name"), passphrase="Pass-123!", max_views=2)

        self.assertRaises(frappe.ValidationError, consume_one_time_link, token=link_doc.get("token"))

        delete_secret(secret.get("name"))

    def test_undecryptable_passphrase_fails_closed(self):
        # If the stored passphrase can no longer be decrypted (rotated site
        # encryption key, corrupted row), the link must refuse to open — never
        # fall back to treating it as a link without a passphrase.
        secret = create_secret(
            {"title": "Test One-Time Link Secret", "secret_type": "Password", "password": "LinkPassword123!"}
        )
        link_doc = create_one_time_link(secret_name=secret.get("name"), passphrase="Pass-123!", max_views=2)

        auth = frappe.qb.Table("__Auth")
        (
            frappe.qb.update(auth)
            .set(auth.password, "not-a-decryptable-value")
            .where(
                (auth.doctype == "Vault One Time Link")
                & (auth.name == link_doc.get("name"))
                & (auth.fieldname == "passphrase")
            )
        ).run()

        for attempt in (None, "Pass-123!"):
            self.assertRaises(
                frappe.ValidationError,
                consume_one_time_link,
                token=link_doc.get("token"),
                passphrase=attempt,
            )

        delete_secret(secret.get("name"))
