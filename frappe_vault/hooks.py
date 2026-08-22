app_name = "frappe_vault"
app_title = "Vault"
app_publisher = "lubus"
app_description = "Secure password and secret management application for Frappe."
app_email = "info@lubus.in"
app_license = "MIT"
app_logo_url = "/assets/frappe_vault/images/vault-logo.svg"
app_home = "/vault"


# Apps Screen
add_to_apps_screen = [
    {
        "name": "frappe_vault",
        "logo": app_logo_url,
        "title": "Vault",
        "route": app_home,
    }
]

# Includes in <head>
app_include_css = "/assets/frappe_vault/css/frappe_vault.css"
app_include_js = "/assets/frappe_vault/js/frappe_vault.js"

# Website Route Rules — serve Vue SPA
website_route_rules = [
    {"from_route": "/vault/<path:app_path>", "to_route": "vault"},
    {"from_route": "/vault", "to_route": "vault"},
    {"from_route": "/desk/vault/<path:app_path>", "to_route": "vault"},
    {"from_route": "/desk/vault", "to_route": "vault"},
]

# Installation & Migration
after_install = "frappe_vault.setup.install.after_install"
after_migrate = "frappe_vault.setup.install.after_migrate"

# Document Events
doc_events = {
    "Vault Secret": {
        "after_insert": "frappe_vault.services.audit_service.log_secret_created",
        "on_update": "frappe_vault.services.audit_service.log_secret_updated",
        "on_trash": "frappe_vault.services.audit_service.log_secret_deleted",
    },
    "Vault Share": {
        "after_insert": "frappe_vault.services.audit_service.log_share_created",
        "on_trash": "frappe_vault.services.audit_service.log_share_removed",
    },
}

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "frappe_vault.background_jobs.password_expiry.check_password_expiry",
    ],
    "weekly": [
        "frappe_vault.background_jobs.security_scan.run_security_scan",
        "frappe_vault.background_jobs.log_cleanup.cleanup_old_logs",
    ],
    "hourly": [
        "frappe_vault.background_jobs.link_cleanup.cleanup_expired_links",
    ],
    # Hourly granularity is required for the "Hours" rotation unit to mean
    # anything; _long keeps archive building and mail queueing off the short queue.
    "hourly_long": [
        "frappe_vault.background_jobs.password_rotation.run_password_rotation",
    ],
}

# Permissions — row-level filtering
permission_query_conditions = {
    "Vault Secret": "frappe_vault.utils.permissions.get_secret_permission_query",
    "Vault Folder": "frappe_vault.utils.permissions.get_folder_permission_query",
}

has_permission = {
    "Vault Secret": "frappe_vault.utils.permissions.has_secret_permission",
    "Vault Folder": "frappe_vault.utils.permissions.has_folder_permission",
    "File": "frappe_vault.utils.permissions.has_file_permission",
}
