import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.background_jobs.log_cleanup import cleanup_old_logs

TEST_USER = "vault-log-cleanup-test@example.com"


class TestLogCleanupPermissions(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        if not frappe.db.exists("User", TEST_USER):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": TEST_USER,
                    "first_name": "Log Cleanup",
                    "send_welcome_email": 0,
                    "roles": [{"role": "Vault User"}],
                }
            ).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_regular_vault_user_cannot_purge_audit_logs(self):
        frappe.set_user(TEST_USER)
        self.assertRaises(frappe.PermissionError, cleanup_old_logs)

    def test_administrator_can_purge_audit_logs(self):
        # The weekly scheduler job runs as Administrator.
        result = cleanup_old_logs()
        self.assertIn("deleted_count", result)
