# User Guide

This guide covers daily credential management, sharing, organization, user management, and security features in Frappe Vault.

## Table of Contents

- [Accessing Frappe Vault](#accessing-frappe-vault)
- [Managing Secrets](#managing-secrets)
- [Nested Folders & Organization](#nested-folders--organization)
- [Sharing Credentials & Subfolder Cascading](#sharing-credentials--subfolder-cascading)
- [One-Time Secure Links](#one-time-secure-links)
- [User Management & Onboarding](#user-management--onboarding)
- [User Settings & Appearance](#user-settings--appearance)
- [Security Dashboard & Password Generator](#security-dashboard--password-generator)
- [Browser Extension](#browser-extension)

## Accessing Frappe Vault

Frappe Vault provides two interfaces depending on your role:

- **Web Portal (`/vault`)**: Modern single-page application built for daily secret management without needing Frappe Desk access. Available to any user assigned the **Vault User** role.
- **Frappe Desk Workspace**: Accessible to **Vault Admin** users for administrative configuration, audit logs, and system policies.

## Managing Secrets

### Creating a Secret

1. Open the web interface at `/vault` (or go to **Vault Secret > New** in Desk).
2. Click **New Secret** and select the appropriate credential type:
   - **Password**: Store usernames, passwords, and live TOTP 2FA secret seeds.
   - **API Key**: Store API client IDs, API keys, tokens, and client secrets.
   - **SSH Key**: Store private and public SSH key pairs.
   - **Database**: Store connection credentials including host, port, database name, and password.
   - **Credit Card**: Store cardholder name, card number, expiration date, and CVV.
   - **Media / Attachment**: Securely attach certificates, private keys, or confidential files.
   - **Secure Note**: Store encrypted or sensitive rich-text / markdown notes.
3. Organize the secret by selecting a **Folder**, setting an optional **Expiration Date**, or marking it as a **Bookmark**.
4. Click **Save**.

### Viewing & Decrypting Secrets

- Passwords and sensitive fields remain masked by default.
- Click the eye icon or copy button to reveal or copy the decrypted value.
- Every decryption event is logged in the audit trail for security compliance.

## Nested Folders & Organization

Frappe Vault supports a hierarchical tree structure for structuring team credentials:

### Hierarchical Tree Structure
- **Root & Subfolders**: Create root-level folders or nest folders inside parents to reflect teams, environments, or projects (e.g. `Infrastructure` > `Production` > `Databases`).
- **Collapsible Sidebar Tree**: The left navigation pane renders a collapsible folder tree with persistent expand/collapse state.
- **Customizable Icons**: Choose distinct Lucide icons for each folder to quickly identify categories.
- **Folder Management & Deletion Safety**:
  - Edit folder names, icons, or re-parent folders in the tree.
  - When deleting a folder with subfolders, choose between moving subfolders up to the parent/root level, moving them to a specific folder, or deleting all descendants.

### Bookmarks & Quick Filters
- **Bookmarks**: Star frequently used credentials to keep them pinned at the top of your vault.
- **Search & Filters**: Quickly filter by secret type or folder, or search in real time by title and username.
- **Resizable Columns**: Drag list column borders to customize column widths; your layout preferences persist across sessions.

## Sharing Credentials & Subfolder Cascading

### Internal Sharing

Share secrets or entire folders with teammates:

1. Open the secret or folder and click **Share**.
2. Select whether to share with a specific **User** or a **Frappe Role** (e.g., *System Manager*, *HR User*).
3. Select the permission level:
   - **View Only**: Can view metadata and non-sensitive fields.
   - **View & Copy**: Can view and copy decrypted passwords/secrets.
   - **Edit**: Can modify secret details and credentials.
   - **Full Control**: Can edit, share, and delete the secret.
4. **Apply to Subfolders (Folder Sharing)**: When sharing a folder, check **Apply to Subfolders** to cascade the selected permission down to all nested subfolders and their secrets.
5. Optionally specify an **Expiration Date** after which access automatically revokes.

### Shared With Me

Navigate to the **Shared With Me** tab in the `/vault` portal to view credentials shared with your account or your roles.

## One-Time Secure Links

Need to securely send a password or credential to an external client, vendor, or contractor without giving them an account?

1. Open the secret and select **Share via Link**.
2. Configure the link parameters:
   - **Expiration Window**: Choose how long the link remains valid (e.g., 1 hour, 24 hours, 7 days).
   - **View Limit**: Restrict to 1 view (self-destructs after viewing) or allow multiple views.
   - **Passphrase**: Add an optional passphrase for extra protection.
3. Copy and share the generated link (`/vault/shared/<token>`).
4. Once the view limit is reached or the link expires, the token is automatically deactivated. Public access is rate-limited to prevent brute-force attacks.

## User Management & Onboarding

Vault Admins can manage team access directly from the web portal without opening Frappe Desk:

### Email Invitations
1. Open **Settings > User Management > Invite User**.
2. Enter one or more email addresses and select the intended role (**Vault User** or **Vault Admin**).
3. Click **Invite**. An email invitation with a secure onboarding link will be sent automatically.
4. When the invitee clicks the link, they are prompted to set their password and redirected straight into `/vault`.

### Managing Existing Users
- **Add Existing Users**: Quickly add existing Frappe/ERPNext users to Vault by granting them Vault roles.
- **Role Updates & Revocation**: Change user roles between Vault User and Vault Admin, or remove access with one click.
- **Email Account & Template Setup**: Configure custom outgoing email accounts and rich HTML email templates under **Settings > Email**.

## User Settings & Appearance

Users can customize their personal experience from the settings dialog:

- **Profile**: Update your first name, last name, and profile avatar.
- **Change Password**: Safely update your login password without leaving the Vault interface.
- **Appearance (Theme)**: Toggle between **Light**, **Dark**, or **System** themes.

## Security Dashboard & Password Generator

### Security Score & Health Audits

The `/vault` dashboard provides real-time visibility into your credential hygiene:
- **Security Score**: An overall health score calculated from password strength and rotation age.
- **Weak Passwords**: Flags weak or fair passwords that should be strengthened.
- **Stale Passwords**: Alerts you to credentials that haven't been rotated in over 90 days.

### Password Generator

Generate cryptographically secure passwords on the fly:
- Configurable length (8 to 128 characters).
- Toggle uppercase, lowercase, numbers, and symbols.
- Option to exclude ambiguous characters (e.g. `O`, `0`, `l`, `1`).

## Browser Extension

Frappe Vault has an official companion extension for Chrome, Brave, Edge, and other Chromium browsers:

- **Autofill & Domain Detection**: Automatically matches credentials to the active website and autofills login forms.
- **Live 2FA / TOTP**: View and copy two-factor verification codes with countdown timers right from your toolbar.
- **Quick Search & Hotkeys**: Press `Cmd+K` to search credentials or `Cmd+Shift+L` to autofill without leaving your tab.

Install from the [Chrome Web Store](https://chromewebstore.google.com/detail/frappe-vault/ljnpblaghkeddioeknlgcoolmomofjlj) or visit the [GitHub Repository](https://github.com/lubusIN/frappe-vault-browser-extension).
