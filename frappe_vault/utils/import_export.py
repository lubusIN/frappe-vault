"""Import/Export utilities for Frappe Vault."""

import csv
import io
import json

import frappe
from frappe import _


@frappe.whitelist()
def export_secrets(format: str = "json", category: str = None) -> dict:
    """Export user's secrets to JSON or CSV format.

    Note: Passwords are NOT exported for security reasons.

    Args:
        format: Export format ('json' or 'csv')
        category: Optional category filter

    Returns:
        dict with file content
    """
    user = frappe.session.user

    filters = {"owner": user}
    if category:
        filters["category"] = category

    secrets = frappe.get_all(
        "Vault Secret",
        filters=filters,
        fields=["title", "secret_type", "category", "url", "username", "api_key", "notes", "is_bookmark"],
    )

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "title",
                "secret_type",
                "category",
                "url",
                "username",
                "api_key",
                "notes",
                "is_bookmark",
            ],
        )
        writer.writeheader()
        writer.writerows(secrets)
        content = output.getvalue()
        filename = "vault_export.csv"
        mimetype = "text/csv"
    else:
        content = json.dumps(secrets, indent=2)
        filename = "vault_export.json"
        mimetype = "application/json"

    return {"content": content, "filename": filename, "mimetype": mimetype}


@frappe.whitelist(methods=["POST"])
def import_secrets(data: str, format: str = "json") -> dict:
    """Import secrets from JSON or CSV format.

    Args:
        data: The file content as string
        format: Import format ('json' or 'csv')

    Returns:
        dict with import results
    """
    if not frappe.has_permission("Vault Secret", "create"):
        frappe.throw(_("You don't have permission to create secrets"))

    imported = 0
    errors = []

    try:
        if format == "csv":
            reader = csv.DictReader(io.StringIO(data))
            records = list(reader)
        else:
            records = json.loads(data)

        for idx, record in enumerate(records, 1):
            try:
                # Validate required fields
                if not record.get("title"):
                    errors.append(f"Row {idx}: Missing title")
                    continue

                doc = frappe.get_doc(
                    {
                        "doctype": "Vault Secret",
                        "title": record.get("title"),
                        "secret_type": record.get("secret_type", "Password"),
                        "category": record.get("category"),
                        "url": record.get("url"),
                        "username": record.get("username"),
                        "api_key": record.get("api_key"),
                        "notes": record.get("notes"),
                        "is_bookmark": 1 if record.get("is_bookmark") or record.get("is_favorite") else 0,
                    }
                )
                doc.insert()
                imported += 1

            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")

    except Exception as e:
        frappe.throw(_("Failed to parse import data: {0}").format(str(e)))

    return {
        "imported": imported,
        "errors": errors,
        "message": _("{0} secrets imported successfully").format(imported),
    }


@frappe.whitelist()
def get_export_template() -> dict:
    """Get a CSV template for importing secrets.

    Returns:
        dict with template content
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "title",
            "secret_type",
            "category",
            "url",
            "username",
            "password",
            "api_key",
            "api_secret",
            "notes",
            "is_bookmark",
        ],
    )
    writer.writeheader()

    # Add example row
    writer.writerow(
        {
            "title": "Example Website",
            "secret_type": "Password",
            "category": "",
            "url": "https://example.com",
            "username": "user@example.com",
            "password": "your_password_here",
            "api_key": "",
            "api_secret": "",
            "notes": "Optional notes",
            "is_bookmark": "0",
        }
    )

    return {"content": output.getvalue(), "filename": "vault_import_template.csv", "mimetype": "text/csv"}
