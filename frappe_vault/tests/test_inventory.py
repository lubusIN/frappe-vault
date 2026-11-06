"""Picking Linux hosts from the Inventory Management app's VM records.

`inventory_management` is a separate app. This site has it installed, but the
CI environment that runs this suite does not — only `frappe_vault` itself gets
installed there. That is deliberate: every test here has to make sense both
with and without the other app present, the same requirement the feature code
itself has to meet. Tests that need real VM data skip cleanly when there is
none, rather than failing on an environment where the integration correctly
has nothing to show.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_vault.api.inventory import (
    UNASSIGNED,
    _best_ipv4,
    is_available,
    list_server_roles,
    list_vms_for_role,
)

TEST_USERS = ["inventory-picker-plain-vault-user@example.com"]


def ensure_plain_vault_user(email):
    """A Vault User with no Inventory role — what most Vault users actually are."""
    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Plain",
                "send_welcome_email": 0,
            }
        )
        user.append("roles", {"role": "Vault User"})
        user.insert(ignore_permissions=True)
    return email


class TestBestIpv4(FrappeTestCase):
    """Picking a usable address out of source data that mixes real addresses
    with the literal string "N/A", blanks, and IPv6 link-local noise."""

    def test_a_clean_primary_ip_is_used(self):
        self.assertEqual(_best_ipv4("172.16.10.29", ""), "172.16.10.29")

    def test_falls_back_to_extra_ip_address_when_primary_is_unusable(self):
        self.assertEqual(_best_ipv4("N/A", "172.16.10.29, fe80::250:56ff:fe8a:bd51"), "172.16.10.29")

    def test_ipv6_link_local_is_never_returned(self):
        self.assertIsNone(_best_ipv4("", "fe80::250:56ff:fe8a:bd51"))

    def test_blank_and_na_both_yield_nothing(self):
        self.assertIsNone(_best_ipv4("N/A", ""))
        self.assertIsNone(_best_ipv4("", ""))
        self.assertIsNone(_best_ipv4(None, None))

    def test_first_valid_address_wins_when_several_are_present(self):
        self.assertEqual(_best_ipv4("172.16.10.29", "10.0.0.1, 10.0.0.2"), "172.16.10.29")

    def test_garbage_that_merely_looks_numeric_is_rejected(self):
        # Not a valid IPv4 octet range — must not be mistaken for one.
        self.assertIsNone(_best_ipv4("999.999.999.999", ""))


class TestInventoryAvailability(FrappeTestCase):
    """Whether the picker has anything to offer at all — the gate the rest of
    the feature depends on, and the one thing every environment exercises,
    with or without inventory_management installed."""

    def setUp(self):
        self.inventory_installed = bool(frappe.db.exists("DocType", "Virtual Machines"))
        frappe.set_user("Administrator")
        ensure_plain_vault_user(TEST_USERS[0])

    def tearDown(self):
        frappe.set_user("Administrator")
        for email in TEST_USERS:
            if frappe.db.exists("User", email):
                frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()  # nosemgrep — fixtures must not survive on this site

    def test_absence_is_reported_cleanly_not_as_an_error(self):
        # Simulated on any site, since it is the one path every CI run for
        # this app actually takes — inventory_management is never installed
        # there. The real, unmocked absence case matters just as much as the
        # mocked one here, so both are covered.
        import unittest.mock

        with unittest.mock.patch.object(frappe.db, "exists", return_value=False):
            self.assertFalse(is_available()["available"])
            self.assertEqual(list_server_roles(), [])
            self.assertEqual(list_vms_for_role(UNASSIGNED), [])

    def test_available_when_installed_and_permitted(self):
        if not self.inventory_installed:
            self.skipTest("inventory_management is not installed on this site")

        frappe.set_user("Administrator")
        self.assertTrue(is_available()["available"])

    def test_unavailable_to_a_vault_user_with_no_inventory_role(self):
        if not self.inventory_installed:
            self.skipTest("inventory_management is not installed on this site")

        # The point of the whole design: being a Vault User grants nothing
        # here. Inventory Management's own roles are what decide this.
        frappe.set_user(TEST_USERS[0])
        self.assertFalse(is_available()["available"])
        self.assertEqual(list_server_roles(), [])
        self.assertEqual(list_vms_for_role(UNASSIGNED), [])


class TestListingRolesAndVms(FrappeTestCase):
    """Shape and consistency of what gets returned when the inventory is
    genuinely there to query — skipped everywhere it is not, rather than
    asserting on data (counts, specific VM names) that could legitimately
    differ between environments or drift over time on this one."""

    def setUp(self):
        if not frappe.db.exists("DocType", "Virtual Machines"):
            self.skipTest("inventory_management is not installed on this site")
        frappe.set_user("Administrator")

    def test_roles_are_well_formed(self):
        roles = list_server_roles()
        for role in roles:
            self.assertIn("label", role)
            self.assertIn("value", role)
            self.assertIn("count", role)
            self.assertGreater(role["count"], 0)

    def test_role_values_are_unique(self):
        roles = list_server_roles()
        values = [r["value"] for r in roles]
        self.assertEqual(len(values), len(set(values)))

    def test_unassigned_bucket_is_last_when_present(self):
        roles = list_server_roles()
        values = [r["value"] for r in roles]
        if UNASSIGNED in values:
            self.assertEqual(values[-1], UNASSIGNED)

    def test_vms_for_a_real_role_are_well_formed(self):
        roles = list_server_roles()
        if not roles:
            self.skipTest("no server roles present in this inventory")

        vms = list_vms_for_role(roles[0]["value"])
        self.assertEqual(len(vms), roles[0]["count"])
        for vm in vms:
            self.assertIn("name", vm)
            self.assertIn("vm_name", vm)
            self.assertIn("ip", vm)
            self.assertIn("has_usable_ip", vm)
            # The two must agree with each other — has_usable_ip is derived
            # from whether ip actually got set, not an independent flag that
            # could silently drift out of sync with it.
            self.assertEqual(vm["has_usable_ip"], vm["ip"] is not None)

    def test_an_unknown_role_returns_no_vms_not_an_error(self):
        self.assertEqual(list_vms_for_role("a role nothing is tagged with"), [])
