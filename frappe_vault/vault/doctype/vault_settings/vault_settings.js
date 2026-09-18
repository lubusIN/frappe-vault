// Vault Settings Form Script
// Follows Frappe Desk UI patterns and guidelines

frappe.ui.form.on("Vault Settings", {
    setup(frm) {
        frm.meta.is_submittable = 0;
    },
    onload(frm) {
        frm.meta.is_submittable = 0;
        if (frm.doc.docstatus !== 0) {
            frm.doc.docstatus = 0;
        }
    },
    refresh(frm) {
        frm.meta.is_submittable = 0;
        frm.doc.docstatus = 0;

        // Force primary action button to Save (prevents Submit confirmation prompt)
        frm.page.clear_primary_action();
        frm.page.set_primary_action(__("Save"), function() {
            frm.save();
        });

        frm.add_custom_button(__("Purge Expired Logs Now"), function() {
            const retention = frm.doc.log_retention_days || 30;
            frappe.confirm(
                __("Delete audit logs older than {0} days?", [retention]),
                function() {
                    frappe.call({
                        method: "frappe_vault.background_jobs.log_cleanup.cleanup_old_logs",
                        freeze: true,
                        freeze_message: __("Purging old audit logs..."),
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: __("Log Cleanup Completed"),
                                    message: r.message.message,
                                    indicator: "green"
                                });
                            }
                        }
                    });
                }
            );
        }, __("Actions"));

        if (frm.doc.enable_hashicorp_vault) {
            frm.add_custom_button(__("Test HashiCorp Vault Connection"), function() {
                frappe.call({
                    method: "frappe_vault.api.hashicorp_vault.test_connection",
                    freeze: true,
                    freeze_message: __("Contacting HashiCorp Vault..."),
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.msgprint({
                                title: __("Connection Successful"),
                                message: r.message.message,
                                indicator: "green"
                            });
                        }
                    }
                });
            }, __("Actions"));
        }
    },
    validate(frm) {
        if (frm.doc.default_password_length && frm.doc.default_password_length < 4) {
            frappe.msgprint({
                title: __("Validation Error"),
                message: __("Default password length must be at least 4"),
                indicator: "red"
            });
            frappe.validated = false;
        }
    }
});
