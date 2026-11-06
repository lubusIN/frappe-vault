"""Constants and enums for Frappe Vault."""

# Secret types
SECRET_TYPES = [
    "Password",
    "API Key",
    "Note",
    "SSH Key",
    "Media",
    "Credit Card",
    "Database",
    "Other",
]

# Permission levels for sharing
PERMISSION_LEVELS = [
    "View Only",
    "View & Copy",
    "Edit",
    "Full Control",
]

# Audit log actions
AUDIT_ACTIONS = [
    "Viewed",
    "Created",
    "Updated",
    "Deleted",
    "Shared",
    "Unshared",
    "Copied",
    "Generated",
    "Exported",
    "Imported",
    "Login",
]

# Database engines a Database secret can name, and whose password rotation can
# be applied to the live server. Must match the Vault Secret `database_type`
# Select options and services/db_rotation_service.SUPPORTED_DATABASE_TYPES.
DATABASE_TYPES = [
    "PostgreSQL",
    "MySQL / MariaDB",
    "MongoDB",
]

# Password strength levels
STRENGTH_LEVELS = ["weak", "fair", "good", "strong", "excellent"]

# Encrypted field mapping by secret type
ENCRYPTED_FIELDS = {
    "Password": ["password"],
    "API Key": ["api_secret"],
    "Credit Card": ["card_number", "card_cvv"],
    "Database": ["db_password", "rotation_admin_password"],
    "SSH Key": [],  # ssh_private_key is Code field, not Password
    "Media": [],
    "Note": [],
    "Other": [],
}

# Fields that should never be returned in list APIs
SENSITIVE_FIELDS = [
    "password",
    "api_secret",
    "card_number",
    "card_cvv",
    "db_password",
    "ssh_private_key",
    "rotation_admin_password",
]

# Safe fields for list view
LIST_VIEW_FIELDS = [
    "name",
    "title",
    "secret_type",
    "folder",
    "url",
    "username",
    "email",
    "attachment",
    "is_bookmark",
    "password_strength",
    "password_last_changed",
    "last_accessed",
    "access_count",
    "expires_on",
    "modified",
    "owner",
]
