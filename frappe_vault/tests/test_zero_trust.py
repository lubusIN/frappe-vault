"""An administrator manages the vault but cannot grant themselves its contents.

Every test here is an attempt by someone holding both Vault Admin and System
Manager — the strongest roles the app knows — to reach a secret they were
never given, by each route that would widen access: sharing it (with
themselves, an accomplice, or a role), moving it into a folder they own,
moving its folder under one of theirs, reassigning ownership, and reading it
through Frappe's generic password API. Each must be refused. Alongside, the
legitimate paths — an owner sharing, a recipient re-sharing, an admin
revoking — must keep working.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.services.secret_service import bulk_move
from frappe_vault.services.sharing_service import save_role_member_permission, share_secret
from frappe_vault.utils.permissions import can_reveal_secret_value

OWNER = "zt-owner@example.com"
ADMIN = "zt-admin@example.com"
ACCOMPLICE = "zt-accomplice@example.com"
COLLEAGUE = "zt-colleague@example.com"
TITLE = "ZT Victim Secret"
FOLDERS = ("ZT Owner Folder", "ZT Admin Folder")


def ensure_user(email, roles):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    for role in roles:
        if not any(r.role == role for r in user.roles):
            user.append("roles", {"role": role})
    user.save(ignore_permissions=True)


class TestAdminCannotGrantThemselvesAccess(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        ensure_user(OWNER, ["Vault User"])
        ensure_user(ADMIN, ["Vault User", "Vault Admin", "System Manager"])
        ensure_user(ACCOMPLICE, ["Vault User"])
        ensure_user(COLLEAGUE, ["Vault User"])

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

        frappe.set_user(OWNER)
        self.owner_folder = frappe.get_doc({"doctype": "Vault Folder", "folder_name": FOLDERS[0]}).insert()
        self.secret = frappe.get_doc(
            {
                "doctype": "Vault Secret",
                "title": TITLE,
                "secret_type": "Password",
                "password": "Victim-Password-123!",
                "folder": self.owner_folder.name,
            }
        ).insert()

        frappe.set_user(ADMIN)
        self.admin_folder = frappe.get_doc({"doctype": "Vault Folder", "folder_name": FOLDERS[1]}).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()

    def _cleanup(self):
        for name in frappe.get_all("Vault Secret", filters={"title": TITLE}, pluck="name"):
            frappe.db.delete("Vault Share", {"shared_name": name})
            frappe.db.delete("Vault Audit Log", {"secret": name})
            frappe.delete_doc("Vault Secret", name, force=True, ignore_permissions=True)
        for folder in FOLDERS:
            if frappe.db.exists("Vault Folder", folder):
                frappe.db.delete("Vault Share", {"shared_name": folder})
                frappe.db.delete("Vault Audit Log", {"folder": folder})
                frappe.db.set_value("Vault Folder", folder, "is_group", 0)
                frappe.delete_doc("Vault Folder", folder, force=True, ignore_permissions=True)

    def assertAdminCannotReveal(self):
        self.assertFalse(can_reveal_secret_value(self.secret.name, ADMIN))

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    def test_admin_cannot_share_a_secret_with_themselves(self):
        frappe.set_user(ADMIN)
        self.assertRaises(frappe.PermissionError, share_secret, self.secret.name, user=ADMIN)
        self.assertAdminCannotReveal()

    def test_admin_cannot_share_a_secret_with_an_accomplice(self):
        frappe.set_user(ADMIN)
        self.assertRaises(frappe.PermissionError, share_secret, self.secret.name, user=ACCOMPLICE)
        self.assertFalse(can_reveal_secret_value(self.secret.name, ACCOMPLICE))

    def test_admin_cannot_share_a_secret_with_their_own_role(self):
        frappe.set_user(ADMIN)
        self.assertRaises(
            frappe.PermissionError,
            share_secret,
            self.secret.name,
            share_type="Role",
            frappe_role="Vault Admin",
        )
        self.assertAdminCannotReveal()

    def test_admin_cannot_share_the_containing_folder(self):
        frappe.set_user(ADMIN)
        self.assertRaises(
            frappe.PermissionError,
            share_secret,
            self.owner_folder.name,
            shared_doctype="Vault Folder",
            user=ADMIN,
        )
        self.assertAdminCannotReveal()

    def test_admin_cannot_insert_a_share_record_directly(self):
        # The desk / REST path: a raw Vault Share insert skips sharing_service.
        frappe.set_user(ADMIN)
        share = frappe.get_doc(
            {
                "doctype": "Vault Share",
                "shared_doctype": "Vault Secret",
                "shared_name": self.secret.name,
                "share_type": "User",
                "user": ADMIN,
                "permission_level": "View Only",
            }
        )
        self.assertRaises(frappe.PermissionError, share.insert, ignore_permissions=True)
        self.assertAdminCannotReveal()

    def test_admin_cannot_restore_a_role_member_through_overrides(self):
        frappe.set_user(ADMIN)
        self.assertRaises(
            frappe.PermissionError,
            save_role_member_permission,
            shared_name=self.secret.name,
            user=ADMIN,
            permission_level="View Only",
            is_revoked=False,
        )
        self.assertAdminCannotReveal()

    def test_admin_cannot_move_a_secret_into_their_own_folder(self):
        frappe.set_user(ADMIN)
        self.assertRaises(frappe.PermissionError, bulk_move, [self.secret.name], self.admin_folder.name)
        self.assertEqual(
            frappe.db.get_value("Vault Secret", self.secret.name, "folder"), self.owner_folder.name
        )
        self.assertAdminCannotReveal()

    def test_admin_cannot_move_a_secret_by_editing_the_record(self):
        frappe.set_user(ADMIN)
        doc = frappe.get_doc("Vault Secret", self.secret.name)
        doc.folder = self.admin_folder.name
        self.assertRaises(frappe.PermissionError, doc.save, ignore_permissions=True)
        self.assertAdminCannotReveal()

    def test_admin_cannot_move_the_owners_folder_under_their_own(self):
        frappe.set_user(ADMIN)
        folder = frappe.get_doc("Vault Folder", self.owner_folder.name)
        folder.parent_vault_folder = self.admin_folder.name
        self.assertRaises(frappe.PermissionError, folder.save, ignore_permissions=True)

    def test_admin_cannot_read_a_secret_through_frappe_get_password(self):
        from frappe_vault.api.overrides import get_password

        frappe.set_user(ADMIN)
        for doctype, name, field in (
            ("Vault Secret", self.secret.name, "password"),
            ("Vault Settings", "Vault Settings", "hashicorp_secret_id"),
        ):
            with self.subTest(doctype=doctype):
                self.assertRaises(frappe.PermissionError, get_password, doctype, name, field)

    def test_frappe_get_password_is_routed_through_the_override(self):
        overrides = frappe.get_hooks("override_whitelisted_methods") or {}
        self.assertEqual(
            (overrides.get("frappe.client.get_password") or [None])[-1],
            "frappe_vault.api.overrides.get_password",
        )

    # ------------------------------------------------------------------
    # Legitimate use keeps working
    # ------------------------------------------------------------------

    def test_owner_can_still_share(self):
        frappe.set_user(OWNER)
        share_secret(self.secret.name, user=COLLEAGUE)
        self.assertTrue(can_reveal_secret_value(self.secret.name, COLLEAGUE))

    def test_a_recipient_can_reshare_what_they_were_given(self):
        frappe.set_user(OWNER)
        share_secret(self.secret.name, user=COLLEAGUE, permission_level="Full Control")
        frappe.set_user(COLLEAGUE)
        share_secret(self.secret.name, user=ACCOMPLICE)
        self.assertTrue(can_reveal_secret_value(self.secret.name, ACCOMPLICE))

    def test_owner_can_still_move_their_secret(self):
        frappe.set_user(OWNER)
        doc = frappe.get_doc("Vault Secret", self.secret.name)
        doc.folder = None
        doc.save()
        self.assertFalse(frappe.db.get_value("Vault Secret", self.secret.name, "folder"))

    def test_admin_can_still_revoke_access(self):
        frappe.set_user(OWNER)
        share_name = share_secret(self.secret.name, user=COLLEAGUE).get("name")
        frappe.set_user(ADMIN)
        share = frappe.get_doc(
            "Vault Share",
            share_name
            or frappe.db.get_value(
                "Vault Share", {"shared_name": self.secret.name, "user": COLLEAGUE}, "name"
            ),
        )
        share.is_revoked = 1
        share.save(ignore_permissions=True)
        self.assertFalse(can_reveal_secret_value(self.secret.name, COLLEAGUE))


class TestSecuritySettingsChangesAreAudited(FrappeTestCase):
    def test_changing_the_hashicorp_target_is_logged(self):
        frappe.set_user("Administrator")
        settings = frappe.get_single("Vault Settings")
        original = settings.hashicorp_vault_path_prefix
        try:
            settings.hashicorp_vault_path_prefix = "zt-audit-check"
            settings.save(ignore_permissions=True)
            log = frappe.get_all(
                "Vault Audit Log",
                filters={"action": "Settings Changed"},
                fields=["details"],
                order_by="creation desc",
                limit=1,
            )
            self.assertTrue(log)
            self.assertIn("hashicorp_vault_path_prefix", log[0].details)
        finally:
            settings.reload()
            settings.hashicorp_vault_path_prefix = original
            settings.save(ignore_permissions=True)
