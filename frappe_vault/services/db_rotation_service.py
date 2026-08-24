"""Applying a rotated password to the live database it belongs to.

Rotation on its own only changes the value *stored in the vault* — the target
system keeps the old credential until somebody applies it by hand. A Database
secret with `apply_rotation_to_target` enabled closes that gap: this module
connects to the real server and runs the engine's password-change statement, so
the vault and the database stay in sync automatically.

Three engines are supported, matching the `database_type` field:

    PostgreSQL       -> ALTER ROLE ... WITH PASSWORD ...
    MySQL / MariaDB  -> ALTER USER ... IDENTIFIED BY ...
    MongoDB          -> db.runCommand({updateUser: ..., pwd: ...})

Who runs the change
-------------------
By default the secret's own account authenticates and changes its own password,
so no extra privileged credential has to live in the vault. When the account
cannot do that — a MongoDB user without `changeOwnPassword`, a locked-down
Postgres role — the secret may name a `rotation_admin_username` /
`rotation_admin_password` that is used to connect instead. That admin credential
is never itself rotated.

Ordering guarantee
------------------
The caller applies to the target *before* storing the new value in the vault, so
a target that refuses the change leaves the stored password untouched and the two
in sync. For the narrow window where the target accepted the change but the vault
write then failed, the caller re-applies the previous password — see
`_undo_target_apply` in background_jobs/password_rotation.py.
"""

from dataclasses import dataclass, replace

import frappe
from frappe import _

POSTGRESQL = "PostgreSQL"
MYSQL = "MySQL / MariaDB"
MONGODB = "MongoDB"

SUPPORTED_DATABASE_TYPES = (POSTGRESQL, MYSQL, MONGODB)

DEFAULT_PORTS = {
    POSTGRESQL: 5432,
    MYSQL: 3306,
    MONGODB: 27017,
}

# Never let an unreachable host wedge the hourly rotation queue.
CONNECT_TIMEOUT_SECONDS = 10


class TargetApplyError(frappe.ValidationError):
    """The password could not be changed on the target database."""


@dataclass(frozen=True)
class Target:
    """Everything needed to reach one database account, resolved from a secret."""

    database_type: str
    host: str
    port: int
    database: str | None
    username: str
    use_ssl: bool
    auth_source: str
    # Credentials used to *run* the change — the account itself, or an admin.
    auth_username: str
    auth_password: str
    via_admin: bool


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def make_target(
    *,
    database_type: str,
    host: str,
    username: str,
    port=None,
    database: str | None = None,
    use_ssl: bool = False,
    auth_source: str | None = None,
    admin_username: str | None = None,
    admin_password: str | None = None,
    current_password: str | None = None,
) -> Target:
    """Build a Target from plain values, validating each one.

    Kept separate from `build_target` so the same rules apply to a secret that
    has not been saved yet — the create dialog tests a connection from form
    values, before there is any document to read.

    `admin_username`/`admin_password` authenticate when given; otherwise the
    account authenticates as itself using `current_password`.
    """
    database_type = (database_type or "").strip()
    if database_type not in SUPPORTED_DATABASE_TYPES:
        frappe.throw(
            _("Set a supported Database Type ({0}) before applying a password to the server.").format(
                ", ".join(SUPPORTED_DATABASE_TYPES)
            ),
            TargetApplyError,
        )

    host = (host or "").strip()
    if not host:
        frappe.throw(_("Host is required to apply a password to the database server."), TargetApplyError)

    username = (username or "").strip()
    if not username:
        frappe.throw(
            _("Username is required — it names the account whose password is changed."), TargetApplyError
        )

    admin_username = (admin_username or "").strip()
    if admin_username:
        if not admin_password:
            frappe.throw(
                _("A Rotation Admin Username is set but its password could not be retrieved."),
                TargetApplyError,
            )
        auth_username, auth_password = admin_username, admin_password
    else:
        if not current_password:
            frappe.throw(
                _(
                    "The current database password could not be retrieved, so there is no way to "
                    "authenticate. Set a Rotation Admin Username instead."
                ),
                TargetApplyError,
            )
        auth_username, auth_password = username, current_password

    return Target(
        database_type=database_type,
        host=host,
        port=frappe.utils.cint(port) or DEFAULT_PORTS[database_type],
        database=(database or "").strip() or None,
        username=username,
        use_ssl=bool(use_ssl),
        auth_source=(auth_source or "").strip() or "admin",
        auth_username=auth_username,
        auth_password=auth_password,
        via_admin=bool(admin_username),
    )


def build_target(doc, current_password: str) -> Target:
    """Resolve a saved Vault Secret into a connectable Target.

    `current_password` is the secret's password as it stands *before* rotation;
    it authenticates the self-service path.
    """
    if doc.secret_type != "Database":
        frappe.throw(
            _("Only secrets of type 'Database' can be applied to a database server."), TargetApplyError
        )

    return make_target(
        database_type=doc.database_type,
        host=doc.db_host,
        port=doc.db_port,
        database=doc.db_name,
        username=doc.username,
        use_ssl=doc.db_use_ssl,
        auth_source=doc.db_auth_source,
        admin_username=doc.rotation_admin_username,
        admin_password=doc.get_password("rotation_admin_password", raise_exception=False),
        current_password=current_password,
    )


def apply_password(target: Target, new_password: str) -> None:
    """Change `target.username`'s password on the live server to `new_password`.

    Raises TargetApplyError with an operator-readable reason on any failure.
    The exception message never contains either password.
    """
    if not new_password:
        frappe.throw(_("Refusing to set an empty password on a database server."), TargetApplyError)

    _handler_for(target.database_type)(target, new_password)


def verify_credentials(target: Target, password: str) -> None:
    """Confirm `target.username` can authenticate with `password`.

    Used to prove a rotation actually took effect, and to back the manual
    "Test Connection" action. Always authenticates as the account itself,
    never as the admin, so it tests the credential that was just changed.
    """
    probe = replace(target, auth_username=target.username, auth_password=password, via_admin=False)
    _verifier_for(target.database_type)(probe)


def verify_admin_credentials(target: Target) -> None:
    """Confirm the configured rotation admin can authenticate.

    Separate from `verify_credentials`, which always tests the rotated account.
    A rotation admin whose own password has drifted would fail the whole
    rotation, so it is worth proving reachable ahead of time.
    """
    if not target.via_admin:
        return

    _verifier_for(target.database_type)(target)


def account_exists(target: Target) -> bool | None:
    """Whether `target.username` exists on the server, as far as we can tell.

    Returns None when the connecting account lacks the privilege to look —
    "cannot tell" is a genuinely different answer from "does not exist", and
    only the latter is worth blocking a save over.

    Connects as whoever `target` authenticates as, so in practice this runs as
    the rotation admin during the pre-save check.
    """
    return _EXISTENCE_PROBES[target.database_type](target)


def describe(target: Target) -> str:
    """Short, non-sensitive description of what was contacted, for audit trails."""
    via = f" as {target.auth_username}" if target.via_admin else ""
    return f"{target.database_type} {target.host}:{target.port} user={target.username}{via}"


# ----------------------------------------------------------------------
# PostgreSQL
# ----------------------------------------------------------------------


def _postgres_connect(target: Target, user: str, password: str):
    try:
        import psycopg2
    except ImportError:
        frappe.throw(
            _("The 'psycopg2' package is not installed; run: bench pip install psycopg2-binary"),
            TargetApplyError,
        )

    try:
        return psycopg2.connect(
            host=target.host,
            port=target.port,
            dbname=target.database or "postgres",
            user=user,
            password=password,
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            sslmode="require" if target.use_ssl else "prefer",
        )
    except Exception as e:
        frappe.throw(
            _("Could not connect to PostgreSQL at {0}:{1} — {2}").format(target.host, target.port, _clean(e)),
            TargetApplyError,
        )


def _postgres_apply(target: Target, new_password: str):
    from psycopg2 import sql

    conn = _postgres_connect(target, target.auth_username, target.auth_password)
    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            # sql.Identifier/Literal quote both halves, so a role name or password
            # containing quotes cannot break out of the statement.
            cursor.execute(
                sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                    sql.Identifier(target.username), sql.Literal(new_password)
                )
            )
    except Exception as e:
        frappe.throw(
            _("PostgreSQL refused the password change for role '{0}' — {1}").format(
                target.username, _clean(e)
            ),
            TargetApplyError,
        )
    finally:
        _close(conn)


def _postgres_verify(target: Target):
    _close(_postgres_connect(target, target.auth_username, target.auth_password))


def _postgres_account_exists(target: Target) -> bool | None:
    conn = _postgres_connect(target, target.auth_username, target.auth_password)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (target.username,))
            return cursor.fetchone() is not None
    except Exception:
        return None
    finally:
        _close(conn)


# ----------------------------------------------------------------------
# MySQL / MariaDB
# ----------------------------------------------------------------------


def _mysql_connect(target: Target, user: str, password: str):
    try:
        import pymysql
    except ImportError:
        frappe.throw(
            _("The 'pymysql' package is not installed; run: bench pip install pymysql"), TargetApplyError
        )

    kwargs = {
        "host": target.host,
        "port": target.port,
        "user": user,
        "password": password,
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "read_timeout": CONNECT_TIMEOUT_SECONDS,
        "write_timeout": CONNECT_TIMEOUT_SECONDS,
        "charset": "utf8mb4",
    }
    if target.database:
        kwargs["database"] = target.database
    if target.use_ssl:
        # No CA configured, so pymysql negotiates TLS without verifying the peer.
        # That still defeats passive interception of the new password on the wire,
        # which is the point here; supply a CA on the server side for full checks.
        kwargs["ssl"] = {"ca": None}

    try:
        return pymysql.connect(**kwargs)
    except Exception as e:
        frappe.throw(
            _("Could not connect to MySQL/MariaDB at {0}:{1} — {2}").format(
                target.host, target.port, _clean(e)
            ),
            TargetApplyError,
        )


def _mysql_apply(target: Target, new_password: str):
    conn = _mysql_connect(target, target.auth_username, target.auth_password)
    try:
        with conn.cursor() as cursor:
            if target.via_admin:
                host_part = _mysql_account_host(cursor, target.username)
                statement = "ALTER USER %s@%s IDENTIFIED BY %s"
                args = (target.username, host_part, new_password)
            else:
                # CURRENT_USER() sidesteps the user@host ambiguity entirely.
                statement = "ALTER USER CURRENT_USER() IDENTIFIED BY %s"
                args = (new_password,)

            try:
                cursor.execute(statement, args)
            except Exception as e:
                if not _is_mysql_syntax_error(e):
                    raise
                # MariaDB before 10.2 has no ALTER USER ... IDENTIFIED BY.
                _mysql_apply_legacy(cursor, target, new_password)

        conn.commit()
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.throw(
            _("MySQL/MariaDB refused the password change for '{0}' — {1}").format(target.username, _clean(e)),
            TargetApplyError,
        )
    finally:
        _close(conn)


def _mysql_apply_legacy(cursor, target: Target, new_password: str):
    """Pre-10.2 MariaDB / pre-5.7.6 MySQL fallback."""
    if target.via_admin:
        host_part = _mysql_account_host(cursor, target.username)
        cursor.execute("SET PASSWORD FOR %s@%s = PASSWORD(%s)", (target.username, host_part, new_password))
    else:
        cursor.execute("SET PASSWORD = PASSWORD(%s)", (new_password,))


def _mysql_account_host(cursor, username: str) -> str:
    """Resolve the host half of a MySQL account name.

    MySQL identifies accounts as user@host, but a vault secret only records the
    user. Look the account up rather than guessing — silently rewriting the
    wrong `bob@%` when the real account is `bob@10.0.0.5` would lock somebody out.
    """
    try:
        cursor.execute("SELECT Host FROM mysql.user WHERE User = %s", (username,))
        hosts = [row[0] for row in cursor.fetchall()]
    except Exception:
        # No SELECT on mysql.user — fall back to the conventional wildcard account.
        return "%"

    if not hosts:
        frappe.throw(
            _("No MySQL/MariaDB account named '{0}' exists on this server.").format(username),
            TargetApplyError,
        )

    if len(hosts) > 1:
        frappe.throw(
            _(
                "'{0}' exists as several accounts on this server ({1}). Rotation cannot tell which one "
                "to change — remove the duplicates or rotate it manually."
            ).format(username, ", ".join(f"{username}@{h}" for h in sorted(hosts))),
            TargetApplyError,
        )

    return hosts[0]


def _is_mysql_syntax_error(exception) -> bool:
    """True for MySQL error 1064 (parse error), which means unsupported syntax."""
    args = getattr(exception, "args", None) or ()
    return bool(args) and args[0] == 1064


def _mysql_verify(target: Target):
    _close(_mysql_connect(target, target.auth_username, target.auth_password))


def _mysql_account_exists(target: Target) -> bool | None:
    conn = _mysql_connect(target, target.auth_username, target.auth_password)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM mysql.user WHERE User = %s", (target.username,))
            return bool(cursor.fetchone()[0])
    except Exception:
        # Reading mysql.user needs privilege the connecting account may not have.
        return None
    finally:
        _close(conn)


# ----------------------------------------------------------------------
# MongoDB
# ----------------------------------------------------------------------


def _mongo_client(target: Target, user: str, password: str):
    try:
        from pymongo import MongoClient
    except ImportError:
        frappe.throw(
            _("The 'pymongo' package is not installed; run: bench pip install pymongo"), TargetApplyError
        )

    return MongoClient(
        host=target.host,
        port=target.port,
        username=user,
        password=password,
        authSource=target.auth_source,
        tls=target.use_ssl,
        serverSelectionTimeoutMS=CONNECT_TIMEOUT_SECONDS * 1000,
        connectTimeoutMS=CONNECT_TIMEOUT_SECONDS * 1000,
        socketTimeoutMS=CONNECT_TIMEOUT_SECONDS * 1000,
    )


def _mongo_apply(target: Target, new_password: str):
    client = _mongo_client(target, target.auth_username, target.auth_password)
    try:
        try:
            client[target.auth_source].command("updateUser", target.username, pwd=new_password)
        except Exception as e:
            frappe.throw(
                _("MongoDB refused the password change for '{0}' on auth source '{1}' — {2}").format(
                    target.username, target.auth_source, _clean(e)
                ),
                TargetApplyError,
            )
    finally:
        _close(client)


def _mongo_verify(target: Target):
    client = _mongo_client(target, target.auth_username, target.auth_password)
    try:
        # ping only succeeds once the credentials have been accepted.
        client[target.auth_source].command("ping")
    except Exception as e:
        frappe.throw(
            _("Could not authenticate to MongoDB at {0}:{1} — {2}").format(
                target.host, target.port, _clean(e)
            ),
            TargetApplyError,
        )
    finally:
        _close(client)


def _mongo_account_exists(target: Target) -> bool | None:
    client = _mongo_client(target, target.auth_username, target.auth_password)
    try:
        info = client[target.auth_source].command(
            "usersInfo", {"user": target.username, "db": target.auth_source}
        )
        return bool(info.get("users"))
    except Exception:
        return None
    finally:
        _close(client)


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------

_HANDLERS = {
    POSTGRESQL: _postgres_apply,
    MYSQL: _mysql_apply,
    MONGODB: _mongo_apply,
}

_VERIFIERS = {
    POSTGRESQL: _postgres_verify,
    MYSQL: _mysql_verify,
    MONGODB: _mongo_verify,
}

_EXISTENCE_PROBES = {
    POSTGRESQL: _postgres_account_exists,
    MYSQL: _mysql_account_exists,
    MONGODB: _mongo_account_exists,
}


def _handler_for(database_type: str):
    return _HANDLERS[database_type]


def _verifier_for(database_type: str):
    return _VERIFIERS[database_type]


def _close(handle):
    """Best-effort close — a failure here must never mask the real outcome."""
    try:
        handle.close()
    except Exception:
        pass


def _clean(exception) -> str:
    """A driver error trimmed to one readable line.

    Driver messages can echo connection parameters, so keep them short and never
    let one grow long enough to carry a password back into a log or an email.
    """
    text = str(exception).strip().splitlines()
    return (text[0] if text else exception.__class__.__name__)[:200]
