# HashiCorp Setup

How to connect Frappe Vault to HashiCorp Vault for KV sync and Transit encryption. For the reasons behind this design, see [Security Architecture](security-architecture.md#why-hashicorp-transit).

## Table of Contents

- [Before You Start](#before-you-start)
- [1. AppRole for Frappe](#1-approle-for-frappe)
- [2. Transit Engine, Key and Policy](#2-transit-engine-key-and-policy)
- [3. Turn On Transit for the Site](#3-turn-on-transit-for-the-site)
- [4. Audit Device and Log Rotation](#4-audit-device-and-log-rotation)
- [Resulting Layout](#resulting-layout)

## Before You Start

- HashiCorp Vault is installed, initialized and unsealed.
- A KV v2 engine is mounted at `kv/`. If it is not, run `vault secrets enable -path=kv kv-v2`.
- You have an admin token. Type it into the shell. Do not paste it into chat, tickets or files, and do not use the root token for daily work.

```bash
export VAULT_ADDR=http://127.0.0.1:8200   # use https:// when HashiCorp has TLS
read -rs VAULT_TOKEN && export VAULT_TOKEN
```

## 1. AppRole for Frappe

Frappe logs in with AppRole. Its tokens last one hour. The two policies below are all the access it has.

```bash
vault auth enable approle

vault policy write frappe-vault-sync - <<'EOF'
path "kv/data/frappe-vault/*" { capabilities = ["create", "update", "read"] }
EOF

vault write auth/approle/role/frappe-vault \
  token_policies="frappe-vault-sync,frappe-vault-transit" \
  token_ttl=1h token_max_ttl=4h

vault read  -field=role_id      auth/approle/role/frappe-vault/role-id
vault write -f -field=secret_id auth/approle/role/frappe-vault/secret-id
```

In **Vault Settings → HashiCorp Vault**, set:

| Field | Value |
|---|---|
| Enable | On |
| URL | `http://127.0.0.1:8200` (or the HashiCorp address) |
| Auth Method | AppRole |
| Role ID / Secret ID | The values from the commands above |
| KV Mount | `kv` |
| Path Prefix | `frappe-vault` |
| Auto-sync on Password Change / Rotation | On, if secrets marked "Sync to HashiCorp Vault" must stay current |

Click **Save**. The setting is only stored when the form is saved, so do this even if the defaults look correct.

## 2. Transit Engine, Key and Policy

```bash
vault secrets enable transit

vault write -f transit/keys/frappe-vault-secrets type=aes256-gcm96
vault write transit/keys/frappe-vault-secrets/config \
  exportable=false deletion_allowed=false auto_rotate_period=2160h

vault policy write frappe-vault-transit - <<'EOF'
path "transit/encrypt/frappe-vault-secrets" { capabilities = ["update"] }
path "transit/decrypt/frappe-vault-secrets" { capabilities = ["update"] }
EOF
```

- `exportable=false`: the key can never be read out of HashiCorp.
- `deletion_allowed=false`: the key cannot be deleted by mistake. Deleting it would make every secret unrecoverable.
- `auto_rotate_period=2160h`: a new key version every 90 days.

## 3. Turn On Transit for the Site

This setting is in `site_config.json` on purpose, so it cannot be switched off from the web UI.

```bash
cd ~/frappe-bench
bench --site <site> set-config vault_transit_key frappe-vault-secrets
# optional, when the engine is not mounted at transit/:
# bench --site <site> set-config vault_transit_mount <mount>
sudo supervisorctl restart all
```

Then convert the values that were stored before Transit was on. Do a dry run first:

```bash
bench --site <site> execute frappe_vault.integrations.transit.rewrap_existing --kwargs "{'dry_run': True}"
bench --site <site> execute frappe_vault.integrations.transit.rewrap_existing --kwargs "{'dry_run': False}"
```

Check the result. This decrypts each stored value with the Frappe site key only, which is what an attacker with a database dump and `site_config.json` can do:

```bash
bench --site <site> execute frappe_vault.integrations.transit.verify_protection
```

Expect `"plaintext": 0`. The command prints counts and field names, never values.

## 4. Audit Device and Log Rotation

```bash
sudo install -d -m 750 -o vault -g vault /var/log/vault
vault audit enable file file_path=/var/log/vault/audit.log
vault audit list
```

Rotate the log, for example in `/etc/logrotate.d/vault-audit`:

```
/var/log/vault/audit.log {
    daily
    maxsize 100M
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 vault vault
    postrotate
        systemctl reload vault >/dev/null 2>&1 || true
    endscript
}
```

> [!WARNING]
> HashiCorp refuses every request it cannot audit. If the only audit device cannot write, for example because the disk is full, all reveals, saves and rotations stop. Watch disk space, send the log to a separate store, and consider a second audit device.

## Resulting Layout

| Item | Value |
|---|---|
| Auth method for Frappe | `approle`, role `frappe-vault` |
| Policies | `frappe-vault-sync` (KV), `frappe-vault-transit` (encrypt/decrypt) |
| Transit key | `frappe-vault-secrets`: AES-256-GCM, not exportable, not deletable, rotates every 90 days |
| KV copies | `kv/frappe-vault/<secret id>`, only for secrets with "Sync to HashiCorp Vault" on |
| Audit | File device at `/var/log/vault/audit.log` |
| Site config | `vault_transit_key` (and optionally `vault_transit_mount`) |
