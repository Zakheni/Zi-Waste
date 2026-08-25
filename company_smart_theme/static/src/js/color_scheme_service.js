/** @odoo-module **/

import { registry } from "@web/core/registry";
import { cookie } from "@web/core/browser/cookie";
import { browser } from "@web/core/browser/browser";
import { DARK_MODE_ENABLED } from "./theme_config";

export const colorSchemeService = {
    start() {
        if (!DARK_MODE_ENABLED && cookie.get("color_scheme") === "dark") {
            cookie.delete("color_scheme");
            browser.location.reload();
            return {};
        }

        const getScheme = () =>
            DARK_MODE_ENABLED && cookie.get("color_scheme") === "dark" ? "dark" : "light";

        return {
            get current() {
                return getScheme();
            },
            get isDark() {
                return getScheme() === "dark";
            },
            get enabled() {
                return DARK_MODE_ENABLED;
            },
            toggle() {
                if (!DARK_MODE_ENABLED) {
                    return;
                }
                if (getScheme() === "dark") {
                    cookie.delete("color_scheme");
                } else {
                    cookie.set("color_scheme", "dark");
                }
                browser.location.reload();
            },
        };
    },
};

registry.category("services").add("color_scheme", colorSchemeService);
