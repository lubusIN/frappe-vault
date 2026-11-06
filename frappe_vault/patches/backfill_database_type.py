"""Give pre-existing Database secrets a `database_type`.

`database_type` became mandatory for Database secrets when rotation gained the
ability to apply a new password to the live server — it decides which statement
gets run. Records created before that have it blank, and would refuse to save
until somebody opened each one.

The stored port is a strong hint and costs nothing to act on. Anything that does
not match a well-known port is left blank on purpose: guessing wrong here would
point a future rotation at the wrong engine, which is worse than asking.
"""

import frappe

# Default listening ports, in the same terms as the `database_type` Select.
TYPE_BY_PORT = {
    5432: "PostgreSQL",
    3306: "MySQL / MariaDB",
    3307: "MySQL / MariaDB",
    27017: "MongoDB",
}


def execute():
    secrets = frappe.get_all(
        "Vault Secret",
        filters={"secret_type": "Database", "database_type": ["in", ["", None]]},
        fields=["name", "db_port"],
    )

    inferred = 0
    for secret in secrets:
        database_type = TYPE_BY_PORT.get(frappe.utils.cint(secret.db_port))
        if not database_type:
            continue

        frappe.db.set_value(
            "Vault Secret", secret.name, "database_type", database_type, update_modified=False
        )
        inferred += 1

    if secrets:
        frappe.logger().info(
            f"frappe_vault: set database_type on {inferred} of {len(secrets)} Database secret(s); "
            f"{len(secrets) - inferred} left blank for their owner to fill in."
        )
