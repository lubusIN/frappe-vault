# Operations

Runbooks, backup and recovery for a Frappe Vault site that uses HashiCorp Transit. Replace `<site>` with the site name.

## Table of Contents

- [Runbooks](#runbooks)
- [When HashiCorp Is Down or Sealed](#when-hashicorp-is-down-or-sealed)
- [Backup and Recovery](#backup-and-recovery)
- [Hardening Checklist](#hardening-checklist)

## Runbooks

### Check Transit protection

```bash
bench --site <site> execute frappe_vault.integrations.transit.verify_protection
```

Expect `"plaintext": 0`. If the count is not zero, run `rewrap_existing` (see [HashiCorp Setup](hashicorp-setup.md#3-turn-on-transit-for-the-site)).

### See who decrypted what

```bash
sudo grep -c 'transit/decrypt/frappe-vault-secrets' /var/log/vault/audit.log
```

In the app, the Audit Log view shows Viewed, Shared, Rotated and Settings Changed events.

### Rotate the Transit key now

```bash
vault write -f transit/keys/frappe-vault-secrets/rotate
```

Old key versions still decrypt. When convenient, rewrap the stored values to the newest version.

### Stop all decryption (incident)

```bash
vault write auth/approle/role/frappe-vault/secret-id-accessor/destroy \
  secret_id_accessor=<accessor>
# or remove the role completely:
vault delete auth/approle/role/frappe-vault
```

Vault stops revealing and saving secrets at once. The records are not changed. To restore service, issue a new Secret ID and enter it in Vault Settings.

### Deploy an app update

```bash
bench --site <site> backup
cd apps/frappe_vault && git pull
cd ../.. && bench build --app frappe_vault
bench --site <site> migrate
sudo supervisorctl restart all
```

### Merge a new upstream release

```bash
cd apps/frappe_vault
git fetch lubus            # remote for https://github.com/lubusIN/frappe-vault
git merge lubus/main       # resolve conflicts, run the tests, then deploy
```

Run the tests before you deploy:

```bash
bench --site <test-site> run-tests --app frappe_vault
```

## When HashiCorp Is Down or Sealed

Vault records still list and open. Revealing, saving secrets, one-time links and rotation return "HashiCorp Vault is unreachable". Start or unseal HashiCorp; you do not need to repair anything in Frappe afterwards.

## Backup and Recovery

> [!CAUTION]
> **You need both halves.** With Transit on, Frappe backups contain only Transit ciphertext. Without HashiCorp's storage and unseal keys, every secret is unrecoverable.

| What | Where | How |
|---|---|---|
| Frappe site | `sites/<site>/private/backups` | `bench --site <site> backup --with-files`, copied off the server |
| Site config (contains the site encryption key) | `sites/<site>/site_config.json` | Copy it with the backup, but store it separately |
| HashiCorp storage | The storage path in the HashiCorp config (for example `/opt/vault/data`) | Stop HashiCorp or take a consistent snapshot, then copy it off the server, encrypted |
| HashiCorp unseal keys | Named custodians | Split across people. Never store them on the Frappe or HashiCorp server. |
| HashiCorp audit log | `/var/log/vault/` | Send to a separate log store (syslog or similar) |

Before you rely on the backups, restore both halves together on a separate machine and test them.

## Hardening Checklist

- [ ] Revoke the root token after setup. Use a scoped admin token for daily work.
- [ ] Run HashiCorp on its own host, with TLS and separate administrators.
- [ ] Use a firewall. Allow only 80/443 to the public. Allow SSH and the HashiCorp port only from admin addresses and the Frappe server.
- [ ] Send the HashiCorp audit log and the Frappe logs to a separate store. Watch disk space.
- [ ] Back up HashiCorp storage and the unseal keys. Test a restore.
- [ ] Keep System Manager for break-glass accounts only.
- [ ] Use SSH keys only (`PasswordAuthentication no`, `PermitRootLogin no`).
- [ ] Turn on strict host key checking on every Linux rotation secret.
- [ ] When HashiCorp uses HTTPS, turn on TLS verification in Vault Settings.
