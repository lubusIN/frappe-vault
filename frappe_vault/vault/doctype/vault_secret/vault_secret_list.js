// Vault Secret List View Script
// Follows Frappe Desk UI patterns and guidelines

frappe.listview_settings["Vault Secret"] = {
    // Additional fields to fetch for list view
    add_fields: ["secret_type", "category", "is_bookmark", "password_strength", "last_accessed", "owner"],

    // Default filters - show user's own secrets
    filters: [
        ["owner", "=", frappe.session.user]
    ],

    // Status indicator based on password strength
    get_indicator(doc) {
        if (!doc.password_strength) {
            return ["", "grey", ""];
        }

        const indicator_map = {
            weak: [__("Weak"), "red", "password_strength,=,weak"],
            fair: [__("Fair"), "orange", "password_strength,=,fair"],
            good: [__("Good"), "yellow", "password_strength,=,good"],
            strong: [__("Strong"), "green", "password_strength,=,strong"],
            excellent: [__("Excellent"), "blue", "password_strength,=,excellent"]
        };

        return indicator_map[doc.password_strength] || ["", "grey", ""];
    },

    // Custom formatters for columns
    formatters: {
        title(value, df, doc) {
            // Show bookmark icon using Frappe icon
            if (doc.is_bookmark) {
                return `<span class="text-warning">${frappe.utils.icon("es-solid-bookmark", "sm")}</span> ${frappe.utils.escape_html(value)}`;
            }
            return frappe.utils.escape_html(value);
        },

        secret_type(value) {
            // Use Frappe icons instead of emojis
            const icon_map = {
                "Password": "lock",
                "API Key": "key",
                "Note": "file",
                "SSH Key": "es-solid-code-block",
                "Certificate": "es-solid-certificate",
                "Other": "folder-normal"
            };
            const icon = icon_map[value] || "folder-normal";
            return `${frappe.utils.icon(icon, "sm")} ${__(value)}`;
        },

        category(value) {
            if (!value) return "";
            return `<span class="text-muted">${frappe.utils.icon("folder-normal", "xs")} ${frappe.utils.escape_html(value)}</span>`;
        }
    },

    // Row button for quick copy action
    button: {
        show(doc) {
            return doc.secret_type === "Password" || doc.secret_type === "API Key";
        },
        get_label() {
            return __("Copy");
        },
        get_description(doc) {
            return __("Copy secret for {0}", [doc.title]);
        },
        action(doc) {
            frappe_vault.reveal_password(doc.name, (data) => {
                if (data.password) {
                    frappe_vault.copy_to_clipboard(data.password, __("Password"));
                } else if (data.api_secret) {
                    frappe_vault.copy_to_clipboard(data.api_secret, __("API Secret"));
                }
            });
        }
    },

    // Setup on list view load
    onload(listview) {
        // Add "Bookmarks Only" filter toggle
        listview.page.add_inner_button(__("Bookmarks"), () => {
            const has_filter = listview.filter_area.get().some(f => f[1] === "is_bookmark");

            if (has_filter) {
                listview.filter_area.remove("is_bookmark");
            } else {
                listview.filter_area.add([[listview.doctype, "is_bookmark", "=", 1]]);
            }
        }, __("Filter"));

        // Add type filters
        ["Password", "API Key", "Note"].forEach(type => {
            listview.page.add_inner_button(__(type), () => {
                const has_filter = listview.filter_area.get().some(f =>
                    f[1] === "secret_type" && f[3] === type
                );

                if (has_filter) {
                    listview.filter_area.remove("secret_type");
                } else {
                    listview.filter_area.remove("secret_type");
                    listview.filter_area.add([[listview.doctype, "secret_type", "=", type]]);
                }
            }, __("Filter"));
        });

        // Add bulk actions
        listview.page.add_action_item(__("Add to Bookmarks"), () => {
            const names = listview.get_checked_items().map(i => i.name);

            frappe.call({
                method: "frappe.client.set_value",
                args: {
                    doctype: "Vault Secret",
                    name: names,
                    fieldname: "is_bookmark",
                    value: 1
                },
                callback: function (r) {
                    if (!r.exc) {
                        frappe.show_alert({
                            message: __("{0} secrets added to bookmarks", [names.length]),
                            indicator: "green"
                        });
                        listview.refresh();
                    }
                }
            });
        });

        listview.page.add_action_item(__("Remove from Bookmarks"), () => {
            const names = listview.get_checked_items(true);
            if (!names.length) {
                frappe.toast(__("Please select secrets first"));
                return;
            }

            frappe.xcall("frappe.client.set_value", {
                doctype: "Vault Secret",
                name: names,
                fieldname: "is_bookmark",
                value: 0
            }).then(() => {
                listview.refresh();
                frappe.show_alert({
                    message: __("{0} secrets removed from bookmarks", [names.length]),
                    indicator: "grey"
                });
            });
        });
    },

    // Primary action button
    primary_action() {
        frappe.new_doc("Vault Secret");
    },

    // Listing settings
    hide_name_column: false
};
