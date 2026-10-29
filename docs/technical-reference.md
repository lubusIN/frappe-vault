# Technical Reference

Comprehensive technical reference covering architecture, administration, background maintenance, REST APIs, and developer setup.

## Table of Contents

- [Administration & Access Control](#administration--access-control)
- [Nested Folder & Permission Architecture](#nested-folder--permission-architecture)
- [Encryption Architecture](#encryption-architecture)
- [Scheduled Background Jobs](#scheduled-background-jobs)
- [Audit Logging & Compliance](#audit-logging--compliance)
- [REST API Reference](#rest-api-reference)
  - [Secrets API](#secrets-api)
  - [Sharing & One-Time Links API](#sharing--one-time-links-api)
  - [Folders API](#folders-api)
  - [User Management API](#user-management-api)
- [DocType Data Models](#doctype-data-models)
- [Frontend Development](#frontend-development)

## Administration & Access Control

### Roles & Permissions

Frappe Vault ships with two native roles for clean separation of concerns:

| Role | Desk Access | Scope | Typical Assignment |
|---|---|---|---|
| **Vault User** | No (`desk_access: 0`) | Create, read, update, and share personal credentials and folders via the `/vault` SPA. | Standard employees, team members |
| **Vault Admin** | Yes (`desk_access: 1`) | Full administrative control over Vault Settings, user invitations, global secrets, sharing policies, and audit logs. | System Managers, IT Admins |

> [!NOTE]
> Upon app installation, `Vault Admin` is automatically assigned to `Administrator` and active `System Manager` users. Assign `Vault User` to standard members who only need access to the web portal.

## Nested Folder & Permission Architecture

### NestedSet Tree Model

`Vault Folder` implements Frappe's `NestedSet` controller (`nsm_parent_field = "parent_vault_folder"`):
- Folders are indexed using nested set bounds (`lft` and `rgt`) alongside `parent_vault_folder` and `is_group`.
- Ancestry relationships and entire subtrees can be queried efficiently without recursive database joins.

### Row-Level Permissions & Cascade Sharing

Frappe Vault enforces row-level data isolation via `permission_query_conditions` hooks in [`frappe_vault/hooks.py`](../frappe_vault/hooks.py):
- **Secret Isolation**: Users only see secrets they own or that are shared directly with them or their roles.
- **Folder Cascade Sharing**: When a folder is shared with `cascade_permissions = 1` ("Apply to Subfolders"), all descendant subfolders (`child.lft >= ancestor.lft AND child.rgt <= ancestor.rgt`) and secrets inside them automatically inherit the share's permission level.
- **Direct Overrides**: Direct shares on an item take precedence over inherited role or parent folder permissions.

## Encryption Architecture

Frappe Vault leverages Frappe Framework's built-in AES encryption:
- **At-Rest Encryption**: Sensitive fields (`password`, `totp_secret`, `api_secret`, `card_number`, `card_cvv`, and `db_password`) use Frappe's `Password` fieldtype and are AES-encrypted inside the `__Auth` database table.
- **Site Encryption Key**: Encryption relies on `encryption_key` stored in `sites/<site-name>/site_config.json`.
- **Private Attachments**: Files uploaded to secrets are marked `is_private = 1` and protected by server-side permission hooks.

### Verifying Site Encryption Key

```bash
bench --site your-site.local console
>>> from frappe.utils.password import get_encryption_key
>>> bool(get_encryption_key())  # Must return True
```

### Setting an Encryption Key Manually

```bash
bench --site your-site.local set-config encryption_key "your-secure-32-byte-key-here"
```

> [!IMPORTANT]
> Always include `site_config.json` in your regular site backups. Losing the encryption key renders encrypted credentials permanently unrecoverable.

## Scheduled Background Jobs

Frappe scheduler tasks are registered in `hooks.py`:

| Frequency | Handler | Purpose |
|---|---|---|
| **Hourly** | `frappe_vault.background_jobs.link_cleanup.cleanup_expired_links` | Deactivates expired or consumed one-time sharing links (`is_consumed = 1`). |
| **Daily** | `frappe_vault.background_jobs.password_expiry.check_password_expiry` | Scans for passwords older than `max_password_age_days` (default 90 days) and alerts owners. |
| **Weekly** | `frappe_vault.background_jobs.security_scan.run_security_scan` | Recalculates user security scores based on password strength and rotation. |
| **Weekly** | `frappe_vault.background_jobs.log_cleanup.cleanup_old_logs` | Purges audit logs older than `log_retention_days` configured in `Vault Settings`. |

Ensure the bench scheduler is enabled on your site:
```bash
bench --site your-site.local enable-scheduler
```

## Audit Logging & Compliance

All sensitive actions generate an immutable record in **Vault Audit Log**:
- Secret decryption & view events
- Secret creation, updates, and deletion
- Share grants, permission changes, and revocations
- One-time link creation and consumption

`Vault Audit Log` records have read-only permissions in Frappe Desk and can only be inspected by `System Manager` and `Vault Admin`.

## REST API Reference

All endpoints are whitelisted RPC methods located under `frappe_vault.api.*`.

Authenticate requests with Frappe token authorization:
```
Authorization: token <api_key>:<api_secret>
```

### Secrets API

#### 1. List Secrets
```bash
curl -X GET "https://your-site.local/api/method/frappe_vault.api.secrets.list" \
  -H "Authorization: token api_key:api_secret"
```

**Parameters (Query String / JSON):**
- `search` *(str, optional)*: Filter by title or username
- `secret_type` *(str, optional)*: Filter by type (`Password`, `API Key`, `Database`, etc.)
- `folder` *(str, optional)*: Filter by folder name
- `bookmarks_only` *(bool, optional)*: Return only starred secrets
- `limit` *(int, default: 20)*: Page size
- `offset` *(int, default: 0)*: Page offset

#### 2. Get Decrypted Secret
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.secrets.decrypt" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{"name": "VS-0001"}'
```

Returns the secret document along with a `decrypted` object containing plaintext sensitive fields. Automatically logs a `Viewed` audit event.

#### 3. Create a Secret
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.secrets.create" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Production DB",
    "secret_type": "Database",
    "db_host": "db.internal",
    "db_port": 5432,
    "db_name": "app_prod",
    "username": "dbuser",
    "db_password": "super-secure-password"
  }'
```

#### 4. Get Live TOTP Token
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.secrets.get_totp" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{"name": "VS-0001"}'
```

### Sharing & One-Time Links API

#### 1. Share Secret or Folder
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.sharing.share" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "shared_name": "VF-0001",
    "shared_doctype": "Vault Folder",
    "share_type": "Role",
    "role": "Vault User",
    "permission_level": "View & Copy",
    "cascade_permissions": 1
  }'
```

#### 2. Generate a One-Time Sharing Link
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.sharing.create_one_time_link" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "secret_name": "VS-0001",
    "expiry_hours": 24,
    "max_views": 1,
    "passphrase": "optional-passphrase"
  }'
```

#### 3. Consume One-Time Link (Public)
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.sharing.consume_link" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<one-time-token>",
    "passphrase": "optional-passphrase"
  }'
```

> [!NOTE]
> `consume_link` allows guest access and is rate-limited to 5 requests per 60 seconds.

### Folders API

#### 1. Get All Folders with Tree Ordering
```bash
curl -X GET "https://your-site.local/api/method/frappe_vault.api.folders.get_all" \
  -H "Authorization: token api_key:api_secret"
```

Returns folders ordered by `lft asc` with fields `parent_vault_folder`, `is_group`, `can_write`, and icon metadata.

#### 2. Create a Folder
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.folders.create" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "folder_name": "Databases",
    "icon": "database",
    "parent_vault_folder": "Production"
  }'
```

### User Management API

#### 1. Invite Users via Email
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.user.invite_by_email" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "emails": "teammate@company.com",
    "role": "Vault User"
  }'
```

#### 2. Add Existing Frappe Users to Vault
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.user.add_existing_users" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "users": ["existing.user@company.com"],
    "role": "Vault User"
  }'
```

#### 3. Update User Role
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.user.update_user_role" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "user": "teammate@company.com",
    "new_role": "Vault Admin"
  }'
```

#### 4. Remove User Access
```bash
curl -X POST "https://your-site.local/api/method/frappe_vault.api.user.remove_vault_roles_from_user" \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "user": "teammate@company.com"
  }'
```

## DocType Data Models

| DocType | Type | Module | Purpose |
|---|---|---|---|
| `Vault Secret` | Standard | Vault | Main document storing credentials, sensitive keys, and metadata. |
| `Vault Folder` | Tree | Vault | Hierarchical folder records utilizing Frappe's NestedSet (`parent_vault_folder`, `lft`, `rgt`). |
| `Vault Share` | Standard | Vault | Tracks user/role sharing, permission levels, expiration, and `cascade_permissions`. |
| `Vault Invitation` | Standard | Vault | Manages email invitations, onboarding keys, role assignments, and acceptance status. |
| `Vault One Time Link` | Standard | Vault | Ephemeral public access tokens, counters, and optional passphrases. |
| `Vault Audit Log` | Read-only | Vault | Immutable compliance records tracking views, edits, and shares. |
| `Vault Bookmark` | Standard | Vault | Stores user-specific starred and bookmarked credentials. |
| `Vault Settings` | Single | Vault | Global policies, password complexity rules, and log retention days. |

## Frontend Development

The web portal is a Vue 3 single-page application located in [`frontend/`](../frontend) built with [Frappe UI](https://github.com/frappe/frappe-ui), Tailwind CSS, and Vite.

Key frontend features:
- **Nested Folder Tree**: Collapsible, re-orderable sidebar navigation with persistent state.
- **Settings Screen**: In-app management for users, invitations, email accounts/templates, profiles, and theme preferences.
- **Persistent Layouts**: Column resize preferences (`useColumnResize`) and dark/light themes saved across sessions.

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
yarn install

# Start Vite dev server with proxy to local bench
yarn dev

# Compile production bundle (outputs to frappe_vault/public/frontend)
yarn build
```
