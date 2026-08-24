"""Vault's entry points in the Frappe Desk UI: the app-grid icon and the sidebar.

`DocType` and `Workspace` are synced from an app's module folder automatically on
every `bench migrate`. `Desktop Icon` and `Workspace Sidebar` are not — Frappe's
orphan-cleanup pass only checks that a matching fixture file exists on disk to
decide whether to leave a `standard` record alone; nothing keeps the record's
content in step with the file, and nothing recreates the record if it is ever
deleted. `sync_navigation_fixtures()` closes both gaps by importing the fixture
files directly, and this is what proves it actually does.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.setup.install import sync_navigation_fixtures


class TestNavigationFixtures(FrappeTestCase):
    def test_desktop_icon_exists_and_is_owned_by_the_app(self):
        sync_navigation_fixtures()
        icon = frappe.get_doc("Desktop Icon", "Vault")

        self.assertEqual(icon.app, "frappe_vault")
        self.assertTrue(icon.standard)
        self.assertFalse(icon.hidden)
        # Bundled with the app, not a site-uploaded File — reachable on any site
        # this app installs to, not only one where someone uploaded it by hand.
        self.assertEqual(icon.icon_image, "/assets/frappe_vault/images/vault-icon.svg")

    def test_sidebar_exists_and_is_owned_by_the_app(self):
        sync_navigation_fixtures()
        sidebar = frappe.get_doc("Workspace Sidebar", "Vault")

        self.assertEqual(sidebar.app, "frappe_vault")
        self.assertTrue(sidebar.standard)
        self.assertEqual(sidebar.module, "Vault")
        labels = [i.label for i in sidebar.items]
        self.assertIn("Vault Secrets", labels)

    def test_missing_icon_record_is_recreated_by_a_resync(self):
        # The scenario this whole module exists to prevent: the record is gone
        # from the database (orphan-cleanup ran before this fix existed, a stray
        # delete, a fresh install) and nothing brings it back until something
        # calls sync_navigation_fixtures() again — which after_install and
        # after_migrate now both do, unconditionally.
        #
        # Removed at the raw DB layer, deliberately not via frappe.delete_doc:
        # both Desktop Icon and Workspace Sidebar have an on_trash hook that
        # deletes their *source fixture file* when a standard record is trashed
        # through the document layer, so the document-layer path would destroy
        # the very file this test relies on to prove the resync works.
        sync_navigation_fixtures()
        frappe.db.delete("Desktop Icon", {"name": "Vault"})
        self.assertFalse(frappe.db.exists("Desktop Icon", "Vault"))

        sync_navigation_fixtures()

        self.assertTrue(frappe.db.exists("Desktop Icon", "Vault"))
        icon = frappe.get_doc("Desktop Icon", "Vault")
        self.assertEqual(icon.app, "frappe_vault")

    def test_missing_sidebar_record_is_recreated_by_a_resync(self):
        sync_navigation_fixtures()
        frappe.db.delete("Workspace Sidebar Item", {"parent": "Vault"})
        frappe.db.delete("Workspace Sidebar", {"name": "Vault"})
        self.assertFalse(frappe.db.exists("Workspace Sidebar", "Vault"))

        sync_navigation_fixtures()

        self.assertTrue(frappe.db.exists("Workspace Sidebar", "Vault"))
        sidebar = frappe.get_doc("Workspace Sidebar", "Vault")
        self.assertGreater(len(sidebar.items), 0)

    def test_workspace_itself_is_standard_frappe_fixture_synced(self):
        # Unlike the icon and sidebar, Workspace already survives migrate on its
        # own — Frappe syncs it from the module folder as a matter of course.
        # This just documents that assumption so a future change to either
        # mechanism is caught here rather than discovered as "Vault vanished".
        workspace = frappe.get_doc("Workspace", "Vault")
        self.assertTrue(workspace.public)
        self.assertFalse(workspace.is_hidden)
        self.assertEqual(workspace.module, "Vault")
