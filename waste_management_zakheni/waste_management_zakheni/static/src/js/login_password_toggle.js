/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.WmzPasswordToggle = publicWidget.Widget.extend({
    selector: ".wmz-password-toggle",
    events: {
        "click .wmz-password-toggle-btn": "_onToggleClick",
    },

    _onToggleClick(ev) {
        ev.preventDefault();
        const btn = ev.currentTarget;
        const input = btn.closest(".wmz-password-toggle")?.querySelector("input");
        const icon = btn.querySelector("i");
        if (!input || !icon) {
            return;
        }
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        icon.classList.toggle("fa-eye", !show);
        icon.classList.toggle("fa-eye-slash", show);
        btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
    },
});
