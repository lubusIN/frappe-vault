"""Security service — scoring, breach detection, weak password analysis."""

import frappe
from frappe import _
from frappe.utils import add_days, today


@frappe.whitelist()
def calculate_security_score(user: str | None = None) -> dict:
    session_user = frappe.session.user
    user_roles = frappe.get_roles(session_user)
    is_admin = (
        session_user == "Administrator" or "Vault Admin" in user_roles or "System Manager" in user_roles
    )

    if not is_admin or not user:
        user = session_user

    base_filters = {"secret_type": "Password"}
    if not is_admin:
        base_filters["owner"] = session_user
    elif user:
        base_filters["owner"] = user

    total = frappe.db.count("Vault Secret", filters=base_filters)
    if not total:
        return {"score": 100, "breakdown": {"total": 0, "weak": 0, "old": 0, "strong": 0}, "suggestions": []}

    weak_filters = {**base_filters, "password_strength": ["in", ["weak", "fair"]]}
    weak_count = frappe.db.count("Vault Secret", filters=weak_filters)

    threshold_date = add_days(today(), -90)
    old_filters = {**base_filters, "password_last_changed": ["<", threshold_date]}
    old_count = frappe.db.count("Vault Secret", filters=old_filters)

    strong_filters = {**base_filters, "password_strength": ["in", ["strong", "excellent"]]}
    strong_count = frappe.db.count("Vault Secret", filters=strong_filters)

    score = 100 - (weak_count / total) * 40 - (old_count / total) * 30
    score = max(0, min(100, score))

    suggestions = []
    if weak_count:
        suggestions.append(_("Update {0} weak password(s)").format(weak_count))
    if old_count:
        suggestions.append(_("Rotate {0} password(s) older than 90 days").format(old_count))

    return {
        "score": round(score),
        "breakdown": {"total": total, "weak": weak_count, "old": old_count, "strong": strong_count},
        "suggestions": suggestions,
    }


def check_password_breach(password: str) -> dict:
    """Breach check placeholder."""
    return {"is_breached": False, "count": 0}


def get_weak_passwords(user: str | None = None) -> list[dict]:
    return frappe.get_list(
        "Vault Secret",
        filters={"password_strength": ("in", ["weak", "fair"])},
        fields=["name", "title", "password_strength", "url", "password_last_changed"],
    )
