"""Applying a rotated password to the Linux servers it belongs to.

The database counterpart of this module talks one protocol to one host. A Linux
credential is usually the same account spread across many machines — a service
account on twenty VMs — so this one drives Ansible over a whole inventory and
reports per host.

    ansible.builtin.user:
      name: <account>
      password: <sha512-crypt hash>

Who runs the change
-------------------
Never the account being rotated. Ansible connects as a separate automation user
over SSH key only — never a password, so no SSH credential for this account sits
in the vault waiting to be brute-forced or reused — and escalates with `become`.
Two things follow from that, and both matter:

  * changing the password cannot cut off the connection doing the changing, and
  * a rollback still works afterwards, because the credential that reaches the
    host was never the one that changed.

The database path cannot promise the second of those when it authenticates as
the account itself. Here it holds unconditionally.

All-or-nothing
--------------
A vault entry holds one password, so it cannot be true on eight hosts and stale
on two. Every host is reached and proved first; if any host then refuses the
change, the ones that took it are put back before anything is stored. The caller
only writes the new value once every host agrees on it.

Handling of the secret itself
-----------------------------
The hash never appears in a command line — `ps` is readable by every user on the
box — nor in Ansible's own output, which is why the task sets `no_log`. It is
written to a private file that this module deletes on the way out, whatever
happened.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass, field

import frappe
from frappe import _

# Ansible ships as a system package here rather than in the bench venv, so it is
# invoked as a subprocess rather than imported.
ANSIBLE_PLAYBOOK = "/usr/bin/ansible-playbook"

# A whole inventory has to finish inside this, or the rotation queue backs up.
PLAYBOOK_TIMEOUT_SECONDS = 600

# Per-host SSH connect timeout, kept well under the playbook budget.
SSH_TIMEOUT_SECONDS = 15

# How many hosts Ansible addresses at once.
DEFAULT_FORKS = 10


class LinuxApplyError(frappe.ValidationError):
    """The password could not be changed on one or more Linux hosts."""


@dataclass(frozen=True)
class LinuxTarget:
    """An account, and every machine it needs to be true on."""

    username: str
    hosts: tuple
    ansible_user: str
    ssh_private_key: str
    become_password: str | None = None
    use_become: bool = True
    strict_host_key_checking: bool = True
    ssh_port: int = 22

    def describe(self) -> str:
        """Non-sensitive summary for audit trails and operator messages."""
        shown = ", ".join(h["hostname"] for h in self.hosts[:3])
        if len(self.hosts) > 3:
            shown += f", +{len(self.hosts) - 3} more"
        return f"{self.username}@[{shown}] via {self.ansible_user}"


@dataclass
class HostOutcome:
    """What happened on one machine."""

    hostname: str
    ok: bool
    error: str = ""


@dataclass
class RunResult:
    """The outcome of one Ansible run across the inventory."""

    outcomes: list = field(default_factory=list)

    @property
    def failed(self) -> list:
        return [o for o in self.outcomes if not o.ok]

    @property
    def succeeded(self) -> list:
        return [o for o in self.outcomes if o.ok]

    @property
    def all_ok(self) -> bool:
        return bool(self.outcomes) and not self.failed

    def summary(self) -> str:
        if self.all_ok:
            return f"all {len(self.outcomes)} host(s) succeeded"
        parts = [f"{o.hostname}: {o.error or 'failed'}" for o in self.failed]
        return f"{len(self.failed)} of {len(self.outcomes)} host(s) failed — " + "; ".join(parts[:5])


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def make_linux_target(
    *,
    username: str,
    hosts,
    ansible_user: str,
    ssh_private_key: str,
    become_password: str | None = None,
    use_become: bool = True,
    strict_host_key_checking: bool = True,
    ssh_port=None,
) -> LinuxTarget:
    """Build a LinuxTarget from plain values, validating each one.

    Separate from `build_linux_target` so the same rules apply before a secret
    has been saved — the create dialog tests reachability from form values.
    """
    username = (username or "").strip()
    if not username:
        frappe.throw(
            _("Username is required — it names the account whose password is changed."), LinuxApplyError
        )

    ansible_user = (ansible_user or "").strip()
    if not ansible_user:
        frappe.throw(
            _("An Ansible user is required. It is the account Vault connects as to reach each host."),
            LinuxApplyError,
        )

    if ansible_user == username:
        # Rotating the very account Ansible authenticates as would work once and
        # then lock the automation out of every host in the inventory.
        frappe.throw(
            _(
                "The Ansible user cannot be the account being rotated ('{0}') — changing its password "
                "would lock Vault out of these hosts."
            ).format(username),
            LinuxApplyError,
        )

    if not ssh_private_key:
        frappe.throw(
            _("An SSH private key is required. Vault only connects to Linux hosts by key, never a password."),
            LinuxApplyError,
        )

    normalised = _normalise_hosts(hosts, default_port=frappe.utils.cint(ssh_port) or 22)
    if not normalised:
        frappe.throw(_("Add at least one host before applying a password to Linux servers."), LinuxApplyError)

    return LinuxTarget(
        username=username,
        hosts=tuple(normalised),
        ansible_user=ansible_user,
        ssh_private_key=ssh_private_key,
        become_password=become_password or None,
        use_become=bool(use_become),
        strict_host_key_checking=bool(strict_host_key_checking),
        ssh_port=frappe.utils.cint(ssh_port) or 22,
    )


def build_linux_target(doc) -> LinuxTarget:
    """Resolve a saved Vault Secret into a connectable LinuxTarget."""
    if doc.secret_type != "Linux Server":
        frappe.throw(_("Only secrets of type 'Linux Server' can be applied to Linux hosts."), LinuxApplyError)

    return make_linux_target(
        username=doc.username,
        hosts=[{"hostname": r.hostname, "ssh_port": r.ssh_port} for r in (doc.get("linux_hosts") or [])],
        ansible_user=doc.ansible_user,
        ssh_private_key=doc.get_password("ansible_ssh_private_key", raise_exception=False),
        become_password=doc.get_password("ansible_become_password", raise_exception=False),
        use_become=doc.ansible_use_become,
        strict_host_key_checking=doc.strict_host_key_checking,
        ssh_port=doc.ssh_port,
    )


def hash_password(plaintext: str) -> str:
    """SHA-512 crypt hash, the form `ansible.builtin.user` expects.

    The module refuses plaintext, which is the right call — a plaintext password
    in a playbook variable would end up in Ansible's fact cache and retry files.
    Python 3.13 removed `crypt`, so passlib does this rather than the stdlib.
    """
    from passlib.hash import sha512_crypt

    return sha512_crypt.using(rounds=5000).hash(plaintext)


def ping(target: LinuxTarget) -> RunResult:
    """Reach every host without changing anything.

    Run before a rotation so an unreachable machine is found while the stored
    password is still the true one everywhere, and backs the manual
    "Test Connection" action.
    """
    return _run(target, _PING_PLAY, extra_vars={"vault_target_user": target.username})


def apply_password(target: LinuxTarget, new_password: str) -> RunResult:
    """Set `target.username`'s password on every host in the inventory."""
    if not new_password:
        frappe.throw(_("Refusing to set an empty password on a Linux host."), LinuxApplyError)

    return _run(
        target,
        _SET_PASSWORD_PLAY,
        extra_vars={
            "vault_target_user": target.username,
            "vault_password_hash": hash_password(new_password),
        },
    )


def apply_password_to_hosts(target: LinuxTarget, new_password: str, hostnames: list) -> RunResult:
    """Set the password on a named subset of hosts — used to undo a partial run."""
    from dataclasses import replace

    subset = tuple(h for h in target.hosts if h["hostname"] in set(hostnames))
    if not subset:
        return RunResult()

    return apply_password(replace(target, hosts=subset), new_password)


# ----------------------------------------------------------------------
# Playbooks
# ----------------------------------------------------------------------

_PING_PLAY = """
- hosts: all
  gather_facts: false
  tasks:
    - name: Reach the host
      ansible.builtin.ping:
    - name: Confirm privilege escalation works for the account to rotate
      # passwd -S is read-only — it queries password status, changes nothing
      # — and is one of the exact commands the setup instructions this app
      # gives scope `become` access to (usermod, passwd). Checking with
      # anything else, id -u included, fails on a properly scoped sudoers
      # rule even though rotation itself would have worked fine: sudo refuses
      # a command that is not on the rule's list, which is not the same thing
      # as become being broken.
      ansible.builtin.command: passwd -S {{ vault_target_user }}
      become: "{{ vault_use_become }}"
      changed_when: false
"""

# `update_password: always` is what makes this idempotent in the sense we need:
# the module would otherwise leave an existing password alone.
_SET_PASSWORD_PLAY = """
- hosts: all
  gather_facts: false
  tasks:
    - name: Set the account password
      ansible.builtin.user:
        name: "{{ vault_target_user }}"
        password: "{{ vault_password_hash }}"
        update_password: always
      become: "{{ vault_use_become }}"
      no_log: true
"""


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _normalise_hosts(hosts, default_port: int) -> list:
    """Accept rows or plain strings, and drop blanks and duplicates."""
    seen, out = set(), []
    for entry in hosts or []:
        if isinstance(entry, str):
            hostname, port = entry.strip(), default_port
        else:
            hostname = (entry.get("hostname") or "").strip()
            port = frappe.utils.cint(entry.get("ssh_port")) or default_port

        if not hostname or hostname in seen:
            continue
        seen.add(hostname)
        out.append({"hostname": hostname, "ssh_port": port})

    return out


def _run(target: LinuxTarget, playbook: str, extra_vars: dict) -> RunResult:
    """Run one playbook over the inventory and return a per-host outcome.

    Everything sensitive lives in files inside a private directory that is
    removed in `finally`, so nothing survives the call and nothing reaches a
    command line.
    """
    if not os.path.exists(ANSIBLE_PLAYBOOK):
        frappe.throw(
            _("Ansible is not installed on this server; expected {0}.").format(ANSIBLE_PLAYBOOK),
            LinuxApplyError,
        )

    workdir = tempfile.mkdtemp(prefix="vault-linux-")
    os.chmod(workdir, stat.S_IRWXU)  # 0700

    try:
        play_path = _write_private(workdir, "play.yml", playbook)
        inventory_path = _write_private(workdir, "inventory.ini", _build_inventory(target, workdir))

        variables = dict(extra_vars)
        variables["vault_use_become"] = bool(target.use_become)
        vars_path = _write_private(workdir, "vars.json", json.dumps(variables))

        completed = subprocess.run(  # noqa: S603 — fixed binary, no shell
            [
                ANSIBLE_PLAYBOOK,
                "-i",
                inventory_path,
                play_path,
                "--extra-vars",
                f"@{vars_path}",
                "--forks",
                str(DEFAULT_FORKS),
            ],
            capture_output=True,
            text=True,
            timeout=PLAYBOOK_TIMEOUT_SECONDS,
            env=_build_env(target, workdir),
            cwd=workdir,
        )

        return _parse_result(target, completed)

    except subprocess.TimeoutExpired:
        frappe.throw(
            _("Ansible did not finish within {0} seconds against {1} host(s).").format(
                PLAYBOOK_TIMEOUT_SECONDS, len(target.hosts)
            ),
            LinuxApplyError,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _write_private(workdir: str, name: str, content: str) -> str:
    """Write a file only this user can read."""
    path = os.path.join(workdir, name)
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w") as fh:
        fh.write(content)
    return path


def _build_inventory(target: LinuxTarget, workdir: str) -> str:
    """An INI inventory carrying the connection settings.

    Connection secrets go here rather than on the command line: the inventory is
    0600 and deleted afterwards, whereas an argument is visible in `ps` to every
    user on this machine for as long as the process runs.
    """
    lines = ["[vault_targets]"]
    for host in target.hosts:
        lines.append(f"{host['hostname']} ansible_port={host['ssh_port']}")

    lines += [
        "",
        "[vault_targets:vars]",
        f"ansible_user={target.ansible_user}",
        "ansible_connection=ssh",
        f"ansible_ssh_common_args=-o ConnectTimeout={SSH_TIMEOUT_SECONDS}",
    ]

    lines.append(f"ansible_ssh_private_key_file={os.path.join(workdir, 'id_key')}")

    if target.use_become:
        lines.append("ansible_become=true")
        lines.append("ansible_become_method=sudo")
        if target.become_password:
            lines.append(f"ansible_become_password={target.become_password}")

    _write_key(workdir, target.ssh_private_key)

    return "\n".join(lines) + "\n"


def _write_key(workdir: str, private_key: str):
    """Drop the SSH key into the private working directory.

    OpenSSH refuses a key file readable by anyone else, and rejects one whose
    final newline is missing, which is easy to lose when a key is pasted into a
    web form.
    """
    material = (private_key or "").strip() + "\n"
    _write_private(workdir, "id_key", material)


def _build_env(target: LinuxTarget, workdir: str) -> dict:
    """Environment for the Ansible run."""
    env = dict(os.environ)
    env.update(
        {
            "ANSIBLE_STDOUT_CALLBACK": "json",
            "ANSIBLE_LOAD_CALLBACK_PLUGINS": "1",
            # Retry files and fact caches would outlive the working directory.
            "ANSIBLE_RETRY_FILES_ENABLED": "0",
            "ANSIBLE_CACHE_PLUGIN": "memory",
            "ANSIBLE_LOCAL_TEMP": os.path.join(workdir, "tmp"),
            "ANSIBLE_HOST_KEY_CHECKING": "True" if target.strict_host_key_checking else "False",
            "ANSIBLE_NOCOLOR": "1",
            "ANSIBLE_DEPRECATION_WARNINGS": "0",
        }
    )
    return env


def _parse_result(target: LinuxTarget, completed) -> RunResult:
    """Turn Ansible's JSON output into one outcome per host.

    Ansible's exit status only says "something went wrong somewhere", which is
    useless when the whole point is knowing *which* machines are now out of step.
    """
    result = RunResult()

    try:
        report = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        # No parseable output means the run never got as far as contacting hosts
        # — bad inventory, missing collection, unreadable key.
        reason = (
            _first_line(completed.stderr) or _first_line(completed.stdout) or "Ansible produced no output"
        )
        frappe.throw(_("Ansible could not run — {0}").format(reason), LinuxApplyError)

    stats = report.get("stats") or {}
    if not stats:
        reason = _first_line(completed.stderr) or "no hosts were contacted"
        frappe.throw(_("Ansible reached no hosts — {0}").format(reason), LinuxApplyError)

    messages = _failure_messages(report)

    for host in target.hosts:
        name = host["hostname"]
        counters = stats.get(name) or {}
        bad = counters.get("failures", 0) or counters.get("unreachable", 0)
        result.outcomes.append(
            HostOutcome(
                hostname=name,
                ok=not bad and counters.get("ok", 0) > 0,
                error=messages.get(name, "") if bad else "",
            )
        )

    return result


def _failure_messages(report: dict) -> dict:
    """Map hostname to the first failure message Ansible reported for it."""
    messages = {}
    for play in report.get("plays") or []:
        for task in play.get("tasks") or []:
            for hostname, outcome in (task.get("hosts") or {}).items():
                if hostname in messages:
                    continue
                if outcome.get("failed") or outcome.get("unreachable"):
                    messages[hostname] = _clean(outcome)
    return messages


def _clean(outcome: dict) -> str:
    """One readable line from a task result, with no secret in it."""
    text = outcome.get("msg") or outcome.get("stderr") or outcome.get("stdout") or "failed"
    return str(text).strip().splitlines()[0][:200] if str(text).strip() else "failed"


def _first_line(text: str) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return lines[0][:200] if lines else ""
