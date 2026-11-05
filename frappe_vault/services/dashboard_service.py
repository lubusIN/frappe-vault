"""Vault Dashboard Service — dashboard metrics and charts for Frappe Vault."""

import json

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate, nowdate


def get_default_layout() -> list[dict]:
    """Return standard default layout for Vault Dashboard."""
    return [
        {
            "name": "security_score",
            "type": "security_score",
            "layout": {"x": 0, "y": 0, "w": 5, "h": 3, "i": "security_score_1"},
        },
        {
            "name": "total_secrets",
            "type": "number_chart",
            "layout": {"x": 5, "y": 0, "w": 5, "h": 3, "i": "total_secrets_1"},
        },
        {
            "name": "active_shares",
            "type": "number_chart",
            "layout": {"x": 10, "y": 0, "w": 5, "h": 3, "i": "active_shares_1"},
        },
        {
            "name": "bookmarks",
            "type": "number_chart",
            "layout": {"x": 15, "y": 0, "w": 5, "h": 3, "i": "bookmarks_1"},
        },
        {
            "name": "recently_accessed",
            "type": "recently_accessed",
            "layout": {"x": 0, "y": 3, "w": 10, "h": 8, "i": "recently_accessed_1"},
        },
        {
            "name": "secrets_by_folder",
            "type": "donut_chart",
            "layout": {"x": 10, "y": 3, "w": 10, "h": 8, "i": "secrets_by_folder_1"},
        },
        {
            "name": "vault_trend",
            "type": "axis_chart",
            "layout": {"x": 0, "y": 11, "w": 20, "h": 7, "i": "vault_trend_1"},
        },
    ]


def get_dashboard_layout(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> list:
    """Get dashboard layout populated with real-time chart & number metric data."""
    if not from_date or not to_date:
        today_str = nowdate()
        from_date = add_days(today_str, -29)
        to_date = today_str

    user_roles = frappe.get_roles(frappe.session.user)
    is_admin = (
        frappe.session.user == "Administrator"
        or "Vault Admin" in user_roles
        or "System Manager" in user_roles
    )
    if not is_admin:
        user = frappe.session.user

    # Fetch stored layout or default layout
    saved_layout_json = frappe.db.get_value(  # nosemgrep: frappe-single-value-type-safety
        "Vault Settings", "Vault Settings", "dashboard_layout"
    )
    if saved_layout_json:
        try:
            layout = json.loads(saved_layout_json)
        except Exception:
            layout = get_default_layout()
    else:
        layout = get_default_layout()

    # Populate data for each item
    for item in layout:
        chart_name = item.get("name")
        method_name = f"get_{chart_name}"
        if hasattr(frappe.get_module("frappe_vault.services.dashboard_service"), method_name):
            func = getattr(frappe.get_module("frappe_vault.services.dashboard_service"), method_name)
            item["data"] = func(from_date, to_date, user)
        else:
            item["data"] = None

    return layout


def get_total_secrets(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> dict:
    """NumberChart config for Total Secrets created."""
    diff = max(1, date_diff(to_date, from_date) + 1)
    prev_from_date = str(add_days(from_date, -diff))

    curr_count = len(
        frappe.get_all(
            "Vault Secret",
            filters={"creation": ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]]},
            limit=0,
        )
    )

    prev_count = len(
        frappe.get_all(
            "Vault Secret",
            filters={"creation": ["between", [f"{prev_from_date} 00:00:00", f"{from_date} 00:00:00"]]},
            limit=0,
        )
    )

    from frappe_vault.services.secret_service import get_vault_stats

    target_user = user or frappe.session.user
    stats = get_vault_stats(target_user)
    total_all = stats.get("total_secrets", 0)
    delta = round(((curr_count - prev_count) / prev_count * 100.0), 1) if prev_count else 0.0

    return {
        "title": _("Total Secrets"),
        "tooltip": _("Total secrets in vault (new in period: {0})").format(curr_count),
        "value": total_all,
        "delta": delta,
        "deltaSuffix": "%",
    }


def get_bookmarks(from_date: str | None = None, to_date: str | None = None, user: str | None = None) -> dict:
    """NumberChart config for User Bookmarks."""
    target_user = user or frappe.session.user
    count = frappe.db.count("Vault Bookmark", filters={"user": target_user})

    return {
        "title": _("Bookmarks"),
        "tooltip": _("Bookmarked secrets"),
        "value": count,
    }


def get_active_shares(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> dict:
    """NumberChart config for Active Shares."""
    diff = max(1, date_diff(to_date, from_date) + 1)
    prev_from_date = str(add_days(from_date, -diff))

    filters = {"is_revoked": 0}
    if user:
        filters["shared_by"] = user

    curr_count = frappe.db.count(
        "Vault Share",
        filters={**filters, "creation": ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]]},
    )
    prev_count = frappe.db.count(
        "Vault Share",
        filters={**filters, "creation": ["between", [f"{prev_from_date} 00:00:00", f"{from_date} 00:00:00"]]},
    )

    total_active = frappe.db.count("Vault Share", filters=filters)
    delta = round(((curr_count - prev_count) / prev_count * 100.0), 1) if prev_count else 0.0

    return {
        "title": _("Active Shares"),
        "tooltip": _("Active secret & folder shares"),
        "value": total_active,
        "delta": delta,
        "deltaSuffix": "%",
    }


def get_revoked_shares(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> dict:
    """NumberChart config for Revoked Shares."""
    filters = {"is_revoked": 1}
    if user:
        filters["shared_by"] = user

    total_revoked = frappe.db.count("Vault Share", filters=filters)

    return {
        "title": _("Revoked Shares"),
        "tooltip": _("Revoked secret & folder share records"),
        "value": total_revoked,
    }


def get_security_score(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> dict:
    """Security Score and Health suggestions."""
    from frappe_vault.services.security_service import calculate_security_score

    return calculate_security_score(user=user)


def get_recently_accessed(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> dict:
    """Recently accessed secrets list."""
    recent_secrets = frappe.get_list(
        "Vault Secret",
        fields=["name", "title", "secret_type", "folder", "last_accessed", "owner"],
        order_by="last_accessed desc",
        limit=5,
    )
    return {"recent_secrets": recent_secrets}


def get_vault_trend(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> dict:
    """AxisChart config for daily Secrets, Shares, and Revocations performance."""
    start_d = getdate(from_date)
    end_d = getdate(to_date)

    daily_map = {}
    current_d = start_d
    while current_d <= end_d:
        d_str = str(current_d)
        daily_map[d_str] = {"date": d_str, "secrets": 0, "shares": 0, "revocations": 0}
        current_d = add_days(current_d, 1)

    # Secrets query
    sec_user_clause = f"AND owner = {frappe.db.escape(user)}" if user else ""
    secrets_data = frappe.db.sql(  # nosemgrep
        f"""
        SELECT DATE(creation) as date_val, COUNT(*) as count
        FROM `tabVault Secret`
        WHERE DATE(creation) BETWEEN %s AND %s {sec_user_clause}
        GROUP BY DATE(creation)
    """,
        (from_date, to_date),
        as_dict=True,
    )

    for row in secrets_data:
        d_str = str(row["date_val"])
        if d_str in daily_map:
            daily_map[d_str]["secrets"] = row["count"]

    # Active Shares query
    share_user_clause = f"AND shared_by = {frappe.db.escape(user)}" if user else ""
    shares_data = frappe.db.sql(  # nosemgrep
        f"""
        SELECT DATE(creation) as date_val, COUNT(*) as count
        FROM `tabVault Share`
        WHERE is_revoked = 0 AND DATE(creation) BETWEEN %s AND %s {share_user_clause}
        GROUP BY DATE(creation)
    """,
        (from_date, to_date),
        as_dict=True,
    )

    for row in shares_data:
        d_str = str(row["date_val"])
        if d_str in daily_map:
            daily_map[d_str]["shares"] = row["count"]

    # Revocations query
    rev_data = frappe.db.sql(  # nosemgrep
        f"""
        SELECT DATE(modified) as date_val, COUNT(*) as count
        FROM `tabVault Share`
        WHERE is_revoked = 1 AND DATE(modified) BETWEEN %s AND %s {share_user_clause}
        GROUP BY DATE(modified)
    """,
        (from_date, to_date),
        as_dict=True,
    )

    for row in rev_data:
        d_str = str(row["date_val"])
        if d_str in daily_map:
            daily_map[d_str]["revocations"] = row["count"]

    chart_rows = list(daily_map.values())

    return {
        "title": _("Vault Activity Trend"),
        "subtitle": _("Daily performance of secrets created, shares, and revocations"),
        "xAxis": {
            "title": _("Date"),
            "key": "date",
            "type": "time",
            "timeGrain": "day",
        },
        "yAxis": {
            "title": _("Count"),
        },
        "series": [
            {"name": "secrets", "type": "line", "showDataPoints": True},
            {"name": "shares", "type": "line", "showDataPoints": True},
            {"name": "revocations", "type": "line", "showDataPoints": True},
        ],
        "data": chart_rows,
    }


def get_secrets_by_folder(
    from_date: str | None = None, to_date: str | None = None, user: str | None = None
) -> dict:
    """DonutChart config for Secrets by Folder breakdown."""

    if not user:
        # Admin gets everything, fast SQL is fine
        folder_counts = frappe.db.sql(  # nosemgrep
            """
            SELECT
                COALESCE(
                    IF(f.parent_vault_folder IS NOT NULL AND f.parent_vault_folder != '',
                       CONCAT(f.parent_vault_folder, ' / ', s.folder),
                       s.folder),
                    'Unfiled'
                ) as folder_name,
                COUNT(s.name) as count
            FROM `tabVault Secret` s
            LEFT JOIN `tabVault Folder` f ON s.folder = f.name
            GROUP BY s.folder
            ORDER BY count DESC
        """,
            as_dict=True,
        )
    else:
        # Normal users need permission hooks for shared folders
        secrets = frappe.get_list("Vault Secret", fields=["folder", "name"], limit=50000)
        folders = frappe.get_all("Vault Folder", fields=["name", "parent_vault_folder"])
        folder_map = {f.name: f.parent_vault_folder for f in folders}

        counts = {}
        for s in secrets:
            fname = s.folder or "Unfiled"
            if fname != "Unfiled":
                parent = folder_map.get(fname)
                if parent:
                    fname = f"{parent} / {fname}"
            counts[fname] = counts.get(fname, 0) + 1

        folder_counts = [{"folder_name": k, "count": v} for k, v in counts.items()]
        folder_counts = sorted(folder_counts, key=lambda x: x["count"], reverse=True)

    return {
        "title": _("Secrets by Folder"),
        "subtitle": _("Distribution of secrets across folders"),
        "categoryColumn": "folder_name",
        "valueColumn": "count",
        "data": folder_counts or [],
    }
