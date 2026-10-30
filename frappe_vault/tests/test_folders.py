import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.api.folders import create, get_all


class TestFolders(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Vault Folder", {"folder_name": "Test Folder"})
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Vault Folder", {"folder_name": "Test Folder"})
        frappe.db.commit()

    def test_create_and_get_folders(self):
        folder = create("Test Folder", icon="folder")
        self.assertTrue(folder)

        folders = get_all()
        self.assertTrue(any(f.get("folder_name") == "Test Folder" for f in folders))

    def test_delete_folder_keep_secrets(self):
        folder = create("Test Folder", icon="folder")
        folder_name = folder["name"]

        from frappe_vault.api.folders import delete as delete_folder
        from frappe_vault.api.secrets import create as create_secret

        secret = create_secret(title="Secret to keep", folder=folder_name, password="Password123!")
        secret_name = secret["name"]

        # Delete folder but keep secrets (move to unfoldered)
        result = delete_folder(folder_name, delete_secrets=False)
        self.assertEqual(result["deleted"], folder_name)
        self.assertFalse(frappe.db.exists("Vault Folder", folder_name))
        self.assertTrue(frappe.db.exists("Vault Secret", secret_name))

        # Verify secret's folder field is now None / empty
        sec_folder = frappe.db.get_value("Vault Secret", secret_name, "folder")
        self.assertIsNone(sec_folder)

    def test_delete_folder_and_secrets(self):
        folder = create("Test Folder", icon="folder")
        folder_name = folder["name"]

        from frappe_vault.api.folders import delete as delete_folder
        from frappe_vault.api.secrets import create as create_secret

        secret = create_secret(title="Secret to delete", folder=folder_name, password="Password123!")
        secret_name = secret["name"]

        # Delete folder AND secrets
        result = delete_folder(folder_name, delete_secrets=True)
        self.assertEqual(result["deleted"], folder_name)
        self.assertFalse(frappe.db.exists("Vault Folder", folder_name))
        self.assertFalse(frappe.db.exists("Vault Secret", secret_name))

    def test_delete_nested_folders_move_up(self):
        from frappe_vault.api.folders import delete as delete_folder

        parent = create("Test Parent", icon="folder")
        child = create("Test Child", icon="folder", parent_vault_folder=parent["name"])

        # Delete Parent, move child up
        delete_folder(parent["name"], subfolder_action="move_up")

        self.assertFalse(frappe.db.exists("Vault Folder", parent["name"]))

        # Child should now have no parent
        child_doc = frappe.get_doc("Vault Folder", child["name"])
        self.assertIsNone(child_doc.parent_vault_folder)

        frappe.delete_doc("Vault Folder", child["name"])

    def test_delete_nested_folders_delete_all(self):
        from frappe_vault.api.folders import delete as delete_folder
        from frappe_vault.api.secrets import create as create_secret

        parent = create("Test Parent", icon="folder")
        child = create("Test Child", icon="folder", parent_vault_folder=parent["name"])

        secret = create_secret(title="Child Secret", folder=child["name"], password="Password123!")

        # Delete Parent, and all children
        delete_folder(parent["name"], subfolder_action="delete_all", delete_secrets=True)

        self.assertFalse(frappe.db.exists("Vault Folder", parent["name"]))
        self.assertFalse(frappe.db.exists("Vault Folder", child["name"]))
        self.assertFalse(frappe.db.exists("Vault Secret", secret["name"]))

    def test_update_folder_parent_reparenting(self):
        from frappe_vault.api.folders import update as update_folder

        parent_a = create("Test Folder A", icon="folder")
        parent_b = create("Test Folder B", icon="folder")
        child = create("Test Subfolder", icon="folder", parent_vault_folder=parent_a["name"])

        # Verify initial parent
        child_doc = frappe.get_doc("Vault Folder", child["name"])
        self.assertEqual(child_doc.parent_vault_folder, parent_a["name"])

        # Re-parent under Parent B
        update_folder(name=child["name"], parent_vault_folder=parent_b["name"])
        child_doc.reload()
        self.assertEqual(child_doc.parent_vault_folder, parent_b["name"])

        # Move to Root level (empty string or None)
        update_folder(name=child["name"], parent_vault_folder="")
        child_doc.reload()
        self.assertIsNone(child_doc.parent_vault_folder)

        # Cleanup
        frappe.delete_doc("Vault Folder", child["name"])
        frappe.delete_doc("Vault Folder", parent_a["name"])
        frappe.delete_doc("Vault Folder", parent_b["name"])

    def test_delete_folder_with_subfolder_having_children_move_up(self):
        """Test deleting a folder in a deep tree where the moving subfolder itself has subfolders."""
        from frappe_vault.api.folders import delete as delete_folder

        root_h = create("Test Folder H", icon="folder")
        test_1 = create("Test Folder 1", icon="folder", parent_vault_folder=root_h["name"])
        test1_1 = create("Test Subfolder 1-1", icon="folder", parent_vault_folder=test_1["name"])
        test2_1 = create("Test Subfolder 2-1", icon="folder", parent_vault_folder=test1_1["name"])

        # Delete test_1 with move_up (should move test1_1 under root_h, keeping test2_1 under test1_1)
        delete_folder(test_1["name"], subfolder_action="move_up")

        self.assertFalse(frappe.db.exists("Vault Folder", test_1["name"]))

        # test1_1 should now be under root_h
        test1_1_doc = frappe.get_doc("Vault Folder", test1_1["name"])
        self.assertEqual(test1_1_doc.parent_vault_folder, root_h["name"])

        # test2_1 should still be under test1_1
        test2_1_doc = frappe.get_doc("Vault Folder", test2_1["name"])
        self.assertEqual(test2_1_doc.parent_vault_folder, test1_1["name"])

        # Cleanup
        delete_folder(root_h["name"], subfolder_action="delete_all")
