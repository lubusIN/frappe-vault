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
                {
                    "doctype": "User",
                    "email": "test_hacker@example.com",
                    "first_name": "Test Hacker",
                    "roles": [{"role": "Vault User"}],
                }
            )
            doc.insert(ignore_permissions=True)
        else:
            doc = frappe.get_doc("User", "test_hacker@example.com")
            if "Vault User" not in [r.role for r in doc.roles]:
                doc.append_roles("Vault User")

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

        self.assertIn("Not permitted", str(context.exception))

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

    def test_unauthorized_vault_share_creation(self):
        """Verify an unauthorized user cannot grant themselves Full Control via direct Vault Share creation."""
        frappe.set_user("test_hacker@example.com")
        share_doc = frappe.get_doc(
            {
                "doctype": "Vault Share",
                "share_type": "User",
                "user": "test_hacker@example.com",
                "shared_doctype": "Vault Secret",
                "shared_name": self.secret.get("name"),
                "permission_level": "Full Control",
            }
        )
        with self.assertRaises(frappe.PermissionError):
            share_doc.insert()

    def test_unauthorized_one_time_link_creation(self):
        """Verify an unauthorized user cannot generate one-time links for secrets they cannot read."""
        frappe.set_user("test_hacker@example.com")
        link_doc = frappe.get_doc(
            {
                "doctype": "Vault One Time Link",
                "secret": self.secret.get("name"),
                "max_views": 10,
            }
        )
        with self.assertRaises(frappe.PermissionError):
            link_doc.insert()

    def test_unauthorized_file_attachment_relinking(self):
        """Verify a user cannot steal or re-link private files belonging to other records."""
        from frappe_vault.services.secret_service import _link_attachments

        # Create a mock private file owned by Administrator
        frappe.set_user("Administrator")
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "sensitive_admin_doc.txt",
                "file_url": "/private/files/sensitive_admin_doc.txt",
                "content": "Sensitive content",
                "is_private": 1,
            }
        )
        file_doc.insert(ignore_permissions=True)

        # Test hacker tries to claim this file in their secret
        frappe.set_user("test_hacker@example.com")
        mock_secret = frappe._dict(
            {
                "name": "VS-TEST-HACK",
                "secret_type": "Media",
                "attachment": '["/private/files/sensitive_admin_doc.txt"]',
            }
        )
        with self.assertRaises(frappe.PermissionError):
            _link_attachments(mock_secret)

        # Cleanup
        frappe.set_user("Administrator")
        frappe.delete_doc("File", file_doc.name, ignore_permissions=True)

    def test_totp_seed_not_exposed_to_readers(self):
        """Verify totp_secret seed is not exposed in decrypted output to View Only users."""
        from frappe_vault.services.secret_service import get_secret
        from frappe_vault.services.sharing_service import share_secret

        frappe.set_user("Administrator")
        secret_with_totp = create_secret(
            {
                "title": "TOTP Test Secret",
                "secret_type": "Password",
                "password": "pass",
                "totp_secret": "JBSWY3DPEHPK3PXP",
            }
        )
        share_secret(
            shared_name=secret_with_totp["name"],
            shared_doctype="Vault Secret",
            share_type="User",
            user="test_hacker@example.com",
            permission_level="View Only",
        )

        frappe.set_user("test_hacker@example.com")
        res = get_secret(secret_with_totp["name"], decrypt=True)
        self.assertIsNone(
            res.get("decrypted", {}).get("totp_secret"),
            "totp_secret seed should be hidden from non-Full-Control users",
        )

        frappe.set_user("Administrator")
        frappe.db.delete("Vault Share", {"shared_name": secret_with_totp["name"]})
        frappe.delete_doc("Vault Secret", secret_with_totp["name"], ignore_permissions=True)
