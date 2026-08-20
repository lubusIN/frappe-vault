<p align="center"><img width="160" src=".github/assets/logo.svg"></p>


<img src=".github/assets/banner.png" />

[![Playground Demo Link](https://img.shields.io/badge/Live%20Demo-3858e9?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyMTkuNzUgMjE2Ij4KICA8ZGVmcz4KICAgIDxjbGlwUGF0aCBpZD0iYSI+CiAgICAgIDxwYXRoIGQ9Ik0wIC4xMjFoMjE5VjIxMkgwWm0wIDAiLz4KICAgIDwvY2xpcFBhdGg+CiAgPC9kZWZzPgogIDxnIGNsaXAtcGF0aD0idXJsKCNhKSI+CiAgICA8cGF0aCBmaWxsPSIjZmZmIiBkPSJNMTQ4LjQwMiAyMTEuNTI3Yy0xMi43OC03NC4xMjUtMzQuMTQ0LTExMy42MTctODYuMjU3LTE0MS43OGwyMi40NjQtNC41OTljMTIuMjM5IDguMDM2IDIyLjg4IDE3LjA2NyAzMi4wOTggMjcuNDk3IDE1LjM1NiAxNy4zNyAyNi4xNCAzNy45MDYgMzQuMTg4IDYyLjU0M2w0NC45MTQtMTM0LjU3NUw1NS43MjMgNDkuMjYycS4wMDYuMDA2LjAyLjAxMWwtMjYuODAyIDUuNDhjLTguOTA2LTMuNDA1LTE4LjQ3Ni02LjY4Ny0yOC43Ny05Ljg5TDIxOC45NTQuMTIxWm0wIDAiLz4KICA8L2c+Cjwvc3ZnPg==&logoSize=auto)](https://frappe-playground.lubus.in/?name=Frappe%20Vault&onboarding=0&apps=frappe_vault&path=/vault)

# Frappe Vault

Secrets and password management application. Securely store, share, and manage sensitive credentials within your Frappe/ERPNext portal.

## Features

- **Secure Storage**: Store passwords, API keys, SSH keys, notes, credit cards, databases, and media files with encryption
- **Folders**: Organize secrets in a tree-based folder structure
- **Access Logging**: Track who accessed which secrets and when
- **Sharing**: Share secrets with specific users or roles
- **Bookmarks**: Mark frequently used secrets as bookmarks
- **Dashboard**: Visual overview with statistics and charts
- **REST API**: Full API access for browser extensions and integrations

## Compatibility

This app is compatible with Frappe Framework:

| Vault Branch | Stability | Frappe Branch |
|---|---|---|
| `main` - `v1.x` | **Stable** | `v15.x` & `v16.x` |
| `develop` - `future/v2.x` | **Unstable** | `develop` |

## Installation

### Prerequisites

- Frappe Framework v15+
- An active Frappe/ERPNext site

### Install via Bench

```bash
# Get the app
bench get-app https://github.com/lubusIN/frappe-vault.git

# Install on your site
bench --site your-site.local install-app frappe_vault
```

### Development Installation

```bash
# Clone the repository
cd ~/frappe-bench/apps
git clone https://github.com/lubusIN/frappe-vault.git

# Install the app
bench --site your-site.local install-app frappe_vault

# Enable developer mode (optional, for development)
bench --site your-site.local set-config developer_mode 1
```

## Configuration

### Encryption Key

Frappe Vault uses Frappe's built-in encryption which relies on the site's encryption key. This is automatically configured when you set up your Frappe site.

To verify your encryption key is set:

```bash
bench --site your-site.local console
>>> from frappe.utils.password import get_encryption_key
>>> bool(get_encryption_key())  # Should return True
```

If you need to set an encryption key manually:

```bash
bench --site your-site.local set-config encryption_key "your-secure-32-byte-key-here"
```

**Important**: Keep your encryption key secure and backed up. Losing it means losing access to all encrypted secrets.

### Roles and Permissions

Frappe Vault uses two custom roles:

- **Vault User**: Can create, read, update, and share their own secrets and folders
- **Vault Admin**: Administrative access to vault settings, policies, and audit logs

Assign these roles to users through the User DocType or Role Permissions Manager.

## Usage

### Creating Secrets

1. Navigate to **Frappe Vault > Vault Secret > New**
2. Enter a title and select the secret type
3. Fill in the credentials (password, API key, etc.)
4. Optionally assign a folder and tags
5. Save

### Sharing Secrets

1. Open a secret
2. Go to the **Sharing** section
3. Add users or roles with read/write permissions
4. Set an optional expiration date

### REST API

All secrets are accessible via REST API for integration with other applications.

```bash
# Get all secrets
curl -X GET "https://your-site.local/api/method/frappe_vault.api.secrets.list" \
  -H "Authorization: token api_key:api_secret"

# Get a specific secret with decrypted password
curl -X POST "https://your-site.local/api/method/frappe_vault.api.secrets.decrypt" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{"name": "VS-0001"}'

# Create a new secret
curl -X POST "https://your-site.local/api/method/frappe_vault.api.secrets.create" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{"title": "My Secret", "secret_type": "Password", "password": "hunter2"}'
```


## DocTypes

### Vault Secret

Main document for storing credentials.

| Field | Type | Description |
|-------|------|-------------|
| title | Data | Name/title of the secret |
| secret_type | Select | Password, API Key, Note, SSH Key, Media, Credit Card, Database, Other |
| folder | Link | Reference to Vault Folder |
| url | Data | Associated website/service URL |
| username | Data | Username for the credential |
| password | Password | Encrypted password field |
| api_key | Data | API key (for API Key type) |
| api_secret | Password | Encrypted API secret |
| notes | Text Editor | Additional notes |
| is_bookmark | Check | Mark as bookmark |
| password_strength | Select | Calculated password strength |

### Vault Folder

Organize your secrets into logical groups using folders.

### Vault Access Log

Read-only audit log tracking all secret access.

## Security

- All passwords and secrets are encrypted using Frappe's built-in AES encryption
- Encryption relies on the site's encryption key stored in `site_config.json`
- Role-based access control (RBAC) using Frappe's Permission Manager
- Access logging for audit compliance
- Secrets are only accessible by owners or explicitly shared users/roles

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and feature requests, please use the GitHub issue tracker.

## More Frappe Tools

Explore more open-source tools we're building for the Frappe ecosystem.

<table>
  <tr>
    <td width="50%" valign="top">
      <a href="https://github.com/lubusIN/frappe-local">
        <img src="https://raw.githubusercontent.com/lubusIN/frappe-local/main/.github/assets/logo.svg" alt="Frappe Local" height="60">
      </a>
      <br>
      Create and manage local Frappe benches and sites visually.
    </td>
    <td width="50%" valign="top">
      <a href="https://github.com/lubusIN/frappe-playground">
        <img src="https://raw.githubusercontent.com/lubusIN/frappe-playground/main/.github/logo.svg" alt="Frappe Playground" height="60">
      </a>
      <br>
      Run Frappe entirely in your browser.
    </td>
  </tr>

  <tr>
    <td width="50%" valign="top">
      <a href="https://github.com/lubusIN/frappe-brewery">
        <img src="https://raw.githubusercontent.com/lubusIN/frappe-brewery/main/.github/assets/logo.svg" alt="Frappe Brewery" height="60">
      </a>
      <br>
      Discover community-built apps for Frappe.
    </td>
    <td width="50%" valign="top">
      <a href="https://github.com/lubusIN/wp-frappe-data-store">
        <img src="https://raw.githubusercontent.com/lubusIN/wp-frappe-data-store/main/.github/assets/logo.svg" alt="WP Frappe Data Store" height="60">
      </a>
      <br>
      Connect WordPress and Frappe with a React data store.
    </td>
  </tr>
</table>

[Explore all LUBUS projects →](https://github.com/lubusIN)

## Meet Your Artisans

[LUBUS](https://lubus.in/?utm_source=github&utm_medium=open-source&utm_campaign=frappe-vault) is a web design agency based in Mumbai.

<a href="https://cal.com/lubus">
<img src="https://raw.githubusercontent.com/lubusIN/.github/refs/heads/main/profile/banner.png" />
</a>

## License

Frappe Vault is open-sourced licensed under the [MIT License](LICENSE).
