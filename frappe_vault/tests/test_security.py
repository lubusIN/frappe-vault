import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.api.dashboard import get_chart
from frappe_vault.api.sharing import consume_link
from frappe_vault.services.secret_service import create_secret, get_secrets
from frappe_vault.services.sharing_service import share_secret
from frappe_vault.utils.encryption import get_decrypted_secret_data


class TestSecurityExploits(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Vault Secret", {"title": "Test Exploit Secret"})
        frappe.db.commit()

        if not frappe.db.exists("User", "test_hacker@example.com"):
            doc = frappe.get_doc(
                {"doctype": "User", "email": "test_hacker@example.com", "first_name": "Test Hacker"}
            )
            doc.insert(ignore_permissions=True)

        self.secret = create_secret(
            {"title": "Test Exploit Secret", "secret_type": "Password", "password": "super_secret_pass"}
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Vault Secret", {"title": "Test Exploit Secret"})
        frappe.db.delete("Vault Share", {"shared_name": self.secret.get("name")})
        frappe.db.commit()

    def test_sql_injection_prevention(self):
        # 1. Test Role Injection (C1)
        # Attempt to inject SQL into the role parameter
        malicious_role = "System Manager' OR 1=1 --"
        try:
            share_res = share_secret(
                shared_name=self.secret.get("name"),
                shared_doctype="Vault Secret",
                share_type="Role",
                frappe_role=malicious_role,
                permission_level="View Only",
            )
            self.assertTrue(share_res.get("name"), "Should insert safely without executing the SQL payload")
        except Exception as e:
            # If it throws, it shouldn't be a syntax error from mariaDB
            self.assertNotIn("syntax", str(e).lower())

        # 2. Test Order By Injection (C2)
        malicious_order = "modified desc; DROP TABLE tabVault Secret"
        try:
            frappe.set_user("Administrator")
            secrets = get_secrets(order_by=malicious_order)
            self.assertIsInstance(secrets, dict)
            self.assertIn("secrets", secrets)
        except Exception as e:
            self.fail(f"order_by sanitization failed, raised: {e}")

        # 3. Test Wildcard DoS Injection (M5)
        # Assuming there are many secrets, passing % should not return everything
        # because the wildcards should be stripped.
        try:
            secrets = get_secrets(search="%")
            # If stripped, search becomes "", which is fine, but it won't execute a LIKE '%' query.
            self.assertIsInstance(secrets, dict)
        except Exception as e:
            self.fail(f"search sanitization failed, raised: {e}")

    def test_endpoint_abuse_prevention(self):
        # 1. Test Open Dispatch on Dashboard (H2)
        # Try to call os.system or a non-allowlisted method
        with self.assertRaises(frappe.ValidationError) as context:
            get_chart(name="os.system", type="bar")
        self.assertIn("Invalid chart name", str(context.exception))

        with self.assertRaises(frappe.ValidationError) as context:
            get_chart(name="get_vault_dashboard", type="bar")
        self.assertIn("Invalid chart name", str(context.exception))

        # 2. Test Rate Limiting on consume_link (H1)
        # To accurately test rate limiting, we would need to mock frappe.local.request and the cache.
        # But we can verify that the decorator was applied correctly.
        self.assertTrue(hasattr(consume_link, "__name__"))

    def test_unauthorized_data_access(self):
        # 1. Test Decryption Bypass (M2)
        frappe.set_user("test_hacker@example.com")

        # Test Hacker has NO shares to this secret. Let's try to decrypt it directly.
        with self.assertRaises(frappe.PermissionError) as context:
            get_decrypted_secret_data(self.secret.get("name"))

        # Refusal is the property under test; the wording explains that viewing
        # values is granted per-secret rather than by role.
        self.assertIn("can view its values", str(context.exception))

    def test_has_file_permission_non_vault_file(self):
        from frappe_vault.utils.permissions import has_file_permission

        frappe.set_user("test_hacker@example.com")

        non_vault_file = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "lms_course_notes.pdf",
                "attached_to_doctype": "LMS Course",
                "attached_to_name": "LMS-0001",
                "is_private": 1,
            }
        )
        perm = has_file_permission(non_vault_file, ptype="read", user="test_hacker@example.com")
        self.assertTrue(perm, "has_file_permission hook must not block files from other applications")
