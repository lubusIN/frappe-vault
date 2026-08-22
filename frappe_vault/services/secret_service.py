"""Secret service — core CRUD and business logic for vault secrets."""

import time

import frappe
import pyotp
from frappe import _

from frappe_vault.services.audit_service import log_secret_viewed
from frappe_vault.utils.constants import LIST_VIEW_FIELDS

# Allowlisted order_by values to prevent SQL injection
ALLOWED_ORDER_BY = {
    "modified desc",
    "modified asc",
    "creation desc",
    "creation asc",
    "title asc",
    "title desc",
    "last_accessed desc",
    "last_accessed asc",
    "secret_type asc",
    "secret_type desc",
}


def _sanitize_search(value: str) -> str:
    """Strip SQL wildcard metacharacters from user search input."""
    if not value:
        return value
    return value.replace("%", "").replace("_", "").strip()


def get_secrets(
    search: str = None,
    title: str = None,
    username: str = None,
    secret_type: str = None,
    folder: str = None,
    bookmarks_only: bool = False,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "modified desc",
    **kwargs,
) -> dict:
    """Get list of secrets visible to current user (respects permission_query_conditions).

    Returns:
        dict with secrets list, total count, and pagination
    """
    # Validate order_by against allowlist
    if order_by not in ALLOWED_ORDER_BY:
        order_by = "modified desc"

    filters = {}

    if secret_type:
        filters["secret_type"] = secret_type
    if folder:
        filters["folder"] = folder

    # Dynamic filters from kwargs (FilterPanel)
    for k, v in kwargs.items():
        if k in ("cmd", "csrf_token"):
            continue
        if v is not None:
            if isinstance(v, str) and v.startswith("[") and v.endswith("]"):
                try:
                    # Frappe's frontend may send lists as stringified JSON if they use arrays
                    parsed_v = frappe.parse_json(v)
                    filters[k] = parsed_v
                except Exception:
                    filters[k] = v
            else:
                filters[k] = v

    # Resolve user bookmarks
    user = frappe.session.user
    user_bookmarks = set(frappe.get_all("Vault Bookmark", filters={"user": user}, pluck="secret"))

    if bookmarks_only:
        if not user_bookmarks:
            return {
                "secrets": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
            }
        filters["name"] = ["in", list(user_bookmarks)]

    if title:
        clean_title = _sanitize_search(title)
        if clean_title:
            filters["title"] = ["like", f"%{clean_title}%"]
    if username:
        clean_username = _sanitize_search(username)
        if clean_username:
            filters["username"] = ["like", f"%{clean_username}%"]

    or_filters = None
    if search:
        clean_search = _sanitize_search(search)
        if clean_search:
            or_filters = [
                ["title", "like", f"%{clean_search}%"],
                ["url", "like", f"%{clean_search}%"],
                ["username", "like", f"%{clean_search}%"],
                ["email", "like", f"%{clean_search}%"],
            ]

    secrets = frappe.get_list(
        "Vault Secret",
        filters=filters,
        or_filters=or_filters,
        fields=LIST_VIEW_FIELDS,
        order_by=order_by,
        limit=limit,
        limit_start=offset,
    )

    # Populate folder_name and folder_icon for all distinct folders from DB dynamically
    folder_ids = list(set([s["folder"] for s in secrets if s.get("folder")]))
    folder_map = {}
    if folder_ids:
        folder_docs = frappe.get_all(
            "Vault Folder",
            or_filters=[
                ["name", "in", folder_ids],
                ["folder_name", "in", folder_ids],
            ],
            fields=["name", "folder_name", "icon"],
            ignore_permissions=True,
        )
        for f in folder_docs:
            folder_map[f["name"]] = f
            folder_map[f["folder_name"]] = f

    # Populate is_bookmark and folder details dynamically per-user
    for s in secrets:
        s["is_bookmark"] = 1 if s["name"] in user_bookmarks else 0
        folder_val = s.get("folder")
        if folder_val and folder_val in folder_map:
            s["folder_name"] = folder_map[folder_val]["folder_name"]
            s["folder_icon"] = folder_map[folder_val]["icon"]

    # Fix total count leak by counting only visible records
    total = len(frappe.get_list("Vault Secret", filters=filters, or_filters=or_filters, pluck="name"))

    return {
        "secrets": secrets,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_secret(name: str, decrypt: bool = False) -> dict:
    """Get a single secret with optional decryption.

    Args:
        name: Vault Secret document name
        decrypt: Whether to include decrypted sensitive fields

    Returns:
        dict with secret data
    """
    if not frappe.has_permission("Vault Secret", "read", name):
        frappe.throw(_("You don't have permission to access this secret"), frappe.PermissionError)

    doc = frappe.get_doc("Vault Secret", name)

    # Determine user permission level for this secret
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = user == "Administrator" or "Vault Admin" in roles or "System Manager" in roles

    is_folder_owner = False
    if doc.folder:
        folder_owner = frappe.db.get_value("Vault Folder", doc.folder, "owner")
        if folder_owner == user:
            is_folder_owner = True

    shared_by = None
    if is_admin or doc.owner == user or is_folder_owner:
        user_permission = "Full Control"
    else:
        conditions = ["(expires_on IS NULL OR expires_on > NOW())", "is_revoked = 0"]
        target_conds = [f"(shared_doctype = 'Vault Secret' AND shared_name = {frappe.db.escape(doc.name)})"]
        if doc.folder:
            target_conds.append(
                f"(shared_doctype = 'Vault Folder' AND shared_name = {frappe.db.escape(doc.folder)})"
            )
        conditions.append("(" + " OR ".join(target_conds) + ")")

        share_conds = [f"(share_type = 'User' AND user = {frappe.db.escape(user)})"]

        if roles:
            roles_str = ", ".join([frappe.db.escape(r) for r in roles])
            share_conds.append(f"(share_type = 'Role' AND frappe_role IN ({roles_str}))")

        conditions.append("(" + " OR ".join(share_conds) + ")")

        shares = frappe.db.sql(  # nosemgrep
            f"""
            SELECT permission_level, shared_by, share_type, shared_doctype, is_role_override FROM `tabVault Share`
            WHERE {" AND ".join(conditions)}
        """,
            as_dict=True,
        )

        if shares:
            perm_map = {"View Only": 1, "View & Copy": 2, "Edit": 3, "Full Control": 4}

            def share_priority_key(s):
                is_user = s.get("share_type") == "User"
                is_override = s.get("is_role_override")

                if is_user and not is_override:
                    hierarchy = 3
                elif is_user and is_override:
                    hierarchy = 2
                else:
                    hierarchy = 1

                doc_priority = 2 if s.get("shared_doctype") == "Vault Secret" else 1
                perm_score = perm_map.get(s.get("permission_level"), 0)
                return (hierarchy, doc_priority, perm_score)

            best_share = max(shares, key=share_priority_key)
            user_permission = best_share.get("permission_level")
            shared_by = best_share.get("shared_by")
        else:
            user_permission = "View Only"
            shared_by = doc.owner

    result = {
        "name": doc.name,
        "title": doc.title,
        "secret_type": doc.secret_type,
        "folder": doc.folder,
        "url": doc.url,
        "username": doc.username,
        "email": doc.email,
        "attachment": doc.attachment,
        "notes": doc.notes,
        "is_bookmark": 1
        if frappe.db.exists("Vault Bookmark", {"user": frappe.session.user, "secret": doc.name})
        else 0,
        "password_strength": doc.password_strength,
        "password_last_changed": doc.password_last_changed,
        "has_password": bool(doc.get("password")),
        "has_totp": bool(doc.get("totp_secret")),
        "has_api_secret": bool(doc.get("api_secret")),
        "has_card_number": bool(doc.get("card_number")),
        "has_card_cvv": bool(doc.get("card_cvv")),
        "has_db_password": bool(doc.get("db_password")),
        "last_accessed": str(doc.last_accessed) if doc.last_accessed else None,
        "access_count": doc.access_count,
        "expires_on": str(doc.expires_on) if doc.expires_on else None,
        "enable_rotation": doc.enable_rotation,
        "rotation_interval": doc.rotation_interval,
        "rotation_unit": doc.rotation_unit,
        "last_rotated_on": str(doc.last_rotated_on) if doc.last_rotated_on else None,
        "next_rotation_on": str(doc.next_rotation_on) if doc.next_rotation_on else None,
        # Status flag only — zip_passphrase itself is never sent to the client,
        # same as password/api_secret/db_password never being included here.
        "has_zip_passphrase": doc.has_zip_passphrase,
        "owner": doc.owner,
        "shared_by": shared_by,
        "modified": str(doc.modified),
        "user_permission": user_permission,
        "permission_level": user_permission,
    }

    # Type-specific non-sensitive fields
    if doc.secret_type == "API Key":
        result["api_key"] = doc.api_key
    elif doc.secret_type == "Credit Card":
        result["card_holder"] = doc.card_holder
        result["card_expiry"] = doc.card_expiry
    elif doc.secret_type == "Database":
        result["db_host"] = doc.db_host
        result["db_port"] = doc.db_port
        result["db_name"] = doc.db_name
    elif doc.secret_type == "SSH Key":
        result["ssh_private_key"] = doc.ssh_private_key

    if decrypt:
        from frappe_vault.utils.encryption import get_decrypted_secret_data

        result["decrypted"] = get_decrypted_secret_data(name)

    # Log access and update metadata
    log_secret_viewed(name)
    doc.update_access_metadata()

    return result


def get_totp_code(name: str) -> dict:
    """Generate the current TOTP code and remaining seconds for a secret."""
    if not frappe.has_permission("Vault Secret", "read", name):
        frappe.throw(_("You don't have permission to access this secret"), frappe.PermissionError)

    secret = get_secret(name, decrypt=True)
    decrypted = secret.get("decrypted", {})
    totp_secret = decrypted.get("totp_secret")

    if not totp_secret:
        return {"code": None, "remaining_seconds": 0, "error": _("No TOTP secret configured.")}

    try:
        clean_secret = str(totp_secret).strip().replace(" ", "").upper()
        unpadded = clean_secret.rstrip("=")
        rem = len(unpadded) % 8
        padded = unpadded + ("=" * {2: 6, 4: 4, 5: 3, 7: 1}.get(rem, 0))
        totp = pyotp.TOTP(padded)
        code = totp.now()
        remaining_seconds = 30 - (int(time.time()) % 30)

        # Generate QR Code SVG only for owners/admins to prevent offline copying by shared users
        qr_svg = None
        if secret.get("user_permission") == "Full Control":
            try:
                import base64

                from frappe.twofactor import get_qr_svg_code

                totp_uri = totp.provisioning_uri(name=name, issuer_name="Frappe Vault")
                qr_b64_bytes = get_qr_svg_code(totp_uri)
                if isinstance(qr_b64_bytes, bytes):
                    qr_svg = base64.b64decode(qr_b64_bytes).decode("utf-8")
                elif isinstance(qr_b64_bytes, str):
                    qr_svg = base64.b64decode(qr_b64_bytes.encode("utf-8")).decode("utf-8")
                else:
                    qr_svg = str(qr_b64_bytes)
            except Exception as e:
                frappe.logger().error(f"Could not generate QR SVG: {str(e)}")

        return {"code": code, "remaining_seconds": remaining_seconds, "qr_svg": qr_svg, "error": None}

    except Exception as e:
        frappe.log_error(title=f"TOTP Generation Failed for {name}", message=str(e))
        return {"code": None, "remaining_seconds": 0, "error": _("Invalid TOTP setup key format.")}


def sanitize_url(url: str) -> str:
    if not url:
        return ""
    url = str(url).strip()
    if not url:
        return ""
    if not (url.startswith("http://") or url.startswith("https://") or "://" in url):
        return f"https://{url}"
    return url


def upload_secret_attachment(
    file_obj,
    filename: str,
    is_private: int = 1,
    doctype: str | None = None,
    docname: str | None = None,
) -> dict:
    """Upload a file attachment for a Vault Secret (works for standard Vault Users and Admins)."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required"), frappe.PermissionError)

    if doctype == "Vault Secret" and docname:
        from frappe_vault.utils.permissions import has_secret_permission

        if not has_secret_permission(docname, ptype="write"):
            frappe.throw(_("You don't have permission to modify this secret"), frappe.PermissionError)

    content = file_obj.read() if hasattr(file_obj, "read") else file_obj

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": doctype,
            "attached_to_name": docname,
            "is_private": frappe.utils.cint(is_private),
            "content": content,
        }
    )
    file_doc.save(ignore_permissions=True)

    return {
        "file_url": file_doc.file_url,
        "file_name": file_doc.file_name,
        "name": file_doc.name,
    }


def _link_attachments(doc):
    if getattr(doc, "secret_type", None) != "Media":
        return
    attachment = getattr(doc, "attachment", None)
    if not attachment:
        return

    import json

    urls = []
    if isinstance(attachment, str):
        if attachment.startswith("["):
            try:
                urls = json.loads(attachment)
            except Exception:
                urls = [attachment]
        else:
            urls = [attachment]

    if not urls:
        return

    for url in urls:
        file_name = frappe.db.get_value("File", {"file_url": url}, "name")
        if file_name:
            # Attach the file to the secret so permissions are inherited
            frappe.db.set_value(
                "File", file_name, {"attached_to_doctype": "Vault Secret", "attached_to_name": doc.name}
            )


def create_secret(data: dict) -> dict:
    """Create a new vault secret.

    Args:
        data: dict with secret fields

    Returns:
        dict with created secret name
    """
    if not frappe.has_permission("Vault Secret", "create"):
        frappe.throw(_("You don't have permission to create secrets"), frappe.PermissionError)

    folder = data.get("folder")
    if folder:
        from frappe_vault.utils.permissions import has_folder_permission

        if not has_folder_permission(folder, ptype="write"):
            frappe.throw(_("You don't have permission to add secrets to this folder"), frappe.PermissionError)

    if "url" in data:
        data["url"] = sanitize_url(data["url"])

    doc = frappe.get_doc(
        {
            "doctype": "Vault Secret",
            **{k: v for k, v in data.items() if k not in ("doctype", "name")},
        }
    )
    doc.insert()

    _link_attachments(doc)

    # Notify Vault Admins of new secret creation
    from frappe_vault.services.notification_service import notify_vault_admins

    creator_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    notify_vault_admins(
        subject=f"New Secret Created: '{doc.title}'",
        email_content=f"{creator_name} created secret '{doc.title}'.",
        document_type="Vault Secret",
        document_name=doc.name,
    )

    return {"name": doc.name, "title": doc.title}


def update_secret(name: str, data: dict) -> dict:
    """Update an existing vault secret.

    Args:
        name: Vault Secret document name
        data: dict with fields to update

    Returns:
        dict with updated secret name
    """
    if not frappe.has_permission("Vault Secret", "write", name):
        frappe.throw(_("You don't have permission to update this secret"), frappe.PermissionError)

    doc = frappe.get_doc("Vault Secret", name)

    new_folder = data.get("folder")
    if new_folder and new_folder != doc.folder:
        from frappe_vault.utils.permissions import has_folder_permission

        if not has_folder_permission(new_folder, ptype="write"):
            frappe.throw(
                _("You don't have permission to move secrets to this folder"), frappe.PermissionError
            )

    if "url" in data:
        data["url"] = sanitize_url(data["url"])

    allowed_fields = [
        "title",
        "secret_type",
        "folder",
        "url",
        "username",
        "email",
        "password",
        "totp_secret",
        "api_key",
        "api_secret",
        "notes",
        "is_bookmark",
        "ssh_private_key",
        "attachment",
        "card_holder",
        "card_number",
        "card_expiry",
        "card_cvv",
        "db_host",
        "db_port",
        "db_name",
        "db_password",
        "expires_on",
        "custom_fields_json",
        "enable_rotation",
        "rotation_interval",
        "rotation_unit",
        "zip_passphrase",
    ]

    for field, value in data.items():
        if field in allowed_fields:
            doc.set(field, value)

    doc.save()
    _link_attachments(doc)
    return {"name": doc.name, "title": doc.title}


def delete_secret(name: str) -> dict:
    """Delete a vault secret."""
    from frappe_vault.utils.permissions import has_secret_permission

    if not has_secret_permission(name, ptype="delete"):
        frappe.throw(_("You don't have permission to delete this secret"), frappe.PermissionError)

    title = frappe.db.get_value("Vault Secret", name, "title")

    # 1. Clean up associated shareable One Time Links
    one_time_links = frappe.get_all("Vault One Time Link", filters={"secret": name}, pluck="name")
    for link_name in one_time_links:
        frappe.delete_doc("Vault One Time Link", link_name, force=True, ignore_permissions=True)

    # 2. Delete associated share settings
    shares = frappe.get_all(
        "Vault Share", filters={"shared_doctype": "Vault Secret", "shared_name": name}, pluck="name"
    )
    for share_name in shares:
        frappe.delete_doc("Vault Share", share_name, force=True, ignore_permissions=True)

    # 3. Clean up associated bookmarks
    bookmarks = frappe.get_all("Vault Bookmark", filters={"secret": name}, pluck="name")
    for b_name in bookmarks:
        frappe.delete_doc("Vault Bookmark", b_name, force=True, ignore_permissions=True)

    # 4. Finally delete the Vault Secret document itself.
    # We bypass link verification for Vault Audit Log so we can keep the historical
    # Vault Audit Logs intact and displaying the raw secret ID in list views!
    frappe.delete_doc(
        "Vault Secret", name, force=True, ignore_doctypes=["Vault Audit Log"], ignore_permissions=True
    )

    # 5. Notify Vault Admins
    from frappe_vault.services.notification_service import notify_vault_admins

    actor_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    notify_vault_admins(
        subject=f"Secret Deleted: '{title}'",
        email_content=f"{actor_name} deleted secret '{title}'.",
        document_type="Vault Secret",
        document_name=name,
    )

    return {"name": name, "title": title}


def bulk_delete(secret_names: list) -> dict:
    """Delete multiple vault secrets. Skips any the user lacks permission for."""
    deleted = 0
    skipped = 0
    failed = 0
    error = None
    for name in secret_names:
        if not frappe.db.exists("Vault Secret", name):
            continue  # already deleted
        try:
            delete_secret(name)
            deleted += 1
        except frappe.PermissionError:
            # User doesn't own this secret and doesn't have Full Control — skip gracefully
            skipped += 1
        except Exception as e:
            failed += 1
            error = str(e)

    return {"deleted": deleted, "skipped": skipped, "failed": failed, "error": error}


def toggle_bookmark(name: str) -> dict:
    """Toggle bookmark status."""
    if not frappe.has_permission("Vault Secret", "read", name):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    user = frappe.session.user
    fav_exists = frappe.db.exists("Vault Bookmark", {"user": user, "secret": name})
    if fav_exists:
        frappe.delete_doc("Vault Bookmark", fav_exists, force=True, ignore_permissions=True)
        is_bookmark = 0
    else:
        try:
            fav_doc = frappe.get_doc({"doctype": "Vault Bookmark", "user": user, "secret": name})
            fav_doc.insert(ignore_permissions=True)
            is_bookmark = 1
        except frappe.DuplicateEntryError:
            is_bookmark = 1

    return {"name": name, "is_bookmark": is_bookmark}


def bulk_move(secret_names: list, target_folder: str) -> dict:
    """Move multiple secrets to a target folder."""
    moved = 0
    for name in secret_names:
        if frappe.has_permission("Vault Secret", "write", name):
            frappe.db.set_value("Vault Secret", name, "folder", target_folder)
            moved += 1
    return {"moved": moved}


def get_vault_stats(user: str | None = None) -> dict:
    """Get dashboard statistics for a specific user or current user."""
    user = user or frappe.session.user
    user_roles = frappe.get_roles(user)
    is_admin = user == "Administrator" or "Vault Admin" in user_roles or "System Manager" in user_roles

    if is_admin:
        permitted_secrets = frappe.get_all(
            "Vault Secret", fields=["name", "password_strength", "secret_type"], limit=0
        )
    else:
        owned = frappe.get_all(
            "Vault Secret",
            filters={"owner": user},
            fields=["name", "password_strength", "secret_type"],
            limit=0,
        )
        permitted_map = {s.name: s for s in owned}

        role_placeholders = ", ".join(["%s"] * len(user_roles)) if user_roles else "''"
        params = [user] + list(user_roles) + [user]

        secret_query = f"""
            SELECT DISTINCT shared_name FROM `tabVault Share` vs
            WHERE is_revoked = 0
            AND (expires_on IS NULL OR expires_on > NOW())
            AND shared_doctype = 'Vault Secret'
            AND (
                (share_type = 'User' AND user = %s)
                OR (share_type = 'Role' AND frappe_role IN ({role_placeholders})
                    AND NOT EXISTS (
                        SELECT 1 FROM `tabVault Share` override
                        WHERE override.shared_doctype = 'Vault Secret'
                        AND override.shared_name = vs.shared_name
                        AND override.share_type = 'User'
                        AND override.user = %s
                        AND override.is_revoked = 1
                    )
                )
            )
        """
        shared_secret_names = set(frappe.db.sql_list(secret_query, tuple(params)))

        folder_query = f"""
            SELECT DISTINCT shared_name FROM `tabVault Share` vs
            WHERE is_revoked = 0
            AND (expires_on IS NULL OR expires_on > NOW())
            AND shared_doctype = 'Vault Folder'
            AND (
                (share_type = 'User' AND user = %s)
                OR (share_type = 'Role' AND frappe_role IN ({role_placeholders})
                    AND NOT EXISTS (
                        SELECT 1 FROM `tabVault Share` override
                        WHERE override.shared_doctype = 'Vault Folder'
                        AND override.shared_name = vs.shared_name
                        AND override.share_type = 'User'
                        AND override.user = %s
                        AND override.is_revoked = 1
                    )
                )
            )
        """
        shared_folders = set(frappe.db.sql_list(folder_query, tuple(params)))

        if shared_folders:
            folder_secrets = frappe.get_all(
                "Vault Secret",
                filters={"folder": ["in", list(shared_folders)]},
                pluck="name",
                limit=0,
            )
            shared_secret_names.update(folder_secrets)

        additional_names = shared_secret_names - set(permitted_map.keys())
        if additional_names:
            shared_secrets_data = frappe.get_all(
                "Vault Secret",
                filters={"name": ["in", list(additional_names)]},
                fields=["name", "password_strength", "secret_type"],
                limit=0,
            )
            for s in shared_secrets_data:
                permitted_map[s.name] = s

        permitted_secrets = list(permitted_map.values())

    permitted_names = {s["name"] for s in permitted_secrets}

    total = len(permitted_secrets)
    weak = sum(1 for s in permitted_secrets if s.get("password_strength") in ("weak", "fair"))

    secrets_by_type = {}
    for s in permitted_secrets:
        stype = s.get("secret_type") or "Other"
        secrets_by_type[stype] = secrets_by_type.get(stype, 0) + 1

    bookmarks_list = frappe.get_all("Vault Bookmark", filters={"user": user}, pluck="secret", limit=0)
    bookmarks = sum(1 for b in bookmarks_list if b in permitted_names)

    recent = []
    if permitted_names:
        recent = frappe.get_all(
            "Vault Secret",
            filters={"name": ["in", list(permitted_names)]},
            fields=["name", "title", "secret_type", "folder", "last_accessed", "url"],
            order_by="last_accessed desc",
            limit=5,
        )

    from frappe_vault.services.demo_service import check_has_demo_data

    return {
        "total_secrets": total,
        "bookmarks": bookmarks,
        "weak_passwords": weak,
        "secrets_by_type": secrets_by_type,
        "recent_secrets": recent,
        "is_admin": is_admin,
        "has_demo_data": check_has_demo_data(),
    }
