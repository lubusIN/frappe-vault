"""Who may read a secret's stored values.

Viewing a secret's *values* is deliberately stricter than viewing the record:
the Vault Admin / System Manager / Administrator bypass that grants every other
permission in this app does not extend to plaintext. Only the people actually
granted the secret qualify — its owner, its folder's owner, and holders of an
active share.

Scope, so these tests are not read as promising more than they check: this is an
application-level control. Values are encrypted with the site-wide key, so
anyone with shell or database access can still decrypt them without going
through any of this. What is asserted here is that the *app* refuses.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.utils.encryption import get_decrypted_secret_data
from frappe_vault.utils.permissions import (
    can_reveal_secret_value,
    get_secret_access_grants,
    get_users_with_secret_access,
)

TEST_TITLES = ["Value Access Owned Secret", "Value Access Shared Secret"]

OWNER = "value-access-owner@example.com"
GRANTED = "value-access-granted@example.com"
OUTSIDER = "value-access-outsider@example.com"
ADMIN_USER = "value-access-admin@example.com"

TEST_USERS = [OWNER, GRANTED, OUTSIDER, ADMIN_USER]

SECRET_VALUE = "TopSecretValue123!"


def ensure_user(email, roles=()):
    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": email.split("@")[0],
                "send_welcome_email": 0,
            }
        )
        user.insert(ignore_permissions=True)
    else:
        user = frappe.get_doc("User", email)

    for role in roles:
        if not any(r.role == role for r in user.get("roles") or []):
            user.append("roles", {"role": role})
    if roles:
        user.save(ignore_permissions=True)
    return user


class TestSecretValueAccess(FrappeTestCase):
    def setUp(self):
        self.cleanup()
        frappe.set_user("Administrator")

        ensure_user(OWNER, roles=["Vault User"])
        ensure_user(GRANTED, roles=["Vault User"])
        ensure_user(OUTSIDER, roles=["Vault User"])
        ensure_user(ADMIN_USER, roles=["Vault Admin", "System Manager"])

        self.secret = frappe.get_doc(
            {
                "doctype": "Vault Secret",
                "title": "Value Access Owned Secret",
                "secret_type": "Password",
                "password": SECRET_VALUE,
                "owner": OWNER,
            }
        )
        self.secret.insert(ignore_permissions=True)
        # `owner` is set by the framework on insert; force it to the fixture.
        frappe.db.set_value("Vault Secret", self.secret.name, "owner", OWNER, update_modified=False)

    def tearDown(self):
        frappe.set_user("Administrator")
        self.cleanup()

    def cleanup(self):
        frappe.set_user("Administrator")
        names = frappe.get_all("Vault Secret", filters={"title": ["in", TEST_TITLES]}, pluck="name")
        for name in names:
            frappe.db.delete("Vault Share", {"shared_name": name})
            frappe.db.delete("Vault Audit Log", {"secret": name})
            frappe.delete_doc("Vault Secret", name, force=True, ignore_permissions=True)

        # This site's tests run against the live DB — fixtures must not survive.
        for email in TEST_USERS:
            if frappe.db.exists("User", email):
                frappe.db.delete("Vault Share", {"user": email})
                frappe.delete_doc("User", email, force=True, ignore_permissions=True)

        frappe.db.commit()  # nosemgrep — cleanup must outlive the test rollback

    def share_with(self, user, permission_level="View Only"):
        share = frappe.get_doc(
            {
                "doctype": "Vault Share",
                "shared_doctype": "Vault Secret",
                "shared_name": self.secret.name,
                "share_type": "User",
                "user": user,
                "permission_level": permission_level,
            }
        )
        share.insert(ignore_permissions=True)
        return share

    # ------------------------------------------------------------------
    # Who qualifies
    # ------------------------------------------------------------------

    def test_owner_may_reveal(self):
        self.assertTrue(can_reveal_secret_value(self.secret.name, OWNER))

    def test_shared_user_may_reveal(self):
        self.share_with(GRANTED)
        self.assertTrue(can_reveal_secret_value(self.secret.name, GRANTED))

    def test_outsider_may_not_reveal(self):
        self.assertFalse(can_reveal_secret_value(self.secret.name, OUTSIDER))

    def test_guest_may_never_reveal(self):
        self.assertFalse(can_reveal_secret_value(self.secret.name, "Guest"))

    # ------------------------------------------------------------------
    # The point of the exercise: administering is not reading
    # ------------------------------------------------------------------

    def test_vault_admin_may_not_reveal_a_secret_they_were_not_given(self):
        self.assertFalse(can_reveal_secret_value(self.secret.name, ADMIN_USER))

    def test_administrator_may_not_reveal_a_secret_they_do_not_own(self):
        self.assertFalse(can_reveal_secret_value(self.secret.name, "Administrator"))

    def test_administrator_may_reveal_a_secret_they_do_own(self):
        frappe.db.set_value("Vault Secret", self.secret.name, "owner", "Administrator", update_modified=False)
        self.assertTrue(can_reveal_secret_value(self.secret.name, "Administrator"))

    def test_admin_is_refused_by_the_decrypt_path_itself(self):
        # Not just the predicate — the function that actually returns plaintext.
        frappe.set_user(ADMIN_USER)
        with self.assertRaises(frappe.PermissionError):
            get_decrypted_secret_data(self.secret.name)

    def test_granting_a_share_restores_the_admin_s_access(self):
        self.share_with(ADMIN_USER)
        self.assertTrue(can_reveal_secret_value(self.secret.name, ADMIN_USER))

    # ------------------------------------------------------------------
    # The value itself still reaches the people entitled to it
    # ------------------------------------------------------------------

    def test_owner_gets_the_real_value_back(self):
        frappe.set_user(OWNER)
        decrypted = get_decrypted_secret_data(self.secret.name)
        self.assertEqual(decrypted.get("password"), SECRET_VALUE)

    def test_a_rotated_value_is_still_readable_by_its_owner(self):
        rotated = "RotatedValue456!"
        doc = frappe.get_doc("Vault Secret", self.secret.name)
        doc.password = rotated
        doc.save(ignore_permissions=True)

        frappe.set_user(OWNER)
        self.assertEqual(get_decrypted_secret_data(self.secret.name).get("password"), rotated)

    def test_a_rotated_value_stays_hidden_from_an_admin(self):
        doc = frappe.get_doc("Vault Secret", self.secret.name)
        doc.password = "RotatedValue456!"
        doc.save(ignore_permissions=True)

        frappe.set_user(ADMIN_USER)
        with self.assertRaises(frappe.PermissionError):
            get_decrypted_secret_data(self.secret.name)

    def test_a_revoked_share_takes_the_value_away_again(self):
        share = self.share_with(GRANTED)
        self.assertTrue(can_reveal_secret_value(self.secret.name, GRANTED))

        share.is_revoked = 1
        share.save(ignore_permissions=True)

        self.assertFalse(can_reveal_secret_value(self.secret.name, GRANTED))

    # ------------------------------------------------------------------
    # Authorization and mail delivery must not drift apart
    # ------------------------------------------------------------------

    def test_everyone_mailed_a_rotation_may_also_read_the_secret(self):
        self.share_with(GRANTED)
        for user in get_users_with_secret_access(self.secret.name):
            self.assertTrue(
                can_reveal_secret_value(self.secret.name, user),
                f"{user} is mailed rotated passwords but cannot view the secret",
            )

    def test_delivery_filtering_does_not_decide_authorization(self):
        # A granted user with no email address drops out of the mail list but
        # must keep access to their own secret.
        self.share_with(GRANTED)
        frappe.db.set_value("User", GRANTED, "email", "", update_modified=False)

        self.assertNotIn(GRANTED, get_users_with_secret_access(self.secret.name))
        self.assertIn(GRANTED, get_secret_access_grants(self.secret.name))
        self.assertTrue(can_reveal_secret_value(self.secret.name, GRANTED))
