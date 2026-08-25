/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const STORAGE_KEY = "wmz-theme";

function getStoredTheme() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "dark" || stored === "light" ? stored : null;
}

function getSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getActiveTheme() {
    return document.documentElement.getAttribute("data-wmz-theme") || getStoredTheme() || getSystemTheme();
}

function syncToggleButtons(theme) {
    document.querySelectorAll(".wmz-theme-toggle").forEach((btn) => {
        const darkIcon = btn.querySelector(".wmz-theme-icon-dark");
        const lightIcon = btn.querySelector(".wmz-theme-icon-light");
        if (darkIcon) {
            darkIcon.classList.toggle("d-none", theme === "dark");
        }
        if (lightIcon) {
            lightIcon.classList.toggle("d-none", theme !== "dark");
        }
        const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
        btn.setAttribute("aria-label", label);
        btn.setAttribute("title", label);
    });
}

function applyTheme(theme, persist = true) {
    document.documentElement.setAttribute("data-wmz-theme", theme);
    if (persist) {
        localStorage.setItem(STORAGE_KEY, theme);
    }
    syncToggleButtons(theme);
}

publicWidget.registry.WmzThemeToggle = publicWidget.Widget.extend({
    selector: ".wmz-theme-toggle",
    events: {
        click: "_onToggleClick",
    },
    start() {
        syncToggleButtons(getActiveTheme());
        return this._super(...arguments);
    },
    _onToggleClick(ev) {
        ev.preventDefault();
        applyTheme(getActiveTheme() === "dark" ? "light" : "dark");
    },
});
