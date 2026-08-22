// Vault Secret Form Script
// Follows Frappe Desk UI patterns and guidelines

frappe.ui.form.on("Vault Secret", {
    setup(frm) {
        // Set up Link field filters
        frm.set_query("category", () => ({
            filters: { is_group: 0 }
        }));
    },

    refresh(frm) {
        // Clear any existing custom buttons
        frm.clear_custom_buttons();

        // Set up the form based on document state
        frappe_vault.setup_vault_secret_form(frm);

        // Automatic rotation controls
        frappe_vault.setup_rotation_ui(frm);
    },

    secret_type(frm) {
        // Toggle field visibility based on secret type
        frappe_vault.toggle_secret_fields(frm);
    },

    validate(frm) {
        // Client-side validation
        if (frm.doc.secret_type === "Password" && !frm.doc.password && !frm.is_new()) {
            // Allow empty password on existing docs
        }
    }
});

// Child table events for shared_with
frappe.ui.form.on("Vault Secret Share", {
    user(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.user === frappe.session.user) {
            frappe.model.set_value(cdt, cdn, "user", "");
            frappe.show_alert({
                message: __("You cannot share a secret with yourself"),
                indicator: "orange"
            });
        }
    }
});

// Automatic password rotation: schedule summary + manual trigger.
// Self-contained so it does not depend on the older helpers in this file.
frappe_vault.setup_rotation_ui = function(frm) {
    if (frm.is_new() || frm.doc.secret_type !== "Password") {
        return;
    }

    if (frm.doc.enable_rotation && frm.doc.next_rotation_on) {
        const passphrase_note = frm.doc.has_zip_passphrase
            ? __(" Its archive opens with this secret's own custom passphrase, not the shared site one.")
            : "";
        frm.set_intro(
            __("Automatic rotation is on. Next rotation {0} — every {1} {2}. A new password will be emailed to everyone with access as an encrypted archive, and will need applying to the target system manually.", [
                frappe.datetime.str_to_user(frm.doc.next_rotation_on),
                frm.doc.rotation_interval,
                frm.doc.rotation_unit ? frm.doc.rotation_unit.toLowerCase() : ""
            ]) + passphrase_note,
            "blue"
        );
    }

    if (frm.doc.has_zip_passphrase) {
        frm.add_custom_button(__("Remove Passphrase Protection"), () => {
            frappe.confirm(
                __("Remove the custom passphrase from <strong>{0}</strong>? Its rotation archive will go back to opening with the shared site passphrase instead.", [
                    frappe.utils.escape_html(frm.doc.title)
                ]),
                () => {
                    frappe.call({
                        method: "frappe_vault.api.secrets.clear_zip_passphrase",
                        args: { name: frm.doc.name }
                    }).then((r) => {
                        if (r.message && r.message.success) {
                            frappe.show_alert({ message: __("Passphrase protection removed"), indicator: "green" });
                            frm.reload_doc();
                        }
                    });
                }
            );
        }, __("Rotation"));
    }

    if (!frm.doc.enable_rotation) {
        return;
    }

    frm.add_custom_button(__("Rotate Now"), () => {
        frappe.confirm(
            __("Generate a new password for <strong>{0}</strong> now and email it to everyone with access?<br><br>The current password will be replaced in Vault. It will <strong>not</strong> be changed on the target system — you must apply it there yourself.", [
                frappe.utils.escape_html(frm.doc.title)
            ]),
            () => frappe_vault.run_rotate_now(frm)
        );
    }, __("Rotation"));
};

frappe_vault.run_rotate_now = function(frm) {
    frappe.dom.freeze(__("Rotating password..."));
    frappe.call({
        method: "frappe_vault.api.secrets.rotate_now",
        args: { name: frm.doc.name }
    }).then((r) => {
        frappe.dom.unfreeze();
        if (r.message && r.message.success) {
            frappe.show_alert({ message: r.message.message, indicator: "green" });
            frm.reload_doc();
        }
    }).catch(() => {
        frappe.dom.unfreeze();
    });
};

frappe_vault.setup_vault_secret_form = function(frm) {
    // Add password strength indicator to dashboard
    if (frm.doc.password_strength) {
        frappe_vault.add_strength_indicator(frm);
    }


    // Toggle secret type specific fields
    frappe_vault.toggle_secret_fields(frm);

    // Setup buttons based on document state
    if (!frm.is_new()) {
        frappe_vault.setup_action_buttons(frm);
    }
};

frappe_vault.toggle_secret_fields = function(frm) {
    // Show/hide fields based on secret type
    const type = frm.doc.secret_type;

    // Password fields
    frm.toggle_display("password", type === "Password");
    frm.toggle_display("username", ["Password", "API Key"].includes(type));
    frm.toggle_display("url", ["Password", "API Key"].includes(type));
    frm.toggle_display("totp_secret", ["Password", "API Key"].includes(type));

    // API Key fields
    frm.toggle_display("api_key", type === "API Key");
    frm.toggle_display("api_secret", type === "API Key");

    // Notes always visible but more prominent for Note type
    frm.toggle_display("notes", true);
    frm.set_df_property("notes", "reqd", type === "Note");
};

frappe_vault.setup_action_buttons = function(frm) {
    // Copy Username button
    if (frm.doc.username) {
        frm.add_custom_button(__("Copy Username"), () => {
            frappe_vault.copy_to_clipboard(frm.doc.username, __("Username"));
        }, __("Actions"));
    }

    // Secret type specific actions
    if (frm.doc.secret_type === "Password") {
        frm.add_custom_button(__("Copy Password"), () => {
            frappe_vault.reveal_password(frm.doc.name, (data) => {
                if (data.password) {
                    frappe_vault.copy_to_clipboard(data.password, __("Password"));
                }
            });
        }, __("Actions"));

        frm.add_custom_button(__("Reveal Password"), () => {
            frappe_vault.reveal_password(frm.doc.name, (data) => {
                if (data.password) {
                    frappe_vault.show_revealed_secret(__("Password"), data.password);
                }
            });
        }, __("Actions"));
    }

    if (frm.doc.secret_type === "API Key") {
        if (frm.doc.api_key) {
            frm.add_custom_button(__("Copy API Key"), () => {
                frappe_vault.copy_to_clipboard(frm.doc.api_key, __("API Key"));
            }, __("Actions"));
        }

        frm.add_custom_button(__("Copy API Secret"), () => {
            frappe_vault.reveal_password(frm.doc.name, (data) => {
                if (data.api_secret) {
                    frappe_vault.copy_to_clipboard(data.api_secret, __("API Secret"));
                }
            });
        }, __("Actions"));

        frm.add_custom_button(__("Reveal API Secret"), () => {
            frappe_vault.reveal_password(frm.doc.name, (data) => {
                if (data.api_secret) {
                    frappe_vault.show_revealed_secret(__("API Secret"), data.api_secret);
                }
            });
        }, __("Actions"));
    }

    // TOTP Code Action
    if (["Password", "API Key"].includes(frm.doc.secret_type)) {
        if (frm.doc.totp_secret) {
            frm.add_custom_button(__("Get TOTP Code"), () => {
                frappe_vault.show_totp_dialog(frm);
            }, __("Actions"));
        }
    }

    // URL actions
    if (frm.doc.url) {
        frm.add_custom_button(__("Copy URL"), () => {
            frappe_vault.copy_to_clipboard(frm.doc.url, __("URL"));
        }, __("Actions"));

        frm.add_custom_button(__("Open URL"), () => {
            window.open(frm.doc.url, "_blank");
        }, __("Actions"));
    }
};

frappe_vault.add_strength_indicator = function(frm) {
    // Use Frappe's standard indicator colors
    const indicator_map = {
        weak: { color: "red", label: __("Weak Password") },
        fair: { color: "orange", label: __("Fair Password") },
        good: { color: "yellow", label: __("Good Password") },
        strong: { color: "green", label: __("Strong Password") },
        excellent: { color: "blue", label: __("Excellent Password") }
    };

    const indicator = indicator_map[frm.doc.password_strength];
    if (indicator) {
        frm.dashboard.add_indicator(indicator.label, indicator.color);
    }
};


frappe_vault.show_revealed_secret = function(label, value) {
    // Use Frappe's standard dialog for revealing secrets
    const d = new frappe.ui.Dialog({
        title: label,
        fields: [
            {
                fieldname: "value",
                fieldtype: "Code",
                label: label,
                read_only: 1,
                default: value
            }
        ],
        primary_action_label: __("Copy"),
        primary_action: () => {
            frappe_vault.copy_to_clipboard(value, label);
            d.hide();
        }
    });
    d.show();
};

frappe_vault.show_totp_dialog = function(frm) {
    let d = new frappe.ui.Dialog({
        title: __("TOTP Code"),
        fields: [
            {
                fieldname: "totp_display",
                fieldtype: "HTML"
            }
        ],
        primary_action_label: __("Copy"),
        primary_action: () => {
            if (d.current_code) {
                frappe_vault.copy_to_clipboard(d.current_code, __("TOTP Code"));
                d.hide();
            }
        }
    });

    let fetch_totp = () => {
        frappe.call({
            method: "frappe_vault.api.secrets.get_totp",
            args: {
                name: frm.doc.name
            },
            callback: function(r) {
                if (r.message && r.message.code) {
                    let code = r.message.code;
                    let remaining = r.message.remaining_seconds;
                    let qr_svg = r.message.qr_svg || '';
                    d.current_code = code;

                    let render_totp = (c, r_sec, svg) => {
                        let indicator_color = r_sec > 5 ? 'var(--blue-500, #2490ef)' : 'var(--red-500, #ff5858)';
                        let qr_html = svg ? `<div style="margin-bottom: 20px; display: flex; justify-content: center;">${svg}</div>` : '';
                        let html = `
                            <div style="text-align: center; padding: 10px 0;">
                                ${qr_html}
                                <div style="font-family: monospace; font-size: 2.5em; font-weight: bold; letter-spacing: 4px; color: var(--text-color);">${c.slice(0,3)} ${c.slice(3)}</div>
                                <div style="margin-top: 10px; font-size: 0.9em; color: var(--text-muted); display: flex; align-items: center; justify-content: center;">
                                    <span style="display:inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${indicator_color}; margin-right: 8px;"></span>
                                    ${r_sec} seconds remaining
                                </div>
                            </div>
                        `;
                        d.get_field("totp_display").$wrapper.html(html);
                    };

                    render_totp(code, remaining, qr_svg);

                    if (d.totp_interval) {
                        clearInterval(d.totp_interval);
                    }

                    d.totp_interval = setInterval(() => {
                        remaining -= 1;
                        if (remaining <= 0) {
                            clearInterval(d.totp_interval);
                            fetch_totp();
                        } else {
                            render_totp(code, remaining, qr_svg);
                        }
                    }, 1000);
                } else {
                    let err_msg = (r.message && r.message.error) ? r.message.error : __("Invalid or missing TOTP secret.");
                    d.get_field("totp_display").$wrapper.html(`<div class="text-muted text-center py-4" style="color: var(--red-500);">${err_msg}</div>`);
                }
            }
        });
    };

    d.onhide = () => {
        if (d.totp_interval) {
            clearInterval(d.totp_interval);
        }
    };

    d.show();
    fetch_totp();
};

frappe_vault.reveal_password = function(name, callback) {
    frappe.call({
        method: "frappe_vault.api.secrets.decrypt",
        args: { name: name },
        callback: function(r) {
            if (r.message && r.message.decrypted) {
                if (callback) callback(r.message.decrypted);
            }
        }
    });
};
