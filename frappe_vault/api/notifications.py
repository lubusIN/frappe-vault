"""Vault Notification API — Whitelisted endpoints for notification management."""

import frappe


@frappe.whitelist()
def get_notifications(limit: int = 30) -> list[dict]:
    user = frappe.session.user
    if not user or user == "Guest":
        return []

    logs = frappe.get_all(
        "Notification Log",
        filters={"for_user": user},
        fields=[
            "name",
            "subject",
            "email_content",
            "type",
            "document_type",
            "document_name",
            "read",
            "from_user",
            "creation",
        ],
        order_by="creation desc",
        limit=int(limit),
    )

    user_names = {}
    from_users = {log["from_user"] for log in logs if log.get("from_user")}
    if from_users:
        user_docs = frappe.get_all(
            "User", filters={"name": ["in", list(from_users)]}, fields=["name", "full_name"]
        )
        for u in user_docs:
            user_names[u["name"]] = u.get("full_name") or u["name"]

    notifications_list = []
    for log in logs:
        sender_id = log.get("from_user") or "System"
        sender_name = user_names.get(sender_id, sender_id)

        # Route mapping
        doc_type = log.get("document_type")
        doc_name = log.get("document_name")
        route_path = "/secrets"
        if doc_type == "Vault Secret" and doc_name:
            route_path = f"/secrets?secret={doc_name}"
        elif doc_type == "Vault Share" or log.get("type") == "Share":
            route_path = "/shared"

        # Format HTML notification text if needed
        notification_text = log.get("email_content") or log.get("subject")

        notifications_list.append(
            {
                "name": log["name"],
                "creation": str(log["creation"]),
                "from_user": {
                    "name": sender_id,
                    "full_name": sender_name,
                },
                "type": log.get("type") or "Share",
                "to_user": user,
                "read": bool(log.get("read")),
                "subject": log.get("subject"),
                "notification_text": notification_text,
                "document_type": doc_type,
                "document_name": doc_name,
                "route_path": route_path,
            }
        )

    return notifications_list


@frappe.whitelist(methods=["POST"])
def mark_as_read(docname: str | None = None, mark_all: bool = False) -> dict:
    user = frappe.session.user
    is_mark_all = str(mark_all).lower() in ("true", "1") if mark_all is not True else True
    if is_mark_all:
        unread_docs = frappe.get_all("Notification Log", filters={"for_user": user, "read": 0}, pluck="name")
        if unread_docs:
            frappe.db.set_value(
                "Notification Log", {"name": ["in", unread_docs]}, "read", 1, update_modified=False
            )
        return {"status": "success", "marked_count": len(unread_docs)}

    if docname and isinstance(docname, str):
        if frappe.db.exists("Notification Log", docname):
            frappe.db.set_value("Notification Log", docname, "read", 1)
            return {"status": "success", "name": docname}

    return {"status": "ignored"}


@frappe.whitelist(methods=["POST"])
def mark_read(docname: str | None = None) -> dict:
    return mark_as_read(docname=docname)


@frappe.whitelist(methods=["POST"])
def mark_all_read() -> dict:
    return mark_as_read(mark_all=True)


@frappe.whitelist(methods=["POST"])
def delete_notification(docname: str | None = None) -> dict:
    user = frappe.session.user
    if docname and isinstance(docname, str) and frappe.db.exists("Notification Log", docname):
        doc = frappe.get_doc("Notification Log", docname)
        if doc.for_user == user or "System Manager" in frappe.get_roles():
            frappe.delete_doc("Notification Log", docname, ignore_permissions=True)
            return {"status": "success", "deleted": docname}
    return {"status": "ignored"}


@frappe.whitelist(methods=["POST"])
def clear_all_notifications() -> dict:
    user = frappe.session.user
    user_docs = frappe.get_all("Notification Log", filters={"for_user": user}, pluck="name")
    for dname in user_docs:
        frappe.delete_doc("Notification Log", dname, ignore_permissions=True)
    return {"status": "success", "cleared_count": len(user_docs)}
