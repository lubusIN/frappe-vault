import re

import frappe
from frappe import _
from frappe.model.document import Document

PROSE_COLORS = {
    "red": "#dc2626",
    "blue": "#2563eb",
    "green": "#16a34a",
    "yellow": "#ca8a04",
    "orange": "#ea580c",
    "purple": "#9333ea",
    "pink": "#db2777",
    "gray": "#4b5563",
    "teal": "#0d9488",
    "cyan": "#0891b2",
}


def _strip_dev_port(url: str) -> str:
    """Remove :8000 from URLs when running through Frappe Local's reverse proxy."""
    return url.replace(":8000", "") if ":8000" in url else url


class VaultInvitation(Document):
    def before_insert(self):
        frappe.utils.validate_email_address(self.email, True)

        self.key = frappe.generate_hash(length=12)
        self.invited_by = frappe.session.user
        self.status = "Pending"

    def after_insert(self):
        self.invite_via_email()

    def invite_via_email(self):
        invite_link = _strip_dev_port(
            frappe.utils.get_url(f"/api/method/frappe_vault.api.user.accept_invitation?key={self.key}")
        )

        if frappe.local.dev_server:
            print(f"Invite link for {self.email}: {invite_link}")  # nosemgrep

        title = "Frappe Vault"
        args = {"title": title, "invite_link": invite_link}

        active_template = frappe.db.get_value("Email Template", {"vault_is_default": 1, "vault_enabled": 1})
        try:
            if active_template:
                template_doc = frappe.get_doc("Email Template", active_template)
                subject = frappe.render_template(template_doc.subject, args)
                response = template_doc.response_html if template_doc.use_html else template_doc.response
                content = frappe.render_template(response, args)

                # Fix Frappe UI TextEditor colors (CSS variables aren't supported in email clients)
                content = re.sub(
                    r"var\(--prose-color-(\w+)\)", lambda m: PROSE_COLORS.get(m.group(1), "inherit"), content
                )

                # Resolve relative image URLs to absolute (email clients cannot use relative paths)
                site_url = _strip_dev_port(frappe.utils.get_url())
                content = content.replace('src="/files/', f'src="{site_url}/files/')

                # Fallback to any enabled outgoing email account if a default isn't explicitly set
                account = frappe.db.get_value(
                    "Email Account",
                    {"default_outgoing": 1, "enable_outgoing": 1},
                    ["name", "email_id"],
                    as_dict=True,
                )
                if not account:
                    account = frappe.db.get_value(
                        "Email Account", {"enable_outgoing": 1}, ["name", "email_id"], as_dict=True
                    )

                sender = None
                if account:
                    from frappe.utils import formataddr

                    sender = formataddr((account.name, account.email_id))

                frappe.sendmail(
                    sender=sender,
                    recipients=self.email,
                    subject=subject,
                    content=content,
                    now=True,
                )
            else:
                account = frappe.db.get_value(
                    "Email Account",
                    {"default_outgoing": 1, "enable_outgoing": 1},
                    ["name", "email_id"],
                    as_dict=True,
                )
                if not account:
                    account = frappe.db.get_value(
                        "Email Account", {"enable_outgoing": 1}, ["name", "email_id"], as_dict=True
                    )

                sender = None
                if account:
                    from frappe.utils import formataddr

                    sender = formataddr((account.name, account.email_id))

                fallback_html = f"""<p>Hello,</p>
<p>You have been invited to join <strong>{title}</strong>.</p>
<p>Click the link below to accept your invitation:</p>
<p><a href="{invite_link}" style="display: inline-block; padding: 10px 20px; color: white; background-color: #007bff; text-decoration: none; border-radius: 5px;">Accept Invitation</a></p>
<p>If you have any questions, feel free to contact your administrator.</p>
<p>Thanks,<br>{title} Team</p>"""

                frappe.sendmail(
                    sender=sender,
                    recipients=self.email,
                    subject=f"You have been invited to join {title}",
                    content=fallback_html,
                    now=True,
                )
            self.db_set("email_sent_at", frappe.utils.now())
        except Exception as e:
            if "outgoing Email Account" in str(e):
                frappe.local.message_log = []
                frappe.throw(
                    _("Please configure an Email Account in Vault Settings > Email to send invitations.")
                )
            raise

    @frappe.whitelist(allow_guest=True)
    def accept_invitation(self):
        if self.accept():
            # the invitee was not around to set a password, mail them a link to do it
            user = frappe.get_doc("User", self.email)
            user.reset_password_key = frappe.generate_hash()
            user.db_set("reset_password_key", user.reset_password_key)

            update_link = _strip_dev_port(
                frappe.utils.get_url(f"/update-password?key={user.reset_password_key}")
            )

            try:
                # Fallback to any enabled outgoing email account if a default isn't explicitly set
                account = frappe.db.get_value(
                    "Email Account",
                    {"default_outgoing": 1, "enable_outgoing": 1},
                    ["name", "email_id"],
                    as_dict=True,
                )
                if not account:
                    account = frappe.db.get_value(
                        "Email Account", {"enable_outgoing": 1}, ["name", "email_id"], as_dict=True
                    )

                sender = None
                if account:
                    from frappe.utils import formataddr

                    sender = formataddr((account.name, account.email_id))

                fallback_html = f"""<p>Hello,</p>
<p>A password reset was requested for your Frappe Vault account.</p>
<p>Click the link below to set your new password:</p>
<p><a href="{update_link}" style="display: inline-block; padding: 10px 20px; color: white; background-color: #007bff; text-decoration: none; border-radius: 5px;">Set Password</a></p>"""

                frappe.sendmail(
                    sender=sender,
                    recipients=self.email,
                    subject="Set Your Password",
                    content=fallback_html,
                    now=True,
                )
            except Exception as e:
                if "outgoing Email Account" in str(e):
                    frappe.local.message_log = []
                    frappe.throw(
                        _(
                            "Please configure an Email Account in Vault Settings > Email to send password reset links."
                        )
                    )
                raise

    def accept(self):
        if self.status != "Pending":
            frappe.throw(_("Invalid or expired key"))

        user, is_new_user = self.create_user_if_not_exists()
        user.append_roles(self.role)
        if self.role == "Vault Admin":
            user.append_roles("Vault User")

        user.save(ignore_permissions=True)

        self.status = "Accepted"
        self.accepted_at = frappe.utils.now()
        self.key = None
        self.save(ignore_permissions=True)

        return is_new_user

    def create_user_if_not_exists(self):
        if not frappe.db.exists("User", self.email):
            first_name = self.email.split("@")[0].title()
            user = frappe.get_doc(
                doctype="User",
                user_type="System User",
                email=self.email,
                send_welcome_email=0,
                thread_notify=0,
                first_name=first_name,
                default_app="frappe_vault",
            ).insert(ignore_permissions=True)
            return user, True

        return frappe.get_doc("User", self.email), False


def expire_invitations():
    """Expire pending invitations after 3 days."""
    from frappe.utils import add_days, now

    days = 3
    invitations_to_expire = frappe.db.get_all(
        "Vault Invitation", filters={"status": "Pending", "creation": ["<", add_days(now(), -days)]}
    )
    for invitation in invitations_to_expire:
        invitation = frappe.get_doc("Vault Invitation", invitation.name)
        invitation.status = "Expired"
        invitation.save(ignore_permissions=True)
