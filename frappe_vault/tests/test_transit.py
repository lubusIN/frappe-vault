"""Vault secrets are Transit-encrypted by HashiCorp before Frappe stores them.

HashiCorp is not available in CI, so the single HTTP call (`transit._call`) is
replaced by an in-memory fake with the same contract. What is checked is
Vault's side of the bargain: that only Transit ciphertext ever reaches
storage, that every legitimate read path still gets the real value back,
and that nothing is stored when HashiCorp cannot be reached.
"""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.password import get_decrypted_password

from frappe_vault.integrations import transit
from frappe_vault.utils.encryption import get_decrypted_secret_data

TITLES = ("Transit Secret", "Transit Legacy Secret", "Transit Down Secret")


class FakeTransit:
    """Stands in for HashiCorp's transit/encrypt and transit/decrypt endpoints."""

    def __init__(self):
        self.down = False
        self.calls = {"encrypt": 0, "decrypt": 0}

    def __call__(self, operation, payload):
        if self.down:
            raise transit.TransitError("HashiCorp Vault is unreachable: ConnectionError")
        self.calls[operation] += 1
        if operation == "encrypt":
            return {
                "ciphertext": "vault:v1:"
                + base64.b64encode(b"fake:" + payload["plaintext"].encode()).decode()
            }
        raw = base64.b64decode(payload["ciphertext"].split(":", 2)[2])
        assert raw.startswith(b"fake:"), "not a ciphertext this fake produced"
        return {"plaintext": raw[len(b"fake:") :].decode()}


class TestTransitProtection(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()
        self.fake = FakeTransit()
        self._real_call = transit._call
        transit._call = self.fake
        frappe.local.conf["vault_transit_key"] = "test-key"

    def tearDown(self):
        transit._call = self._real_call
        frappe.local.conf.pop("vault_transit_key", None)
        frappe.set_user("Administrator")
        self._cleanup()

    def _cleanup(self):
        for name in frappe.get_all("Vault Secret", filters={"title": ["in", TITLES]}, pluck="name"):
            for link in frappe.get_all("Vault One Time Link", filters={"secret": name}, pluck="name"):
                frappe.delete_doc("Vault One Time Link", link, force=True, ignore_permissions=True)
            frappe.db.delete("Vault Audit Log", {"secret": name})
            frappe.delete_doc("Vault Secret", name, force=True, ignore_permissions=True)

    def make_secret(self, title="Transit Secret", **kwargs):
        return frappe.get_doc(
            {
                "doctype": "Vault Secret",
                "title": title,
                "secret_type": "Password",
                "password": "Transit-Pass-123!",
                **kwargs,
            }
        ).insert(ignore_permissions=True)

    # ------------------------------------------------------------------

    def test_storage_holds_only_transit_ciphertext(self):
        doc = self.make_secret()
        # Exactly what a database dump plus site_config.json can recover:
        stored = get_decrypted_password("Vault Secret", doc.name, "password")
        self.assertTrue(transit.is_ciphertext(stored))
        self.assertNotIn("Transit-Pass-123!", stored)
        self.assertEqual(transit.verify_protection()["plaintext"], 0)

    def test_the_app_still_reveals_the_real_value(self):
        doc = self.make_secret()
        self.assertEqual(get_decrypted_secret_data(doc.name)["password"], "Transit-Pass-123!")
        self.assertEqual(
            frappe.get_doc("Vault Secret", doc.name).get_password("password"), "Transit-Pass-123!"
        )
        self.assertGreater(self.fake.calls["decrypt"], 0)

    def test_every_password_field_is_wrapped(self):
        doc = self.make_secret(zip_passphrase="Zip-Passphrase-Long-123!")
        for field in ("password", "zip_passphrase"):
            with self.subTest(field=field):
                self.assertTrue(
                    transit.is_ciphertext(get_decrypted_password("Vault Secret", doc.name, field))
                )

    def test_rotation_stores_ciphertext_and_reads_back(self):
        from frappe_vault.background_jobs.password_rotation import rotate_secret

        frappe.db.set_single_value("Vault Settings", "send_rotation_emails", 0)
        doc = self.make_secret()
        rotate_secret(doc.name)

        stored = get_decrypted_password("Vault Secret", doc.name, "password")
        self.assertTrue(transit.is_ciphertext(stored))
        current = frappe.get_doc("Vault Secret", doc.name).get_password("password")
        self.assertNotEqual(current, "Transit-Pass-123!")
        self.assertFalse(transit.is_ciphertext(current))

    def test_resaving_without_changing_the_password_is_not_a_change(self):
        doc = self.make_secret()
        doc = frappe.get_doc("Vault Secret", doc.name)
        doc.password = "Transit-Pass-123!"  # the edit form sends the value back verbatim
        self.assertFalse(doc.has_plaintext_password())

    def test_a_legacy_value_stays_readable_and_is_rewrapped(self):
        frappe.local.conf.pop("vault_transit_key", None)
        doc = self.make_secret(title="Transit Legacy Secret")
        self.assertEqual(get_decrypted_password("Vault Secret", doc.name, "password"), "Transit-Pass-123!")

        frappe.local.conf["vault_transit_key"] = "test-key"
        self.assertEqual(get_decrypted_secret_data(doc.name)["password"], "Transit-Pass-123!")
        self.assertGreaterEqual(transit.verify_protection()["plaintext"], 1)

        self.assertGreaterEqual(transit.rewrap_existing(dry_run=True)["would_rewrap"], 1)
        transit.rewrap_existing(dry_run=False)

        self.assertTrue(transit.is_ciphertext(get_decrypted_password("Vault Secret", doc.name, "password")))
        self.assertEqual(get_decrypted_secret_data(doc.name)["password"], "Transit-Pass-123!")

    def test_nothing_is_stored_when_hashicorp_is_down(self):
        self.fake.down = True
        self.assertRaises(transit.TransitError, self.make_secret, title="Transit Down Secret")
        self.assertFalse(frappe.db.exists("Vault Secret", {"title": "Transit Down Secret"}))

    def test_an_unreachable_hashicorp_is_reported_not_shown_as_blank(self):
        doc = self.make_secret()
        self.fake.down = True
        self.assertRaises(transit.TransitError, get_decrypted_secret_data, doc.name)

    def test_one_time_link_passphrases_are_wrapped(self):
        from frappe_vault.services.sharing_service import consume_one_time_link, create_one_time_link

        doc = self.make_secret()
        link = create_one_time_link(doc.name, max_views=2, passphrase="Link-Pass-123!")
        stored = get_decrypted_password("Vault One Time Link", link["name"], "passphrase")
        self.assertTrue(transit.is_ciphertext(stored))

        opened = consume_one_time_link(link["token"], passphrase="Link-Pass-123!")
        self.assertEqual(opened["decrypted"]["password"], "Transit-Pass-123!")
        self.assertRaises(frappe.ValidationError, consume_one_time_link, link["token"], passphrase="wrong")

    def test_without_transit_nothing_changes(self):
        frappe.local.conf.pop("vault_transit_key", None)
        doc = self.make_secret()
        self.assertEqual(get_decrypted_password("Vault Secret", doc.name, "password"), "Transit-Pass-123!")
        self.assertEqual(self.fake.calls, {"encrypt": 0, "decrypt": 0})
