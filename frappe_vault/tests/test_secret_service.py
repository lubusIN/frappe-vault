import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.services.generator_service import calculate_password_strength, generate_password
from frappe_vault.services.secret_service import (
    create_secret,
    delete_secret,
    get_secret,
    get_totp_code,
    toggle_bookmark,
    update_secret,
)


class TestSecretService(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        # Ensure clean slate for test secrets
        frappe.db.delete(
            "Vault Secret",
            {
                "title": [
                    "in",
                    [
                        "Test Service Secret",
                        "Test Bookmark Secret",
                        "Test Update Secret",
                        "User Owned Secret",
                        "Admin Secret",
                    ],
                ]
            },
        )
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.delete(
            "Vault Secret",
            {
                "title": [
                    "in",
                    [
                        "Test Service Secret",
                        "Test Bookmark Secret",
                        "Test Update Secret",
                        "User Owned Secret",
                        "Admin Secret",
                    ],
                ]
            },
        )
        frappe.db.commit()

    def test_create_and_get_secret(self):
        secret_data = {
            "title": "Test Service Secret",
            "secret_type": "Password",
            "username": "admin",
            "password": "SuperSecretPassword123!",
            "url": "https://example.com",
        }

        # Test creation
        new_secret = create_secret(secret_data)
        self.assertTrue(new_secret)
        self.assertEqual(new_secret.get("title"), "Test Service Secret")

        # Test retrieval (without decrypting password)
        retrieved = get_secret(new_secret.get("name"))
        self.assertEqual(retrieved.get("title"), "Test Service Secret")

        # Test decryption retrieval
        decrypted = get_secret(new_secret.get("name"), decrypt=True)
        self.assertEqual(decrypted.get("decrypted", {}).get("password"), "SuperSecretPassword123!")

    def test_update_secret(self):
        secret_data = {
            "title": "Test Service Secret",
            "secret_type": "Password",
            "username": "admin",
            "password": "OldPassword123!",
        }
        new_secret = create_secret(secret_data)
        secret_name = new_secret.get("name")

        # Update password & title
        updated = update_secret(secret_name, {"title": "Test Update Secret", "password": "NewPassword456!"})
        self.assertEqual(updated.get("title"), "Test Update Secret")

        decrypted = get_secret(secret_name, decrypt=True)
        self.assertEqual(decrypted.get("decrypted", {}).get("password"), "NewPassword456!")

    def test_delete_secret(self):
        secret_data = {"title": "Test Service Secret", "secret_type": "Note", "notes": "Some test notes"}

        new_secret = create_secret(secret_data)
        secret_name = new_secret.get("name")

        # Delete it
        delete_secret(secret_name)

        # Ensure it's deleted or trashed
        exists = frappe.db.exists("Vault Secret", secret_name)
        self.assertFalse(exists)

    def test_toggle_bookmark(self):
        secret_data = {"title": "Test Bookmark Secret", "secret_type": "Note", "notes": "Some test notes"}
        new_secret = create_secret(secret_data)
        secret_name = new_secret.get("name")

        user = frappe.session.user
        fav_exists = frappe.db.exists("Vault Bookmark", {"user": user, "secret": secret_name})
        self.assertFalse(fav_exists)

        # Toggle on
        res = toggle_bookmark(secret_name)
        self.assertEqual(res.get("is_bookmark"), 1)
        self.assertTrue(frappe.db.exists("Vault Bookmark", {"user": user, "secret": secret_name}))

        # Toggle off
        res = toggle_bookmark(secret_name)
        self.assertEqual(res.get("is_bookmark"), 0)
        self.assertFalse(frappe.db.exists("Vault Bookmark", {"user": user, "secret": secret_name}))

        delete_secret(secret_name)

    def test_generate_password_and_strength(self):
        pwd = generate_password(length=20, use_uppercase=1, use_lowercase=1, use_digits=1, use_special=1)
        self.assertEqual(len(pwd), 20)

        strength = calculate_password_strength("P@ssw0rd12345678!")
        self.assertEqual(strength.get("level"), "excellent")

    def test_media_attachment_and_url_sanitization(self):
        secret_data = {
            "title": "Test Media Secret",
            "secret_type": "Media",
            "url": "example.com",
            "attachment": '["/private/files/1.jpeg","/private/files/2.jpeg"]',
        }
        new_secret = create_secret(secret_data)
        secret_name = new_secret.get("name")

        retrieved = get_secret(secret_name)
        self.assertEqual(retrieved.get("url"), "https://example.com")
        self.assertEqual(retrieved.get("attachment"), '["/private/files/1.jpeg","/private/files/2.jpeg"]')

        # Update attachment
        update_secret(secret_name, {"attachment": '["/private/files/1.jpeg"]'})
        updated = get_secret(secret_name)
        self.assertEqual(updated.get("attachment"), '["/private/files/1.jpeg"]')

        delete_secret(secret_name)

    def test_ssh_key_secret(self):
        secret_data = {
            "title": "Test SSH Key Secret",
            "secret_type": "SSH Key",
            "username": "ubuntu",
            "ssh_private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\ntest\n-----END OPENSSH PRIVATE KEY-----",
        }
        new_secret = create_secret(secret_data)
        secret_name = new_secret.get("name")

        retrieved = get_secret(secret_name)
        self.assertEqual(retrieved.get("username"), "ubuntu")
        delete_secret(secret_name)

    def test_bulk_delete_api(self):
        from frappe_vault.api.secrets import bulk_delete as bulk_delete_api

        s1 = create_secret({"title": "Bulk Delete Secret 1", "password": "Password1!"})
        s2 = create_secret({"title": "Bulk Delete Secret 2", "password": "Password2!"})

        result = bulk_delete_api([s1["name"], s2["name"]])
        self.assertEqual(result.get("deleted"), 2)
        self.assertFalse(frappe.db.exists("Vault Secret", s1["name"]))
        self.assertFalse(frappe.db.exists("Vault Secret", s2["name"]))

    def test_totp_code_generation(self):
        secret_data = {
            "title": "Test TOTP Secret",
            "secret_type": "Password",
            "username": "totpuser",
            "totp_secret": "JBSWY3DPEHPK3PXP",
        }
        new_secret = create_secret(secret_data)
        secret_name = new_secret.get("name")

        # Test valid TOTP generation
        totp_data = get_totp_code(secret_name)
        self.assertIsNotNone(totp_data.get("code"))
        self.assertEqual(len(str(totp_data.get("code"))), 6)
        self.assertGreater(totp_data.get("remaining_seconds"), 0)
        self.assertIsNone(totp_data.get("error"))

        # Test invalid/empty TOTP secret
        update_secret(secret_name, {"totp_secret": ""})
        empty_totp_data = get_totp_code(secret_name)
        self.assertIsNone(empty_totp_data.get("code"))
        self.assertIsNotNone(empty_totp_data.get("error"))

        # Cleanup
        delete_secret(secret_name)

    def test_upload_file_api(self):
        from frappe_vault.api.secrets import upload_file as upload_file_api

        test_email = "standard_vault_test_user@example.com"
        if not frappe.db.exists("User", test_email):
            user_doc = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": test_email,
                    "first_name": "Standard",
                    "last_name": "Vault User",
                }
            )
            user_doc.insert(ignore_permissions=True)

        user_doc = frappe.get_doc("User", test_email)
        user_doc.add_roles("Vault User")
        frappe.clear_cache(user=test_email)

        orig_user = frappe.session.user
        s_own = None
        s_other = None
        try:
            frappe.set_user(test_email)

            frappe.form_dict = frappe._dict({"is_private": 1})
            frappe.request = frappe._dict(
                {
                    "files": {
                        "file": frappe._dict(
                            {
                                "stream": frappe._dict({"read": lambda: b"test image file content"}),
                                "filename": "sample_media.png",
                            }
                        )
                    }
                }
            )

            # 1. Upload for new secret (without doctype/docname)
            res = upload_file_api()
            self.assertIsNotNone(res.get("file_url"))
            self.assertEqual(res.get("file_name"), "sample_media.png")
            self.assertTrue(frappe.db.exists("File", res.get("name")))

            # 2. Upload attached to existing secret owned by user
            s_own = create_secret({"title": "User Owned Secret", "secret_type": "Note"})
            frappe.form_dict = frappe._dict(
                {
                    "is_private": 1,
                    "doctype": "Vault Secret",
                    "docname": s_own["name"],
                }
            )
            res_own = upload_file_api()
            self.assertEqual(res_own.get("file_name"), "sample_media.png")

            # 3. Upload attached to another user's secret (unauthorized) -> must throw PermissionError
            frappe.set_user("Administrator")
            s_other = create_secret({"title": "Admin Secret", "secret_type": "Note"})
            frappe.set_user(test_email)

            frappe.form_dict = frappe._dict(
                {
                    "is_private": 1,
                    "doctype": "Vault Secret",
                    "docname": s_other["name"],
                }
            )
            with self.assertRaises(frappe.PermissionError):
                upload_file_api()

        finally:
            frappe.set_user("Administrator")
            if s_own:
                delete_secret(s_own["name"])
            if s_other:
                delete_secret(s_other["name"])
            frappe.set_user(orig_user)
