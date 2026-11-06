# Rotation Setup

How to prepare Linux servers and databases so that Frappe Vault can change their passwords automatically.

## Table of Contents

- [Linux Servers (Ansible)](#linux-servers-ansible)
  - [How It Works](#how-it-works)
  - [Add a Server](#add-a-server)
  - [Troubleshooting](#troubleshooting)
- [Databases](#databases)
  - [How It Works](#how-it-works-1)
  - [PostgreSQL](#postgresql)
  - [MySQL / MariaDB](#mysql--mariadb)
  - [Create the Secret in Vault](#create-the-secret-in-vault)

In the examples below, `<frappe-host-ip>` is the address that the Frappe server uses to connect to targets.

## Linux Servers (Ansible)

### How It Works

Vault runs a short Ansible playbook from the Frappe server to change a Linux account's password on one or more hosts.

- Ansible connects as a separate automation account, `vault-rotate`, with an SSH key stored in the secret.
- Each run uses a temporary working folder with mode 0700. The folder holds the inventory, the playbook and a vars file in which every value is marked `!unsafe`.
- If one host fails, Vault changes the hosts that already succeeded back to the old password, and keeps the old password.

Install Ansible on the Frappe server (`sudo apt install ansible`). The JSON output callback comes from the `ansible.posix` collection.

> [!NOTE]
> **Why the account has full sudo.** Ansible's `become` runs `/bin/sh -c 'python3 …'` as root. It does not run `usermod` directly. A sudoers rule limited to `usermod` or `passwd` therefore makes every run fail. The account gets `NOPASSWD: ALL` and is restricted in other ways: key login only, accepted only from the Frappe server, and no forwarding.

### Add a Server

**1. Prepare the server.** Run this as root on the target. Set `PUBKEY` to the public key of the private key you will store in Vault. To get the public key from the private key, use `ssh-keygen -y -f <keyfile>`.

```bash
sudo bash -s <<'SETUP'
set -euo pipefail
U=vault-rotate
CONTROL_IP=<frappe-host-ip>
PUBKEY='ssh-ed25519 AAAA… vault-rotate (Frappe Vault Linux rotation)'
command -v python3 >/dev/null || { apt-get update -qq && apt-get install -y -qq python3; }
id "$U" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash --comment "Frappe Vault rotation (Ansible)" "$U"
usermod -p '*' "$U"
install -d -m 700 -o "$U" -g "$U" "/home/$U/.ssh"
echo "from=\"$CONTROL_IP\",no-agent-forwarding,no-port-forwarding,no-X11-forwarding $PUBKEY" > "/home/$U/.ssh/authorized_keys"
chown "$U:$U" "/home/$U/.ssh/authorized_keys"; chmod 600 "/home/$U/.ssh/authorized_keys"
echo "$U ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/90-vault-rotate
chmod 440 /etc/sudoers.d/90-vault-rotate
visudo -cf /etc/sudoers.d/90-vault-rotate
SETUP
```

`usermod -p '*'` locks password login for `vault-rotate`, so only the key works.

**2. Record the server's host key.** Do this on the Frappe server as the `frappe` user. Do it once per server, not once per secret. First, read the real fingerprint on the server itself with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Then:

```bash
ssh-keyscan -t ed25519 <server-ip> | tee /tmp/hk | ssh-keygen -lf -   # compare the fingerprints
cat /tmp/hk >> ~/.ssh/known_hosts && rm /tmp/hk
```

If you clone VMs from a template, make new host keys on each clone first: `sudo rm /etc/ssh/ssh_host_* && sudo dpkg-reconfigure openssh-server`.

**3. Create or edit the secret** in Vault:

| Field | Value |
|---|---|
| Type | Linux Server |
| Username / Password | The account to rotate and its current password |
| Hosts | One or more hostnames or IP addresses |
| Ansible User | `vault-rotate` |
| SSH Private Key | The private key that matches `PUBKEY` |
| Use sudo | On, with the sudo password blank |
| Strict host key checking | On |

**4. Test.** Click **Test Connection**, then **Rotate Now** once. Then turn on automatic rotation with a suitable interval. For service accounts, use weeks, not hours.

### Troubleshooting

| Symptom | Check |
|---|---|
| Host unreachable or host key failed | As `frappe` on the Frappe server, run `ssh -o StrictHostKeyChecking=yes vault-rotate@<ip>`. The host key must be in `~/.ssh/known_hosts`. |
| sudo refused | The sudoers file must be `NOPASSWD: ALL`, not a list of commands. |
| Input rejected | Hosts must be a hostname or an IP address. Account names must be valid Linux usernames. Ports must be 1–65535. This is intentional injection protection. |

## Databases

### How It Works

1. Vault logs in as a **rotation admin** and changes the app account's password.
2. Vault logs in **as the app account**, from the Frappe server, to prove the new password works.
3. If that login fails, Vault puts the old password back.

Three rules follow from this:

- A rotation admin account is necessary when automatic rotation is on. Vault never rotates the admin's own password.
- The app account must accept logins from `<frappe-host-ip>`, not only from its application server.
- MySQL only: the username must exist under exactly one host. If it exists under more than one, rotation stops instead of guessing.

### PostgreSQL

As a superuser in `psql`:

```sql
CREATE ROLE vault_rot_admin WITH LOGIN CREATEROLE PASSWORD 'strong-admin-password';
GRANT app_user TO vault_rot_admin WITH ADMIN OPTION;   -- PostgreSQL 16+ only, once for each rotated role
ALTER ROLE app_user WITH LOGIN;
GRANT CONNECT ON DATABASE appdb TO app_user;
ALTER ROLE vault_rot_admin SET log_statement = 'none'; -- keep ALTER ROLE … PASSWORD out of the logs
```

In `pg_hba.conf`, put these lines above the broader `host` lines, then reload PostgreSQL:

```
host  all  vault_rot_admin  <frappe-host-ip>/32  scram-sha-256
host  all  app_user         <frappe-host-ip>/32  scram-sha-256
```

- Only a superuser can change a superuser role such as `postgres`. Do not rotate superuser roles with this admin.
- Port 5432 must be reachable from the Frappe server.

### MySQL / MariaDB

As an admin:

```sql
SELECT User, Host FROM mysql.user WHERE User = 'app_user';          -- must return exactly one row
RENAME USER 'app_user'@'10.0.0.5' TO 'app_user'@'<allowed-network>'; -- only if its host excludes the Frappe server

CREATE USER 'vault_rot_admin'@'<frappe-host-ip>' IDENTIFIED BY 'strong-admin-password';
GRANT CREATE USER ON *.* TO 'vault_rot_admin'@'<frappe-host-ip>';
GRANT SELECT ON mysql.user TO 'vault_rot_admin'@'<frappe-host-ip>';
```

- `CREATE USER` is a powerful privilege. For this reason the admin accepts connections from one address only.
- Keep the general query log off in production. It records `ALTER USER … IDENTIFIED BY` in clear text.
- `bind-address` must allow remote connections, and port 3306 must be reachable from the Frappe server.

### Create the Secret in Vault

| Field | Value |
|---|---|
| Type / Database Type | Database / PostgreSQL or MySQL / MariaDB |
| Host, Port | The database server address, 5432 or 3306 |
| Database Name | PostgreSQL: a database the app role can connect to (blank means `postgres`). MySQL: usually blank. |
| Username / Password | The app account and its current password |
| Use SSL | On when the server supports TLS |
| Automatic Rotation | On, with an interval (for example 30 days) |
| Rotation Admin | `vault_rot_admin` and its password |

Then:

1. Click **Test Connection**, then **Create**.
2. Click **Rotate Now** once.
3. Make sure that the new password logs in and the old one is refused.
4. Before the next rotation, change the applications that use the account so that they read the password from Vault or HashiCorp.
