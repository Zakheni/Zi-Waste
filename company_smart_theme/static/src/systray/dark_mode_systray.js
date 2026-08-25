/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { DARK_MODE_ENABLED } from "../js/theme_config";

export class DarkModeSystray extends Component {
    static template = "company_smart_theme.DarkModeSystray";

    setup() {
        this.colorScheme = useService("color_scheme");
    }

    get isDark() {
        return this.colorScheme.isDark;
    }

    get title() {
        return this.isDark ? "Switch to light mode" : "Switch to dark mode";
    }

    onToggle() {
        this.colorScheme.toggle();
    }
}

export const darkModeSystrayItem = {
    Component: DarkModeSystray,
};

if (DARK_MODE_ENABLED) {
    registry.category("systray").add("company_smart_theme.dark_mode", darkModeSystrayItem, {
        sequence: 35,
    });
}
